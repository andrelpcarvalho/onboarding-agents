"""Testes sem LLM: leitura de PDF, base, checagem de fidelidade, trilha e exportação."""

from pathlib import Path

import pytest
import yaml

from curator_agent.ingest import check_grounding, write_kb
from curator_agent.kb import KnowledgeBase
from curator_agent.package import export_package
from curator_agent.pdf import load_pdf
from curator_agent.quiz_bank import parse_bank
from curator_agent.schemas import KnowledgeBaseDraft, ModuleProposal, RoleProposal
from curator_agent.storage import Catalog
from curator_agent.trail import finalize_role, write_role

ROOT = Path(__file__).resolve().parents[1]
PDF_TEXT = ("Testes nunca podem ser executados em produção. A suíte roda às 22h no UAT. "
            "Bugs são abertos no Jira, projeto QA, com evidência.")


def draft(text_seguranca="Testes nunca podem ser executados em produção."):
    return KnowledgeBaseDraft(documents=[
        {"slug": "Ambientes de Teste", "title": "Ambientes", "sections": [
            {"heading": "Onde testar", "text": text_seguranca}]},
        {"slug": "bugs", "title": "Bugs", "sections": [
            {"heading": "Como abrir um bug", "text": "Bugs são abertos no Jira, projeto QA, com evidência."}]},
    ])


def test_pdf_de_exemplo_tem_texto():
    data, text, pages = load_pdf(ROOT / "examples" / "manual-qa.pdf")
    assert pages == 2 and data[:4] == b"%PDF" and "nunca podem ser executados" in text


def test_grounding_aceita_fiel_e_pega_regra_enfraquecida_e_numero_inventado():
    ok = check_grounding(draft(), PDF_TEXT)
    assert all(c.ok for c in ok)
    ruim = check_grounding(draft("Testes devem ser evitados em produção às 23h, sempre."), PDF_TEXT)[0]
    assert not ruim.ok and "23h" in ruim.missing_numbers and "sempre" in ruim.new_strong_words


def test_write_kb_gera_formato_do_onboarding_agents(tmp_path):
    files = write_kb(draft(), tmp_path / "kb", "manual.pdf")
    assert [f.name for f in files] == ["ambientes_de_teste.md", "bugs.md"]
    kb = KnowledgeBase(tmp_path / "kb")
    assert "ambientes_de_teste.md#Onde testar" in kb.valid_sources()
    assert kb.search("onde testar em produção")[0]["source"] == "ambientes_de_teste.md#Onde testar"


def test_trilha_validada_sem_llm(tmp_path):
    write_kb(draft(), tmp_path / "kb", "manual.pdf")
    kb = KnowledgeBase(tmp_path / "kb")
    proposal = RoleProposal(description="Testa entregas.", modules=[
        ModuleProposal(id="ambientes", title="Ambientes", objectives=["Saber onde testar", "x"],
                       kb_tags=["produção", "inexistente"], prerequisites=["bugs"]),
        ModuleProposal(id="bugs", title="Bugs", objectives=["Saber abrir bug", "y"],
                       kb_tags=["jira", "bug"], prerequisites=["ambientes"]),
        ModuleProposal(id="Nada Aqui", title="?", objectives=["a", "b"], kb_tags=["marte"]),
    ])
    role, warnings = finalize_role(proposal, kb, "analista_qa", "Analista de QA", None)
    assert [m.id for m in role.modules] == ["ambientes", "bugs"]  # sem cobertura: descartado
    assert role.modules[0].kb_tags == ["produção"] and role.modules[0].prerequisites == []
    assert role.modules[1].prerequisites == ["ambientes"]
    assert any("inexistente" in w for w in warnings) and role.buddy_contact.startswith("TODO")
    data = yaml.safe_load(write_role(role, tmp_path / "roles").read_text())
    assert data["id"] == "analista_qa" and "seniority" not in data


def test_exporta_para_projeto_destino_como_rascunho(tmp_path):
    pkg, target = tmp_path / "pkg", tmp_path / "onboarding-agent"
    (target / "data" / "kb").mkdir(parents=True)
    (target / "data" / "roles").mkdir(parents=True)
    write_kb(draft(), pkg / "kb", "manual.pdf")
    (pkg / "roles").mkdir()
    (pkg / "roles" / "analista_qa.yaml").write_text("id: analista_qa\n")
    bank = [{"question": f"P{i}?", "options": ["a", "b", "c", "d"], "correct_option": 1}
            for i in range(4)]
    Catalog(pkg / "catalog.db").save_draft("analista_qa", "bugs", "Bugs", "c", ["bugs.md#Como abrir um bug"],
                                           quiz=parse_bank(bank))
    r = export_package(pkg, target, log=lambda _: None)
    assert r["files"] == 3 and len(r["drafts"]) == 1
    dst = Catalog(target / ".adk" / "catalog.db").list_by_status("draft")[0]
    assert dst.status == "draft" and len(dst.quiz) == 4 and "importado" in dst.review_note
    with pytest.raises(FileExistsError):
        export_package(pkg, target, log=lambda _: None)  # não sobrescreve sem --force
