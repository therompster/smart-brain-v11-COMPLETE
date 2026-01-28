"""Work Context Service - learns user's world through interview and brain dumps."""

import sqlite3
import json
from typing import Dict, List, Optional, Any
from loguru import logger

from src.config import settings


class WorkContextService:
    """Learns and provides work context - no hardcoding."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure work_context tables exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Unified work context - stores platforms, areas, topics, people, etc.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                parent_id INTEGER,
                description TEXT,
                relationships TEXT,
                keywords TEXT,
                metadata TEXT,
                confirmed BOOLEAN DEFAULT 0,
                source TEXT DEFAULT 'interview',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES work_context(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wc_type ON work_context(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wc_parent ON work_context(parent_id)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_wc_unique ON work_context(entity_type, name, parent_id)")
        
        # Interview state
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interview_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                phase TEXT DEFAULT 'not_started',
                answers TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ===== INTERVIEW FLOW =====
    
    def get_interview_status(self) -> Dict:
        """Get interview progress."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT phase, answers FROM interview_state WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"phase": "not_started", "answers": {}}
        
        return {
            "phase": row[0],
            "answers": json.loads(row[1]) if row[1] else {}
        }
    
    def get_next_interview_question(self) -> Optional[Dict]:
        """Get next question based on interview state."""
        state = self.get_interview_status()
        phase = state["phase"]
        answers = state["answers"]
        
        if phase == "not_started" or phase == "platforms":
            return {
                "id": "platforms",
                "phase": "platforms",
                "question": "What major systems, platforms, or projects do you work on?",
                "help": "List each one on a separate line. These are the big things you're responsible for or contribute to.",
                "placeholder": "ECMP\nTIP.AI\nCustomer Portal",
                "type": "multiline"
            }
        
        elif phase == "areas":
            # Ask about areas for each platform
            platforms = answers.get("platforms", [])
            areas_answered = answers.get("areas", {})
            
            for platform in platforms:
                if platform not in areas_answered:
                    return {
                        "id": f"areas_{platform}",
                        "phase": "areas",
                        "platform": platform,
                        "question": f"What are the main areas or components of {platform}?",
                        "help": "Break it down into logical parts - features, modules, subsystems.",
                        "placeholder": "AI Integration\nAdmin Tools\nAPI Layer",
                        "type": "multiline"
                    }
            
            # All platforms done, move to relationships
            return self._get_relationships_question(answers)
        
        elif phase == "relationships":
            return self._get_relationships_question(answers)
        
        elif phase == "people":
            return {
                "id": "people",
                "phase": "people",
                "question": "Who do you work with regularly?",
                "help": "List people with their role or area. Format: Name - Role/Area",
                "placeholder": "Chris Hunter - AEM\nArun - Feature Flags\nSarah - Product",
                "type": "multiline"
            }
        
        elif phase == "complete":
            return None
        
        return None
    
    def _get_relationships_question(self, answers: Dict) -> Dict:
        platforms = answers.get("platforms", [])
        platform_list = ", ".join(platforms) if platforms else "your platforms"
        
        return {
            "id": "relationships",
            "phase": "relationships",
            "question": f"How do {platform_list} relate to each other?",
            "help": "Describe integrations, dependencies, or how they work together.",
            "placeholder": "ECMP AI uses TIP.AI for intent classification\nAEM manages templates that ECMP consumes",
            "type": "textarea"
        }
    
    def save_interview_answer(self, question_id: str, answer: Any) -> Dict:
        """Save interview answer and determine next phase."""
        state = self.get_interview_status()
        answers = state["answers"]
        phase = state["phase"]
        
        # Parse answer based on question type
        if question_id == "platforms":
            platforms = [p.strip() for p in answer.strip().split("\n") if p.strip()]
            answers["platforms"] = platforms
            next_phase = "areas" if platforms else "complete"
        
        elif question_id.startswith("areas_"):
            platform = question_id.replace("areas_", "")
            areas = [a.strip() for a in answer.strip().split("\n") if a.strip()]
            if "areas" not in answers:
                answers["areas"] = {}
            answers["areas"][platform] = areas
            
            # Check if all platforms have areas
            all_platforms = answers.get("platforms", [])
            areas_done = all(p in answers.get("areas", {}) for p in all_platforms)
            next_phase = "relationships" if areas_done else "areas"
        
        elif question_id == "relationships":
            answers["relationships"] = answer.strip()
            next_phase = "people"
        
        elif question_id == "people":
            people = [p.strip() for p in answer.strip().split("\n") if p.strip()]
            answers["people"] = people
            next_phase = "complete"
            
            # Process into work_context
            self._process_interview_complete(answers)
        
        else:
            next_phase = phase
        
        # Save state
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO interview_state (id, phase, answers, updated_at)
            VALUES (1, ?, ?, CURRENT_TIMESTAMP)
        """, (next_phase, json.dumps(answers)))
        conn.commit()
        conn.close()
        
        return {"next_phase": next_phase, "complete": next_phase == "complete"}
    
    def _process_interview_complete(self, answers: Dict):
        """Convert interview answers into work_context entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        platforms = answers.get("platforms", [])
        areas = answers.get("areas", {})
        relationships = answers.get("relationships", "")
        people = answers.get("people", [])
        
        # Create platforms
        for platform in platforms:
            cursor.execute("""
                INSERT OR IGNORE INTO work_context (entity_type, name, confirmed, source)
                VALUES ('platform', ?, 1, 'interview')
            """, (platform,))
            
            # Get platform ID
            cursor.execute("SELECT id FROM work_context WHERE entity_type = 'platform' AND name = ?", (platform,))
            row = cursor.fetchone()
            if not row:
                continue
            platform_id = row[0]
            
            # Create areas under platform
            for area in areas.get(platform, []):
                cursor.execute("""
                    INSERT OR IGNORE INTO work_context (entity_type, name, parent_id, confirmed, source)
                    VALUES ('area', ?, ?, 1, 'interview')
                """, (area, platform_id))
        
        # Store relationships
        if relationships:
            cursor.execute("""
                INSERT INTO work_context (entity_type, name, description, confirmed, source)
                VALUES ('relationships', 'System Relationships', ?, 1, 'interview')
            """, (relationships,))
        
        # Create people
        for person_line in people:
            parts = person_line.split(" - ", 1)
            name = parts[0].strip()
            role = parts[1].strip() if len(parts) > 1 else ""
            
            cursor.execute("""
                INSERT OR IGNORE INTO work_context (entity_type, name, description, confirmed, source)
                VALUES ('person', ?, ?, 1, 'interview')
            """, (name, role))
        
        conn.commit()
        conn.close()
        
        logger.success(f"Interview complete: {len(platforms)} platforms, {len(people)} people")
    
    def reset_interview(self):
        """Reset to start fresh."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE interview_state SET phase = 'not_started', answers = NULL WHERE id = 1")
        cursor.execute("DELETE FROM work_context WHERE source = 'interview'")
        conn.commit()
        conn.close()
    
    # ===== WORK CONTEXT QUERIES =====
    
    def get_context_for_extraction(self) -> Dict:
        """Get learned context for brain dump extraction."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get platforms with areas
        cursor.execute("""
            SELECT id, name FROM work_context 
            WHERE entity_type = 'platform' AND confirmed = 1
        """)
        platforms = []
        for row in cursor.fetchall():
            platform_id, platform_name = row
            
            # Get areas
            cursor.execute("""
                SELECT name FROM work_context 
                WHERE entity_type = 'area' AND parent_id = ? AND confirmed = 1
            """, (platform_id,))
            areas = [r[0] for r in cursor.fetchall()]
            
            # Get topics
            cursor.execute("""
                SELECT name FROM work_context 
                WHERE entity_type = 'topic' AND parent_id = ? AND confirmed = 1
            """, (platform_id,))
            topics = [r[0] for r in cursor.fetchall()]
            
            platforms.append({
                "id": platform_id,
                "name": platform_name,
                "areas": areas,
                "topics": topics
            })
        
        # Get people
        cursor.execute("""
            SELECT name, description FROM work_context 
            WHERE entity_type = 'person' AND confirmed = 1
        """)
        people = [{"name": r[0], "role": r[1] or ""} for r in cursor.fetchall()]
        
        # Get relationships
        cursor.execute("""
            SELECT description FROM work_context 
            WHERE entity_type = 'relationships'
        """)
        row = cursor.fetchone()
        relationships = row[0] if row else ""
        
        conn.close()
        
        return {
            "platforms": platforms,
            "people": people,
            "relationships": relationships
        }
    
    def add_discovered_entity(self, entity_type: str, name: str, parent_name: str = None, 
                             description: str = None, confirmed: bool = False) -> int:
        """Add entity discovered from brain dump."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        parent_id = None
        if parent_name:
            cursor.execute("""
                SELECT id FROM work_context WHERE name = ? AND confirmed = 1
            """, (parent_name,))
            row = cursor.fetchone()
            parent_id = row[0] if row else None
        
        cursor.execute("""
            INSERT OR IGNORE INTO work_context (entity_type, name, parent_id, description, confirmed, source)
            VALUES (?, ?, ?, ?, ?, 'brain_dump')
        """, (entity_type, name, parent_id, description, confirmed))
        
        entity_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return entity_id
    
    def confirm_entity(self, entity_id: int):
        """Confirm a discovered entity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE work_context SET confirmed = 1 WHERE id = ?", (entity_id,))
        conn.commit()
        conn.close()
    
    def get_unconfirmed_entities(self) -> List[Dict]:
        """Get entities discovered but not confirmed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, entity_type, name, description 
            FROM work_context 
            WHERE confirmed = 0
            ORDER BY created_at DESC
        """)
        
        entities = [
            {"id": r[0], "type": r[1], "name": r[2], "description": r[3]}
            for r in cursor.fetchall()
        ]
        
        conn.close()
        return entities
    
    def get_all_context(self) -> List[Dict]:
        """Get all work context entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT wc.id, wc.entity_type, wc.name, wc.parent_id, 
                   p.name as parent_name, wc.description, wc.confirmed, wc.source
            FROM work_context wc
            LEFT JOIN work_context p ON wc.parent_id = p.id
            ORDER BY wc.entity_type, wc.name
        """)
        
        entries = [
            {
                "id": r[0], "type": r[1], "name": r[2], 
                "parent_id": r[3], "parent_name": r[4],
                "description": r[5], "confirmed": bool(r[6]), "source": r[7]
            }
            for r in cursor.fetchall()
        ]
        
        conn.close()
        return entries


# Global instance
work_context = WorkContextService()
