"""
Ariadne Configuration System.

Unified configuration management supporting:
- JSON config files
- .env files (for API keys)
- Environment variables
- Multiple config locations (project/user/system level)
- Config validation and testing

Config priority (highest to lowest):
1. Environment variables
2. Project-level config (.ariadne/config.json under project root)
3. User-level config (legacy: ~/.ariadne/config.json, migrated automatically)
4. System-level config (/etc/ariadne/config.json)
5. Default values

All data is stored under the project root directory (Ariadne/.ariadne/).
"""

from __future__ import annotations

import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import platform

# Import centralized path management
from ariadne.paths import (
    ARIADNE_DIR, CONFIG_FILE, ENV_FILE,
    CHROMA_DEFAULT_DIR as _CHROMA_DEFAULT,
    MEMORIES_DIR,
    PROJECT_ROOT,
)

from ariadne.llm.base import LLMProvider, LLMConfig, BaseLLM
from ariadne.llm.factory import LLMFactory


# ============================================================================
# Config Paths
# ============================================================================

def get_config_paths() -> Dict[str, Optional[Path]]:
    """
    Get all possible config file paths in priority order.

    Returns:
        Dict with path names and their Path objects (or None if not found)
    """
    # Primary: project-local .ariadne/config.json
    # Legacy: ~/.ariadne/config.json (auto-migrated on first run)
    home = Path.home()
    legacy_ariadne = home / ".ariadne"
    system = Path("/etc/ariadne") if platform.system() != "Windows" else None

    paths = {
        "project": CONFIG_FILE,  # .ariadne/config.json under project root
        "user": legacy_ariadne / "config.json",  # legacy user home location
        "env": ENV_FILE,  # .ariadne/.env under project root
        "system": system / "config.json" if system else None,
    }

    return paths


def get_default_config_dir() -> Path:
    """Get the default config directory — now under project root."""
    return ARIADNE_DIR


# ============================================================================
# Config Data Classes
# ============================================================================

@dataclass
class LLMConfigData:
    """LLM configuration data."""
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 60

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None and v != ""}
    
    @classmethod
    def from_dict(cls, data: dict) -> "LLMConfigData":
        return cls(
            provider=data.get("provider", "deepseek"),
            model=data.get("model", "deepseek-chat"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 2048),
            timeout=data.get("timeout", 60),
        )


@dataclass
class ChromaConfigData:
    """ChromaDB configuration data."""
    persist_directory: str = ""  # Empty means use CHROMA_DEFAULT_DIR from paths
    collection_name: str = "ariadne_memory"

    def _effective_persist_dir(self) -> str:
        """Return actual persist directory, falling back to project-local path."""
        return self.persist_directory or str(_CHROMA_DEFAULT)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["persist_directory"] = self._effective_persist_dir()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ChromaConfigData":
        pd = data.get("persist_directory", "")
        # Convert legacy ~/~/.ariadne paths if found
        if "~/.ariadne" in pd or ".ariadne" in pd and "/" in pd or "\\" in pd:
            pd = ""  # Reset to use default (project root)
        return cls(
            persist_directory=pd,
            collection_name=data.get("collection_name", "ariadne_memory"),
        )


@dataclass
class IngestConfigData:
    """Ingest configuration data."""
    chunk_size: int = 500
    chunk_overlap: int = 50
    batch_size: int = 100
    supported_formats: List[str] = field(default_factory=lambda: [
        ".md", ".docx", ".pptx", ".pdf", ".txt", ".mm", ".xmind",
        ".py", ".java", ".cpp", ".c", ".js", ".ts", ".xlsx", ".xls", ".csv"
    ])

    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "IngestConfigData":
        return cls(
            chunk_size=data.get("chunk_size", 500),
            chunk_overlap=data.get("chunk_overlap", 50),
            batch_size=data.get("batch_size", 100),
            supported_formats=data.get("supported_formats", cls().supported_formats),
        )


