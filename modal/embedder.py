"""
LectureClip multimodal embedding service on Modal.

Deploys jinaai/jina-clip-v2 as a web endpoint that returns 1024-dim embeddings
for both images and text in a shared vector space — enabling cross-modal
similarity search (text query → nearest video frames).

Deploy:
    modal deploy modal/embedder.py

Set the deployed endpoint URL as MODAL_EMBEDDING_URL in the container's
environment to route get_image_embeddings.py calls to this service instead
of Bedrock.
"""

import modal

app = modal.App("lectureclip-embeddings")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(["torch", "transformers<5.0", "Pillow", "einops", "timm", "numpy", "fastapi[standard]", "requests"])
)

model_vol = modal.Volume.from_name("lectureclip-model-cache", create_if_missing=True)

MODEL_ID = "jinaai/jina-clip-v2"


@app.cls(
    image=image,
    gpu="T4",
    volumes={"/model-cache": model_vol},
    scaledown_window=100,
    min_containers=1,
)
class Embedder:

    @modal.enter()
    def load(self):
        import os
        from transformers import AutoModel

        os.environ["HF_HOME"] = "/model-cache"
        self.model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
        self.model = self.model.half().cuda().eval()

    @modal.fastapi_endpoint(method="POST")
    def embed(self, body: dict) -> dict:
        """
        Embed an image or text query into the shared 1024-dim vector space.

        Request (image):  { "type": "image", "data": "<base64-encoded bytes>" }
        Request (text):   { "type": "text",  "data": "<query string>" }
        Response:         { "embedding": [<1024 floats>] }
        """
        import base64
        import io
        import torch
        from PIL import Image

        input_type = body.get("type")

        import numpy as np

        with torch.no_grad():
            if input_type == "image":
                image_bytes = base64.b64decode(body["data"])
                pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                emb = self.model.encode_image([pil_image])
            elif input_type == "text":
                emb = self.model.encode_text([body["data"]])
            else:
                raise ValueError(f"Unknown type: {input_type!r}. Must be 'image' or 'text'.")

        emb = np.array(emb)
        emb = emb / np.linalg.norm(emb, axis=-1, keepdims=True)
        return {"embedding": emb[0].tolist()}