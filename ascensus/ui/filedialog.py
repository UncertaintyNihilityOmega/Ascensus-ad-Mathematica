"""Native "Save as" / "Open" file dialogs for exporting and importing saves (tkinter, part of Python).

Each call opens a hidden, always-on-top Tk root so the dialog appears above the game window, waits for the
player, and returns the chosen path (None when cancelled). FileDialogError is raised when no dialog can be
shown (tkinter missing or no display), so the caller can say so instead of crashing.
"""
from __future__ import annotations

from pathlib import Path

FILETYPES = [("Ascensus save", "*.ascensus"), ("All files", "*.*")]


class FileDialogError(RuntimeError):
    """No file dialog could be shown on this system."""


def _start_dir() -> str:
    """Documents when it exists, else the home folder."""
    docs = Path.home() / "Documents"
    return str(docs if docs.is_dir() else Path.home())


def _run(kind: str, **options) -> Path | None:
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as err:
        raise FileDialogError("File dialogs need tkinter, which this Python does not have") from err
    try:
        root = tkinter.Tk()
    except tkinter.TclError as err:
        raise FileDialogError("No file dialog available") from err
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        ask = filedialog.asksaveasfilename if kind == "save" else filedialog.askopenfilename
        chosen = ask(parent=root, initialdir=_start_dir(), filetypes=FILETYPES, **options)
    finally:
        root.destroy()
    return Path(chosen) if chosen else None


def ask_save_path(default_name: str) -> Path | None:
    """Where to export a save (adds .ascensus when the player types no extension)."""
    return _run("save", title="Export save", defaultextension=".ascensus", initialfile=default_name)


def ask_open_path() -> Path | None:
    """Which .ascensus file to import."""
    return _run("open", title="Import save")
