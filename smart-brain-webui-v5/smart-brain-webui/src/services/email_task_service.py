"""Email Task Service - handles tasks from email sources like BillBrain."""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

from src.config import settings
from src.models.workflow_state import ClusterNote, NoteType, Task, Priority, TaskStatus


class EmailTaskService:
    """Service for creating tasks from email sources with deduplication."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._model = None  # Lazy load
    
    @property
    def model(self):
        """Lazy load embedding model."""
        if self._model is None:
            logger.info("Loading embedding model for email task dedup...")
            self._model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            logger.success("Embedding model loaded")
        return self._model
    
    def create_task_from_email(
        self,
        action: str,
        sender: Optional[str] = None,
        subject: Optional[str] = None,
        priority: str = "medium",
        domain_hint: Optional[str] = None,
        deadline: Optional[str] = None,
        context: Optional[str] = None,
        first_step: Optional[str] = None,
        estimated_minutes: Optional[int] = None,
        source_email_id: Optional[str] = None
    ) -> Dict:
        """
        Create a task from an email action item.
        
        Returns:
            Dict with task_id, was_duplicate, assigned_domain, duplicate_of
        """
        logger.info(f"Creating email task: {action[:50]}...")
        
        # Build full task text with context
        task_text = action
        if sender:
            task_text = f"{action} (from {sender})"
        
        # Check for duplicates against existing tasks
        is_dupe, duplicate_id = self._check_duplicate(action)
        
        if is_dupe:
            logger.info(f"Duplicate detected - matches task #{duplicate_id}")
            return {
                "task_id": None,
                "was_duplicate": True,
                "duplicate_of": duplicate_id,
                "assigned_domain": None,
                "message": f"Duplicate of existing task #{duplicate_id}"
            }
        
        # Route to domain
        assigned_domain = self._route_to_domain(action, context, domain_hint)
        
        # Create the task
        task_id = self._insert_task(
            text=task_text,
            action=first_step or action,
            priority=priority,
            domain=assigned_domain,
            estimated_minutes=estimated_minutes,
            metadata={
                "source": "email",
                "sender": sender,
                "subject": subject,
                "deadline": deadline,
                "source_email_id": source_email_id
            }
        )
        
        logger.success(f"Created email task #{task_id} in domain '{assigned_domain}'")
        
        return {
            "task_id": task_id,
            "was_duplicate": False,
            "duplicate_of": None,
            "assigned_domain": assigned_domain,
            "message": "Task created successfully"
        }
    
    def _check_duplicate(self, action: str, threshold: float = 0.85) -> Tuple[bool, Optional[int]]:
        """
        Check if action is duplicate of existing open task.
        
        Returns:
            (is_duplicate, existing_task_id)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recent open tasks (last 30 days)
        cursor.execute("""
            SELECT id, action FROM tasks
            WHERE status = 'open'
            AND created_at > datetime('now', '-30 days')
        """)
        
        existing = cursor.fetchall()
        conn.close()
        
        if not existing:
            return False, None
        
        # Encode new action
        new_embedding = self.model.encode([action])[0]
        
        # Encode existing actions
        existing_ids = [row[0] for row in existing]
        existing_actions = [row[1] for row in existing]
        existing_embeddings = self.model.encode(existing_actions)
        
        # Calculate similarities
        similarities = np.inner(new_embedding, existing_embeddings)
        
        # Find max similarity
        max_idx = np.argmax(similarities)
        max_sim = similarities[max_idx]
        
        if max_sim >= threshold:
            return True, existing_ids[max_idx]
        
        return False, None
    
    def _route_to_domain(
        self, 
        action: str, 
        context: Optional[str],
        domain_hint: Optional[str]
    ) -> str:
        """Route task to appropriate domain."""
        from src.services.route_service import route_service
        from src.services.domain_service import domain_service
        
        # If valid domain hint provided, use it
        if domain_hint:
            domains = domain_service.get_all_domains()
            valid_paths = [d['path'] for d in domains]
            
            # Check exact match
            if domain_hint in valid_paths:
                return domain_hint
            
            # Check partial match (e.g., "work" matches "work/marriott")
            for path in valid_paths:
                if domain_hint in path or path.startswith(domain_hint):
                    return path
        
        # Use route service with a pseudo-note
        content = action
        if context:
            content = f"{action}\n\nContext: {context}"
        
        pseudo_note = ClusterNote(
            title=action[:100],
            content=content,
            type=NoteType.NOTE,
            keywords=[]
        )
        
        # Route without asking clarification questions for email tasks
        routed = route_service.route(pseudo_note, ask_if_uncertain=False)
        
        return routed.get("domain", "personal")
    
    def _insert_task(
        self,
        text: str,
        action: str,
        priority: str,
        domain: str,
        estimated_minutes: Optional[int],
        metadata: Dict
    ) -> int:
        """Insert task into database."""
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tasks (
                text, action, status, priority, 
                estimated_duration_minutes, domain, 
                created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            text,
            action,
            "open",
            priority,
            estimated_minutes,
            domain,
            datetime.now().isoformat(),
            json.dumps(metadata)
        ))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return task_id
    
    def get_email_tasks(self, limit: int = 50) -> List[Dict]:
        """Get tasks created from email sources."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, text, action, status, priority, domain, created_at, metadata
            FROM tasks
            WHERE metadata LIKE '%"source": "email"%'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                "id": row[0],
                "text": row[1],
                "action": row[2],
                "status": row[3],
                "priority": row[4],
                "domain": row[5],
                "created_at": row[6],
                "metadata": row[7]
            })
        
        conn.close()
        return tasks


# Global instance
email_task_service = EmailTaskService()
