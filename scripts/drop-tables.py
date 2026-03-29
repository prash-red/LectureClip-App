#!/usr/bin/env python3
"""
Drop all tables and extensions created by db-migrate.

Usage:
    python scripts/drop-tables.py

Override defaults via environment variables:
    AURORA_CLUSTER_ARN, AURORA_SECRET_ARN, AURORA_DB_NAME
"""

import os
import boto3

CLUSTER_ARN = os.environ.get(
    "AURORA_CLUSTER_ARN",
    "arn:aws:rds:ca-central-1:757242163795:cluster:lectureclip-dev-aurora",
)
SECRET_ARN = os.environ.get(
    "AURORA_SECRET_ARN",
    "arn:aws:secretsmanager:ca-central-1:757242163795:secret:rds!cluster-ac2cc966-f877-4170-a978-ed6a39f3b173-fKw14e",
)
DB_NAME = os.environ.get("AURORA_DB_NAME", "lectureclip")

# Drop in reverse dependency order so FK constraints don't block drops.
DROP_STATEMENTS = [
    "DROP INDEX  IF EXISTS segment_embeddings_hnsw_idx",
    "DROP TABLE  IF EXISTS segment_embeddings",
    "DROP TABLE  IF EXISTS sublecture_ratings",
    "DROP TABLE  IF EXISTS eval_task_runs",
    "DROP TABLE  IF EXISTS truth_spans",
    "DROP TABLE  IF EXISTS eval_queries",
    "DROP TABLE  IF EXISTS segments",
    "DROP TABLE  IF EXISTS lectures",
    "DROP EXTENSION IF EXISTS vector",
]

rds_data = boto3.client("rds-data", region_name="ca-central-1")


def execute(sql: str) -> None:
    rds_data.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DB_NAME,
        sql=sql.strip(),
    )


def main() -> None:
    print(f"Dropping tables in '{DB_NAME}' on cluster:")
    print(f"  {CLUSTER_ARN}\n")

    for i, stmt in enumerate(DROP_STATEMENTS, 1):
        print(f"  [{i}/{len(DROP_STATEMENTS)}] {stmt}")
        execute(stmt)

    print("\nDone — all tables dropped.")


if __name__ == "__main__":
    main()