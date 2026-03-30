"""
LectureClip segment-frame embedding container.

Extracts one representative frame per transcript segment, generates an image
embedding for each frame using Amazon Bedrock Titan Embed Image V1, and writes
the result JSON to S3.  Frames are never stored — only the computed vectors.

Environment variables (injected by the Step Functions task definition):
    S3_URI              — s3:// URI of the source video
    TASK_TOKEN          — Step Functions waitForTaskToken callback token
    TRANSCRIBE_S3_URI   — s3:// URI of the Transcribe JSON output
                          (defaults to {prefix}/{file}/transcribe.json in the
                          same bucket if not supplied)

Callback output (sent on success):
    {
        "bucket":             "<video bucket>",
        "videoKey":           "<prefix>/<file>",
        "frameEmbeddingsKey": "<prefix>/<file>/segment_frame_embeddings.json"
    }

NOTE: This container must run AFTER the transcription branch completes in the
Step Functions state machine, because it reads the Transcribe output to derive
segment boundaries.
"""

import os
import sys

from constants import Model
from get_image_embeddings import embed_image
from step_function_utils import send_task_failure, send_task_success
from transcript_utils import fetch_transcript_from_s3_uri, parse_transcript
from utils import download_file, parse_s3_uri, upload_json
from video_processor import extract_frame_at_time, ffmpeg_check

TMP = "/tmp"

IMAGE_MODEL_ID = os.environ.get("FRAME_EMBEDDING_MODEL_ID", "amazon.titan-embed-image-v1")
EMBEDDING_DIM  = int(os.environ.get("EMBEDDING_DIM", "1024"))

if __name__ == "__main__":
    s3_uri           = os.environ["S3_URI"]
    task_token       = os.environ.get("TASK_TOKEN")
    transcribe_s3_uri = os.environ.get("TRANSCRIBE_S3_URI")

    try:
        ffmpeg_check()

        bucket, prefix, filename, _ext, file = parse_s3_uri(s3_uri)
        video_key  = f"{prefix}/{file}" if prefix else file
        local_video = f"{TMP}/{file}"

        os.makedirs(TMP, exist_ok=True)
        download_file(bucket, video_key, local_video)

        # Derive transcript path from the convention used by start-transcribe
        # if the caller did not supply TRANSCRIBE_S3_URI explicitly.
        if not transcribe_s3_uri:
            transcribe_key = f"{prefix}/{file}/transcribe.json" if prefix else f"{file}/transcribe.json"
            transcribe_s3_uri = f"s3://{bucket}/{transcribe_key}"

        print(f"Loading transcript from {transcribe_s3_uri}")
        transcript_json = fetch_transcript_from_s3_uri(transcribe_s3_uri)
        segments = parse_transcript(transcript_json)
        print(f"Found {len(segments)} segments")

        frame_embeddings = []
        for idx, (start_s, speaker, _text) in enumerate(segments):
            # end_s: start of the next segment, or start_s + 30 s for the last one
            end_s = float(segments[idx + 1][0]) if idx + 1 < len(segments) else float(start_s) + 30.0
            mid_s = (float(start_s) + end_s) / 2.0

            frame_path = f"{TMP}/frame_{idx:05d}.jpg"
            print(f"  [{idx}] segment [{start_s}s – {end_s:.1f}s] → frame at {mid_s:.1f}s  speaker={speaker}")

            if not extract_frame_at_time(local_video, mid_s, frame_path):
                print(f"    Warning: skipping segment {idx}, FFmpeg could not extract frame")
                continue

            with open(frame_path, "rb") as fh:
                image_bytes = fh.read()
            os.remove(frame_path)

            model_id = Model(IMAGE_MODEL_ID)
            embedding = embed_image(image_bytes, model_id, EMBEDDING_DIM)
            frame_embeddings.append({
                "idx":       idx,
                "start_s":   float(start_s),
                "end_s":     end_s,
                "speaker":   speaker,
                "embedding": embedding,
            })

        # Persist segments alongside frame embeddings so process-results can
        # use them directly and skip re-fetching / re-parsing the transcript.
        segments_out = [
            {"start_s": int(start_s), "speaker": speaker, "text": text}
            for start_s, speaker, text in segments
        ]

        embeddings_key = f"{prefix}/{file}/segment_frame_embeddings.json" if prefix else f"{file}/segment_frame_embeddings.json"
        upload_json(bucket, embeddings_key, {"segments": segments_out, "frame_embeddings": frame_embeddings})
        print(f"Stored {len(segments_out)} segments and {len(frame_embeddings)} frame embeddings → s3://{bucket}/{embeddings_key}")

        if task_token:
            send_task_success(task_token, {
                "bucket":             bucket,
                "videoKey":           video_key,
                "frameEmbeddingsKey": embeddings_key,
            })

    except Exception as exc:
        print(f"Error: {exc}")
        if task_token:
            send_task_failure(task_token, cause=str(exc))
        sys.exit(1)