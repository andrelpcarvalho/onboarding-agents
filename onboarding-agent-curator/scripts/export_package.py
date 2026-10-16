"""Exporta um pacote para o onboarding-agent: base e trilha em data/, materiais como
RASCUNHO no catálogo (precisam de aprovação lá).

Uso:
    python scripts/export_package.py out/analista_qa-20261013-120000 ../onboarding-agent
    python scripts/export_package.py <pacote> <destino> --force   # sobrescreve arquivos
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from curator_agent.package import export_package


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("package", type=Path)
    p.add_argument("target", type=Path, help="pasta do onboarding-agent")
    p.add_argument("--catalog", type=Path, help="catálogo do destino (padrão: <destino>/.adk/catalog.db)")
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    try:
        r = export_package(a.package, a.target, target_catalog=a.catalog, force=a.force)
    except (ValueError, FileExistsError) as e:
        sys.exit(str(e))
    print("\nNo onboarding-agent: reinicie make web/chat, rode `make check` e aprove os rascunhos"
          f" {r['drafts']} com scripts/approve.py.")


if __name__ == "__main__":
    main()
