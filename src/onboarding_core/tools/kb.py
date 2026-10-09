"""Tools de busca na base de conhecimento.

- `search_knowledge_base` (Tutor): busca para responder o colaborador. Se nada for
  encontrado, REGISTRA A LACUNA por código, sem depender do modelo encadear outra tool.
- `search_sources` (Curador): busca crua para montar materiais; não gera lacunas
  (o Curador busca por tags e muitas buscas vazias são normais).
"""

from __future__ import annotations

from google.adk.tools import ToolContext

from .. import kb
from ..pii import redact_text
from ..storage import get_catalog
from . import state_keys as K


def search_knowledge_base(question: str, tool_context: ToolContext) -> dict:
    """Busca na base de conhecimento oficial a resposta para uma dúvida do colaborador.
    Cada resultado traz `cite` ([arquivo.md#Seção]), que DEVE aparecer na resposta.
    Se nada for encontrado, a dúvida é registrada automaticamente para o time de
    conteúdo (`gap_registered`): diga que não sabe e que a dúvida foi registrada.

    Args:
        question: a dúvida do colaborador, em linguagem natural.
    """
    results = kb.search(question)
    if results:
        return {"found": True,
                "results": [{**r, "cite": f"[{r['source']}]"} for r in results]}
    gap = get_catalog().log_gap(
        user_id=tool_context.user_id,
        question=redact_text(question),
        role_id=tool_context.state.get(K.ROLE_ID),
        module_id=tool_context.state.get(K.CURRENT_MODULE),
    )
    return {"found": False, "gap_registered": gap.id,
            "instruction": "diga que não tem essa informação, NÃO invente, e avise que a "
            "dúvida foi registrada para o time de conteúdo"}


def search_sources(query: str) -> dict:
    """Busca trechos na base de conhecimento para montar materiais. Cada resultado
    traz `source` (arquivo.md#Seção), que deve ser citado no material.

    Args:
        query: termos de busca (ex.: kb_tags e objetivos do módulo).
    """
    results = kb.search(query)
    return {"results": results, "found": bool(results)}
