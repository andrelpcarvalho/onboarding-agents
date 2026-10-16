"""Modelos de domínio do onboarding."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Module(BaseModel):
    id: str
    title: str
    objectives: list[str]
    kb_tags: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    estimated_minutes: int = 30


class Role(BaseModel):
    id: str
    title: str
    description: str
    seniority: list[str] = Field(default_factory=lambda: ["junior", "pleno", "senior"])
    buddy_contact: str | None = None
    modules: list[Module]

    def module(self, module_id: str) -> Module | None:
        return next((m for m in self.modules if m.id == module_id), None)


class QuizQuestion(BaseModel):
    """Pergunta de múltipla escolha do banco de um material."""

    question: str = Field(description="enunciado da pergunta")
    options: list[str] = Field(description="exatamente 4 alternativas, sem letras na frente")
    correct_option: int = Field(description="índice da alternativa correta: 0, 1, 2 ou 3")
    explanation: str = Field(
        default="", description="1 frase dizendo por que a correta está certa, com a fonte"
    )


class QuizBank(BaseModel):
    """Saída estruturada do gerador de perguntas do Curador."""

    questions: list[QuizQuestion]


MaterialStatus = Literal["draft", "approved", "stale"]


class Material(BaseModel):
    id: int | None = None
    role_id: str
    module_id: str
    version: int = 1
    title: str
    content_md: str
    sources: list[str]
    status: MaterialStatus = "draft"
    approved_by: str | None = None
    review_note: str | None = None
    quiz: list[QuizQuestion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


ModuleStatus = Literal["not_started", "in_progress", "done"]


class ModuleProgress(BaseModel):
    status: ModuleStatus = "not_started"
    score: float | None = None
    attempts: int = 0
    updated_at: str | None = None


class Gap(BaseModel):
    id: int | None = None
    user_id: str
    role_id: str | None
    module_id: str | None
    question: str
    status: Literal["open", "resolved"] = "open"
    created_at: datetime = Field(default_factory=datetime.utcnow)


EscalationCategory = Literal["rh", "juridico", "saude", "conflito", "acesso", "outro"]


class Escalation(BaseModel):
    id: int | None = None
    user_id: str
    role_id: str | None
    category: EscalationCategory
    urgency: Literal["normal", "alta"] = "normal"
    summary: str
    buddy_id: str | None = None
    status: Literal["open", "closed"] = "open"
    closed_by: str | None = None
    close_note: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BuddyAssignment(BaseModel):
    """Quem é o buddy de cada tutorado. Definido pelo responsável, nunca pelo tutorado."""

    user_id: str
    buddy_id: str
    buddy_name: str
    buddy_contact: str
    assigned_by: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
