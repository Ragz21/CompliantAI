import ollama
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import yaml
import logging
import os
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMConnectionError(Exception):
    """Custom exception for connection-related errors"""
    pass

class LLMResponseError(Exception):
    """Custom exception for model response errors"""
    pass

class BaseLLM:
    """Abstract base class for LLM interactions with Ollama"""
    
    _DEFAULT_CONFIG_PATH = "config/config.yaml"
    
    def __init__(self, config_path: str = None, **kwargs):
        """
        Initialize base LLM with configuration
        
        Args:
            config_path: Path to configuration YAML
        """
        self.config = self._load_config(config_path or self._DEFAULT_CONFIG_PATH)
        self.config.update(kwargs)
        # print(self.config)
        
        models_config = self.config.get('models', {})
        host = models_config.get('endpoint', 'http://localhost:11434')
        self.client = ollama.Client(host=host)
        
        self.model_name = models_config.get('default', 'llama3:8b')
        self.temperature = models_config.get('temperature', 0.7)
        self.max_tokens = models_config.get('max_tokens', self.config.get('max_tokens', 4096))
        
        self._preprocess_hooks = []
        self._postprocess_hooks = []
        
        self._verify_model_availability()
        self._register_default_hooks()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load YAML configuration file"""
        try:
            with open(config_path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return {}
        except yaml.YAMLError as e:
            raise LLMConnectionError(f"Invalid config file: {e}") from e
        
    def _get_system_prompt(self, prompt_path: str) -> str:
        """Read system prompt from a text file located at prompt_path."""
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read().strip()
                logger.info(f"System prompt loaded from {prompt_path}")
                return prompt
        else:
            logger.warning(f"System prompt file {prompt_path} not found.")
            return ""

    def _verify_model_availability(self):
        """Ensure required model is available"""
        try:
            self.client.show(self.model_name)
        except ollama.ResponseError:
            logger.info(f"Model {self.model_name} not found, pulling...")
            self.client.pull(self.model_name)
        except ConnectionError as e:
            raise LLMConnectionError("Could not connect to Ollama server") from e

    def _register_default_hooks(self):
        """Register default preprocessing hooks"""
        self.add_preprocess_hook(self._inject_system_prompt)
        self.add_postprocess_hook(self._validate_response)

    def add_preprocess_hook(self, hook: callable):
        """Add custom preprocessing hook"""
        self._preprocess_hooks.append(hook)

    def add_postprocess_hook(self, hook: callable):
        """Add custom postprocessing hook"""
        self._postprocess_hooks.append(hook)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((LLMConnectionError, LLMResponseError)),
        reraise=True
    )
    def generate(self, prompt: str, **generation_params) -> str:
        """Main generation method with retry logic"""
        try:
            # Apply preprocessing
            processed_prompt = self._apply_preprocessing(prompt)
            
            logger.info(f"Generating response with params: {self._current_params()}")
            
            response = self.client.generate(
                model=self.model_name,
                prompt=processed_prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': self.max_tokens,
                    **generation_params
                }
            )
            
            return self._apply_postprocessing(response['response'])
            
        except ConnectionError as e:
            logger.error("Connection failed: %s", str(e))
            raise LLMConnectionError("LLM service unavailable") from e
        except ollama.ResponseError as e:
            logger.error("API error: %s", str(e))
            raise LLMResponseError(f"Model error: {e.error}") from e
        except Exception as e:
            logger.exception("Unexpected error during generation")
            raise LLMResponseError("Generation failed") from e

    def _apply_preprocessing(self, prompt: str) -> str:
        """Execute all preprocessing hooks"""
        for hook in self._preprocess_hooks:
            prompt = hook(prompt)
        return prompt

    def _apply_postprocessing(self, response: str) -> str:
        """Execute all postprocessing hooks"""
        for hook in self._postprocess_hooks:
            response = hook(response)
        return response

    def _inject_system_prompt(self, prompt: str) -> str:
        """Default preprocessing: inject system prompt if defined"""
        if hasattr(self, 'system_prompt'):
            return f"[System: {self.system_prompt}]\n{prompt}"
        return prompt

    def _validate_response(self, response: str) -> str:
        """Default postprocessing: validate response format"""
        if not response.strip():
            raise LLMResponseError("Empty response from model")
        return response.strip()

    def _current_params(self) -> Dict[str, Any]:
        """Get current parameter set"""
        return {
            'model': self.model_name,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens
        }

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float):
        if not 0 <= value <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        self._temperature = value

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @max_tokens.setter
    def max_tokens(self, value: int):
        if value < 1:
            raise ValueError("Max tokens must be at least 1")
        self._max_tokens = value

    def __str__(self):
        return f"BaseLLM(model={self.model_name}, temp={self.temperature})"
