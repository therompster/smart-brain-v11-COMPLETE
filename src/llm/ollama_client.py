"""Ollama LLM client."""

import json
from typing import Optional, Dict, Any, List
import ollama
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings


class OllamaClient:
    """Wrapper for Ollama API with task-specific model selection."""
    
    def __init__(self):
        self.client = ollama.Client(host=settings.ollama_host)
        self.fallback_model = settings.ollama_fallback_model
    
    def get_model_for_task(self, task_type: str) -> str:
        """
        Get appropriate model for task type.
        
        Args:
            task_type: One of 'task_extraction', 'entity_recognition', 'routing', 'clustering'
        
        Returns:
            Model name
        """
        model_map = {
            'task_extraction': settings.ollama_task_extraction_model,
            'entity_recognition': settings.ollama_entity_recognition_model,
            'routing': settings.ollama_routing_model,
            'clustering': settings.ollama_clustering_model
        }
        
        return model_map.get(task_type, settings.ollama_routing_model)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = None
    ) -> str:
        """
        Generate completion from Ollama.
        
        Args:
            prompt: User prompt
            model: Specific model name (overrides task_type)
            task_type: Task type for auto model selection
            system: System prompt
            temperature: Sampling temperature
            format: Response format ('json' for structured output)
        
        Returns:
            Generated text
        """
        # Determine model
        if model:
            selected_model = model
        elif task_type:
            selected_model = self.get_model_for_task(task_type)
        else:
            selected_model = settings.ollama_routing_model
        
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            logger.debug(f"Generating with {selected_model} (task: {task_type}): {prompt[:100]}...")
            
            response = self.client.chat(
                model=selected_model,
                messages=messages,
                options={
                    "temperature": temperature,
                },
                format=format
            )
            
            result = response['message']['content']
            logger.debug(f"Generated {len(result)} chars")
            
            return result
            
        except Exception as e:
            logger.warning(f"Model {selected_model} failed: {e}")
            
            # Try fallback if not already using it
            if selected_model != self.fallback_model:
                logger.info(f"Falling back to {self.fallback_model}")
                return self.generate(
                    prompt=prompt,
                    model=self.fallback_model,
                    system=system,
                    temperature=temperature,
                    format=format
                )
            else:
                raise
    
    def generate_json(
        self,
        prompt: str,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate JSON response.
        
        Args:
            prompt: User prompt
            model: Model name
            task_type: Task type for auto model selection
            system: System prompt
        
        Returns:
            Parsed JSON dict
        """
        response = self.generate(
            prompt=prompt,
            model=model,
            task_type=task_type,
            system=system,
            temperature=0.3,
            format="json"
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
            logger.error(f"Failed to parse JSON: {response[:200]}")
            raise ValueError(f"Invalid JSON response: {e}")
    
    def test_connection(self) -> bool:
        """Test Ollama connection and check models."""
        try:
            models = self.client.list()
            available = [m['name'] for m in models.get('models', [])]
            
            logger.info(f"Ollama connected. Available models: {available}")
            
            # Check required models
            required = [
                settings.ollama_task_extraction_model,
                settings.ollama_entity_recognition_model,
                settings.ollama_routing_model,
                settings.ollama_clustering_model
            ]
            
            missing = [m for m in required if m not in available]
            if missing:
                logger.warning(f"Missing models: {missing}")
                logger.warning("Pull them with: ollama pull <model-name>")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False


# Global client instance
llm = OllamaClient()
