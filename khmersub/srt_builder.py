"""Word-level SRT construction: timestamp helpers, cue splitting, Gemini retry."""

import os
import re
import subprocess
import time
from pathlib import Path

from khmercut import tokenize

from khmersub.transcribe import call_gemini

KHMER_RE = re.compile(r"[ក-៿]")
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

# Gemini is asked for short sentence-level cues; we then cut those into
# word-level captions anchored to the same time window.
# Note: longer instruction lists make Gemini's filter occasionally refuse
# the request (blockReason OTHER), so the prompt stays minimal and we keep
# a simpler fallback in the chain.
WORD_PROMPT = """\
You are a Khmer transcriptionist. Transcribe this audio in Khmer script (Unicode Khmer).

Output only SRT cues in this exact form:
1
HH:MM:SS,mmm --> HH:MM:SS,mmm
Khmer text

Rules: short cues (one clause, at most ~5 seconds), timestamps in milliseconds with a comma, no translation, no commentary, no markdown.
"""

FALLBACK_PROMPT = """\
Transcribe this Khmer audio into Khmer script.
Output only numbered SRT cues: an index line, then HH:MM:SS,mmm --> HH:MM:SS,mmm, then the Khmer text.
Short cues, no markdown, no commentary.
"""

PROMPT_CHAIN = [WORD_PROMPT, WORD_PROMPT, FALLBACK_PROMPT, FALLBACK_PROMPT]


def audio_duration_ms(path: Path) -> int | None:
    """Audio length in milliseconds via ffprobe, or None if unavailable."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return round(float(out) * 1000)
    except Exception:
        return None


def ts_to_ms(ts: str) -> int:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def ms_to_ts(ms: int) -> str:
    ms = max(0, ms)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def group_words(units: list[str]) -> list[str]:
    """Pack khmercut word units into captions of one or two words.

    Khmer words have no fixed length, so the cut decides: short words pair
    up (when the combined text stays compact), longer words stand alone.
    """
    groups: list[str] = []
    i = 0
    while i < len(units):
        word = units[i]
        if i + 1 < len(units) and len(word) + len(units[i + 1]) <= 8:
            groups.append(word + units[i + 1])  # Khmer joins words without spaces
            i += 2
        else:
            groups.append(word)
            i += 1
    return groups


def build_word_cues(start_ms: int, end_ms: int, text: str) -> list[tuple[int, int, str]]:
    """Split one timed sentence into word-level cues inside its window.

    Words are distributed proportionally to their length so the captions
    stay in step with the speech inside [start_ms, end_ms].
    """
    units = [u for u in tokenize(text) if u.strip()]
    if not units:
        return []
    groups = group_words(units)
    total_chars = sum(len(g) for g in groups)
    window = max(end_ms - start_ms, 0)

    cues: list[tuple[int, int, str]] = []
    t = start_ms
    for group in groups:
        share = round(window * len(group) / total_chars)
        cues.append((t, t + share, group))
        t += share
    if cues:  # clamp the tail exactly onto the sentence end
        cues[-1] = (cues[-1][0], end_ms, cues[-1][2])
    return cues


def srt_document(cues: list[tuple[int, int, str]]) -> str:
    blocks = [
        f"{i}\n{ms_to_ts(s)} --> {ms_to_ts(e)}\n{text}\n"
        for i, (s, e, text) in enumerate(cues, 1)
    ]
    return "\n".join(blocks)


def transcribe(api_key: str, audio_path: Path) -> str:
    """Call Gemini, retrying on transient refusals (empty candidates).

    Tries the main prompt twice, then a simplified fallback prompt twice.
    """
    last_error: Exception | None = None
    for attempt, prompt in enumerate(PROMPT_CHAIN, start=1):
        try:
            return call_gemini(api_key, DEFAULT_MODEL, audio_path, prompt=prompt)
        except Exception as exc:  # noqa: BLE001 - retry any API-side failure
            last_error = exc
            if attempt < len(PROMPT_CHAIN):
                time.sleep(2 * attempt)
    raise RuntimeError(
        "Gemini kept refusing this audio after several attempts "
        "(transient API block, not a usage limit). "
        f"Last response: {last_error}"
    )
