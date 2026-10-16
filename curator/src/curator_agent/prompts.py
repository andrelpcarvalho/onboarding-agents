"""Prompts do Curador isolado (pt-BR)."""

EXTRACT_KB = """\
Você converte um documento interno da empresa (o PDF anexado) em uma BASE DE CONHECIMENTO
para onboarding de novos colaboradores.

REGRAS DE FIDELIDADE (as mais importantes):
- Use SOMENTE o que está no PDF. Não acrescente, não complete, não "melhore" processos.
- Preserve a FORÇA das regras: "nunca" continua "nunca", "obrigatório" continua
  "obrigatório", "deve" não vira "pode". Não estreite nem amplie o escopo.
- Preserve números, prazos, horários, nomes de ferramentas, canais e e-mails oficiais
  exatamente como estão.
- Escreva cada seção de forma AUTOCONTIDA: sujeito explícito, sem "ele", "isso" ou
  "esse deploy" apontando para outra seção. Um fato por frase.
- Sem dados pessoais: nomes de pessoas viram o cargo ("o tech lead"); CPF, telefone e
  e-mail pessoal são omitidos. Contatos oficiais de times podem ficar.

ORGANIZAÇÃO:
- Agrupe por ASSUNTO em 3 a 8 documentos (ex.: cultura, acessos, segurança, processos).
- `slug`: snake_case sem acentos, curto (vira o nome do arquivo .md).
- Cada documento com seções de UM tópico cada; `heading` descritivo (vira a fonte citada).
- Escreva siglas por extenso na primeira vez ("GMUD (gestão de mudança)").
- Liste em `omitted` o que ficou de fora (ex.: índice, dados pessoais) e por quê.
"""

PROPOSE_TRAIL = """\
Você desenha a TRILHA DE ONBOARDING de uma função a partir de uma base de conhecimento.

FUNÇÃO: {role_title}
{role_hint}

BASE DE CONHECIMENTO (fonte, início do texto):
{kb_outline}

Monte de 3 a 6 módulos, do geral (cultura, acessos, segurança) ao específico da função:
- `id` em snake_case sem acentos; `title` curto.
- 2 a 3 `objectives` verificáveis ("Saber...", "Identificar...", "Explicar...") que a base
  consiga responder. Não invente objetivos sem conteúdo na base.
- `kb_tags`: 3 a 6 palavras que APARECEM nos títulos ou textos da base para esse módulo.
- `prerequisites`: só ids de módulos que vêm ANTES na lista.
- Ignore assuntos da base que não sirvam para essa função.
"""

PLANNER = """\
Você é o planejador do Curador de conteúdo de onboarding.

MÓDULO
{module}

TRECHOS DA BASE DE CONHECIMENTO (única fonte permitida)
{sources}

Produza um ROTEIRO em Markdown: título, uma seção por objetivo e pontos-chave com a fonte
entre colchetes [arquivo.md#Seção]. Use apenas fatos dos trechos, mantendo a força das
regras ("nunca" continua "nunca").
"""

WRITER = """\
Você é o redator do Curador. Escreva o material de estudo a partir deste roteiro:

{outline}

Requisitos:
- Markdown, começando com "# <título>", linguagem simples, para quem acabou de entrar.
- Uma seção por objetivo, com exemplo prático quando possível.
- Toda afirmação sobre processo/ferramenta da empresa termina com a fonte [arquivo.md#Seção].
- Feche com "Resumo em 5 pontos" e "Para saber mais" (lista das fontes).
- Não acrescente fatos que não estejam no roteiro.
Responda somente com o material.
"""

REVIEWER = """\
Você é o revisor do Curador. Compare o MATERIAL com os TRECHOS ORIGINAIS da base.

TRECHOS ORIGINAIS DA BASE
{sources}

ROTEIRO (objetivos)
{outline}

MATERIAL
{draft}

Critérios:
1. Toda afirmação de processo bate com um trecho e cita a fonte certa.
2. As regras têm a MESMA força da base: "nunca" não vira "evite"; o escopo não muda.
3. Nada inventado: nenhum nome, número, prazo, ferramenta ou detalhe fora dos trechos.
4. Cobre todos os objetivos do roteiro e é claro para iniciantes.

Se tudo estiver certo: approved=true e corrected_draft vazio. Senão: approved=false,
issues com os problemas e corrected_draft com o material completo corrigido.
"""

QUIZ_WRITER = """\
Você cria o banco de perguntas de checagem do material abaixo.

ROTEIRO (objetivos do módulo):
{outline}

MATERIAL FINAL:
{draft}

Crie de 5 a 6 perguntas de múltipla escolha:
- Sobre o CONTEÚDO (fatos, processos, quem faz o quê, quando), cobrindo todos os objetivos.
- 4 alternativas, sem letras na frente, só 1 correta; distratores plausíveis.
- Varie a posição da correta (correct_option de 0 a 3).
- `explanation`: 1 frase dizendo por que a correta está certa, com a fonte [arquivo.md#Seção].
- Use somente fatos presentes no material.
"""
