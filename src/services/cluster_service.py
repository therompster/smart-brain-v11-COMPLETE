"""Clustering service - breaks brain dumps into 3-7 structured notes."""

from typing import List
from loguru import logger

from src.models.workflow_state import ClusterNote, NoteType
from src.llm.ollama_client import llm
from src.config import settings


CLUSTERING_PROMPT = """You are a note-taking assistant. Break this brain dump into {min_clusters} to {max_clusters} distinct topics.

For each topic:
- Create a clear, descriptive title
- Extract and organize the relevant content
- Suggest a note type (Project/Area/Note)
- Identify 2-5 keywords

Rules:
- Each cluster should be a cohesive topic
- Don't create clusters for trivial mentions
- Rewrite content for clarity (not verbatim copy)
- If the dump has < 3 topics, that's fine

Output JSON format:
{{
  "clusters": [
    {{
      "title": "Clear descriptive title",
      "content": "Organized content for this topic",
      "type": "Project|Area|Note",
      "keywords": ["keyword1", "keyword2"]
    }}
  ]
}}

Brain dump:
---
{content}
---

Return ONLY the JSON, no preamble."""


class ClusterService:
    """Service for clustering brain dump content."""
    
    def cluster(self, content: str) -> List[ClusterNote]:
        """
        Break brain dump into 3-7 structured notes.
        
        Args:
            content: Raw brain dump text
        
        Returns:
            List of clustered notes
        """
        logger.info("Clustering brain dump content")
        
        prompt = CLUSTERING_PROMPT.format(
            min_clusters=settings.min_clusters,
            max_clusters=settings.max_clusters,
            content=content
        )
        
        try:
            response = llm.generate_json(prompt, task_type='clustering')
            
            clusters_data = response.get("clusters", [])
            
            if not clusters_data:
                logger.warning("No clusters generated, creating single note")
                return [self._create_fallback_cluster(content)]
            
            clusters = []
            for cluster_dict in clusters_data:
                try:
                    # Validate note type
                    note_type = cluster_dict.get("type", "Note")
                    if note_type not in ["Project", "Area", "Note"]:
                        note_type = "Note"
                    
                    cluster = ClusterNote(
                        title=cluster_dict["title"],
                        content=cluster_dict["content"],
                        type=NoteType(note_type),
                        keywords=cluster_dict.get("keywords", [])
                    )
                    clusters.append(cluster)
                    
                except Exception as e:
                    logger.error(f"Failed to parse cluster: {e}")
                    continue
            
            # Validate cluster count
            if len(clusters) < settings.min_clusters:
                logger.warning(f"Only {len(clusters)} clusters, expected {settings.min_clusters}+")
            
            if len(clusters) > settings.max_clusters:
                logger.warning(f"Too many clusters ({len(clusters)}), keeping top {settings.max_clusters}")
                clusters = clusters[:settings.max_clusters]
            
            logger.success(f"Generated {len(clusters)} clusters")
            return clusters
            
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            return [self._create_fallback_cluster(content)]
    
    def _create_fallback_cluster(self, content: str) -> ClusterNote:
        """Create single cluster if LLM fails."""
        return ClusterNote(
            title="Brain Dump",
            content=content,
            type=NoteType.NOTE,
            keywords=[]
        )


# Global service instance
cluster_service = ClusterService()
