#!/usr/bin/env python3
"""Initialize SQLite database with schema."""

import sqlite3
from pathlib import Path
from loguru import logger


def init_database(db_path: str = "data/smart_brain.db"):
    """Create database and tables."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    
    logger.info(f"Initializing database at {db_path}")
    
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
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'medium',
        estimated_duration_minutes INTEGER,
        domain TEXT,
        source_note_id INTEGER,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (source_note_id) REFERENCES notes(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        onboarding_completed BOOLEAN DEFAULT 0,
        profile_completeness_score REAL DEFAULT 0.0
    )
    """)
    
    cursor.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")
    
    conn.commit()
    conn.close()
    
    logger.success(f"Database initialized successfully at {db_path}")


if __name__ == "__main__":
    init_database()


def add_projects_table(db_path: str = "data/smart_brain.db"):
    """Add projects table and update tasks."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Projects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        domain TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'active',
        keywords TEXT,
        confidence REAL DEFAULT 1.0,
        source TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_domain ON projects(domain)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
    
    # Add project_id to tasks if not exists
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'project_id' not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id)")
    
    # Project assignment confidence tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        project_id INTEGER,
        confidence REAL,
        confirmed BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES tasks(id),
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )
    """)
    
    conn.commit()
    conn.close()
    logger.success("Projects table added")


if __name__ == "__main__":
    init_database()
    add_projects_table()
