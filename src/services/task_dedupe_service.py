"""Task deduplication service using embeddings."""

from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

from src.models.workflow_state import Task
from src.config import settings


class TaskDedupeService:
    """Deduplicate tasks using semantic similarity."""
    
    def __init__(self):
        logger.info("Loading embedding model...")
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.success("Embedding model loaded")
    
    def deduplicate(self, tasks: List[Task]) -> List[Task]:
        """
        Remove duplicate tasks based on semantic similarity.
        
        Args:
            tasks: List of tasks to deduplicate
        
        Returns:
            Deduplicated task list
        """
        if len(tasks) <= 1:
            return tasks
        
        logger.info(f"Deduplicating {len(tasks)} tasks")
        
        # Generate embeddings for all task actions
        actions = [task.action for task in tasks]
        embeddings = self.model.encode(actions)
        
        # Calculate cosine similarity matrix
        similarities = np.inner(embeddings, embeddings)
        
        # Track which tasks to keep
        keep_indices = []
        seen = set()
        
        for i in range(len(tasks)):
            if i in seen:
                continue
            
            keep_indices.append(i)
            
            # Mark similar tasks as seen
            for j in range(i + 1, len(tasks)):
                if similarities[i][j] > settings.task_dedupe_threshold:
                    seen.add(j)
                    logger.debug(f"Duplicate: '{tasks[j].action}' similar to '{tasks[i].action}' ({similarities[i][j]:.2f})")
        
        unique_tasks = [tasks[i] for i in keep_indices]
        
        logger.success(f"Kept {len(unique_tasks)} unique tasks (removed {len(tasks) - len(unique_tasks)} duplicates)")
        
        return unique_tasks


# Global instance
task_dedupe_service = TaskDedupeService()
