"""Task extraction with ambiguity detection."""

from typing import List, Dict, Tuple
from loguru import logger

from src.models.workflow_state import Task, TaskStatus, Priority
from src.llm.ollama_client import llm


TASK_EXTRACTION_PROMPT = """Extract action items from this note.

For each task, determine if it's CLEAR or AMBIGUOUS.
- CLEAR: Has enough context to act on later
- AMBIGUOUS: Vague, missing context, future-you won't know what this means

For ambiguous tasks, generate a clarifying question.

Note content:
---
{content}
---

Output JSON:
{{
  "tasks": [
    {{
      "action": "Verb-first action description",
      "original_text": "The exact text from the note",
      "context": "Any surrounding context that helps explain it",
      "is_ambiguous": true/false,
      "clarifying_question": "What does X mean?" (only if ambiguous),
      "priority": "high|medium|low",
      "estimated_duration_minutes": 30
    }}
  ]
}}

Examples of AMBIGUOUS:
- "merge the output files" → Which files? From what?
- "KEYs for rag" → What about the keys? Add them? Review them?
- "Break down by property" → Break down what?

Examples of CLEAR:
- "Talk to Chris Hunter about extra AI engineering" → Clear person + topic
- "Add brand to RAG taxonomy part" → Clear action + location

Return ONLY the JSON."""


class TaskExtractionService:
    """Extract tasks, flagging ambiguous ones for clarification."""
    
    def extract_tasks(self, content: str, note_id: int, domain: str) -> Tuple[List[Task], List[Dict]]:
        """
        Extract tasks and return (tasks, questions_needed).
        
        Returns:
            Tuple of (list of tasks, list of clarification questions needed)
        """
        logger.info(f"Extracting tasks from note {note_id}")
        
        try:
            prompt = TASK_EXTRACTION_PROMPT.format(content=content)
            response = llm.generate_json(prompt, task_type='task_extraction')
            
            tasks_data = response.get("tasks", [])
            
            if not tasks_data:
                logger.info("No tasks found")
                return [], []
            
            tasks = []
            questions = []
            
            for i, task_dict in enumerate(tasks_data):
                try:
                    priority_str = task_dict.get("priority", "medium").lower()
                    if priority_str not in ["high", "medium", "low"]:
                        priority_str = "medium"
                    
                    # Handle empty/invalid duration
                    duration = task_dict.get("estimated_duration_minutes")
                    if not duration or duration == "":
                        duration = 30
                    else:
                        try:
                            duration = int(duration)
                        except (ValueError, TypeError):
                            duration = 30
                    
                    task = Task(
                        text=task_dict.get("original_text", task_dict.get("action", "")),
                        action=task_dict["action"],
                        priority=Priority(priority_str),
                        estimated_duration_minutes=duration,
                        domain=domain,
                        source_note_id=note_id,
                        status=TaskStatus.OPEN,
                        metadata={
                            "context": task_dict.get("context", ""),
                            "is_ambiguous": task_dict.get("is_ambiguous", False),
                            "temp_index": i  # For linking questions to tasks
                        }
                    )
                    tasks.append(task)
                    
                    # If ambiguous, queue a question
                    if task_dict.get("is_ambiguous") and task_dict.get("clarifying_question"):
                        questions.append({
                            "task_index": i,
                            "action": task_dict["action"],
                            "original_text": task_dict.get("original_text", ""),
                            "question": task_dict["clarifying_question"]
                        })
                    
                except Exception as e:
                    logger.error(f"Failed to parse task: {e}")
                    continue
            
            logger.success(f"Extracted {len(tasks)} tasks, {len(questions)} need clarification")
            
            # Suggest project assignments
            from src.services.project_service import project_service
            for task in tasks:
                if task.domain:
                    proj_id, proj_name, confidence = project_service.suggest_project(
                        f"{task.action}: {task.text}", task.domain
                    )
                    task.metadata["suggested_project_id"] = proj_id
                    task.metadata["suggested_project_name"] = proj_name
                    task.metadata["project_confidence"] = confidence
                    
                    # If new project suggested with high confidence
                    if not proj_id and proj_name and confidence > 0.7:
                        task.metadata["new_project_suggested"] = proj_name
            
            return tasks, questions
            
        except Exception as e:
            logger.error(f"Task extraction failed: {e}")
            return [], []
    
    def apply_clarifications(self, tasks: List[Task], answers: Dict[int, str]) -> List[Task]:
        """Apply user's clarification answers to tasks."""
        for task in tasks:
            idx = task.metadata.get("temp_index")
            if idx is not None and idx in answers:
                # Add clarification to context
                existing_context = task.metadata.get("context", "")
                task.metadata["context"] = f"{existing_context}\n\nClarification: {answers[idx]}".strip()
                task.metadata["is_ambiguous"] = False
                task.text = f"{task.text}\n→ {answers[idx]}"
        return tasks


# Global instance
task_extraction_service = TaskExtractionService()
