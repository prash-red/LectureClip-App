import base64
import json

import boto3
from constants import Model

bedrock = boto3.client("bedrock-runtime")


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


def embed_image(image_bytes: bytes, model_id: Model, embedding_dim: int) -> list:
    """Return a 1024-dim embedding vector for the given JPEG/PNG bytes."""

    if model_id == Model.AMAZON_TITAN_EMBED_IMAGE:
        body = create_titan_body(image_bytes, embedding_dim)
    elif model_id == Model.COHERE_EMBED_V4:
        body = create_cohere_body(image_bytes, embedding_dim)
    else:
        raise ValueError("Invalid model ID")

    response = bedrock.invoke_model(
        body=body,
        modelId=model_id.value,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response["body"].read())["embedding"]