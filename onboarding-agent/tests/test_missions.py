"""Missões: o exemplo de execução da reunião vira contrato testável (sem LLM)."""

import pytest

from onboarding_core import missions as M
from onboarding_core.pii import cpf_is_valid, redact
from onboarding_core.tools import (
    answer_mission,
    get_test_cpf,
    set_my_role,
    start_mission,
)
from onboarding_core.tools import state_keys as K
from onboarding_core.tools.progress import progress_snapshot

MISSAO = "site_solar_proposta_acom"

ATE_PERFIL = [
    "Sim. Apareceu a tela inicial com a opção de iniciar uma simulação.",
    "Concluí a pré-análise e estou na tela de simulação.",
    "A simulação foi concluída. Estou preenchendo os dados do proponente.",
    "Concluí. O sistema confirmou a proposta. Número: 12345.",
    "Entendi, pode seguir.",
    "Estou na tela inicial e vejo a opção de consulta de propostas.",
]


def _cpf_ficticio() -> str:
    """Gera um CPF com dígitos válidos só para o teste (não vai para o repositório)."""
    base = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    for n in (9, 10):
        total = sum(d * (n + 1 - i) for i, d in enumerate(base))
        base.append((total * 10 % 11) % 10)
    return "".join(map(str, base))


@pytest.fixture
def massa(monkeypatch):
    cpf = _cpf_ficticio()
    assert cpf_is_valid(cpf)
    M.homolog_cpfs.cache_clear()
    monkeypatch.setattr(M, "homolog_cpfs", lambda: (cpf,))
    return cpf


def _iniciar(ctx):
    set_my_role("analista_negocios", ctx)
    ctx.say("quero fazer a missão do solar")
    return start_mission(MISSAO, ctx)


def _ate_perfil(ctx):
    assert _iniciar(ctx)["ok"]
    for msg in ATE_PERFIL:
        ctx.say(msg)
        assert answer_mission(ctx)["status"] == "advanced", msg


def test_execucao_do_exemplo_conclui_com_evidencia(ctx):
    _ate_perfil(ctx)
    ctx.say("No topo aparece o perfil Operador Solar.")
    assert answer_mission(ctx)["status"] == "advanced"
    ctx.say("Encontrei a proposta 12345.")
    r = answer_mission(ctx)
    assert r["status"] == "mission_done"
    assert r["evidence"] == {"numero_proposta_site": "12345", "numero_proposta_acom": "12345"}
    p = ctx.state[K.MISSIONS][MISSAO]
    assert p["status"] == "done" and p["finished_at"] and ctx.state[K.ACTIVE_MISSION] is None


def test_numero_diferente_nao_conclui(ctx):
    _ate_perfil(ctx)
    ctx.say("Perfil operador solar.")
    answer_mission(ctx)
    ctx.say("Encontrei a proposta 99999.")
    r = answer_mission(ctx)
    assert r["status"] == "mismatch" and r["expected_value"] == "12345"
    assert ctx.state[K.MISSIONS][MISSAO]["status"] == "in_progress"
    ctx.say("Corrigi o CPF, achei a 12345.")
    assert answer_mission(ctx)["status"] == "mission_done"


def test_sem_perfil_bloqueia_e_retoma_do_mesmo_ponto(ctx):
    _ate_perfil(ctx)
    ctx.say("Não tenho acesso de operador.")
    assert answer_mission(ctx)["status"] == "blocked_access"
    ctx.say("tenta de novo")
    assert answer_mission(ctx)["status"] == "blocked_access"
    ctx.say("já liberaram meu acesso")
    r = start_mission(MISSAO, ctx)
    assert r["ok"] and r["current"]["checkpoint"] == "acesso_operador"
    ctx.say("Agora aparece Operador Solar.")
    assert answer_mission(ctx)["status"] == "advanced"


def test_descricao_errada_nao_avanca_e_sugere_buddy(ctx):
    assert _iniciar(ctx)["ok"]
    for n in (1, 2, 3):
        ctx.say("apareceu uma tela azul")
        r = answer_mission(ctx)
        assert r["status"] == "not_confirmed" and r["attempts"] == n
    assert r["suggest_buddy"] is True
    assert r["current"]["checkpoint"] == "tela_inicial_site"


def test_mesma_mensagem_nao_conta_duas_vezes(ctx):
    assert _iniciar(ctx)["ok"]
    assert not answer_mission(ctx)["ok"]  # o pedido de iniciar não é resposta
    ctx.say("Vejo a opção de simulação.")
    assert answer_mission(ctx)["status"] == "advanced"
    assert not answer_mission(ctx)["ok"]  # modelo chamando de novo sem nova mensagem


def test_nao_entendi_nao_confirma(ctx):
    _ate_perfil_sem_ultimos = ATE_PERFIL[:4]
    assert _iniciar(ctx)["ok"]
    for msg in _ate_perfil_sem_ultimos:
        ctx.say(msg)
        answer_mission(ctx)
    ctx.say("não entendi o que é o ACOM")
    assert answer_mission(ctx)["status"] == "not_confirmed"


def test_fallback_aparece_depois_de_duas_tentativas(ctx):
    _ate_perfil(ctx)
    ctx.say("Perfil operador solar.")
    answer_mission(ctx)
    ctx.say("não achei nada")
    assert answer_mission(ctx)["current"]["fallback"] is None
    ctx.say("continua sem aparecer")
    fb = answer_mission(ctx)["current"]["fallback"]
    assert fb["cite"] == "[site_solar_acom.md#Proposta não encontrada no ACOM]" and fb["text"]


