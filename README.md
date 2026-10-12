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
python scripts/init_dirs.py   # creates video/, audio/, srt/ and .env
# edit .env and set GEMINI_API_KEY=<your key>
```

`.env.example` documents the available variables:

| Variable        | Default             | Purpose                        |
|-----------------|---------------------|--------------------------------|
| `GEMINI_API_KEY`| — (required for SRT)| Gemini API key                 |
| `GEMINI_MODEL`  | `gemini-3.8-flash`  | Gemini model used for SRT mode |

> The app reads the key from the environment — export it or use
> `setx GEMINI_API_KEY <key>` on Windows. Never commit `.env`.

## Usage

```bash
python main.py                      # interactive menu (recommended)
python -m khmersub.audio            # CLI: extract audio from every video in video/
python -m khmersub.transcribe       # CLI: transcribe audio/ to .srt (sentence-level)
```

In the menu:

1. **Extract audio from video/** — `video/*.mov|mp4|...` → `audio/*.mp3`.
2. **Generate word-by-word SRT from audio/** — pick an audio file, get
   `srt/<name>.srt` with word-level cues.

## Folder structure

```
.
├── main.py                  # entry point: menu + flows
├── khmersub/                # application package
│   ├── audio.py             # ffmpeg extraction
│   ├── transcribe.py        # Gemini API + SRT parsing
│   ├── srt_builder.py       # word-level cue building
│   └── ui.py                # banner, prompts, console helpers
├── scripts/
│   └── init_dirs.py         # creates video/, audio/, srt/, .env
├── examples/
│   └── sample_word.srt      # mock example of word-level output
├── video/                   # ← you put videos here (gitignored)
├── audio/                   # generated MP3s (gitignored)
├── srt/                     # generated subtitles (gitignored)
└── .env                     # your API key (gitignored — see .env.example)
```

Folders marked *gitignored* are not shipped with the repository; run
`python scripts/init_dirs.py` after cloning to recreate them.

`examples/sample_word.srt` is a **mock** file showing the expected output
format — it is not a transcription of any real recording.

## Development

```bash
python -m khmersub.transcribe --help   # module CLI sanity check
printf '\n' | python main.py           # non-interactive smoke test
```