@dataclass
class LocaleConfigData:
    """Locale/i18n configuration data."""
    language: str = "auto"  # auto, zh_CN, zh_TW, en, fr, es, ru, ar
    fallback: str = "en"
    output_language: Optional[str] = None  # None means same as UI language

    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "LocaleConfigData":
        return cls(
            language=data.get("language", "auto"),
            fallback=data.get("fallback", "en"),
            output_language=data.get("output_language"),
        )


@dataclass
class ExportConfigData:
    """Export configuration data."""
    default_format: str = "markdown"  # markdown, html, docx, pdf
    include_metadata: bool = True
    include_graph: bool = True

    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExportConfigData":
        return cls(
            default_format=data.get("default_format", "markdown"),
            include_metadata=data.get("include_metadata", True),
            include_graph=data.get("include_graph", True),
        )


@dataclass 
class AdvancedConfigData:
    """Advanced feature configuration."""
    enable_reranker: bool = False
    enable_graph: bool = True
    enable_summary: bool = True
    reranker_top_k: int = 5
    initial_top_k: int = 20

    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "AdvancedConfigData":
        return cls(
            enable_reranker=data.get("enable_reranker", False),
            enable_graph=data.get("enable_graph", True),
            enable_summary=data.get("enable_summary", True),
            reranker_top_k=data.get("reranker_top_k", 5),
            initial_top_k=data.get("initial_top_k", 20),
        )


# ============================================================================
# Main Config Class
# ============================================================================

