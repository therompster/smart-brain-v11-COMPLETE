"""LangGraph workflow for processing brain dumps."""

import time
from pathlib import Path
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from loguru import logger

from src.models.workflow_state import WorkflowState
from src.services.cluster_service import cluster_service
from src.services.route_service import route_service
from src.storage.file_system import file_storage


def read_file(state: WorkflowState) -> Dict[str, Any]:
    """Read brain dump file."""
    logger.info(f"Reading file: {state.file_path}")
    
    try:
        content = Path(state.file_path).read_text(encoding="utf-8")
        return {"raw_content": content}
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return {"status": "error", "errors": [str(e)]}


def cluster_content(state: WorkflowState) -> Dict[str, Any]:
    """Cluster brain dump into structured notes."""
    logger.info("Clustering content")
    
    try:
        clusters = cluster_service.cluster(state.raw_content)
        return {"clusters": clusters}
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        return {"status": "error", "errors": state.errors + [str(e)]}


def route_notes(state: WorkflowState) -> Dict[str, Any]:
    """Route notes to PARA domains."""
    logger.info(f"Routing {len(state.clusters)} notes")
    
    try:
        routed = [route_service.route(cluster) for cluster in state.clusters]
        return {"routed_notes": routed}
    except Exception as e:
        logger.error(f"Routing failed: {e}")
        return {"status": "error", "errors": state.errors + [str(e)]}


def write_notes(state: WorkflowState) -> Dict[str, Any]:
    """Write notes to vault."""
    logger.info(f"Writing {len(state.routed_notes)} notes")
    
    try:
        written_paths = []
        for note in state.routed_notes:
            path = file_storage.write_note(note, state.file_path)
            written_paths.append(str(path))
        
        return {
            "status": "complete",
            "metadata": {"written_files": written_paths}
        }
    except Exception as e:
        logger.error(f"Writing notes failed: {e}")
        return {"status": "error", "errors": state.errors + [str(e)]}


def log_completion(state: WorkflowState) -> Dict[str, Any]:
    """Log processing completion."""
    if state.status == "complete":
        logger.success(f"Processed {state.file_path}: {len(state.routed_notes)} notes created")
    else:
        logger.error(f"Processing failed for {state.file_path}: {state.errors}")
    
    return {}


# Build workflow
workflow = StateGraph(WorkflowState)

# Add nodes
workflow.add_node("read_file", read_file)
workflow.add_node("cluster", cluster_content)
workflow.add_node("route", route_notes)
workflow.add_node("write", write_notes)
workflow.add_node("log", log_completion)

# Define edges
workflow.set_entry_point("read_file")
workflow.add_edge("read_file", "cluster")
workflow.add_edge("cluster", "route")
workflow.add_edge("route", "write")
workflow.add_edge("write", "log")
workflow.add_edge("log", END)

# Compile
app = workflow.compile()


def process_brain_dump(file_path: str) -> WorkflowState:
    """
    Process a brain dump file through the workflow.
    
    Args:
        file_path: Path to brain dump markdown file
    
    Returns:
        Final workflow state
    """
    start_time = time.time()
    
    logger.info(f"Starting workflow for: {file_path}")
    
    initial_state = WorkflowState(file_path=file_path)
    final_state = app.invoke(initial_state)
    
    elapsed = time.time() - start_time
    logger.info(f"Workflow completed in {elapsed:.2f}s")
    
    # Log to database
    _log_processing(file_path, final_state, elapsed)
    
    return final_state


def _log_processing(file_path: str, state: WorkflowState, elapsed: float):
    """Log processing to database."""
    import sqlite3
    from src.config import settings
    
    conn = sqlite3.connect(settings.sqlite_db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO processing_log (
            source_file, status, clusters_generated, notes_created,
            processing_time_seconds, error_message
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        file_path,
        state.status,
        len(state.clusters),
        len(state.routed_notes),
        elapsed,
        "; ".join(state.errors) if state.errors else None
    ))
    
    conn.commit()
    conn.close()
