"""
Configuration Management System for PyScrAI Forge

This module provides a centralized configuration system that supports a 4-tier
precedence hierarchy: environment → project → user → system defaults.
"""

import json
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, ValidationError, validator
from enum import Enum

class ValidationLevel(Enum):
    """Configuration validation strictness levels"""
    STRICT = "strict"      # Fail fast on validation errors
    LENIENT = "lenient"    # Log warnings, use defaults

class LLMConfig(BaseModel):
    """LLM Provider and Model Configuration"""
    model_config = ConfigDict(extra='forbid')
    
    # Provider settings
    default_provider: str = Field(default="openrouter", description="Primary LLM provider")
    secondary_provider: str = Field(default="openrouter", description="Fallback LLM provider")
    semantic_provider: str = Field(default="openrouter", description="Provider for semantic operations")
    
    # Rate limiting
    rate_limit_max_concurrent: int = Field(default=1, ge=1, le=20, description="Max concurrent requests")
    rate_limit_min_delay: float = Field(default=2.0, ge=0.1, le=60.0, description="Min delay between requests (seconds)")
    rate_limit_max_retries: int = Field(default=3, ge=0, le=10, description="Max retries for rate limits")
    rate_limit_retry_delay: float = Field(default=3.0, ge=0.1, le=60.0, description="Initial retry delay (seconds)")
    
    # Model parameters by service
    entity_extraction_max_tokens: int = Field(default=2000, ge=100, le=8000)
    entity_extraction_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    
    relationship_extraction_max_tokens: int = Field(default=2000, ge=100, le=8000)
    relationship_extraction_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    
    semantic_profiling_max_tokens: int = Field(default=500, ge=100, le=2000)
    semantic_profiling_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    
    narrative_synthesis_max_tokens: int = Field(default=1500, ge=100, le=4000)
    narrative_synthesis_temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    
    relationship_inference_max_tokens: int = Field(default=200, ge=50, le=1000)
    relationship_inference_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    
    deduplication_max_tokens: int = Field(default=10, ge=5, le=100)
    deduplication_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # API credentials
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    openrouter_base_url: Optional[str] = Field(default=None, description="OpenRouter base URL")
    openrouter_model: Optional[str] = Field(default=None, description="OpenRouter model")
    
    cherry_api_key: Optional[str] = Field(default=None, description="Cherry API key")
    lm_proxy_api_key: Optional[str] = Field(default=None, description="LM Proxy API key")

class VectorConfig(BaseModel):
    """Vector Database Configuration"""
    model_config = ConfigDict(extra='forbid')
    
    url: str = Field(default=":memory:", description="Qdrant connection URL")
    api_key: Optional[str] = Field(default=None, description="Qdrant API key")
    embedding_dimension: int = Field(default=768, ge=128, le=4096, description="Vector dimension")
    
    # Collection settings
    entities_collection: str = Field(default="entities", description="Entities collection name")
    relationships_collection: str = Field(default="relationships", description="Relationships collection name")
    
    # Search settings
    similarity_search_limit: int = Field(default=5, ge=1, le=50, description="Max similar entities returned")
    similarity_search_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Min similarity score")
    deduplication_threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="Duplicate detection threshold")
    deduplication_limit: int = Field(default=1000, ge=100, le=10000, description="Max entities for deduplication scan")

class DatabaseConfig(BaseModel):
    """Database Configuration"""
    model_config = ConfigDict(extra='forbid')
    
    db_path: str = Field(default="data/db/forge_data.duckdb", description="Database file path")
    connection_timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="Connection timeout (seconds)")
    wal_mode: bool = Field(default=True, description="Write-ahead logging enabled")

class EmbeddingConfig(BaseModel):
    """Embedding Model Configuration"""
    model_config = ConfigDict(extra='forbid')
    
    device: str = Field(default="cuda", description="Device for inference")
    general_model: str = Field(default="BAAI/bge-base-en-v1.5", description="General purpose embedding model")
    long_context_model: str = Field(default="nomic-ai/nomic-embed-text-v1.5", description="Long context model")
    batch_size: int = Field(default=32, ge=1, le=256, description="Batch size for processing")
    long_context_threshold: int = Field(default=512, ge=100, le=2048, description="Token threshold for long context")

