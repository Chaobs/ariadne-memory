"""
LLM Factory — creates LLM instances from configuration.
"""

from ariadne.llm.base import BaseLLM, LLMConfig, LLMProvider
from ariadne.llm.providers import (
    DeepSeekLLM,
    OpenAILLM,
    AnthropicLLM,
    QwenLLM,
    GeminiLLM,
    GrokLLM,
)
from typing import Optional, Dict
import json
import os


class LLMFactory:
    """
    Factory for creating LLM instances.
    
    Supports both programmatic configuration and JSON config files.
    
    Example:
        # From config
        llm = LLMFactory.from_config("config.json")
        
        # From dict
        llm = LLMFactory.create(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-..."
        )
    """
    
    _providers: Dict[LLMProvider, type] = {
        LLMProvider.DEEPSEEK: DeepSeekLLM,
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.ANTHROPIC: AnthropicLLM,
        LLMProvider.QWEN: QwenLLM,
        LLMProvider.GEMINI: GeminiLLM,
        LLMProvider.GROK: GrokLLM,
    }
    
    @classmethod
    def create(
        cls,
        provider: str,
        model: str,
        api_key: str = "",
        **kwargs
    ) -> BaseLLM:
        """
        Create an LLM instance from parameters.
        
        Args:
            provider: Provider name (deepseek, openai, anthropic, etc.)
            model: Model identifier.
            api_key: API key for authentication.
            **kwargs: Additional configuration options.
            
        Returns:
            Configured LLM instance.
        """
        provider_enum = LLMProvider(provider.lower())
        config = LLMConfig(
            provider=provider_enum,
            model=model,
            api_key=api_key,
            **kwargs
        )
        return cls._providers[provider_enum](config)
    
    @classmethod
    def from_config(cls, config: Dict) -> BaseLLM:
        """
        Create an LLM instance from a config dictionary.
        
        Args:
            config: Configuration dict with provider, model, api_key, etc.
            
        Returns:
            Configured LLM instance.
        """
        provider = config.get("provider", "deepseek")
        model = config.get("model", "")
        api_key = config.get("api_key", os.environ.get(f"{provider.upper()}_API_KEY", ""))
        
        return cls.create(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=config.get("base_url"),
            max_tokens=config.get("max_tokens", 2048),
            temperature=config.get("temperature", 0.7),
            timeout=config.get("timeout", 60),
            extra=config.get("extra", {}),
        )
    
    @classmethod
    def from_json_file(cls, path: str) -> BaseLLM:
        """
        Load configuration from a JSON file and create an LLM instance.
        
        Args:
            path: Path to the JSON config file.
            
        Returns:
            Configured LLM instance.
            
        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If config is invalid.
        """
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return cls.from_config(config)
    
    @classmethod
    def from_env(cls, provider: str = "DEEPSEEK") -> Optional[BaseLLM]:
        """
        Create an LLM instance using environment variables.
        
        Expects:
            {PROVIDER}_API_KEY: API key
            {PROVIDER}_MODEL: Model name (optional)
            
        Args:
            provider: Provider name (defaults to DEEPSEEK).
            
        Returns:
            Configured LLM instance, or None if API key not found.
        """
        api_key = os.environ.get(f"{provider}_API_KEY")
        if not api_key:
            return None
        
        model = os.environ.get(f"{provider}_MODEL", "")
        return cls.create(provider=provider.lower(), model=model, api_key=api_key)


class ConfigManager:
    """
    Manages Ariadne configuration files.
    
    Handles loading, saving, and merging configurations from multiple sources:
    - JSON config files
    - Environment variables
    - Default values
    """
    
    DEFAULT_CONFIG = {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        "chroma": {
            "persist_directory": ".ariadne/chroma",
        },
        "ingest": {
            "chunk_size": 500,
            "chunk_overlap": 50,
            "batch_size": 100,
        },
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to config.json file. If None, uses defaults.
        """
        self.config_path = config_path
        self.config = self.DEFAULT_CONFIG.copy()
        
        if config_path and os.path.exists(config_path):
            self.load(config_path)
    
    def load(self, path: str) -> None:
        """Load configuration from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        self._merge(user_config)
    
    def save(self, path: str) -> None:
        """Save current configuration to a JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def _merge(self, user_config: dict) -> None:
        """Deep merge user config into default config."""
        def _deep_merge(base: dict, overlay: dict) -> dict:
            result = base.copy()
            for key, value in overlay.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = _deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        self.config = _deep_merge(self.config, user_config)
    
    def get(self, key: str, default=None):
        """Get a configuration value by dot-notation key."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    def set(self, key: str, value) -> None:
        """Set a configuration value by dot-notation key."""
        keys = key.split(".")
        target = self.config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
    
    def get_llm_config(self) -> LLMConfig:
        """Get LLM configuration as LLMConfig object."""
        llm_cfg = self.config.get("llm", {})
        return LLMConfig(
            provider=LLMProvider(llm_cfg.get("provider", "deepseek")),
            model=llm_cfg.get("model", "deepseek-chat"),
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            temperature=llm_cfg.get("temperature", 0.7),
            max_tokens=llm_cfg.get("max_tokens", 2048),
        )
    
    def create_llm(self) -> BaseLLM:
        """Create an LLM instance from current configuration."""
        config = self.get_llm_config()
        return LLMFactory._providers[config.provider](config)
