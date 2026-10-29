"""`make demo-setup` monta a demo inteira com dados simulados, isolada dos dados normais."""

import os
import subprocess
import sys
from pathlib import Path

import yaml

from onboarding_core import kb
from onboarding_core.quiz_bank import parse_bank, validate_bank
from onboarding_core.roles import load_roles

ROOT = Path(__file__).resolve().parents[1]


def test_materiais_simulados_cobrem_todos_os_modulos_com_fontes_validas():
    data = yaml.safe_load((ROOT / "data/demo/materiais.yaml").read_text(encoding="utf-8"))
    for role in load_roles().values():
        for m in role.modules:
            spec = data["modulos"][m.id]
            assert validate_bank(parse_bank(spec["perguntas"])) is None, m.id
            assert set(spec["fontes"]) <= kb.valid_sources(), m.id
            for q in spec["perguntas"]:  # a explicação cita uma fonte do próprio material
                assert any(f"[{s}]" in q["explanation"] for s in spec["fontes"]), q["question"]


def _run(env_dir: Path) -> subprocess.CompletedProcess:
    env = {**os.environ,
           "ONBOARDING_CATALOG_DB": str(env_dir / "catalog.db"),
           "ONBOARDING_SESSIONS_DB": str(env_dir / "sessions.db"),
           "ONBOARDING_MEMORY_DB": str(env_dir / "memory.db")}
    return subprocess.run([sys.executable, "scripts/demo_setup.py"], cwd=ROOT, env=env,
                          capture_output=True, text=True, check=False)


def test_demo_setup_monta_catalogo_aprovado_e_atribuicoes(tmp_path):
    from onboarding_core.storage import Catalog

    d = tmp_path / ".adk" / "demo"
    r = _run(d)
    assert r.returncode == 0, r.stderr
    cat = Catalog(d / "catalog.db")
    for role in load_roles().values():
        for m in role.modules:
            mat = cat.get_latest(role.id, m.id, approved_only=True)
            assert mat is not None and mat.status == "approved" and len(mat.quiz) >= 4
    assert cat.get_role_assignment("demo.ana").role_id == "dev_salesforce"
    assert cat.get_assignment("demo.bruno").buddy_name == "Bia Buddy"
    assert _run(d).returncode == 0  # rodar de novo recria do zero


def test_demo_setup_recusa_banco_que_nao_e_de_demo(tmp_path):
    r = _run(tmp_path / ".adk")
    assert r.returncode != 0 and "recusado" in r.stderr