class AriadneConfig:
    """
    Unified configuration manager for Ariadne.
    
    Supports multiple config sources with proper priority handling.
    
    Example:
        # Auto-discover config from multiple sources
        config = AriadneConfig.auto()
        
        # Set values
        config.set("llm.provider", "deepseek")
        config.set("llm.model", "deepseek-chat")
        
        # Get values
        provider = config.get("llm.provider")
        
        # Save to user config
        config.save_user()
    """
    
    DEFAULT_CONFIG = {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        "chroma": {
            "persist_directory": str(_CHROMA_DEFAULT),
            "collection_name": "ariadne_memory",
        },
        "ingest": {
            "chunk_size": 500,
            "chunk_overlap": 50,
            "batch_size": 100,
        },
        "locale": {
            "language": "auto",
            "fallback": "en",
        },
        "export": {
            "default_format": "markdown",
            "include_metadata": True,
            "include_graph": True,
        },
        "advanced": {
            "enable_reranker": False,
            "enable_graph": True,
            "enable_summary": True,
            "reranker_top_k": 5,
            "initial_top_k": 20,
        },
        "plugins": {
            "enabled": [],
            "directories": [],
            "config": {},
        },
    }
    
    # Supported providers for display
    SUPPORTED_PROVIDERS = [
        ("deepseek", "DeepSeek", "deepseek-chat, deepseek-coder"),
        ("openai", "OpenAI (GPT)", "gpt-4o, gpt-4, gpt-3.5-turbo"),
        ("anthropic", "Anthropic (Claude)", "claude-3-5-sonnet, claude-3-opus"),
        ("qwen", "Alibaba (Qwen)", "qwen-plus, qwen-turbo, qwen-max"),
        ("gemini", "Google (Gemini)", "gemini-1.5-flash, gemini-1.5-pro"),
        ("grok", "xAI (Grok)", "grok-2, grok-1"),
        ("kimi", "Moonshot (Kimi)", "moonshot-v1-8k, moonshot-v1-32k"),
        ("minimax", "MiniMax", "abab5.5-chat, abab6"),
        ("glm", "Zhipu (ChatGLM)", "glm-4, glm-4-flash, glm-4-plus"),
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to a specific config file to load.
        """
        self.config_dir = ARIADNE_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Auto-migrate from legacy ~/.ariadne location if it exists
        self._migrate_legacy()

        self._config = self._deep_copy(self.DEFAULT_CONFIG)
        self._loaded_sources: List[str] = ["defaults"]
        
        # Load config from file if provided
        if config_path:
            self.load(config_path)
            self._loaded_sources.append(config_path)
    
    def _migrate_legacy(self) -> None:
        """
        Migrate data from legacy ~/.ariadne location to project root.
        
        Copies config.json, .env, and memories/ if they exist in the old path,
        then renames the old directory to .ariadne_legacy (safe delete).
        """
        legacy = Path.home() / ".ariadne"
        if not legacy.exists():
            return
        
        # Check if already migrated
        migration_marker = legacy / ".migrated_to_project"
        if migration_marker.exists():
            return
        
        import shutil
        moved_any = False
        
        # Migrate config.json
        legacy_config = legacy / "config.json"
        if legacy_config.exists() and not CONFIG_FILE.exists():
            shutil.copy2(str(legacy_config), str(CONFIG_FILE))
            print(f"[Migrated] config.json -> {CONFIG_FILE}")
            moved_any = True
        
        # Migrate .env
        legacy_env = legacy / ".env"
        if legacy_env.exists() and not ENV_FILE.exists():
            shutil.copy2(str(legacy_env), str(ENV_FILE))
            print(f"[Migrated] .env -> {ENV_FILE}")
            moved_any = True
        
        # Migrate memories directory
        legacy_memories = legacy / "memories"
        if legacy_memories.is_dir() and not MEMORIES_DIR.is_dir():
            shutil.copytree(str(legacy_memories), str(MEMORIES_DIR))
            print(f"[Migrated] memories/ -> {MEMORIES_DIR}")
            moved_any = True
        
        # Mark as migrated so we don't do it again
        if moved_any:
            migration_marker.write_text(f"Migrated to {PROJECT_ROOT}\n")
            print(f"[Migration complete] Legacy data copied to project root.")
    
    @classmethod
    def auto(cls) -> "AriadneConfig":
        """
        Auto-discover and load configuration from multiple sources.
        
        Priority: Environment > Project config > User config > System config > Defaults
        
        Returns:
            Configured AriadneConfig instance
        """
        config = cls()
        paths = get_config_paths()
        
        # Load from environment first (highest priority)
        config._load_from_env()
        config._loaded_sources.append("environment")
        
        # Then load from config files (lower priority)
        for name, path in paths.items():
            if path and path.exists():
                config.load(str(path))
                config._loaded_sources.append(f"{name}:{path}")
        
        return config
    
    def _deep_copy(self, obj: Any) -> Any:
        """Deep copy a dict or list."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # LLM config from env
        for provider in ["DEEPSEEK", "OPENAI", "ANTHROPIC", "QWEN", "GEMINI", "GROK", "KIMI", "MINIMAX", "GLM"]:
            api_key = os.environ.get(f"{provider}_API_KEY")
            if api_key:
                # Update provider if we have an API key but no config
                provider_lower = provider.lower()
                if not self._config["llm"].get("api_key"):
                    self._config["llm"]["provider"] = provider_lower
                    self._config["llm"]["api_key"] = api_key
                    model = os.environ.get(f"{provider}_MODEL")
                    if model:
                        self._config["llm"]["model"] = model
                    break
        
        # Locale from env
        locale = os.environ.get("ARIADNE_LANGUAGE") or os.environ.get("ARIADNE_LANG")
        if locale:
            self._config["locale"]["language"] = locale
        
        # Other settings from env
        if os.environ.get("ARIADNE_CHROMA_DIR"):
            self._config["chroma"]["persist_directory"] = os.environ.get("ARIADNE_CHROMA_DIR")
    
    def load(self, path: str) -> None:
        """
        Load configuration from a file.
        
        Args:
            path: Path to config file (JSON or YAML)
        """
        path = Path(path)
        if not path.exists():
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                if path.suffix in [".yaml", ".yml"]:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            if data:
                self._merge_config(data)
        except Exception as e:
            print(f"Warning: Failed to load config from {path}: {e}")
    
    def _merge_config(self, data: dict) -> None:
        """Deep merge data into config."""
        def _merge(base: dict, overlay: dict) -> dict:
            result = base.copy()
            for key, value in overlay.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = _merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        self._config = _merge(self._config, data)
    
    def save(self, path: Optional[str] = None) -> None:
        """
        Save configuration to a file.
        
        Args:
            path: Path to save to. Defaults to user config.
        """
        if path is None:
            path = str(self.config_dir / "config.json")
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def save_user(self) -> str:
        """
        Save configuration to user config file.
        
        Returns:
            Path to saved config file
        """
        path = self.config_dir / "config.json"
        self.save(str(path))
        return str(path)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Dot-separated key (e.g., "llm.provider")
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        
        return value if value is not None else default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.
        
        Args:
            key: Dot-separated key (e.g., "llm.provider")
            value: Value to set
        """
        keys = key.split(".")
        target = self._config
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            elif not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
    
    def get_llm_config(self) -> LLMConfig:
        """
        Get LLM configuration as LLMConfig object.
        
        API key is read from config or environment.
        
        Returns:
            Configured LLMConfig instance
        """
        llm_cfg = self._config.get("llm", {})
        
        # Get API key from config or environment
        api_key = llm_cfg.get("api_key", "")
        if not api_key:
            provider_upper = llm_cfg.get("provider", "deepseek").upper()
            api_key = os.environ.get(f"{provider_upper}_API_KEY", "")
        
        return LLMConfig(
            provider=LLMProvider(llm_cfg.get("provider", "deepseek")),
            model=llm_cfg.get("model", "deepseek-chat"),
            api_key=api_key,
            base_url=llm_cfg.get("base_url"),
            temperature=llm_cfg.get("temperature", 0.7),
            max_tokens=llm_cfg.get("max_tokens", 2048),
            timeout=llm_cfg.get("timeout", 60),
        )
    
    def create_llm(self) -> Optional[BaseLLM]:
        """
        Create an LLM instance from current configuration.
        
        Returns:
            Configured LLM instance, or None if API key is missing
        """
        llm_config = self.get_llm_config()
        
        if not llm_config.api_key:
            return None
        
        try:
            return LLMFactory.create(
                provider=llm_config.provider.value,
                model=llm_config.model,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )
        except Exception:
            return None
    
    def test_llm(self) -> Tuple[bool, str]:
        """
        Test if the LLM configuration is working.
        
        Returns:
            Tuple of (success, message)
        """
        llm = self.create_llm()
        
        if llm is None:
            return False, "No API key configured. Please set your API key."
        
        try:
            response = llm.chat("Hello, please respond with 'OK' if you can read this.")
            if "ok" in response.content.lower():
                return True, f"LLM connection successful! Model: {response.model}"
            else:
                return False, f"LLM responded unexpectedly: {response.content[:100]}"
        except Exception as e:
            return False, f"LLM connection failed: {str(e)}"
    
    def get_locale_language(self) -> str:
        """
        Get the actual language to use based on config.
        
        Returns:
            Language code (e.g., "en", "zh_CN")
        """
        lang = self._config.get("locale", {}).get("language", "auto")
        
        if lang == "auto":
            # Try to detect from environment
            env_lang = os.environ.get("LANG") or os.environ.get("LC_ALL", "")
            if env_lang:
                # Extract language code (e.g., "en_US.UTF-8" -> "en")
                lang = env_lang.split("_")[0].split(".")[0]
                
                # Map to supported language codes
                if lang == "zh":
                    # Check for traditional/simplified
                    if "TW" in env_lang or "Hant" in env_lang:
                        return "zh_TW"
                    return "zh_CN"
                
                # Check if supported
                supported = ["en", "fr", "es", "ru", "ar"]
                if lang in supported:
                    return lang
                
                return "en"  # Default to English
        
        # Check if the specified language is supported
        supported_codes = ["zh_CN", "zh_TW", "en", "fr", "es", "ru", "ar"]
        if lang in supported_codes:
            return lang
        
        return "en"  # Default fallback
    
    def get_output_language(self) -> str:
        """
        Get the language for output/results.
        
        Returns:
            Language code for output
        """
        output_lang = self._config.get("locale", {}).get("output_language")
        if output_lang:
            return output_lang
        
        return self.get_locale_language()
    
    def to_dict(self) -> dict:
        """Get configuration as dictionary (for display)."""
        return self._deep_copy(self._config)
    
    def get_llm_info(self) -> dict:
        """
        Get LLM configuration info (excluding API key).
        
        Returns:
            Dict with LLM config info
        """
        llm_cfg = self._config.get("llm", {})
        return {
            "provider": llm_cfg.get("provider", "deepseek"),
            "model": llm_cfg.get("model", "deepseek-chat"),
            "has_api_key": bool(llm_cfg.get("api_key") or os.environ.get(
                f"{llm_cfg.get('provider', 'deepseek').upper()}_API_KEY"
            )),
            "temperature": llm_cfg.get("temperature", 0.7),
            "max_tokens": llm_cfg.get("max_tokens", 2048),
        }
    
    @property
    def loaded_sources(self) -> List[str]:
        """Get list of loaded configuration sources."""
        return self._loaded_sources.copy()


# ============================================================================
# Global Config Instance
# ============================================================================

_global_config: Optional[AriadneConfig] = None


def get_config() -> AriadneConfig:
    """
    Get the global configuration instance.
    
    Returns:
        AriadneConfig instance (auto-loaded if not exists)
    """
    global _global_config
    if _global_config is None:
        _global_config = AriadneConfig.auto()
    return _global_config


def reload_config() -> AriadneConfig:
    """
    Reload configuration from all sources.
    
    Returns:
        Fresh AriadneConfig instance
    """
    global _global_config
    _global_config = AriadneConfig.auto()
    return _global_config


def reset_config() -> None:
    """Reset global configuration to defaults."""
    global _global_config
    _global_config = AriadneConfig()


# ============================================================================
# CLI Helpers
# ============================================================================

def print_config_info(config: Optional[AriadneConfig] = None) -> None:
    """Print configuration information."""
    if config is None:
        config = get_config()
    
    print("\n" + "="*60)
    print("Ariadne Configuration")
    print("="*60)
    
    print("\nConfiguration Sources (in priority order):")
    for source in config.loaded_sources:
        print(f"  - {source}")
    
    print("\nLLM Configuration:")
    llm_info = config.get_llm_info()
    print(f"  Provider: {llm_info['provider']}")
    print(f"  Model: {llm_info['model']}")
    print(f"  API Key: {'[SET]' if llm_info['has_api_key'] else '[NOT SET]'}")
    print(f"  Temperature: {llm_info['temperature']}")
    print(f"  Max Tokens: {llm_info['max_tokens']}")
    
    print("\nLocale:")
    print(f"  Language: {config.get_locale_language()}")
    print(f"  Output: {config.get_output_language()}")
    
    print("\nAdvanced Features:")
    adv = config.get("advanced", {})
    print(f"  Reranker: {'Enabled' if adv.get('enable_reranker') else 'Disabled'}")
    print(f"  Knowledge Graph: {'Enabled' if adv.get('enable_graph') else 'Disabled'}")
    print(f"  Summary: {'Enabled' if adv.get('enable_summary') else 'Disabled'}")
    
    print("\n" + "="*60)


def list_supported_providers() -> None:
    """List all supported LLM providers."""
    print("\nSupported LLM Providers:")
    print("-" * 50)
    for code, name, models in AriadneConfig.SUPPORTED_PROVIDERS:
        print(f"  {code:12} - {name}")
        print(f"             Models: {models}")
        print()
