import subprocess


def ffmpeg_check() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(f"ffmpeg: {result.stdout[:80]}")
        return result.returncode == 0
    except FileNotFoundError:
        return False


def extract_frame_at_time(video_path: str, timestamp_seconds: float, output_path: str) -> bool:
    """Extract a single frame at timestamp_seconds from video_path.

    Uses input-side seeking (-ss before -i) for fast keyframe seek then
    decodes the first reachable frame.  Scale is capped at 1024 px wide
    (aspect ratio preserved) to match the Titan Embed Image input limit.
    """
    command = [
        "ffmpeg",
        "-ss", str(timestamp_seconds),
        "-i", video_path,
        "-frames:v", "1",
        "-vf", "scale=1024:-1",
        "-y",
        output_path,
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(f"FFmpeg error at {timestamp_seconds:.1f}s: {result.stderr[-300:]}")
    return result.returncode == 0