def test_view_nao_vaza_verificacao_e_traz_explicacao_da_base(ctx):
    r = _iniciar(ctx)
    assert "expected" not in str(r) and "pattern" not in str(r) and "block_on" not in str(r)
    ctx.say("Apareceu o simulador.")
    nxt = answer_mission(ctx)["next"]
    assert nxt["explain"][0]["cite"] == "[site_solar_acom.md#Pré-análise]"
    assert "avaliação inicial" in nxt["explain"][0]["text"]
    assert nxt["guidance"].startswith("Se precisar de um CPF")


def test_missao_fora_da_trilha_ou_sem_papel(ctx):
    assert not start_mission(MISSAO, ctx)["ok"]
    set_my_role("analista_negocios", ctx)
    assert not start_mission("missao_inexistente", ctx)["ok"]


def test_cpf_de_teste_estavel_e_so_na_etapa_certa(ctx, massa):
    assert _iniciar(ctx)["ok"]
    assert not get_test_cpf(ctx)["ok"]  # etapa 1 não libera CPF
    ctx.say("Vejo o simulador.")
    answer_mission(ctx)
    a, b = get_test_cpf(ctx), get_test_cpf(ctx)
    assert a["ok"] and a["test_cpf"] == b["test_cpf"] == massa


def test_cpf_sem_massa_configurada(ctx, monkeypatch):
    monkeypatch.setattr(M, "homolog_cpfs", lambda: ())
    assert _iniciar(ctx)["ok"]
    ctx.say("Vejo o simulador.")
    answer_mission(ctx)
    assert get_test_cpf(ctx)["error"] == "massa de teste não configurada"


def test_cpf_da_massa_passa_pelo_mascaramento(massa):
    texto, ents = redact(f"usei o cpf {massa} na simulação")
    assert massa in texto and not ents


def test_contexto_do_tutor_mostra_missao_em_andamento(ctx):
    set_my_role("analista_negocios", ctx)
    snap = progress_snapshot(ctx.state, ctx.user_id)
    assert snap["missions"][0]["id"] == MISSAO and snap["mission_in_progress"] is None
    ctx.say("bora")
    start_mission(MISSAO, ctx)
    snap = progress_snapshot(ctx.state, ctx.user_id)
    assert snap["mission_in_progress"]["checkpoint"] == "tela_inicial_site"


# ---- regressões do teste manual de 27/10 (make chat) ----

def test_colaborador_a_frente_captura_numero_na_mesma_etapa(ctx):
    """'Número: 12345' chegou quando a missão ainda esperava a tela de simulação."""
    assert _iniciar(ctx)["ok"]
    ctx.say("apareceu a opção de iniciar uma simulação")
    answer_mission(ctx)
    ctx.say("estou na tela de simulação → estou nos dados do proponente")  # duas telas numa msg
    r = answer_mission(ctx)
    assert r["status"] == "advanced" and r["next"]["checkpoint"] == "dados_proposta"
    assert [s["checkpoint"] for s in r["skipped"]] == ["simulacao"]
    assert r["skipped"][0]["explain"][0]["cite"] == "[site_solar_acom.md#Simulação]"
    ctx.say("o sistema confirmou a proposta. Número: 12345")
    r = answer_mission(ctx)
    assert r["status"] == "advanced" and r["next"]["step"] == "3/3"
    assert ctx.state[K.MISSIONS][MISSAO]["evidence"]["numero_proposta_site"] == "12345"


def test_pula_direto_para_o_capture_da_etapa(ctx):
    assert _iniciar(ctx)["ok"]
    ctx.say("vejo o simulador")
    answer_mission(ctx)  # agora em pre_analise
    ctx.say("já terminei tudo, o sistema confirmou a proposta 12345")
    r = answer_mission(ctx)
    assert r["status"] == "advanced" and r["next"]["checkpoint"] == "entendeu_acom"
    assert [s["checkpoint"] for s in r["skipped"]] == ["simulacao", "dados_proposta"]


def test_nao_atravessa_etapa_nem_pula_capture(ctx):
    assert _iniciar(ctx)["ok"]
    ctx.say("vejo o simulador")
    answer_mission(ctx)  # pre_analise, etapa 2
    ctx.say("vejo a consulta de propostas e o perfil operador solar")  # isso é da etapa 3
    assert answer_mission(ctx)["status"] == "not_confirmed"
    assert ctx.state[K.MISSIONS][MISSAO]["checkpoint"] == 0


def test_bloqueio_de_checkpoint_adiante_na_mesma_etapa(ctx):
    _ate_perfil(ctx)  # já em acesso_operador; recua para testar a partir de tela_inicial_acom
    p = ctx.state[K.MISSIONS][MISSAO]
    p["checkpoint"] = 1
    ctx.state[K.MISSIONS] = {MISSAO: p}
    ctx.say("não tenho acesso de operador")
    assert answer_mission(ctx)["status"] == "blocked_access"
    assert ctx.state[K.MISSIONS][MISSAO]["blocked"]["checkpoint"] == "acesso_operador"


def test_chamada_repetida_manda_parar(ctx):
    assert _iniciar(ctx)["ok"]
    ctx.say("vejo o simulador")
    assert answer_mission(ctx)["status"] == "advanced"
    r = answer_mission(ctx)
    assert r["status"] == "already_evaluated" and "NÃO chame" in r["next_step"]
    assert "current" not in r


def test_cpf_de_teste_na_mensagem_nao_vira_numero_da_proposta(ctx, massa):
    _ate_perfil(ctx)
    ctx.say("Perfil operador solar.")
    answer_mission(ctx)
    ctx.say(f"consultei pelo CPF {massa} e achei a proposta 12345")
    assert answer_mission(ctx)["status"] == "mission_done"
