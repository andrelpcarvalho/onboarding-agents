"""Entradas para o LangGraph Studio (`langgraph dev`), equivalente ao `adk web`.

O servidor do Studio fornece checkpointer e store próprios, por isso os grafos são
compilados sem persistência aqui. Atenção: no Studio a entrada não passa por
`prepare_user_message`, então a mensagem chega sem mascaramento de PII.
"""

from onboarding_lg.curator.graph import build_curator_graph
from onboarding_lg.tutor.graph import build_tutor_graph

tutor = build_tutor_graph()
curator = build_curator_graph()
