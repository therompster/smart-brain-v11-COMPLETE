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
    
    # Questions table - for clarification and open questions
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_domain ON questions(domain)")
    
    # Decisions table - for tracking decisions made
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_domain ON decisions(domain)")
    
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
        parent_project_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_project_id) REFERENCES projects(id)
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_domain ON projects(domain)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
    
    # Add parent_project_id to projects if not exists (for hierarchy)
    cursor.execute("PRAGMA table_info(projects)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'parent_project_id' not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN parent_project_id INTEGER REFERENCES projects(id)")
    
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


def add_email_task_support(db_path: str = "data/smart_brain.db"):
    """Add metadata column to tasks for email task tracking."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if metadata column exists
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'metadata' not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN metadata JSON")
        logger.info("Added metadata column to tasks table")
    
    conn.commit()
    conn.close()
    logger.success("Email task support added")


if __name__ == "__main__":
    init_database()
    add_projects_table()
    add_email_task_support()


def add_financial_tables(db_path: str = "data/smart_brain.db"):
    """Add financial tracking tables: bills, subscriptions, loans."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Bills table - one-time payments (utilities, invoices, medical)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        due_date DATE,
        category TEXT,
        vendor TEXT,
        status TEXT DEFAULT 'pending',
        paid_date DATE,
        paid_amount REAL,
        source TEXT,
        source_email_id TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_due_date ON bills(due_date)")
    
    # Subscriptions table - recurring payments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        frequency TEXT NOT NULL,
        category TEXT,
        vendor TEXT,
        status TEXT DEFAULT 'active',
        start_date DATE,
        next_due_date DATE,
        last_paid_date DATE,
        payment_method TEXT,
        auto_pay BOOLEAN DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_next_due ON subscriptions(next_due_date)")
    
    # Loans table - amortized debt
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        lender TEXT,
        loan_type TEXT,
        original_principal REAL NOT NULL,
        current_balance REAL,
        interest_rate REAL NOT NULL,
        term_months INTEGER NOT NULL,
        start_date DATE NOT NULL,
        monthly_payment REAL,
        payment_due_day INTEGER,
        status TEXT DEFAULT 'active',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status)")
    
    # Loan payments table - track actual payments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loan_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id INTEGER NOT NULL,
        payment_date DATE NOT NULL,
        amount REAL NOT NULL,
        principal_amount REAL,
        interest_amount REAL,
        extra_principal REAL DEFAULT 0,
        balance_after REAL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loan_id) REFERENCES loans(id)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_loan_payments_loan ON loan_payments(loan_id)")
    
    # Transactions table - imported from bank
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT,
        account TEXT,
        transaction_type TEXT,
        matched_bill_id INTEGER,
        matched_subscription_id INTEGER,
        matched_loan_id INTEGER,
        import_source TEXT,
        import_id TEXT UNIQUE,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (matched_bill_id) REFERENCES bills(id),
        FOREIGN KEY (matched_subscription_id) REFERENCES subscriptions(id),
        FOREIGN KEY (matched_loan_id) REFERENCES loans(id)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category)")
    
    conn.commit()
    conn.close()
    logger.success("Financial tables added: bills, subscriptions, loans, loan_payments, transactions")


def add_questions_decisions_tables(db_path: str = "data/smart_brain.db"):
    """Add questions and decisions tables for brain dump item types."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_domain ON questions(domain)")
    
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_domain ON decisions(domain)")
    
    conn.commit()
    conn.close()
    logger.success("Questions and decisions tables added")


def add_topics_table(db_path: str = "data/smart_brain.db"):
    """Add topics table for project->topic->task hierarchy."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_id INTEGER,
            description TEXT,
            keywords TEXT,
            status TEXT DEFAULT 'active',
            source TEXT DEFAULT 'learned',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_project ON topics(project_id)")
    
    # Add topic_id to tasks if not exists
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'topic_id' not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN topic_id INTEGER REFERENCES topics(id)")
    
    # Add topic_id to notes if not exists
    cursor.execute("PRAGMA table_info(notes)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'topic_id' not in columns:
        cursor.execute("ALTER TABLE notes ADD COLUMN topic_id INTEGER REFERENCES topics(id)")
    
    conn.commit()
    conn.close()
    logger.success("Topics table added")


def add_systems_interview_tables(db_path: str = "data/smart_brain.db"):
    """Add tables for systems interview - learned work context."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Work context - platforms, systems, relationships
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            relationships TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_context_type ON work_context(context_type)")
    
    # People registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            role TEXT,
            team TEXT,
            project_ids TEXT,
            notes TEXT,
            source TEXT DEFAULT 'learned',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_name ON people(name)")
    
    # Interview state - track what's been asked
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_state (
            id INTEGER PRIMARY KEY DEFAULT 1,
            completed BOOLEAN DEFAULT 0,
            current_step TEXT,
            context_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.success("Systems interview tables added")
