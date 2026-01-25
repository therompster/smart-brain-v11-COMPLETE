"""Confidence scoring system for routing and entity recognition."""

import sqlite3
from typing import Dict, Optional, Tuple
from datetime import datetime
from loguru import logger

from src.config import settings


class ConfidenceService:
    """Track confidence scores for routing and entities."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create confidence tracking tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Domain routing confidence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routing_confidence (
                keywords TEXT PRIMARY KEY,
                domain TEXT,
                correct_count INTEGER DEFAULT 0,
                incorrect_count INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Entity (people, projects) confidence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_confidence (
                entity_name TEXT PRIMARY KEY,
                entity_type TEXT,
                metadata TEXT,
                confidence REAL DEFAULT 0.0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def check_domain_confidence(self, keywords: str, suggested_domain: str) -> float:
        """
        Check confidence for domain routing.
        
        Returns:
            Confidence score 0.0-1.0
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT correct_count, incorrect_count, confidence
            FROM routing_confidence
            WHERE keywords = ? AND domain = ?
        """, (keywords, suggested_domain))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            # No history, low confidence
            return 0.5
        
        correct, incorrect, stored_conf = row
        total = correct + incorrect
        
        if total == 0:
            return 0.5
        
        # Calculate confidence from success rate
        confidence = correct / total
        
        return confidence
    
    def record_routing_feedback(self, keywords: str, suggested_domain: str, 
                               actual_domain: str):
        """Record user's routing decision."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        is_correct = suggested_domain == actual_domain
        
        cursor.execute("""
            INSERT INTO routing_confidence (keywords, domain, correct_count, incorrect_count, confidence, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(keywords) DO UPDATE SET
                correct_count = correct_count + ?,
                incorrect_count = incorrect_count + ?,
                confidence = (correct_count + ?) / (correct_count + incorrect_count + ? + ?),
                updated_at = CURRENT_TIMESTAMP
        """, (
            keywords,
            actual_domain,
            1 if is_correct else 0,
            0 if is_correct else 1,
            0.5,
            1 if is_correct else 0,
            0 if is_correct else 1,
            1 if is_correct else 0,
            1 if is_correct else 0,
            0 if is_correct else 1
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Routing feedback: {keywords} → {actual_domain} (correct: {is_correct})")
    
    def check_entity(self, name: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if entity (person, project) is known.
        
        Returns:
            (is_known, metadata_dict)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT entity_type, metadata, confidence
            FROM entity_confidence
            WHERE entity_name = ?
        """, (name.lower(),))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False, None
        
        entity_type, metadata, confidence = row
        
        if confidence < 0.7:
            return False, None
        
        return True, {
            'type': entity_type,
            'metadata': metadata,
            'confidence': confidence
        }
    
    def add_entity(self, name: str, entity_type: str, metadata: str):
        """Add entity to knowledge base."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO entity_confidence (entity_name, entity_type, metadata, confidence, last_seen)
            VALUES (?, ?, ?, 1.0, CURRENT_TIMESTAMP)
            ON CONFLICT(entity_name) DO UPDATE SET
                metadata = ?,
                confidence = 1.0,
                last_seen = CURRENT_TIMESTAMP
        """, (name.lower(), entity_type, metadata, metadata))
        
        conn.commit()
        conn.close()
        
        logger.success(f"Added entity: {name} ({entity_type})")


# Global instance
confidence_service = ConfidenceService()
