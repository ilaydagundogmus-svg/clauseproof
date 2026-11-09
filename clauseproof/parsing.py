"""TXT and text-based PDF reading with input validation."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .config import MAX_FILE_BYTES, MIN_TEXT_CHARS


class ParsingError(ValueError):
    """Raised when a document cannot be read or is unsuitable for analysis."""


def normalize_text(text: str) -> str:
    """Normalize line endings and whitespace without changing wording."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def validate_text(text: str) -> str:
    """Normalize and check minimum length."""
    cleaned = normalize_text(text or "")
    if not cleaned:
        raise ParsingError("The document is empty.")
    if len(cleaned) < MIN_TEXT_CHARS:
        raise ParsingError("Text too short for DPA analysis.")
    return cleaned


def _read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ParsingError("The PDF is encrypted; decrypt it and try again.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ParsingError:
        raise
    except (PyPdfError, OSError, ValueError, KeyError) as exc:
        raise ParsingError(f"The PDF is corrupted or unreadable: {exc}") from exc
    text = "\n\n".join(pages)
    if not text.strip():
        raise ParsingError("No extractable text found. OCR is not supported.")
    return text


def read_document(path: str | Path) -> str:
    """Read a .txt or text-based .pdf file and return validated, normalized text."""
    p = Path(path)
    if not p.is_file():
        raise ParsingError(f"File not found: {p}")
    if p.stat().st_size > MAX_FILE_BYTES:
        raise ParsingError(f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit.")
    suffix = p.suffix.lower()
    if suffix == ".txt":
        try:
            raw = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ParsingError("The text file is not valid UTF-8.") from exc
    elif suffix == ".pdf":
        raw = _read_pdf(p)
    else:
        raise ParsingError(f"Unsupported file type '{suffix}'. Use .txt or .pdf.")
    return validate_text(raw)
