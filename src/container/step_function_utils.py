import json

import boto3

sf = boto3.client("stepfunctions")


def send_task_success(token: str, output: dict) -> None:
    sf.send_task_success(taskToken=token, output=json.dumps(output))


def send_task_failure(token: str, error: str = "TaskFailure", cause: str = "") -> None:
    sf.send_task_failure(taskToken=token, error=error, cause=cause)