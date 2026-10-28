import pytest
from google.genai import types

from onboarding_core.guardrails import PiiRedactionPlugin
from onboarding_core.pii import cnpj_is_valid, cpf_is_valid, redact
from onboarding_core.tools import escalate_to_buddy, log_gap, set_my_role


def test_validadores_br():
    assert cpf_is_valid("529.982.247-25") and not cpf_is_valid("123.456.789-00")
    assert cnpj_is_valid("11.222.333/0001-81") and not cnpj_is_valid("11.222.333/0001-00")


@pytest.mark.parametrize("texto,esperado", [
    ("meu cpf é 529.982.247-25", "<CPF>"),
    ("fone (11) 98765-4321", "<TELEFONE>"),
    ("joao@empresa.com.br", "<EMAIL>"),
    ("cnpj 11.222.333/0001-81", "<CNPJ>"),
])
def test_mascara_pii(texto, esperado):
    assert esperado in redact(texto)[0]


@pytest.mark.parametrize("texto", [
    "o módulo 3 tem 45 minutos",
    "a release 2026.10 sai dia 15",
    "quem aprova a GMUD?",
    "B",
])
def test_sem_falso_positivo(texto):
    assert redact(texto) == (texto, [])


async def test_plugin_mascara_mensagem_antes_de_gravar():
    msg = types.Content(role="user", parts=[types.Part(text="cpf 529.982.247-25, me ajuda?")])
    out = await PiiRedactionPlugin().on_user_message_callback(
        invocation_context=None, user_message=msg
    )
    assert out.parts[0].text == "cpf <CPF>, me ajuda?"
    limpa = types.Content(role="user", parts=[types.Part(text="oi")])
    assert await PiiRedactionPlugin().on_user_message_callback(
        invocation_context=None, user_message=limpa) is None


def test_escalonamento_mascara_e_limita(ctx, tmp_catalog):
    set_my_role("dev_salesforce", ctx)
    r = escalate_to_buddy("rh", "dúvida sobre salário, cpf 529.982.247-25", ctx)
    assert r["ok"] and r["buddy"]["contact"].startswith("#onboarding-dev")
    esc = tmp_catalog.list_escalations()[0]
    assert "<CPF>" in esc.summary and esc.user_id == "u-test"
    escalate_to_buddy("acesso", "sem acesso ao sandbox", ctx, urgency="alta")
    escalate_to_buddy("outro", "x", ctx)
    assert not escalate_to_buddy("outro", "y", ctx)["ok"]  # limite diário
    assert tmp_catalog.list_escalations()[0].urgency == "alta"  # alta primeiro


def test_lacuna_mascarada(ctx, tmp_catalog):
    set_my_role("dev_salesforce", ctx)
    log_gap("meu email é joao@empresa.com.br, quem aprova GMUD?", ctx)
    assert "<EMAIL>" in tmp_catalog.list_open_gaps()[0].question


def test_pedido_vai_para_o_buddy_atribuido(ctx, tmp_catalog):
    set_my_role("dev_salesforce", ctx)
    tmp_catalog.assign_buddy("u-test", "maria.souza", "Maria", "@maria", "rh")
    escalate_to_buddy("acesso", "sem acesso ao sandbox", ctx)
    assert tmp_catalog.list_escalations(buddy_id="maria.souza")[0].category == "acesso"
    assert tmp_catalog.list_escalations(unassigned=True) == []


async def test_saida_preserva_contatos_oficiais_mas_mascara_cpf():
    from google.adk.models.llm_response import LlmResponse

    texto = "Reporte em seguranca@empresa.com.br ou (11) 3333-4444. CPF 529.982.247-25"
    resp = LlmResponse(content=types.Content(role="model", parts=[types.Part(text=texto)]))
    out = await PiiRedactionPlugin().after_model_callback(callback_context=None, llm_response=resp)
    t = out.content.parts[0].text
    assert "seguranca@empresa.com.br" in t and "(11) 3333-4444" in t and "<CPF>" in t


async def test_orcamento_de_tools_por_resposta():
    from types import SimpleNamespace

    from onboarding_core.guardrails import ToolCallBudgetPlugin

    plug = ToolCallBudgetPlugin(per_tool=3, per_turn=5)
    tool = SimpleNamespace(name="answer_mission")
    turn1 = SimpleNamespace(invocation_id="inv-1")
    results = [await plug.before_tool_callback(tool=tool, tool_args={}, tool_context=turn1)
               for _ in range(4)]
    assert results[:3] == [None, None, None]  # até 3 chamadas da mesma tool rodam
    assert results[3]["ok"] is False and "pare de chamar" in results[3]["next_step"]

    other = SimpleNamespace(name="search_knowledge_base")
    assert await plug.before_tool_callback(tool=other, tool_args={}, tool_context=turn1) is None
    assert await plug.before_tool_callback(tool=other, tool_args={}, tool_context=turn1)  # 6ª total

    await plug.after_run_callback(invocation_context=turn1)  # nova mensagem zera o orçamento
    assert await plug.before_tool_callback(tool=tool, tool_args={}, tool_context=turn1) is None
