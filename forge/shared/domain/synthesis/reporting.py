"""Entity Card Service for publishing entity cards to the intelligence workspace."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from forge.shared.core.event_bus import EventPayload, EventBus
from forge.shared.core import events

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EntityCardService:
    """Service for publishing entity cards when entities are extracted."""
    
    def __init__(self, event_bus: EventBus, db_connection=None):
        """Initialize the entity card service.
        
        Args:
            event_bus: Event bus for subscribing to events
            db_connection: DuckDB connection for querying entity data
        """
        self.event_bus = event_bus
        self.db_conn = db_connection
        self.service_name = "EntityCardService"
        
    def update_db_connection(self, db_connection) -> None:
        """Update the database connection (called when a project is opened)."""
        self.db_conn = db_connection
        
    async def start(self):
        """Start the service and subscribe to events."""
        logger.info("Starting EntityCardService")
        
        # Subscribe to entity extraction events
        await self.event_bus.subscribe(events.TOPIC_ENTITY_EXTRACTED, self.handle_entity_extracted)
        
        logger.info("EntityCardService started")
    
    async def handle_entity_extracted(self, payload: EventPayload):
        """Handle entity extracted events by publishing entity cards."""
        try:
            logger.debug(f"Received entity extracted event payload: {payload}")
            entity_id = payload.get("entity_id")
            entity_type = payload.get("entity_type")
            entity_name = payload.get("entity_name") 
            doc_id = payload.get("doc_id")
            if not entity_id or not entity_name:
                logger.warning("Entity extracted event missing required data")
                logger.debug(f"Payload missing fields: entity_id={entity_id}, entity_name={entity_name}, full payload={payload}")
                return
            # Get relationship count for this entity from database
            relationship_count = 0
            if self.db_conn:
                try:
                    result = self.db_conn.execute("""
                        SELECT COUNT(*) FROM relationships 
                        WHERE source = ? OR target = ?
                    """, (entity_id, entity_id)).fetchone()
                    if result:
                        relationship_count = result[0]
                except Exception as e:
                    logger.warning(f"Could not fetch relationship count for entity {entity_id}: {e}")
            # Publish entity card to intelligence workspace via event
            event_payload = {
                "entity_id": entity_id,
                "entity_type": entity_type or "Unknown",
                "label": entity_name,
                "relationship_count": relationship_count
            }
            logger.debug(f"Publishing entity card event payload: {event_payload}")
            await self.event_bus.publish(
                events.TOPIC_ENTITY_CARD_READY,
                event_payload
            )
            logger.info(f"Published entity card event for {entity_name} ({entity_id})")
            
        except Exception as e:
            logger.error(f"Error publishing entity card: {e}")
