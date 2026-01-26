"""Enhanced daily planning service using profile data."""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

from src.config import settings


class DailyPlanningService:
    def __init__(self):
        self.db_path = settings.sqlite_db_path
    
    def generate_plan(self) -> Dict[str, Any]:
        profile = self._get_profile()
        tasks = self._get_candidate_tasks()
        
        if not tasks:
            return {"current_task": None, "upcoming": [], "message": "All clear!", "insights": []}
        
        scored = self._score_tasks(tasks, profile)
        daily_tasks = scored[:5]
        scheduled = self._schedule_tasks(daily_tasks, profile)
        
        return {
            "current_task": scheduled[0] if scheduled else None,
            "upcoming": scheduled[1:],
            "total_time_minutes": sum(t['duration'] for t in scheduled),
            "message": f"Focus on {len(scheduled)} tasks today.",
            "insights": self._generate_insights()
        }
    
    def _get_profile(self) -> Dict[str, str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM profile_data")
        profile = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return profile
    
    def _get_candidate_tasks(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, action, priority, estimated_duration_minutes, domain, created_at
            FROM tasks WHERE status = 'open'
            ORDER BY created_at ASC LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [{'id': r[0], 'action': r[1], 'priority': r[2], 'duration': r[3] or 30, 
                 'domain': r[4], 'created_at': r[5]} for r in rows]
    
    def _score_tasks(self, tasks: List[Dict], profile: Dict) -> List[Dict]:
        company = profile.get('company', '').lower()
        for task in tasks:
            score = {'high': 10, 'medium': 5, 'low': 0}.get(task['priority'], 5)
            if company and company in (task.get('domain') or ''):
                score += 5
            task['score'] = score
        return sorted(tasks, key=lambda t: t['score'], reverse=True)
    
    def _schedule_tasks(self, tasks: List[Dict], profile: Dict) -> List[Dict]:
        hour = datetime.now().hour + 1
        scheduled = []
        for task in tasks:
            scheduled.append({**task, 'suggested_time': f"{hour % 12 or 12}:00 {'PM' if hour >= 12 else 'AM'}"})
            hour += (task['duration'] + 59) // 60
        return scheduled
    
    def _generate_insights(self) -> List[str]:
        return []


daily_planning_service = DailyPlanningService()
