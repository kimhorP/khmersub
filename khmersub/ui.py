"""Shared terminal helpers: UTF-8 setup, banner, and prompt wrapper."""

import sys

import pyfiglet
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

APP_NAME = "KhmerSub Studio"
VERSION = "1.0"


def configure_encoding() -> None:
    # Windows consoles default to cp1252, which cannot encode Khmer script.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def print_banner(console: Console) -> None:
    art = pyfiglet.figlet_format("KhmerSub", font="standard")
    body = Text()
    body.append(art, style="bold cyan")
    body.append("            S T U D I O\n\n", style="bold magenta")
    body.append("  word-by-word Khmer subtitles, one command away", style="italic white")
    console.print(Panel(body, border_style="bright_blue"))


def ask(make_prompt) -> str | list | None:
    """Run a questionary prompt factory, returning None on cancel or without a TTY."""
    try:
        return make_prompt().ask()
    except (EOFError, KeyboardInterrupt):
        return None
    except Exception as exc:  # prompt_toolkit raises when there is no console
        if exc.__class__.__name__ == "NoConsoleScreenBufferError":
            return None
        raise
