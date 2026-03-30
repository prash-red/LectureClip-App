import json
import os

import dynamodb_utils
from aurora_utils import search_segments
from bedrock_utils import chat, embed_text
from constants import DEFAULT_CHAT_MODEL_ID, Model

EMBEDDING_MODEL_ID  = Model(os.environ["EMBEDDING_MODEL_ID"])
EMBEDDING_DIM       = int(os.environ.get("EMBEDDING_DIM", "1024"))
CHAT_MODEL_ID       = os.environ.get("CHAT_MODEL_ID", DEFAULT_CHAT_MODEL_ID)
CHAT_SESSIONS_TABLE = os.environ.get("CHAT_SESSIONS_TABLE", "")
BUCKET_NAME         = os.environ.get("BUCKET_NAME", "")

_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about lecture videos.
Answer using only the transcript excerpts provided in each question.
If the context does not contain enough information to answer, say so — do not make anything up.
For each key claim cite the relevant segment using [Segment N] notation."""

_CORS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _resp(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": _CORS, "body": json.dumps(body)}


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _build_context(segments: list[dict]) -> str:
    blocks = []
    for i, seg in enumerate(segments, start=1):
        blocks.append(
            f"[Segment {i}] ({_fmt_time(seg['start'])} – {_fmt_time(seg['end'])})\n{seg['text']}"
        )
    return "\n\n".join(blocks)


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")

        video_id   = body.get("videoId")
        query      = body.get("query")
        session_id = body.get("sessionId")
        k          = min(int(body.get("k", 5)), 10)
        model_id   = body.get("modelId", CHAT_MODEL_ID)

        if not video_id or not query:
            return _resp(400, {"error": "videoId and query are required"})

        # 1. Embed the query
        query_embedding = embed_text(query, EMBEDDING_MODEL_ID, EMBEDDING_DIM)

        # 2. Retrieve relevant segments
        # video_id is the S3 key returned by the upload endpoint; reconstruct
        # the full URI to match lectures.video_uri stored in the database.
        video_uri = f"s3://{BUCKET_NAME}/{video_id}" if BUCKET_NAME else video_id
        segments = search_segments(video_uri, query_embedding, k)
        if not segments:
            return _resp(200, {
                "answer":    "I couldn't find any relevant segments in this lecture for your question.",
                "sessionId": session_id,
                "segments":  [],
            })

        # 3. Load conversation history
        history = []
        if CHAT_SESSIONS_TABLE and session_id:
            history = dynamodb_utils.get_session(session_id)

        # 4. Build Converse API messages — inject retrieved context into user turn
        user_text = (
            f"Context from the lecture transcript:\n\n{_build_context(segments)}\n\n"
            f"Question: {query}"
        )
        messages = [
            *history,
            {"role": "user", "content": [{"text": user_text}]},
        ]

        # 5. Call Claude
        answer = chat(messages, _SYSTEM_PROMPT, model_id)

        # 6. Persist updated session history
        if CHAT_SESSIONS_TABLE:
            if not session_id:
                session_id = dynamodb_utils.new_session_id()
            dynamodb_utils.save_session(session_id, [
                *history,
                {"role": "user",      "content": [{"text": user_text}]},
                {"role": "assistant", "content": [{"text": answer}]},
            ])

        return _resp(200, {
            "answer":    answer,
            "sessionId": session_id,
            "segments":  [
                {
                    "segmentId":  s["segment_id"],
                    "start":      s["start"],
                    "end":        s["end"],
                    "idx":        s["idx"],
                    "text":       s["text"],
                    "similarity": s["similarity"],
                }
                for s in segments
            ],
        })

    except Exception as e:
        print(f"Error: {e}")
        return _resp(500, {"error": str(e)})