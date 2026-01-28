"""
Enhanced models for BillBrain + Action Items.
Bills stay bills (amounts, vendors, reconciliation).
Actions become tasks synced to Second Brain.
"""
import uuid
import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
import enum

# --- Configuration ---
DATABASE_URL = "sqlite:///bill_brain.db"

class Base(DeclarativeBase):
    pass

# --- Enums ---
class BillStatus(enum.Enum):
    DETECTED = "detected"       # Raw extraction done
    NEEDS_INFO = "needs_info"   # Missing critical fields
    READY = "ready"             # Validated, ready for budget
    PAID = "paid"               # Matched to transaction
    ARCHIVED = "archived"       # Old history

class UrgencyLevel(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"               # Due in < 3 days
    critical = "critical"       # Disconnect notice / Fraud

class ActionStatus(enum.Enum):
    PENDING = "pending"         # Needs review
    APPROVED = "approved"       # User confirmed, ready to sync
    SYNCED = "synced"           # Pushed to Second Brain
    IGNORED = "ignored"         # User marked as not needed
    COMPLETED = "completed"     # Done

class ActionPriority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

# --- BILL MODELS (unchanged) ---

class BillEntity(Base):
    """
    The Identity. Represents a recurring relationship (e.g., 'Pepco', 'Netflix').
    """
    __tablename__ = "bill_entities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_normalized: Mapped[str] = mapped_column(String, unique=True, index=True)
    
    category: Mapped[Optional[str]] = mapped_column(String)  # Utilities, Rent, Subscriptions
    recurrence_interval: Mapped[Optional[str]] = mapped_column(String)  # monthly, yearly
    default_urgency: Mapped[UrgencyLevel] = mapped_column(Enum(UrgencyLevel), default=UrgencyLevel.medium)
    
    match_patterns: Mapped[Optional[dict]] = mapped_column(JSON)
    
    instances: Mapped[List["BillInstance"]] = relationship(back_populates="entity")

    def __repr__(self):
        return f"<BillEntity(vendor='{self.vendor_normalized}')>"


class BillInstance(Base):
    """
    The Obligation. A specific bill for a specific month.
    """
    __tablename__ = "bill_instances"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    entity_id: Mapped[Optional[str]] = mapped_column(ForeignKey("bill_entities.id"))
    entity: Mapped[Optional["BillEntity"]] = relationship(back_populates="instances")

    # Financial Data
    amount_due: Mapped[Optional[float]] = mapped_column(Float)
    min_due: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    statement_balance: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    
    urgency: Mapped[str] = mapped_column(String, default="medium")
    due_date: Mapped[Optional[datetime.date]] = mapped_column(DateTime)
    billing_period: Mapped[Optional[str]] = mapped_column(String)
    
    # State
    status: Mapped[BillStatus] = mapped_column(Enum(BillStatus), default=BillStatus.DETECTED)
    is_autopay: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Audit
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    evidence_links: Mapped[List["Evidence"]] = relationship(back_populates="bill_instance")

    def __repr__(self):
        return f"<BillInstance(vendor='{self.entity_id}', amount={self.amount_due}, status={self.status})>"


# --- NEW: ACTION ITEM MODEL ---

class ActionItem(Base):
    """
    Non-bill actionable emails. Synced to Second Brain as tasks.
    """
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Task details
    action_required: Mapped[str] = mapped_column(Text)  # Verb-first task description
    sender_name: Mapped[Optional[str]] = mapped_column(String)
    sender_email: Mapped[Optional[str]] = mapped_column(String)
    subject: Mapped[Optional[str]] = mapped_column(String)
    
    # Classification
    priority: Mapped[ActionPriority] = mapped_column(Enum(ActionPriority), default=ActionPriority.medium)
    domain: Mapped[str] = mapped_column(String, default="work")  # work, personal, admin
    deadline: Mapped[Optional[datetime.date]] = mapped_column(DateTime)
    
    # Context for the task
    context: Mapped[Optional[str]] = mapped_column(Text)  # Brief summary from email
    email_snippet: Mapped[Optional[str]] = mapped_column(Text)  # First 500 chars
    
    # State machine
    status: Mapped[ActionStatus] = mapped_column(Enum(ActionStatus), default=ActionStatus.PENDING)
    
    # Second Brain sync tracking
    second_brain_task_id: Mapped[Optional[int]] = mapped_column(Integer)  # FK to Second Brain tasks table
    synced_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    
    # Evidence link
    evidence_id: Mapped[Optional[str]] = mapped_column(ForeignKey("evidence_store.id"))
    
    # Audit
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    
    # LLM refinement fields (for ADHD-friendly task breakdown)
    first_step: Mapped[Optional[str]] = mapped_column(String)  # 2-minute starter
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    needs_clarification: Mapped[bool] = mapped_column(Boolean, default=False)
    clarification_questions: Mapped[Optional[dict]] = mapped_column(JSON)

    def __repr__(self):
        return f"<ActionItem(action='{self.action_required[:50]}...', priority={self.priority}, status={self.status})>"


# --- EVIDENCE MODEL (updated) ---

class Evidence(Base):
    """
    The Proof. Stores raw emails for both bills AND actions.
    """
    __tablename__ = "evidence_store"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    source_type: Mapped[str] = mapped_column(String)  # "gmail", "file_upload"
    external_id: Mapped[Optional[str]] = mapped_column(String, unique=True)  # Gmail Message-ID
    
    raw_text_hash: Mapped[str] = mapped_column(String, index=True)
    raw_content: Mapped[str] = mapped_column(Text)
    meta_data: Mapped[dict] = mapped_column(JSON)  # Sender, Subject, Date
    
    # Can link to EITHER a bill OR an action (or neither for ignored)
    bill_instance_id: Mapped[Optional[str]] = mapped_column(ForeignKey("bill_instances.id"))
    bill_instance: Mapped[Optional["BillInstance"]] = relationship(back_populates="evidence_links")
    
    item_type: Mapped[str] = mapped_column(String, default="unknown")  # "bill", "action", "ignore"
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


# --- Initialization ---

def init_db():
    """Creates the database and tables if they don't exist."""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print(f"✅ Database initialized at {DATABASE_URL}")
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == "__main__":
    init_db()
