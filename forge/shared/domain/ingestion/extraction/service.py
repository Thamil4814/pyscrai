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
        
        if not content or not content.strip():
            logger.warning(f"Document {doc_id} has no content")
            return
        
        # Extract entities using LLM
        entities = await self._extract_entities(doc_id, content)
        
        if entities:
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
        if not await self.ensure_llm_provider():
            return []
        
        assert self.llm_provider is not None
        llm_provider = self.llm_provider
        
        # Render prompt using Jinja2 template
        prompt = render_prompt("extraction_service", content=content)
        
        # Call LLM and parse JSON response
        entities = await call_llm_and_parse_json(
            llm_provider=llm_provider,
            prompt=prompt,
            max_tokens=10000,
            temperature=0,
            service_name=self.service_name,
            doc_id=doc_id
        )
        
        if entities is None:
            return []
        
        if not isinstance(entities, list):
            logger.error(f"{self.service_name}: LLM returned non-list entity data: {type(entities)}")
            return []
        
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
        
        return normalized_entities

class ExtractionService:
    """Synchronous/Batch Extraction Service for the Unified Streamlit Architecture."""
    
    def __init__(self, db_connection_string: str, chunk_size: int = 512, chunk_overlap: int = 50):
        self.db_path = db_connection_string
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.llm_provider: Optional[LLMProvider] = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM provider from environment."""
        try:
            self.llm_provider, _ = ProviderFactory.create_from_env()
            logger.info("ExtractionService: LLM provider initialized")
        except Exception as e:
            logger.error(f"ExtractionService: Failed to initialize LLM provider: {e}")

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
        """Process all supported documents in a directory."""
        if not source_dir.exists():
            return {"error": f"Directory {source_dir} does not exist", "processed_files": 0}

        files = list(source_dir.glob("*.pdf")) + list(source_dir.glob("*.txt"))
        total_entities = 0
        processed_count = 0
        
        # Connect to DB
        conn = duckdb.connect(self.db_path)
        
        # We'll use asyncio.run to call the async LLM logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for file_path in files:
                logger.info(f"Processing {file_path.name}...")
                content = self._read_file(file_path)
                if not content:
                    continue
                
                chunks = self._chunk_text(content)
                file_entities_count = 0
                
                for i, chunk in enumerate(chunks):
                    # Use DocumentExtractionService's extraction logic (internal call)
                    # We can instantiate a temporary DocumentExtractionService or just call it directly
                    # since it's a BaseLLMService
                    doc_id = f"{file_path.name}_chunk_{i}"
                    
                    try:
                        entities = loop.run_until_complete(self._extract_entities_async(doc_id, chunk))
                        if entities:
                            self._persist_entities(conn, entities)
                            file_entities_count += len(entities)
                    except Exception as e:
                        logger.error(f"Error extracting from chunk {i} of {file_path.name}: {e}")
                
                total_entities += file_entities_count
                processed_count += 1
                logger.info(f"Finished {file_path.name}: Extracted {file_entities_count} entities")

            conn.commit()
        finally:
            conn.close()
            loop.close()

        return {
            "processed_files": processed_count,
            "entities_count": total_entities
        }

    async def _extract_entities_async(self, doc_id: str, content: str) -> List[Dict[str, Any]]:
        """Async bridge for LLM extraction."""
        if not self.llm_provider:
            return []
        
        prompt = render_prompt("extraction_service", content=content)
        entities = await call_llm_and_parse_json(
            llm_provider=self.llm_provider,
            prompt=prompt,
            max_tokens=10000,
            temperature=0,
            service_name="ExtractionService",
            doc_id=doc_id
        )
        
        if not entities or not isinstance(entities, list):
            return []
            
        normalized = []
        for e in entities:
            if isinstance(e, dict) and "type" in e and "text" in e:
                normalized.append({
                    "id": f"{e['type']}_{e['text']}".replace(" ", "_").lower(),
                    "type": str(e["type"]).upper(),
                    "label": str(e["text"]).strip(),
                    "attributes": e.get("attributes", {})
                })
        return normalized

    def _persist_entities(self, conn, entities: List[Dict[str, Any]]):
        """Save entities to world.duckdb."""
        for e in entities:
            attr_json = json.dumps(e["attributes"])
            conn.execute("""
                INSERT INTO entities (id, type, label, attributes_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET 
                    type = EXCLUDED.type,
                    label = EXCLUDED.label,
                    attributes_json = EXCLUDED.attributes_json,
                    updated_at = CURRENT_TIMESTAMP
            """, [e["id"], e["type"], e["label"], attr_json])
