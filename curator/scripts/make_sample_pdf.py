"""Gera examples/manual-qa.pdf: manual FICTÍCIO para testar a importação.

Tem armadilhas de propósito para conferir a fidelidade da extração:
- regras com "nunca"/"obrigatório" (não podem enfraquecer);
- números, prazos e horários (não podem mudar);
- uma tabela (severidade x prazo);
- um nome de pessoa (deve virar cargo) e um contato oficial (deve ser mantido).
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[1] / "examples" / "manual-qa.pdf"

S = getSampleStyleSheet()
H1, H2, P = S["Title"], S["Heading2"], S["BodyText"]

story = [
    Paragraph("Manual de Onboarding: Analista de QA", H1),
    Paragraph("Empresa Exemplo (documento fictício para testes)", P),
    Spacer(1, 12),
    Paragraph("1. Boas-vindas e forma de trabalhar", H2),
    Paragraph("O time de QA trabalha em sprints de duas semanas. A daily acontece às 9h45 e "
              "dura no máximo 15 minutos. A retrospectiva é na última sexta-feira da sprint.", P),
    Paragraph("Dúvidas sobre o processo de testes devem ser levadas à Carla Mendes, tech lead "
              "de QA, ou ao canal #qa-duvidas no Slack.", P),
    Paragraph("2. Ambientes e acessos", H2),
    Paragraph("No primeiro dia, abra um chamado no portal de serviços pedindo acesso ao Jira "
              "(projeto QA), ao Provar e ao sandbox de UAT. O prazo médio de liberação é de "
              "2 dias úteis após a aprovação do gestor.", P),
    Paragraph("Testes nunca podem ser executados em produção. Todo teste roda no sandbox de UAT "
              "ou no sandbox de QA.", P),
    PageBreak(),
    Paragraph("3. Testes automatizados", H2),
    Paragraph("Usamos o Provar para os testes de regressão. A suíte completa roda toda noite às "
              "22h contra o ambiente de UAT. Um teste que falha duas noites seguidas deve ser "
              "investigado no dia seguinte.", P),
    Paragraph("É obrigatório criar um teste automatizado para todo bug de severidade alta "
              "corrigido.", P),
    Paragraph("4. Como reportar um bug", H2),
    Paragraph("Bugs são abertos no Jira, projeto QA, com passos para reproduzir, ambiente, "
              "resultado esperado, resultado obtido e evidência (print ou vídeo).", P),
    Paragraph("Prazos de resposta por severidade:", P),
    Table([["Severidade", "Exemplo", "Primeira resposta"],
           ["Alta", "Sistema fora do ar ou perda de dados", "2 horas"],
           ["Média", "Funcionalidade com contorno", "1 dia útil"],
           ["Baixa", "Erro visual ou de texto", "5 dias úteis"]],
          style=TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)])),
    Spacer(1, 8),
    Paragraph("Bugs de severidade alta também devem ser avisados imediatamente no canal "
              "#qa-urgente. Fora do horário comercial, ligue para o plantão de suporte no "
              "ramal 4500.", P),
    Paragraph("5. Dados e segurança", H2),
    Paragraph("Dados reais de clientes nunca podem ser usados em massa de teste. Use apenas os "
              "dados sintéticos do repositório qa-fixtures. Suspeitas de vazamento devem ser "
              "reportadas ao time de segurança pelo e-mail seguranca@exemplo.com.", P),
]

OUT.parent.mkdir(exist_ok=True)
SimpleDocTemplate(str(OUT), pagesize=A4, title="Manual de Onboarding - QA").build(story)
print(f"gerado: {OUT}")
