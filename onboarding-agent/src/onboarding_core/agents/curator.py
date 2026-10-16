"""Curador: pipeline planner -> writer -> (reviewer em loop) -> quiz_writer -> publisher."""

from __future__ import annotations

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import exit_loop

from .. import config
from ..schemas import QuizBank
from ..tools import get_learning_path, list_open_gaps, save_material_draft, search_sources
from . import prompts


def build_curator(name: str = "curator") -> SequentialAgent:
    """Cria uma instância nova do Curador.

    Uma instância por pai: o ADK não permite reaproveitar o mesmo agente em
    duas árvores (ex.: root do `adk web` e AgentTool dentro do Tutor).
    """
    planner = LlmAgent(
        name="syllabus_planner",
        model=config.model("curator"),
        instruction=prompts.CURATOR_PLANNER,
        tools=[get_learning_path, list_open_gaps, search_sources],
        output_key="outline",
    )
    writer = LlmAgent(
        name="material_writer",
        model=config.model("curator"),
        instruction=prompts.CURATOR_WRITER,
        output_key="draft",
    )
    reviewer = LlmAgent(
        name="material_reviewer",
        model=config.model("reviewer"),
        instruction=prompts.CURATOR_REVIEWER,
        tools=[exit_loop],
        # Sem output_key: quando reprova, a versão corrigida é escrita em `draft`
        # pelo callback abaixo; quando aprova ("APROVADO"), `draft` fica intacto.
        after_agent_callback=_keep_corrected_draft,
    )
    quiz_writer = LlmAgent(
        name="quiz_writer",
        model=config.model("curator"),
        instruction=prompts.CURATOR_QUIZ_WRITER,
        output_schema=QuizBank,  # saída estruturada: vira dict em state["quiz_bank"]
        output_key="quiz_bank",
    )
    publisher = LlmAgent(
        name="material_publisher",
        model=config.model("reviewer"),
        instruction=prompts.CURATOR_PUBLISHER,
        tools=[save_material_draft],
    )
    return SequentialAgent(
        name=name,
        description=(
            "Gera material de onboarding para um módulo de um papel, com base na "
            "base de conhecimento, com banco de perguntas, e salva como rascunho. "
            "Entrada: 'role_id=<id> module_id=<id>'."
        ),
        sub_agents=[
            planner,
            writer,
            LoopAgent(name="review_loop", sub_agents=[reviewer], max_iterations=3),
            quiz_writer,
            publisher,
        ],
    )


def _keep_corrected_draft(callback_context) -> None:
    """Copia a última resposta do revisor para `draft` se não for aprovação."""
    events = callback_context.session.events
    for ev in reversed(events):
        if ev.author == "material_reviewer" and ev.content and ev.content.parts:
            text = "".join(p.text or "" for p in ev.content.parts).strip()
            if text and "APROVADO" not in text.upper()[:20]:
                callback_context.state["draft"] = text
            return
    return
