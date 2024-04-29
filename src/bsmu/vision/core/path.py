from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def is_ascii_filename(filename: str):
    return all(ord(ch) < 128 for ch in filename)


def is_ascii_path(path: Path):
    return is_ascii_filename(str(path))
