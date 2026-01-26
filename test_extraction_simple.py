#!/usr/bin/env python3
"""Simple test script for entity extraction pipeline."""

import asyncio
import logging
from pathlib import Path
from forge.shared.domain.ingestion.extraction.service import ExtractionService

# Setup logging to see all debug messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Test the extraction service with test_1.txt"""
    
    # Setup paths
    project_path = Path("forge/data/projects/jessica_tyler")
    source_dir = project_path / "source_docs"
    db_path = str(project_path / "world.duckdb")
    
    logger.info(f"Testing extraction service")
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Database path: {db_path}")
    logger.info(f"Source dir exists: {source_dir.exists()}")
    logger.info(f"Files in source dir: {list(source_dir.glob('*'))}")
    
    # Create service
    service = ExtractionService(
        db_connection_string=db_path,
        chunk_size=512,
        chunk_overlap=50
    )
    
    logger.info("ExtractionService created")
    logger.info(f"LLM Provider: {service.llm_provider}")
    
    # Process directory - call the async method directly since we're in async context
    logger.info("Starting extraction...")
    result = await service._process_directory_async(source_dir, list(source_dir.glob("*.pdf")) + list(source_dir.glob("*.txt")))
    
    logger.info(f"Extraction result: {result}")

if __name__ == "__main__":
    asyncio.run(main())

