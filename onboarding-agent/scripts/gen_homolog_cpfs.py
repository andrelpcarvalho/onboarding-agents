"""Gera CPFs FICTÍCIOS com dígitos verificadores válidos para a massa de homologação.

Uso:
    python scripts/gen_homolog_cpfs.py            # imprime 5 CPFs (semente fixa)
    python scripts/gen_homolog_cpfs.py --n 10 --write   # regrava data/homolog_data.yaml

Os números saem de uma semente fixa para a demo ser reproduzível. São válidos só no
formato (passam no dígito verificador), não correspondem a ninguém de propósito, mas
CPF é um espaço pequeno: trate a massa como dado de teste e nunca a use fora da PoC.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "homolog_data.yaml"
HEADER = """# Massa de teste de HOMOLOGAÇÃO — SIMULADA para a PoC do curso.
# Os CPFs abaixo foram GERADOS (dígitos verificadores válidos, números fictícios) por
# `python scripts/gen_homolog_cpfs.py`. Nunca coloque CPF real aqui: estes valores são a
# única exceção ao mascaramento de dados pessoais (ver README, riscos residuais).
simulado: true
gerado_por: scripts/gen_homolog_cpfs.py
cpfs:
"""


def cpf(rng: random.Random) -> str:
    d = [rng.randint(0, 9) for _ in range(9)]
    while len(set(d)) == 1:
        d = [rng.randint(0, 9) for _ in range(9)]
    for n in (9, 10):
        d.append((sum(v * (n + 1 - i) for i, v in enumerate(d)) * 10 % 11) % 10)
    s = "".join(map(str, d))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261029)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    cpfs = [cpf(rng) for _ in range(a.n)]
    if a.write:
        OUT.write_text(HEADER + "".join(f'  - "{c}"\n' for c in cpfs), encoding="utf-8")
        print(f"{len(cpfs)} CPF(s) fictício(s) gravados em {OUT}")
    else:
        print("\n".join(cpfs))


if __name__ == "__main__":
    main()
