import base64
import json
import os

import boto3
import requests
from botocore.config import Config
from constants import Model

# adaptive mode automatically slows request rate when Bedrock returns throttling
# errors; max_attempts=10 gives more room than the default 4 before giving up.
_RETRY_CONFIG = Config(retries={"mode": "adaptive", "max_attempts": 10})
bedrock = boto3.client("bedrock-runtime", config=_RETRY_CONFIG)


def create_titan_body(image_bytes, embedding_dim):
    return json.dumps({
        "inputImage": base64.b64encode(image_bytes).decode("utf-8"),
        "embeddingConfig": {"outputEmbeddingLength": embedding_dim},
    })

def create_cohere_body(image_bytes, embedding_dim):
    return json.dumps({
        "input_type": "search_document",
        "images": [base64.b64encode(image_bytes).decode("utf-8")],
        "output_dimension": embedding_dim,
    })

def embed_image_modal(image_bytes: bytes) -> list:
    url = os.environ["MODAL_EMBEDDING_URL"]
    payload = {
        "type": "image",
        "data": base64.b64encode(image_bytes).decode("utf-8"),
    }
    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["embedding"]


def embed_image(image_bytes: bytes, model_id: Model, embedding_dim: int) -> list:
    """Return an embedding vector for the given JPEG/PNG bytes."""

    if model_id == Model.MODAL_JINA_CLIP_V2:
        return embed_image_modal(image_bytes)

    if model_id == Model.AMAZON_TITAN_EMBED_IMAGE:
        body = create_titan_body(image_bytes, embedding_dim)
    elif model_id == Model.COHERE_EMBED_V4:
        body = create_cohere_body(image_bytes, embedding_dim)
    else:
        raise ValueError(f"Invalid model ID: {model_id}")

    response = bedrock.invoke_model(
        body=body,
        modelId=model_id.value,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response["body"].read())["embedding"]