"""Learn user's energy patterns from task completion times."""

import sqlite3
from typing import Dict, List
from datetime import datetime
from loguru import logger

from src.config import settings


class EnergyPatternService:
    """Learn when user is most productive."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create energy patterns table."""
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
        
        # Initialize 24 hours
        for hour in range(24):
            cursor.execute("""
                INSERT OR IGNORE INTO completion_patterns (hour)
                VALUES (?)
            """, (hour,))
        
        conn.commit()
        conn.close()
    
    def log_completion(self, task_id: int, completed_at: datetime):
        """Log task completion for pattern learning."""
        hour = completed_at.hour
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get task difficulty (based on duration estimate)
        cursor.execute("""
            SELECT estimated_duration_minutes
            FROM tasks WHERE id = ?
        """, (task_id,))
        
        row = cursor.fetchone()
        difficulty = (row[0] / 60.0) if row and row[0] else 1.0
        
        # Update pattern
        cursor.execute("""
            UPDATE completion_patterns
            SET completion_count = completion_count + 1,
                avg_difficulty = (avg_difficulty * completion_count + ?) / (completion_count + 1)
            WHERE hour = ?
        """, (difficulty, hour))
        
        conn.commit()
        conn.close()
        
        self._recalculate_scores()
    
    def _recalculate_scores(self):
        """Calculate productivity scores."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT MAX(completion_count) FROM completion_patterns")
        max_count = cursor.fetchone()[0] or 1
        
        cursor.execute("""
            UPDATE completion_patterns
            SET productivity_score = (completion_count * 1.0 / ?) * (1 + avg_difficulty * 0.2)
        """, (max_count,))
        
        conn.commit()
        conn.close()
    
    def get_peak_hours(self, top_n: int = 3) -> List[int]:
        """Get user's most productive hours."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT hour
            FROM completion_patterns
            WHERE completion_count > 0
            ORDER BY productivity_score DESC
            LIMIT ?
        """, (top_n,))
        
        hours = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return hours if hours else [9, 14, 16]  # Default
    
    def get_energy_label(self, hour: int) -> str:
        """Get energy level label for hour."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT productivity_score
            FROM completion_patterns
            WHERE hour = ?
        """, (hour,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or row[0] == 0.5:
            # No data, use general patterns
            if 6 <= hour < 12:
                return "Morning"
            elif 12 <= hour < 17:
                return "Afternoon"
            elif 17 <= hour < 22:
                return "Evening"
            else:
                return "Night"
        
        score = row[0]
        if score > 0.7:
            return "Peak"
        elif score > 0.4:
            return "Good"
        else:
            return "Low"
    
    def get_pattern_summary(self) -> Dict:
        """Get summary of energy patterns."""
        peak_hours = self.get_peak_hours(3)
        
        return {
            'peak_hours': peak_hours,
            'peak_labels': [f"{h:02d}:00" for h in peak_hours],
            'confidence': self._get_confidence()
        }
    
    def _get_confidence(self) -> float:
        """Calculate confidence in patterns."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT SUM(completion_count) FROM completion_patterns")
        total = cursor.fetchone()[0] or 0
        conn.close()
        
        return min(1.0, total / 50.0)  # 50 completions = full confidence


# Global instance
energy_pattern_service = EnergyPatternService()
