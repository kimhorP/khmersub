"""Extract audio from every video file in video/ and save it in audio/.

Usage:
    python -m khmersub.audio
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "video"
AUDIO_DIR = ROOT / "audio"
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm"}


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Transcode the video's audio stream to MP3 using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",  # drop the video stream
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",  # high-quality VBR
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    # Create audio/ first, as required.
    AUDIO_DIR.mkdir(exist_ok=True)

    if not VIDEO_DIR.is_dir():
        print(f"error: video directory not found: {VIDEO_DIR}", file=sys.stderr)
        return 1

    videos = sorted(
        p for p in VIDEO_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        print(f"no video files found in {VIDEO_DIR}")
        return 0

    failures = 0
    for video_path in videos:
        audio_path = AUDIO_DIR / f"{video_path.stem}.mp3"
        print(f"{video_path.name} -> {audio_path.relative_to(ROOT)}")
        try:
            extract_audio(video_path, audio_path)
        except subprocess.CalledProcessError as exc:
            failures += 1
            print(f"  failed: ffmpeg exited with code {exc.returncode}", file=sys.stderr)

    print(f"done: {len(videos) - failures}/{len(videos)} extracted")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
