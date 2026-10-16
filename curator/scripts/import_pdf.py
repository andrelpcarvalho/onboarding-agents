"""Importa um PDF e gera o pacote (base, trilha, materiais como rascunho).

Uso:
    python scripts/import_pdf.py examples/manual-qa.pdf --role-id analista_qa \\
        --role-title "Analista de QA" --role-hint "testa entregas Salesforce" \\
        --buddy-contact "#onboarding-qa no Slack"
    python scripts/import_pdf.py arquivo.pdf --role-id x --role-title "X" --skip-materials
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

from curator_agent.package import run_pipeline

warnings.filterwarnings("ignore")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("pdf", type=Path)
    p.add_argument("--role-id", required=True)
    p.add_argument("--role-title", required=True)
    p.add_argument("--role-hint")
    p.add_argument("--buddy-contact")
    p.add_argument("--out", type=Path)
    p.add_argument("--skip-materials", action="store_true", help="só base e trilha (mais rápido)")
    a = p.parse_args()
    run_pipeline(a.pdf, a.role_id, a.role_title, role_hint=a.role_hint,
                 buddy_contact=a.buddy_contact, out_dir=a.out, skip_materials=a.skip_materials)


if __name__ == "__main__":
    main()
