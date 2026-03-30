import json
import os
import urllib.request

import boto3
from botocore.config import Config
from constants import Model

_retry_config = Config(retries={"max_attempts": 10, "mode": "adaptive"})
bedrock = boto3.client("bedrock-runtime", config=_retry_config)


# ── embedding ─────────────────────────────────────────────────────────────────

def _titan_body(text: str, embedding_dim: int) -> str:
    return json.dumps({
        "inputText": text,
        "embeddingConfig": {"outputEmbeddingLength": embedding_dim},
    })


def _cohere_body(text: str, embedding_dim: int) -> str:
    return json.dumps({
        "input_type": "search_document",
        "text": text,
        "output_dimension": embedding_dim,
    })


def _embed_modal(text: str) -> list:
    url = os.environ["MODAL_EMBEDDING_URL"]
    payload = json.dumps({"type": "text", "data": text}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["embedding"]


def embed_text(text: str, model_id: Model, embedding_dim: int) -> list:
    if model_id == Model.MODAL_JINA_CLIP_V2:
        return _embed_modal(text)

    if model_id == Model.AMAZON_TITAN_EMBED_IMAGE:
        body = _titan_body(text, embedding_dim)
    elif model_id == Model.COHERE_EMBED_V4:
        body = _cohere_body(text, embedding_dim)
    else:
        raise ValueError(f"Invalid model ID: {model_id}")

    response = bedrock.invoke_model(
        body=body,
        modelId=model_id.value,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


# ── LLM inference ─────────────────────────────────────────────────────────────

def chat(messages: list, system_prompt: str, model_id: str, max_tokens: int = 1024) -> str:
    """Invoke Claude via Bedrock Converse API. Returns the assistant text response."""
    response = bedrock.converse(
        modelId=model_id,
        inferenceConfig={"maxTokens": max_tokens},
        system=[{"text": system_prompt}],
        messages=messages,
    )
    for block in response["output"]["message"]["content"]:
        if "text" in block:
            return block["text"]
    return ""