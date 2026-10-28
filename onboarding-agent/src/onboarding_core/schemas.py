"""Modelos de domínio do onboarding."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    # Missões práticas da trilha (ids de data/missions/*.yaml), na ordem sugerida.
    missions: list[str] = Field(default_factory=list)

    def module(self, module_id: str) -> Module | None:
        return next((m for m in self.modules if m.id == module_id), None)


# ---------- Missões (prática guiada em sistemas, em homologação) ----------

CheckpointKind = Literal["confirm", "describe", "capture"]


class Checkpoint(BaseModel):
    """Um passo verificável da missão. Os campos de verificação nunca vão ao modelo."""

    id: str
    kind: CheckpointKind
    tutor_instruction: str
    explain: list[str] = Field(default_factory=list)  # fontes arquivo.md#Seção
    expected: list[str] = Field(default_factory=list)  # describe: palavras-chave
    block_on: list[str] = Field(default_factory=list)  # termos que bloqueiam a missão
    field: str | None = None  # capture: nome da evidência guardada no estado
    pattern: str | None = None  # capture: regex aplicada à mensagem do colaborador
    fallback_source: str | None = None  # fonte indicada depois de N tentativas
    fallback_after: int = 2

    @model_validator(mode="after")
    def _by_kind(self) -> Checkpoint:
        if self.kind == "describe" and not self.expected:
            raise ValueError(f"checkpoint {self.id}: 'describe' exige 'expected'")
        if self.kind == "capture" and not (self.field and self.pattern):
            raise ValueError(f"checkpoint {self.id}: 'capture' exige 'field' e 'pattern'")
        return self


class MissionStep(BaseModel):
    id: str
    title: str
    guidance: str = ""
    helpers: list[str] = Field(default_factory=list)  # tools auxiliares liberadas na etapa
    checkpoints: list[Checkpoint]


class DoneWhen(BaseModel):
    """Critério de finalização: duas evidências capturadas precisam ser iguais."""

    left: str
    right: str


class Mission(BaseModel):
    id: str
    title: str
    description: str = ""
    status: Literal["draft", "approved"] = "draft"
    approved_by: str | None = None
    prerequisites: list[str] = Field(default_factory=list)  # ids de módulos ou missões
    params: dict[str, str] = Field(default_factory=dict)
    steps: list[MissionStep]
    done_when: DoneWhen | None = None

    @model_validator(mode="after")
    def _fields_exist(self) -> Mission:
        fields = {c.field for s in self.steps for c in s.checkpoints if c.field}
        if self.done_when and not {self.done_when.left, self.done_when.right} <= fields:
            raise ValueError("done_when cita evidências que nenhum checkpoint captura")
        return self


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


class RoleAssignment(BaseModel):
    """Papel (trilha) de cada tutorado. Definido pelo responsável, nunca pela conversa."""

    user_id: str
    role_id: str
    assigned_by: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class BuddyAssignment(BaseModel):
    """Quem é o buddy de cada tutorado. Definido pelo responsável, nunca pelo tutorado."""

    user_id: str
    buddy_id: str
    buddy_name: str
    buddy_contact: str
    assigned_by: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
