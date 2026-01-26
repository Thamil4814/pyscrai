"""FletXr Reactive State Management for Launcher.

This module implements the state management layer for the Flet UI using FletXr
reactive primitives. It replaces traditional controller patterns with a more
efficient reactive state approach.

Architecture:
- AppState: Global application shell state (navigation, logs, status)
- Store: Service locator for accessing state from any component
"""

from .app_state import AppState
from .store import Store

__all__ = ["AppState", "Store"]
