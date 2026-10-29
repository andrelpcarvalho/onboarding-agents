# Guia do revisor: revisar e aprovar os materiais

> **Em resumo:** o Curador escreve; **você decide o que chega ao tutorado**. Para cada material,
> você confere o texto e o banco de perguntas contra a base de conhecimento e então aprova, corrige
> ou devolve com instruções. Você também faz a triagem das lacunas.

Cada material tem duas partes, aprovadas juntas:

1. **O conteúdo** de um módulo, escrito a partir da base de conhecimento (`data/kb/`), com a fonte
   de cada afirmação no formato `[arquivo.md#Seção]`.
2. **O banco de perguntas** do quiz: 5 a 6 perguntas de múltipla escolha, das quais o Tutor sorteia
   3 a cada tentativa. **A nota do tutorado depende do gabarito que você aprovar.**

**Sumário:**
[1. Ciclo de vida](#1-ciclo-de-vida-de-um-material) ·
[2. Passo a passo](#2-passo-a-passo) ·
[3. O que procurar](#3-o-que-procurar-checklist) ·
[4. Decidir](#4-decidir) ·
[5. Lacunas](#5-lacunas) ·
[6. Documento da base alterado](#6-documento-da-base-alterado) ·
[7. Referência rápida](#7-referência-rápida)

---

## 1. Ciclo de vida de um material

```
            make curate                approve                      nova versão aprovada
  (nada) ─────────────▶ RASCUNHO ───────────────▶ APROVADO ─────────────────────▶ FORA DE USO
                          │  ▲                                     stale <doc>          ▲
                    edit  │  │ nova versão (v+1)                                         │
                          ▼  │                                                           │
                       RASCUNHO v+1                                                      │
                          │                                                              │
                          └──────── discard (com motivo) ────────────────────────────────┘
```

| Status | O tutorado vê? |
|---|---|
| **rascunho** | **Não.** Só a versão aprovada chega ao tutorado; sem ela, o Tutor diz que o módulo ainda não foi aprovado |
| **APROVADO** | Sim. Só existe uma aprovada por módulo; aprovar uma nova tira a anterior de uso. |
| **fora de uso** | Não. Fica no histórico, com quem descartou e por quê. |

Nada é apagado: `list --all` mostra todas as versões, quem aprovou e as notas de edição.

---

## 2. Passo a passo

Todos os comandos rodam na pasta do projeto.

### 2.1 Veja o que está pendente

```bash
.venv/bin/python scripts/approve.py list          # rascunhos pendentes
.venv/bin/python scripts/approve.py list --all    # histórico completo
```

```
#9    rascunho    dev_salesforce/pipeline_deploy v3  Pipeline de deploy Salesforce
```

O número após `#` é o **id** usado nos outros comandos.

### 2.2 Leia o material

```bash
.venv/bin/python scripts/approve.py show 9
```

A saída tem três partes:

**1. O texto**, com as fontes entre colchetes.

**2. A checagem das fontes:**

```
Fontes citadas:
  ✓  pipeline_deploy.md#GMUD
  ✗ NÃO EXISTE NA BASE  pipeline_deploy.md#Aprovação de mudança
```

Uma fonte com **✗** foi inventada ou citada errado, e bloqueia o `approve`.

**3. O banco de perguntas**, com a correta marcada:

```
Banco de perguntas (6; o quiz sorteia 3)  ✓

  5. Em caso de problema crítico em produção, qual workflow reimplanta a última release estável?
     A) O workflow `ci-validate` é executado novamente.
     B) O workflow `deploy-prd` é acionado para uma nova implantação.
     C) O workflow `rollback-prd` é acionado.  <- correta
     D) O workflow `gmud-gate` bloqueia o acesso à produção.
     por quê: ... [pipeline_deploy.md#Deploy em produção e rollback]
```

Um banco inválido (menos de 4 perguntas, alternativas repetidas, gabarito fora de A–D) também
bloqueia o `approve`.

### 2.3 Compare com a base

Abra ao lado o documento citado em `data/kb/` e use o checklist da seção 3. A checagem automática
só garante que a fonte **existe**; se o texto diz o que a fonte diz, só você confere.

---

## 3. O que procurar (checklist)

### Conteúdo

| # | Critério | Como verificar | Se falhar |
|---|---|---|---|
| 1 | **Fiel às fontes** | Cada processo, prazo, ferramenta ou canal bate com a seção citada | Editar |
| 2 | **Regras com a mesma força** | "Nunca" continua "nunca", "obrigatório" continua "obrigatório", e o escopo não encolheu nem cresceu | Editar |
| 3 | **Nada inventado** | Nomes, números, prazos, URLs, siglas ou "detalhes úteis" que não estão na base | Editar (remover) |
| 4 | **Cobre os objetivos** | Compare com `objectives` do módulo em `data/roles/<papel>.yaml` | Descartar com feedback |
| 5 | **Claro para quem chegou ontem** | Siglas explicadas, frases curtas, exemplos | Editar ou descartar |
| 6 | **Tom e tamanho** | Acolhedor e objetivo; leitura de 10 a 20 minutos | Descartar com feedback |
| 7 | **Nada sensível** | Sem dados de clientes, senhas, salários ou nomes de pessoas | Editar (remover) |
| 8 | **Fontes ✓** | Nenhuma ✗ | Editar ou descartar |

### Banco de perguntas

| # | Critério | Como verificar | Se falhar |
|---|---|---|---|
| 9 | **Gabarito certo** | A alternativa marcada bate com a base e **nenhuma outra** também está certa | Editar |
| 10 | **Fiel à base** | Enunciado e explicação não pressupõem nada que a base não diz | Editar |
| 11 | **Pergunta o que importa** | Testa os objetivos do módulo, sem pegadinhas ou detalhes irrelevantes | Editar ou descartar |
| 12 | **Distratores plausíveis** | Alternativas erradas são erros comuns, não absurdos óbvios, e não ensinam algo errado | Editar |

### Erros reais encontrados na primeira revisão

Os três passaram pela checagem automática e pela autorrevisão do Curador:

| Material | O que estava escrito | O que a base diz | Critério |
|---|---|---|---|
| Segurança | Dados de clientes: "**evite ao máximo**" compartilhar em "canais **abertos** como o Slack" | **Nunca** compartilhar em canais do Slack (qualquer um) | 2 (a regra ficou fraca e com escopo menor) |
| Pipeline de deploy | O aviso de rebase vem "após o deploy de **rollback**", e as branches "sincronizam com a versão corrigida da `main`" | O aviso vem depois do deploy em **produção**; a base não fala em sincronizar com a `main` | 1 e 3 (fato trocado + detalhe inventado) |
| Acessos | Pergunta: "prazo de 1 dia útil **após a aprovação** do gestor"; "editor **recomendado**" | Diz só "prazo médio de 1 dia útil" e "instale o VS Code" | 10 (a pergunta cobra uma inferência) |

> Se o erro vem da **base** (informação errada ou faltando), corrija a base com o
> [autor](2-autor-de-conteudo.md). Corrigir só o material faz o problema voltar na próxima geração.

---

## 4. Decidir

### A) Está bom: aprove

```bash
.venv/bin/python scripts/approve.py approve 9 --by seu.login
```

O Tutor passa a usar essa versão **na próxima mensagem**, sem reiniciar nada.

### B) Ajuste pontual: edite

```bash
.venv/bin/python scripts/approve.py edit 9 --by seu.login
```

O editor (padrão `nano`; para outro, `export EDITOR="code -w"` ou similar, que espere você fechar
o arquivo) abre o texto e, no fim, o banco de perguntas em YAML:

```yaml
- question: Qual workflow reimplanta a última release estável?
  options:
  - O workflow `ci-validate` é executado novamente.
  - O workflow `deploy-prd` é acionado para uma nova implantação.
  - O workflow `rollback-prd` é acionado.
  - O workflow `gmud-gate` bloqueia o acesso à produção.
  correct_option: 2        # 0=A, 1=B, 2=C, 3=D
  explanation: ...
```

- Não apague a linha `<!-- QUIZ ... -->` que separa as duas partes.
- Salve e feche. O resultado vira um **novo rascunho** (v+1), com a nota "editado por seu.login a
  partir da vN". Revise com `show` e aprove o novo id.
- Se você editou um **rascunho**, ele sai de uso. Se editou um material **aprovado**, ele continua
  publicado até você aprovar a nova versão.
- Se o banco ficar inválido, nada é salvo, e o comando diz onde está a sua edição para recuperar.
- Fatos novos que você incluir também precisam existir na base.

### C) Problema de estrutura, tom ou cobertura: descarte e regenere

```bash
.venv/bin/python scripts/approve.py discard 9 --by seu.login \
    --reason "explicar quem aprova a GMUD; tom menos técnico; no máximo 5 parágrafos"
```

O comando mostra como regenerar levando o motivo em conta:

```bash
.venv/bin/python scripts/curate_role.py dev_salesforce --module pipeline_deploy \
    --feedback "explicar quem aprova a GMUD; tom menos técnico; no máximo 5 parágrafos"
```

Escreva o feedback como **instruções** ("incluir X", "remover Y", "no máximo N"), não como
avaliação ("ficou ruim").

### Trilha pronta

Quando `list --all` mostra uma linha **APROVADO** para cada módulo do papel. Avise o responsável
pelo piloto.

---

## 5. Lacunas

Quando o Tutor não encontra resposta na base para uma pergunta do tutorado, a pergunta vira uma
**lacuna**, registrada automaticamente e já sem dados pessoais.

```bash
make gaps
```

```
#7    [dev_salesforce/pipeline_deploy] Quem aprova a GMUD em feriados?
```

| Situação | Ação |
|---|---|
| A resposta deveria estar na base | Autor escreve a seção; regenere o módulo com `--feedback "responder: <pergunta>"`; depois `resolve-gap 7` |
| A resposta **já está** na base, com outras palavras | A busca é por palavra-chave: peça ao autor para incluir o termo usado pelo tutorado no documento; depois `resolve-gap 7` |
| Já coberta por uma versão nova do material | `scripts/approve.py resolve-gap 7` |
| Fora do escopo (pessoal, RH) | `resolve-gap 7`. Assuntos pessoais são do [buddy](4-buddy.md). |

Várias lacunas no mesmo módulo indicam um buraco no material.

---

## 6. Documento da base alterado

```bash
.venv/bin/python scripts/approve.py stale pipeline_deploy.md       # tira de uso o que cita o doc
.venv/bin/python scripts/curate_role.py dev_salesforce --missing-only
```

Os aprovados que citam o documento saem de uso. Até haver nova aprovação, o módulo fica
**indisponível** para o tutorado: aprove a nova versão o quanto antes.

---

## 7. Referência rápida

| Quero... | `.venv/bin/python scripts/approve.py ...` |
|---|---|
| Ver pendentes / tudo | `list` / `list --all` |
| Ler, checar fontes e ver o banco | `show <id>` |
| Publicar | `approve <id> --by <login>` |
| Corrigir texto ou perguntas | `edit <id> --by <login>` |
| Rejeitar | `discard <id> --by <login> --reason "<o que mudar>"` |
| Regenerar com feedback | `scripts/curate_role.py <papel> --module <módulo> --feedback "<...>"` |
| Lacunas / fechar | `gaps` / `resolve-gap <id>` |
| Documento alterado | `stale <arquivo.md>` |
