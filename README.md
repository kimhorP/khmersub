# KhmerSub Studio

Word-by-word Khmer subtitles, one command away. Point it at a folder of videos,
get MP3s, then get SRT subtitles where each cue pops up one or two words at a
time — ready for your video editor's timeline.

## Features

- **Audio extraction** — batch-convert every video in `video/` to MP3 with
  ffmpeg (existing MP3s are skipped).
- **Khmer transcription** — send audio to the Gemini API and get back SRT cues
  in Unicode Khmer.
- **Word-level cues** — sentence cues are re-cut with
  [khmercut](https://pypi.org/project/khmercut/) and timed proportionally, so
  captions appear word by word.
- **Interactive menu** — a rich/questionary terminal UI; the two steps are
  also available as standalone module CLIs.

## Requirements

- Python 3.12+ ([uv](https://docs.astral.sh/uv/) recommended, or pip)
- `ffmpeg` and `ffprobe` on your `PATH`
- A Gemini API key (`GEMINI_API_KEY`)

## Install

```bash
uv sync            # or: pip install -r <(uv export --no-hashes)
```

## First run

```bash
uv run python scripts/init_dirs.py   # creates video/, audio/, srt/
```

Set up your environment file:

```bash
cp .env.example .env
```

`.env.example` documents the available variables:

| Variable        | Default             | Purpose                        |
|-----------------|---------------------|--------------------------------|
| `GEMINI_API_KEY`| (required for SRT)| Gemini API key                 |
| `GEMINI_MODEL`  | `gemini-3.8-flash`  | Gemini model used for SRT mode |


## Usage

```bash
uv run python main.py                      # interactive menu (recommended)
uv run python -m khmersub.audio            # CLI: extract audio from every video in video/
uv run python -m khmersub.transcribe       # CLI: transcribe audio/ to .srt (sentence-level)
```

> Bare `python` works too if you activate the venv first:
> `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on Unix.

In the menu:

1. **Extract audio from video/** — `video/*.mov|mp4|...` → `audio/*.mp3`.
2. **Generate word-by-word SRT from audio/** — pick an audio file, get
   `srt/<name>.srt` with word-level cues.

## How it works

`video/` → **ffmpeg** → `audio/*.mp3` → **Gemini** → sentence-level SRT →
[khmercut](https://pypi.org/project/khmercut/) → word-level SRT in `srt/`.

## Example output

Each cue holds a single word, so captions pop in one at a time:

```srt
1
00:00:00,000 --> 00:00:00,720
សួស្តី

2
00:00:00,720 --> 00:00:01,680
មិត្តភក្តិ

3
00:00:01,680 --> 00:00:02,640
ទាំងអស់គ្នា

4
00:00:02,640 --> 00:00:04,000
សូមស្វាគមន៍
```

("Hello / friends / everyone / welcome" — see
`examples/sample_word.srt` for the full sample.)