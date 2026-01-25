"""Dynamic note type system."""

import sqlite3
from typing import List, Dict
from loguru import logger

from src.config import settings


class NoteTypeService:
    """Manage user-defined note types."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create note types table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                icon TEXT,
                active BOOLEAN DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize PARA defaults
        cursor.execute("""
            INSERT OR IGNORE INTO note_types (name, description, icon) VALUES
            ('Project', 'Time-bound goal with specific outcome', '🎯'),
            ('Area', 'Ongoing responsibility or interest', '🏔️'),
            ('Resource', 'Reference material or knowledge', '📚'),
            ('Archive', 'Completed or inactive items', '📦')
        """)
        
        conn.commit()
        conn.close()
    
    def get_all_types(self) -> List[Dict]:
        """Get all active note types."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, description, icon, usage_count
            FROM note_types
            WHERE active = 1
            ORDER BY usage_count DESC
        """)
        
        types = [
            {
                'name': row[0],
                'description': row[1],
                'icon': row[2],
                'usage_count': row[3]
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return types
    
    def add_type(self, name: str, description: str = '', icon: str = '📄'):
        """Add custom note type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO note_types (name, description, icon)
            VALUES (?, ?, ?)
        """, (name, description, icon))
        
        conn.commit()
        conn.close()
        
        logger.success(f"Added note type: {name}")
    
    def increment_usage(self, type_name: str):
        """Track type usage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE note_types
            SET usage_count = usage_count + 1
            WHERE name = ?
        """, (type_name,))
        
        conn.commit()
        conn.close()
    
    def suggest_types_from_content(self, title: str, content: str) -> str:
        """Suggest note type based on content patterns."""
        text = f"{title} {content}".lower()
        
        # Project indicators
        if any(word in text for word in ['goal', 'launch', 'deadline', 'ship', 'release', 'complete']):
            return 'Project'
        
        # Area indicators
        if any(word in text for word in ['maintain', 'manage', 'ongoing', 'responsibility', 'area']):
            return 'Area'
        
        # Resource indicators
        if any(word in text for word in ['reference', 'learn', 'guide', 'documentation', 'resource']):
            return 'Resource'
        
        # Default
        return 'Resource'


# Global instance
note_type_service = NoteTypeService()
