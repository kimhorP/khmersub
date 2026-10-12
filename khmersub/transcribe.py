"""Transcribe Khmer audio files to SRT subtitles using the Gemini API.

Usage:
    python -m khmersub.transcribe                    # every .mp3 in audio/
    python -m khmersub.transcribe path/to/a.mp3      # specific file(s)
    python -m khmersub.transcribe --out-dir srt      # write .srt elsewhere (default: next to audio)
    python -m khmersub.transcribe --model gemini-2.5-flash

Requires the GEMINI_API_KEY environment variable and the `requests` package.
"""

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".mov", ".mp4"}

PROMPT = """\
You are an expert Khmer (Cambodian) transcriptionist. Transcribe the attached \
audio file verbatim into Khmer script (Unicode Khmer, Khmer numerals not required).

Rules:
- Output ONLY valid SRT subtitle content. No commentary, no markdown, no code fences.
- Each cue is: a sequential number starting at 1, a blank line, then a line \
"HH:MM:SS,mmm --> HH:MM:SS,mmm", a blank line, then the Khmer text, then a blank line.
- Use real timestamps in milliseconds with a comma (,), e.g. 00:01:23,450.
- Timestamps must be monotonically increasing and within the audio's duration.
- Keep each cue to at most about 2 lines and about 7 seconds of speech.
- Transcribe faithfully: do not translate, summarize, or add punctuation that \
changes meaning. Keep filler words if they carry meaning.
- If the audio is silent or unintelligible in a region, skip that region \
(do not emit empty cues).
- If the audio contains no speech at all, output nothing.
"""

TIMESTAMP_RE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2},\d{3})"
)
CUE_HEADER_RE = re.compile(r"^\d+$")


def call_gemini(api_key: str, model: str, audio_path: Path, prompt: str = PROMPT) -> str:
    """Send the audio inline to Gemini and return the raw text response."""
    data = base64.standard_b64encode(audio_path.read_bytes()).decode("ascii")
    mime = {
        ".mp3": "audio/mp3",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".mov": "video/quicktime",
        ".mp4": "video/mp4",
    }.get(audio_path.suffix.lower(), "application/octet-stream")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": data}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    resp = requests.post(
        API_URL.format(model=model),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"No candidates in response: {json.dumps(body)[:500]}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts)


def _parse_timestamp(line: str) -> tuple[str, str] | None:
    m = TIMESTAMP_RE.search(line)
    return (m.group(1), m.group(2)) if m else None


def parse_srt(raw: str) -> list[tuple[str, str, str]]:
    """Parse SRT-ish text into (start, end, text) tuples.

    Tolerates markdown code fences and extra prose around the cues.
    Timestamps are returned as HH:MM:SS,mmm strings.
    """
    text = raw.strip()
    # Drop ```srt ... ``` fences if the model added them anyway.
    text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        # Find the timestamp line; text is everything after it.
        for i, line in enumerate(lines):
            ts = _parse_timestamp(line)
            if ts:
                body = "\n".join(lines[i + 1 :]).strip()
                if body:
                    cues.append((ts[0], ts[1], body))
                break
    return cues


def normalize_srt(raw: str) -> str:
    """Strip code fences and renumber cues sequentially."""
    cues = parse_srt(raw)
    out = []
    for n, (start, end, body) in enumerate(cues, start=1):
        out.append(f"{n}\n{start} --> {end}\n{body}\n")
    return "\n".join(out)


def process_file(api_key: str, model: str, audio_path: Path, out_dir: Path | None) -> Path:
    raw = call_gemini(api_key, model, audio_path)
    srt = normalize_srt(raw)
    dest_dir = out_dir if out_dir is not None else audio_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    srt_path = dest_dir / f"{audio_path.stem}.srt"
    srt_path.write_text(srt, encoding="utf-8")
    return srt_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe Khmer audio to SRT with Gemini.")
    parser.add_argument("files", nargs="*", type=Path, help="audio files (default: audio/*.mp3)")
    parser.add_argument("--out-dir", type=Path, default=None, help="directory for .srt files")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY environment variable is not set", file=sys.stderr)
        return 1

    files = args.files
    if not files:
        audio_dir = ROOT / "audio"
        files = sorted(
            p for p in audio_dir.iterdir()
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
        )
        if not files:
            print(f"no audio files found in {audio_dir}", file=sys.stderr)
            return 1

    failures = 0
    for audio_path in files:
        if not audio_path.is_file():
            print(f"skip (not found): {audio_path}", file=sys.stderr)
            failures += 1
            continue
        print(f"transcribing {audio_path.name} ...")
        try:
            srt_path = process_file(api_key, args.model, audio_path, args.out_dir)
            print(f"  -> {srt_path}")
        except Exception as exc:  # noqa: BLE001 - report and continue with other files
            failures += 1
            print(f"  failed: {exc}", file=sys.stderr)

    print(f"done: {len(files) - failures}/{len(files)} transcribed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
