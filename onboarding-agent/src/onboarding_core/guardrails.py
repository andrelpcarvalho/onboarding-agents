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


def default_plugins() -> list[BasePlugin]:
    return [PiiRedactionPlugin()]
