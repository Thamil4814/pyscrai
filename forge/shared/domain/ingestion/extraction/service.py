"""Extraction services for PyScrAI Forge."""

import os
import logging
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import duckdb
from forge.shared.core.event_bus import EventBus, EventPayload
from forge.shared.core import events
from forge.shared.core.services import BaseLLMService, call_llm_and_parse_json
from forge.shared.infrastructure.llm.base import LLMProvider
from forge.shared.config.prompts import render_prompt
from forge.shared.infrastructure.llm.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)

class DocumentExtractionService(BaseLLMService):
    """Service for extracting entities and relationships from documents (Event-based)."""
    
    def __init__(self, event_bus: EventBus, llm_provider: Optional[LLMProvider] = None):
        """Initialize the document extraction service.
        
        Args:
            event_bus: Event bus for publishing/subscribing to events
            llm_provider: LLM provider for entity extraction (optional)
        """
        super().__init__(event_bus, llm_provider, "DocumentExtractionService")

    async def start(self):
        """Start the service and subscribe to events."""
        await self.event_bus.subscribe(events.TOPIC_DATA_INGESTED, self.handle_data_ingested)

    async def handle_data_ingested(self, payload: EventPayload):
        """Handle document ingestion events by extracting entities.
        
        Args:
            payload: Event payload containing doc_id and content
        """
        doc_id = payload.get("doc_id", "unknown")
        content = payload.get("content", "")
        
        logger.debug(f"{self.service_name}: handle_data_ingested called for {doc_id} (content length: {len(content)})")
        
        if not content or not content.strip():
            logger.warning(f"Document {doc_id} has no content")
            return
        
        # Extract entities using LLM
        logger.info(f"{self.service_name}: Extracting entities from {doc_id}")
        entities = await self._extract_entities(doc_id, content)
        
        if entities:
            logger.info(f"{self.service_name}: Publishing TOPIC_ENTITY_EXTRACTED for {doc_id} with {len(entities)} entities")
            await self.event_bus.publish(
                events.TOPIC_ENTITY_EXTRACTED,
                {
                    "doc_id": doc_id,
                    "entities": entities,
                },
            )
            logger.info(f"Extracted {len(entities)} entities from document {doc_id}")
        else:
            logger.warning(f"No entities extracted from document {doc_id}")
    
    async def _extract_entities(self, doc_id: str, content: str) -> list[dict]:
        """Extract entities from document content using LLM."""
        logger.debug(f"{self.service_name}: Starting entity extraction for {doc_id} (content length: {len(content)})")
        
        if not await self.ensure_llm_provider():
            logger.error(f"{self.service_name}: LLM provider not available")
            return []
        
        assert self.llm_provider is not None
        llm_provider = self.llm_provider
        
        # Render prompt using Jinja2 template
        logger.debug(f"{self.service_name}: Rendering extraction prompt for {doc_id}")
        try:
            prompt = render_prompt("extraction_service", content=content)
            logger.debug(f"{self.service_name}: Prompt length: {len(prompt)} chars")
        except Exception as e:
            logger.error(f"{self.service_name}: Failed to render extraction prompt: {e}", exc_info=True)
            return []
        
        # Call LLM and parse JSON response
        logger.info(f"{self.service_name}: Calling LLM for entity extraction on {doc_id}")
        try:
            entities = await call_llm_and_parse_json(
                llm_provider=llm_provider,
                prompt=prompt,
                max_tokens=10000,
                temperature=0,
                service_name=self.service_name,
                doc_id=doc_id
            )
        except Exception as e:
            logger.error(f"{self.service_name}: Exception during LLM call for {doc_id}: {e}", exc_info=True)
            return []
        
        logger.debug(f"{self.service_name}: LLM response type: {type(entities)}, value: {entities}")
        
        if entities is None:
            logger.warning(f"{self.service_name}: LLM returned None for {doc_id}")
            return []
        
        if not isinstance(entities, list):
            logger.error(f"{self.service_name}: LLM returned non-list entity data: {type(entities)} - {entities}")
            return []
        
        logger.info(f"{self.service_name}: Got {len(entities)} raw entities from LLM for {doc_id}")
        
        normalized_entities = []
        for entity in entities:
            if isinstance(entity, dict) and "type" in entity and "text" in entity:
                attributes = entity.get("attributes", {})
                if not isinstance(attributes, dict):
                    attributes = {}
                
                normalized_entities.append({
                    "type": str(entity["type"]).upper(),
                    "text": str(entity["text"]).strip(),
                    "attributes": attributes
                })
        
        logger.info(f"{self.service_name}: Normalized to {len(normalized_entities)} entities for {doc_id}")
        return normalized_entities

