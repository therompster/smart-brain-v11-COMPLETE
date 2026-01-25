"""Task extraction service."""

import re
from typing import List
from loguru import logger

from src.models.workflow_state import Task, TaskStatus, Priority
from src.llm.ollama_client import llm


TASK_EXTRACTION_PROMPT = """Extract all action items and tasks from this note.

Look for:
- Explicit tasks with checkboxes [ ]
- "need to", "should", "must", "have to"
- Action verbs (schedule, review, create, fix, etc)
- Questions that require action

For each task, provide:
- Original text
- Rewritten as verb-first action (e.g., "Schedule meeting with John")
- Priority (high/medium/low)
- Estimated duration in minutes

Note content:
---
{content}
---

Output JSON:
{{
  "tasks": [
    {{
      "text": "original text from note",
      "action": "Verb-first action description",
      "priority": "high|medium|low",
      "estimated_duration_minutes": 30
    }}
  ]
}}

Return ONLY the JSON."""


class TaskExtractionService:
    """Extract tasks from note content."""
    
    def extract_tasks(self, content: str, note_id: int, domain: str) -> List[Task]:
        """
        Extract tasks from note content.
        
        Args:
            content: Note text
            note_id: Note ID in database
            domain: Note domain
        
        Returns:
            List of extracted tasks
        """
        logger.info(f"Extracting tasks from note {note_id}")
        
        try:
            prompt = TASK_EXTRACTION_PROMPT.format(content=content)
            response = llm.generate_json(prompt, task_type='task_extraction')
            
            tasks_data = response.get("tasks", [])
            
            if not tasks_data:
                logger.info("No tasks found")
                return []
            
            tasks = []
            for task_dict in tasks_data:
                try:
                    # Parse priority
                    priority_str = task_dict.get("priority", "medium").lower()
                    if priority_str not in ["high", "medium", "low"]:
                        priority_str = "medium"
                    
                    task = Task(
                        text=task_dict["text"],
                        action=task_dict["action"],
                        priority=Priority(priority_str),
                        estimated_duration_minutes=task_dict.get("estimated_duration_minutes"),
                        domain=domain,
                        source_note_id=note_id,
                        status=TaskStatus.OPEN
                    )
                    tasks.append(task)
                    
                except Exception as e:
                    logger.error(f"Failed to parse task: {e}")
                    continue
            
            logger.success(f"Extracted {len(tasks)} tasks")
            return tasks
            
        except Exception as e:
            logger.error(f"Task extraction failed: {e}")
            return []


# Global instance
task_extraction_service = TaskExtractionService()
