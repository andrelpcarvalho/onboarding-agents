"""Configuração centralizada (paths, modelos, thresholds) lida do ambiente."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.adk.models import Gemini
from google.genai.types import HttpRetryOptions

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
ROLES_DIR = DATA_DIR / "roles"
KB_DIR = DATA_DIR / "kb"
MISSIONS_DIR = DATA_DIR / "missions"
HOMOLOG_DATA = DATA_DIR / "homolog_data.yaml"
MISSION_MAX_ATTEMPTS = int(os.getenv("ONBOARDING_MISSION_MAX_ATTEMPTS", "3"))

# Orçamento por resposta do Tutor (uma mensagem do colaborador). Evita loop de tools:
# o teste manual da missão chegou a 70+ chamadas de answer_mission numa resposta só.
TOOL_CALLS_PER_TOOL = int(os.getenv("ONBOARDING_TOOL_CALLS_PER_TOOL", "3"))
TOOL_CALLS_PER_TURN = int(os.getenv("ONBOARDING_TOOL_CALLS_PER_TURN", "10"))
MAX_LLM_CALLS = int(os.getenv("ONBOARDING_MAX_LLM_CALLS", "15"))


def _path_env(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else PROJECT_ROOT / p


CATALOG_DB = _path_env("ONBOARDING_CATALOG_DB", ".adk/catalog.db")
SESSIONS_DB = _path_env("ONBOARDING_SESSIONS_DB", ".adk/sessions.db")
MEMORY_DB = _path_env("ONBOARDING_MEMORY_DB", ".adk/memory.db")

PASS_SCORE = float(os.getenv("ONBOARDING_PASS_SCORE", "0.7"))

# Igual ao nome da pasta em agents/: o estado `user:` é escopado por app, então
# chat.py e `adk web agents` (app "tutor") compartilham o mesmo progresso.
APP_NAME = "tutor"


@lru_cache
def model(kind: str) -> Any:
    """Resolve o modelo de um papel de agente (tutor|curator|reviewer).

    Ids no formato ``provider/model`` usam LiteLLM (pip install '.[litellm]');
    qualquer outro valor é tratado como id Gemini nativo, com retry exponencial
    para 429 (cota) e 5xx, comuns em projetos Vertex novos.
    """
    defaults = {
        "tutor": "gemini-2.5-flash",
        "curator": "gemini-2.5-flash",
        "reviewer": "gemini-2.5-flash",
    }
    model_id = os.getenv(f"{kind.upper()}_MODEL", defaults[kind])
    if "/" in model_id:
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(model=model_id)

    return Gemini(
        model=model_id,
        retry_options=HttpRetryOptions(
            attempts=int(os.getenv("MODEL_RETRY_ATTEMPTS", "6")),
            initial_delay=2.0,
            max_delay=60.0,
            exp_base=2.0,
            jitter=1.0,
            http_status_codes=[429, 500, 502, 503, 504],
        ),
    )
