"""Guardrails de PII na versão LangGraph.

Diferença importante em relação ao ADK: o ADK tem um hook de plugin
(`on_user_message_callback`) que troca a mensagem ANTES de ela ser gravada. No
LangGraph, a entrada do `invoke` é gravada no checkpoint antes de qualquer nó
rodar; um nó que mascarasse depois deixaria o texto original no histórico.

Por isso a entrada é mascarada na fronteira (`prepare_user_message`, usada por
scripts/chat.py e pelos evals), e o nó `guard_output` mascara a resposta.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from .pii import PERSONAL_IDS, redact


def prepare_user_message(text: str) -> tuple[HumanMessage, list[str]]:
    masked, found = redact(text)
    return HumanMessage(content=masked), found


def redact_ai_message(msg: AIMessage) -> AIMessage | None:
    """Versão mascarada (só CPF/cartão) com o MESMO id, para substituir no estado.

    Usa `msg.text`: com thinking ligado o Gemini pode devolver o conteúdo como lista
    de blocos, e olhar só `content: str` deixaria a PII passar.
    """
    text = str(msg.text)
    if not text:
        return None
    masked, found = redact(text, PERSONAL_IDS)
    if not found:
        return None
    return AIMessage(content=masked, id=msg.id)
