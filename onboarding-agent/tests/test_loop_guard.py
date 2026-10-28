"""Ponta a ponta sem LLM real: um modelo falso que só pede answer_mission em loop.

Reproduz o teste manual de 27/10 (70+ chamadas numa resposta) e prova que o
ToolCallBudgetPlugin e o teto de chamadas ao modelo cortam o loop.
"""

from collections.abc import AsyncGenerator

import pytest
from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from onboarding_core.guardrails import ToolCallBudgetPlugin

CALLS = {"tool": 0}


def answer_mission() -> dict:
    """Dublê da tool da missão."""
    CALLS["tool"] += 1
    return {"ok": False, "status": "already_evaluated"}


class LoopingModel(BaseLlm):
    model: str = "loop"

    async def generate_content_async(self, llm_request, stream: bool = False
                                     ) -> AsyncGenerator[LlmResponse, None]:
        yield LlmResponse(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name="answer_mission", args={}))]))


async def test_loop_de_tool_e_cortado():
    agent = LlmAgent(name="tutor", model=LoopingModel(), instruction="x", tools=[answer_mission])
    runner = InMemoryRunner(agent=agent, app_name="t", plugins=[ToolCallBudgetPlugin()])
    s = await runner.session_service.create_session(app_name="t", user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text="oi")])
    CALLS["tool"] = 0
    with pytest.raises(LlmCallsLimitExceededError):
        async for _ in runner.run_async(user_id="u", session_id=s.id, new_message=msg,
                                        run_config=RunConfig(max_llm_calls=15)):
            pass
    assert CALLS["tool"] == 3  # o plugin deixou só 3 execuções reais da tool
