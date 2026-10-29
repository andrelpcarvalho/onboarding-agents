# Guia do autor de conteúdo: criar trilhas e a base de conhecimento

> **Em resumo:** você define **o que** cada função precisa aprender (papéis e módulos) e escreve
> os **documentos oficiais** de onde o Curador tira os materiais e as perguntas do quiz. Não
> precisa programar: você edita arquivos de texto e roda comandos prontos.

**Sumário:**
[1. Conceitos](#1-conceitos) ·
[2. Escrever a base](#2-escrever-a-base-de-conhecimento) ·
[3. Papel novo do zero](#3-passo-a-passo-um-papel-novo-do-zero) ·
[4. Manutenção](#4-manutenção) ·
[5. Checklist](#5-checklist-de-entrega)

Todos os comandos rodam na pasta do projeto, já instalado pelo [responsável](1-responsavel-pelo-piloto.md).

---

## 1. Conceitos

```
 VOCÊ                                     CURADOR (agente)          REVISOR          TUTOR
 data/kb/*.md ──────── fatos ──────────▶  gera material +     ───▶  aprova    ───▶  ensina e
 data/roles/<papel>.yaml ── trilha ────▶  banco de perguntas        ou devolve      aplica quiz
```

| Conceito | O que é | Exemplo |
|---|---|---|
| **Base de conhecimento** | Documentos oficiais em Markdown. **Única fonte de verdade**: o Curador e o Tutor só afirmam o que está aqui. | `data/kb/pipeline_deploy.md` |
| **Seção** | Cada título `## ...` de um documento. É o que o material cita como fonte. | `pipeline_deploy.md#GMUD` |
| **Papel** | Uma trilha de onboarding para uma função | Desenvolvedor(a) Salesforce |
| **Módulo** | Um tema da trilha, de 20 a 45 minutos | Pipeline de deploy |
| **Objetivo** | O que a pessoa deve saber ao final; orienta o material e as perguntas | "Saber o que é a GMUD e quando ela é exigida" |
| **Banco de perguntas** | 5 a 6 perguntas de múltipla escolha que o Curador gera para cada material e o revisor aprova; o quiz sorteia 3 | "Qual workflow bloqueia o deploy sem GMUD aprovada?" |
| **kb_tags** | Palavras que o Curador usa para buscar na base ao montar um módulo | `[deploy, gmud, rollback]` |

> **Regra de ouro:** se não está na base, não estará no material. E se a base é **ambígua**, o
> material pode sair errado. A maioria dos problemas de material nasce na base.

---

## 2. Escrever a base de conhecimento

Um arquivo `.md` por assunto em `data/kb/`:

```markdown
# Ferramentas de QA

## Ferramenta de testes automatizados
Usamos o Provar para testes de regressão. Os testes ficam no repositório qa-regression
e rodam toda noite contra o ambiente de UAT.

## Como reportar um bug
Bugs são abertos no Jira, projeto QA, com passos para reproduzir, ambiente e evidência
(print ou vídeo). Bug de severidade alta também deve ser avisado no canal #qa-urgente.
```

### Estrutura

- **Uma seção `##` por tópico**, com título descritivo. O título da seção pesa mais na busca e
  aparece como fonte para o tutorado. O nome do arquivo também conta; o título `#` do topo não.
- **Não duplique:** se o assunto já existe (cultura, segurança), aponte as `kb_tags` para ele.

### Clareza: escreva para não ser mal interpretado

| Regra | Evite | Prefira |
|---|---|---|
| **Diga a força da regra** | "Dados de clientes não devem ir para o Slack." | "Dados de clientes **nunca** podem ir para canais do Slack, de nenhum tipo." |
| **Um fato por frase, com o sujeito explícito** | "Se houver problema, o rollback reimplanta. Depois do deploy, as branches recebem aviso." (qual deploy?) | "Depois do deploy em produção, as branches abertas recebem aviso de rebase. Se houver problema, o rollback reimplanta a última release estável." |
| **Fatos concretos** | "Normalmente o acesso sai rápido." | "O prazo médio é de 1 dia útil após a abertura do chamado." |
| **Siglas por extenso na primeira vez** | "Toda ida para PRD exige GMUD." | "Toda ida para produção exige uma GMUD (gestão de mudança) aprovada." |

> O segundo exemplo da tabela é um caso real: essa frase ambígua levou o Curador a dizer que o
> aviso de rebase vinha do rollback. A base foi corrigida e o material também.

### Busca: use as palavras de quem pergunta

O Tutor procura respostas na base **por palavra-chave**, não por significado. Se o colaborador
pergunta "como peço acesso ao **Jira**?" e o documento só diz "ferramenta de backlog", a busca não
encontra e a dúvida vira uma lacuna.

- Use os termos que as pessoas realmente usam, inclusive nomes de ferramentas e sinônimos comuns.
- Escreva a sigla e a forma por extenso ("GMUD (gestão de mudança)").
- Palavras muito genéricas ("empresa", "como", "qual") são ignoradas pela busca.

### Nada sensível

Sem senhas, dados de clientes ou salários. Prefira cargos e canais a nomes de pessoas, que mudam.
Contatos oficiais de times (o e-mail ou o telefone de um helpdesk) podem ficar.

---

## 3. Passo a passo: um papel novo do zero

### Passo 1: documentos da base

Escreva ou revise os documentos dos assuntos da trilha (seção 2).

### Passo 2: arquivo do papel

```bash
make new-role ID=analista_qa TITLE="Analista de QA"
make new-role ID=analista_qa TITLE="Analista de QA" FROM=analista_negocios   # copia os módulos
```

Abra `data/roles/analista_qa.yaml` e preencha tudo que estiver marcado com `TODO`:

```yaml
id: analista_qa
title: Analista de QA
description: >-
  Garante a qualidade das entregas com testes manuais e automatizados.
buddy_contact: "#onboarding-qa no Slack"

modules:
  - id: cultura_empresa
    title: Cultura e forma de trabalhar
    objectives:
      - Conhecer os valores da empresa e como aparecem no dia a dia
      - Conhecer os rituais do time
    kb_tags: [cultura, valores, rituais]
    prerequisites: []
    estimated_minutes: 20

  - id: ferramentas_qa
    title: Ferramentas de QA
    objectives:
      - Saber qual ferramenta usamos para regressão e quando ela roda
      - Saber como reportar um bug e o que fazer com severidade alta
    kb_tags: [provar, testes, bug, jira, severidade]
    prerequisites: [cultura_empresa]
    estimated_minutes: 30
```

| Campo | Dica |
|---|---|
| `id` (papel e módulo) | Minúsculo, sem acento e sem espaço; o do papel é igual ao nome do arquivo. **Não renomeie depois que alguém começou**: o progresso está ligado a ele. |
| `description` | Uma frase. O Tutor mostra quando a pessoa escolhe o papel. |
| `buddy_contact` | **Canal geral** de apoio do papel, usado enquanto o tutorado não tem buddy individual (atribuído pelo responsável). |
| `objectives` | 2 a 3 por módulo, com verbo verificável ("Saber...", "Identificar..."). Objetivos vagos geram material e perguntas vagos. |
| `kb_tags` | Palavras que **aparecem nos documentos**: nome do arquivo, títulos ou texto. |
| `prerequisites` | Módulos que precisam vir antes; só pode citar módulos **acima** na lista. |

A ordem dos módulos é a ordem sugerida ao tutorado: do geral (cultura, acessos, segurança) ao
específico.

### Passo 3: valide

```bash
make check
```

```
  aviso: roles/analista_qa.yaml › ferramentas_qa: tags sem resultado na base: ['provar']
  ERRO:  roles/analista_qa.yaml › ferramentas_qa: pré-requisito 'acessos' não existe ou vem depois na lista
```

**ERRO** bloqueia. **aviso** não bloqueia, mas indica uma tag que não acha nada.

| Erro comum | Correção |
|---|---|
| `YAML inválido (indentação?)` | Use espaços, nunca TAB; itens de `modules:` começam com `  - ` |
| `ainda tem TODO para preencher` | Procure "TODO" no arquivo |
| `o nome do arquivo deve ser igual ao id` | Renomeie o arquivo ou ajuste o `id` |
| `kb_tags ... não encontram nada` | Escreva o documento (passo 1) ou use palavras que estão nele |
| `pré-requisito ... vem depois na lista` | Suba o módulo pré-requisito |

### Passo 4: gere os materiais

```bash
make curate ROLE=analista_qa
```

Para cada módulo, o Curador planeja um roteiro a partir dos objetivos e da base, redige com fontes,
revisa o texto sozinho (até 3 rodadas), cria o banco de perguntas e salva tudo como **rascunho**.
Leva cerca de 1 minuto por módulo.

```bash
.venv/bin/python scripts/curate_role.py analista_qa --module ferramentas_qa   # só um módulo
.venv/bin/python scripts/curate_role.py analista_qa --missing-only --pause 30  # retomar após erro 429
```

### Passo 5: entregue para revisão

Avise o revisor ([Guia do revisor](3-revisor.md)). Nada chega ao tutorado como "revisado" sem
aprovação humana. Depois de mudar papéis ou a base, peça ao responsável para reiniciar o
`make web` / `make chat`.

### Passo 6 (opcional): missões práticas

Missão = roteiro em homologação que o Tutor conduz (`data/missions/<id>.yaml`, exemplo em
`site_solar_proposta_acom.yaml`). Etapas têm checkpoints de três tipos: `confirm` (entendeu e
pode seguir), `describe` (descreveu a tela: `expected` lista palavras-chave) e `capture` (guarda
uma evidência com `pattern`). Todo checkpoint tem `ask`: a pergunta, em linguagem do colaborador, que
fecha a mensagem do Tutor (o sistema garante que ela apareça). `done_when` compara duas evidências capturadas. As explicações
citam seções da base (`explain: ["arquivo.md#Seção"]`), então o conteúdo fica em `data/kb/`.
Liste o id em `missions:` do papel, use `status: approved` só depois da revisão no PR e rode
`make check`. CPFs de teste vão em `data/homolog_data.yaml` (massa oficial de homologação).

---

## 4. Manutenção

**Um documento da base mudou**

```bash
.venv/bin/python scripts/approve.py stale ferramentas_qa.md         # tira de uso o que cita o doc
.venv/bin/python scripts/curate_role.py analista_qa --missing-only  # gera de novo
```

E peça nova revisão.

**Novo módulo num papel existente:** adicione no YAML, rode `make check` e gere só ele com
`--module`. Quem já fez a trilha passa a ver o módulo como pendente.

**Lacunas: perguntas que a base não respondeu**

```bash
make gaps
```

Cada lacuna é uma pergunta real de um tutorado. Ou falta uma seção (escreva-a e regenere o módulo
com `--feedback "responder: <pergunta>"`), ou a resposta existe com outras palavras (acrescente o
termo que o tutorado usou). Depois, peça ao revisor para fechar a lacuna.

**Mesmo módulo em vários papéis:** o material é gerado **por papel**; rode `make curate` para cada um.

**Escrever o material você mesmo:** gere com o Curador e reescreva com
`scripts/approve.py edit <id> --by <você>`; o texto e o banco de perguntas abrem juntos no editor.
A nova versão passa pela revisão normalmente.

---

## 5. Checklist de entrega

- [ ] Cada módulo tem 2 a 3 objetivos verificáveis
- [ ] Cada objetivo tem resposta em alguma seção da base
- [ ] Regras escritas com a força certa ("nunca", "sempre", "obrigatório")
- [ ] Nenhuma frase ambígua sobre **qual** processo, **quem** faz ou **quando**
- [ ] Nada sensível nos documentos
- [ ] `make check` termina com "tudo certo ✓"
- [ ] `scripts/approve.py list` mostra um rascunho para cada módulo
