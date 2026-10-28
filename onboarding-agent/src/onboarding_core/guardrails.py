"""Plugin de guardrails do ADK: mascara PII na entrada e na saída do modelo.

Registrado no Runner (services.build_runner) e no App do `adk web`
(agents/tutor/agent.py), vale para todos os agentes da árvore.

- on_user_message_callback: mascara a mensagem do colaborador ANTES de ela ser
  gravada na sessão/memória e enviada ao modelo.
- after_model_callback: mascara só identificadores pessoais (CPF, cartão) na
  resposta do modelo. Contatos oficiais da base (e-mail/telefone de times) passam.

Argumentos de tools não são mascarados genericamente: o Curador grava material
da base oficial por tool e não pode ter contatos legítimos apagados. As tools que
gravam texto livre do colaborador (log_gap, escalate_to_buddy) mascaram sozinhas.
"""

from __future__ import annotations

import logging

from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from .config import TOOL_CALLS_PER_TOOL, TOOL_CALLS_PER_TURN
from .pii import PERSONAL_IDS, redact

log = logging.getLogger(__name__)


def _redact_content(
    content: types.Content | None, entities: tuple[str, ...] | None = None
) -> tuple[types.Content | None, list[str]]:
    if not content or not content.parts:
        return None, []
    found: list[str] = []
    new_parts, changed = [], False
    for part in content.parts:
        if part.text and not part.thought:
            masked, ents = redact(part.text, entities)
            if ents:
                changed = True
                found += ents
                part = part.model_copy(update={"text": masked})
        new_parts.append(part)
    if not changed:
        return None, []
    return content.model_copy(update={"parts": new_parts}), found


class PiiRedactionPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="pii_redaction")

    async def on_user_message_callback(self, *, invocation_context, user_message):
        masked, ents = _redact_content(user_message)
        if masked is not None:
            log.info("PII mascarada na entrada: %s", ents)
        return masked

    async def after_model_callback(self, *, callback_context, llm_response):
        masked, ents = _redact_content(llm_response.content, PERSONAL_IDS)
        if masked is None:
            return None
        log.warning("PII mascarada na saída do modelo: %s", ents)
        return llm_response.model_copy(update={"content": masked})


class ToolCallBudgetPlugin(BasePlugin):
    """Limita chamadas de tool por resposta (invocação) do agente.

    Acima do limite, a tool NÃO roda: o modelo recebe um erro pedindo para parar e
    responder. É a defesa por código contra loop de tools (custo e latência); o
    prompt sozinho não segurou no teste manual da missão.
    """

    def __init__(self, per_tool: int = TOOL_CALLS_PER_TOOL,
                 per_turn: int = TOOL_CALLS_PER_TURN) -> None:
        super().__init__(name="tool_call_budget")
        self.per_tool, self.per_turn = per_tool, per_turn
        self._counts: dict[str, dict[str, int]] = {}

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        c = self._counts.setdefault(tool_context.invocation_id, {})
        c[tool.name] = c.get(tool.name, 0) + 1
        c["__total__"] = c.get("__total__", 0) + 1
        if c[tool.name] > self.per_tool or c["__total__"] > self.per_turn:
            log.warning("limite de tools na invocação %s: %s", tool_context.invocation_id, c)
            return {"ok": False, "error": "limite de chamadas de ferramenta nesta resposta",
                    "next_step": "pare de chamar ferramentas e responda ao colaborador agora "
                    "com o que já tem"}
        return None

    async def after_run_callback(self, *, invocation_context) -> None:
        self._counts.pop(invocation_context.invocation_id, None)


def default_plugins() -> list[BasePlugin]:
    return [PiiRedactionPlugin(), ToolCallBudgetPlugin()]
