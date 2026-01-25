"""Dynamic domain management service."""

import sqlite3
from typing import List, Dict
from loguru import logger

from src.config import settings


class DomainService:
    """Manage user's dynamic domain structure."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create domains table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_path TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                color TEXT,
                target_percentage REAL DEFAULT 0,
                learned_keywords TEXT,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def setup_from_profile(self, profile: Dict):
        """Setup domains from onboarding profile."""
        logger.info(f"Setting up domains with profile: {profile}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main company
        company = profile.get('company', '').lower().replace(' ', '')
        if company:
            cursor.execute("""
                INSERT OR IGNORE INTO user_domains (domain_path, display_name, color, target_percentage)
                VALUES (?, ?, ?, ?)
            """, (f'work/{company}', profile.get('company', 'Work'), 'blue', 
                  float(profile.get('work_balance_0', 70))))
        
        # Side projects
        side = profile.get('side_projects', '').lower().replace(' ', '')
        if side:
            cursor.execute("""
                INSERT OR IGNORE INTO user_domains (domain_path, display_name, color, target_percentage)
                VALUES (?, ?, ?, ?)
            """, (f'work/{side}', profile.get('side_projects', 'Side Project'), 'green',
                  float(profile.get('work_balance_1', 20))))
        
        # Standard domains
        cursor.execute("""
            INSERT OR IGNORE INTO user_domains (domain_path, display_name, color, target_percentage)
            VALUES 
                ('personal', 'Personal', 'purple', ?),
                ('learning', 'Learning', 'amber', 0),
                ('admin', 'Admin', 'gray', 0)
        """, (float(profile.get('work_balance_2', 10)),))
        
        conn.commit()
        conn.close()
        
        logger.success("Domains setup from profile")
    
    def get_all_domains(self) -> List[Dict]:
        """Get all active domains."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT domain_path, display_name, color, target_percentage, learned_keywords
            FROM user_domains
            WHERE active = 1
            ORDER BY target_percentage DESC
        """)
        
        domains = []
        for row in cursor.fetchall():
            domains.append({
                'path': row[0],
                'name': row[1],
                'color': row[2],
                'target': row[3],
                'keywords': row[4].split(',') if row[4] else []
            })
        
        conn.close()
        return domains
    
    def add_learned_keyword(self, domain_path: str, keyword: str):
        """Add learned keyword to domain."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT learned_keywords FROM user_domains WHERE domain_path = ?
        """, (domain_path,))
        
        row = cursor.fetchone()
        if not row:
            return
        
        current = row[0]
        keywords = set(current.split(',')) if current else set()
        keywords.add(keyword.lower())
        
        cursor.execute("""
            UPDATE user_domains 
            SET learned_keywords = ?
            WHERE domain_path = ?
        """, (','.join(keywords), domain_path))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Learned keyword '{keyword}' for {domain_path}")


# Global instance
domain_service = DomainService()
