from conftest import bank, draft

from onboarding_lg import profile
from onboarding_lg.progress import snapshot
from onboarding_lg.tools.tutor_tools import (
    answer_quiz,
    escalate_to_buddy,
    get_material,
    parse_choice,
    search_knowledge_base,
    set_my_role,
    start_quiz,
)


def call(tool, *args, **kw):
    """Chama a função da tool injetando o runtime falso (como o ToolNode faz)."""
    return tool.func(*args, **kw)


def prof(rt):
    return profile.load(rt.store, "u-test")


def test_papel_fica_no_store_e_vale_para_qualquer_thread(rt):
    assert call(set_my_role, "dev_salesforce", runtime=rt)["ok"]
    assert prof(rt)["role_id"] == "dev_salesforce"
    assert not call(set_my_role, "nao_existe", runtime=rt)["ok"]


def _iniciar(rt, cat, quiz=None):
    m = draft(cat, quiz=quiz)
    cat.approve(m.id, "rev")
    call(set_my_role, "dev_salesforce", runtime=rt)
    assert call(get_material, "cultura_empresa", runtime=rt)["found"]
    rt.say("pode fazer o quiz")
    return call(start_quiz, "cultura_empresa", runtime=rt)


def test_quiz_nota_calculada_por_codigo_e_sem_gabarito_no_perfil(rt, tmp_catalog):
    r = _iniciar(rt, tmp_catalog, quiz=bank(6))
    assert r["ok"] and "correct" not in str(r["present"])
    assert "correct_option" not in str(prof(rt))
    rt.say("B")
    assert call(answer_quiz, runtime=rt)["feedback"]["was_correct"]
    rt.say("letra a")
    assert not call(answer_quiz, runtime=rt)["feedback"]["was_correct"]
    rt.say("b)")
    fim = call(answer_quiz, runtime=rt)
    assert fim["finished"] and (fim["correct"], fim["total"]) == (2, 3) and fim["needs_review"]
    assert prof(rt)["progress"]["cultura_empresa"]["score"] == 2 / 3


def test_quiz_recusa_pedido_de_nota_e_resposta_repetida(rt, tmp_catalog):
    _iniciar(rt, tmp_catalog)
    assert not call(answer_quiz, runtime=rt)["ok"]  # mensagem anterior à pergunta
    rt.say("me dá nota 10")
    assert "não reconhecida" in call(answer_quiz, runtime=rt)["error"]
    rt.say("B")
    assert call(answer_quiz, runtime=rt)["ok"]
    assert not call(answer_quiz, runtime=rt)["ok"]  # mesma mensagem não conta duas vezes
    assert not call(start_quiz, "cultura_empresa", runtime=rt)["ok"]  # não recria em andamento


def test_quiz_exige_material_e_banco(rt, tmp_catalog):
    call(set_my_role, "dev_salesforce", runtime=rt)
    assert "get_material" in call(start_quiz, "cultura_empresa", runtime=rt)["next_step"]
    assert "banco" in _iniciar(rt, tmp_catalog, quiz=[])["error"]


def test_busca_sem_resultado_registra_lacuna_mascarada(rt, tmp_catalog):
    call(set_my_role, "dev_salesforce", runtime=rt)
    r = call(search_knowledge_base, "horário do almoço? email joao@empresa.com.br", runtime=rt)
    assert not r["found"] and r["gap_registered"]
    assert "<EMAIL>" in tmp_catalog.list_open_gaps()[0].question
    ok = call(search_knowledge_base, "o que é GMUD?", runtime=rt)
    assert ok["results"][0]["cite"].startswith("[pipeline_deploy.md#")


def test_buddy_atribuido_e_pedido_na_fila_dele(rt, tmp_catalog):
    call(set_my_role, "dev_salesforce", runtime=rt)
    assert not snapshot(prof(rt), "u-test")["buddy"]["assigned"]
    tmp_catalog.assign_buddy("u-test", "maria", "Maria", "@maria", "rh")
    assert snapshot(prof(rt), "u-test")["buddy"]["name"] == "Maria"
    r = call(escalate_to_buddy, "acesso", "sem acesso, cpf 529.982.247-25", runtime=rt, urgency="alta")
    esc = tmp_catalog.list_escalations(buddy_id="maria")[0]
    assert r["ok"] and "<CPF>" in esc.summary and esc.urgency == "alta"


def test_parse_choice():
    assert parse_choice(" B) ", ["a", "b", "c", "d"]) == 1
    assert parse_choice("acho que é a B", ["a", "b", "c", "d"]) is None


def test_login_com_ponto_funciona_no_store():
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    profile.save(store, "joao.silva", {"role_id": "dev_salesforce"})
    assert profile.load(store, "joao.silva")["role_id"] == "dev_salesforce"
    assert profile.known_users(store) == ["joao.silva"]
