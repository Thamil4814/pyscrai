"""Pages package - Streamlit page implementations for the Sandbox.

This module contains all the page render functions for the PyScrAI Forge Sandbox application.
Each page follows the same pattern: a render function that takes a Session object and renders the UI.
"""

# Import all page rendering functions for easy access
from .world_manifest import render_world_manifest
from .agent_forge import render_agent_forge
from .spatial_domain import render_spatial_domain
from .event_chronology import render_event_chronology
from .simulation_lab import render_simulation_lab
from .prefab_factory import render_prefab_factory

__all__ = [
    'render_world_manifest',
    'render_agent_forge',
    'render_spatial_domain',
    'render_event_chronology',
    'render_simulation_lab',
    'render_prefab_factory'
]