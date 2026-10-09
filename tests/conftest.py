from types import SimpleNamespace

import pytest
from google.genai import types

from onboarding_core import storage


class FakeToolContext(SimpleNamespace):
    """Substituto mínimo do ToolContext: `state` dict, `user_id` e `session.events`."""

    def say(self, text: str) -> None:
        """Simula uma nova mensagem do colaborador na sessão."""
        n = len(self.session.events)
        self.session.events.append(SimpleNamespace(
            id=f"ev{n}", author="user",
            content=types.Content(role="user", parts=[types.Part(text=text)]),
        ))


@pytest.fixture
def ctx() -> FakeToolContext:
    return FakeToolContext(state={}, user_id="u-test", session=SimpleNamespace(events=[]))


@pytest.fixture(autouse=True)
def tmp_catalog(tmp_path, monkeypatch):
    cat = storage.Catalog(tmp_path / "catalog.db")
    monkeypatch.setattr(storage, "_catalog", cat)
    return cat


def bank(n: int = 4, correct: int = 1) -> list[dict]:
    """Banco válido de n perguntas, todas com a mesma alternativa correta."""
    return [
        {"question": f"P{i}?", "options": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"],
         "correct_option": correct, "explanation": f"porque sim {i}"}
        for i in range(n)
    ]


def draft(cat, role="dev_salesforce", module="pipeline_deploy", content="c",
          sources=("pipeline_deploy.md#GMUD",), quiz=None):
    """Atalho: salva um rascunho direto no catálogo."""
    from onboarding_core.quiz_bank import parse_bank

    return cat.save_draft(role, module, "T", content, list(sources),
                          quiz=parse_bank(bank() if quiz is None else quiz))
