"""FastAPI backend for Smart Second Brain."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import sqlite3
from loguru import logger
import uuid

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

@app.get("/api/llm/status")
async def llm_status():
    """Check which LLM provider is active."""
    from src.llm.llm_service import llm_service
    from src.config import settings
    
    # Check if Azure is being used
    use_azure = getattr(settings, 'use_azure', False)
    azure_configured = False
    if llm_service.azure:
        azure_configured = getattr(llm_service.azure, 'is_configured', False)
    
    return {
        "use_azure_setting": use_azure,
        "azure_configured": azure_configured,
        "azure_client": llm_service.azure is not None,
        "ollama_client": llm_service.ollama is not None
    }
    
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
        
        # Route to domain - returns dict
        routed = route_service.route(cluster)
        
        # Find linked notes (search for [[wikilinks]] or similar notes)
        linked = _find_linked_notes(note.content)
        
        # FIX: Use .get() since route_service returns dict, not object
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


class TaskClarification(BaseModel):
    task_index: int
    action: str
    original_text: str
    question: str


class NoteWithClarifications(BaseModel):
    note_id: int
    note: NoteResponse
    clarifications_needed: List[TaskClarification]
    pending_tasks: int


class ClarificationAnswers(BaseModel):
    note_id: int
    answers: Dict[int, str]  # task_index -> answer


@app.post("/api/notes", response_model=NoteWithClarifications)
async def create_note(note: NoteSave):
    """Save note and return any clarification questions for ambiguous tasks."""
    try:
        from src.models.workflow_state import RoutedNote, NoteType
        from src.services.task_extraction_service import task_extraction_service
        
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
        conn.close()
        
        # Extract tasks - now returns (tasks, questions)
        tasks, questions = task_extraction_service.extract_tasks(note.content, note_id, note.domain)
        
        # Store tasks temporarily (with pending status if they need clarification)
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        for task in tasks:
            needs_clarification = task.metadata.get("is_ambiguous", False)
            status = "pending_clarification" if needs_clarification else "open"
            project_id = task.metadata.get("suggested_project_id")
            
            cursor.execute("""
                INSERT INTO tasks (text, action, status, priority, estimated_duration_minutes, domain, source_note_id, project_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.text,
                task.action,
                status,
                task.priority.value,
                task.estimated_duration_minutes,
                task.domain,
                task.source_note_id,
                project_id
            ))
            
            # Learn keywords if assigned to project
            if project_id:
                from src.services.project_service import project_service
                project_service.learn_keywords(project_id, f"{task.action} {task.text}")
        
        conn.commit()
        conn.close()
        
        note_response = NoteResponse(
            id=row[0],
            title=row[1],
            content=row[2],
            domain=row[3],
            type=row[4],
            file_path=row[5],
            created_at=row[6],
            updated_at=row[7]
        )
        
        clarifications = [
            TaskClarification(
                task_index=q["task_index"],
                action=q["action"],
                original_text=q.get("original_text", ""),
                question=q["question"]
            )
            for q in questions
        ]
        
        logger.info(f"Saved note with {len(tasks)} tasks, {len(clarifications)} need clarification")
        
        return NoteWithClarifications(
            note_id=note_id,
            note=note_response,
            clarifications_needed=clarifications,
            pending_tasks=len(tasks)
        )
        
    except Exception as e:
        logger.error(f"Save failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notes/{note_id}/clarify")
