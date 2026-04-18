"""
Base LLM interface for Ariadne.

Provides a unified abstract interface for all LLM providers,
allowing the memory system to switch between providers seamlessly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class LLMProvider(Enum):
    """Supported LLM providers."""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    QWEN = "qwen"
    GEMINI = "gemini"
    GROK = "grok"


@dataclass
class LLMConfig:
    """
    Configuration for an LLM provider.
    
    Attributes:
        provider: The LLM provider type.
        model: The specific model identifier.
        api_key: API key for authentication.
        base_url: Optional custom API endpoint.
        max_tokens: Maximum tokens in response.
        temperature: Sampling temperature (0.0-2.0).
        timeout: Request timeout in seconds.
        extra: Provider-specific extra parameters.
    """
    provider: LLMProvider
    model: str
    api_key: str = ""
    base_url: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding sensitive data."""
        return {
            "provider": self.provider.value,
            "model": self.model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "extra": self.extra,
        }


@dataclass
class LLMResponse:
    """
    Standardized response from an LLM call.
    
    Attributes:
        content: The generated text content.
        raw_response: Original provider response (for debugging).
        model: Model that generated the response.
        usage: Token usage information.
        cost: Estimated cost in USD.
    """
    content: str
    raw_response: Optional[Dict[str, Any]] = None
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    cost: float = 0.0
    
    def __str__(self) -> str:
        return self.content


class BaseLLM(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM implementations must inherit from this class and implement
    the required methods. This ensures a consistent interface across
    different providers.
    
    Example:
        class MyLLM(BaseLLM):
            def _call_api(self, messages, **kwargs) -> LLMResponse:
                # Implement provider-specific API call
                ...
    """
    
    def __init__(self, config: LLMConfig):
        """
        Initialize the LLM client.
        
        Args:
            config: LLM configuration including provider, model, and credentials.
        """
        self.config = config
        self._client = None
        
    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        """Return the provider type."""
        ...
    
    @abstractmethod
    def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        Make the actual API call to the provider.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            LLMResponse with generated content.
        """
        ...
    
    def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a chat completion.
        
        Args:
            prompt: User message.
            system: Optional system message.
            **kwargs: Additional parameters (temperature, max_tokens, etc.).
            
        Returns:
            LLMResponse with generated content.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._call_api(messages, **kwargs)
    
    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate a completion (non-chat models).
        
        Args:
            prompt: The prompt to complete.
            **kwargs: Additional parameters.
            
        Returns:
            LLMResponse with generated content.
        """
        messages = [{"role": "user", "content": prompt}]
        return self._call_api(messages, **kwargs)
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embeddings for text.
        
        Default implementation uses chat API to generate embeddings.
        Providers with native embedding support should override this.
        
        Args:
            text: Text to embed.
            
        Returns:
            List of embedding values.
        """
        # Default: use a simple prompt-based approach
        # Specific providers may override with native embeddings
        response = self.chat(
            prompt=f"Represent this text for semantic similarity: {text}",
            system="Return only a brief semantic representation."
        )
        # This is a placeholder; real implementation should use embedding APIs
        raise NotImplementedError(
            f"Provider {self.provider.value} does not support embeddings yet"
        )
    
    def is_available(self) -> bool:
        """
        Check if the LLM provider is available and credentials are valid.
        
        Returns:
            True if the provider can be reached with current credentials.
        """
        try:
            self.chat("test")
            return True
        except Exception:
            return False
