# Guia do buddy: acompanhar seus tutorados e atender os pedidos do Tutor

> **Em resumo:** o Tutor cuida do conteúdo básico; **você cuida do que precisa de uma pessoa**.
> Uma vez por dia, veja seus pedidos (`requests`) e o progresso dos seus tutorados (`tutees`),
> fale com quem precisa pelo Slack ou pessoalmente e feche os pedidos atendidos (`close`).

Você é o colega de referência de um ou mais novos colaboradores: assuntos individuais, bloqueios e
acompanhamento de perto são com você.

---

## 1. Como você vira buddy de alguém

O responsável pelo piloto liga cada tutorado a um buddy usando o **seu login** (ex.:
`maria.souza`), o seu nome e o contato que o Tutor deve mostrar (ex.: "@maria.souza no Slack").
A partir daí:

- quando o tutorado precisa de ajuda humana, o Tutor diz **"seu buddy é a Maria Souza
  (@maria.souza no Slack)"**;
- os pedidos que o Tutor registrar para essa pessoa caem na **sua** fila;
- você consegue ver o progresso dela na trilha.

O tutorado não escolhe nem troca o buddy pelo Tutor. Se algo estiver errado (tutorado que não é
seu, contato desatualizado), fale com o responsável.

---

## 2. Como um pedido chega até você

```
 Tutorado: "tô sem acesso ao sandbox e não consigo trabalhar"
     │
     ▼
 Tutor: não resolve o assunto; diz "seu buddy é a Maria Souza (@maria.souza no Slack)"
        e PERGUNTA: "quer que eu registre um pedido para ela?"
     │   só se o tutorado disser "sim"
     ▼
 Pedido registrado na fila da maria.souza  ──▶  você consulta (sem notificação no MVP)
```

**Assuntos que viram pedido:** RH individual (salário, férias, desligamento), saúde, jurídico,
conflitos, acesso bloqueado e outros que precisem de uma pessoa.

**Não há notificação automática.** O Tutor sempre sugere ao tutorado que também te chame direto
no seu contato; o registro garante que o pedido não se perca. Combine com o responsável uma rotina
de consulta: **pelo menos uma vez por dia** durante o piloto.

---

## 3. Sua rotina

Os comandos rodam na pasta do projeto, **na máquina onde o Tutor está instalado**, com o seu
login no lugar de `maria.souza`.

> **Sem acesso a essa máquina?** No MVP isso é comum. Combine com o responsável pelo piloto: ele
> roda `requests` e `tutees` com o seu login e te envia o resultado diariamente, e você responde
> com o que fechar.

### 3.1 Ver os pedidos

```bash
.venv/bin/python scripts/buddy.py requests --buddy maria.souza
```

```
#12   URGENTE Acesso    joao.silva         10/10 09:40  Colaborador sem acesso ao sandbox, impedindo o trabalho.
#9    RH                ana.lima           09/10 16:05  Dúvida sobre férias no período de experiência.
```

| Campo | Significado |
|---|---|
| `#12` | Número do pedido, usado para fechá-lo |
| `URGENTE` | O tutorado está impedido de trabalhar ou há risco. Vem primeiro na lista; trate no mesmo dia. |
| Categoria | RH, Jurídico, Saúde, Conflito, Acesso ou Outro |
| Resumo | **Curto de propósito.** Dados pessoais (CPF, telefone...) são mascarados automaticamente. O detalhe você obtém conversando com a pessoa. |

### 3.2 Atender

Fale com a pessoa **pelo canal humano** (Slack, conversa). O Tutor não entrega mensagens suas ao
tutorado.

### 3.3 Fechar

```bash
.venv/bin/python scripts/buddy.py close 12 --by maria.souza --note "acesso liberado pelo TI"
```

Na nota, registre **o encaminhamento**, não o conteúdo sensível ("direcionado ao RH", e não o valor
do salário). Para ver também os fechados: `requests --buddy maria.souza --all`.

### 3.4 Acompanhar o progresso dos seus tutorados

```bash
.venv/bin/python scripts/buddy.py tutees --buddy maria.souza
```

```
tutorado      papel                        feitos  próximo               revisar          último acesso  pedidos
ana.lima      Analista de Negócios         0/4     cultura_empresa       -                nunca entrou   1
joao.silva    Desenvolvedor(a) Salesforce  2/4     quiz: pipeline_deploy cultura_empresa  10/10 09:41    1
```

| Coluna | Para que serve |
|---|---|
| `feitos` | Módulos concluídos / total da trilha |
| `próximo` | Próximo módulo, ou o quiz em andamento |
| `revisar` | Módulos com nota abaixo de 70%: bom assunto para um papo rápido |
| `último acesso` | Quem "nunca entrou" ou sumiu há dias pode precisar de um empurrão |
| `pedidos` | Seus pedidos abertos daquele tutorado |

O progresso é só um sinal: a conversa com a pessoa diz mais que a nota.

---

## 4. Boas práticas

- **Não use o Tutor para falar com o tutorado**: ele não repassa recados.
- **Dúvida de processo** (não pessoal) que virou pedido provavelmente é uma falha da base. Avise
  o autor ([guia do autor](2-autor-de-conteudo.md)).
- **Muitos pedidos da mesma categoria** apontam algo a ajustar no onboarding em si; conte ao responsável.
- **Privacidade:** o que você vê aqui (progresso, notas, pedidos) é dado pessoal do tutorado. Use
  só para apoiá-lo.

---

## 5. Referência rápida

| Quero... | `.venv/bin/python scripts/buddy.py ...` |
|---|---|
| Ver meus pedidos abertos | `requests --buddy <meu.login>` |
| Ver também os fechados | `requests --buddy <meu.login> --all` |
| Fechar um pedido | `close <id> --by <meu.login> --note "<o que foi feito>"` |
| Ver meus tutorados e o progresso | `tutees --buddy <meu.login>` |
