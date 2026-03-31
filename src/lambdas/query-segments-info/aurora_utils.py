"""
Aurora PostgreSQL helpers for the query-segments-info Lambda.

Performs a pgvector cosine similarity search over segment_embeddings,
joining back to segments to retrieve start/end timestamps, segment id,
index, and transcript text.
"""

import os

import boto3

CLUSTER_ARN = os.environ["AURORA_CLUSTER_ARN"]
SECRET_ARN  = os.environ["AURORA_SECRET_ARN"]
DB_NAME     = os.environ.get("AURORA_DB_NAME", "lectureclip")

rds_data = boto3.client("rds-data")

# Cosine similarity: 1 - (embedding <=> query_vector).
# HNSW index on segment_embeddings uses vector_cosine_ops so this query is
# index-accelerated.  Results are filtered to a single lecture and limited
# to k rows.
# DISTINCT ON (se.segment_id) ensures at most one row per segment even when
# both a text embedding and a frame embedding for the same chunk score in the
# top-k results (which happens when text and frames share the same model).
# The inner ORDER BY picks the highest-scoring modality for each segment;
# the outer query re-sorts the deduplicated rows before applying LIMIT.
# _SEARCH_SQL_ALL = """
# SELECT segment_id, start_s, end_s, idx, text, similarity
# FROM (
#     SELECT DISTINCT ON (se.segment_id)
#            s.segment_id,
#            s.start_s,
#            s.end_s,
#            s.idx,
#            s.text,
#            1 - (se.embedding <=> :vec::vector) AS similarity
#     FROM   segment_embeddings se
#     JOIN   segments s ON se.segment_id = s.segment_id
#     JOIN   lectures l ON s.lecture_id  = l.lecture_id
#     WHERE  l.video_uri = :video_uri
#     ORDER  BY se.segment_id, similarity DESC
# ) deduped
# ORDER  BY similarity DESC
# LIMIT  :k
# """
#
# _SEARCH_SQL_TEXT_ONLY = """
# SELECT segment_id, start_s, end_s, idx, text, similarity
# FROM (
#     SELECT DISTINCT ON (se.segment_id)
#            s.segment_id,
#            s.start_s,
#            s.end_s,
#            s.idx,
#            s.text,
#            1 - (se.embedding <=> :vec::vector) AS similarity
#     FROM   segment_embeddings se
#     JOIN   segments s ON se.segment_id = s.segment_id
#     JOIN   lectures l ON s.lecture_id  = l.lecture_id
#     WHERE  l.video_uri = :video_uri
#       AND  se.is_frame_embedding = FALSE
#     ORDER  BY se.segment_id, similarity DESC
# ) deduped
# ORDER  BY similarity DESC
# LIMIT  :k
# """

# Computes a weighted average of text and frame cosine similarities per segment.
# Each modality is joined separately so both scores are available simultaneously.
# Segments missing one modality get 0 for that modality's contribution.
# Segments with no embeddings at all are excluded by the HAVING clause.
_SEARCH_SQL_ALL = """
SELECT
    s.segment_id,
    s.start_s,
    s.end_s,
    s.idx,
    s.text,
    :text_weight * COALESCE(te.similarity, 0) + :frame_weight * COALESCE(fe.similarity, 0) AS similarity
FROM   segments s
JOIN   lectures l ON s.lecture_id = l.lecture_id
LEFT JOIN (
    SELECT DISTINCT ON (segment_id)
           segment_id, 1 - (embedding <=> :vec::vector) AS similarity
    FROM   segment_embeddings
    WHERE  is_frame_embedding = FALSE
    ORDER  BY segment_id, similarity DESC
) te ON s.segment_id = te.segment_id
LEFT JOIN (
    SELECT DISTINCT ON (segment_id)
           segment_id, 1 - (embedding <=> :vec::vector) AS similarity
    FROM   segment_embeddings
    WHERE  is_frame_embedding = TRUE
    ORDER  BY segment_id, similarity DESC
) fe ON s.segment_id = fe.segment_id
WHERE  l.video_uri = :video_uri
  AND  (te.similarity IS NOT NULL OR fe.similarity IS NOT NULL)
ORDER  BY similarity DESC
LIMIT  :k
"""

