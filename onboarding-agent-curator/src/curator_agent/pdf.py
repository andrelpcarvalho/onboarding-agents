"""Leitura de PDF: bytes para o Gemini e texto (pypdf) para a checagem de fidelidade."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from .config import MAX_PDF_MB


def load_pdf(path: Path) -> tuple[bytes, str, int]:
    """Retorna (bytes, texto extraído, nº de páginas). Recusa PDF grande demais."""
    data = path.read_bytes()
    if len(data) > MAX_PDF_MB * 1024 * 1024:
        raise ValueError(f"PDF tem {len(data) / 1e6:.1f} MB; o limite inline é {MAX_PDF_MB} MB")
    reader = PdfReader(path)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return data, text, len(reader.pages)
