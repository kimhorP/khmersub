"""Create the working folders (video/, audio/, srt/) and .env if missing.

Usage:
    python scripts/init_dirs.py

Safe to run repeatedly; existing folders and .env are left untouched.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR_NAMES = ("video", "audio", "srt")


def main() -> int:
    for name in DIR_NAMES:
        folder = ROOT / name
        folder.mkdir(exist_ok=True)
        print(f"ok: {name}/")

    env = ROOT / ".env"
    example = ROOT / ".env.example"
    if env.exists():
        print(".env already exists")
    elif example.exists():
        shutil.copyfile(example, env)
        print("created .env from .env.example — fill in GEMINI_API_KEY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
