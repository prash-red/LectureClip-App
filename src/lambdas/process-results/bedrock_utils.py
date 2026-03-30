import json
import os
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from constants import Model

_RETRY_CONFIG = Config(retries={"mode": "adaptive", "max_attempts": 10})
bedrock = boto3.client("bedrock-runtime", config=_RETRY_CONFIG)

def create_titan_body(text, embedding_dim):
    return json.dumps({
        "inputText": text,
        "embeddingConfig": {
            "outputEmbeddingLength": embedding_dim,
        }
    })

def create_cohere_body(text, embedding_dim):
    return json.dumps({
        "input_type": "search_document",
        "text": text,
        "output_dimension": embedding_dim,
    })

def embed_text_modal(text: str) -> list:
    url = os.environ["MODAL_EMBEDDING_URL"]
    payload = json.dumps({"type": "text", "data": text}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["embedding"]

def embed_text(text, model_id, embedding_dim):
    """
    Return the embedding vector for *text* using the configured model.
    """

    if model_id == Model.MODAL_JINA_CLIP_V2:
        return embed_text_modal(text)

    if model_id == Model.AMAZON_TITAN_EMBED_IMAGE:
        body = create_titan_body(text, embedding_dim)
    elif model_id == Model.COHERE_EMBED_V4:
        body = create_cohere_body(text, embedding_dim)
    else:
        raise ValueError(f"Invalid model ID: {model_id}")

    response = bedrock.invoke_model(
        body=body,
        modelId=model_id.value,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def generate_text_embeddings(segments, source_uri, model_id, embedding_dim):
    """
    Generate an embedding for each (start_second, speaker, text) segment.

    Returns a list of dicts containing the vector and its associated metadata.
    Database storage is intentionally omitted here; the caller receives the
    full list for logging and will persist it in a future iteration.
    """
    filename = source_uri.rsplit("/", 1)[-1] if source_uri else ""
    created_at = datetime.now(timezone.utc).isoformat()

    def _embed(args):
        idx, (start_second, speaker, text) = args
        return idx, {
            "id": str(uuid.uuid4()),
            "embedding": embed_text(text, model_id, embedding_dim),
            "text": text,
            "start_second": start_second,
            "speaker": speaker,
            "source": filename,
            "source_uri": source_uri,
            "model_id": model_id.value,
            # All records belong to the same embedding batch, so one timestamp
            # avoids repeating datetime formatting work in the hot loop.
            "created_at": created_at,
        }

    results = [None] * len(segments)
    with ThreadPoolExecutor(max_workers=5) as pool:
        for idx, record in pool.map(_embed, enumerate(segments)):
            results[idx] = record
    return results
