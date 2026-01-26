"""Question queue for clarifications including task ambiguity."""

import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

from src.config import settings


class QuestionService:
    """Manage clarification questions."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create questions table with task_data support."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clarification_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_type TEXT NOT NULL,
                question_text TEXT NOT NULL,
                context TEXT,
                options TEXT,
                status TEXT DEFAULT 'pending',
                answer TEXT,
                task_data TEXT,
                note_id INTEGER,
                domain TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered_at TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def ask_task_clarification(self, task_action: str, ambiguity: str, question: str,
                                context: str, note_id: int, domain: str, 
                                task_data: Dict) -> int:
        """Ask user to clarify an ambiguous task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO clarification_questions 
            (question_type, question_text, context, status, task_data, note_id, domain)
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
        """, (
            'task_clarification',
            question,
            f"Task: {task_action}\n\nFrom your note: {context}\n\nWhat's unclear: {ambiguity}",
            json.dumps(task_data),
            note_id,
            domain
        ))
        
        question_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created task clarification #{question_id}: {task_action}")
        return question_id
    
    def ask_domain_clarification(self, title: str, content: str, 
                                 suggested_domain: str, confidence: float) -> int:
        """Ask user to clarify domain routing."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        question = f"Where should this note go: '{title}'?"
        
        cursor.execute("""
            INSERT INTO clarification_questions 
            (question_type, question_text, context, options, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (
            'domain_routing',
            question,
            f"Suggested: {suggested_domain} (confidence: {confidence:.0%})",
            ','.join(settings.domains_list)
        ))
        
        question_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return question_id
    
    def get_pending_questions(self) -> List[Dict]:
        """Get all unanswered questions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, question_type, question_text, context, options, task_data
            FROM clarification_questions
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)
        
        questions = []
        for row in cursor.fetchall():
            q = {
                'id': row[0],
                'type': row[1],
                'question': row[2],
                'context': row[3],
                'options': row[4].split(',') if row[4] else []
            }
            if row[5]:
                q['task_data'] = json.loads(row[5])
            questions.append(q)
        
        conn.close()
        return questions
    
    def answer_question(self, question_id: int, answer: str):
        """Record answer and create task if it was a clarification."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get question details
        cursor.execute("""
            SELECT question_type, task_data, note_id, domain
            FROM clarification_questions WHERE id = ?
        """, (question_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return
        
        q_type, task_data_json, note_id, domain = row
        
        # Mark answered
        cursor.execute("""
            UPDATE clarification_questions
            SET answer = ?, status = 'answered', answered_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (answer, question_id))
        
        # If task clarification, create the task with the clarified info
        if q_type == 'task_clarification' and task_data_json:
            task_data = json.loads(task_data_json)
            
            # Update action with clarification
            clarified_action = f"{task_data['action']} - {answer}"
            priority = task_data.get('priority', 'medium')
            duration = task_data.get('estimated_duration_minutes', 30)
            context = task_data.get('context', '')
            
            cursor.execute("""
                INSERT INTO tasks (text, action, status, priority, estimated_duration_minutes, domain, source_note_id)
                VALUES (?, ?, 'open', ?, ?, ?, ?)
            """, (
                f"{context}\n\nClarification: {answer}",
                clarified_action,
                priority,
                duration,
                domain,
                note_id
            ))
            
            logger.success(f"Created clarified task: {clarified_action}")
        
        conn.commit()
        conn.close()


question_service = QuestionService()
