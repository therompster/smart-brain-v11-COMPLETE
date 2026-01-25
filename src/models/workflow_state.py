"""Core data models."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class NoteType(str, Enum):
    """Note types in PARA system."""
    PROJECT = "Project"
    AREA = "Area"
    NOTE = "Note"


class TaskStatus(str, Enum):
    """Task statuses."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    """Priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EnergyLevel(str, Enum):
    """Energy requirement levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EnergyType(str, Enum):
    """Types of energy required."""
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    ADMINISTRATIVE = "administrative"
    SOCIAL = "social"


class ClusterNote(BaseModel):
    """Clustered note from brain dump processing."""
    title: str
    content: str
    type: NoteType
    keywords: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoutedNote(BaseModel):
    """Note with domain assignment."""
    title: str
    content: str
    type: NoteType
    domain: str
    keywords: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """Task model."""
    id: Optional[int] = None
    text: str
    action: str
    status: TaskStatus = TaskStatus.OPEN
    priority: Priority = Priority.MEDIUM
    estimated_duration_minutes: Optional[int] = None
    energy_required: Optional[EnergyLevel] = None
    energy_type: Optional[EnergyType] = None
    focus_required: Optional[str] = None
    due_date: Optional[datetime] = None
    domain: Optional[str] = None
    source_note_id: Optional[int] = None
    parent_task_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    """Decision model."""
    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    source_note_id: Optional[int] = None
    domain: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Question(BaseModel):
    """Question model."""
    id: Optional[int] = None
    question: str
    answer: Optional[str] = None
    status: str = "open"
    source_note_id: Optional[int] = None
    domain: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Blocker(BaseModel):
    """Blocker model."""
    id: Optional[int] = None
    description: str
    status: str = "active"
    related_task_id: Optional[int] = None
    source_note_id: Optional[int] = None
    domain: Optional[str] = None
    resolution: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowState(BaseModel):
    """State object for LangGraph workflow."""
    file_path: str
    raw_content: str = ""
    clusters: List[ClusterNote] = Field(default_factory=list)
    routed_notes: List[RoutedNote] = Field(default_factory=list)
    extracted_tasks: List[Task] = Field(default_factory=list)
    extracted_decisions: List[Decision] = Field(default_factory=list)
    extracted_questions: List[Question] = Field(default_factory=list)
    extracted_blockers: List[Blocker] = Field(default_factory=list)
    status: str = "processing"
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