_SEARCH_SQL_TEXT_ONLY = """
SELECT segment_id, start_s, end_s, idx, text, is_frame_embedding, similarity
FROM (
    SELECT DISTINCT ON (se.segment_id) 
    s.segment_id,
           s.start_s,
           s.end_s,
           s.idx,
           s.text,
        se.is_frame_embedding,
           1 - (se.embedding <=> :vec::vector) AS similarity
    FROM   segment_embeddings se
    JOIN   segments s ON se.segment_id = s.segment_id
    JOIN   lectures l ON s.lecture_id  = l.lecture_id
    WHERE  l.video_uri = :video_uri
      AND  se.is_frame_embedding = FALSE
    ORDER  BY similarity DESC
) ranked
LIMIT  :k
"""

_SEARCH_SQL_FRAMES_ONLY = """
SELECT segment_id, start_s, end_s, idx, text, is_frame_embedding, similarity
FROM (
    SELECT DISTINCT ON (se.segment_id) 
    s.segment_id,
           s.start_s,
           s.end_s,
           s.idx,
           s.text,
        se.is_frame_embedding,
           1 - (se.embedding <=> :vec::vector) AS similarity
    FROM   segment_embeddings se
    JOIN   segments s ON se.segment_id = s.segment_id
    JOIN   lectures l ON s.lecture_id  = l.lecture_id
    WHERE  l.video_uri = :video_uri
      AND  se.is_frame_embedding = TRUE
    ORDER  BY similarity DESC
) ranked
LIMIT  :k
"""

def search_segments(video_uri: str, embedding: list, k: int, include_frames: bool = True, only_frames: bool = False, text_weight: float = 0.5, frame_weight: float = 0.5) -> list:
    """
    Return the top-k most similar segments for a video uri.

    Parameters
    ----------
    video_uri : str
        S3 URI of the video (e.g. "s3://bucket/key"). Matches lectures.video_uri.
    embedding : list[float]
        Query vector produced by bedrock_utils.embed_text().
    k : int
        Number of results to return.
    include_frames : bool
        When True, both text and frame embeddings are searched and the
        highest-scoring modality wins per segment.
        When False (default), only text embeddings are searched.

    Returns
    -------
    list of dicts ordered by similarity, each containing:
        segment_id, start, end, idx, text, similarity
    Each segment appears at most once — the highest-scoring embedding modality
    (text or frame) wins when both land in the candidate set.
    """
    print('##########include frames is ' + str(include_frames))

    if only_frames:
        sql = _SEARCH_SQL_FRAMES_ONLY
    elif include_frames:
        sql = _SEARCH_SQL_ALL
    else:
        sql = _SEARCH_SQL_TEXT_ONLY

    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

    params = [
        {"name": "vec",       "value": {"stringValue": vec_str}},
        {"name": "video_uri", "value": {"stringValue": video_uri}},
        {"name": "k",         "value": {"longValue": k}},
    ]
    if sql is _SEARCH_SQL_ALL:
        params += [
            {"name": "text_weight",  "value": {"doubleValue": text_weight}},
            {"name": "frame_weight", "value": {"doubleValue": frame_weight}},
        ]

    resp = rds_data.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DB_NAME,
        sql=sql,
        includeResultMetadata=True,
        parameters=params,
    )

    cols = [c["label"] for c in resp.get("columnMetadata", [])]
    rows = [
        dict(zip(cols, [list(field.values())[0] for field in row]))
        for row in resp.get("records", [])
    ]

    results = []
    for r in rows:
        entry = {
            "segmentId":  r["segment_id"],
            "start":      float(r["start_s"]),
            "end":        float(r["end_s"]),
            "idx":        int(r["idx"]),
            "text":       r["text"],
            "similarity": float(r["similarity"]),
        }
        if "is_frame_embedding" in r:
            entry["isFrameEmbedding"] = r["is_frame_embedding"]
        results.append(entry)
    return results