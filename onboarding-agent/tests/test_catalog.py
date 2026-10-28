from conftest import bank, draft

from onboarding_core.tools import get_material, log_gap, save_material_draft, set_my_role


def test_rascunho_aprovacao_e_versionamento(ctx, tmp_catalog):
    set_my_role("dev_salesforce", ctx)
    assert get_material("pipeline_deploy", ctx)["found"] is False

    r = draft(tmp_catalog, content="v1")
    m = get_material("pipeline_deploy", ctx)
    assert m["found"] is False and "aprovado" in m["instruction"]  # rascunho não chega ao tutorado

    tmp_catalog.approve(r.id, "maria")
    assert get_material("pipeline_deploy", ctx)["content_md"] == "v1"

    # nova versão em rascunho não substitui a aprovada para o Tutor
    draft(tmp_catalog, content="v2")
    m = get_material("pipeline_deploy", ctx)
    assert m["found"] and m["content_md"] == "v1"


def test_publicacao_le_material_e_banco_do_estado(ctx, tmp_catalog):
    ctx.state.update(draft="conteúdo final", quiz_bank={"questions": bank(5)})
    r = save_material_draft("dev_salesforce", "pipeline_deploy", "D",
                            ["[pipeline_deploy.md#GMUD]"], ctx)
    assert r["ok"] and r["quiz_questions"] == 5
    m = tmp_catalog.get(r["material_id"])
    assert m.content_md == "conteúdo final" and m.sources == ["pipeline_deploy.md#GMUD"]


def test_publicacao_recusa_sem_fonte_ou_banco_invalido(ctx):
    ctx.state.update(draft="c", quiz_bank={"questions": bank(5)})
    assert not save_material_draft("dev_salesforce", "pipeline_deploy", "X", [], ctx)["ok"]
    ctx.state["quiz_bank"] = {"questions": bank(2)}  # pequeno demais
    r = save_material_draft("dev_salesforce", "pipeline_deploy", "X", ["a.md#b"], ctx)
    assert not r["ok"] and "banco" in r["error"]


def test_stale_por_fonte(tmp_catalog):
    r = draft(tmp_catalog)
    tmp_catalog.approve(r.id, "maria")
    assert tmp_catalog.mark_stale_by_source("pipeline_deploy.md") == 1
    assert tmp_catalog.get_latest("dev_salesforce", "pipeline_deploy") is None


def test_log_gap_usa_contexto(ctx, tmp_catalog):
    set_my_role("dev_salesforce", ctx)
    log_gap("Quem aprova a GMUD?", ctx, module_id="pipeline_deploy")
    gaps = tmp_catalog.list_open_gaps("dev_salesforce")
    assert gaps[0].user_id == "u-test" and gaps[0].module_id == "pipeline_deploy"


def test_descartar_registra_motivo_e_libera_regeracao(tmp_catalog):
    r = draft(tmp_catalog)
    m = tmp_catalog.discard(r.id, "maria", "tom técnico demais")
    assert m.status == "stale" and "tom técnico" in m.review_note
    # --missing-only do curate_role usa este get: descartado não conta como "tem material"
    assert tmp_catalog.get_latest("dev_salesforce", "pipeline_deploy", approved_only=False) is None
    assert len(tmp_catalog.list_by_status(None)) == 1


def test_migracao_adiciona_review_note(tmp_path):
    import sqlite3

    from onboarding_core.storage import Catalog

    db = tmp_path / "old.db"
    with sqlite3.connect(db) as c:  # schema antigo, sem review_note
        c.execute("CREATE TABLE materials (id INTEGER PRIMARY KEY, role_id TEXT, module_id TEXT,"
                  " version INTEGER, title TEXT, content_md TEXT, sources TEXT, status TEXT,"
                  " approved_by TEXT, created_at TEXT)")
    cat = Catalog(db)
    m = cat.save_draft("r", "m", "t", "c", ["x"], review_note="ok")
    assert m.review_note == "ok" and cat.get(m.id).quiz == []


def test_get_material_abre_o_modulo(ctx, tmp_catalog):
    from onboarding_core.tools import state_keys as K

    set_my_role("dev_salesforce", ctx)
    m = draft(tmp_catalog, module="cultura_empresa", sources=["cultura.md#Valores"])
    tmp_catalog.approve(m.id, "rev")
    assert get_material("cultura_empresa", ctx)["found"]
    assert ctx.state[K.CURRENT_MODULE] == "cultura_empresa"
    assert ctx.state[K.MATERIAL_LOADED] == "cultura_empresa"


def test_busca_do_tutor_registra_lacuna_quando_nao_acha(ctx, tmp_catalog):
    from onboarding_core.tools import search_knowledge_base, search_sources

    set_my_role("dev_salesforce", ctx)
    r = search_knowledge_base("qual o horário do almoço? meu email é joao@empresa.com.br", ctx)
    assert not r["found"] and r["gap_registered"]
    gap = tmp_catalog.list_open_gaps()[0]
    assert "<EMAIL>" in gap.question and gap.role_id == "dev_salesforce"
    ok = search_knowledge_base("o que é GMUD?", ctx)
    assert ok["found"] and ok["results"][0]["cite"].startswith("[pipeline_deploy.md#")
    assert not search_sources("horário almoço")["found"]
    assert len(tmp_catalog.list_open_gaps()) == 1  # busca do Curador não gera lacuna
