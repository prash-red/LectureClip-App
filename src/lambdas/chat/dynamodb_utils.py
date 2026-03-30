import os
import time
import uuid

import boto3

dynamodb = boto3.resource("dynamodb")

_SESSION_TTL = 60 * 60 * 24  # 24 hours


def _table():
    return dynamodb.Table(os.environ["CHAT_SESSIONS_TABLE"])


def get_session(session_id: str) -> list[dict]:
    """Return the Converse API message history for a session, or [] if not found."""
    item = _table().get_item(Key={"session_id": session_id}).get("Item")
    return item["messages"] if item else []


def save_session(session_id: str, messages: list[dict]):
    """Persist the full Converse API message history for a session."""
    _table().put_item(Item={
        "session_id": session_id,
        "messages":   messages,
        "ttl":        int(time.time()) + _SESSION_TTL,
    })


def new_session_id() -> str:
    return str(uuid.uuid4())