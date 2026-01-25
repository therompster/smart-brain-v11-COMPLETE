"""Profile onboarding service."""

import sqlite3
from typing import Dict, List, Any
from loguru import logger

from src.config import settings


ONBOARDING_QUESTIONS = [
    {
        "id": "role",
        "question": "What's your current job role?",
        "type": "text",
        "placeholder": "e.g., Enterprise Architect"
    },
    {
        "id": "company",
        "question": "Which company?",
        "type": "text",
        "placeholder": "e.g., Marriott"
    },
    {
        "id": "side_projects",
        "question": "Any side projects or ventures?",
        "type": "text",
        "placeholder": "e.g., Konstellate (AI product)"
    },
    {
        "id": "main_projects",
        "question": "What are your main work projects?",
        "type": "textarea",
        "placeholder": "List your key projects..."
    },
    {
        "id": "key_people",
        "question": "Who do you work with regularly?",
        "type": "textarea",
        "placeholder": "Names and roles of people you collaborate with..."
    },
    {
        "id": "work_hours",
        "question": "Typical work hours?",
        "type": "time-range",
        "placeholder": "Start - End"
    },
    {
        "id": "peak_energy",
        "question": "When are you most productive?",
        "type": "select",
        "options": ["Morning", "Afternoon", "Evening", "Night"]
    },
    {
        "id": "work_balance",
        "question": "Ideal time split? (percentages)",
        "type": "allocation",
        "domains": ["Marriott", "Side projects", "Personal/Learning"]
    }
]


class OnboardingService:
    """Manage user profile onboarding."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_profile_table()
    
    def _ensure_profile_table(self):
        """Ensure profile data table exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_data (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_questions(self) -> List[Dict]:
        """Get onboarding questions."""
        return ONBOARDING_QUESTIONS
    
    def is_onboarding_complete(self) -> bool:
        """Check if user completed onboarding."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT onboarding_completed FROM user_profile WHERE id = 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        return row and row[0] == 1
    
    def save_answers(self, answers: Dict[str, Any]):
        """Save onboarding answers."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Save each answer
        for key, value in answers.items():
            cursor.execute("""
                INSERT OR REPLACE INTO profile_data (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, str(value)))
        
        # Mark onboarding complete
        cursor.execute("""
            UPDATE user_profile 
            SET onboarding_completed = 1, profile_completeness_score = 0.5
            WHERE id = 1
        """)
        
        conn.commit()
        conn.close()
        
        # Setup dynamic domains from profile
        from src.services.domain_service import domain_service
        domain_service.setup_from_profile(answers)
        
        logger.success("Onboarding completed")
    
    def get_profile_data(self) -> Dict[str, str]:
        """Get all profile data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT key, value FROM profile_data")
        rows = cursor.fetchall()
        conn.close()
        
        return {row[0]: row[1] for row in rows}


# Global instance
onboarding_service = OnboardingService()
