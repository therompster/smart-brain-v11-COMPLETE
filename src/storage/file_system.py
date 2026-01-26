"""File storage service - writes notes to vault."""

import sqlite3
from pathlib import Path
from datetime import datetime
from loguru import logger

from src.models.workflow_state import RoutedNote
from src.config import settings


class FileStorageService:
    def __init__(self):
        self.vault_path = Path(settings.vault_path)
        self.db_path = settings.sqlite_db_path
    
    def write_note(self, note: RoutedNote, source_file: str) -> Path:
        file_path = self._generate_file_path(note)
        markdown = self._generate_markdown(note)
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(markdown, encoding="utf-8")
        
        logger.info(f"Wrote note: {file_path}")
        self._store_in_db(note, file_path, source_file)
        
        return file_path
    
    def _generate_file_path(self, note: RoutedNote) -> Path:
        safe_title = note.title.lower()
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in safe_title)
        safe_title = safe_title.replace(" ", "-")[:100]
        
        subdir = {"Project": "projects", "Area": "areas", "Note": "notes"}.get(note.type.value, "notes")
        path = self.vault_path / note.domain / subdir / f"{safe_title}.md"
        
        if path.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = path.with_stem(f"{safe_title}-{timestamp}")
        
        return path
    
    def _generate_markdown(self, note: RoutedNote) -> str:
        return f"""---
title: "{note.title}"
domain: {note.domain}
type: {note.type.value}
created: {datetime.now().isoformat()}
tags: [{", ".join(note.keywords)}]
---

{note.content}
"""
    
    def _store_in_db(self, note: RoutedNote, file_path: Path, source_file: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notes (title, content, domain, type, file_path, source_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (note.title, note.content, note.domain, note.type.value, str(file_path), source_file))
        conn.commit()
        conn.close()


file_storage = FileStorageService()
