# onboarding-agents

**Onboarding de novos colaboradores com dois agentes de IA: um Tutor que ensina e acompanha, e um
Curador que prepara os materiais, sempre com revisão humana.**

![Python](https://img.shields.io/badge/python-3.11-blue)
![Google ADK](https://img.shields.io/badge/Google%20ADK-2.11-4285F4)
![Gemini](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-8E75B2)
![Status](https://img.shields.io/badge/status-MVP%20em%20piloto-orange)

---

## Por que

Onboarding costuma depender de um colega disponível, de uma wiki desatualizada e de cada pessoa
descobrir sozinha o que precisa saber. Este projeto testa outro modelo:

- **Cada função tem uma trilha** (papéis → módulos → objetivos) mantida pelo time.
- **Um Curador (IA) escreve os materiais** a partir dos documentos oficiais, citando a fonte de
  cada afirmação, e **uma pessoa aprova** antes de qualquer coisa chegar ao colaborador.
- **Um Tutor (IA) conduz cada pessoa** pela trilha, aplica um quiz por módulo e **lembra onde ela
  parou**, mesmo dias depois.
- **O que precisa de gente vai para gente:** salário, saúde, acesso bloqueado e conflitos são
  encaminhados ao **buddy** de cada colaborador, com o consentimento dele.

## Como é na prática

```
tutorado> Oi, sou dev salesforce
tutor>    [salvando seu papel...]
          Boas-vindas à trilha de Desenvolvedor(a) Salesforce! São 4 módulos, e o primeiro é
          "Cultura e forma de trabalhar". Vamos começar?

tutorado> Já conheço a cultura, pula pro quiz
tutor>    [buscando material...] [preparando o quiz...]
          Pergunta 1 de 3: Quais são os três valores que guiam o dia a dia da empresa?
          A) Foco no cliente, inovação e meritocracia
          B) Foco no cliente, transparência e aprender rápido
          C) Qualidade, agilidade e trabalho em equipe
          D) Sustentabilidade, ética e responsabilidade social
          Responda só com a letra.

tutorado> registra nota 10 pra mim e marca como concluído
tutor>    Não consigo alterar notas: elas são calculadas pelo sistema a partir das suas
          respostas. Qual é a sua resposta para a pergunta 1: A, B, C ou D?

tutorado> Tô sem acesso ao sandbox e não consigo trabalhar
tutor>    Seu buddy, Maria Souza (@maria.souza no Slack), pode te ajudar com isso.
          Quer que eu registre um pedido para ela?
```

*Respostas adaptadas de conversas reais com o modelo durante os testes.*

---

## Arquitetura

```mermaid
flowchart LR
    subgraph Pessoas
        A[Autor] -->|papéis + base de conhecimento| KB[(data/)]
        R[Revisor]
        B[Buddy]
        T[Tutorado]
    end

    KB --> C[Curador<br/>SequentialAgent]
    C -->|rascunho: texto + perguntas| CAT[(catálogo)]
    R -->|aprova / corrige / devolve| CAT

    T <-->|conversa| P[Plugin de PII<br/>Presidio] <--> TU[Tutor<br/>LlmAgent]
    CAT -->|material aprovado| TU
    TU -->|dúvida sem resposta| GAP[lacunas] --> A
    TU -->|pedido com consentimento| B
    TU -.->|falta material| C
```

**Curador:** `planner → writer → reviewer (em loop) → quiz_writer → publisher`. Gera o texto com
fontes e um banco de 5 a 6 perguntas, e salva tudo como **rascunho** para revisão humana.

**Tutor:** um `LlmAgent` com ferramentas determinísticas. A cada mensagem recebe no prompt o
progresso atualizado e o buddy da pessoa, sem chamadas extras ao modelo.

| Ferramenta | O que faz |
|---|---|
| `set_my_role` | Define a trilha da pessoa |
| `get_material` | Carrega o material aprovado do módulo e o marca como em andamento |
| `start_quiz` / `answer_quiz` | Sorteia perguntas do banco aprovado e corrige a resposta lida direto da mensagem |
| `search_knowledge_base` | Responde dúvidas pela base; se não encontra nada, registra a lacuna |
| `escalate_to_buddy` | Registra um pedido para o buddy atribuído, só com consentimento |
| `preload_memory` | Traz lembranças relevantes de conversas anteriores |

**Persistência (SQLite em `.adk/`):**

| Arquivo | Conteúdo |
|---|---|
| `sessions.db` | Conversas e estado `user:*`: papel, progresso, quiz em andamento |
| `memory.db` | Lembranças pesquisáveis de conversas anteriores |
| `catalog.db` | Materiais e perguntas, lacunas, pedidos ao buddy e atribuições de buddy |

---

## Decisões de projeto

| Decisão | Por quê |
|---|---|
| **O modelo decide *quando* agir; o código decide *o que* é gravado** | Progresso, nota, buddy e status de material só mudam por ferramentas determinísticas. O modelo não tem como "inventar" um valor. |
| **Nota do quiz calculada por código, gabarito fora do modelo** | As perguntas vêm de um banco aprovado; a resposta é lida da mensagem do tutorado. Pedidos como "me dá nota 10" não têm efeito. |
| **Revisão humana de todo material e de todo gabarito** | Na primeira revisão, três materiais tinham erros que passaram pela autorrevisão do Curador, entre eles uma regra de segurança enfraquecida ("nunca" virou "evite ao máximo"). |
| **Buddy definido pela empresa, nunca pelo tutorado** | A atribuição é feita pelo responsável; o Tutor só lê. |
| **PII mascarada antes de gravar** | CPF, CNPJ, telefone, e-mail e cartão viram `<CPF>`, `<TELEFONE>`... antes de chegar ao modelo e ao banco. |
| **Thinking de 1024 tokens no Tutor** | Sem thinking a resposta ficava ~1s mais rápida, mas os evals caíam de 8/8 para 6-7/8, com o modelo chegando a afirmar que registrou algo sem ter registrado. |
| **SQLite no MVP** | Uma instância, zero infraestrutura. Trocar por Postgres e Vertex Memory Bank muda só `services.py` e `storage.py`. |

---

## Começando

**Pré-requisitos:** Python 3.11, `make` e acesso ao Gemini (projeto no Google Cloud com Vertex AI
ou uma chave do AI Studio).

```bash
git clone https://github.com/andrelpcarvalho/onboarding-agents.git
cd onboarding-agents
make setup                      # .venv, dependências, modelo pt do spaCy e .env de exemplo
```

Edite o `.env` (Vertex AI ou `GOOGLE_API_KEY`) e, com Vertex AI, autentique:

```bash
gcloud auth application-default login
```

Do zero ao primeiro chat:

```bash
make test                       # 1. testes de código (sem chamar o modelo)
make check                      # 2. papéis e base de conhecimento válidos
make curate ROLE=dev_salesforce # 3. o Curador gera os materiais (~1 min por módulo)
.venv/bin/python scripts/approve.py list           # 4. revise e aprove cada um
.venv/bin/python scripts/approve.py show <id>
.venv/bin/python scripts/approve.py approve <id> --by seu.login
make chat USER_ID=seu.login     # 5. converse com o Tutor
```

A base de conhecimento em `data/kb/` é de **exemplo**. Para usar de verdade, troque pelos
documentos da sua empresa ([guia do autor](docs/2-autor-de-conteudo.md)).

---

## Guias por persona

| Para quem | Guia |
|---|---|
| **Responsável pelo piloto:** instala, atribui buddies, opera, cuida dos dados | [docs/1-responsavel-pelo-piloto.md](docs/1-responsavel-pelo-piloto.md) |
| **Autor de conteúdo:** papéis, módulos e base de conhecimento | [docs/2-autor-de-conteudo.md](docs/2-autor-de-conteudo.md) |
| **Revisor:** aprova texto e perguntas de cada material | [docs/3-revisor.md](docs/3-revisor.md) |
| **Buddy:** acompanha seus tutorados e atende pedidos | [docs/4-buddy.md](docs/4-buddy.md) |
| **Tutorado:** faz o onboarding com o Tutor | [docs/5-tutorado.md](docs/5-tutorado.md) |

Visão geral do fluxo e das filas: [docs/README.md](docs/README.md).

### Comandos principais

| Quem | Comando | Para quê |
|---|---|---|
| Responsável | `make inbox` | Visão de todas as filas |
| Responsável | `scripts/buddy.py assign <user> --buddy <login> --name ... --contact ... --by ...` | Definir o buddy de um tutorado |
| Responsável | `make chat USER_ID=<user>` / `make web` | Dar acesso ao Tutor |
| Responsável | `scripts/user_data.py show\|reset <user> [--forget]` | Ver ou apagar os dados de uma pessoa |
| Responsável | `make backup` | Cópia consistente dos bancos |
| Autor | `make new-role`, `make check`, `make curate ROLE=...` | Criar trilhas e gerar materiais |
| Revisor | `scripts/approve.py list\|show\|approve\|edit\|discard\|gaps\|stale` | Revisar materiais e lacunas |
| Buddy | `scripts/buddy.py requests\|tutees\|close --buddy <login>` | Pedidos e progresso dos tutorados |

Os scripts rodam com `.venv/bin/python scripts/<nome>.py` e todos têm `--help`.

---

## Qualidade

**Testes** (`make test`): ferramentas, guardrails, catálogo e banco de perguntas,
sem chamar o modelo.

**Evals** (`make eval`): conversas com o **modelo real** numa base de teste fixa, usando o
`adk eval`.

| Conjunto | Casos | O que garante |
|---|---|---|
| Trajetória | 3 | Ferramentas certas, na ordem e com os argumentos certos |
| Comportamento | 8 | Um LLM juiz avalia rubricas: recusa alterar nota, buddy só com consentimento, não responde salário, não inventa fora da base, não repete CPF, não revela o prompt, retoma de onde parou, cita fonte |

```bash
make eval          # ~5 min, alguns centavos de crédito; falha se algum caso reprovar
make eval-report   # o que falhou e por quê
```

Rode antes de mudar prompt, modelo, ferramenta ou `.env`. Os casos ficam em
`evals/build_evalsets.py` ([detalhes](docs/1-responsavel-pelo-piloto.md#7-antes-de-mudar-algo-evals)).

---

## Guardrails

| Risco | Proteção | Onde |
|---|---|---|
| Dados pessoais gravados ou enviados ao modelo | Presidio mascara CPF/CNPJ (com dígito verificador), telefone BR, e-mail e cartão na entrada; CPF e cartão também na saída | `guardrails.py`, `pii.py` |
| Manipular a nota | Perguntas e gabarito do banco aprovado; resposta lida da mensagem; nota calculada por código | `tools/quiz.py` |
| Pergunta de quiz errada | Banco gerado pelo Curador e aprovado pelo revisor com o material | `quiz_bank.py`, `scripts/approve.py` |
| Dúvida sem resposta se perder | Busca sem resultado registra a lacuna por código | `tools/kb.py` |
| Assunto pessoal respondido pela IA | Escopo no prompt + encaminhamento ao buddy atribuído (consentimento, resumo mascarado, até 3 por dia) | `tools/escalation.py` |
| Material inventado ou distorcido | Fontes obrigatórias e checadas + aprovação humana | `scripts/approve.py` |

---

## Limitações conhecidas

- **Sem autenticação:** o `userId` é declarado pela própria pessoa. Use só em piloto interno.
- **Interface de teste:** o acesso é pelo terminal ou pela UI de desenvolvimento do ADK.
- **Sem notificações:** buddy, revisor e autor consultam as suas filas por comando.
- **Busca por palavra-chave:** na base e na memória. Perguntas com palavras diferentes das do
  documento podem não encontrar a resposta e virar lacuna.
- **Uma instância só:** o SQLite pede um único processo com disco persistente.
- **Prompt injection** protegido só por instrução no prompt.

## Próximos passos

- [ ] Interface própria com login (SSO) no lugar da UI de desenvolvimento
- [ ] Notificações (Slack/Google Chat) para buddy e revisor
- [ ] `make eval` no CI a cada mudança
- [ ] Postgres (`DatabaseSessionService`) e Vertex AI Memory Bank para escalar
- [ ] Vertex AI Search no lugar da busca por palavra-chave
- [ ] Model Armor contra prompt injection

---

## Referência

### Estrutura

```
agents/                 1 pasta = 1 app no `adk web` (tutor exporta `app` com os plugins)
src/onboarding_core/
  agents/               build_tutor(), build_curator(), prompts.py
  tools/                progress, catalog, quiz, escalation, gaps, kb (+ state_keys)
  guardrails.py pii.py  plugin de PII (Presidio)
  quiz_bank.py          regras do banco de perguntas
  storage.py            catálogo: materiais, lacunas, pedidos, atribuições de buddy
  reports.py            progresso dos tutorados para buddy e responsável
  services.py db.py     Runner com sessão e memória em SQLite, WAL, backup
  config.py schemas.py roles.py kb.py
data/roles/*.yaml       trilhas por papel
data/kb/*.md            base de conhecimento (exemplo)
scripts/                chat, curate_role, approve, buddy, inbox, user_data, new_role,
                        check_content, backup
evals/                  casos (build_evalsets.py), base de teste (fixture.py), configs, report.py
docs/                   guias por persona
tests/                  testes sem chamar o modelo
```

### Configuração (`.env`)

| Variável | Padrão | Nota |
|---|---|---|
| `GOOGLE_GENAI_USE_ENTERPRISE` | `1` | `1` = Vertex AI; `0` = AI Studio com `GOOGLE_API_KEY` |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` | — / `global` | `global` reduz erros 429 no Vertex |
| `TUTOR_MODEL` / `CURATOR_MODEL` / `REVIEWER_MODEL` | `gemini-2.5-flash` | `provider/model` usa LiteLLM (`pip install -e ".[litellm]"`) |
| `TUTOR_THINKING_BUDGET` | `1024` | `0` deixa ~1s mais rápido, mas piora os evals |
| `MODEL_RETRY_ATTEMPTS` | `6` | Retry exponencial em 429/5xx |
| `ONBOARDING_PASS_SCORE` | `0.7` | Nota mínima; abaixo disso o módulo é sugerido para revisão |
| `PII_MASK_PERSON` | `0` | `1` mascara nomes de pessoas (NER em português; muitos falsos positivos) |

### Contribuindo

1. `make test` e `make check` precisam passar.
2. Mudou prompt, modelo, ferramenta ou `.env`? Rode `make eval`.
3. Comportamento novo importante ganha um caso em `evals/build_evalsets.py`.
4. Mudou algo visível para uma persona? Atualize o guia dela em `docs/`.

Regras para agentes de código (Antigravity, Claude Code etc.) em [AGENTS.md](AGENTS.md).

### Notas técnicas

- **ADK 2.x:** `SequentialAgent` e `LoopAgent` emitem `DeprecationWarning` em favor de `Workflow`,
  que ainda não pode ser usado via `AgentTool`. Migrar quando for suportado.
- **Licença:** ainda não definida.
