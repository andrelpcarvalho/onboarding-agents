# AGENTS.md: contexto para agentes de código

Variante em **LangGraph 1.2** do onboarding-agent (Google ADK). Mesmo comportamento; ver
`docs/MIGRACAO-ADK-LANGGRAPH.md` para o mapa de conceitos.

## Regras
- Grafos em `tutor/graph.py` e `curator/graph.py`. Tools do Tutor recebem `runtime: ToolRuntime`
  (store, context.user_id, state): nunca passe user_id como argumento visível ao modelo.
- Progresso = Store `("profile", user_ns(user_id))`; lembranças = `("memories", ...)`. Sempre use
  `profile.user_ns()`: o Store não aceita ponto em namespace.
- Texto de mensagens: use `str(msg.text)`, nunca `msg.content` (o Gemini com thinking devolve blocos).
- PII: a entrada é mascarada em `guardrails.prepare_user_message` ANTES do `invoke` (o checkpoint
  grava a entrada antes dos nós). Todo ponto de entrada novo precisa passar por ela.
- Nota de quiz só por `progress.record_completion`, chamada por `answer_quiz`. Nunca exponha
  `correct_option` ao modelo.
- `schemas.py`, `storage.py`, `quiz_bank.py`, `pii.py`, `kb.py`, `roles.py` são compartilhados com a
  versão ADK: mantenha o formato do catálogo compatível.

## Comandos
`make test` · `make check` · `make chat USER_ID=x` · `make eval` (modelo real) · `make studio`