class UIConfig(BaseModel):
    """UI Configuration"""
    model_config = ConfigDict(extra='forbid')
    
    flet_web_mode: bool = Field(default=True, description="Enable web mode")
    flet_port: int = Field(default=8550, ge=1024, le=65535, description="Web server port")
    flet_web_renderer: str = Field(default="html", description="Web renderer type")
    
    # Theme and appearance
    theme_mode: str = Field(default="dark", description="UI theme mode")
    primary_color: str = Field(default="#2196F3", description="Primary UI color")
    
    # Dashboard settings
    logs_feed_enabled: bool = Field(default=True, description="Enable Log display")
    auto_refresh_interval: float = Field(default=5.0, ge=1.0, le=60.0, description="Auto refresh interval (seconds)")

class ProcessingConfig(BaseModel):
    """Processing and Workflow Configuration"""
    model_config = ConfigDict(extra='forbid')
    
    # Processing delays
    semantic_profiler_delay: float = Field(default=0.3, ge=0.0, le=5.0, description="Delay between profile generations")
    graph_analysis_delay: float = Field(default=0.2, ge=0.0, le=5.0, description="Delay in graph analysis")
    
    # Workflow settings
    auto_deduplication: bool = Field(default=True, description="Enable automatic entity deduplication")
    auto_relationship_inference: bool = Field(default=True, description="Enable automatic relationship inference")
    parallel_processing: bool = Field(default=False, description="Enable parallel document processing")

