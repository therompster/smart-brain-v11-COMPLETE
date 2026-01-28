"""Dynamic note type system."""

import sqlite3
from typing import List, Dict
from loguru import logger

from src.config import settings


class NoteTypeService:
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                icon TEXT,
                active BOOLEAN DEFAULT 1,
                usage_count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO note_types (name, description, icon) VALUES
            ('Project', 'Time-bound goal', '🎯'), ('Area', 'Ongoing responsibility', '🏔️'),
            ('Resource', 'Reference material', '📚'), ('Archive', 'Completed items', '📦')
        """)
        conn.commit()
        conn.close()
    
    def get_all_types(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, icon, usage_count FROM note_types WHERE active = 1")
        types = [{'name': r[0], 'description': r[1], 'icon': r[2], 'usage_count': r[3]} 
                 for r in cursor.fetchall()]
        conn.close()
        return types
    
    def add_type(self, name: str, description: str = '', icon: str = '📄'):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO note_types (name, description, icon) VALUES (?, ?, ?)", 
                       (name, description, icon))
        conn.commit()
        conn.close()


note_type_service = NoteTypeService()
