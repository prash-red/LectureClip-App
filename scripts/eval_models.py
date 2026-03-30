#!/usr/bin/env python3
"""
eval_models.py — upload a video to one or more environments and compare retrieval quality.

STEP 1 — Upload the video to all configured environments:

    python scripts/eval_models.py upload --config eval_config.json --video lecture.mp4

    Uploads to every environment in the config, saves the assigned video IDs to
    eval_state.json, then prints instructions for step 2.
    Wait for the Step Functions pipeline to finish before running step 2.

STEP 2 — Compare retrieval results across all environments:

    python scripts/eval_models.py eval --config eval_config.json

    Reads video IDs from eval_state.json (written by step 1), queries every
    environment, and prints ranked results side by side (or stacked for >2 envs).

CONFIG FILE (eval_config.json):
    {
      "state_file": "eval_state.json",   // optional, default: eval_state.json
      "k": 5,                            // optional, default: 5
      "environments": [
        {
          "label": "Titan (dev)",
          "api_url": "https://<dev-api>.execute-api.ca-central-1.amazonaws.com/dev"
        },
        {
          "label": "jina-clip-v2 (eval)",
          "api_url": "https://<eval-api>.execute-api.ca-central-1.amazonaws.com/eval"
        }
      ],
      "queries": [                       // inline list OR a path string to a .txt file
        "What is gradient descent?",
        "How does backpropagation work?"
      ],
      "ground_truth": {                  // optional
        "What is gradient descent?": ["seg-uuid-1", "seg-uuid-3"]
      }
    }

    "queries" can also be a file path:
      "queries": "queries.txt"
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from upload_video import UploadManager, UploadConfig


# ── types ─────────────────────────────────────────────────────────────────────

@dataclass
class Env:
    label:    str
    api_url:  str
    video_id: str = ""          # filled in after upload

@dataclass
class EvalConfig:
    environments: list[Env]
    queries:      list[str]
    k:            int = 5
    state_file:   str = "eval_state.json"
    ground_truth: dict[str, list[str]] = field(default_factory=dict)

@dataclass
class Segment:
    segment_id: str
    start:      float
    end:        float
    idx:        int
    text:       str
    similarity: float

    def short_text(self, width=80):
        t = self.text.replace("\n", " ")
        return t[:width] + "…" if len(t) > width else t


# ── config loading ─────────────────────────────────────────────────────────────

def load_config(config_path: str) -> EvalConfig:
    raw = json.loads(Path(config_path).read_text())

    environments = [
        Env(label=e["label"], api_url=e["api_url"])
        for e in raw["environments"]
    ]

    # queries can be an inline list or a path to a .txt file
    queries_val = raw["queries"]
    if isinstance(queries_val, str):
        queries = load_queries_file(queries_val)
    else:
        queries = [q.strip() for q in queries_val if q.strip()]

    return EvalConfig(
        environments=environments,
        queries=queries,
        k=raw.get("k", 5),
        state_file=raw.get("state_file", "eval_state.json"),
        ground_truth=raw.get("ground_truth", {}),
    )

def load_queries_file(path: str) -> list[str]:
    with open(path) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


# ── state persistence ─────────────────────────────────────────────────────────

def save_state(cfg: EvalConfig):
    state = {
        "environments": [
            {"label": e.label, "api_url": e.api_url, "video_id": e.video_id}
            for e in cfg.environments
        ]
    }
    Path(cfg.state_file).write_text(json.dumps(state, indent=2))

def load_state(cfg: EvalConfig):
    """Merge saved video_ids back into cfg.environments (matched by label)."""
    state_path = Path(cfg.state_file)
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text())
    by_label = {e["label"]: e["video_id"] for e in state["environments"]}
    for env in cfg.environments:
        if env.label in by_label:
            env.video_id = by_label[env.label]


# ── upload ────────────────────────────────────────────────────────────────────

def upload_to_env(env: Env, video_path: Path) -> str:
    config = UploadConfig()
    config.API_GATEWAY_URL = env.api_url
    result = UploadManager(config).upload_file(video_path, verbose=False)
    return result["file_key"]


# ── query ─────────────────────────────────────────────────────────────────────

def query_env(env: Env, query_text: str, k: int) -> list[Segment]:
    import urllib.request, urllib.error
    url = env.api_url.rstrip("/") + "/query-info"
    payload = json.dumps({"videoId": env.video_id, "query": query_text, "k": k}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} from {url}: {e.read().decode()}", file=sys.stderr)
        return []
    except urllib.error.URLError as e:
        print(f"  Request failed ({url}): {e.reason}", file=sys.stderr)
        return []
    return [
        Segment(
            segment_id=s["segmentId"], start=s["start"], end=s["end"],
            idx=s["idx"], text=s["text"], similarity=s["similarity"],
        )
        for s in data.get("segments", [])
    ]


# ── metrics ───────────────────────────────────────────────────────────────────

def recall_at_k(results: list[Segment], relevant: list[str]) -> float:
    if not relevant:
        return 0.0
    return sum(1 for s in results if s.segment_id in relevant) / len(relevant)

def reciprocal_rank(results: list[Segment], relevant: list[str]) -> float:
    for rank, s in enumerate(results, start=1):
        if s.segment_id in relevant:
            return 1.0 / rank
    return 0.0


# ── display ───────────────────────────────────────────────────────────────────

def print_results(
    query_text: str,
    results_by_env: list[tuple[Env, list[Segment]]],
    relevant: list[str] | None,
    k: int,
):
    width = 72
    print(f"\n{'━' * width}")
    print(f"QUERY: {query_text}")
    print(f"{'━' * width}")

    n = len(results_by_env)

    if n == 2:
        # side-by-side for two environments
        col_w = (width - 3) // 2
        (env_a, res_a), (env_b, res_b) = results_by_env
        print(f"  {'── ' + env_a.label + ' ':-<{col_w}}   {'── ' + env_b.label + ' ':-<{col_w}}")

        for i in range(max(len(res_a), len(res_b))):
            def fmt(results, i):
                if i >= len(results):
                    return ""
                s = results[i]
                hit = "✓" if relevant and s.segment_id in relevant else " "
                return f"{hit} {i+1}. [{s.similarity:.3f}] {s.short_text(col_w - 14)}"
            print(f"  {fmt(res_a, i):<{col_w}}   {fmt(res_b, i):<{col_w}}")

    else:
        # stacked for 1 or 3+ environments
        for env, results in results_by_env:
            print(f"\n  ── {env.label}")
            if not results:
                print("     (no results)")
                continue
            for i, s in enumerate(results):
                hit = "✓" if relevant and s.segment_id in relevant else " "
                print(f"  {hit} {i+1}. [{s.similarity:.3f}] {s.short_text(width - 12)}")

    if relevant is not None:
        print()
        for env, results in results_by_env:
            r  = recall_at_k(results, relevant)
            rr = reciprocal_rank(results, relevant)
            print(f"  {env.label:<24} Recall@{k}={r:.2f}  MRR={rr:.2f}")


def print_summary(
    summary: dict[str, dict[str, list[float]]],
    k: int,
):
    n = next(len(v["recall"]) for v in summary.values())
    if n == 0:
        return

    avg = lambda lst: sum(lst) / len(lst) if lst else 0.0
    width = 72

    print(f"\n{'━' * width}")
    print(f"SUMMARY ({n} queries with ground truth)")
    print(f"{'━' * width}")
    print(f"  {'Environment':<28} {'Recall@' + str(k):<16} {'MRR':<16}")
    print(f"  {'─'*26}  {'─'*14}  {'─'*14}")
    for label, metrics in summary.items():
        print(f"  {label:<28} {avg(metrics['recall']):<16.3f} {avg(metrics['mrr']):<16.3f}")


# ── subcommands ───────────────────────────────────────────────────────────────

def cmd_upload(args):
    cfg = load_config(args.config)
    video_path = Path(args.video).resolve()
    if not video_path.exists():
        print(f"Error: file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Uploading {video_path.name} to {len(cfg.environments)} environment(s)...\n")
    for env in cfg.environments:
        print(f"  [{env.label}] uploading to {env.api_url} ...")
        env.video_id = upload_to_env(env, video_path)
        print(f"  [{env.label}] video ID: {env.video_id}\n")

    save_state(cfg)
    print(f"  State saved to {cfg.state_file}")
    print(f"\n  Wait for the processing pipeline to complete, then run:")
    print(f"\n    python scripts/eval_models.py eval --config {args.config}\n")


def cmd_eval(args):
    cfg = load_config(args.config)
    load_state(cfg)

    missing = [e.label for e in cfg.environments if not e.video_id]
    if missing:
        print(f"Error: no video_id for: {', '.join(missing)}", file=sys.stderr)
        print(f"Run the upload step first, or add video_ids to {cfg.state_file}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Environments:")
    for env in cfg.environments:
        print(f"    {env.label:<28} video: {env.video_id}")

    summary: dict[str, dict[str, list[float]]] = {
        e.label: {"recall": [], "mrr": []} for e in cfg.environments
    }

    for q in cfg.queries:
        results_by_env = [(env, query_env(env, q, cfg.k)) for env in cfg.environments]
        relevant = cfg.ground_truth.get(q)
        print_results(q, results_by_env, relevant, cfg.k)

        if relevant:
            for env, results in results_by_env:
                summary[env.label]["recall"].append(recall_at_k(results, relevant))
                summary[env.label]["mrr"].append(reciprocal_rank(results, relevant))

    print_summary(summary, cfg.k)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Upload a video to one or more environments and compare retrieval quality"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_upload = sub.add_parser("upload", help="Upload video to all configured environments")
    p_upload.add_argument("--config", required=True, help="Path to eval_config.json")
    p_upload.add_argument("--video",  required=True, help="Path to local video file")

    p_eval = sub.add_parser("eval", help="Compare retrieval results across all environments")
    p_eval.add_argument("--config", required=True, help="Path to eval_config.json")

    args = parser.parse_args()
    {"upload": cmd_upload, "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":
    main()