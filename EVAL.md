# Embedding Model Evaluation

Compare retrieval quality between embedding models by uploading a lecture video to one or more environments and running a set of natural language queries against each.

## Prerequisites

- Python 3.11+
- setup environment using requirements.txt
- AWS API Gateway URLs for the environments you want to test
- Each environment must have its embedding model configured and deployed (see [Switching models](#switching-models))

---

## Setup

### 1. Configure environments

Copy the example config and fill in your API Gateway URLs:

```bash
cp scripts/eval_config.example.json scripts/eval_config.json
```

Edit `scripts/eval_config.json`:

```json
{
  "state_file": "eval_state.json",
  "k": 5,
  "environments": [
    {
      "label": "Titan",
      "api_url": "https://<dev-api-id>.execute-api.ca-central-1.amazonaws.com/dev"
    },
    {
      "label": "jina-clip-v2",
      "api_url": "https://<eval-api-id>.execute-api.ca-central-1.amazonaws.com/eval"
    }
  ],
  "queries": "queries.txt"
}
```

You can add as many environments as needed — the script handles 1 or N.

### 2. Write your queries

Create `queries.txt` with one query per line. Use natural language that a student would actually search — paraphrase the lecture content rather than copying transcript phrases verbatim (keyword matches will score equally across models; semantic paraphrases reveal quality differences).

```
# queries.txt
What is gradient descent?
How do neural networks learn from errors?
Explain the vanishing gradient problem
What is the difference between training and validation loss?
How does dropout prevent overfitting?
```

Blank lines and lines starting with `#` are ignored. Aim for 10–20 queries covering different topics and difficulty levels.

### 3. Configure each environment's embedding model

Currently, the following environments have the corresponding models deployed

**Dev → Amazon Titan** (default, no changes needed)

**Eval → jina-clip-v2:**

```bash
# In LectureClip-Infra
# eval.tfvars already has:
#   embedding_model_id  = "modal-jina-clip-v2"
#   modal_embedding_url = "https://kuakimnguu--lectureclip-embeddings-embedder-embed.modal.run"

cd /path/to/LectureClip-Infra/terraform
terraform apply -var-file="environments/eval.tfvars"
```

Or update just the Lambda env vars without Terraform:

```bash
./scripts/deploy.sh \
  --env eval \
  --embedding-model-id modal-jina-clip-v2 \
  --modal-embedding-url https://kuakimnguu--lectureclip-embeddings-embedder-embed.modal.run
```

---

## Running the eval

### Step 1 — Upload the video

Upload the same video file to all configured environments:

```bash
python scripts/eval_models.py upload \
  --config scripts/eval_config.json \
  --video /path/to/lecture.mp4
```

Each environment receives the file and returns a unique video ID (the S3 key). These are saved automatically to `eval_state.json`.

**Example output:**
```
Uploading lecture.mp4 to 2 environment(s)...

  [Titan (dev)] uploading to https://...
  [Titan (dev)] video ID: 2024-01-15T10:00:00.000000/user-123/lecture.mp4

  [jina-clip-v2 (eval)] uploading to https://...
  [jina-clip-v2 (eval)] video ID: 2024-01-15T10:00:01.000000/user-123/lecture.mp4

  State saved to eval_state.json

  Wait for the processing pipeline to complete, then run:

    python scripts/eval_models.py eval --config scripts/eval_config.json
```

### Step 2 — Wait for processing

After upload, the Step Functions pipeline runs in each environment:
1. Amazon Transcribe transcribes the audio (~1–5 min depending on video length)
2. The embedding container extracts frames and generates frame embeddings
3. `process-results` generates text embeddings and writes everything to Aurora

You can monitor progress in the [AWS Step Functions console](https://console.aws.amazon.com/states).

### Step 3 — Run the comparison

```bash
python scripts/eval_models.py eval --config scripts/eval_config.json
```

**Example output (2 environments):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUERY: What is gradient descent?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ── Titan (dev) ──────────────────   ── jina-clip-v2 (eval) ─────────────
    1. [0.821] We update the weights…    1. [0.743] Gradient descent is an…
    2. [0.798] The learning rate co…     2. [0.731] The optimizer adjusts…
    3. [0.761] So we compute the gr…     3. [0.704] Each iteration we move…
```

---

## Optional: Ground truth for metrics

To compute **Recall@k** and **MRR**, add a `ground_truth` block to your config mapping each query to the segment IDs of the correct results.

Segment IDs are returned by the `query-info` endpoint (`segmentId` field). Run a query once against a known-good environment to get them:

```bash
curl -s -X POST \
  https://<api-url>/query-info \
  -H 'Content-Type: application/json' \
  -d '{"videoId": "<video-id>", "query": "What is gradient descent?", "k": 10}' \
  | python3 -m json.tool
```

Then add the relevant segment IDs to the config:

```json
{
  "ground_truth": {
    "What is gradient descent?": ["seg-uuid-1", "seg-uuid-3"],
    "How does backpropagation work?": ["seg-uuid-7"]
  }
}
```

With ground truth, the eval output includes per-query and aggregate metrics:

```
  Recall@5: Titan (dev)=0.50  jina-clip-v2 (eval)=1.00
  MRR:      Titan (dev)=0.50  jina-clip-v2 (eval)=1.00

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY (8 queries with ground truth)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Environment                  Recall@5         MRR
  ──────────────────────────   ──────────────   ──────────────
  Titan (dev)                  0.612            0.541
  jina-clip-v2 (eval)          0.743            0.698
```

---

## Config reference

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `environments` | array | yes | — | List of environments to test |
| `environments[].label` | string | yes | — | Display name |
| `environments[].api_url` | string | yes | — | API Gateway base URL |
| `queries` | string or array | yes | — | Path to `.txt` file or inline list of queries |
| `k` | number | no | `5` | Number of results to retrieve per query |
| `state_file` | string | no | `eval_state.json` | Where to save/load upload state |
| `ground_truth` | object | no | `{}` | Map of query → relevant segment ID list |

---

## Switching models

| Model | Environment variable | Value |
|---|---|---|
| Amazon Titan | `EMBEDDING_MODEL_ID` | `amazon.titan-embed-image-v1` |
| jina-clip-v2 | `EMBEDDING_MODEL_ID` + `MODAL_EMBEDDING_URL` | `modal-jina-clip-v2` + endpoint URL |

See `CLAUDE.md` for full deployment instructions and the `LectureClip-Infra` repo for Terraform-based configuration.