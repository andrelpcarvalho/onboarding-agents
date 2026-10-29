"""Checklist do documento de input (RN-01, RN-02, RN-04) e massa de homologação (#13)."""

from datetime import date
from pathlib import Path

from onboarding_core import kb
from onboarding_core.config import KB_DIR
from onboarding_core.kb_checklist import check_document, check_homolog_data

HOJE = date(2026, 10, 29)

FM = """---
titulo: Teste
slug: {slug}
area_dona: Squad Teste
responsavel: fulano
versao: 1.0
vigente_ate: {vig}
tipo: {tipo}
status: {status}
---
"""

PROC = """# Teste
## Objetivo
Fazer X.
## Pré-requisitos
- Acesso.
## Passo a passo
1. Primeiro.
2. Segundo.
## Como saber que deu certo
Aparece Y.
## Onde tirar dúvidas
Canal Z.
"""


def _doc(tmp_path: Path, body: str = PROC, slug: str = "doc", vig: str = "2027-01-31",
         tipo: str = "procedimento", status: str = "aprovado") -> Path:
    p = tmp_path / f"{slug}.md"
    p.write_text(FM.format(slug=slug, vig=vig, tipo=tipo, status=status) + body, encoding="utf-8")
    return p


def test_base_simulada_passa_no_checklist():
    for f in sorted(KB_DIR.glob("*.md")):
        r = check_document(f, today=HOJE)
        assert r.ok, (f.name, r.errors)


def test_procedimento_completo_passa(tmp_path):
    assert check_document(_doc(tmp_path), today=HOJE).ok


def test_sem_metadados_e_rejeitado(tmp_path):
    p = tmp_path / "x.md"
    p.write_text(PROC, encoding="utf-8")
    assert "sem metadados" in check_document(p, today=HOJE).errors[0]


def test_rejeicao_lista_o_que_falta(tmp_path):
    body = "# T\n## Objetivo\nX.\n## Passo a passo\nfaça isso\n"
    errs = check_document(_doc(tmp_path, body=body), today=HOJE).errors
    assert any("Pré-requisitos" in e for e in errs)
    assert any("Como saber que deu certo" in e for e in errs)
    assert any("lista numerada" in e for e in errs)


def test_vencido_e_slug_errado(tmp_path):
    p = _doc(tmp_path, slug="outro", vig="2026-01-01")
    p = p.rename(tmp_path / "nome_errado.md")
    errs = check_document(p, today=HOJE).errors
    assert any("vencido" in e for e in errs) and any("slug" in e for e in errs)


def test_aviso_de_vencimento_proximo(tmp_path):
    r = check_document(_doc(tmp_path, vig="2026-11-10"), today=HOJE)
    assert r.ok and any("vence em 12" in w for w in r.warnings)


def test_cpf_no_documento_bloqueia(tmp_path):
    body = PROC.replace("Fazer X.", "Use o CPF 529.982.247-25 do cliente.")
    assert any("RN-04" in e for e in check_document(_doc(tmp_path, body=body), today=HOJE).errors)


def test_contato_oficial_nao_bloqueia(tmp_path):
    body = PROC.replace("Canal Z.", "E-mail seguranca@empresa.com.br ou (11) 3333-4444.")
    assert check_document(_doc(tmp_path, body=body), today=HOJE).ok


def test_rascunho_e_vencido_ficam_fora_da_busca():
    assert kb.is_published({"status": "aprovado", "vigente_ate": "2027-01-01"}, HOJE)
    assert not kb.is_published({"status": "rascunho", "vigente_ate": "2027-01-01"}, HOJE)
    assert not kb.is_published({"status": "aprovado", "vigente_ate": "2026-01-01"}, HOJE)
    assert kb.is_published({}, HOJE)  # legado sem metadados: o make check acusa


def test_metadados_nao_viram_trecho_citavel():
    assert not any("area_dona" in c.text or c.heading == "---" for c in kb.load_chunks())
    assert "solar_originar_proposta.md#Passo a passo" in kb.valid_sources()


def test_massa_de_homologacao_precisa_ser_simulada(tmp_path):
    assert check_homolog_data().ok  # a do repositório
    p = tmp_path / "h.yaml"
    p.write_text('cpfs:\n  - "529.982.247-25"\n', encoding="utf-8")
    assert any("simulado" in e for e in check_homolog_data(p).errors)
    p.write_text('simulado: true\ncpfs:\n  - "123"\n', encoding="utf-8")
    assert any("não são CPF" in e for e in check_homolog_data(p).errors)
