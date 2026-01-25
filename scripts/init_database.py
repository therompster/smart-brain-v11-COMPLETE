#!/usr/bin/env python3
"""Initialize SQLite database with schema."""

import sqlite3
from pathlib import Path
from loguru import logger


def init_database(db_path: str = "data/smart_brain.db"):
    """Create database and tables."""
    
    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    
    logger.info(f"Initializing database at {db_path}")
    
    # Notes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        domain TEXT NOT NULL,
        type TEXT NOT NULL,
        file_path TEXT UNIQUE NOT NULL,
        source_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata JSON
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_domain ON notes(domain)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at)")
    
    # Tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'medium',
        estimated_duration_minutes INTEGER,
        actual_duration_minutes INTEGER,
        energy_required TEXT,
        energy_type TEXT,
        focus_required TEXT,
        due_date DATE,
        domain TEXT,
        source_note_id INTEGER,
        parent_task_id INTEGER,
        project_id INTEGER,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata JSON,
        FOREIGN KEY (source_note_id) REFERENCES notes(id),
        FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks(domain)")
    
    # Decisions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        source_note_id INTEGER,
        domain TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata JSON,
        FOREIGN KEY (source_note_id) REFERENCES notes(id)
    )
    """)
    
    # Questions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT,
        status TEXT DEFAULT 'open',
        source_note_id INTEGER,
        domain TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        answered_at TIMESTAMP,
        metadata JSON,
        FOREIGN KEY (source_note_id) REFERENCES notes(id)
    )
    """)
    
    # Blockers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blockers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        related_task_id INTEGER,
        source_note_id INTEGER,
        domain TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        resolution TEXT,
        metadata JSON,
        FOREIGN KEY (related_task_id) REFERENCES tasks(id),
        FOREIGN KEY (source_note_id) REFERENCES notes(id)
    )
    """)
    
    # Processing log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processing_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT NOT NULL,
        status TEXT NOT NULL,
        error_message TEXT,
        clusters_generated INTEGER,
        notes_created INTEGER,
        tasks_extracted INTEGER,
        processing_time_seconds REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata JSON
    )
    """)
    
    # User profile (basic for Phase 1)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        onboarding_completed BOOLEAN DEFAULT 0,
        profile_completeness_score REAL DEFAULT 0.0
    )
    """)
    
    # Insert default profile if not exists
    cursor.execute("""
    INSERT OR IGNORE INTO user_profile (id) VALUES (1)
    """)
    
    conn.commit()
    conn.close()
    
    logger.success(f"Database initialized successfully at {db_path}")


if __name__ == "__main__":
    init_database()
