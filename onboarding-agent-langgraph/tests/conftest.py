from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage
from langgraph.store.memory import InMemoryStore

from onboarding_lg import storage
from onboarding_lg.quiz_bank import parse_bank
from onboarding_lg.tools.tutor_tools import TutorContext


class FakeRuntime(SimpleNamespace):
    """Substituto do ToolRuntime: store em memória, contexto e mensagens da thread."""

    def say(self, text: str) -> None:
        self.state["messages"].append(HumanMessage(content=text, id=f"m{len(self.state['messages'])}"))


@pytest.fixture
def rt() -> FakeRuntime:
    return FakeRuntime(store=InMemoryStore(), context=TutorContext("u-test"),
                       state={"messages": []})


@pytest.fixture(autouse=True)
def tmp_catalog(tmp_path, monkeypatch):
    cat = storage.Catalog(tmp_path / "catalog.db")
    monkeypatch.setattr(storage, "_catalog", cat)
    return cat


def bank(n: int = 4, correct: int = 1) -> list[dict]:
    return [{"question": f"P{i}?", "options": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"],
             "correct_option": correct, "explanation": f"porque {i}"} for i in range(n)]


def draft(cat, role="dev_salesforce", module="cultura_empresa", content="c",
          sources=("cultura.md#Valores",), quiz=None):
    return cat.save_draft(role, module, "T", content, list(sources),
                          quiz=parse_bank(bank() if quiz is None else quiz))
