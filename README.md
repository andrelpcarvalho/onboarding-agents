# onboarding-agents

Onboarding de novos colaboradores com dois agentes **Google ADK** (Python 3.11 + Gemini):

| Agente | O que faz |
|---|---|
| **Tutor** | Conduz cada colaborador pela trilha do seu papel: ensina em blocos curtos, aplica quiz, lembra onde a pessoa parou e encaminha ao buddy o que precisa de uma pessoa. |
| **Curador** | Gera o material de cada módulo a partir da base de conhecimento oficial, com fontes, revisão automática e aprovação humana. |

## Guias por persona

| Para quem | Guia |
|---|---|
| Responsável pelo piloto (instala, atribui buddies, opera, cuida dos dados) | [docs/1-responsavel-pelo-piloto.md](docs/1-responsavel-pelo-piloto.md) |
| Autor de conteúdo (papéis e base de conhecimento) | [docs/2-autor-de-conteudo.md](docs/2-autor-de-conteudo.md) |
| Revisor (aprova os materiais) | [docs/3-revisor.md](docs/3-revisor.md) |
| Buddy (acompanha tutorados e atende pedidos) | [docs/4-buddy.md](docs/4-buddy.md) |
| Tutorado (usuário final) | [docs/5-tutorado.md](docs/5-tutorado.md) |

Visão geral do fluxo e das filas: [docs/README.md](docs/README.md).

## Arquitetura

```
Tutorado ──▶ PiiRedactionPlugin ──▶ Tutor (LlmAgent, gemini-2.5-flash, thinking 1024)
              (Presidio)              │  instrução com progresso + buddy injetados a cada chamada
                                      ├─ tools: set_my_role · get_material · start_quiz/answer_quiz
                                      │         search_knowledge_base · log_gap · escalate_to_buddy
                                      ├─ preload_memory (lembranças de conversas anteriores)
                                      └─ AgentTool(Curador) quando falta material
Curador (SequentialAgent): planner → writer → LoopAgent(reviewer) → quiz_writer → publisher
                           → rascunho (conteúdo + banco de perguntas) → aprovação humana

Persistência (SQLite em .adk/):
  sessions.db  sessões + estado user:* (progresso, quiz)        SqliteSessionService
  memory.db    lembranças pesquisáveis                          SqliteMemoryService
  catalog.db   materiais, lacunas, pedidos ao buddy, atribuições
```

**Princípio:** o modelo decide *quando* agir; **o código decide o que é gravado**. Progresso, nota
do quiz, buddy e status de material só mudam por tools determinísticas.

## Setup rápido

```bash
make setup     # .venv (Python 3.11), dependências, modelo pt do spaCy, .env a partir do exemplo
# edite .env (Vertex AI ou GOOGLE_API_KEY) e rode: gcloud auth application-default login
make test
make check
```

## Comandos

| Quem | Comando | Para quê |
|---|---|---|
| Responsável | `make inbox` | Visão de todas as filas |
| Responsável | `scripts/buddy.py assign <user> --buddy <login> --name ... --contact ... --by ...` | Definir o buddy de um tutorado |
| Responsável | `scripts/user_data.py show\|reset <user> [--forget]` | Ver ou apagar dados de uma pessoa |
| Responsável | `make web` / `make chat USER_ID=<user>` | Dar acesso ao Tutor |
| Responsável | `make backup` | Cópia consistente dos bancos |
| Autor | `make new-role ID=... TITLE="..."`, `make check`, `make curate ROLE=...` | Criar trilhas e gerar materiais |
| Revisor | `scripts/approve.py list\|show\|approve\|edit\|discard\|gaps\|stale` | Revisar materiais e lacunas |
| Buddy | `scripts/buddy.py requests\|tutees\|close --buddy <login>` | Pedidos e progresso dos tutorados |

Scripts rodam com `.venv/bin/python scripts/<nome>.py`; todos têm `--help`.

## Evals

```bash
make eval          # trajetória (3 casos) + comportamento com LLM juiz (8 casos), modelo real
make eval-report   # o que falhou e por quê
```

Rode antes de mudar prompt, modelo, tools ou `.env`. Casos em `evals/build_evalsets.py`; detalhes
na seção 11 do [guia do responsável](docs/1-responsavel-pelo-piloto.md).

