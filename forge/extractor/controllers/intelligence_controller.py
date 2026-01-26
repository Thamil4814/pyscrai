"""Controller for handling intelligence-related UI events."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from forge.shared.core import events
from forge.extractor.ui.components.intelligence_publisher import publish_entity_card_ui

if TYPE_CHECKING:
    from forge.extractor.state.app_state import AppState
    import flet as ft

logger = logging.getLogger(__name__)


class IntelligenceController:
    """Controller that bridges intelligence domain events to the Flet UI."""

    def __init__(self, app_state: AppState, page: ft.Page):
        self.app_controller = app_state
        self.page = page
        self.event_bus = app_state.bus
        
        # Start subscription task
        asyncio.create_task(self._subscribe_to_events())
        
    async def _subscribe_to_events(self):
        """Register event subscriptions."""
        await self.event_bus.subscribe(events.TOPIC_ENTITY_CARD_READY, self._on_card_ready)
        logger.info("IntelligenceController subscribed to TOPIC_ENTITY_CARD_READY")

    async def _on_card_ready(self, payload):
        """Handle entity card ready events by publishing to UI."""
        try:
            entity_id = payload.get("entity_id")
            entity_type = payload.get("entity_type")
            label = payload.get("label")
            relationship_count = payload.get("relationship_count", 0)
            
            if not entity_id or not label:
                logger.warning("Received TOPIC_ENTITY_CARD_READY event with missing data")
                return
            
            # Use the existing UI publisher (which is in the presentation layer)
            await publish_entity_card_ui(
                self.event_bus,
                entity_id=entity_id,
                entity_type=entity_type or "Unknown",
                label=label,
                relationship_count=relationship_count
            )
            
        except Exception as e:
            logger.error(f"Error handling TOPIC_ENTITY_CARD_READY: {e}")
