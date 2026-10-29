"""Aprovação de missão pelo approve.py (item 7): grava no YAML só status e approved_by."""

import shutil

import pytest
import yaml

from onboarding_core import mission_review as mr
from onboarding_core.config import MISSIONS_DIR

MID = "site_solar_proposta_acom"


@pytest.fixture
def pasta(tmp_path):
    shutil.copy(MISSIONS_DIR / f"{MID}.yaml", tmp_path)
    return tmp_path


def _raw(pasta):
    return yaml.safe_load((pasta / f"{MID}.yaml").read_text(encoding="utf-8"))


def test_devolver_e_aprovar_mexe_so_no_status(pasta):
    antes = (pasta / f"{MID}.yaml").read_text(encoding="utf-8")
    mr.set_status(MID, "draft", "maria", "falta o passo do ACOM", folder=pasta)
    r = _raw(pasta)
    assert r["status"] == "draft" and r["approved_by"] is None
    assert r["review_note"] == "falta o passo do ACOM"
    mr.set_status(MID, "approved", "maria", folder=pasta)
    r = _raw(pasta)
    assert r["status"] == "approved" and r["approved_by"] == "maria"
    depois = (pasta / f"{MID}.yaml").read_text(encoding="utf-8")
    # roteiro intacto: só as linhas do topo mudam
    assert antes.split("steps:", 1)[1] == depois.split("steps:", 1)[1]


def test_nao_aprova_missao_com_pendencia(pasta):
    f = pasta / f"{MID}.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace(
        '"site_solar_acom.md#Pré-análise"', '"site_solar_acom.md#Seção que não existe"'),
        encoding="utf-8")
    mr.set_status(MID, "draft", "maria", "teste", folder=pasta)
    with pytest.raises(ValueError, match="não existe"):
        mr.set_status(MID, "approved", "maria", folder=pasta)
    assert _raw(pasta)["status"] == "draft"


def test_missao_em_rascunho_some_da_trilha(pasta, monkeypatch):
    from onboarding_core import missions

    mr.set_status(MID, "draft", "maria", "revisar", folder=pasta)
    monkeypatch.setattr(missions, "MISSIONS_DIR", pasta)
    missions.load_missions.cache_clear()
    try:
        assert missions.get_mission(MID) is None
    finally:
        missions.load_missions.cache_clear()


def test_visao_do_revisor_mostra_o_que_o_codigo_confere():
    txt = mr.describe(mr.find(MID).mission)
    assert "captura numero_proposta_site" in txt and "conclui quando" in txt
    assert mr.problems(mr.find(MID).mission) == []


def test_missao_inexistente(pasta):
    with pytest.raises(KeyError):
        mr.set_status("nao_existe", "approved", "maria", folder=pasta)
