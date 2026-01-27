"""DuckDB Persistence Service for PyScrAI Forge.

Stores entities and relationships for analytics and queries.

All autosave and event handlers use forge_data.duckdb (self.conn) for both writing and reading.
"""

import asyncio
import json
import logging
import duckdb
from pathlib import Path
from typing import List, Dict, Any, Optional
from forge.shared.core.event_bus import EventBus, EventPayload
from forge.shared.core import events

logger = logging.getLogger(__name__)

# Target schema version for new project databases
TARGET_SCHEMA_VERSION = 2


class DuckDBPersistenceService:
    """Manages persistent storage of entities and relationships using DuckDB.
    
    """
    def __init__(self, event_bus: EventBus, db_path: Optional[str] = None):
        self.event_bus = event_bus
        # If no db_path provided, create a temporary in-memory database
        # This will be replaced when a project is opened
        if db_path is None:
            # Use in-memory database as temporary placeholder
            self.db_path = ":memory:"
        else:
            self.db_path = db_path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
    
    async def start(self):
        """Initialize main database and subscribe to autosave events."""
        # Ensure directory exists
        db_path_obj = Path(self.db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        # Initialize main database connection (manual save/load and autosave)
        self.conn = duckdb.connect(self.db_path)
        self._create_schema()
        logger = __import__("logging").getLogger(__name__)
        logger.info(f"Database initialized: {self.db_path}")

        # Subscribe to entity extraction - AUTO-SAVE raw entities immediately
        await self.event_bus.subscribe(
            events.TOPIC_ENTITY_EXTRACTED,
            self.handle_entity_extracted
        )

        # Subscribe to graph updates - AUTO-SAVE to main database
        await self.event_bus.subscribe(
            events.TOPIC_GRAPH_UPDATED,
            self.handle_graph_updated
        )
        # Subscribe to workspace schema events - AUTO-SAVE to main database
        await self.event_bus.subscribe(
            events.TOPIC_WORKSPACE_SCHEMA,
            self.handle_workspace_schema
        )
        # Subscribe to semantic profile events - AUTO-SAVE to main database
        await self.event_bus.subscribe(
            events.TOPIC_SEMANTIC_PROFILE,
            self.handle_semantic_profile
        )
        # Subscribe to narrative events - AUTO-SAVE to main database
        await self.event_bus.subscribe(
            events.TOPIC_NARRATIVE_GENERATED,
            self.handle_narrative_generated
        )
    async def handle_entity_extracted(self, payload: EventPayload):
        """Persist extracted entities to main database immediately."""
        if not self.conn:
            return

        entities = payload.get("entities", [])
        if not entities:
            return

        import json

        # Use a transaction for batch insertion
        try:
            entity_ids_inserted = []

            for entity in entities:
                entity_type = entity.get("type", "UNKNOWN")
                label = entity.get("text", "Unknown")

                # Generate deterministic ID consistent with QdrantService
                entity_id = f"{entity_type}:{label}"

                attributes = entity.get("attributes", {})
                attributes_json = json.dumps(attributes) if attributes else "{}"

                # Check if entity already exists
                existing = self.conn.execute(
                    "SELECT id FROM entities WHERE id = ?", 
                    (entity_id,)
                ).fetchone()

                if existing:
                    self.conn.execute("""
                        UPDATE entities 
                        SET type = ?, label = ?, attributes_json = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (entity_type, label, attributes_json, entity_id))
                else:
                    self.conn.execute("""
                        INSERT INTO entities (id, type, label, attributes_json)
                        VALUES (?, ?, ?, ?)
                    """, (entity_id, entity_type, label, attributes_json))

                entity_ids_inserted.append(entity_id)

            self.conn.commit()
            logger.info(f"Persisted {len(entity_ids_inserted)} raw entities to database")

        except Exception as e:
            logger.error(f"Error persisting entities: {e}")
            if self.conn:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
    
    def _create_schema(self):
        """Create tables for entities and relationships in main database."""
        self._create_schema_in(self.conn)
    
    def _create_schema_in(self, conn: Optional[duckdb.DuckDBPyConnection]):
        """Create tables for entities and relationships in the specified connection."""
        if not conn:
            return
        
        try:
            # Create sequence for relationship IDs first
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS rel_seq START 1
            """)
            
            # Entities table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id VARCHAR PRIMARY KEY,
                    type VARCHAR NOT NULL,
                    label VARCHAR NOT NULL,
                    attributes_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
            # Relationships table
            # Note: DuckDB doesn't support ON DELETE CASCADE in FOREIGN KEY constraints
            # The deduplication service manually updates relationships before deleting entities
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY DEFAULT nextval('rel_seq'),
                    source VARCHAR NOT NULL,
                    target VARCHAR NOT NULL,
                    type VARCHAR NOT NULL,
                    confidence DOUBLE NOT NULL,
                    doc_id VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source) REFERENCES entities(id),
                    FOREIGN KEY (target) REFERENCES entities(id)
                )
            """)
            
            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target)
            """)
            
            # UI Artifacts table for storing workspace schemas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ui_artifacts (
                    id VARCHAR PRIMARY KEY,
                    schema TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ui_artifacts_created ON ui_artifacts(created_at)
            """)
            
            # Semantic Profiles table for storing entity profiles
            # Note: DuckDB doesn't support ON DELETE CASCADE in FOREIGN KEY constraints
            # The deduplication service should manually delete profiles when entities are deleted/merged
            conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_profiles (
                    entity_id VARCHAR PRIMARY KEY,
                    summary TEXT NOT NULL,
                    key_attributes TEXT,
                    related_entities TEXT,
                    significance_score DOUBLE,
                    profile_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_profiles_significance ON semantic_profiles(significance_score)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_profiles_entity ON semantic_profiles(entity_id)
            """)
            
            # Narratives table for storing document narratives
            conn.execute("""
                CREATE TABLE IF NOT EXISTS narratives (
                    doc_id VARCHAR PRIMARY KEY,
                    narrative TEXT NOT NULL,
                    entity_count INTEGER,
                    relationship_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_narratives_created ON narratives(created_at)
            """)
        
            # Project Configuration table for storing project-specific settings
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    config_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 2,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Ensure default row exists at current target version
            conn.execute(
                """
                INSERT INTO project_config (id, config_json, schema_version, updated_at)
                VALUES (1, '{}', ?, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET schema_version = excluded.schema_version
                """,
                [TARGET_SCHEMA_VERSION],
            )
            
            # Sequence for document_processing auto-incrementing id
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS doc_proc_seq START 1
            """)
            # Document Processing History table for tracking processed files
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_processing (
                    id INTEGER PRIMARY KEY DEFAULT nextval('doc_proc_seq'),
                    filename VARCHAR NOT NULL,
                    file_path VARCHAR,
                    doc_id VARCHAR NOT NULL,
                    status VARCHAR NOT NULL DEFAULT 'processing',
                    entity_count INTEGER DEFAULT 0,
                    relationship_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_processing_status ON document_processing(status)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_processing_started ON document_processing(started_at)
            """)
            
            conn.commit()
            logger = __import__("logging").getLogger(__name__)
            logger.info("Database schema created successfully")
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error(f"Error creating database schema: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
    
    async def handle_graph_updated(self, payload: EventPayload):
        """Persist graph updates to main database (auto-save during extraction)."""
        if not self.conn:
            return
        
        # Skip persistence if graph_stats is empty (e.g., during session restore)
        graph_stats = payload.get("graph_stats", {})
        if not graph_stats:
            return
        
        nodes = graph_stats.get("nodes", [])
        edges = graph_stats.get("edges", [])
        
        # Only persist if there are actual nodes/edges to save
        if not nodes and not edges:
            return
        
        # Upsert entities (insert if new, update if exists)
        entity_ids_inserted = []
        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("type")
            label = node.get("label")
            attributes = node.get("attributes", {})
            # Serialize attributes to JSON
            import json
            attributes_json = json.dumps(attributes) if attributes else "{}"
            if node_id and node_type and label:
                # Check if entity already exists
                result = self.conn.execute(
                    "SELECT id FROM entities WHERE id = ?",
                    (node_id,)
                ).fetchone()
                if result:
                    try:
                        self.conn.execute("""
                            UPDATE entities
                            SET type = ?, label = ?, attributes_json = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ? AND (type != ? OR label != ? OR attributes_json != ?)
                        """, (node_type, label, attributes_json, node_id, node_type, label, attributes_json))
                        logger.debug(f"Updated entity: id={node_id}, type={node_type}, label={label}")
                    except Exception as e:
                        logger.debug(f"Could not update entity {node_id}: {e}")
                else:
                    self.conn.execute("""
                        INSERT INTO entities (id, type, label, attributes_json)
                        VALUES (?, ?, ?, ?)
                    """, (node_id, node_type, label, attributes_json))
                    logger.debug(f"Inserted entity: id={node_id}, type={node_type}, label={label}")
                entity_ids_inserted.append(node_id)
        logger.debug(f"All entity IDs inserted/updated in this batch: {entity_ids_inserted}")
        
        # Insert relationships (validate entity references first)
        relationship_sources = []
        relationship_targets = []
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            rel_type = edge.get("type")
            confidence = edge.get("confidence", 1.0)
            doc_id = edge.get("doc_id")
            if source and target and rel_type:
                relationship_sources.append(source)
                relationship_targets.append(target)
                # Check if both source and target entities exist
                source_exists = self.conn.execute("""
                    SELECT 1 FROM entities WHERE id = ?
                """, (source,)).fetchone()
                target_exists = self.conn.execute("""
                    SELECT 1 FROM entities WHERE id = ?
                """, (target,)).fetchone()
                if not source_exists:
                    logger.warning(f"Skipping relationship: source entity '{source}' does not exist")
                    continue
                if not target_exists:
                    logger.warning(f"Skipping relationship: target entity '{target}' does not exist")
                    continue
                # Check if relationship already exists to avoid duplicates
                existing = self.conn.execute("""
                    SELECT id FROM relationships 
                    WHERE source = ? AND target = ? AND type = ? AND doc_id = ?
                """, (source, target, rel_type, doc_id)).fetchone()
                if not existing:
                    self.conn.execute("""
                        INSERT INTO relationships (source, target, type, confidence, doc_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (source, target, rel_type, confidence, doc_id))
        logger.debug(f"All relationship sources in this batch: {relationship_sources}")
        logger.debug(f"All relationship targets in this batch: {relationship_targets}")
        
        self.conn.commit()
        
        # Emit Logs event with persistence confirmation
        entity_count = self.get_entity_count()
        relationship_count = self.get_relationship_count()
        await self.event_bus.publish(
            events.TOPIC_LOGS_EVENT,
            events.create_logs_event(
                f"✅ Persisted {len(nodes)} entities, {len(edges)} relationships | "
                f"Total: {entity_count} entities, {relationship_count} relationships",
                level="success"
            )
        )
    
    async def handle_workspace_schema(self, payload: EventPayload):
        """Persist workspace schema (UI artifact) to main database (auto-save)."""
        schema = payload.get("schema")
        if not schema or not self.conn:
            return
        # Generate a unique ID for this schema artifact
        # Use a hash of the schema content or timestamp-based ID
        import hashlib
        schema_json = json.dumps(schema, sort_keys=True)
        artifact_id = hashlib.md5(schema_json.encode()).hexdigest()
        # Check if this artifact already exists
        result = self.conn.execute(
            "SELECT id FROM ui_artifacts WHERE id = ?",
            (artifact_id,)
        ).fetchone()
        if not result:
            # Insert new artifact to main database
            self.conn.execute("""
                INSERT INTO ui_artifacts (id, schema)
                VALUES (?, ?)
            """, (artifact_id, schema_json))
            self.conn.commit()
    
    def store_ui_artifact(self, schema: Dict[str, Any]) -> None:
        """Manually store a UI artifact schema."""
        if not schema or not self.conn:
            return
        
        import hashlib
        schema_json = json.dumps(schema, sort_keys=True)
        artifact_id = hashlib.md5(schema_json.encode()).hexdigest()
        
        # Check if this artifact already exists
        result = self.conn.execute(
            "SELECT id FROM ui_artifacts WHERE id = ?",
            (artifact_id,)
        ).fetchone()
        
        if not result:
            self.conn.execute("""
                INSERT INTO ui_artifacts (id, schema)
                VALUES (?, ?)
            """, (artifact_id, schema_json))
            self.conn.commit()
    
    def get_stored_ui_artifacts(self) -> List[Dict[str, Any]]:
        """Retrieve all stored UI artifacts."""
        if not self.conn:
            return []
        
        result = self.conn.execute("""
            SELECT id, schema, created_at
            FROM ui_artifacts
            ORDER BY created_at ASC
        """).fetchall()
        
        artifacts = []
        for row in result:
            try:
                schema_dict = json.loads(row[1])
                artifacts.append(schema_dict)
            except json.JSONDecodeError:
                # Skip malformed JSON
                continue
        
        return artifacts
    
    async def handle_semantic_profile(self, payload: EventPayload):
        """Persist semantic profile to main database (auto-save)."""
        if not self.conn:
            return
        
        entity_id = payload.get("entity_id")
        profile = payload.get("profile")
        
        if not entity_id or not profile:
            return
        
        try:
            # Serialize profile to JSON
            profile_json = json.dumps(profile, sort_keys=True)
            
            # Extract key fields from profile for structured storage
            summary = profile.get("summary", "")
            key_attributes = json.dumps(profile.get("key_attributes", []))
            related_entities = json.dumps(profile.get("related_entities", []))
            significance_score = profile.get("significance_score", 0.0)
            
            # Upsert profile (insert if new, update if exists)
            # Check if profile exists
            existing = self.conn.execute(
                "SELECT entity_id FROM semantic_profiles WHERE entity_id = ?",
                (entity_id,)
            ).fetchone()
            
            if existing:
                # Update existing profile
                self.conn.execute("""
                    UPDATE semantic_profiles SET
                        summary = ?,
                        key_attributes = ?,
                        related_entities = ?,
                        significance_score = ?,
                        profile_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE entity_id = ?
                """, (summary, key_attributes, related_entities, significance_score, profile_json, entity_id))
            else:
                # Insert new profile
                self.conn.execute("""
                    INSERT INTO semantic_profiles 
                        (entity_id, summary, key_attributes, related_entities, significance_score, profile_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (entity_id, summary, key_attributes, related_entities, significance_score, profile_json))
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error persisting semantic profile for {entity_id}: {e}")
            if self.conn:
                self.conn.rollback()
    
    async def handle_narrative_generated(self, payload: EventPayload):
        """Persist narrative to main database (auto-save)."""
        if not self.conn:
            return
        
        doc_id = payload.get("doc_id")
        narrative = payload.get("narrative")
        entity_count = payload.get("entity_count", 0)
        relationship_count = payload.get("relationship_count", 0)
        
        if not doc_id or not narrative:
            return
        
        try:
            # Upsert narrative (insert if new, update if exists)
            # Check if narrative exists
            existing = self.conn.execute(
                "SELECT doc_id FROM narratives WHERE doc_id = ?",
                (doc_id,)
            ).fetchone()

            if existing:
                # Update existing narrative
                self.conn.execute("""
                    UPDATE narratives SET
                        narrative = ?,
                        entity_count = ?,
                        relationship_count = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE doc_id = ?
                """, (narrative, entity_count, relationship_count, doc_id))
            else:
                # Insert new narrative
                self.conn.execute("""
                    INSERT INTO narratives 
                        (doc_id, narrative, entity_count, relationship_count)
                    VALUES (?, ?, ?, ?)
                """, (doc_id, narrative, entity_count, relationship_count))

            # --- Ensure document_processing status is set to completed if still processing ---
            self.conn.execute(
                """
                UPDATE document_processing
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE doc_id = ? AND status = 'processing'
                """,
                (doc_id,)
            )

            self.conn.commit()

        except Exception as e:
            logger.error(f"Error persisting narrative for {doc_id}: {e}")
            if self.conn:
                self.conn.rollback()
    
    def get_semantic_profile(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a semantic profile for an entity."""
        if not self.conn:
            return None
        
        try:
            result = self.conn.execute("""
                SELECT profile_json
                FROM semantic_profiles
                WHERE entity_id = ?
            """, (entity_id,)).fetchone()
            
            if result:
                return json.loads(result[0])
        except Exception as e:
            logger.error(f"Error retrieving semantic profile for {entity_id}: {e}")
        
        return None
    
    def get_all_semantic_profiles(self) -> List[Dict[str, Any]]:
        """Retrieve all semantic profiles."""
        if not self.conn:
            return []
        
        profiles = []
        try:
            results = self.conn.execute("""
                SELECT entity_id, profile_json
                FROM semantic_profiles
                ORDER BY significance_score DESC
            """).fetchall()
            
            for row in results:
                try:
                    profile = json.loads(row[1])
                    profile["entity_id"] = row[0]  # Add entity_id to profile
                    profiles.append(profile)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.error(f"Error retrieving semantic profiles: {e}")
        
        return profiles
    
    def get_narrative(self, doc_id: str) -> Optional[str]:
        """Retrieve a narrative for a document."""
        if not self.conn:
            return None
        
        try:
            result = self.conn.execute("""
                SELECT narrative
                FROM narratives
                WHERE doc_id = ?
            """, (doc_id,)).fetchone()
            
            if result:
                return result[0]
        except Exception as e:
            logger.error(f"Error retrieving narrative for {doc_id}: {e}")
        
        return None
    
    def get_all_narratives(self) -> List[Dict[str, Any]]:
        """Retrieve all narratives."""
        if not self.conn:
            return []
        
        narratives = []
        try:
            results = self.conn.execute("""
                SELECT doc_id, narrative, entity_count, relationship_count, created_at
                FROM narratives
                ORDER BY created_at DESC
            """).fetchall()
            
            for row in results:
                narratives.append({
                    "doc_id": row[0],
                    "narrative": row[1],
                    "entity_count": row[2],
                    "relationship_count": row[3],
                    "created_at": row[4],
                })
        except Exception as e:
            logger.error(f"Error retrieving narratives: {e}")
        
        return narratives
    
    def get_entity_count(self) -> int:
        """Get total number of entities in the database."""
        if not self.conn:
            return 0
        result = self.conn.execute("SELECT COUNT(*) FROM entities").fetchone()
        return result[0] if result else 0
    
    def get_relationship_count(self) -> int:
        """Get total number of relationships in the database."""
        if not self.conn:
            return 0
        result = self.conn.execute("SELECT COUNT(*) FROM relationships").fetchone()
        return result[0] if result else 0
    
    def get_all_entities(self) -> List[Dict[str, Any]]:
        """Retrieve all entities."""
        if not self.conn:
            return []
        result = self.conn.execute("""
            SELECT id, type, label, created_at, updated_at
            FROM entities
            ORDER BY created_at DESC
        """).fetchall()
        
        return [
            {
                "id": row[0],
                "type": row[1],
                "label": row[2],
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in result
        ]
    
    def get_all_relationships(self) -> List[Dict[str, Any]]:
        """Retrieve all relationships."""
        if not self.conn:
            return []
        result = self.conn.execute("""
            SELECT id, source, target, type, confidence, doc_id, created_at
            FROM relationships
            ORDER BY created_at DESC
        """).fetchall()
        
        return [
            {
                "id": row[0],
                "source": row[1],
                "target": row[2],
                "type": row[3],
                "confidence": row[4],
                "doc_id": row[5],
                "created_at": row[6],
            }
            for row in result
        ]
    
    def clear_all_data(self):
        """Clear all entities and relationships from the database."""
        if not self.conn:
            return
        
        logger = __import__("logging").getLogger(__name__)
        try:
            # Delete in order to respect foreign key constraints:
            # 1. Delete semantic_profiles first (has foreign key to entities)
            self.conn.execute("DELETE FROM semantic_profiles")
            # 2. Delete narratives (no foreign keys, but clear it)
            self.conn.execute("DELETE FROM narratives")
            # 3. Delete relationships (has foreign keys to entities)
            self.conn.execute("DELETE FROM relationships")
            # 4. Delete entities (now safe since nothing references them)
            self.conn.execute("DELETE FROM entities")
            # 5. Delete UI artifacts (no foreign keys)
            self.conn.execute("DELETE FROM ui_artifacts")
            # Note: DuckDB doesn't support ALTER SEQUENCE RESTART yet
            # The sequence will continue from its current value, which is fine
            # for our use case since we're using it for relationship IDs
            self.conn.commit()
            
            # CRITICAL: Force a checkpoint to ensure WAL is flushed to main database file
            # This prevents the cleared state from being lost if the connection closes unexpectedly
            try:
                self.conn.execute("CHECKPOINT")
                logger.info("Database checkpoint completed after clearing data")
            except Exception as e:
                logger.warning(f"Could not checkpoint database after clearing: {e}")
            
            logger.info("Database cleared: all entities, relationships, profiles, narratives, and UI artifacts removed")
        except Exception as e:
            logger.error(f"Error clearing database: {e}")
            # DuckDB doesn't require explicit rollback for most operations
            # Only rollback if there's an active transaction
            try:
                self.conn.rollback()
            except Exception:
                # If rollback fails, just continue - the transaction may not be active
                pass
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def save_project_config(self, config_dict: Dict[str, Any]) -> bool:
        """Save project configuration to database."""
        if not self.conn:
            return False
        
        logger = __import__("logging").getLogger(__name__)
        try:
            config_json = json.dumps(config_dict, indent=2)
            
            # Use UPSERT pattern for DuckDB
            self.conn.execute("""
                INSERT INTO project_config (id, config_json, schema_version, updated_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    config_json = excluded.config_json,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at
            """, [config_json, TARGET_SCHEMA_VERSION])
            
            self.conn.commit()
            logger.info("Project configuration saved to database")
            return True
            
        except Exception as e:
            logger.error(f"Error saving project configuration: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return False
    
    def load_project_config(self) -> Optional[Dict[str, Any]]:
        """Load project configuration from database."""
        if not self.conn:
            return None
        
        logger = __import__("logging").getLogger(__name__)
        try:
            result = self.conn.execute("SELECT config_json FROM project_config WHERE id = 1").fetchone()
            
            if result:
                config_json = result[0]
                return json.loads(config_json)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error loading project configuration: {e}")
            return None
    
    def has_project_config(self) -> bool:
        """Check if project configuration exists in database."""
        if not self.conn:
            return False
        
        try:
            result = self.conn.execute("SELECT COUNT(*) FROM project_config WHERE id = 1").fetchone()
            return result[0] > 0 if result else False
        except Exception as e:
            return False
    
    def get_schema_version(self) -> int:
        """Get current schema version from database."""
        if not self.conn:
            return TARGET_SCHEMA_VERSION  # Default to current target if no connection
        
        logger = __import__("logging").getLogger(__name__)
        try:
            result = self.conn.execute("SELECT schema_version FROM project_config WHERE id = 1").fetchone()
            if result:
                return result[0]
            else:
                return TARGET_SCHEMA_VERSION  # Default version if no config exists
        except Exception as e:
            logger.warning(f"Error getting schema version, defaulting to {TARGET_SCHEMA_VERSION}: {e}")
            return TARGET_SCHEMA_VERSION
    
    def set_schema_version(self, version: int) -> bool:
        """Set schema version in database."""
        if not self.conn:
            return False
        
        logger = __import__("logging").getLogger(__name__)
        try:
            # If project_config exists, update it; otherwise insert default
            if self.has_project_config():
                self.conn.execute("""
                    UPDATE project_config 
                    SET schema_version = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = 1
                """, [version])
            else:
                # Insert minimal config with version
                self.conn.execute("""
                    INSERT INTO project_config (id, config_json, schema_version, updated_at)
                    VALUES (1, '{}', ?, CURRENT_TIMESTAMP)
                """, [version])
            
            self.conn.commit()
            logger.info(f"Schema version updated to {version}")
            return True
        except Exception as e:
            logger.error(f"Error setting schema version: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return False
