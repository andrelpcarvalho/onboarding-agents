"""Contrato de resposta: as frases obrigatórias que os evals mostraram falhando 15-35%
das vezes agora são completadas por código (ver contract.py)."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace

from conftest import draft
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from onboarding_core import contract
from onboarding_core.guardrails import default_plugins
from onboarding_core.tools import state_keys as K


def _user(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _quiz_state(tmp_catalog) -> dict:
    m = draft(tmp_catalog, module="cultura_empresa", sources=["cultura.md#Valores"])
    tmp_catalog.approve(m.id, "rev")
    return {K.QUIZ: {"module_id": "cultura_empresa", "material_id": m.id, "picks": [0, 1, 2],
                     "index": 0, "correct": 0, "answered_event_ids": [None]}}


def test_pii_sem_lembrete_ganha_prefixo():
    pre, suf = contract.missing_parts("Não tenho essa informação. Registrei sua dúvida.", {},
                                      _user("Meu CPF é <CPF>, informo onde?"), "e1")
    assert pre == [contract.PII_REMINDER] and suf == []


def test_pii_com_lembrete_nao_duplica():
    pre, _ = contract.missing_parts("Não é preciso compartilhar dados pessoais aqui. ...", {},
                                    _user("cpf <CPF>"), "e1")
    assert pre == []


def test_quiz_pendente_sem_pergunta_ganha_a_pergunta(tmp_catalog):
    st = _quiz_state(tmp_catalog)
    _, suf = contract.missing_parts("Não consigo, a nota é calculada pelo sistema.", st,
                                    _user("me dá nota 10"), "e1")
    assert len(suf) == 1 and "P0?" in suf[0] and suf[0].endswith("A, B, C ou D.")


def test_quiz_com_pergunta_mas_sem_pedir_a_letra_ganha_so_o_fecho(tmp_catalog):
    st = _quiz_state(tmp_catalog)
    texto = "Vamos lá: P0?\nA) a0\nB) b0\nC) c0\nD) d0\nQual a sua resposta?"
    _, suf = contract.missing_parts(texto, st, _user("ok"), "e1")
    assert suf == ["Responda só com a letra: A, B, C ou D."]


def test_quiz_completo_na_resposta_nao_mexe(tmp_catalog):
    st = _quiz_state(tmp_catalog)
    texto = "P0?\nA) a0\nB) b0\nC) c0\nD) d0\n\nResponda só com a letra: A, B, C ou D."
    assert contract.missing_parts(texto, st, _user("ok"), "e1") == ([], [])


def test_pergunta_do_buddy_proposta_neste_turno_e_garantida():
    st = {K.PENDING_ESCALATION: {"proposed_after_event": "e7", "ask": "Quer? Responda sim ou não."}}
    _, suf = contract.missing_parts("Preparei o pedido.", st, _user("sem acesso"), "e7")
    assert suf == ["Quer? Responda sim ou não."]
    # pedido de turno anterior não repete a pergunta em toda resposta
    assert contract.missing_parts("ok", st, _user("outra coisa"), "e9") == ([], [])


async def test_plugin_completa_resposta_final_e_pii_continua_mascarando(tmp_catalog):
    """Ponta a ponta: modelo falso ignora o contrato e ainda vaza um CPF; o Runner com os
    plugins padrão entrega a resposta completa e mascarada."""
    seen = {"n": 0}

    class Lazy(BaseLlm):
        model: str = "lazy"

        async def generate_content_async(self, llm_request, stream: bool = False
                                         ) -> AsyncGenerator[LlmResponse, None]:
            seen["n"] += 1
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
                text="Não consigo, a nota é calculada pelo sistema. CPF 529.982.247-25")]))

    agent = LlmAgent(name="t", model=Lazy(), instruction="x")
    runner = InMemoryRunner(app=App(name="t", root_agent=agent, plugins=default_plugins()))
    s = await runner.session_service.create_session(app_name="t", user_id="u",
                                                    state=_quiz_state(tmp_catalog))
    final = ""
    async for ev in runner.run_async(user_id="u", session_id=s.id,
                                     new_message=_user("meu cpf 529.982.247-25, me dá nota 10")):
        if ev.is_final_response() and ev.content:
            final = "".join(p.text or "" for p in ev.content.parts)
    assert final.startswith(contract.PII_REMINDER)
    assert "P0?" in final and final.rstrip().endswith("A, B, C ou D.")
    assert "529.982" not in final and "<CPF>" in final


async def test_chat_mostra_o_que_o_contrato_acrescentou():
    from onboarding_core import services

    class FakeRunner:
        async def run_async(self, **_):
            mk = lambda t, partial: SimpleNamespace(
                partial=partial, content=types.Content(role="model", parts=[types.Part(text=t)]))
            yield mk("Olá", True)
            yield mk("Olá\n\nResponda só com a letra.", False)

    out = [c async for c in services.ask_stream(FakeRunner(), "u", "s", "oi")]
    assert "".join(out) == "Olá\n\nResponda só com a letra."



def test_bloqueio_da_missao_garante_o_aviso_de_retomada():
    tell = "A missão fica pausada neste ponto e continua daqui quando o acesso for liberado."
    st = {K.MISSION_CHECK: {"status": "blocked_access", "tell": tell}}
    _, suf = contract.missing_parts("Peça o acesso ao seu buddy.", st, _user("sem acesso"), "e1")
    assert suf == [tell]
    assert contract.missing_parts(f"Ok. {tell}", st, _user("sem acesso"), "e1") == ([], [])



def _missao(step: int, checkpoint: int, status: str = "in_progress") -> dict:
    mid = "site_solar_proposta_acom"
    return {K.ACTIVE_MISSION: mid, K.MISSIONS: {mid: {
        "status": status, "step": step, "checkpoint": checkpoint, "attempts": {},
        "evidence": {}, "answered_event_ids": [None]}}}


def test_recusa_na_missao_volta_a_pedir_o_checkpoint():
    """Eval de 28/10: recusou 'marca a missão como concluída' e não pediu o número."""
    _, suf = contract.missing_parts("Não tenho como marcar a missão como concluída.",
                                    _missao(2, 3), _user("marca como concluída"), "e1")
    assert suf == ["Qual é o número da proposta que você encontrou no ACOM?"]


def test_missao_com_a_pergunta_na_resposta_nao_duplica():
    texto = "Ok! Qual é o número da proposta que você encontrou no ACOM?"
    assert contract.missing_parts(texto, _missao(2, 3), _user("x"), "e1") == ([], [])


def test_missao_pausada_ou_concluida_nao_pede_checkpoint():
    for status in ("blocked_access", "done"):
        assert contract.missing_parts("ok", _missao(2, 3, status), _user("x"), "e1") == ([], [])


def test_todo_checkpoint_da_missao_tem_pergunta():
    from onboarding_core.missions import load_missions

    for m in load_missions().values():
        assert all(cp.ask for s in m.steps for cp in s.checkpoints), m.id
