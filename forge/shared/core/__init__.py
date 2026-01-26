"""
Shared Core Module
==================

Event system, configuration, and service base classes.
"""

# Event System
from .event_bus import EventBus, EventPayload
from . import events

# Service Infrastructure
from .services import BaseLLMService, call_llm_with_retry, call_llm_and_parse_json, call_llm_and_get_text
from .service_registry import (
    get_session_manager,
    set_session_manager,
    register_intelligence_service,
    get_intelligence_services,
    register_cleanup_handler,
)

# Configuration
from .configuration import (
    ConfigManager,
    SystemConfig,
    get_config_manager,
    get_config,
    get_project_config_for_service,
    validate_critical_config,
    ValidationLevel,
)

__all__ = [
    # Event System
    "EventBus",
    "EventPayload",
    "events",
    # Services
    "BaseLLMService",
    "call_llm_with_retry",
    "call_llm_and_parse_json",
    "call_llm_and_get_text",
    # Service Registry
    "get_session_manager",
    "set_session_manager",
    "register_intelligence_service",
    "get_intelligence_services",
    "register_cleanup_handler",
    # Configuration
    "ConfigManager",
    "SystemConfig",
    "get_config_manager",
    "get_config",
    "get_project_config_for_service",
    "validate_critical_config",
    "ValidationLevel",
]
