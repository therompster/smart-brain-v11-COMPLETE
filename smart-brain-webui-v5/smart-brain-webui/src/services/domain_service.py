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
        
        # Parse work balance percentages (handle both formats)
        work_balance_0 = self._safe_float(profile.get('work_balance_0', profile.get('work_balance', {}).get(0, 70)))
        work_balance_1 = self._safe_float(profile.get('work_balance_1', profile.get('work_balance', {}).get(1, 20)))
        work_balance_2 = self._safe_float(profile.get('work_balance_2', profile.get('work_balance', {}).get(2, 10)))
        
        # Main company
        company = (profile.get('company') or '').strip()
        company_slug = company.lower().replace(' ', '') if company else ''
        
        if company_slug:
            logger.info(f"Creating domain for company: {company} -> work/{company_slug}")
            cursor.execute("""
                INSERT OR REPLACE INTO user_domains (domain_path, display_name, color, target_percentage)
                VALUES (?, ?, ?, ?)
            """, (f'work/{company_slug}', company, 'blue', work_balance_0))
        
        # Side projects
        side_projects = (profile.get('side_projects') or '').strip()
        side_slug = side_projects.lower().replace(' ', '') if side_projects else ''
        
        if side_slug:
            logger.info(f"Creating domain for side project: {side_projects} -> work/{side_slug}")
            cursor.execute("""
                INSERT OR REPLACE INTO user_domains (domain_path, display_name, color, target_percentage)
                VALUES (?, ?, ?, ?)
            """, (f'work/{side_slug}', side_projects, 'green', work_balance_1))
        
        # Standard domains - always create these
        logger.info("Creating standard domains: personal, learning, admin")
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_domains (domain_path, display_name, color, target_percentage)
            VALUES (?, ?, ?, ?)
        """, ('personal', 'Personal', 'purple', work_balance_2))
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_domains (domain_path, display_name, color, target_percentage)
            VALUES (?, ?, ?, ?)
        """, ('learning', 'Learning', 'amber', 0))
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_domains (domain_path, display_name, color, target_percentage)
            VALUES (?, ?, ?, ?)
        """, ('admin', 'Admin', 'gray', 0))
        
        conn.commit()
        conn.close()
        
        # Verify domains were created
        domains = self.get_all_domains()
        logger.success(f"Domains setup complete. Created {len(domains)} domains: {[d['path'] for d in domains]}")
    
    def _safe_float(self, value, default: float = 0.0) -> float:
        """Safely convert value to float."""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
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
                'color': row[2] or 'slate',
                'target': row[3] or 0,
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
            conn.close()
            return
        
        current = row[0]
        keywords = set(current.split(',')) if current else set()
        keywords.discard('')  # Remove empty strings
        keywords.add(keyword.lower())
        
        cursor.execute("""
            UPDATE user_domains 
            SET learned_keywords = ?
            WHERE domain_path = ?
        """, (','.join(keywords), domain_path))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Learned keyword '{keyword}' for {domain_path}")
    
    def ensure_default_domains(self):
        """Ensure at least default domains exist."""
        domains = self.get_all_domains()
        if not domains:
            logger.info("No domains found, creating defaults from settings")
            self._create_defaults_from_settings()
    
    def _create_defaults_from_settings(self):
        """Create default domains from settings."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        default_colors = {
            'work/marriott': 'blue',
            'work/mansour': 'green',
            'work/konstellate': 'green',
            'personal': 'purple',
            'learning': 'amber',
            'admin': 'gray'
        }
        
        for domain_path in settings.domains_list:
            name = domain_path.split('/')[-1].title()
            color = default_colors.get(domain_path, 'slate')
            
            cursor.execute("""
                INSERT OR IGNORE INTO user_domains (domain_path, display_name, color, target_percentage)
                VALUES (?, ?, ?, ?)
            """, (domain_path, name, color, 0))
        
        conn.commit()
        conn.close()
        logger.info(f"Created default domains from settings: {settings.domains_list}")


# Global instance
domain_service = DomainService()
