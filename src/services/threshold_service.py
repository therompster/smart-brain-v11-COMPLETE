"""Learned threshold service - adapts based on user behavior."""

import sqlite3
from typing import Dict
from loguru import logger

from src.config import settings


DEFAULT_THRESHOLDS = {
    'routing_confidence_min': 0.7,
    'domain_neglect_days': 7,
    'task_overload_ratio': 2.0,
    'quick_win_minutes': 30,
    'old_task_days': 3,
}


class ThresholdService:
    """Learn and adapt system thresholds."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create thresholds table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_thresholds (
                name TEXT PRIMARY KEY,
                value REAL,
                confidence REAL DEFAULT 0.5,
                adjustment_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def initialize(self):
        """Initialize with defaults."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for name, value in DEFAULT_THRESHOLDS.items():
            cursor.execute("""
                INSERT OR IGNORE INTO learned_thresholds (name, value)
                VALUES (?, ?)
            """, (name, value))
        
        conn.commit()
        conn.close()
        logger.info("Initialized thresholds")
    
    def get(self, name: str) -> float:
        """Get threshold value."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM learned_thresholds WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0]
        return DEFAULT_THRESHOLDS.get(name, 0.5)
    
    def adjust(self, name: str, feedback: str):
        """
        Adjust threshold based on user feedback.
        
        Args:
            name: Threshold name
            feedback: 'too_sensitive' or 'not_sensitive'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM learned_thresholds WHERE name = ?", (name,))
        row = cursor.fetchone()
        current = row[0] if row else DEFAULT_THRESHOLDS.get(name, 0.5)
        
        # Adjust based on feedback
        if feedback == 'too_sensitive':
            # User wants fewer interruptions
            if 'confidence' in name:
                new_value = max(0.1, current - 0.05)  # Lower bar
            elif 'days' in name:
                new_value = current + 2  # Wait longer
            elif 'ratio' in name:
                new_value = current + 0.5  # Higher tolerance
            else:
                new_value = current * 1.1
        else:  # not_sensitive
            # User wants more attention
            if 'confidence' in name:
                new_value = min(0.95, current + 0.05)  # Raise bar
            elif 'days' in name:
                new_value = max(1, current - 2)  # Check sooner
            elif 'ratio' in name:
                new_value = max(1.2, current - 0.5)  # Lower tolerance
            else:
                new_value = current * 0.9
        
        cursor.execute("""
            UPDATE learned_thresholds
            SET value = ?, adjustment_count = adjustment_count + 1, updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
        """, (new_value, name))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Adjusted {name}: {current:.2f} → {new_value:.2f} ({feedback})")
    
    def get_all(self) -> Dict[str, float]:
        """Get all thresholds."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, value FROM learned_thresholds")
        thresholds = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        # Fill missing with defaults
        for name, value in DEFAULT_THRESHOLDS.items():
            if name not in thresholds:
                thresholds[name] = value
        
        return thresholds


# Global instance
threshold_service = ThresholdService()
