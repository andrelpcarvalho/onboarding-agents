"""Function tools do ADK. Docstrings e type hints viram o schema visto pelo LLM."""

from .catalog import get_learning_path, get_material, list_roles, save_material_draft
from .escalation import confirm_escalation, escalate_to_buddy, propose_escalation
from .gaps import list_open_gaps, log_gap
from .kb import search_knowledge_base, search_sources
from .missions import answer_mission, get_test_cpf, list_missions, start_mission
from .progress import get_my_progress, set_my_role, start_module
from .quiz import answer_quiz, start_quiz

__all__ = [
    "answer_mission",
    "answer_quiz",
    "confirm_escalation",
    "escalate_to_buddy",
    "get_learning_path",
    "get_material",
    "get_my_progress",
    "get_test_cpf",
    "list_missions",
    "list_open_gaps",
    "list_roles",
    "log_gap",
    "propose_escalation",
    "save_material_draft",
    "search_knowledge_base",
    "search_sources",
    "set_my_role",
    "start_mission",
    "start_module",
    "start_quiz",
]
