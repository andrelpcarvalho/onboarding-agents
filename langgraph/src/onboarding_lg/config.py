"""Configuração centralizada (paths, modelos, thresholds) lida do ambiente."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
ROLES_DIR = DATA_DIR / "roles"
KB_DIR = DATA_DIR / "kb"


def _path_env(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else PROJECT_ROOT / p


CATALOG_DB = _path_env("ONBOARDING_CATALOG_DB", ".lg/catalog.db")
CHECKPOINT_DB = _path_env("ONBOARDING_CHECKPOINT_DB", ".lg/checkpoints.db")  # conversas (threads)
STORE_DB = _path_env("ONBOARDING_STORE_DB", ".lg/store.db")  # perfil + lembranças (por usuário)

PASS_SCORE = float(os.getenv("ONBOARDING_PASS_SCORE", "0.7"))

_DEFAULT_THINKING = {"tutor": 1024, "curator": None, "reviewer": None, "judge": 0}


@lru_cache
def llm(kind: str):
    """Modelo de chat para um papel (tutor|curator|reviewer|judge).

    Gemini via Vertex AI (GOOGLE_GENAI_USE_ENTERPRISE=1) ou AI Studio (GOOGLE_API_KEY).
    Ids no formato `provider:model` usam `init_chat_model` do LangChain (ex.:
    `anthropic:claude-sonnet-5-5`, requer o pacote do provider).
    """
    model_id = os.getenv(f"{kind.upper()}_MODEL", "gemini-2.5-flash")
    if ":" in model_id:
        from langchain.chat_models import init_chat_model

        return init_chat_model(model_id)

    from langchain_google_genai import ChatGoogleGenerativeAI

    budget_env = os.getenv(f"{kind.upper()}_THINKING_BUDGET")
    budget = int(budget_env) if budget_env not in (None, "") else _DEFAULT_THINKING.get(kind)
    kwargs = {
        "model": model_id,
        "max_retries": int(os.getenv("MODEL_RETRY_ATTEMPTS", "6")),  # retry com backoff em 429/5xx
    }
    if budget is not None:
        kwargs["thinking_budget"] = budget
    if os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "0")) in (
        "1", "TRUE", "true",
    ):
        kwargs |= {
            "vertexai": True,
            "project": os.environ["GOOGLE_CLOUD_PROJECT"],
            "location": os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        }
    return ChatGoogleGenerativeAI(**kwargs)
