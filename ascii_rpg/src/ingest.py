"""Ingest .txt / .pdf / .epub documents into plain text."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree as ET


class _TextStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self.parts)


def _read_txt(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        if "\x00" in text:
            # probably UTF-16 misread as single-byte: every other byte is null
            for wide in ("utf-16", "utf-16-le", "utf-16-be"):
                try:
                    wide_text = path.read_text(encoding=wide)
                except (UnicodeDecodeError, UnicodeError):
                    continue
                if "\x00" not in wide_text:
                    return wide_text
            return text.replace("\x00", "")
        return text
    return path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "")


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader  # lazy import so worldgen works without pdf support

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(chunks)


def _read_epub(path: Path) -> str:
    # Parse epub manually with stdlib to avoid heavy ebooklib dependency.
    # An epub is a zip containing xhtml files + an .opf manifest.
    chunks: list[str] = []
    with zipfile.ZipFile(path) as z:
        # Find spine order from .opf if present, else just read all html/xhtml.
        names = z.namelist()
        html_files = [n for n in names if n.lower().endswith((".xhtml", ".html", ".htm"))]
        # Prefer content.opf order
        opf_files = [n for n in names if n.lower().endswith(".opf")]
        ordered: list[str] = []
        if opf_files:
            try:
                root = ET.fromstring(z.read(opf_files[0]))
                ns = {"opf": "http://www.opf.org/2007/opf"}
                for itemref in root.findall(".//opf:spine/opf:itemref", ns):
                    idref = itemref.get("idref", "")
                    for item in root.findall(".//opf:manifest/opf:item", ns):
                        if item.get("id") == idref:
                            href = item.get("href", "")
                            base = "/".join(opf_files[0].split("/")[:-1])
                            full = f"{base}/{href}" if base else href
                            if full in names:
                                ordered.append(full)
            except Exception:
                ordered = []
        for name in ordered or html_files:
            try:
                raw = z.read(name).decode("utf-8", errors="ignore")
                parser = _TextStripper()
                parser.feed(raw)
                chunks.append(parser.text())
            except Exception:
                continue
    return "\n".join(chunks)


def load_document(path: str | Path) -> str:
    """Load a single document to plain text. Raises FileNotFoundError / ValueError."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Book not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".txt":
        text = _read_txt(p)
    elif suffix == ".pdf":
        text = _read_pdf(p)
    elif suffix == ".epub":
        text = _read_epub(p)
    else:
        raise ValueError(f"Unsupported file type: {suffix} (use .txt/.pdf/.epub)")
    text = re.sub(r"\s+", " ", text).strip()
    # pygame fonts choke on null bytes (PDF encodings, stray UTF-16) — drop them
    # at the root so no book-derived name, lore, or rumor can ever crash a render.
    return text.replace("\x00", "")


def load_corpus(paths: list[str | Path]) -> str:
    """Load and concatenate multiple documents."""
    texts = [load_document(p) for p in paths]
    texts = [t for t in texts if t]
    if not texts:
        return ""
    return "\n\n".join(texts)


def collect_book_files(book_dir: str | Path) -> list[Path]:
    """Collect supported book files from a directory (non-recursive)."""
    d = Path(book_dir)
    if not d.exists():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if p.suffix.lower() in (".txt", ".pdf", ".epub") and p.is_file():
            out.append(p)
    return out
