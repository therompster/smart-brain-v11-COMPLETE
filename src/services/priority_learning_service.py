"""Dynamic priority weighting learned from user behavior."""

import sqlite3
from typing import Dict
from datetime import datetime, timedelta
from loguru import logger

from src.config import settings


class PriorityLearningService:
    """Learn optimal priority weights from completion patterns."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create priority weights table."""
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
        
        # Initialize defaults
        cursor.execute("""
            INSERT OR IGNORE INTO learned_weights (name, weight) VALUES
            ('priority_high', 10.0),
            ('priority_medium', 5.0),
            ('priority_low', 0.0),
            ('quick_win_boost', 2.0),
            ('age_3day_boost', 1.0),
            ('age_7day_boost', 3.0),
            ('main_company_boost', 5.0)
        """)
        
        conn.commit()
        conn.close()
    
    def get_weight(self, name: str) -> float:
        """Get learned weight."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT weight FROM learned_weights WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else 0.0
    
    def learn_from_completions(self):
        """
        Analyze completed tasks to optimize weights.
        
        Logic: Tasks completed quickly despite low priority → reduce priority weight
               Tasks delayed despite high priority → increase priority weight
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Analyze completion patterns from last 30 days
        cursor.execute("""
            SELECT priority, 
                   AVG(julianday(completed_at) - julianday(created_at)) as avg_delay_days,
                   COUNT(*) as count
            FROM tasks
            WHERE status = 'completed' 
              AND completed_at > datetime('now', '-30 days')
            GROUP BY priority
        """)
        
        patterns = cursor.fetchall()
        
        for priority, avg_delay, count in patterns:
            if count < 3:  # Need minimum samples
                continue
            
            weight_name = f'priority_{priority}'
            current_weight = self.get_weight(weight_name)
            
            # If high priority delayed too long, increase weight
            if priority == 'high' and avg_delay > 3:
                new_weight = min(15.0, current_weight + 1.0)
                self._update_weight(weight_name, new_weight, count)
            
            # If low priority completed fast, increase its weight
            elif priority == 'low' and avg_delay < 1:
                new_weight = min(3.0, current_weight + 0.5)
                self._update_weight(weight_name, new_weight, count)
        
        conn.close()
        logger.info("Updated priority weights from completion patterns")
    
    def _update_weight(self, name: str, weight: float, sample_count: int):
        """Update weight with confidence."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        confidence = min(0.95, sample_count / 20.0)  # 20 samples = 95% confidence
        
        cursor.execute("""
            UPDATE learned_weights
            SET weight = ?, confidence = ?, sample_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
        """, (weight, confidence, sample_count, name))
        
        conn.commit()
        conn.close()
    
    def get_all_weights(self) -> Dict[str, float]:
        """Get all learned weights."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, weight FROM learned_weights")
        weights = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return weights


# Global instance
priority_learning = PriorityLearningService()
