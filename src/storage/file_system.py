"""File storage service - writes notes to vault."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List
from loguru import logger

from src.models.workflow_state import RoutedNote
from src.config import settings


class FileStorageService:
    """Service for writing notes to filesystem and database."""
    
    def __init__(self):
        self.vault_path = Path(settings.vault_path)
        self.db_path = settings.sqlite_db_path
    
    def write_note(self, note: RoutedNote, source_file: str) -> Path:
        """
        Write note to vault as markdown file and database.
        
        Args:
            note: Routed note to write
            source_file: Original brain dump file
        
        Returns:
            Path to created note file
        """
        # Generate file path
        file_path = self._generate_file_path(note)
        
        # Create markdown content
        markdown = self._generate_markdown(note)
        
        # Write file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(markdown, encoding="utf-8")
        
        logger.info(f"Wrote note: {file_path}")
        
        # Store in database
        self._store_in_db(note, file_path, source_file)
        
        return file_path
    
    def _generate_file_path(self, note: RoutedNote) -> Path:
        """Generate file path for note based on PARA structure."""
        # Sanitize title for filename
        safe_title = note.title.lower()
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in safe_title)
        safe_title = safe_title.replace(" ", "-")[:100]
        
        # Determine subdirectory based on type
        subdir = {
            "Project": "projects",
            "Area": "areas",
            "Note": "notes"
        }.get(note.type.value, "notes")
        
        # Build path: vault/domain/subdir/title.md
        path = self.vault_path / note.domain / subdir / f"{safe_title}.md"
        
        # Handle duplicates
        if path.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = path.with_stem(f"{safe_title}-{timestamp}")
        
        return path
    
    def _generate_markdown(self, note: RoutedNote) -> str:
        """Generate markdown content with frontmatter."""
        frontmatter = f"""---
title: "{note.title}"
domain: {note.domain}
type: {note.type.value}
created: {datetime.now().isoformat()}
tags: [{", ".join(note.keywords)}]
---

"""
        
        content = frontmatter + note.content
        
        return content
    
    def _store_in_db(self, note: RoutedNote, file_path: Path, source_file: str):
        """Store note metadata in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO notes (title, content, domain, type, file_path, source_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            note.title,
            note.content,
            note.domain,
            note.type.value,
            str(file_path),
            source_file
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Stored note in database: {note.title}")


# Global service instance
file_storage = FileStorageService()
