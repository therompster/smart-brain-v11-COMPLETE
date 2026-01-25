#!/usr/bin/env python3
"""Main entry point for Smart Second Brain."""

import sys
from pathlib import Path
from loguru import logger

from src.config import settings
from src.llm.ollama_client import llm
from src.utils.file_watcher import watcher
from src.agents.process_agent import process_brain_dump


def setup_logging():
    """Configure logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    # Log to file
    log_path = Path(settings.log_path) / "smart_brain.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days"
    )


def cmd_watch():
    """Watch inbox for new brain dumps."""
    logger.info("Starting Smart Second Brain")
    
    # Test Ollama connection
    if not llm.test_connection():
        logger.error("Ollama connection failed. Is Ollama running?")
        logger.info("Start Ollama and pull required models:")
        logger.info(f"  ollama pull {settings.ollama_primary_model}")
        logger.info(f"  ollama pull {settings.ollama_fallback_model}")
        sys.exit(1)
    
    # Ensure directories exist
    settings.ensure_directories()
    
    # Start watching
    watcher.start()


def cmd_process(file_path: str):
    """Process a single brain dump file."""
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    
    # Test Ollama connection
    if not llm.test_connection():
        logger.error("Ollama connection failed")
        sys.exit(1)
    
    # Ensure directories exist
    settings.ensure_directories()
    
    # Process file
    result = process_brain_dump(file_path)
    
    if result.status == "complete":
        logger.success(f"Created {len(result.routed_notes)} notes")
        for note in result.routed_notes:
            logger.info(f"  - {note.title} ({note.domain})")
    else:
        logger.error(f"Processing failed: {result.errors}")
        sys.exit(1)


def cmd_test():
    """Test Ollama connection and configuration."""
    logger.info("Testing configuration...")
    
    # Test Ollama
    if llm.test_connection():
        logger.success("✓ Ollama connection OK")
    else:
        logger.error("✗ Ollama connection failed")
        return
    
    # Test directories
    settings.ensure_directories()
    logger.success("✓ Directories created")
    
    # Test database
    from scripts.init_database import init_database
    init_database(settings.sqlite_db_path)
    logger.success("✓ Database initialized")
    
    logger.success("All tests passed!")


def main():
    """Main CLI entry point."""
    setup_logging()
    
    if len(sys.argv) < 2:
        print("Smart Second Brain")
        print()
        print("Usage:")
        print("  python src/main.py watch              - Watch inbox for brain dumps")
        print("  python src/main.py process <file>     - Process a single file")
        print("  python src/main.py test               - Test configuration")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "watch":
        cmd_watch()
    elif command == "process":
        if len(sys.argv) < 3:
            logger.error("Usage: python src/main.py process <file>")
            sys.exit(1)
        cmd_process(sys.argv[2])
    elif command == "test":
        cmd_test()
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
