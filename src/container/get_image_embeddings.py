import base64
import json
import os

import boto3

bedrock = boto3.client("bedrock-runtime")

IMAGE_MODEL_ID = os.environ.get("FRAME_EMBEDDING_MODEL_ID", "amazon.titan-embed-image-v1")
EMBEDDING_DIM  = int(os.environ.get("EMBEDDING_DIM", "1024"))


def embed_image(image_bytes: bytes, model_id: str = IMAGE_MODEL_ID, embedding_dim: int = EMBEDDING_DIM) -> list:
    """Return a 1024-dim embedding vector for the given JPEG/PNG bytes."""
    body = json.dumps({
        "inputImage": base64.b64encode(image_bytes).decode("utf-8"),
        "embeddingConfig": {"outputEmbeddingLength": embedding_dim},
    })
    response = bedrock.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response["body"].read())["embedding"]