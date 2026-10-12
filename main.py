"""KhmerSub Studio — extract audio and build word-by-word Khmer subtitles.

Flow (run `python main.py`):
  1. Choose "Extract audio"  -> every video in video/ becomes audio/<name>.mp3
     (files that already exist in audio/ are skipped).
  2. Choose "Extract SRT"    -> pick an audio file with questionary, transcribe
     with the Gemini API, cut the Khmer text with khmercut, and emit an SRT
     where each cue shows one or two words at a time, so subtitles pop up
     word by word in your video editor.

Requires: ffmpeg on PATH, GEMINI_API_KEY for SRT mode.
"""

import os
import re
from pathlib import Path

import questionary
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from khmersub.audio import AUDIO_DIR, VIDEO_DIR, VIDEO_EXTENSIONS, extract_audio
from khmersub.srt_builder import (
    KHMER_RE,
    audio_duration_ms,
    build_word_cues,
    ms_to_ts,
    srt_document,
    transcribe,
    ts_to_ms,
)
from khmersub.transcribe import AUDIO_EXTENSIONS, parse_srt
from khmersub.ui import ask, configure_encoding, print_banner

SRT_DIR = Path(__file__).parent / "srt"


def run_audio_extraction(console: Console) -> None:
    videos = sorted(
        p for p in VIDEO_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    ) if VIDEO_DIR.is_dir() else []
    if not videos:
        console.print("[yellow]No videos found in video/.[/]")
        return

    AUDIO_DIR.mkdir(exist_ok=True)
    table = Table(title="Audio extraction", show_lines=False)
    table.add_column("Video", style="cyan")
    table.add_column("Output", style="dim")
    table.add_column("Status", justify="left")

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console, transient=True,
    ) as progress:
        for video in videos:
            out = AUDIO_DIR / f"{video.stem}.mp3"
            if out.exists():
                table.add_row(video.name, out.name, "[yellow]skipped (already exists)[/]")
                continue
            task = progress.add_task(f"extracting {video.name} ...", total=None)
            try:
                extract_audio(video, out)
                table.add_row(video.name, out.name, "[green]extracted[/]")
            except Exception as exc:
                table.add_row(video.name, out.name, f"[red]failed: {exc}[/]")
            finally:
                progress.stop_task(task)

    console.print(table)
    console.print("[bold green]Audio ready in[/] [bold]audio/[/]")


def run_srt_generation(console: Console) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]GEMINI_API_KEY is not set[/] — export it first, e.g. "
                      "setx GEMINI_API_KEY <your-key>")
        return

    audios = sorted(
        p for p in AUDIO_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    ) if AUDIO_DIR.is_dir() else []
    if not audios:
        console.print("[yellow]No audio found in audio/.[/] Run the audio extraction first.")
        return

    pick = ask(lambda: questionary.select(
        "Which audio to subtitle? (\u2191/\u2193 to move, Enter to confirm)",
        choices=[questionary.Choice(a.name) for a in audios],
    ))
    if not pick:
        console.print("[dim]Cancelled.[/]")
        return
    picks = [pick]

    SRT_DIR.mkdir(parents=True, exist_ok=True)
    by_name = {a.name: a for a in audios}
    for name in picks:
        audio_path = by_name[name]
        with console.status(f"[cyan]{name}[/] — transcribing with Gemini ..."):
            raw = transcribe(api_key, audio_path)
        sentence_cues = [
            (ts_to_ms(s), ts_to_ms(e), t) for s, e, t in parse_srt(raw)
            # drop malformed/preamble blocks the model sometimes emits
            # (e.g. stray timestamp fragments like "00:03,140 -->")
            if KHMER_RE.search(t) and ts_to_ms(e) > ts_to_ms(s)
        ]
        duration = audio_duration_ms(audio_path)

        word_cues: list[tuple[int, int, str]] = []
        if sentence_cues:
            if duration:  # clamp Gemini's last cue onto the real duration
                sentence_cues[-1] = (
                    sentence_cues[-1][0],
                    min(sentence_cues[-1][1], duration),
                    sentence_cues[-1][2],
                )
            for s, e, t in sentence_cues:
                word_cues.extend(build_word_cues(s, e, t))
        else:  # fallback: no timestamps came back; spread words evenly
            words = [w for w in re.split(r"\s+", raw) if KHMER_RE.search(w)]
            text = " ".join(words)
            total = duration or max(len(text) * 250, 10_000)
            word_cues = build_word_cues(0, total, text)

        if not word_cues:
            console.print(f"[yellow]{name}:[/] no speech detected, skipping.")
            continue

        out_path = SRT_DIR / f"{audio_path.stem}.srt"
        out_path.write_text(srt_document(word_cues), encoding="utf-8")
        console.print(
            f"[green]✔[/] {name} → [bold]{out_path.name}[/] "
            f"({len(word_cues)} word-cues, {ms_to_ts(word_cues[-1][1])} long)"
        )


def main() -> int:
    configure_encoding()
    console = Console()
    print_banner(console)

    while True:
        choice = ask(lambda: questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("Extract audio from video/", "audio"),
                questionary.Choice("Generate word-by-word SRT from audio/", "srt"),
                questionary.Choice("Exit", "exit"),
            ],
        ))

        if choice == "audio":
            run_audio_extraction(console)
        elif choice == "srt":
            run_srt_generation(console)
        else:  # exit, Ctrl+C, or no interactive console
            console.print("[bold cyan]សូមអរគុណ![/] Goodbye.")
            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nBye.")
        raise SystemExit(130)
