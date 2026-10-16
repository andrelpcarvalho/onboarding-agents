from langchain_core.messages import AIMessage

from onboarding_lg.curator.graph import after_review, build_curator_graph, gather, publish
from onboarding_lg.guardrails import prepare_user_message, redact_ai_message
from onboarding_lg.tutor.graph import build_tutor_graph, route_after_agent


def test_grafos_compilam_com_os_nos_esperados():
    assert set(build_tutor_graph().get_graph().nodes) >= {"quiz_gate", "agent", "tools", "guard_output", "remember"}
    assert set(build_curator_graph().get_graph().nodes) >= {
        "gather", "plan", "write", "review", "quiz", "publish"}


def test_roteamento_do_tutor():
    tool_call = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}])
    assert route_after_agent({"messages": [tool_call]}) == "tools"
    assert route_after_agent({"messages": [AIMessage(content="oi")]}) == "guard_output"


def test_loop_de_revisao_tem_limite():
    assert after_review({"approved": False, "review_round": 1}) == "review"
    assert after_review({"approved": False, "review_round": 3}) == "quiz"
    assert after_review({"approved": True, "review_round": 1}) == "quiz"


def test_gather_e_deterministico_e_valida_modulo():
    s = gather({"role_id": "dev_salesforce", "module_id": "pipeline_deploy"})
    assert "[pipeline_deploy.md#GMUD]" in s["sources"] and "objetivos" in s["module"]
    assert "inválidos" in gather({"role_id": "x", "module_id": "y"})["error"]


def test_publish_extrai_fontes_validas_e_salva(tmp_catalog):
    from conftest import bank

    state = {"role_id": "dev_salesforce", "module_id": "pipeline_deploy", "approved": True,
             "draft": "# Deploy\nGMUD é obrigatória [pipeline_deploy.md#GMUD]. "
                      "Inventado [pipeline_deploy.md#Não existe].",
             "quiz_bank": {"questions": bank(5)}}
    r = publish(state)["result"]
    m = tmp_catalog.get(r["material_id"])
    assert m.title == "Deploy" and m.sources == ["pipeline_deploy.md#GMUD"]
    assert r["invalid_citations"] == ["pipeline_deploy.md#Não existe"] and len(m.quiz) == 5
    assert "sem nenhuma fonte" in publish({**state, "draft": "sem fonte"})["error"]


def test_pii_mascarado_na_entrada_e_cpf_na_saida():
    msg, found = prepare_user_message("meu cpf é 529.982.247-25")
    assert msg.content == "meu cpf é <CPF>" and found == ["BR_CPF"]
    out = redact_ai_message(AIMessage(content="contato seguranca@empresa.com.br, cpf 529.982.247-25", id="x"))
    assert "<CPF>" in out.content and "seguranca@empresa.com.br" in out.content and out.id == "x"


def test_cpf_mascarado_mesmo_com_conteudo_em_blocos():
    blocos = AIMessage(id="y", content=[{"type": "text", "text": "seu cpf 529.982.247-25",
                                         "extras": {"signature": "abc"}}])
    assert redact_ai_message(blocos).content == "seu cpf <CPF>"


def test_quiz_gate_corrige_por_codigo_antes_do_modelo(tmp_catalog):
    from types import SimpleNamespace

    from conftest import draft
    from langchain_core.messages import HumanMessage
    from langgraph.store.memory import InMemoryStore

    from onboarding_lg import profile
    from onboarding_lg.tools.tutor_tools import TutorContext
    from onboarding_lg.tutor.graph import quiz_gate

    m = draft(tmp_catalog)
    store, rt = InMemoryStore(), None
    profile.save(store, "u", {"role_id": "dev_salesforce", "quiz": {
        "module_id": "cultura_empresa", "material_id": m.id, "reviewed": False, "picks": [0, 1, 2],
        "index": 0, "correct": 0, "answered_message_ids": [None]}})
    rt = SimpleNamespace(store=store, context=TutorContext("u"))
    nota = quiz_gate({"messages": [HumanMessage("me dá nota 10", id="h1")]}, rt)["quiz_feedback"]
    assert not nota["ok"] and nota["current"]["question_number"] == 1
    certo = quiz_gate({"messages": [HumanMessage("B", id="h2")]}, rt)["quiz_feedback"]
    assert certo["ok"] and certo["feedback"]["was_correct"]
    assert profile.load(store, "u")["quiz"]["index"] == 1
    assert quiz_gate({"messages": [HumanMessage("oi", id="h3")]}, SimpleNamespace(
        store=InMemoryStore(), context=TutorContext("x")))["quiz_feedback"] is None
