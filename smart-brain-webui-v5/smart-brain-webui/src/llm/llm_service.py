"""Unified LLM service - uses Azure OpenAI if configured, falls back to Ollama."""

from typing import Optional, Dict, Any
from loguru import logger

from src.config import settings


class LLMService:
    """Unified LLM interface - Azure preferred, Ollama fallback."""
    
    def __init__(self):
        self._azure = None
        self._ollama = None
    
    @property
    def azure(self):
        if self._azure is None:
            from src.llm.azure_client import azure_llm
            self._azure = azure_llm
        return self._azure
    
    @property
    def ollama(self):
        if self._ollama is None:
            from src.llm.ollama_client import llm
            self._ollama = llm
        return self._ollama
    
    @property
    def using_azure(self) -> bool:
        return settings.use_azure and self.azure.is_configured
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        task_type: Optional[str] = None
    ) -> str:
        """Generate text using best available LLM."""
        if self.using_azure:
            try:
                return self.azure.generate(prompt, system, temperature)
            except Exception as e:
                logger.warning(f"Azure failed, falling back to Ollama: {e}")
        
        return self.ollama.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            task_type=task_type
        )
    
    def generate_json(self, prompt: str, task_type: str = None, system: str = None):
        """Generate JSON, Azure only - no Ollama fallback."""
        if self.azure:
            try:
                return self.azure.generate_json(prompt, system=system)
            except Exception as e:
                logger.error(f"Azure failed: {e}")
                raise  # Don't fall back to Ollama
        
        raise ValueError("Azure not configured")
    
    def test_connection(self) -> Dict[str, bool]:
        """Test all LLM connections."""
        results = {}
        
        if settings.use_azure:
            results["azure"] = self.azure.test_connection()
        
        results["ollama"] = self.ollama.test_connection()
        
        return results


# Global instance
llm_service = LLMService()
