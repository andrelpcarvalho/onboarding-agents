# AGENTS.md: contexto para agentes de código

Curador isolado: PDF → base de conhecimento → trilha → materiais com quiz, como **rascunhos**.
Exposto por CLI, `adk web` e A2A.

## Regras
- Pipeline em `package.run_pipeline`; etapas em `ingest.py`, `trail.py`, `materials.py`.
  Etapas de checagem/validação são **código, sem LLM**: mantenha assim.
- Nada é aprovado aqui. A exportação (`export_package`) grava em outro projeto e **não** pode virar
  tool do agente: é decisão humana.
- O formato de `kb/*.md`, `roles/*.yaml` e `catalog.db` precisa continuar compatível com o
  onboarding-agent (`schemas.py`, `storage.py` e `quiz_bank.py` são cópias de lá).
- A linha de título `# ...` dos `.md` gerados carrega o comentário de origem; não coloque texto
  solto antes da primeira seção `##` (viraria uma seção citável).
- Prompts em `prompts.py`, em pt-BR. Toda mudança neles: rode a importação do
  `examples/manual-qa.pdf` e compare o relatório.

## Comandos
`make test` · `make sample` · `scripts/import_pdf.py` · `scripts/export_package.py` · `make web` · `make a2a`
