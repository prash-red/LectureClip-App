import json
import os

import boto3

rds = boto3.client("rds-data")

# Retrieves the k most similar segments for a video, deduplicating across text
# and frame embeddings so each transcript segment appears at most once.
_SEARCH_SQL = """
SELECT start_s, end_s, idx, segment_id, text, similarity
FROM (
    SELECT DISTINCT ON (se.segment_id)
           s.start_s, s.end_s, s.idx, s.segment_id, s.text,
           1 - (se.embedding <=> :vec::vector) AS similarity
    FROM segment_embeddings se
    JOIN segments s ON se.segment_id = s.segment_id
    JOIN lectures l ON s.lecture_id = l.lecture_id
    WHERE l.video_uri = :video_uri
    ORDER BY se.segment_id, similarity DESC
) deduped
ORDER BY similarity DESC
LIMIT :k
"""


def search_segments(video_uri: str, embedding: list, k: int) -> list[dict]:
    # print the SQL query with the substituted parameters
    print(_SEARCH_SQL.replace(":vec", str(embedding)).replace(":video_uri", video_uri).replace(":k", str(k)))
    response = rds.execute_statement(
        resourceArn=os.environ["AURORA_CLUSTER_ARN"],
        secretArn=os.environ["AURORA_SECRET_ARN"],
        database=os.environ["AURORA_DB_NAME"],
        sql=_SEARCH_SQL,
        parameters=[
            {"name": "vec",       "value": {"stringValue": str(embedding)}},
            {"name": "video_uri", "value": {"stringValue": video_uri}},
            {"name": "k",         "value": {"longValue": k}},
        ],
        formatRecordsAs="JSON",
    )
    return [
        {
            "segment_id": row["segment_id"],
            "start":      row["start_s"],
            "end":        row["end_s"],
            "idx":        row["idx"],
            "text":       row["text"],
            "similarity": row["similarity"],
        }
        for row in json.loads(response["formattedRecords"])
    ]