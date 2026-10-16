# Do Google ADK ao LangGraph: o que mudou

Este projeto é o [onboarding-agents](../../onboarding-agents) reescrito em **LangGraph 1.2**, com o
mesmo comportamento: Tutor e Curador, progresso e memória persistentes, quiz com nota calculada por
código, encaminhamento ao buddy, mascaramento de PII, lacunas, revisão humana e evals.

> **Em resumo:** as regras de negócio (catálogo, banco de perguntas, PII, busca na base, papéis)
> foram **copiadas sem mudança**. O que foi reescrito é a camada de agentes: no ADK você **declara
> agentes** e o framework orquestra; no LangGraph você **desenha o grafo**, com nós, arestas e
> estado explícitos.

---

## 1. Mapa de conceitos

| Na versão ADK | Na versão LangGraph | Onde |
|---|---|---|
| `LlmAgent` (Tutor) | Nó `agent` num `StateGraph`, com `ChatGoogleGenerativeAI.bind_tools()` | `tutor/graph.py` |
| Ciclo modelo ⇄ tools implícito | Arestas explícitas: `agent → tools → agent`, rota condicional | `tutor/graph.py` |
| Quiz corrigido quando o modelo chama `answer_quiz` | Nó `quiz_gate` corrige **antes** do modelo, por código | `tutor/graph.py` |
| `SequentialAgent` + `LoopAgent` + `exit_loop` (Curador) | Nós em sequência + **aresta condicional** `review → review` com contador | `curator/graph.py` |
| `AgentTool(curador)` | Tool `ask_curator` que invoca o grafo do Curador | `tutor/graph.py` |
| `FunctionTool` + `ToolContext` | `@tool` + **`ToolRuntime`** (`state`, `store`, `context`), injetado e invisível ao modelo | `tools/tutor_tools.py` |
| Sessão (`SqliteSessionService`) | **Thread** + checkpointer (`SqliteSaver`) | `services.py` |
| Estado `user:*` (vale para todas as sessões) | **Store**, namespace `("profile", user)` | `profile.py` |
| `MemoryService` + `preload_memory` | Store `("memories", user)` + busca no nó `agent` | `memory.py` |
| `InstructionProvider` (prompt dinâmico) | O nó `agent` monta o `SystemMessage` a cada chamada | `tutor/graph.py` |
| `user_id` do Runner | `context_schema=TutorContext` → `runtime.context.user_id` | `tools/tutor_tools.py` |
| Plugin `on_user_message_callback` (PII antes de gravar) | Máscara **na fronteira** (`prepare_user_message`), antes do `invoke` | `guardrails.py` |
| Plugin `after_model_callback` (PII na saída) | Nó `guard_output` (substitui a mensagem pelo mesmo id) | `tutor/graph.py` |
| `output_schema` | `with_structured_output(Model)` | `curator/graph.py` |
| `RunConfig(streaming_mode=SSE)` | `graph.stream(..., stream_mode="messages")` | `services.py` |
| `retry_options` | `max_retries` do modelo | `config.py` |
| `adk web` | **LangGraph Studio** (`make studio`, via `langgraph.json`) | `studio.py` |
| `adk eval` | Harness próprio com os mesmos 11 casos (ou LangSmith, serviço externo) | `evals/run_evals.py` |

---

## 2. O que NÃO mudou (copiado sem alteração)

| Módulo | Função |
|---|---|
| `schemas.py`, `roles.py` | Modelos de domínio e papéis em YAML |
| `storage.py` | Catálogo: materiais, lacunas, pedidos, buddies. **Mesmo formato de banco**: dá para copiar o `catalog.db` entre as versões. |
| `quiz_bank.py` | Regras do banco de perguntas |
| `pii.py` | Presidio com CPF/CNPJ |
| `kb.py` | Base de conhecimento e busca |
| `scripts/approve.py`, `check_content.py`, `new_role.py` | Revisão humana e validação de conteúdo |

São ~790 linhas de regras de negócio reaproveitadas. A camada de agentes ficou do mesmo tamanho nas
duas versões (~900 linhas cada): o LangGraph pede mais código de orquestração, mas eliminou o
"publisher" (um agente LLM inteiro) e o callback do loop de revisão.

---

## 3. As duas maiores diferenças de desenho

### 3.1 Fluxo explícito em vez de agentes declarados

**Curador no ADK:** 5 `LlmAgent` encadeados. O planner buscava contexto **chamando tools**, e um
agente "publisher" existia só para **transcrever** o resultado para a tool de salvar.

**Curador no LangGraph:**

```
START → gather → plan → write → review ─┬─(aprovado ou 3 rodadas)→ quiz → publish → END
                                        └─(reprovado)→ review
```

- `gather` e `publish` são **nós de código**, sem LLM: buscar trechos e salvar o rascunho são
  determinísticos. Saem duas chamadas ao modelo por material, e some o risco de o publisher
  transcrever errado.
- O loop é uma aresta condicional com contador no estado, legível e testável sem modelo
  (`test_loop_de_revisao_tem_limite`).

### 3.2 Correção do quiz antes do modelo (`quiz_gate`)

```
START → quiz_gate → agent ─┬─(tool_calls)→ tools → agent
                           └─(resposta)──→ guard_output → remember → END
```

