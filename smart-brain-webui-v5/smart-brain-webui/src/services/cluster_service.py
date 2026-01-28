"""Clustering service - breaks brain dumps into 3-7 structured notes."""

from typing import List
from loguru import logger

from src.models.workflow_state import ClusterNote, NoteType
from src.llm.llm_service import llm_service as llm
from src.config import settings


class ClusterService:
    def cluster(self, content: str) -> List[ClusterNote]:
        logger.info("Clustering brain dump content")
        
        prompt = f"""Break this brain dump into distinct topics. For each topic provide:
title, content, type (Project/Area/Note), keywords.

Brain dump:
---
{content}
---

Output JSON:
{{"clusters": [{{"title": "...", "content": "...", "type": "Project|Area|Note", "keywords": []}}]}}

Return ONLY the JSON."""
        
        try:
            response = llm.generate_json(prompt, task_type='clustering')
            clusters_data = response.get("clusters", [])
            
            if not clusters_data:
                return [self._create_fallback_cluster(content)]
            
            clusters = []
            for c in clusters_data:
                try:
                    note_type = c.get("type", "Note")
                    if note_type not in ["Project", "Area", "Note"]:
                        note_type = "Note"
                    clusters.append(ClusterNote(
                        title=c["title"],
                        content=c["content"],
                        type=NoteType(note_type),
                        keywords=c.get("keywords", [])
                    ))
                except Exception as e:
                    logger.error(f"Failed to parse cluster: {e}")
            
            logger.success(f"Generated {len(clusters)} clusters")
            return clusters
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            return [self._create_fallback_cluster(content)]
    
    def _create_fallback_cluster(self, content: str) -> ClusterNote:
        return ClusterNote(title="Brain Dump", content=content, type=NoteType.NOTE, keywords=[])


cluster_service = ClusterService()
