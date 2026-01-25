"""FastAPI backend for Smart Second Brain."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import sqlite3
from loguru import logger

from src.config import settings
from src.services.cluster_service import cluster_service
from src.services.route_service import route_service
from src.storage.file_system import file_storage
from src.models.workflow_state import ClusterNote, NoteType

app = FastAPI(title="Smart Second Brain API")

# CORS for Svelte frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class NoteCreate(BaseModel):
    content: str
    title: Optional[str] = None


class NoteProcessed(BaseModel):
    suggested_domain: str
    suggested_title: str
    suggested_type: str
    confidence: float
    linked_notes: List[str]
    keywords: List[str]


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    domain: str
    type: str
    file_path: str
    created_at: str
    updated_at: str


class NoteSave(BaseModel):
    title: str
    content: str
    domain: str
    type: str


# Endpoints
@app.get("/")
async def root():
    return {"status": "ok", "app": "Smart Second Brain"}


@app.post("/api/notes/process", response_model=NoteProcessed)
async def process_note(note: NoteCreate):
    """
    Process note content without saving.
    Returns suggestions for domain, title, links, keywords.
    """
    try:
        # Generate title if not provided
        title = note.title
        if not title:
            # Extract first line as title
            first_line = note.content.split('\n')[0].strip('#').strip()
            title = first_line[:100] if first_line else "Untitled Note"
        
        # Cluster (in this case, single note)
        cluster = ClusterNote(
            title=title,
            content=note.content,
            type=NoteType.NOTE,
            keywords=[]
        )
        
        # Route to domain - returns dict not object
        routed = route_service.route(cluster)
        
        # Find linked notes (search for [[wikilinks]] or similar notes)
        linked = _find_linked_notes(note.content)
        
        return NoteProcessed(
            suggested_domain=routed.get("domain", "personal"),
            suggested_title=title,
            suggested_type="Note",
            confidence=routed.get("confidence", 0.5),
            linked_notes=linked,
            keywords=cluster.keywords
        )
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notes", response_model=NoteResponse)
async def create_note(note: NoteSave):
    """Save note to database and vault."""
    try:
        from src.models.workflow_state import RoutedNote, NoteType
        from src.services.task_extraction_service import task_extraction_service
        from src.services.task_dedupe_service import task_dedupe_service
        
        routed = RoutedNote(
            title=note.title,
            content=note.content,
            domain=note.domain,
            type=NoteType(note.type),
            keywords=[]
        )
        
        # Write to vault
        file_path = file_storage.write_note(routed, source_file="web-ui")
        
        # Get from database
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, content, domain, type, file_path, created_at, updated_at
            FROM notes WHERE file_path = ?
        """, (str(file_path),))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            raise HTTPException(status_code=500, detail="Note saved but not found in DB")
        
        note_id = row[0]
        
        # Extract tasks
        tasks = task_extraction_service.extract_tasks(note.content, note_id, note.domain)
        
        # Deduplicate tasks
        unique_tasks = task_dedupe_service.deduplicate(tasks)
        
        # Save tasks to database
        for task in unique_tasks:
            cursor.execute("""
                INSERT INTO tasks (text, action, status, priority, estimated_duration_minutes, domain, source_note_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task.text,
                task.action,
                task.status.value,
                task.priority.value,
                task.estimated_duration_minutes,
                task.domain,
                task.source_note_id
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved note with {len(unique_tasks)} unique tasks")
        
        return NoteResponse(
            id=row[0],
            title=row[1],
            content=row[2],
            domain=row[3],
            type=row[4],
            file_path=row[5],
            created_at=row[6],
            updated_at=row[7]
        )
        
    except Exception as e:
        logger.error(f"Save failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notes", response_model=List[NoteResponse])
async def list_notes(domain: Optional[str] = None, limit: int = 50):
    """List all notes, optionally filtered by domain."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        if domain:
            cursor.execute("""
                SELECT id, title, content, domain, type, file_path, created_at, updated_at
                FROM notes WHERE domain = ?
                ORDER BY created_at DESC LIMIT ?
            """, (domain, limit))
        else:
            cursor.execute("""
                SELECT id, title, content, domain, type, file_path, created_at, updated_at
                FROM notes
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            NoteResponse(
                id=row[0],
                title=row[1],
                content=row[2],
                domain=row[3],
                type=row[4],
                file_path=row[5],
                created_at=row[6],
                updated_at=row[7]
            )
            for row in rows
        ]
        
    except Exception as e:
        logger.error(f"List failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notes/{note_id}", response_model=NoteResponse)
async def get_note(note_id: int):
    """Get single note by ID."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, content, domain, type, file_path, created_at, updated_at
            FROM notes WHERE id = ?
        """, (note_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
        
        return NoteResponse(
            id=row[0],
            title=row[1],
            content=row[2],
            domain=row[3],
            type=row[4],
            file_path=row[5],
            created_at=row[6],
            updated_at=row[7]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get note failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/domains")
async def list_domains():
    """Get available PARA domains."""
    return {"domains": settings.domains_list}


class TaskResponse(BaseModel):
    id: int
    text: str
    action: str
    status: str
    priority: str
    estimated_duration_minutes: Optional[int]
    domain: str
    source_note_id: int
    created_at: str


@app.get("/api/tasks", response_model=List[TaskResponse])
async def list_tasks(status: Optional[str] = None, domain: Optional[str] = None):
    """List tasks, optionally filtered by status and domain."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        query = "SELECT id, text, action, status, priority, estimated_duration_minutes, domain, source_note_id, created_at FROM tasks WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            TaskResponse(
                id=row[0],
                text=row[1],
                action=row[2],
                status=row[3],
                priority=row[4],
                estimated_duration_minutes=row[5],
                domain=row[6],
                source_note_id=row[7],
                created_at=row[8]
            )
            for row in rows
        ]
    except Exception as e:
        logger.error(f"List tasks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/plan/daily")
async def get_daily_plan():
    """Get focused daily plan with 3-5 prioritized tasks."""
    try:
        from src.services.daily_planning_service import daily_planning_service
        plan = daily_planning_service.generate_plan()
        return plan
    except Exception as e:
        logger.error(f"Daily plan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/domains")
async def get_domains():
    """Get user's domains."""
    try:
        from src.services.domain_service import domain_service
        domains = domain_service.get_all_domains()
        return {"domains": domains}
    except Exception as e:
        logger.error(f"Get domains failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/onboarding/status")
async def onboarding_status():
    """Check if onboarding is complete."""
    try:
        from src.services.adaptive_onboarding_service import adaptive_onboarding
        return {"completed": adaptive_onboarding.is_complete()}
    except Exception as e:
        logger.error(f"Onboarding status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/complete")
async def complete_onboarding(answers: Dict[str, Any]):
    """Save onboarding answers."""
    try:
        from src.services.adaptive_onboarding_service import adaptive_onboarding
        adaptive_onboarding.save_answers(answers)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Complete onboarding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/onboarding/next")
async def get_next_question(request: Dict[str, Any]):
    """Get next onboarding question based on previous answers."""
    try:
        from src.services.adaptive_onboarding_service import adaptive_onboarding
        previous = request.get("previous_answers", {})
        question = adaptive_onboarding.get_next_question(previous)
        return {"question": question}
    except Exception as e:
        logger.error(f"Get next question failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thresholds")
async def get_thresholds():
    """Get learned thresholds."""
    try:
        from src.services.threshold_service import threshold_service
        return {"thresholds": threshold_service.get_all()}
    except Exception as e:
        logger.error(f"Get thresholds failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/thresholds/{name}/adjust")
async def adjust_threshold(name: str, feedback: Dict[str, str]):
    """Adjust threshold based on user feedback."""
    try:
        from src.services.threshold_service import threshold_service
        threshold_service.adjust(name, feedback.get("feedback"))
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Adjust threshold failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/questions/pending")
async def get_pending_questions():
    """Get all pending clarification questions."""
    try:
        from src.services.question_service import question_service
        questions = question_service.get_pending_questions()
        return {"questions": questions}
    except Exception as e:
        logger.error(f"Get questions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/questions/{question_id}/answer")
async def answer_question(question_id: int, answer: Dict[str, str]):
    """Answer a clarification question."""
    try:
        from src.services.question_service import question_service
        from src.services.confidence_service import confidence_service
        
        question_service.answer_question(question_id, answer.get("answer"))
        
        # If domain question, record feedback for learning
        if answer.get("type") == "domain_routing":
            confidence_service.record_routing_feedback(
                answer.get("keywords", ""),
                answer.get("suggested_domain", ""),
                answer.get("answer")
            )
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Answer question failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: int):
    """Mark task as complete and log patterns."""
    try:
        from src.services.energy_pattern_service import energy_pattern_service
        from src.services.priority_learning_service import priority_learning
        
        completed_at = datetime.now()
        
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tasks 
            SET status = 'completed', completed_at = ?
            WHERE id = ?
        """, (completed_at.isoformat(), task_id))
        
        conn.commit()
        conn.close()
        
        # Log completion for learning
        energy_pattern_service.log_completion(task_id, completed_at)
        priority_learning.learn_from_completions()
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Complete task failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/note-types")
async def get_note_types():
    """Get all note types."""
    try:
        from src.services.note_type_service import note_type_service
        return {"types": note_type_service.get_all_types()}
    except Exception as e:
        logger.error(f"Get note types failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/note-types")
async def add_note_type(type_data: Dict[str, str]):
    """Add custom note type."""
    try:
        from src.services.note_type_service import note_type_service
        note_type_service.add_type(
            type_data.get("name"),
            type_data.get("description", ""),
            type_data.get("icon", "📄")
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Add note type failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/energy-pattern")
async def get_energy_pattern():
    """Get learned energy pattern."""
    try:
        from src.services.energy_pattern_service import energy_pattern_service
        return energy_pattern_service.get_pattern_summary()
    except Exception as e:
        logger.error(f"Get energy pattern failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/priority-weights")
async def get_priority_weights():
    """Get learned priority weights."""
    try:
        from src.services.priority_learning_service import priority_learning
        return {"weights": priority_learning.get_all_weights()}
    except Exception as e:
        logger.error(f"Get priority weights failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _find_linked_notes(content: str) -> List[str]:
    """Extract wikilinks and find similar notes."""
    import re
    
    # Extract [[wikilinks]]
    wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
    
    # TODO: Add semantic search for similar notes
    
    return wikilinks


if __name__ == "__main__":
    import uvicorn
    
    # Ensure setup
    settings.ensure_directories()
    
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
