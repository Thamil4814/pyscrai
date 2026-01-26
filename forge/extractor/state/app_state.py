"""Application Shell State Management.

Replaces AppController with a pure reactive state approach using FletXr.
Optimized for performance with circular log buffers and minimal re-renders.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fletx.core import RxBool, RxDict, RxList, RxStr

from forge.shared.core.event_bus import EventBus, EventPayload


class AppState:
    """Reactive State for the Application Shell.
    
    This class manages the global UI state including navigation, status,
    and workspace information. It subscribes to EventBus events and updates
    reactive properties that automatically trigger UI updates.
    
    Performance Optimizations:
    - Direct list mutation with manual triggers
    - Minimal state updates
    """
    
    def __init__(self, event_bus: EventBus) -> None:
        """Initialize application state.
        
        Args:
            event_bus: The shared event bus for cross-cutting concerns
        """
        self.bus = event_bus
        
        # Navigation State
        self.nav_items: RxList[Dict[str, str]] = RxList([
            {"id": "dashboard", "label": "", "icon": "dashboard"},
            {"id": "intel", "label": "", "icon": "psychology"},
            {"id": "settings", "label": "", "icon": "settings"},
        ])
        self.nav_selected: RxStr = RxStr("dashboard")
        
        # Status & Readiness
        self.is_ready: RxBool = RxBool(False)
        self.status_text: RxStr = RxStr("System Initializing...")
        
        # Workspace Information
        self.workspace_schemas: RxList[Dict[str, Any]] = RxList([])

        # Log entries (each is a dict: {message, level, ts})
        self.logs: RxList[Dict[str, Any]] = RxList([])
        
        # Internal state
        self._started = False
        
    async def initialize(self) -> None:
        """Initialize state and bind to EventBus events.
        
        This method should be called once during application startup to
        establish event subscriptions.
        """
        if self._started:
            return
            
        # Subscribe to events
        await self.bus.subscribe("workspace.schema", self._handle_workspace_schema)
        await self.bus.subscribe("workspace.clear", self._handle_workspace_clear)
        await self.bus.subscribe("status.text", self._handle_status_text)
        await self.bus.subscribe("nav.select", self._handle_nav_select)
        
        self._started = True
        self.is_ready.value = True

    # --- Public Actions ---
    
    def set_nav(self, route_id: str) -> None:
        """Change the selected navigation route.
        
        Args:
            route_id: The ID of the route to navigate to
        """
        self.nav_selected.value = route_id
        
    async def publish(self, topic: str, payload: EventPayload) -> None:
        """Publish an event to the EventBus.
        
        Args:
            topic: Event topic
            payload: Event payload data
        """
        await self.bus.publish(topic, payload)
        
    async def raise_user_action(
        self, 
        action: str, 
        payload: Optional[EventPayload] = None
    ) -> None:
        """Raise a user action event.
        
        Helper for UI components to push user intent into the event bus.
        
        Args:
            action: Action identifier
            payload: Optional additional data
        """
        await self.publish("user.action", {"action": action, **(payload or {})})
        
    async def emit_schema(self, schema: Dict[str, Any]) -> None:
        """Emit a workspace schema event.
        
        Args:
            schema: Schema data to publish
        """
        await self.publish("workspace.schema", {"schema": schema})
        
    async def push_status(self, text: str) -> None:
        """Update the status text.
        
        Helper method for quick status updates.
        
        Args:
            text: Status message to display
        """
        await self.publish("status.text", {"text": text})
        
    async def push_log(self, message: str, level: str = "info") -> None:
        """Add a log message and update the logs list reactively."""
        entry = {"message": message, "level": level, "ts": time.time()}
        self.logs.append(entry)
        await self.publish("logs.event", entry)
        
    # --- Event Handlers ---

    async def _handle_workspace_schema(self, payload: EventPayload) -> None:
        """Handle workspace schema updates."""
        schema = payload.get("schema")
        if schema:
            self.workspace_schemas.append(schema)

    async def _handle_workspace_clear(self, payload: EventPayload) -> None:
        """Handle workspace clear requests."""
        self.workspace_schemas.clear()

    async def _handle_status_text(self, payload: EventPayload) -> None:
        """Handle status text updates."""
        text = payload.get("text")
        if text:
            self.status_text.value = str(text)

    async def _handle_nav_select(self, payload: EventPayload) -> None:
        """Handle navigation selection events."""
        selection = payload.get("id")
        if selection:
            self.nav_selected.value = str(selection)

    async def _handle_log_event(self, payload: EventPayload) -> None:
        """Handle log events and update the logs list reactively."""
        if payload:
            self.logs.append(payload)
