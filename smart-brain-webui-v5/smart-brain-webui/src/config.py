"""Configuration management."""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # Azure OpenAI (preferred if configured)
    azure_openai_endpoint: str = Field(default="")
    azure_openai_api_key: str = Field(default="")
    azure_openai_deployment: str = Field(default="gpt-4o")
    azure_openai_api_version: str = Field(default="2024-02-15-preview")
    
    # Ollama - Fallback if Azure not configured
    ollama_host: str = Field(default="http://localhost:11434")
    ollama_task_extraction_model: str = Field(default="deepseek-r1:14b")
    ollama_entity_recognition_model: str = Field(default="qwen2.5:32b")
    ollama_routing_model: str = Field(default="qwen2.5:14b")
    ollama_clustering_model: str = Field(default="qwen2.5:14b")
    ollama_fallback_model: str = Field(default="llama3.1:8b")
    
    @property
    def use_azure(self) -> bool:
        """Check if Azure OpenAI is configured."""
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)
    
    # Database
    sqlite_db_path: str = Field(default="data/smart_brain.db")
    chromadb_path: str = Field(default="data/chromadb")
    
    # Paths
    vault_path: str = Field(default="vault")
    inbox_path: str = Field(default="inbox")
    archive_path: str = Field(default="archive")
    log_path: str = Field(default="data/logs")
    
    # Domains
    domains: str = Field(default="work/marriott,work/konstellate,personal,learning,admin,financial")
    
    # Processing
    max_clusters: int = Field(default=7)
    min_clusters: int = Field(default=3)
    task_dedupe_threshold: float = Field(default=0.85)
    
    # Logging
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def domains_list(self) -> List[str]:
        """Parse domains into list."""
        return [d.strip() for d in self.domains.split(",")]
    
    def ensure_directories(self):
        """Create required directories if they don't exist."""
        for path in [
            self.vault_path,
            self.inbox_path,
            self.archive_path,
            self.log_path,
            Path(self.sqlite_db_path).parent,
            self.chromadb_path,
        ]:
            Path(path).mkdir(parents=True, exist_ok=True)
        
        # Create PARA subdirectories in vault
        for domain in self.domains_list:
            for note_type in ["projects", "areas", "notes"]:
                vault_dir = Path(self.vault_path) / domain / note_type
                vault_dir.mkdir(parents=True, exist_ok=True)
        
        # Create daily notes directory
        (Path(self.vault_path) / "daily").mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
