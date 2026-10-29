"""Controles por código do PR de controles: papel pelo responsável e consentimento do buddy."""

from onboarding_core.agents import build_tutor
from onboarding_core.tools import confirm_escalation, propose_escalation
from onboarding_core.tools import state_keys as K
from onboarding_core.tools.progress import progress_snapshot, sync_role


def _tool_names() -> set[str]:
    return {getattr(t, "__name__", getattr(t, "name", "")) for t in build_tutor().tools}


def test_tutor_nao_expoe_tools_que_o_modelo_nao_pode_usar():
    names = _tool_names()
    assert {"set_my_role", "escalate_to_buddy", "curator"}.isdisjoint(names)
    assert {"propose_escalation", "confirm_escalation"} <= names


# ---------- papel pelo responsável ----------

def test_papel_vem_da_atribuicao_e_nao_da_conversa(ctx, tmp_catalog):
    ctx.state[K.ROLE_ID] = "dev_salesforce"  # estado antigo ou "escolhido" na conversa
    assert sync_role(ctx.state, ctx.user_id) is None
    assert ctx.state[K.ROLE_ID] is None
    assert "responsável" in progress_snapshot(ctx.state, ctx.user_id)["hint"]

    tmp_catalog.assign_role(ctx.user_id, "analista_negocios", "andre")
    assert sync_role(ctx.state, ctx.user_id) == "analista_negocios"
    assert progress_snapshot(ctx.state, ctx.user_id)["role"] == "Analista de Negócios"


def test_troca_de_papel_pelo_responsavel_vale_na_proxima_mensagem(ctx, tmp_catalog):
    tmp_catalog.assign_role(ctx.user_id, "dev_salesforce", "andre")
    sync_role(ctx.state, ctx.user_id)
    tmp_catalog.assign_role(ctx.user_id, "analista_negocios", "andre")
    assert sync_role(ctx.state, ctx.user_id) == "analista_negocios"
    tmp_catalog.unassign_role(ctx.user_id)
    assert sync_role(ctx.state, ctx.user_id) is None


def test_papel_inexistente_no_catalogo_nao_vale(ctx, tmp_catalog):
    tmp_catalog.assign_role(ctx.user_id, "papel_removido", "andre")
    assert sync_role(ctx.state, ctx.user_id) is None


# ---------- consentimento do buddy ----------

def _propor(ctx):
    ctx.state[K.ROLE_ID] = "dev_salesforce"
    ctx.say("tô sem acesso ao sandbox, quem me ajuda?")
    return propose_escalation("acesso", "sem acesso ao sandbox, cpf 529.982.247-25", ctx)


def test_proposta_nao_registra_nada(ctx, tmp_catalog):
    r = _propor(ctx)
    assert r["status"] == "awaiting_consent" and "<CPF>" in r["summary"]
    assert tmp_catalog.list_escalations() == []


def test_confirmar_sem_nova_mensagem_nao_registra(ctx, tmp_catalog):
    _propor(ctx)
    r = confirm_escalation(ctx)  # modelo tentando consentir pelo colaborador
    assert r["status"] == "awaiting_consent" and tmp_catalog.list_escalations() == []


def test_sim_registra_uma_vez(ctx, tmp_catalog):
    _propor(ctx)
    ctx.say("sim, pode registrar")
    r = confirm_escalation(ctx)
    assert r["status"] == "registered"
    esc = tmp_catalog.list_escalations()
    assert len(esc) == 1 and esc[0].category == "acesso" and "<CPF>" in esc[0].summary
    assert ctx.state[K.PENDING_ESCALATION] is None
    assert not confirm_escalation(ctx)["ok"]  # repetir não duplica
    assert len(tmp_catalog.list_escalations()) == 1


def test_nao_cancela_e_resposta_ambigua_pergunta_de_novo(ctx, tmp_catalog):
    _propor(ctx)
    ctx.say("hmm, quem é o buddy mesmo?")
    assert confirm_escalation(ctx)["status"] == "unclear"
    ctx.say("não, deixa que eu falo com ele")
    assert confirm_escalation(ctx)["status"] == "declined"
    assert tmp_catalog.list_escalations() == [] and ctx.state[K.PENDING_ESCALATION] is None


def test_pedido_pendente_aparece_no_contexto(ctx, tmp_catalog):
    _propor(ctx)
    snap = progress_snapshot(ctx.state, ctx.user_id)
    assert snap["pending_escalation"]["category"] == "acesso"
    assert "529" not in str(snap["pending_escalation"])


def test_limite_diario_vale_na_proposta(ctx, tmp_catalog):
    for _ in range(3):
        _propor(ctx)
        ctx.say("sim")
        assert confirm_escalation(ctx)["status"] == "registered"
    assert not _propor(ctx)["ok"]