Na versão ADK, o quiz dependia de o modelo **lembrar** de chamar `answer_quiz` a cada resposta.
Os evals das duas versões pegaram o mesmo defeito: diante de "registra nota 10 pra mim", o modelo
recusava, mas não reapresentava a pergunta. No ADK, a correção foi aumentar o thinking e reforçar
o prompt.

No LangGraph, um nó de código, `quiz_gate`, roda **antes** do modelo: se há quiz em andamento, ele
corrige a mensagem (letra válida, pedido de nota, resposta ambígua) e grava o resultado no estado.
O modelo só comunica o que o código decidiu. É o tipo de garantia que um fluxo explícito permite e
um agente declarado não.

### 3.3 Onde mora cada tipo de memória

| Pergunta | ADK | LangGraph |
|---|---|---|
| "O que foi dito nesta conversa?" | Sessão | Thread (checkpointer) |
| "Em que ponto da trilha a pessoa está?" | Estado `user:*` da sessão | Store `("profile", user)` |
| "Do que conversamos semanas atrás?" | MemoryService | Store `("memories", user)` |

No LangGraph a separação **thread × usuário** é explícita: o checkpointer nunca guarda o progresso,
e o Store nunca guarda a conversa.

---

## 4. Melhorias aproveitadas na reescrita (não vêm do framework)

| Melhoria | Por quê |
|---|---|
| O revisor do Curador recebe os **trechos originais da base**, e não só o roteiro, e tem o critério "regras com a mesma força" | Na versão ADK, o revisor só comparava com o roteiro. É a causa provável de o "nunca" ter virado "evite ao máximo" sem ninguém notar. Na primeira geração desta versão, o material de segurança manteve "nunca" e "canais do Slack" (uma amostra, não uma prova). |
| `publish` extrai as fontes do texto e descarta citações inexistentes | Em vez de pedir ao modelo para listar as fontes |
| O rascunho guarda a nota quando a revisão automática não aprova | O revisor humano vê no `show` |

Valeria levar as duas primeiras para a versão ADK também.

---

## 5. Pegadinhas encontradas (todas corrigidas no código)

| Problema | Sintoma | Solução |
|---|---|---|
| `SqliteStore` precisa de conexão em **autocommit** | `cannot start a transaction within a transaction` | `sqlite3.connect(..., isolation_level=None)` |
| Namespace do Store **não aceita ponto** | `InvalidNamespaceError` com logins como `joao.silva` | Codificação reversível do user_id (`profile.user_ns`) |
| Com thinking ligado, o Gemini devolve o conteúdo como **lista de blocos** | Resposta aparecendo como `[{'type': 'text', ...}]`, chat sem texto e **CPF passando pela máscara de saída** | Usar `str(message.text)` em todo lugar |
| `message.text` é um `TextAccessor`, não `str` | O spaCy (Presidio) recusa o tipo | Converter com `str()` |
| O checkpoint grava a entrada **antes** de qualquer nó | Um nó de "mascarar entrada" deixaria o texto original no histórico | Mascarar na fronteira, antes do `invoke` |
| No LangGraph Studio a entrada não passa pela fronteira | PII chega sem máscara no Studio | Documentado; use o Studio só com dados de teste |

---

## 6. Resultados medidos

Mesmo modelo (`gemini-2.5-flash` via Vertex AI), mesma base, mesmo catálogo.

| Verificação | Resultado |
|---|---|
| Testes sem modelo | 16 passando |
| Conversa roteirizada (10 turnos + thread nova) | Mesmo comportamento da versão ADK: papel salvo, material antes do quiz, nota 10 recusada, nota 1/3 por código, buddy pelo nome só com consentimento, CPF recusado, lacuna registrada, progresso retomado numa thread nova |
| Curador, 1 módulo | 71s; a revisão reprovou na 1ª rodada (2 problemas), corrigiu e aprovou na 2ª |
| Evals (11 casos) | 1ª rodada: 10/11 (falhou "recusa manipular nota", o mesmo defeito que a versão ADK teve). Depois do `quiz_gate`: **11/11** (3/3 trajetória, 8/8 comportamento) |

**Latência:** turnos simples levaram 3 a 7s, como na versão ADK. Turnos de ~70s nos testes foram
espera de retry por cota do Vertex (erro 429), que também apareceu na versão ADK.

---

## 7. Quando escolher cada um

| Escolha o **ADK** se... | Escolha o **LangGraph** se... |
|---|---|
| Vai rodar no Google Cloud e quer Agent Engine, Memory Bank e Vertex nativos | Quer independência de provedor (Gemini, Claude, OpenAI via LangChain) |
| Prefere declarar agentes e deixar o framework orquestrar | Prefere controlar cada passo do fluxo e testar nós isoladamente |
| Quer `adk web` e `adk eval` prontos, sem serviços externos | Vai usar LangSmith para tracing e avaliação |
| Precisa de hooks antes da persistência (plugins) | Precisa de human-in-the-loop com pausa e retomada (`interrupt`) no meio do grafo |

**Próximo passo natural nesta versão:** usar `interrupt()` no Curador para pausar antes do
`publish` e retomar com a decisão do revisor (`Command(resume=...)`). O checkpointer guarda a pausa
pelo tempo que for preciso. Hoje a aprovação continua no catálogo, igual à versão ADK, para os dois
projetos seguirem compatíveis.
