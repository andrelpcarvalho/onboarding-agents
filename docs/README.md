# Onboarding com Tutor e Curador: guias

O sistema tem **dois agentes** (Tutor e Curador) e **cinco tipos de pessoa** envolvidos. Cada
guia abaixo é escrito para uma dessas pessoas e cobre só o que ela precisa fazer.

| # | Guia | Para quem | Em uma frase |
|---|---|---|---|
| 1 | [Responsável pelo piloto](1-responsavel-pelo-piloto.md) | Quem instala, opera e cuida dos dados | Coloca no ar, atribui buddies, acompanha as filas e conduz o teste |
| 2 | [Autor de conteúdo](2-autor-de-conteudo.md) | Quem define trilhas e escreve a base de conhecimento | Cria papéis, módulos e documentos-fonte e pede ao Curador os materiais |
| 3 | [Revisor](3-revisor.md) | Quem garante a qualidade dos materiais | Confere texto e perguntas do quiz contra a base; aprova, corrige ou devolve |
| 4 | [Buddy](4-buddy.md) | Colega que acompanha cada novo colaborador | Acompanha o progresso dos seus tutorados e atende os pedidos que o Tutor encaminha |
| 5 | [Tutorado](5-tutorado.md) | Novo colaborador | Faz o onboarding conversando com o Tutor |
| 6 | [Guia de teste](6-guia-de-teste.md) | Quem quer ver o sistema funcionando | Roteiro prático para replicar e comprovar cada comportamento importante |

## Por onde começar

1. **Responsável** instala (guia 1, seção 1).
2. **Autor** escreve a base e os papéis e gera os materiais (guia 2).
3. **Revisor** aprova todos os módulos (guia 3).
4. **Responsável** roda `make eval`, atribui os buddies e convida os tutorados (guia 1).
5. **Tutorados** fazem o onboarding (guia 5); **buddies** acompanham e atendem pedidos (guia 4).

---

## Como as peças se encaixam

```
   AUTOR                    CURADOR (agente)              REVISOR
   papéis + base  ───────▶  gera material + perguntas ──▶ aprova / corrige / devolve
   de conhecimento          (rascunho, com fontes)              │
                                                                │ material aprovado
                                                                ▼
   TUTORADO  ◀─── conversa, ensina, aplica quiz ───  TUTOR (agente)
       │                                                │      │
       │                    dúvida sem resposta na base │      │ assunto pessoal (RH, saúde,
       │                                                ▼      ▼ acesso...), com consentimento
       │                                    lacunas p/ AUTOR   pedido p/ BUDDY do tutorado
       │                                                               │
       └──────────────── contato humano (Slack, conversa) ◀─────────────┘

   RESPONSÁVEL: instala, atribui buddy a cada tutorado, acompanha todas as filas (make inbox)
```

## O que existe em cada fila

| Fila | Quem alimenta | Quem atende | Comando |
|---|---|---|---|
| Rascunhos de material | Curador | Revisor | `scripts/approve.py list` |
| Lacunas (perguntas sem resposta na base) | Tutor | Autor (e revisor) | `scripts/approve.py gaps` |
| Pedidos ao buddy | Tutor | Buddy do tutorado (ou responsável, se não houver buddy) | `scripts/buddy.py requests --buddy <login>` |
| Visão geral de tudo | — | Responsável | `make inbox` |

> **MVP:** não há notificações automáticas. Cada pessoa consulta a sua fila com uma rotina
> combinada (ex.: uma vez por dia durante o piloto).