class SystemConfig(BaseModel):
    """Complete system configuration"""
    model_config = ConfigDict(extra='forbid')
    
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vector: VectorConfig = Field(default_factory=VectorConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    
    # Metadata
    schema_version: int = Field(default=1, description="Configuration schema version")

class ConfigManager:
    """Centralized configuration manager with 4-tier precedence hierarchy"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.config_dir = self.project_root / "forge" / "shared" / "config" / "settings"
        self._system_config: Optional[SystemConfig] = None
        self._user_config: Optional[Dict[str, Any]] = None
        self._project_config: Optional[Dict[str, Any]] = None
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML configuration file"""
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            print(f"Warning: Failed to load {file_path}: {e}")
            return {}
    
    def _save_yaml_file(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """Save configuration to YAML file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
            return True
        except Exception as e:
            print(f"Error: Failed to save {file_path}: {e}")
            return False
    
    def _load_system_defaults(self) -> SystemConfig:
        """Load system default configuration"""
        if self._system_config is None:
            defaults_path = self.config_dir / "defaults.yaml"
            defaults_dict = self._load_yaml_file(defaults_path)
            
            try:
                self._system_config = SystemConfig(**defaults_dict)
            except ValidationError as e:
                print(f"Warning: System defaults validation failed: {e}")
                # Use Pydantic defaults
                self._system_config = SystemConfig()
        
        return self._system_config
    
    def _load_user_config(self) -> Dict[str, Any]:
        """Load user-level configuration"""
        if self._user_config is None:
            user_path = self.config_dir / "user.yaml"
            self._user_config = self._load_yaml_file(user_path)
        
        return self._user_config
    
    def _load_project_config(self) -> Dict[str, Any]:
        """Load project-specific configuration"""
        if self._project_config is None:
            project_path = self.config_dir / "project.yaml"
            self._project_config = self._load_yaml_file(project_path)
        
        return self._project_config
    
    def _get_env_value(self, env_key: str, default: Any = None) -> Any:
        """Get value from environment variable with type conversion"""
        value = os.getenv(env_key)
        if value is None:
            return default
        
        # Type conversion based on default type
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return default
        
        return value
    
    def _merge_configs(self) -> Dict[str, Any]:
        """Merge configurations with precedence: env → project → user → system"""
        # Start with system defaults
        system_config = self._load_system_defaults()
        merged = system_config.model_dump()
        
        # Apply user overrides
        user_config = self._load_user_config()
        self._deep_merge(merged, user_config)
        
        # Apply project overrides
        project_config = self._load_project_config()
        self._deep_merge(merged, project_config)
        
        # Apply environment overrides
        env_overrides = self._get_env_overrides()
        self._deep_merge(merged, env_overrides)
        
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Deep merge configuration dictionaries"""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _get_env_overrides(self) -> Dict[str, Any]:
        """Extract configuration overrides from environment variables"""
        env_map = {
            # LLM configuration
            'LLM_RATE_LIMIT_MAX_CONCURRENT': ('llm', 'rate_limit_max_concurrent'),
            'LLM_RATE_LIMIT_MIN_DELAY': ('llm', 'rate_limit_min_delay'),
            'LLM_RATE_LIMIT_MAX_RETRIES': ('llm', 'rate_limit_max_retries'),
            'LLM_RATE_LIMIT_RETRY_DELAY': ('llm', 'rate_limit_retry_delay'),
            'OPENROUTER_API_KEY': ('llm', 'openrouter_api_key'),
            'OPENROUTER_BASE_URL': ('llm', 'openrouter_base_url'),
            'OPENROUTER_MODEL': ('llm', 'openrouter_model'),
            'DEFAULT_PROVIDER': ('llm', 'default_provider'),
            'SECONDARY_PROVIDER': ('llm', 'secondary_provider'),
            'SEMANTIC_PROVIDER': ('llm', 'semantic_provider'),
            
            # UI configuration
            'FLET_WEB_MODE': ('ui', 'flet_web_mode'),
            'FLET_PORT': ('ui', 'flet_port'),
            'FLET_WEB_RENDERER': ('ui', 'flet_web_renderer'),
        }
        
        overrides = {}
        for env_key, (section, config_key) in env_map.items():
            value = os.getenv(env_key)
            if value is not None:
                if section not in overrides:
                    overrides[section] = {}
                
                # Type conversion
                if config_key in ['rate_limit_max_concurrent', 'rate_limit_max_retries', 'flet_port']:
                    try:
                        overrides[section][config_key] = int(value)
                    except ValueError:
                        continue
                elif config_key in ['rate_limit_min_delay', 'rate_limit_retry_delay']:
                    try:
                        overrides[section][config_key] = float(value)
                    except ValueError:
                        continue
                elif config_key in ['flet_web_mode']:
                    overrides[section][config_key] = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    overrides[section][config_key] = value
        
        return overrides
    
    def get_config(self, validation_level: ValidationLevel = ValidationLevel.STRICT) -> SystemConfig:
        """Get merged configuration with validation"""
        merged_config = self._merge_configs()
        
        try:
            return SystemConfig(**merged_config)
        except ValidationError as e:
            if validation_level == ValidationLevel.STRICT:
                raise ValueError(f"Configuration validation failed: {e}")
            else:
                print(f"Warning: Configuration validation failed, using defaults: {e}")
                return SystemConfig()
    
    def save_project_config(self, config_updates: Dict[str, Any]) -> bool:
        """Save project-specific configuration updates"""
        project_path = self.config_dir / "project.yaml"
        
        # Load existing project config
        existing_config = self._load_yaml_file(project_path)
        
        # Merge updates
        self._deep_merge(existing_config, config_updates)
        
        # Save updated config
        success = self._save_yaml_file(project_path, existing_config)
        if success:
            # Clear cached project config to force reload
            self._project_config = None
        
        return success
    
    def get_llm_config_for_service(self, service_name: str) -> Dict[str, Any]:
        """Get LLM configuration for specific service"""
        config = self.get_config()
        
        service_mapping = {
            'entity_extraction': {
                'max_tokens': config.llm.entity_extraction_max_tokens,
                'temperature': config.llm.entity_extraction_temperature,
            },
            'relationship_extraction': {
                'max_tokens': config.llm.relationship_extraction_max_tokens,
                'temperature': config.llm.relationship_extraction_temperature,
            },
            'semantic_profiling': {
                'max_tokens': config.llm.semantic_profiling_max_tokens,
                'temperature': config.llm.semantic_profiling_temperature,
            },
            'narrative_synthesis': {
                'max_tokens': config.llm.narrative_synthesis_max_tokens,
                'temperature': config.llm.narrative_synthesis_temperature,
            },
            'relationship_inference': {
                'max_tokens': config.llm.relationship_inference_max_tokens,
                'temperature': config.llm.relationship_inference_temperature,
            },
            'deduplication': {
                'max_tokens': config.llm.deduplication_max_tokens,
                'temperature': config.llm.deduplication_temperature,
            },
        }
        
        return service_mapping.get(service_name, {
            'max_tokens': 1000,
            'temperature': 0.3,
        })
    
    def reload_config(self) -> None:
        """Clear cached configurations and reload from files"""
        self._system_config = None
        self._user_config = None
        self._project_config = None

# Global instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager(project_root: Optional[Path] = None) -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None or project_root is not None:
        _config_manager = ConfigManager(project_root)
    return _config_manager

def get_config(validation_level: ValidationLevel = ValidationLevel.STRICT) -> SystemConfig:
    """Get current system configuration"""
    return get_config_manager().get_config(validation_level)

def get_project_config_for_service() -> Dict[str, Any]:
    """Get project configuration dictionary for service initialization."""
    try:
        config_manager = get_config_manager()

        # Load project config from database if available
        from forge.shared.core.service_registry import get_session_manager
        session_manager = get_session_manager()
        persistence_service = getattr(session_manager, "persistence", None) if session_manager else None
        if persistence_service:
            project_config = persistence_service.load_project_config()
            if project_config:
                return project_config

        # Fall back to file-based configuration
        return config_manager._load_project_config()

    except Exception:
        # If any error occurs, return empty config (will use system defaults)
        return {}

def validate_critical_config(config: Dict[str, Any]) -> bool:
    """Validate critical configuration parameters that could cause failures."""
    try:
        # Extract LLM configuration
        llm_config = config.get('llm', {})
        
        # Critical validations
        critical_checks = [
            # API key validation
            _validate_api_keys(llm_config),
            # Rate limiting validation  
            _validate_rate_limits(llm_config),
            # Model parameter validation
            _validate_model_params(llm_config),
        ]
        
        return all(critical_checks)
        
    except Exception as e:
        print(f"Configuration validation error: {e}")
        return False

def _validate_api_keys(llm_config: Dict[str, Any]) -> bool:
    """Validate API keys are present if required."""
    # Check if at least one API key is provided
    api_keys = [
        llm_config.get('openrouter_api_key'),
        llm_config.get('cherry_api_key'),
        llm_config.get('lm_proxy_api_key'),
    ]
    
    # Also check environment variables as fallback
    env_api_keys = [
        os.getenv('OPENROUTER_API_KEY'),
        os.getenv('CHERRY_API_KEY'), 
        os.getenv('LM_PROXY_API_KEY'),
    ]
    
    all_api_keys = api_keys + env_api_keys
    return any(key and key.strip() for key in all_api_keys)

def _validate_rate_limits(llm_config: Dict[str, Any]) -> bool:
    """Validate rate limiting parameters."""
    max_concurrent = llm_config.get('rate_limit_max_concurrent', 1)
    min_delay = llm_config.get('rate_limit_min_delay', 2.0)
    
    return (
        isinstance(max_concurrent, int) and 1 <= max_concurrent <= 20 and
        isinstance(min_delay, (int, float)) and 0.1 <= min_delay <= 60.0
    )

def _validate_model_params(llm_config: Dict[str, Any]) -> bool:
    """Validate model parameters are within reasonable ranges."""
    temperature_fields = [
        'entity_extraction_temperature',
        'relationship_extraction_temperature', 
        'semantic_profiling_temperature',
        'narrative_synthesis_temperature',
        'relationship_inference_temperature',
        'deduplication_temperature',
    ]
    
    for field in temperature_fields:
        temp = llm_config.get(field)
        if temp is not None and not (0.0 <= temp <= 2.0):
            return False
    
    return True
