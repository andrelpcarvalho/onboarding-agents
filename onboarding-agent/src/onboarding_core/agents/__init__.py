from ..db import prepare_databases
from .curator import build_curator
from .tutor import build_tutor

# `adk web` cria o SessionService sem passar pelo nosso build_runner; garantimos
# o WAL no sessions.db quando os agentes são carregados (idempotente).
prepare_databases()

__all__ = ["build_curator", "build_tutor"]
