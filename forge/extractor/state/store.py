"""Global State Store - Service Locator Pattern.

Provides centralized access to all reactive state from any UI component.
Implements the singleton pattern for consistent state access.
"""

from __future__ import annotations

from typing import Optional

from .app_state import AppState
from forge.shared.core.event_bus import EventBus


class Store:
    """Global state store for the launcher application.
    
    This class implements a singleton pattern to provide consistent access
    to reactive state across all UI components. It acts as a service locator
    for state management.
    
    Usage:
        # During app initialization
        Store.initialize(event_bus)
        
        # In any UI component
        store = Store.get()
        store.app.nav_selected.value = "dashboard"
    """
    
    _instance: Optional['Store'] = None
    
    def __init__(self, event_bus: EventBus) -> None:
        """Initialize store with event bus.
        
        Note: Do not call directly. Use Store.initialize() instead.
        
        Args:
            event_bus: The shared event bus instance
        """
        self.app = AppState(event_bus)
        # Future expansion:
        # self.session = SessionState(event_bus)
        # self.project = ProjectState(event_bus)

    @classmethod
    def initialize(cls, event_bus: EventBus) -> 'Store':
        """Initialize the global store instance.
        
        Should be called once during application startup before any UI
        components are created.
        
        Args:
            event_bus: The shared event bus instance
            
        Returns:
            The initialized store instance
            
        Raises:
            RuntimeError: If store is already initialized
        """
        if cls._instance is not None:
            raise RuntimeError("Store already initialized!")
            
        cls._instance = cls(event_bus)
        return cls._instance

    @classmethod
    def get(cls) -> 'Store':
        """Get the global store instance.
        
        Returns:
            The store instance
            
        Raises:
            RuntimeError: If store has not been initialized
        """
        if cls._instance is None:
            raise RuntimeError("Store not initialized! Call Store.initialize() first.")
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the store instance.
        
        Primarily used for testing. In production, store persists for
        application lifetime.
        """
        cls._instance = None
