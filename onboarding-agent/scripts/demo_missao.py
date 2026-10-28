"""Mostra, sem chamar o modelo, o que o Tutor recebe e o que o código decide em cada checkpoint.

Uso:
    .venv/bin/python scripts/demo_missao.py            # caminho feliz
    .venv/bin/python scripts/demo_missao.py --tropecos # erros, bloqueio e número divergente

As mensagens simulam o colaborador. Nada é gravado em .adk/ (estado em memória).
"""

from __future__ import annotations

import argparse
from types import SimpleNamespace

from google.genai import types

from onboarding_core.tools import answer_mission, set_my_role, start_mission

FELIZ = [
    "Sim. Apareceu a tela inicial com a opção de iniciar uma simulação.",
    "Concluí a pré-análise e estou na tela de simulação.",
    "A simulação foi concluída. Estou preenchendo os dados do proponente.",
    "Concluí. O sistema confirmou a proposta. Número: 12345.",
    "Entendi, pode seguir.",
    "Estou na tela inicial e vejo a opção de consulta de propostas.",
    "No topo aparece o perfil Operador Solar.",
    "Encontrei a proposta 12345.",
]

TROPECOS = [
    "Apareceu uma tela azul.",                                   # não confere
    "Sim. Apareceu a opção de iniciar uma simulação.",
    "Concluí a pré-análise e estou na tela de simulação.",
    "Estou nos dados do proponente.",
    "Confirmou a proposta. Número: 12345.",
    "Não entendi o que é o ACOM.",                               # confirm com negação
    "Entendi, pode seguir.",
    "Vejo a consulta de propostas.",
    "Não tenho acesso de operador.",                             # pausa a missão
    "!retomar",                                                  # start_mission de novo
    "Agora aparece Operador Solar.",
    "Não achei nada.",                                           # 1ª tentativa
    "Continua sem aparecer.",                                    # 2ª: libera manual de logs
    "Encontrei a proposta 99999.",                               # número divergente
    "Conferi o CPF e achei a 12345.",
]


class Ctx(SimpleNamespace):
    def say(self, text: str) -> None:
        n = len(self.session.events)
        self.session.events.append(SimpleNamespace(
            id=f"ev{n}", author="user",
            content=types.Content(role="user", parts=[types.Part(text=text)])))


def mostrar(r: dict) -> None:
    view = r.get("next") or r.get("current")
    extra = {k: r[k] for k in ("attempts", "suggest_buddy", "expected_value", "evidence")
             if k in r and r[k] not in (None, False)}
    print(f"   código: {r.get('status') or r.get('error')} {extra if extra else ''}")
    if r.get("next_step"):
        print(f"   orientação: {r['next_step']}")
    if not view:
        return
    print(f"   Tutor recebe → etapa {view['step']} · {view['step_title']} · checkpoint {view['checkpoint']}")
    print(f"     instrução: {view['tutor_instruction'].strip()}")
    for e in view["explain"]:
        print(f"     explicar com: {e['cite']}")
    if view.get("fallback"):
        print(f"     fallback: {view['fallback']['cite']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tropecos", action="store_true")
    roteiro = TROPECOS if ap.parse_args().tropecos else FELIZ

    ctx = Ctx(state={}, user_id="demo", session=SimpleNamespace(events=[]))
    set_my_role("analista_negocios", ctx)
    ctx.say("quero fazer a missão do solar")
    print("▶ colaborador: quero fazer a missão do solar")
    mostrar(start_mission("site_solar_proposta_acom", ctx))

    for msg in roteiro:
        ctx.say(msg)
        if msg == "!retomar":
            print("\n▶ colaborador: já liberaram meu acesso (Tutor chama start_mission)")
            mostrar(start_mission("site_solar_proposta_acom", ctx))
            continue
        print(f"\n▶ colaborador: {msg}")
        mostrar(answer_mission(ctx))


if __name__ == "__main__":
    main()
