"""Azure OpenAI client."""

import json
from typing import Optional, Dict, Any
import httpx
from loguru import logger

from src.config import settings


class AzureOpenAIClient:
    """Wrapper for Azure OpenAI API."""
    
    def __init__(self):
        self.endpoint = settings.azure_openai_endpoint.rstrip('/')
        self.api_key = settings.azure_openai_api_key
        self.deployment = settings.azure_openai_deployment
        self.api_version = settings.azure_openai_api_version
    
    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)
    
    def _get_url(self) -> str:
        return f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 16000
    ) -> str:
        """Generate completion from Azure OpenAI."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    self._get_url(),
                    headers={
                        "api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Azure OpenAI request failed: {e}")
            raise
    
    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """Generate JSON response."""
        # Add JSON instruction to system prompt
        json_system = (system or "") + "\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        
        response = self.generate(
            prompt=prompt,
            system=json_system,
            temperature=temperature
        )
        
        # Clean response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {response[:500]}")
            raise ValueError(f"Invalid JSON response: {e}")
    
    def test_connection(self) -> bool:
        """Test Azure OpenAI connection."""
        if not self.is_configured:
            logger.warning("Azure OpenAI not configured")
            return False
        
        try:
            response = self.generate("Say 'ok'", temperature=0)
            logger.success(f"Azure OpenAI connected: {self.deployment}")
            return True
        except Exception as e:
            logger.error(f"Azure OpenAI connection failed: {e}")
            return False


# Global client instance
azure_llm = AzureOpenAIClient()
