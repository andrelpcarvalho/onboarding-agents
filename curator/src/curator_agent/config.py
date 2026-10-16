"""Configuração: paths, cliente Gemini e modelos."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

OUT_DIR = Path(os.getenv("CURATOR_OUT_DIR", PROJECT_ROOT / "out"))      # pacotes gerados
INBOX_DIR = Path(os.getenv("CURATOR_INBOX_DIR", PROJECT_ROOT / "inbox"))  # PDFs a importar
CATALOG_DB = OUT_DIR / "catalog.db"  # usado só quando nenhum pacote é informado

MODEL = os.getenv("CURATOR_MODEL", "gemini-2.5-flash")
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", MODEL)
AGENT_MODEL = os.getenv("AGENT_MODEL", MODEL)  # modelo da conversa (adk web / A2A)
MAX_PDF_MB = 20  # limite de PDF inline no Gemini; acima disso, use a Files API / GCS


@lru_cache
def client():
    """Cliente google-genai (Vertex AI ou AI Studio, conforme o .env), com retry em 429/5xx."""
    from google import genai
    from google.genai import types

    return genai.Client(http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(
        attempts=int(os.getenv("MODEL_RETRY_ATTEMPTS", "6")), initial_delay=2.0, max_delay=60.0,
        exp_base=2.0, jitter=1.0, http_status_codes=[429, 500, 502, 503, 504])))
