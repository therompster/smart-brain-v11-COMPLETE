"""Learn user's energy patterns from task completion times."""

import sqlite3
from typing import Dict, List
from datetime import datetime
from loguru import logger

from src.config import settings


class EnergyPatternService:
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS completion_patterns (
                hour INTEGER PRIMARY KEY,
                completion_count INTEGER DEFAULT 0,
                avg_difficulty REAL DEFAULT 0,
                productivity_score REAL DEFAULT 0.5
            )
        """)
        for hour in range(24):
            cursor.execute("INSERT OR IGNORE INTO completion_patterns (hour) VALUES (?)", (hour,))
        conn.commit()
        conn.close()
    
    def log_completion(self, task_id: int, completed_at: datetime):
        hour = completed_at.hour
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT estimated_duration_minutes FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        difficulty = (row[0] / 60.0) if row and row[0] else 1.0
        cursor.execute("""
            UPDATE completion_patterns
            SET completion_count = completion_count + 1,
                avg_difficulty = (avg_difficulty * completion_count + ?) / (completion_count + 1)
            WHERE hour = ?
        """, (difficulty, hour))
        conn.commit()
        conn.close()
    
    def get_peak_hours(self, top_n: int = 3) -> List[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT hour FROM completion_patterns
            WHERE completion_count > 0
            ORDER BY productivity_score DESC LIMIT ?
        """, (top_n,))
        hours = [row[0] for row in cursor.fetchall()]
        conn.close()
        return hours if hours else [9, 14, 16]
    
    def get_pattern_summary(self) -> Dict:
        peak_hours = self.get_peak_hours(3)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(completion_count) FROM completion_patterns")
        total = cursor.fetchone()[0] or 0
        conn.close()
        return {
            'peak_hours': peak_hours,
            'peak_labels': [f"{h:02d}:00" for h in peak_hours],
            'confidence': min(1.0, total / 50.0)
        }


energy_pattern_service = EnergyPatternService()
