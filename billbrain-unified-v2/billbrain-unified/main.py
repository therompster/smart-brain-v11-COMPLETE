"""
BillBrain Unified API.
Handles both bills AND action items.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os

from models import (
    init_db, get_session,
    BillInstance, BillEntity, BillStatus,
    ActionItem, ActionStatus, ActionPriority,
    Evidence
)
from connectors.second_brain_sync import second_brain

app = FastAPI(title="BillBrain Unified API", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
engine = init_db()


# --- Pydantic Models ---

class BillResponse(BaseModel):
    id: str
    vendor: str
    amount_due: Optional[float]
    due_date: Optional[str]
    urgency: str
    status: str
    is_autopay: bool
    created_at: str

class ActionResponse(BaseModel):
    id: str
    action_required: str
    sender_name: Optional[str]
    subject: Optional[str]
    priority: str
    domain: str
    deadline: Optional[str]
    status: str
    first_step: Optional[str]
    estimated_minutes: Optional[int]
    needs_clarification: bool
    created_at: str


# --- Bill Endpoints ---

@app.get("/api/bills", response_model=List[BillResponse])
def get_bills(status: Optional[str] = None):
    """Get all bills, optionally filtered by status."""
    session = get_session(engine)
    
    query = session.query(BillInstance).join(BillEntity)
    
    if status:
        try:
            status_enum = BillStatus[status.upper()]
            query = query.filter(BillInstance.status == status_enum)
        except KeyError:
            pass
    
    bills = query.order_by(BillInstance.created_at.desc()).all()
    
    result = []
    for bill in bills:
        result.append(BillResponse(
            id=bill.id,
            vendor=bill.entity.vendor_normalized if bill.entity else "Unknown",
            amount_due=bill.amount_due,
            due_date=bill.due_date.isoformat() if bill.due_date else None,
            urgency=bill.urgency or "medium",
            status=bill.status.value,
            is_autopay=bill.is_autopay,
            created_at=bill.created_at.isoformat()
        ))
    
    session.close()
    return result


@app.post("/api/bills/{bill_id}/approve")
def approve_bill(bill_id: str):
    """Approve a detected bill (mark as READY)."""
    session = get_session(engine)
    bill = session.query(BillInstance).filter_by(id=bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    bill.status = BillStatus.READY
    session.commit()
    session.close()
    
    return {"status": "ok", "message": "Bill approved"}


@app.post("/api/bills/{bill_id}/paid")
def mark_bill_paid(bill_id: str):
    """Mark a bill as paid."""
    session = get_session(engine)
    bill = session.query(BillInstance).filter_by(id=bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    bill.status = BillStatus.PAID
    session.commit()
    session.close()
    
    return {"status": "ok", "message": "Bill marked as paid"}


@app.post("/api/bills/{bill_id}/ignore")
def ignore_bill(bill_id: str):
    """Archive/ignore a bill."""
    session = get_session(engine)
    bill = session.query(BillInstance).filter_by(id=bill_id).first()
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    bill.status = BillStatus.ARCHIVED
    session.commit()
    session.close()
    
    return {"status": "ok", "message": "Bill ignored"}


# --- Action Endpoints ---

@app.get("/api/actions", response_model=List[ActionResponse])
def get_actions(status: Optional[str] = None):
    """Get all action items, optionally filtered by status."""
    session = get_session(engine)
    
    query = session.query(ActionItem)
    
    if status:
        try:
            status_enum = ActionStatus[status.upper()]
            query = query.filter(ActionItem.status == status_enum)
        except KeyError:
            pass
    
    actions = query.order_by(ActionItem.created_at.desc()).all()
    
    result = []
    for action in actions:
        result.append(ActionResponse(
            id=action.id,
            action_required=action.action_required,
            sender_name=action.sender_name,
            subject=action.subject,
            priority=action.priority.value if action.priority else "medium",
            domain=action.domain or "work",
            deadline=action.deadline.isoformat() if action.deadline else None,
            status=action.status.value,
            first_step=action.first_step,
            estimated_minutes=action.estimated_minutes,
            needs_clarification=action.needs_clarification,
            created_at=action.created_at.isoformat()
        ))
    
    session.close()
    return result


@app.post("/api/actions/{action_id}/approve")
def approve_action(action_id: str):
    """Approve an action (ready to sync to Second Brain)."""
    session = get_session(engine)
    action = session.query(ActionItem).filter_by(id=action_id).first()
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    action.status = ActionStatus.APPROVED
    session.commit()
    session.close()
    
    return {"status": "ok", "message": "Action approved"}


@app.post("/api/actions/{action_id}/ignore")
def ignore_action(action_id: str):
    """Ignore an action item."""
    session = get_session(engine)
    action = session.query(ActionItem).filter_by(id=action_id).first()
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    action.status = ActionStatus.IGNORED
    session.commit()
    session.close()
    
    return {"status": "ok", "message": "Action ignored"}


@app.post("/api/actions/{action_id}/complete")
def complete_action(action_id: str):
    """Mark action as completed."""
    session = get_session(engine)
    action = session.query(ActionItem).filter_by(id=action_id).first()
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    action.status = ActionStatus.COMPLETED
    session.commit()
    session.close()
    
    return {"status": "ok", "message": "Action completed"}


@app.post("/api/actions/sync")
def sync_actions_to_second_brain():
    """Sync all approved actions to Second Brain."""
    session = get_session(engine)
    
    stats = second_brain.sync_all_approved(session, ActionItem, ActionStatus)
    session.close()
    
    return {
        "status": "ok",
        "synced": stats["synced"],
        "failed": stats["failed"]
    }


# --- Stats Endpoint ---

@app.get("/api/stats")
def get_stats():
    """Get summary stats."""
    session = get_session(engine)
    
    # Bills
    bills_pending = session.query(BillInstance).filter(
        BillInstance.status.in_([BillStatus.DETECTED, BillStatus.NEEDS_INFO])
    ).count()
    
    bills_ready = session.query(BillInstance).filter(
        BillInstance.status == BillStatus.READY
    ).count()
    
    bills_paid = session.query(BillInstance).filter(
        BillInstance.status == BillStatus.PAID
    ).count()
    
    # Actions
    actions_pending = session.query(ActionItem).filter(
        ActionItem.status == ActionStatus.PENDING
    ).count()
    
    actions_approved = session.query(ActionItem).filter(
        ActionItem.status == ActionStatus.APPROVED
    ).count()
    
    actions_synced = session.query(ActionItem).filter(
        ActionItem.status == ActionStatus.SYNCED
    ).count()
    
    session.close()
    
    return {
        "bills": {
            "pending": bills_pending,
            "ready": bills_ready,
            "paid": bills_paid
        },
        "actions": {
            "pending": actions_pending,
            "approved": actions_approved,
            "synced": actions_synced
        }
    }


# --- Ingestion Trigger ---

@app.post("/api/ingest")
def trigger_ingestion(limit: int = 50):
    """Trigger email ingestion."""
    from orchestrator import run_ingestion_loop
    
    stats = run_ingestion_loop(limit=limit)
    return {
        "status": "ok",
        "bills": stats["bills"],
        "actions": stats["actions"],
        "ignored": stats["ignored"]
    }


# --- Serve UI ---

@app.get("/")
def serve_ui():
    """Serve the main UI."""
    return FileResponse("index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
