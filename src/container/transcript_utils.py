"""
Transcript parsing for the segment-frame container.

"""

import json

import boto3

s3 = boto3.client("s3")

_MAX_CHUNK_CHARS = 1000


def fetch_transcript_from_s3_uri(s3_uri: str) -> dict:
    """Download the Transcribe JSON result from an s3:// URI."""
    without_scheme = s3_uri.split("s3://", 1)[1]
    bucket, key = without_scheme.split("/", 1)
    resp = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read())


def _process_items(items):
    result = []
    for item in items:
        content = item["alternatives"][0]["content"]
        if item["type"] == "punctuation":
            if result:
                sec, spk, txt = result[-1]
                result[-1] = (sec, spk, txt + content)
        else:
            sec = int(float(item["start_time"]))
            spk = item.get("speaker_label", "spk_0")
            result.append((sec, spk, content))
    return result


def _combine_by_speaker(items):
    chunks = []
    cur_sec = cur_spk = cur_txt = None

    for sec, spk, txt in items:
        if cur_spk is None:
            cur_sec, cur_spk, cur_txt = sec, spk, txt
            continue

        if spk == cur_spk:
            cur_txt = f"{cur_txt} {txt}"
            if len(cur_txt) > _MAX_CHUNK_CHARS and cur_txt.rstrip().endswith((".", "!", "?")):
                chunks.append((cur_sec, cur_spk, cur_txt))
                cur_sec, cur_spk, cur_txt = sec, spk, txt
        else:
            chunks.append((cur_sec, cur_spk, cur_txt))
            cur_sec, cur_spk, cur_txt = sec, spk, txt

    if cur_txt is not None:
        if len(cur_txt) < 100 and chunks and chunks[-1][1] == cur_spk:
            last = chunks.pop()
            chunks.append((last[0], last[1], f"{last[2]} {cur_txt}"))
        else:
            chunks.append((cur_sec, cur_spk, cur_txt))

    return chunks


def parse_transcript(transcript_json: dict) -> list:
    """Return (start_second, speaker, text) tuples — one per speaker chunk."""
    items = transcript_json["results"]["items"]
    return _combine_by_speaker(_process_items(items))