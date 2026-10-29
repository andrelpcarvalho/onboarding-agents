"""Busca vetorial (com embedder falso, sem rede) e servidor MCP da base (item 8)."""

import math
import re
import unicodedata

import pytest

from onboarding_core import kb, kb_vector


def _fake_embedder(texts):
    """Bag-of-words em 64 dimensões: determinístico, sem rede, parecido o bastante."""
    out = []
    for t in texts:
        t = "".join(c for c in unicodedata.normalize("NFKD", t.lower())
                    if not unicodedata.combining(c))
        v = [0.0] * 64
        for w in re.findall(r"[a-z]{4,}", t):
            v[sum(map(ord, w)) % 64] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


@pytest.fixture
def vetorial(tmp_path, monkeypatch):
    monkeypatch.setenv("ONBOARDING_KB_BACKEND", "vector")
    monkeypatch.setattr(kb_vector, "INDEX", tmp_path / "idx.json")
    monkeypatch.setattr(kb_vector, "MIN_SIMILARITY", 0.3)
    kb_vector.set_embedder(_fake_embedder)
    yield tmp_path / "idx.json"
    kb_vector.set_embedder(kb_vector.gemini_embedder)


def test_backend_vetorial_tem_o_mesmo_formato(vetorial):
    r = kb.search("o que a gmud bloqueia no deploy em producao?", 2)
    assert r and set(r[0]) == {"source", "score", "text"}
    assert r[0]["source"].startswith("pipeline_deploy.md#")


def test_indice_so_recalcula_o_que_mudou(vetorial):
    calls = []

    def contando(texts):
        calls.append(len(texts))
        return _fake_embedder(texts)

    kb_vector.set_embedder(contando)
    kb_vector.build_index(vetorial)
    kb_vector.build_index(vetorial)
    assert calls == [len(kb.load_chunks())]  # a 2ª vez vem toda do cache


def test_falha_do_provedor_nao_vira_lacuna(vetorial, ctx, tmp_catalog):
    from onboarding_core.tools import search_knowledge_base

    def fora_do_ar(texts):
        raise kb_vector.VectorSearchUnavailable("sem rede")

    kb_vector.set_embedder(fora_do_ar)
    r = search_knowledge_base("o que é a GMUD?", ctx)
    assert r["found"] is False and "indisponível" in r["error"]
    assert tmp_catalog.list_open_gaps() == []  # sem troca silenciosa e sem lacuna falsa


def test_padrao_continua_palavra_chave(monkeypatch):
    monkeypatch.delenv("ONBOARDING_KB_BACKEND", raising=False)
    assert kb.backend() == "keyword"
    assert kb.search("o que é GMUD?")[0]["source"] == "pipeline_deploy.md#GMUD"


async def test_servidor_mcp_expoe_a_mesma_busca():
    mcp_kb = pytest.importorskip("onboarding_core.mcp_kb")
    tools = {t.name for t in await mcp_kb.server.list_tools()}
    assert {"buscar_trechos", "listar_fontes", "status_base"} <= tools
    r = await mcp_kb.server.call_tool("buscar_trechos", {"pergunta": "o que é GMUD?", "top_k": 1})
    assert "pipeline_deploy.md#GMUD" in r.content[0].text
    fontes = await mcp_kb.server.call_tool("listar_fontes", {})
    assert "solar_originar_proposta.md#Passo a passo" in str(fontes.content)
