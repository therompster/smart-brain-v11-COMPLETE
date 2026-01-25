"""Enhanced daily planning service using profile data."""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any
from loguru import logger

from src.config import settings


class DailyPlanningService:
    """Generate focused daily plans using profile data."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
    
    def generate_plan(self) -> Dict[str, Any]:
        """Generate daily plan with profile-aware prioritization."""
        profile = self._get_profile()
        tasks = self._get_candidate_tasks()
        
        if not tasks:
            return {
                "current_task": None,
                "upcoming": [],
                "message": "All clear! No urgent tasks right now.",
                "insights": []
            }
        
        # Score tasks using profile
        scored = self._score_tasks_with_profile(tasks, profile)
        daily_tasks = scored[:5]
        scheduled = self._schedule_tasks(daily_tasks, profile)
        
        # Generate insights
        insights = self._generate_insights(profile)
        
        return {
            "current_task": scheduled[0] if scheduled else None,
            "upcoming": scheduled[1:],
            "total_time_minutes": sum(t['duration'] for t in scheduled),
            "message": self._generate_message(scheduled, profile),
            "insights": insights
        }
    
    def _get_profile(self) -> Dict[str, str]:
        """Get user profile data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM profile_data")
        profile = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return profile
    
    def _get_candidate_tasks(self) -> List[Dict]:
        """Get open tasks."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, action, priority, estimated_duration_minutes, domain, created_at
            FROM tasks
            WHERE status = 'open'
            ORDER BY created_at ASC
            LIMIT 20
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'action': row[1],
                'priority': row[2],
                'duration': row[3] or 30,
                'domain': row[4],
                'created_at': row[5]
            }
            for row in rows
        ]
    
    def _score_tasks_with_profile(self, tasks: List[Dict], profile: Dict) -> List[Dict]:
        """Score tasks using profile and learned weights."""
        from src.services.priority_learning_service import priority_learning
        from src.services.threshold_service import threshold_service
        
        weights = priority_learning.get_all_weights()
        company = profile.get('company', '').lower()
        
        for task in tasks:
            score = 0
            
            # Learned priority weights
            priority_weight = weights.get(f'priority_{task["priority"]}', 5.0)
            score += priority_weight
            
            # Profile-based boosting
            if company in task['domain']:
                score += weights.get('main_company_boost', 5.0)
            
            # Age penalty using learned weights
            age_days = (datetime.now() - datetime.fromisoformat(task['created_at'])).days
            if age_days > 7:
                score += weights.get('age_7day_boost', 3.0)
            elif age_days > 3:
                score += weights.get('age_3day_boost', 1.0)
            
            # Quick wins using learned threshold
            quick_win_mins = int(threshold_service.get('quick_win_minutes'))
            if task['duration'] <= quick_win_mins:
                score += weights.get('quick_win_boost', 2.0)
            
            task['score'] = score
        
        return sorted(tasks, key=lambda t: t['score'], reverse=True)
    
    def _schedule_tasks(self, tasks: List[Dict], profile: Dict) -> List[Dict]:
        """Schedule tasks based on profile work hours."""
        current_time = datetime.now()
        start_hour = current_time.hour + 1
        
        scheduled = []
        for task in tasks:
            scheduled.append({
                **task,
                'suggested_time': f"{start_hour % 12 or 12}:00 {'PM' if start_hour >= 12 else 'AM'}"
            })
            hours_needed = (task['duration'] + 59) // 60
            start_hour += hours_needed
        
        return scheduled
    
    def _generate_insights(self, profile: Dict) -> List[str]:
        """Generate actionable insights."""
        insights = []
        
        # Check for neglected domains
        neglect = self._check_domain_neglect()
        if neglect:
            insights.extend(neglect)
        
        # Check work patterns
        patterns = self._check_work_patterns()
        if patterns:
            insights.extend(patterns)
        
        return insights
    
    def _check_domain_neglect(self) -> List[str]:
        """Check if any domain is being neglected."""
        from src.services.threshold_service import threshold_service
        neglect_days = int(threshold_service.get('domain_neglect_days'))
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT domain, MAX(completed_at) as last_completed
            FROM tasks
            WHERE status = 'completed' AND completed_at IS NOT NULL
            GROUP BY domain
        """)
        
        insights = []
        for row in cursor.fetchall():
            domain = row[0]
            last = row[1]
            
            if last:
                days_ago = (datetime.now() - datetime.fromisoformat(last)).days
                
                if days_ago >= neglect_days:
                    domain_name = domain.split('/')[-1].title()
                    insights.append(f"⚠️ {domain_name} work hasn't been touched in {days_ago} days")
        
        conn.close()
        return insights
    
    def _check_work_patterns(self) -> List[str]:
        """Analyze work patterns."""
        from src.services.threshold_service import threshold_service
        overload_ratio = threshold_service.get('task_overload_ratio')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE created_at > datetime('now', '-7 days')")
        created_week = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE completed_at > datetime('now', '-7 days')")
        completed_week = cursor.fetchone()[0]
        
        conn.close()
        
        insights = []
        if completed_week > 0 and created_week > completed_week * overload_ratio:
            insights.append("🔥 Tasks piling up. Focus on completion over creation.")
        
        return insights
    
    def _generate_message(self, scheduled: List[Dict], profile: Dict) -> str:
        """Generate personalized message."""
        if not scheduled:
            return "You're all caught up! 🎉"
        
        total_time = sum(t['duration'] for t in scheduled)
        hours = total_time // 60
        mins = total_time % 60
        time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
        
        return f"Focus on {len(scheduled)} tasks today ({time_str}). You've got this!"


# Global instance
daily_planning_service = DailyPlanningService()
