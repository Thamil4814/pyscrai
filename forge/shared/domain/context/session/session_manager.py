"""Session Manager for saving, loading, and clearing application state."""

from __future__ import annotations

import json
import logging
import os
import asyncio
import shutil
from pathlib import Path

from forge.shared.core import events
from forge.shared.core.event_bus import EventBus
from forge.shared.infrastructure.persistence.duckdb_service import DuckDBPersistenceService
from forge.shared.infrastructure.vector.qdrant_service import QdrantService
from forge.shared.infrastructure.embeddings.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class SessionManager:
    """Orchestrates loading persisted state into the runtime."""

    def __init__(
        self,
        event_bus: EventBus,
        persistence_service: DuckDBPersistenceService,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService
    ):
        self.event_bus = event_bus
        self.persistence = persistence_service
        self.qdrant = qdrant_service
        self.embedding = embedding_service

    async def restore_session(self):
        """Reloads UI state and re-indexes vectors from the last manually-saved project.
        
        NOTE: Since auto-save is disabled, this loads the state from the last time
        the user clicked 'Save Project'. Real-time extraction/analysis changes are
        held in memory until explicitly saved.
        
        NOTE: UI artifacts are NOT restored - they are snapshots from previous extractions
        and may be stale. The workspace should be empty, allowing intelligence views
        to query the database directly for current data.
        """
        logger.info("♻️ Restoring session from database...")
        await self._push_log("♻️ Starting Session Restore...", "info")

        # Get current running loop for offloading blocking calls
        loop = asyncio.get_running_loop()

        # Publish session restore start event
        await self.event_bus.publish("session.restore.start", {})

        # 1. Clear current UI first to avoid duplicates
        await self._clear_workspace()

        # 1.5. Clean up stale processing entries from previous sessions
        # When opening an existing project, mark any documents that were in 'processing'
        # status from the previous session as 'completed' to prevent them from
        # displaying as still processing in the UI
        try:
            updated_count = await loop.run_in_executor(
                None,
                self.persistence.clean_stale_processing_entries
            )
            if updated_count > 0:
                logger.info(f"Updated {updated_count} stale processing entries to 'completed'")
                await self._push_log(f"Updated {updated_count} document entries from previous session", "info")
            updated_count = await loop.run_in_executor(
                None, 
                self.persistence.clean_stale_processing_entries
            )
            if updated_count > 0:
                logger.info(f"Updated {updated_count} stale processing entries to 'completed'")
                await self._push_log(f"Updated {updated_count} document entries from previous session", "info")
        except Exception as e:
            logger.error(f"Error cleaning up stale processing entries: {e}")
            await self._push_log(f"Warning: Could not clean up processing entries: {e}", "warning")

        # 2. Skip restoring UI artifacts - they are snapshots from previous extractions
        # and may be stale. The workspace should be empty, allowing intelligence views
        # (Graph Analytics, Entity Cards, etc.) to query the database directly for current data.
        # UI artifacts are meant for real-time streaming during extraction, not persistent storage.
        logger.info("Skipping UI artifacts restoration (workspace will be empty, views query DB directly)")
        await self._push_log("Workspace cleared. Intelligence views will load from database.", "info")
        
        # 3. Clear QDrant collections before re-indexing to avoid IndexError
        logger.info("Clearing QDrant collections before re-indexing...")
        await self._push_log("Clearing vector store...", "info")
        await self.qdrant.clear_collections()

        # 4. Re-index Entities
        entities = await loop.run_in_executor(None, self.persistence.get_all_entities)
        entities = await loop.run_in_executor(None, self.persistence.get_all_entities)
        if entities:
            msg = f"Re-indexing {len(entities)} entities into Vector Store..."
            logger.info(msg)
            await self._push_log(msg, "info")
            
            # Convert database format to entity format for embedding
            # Database has: id, type, label, created_at, updated_at
            # Embedding format needs: text, type (for entity dict)
            entity_list = [
                {
                    "text": entity["label"],
                    "type": entity["type"]
                }
                for entity in entities
            ]
            
            # Prepare texts for embedding (same format as EmbeddingService)
            entity_texts = [
                f"{entity['text']} ({entity['type']})"
                for entity in entity_list
            ]
            
            # Embed entities directly (bypass extraction pipeline)
            embeddings = await self.embedding.embed_batch(entity_texts, use_long_context=False)
            
            # Publish embedded events directly (only QdrantService listens to these)
            for entity, embedding_vec in zip(entity_list, embeddings):
                await self.event_bus.publish(
                    events.TOPIC_ENTITY_EMBEDDED,
                    {
                        "doc_id": "restore_session",
                        "entity": entity,
                        "text": f"{entity['text']} ({entity['type']})",
                        "embedding": embedding_vec,
                        "dimension": len(embedding_vec),
                    }
                )
            
            await self._push_log("Entity re-indexing complete.", "success")
        else:
            await self._push_log("No entities found to re-index.", "warning")

        # 5. Re-index Relationships
        relationships = await loop.run_in_executor(None, self.persistence.get_all_relationships)
        relationships = await loop.run_in_executor(None, self.persistence.get_all_relationships)
        if relationships:
            msg = f"Re-indexing {len(relationships)} relationships into Vector Store..."
            logger.info(msg)
            await self._push_log(msg, "info")
            
            # Convert database format to relationship format for embedding
            # Database has: id, source, target, type, confidence, doc_id, created_at
            # Embedding format needs: source, target, type
            relationship_list = [
                {
                    "source": rel["source"],
                    "target": rel["target"],
                    "type": rel["type"]
                }
                for rel in relationships
            ]
            
            # Prepare texts for embedding (same format as EmbeddingService)
            relationship_texts = [
                f"{rel['source']} {rel['type']} {rel['target']}"
                for rel in relationship_list
            ]
            
            # Embed relationships directly (bypass extraction pipeline)
            embeddings = await self.embedding.embed_batch(relationship_texts, use_long_context=False)
            
            # Publish embedded events directly (only QdrantService listens to these)
            for rel, embedding_vec in zip(relationship_list, embeddings):
                await self.event_bus.publish(
                    events.TOPIC_RELATIONSHIP_EMBEDDED,
                    {
                        "doc_id": "restore_session",
                        "relationship": rel,
                        "text": f"{rel['source']} {rel['type']} {rel['target']}",
                        "embedding": embedding_vec,
                        "dimension": len(embedding_vec),
                    }
                )
            
            await self._push_log("Relationship re-indexing complete.", "success")
        else:
            await self._push_log("No relationships found to re-index.", "warning")
        
        # 6. Load semantic profiles from database and publish to workspace
        profiles = await loop.run_in_executor(None, self.persistence.get_all_semantic_profiles)
        profiles = await loop.run_in_executor(None, self.persistence.get_all_semantic_profiles)
        if profiles:
            logger.info(f"Loading {len(profiles)} semantic profiles from database...")
            # Get all entities once (avoid O(n*m) complexity)
            # Re-use already fetched entities if possible, but safe to fetch again async
            entities_for_map = await loop.run_in_executor(None, self.persistence.get_all_entities)
            entity_map = {e["id"]: e for e in entities_for_map}  # Create lookup map
            # Re-use already fetched entities if possible, but safe to fetch again async
            entities_for_map = await loop.run_in_executor(None, self.persistence.get_all_entities)
            entity_map = {e["id"]: e for e in entities_for_map}  # Create lookup map
            
            for profile in profiles:
                entity_id = profile.get("entity_id")
                if entity_id:
                    # Get entity info for display
                    entity_info = entity_map.get(entity_id)
                    if entity_info:
                        await self.event_bus.publish(
                            events.TOPIC_WORKSPACE_SCHEMA,
                            events.create_workspace_schema_event({
                                "type": "semantic_profile",
                                "title": f"Profile: {entity_info['label']}",
                                "props": profile
                            })
                        )
            await self._push_log(f"Loaded {len(profiles)} semantic profiles from database.", "info")
        else:
            await self._push_log("No semantic profiles found in database.", "info")
        
        # 7. Load narratives from database and publish to workspace
        narratives = await loop.run_in_executor(None, self.persistence.get_all_narratives)
        narratives = await loop.run_in_executor(None, self.persistence.get_all_narratives)
        if narratives:
            logger.info(f"Loading {len(narratives)} narratives from database...")
            for narrative_data in narratives:
                await self.event_bus.publish(
                    events.TOPIC_WORKSPACE_SCHEMA,
                    events.create_workspace_schema_event({
                        "type": "narrative",
                        "title": f"Narrative: {narrative_data['doc_id']}",
                        "props": {
                            "doc_id": narrative_data["doc_id"],
                            "narrative": narrative_data["narrative"],
                            "entity_count": narrative_data["entity_count"],
                            "relationship_count": narrative_data["relationship_count"],
                        }
                    })
                )
            await self._push_log(f"Loaded {len(narratives)} narratives from database.", "info")
        
        # 8. Load entity cards from database and publish to workspace
        # Run DB calls in executor (entities and relationship counts)
        # Using a single query to get counts for all entities to avoid N+1 problem
        entities = await loop.run_in_executor(None, self.persistence.get_all_entities)
        counts = await loop.run_in_executor(None, self.persistence.get_entity_relationship_counts)

        if entities and self.persistence.conn:
            logger.info(f"Loading {len(entities)} entity cards from database...")
            
            for entity_data in entities:
                relationship_count = counts.get(entity_data["id"], 0)
                
                # Publish entity card ready event
                await self.event_bus.publish(
                    events.TOPIC_ENTITY_CARD_READY,
                    {
                        "entity_id": entity_data["id"],
                        "entity_type": entity_data["type"] or "Unknown",
                        "label": entity_data["label"] or entity_data["id"],
                        "relationship_count": relationship_count
                    }
                )
            
            await self._push_log(f"Loaded {len(entities)} entity cards from database.", "info")
        
        # 9. Trigger graph analysis to generate UI schemas from database data
        # This will cause AdvancedGraphAnalysisService to analyze the graph and publish schemas
        # Pass None as doc_id to analyze ALL entities/relationships, not just a specific document
        # Set skip_deduplication=True since data is already deduplicated
        logger.info("Triggering graph analysis to generate UI schemas...")
        await self._push_log("Generating intelligence views from database...", "info")
        await self.event_bus.publish(
            events.TOPIC_GRAPH_UPDATED,
            {
                "doc_id": None,  # None = analyze all data, not filtered by doc_id
                "graph_stats": {},  # Empty stats - services will query DB directly
                "skip_deduplication": True,  # Skip deduplication during restore (data already processed)
                "skip_semantic_profiling": True  # Skip semantic profiling (profiles already loaded from DB)
            }
        )

        # Publish session restore end event
        await self.event_bus.publish("session.restore.end", {})

    async def clear_workspace_only(self):
        """Clears only the UI workspace for a new project (database untouched)."""
        logger.info("🎨 Clearing workspace UI only...")
        
        # Clear only the UI workspace, keep all database data intact
        await self._clear_workspace()
        
        await self._push_log("Workspace cleared. Database preserved.", "success")

    async def clear_session(self):
        """Wipes the database and clears the UI (full reset)."""
        logger.info("🗑️ Clearing session...")
        
        # 1. Clear UI
        await self._clear_workspace()
        
        # 2. Clear Database
        self.persistence.clear_all_data()
        
        # 3. Reset the database connection to ensure fresh state
        # This prevents cached state or pending transactions from interfering
        try:
            if self.persistence.conn:
                self.persistence.conn.close()
                logger.info("Closed database connection after clearing")
            
            # Reconnect to get a fresh connection
            import duckdb
            self.persistence.conn = duckdb.connect(self.persistence.db_path)
            # Recreate schema to ensure tables exist
            self.persistence._create_schema()
            logger.info("Reconnected to database with fresh state")
        except Exception as e:
            logger.error(f"Error resetting database connection: {e}")
            await self._push_log(f"Warning: Database connection reset failed: {e}", "warning")
        
        # 4. Clear Vector Store (if supported by QdrantService, otherwise restart needed for in-memory)
        # Assuming QdrantService has a way to reset or we just rely on DB wipe
        # Re-creating collections in Qdrant is a heavy op, ideally we'd delete points.
        # For now, we rely on the DB wipe. Future searches won't match if we don't clear vectors,
        # but semantic deduplication logic will just fail to find matches (safe).
        
        await self._push_log("Session and Database Cleared.", "success")

    async def save_project(self, file_path: str) -> None:
        """Save the current project by storing config.json in database and checkpointing.
        
        The database file ({project_name}.duckdb) is already the primary file,
        so we just need to:
        1. Store config.json from project directory into the database
        2. Checkpoint WAL to ensure all data is persisted
        """
        logger.info(f"💾 Saving project...")
        await self._push_log(f"Saving project...", "info")

        # Publish project saving start event
        await self.event_bus.publish("project.saving.start", {})

        try:
            # Load config.json from project directory if it exists
            db_path = Path(self.persistence.db_path)
            project_dir = db_path.parent
            config_json_path = project_dir / "config.json"

            if config_json_path.exists():
                import json
                with open(config_json_path, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)
                # Store config.json in the database
                self.persistence.save_project_config(config_dict)
                logger.info("Stored config.json in database")

            # Ensure all transactions are committed and WAL is checkpointed
            if self.persistence.conn:
                # Force a checkpoint to write WAL data to the main database file
                try:
                    self.persistence.conn.execute("CHECKPOINT")
                except Exception as e:
                    logger.warning(f"Could not checkpoint database: {e}")

                # Commit any pending transactions
                try:
                    self.persistence.conn.commit()
                except Exception:
                    pass

                logger.info(f"Project saved successfully (database: {db_path.name})")
                await self._push_log(f"Project saved successfully", "success")

        except Exception as e:
            logger.error(f"Error saving project: {e}")
            await self._push_log(f"Error saving project: {str(e)}", "error")

        # Publish project saving end event (always, even on error)
        await self.event_bus.publish("project.saving.end", {})

    async def open_project(self, file_path: str) -> None:
        """Open a project database file and restore the session.

        SAFE APPROACH: Connects to the selected file without overwriting main database.
        """
        logger.info(f"📂 Opening project from {file_path}...")
        await self._push_log(f"Opening project from {file_path}...", "info")

        # Publish project opening start event
        await self.event_bus.publish("project.opening.start", {})
        
        try:
            source_path = Path(file_path).resolve()
            if not source_path.exists():
                await self._push_log(f"Project file not found: {file_path}", "error")
                return
            
            # Check if the source path is the same as the current database path
            db_path = Path(self.persistence.db_path).resolve()
            if source_path == db_path:
                # Same file, just restore the session
                logger.info("Opening current database, restoring session...")
                await self._push_log("Opening current database, restoring session...", "info")
                await self.restore_session()
                return
            
            # SAFE APPROACH: Connect to the external file temporarily without overwriting main database
            # Close the current database connection
            if self.persistence.conn:
                self.persistence.conn.close()
            
            # Connect directly to the selected file (DO NOT COPY/OVERWRITE)
            import duckdb
            self.persistence.conn = duckdb.connect(str(source_path))
            # Update the db_path reference to track what file we're currently connected to
            self.persistence.db_path = str(source_path)
            
            # Ensure the opened database has proper schema (tables may not exist)
            self.persistence._create_schema()
            
            # Extract config.json from database and write to project directory
            project_dir = source_path.parent
            config_json_path = project_dir / "config.json"
            
            project_config = self.persistence.load_project_config()
            if project_config:
                import json
                # Update db_path in extracted config to point to intel.duckdb
                if "database" not in project_config:
                    project_config["database"] = {}
                project_root = Path(__file__).parent.parent.parent.parent
                project_db_path = project_dir / "intel.duckdb"
                try:
                    if project_db_path.is_relative_to(project_root):
                        project_config["database"]["db_path"] = str(project_db_path.relative_to(project_root))
                    else:
                        project_config["database"]["db_path"] = str(project_db_path)
                except (AttributeError, ValueError):
                    project_config["database"]["db_path"] = str(project_db_path)
                
                with open(config_json_path, 'w', encoding='utf-8') as f:
                    json.dump(project_config, f, indent=2)
                logger.info(f"Extracted config.json to {config_json_path}")
            else:
                # If no config in DB, create a temporary one from .env
                await self._create_temp_config(config_json_path, project_dir)
            
            # Check for schema version and auto-migrate if needed
            await self._migrate_schema(source_path)
            
            logger.info(f"Project opened successfully from {file_path}")
            await self._push_log(f"Project opened successfully. Restoring session...", "success")
            
            # Update database connections for intelligence services
            await self._update_service_connections()
            
            # Restore the session from the new database
            await self.restore_session()
            
            # Emit project opened event to notify UI
            try:
                entities = self.persistence.get_all_entities()
                relationships = self.persistence.get_all_relationships()
                await self.event_bus.publish(
                    events.TOPIC_PROJECT_OPENED,
                    events.create_project_opened_event(
                        project_path=str(source_path),
                        project_name=source_path.stem,
                        entity_count=len(entities),
                        relationship_count=len(relationships),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to emit project opened event: {e}")
            
        except Exception as e:
            logger.error(f"Error opening project: {e}")
            await self._push_log(f"Error opening project: {str(e)}", "error")
            # Try to reconnect on error
            try:
                import duckdb
                self.persistence.conn = duckdb.connect(self.persistence.db_path)
            except Exception:
                pass
    
    async def _update_service_connections(self) -> None:
        """Update database connections for all intelligence services after project change."""
        logger.info("Updating service database connections...")
        
        try:
            from forge.shared.core.service_registry import get_intelligence_services
            
            services = get_intelligence_services()
            
            for service_name, service in services.items():
                if hasattr(service, 'update_db_connection'):
                    service.update_db_connection(self.persistence.conn)
                    logger.info(f"Updated {service_name} database connection")
                    
        except Exception as e:
            logger.error(f"Error updating service connections: {e}")
    
    async def _check_and_migrate_project_config(self) -> None:
        """Check if project has configuration and migrate if needed."""
        logger.info("Checking project configuration...")
        
        # Check if project_config table exists and has data
        if not self.persistence.has_project_config():
            logger.info("Legacy project detected, performing automatic migration...")
            await self._push_log("Legacy project detected, migrating to v3.0 configuration system...", "info")
            
            try:
                # Import ConfigManager here to avoid circular imports
                from forge.shared.core.configuration import get_config_manager
                
                # Get default configuration
                config_manager = get_config_manager()
                default_config = config_manager.get_config().model_dump()
                
                # Save default configuration to project database
                success = self.persistence.save_project_config(default_config)
                
                if success:
                    logger.info("Project migration completed successfully")
                    await self._push_log("✓ Project migrated to v3.0 configuration standard", "success")
                else:
                    logger.warning("Project migration failed, continuing with defaults")
                    await self._push_log("⚠ Project migration failed, using system defaults", "warning")
                    
            except Exception as e:
                logger.error(f"Error during project migration: {e}")
                await self._push_log(f"Migration error: {str(e)}", "error")
        else:
            logger.info("Project configuration found, no migration needed")
    
    async def _migrate_schema(self, project_db_path: Path) -> None:
        """Check schema version and auto-migrate if needed.
        
        WARNING: Auto-migration during project load is DEPRECATED.
        Use scripts/migrate_database.py to migrate projects offline.
        This method now only checks schema version and warns if outdated.
        
        Migration strategy:
        - v1→v2: Add JSON columns for entity attributes and relationship metadata
        - Future versions: Add as needed with sequential migration scripts
        """
        TARGET_SCHEMA_VERSION = 2
        
        current_version = self.persistence.get_schema_version()
        
        if current_version >= TARGET_SCHEMA_VERSION:
            logger.info(f"Schema is current (v{current_version})")
            return
        
        # Schema is outdated - warn user but don't auto-migrate
        logger.warning(f"Database schema is outdated: v{current_version} (current: v{TARGET_SCHEMA_VERSION})")
        await self._push_log(
            f"⚠️ Database schema v{current_version} is outdated. Please run: python scripts/migrate_database.py",
            "warning"
        )
        
        # Don't auto-migrate - this prevents conflicts when forge is loading the database
        # User should close forge and run the migration script separately
    
    # DEPRECATED: Migration logic moved to scripts/migrate_database.py
    # This method is kept for reference but should not be called
    async def _migrate_v1_to_v2(self) -> None:
        """DEPRECATED: Use scripts/migrate_database.py instead.
        
        Migration logic has been moved to a standalone script to prevent
        conflicts when the database is being loaded by forge.
        """
        raise RuntimeError(
            "Auto-migration is deprecated. "
            "Please close forge and run: python scripts/migrate_database.py"
        )

    
    async def _create_temp_config(self, config_json_path: Path, project_dir: Path) -> None:
        """Create temporary config.json based on defaults.yaml with all .env overrides."""
        import yaml
        
        # Load defaults.yaml as base configuration
        project_root = Path(__file__).parent.parent.parent.parent
        defaults_path = project_root / "forge" / "config" / "settings" / "defaults.yaml"
        
        config = {}
        if defaults_path.exists():
            with open(defaults_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        
        # Set database path to point to intel.duckdb in project directory
        if "database" not in config:
            config["database"] = {}
        # Use standardized intel.duckdb filename for Sandbox compatibility
        project_db_path = project_dir / "intel.duckdb"
        try:
            if project_db_path.is_relative_to(project_root):
                config["database"]["db_path"] = str(project_db_path.relative_to(project_root))
            else:
                config["database"]["db_path"] = str(project_db_path)
        except (AttributeError, ValueError):
            # Python < 3.9 fallback or path not relative
            config["database"]["db_path"] = str(project_db_path)
        
        # Override with ALL .env variables from .env file
        if "llm" not in config:
            config["llm"] = {}
        
        # Override all LLM configuration from .env (except API keys which are handled separately)
        if os.getenv("DEFAULT_PROVIDER"):
            config["llm"]["default_provider"] = os.getenv("DEFAULT_PROVIDER")
        if os.getenv("SECONDARY_PROVIDER"):
            config["llm"]["secondary_provider"] = os.getenv("SECONDARY_PROVIDER")
        if os.getenv("SEMANTIC_PROVIDER"):
            config["llm"]["semantic_provider"] = os.getenv("SEMANTIC_PROVIDER")
        
        # API credentials - include all from .env
        if os.getenv("OPENROUTER_API_KEY"):
            config["llm"]["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
        if os.getenv("OPENROUTER_BASE_URL"):
            config["llm"]["openrouter_base_url"] = os.getenv("OPENROUTER_BASE_URL")
        if os.getenv("OPENROUTER_MODEL"):
            config["llm"]["openrouter_model"] = os.getenv("OPENROUTER_MODEL")
        
        if os.getenv("LM_PROXY_BASE_URL"):
            config["llm"]["lm_proxy_base_url"] = os.getenv("LM_PROXY_BASE_URL")
        if os.getenv("LM_PROXY_MODEL"):
            config["llm"]["lm_proxy_model"] = os.getenv("LM_PROXY_MODEL")
        if os.getenv("LM_PROXY_API_KEY"):
            config["llm"]["lm_proxy_api_key"] = os.getenv("LM_PROXY_API_KEY")
        
        if os.getenv("CHERRY_API_URL"):
            config["llm"]["cherry_api_url"] = os.getenv("CHERRY_API_URL")
        if os.getenv("CHERRY_API_KEY"):
            config["llm"]["cherry_api_key"] = os.getenv("CHERRY_API_KEY")
        if os.getenv("CHERRY_PROVIDER"):
            config["llm"]["cherry_provider"] = os.getenv("CHERRY_PROVIDER")
        if os.getenv("CHERRY_MODEL"):
            config["llm"]["cherry_model"] = os.getenv("CHERRY_MODEL")
        
        if os.getenv("LM_STUDIO_BASE_URL"):
            config["llm"]["lm_studio_base_url"] = os.getenv("LM_STUDIO_BASE_URL")
        if os.getenv("LM_STUDIO_MODEL"):
            config["llm"]["lm_studio_model"] = os.getenv("LM_STUDIO_MODEL")
        if os.getenv("LM_STUDIO_API_KEY"):
            config["llm"]["lm_studio_api_key"] = os.getenv("LM_STUDIO_API_KEY")
        
        # Override UI settings from .env
        if "ui" not in config:
            config["ui"] = {}
        if os.getenv("FLET_WEB_MODE"):
            flet_web_mode = os.getenv("FLET_WEB_MODE", "false").lower()
            config["ui"]["flet_web_mode"] = flet_web_mode in ("true", "1", "yes", "on")
        
        # Override embedding settings from .env
        if "embedding" not in config:
            config["embedding"] = {}
        if os.getenv("HF_HOME"):
            config["embedding"]["hf_home"] = os.getenv("HF_HOME")
        
        with open(config_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    async def _push_log(self, message: str, level: str = "info") -> None:
        """Helper method to publish log events via EventBus."""
        import time
        await self.event_bus.publish(
            "logs.event",
            {"message": message, "level": level, "ts": time.time()},
        )
    
    async def _clear_workspace(self) -> None:
        """Helper method to clear workspace by publishing an event."""
        await self.event_bus.publish("workspace.clear", {})
