# AGENTS.md — contexto para agentes de código (Antigravity, Claude Code, etc.)

## O que é
Sistema multiagente de onboarding com Google ADK (Python 3.11):
- **Tutor** (`src/onboarding_core/agents/tutor.py`): conversa com o colaborador, conduz a trilha
  do papel dele, aplica quiz, conduz missões práticas e registra progresso.
- **Curador** (`src/onboarding_core/agents/curator.py`): pipeline planner → writer →
  reviewer (loop) → publisher que gera materiais por papel a partir de `data/kb/` e salva como rascunho.

## Regras do projeto
- Lógica de agentes vive em `src/onboarding_core/`; `agents/<nome>/agent.py` só expõe `root_agent`.
- Uma pasta em `agents/` = um app no `adk web`. Não coloque código compartilhado lá.
- Progresso do colaborador = estado `user:*` (ver `tools/state_keys.py`). Nunca grave progresso
  via LLM livre; sempre via tool determinística.
- Materiais só chegam ao colaborador como "revisados" após `scripts/approve.py approve`.
- Toda tool: type hints + docstring com `Args:` (vira o schema da function call).
- Toda tool nova precisa de teste em `tests/` usando o `FakeToolContext` (sem chamar LLM).
- Prompts ficam em `agents/prompts.py`, em pt-BR.
- Missão (`data/missions/*.yaml`, `tools/missions.py`): só o código avança checkpoint e conclui.
  `expected`, `pattern` e `block_on` nunca vão ao modelo; `answer_mission` lê a mensagem do
  colaborador. CPF de teste só da massa em `data/homolog_data.yaml`. Rode `make check` ao mexer.
- O Tutor não chama o Curador (Curador é TO-BE/offline): material só vem do catálogo.
- Nota de quiz NUNCA vem do modelo: só `answer_quiz` grava, via `record_completion` (não exposto).
  Perguntas e gabarito vêm do banco aprovado do material; nunca devolva `correct_option` ao modelo.
- Mudou prompt, modelo, tool ou `.env`? Rode `make eval` (modelo real) além do `make test`.
  Novos comportamentos importantes ganham um caso em `evals/build_evalsets.py`.
- Texto livre que vai para o banco (lacunas, escalonamentos etc.) passa por `pii.redact_text`.
  O plugin `PiiRedactionPlugin` deve estar no Runner e no `App` de cada agente com usuário final.
- Buddy vem de `buddy_assignments` (definido pelo responsável via scripts/buddy.py); nunca
  exponha tool que deixe o tutorado escolher ou trocar o próprio buddy.

## Comandos
- `make setup` · `make test` · `make check` · `make web` · `make chat USER_ID=fulano`
- `make new-role ID=x TITLE="X"` · `make curate ROLE=dev_salesforce` · `scripts/approve.py --help`
- Guias por persona em `docs/` (responsável, autor, revisor, buddy, tutorado); índice em `docs/README.md`.
- Ao mudar comportamento visível a uma persona, atualize o guia dela.
