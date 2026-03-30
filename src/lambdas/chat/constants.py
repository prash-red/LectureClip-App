from enum import Enum


class Model(Enum):
    AMAZON_TITAN_EMBED_IMAGE = "amazon.titan-embed-image-v1"
    COHERE_EMBED_V4 = "global.cohere.embed-v4:0"
    MODAL_JINA_CLIP_V2 = "modal-jina-clip-v2"


DEFAULT_CHAT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"