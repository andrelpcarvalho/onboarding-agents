"""Backup consistente dos bancos SQLite do MVP (pode rodar com o app no ar).

Uso:
    python scripts/backup.py                 # -> backups/<timestamp>/
    python scripts/backup.py --dest /mnt/bkp

Agende com cron (ex.: diário) e copie a pasta para um bucket se quiser off-site:
    gsutil -m cp -r backups/<timestamp> gs://<bucket>/onboarding/
"""

from __future__ import annotations

import argparse
from pathlib import Path

from onboarding_core.db import backup


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dest", type=Path, help="diretório raiz dos backups (default: backups/)")
    print(f"backup em {backup(p.parse_args().dest)}")


if __name__ == "__main__":
    main()