async def test_tutor_sincroniza_papel_antes_de_responder(tmp_catalog):
    """Ponta a ponta com modelo falso: o papel do catálogo chega ao estado e à instrução."""
    from collections.abc import AsyncGenerator

    from google.adk.apps import App
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    seen: dict = {}

    class EchoModel(BaseLlm):
        model: str = "echo"

        async def generate_content_async(self, llm_request, stream: bool = False
                                         ) -> AsyncGenerator[LlmResponse, None]:
            seen["instruction"] = str(llm_request.config.system_instruction)
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="ok")]))

    agent = build_tutor()
    agent.model = EchoModel()
    agent.generate_content_config = None
    runner = InMemoryRunner(app=App(name="tutor", root_agent=agent))
    tmp_catalog.assign_role("joao", "analista_negocios", "andre")
    s = await runner.session_service.create_session(app_name="tutor", user_id="joao",
                                                    state={K.ROLE_ID: "dev_salesforce"})
    msg = types.Content(role="user", parts=[types.Part(text="sou dev salesforce")])
    async for _ in runner.run_async(user_id="joao", session_id=s.id, new_message=msg):
        pass
    s = await runner.session_service.get_session(app_name="tutor", user_id="joao", session_id=s.id)
    assert s.state[K.ROLE_ID] == "analista_negocios"
    assert "Analista de Negócios" in seen["instruction"]



async def test_relatorio_usa_papel_atribuido_mesmo_sem_nova_conversa(tmp_catalog, monkeypatch, tmp_path):
    from onboarding_core import reports

    monkeypatch.setattr(reports, "SESSIONS_DB", tmp_path / "s.db")
    tmp_catalog.assign_role("nova.pessoa", "analista_negocios", "andre")
    s = await reports.tutee_status("nova.pessoa")
    assert s.role == "Analista de Negócios" and s.completed == "0/4"



def test_pergunta_de_consentimento_traz_nome_e_contato(ctx, tmp_catalog):
    tmp_catalog.assign_buddy(ctx.user_id, "maria", "Maria Eval", "@maria.eval no Slack", "rh")
    r = _propor(ctx)
    assert "Maria Eval" in r["ask"] and "@maria.eval no Slack" in r["ask"]
    assert r["ask"].endswith("Responda sim ou não.")


def test_pergunta_sem_buddy_usa_canal_do_papel(ctx, tmp_catalog):
    r = _propor(ctx)
    assert "#onboarding-dev" in r["ask"] and "responsável" in r["ask"]



def test_bloqueio_da_missao_vem_antes_do_buddy(ctx, tmp_catalog):
    """Eval de 28/10: 'não tenho acesso de operador' foi direto para o buddy, sem
    registrar o bloqueio na missão."""
    from test_missions import ATE_PERFIL, MISSAO, _iniciar

    from onboarding_core.tools import answer_mission

    tmp_catalog.assign_role(ctx.user_id, "analista_negocios", "rh")
    _iniciar(ctx)
    for m in ATE_PERFIL:
        ctx.say(m)
        answer_mission(ctx)
    ctx.say("Não tenho acesso de operador no ACOM")
    r = propose_escalation("acesso", "sem acesso de operador no ACOM", ctx)
    assert not r["ok"] and "answer_mission" in r["next_step"]
    assert tmp_catalog.list_escalations() == []

    b = answer_mission(ctx)
    assert b["status"] == "blocked_access" and "continua daqui" in b["tell"]
    assert propose_escalation("acesso", "sem acesso de operador no ACOM", ctx)["ok"]
    assert ctx.state[K.MISSIONS][MISSAO]["status"] == "blocked_access"


def test_duvida_fora_da_missao_vai_ao_buddy_sem_contar_tentativa(ctx, tmp_catalog):
    from test_missions import MISSAO, _iniciar

    _iniciar(ctx)
    ctx.say("quanto ganha um dev pleno aqui?")
    assert propose_escalation("rh", "dúvida sobre faixa salarial", ctx)["ok"]
    assert ctx.state[K.MISSIONS][MISSAO]["attempts"] == {}


async def test_conferencia_da_missao_chega_ao_modelo_sem_tool(tmp_catalog):
    """Ponta a ponta com modelo falso que NÃO chama tool: a missão avança mesmo assim e o
    resultado aparece na instrução."""
    from collections.abc import AsyncGenerator

    from google.adk.apps import App
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    seen: dict = {}

    class Mute(BaseLlm):
        model: str = "mute"

        async def generate_content_async(self, llm_request, stream: bool = False
                                         ) -> AsyncGenerator[LlmResponse, None]:
            seen["si"] = str(llm_request.config.system_instruction)
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="ok")]))

    agent = build_tutor()
    agent.model = Mute()
    agent.generate_content_config = None
    runner = InMemoryRunner(app=App(name="tutor", root_agent=agent))
    tmp_catalog.assign_role("ana", "dev_salesforce", "rh")
    mid = "site_solar_proposta_acom"
    s = await runner.session_service.create_session(app_name="tutor", user_id="ana", state={
        K.ACTIVE_MISSION: mid, K.MISSIONS: {mid: {
            "status": "in_progress", "step": 0, "checkpoint": 0, "attempts": {},
            "evidence": {}, "answered_event_ids": [None], "started_at": "x"}}})
    msg = types.Content(role="user", parts=[types.Part(text="Apareceu a opção de simulação")])
    async for _ in runner.run_async(user_id="ana", session_id=s.id, new_message=msg):
        pass
    s = await runner.session_service.get_session(app_name="tutor", user_id="ana", session_id=s.id)
    assert (s.state[K.MISSIONS][mid]["step"], s.state[K.MISSIONS][mid]["checkpoint"]) == (1, 0)
    assert '"mission_check": {' in seen["si"] and '"status": "advanced"' in seen["si"]
