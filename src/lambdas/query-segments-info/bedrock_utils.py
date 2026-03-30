import json

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

def embed_text(text, model_id, embedding_dim):
    """
    Call Bedrock and return the embedding vector for *text*.
    """

    if model_id == Model.AMAZON_TITAN_EMBED_IMAGE:
        body = create_titan_body(text, embedding_dim)
    elif model_id == Model.COHERE_EMBED_V4:
        body = create_cohere_body(text, embedding_dim)
    else:
        raise ValueError("Invalid model ID")

    response = bedrock.invoke_model(
        body=body,
        modelId=model_id.value,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response["body"].read())["embedding"]