async def apply_clarifications(note_id: int, data: ClarificationAnswers):
    """Apply clarification answers to pending tasks."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        # Get pending tasks for this note, ordered by id (same order as extracted)
        cursor.execute("""
            SELECT id, text, action
            FROM tasks
            WHERE source_note_id = ? AND status = 'pending_clarification'
            ORDER BY id ASC
        """, (note_id,))
        
        pending_tasks = cursor.fetchall()
        
        for idx, (task_id, text, action) in enumerate(pending_tasks):
            if idx in data.answers:
                answer = data.answers[idx]
                # Update task with clarification
                new_text = f"{text}\n→ {answer}"
                cursor.execute("""
                    UPDATE tasks
                    SET text = ?, status = 'open'
                    WHERE id = ?
                """, (new_text, task_id))
            else:
                # No answer provided, just mark as open
                cursor.execute("""
                    UPDATE tasks SET status = 'open' WHERE id = ?
                """, (task_id,))
        
        conn.commit()
        conn.close()
        
        logger.success(f"Applied {len(data.answers)} clarifications to note {note_id}")
        return {"status": "ok", "clarifications_applied": len(data.answers)}
        
    except Exception as e:
        logger.error(f"Clarification failed: {e}")
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


# FIX: Single /api/domains endpoint that returns proper dict format
@app.get("/api/domains")
async def get_domains():
    """Get user's domains with full metadata."""
    try:
        from src.services.domain_service import domain_service
        domains = domain_service.get_all_domains()
        
        # If no user domains exist yet, return defaults from settings
        if not domains:
            # Convert settings domains to proper format
            default_colors = {
                'work/marriott': 'blue',
                'work/mansour': 'green', 
                'work/konstellate': 'green',
                'personal': 'purple',
                'learning': 'amber',
                'admin': 'gray'
            }
            domains = [
                {
                    'path': d,
                    'name': d.split('/')[-1].title(),
                    'color': default_colors.get(d, 'slate'),
                    'target': 0,
                    'keywords': []
                }
                for d in settings.domains_list
            ]
        
        return {"domains": domains}
    except Exception as e:
        logger.error(f"Get domains failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TaskResponse(BaseModel):
    id: int
    text: str
    action: str
    status: str
    priority: str
    estimated_duration_minutes: Optional[int]
    domain: str
    source_note_id: Optional[int]  # Changed from int to Optional[int]
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


@app.get("/api/stats/today")
async def get_today_stats():
    """Get today's gamification stats."""
    from datetime import datetime, timedelta
    
    conn = sqlite3.connect(settings.sqlite_db_path)
    cursor = conn.cursor()
    
    today = datetime.now().date().isoformat()
    
    # Completed today
    cursor.execute("""
        SELECT COUNT(*) FROM tasks 
        WHERE status = 'completed' AND DATE(completed_at) = ?
    """, (today,))
    completed_today = cursor.fetchone()[0] or 0
    
    # Total for today (from daily plan - top 5)
    cursor.execute("""
        SELECT COUNT(*) FROM tasks WHERE status = 'open'
    """)
    total_open = cursor.fetchone()[0] or 0
    total_today = min(5, total_open) + completed_today
    
    # Calculate XP (simplified)
    cursor.execute("""
        SELECT priority, estimated_duration_minutes FROM tasks 
        WHERE status = 'completed' AND DATE(completed_at) = ?
    """, (today,))
    xp_today = 0
    for row in cursor.fetchall():
        priority, duration = row
        base = {'high': 100, 'medium': 50, 'low': 20}.get(priority, 50)
        duration_bonus = ((duration or 30) // 15) * 10
        xp_today += base + duration_bonus
    
    # Calculate streak
    streak = 0
    check_date = datetime.now().date()
    while True:
        cursor.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE status = 'completed' AND DATE(completed_at) = ?
        """, (check_date.isoformat(),))
        count = cursor.fetchone()[0] or 0
        if count > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    
    conn.close()
    
    return {
        "completed_today": completed_today,
        "total_today": max(total_today, 1),
        "xp_today": xp_today,
        "streak": streak
    }


# === PROJECT ENDPOINTS ===

class ProjectCreate(BaseModel):
    name: str
    domain: str
    description: Optional[str] = ""
    keywords: Optional[str] = ""


class ProjectResponse(BaseModel):
    id: int
    name: str
    domain: str
    description: Optional[str]
    status: str
    keywords: List[str]
    task_count: int


@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects(domain: Optional[str] = None):
    """List all projects, optionally filtered by domain."""
    from src.services.project_service import project_service
    projects = project_service.get_projects(domain)
    return [
        ProjectResponse(
            id=p['id'],
            name=p['name'],
            domain=p['domain'],
            description=p['description'],
            status=p['status'],
            keywords=p['keywords'],
            task_count=p['task_count']
        )
        for p in projects
    ]


@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    """Create a new project."""
    from src.services.project_service import project_service
    project_id = project_service.create_project(
        project.name, project.domain, project.description, project.keywords
    )
    
    return ProjectResponse(
        id=project_id,
        name=project.name,
        domain=project.domain,
        description=project.description,
        status="active",
        keywords=project.keywords.split(',') if project.keywords else [],
        task_count=0
    )


@app.get("/api/projects/{project_id}/tasks")
async def get_project_tasks(project_id: int):
    """Get tasks for a specific project."""
    conn = sqlite3.connect(settings.sqlite_db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, text, action, status, priority, estimated_duration_minutes, domain
        FROM tasks
        WHERE project_id = ? AND status = 'open'
        ORDER BY priority DESC, created_at ASC
    """, (project_id,))
    
    tasks = [
        {
            'id': row[0],
            'text': row[1],
            'action': row[2],
            'status': row[3],
            'priority': row[4],
            'estimated_duration_minutes': row[5],
            'domain': row[6]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return {"tasks": tasks}


@app.post("/api/tasks/{task_id}/assign-project")
async def assign_task_to_project(task_id: int, data: Dict[str, int]):
    """Assign a task to a project."""
    from src.services.project_service import project_service
    project_id = data.get("project_id")
    
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id required")
    
    project_service.assign_task_to_project(task_id, project_id)
    return {"status": "ok"}


@app.get("/api/projects/validate/{domain:path}")
async def validate_project_assignments(domain: str):
    """Check for misassigned tasks in a domain."""
    from src.services.project_service import project_service
    suggestions = project_service.validate_assignments(domain)
    return {"suggestions": suggestions}


@app.get("/api/hierarchy/{domain:path}")
async def get_domain_hierarchy(domain: str):
    """Get full hierarchy: domain -> projects -> tasks."""
    from src.services.project_service import project_service
    
    conn = sqlite3.connect(settings.sqlite_db_path)
    cursor = conn.cursor()
    
    projects = project_service.get_projects(domain)
    
    result = {
        "domain": domain,
        "projects": [],
        "unassigned_tasks": []
    }
    
    for project in projects:
        cursor.execute("""
            SELECT id, action, text, priority, estimated_duration_minutes, status
            FROM tasks
            WHERE project_id = ? AND status IN ('open', 'pending_clarification')
            ORDER BY priority DESC, created_at ASC
        """, (project['id'],))
        
        tasks = [
            {
                'id': row[0],
                'action': row[1],
                'text': row[2],
                'priority': row[3],
                'estimated_duration_minutes': row[4],
                'status': row[5]
            }
            for row in cursor.fetchall()
        ]
        
        result["projects"].append({
            **project,
            "tasks": tasks
        })
    
    # Get unassigned tasks
    cursor.execute("""
        SELECT id, action, text, priority, estimated_duration_minutes, status
        FROM tasks
        WHERE domain = ? AND project_id IS NULL AND status IN ('open', 'pending_clarification')
        ORDER BY created_at DESC
    """, (domain,))
    
    result["unassigned_tasks"] = [
        {
            'id': row[0],
            'action': row[1],
            'text': row[2],
            'priority': row[3],
            'estimated_duration_minutes': row[4],
            'status': row[5]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return result


# =============================================================================
# EMAIL TASK INTEGRATION (for BillBrain and other email sources)
# =============================================================================

class EmailTaskCreate(BaseModel):
    """Request model for creating a task from email."""
    action: str
    sender: Optional[str] = None
    subject: Optional[str] = None
    priority: str = "medium"
    domain_hint: Optional[str] = None
    deadline: Optional[str] = None
    context: Optional[str] = None
    first_step: Optional[str] = None
    estimated_minutes: Optional[int] = None
    source_email_id: Optional[str] = None


class EmailTaskResponse(BaseModel):
    """Response model for email task creation."""
    task_id: Optional[int]
    was_duplicate: bool
    duplicate_of: Optional[int]
    assigned_domain: Optional[str]
    message: str


class EmailTaskBatchCreate(BaseModel):
    """Batch create multiple email tasks."""
    tasks: List[EmailTaskCreate]


class EmailTaskBatchResponse(BaseModel):
    """Response for batch creation."""
    created: int
    duplicates: int
    results: List[EmailTaskResponse]


@app.post("/api/tasks/from-email", response_model=EmailTaskResponse)
async def create_task_from_email(task: EmailTaskCreate):
    """
    Create a task from an email source (BillBrain, etc).
    
    This endpoint:
    - Checks for duplicates against existing open tasks
    - Routes to appropriate domain (uses hint if provided)
    - Creates the task with email metadata
    
    Use this instead of direct DB inserts to maintain data integrity.
    """
    try:
        from src.services.email_task_service import email_task_service
        
        result = email_task_service.create_task_from_email(
            action=task.action,
            sender=task.sender,
            subject=task.subject,
            priority=task.priority,
            domain_hint=task.domain_hint,
            deadline=task.deadline,
            context=task.context,
            first_step=task.first_step,
            estimated_minutes=task.estimated_minutes,
            source_email_id=task.source_email_id
        )
        
        return EmailTaskResponse(**result)
        
    except Exception as e:
        logger.error(f"Email task creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/from-email/batch", response_model=EmailTaskBatchResponse)
async def create_tasks_from_email_batch(batch: EmailTaskBatchCreate):
    """
    Create multiple tasks from email sources in one call.
    
    Returns summary of created vs duplicate tasks.
    """
    try:
        from src.services.email_task_service import email_task_service
        
        results = []
        created = 0
        duplicates = 0
        
        for task in batch.tasks:
            result = email_task_service.create_task_from_email(
                action=task.action,
                sender=task.sender,
                subject=task.subject,
                priority=task.priority,
                domain_hint=task.domain_hint,
                deadline=task.deadline,
                context=task.context,
                first_step=task.first_step,
                estimated_minutes=task.estimated_minutes,
                source_email_id=task.source_email_id
            )
            
            results.append(EmailTaskResponse(**result))
            
            if result["was_duplicate"]:
                duplicates += 1
            else:
                created += 1
        
        return EmailTaskBatchResponse(
            created=created,
            duplicates=duplicates,
            results=results
        )
        
    except Exception as e:
        logger.error(f"Batch email task creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks/from-email")
async def list_email_tasks(limit: int = 50):
    """List tasks that were created from email sources."""
    try:
        from src.services.email_task_service import email_task_service
        tasks = email_task_service.get_email_tasks(limit=limit)
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:
        logger.error(f"List email tasks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FINANCIAL API ====================

# --- Pydantic Models for Financial ---

class BillCreate(BaseModel):
    name: str
    amount: float
    due_date: Optional[str] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    source: Optional[str] = None
    source_email_id: Optional[str] = None
    notes: Optional[str] = None


class BillResponse(BaseModel):
    id: int
    name: str
    amount: float
    due_date: Optional[str]
    category: Optional[str]
    vendor: Optional[str]
    status: str
    paid_date: Optional[str]
    paid_amount: Optional[float]
    notes: Optional[str]
    created_at: str


class SubscriptionCreate(BaseModel):
    name: str
    amount: float
    frequency: str = "monthly"
    category: Optional[str] = None
    vendor: Optional[str] = None
    start_date: Optional[str] = None
    next_due_date: Optional[str] = None
    auto_pay: bool = False
    notes: Optional[str] = None


class SubscriptionResponse(BaseModel):
    id: int
    name: str
    amount: float
    frequency: str
    category: Optional[str]
    vendor: Optional[str]
    status: str
    next_due_date: Optional[str]
    auto_pay: bool
    notes: Optional[str]


class LoanCreate(BaseModel):
    name: str
    lender: Optional[str] = None
    loan_type: Optional[str] = None
    original_principal: float
    current_balance: Optional[float] = None
    interest_rate: float
    term_months: int
    start_date: str
    monthly_payment: Optional[float] = None
    payment_due_day: int = 1
    notes: Optional[str] = None


class LoanResponse(BaseModel):
    id: int
    name: str
    lender: Optional[str]
    loan_type: Optional[str]
    original_principal: float
    current_balance: float
    interest_rate: float
    term_months: int
    start_date: str
    monthly_payment: float
    payment_due_day: int
    status: str
    notes: Optional[str]


class LoanPaymentCreate(BaseModel):
    amount: float
    payment_date: Optional[str] = None
    extra_principal: float = 0


# --- Bills Endpoints ---

@app.post("/api/financial/bills", response_model=BillResponse)
async def create_bill(bill: BillCreate):
    """Create a new bill."""
    try:
        from src.services.financial_service import financial_service
        bill_id = financial_service.create_bill(bill.model_dump())
        bills = financial_service.get_bills()
        return next(b for b in bills if b["id"] == bill_id)
    except Exception as e:
        logger.error(f"Create bill failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/financial/bills")
async def list_bills(status: Optional[str] = None, limit: int = 50):
    """List bills, optionally filtered by status."""
    try:
        from src.services.financial_service import financial_service
        bills = financial_service.get_bills(status=status, limit=limit)
        return {"bills": bills, "count": len(bills)}
    except Exception as e:
        logger.error(f"List bills failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/financial/bills/upcoming")
async def upcoming_bills(days: int = 14):
    """Get bills due in the next N days."""
    try:
        from src.services.financial_service import financial_service
        bills = financial_service.get_upcoming_bills(days=days)
        total = sum(b["amount"] for b in bills)
        return {"bills": bills, "count": len(bills), "total": total}
    except Exception as e:
        logger.error(f"Upcoming bills failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/financial/bills/{bill_id}/pay")
async def mark_bill_paid(bill_id: int, paid_amount: float, paid_date: Optional[str] = None):
    """Mark a bill as paid."""
    try:
        from src.services.financial_service import financial_service
        financial_service.mark_bill_paid(bill_id, paid_amount, paid_date)
        return {"status": "ok", "message": f"Bill #{bill_id} marked as paid"}
    except Exception as e:
        logger.error(f"Mark bill paid failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Subscriptions Endpoints ---

@app.post("/api/financial/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(sub: SubscriptionCreate):
    """Create a new subscription."""
    try:
        from src.services.financial_service import financial_service
        sub_id = financial_service.create_subscription(sub.model_dump())
        subs = financial_service.get_subscriptions()
        return next(s for s in subs if s["id"] == sub_id)
    except Exception as e:
        logger.error(f"Create subscription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/financial/subscriptions")
async def list_subscriptions(status: Optional[str] = None):
    """List subscriptions."""
    try:
        from src.services.financial_service import financial_service
        subs = financial_service.get_subscriptions(status=status)
        monthly_total = financial_service.get_monthly_subscription_total()
        return {"subscriptions": subs, "count": len(subs), "monthly_total": monthly_total}
    except Exception as e:
        logger.error(f"List subscriptions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Loans Endpoints ---

@app.post("/api/financial/loans", response_model=LoanResponse)
async def create_loan(loan: LoanCreate):
    """Create a new loan."""
    try:
        from src.services.financial_service import financial_service
        loan_id = financial_service.create_loan(loan.model_dump())
        loans = financial_service.get_loans()
        return next(l for l in loans if l["id"] == loan_id)
    except Exception as e:
        logger.error(f"Create loan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/financial/loans")
async def list_loans(status: Optional[str] = None):
    """List loans."""
    try:
        from src.services.financial_service import financial_service
        loans = financial_service.get_loans(status=status)
        total_debt = sum(l["current_balance"] or 0 for l in loans)
        monthly_payments = sum(l["monthly_payment"] or 0 for l in loans)
        return {"loans": loans, "count": len(loans), "total_debt": total_debt, "monthly_payments": monthly_payments}
    except Exception as e:
        logger.error(f"List loans failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/financial/loans/{loan_id}/payment")
async def record_loan_payment(loan_id: int, payment: LoanPaymentCreate):
    """Record a loan payment."""
    try:
        from src.services.financial_service import financial_service
        result = financial_service.record_loan_payment(
            loan_id=loan_id,
            amount=payment.amount,
            payment_date=payment.payment_date,
            extra_principal=payment.extra_principal
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Record loan payment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/financial/loans/{loan_id}/amortization")
async def get_amortization(loan_id: int):
    """Get amortization schedule for a loan."""
    try:
        from src.services.financial_service import financial_service
        schedule = financial_service.get_amortization_schedule(loan_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Loan not found")
        total_interest = sum(p["interest"] for p in schedule)
        return {"schedule": schedule, "total_interest": round(total_interest, 2), "payments": len(schedule)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get amortization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Financial Dashboard ---

@app.get("/api/financial/summary")
async def financial_summary():
    """Get overall financial summary."""
    try:
        from src.services.financial_service import financial_service
        summary = financial_service.get_financial_summary()
        return summary
    except Exception as e:
        logger.error(f"Financial summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# BRAIN DUMP PROCESSING
# ============================================================

class BrainDumpRequest(BaseModel):
    content: str
    domain: Optional[str] = "work/marriott"


class ClarifyAnswers(BaseModel):
    answers: Dict[str, str]  # question_text -> answer


@app.post("/api/brain-dump/analyze")
async def analyze_brain_dump(request: BrainDumpRequest):
    """
    Analyze a brain dump and return structured data.
    Detects projects, people, tasks, and ambiguous items.
    """
    try:
        from src.services.brain_dump_service import brain_dump_service
        from src.services.project_service import project_service
        
        # Get existing projects for this domain to help with consolidation suggestions
        existing_projects = []
        try:
            existing = project_service.get_projects_for_domain(request.domain)
            existing_projects = [p['name'] for p in existing]
        except Exception as e:
            logger.warning(f"Could not get existing projects: {e}")
        
        result = brain_dump_service.process_brain_dump(
            request.content, 
            request.domain,
            existing_projects=existing_projects
        )
        return result
    except Exception as e:
        logger.error(f"Brain dump analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/brain-dump/suggest-projects")
async def suggest_projects_from_dump(request: BrainDumpRequest):
    """Suggest new projects based on brain dump content."""
    try:
        from src.services.brain_dump_service import brain_dump_service
        from src.services.project_service import project_service
        
        # Get existing projects for this domain
        existing = project_service.get_projects_for_domain(request.domain)
        existing_names = [p['name'] for p in existing]
        
        suggestions = brain_dump_service.suggest_projects_from_content(
            request.content, 
            existing_names
        )
        return {"suggestions": suggestions, "existing_projects": existing_names}
    except Exception as e:
        logger.error(f"Project suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/brain-dump/save")
async def save_brain_dump_items(data: Dict[str, Any]):
    try:
        from src.services.project_service import project_service
        
        # 1. Clean Top-Level Domain
        raw_domain = data.get("domain", "personal")
        domain = str(raw_domain[0] if isinstance(raw_domain, list) else raw_domain)

        items = data.get("items", [])
        org_choices = data.get("organization_choices", {})
        new_projects = org_choices.get("create_projects", [])
        consolidations = data.get("consolidations", [])
        hierarchies = data.get("hierarchies", [])
        
        # Build consolidation mapping
        name_mapping = {}
        for cons in consolidations:
            suggested = cons.get("suggested_name")
            if isinstance(suggested, list): suggested = suggested[0]
            for variant in cons.get("variants", []):
                name_mapping[str(variant).lower()] = str(suggested)
        
        # 2. Populate Project Map with "List Insurance"
        project_map = {}
        for proj_name in new_projects:
            actual_name = name_mapping.get(proj_name.lower(), proj_name)
            if actual_name not in project_map:
                p_id = project_service.create_project(name=actual_name, domain=domain, description="Auto-created")
                # Flatten p_id if it's a list
                project_map[actual_name] = p_id[0] if isinstance(p_id, list) else p_id
        
        existing_projects = project_service.get_projects_for_domain(domain)
        for p in existing_projects:
            p_id, p_name = p['id'], p['name']
            if p_name not in project_map:
                # Flatten p_id if it's a list
                project_map[p_name] = p_id[0] if isinstance(p_id, list) else p_id
        
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        # Apply hierarchies (using flattened IDs)
        for hier in hierarchies:
            child_id = project_map.get(hier.get("child_project"))
            parent_id = project_map.get(hier.get("parent_project"))
            if child_id and parent_id:
                cursor.execute("UPDATE projects SET parent_project_id = ? WHERE id = ?", 
                             (parent_id[0] if isinstance(parent_id, list) else parent_id, 
                              child_id[0] if isinstance(child_id, list) else child_id))
        
        saved_counts = {"task": 0, "note": 0, "idea": 0, "question": 0, "decision": 0, "reference": 0}
        
        for item in items:
            item_type = item.get("item_type", "task")
            action = item.get("action", "")
            original_text = item.get("original_text", "")

            # --- RESOLVE & FLATTEN PROJECT ID ---
            raw_proj_name = item.get("project") or item.get("project_name") or ""
            if isinstance(raw_proj_name, list): raw_proj_name = raw_proj_name[0] if raw_proj_name else ""
            
            final_proj_name = name_mapping.get(str(raw_proj_name).lower(), raw_proj_name)
            current_project_id = project_map.get(final_proj_name)
            
            # FINAL INSURANCE: If current_project_id is still a list, extract the first element
            if isinstance(current_project_id, list):
                current_project_id = current_project_id[0] if current_project_id else None

            if item_type == "task":
                # Priority/Duration Sanitization (Already good in your code)
                priority_val = item.get("priority", "medium")
                if isinstance(priority_val, list): priority_val = priority_val[0]
                
                duration_val = item.get("estimated_minutes", 30)
                if isinstance(duration_val, list): duration_val = duration_val[0]
                try: duration_val = int(duration_val)
                except: duration_val = 30

                cursor.execute("""
                    INSERT INTO tasks (text, action, status, priority, estimated_duration_minutes, domain, project_id, metadata)
                    VALUES (?, ?, 'open', ?, ?, ?, ?, ?)
                """, (original_text, action, str(priority_val), duration_val, domain, current_project_id, str({"item_type": "task", "from_brain_dump": True})))
                saved_counts["task"] += 1
                
            elif item_type == "idea":
                # THIS IS WHERE PARAMETER 4 WAS FAILING
                cursor.execute("""
                    INSERT INTO tasks (text, action, status, priority, domain, project_id, metadata)
                    VALUES (?, ?, 'open', 'low', ?, ?, ?)
                """, (original_text, action, domain, current_project_id, str({"item_type": "idea", "tags": ["idea"], "from_brain_dump": True})))
                saved_counts["idea"] += 1
                
            # ... (rest of your note/question/decision blocks remain the same) ...
            elif item_type == "note":
                cursor.execute("INSERT INTO notes (title, content, domain, type, file_path, source_file) VALUES (?, ?, ?, 'Note', ?, 'brain_dump')",
                             (action[:100], action, domain, f"bd_{uuid.uuid4().hex[:8]}.md"))
                saved_counts["note"] += 1

        conn.commit()
        conn.close()
        return {"saved": saved_counts, "total": sum(saved_counts.values())}
        
    except Exception as e:
        logger.error(f"Save brain dump failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/brain-dump/consolidate-projects")
async def consolidate_projects(data: Dict[str, Any]):
    """
    Apply project consolidation - merge/rename projects.
    
    Expected data:
    {
        "domain": "work/marriott",
        "consolidations": [
            {
                "variants": ["TIP AI", "tip.ai", "TIP AI stuff"],
                "suggested_name": "TIP AI",
                "consolidation_type": "merge"
            }
        ]
    }
    """
    try:
        from src.services.project_service import project_service
        
        raw_domain = data.get("domain", "personal")
        domain = raw_domain[0] if isinstance(raw_domain, list) else raw_domain
        domain = str(domain)
        
        consolidations = data.get("consolidations", [])
        
        results = []
        
        for cons in consolidations:
            variants = cons.get("variants", [])
            suggested_name = cons.get("suggested_name")
            cons_type = cons.get("consolidation_type", "merge")
            
            if cons_type == "merge":
                # Find or create the target project
                existing = project_service.get_projects_for_domain(domain)
                target_id = None
                variant_ids = []
                
                for proj in existing:
                    if proj['name'].lower() == suggested_name.lower():
                        target_id = proj['id']
                    elif proj['name'].lower() in [v.lower() for v in variants]:
                        variant_ids.append(proj['id'])
                
                if not target_id and variant_ids:
                    # Rename first variant to suggested name
                    target_id = variant_ids[0]
                    project_service.update_project(target_id, name=suggested_name)
                    variant_ids = variant_ids[1:]
                
                # Move tasks from variant projects to target
                if target_id and variant_ids:
                    conn = sqlite3.connect(settings.sqlite_db_path)
                    cursor = conn.cursor()
                    
                    for vid in variant_ids:
                        cursor.execute("""
                            UPDATE tasks SET project_id = ? WHERE project_id = ?
                        """, (target_id, vid))
                        
                        # Delete the old project
                        cursor.execute("DELETE FROM projects WHERE id = ?", (vid,))
                    
                    conn.commit()
                    conn.close()
                
                results.append({
                    "action": "merged",
                    "variants": variants,
                    "target": suggested_name,
                    "tasks_moved": len(variant_ids)
                })
                
            elif cons_type == "rename":
                existing = project_service.get_projects_for_domain(domain)
                for proj in existing:
                    if proj['name'] in variants:
                        project_service.update_project(proj['id'], name=suggested_name)
                        results.append({
                            "action": "renamed",
                            "from": proj['name'],
                            "to": suggested_name
                        })
                        break
        
        return {"results": results, "consolidations_processed": len(results)}
        
    except Exception as e:
        logger.error(f"Project consolidation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks/by-person")
async def get_tasks_by_person(domain: Optional[str] = None):
    """Get tasks grouped by associated person."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT id, text, action, status, priority, 
                   estimated_duration_minutes, domain, project_id, metadata
            FROM tasks
            WHERE status = 'open'
        """
        params = []
        
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Group by person from metadata
        by_person = {"unassigned": []}
        
        for row in rows:
            task = {
                "id": row[0],
                "text": row[1],
                "action": row[2],
                "status": row[3],
                "priority": row[4],
                "estimated_duration_minutes": row[5],
                "domain": row[6],
                "project_id": row[7]
            }
            
            # Parse metadata for person
            try:
                import ast
                metadata = ast.literal_eval(row[8]) if row[8] else {}
                person = metadata.get("person")
            except:
                person = None
            
            if person:
                if person not in by_person:
                    by_person[person] = []
                by_person[person].append(task)
            else:
                by_person["unassigned"].append(task)
        
        return {"by_person": by_person}
        
    except Exception as e:
        logger.error(f"Get tasks by person failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks/ambiguous")
async def get_ambiguous_tasks():
    """Get tasks that were marked as ambiguous and may need clarification."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, text, action, domain, metadata
            FROM tasks
            WHERE status = 'open'
            AND metadata LIKE '%"is_ambiguous": true%'
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in rows:
            try:
                import ast
                metadata = ast.literal_eval(row[4]) if row[4] else {}
            except:
                metadata = {}
            
            tasks.append({
                "id": row[0],
                "text": row[1],
                "action": row[2],
                "domain": row[3],
                "clarifying_question": metadata.get("clarifying_question", "What does this mean?")
            })
        
        return {"ambiguous_tasks": tasks, "count": len(tasks)}
        
    except Exception as e:
        logger.error(f"Get ambiguous tasks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/questions")
async def list_questions(status: Optional[str] = None, domain: Optional[str] = None):
    """List all questions, optionally filtered."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT id, question, answer, status, domain, created_at, answered_at, metadata
            FROM questions WHERE 1=1
        """
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
        
        return {
            "questions": [
                {
                    "id": row[0],
                    "question": row[1],
                    "answer": row[2],
                    "status": row[3],
                    "domain": row[4],
                    "created_at": row[5],
                    "answered_at": row[6],
                    "metadata": row[7]
                }
                for row in rows
            ],
            "count": len(rows)
        }
    except Exception as e:
        logger.error(f"List questions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/questions/{question_id}/answer")
async def answer_open_question(question_id: int, data: Dict[str, str]):
    """Answer an open question from brain dump."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE questions
            SET answer = ?, status = 'answered', answered_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (data.get("answer", ""), question_id))
        
        conn.commit()
        conn.close()
        
        return {"status": "ok", "id": question_id}
    except Exception as e:
        logger.error(f"Answer question failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/decisions")
async def list_decisions(domain: Optional[str] = None):
    """List all decisions, optionally filtered by domain."""
    try:
        conn = sqlite3.connect(settings.sqlite_db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT id, title, description, domain, created_at, metadata
            FROM decisions WHERE 1=1
        """
        params = []
        
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return {
            "decisions": [
                {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "domain": row[3],
                    "created_at": row[4],
                    "metadata": row[5]
                }
                for row in rows
            ],
            "count": len(rows)
        }
    except Exception as e:
        logger.error(f"List decisions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== WORK CONTEXT / INTERVIEW ENDPOINTS =====

@app.get("/api/work-context/interview/status")
async def get_interview_status():
    """Get interview progress."""
    try:
        from src.services.systems_interview_service import work_context
        status = work_context.get_interview_status()
        return status
    except Exception as e:
        logger.error(f"Get interview status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/work-context/interview/next")
async def get_next_interview_question():
    """Get next interview question."""
    try:
        from src.services.systems_interview_service import work_context
        question = work_context.get_next_interview_question()
        return {"question": question, "complete": question is None}
    except Exception as e:
        logger.error(f"Get next question failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/work-context/interview/answer")
async def save_interview_answer(data: Dict[str, Any]):
    """Save interview answer."""
    try:
        from src.services.systems_interview_service import work_context
        question_id = data.get("question_id")
        answer = data.get("answer")
        
        if not question_id or answer is None:
            raise HTTPException(status_code=400, detail="question_id and answer required")
        
        result = work_context.save_interview_answer(question_id, answer)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save interview answer failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/work-context/interview/reset")
async def reset_interview():
    """Reset interview to start fresh."""
    try:
        from src.services.systems_interview_service import work_context
        work_context.reset_interview()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Reset interview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/work-context")
async def get_work_context():
    """Get all work context entries."""
    try:
        from src.services.systems_interview_service import work_context
        entries = work_context.get_all_context()
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"Get work context failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/work-context/extraction")
async def get_extraction_context():
    """Get context for brain dump extraction."""
    try:
        from src.services.systems_interview_service import work_context
        context = work_context.get_context_for_extraction()
        return context
    except Exception as e:
        logger.error(f"Get extraction context failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/work-context/entity")
async def add_work_context_entity(data: Dict[str, Any]):
    """Add discovered entity to work context."""
    try:
        from src.services.systems_interview_service import work_context
        entity_id = work_context.add_discovered_entity(
            entity_type=data.get("type"),
            name=data.get("name"),
            parent_name=data.get("parent_name"),
            description=data.get("description"),
            confirmed=data.get("confirmed", False)
        )
        return {"id": entity_id, "status": "ok"}
    except Exception as e:
        logger.error(f"Add entity failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/work-context/entity/{entity_id}/confirm")
async def confirm_work_context_entity(entity_id: int):
    """Confirm a discovered entity."""
    try:
        from src.services.systems_interview_service import work_context
        work_context.confirm_entity(entity_id)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Confirm entity failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/work-context/unconfirmed")
async def get_unconfirmed_entities():
    """Get unconfirmed entities discovered from brain dumps."""
    try:
        from src.services.systems_interview_service import work_context
        entities = work_context.get_unconfirmed_entities()
        return {"entities": entities, "count": len(entities)}
    except Exception as e:
        logger.error(f"Get unconfirmed entities failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
