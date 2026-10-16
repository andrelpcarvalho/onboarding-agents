from onboarding_core.tools import get_my_progress, set_my_role, start_module
from onboarding_core.tools import state_keys as K
from onboarding_core.tools.progress import record_completion


def test_sem_papel_pede_definicao(ctx):
    assert get_my_progress(ctx)["role_id"] is None


def test_papel_invalido(ctx):
    r = set_my_role("nao_existe", ctx)
    assert not r["ok"] and "dev_salesforce" in r["valid_roles"]


def test_fluxo_completo_e_prerequisito(ctx):
    set_my_role("dev_salesforce", ctx)
    p = get_my_progress(ctx)
    assert p["next_module"] == "cultura_empresa"
    assert p["completed"] == "0/4"

    start_module("cultura_empresa", ctx)
    assert ctx.state[K.CURRENT_MODULE] == "cultura_empresa"
    record_completion("cultura_empresa", 1.0, ctx.state)

    # pipeline_deploy depende de acessos_ferramentas, então o próximo é acessos
    assert get_my_progress(ctx)["next_module"] == "acessos_ferramentas"


def test_nota_baixa_entra_em_revisao_e_melhor_nota_prevalece(ctx):
    set_my_role("dev_salesforce", ctx)
    r = record_completion("seguranca_informacao", 0.33, ctx.state)
    assert r["needs_review"]
    assert get_my_progress(ctx)["to_review"] == ["seguranca_informacao"]

    record_completion("seguranca_informacao", 1.0, ctx.state)
    record_completion("seguranca_informacao", 0.5, ctx.state)
    assert ctx.state[K.PROGRESS]["seguranca_informacao"]["score"] == 1.0
    assert ctx.state[K.PROGRESS]["seguranca_informacao"]["attempts"] == 3
    assert get_my_progress(ctx)["to_review"] == []


def test_modulo_fora_da_trilha(ctx):
    set_my_role("analista_negocios", ctx)
    assert not start_module("pipeline_deploy", ctx)["ok"]


def test_buddy_sem_atribuicao_usa_canal_do_papel(ctx):
    set_my_role("dev_salesforce", ctx)
    b = get_my_progress(ctx)["buddy"]
    assert not b["assigned"] and b["contact"].startswith("#onboarding-dev")


def test_buddy_atribuido_vem_do_banco(ctx, tmp_catalog):
    tmp_catalog.assign_buddy("u-test", "maria.souza", "Maria Souza", "@maria.souza no Slack", "rh")
    b = get_my_progress(ctx)["buddy"]  # mesmo sem papel definido
    assert b == {"assigned": True, "name": "Maria Souza", "contact": "@maria.souza no Slack"}
