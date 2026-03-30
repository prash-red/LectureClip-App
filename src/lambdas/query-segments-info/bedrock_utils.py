import json
import os
import urllib.request

import boto3
from constants import Model

bedrock = boto3.client("bedrock-runtime")

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