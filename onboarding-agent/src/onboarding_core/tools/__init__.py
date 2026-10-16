"""Function tools do ADK. Docstrings e type hints viram o schema visto pelo LLM."""

from .catalog import get_learning_path, get_material, list_roles, save_material_draft
from .escalation import escalate_to_buddy
from .gaps import list_open_gaps, log_gap
from .kb import search_knowledge_base, search_sources
from .progress import get_my_progress, set_my_role, start_module
from .quiz import answer_quiz, start_quiz

__all__ = [
    "answer_quiz",
    "escalate_to_buddy",
    "get_learning_path",
    "get_material",
    "get_my_progress",
    "list_open_gaps",
    "list_roles",
    "log_gap",
    "save_material_draft",
    "search_knowledge_base",
    "search_sources",
    "set_my_role",
    "start_module",
    "start_quiz",
]
