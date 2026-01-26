"""Document Metadata Extraction Service for PyScrAI Forge.

Extracts document metadata from intelligence report headers (classification, report ID, etc.).
"""

import logging
import re
from typing import Optional, Dict, Any

from forge.shared.core.event_bus import EventBus, EventPayload
from forge.shared.core import events

logger = logging.getLogger(__name__)


class DocumentMetadataService:
    """Service for extracting document metadata from intelligence reports."""
    
    # Regex patterns for common intelligence report metadata
    CLASSIFICATION_PATTERN = r'(?:SECRET|TOP SECRET|CONFIDENTIAL|UNCLASSIFIED)(?:\s*//\s*[A-Z\s]+)?'
    REPORT_ID_PATTERN = r'(?:REPORT\s+ID|SITREP|SIG)[\s:]+([A-Z0-9\-]+)'
    DATE_PATTERNS = [
        r'DATE:\s*(\d{4}-\d{2}-\d{2})',  # ISO format
        r'(?:DATE|DTG):\s*(\d{1,2}\s+[A-Z]{3}\s+\d{4})',  # 13 JAN 2026
        r'(\d{1,2}\s+[A-Z]{3}\s+\d{4})',  # Standalone date
    ]
    PRECEDENCE_PATTERN = r'PRECEDENCE:\s*([A-Z\s]+(?:\([^)]+\))?)'
    ZONE_PATTERN = r'ZONE:\s*([A-Z0-9\s]+(?:\([^)]+\))?)'
    AUTHORING_UNIT_PATTERN = r'PREPARED BY:\s*([^\n]+)'
    
    def __init__(self, event_bus: EventBus, persistence_service: Optional[Any] = None):
        """Initialize the metadata extraction service.
        
        Args:
            event_bus: Event bus for publishing/subscribing to events
            persistence_service: Persistence service for storing metadata (optional)
        """
        self.event_bus = event_bus
        self.persistence = persistence_service
    
    async def start(self):
        """Start the service and subscribe to events."""
        await self.event_bus.subscribe(events.TOPIC_DATA_INGESTED, self.handle_data_ingested)
    
    async def handle_data_ingested(self, payload: EventPayload):
        """Handle document ingestion events by extracting metadata.
        
        Runs before entity extraction to capture document-level context.
        
        Args:
            payload: Event payload containing doc_id and content
        """
        doc_id = payload.get("doc_id", "unknown")
        content = payload.get("content", "")
        
        if not content or not content.strip():
            logger.warning(f"Document {doc_id} has no content")
            return
        
        # Extract metadata from document header (first 500 chars typically contain header)
        header = content[:500]
        metadata = self._extract_metadata(header, content)
        
        if metadata:
            logger.info(f"Extracted metadata from document {doc_id}: {list(metadata.keys())}")
            
            # Store in database if persistence service available
            if self.persistence:
                await self._store_metadata(doc_id, metadata)
            
            # Publish metadata extracted event for other services
            await self.event_bus.publish(
                events.TOPIC_DOCUMENT_METADATA,
                {
                    "doc_id": doc_id,
                    "metadata": metadata,
                },
            )
        else:
            logger.debug(f"No metadata extracted from document {doc_id}")
    
    def _extract_metadata(self, header: str, full_content: str) -> Dict[str, Any]:
        """Extract metadata from document header using regex patterns.
        
        Args:
            header: First portion of document (typically contains metadata)
            full_content: Full document content for fallback searches
            
        Returns:
            Dictionary of extracted metadata fields
        """
        metadata = {}
        
        # Classification
        match = re.search(self.CLASSIFICATION_PATTERN, header, re.IGNORECASE)
        if match:
            metadata["classification"] = match.group(0).strip()
        
        # Report ID
        match = re.search(self.REPORT_ID_PATTERN, header, re.IGNORECASE)
        if match:
            metadata["report_id"] = match.group(1).strip()
        
        # Date (try multiple patterns)
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, header, re.IGNORECASE)
            if match:
                metadata["date"] = match.group(1).strip()
                break
        
        # Precedence
        match = re.search(self.PRECEDENCE_PATTERN, header, re.IGNORECASE)
        if match:
            metadata["precedence"] = match.group(1).strip()
        
        # Zone
        match = re.search(self.ZONE_PATTERN, header, re.IGNORECASE)
        if match:
            metadata["zone"] = match.group(1).strip()
        
        # Authoring Unit
        match = re.search(self.AUTHORING_UNIT_PATTERN, header, re.IGNORECASE)
        if match:
            metadata["authoring_unit"] = match.group(1).strip()
        
        return metadata
    
    async def _store_metadata(self, doc_id: str, metadata: Dict[str, Any]):
        """Store metadata in database.
        
        Args:
            doc_id: Document ID
            metadata: Metadata dictionary to store
        """
        if not self.persistence or not self.persistence.conn:
            return
        
        try:
            import json
            
            # Prepare values for database insertion
            classification = metadata.get("classification")
            report_id = metadata.get("report_id")
            date = metadata.get("date")
            precedence = metadata.get("precedence")
            authoring_unit = metadata.get("authoring_unit")
            zone = metadata.get("zone")
            metadata_json = json.dumps(metadata)
            
            # Upsert metadata
            self.persistence.conn.execute("""
                INSERT INTO document_metadata 
                (doc_id, classification, report_id, date, precedence, authoring_unit, zone, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (doc_id) DO UPDATE SET
                    classification = excluded.classification,
                    report_id = excluded.report_id,
                    date = excluded.date,
                    precedence = excluded.precedence,
                    authoring_unit = excluded.authoring_unit,
                    zone = excluded.zone,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
            """, [doc_id, classification, report_id, date, precedence, authoring_unit, zone, metadata_json])
            
            self.persistence.conn.commit()
            logger.info(f"Stored metadata for document {doc_id}")
            
        except Exception as e:
            logger.error(f"Error storing metadata for {doc_id}: {e}")
            try:
                self.persistence.conn.rollback()
            except:
                pass