## Memória

1. **Progresso estruturado** no estado `user:*` da sessão: vale para todas as sessões do mesmo
   `userId` e só é gravado por tools.
2. **Lembranças** no `MemoryService`, salvas ao fim de cada resposta e recuperadas com
   `preload_memory`. No MVP a busca é por palavra-chave.

Detalhes na seção 7 do [guia do responsável](docs/1-responsavel-pelo-piloto.md).

## Guardrails

| Risco | Proteção | Onde |
|---|---|---|
| Dados pessoais gravados ou enviados ao modelo | Presidio mascara CPF/CNPJ (dígito verificador), telefone BR, e-mail e cartão na entrada; CPF e cartão também na saída | `guardrails.py`, `pii.py` |
| Manipular a nota | Perguntas e gabarito do banco aprovado (o modelo nunca vê o gabarito); resposta lida da mensagem; nota calculada por código | `tools/quiz.py` |
| Pergunta de quiz errada | Banco gerado pelo Curador e aprovado pelo revisor junto com o material | `quiz_bank.py`, `approve.py` |
| Dúvida sem resposta se perder | Busca do Tutor sem resultado registra a lacuna por código | `tools/kb.py` |
| Assunto pessoal respondido pelo modelo | Escopo no prompt + `escalate_to_buddy` (consentimento, resumo mascarado, 3/dia, vai para o buddy atribuído) | `tools/escalation.py` |
| Material inventado | Fontes obrigatórias e validadas + aprovação humana | `scripts/approve.py` |

**Fora do MVP:** autenticação (o `userId` não é verificado), Model Armor contra prompt injection
e checagem de fundamentação das respostas do chat.

## Estrutura

```
agents/                 1 pasta = 1 app no `adk web` (tutor exporta `app` com os plugins)
src/onboarding_core/
  agents/               build_tutor(), build_curator(), prompts.py
  tools/                progress, catalog, quiz, escalation, gaps, kb (+ state_keys)
  guardrails.py pii.py  plugin de PII (Presidio)
  storage.py            catálogo: materiais, lacunas, pedidos, atribuições de buddy
  reports.py            progresso dos tutorados para buddy e responsável
  services.py db.py     Runner com sessão/memória SQLite, WAL, backup
  config.py schemas.py roles.py kb.py
data/roles/*.yaml       trilhas por papel
data/kb/*.md            base de conhecimento (EXEMPLOS: trocar pelos docs reais)
scripts/                chat, curate_role, approve, buddy, inbox, user_data, new_role,
                        check_content, backup
evals/                  casos de eval (build_evalsets.py), base fixa (fixture.py), configs, report.py
docs/                   guias por persona
tests/                  testes das tools, guardrails e catálogo (sem chamar o LLM)
```

## Configuração (`.env`)

| Variável | Padrão | Nota |
|---|---|---|
| `TUTOR_MODEL` / `CURATOR_MODEL` / `REVIEWER_MODEL` | `gemini-2.5-flash` | `provider/model` usa LiteLLM (`pip install -e ".[litellm]"`) |
| `TUTOR_THINKING_BUDGET` | `1024` | Com `0` fica ~1s mais rápido, mas os evals caem de 8/8 para 6-7/8 |
| `MODEL_RETRY_ATTEMPTS` | `6` | Retry exponencial em 429/5xx |
| `GOOGLE_CLOUD_LOCATION` | `global` | Reduz erros 429 no Vertex |
| `ONBOARDING_PASS_SCORE` | `0.7` | Nota mínima; abaixo disso o módulo entra em revisão |
| `PII_MASK_PERSON` | `0` | `1` mascara nomes (NER pt; muitos falsos positivos) |

## Evolução para produção

Sessão em `DatabaseSessionService` (Postgres), memória no `VertexAiMemoryBankService`, base no
Vertex AI Search, UI própria com login (SSO) no lugar da `dev-ui`, notificações (Slack/Chat),
Model Armor e evals rodando no CI. Os agentes não mudam: trocam-se `services.py` e `storage.py`.

> **ADK 2.x:** `SequentialAgent`/`LoopAgent` emitem DeprecationWarning em favor de `Workflow`,
> que ainda não pode ser usado via `AgentTool`. Migrar quando for suportado.
