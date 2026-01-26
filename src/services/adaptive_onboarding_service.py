"""Adaptive onboarding with dynamic question flow."""

import sqlite3
from typing import List, Dict, Optional
from loguru import logger

from src.config import settings


class AdaptiveOnboardingService:
    """Adaptive onboarding that learns from answers."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create onboarding tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS onboarding_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                current_step INTEGER DEFAULT 0,
                completed BOOLEAN DEFAULT 0,
                context TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_data (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_next_question(self, previous_answers: Dict = None) -> Optional[Dict]:
        """Get next question based on previous answers."""
        if not previous_answers:
            previous_answers = {}
        
        logger.debug(f"Getting next question. Previous answers: {list(previous_answers.keys())}")
        
        # Question flow adapts based on answers
        if 'role' not in previous_answers:
            return {
                'id': 'role',
                'question': "What's your current role?",
                'type': 'text',
                'placeholder': 'e.g., Enterprise Architect'
            }
        
        if 'company' not in previous_answers:
            return {
                'id': 'company',
                'question': "Which company?",
                'type': 'text',
                'placeholder': 'e.g., Marriott'
            }
        
        if 'side_projects' not in previous_answers:
            return {
                'id': 'side_projects',
                'question': "Any side projects or ventures? (Leave blank if none)",
                'type': 'text',
                'placeholder': 'e.g., Konstellate'
            }
        
        # Adaptive: only ask about main projects if they have work
        if previous_answers.get('company') or previous_answers.get('side_projects'):
            if 'main_projects' not in previous_answers:
                return {
                    'id': 'main_projects',
                    'question': "What are your main projects?",
                    'type': 'textarea',
                    'placeholder': 'List key projects...'
                }
        
        if 'key_people' not in previous_answers:
            return {
                'id': 'key_people',
                'question': "Who do you work with regularly?",
                'type': 'textarea',
                'placeholder': 'Names and roles...'
            }
        
        if 'peak_energy' not in previous_answers:
            from src.services.energy_pattern_service import energy_pattern_service
            pattern = energy_pattern_service.get_pattern_summary()
            
            # If no learned data, ask; otherwise use learned pattern
            if pattern['confidence'] < 0.3:
                return {
                    'id': 'peak_energy',
                    'question': "When are you most productive?",
                    'type': 'select',
                    'options': ['Morning (6-12)', 'Afternoon (12-17)', 'Evening (17-22)', 'Night (22-6)']
                }
            else:
                # Skip question, use learned data
                previous_answers['peak_energy'] = 'learned'
        
        # Adaptive: only ask balance if multiple work areas
        has_multiple = bool(previous_answers.get('company')) and bool(previous_answers.get('side_projects'))
        
        # Check for work_balance_0 since UI binds to work_balance_0, work_balance_1, work_balance_2
        if has_multiple and 'work_balance_0' not in previous_answers:
            domains = []
            if previous_answers.get('company'):
                domains.append(previous_answers['company'])
            if previous_answers.get('side_projects'):
                domains.append(previous_answers['side_projects'])
            domains.append('Personal/Learning')
            
            return {
                'id': 'work_balance',
                'question': "Ideal time split? (percentages)",
                'type': 'allocation',
                'domains': domains
            }
        
        # Done
        logger.info("Onboarding questions complete")
        return None
    
    def save_answers(self, answers: Dict):
        """Save onboarding answers and setup system."""
        logger.info(f"Saving onboarding answers: {list(answers.keys())}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Save answers
        for key, value in answers.items():
            cursor.execute("""
                INSERT OR REPLACE INTO profile_data (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, str(value) if value is not None else ''))
            logger.debug(f"Saved profile data: {key} = {value}")
        
        # Mark complete
        cursor.execute("""
            INSERT OR REPLACE INTO onboarding_state (id, completed)
            VALUES (1, 1)
        """)
        
        conn.commit()
        conn.close()
        
        # Setup domains from profile
        try:
            from src.services.domain_service import domain_service
            logger.info("Setting up domains from profile...")
            domain_service.setup_from_profile(answers)
        except Exception as e:
            logger.error(f"Failed to setup domains: {e}")
            # Try to create defaults anyway
            try:
                domain_service.ensure_default_domains()
            except Exception as e2:
                logger.error(f"Failed to create default domains: {e2}")
        
        # Initialize learned thresholds
        try:
            from src.services.threshold_service import threshold_service
            threshold_service.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize thresholds: {e}")
        
        # Initialize priority learning
        try:
            from src.services.priority_learning_service import priority_learning
            priority_learning._ensure_table()
        except Exception as e:
            logger.error(f"Failed to initialize priority learning: {e}")
        
        logger.success("Adaptive onboarding completed")
    
    def is_complete(self) -> bool:
        """Check if onboarding done."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT completed FROM onboarding_state WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        return row and row[0] == 1


# Global instance
adaptive_onboarding = AdaptiveOnboardingService()
