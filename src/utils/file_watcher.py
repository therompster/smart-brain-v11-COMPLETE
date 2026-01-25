"""File watcher for inbox directory."""

import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from loguru import logger

from src.config import settings
from src.agents.process_agent import process_brain_dump


class BrainDumpHandler(FileSystemEventHandler):
    """Handler for brain dump file events."""
    
    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Only process markdown files
        if file_path.suffix.lower() not in ['.md', '.markdown', '.txt']:
            return
        
        logger.info(f"New brain dump detected: {file_path.name}")
        
        # Small delay to ensure file is fully written
        time.sleep(0.5)
        
        try:
            process_brain_dump(str(file_path))
            
            # Archive processed file
            archive_path = Path(settings.archive_path) / file_path.name
            file_path.rename(archive_path)
            logger.info(f"Archived to: {archive_path}")
            
        except Exception as e:
            logger.error(f"Failed to process {file_path.name}: {e}")


class FileWatcher:
    """Watches inbox directory for new brain dumps."""
    
    def __init__(self):
        self.inbox_path = Path(settings.inbox_path)
        self.observer = Observer()
    
    def start(self):
        """Start watching inbox directory."""
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        
        event_handler = BrainDumpHandler()
        self.observer.schedule(event_handler, str(self.inbox_path), recursive=False)
        self.observer.start()
        
        logger.success(f"Watching inbox: {self.inbox_path}")
        logger.info("Drop brain dumps (*.md, *.txt) in inbox/ to process")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")


# Global watcher instance
watcher = FileWatcher()