class ExtractionService:
    """Event-driven Batch Extraction Service for the Unified Streamlit Architecture.
    
    This service orchestrates the full extraction pipeline:
    1. Document ingestion and chunking
    2. Entity extraction (via DocumentExtractionService)
    3. Relationship extraction (via EntityResolutionService)
    4. Graph building (via GraphAnalysisService)
    5. Persistence (via DuckDBPersistenceService)
    """
    
    def __init__(self, db_connection_string: str, chunk_size: int = 512, chunk_overlap: int = 50):
        self.db_path = db_connection_string
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize event bus and services
        self.event_bus = EventBus()
        self.llm_provider: Optional[LLMProvider] = None
        self._init_services()

    def _init_services(self):
        """Initialize all required services for the extraction pipeline."""
        try:
            # Initialize LLM provider
            self.llm_provider, _ = ProviderFactory.create_from_env()
            logger.info("ExtractionService: LLM provider initialized")
            
            # Import services here to avoid circular imports
            from forge.shared.domain.knowledge.resolution.service import EntityResolutionService
            from forge.shared.domain.knowledge.graph.service import GraphAnalysisService
            from forge.shared.infrastructure.persistence.duckdb_service import DuckDBPersistenceService
            
            # Initialize extraction service (subscribes to TOPIC_DATA_INGESTED)
            self.extraction_service = DocumentExtractionService(self.event_bus, self.llm_provider)
            
            # Initialize resolution service (subscribes to TOPIC_ENTITY_EXTRACTED)
            self.resolution_service = EntityResolutionService(self.event_bus, self.llm_provider)
            
            # Initialize graph service (subscribes to TOPIC_RELATIONSHIP_FOUND)
            self.graph_service = GraphAnalysisService(self.event_bus)
            
            # Initialize persistence service (subscribes to TOPIC_GRAPH_UPDATED)
            self.persistence_service = DuckDBPersistenceService(self.event_bus, self.db_path)
            
            logger.info("ExtractionService: All services initialized successfully")
        except Exception as e:
            logger.error(f"ExtractionService: Failed to initialize services: {e}", exc_info=True)

    def _read_file(self, file_path: Path) -> str:
        """Read content from supported file formats."""
        suffix = file_path.suffix.lower()
        if suffix == '.txt':
            return file_path.read_text(encoding='utf-8', errors='replace')
        elif suffix == '.pdf':
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except Exception as e:
                logger.error(f"Error reading PDF {file_path}: {e}")
                return ""
        return ""

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap."""
        if not text:
            return []
        
        words = text.split()
        chunks = []
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk = " ".join(words[i:i + self.chunk_size])
            chunks.append(chunk)
            if i + self.chunk_size >= len(words):
                break
        return chunks

    def process_directory(self, source_dir: Path) -> Dict[str, Any]:
        """Process all supported documents in a directory using the full event-driven pipeline."""
        if not source_dir.exists():
            return {"error": f"Directory {source_dir} does not exist", "processed_files": 0}

        files = list(source_dir.glob("*.pdf")) + list(source_dir.glob("*.txt"))
        if not files:
            return {"error": "No PDF or TXT files found", "processed_files": 0}
        
        # Check if there's already a running event loop
        try:
            loop = asyncio.get_running_loop()
            # We're already in an async context - this shouldn't happen in Streamlit
            logger.warning("ExtractionService: Already in async context, cannot use process_directory synchronously")
            return {"error": "ExtractionService.process_directory cannot be called from async context", "processed_files": 0}
        except RuntimeError:
            # No running event loop - we can create one
            pass
        
        # Create a new event loop for this sync->async bridge
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._process_directory_async(source_dir, files))
            return result
        finally:
            loop.close()

    async def _process_directory_async(self, source_dir: Path, files: List[Path]) -> Dict[str, Any]:
        """Async processing of all documents in a directory."""
        logger.info(f"ExtractionService._process_directory_async: Starting with {len(files)} files")
        
        # Start all services
        logger.info("ExtractionService: Starting persistence service...")
        await self.persistence_service.start()
        logger.info("ExtractionService: Starting extraction service...")
        await self.extraction_service.start()
        logger.info("ExtractionService: Starting resolution service...")
        await self.resolution_service.start()
        logger.info("ExtractionService: Starting graph service...")
        await self.graph_service.start()
        logger.info("ExtractionService: All services started successfully")
        
        logger.info(f"Starting extraction pipeline for {len(files)} files")
        await self.event_bus.publish(
            events.TOPIC_LOGS_EVENT,
            events.create_logs_event(
                f"🚀 Starting extraction of {len(files)} documents...",
                level="info"
            )
        )
        
        processed_count = 0
        total_entities = 0
        
        # Process each file
        for file_path in files:
            logger.info(f"Processing {file_path.name}...")
            await self.event_bus.publish(
                events.TOPIC_LOGS_EVENT,
                events.create_logs_event(
                    f"📄 Processing {file_path.name}...",
                    level="info"
                )
            )
            
            content = self._read_file(file_path)
            if not content:
                logger.warning(f"Could not read content from {file_path.name}")
                continue
            
            # Chunk the content for better processing
            chunks = self._chunk_text(content)
            logger.info(f"Split {file_path.name} into {len(chunks)} chunks")
            
            # Process each chunk by publishing to the event bus
            # This triggers the full pipeline: extraction -> resolution -> graph -> persistence
            for i, chunk in enumerate(chunks):
                doc_id = f"{file_path.stem}_chunk_{i}"
                
                try:
                    logger.debug(f"ExtractionService: Publishing TOPIC_DATA_INGESTED for {doc_id} (chunk size: {len(chunk)})")
                    # Publish data ingestion event - this triggers the entire pipeline
                    await self.event_bus.publish(
                        events.TOPIC_DATA_INGESTED,
                        events.create_data_ingested_event(doc_id, chunk)
                    )
                    logger.debug(f"ExtractionService: Event published for {doc_id}, waiting for processing...")
                    
                    # Give the pipeline time to process and respect rate limits
                    # Longer delays prevent hitting rate limits too quickly
                    # The extraction service will extract entities
                    # The resolution service will find relationships
                    # The graph service will update the graph
                    # The persistence service will save everything
                    await asyncio.sleep(2.0)  # Increased from 0.5s to 2.0s to avoid rate limits
                    
                except Exception as e:
                    logger.error(f"Error processing chunk {i} of {file_path.name}: {e}", exc_info=True)
                    await self.event_bus.publish(
                        events.TOPIC_LOGS_EVENT,
                        events.create_logs_event(
                            f"❌ Error in chunk {i} of {file_path.name}: {str(e)}",
                            level="error"
                        )
                    )
            
            processed_count += 1
            
            # Wait longer between files to allow full processing and avoid rate limits
            await asyncio.sleep(3.0)  # Increased wait between files
            
            # Get entity count from database
            if self.persistence_service.conn:
                result = self.persistence_service.conn.execute("""
                    SELECT COUNT(*) FROM entities
                """).fetchone()
                total_entities = result[0] if result else 0
            
            await self.event_bus.publish(
                events.TOPIC_LOGS_EVENT,
                events.create_logs_event(
                    f"✅ Completed {file_path.name} | Total entities: {total_entities}",
                    level="success"
                )
            )

        # Final wait for any remaining async events
        await asyncio.sleep(3.0)  # Increased from 2.0s to 3.0s
        
        # Get final counts from database
        if self.persistence_service.conn:
            entity_result = self.persistence_service.conn.execute("""
                SELECT COUNT(*) FROM entities
            """).fetchone()
            relationship_result = self.persistence_service.conn.execute("""
                SELECT COUNT(*) FROM relationships
            """).fetchone()
            total_entities = entity_result[0] if entity_result else 0
            total_relationships = relationship_result[0] if relationship_result else 0
        
        logger.info(f"Extraction complete: {processed_count} files, {total_entities} entities, {total_relationships} relationships")
        await self.event_bus.publish(
            events.TOPIC_LOGS_EVENT,
            events.create_logs_event(
                f"🎉 Extraction complete! Processed {processed_count} files | "
                f"{total_entities} entities | {total_relationships} relationships",
                level="success"
            )
        )

        return {
            "processed_files": processed_count,
            "entities_count": total_entities,
            "relationships_count": total_relationships
        }
