"""Task deduplication service using embeddings."""

from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

from src.models.workflow_state import Task
from src.config import settings


class TaskDedupeService:
    def __init__(self):
        logger.info("Loading embedding model...")
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.success("Embedding model loaded")
    
    def deduplicate(self, tasks: List[Task]) -> List[Task]:
        if len(tasks) <= 1:
            return tasks
        
        logger.info(f"Deduplicating {len(tasks)} tasks")
        
        actions = [task.action for task in tasks]
        embeddings = self.model.encode(actions)
        similarities = np.inner(embeddings, embeddings)
        
        keep_indices = []
        seen = set()
        
        for i in range(len(tasks)):
            if i in seen:
                continue
            keep_indices.append(i)
            for j in range(i + 1, len(tasks)):
                if similarities[i][j] > settings.task_dedupe_threshold:
                    seen.add(j)
        
        unique_tasks = [tasks[i] for i in keep_indices]
        logger.success(f"Kept {len(unique_tasks)} unique tasks")
        
        return unique_tasks


task_dedupe_service = TaskDedupeService()
