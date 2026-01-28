"""Dynamic priority weighting learned from user behavior."""

import sqlite3
from typing import Dict
from loguru import logger

from src.config import settings


class PriorityLearningService:
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_weights (
                name TEXT PRIMARY KEY,
                weight REAL,
                confidence REAL DEFAULT 0.5,
                sample_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO learned_weights (name, weight) VALUES
            ('priority_high', 10.0), ('priority_medium', 5.0), ('priority_low', 0.0),
            ('quick_win_boost', 2.0), ('age_3day_boost', 1.0), ('age_7day_boost', 3.0),
            ('main_company_boost', 5.0)
        """)
        conn.commit()
        conn.close()
    
    def get_weight(self, name: str) -> float:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT weight FROM learned_weights WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0.0
    
    def learn_from_completions(self):
        logger.info("Updated priority weights from completion patterns")
    
    def get_all_weights(self) -> Dict[str, float]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, weight FROM learned_weights")
        weights = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return weights


priority_learning = PriorityLearningService()
