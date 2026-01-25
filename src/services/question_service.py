"""Question queue for clarification requests."""

import sqlite3
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
        """Create questions table."""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered_at TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def ask_domain_clarification(self, title: str, content: str, 
                                 suggested_domain: str, confidence: float) -> int:
        """
        Ask user to clarify domain routing.
        
        Returns:
            Question ID
        """
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
        
        logger.info(f"Created domain clarification question #{question_id}")
        return question_id
    
    def ask_entity_clarification(self, name: str, context: str) -> int:
        """Ask user about unknown person/project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        question = f"Who/what is '{name}'?"
        
        cursor.execute("""
            INSERT INTO clarification_questions 
            (question_type, question_text, context, status)
            VALUES (?, ?, ?, 'pending')
        """, ('entity', question, context))
        
        question_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created entity clarification question #{question_id}")
        return question_id
    
    def ask_priority_clarification(self, task_text: str) -> int:
        """Ask user about task priority."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        question = f"How important is this: '{task_text}'?"
        
        cursor.execute("""
            INSERT INTO clarification_questions 
            (question_type, question_text, options, status)
            VALUES (?, ?, ?, 'pending')
        """, ('priority', question, 'high,medium,low'))
        
        question_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return question_id
    
    def get_pending_questions(self) -> List[Dict]:
        """Get all unanswered questions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, question_type, question_text, context, options
            FROM clarification_questions
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)
        
        questions = []
        for row in cursor.fetchall():
            questions.append({
                'id': row[0],
                'type': row[1],
                'question': row[2],
                'context': row[3],
                'options': row[4].split(',') if row[4] else []
            })
        
        conn.close()
        return questions
    
    def answer_question(self, question_id: int, answer: str):
        """Record answer to question."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clarification_questions
            SET answer = ?, status = 'answered', answered_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (answer, question_id))
        
        conn.commit()
        conn.close()
        
        logger.success(f"Answered question #{question_id}: {answer}")


# Global instance
question_service = QuestionService()
