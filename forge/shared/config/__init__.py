"""
Shared Config Module
====================

Configuration settings and prompts used by all PyScrAI applications.

Structure:
- prompts/: Jinja2 templates for LLM prompts (domain services)
- settings/: YAML configuration files (defaults, project, user)
"""

from forge.shared.config.prompts import (
    PromptManager,
    render_prompt,
    get_prompt_manager,
)

__all__ = [
    "PromptManager",
    "render_prompt",
    "get_prompt_manager",
]
