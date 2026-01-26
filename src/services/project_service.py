"""Project management with learning."""

import sqlite3
from typing import List, Dict, Optional, Tuple
from loguru import logger

from src.config import settings
from src.llm.ollama_client import llm


class ProjectService:
    """Manage projects with auto-suggestion and learning."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create projects table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, domain)
            )
        """)
        
        def _ensure_task_assignment_columns():
            conn = sqlite3.connect(settings.sqlite_db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(tasks)")
            cols = {r[1] for r in cur.fetchall()}

            if "project_assign_method" not in cols:
                cur.execute("ALTER TABLE tasks ADD COLUMN project_assign_method TEXT")
            if "project_assign_confidence" not in cols:
                cur.execute("ALTER TABLE tasks ADD COLUMN project_assign_confidence REAL")
            if "project_assign_needs_review" not in cols:
                cur.execute("ALTER TABLE tasks ADD COLUMN project_assign_needs_review INTEGER DEFAULT 0")

            conn.commit()
            conn.close()

        # Track project assignment confidence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_confidence (
                keywords TEXT,
                project_id INTEGER,
                correct_count INTEGER DEFAULT 0,
                incorrect_count INTEGER DEFAULT 0,
                PRIMARY KEY (keywords, project_id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def create_project(self, name: str, domain: str, description: str = "", keywords: str = "") -> int:
        """Create a new project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO projects (name, domain, description, keywords)
            VALUES (?, ?, ?, ?)
        """, (name, domain, description, keywords))
        
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.success(f"Created project: {name} in {domain}")
        return project_id
    
    def get_projects_for_domain(self, domain: str) -> List[Dict]:
        """Get all projects for a domain."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, status, keywords
            FROM projects
            WHERE domain = ? AND status = 'active'
            ORDER BY name
        """, (domain,))
        
        projects = [
            {"id": r[0], "name": r[1], "description": r[2], "status": r[3], "keywords": r[4]}
            for r in cursor.fetchall()
        ]
        conn.close()
        return projects
    
    def get_all_projects(self) -> List[Dict]:
        """Get all active projects grouped by domain."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, domain, description, status, keywords
            FROM projects
            WHERE status = 'active'
            ORDER BY domain, name
        """)
        
        projects = [
            {"id": r[0], "name": r[1], "domain": r[2], "description": r[3], "status": r[4], "keywords": r[5]}
            for r in cursor.fetchall()
        ]
        conn.close()
        return projects
    
    def suggest_project(self, content: str, domain: str) -> Tuple[Optional[int], str, float, Optional[str]]:
        """
        Suggest project for content. Returns (project_id, project_name, confidence, new_project_suggestion).
        
        If no good match, suggests a new project name.
        """
        projects = self.get_projects_for_domain(domain)
        
        if not projects:
            # No projects yet, suggest creating one
            new_name = self._extract_project_name(content)
            return None, "", 0.0, new_name
        
        # Check keyword matches first (learned patterns)
        keyword_match = self._keyword_match(content, projects)
        if keyword_match and keyword_match[2] > 0.7:
            return keyword_match[0], keyword_match[1], keyword_match[2], None
        
        # Use LLM to classify
        return self._llm_suggest(content, domain, projects)
    
    def _keyword_match(self, content: str, projects: List[Dict]) -> Optional[Tuple[int, str, float]]:
        """Match content to project using learned keywords."""
        content_lower = content.lower()
        
        best_match = None
        best_score = 0
        
        for proj in projects:
            if not proj["keywords"]:
                continue
            
            keywords = [k.strip().lower() for k in proj["keywords"].split(",")]
            matches = sum(1 for kw in keywords if kw and kw in content_lower)
            
            if keywords:
                score = matches / len(keywords)
                if score > best_score:
                    best_score = score
                    best_match = (proj["id"], proj["name"], min(score * 1.5, 0.95))
        
        return best_match
    
    def _llm_suggest(self, content: str, domain: str, projects: List[Dict]) -> Tuple[Optional[int], str, float, Optional[str]]:
        """Use LLM to suggest project."""
        project_list = "\n".join([f"- {p['name']}: {p['description'] or 'No description'}" for p in projects])
        
        prompt = f"""Given this content, which project does it belong to?

Content:
{content[:500]}

Available projects in {domain}:
{project_list}

If it clearly belongs to one project, respond with:
{{"project": "exact project name", "confidence": 0.0-1.0}}

If it doesn't fit any project well, suggest a new one:
{{"project": null, "new_project": "Suggested Name", "confidence": 0.0}}

Return ONLY JSON."""

        try:
            response = llm.generate_json(prompt, task_type='routing')
            
            if response.get("project"):
                # Find project by name
                for p in projects:
                    if p["name"].lower() == response["project"].lower():
                        return p["id"], p["name"], float(response.get("confidence", 0.7)), None
            
            # New project suggested
            return None, "", 0.0, response.get("new_project")
            
        except Exception as e:
            logger.error(f"Project suggestion failed: {e}")
            return None, "", 0.0, None
    
    def _extract_project_name(self, content: str) -> Optional[str]:
        """Extract a project name from content."""
        prompt = f"""What project or initiative is this content about? Give a short 2-4 word name.

Content:
{content[:300]}

Respond with ONLY the project name, nothing else."""

        try:
            name = llm.generate(prompt, task_type='routing', temperature=0.3)
            return name.strip().strip('"').strip("'")[:50]
        except:
            return None
    
    def record_feedback(self, content_keywords: str, project_id: int, was_correct: bool):
        """Record whether project assignment was correct."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if was_correct:
            cursor.execute("""
                INSERT INTO project_confidence (keywords, project_id, correct_count)
                VALUES (?, ?, 1)
                ON CONFLICT(keywords, project_id) DO UPDATE SET
                correct_count = correct_count + 1
            """, (content_keywords, project_id))
        else:
            cursor.execute("""
                INSERT INTO project_confidence (keywords, project_id, incorrect_count)
                VALUES (?, ?, 1)
                ON CONFLICT(keywords, project_id) DO UPDATE SET
                incorrect_count = incorrect_count + 1
            """, (content_keywords, project_id))
        
        conn.commit()
        conn.close()
    
    def add_learned_keywords(self, project_id: int, new_keywords: str):
        """Add keywords learned from user corrections."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT keywords FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        
        existing = set(row[0].split(",")) if row and row[0] else set()
        existing.update([k.strip().lower() for k in new_keywords.split(",")])
        
        cursor.execute("""
            UPDATE projects SET keywords = ? WHERE id = ?
        """, (",".join(existing), project_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Added keywords to project {project_id}: {new_keywords}")


    def get_projects(self, domain: Optional[str] = None) -> List[Dict]:
        """Get projects, optionally filtered by domain."""
        if domain:
            return self.get_projects_for_domain(domain)
        return self.get_all_projects()
    
    def assign_task_to_project(self, task_id: int, project_id: int):
        """Assign a task to a project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE tasks SET project_id = ? WHERE id = ?", (project_id, task_id))
        conn.commit()
        conn.close()
        logger.info(f"Assigned task {task_id} to project {project_id}")
    
    def learn_keywords(self, project_id: int, text: str):
        """Extract keywords from text and add to project."""
        # Simple keyword extraction - words > 4 chars
        words = [w.lower() for w in text.split() if len(w) > 4 and w.isalpha()]
        if words:
            self.add_learned_keywords(project_id, ",".join(words[:5]))
    
    def validate_assignments(self, domain: str) -> List[Dict]:
        """Check if tasks are correctly assigned and suggest corrections."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get tasks with their current project
        cursor.execute("""
            SELECT t.id, t.action, t.text, t.project_id, p.name
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.domain = ? AND t.status = 'open'
            LIMIT 20
        """, (domain,))
        
        tasks = cursor.fetchall()
        conn.close()
        
        suggestions = []
        projects = self.get_projects_for_domain(domain)
        
        if not projects:
            return []
        
        for task_id, action, text, current_proj_id, current_proj_name in tasks:
            content = f"{action}: {text}"
            suggested_id, suggested_name, confidence, new_proj = self.suggest_project(content, domain)
            
            # If suggestion differs from current with high confidence
            if suggested_id and suggested_id != current_proj_id and confidence > 0.7:
                suggestions.append({
                    "task_id": task_id,
                    "task_action": action,
                    "current_project": current_proj_name,
                    "suggested_project": suggested_name,
                    "suggested_project_id": suggested_id,
                    "confidence": confidence
                })
        
        return suggestions


# Global instance
project_service = ProjectService()
