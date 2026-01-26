"""Database manager for the Sandbox application - handles dual-database architecture.

This module provides SandboxDB class that manages:
1. Connection to world.duckdb (read/write) - sandbox-specific data  
2. Attachment of intel.duckdb (read-only) - raw extraction data
3. Sync logic to detect drift between databases
4. Schema creation for sandbox-specific tables
"""

import duckdb
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, TYPE_CHECKING, Union
import streamlit as st

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

@st.cache_resource
def get_db_connection(project_path: Union[str, Path]) -> 'SandboxDB':
    """Get a cached database connection for the project.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        SandboxDB: Connected database manager
    """
    db = SandboxDB(project_path)
    db.connect()
    return db


class SandboxDB:
    """Manages dual-DB setup with ATTACH for READ_ONLY raw data."""
    
    def __init__(self, project_path: Union[str, Path]):
        """Initialize SandboxDB with project path.
        
        Args:
            project_path: Path to the project directory (can be str or Path)
        """
        # Always resolve to forge/data/projects/{project_name}
        p = Path(project_path)
        if not str(p).replace('\\','/').startswith('forge/data/projects/'):
            p = Path('forge/data/projects') / p.name
        self.project_path = p
        self.world_path = self.project_path / "world.duckdb"
        self.raw_path = self.project_path / "intel.duckdb"
        self.world_conn: Optional['DuckDBPyConnection'] = None
        
    def connect(self):
        """Connect to world.duckdb and attach intel.duckdb as READ_ONLY."""
        # Ensure directory exists
        self.world_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Verify intel.duckdb exists
        if not self.raw_path.exists():
            raise FileNotFoundError(
                f"Raw extraction database not found: {self.raw_path}. "
                "Please run the Extractor first to create intel.duckdb."
            )
        
        # Connect to world database
        self.world_conn = duckdb.connect(str(self.world_path))
        
        # Attach raw database as READ_ONLY
        self.world_conn.execute(f"""
            ATTACH '{self.raw_path}' AS raw_db (READ_ONLY)
        """)
        
        # Create sandbox-specific tables if they don't exist
        self._create_sandbox_schema()
        
        return self
    
    def _create_sandbox_schema(self):
        """Create sandbox-specific tables in world.duckdb."""
        if not self.world_conn:
            return
        
        conn = self.world_conn
        
        # Active Agents Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_agents (
                agent_id VARCHAR PRIMARY KEY,
                persona_prompt TEXT NOT NULL,
                goals TEXT,
                capabilities TEXT,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Spatial Bookmarks Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spatial_bookmarks (
                location_id VARCHAR PRIMARY KEY,
                latitude DOUBLE,
                longitude DOUBLE,
                elevation DOUBLE,
                spatial_tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Narrative Context Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS narrative_context (
                context_id VARCHAR PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                mood TEXT,
                timeline TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Simulation Settings Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS simulation_settings (
                setting_id VARCHAR PRIMARY KEY DEFAULT 'global',
                parameters TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Sync Ledger Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_ledger (
                entity_hash VARCHAR PRIMARY KEY,
                entity_id VARCHAR NOT NULL,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted BOOLEAN DEFAULT TRUE,
                notes TEXT
            )
        """)
        
        conn.commit()
    
    def get_active_agents(self):
        """Get all active agents with their labels and types."""
        if not self.world_conn:
            return []
        return self.world_conn.execute("""
            SELECT aa.agent_id, e.label, e.type, aa.persona_prompt, aa.goals, aa.capabilities, aa.state
            FROM active_agents aa
            JOIN raw_db.entities e ON aa.agent_id = e.id
            ORDER BY e.label
        """).df()

    def get_agent_details(self, agent_id: str):
        """Get detailed information for a specific agent."""
        if not self.world_conn:
            return None
        return self.world_conn.execute("""
            SELECT persona_prompt, goals, capabilities, state
            FROM active_agents WHERE agent_id = ?
        """, [agent_id]).fetchone()

    def get_spatial_bookmarks(self):
        """Get all spatial bookmarks with labels."""
        if not self.world_conn:
            return []
        return self.world_conn.execute("""
            SELECT sb.location_id, e.label, sb.latitude, sb.longitude, sb.elevation, sb.spatial_tags
            FROM spatial_bookmarks sb
            JOIN raw_db.entities e ON sb.location_id = e.id
            ORDER BY e.label
        """).df()

    def get_narrative_contexts(self):
        """Get all narrative contexts."""
        if not self.world_conn:
            return []
        return self.world_conn.execute("""
            SELECT context_id, title, description, mood, timeline 
            FROM narrative_context
            ORDER BY title
        """).df()

    def get_raw_entity_count(self):
        """Get total count of entities in the raw database."""
        if not self.world_conn:
            return 0
        try:
            result = self.world_conn.execute("SELECT COUNT(*) FROM raw_db.entities").fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def get_promotable_entities(self):
        """Get entities from intel.duckdb that are not yet active agents."""
        if not self.world_conn:
            return []
        
        return self.world_conn.execute("""
            SELECT 
                r.id, r.type, r.label, r.attributes_json,
                CASE WHEN w.agent_id IS NOT NULL THEN TRUE ELSE FALSE END as is_active,
                w.persona_prompt, w.goals, w.capabilities, w.state
            FROM raw_db.entities r
            LEFT JOIN active_agents w ON r.id = w.agent_id
            WHERE r.type IN ('PERSON', 'ORGANIZATION', 'CHARACTER', 'ENTITY')
            ORDER BY r.type, r.label
        """).df()
    
    def get_entity_details(self, entity_id: str):
        """Get details for a specific entity from raw database."""
        if not self.world_conn:
            return None
        return self.world_conn.execute("""
            SELECT id, type, label, attributes_json
            FROM raw_db.entities WHERE id = ?
        """, [entity_id]).fetchone()

    def save_agent_persona(self, agent_id: str, persona_prompt: str, goals: str, capabilities: str, state: str = "{}"):
        """Save or update an agent persona."""
        if not self.world_conn:
            return
        
        self.world_conn.execute("""
            INSERT INTO active_agents (agent_id, persona_prompt, goals, capabilities, state, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (agent_id) DO UPDATE SET
                persona_prompt = excluded.persona_prompt,
                goals = excluded.goals,
                capabilities = excluded.capabilities,
                state = excluded.state,
                updated_at = excluded.updated_at
        """, [agent_id, persona_prompt, goals, capabilities, state])
        self.world_conn.commit()

    def delete_agent(self, agent_id: str):
        """Delete an agent from active_agents."""
        if not self.world_conn:
            return
        self.world_conn.execute("DELETE FROM active_agents WHERE agent_id = ?", [agent_id])
        self.world_conn.commit()

    def get_entities(self):
        """Get all entities from raw database."""
        if not self.world_conn:
            return []
        return self.world_conn.execute("""
            SELECT id, type, label, attributes_json, created_at 
            FROM raw_db.entities 
            ORDER BY type, label
        """).df()

    def get_relationships(self):
        """Get all relationships from raw database."""
        if not self.world_conn:
            return []
        return self.world_conn.execute("""
            SELECT id, source, target, type, confidence, doc_id, created_at
            FROM raw_db.relationships 
            ORDER BY confidence DESC
        """).df()

    def detect_drift(self):
        """Detect entities in intel.duckdb that have changed."""
        if not self.world_conn:
            return []
        
        # Get current entity hashes from sync_ledger
        ledger_query = """
            SELECT entity_id, entity_hash FROM sync_ledger WHERE accepted = TRUE
        """
        ledger_df = self.world_conn.execute(ledger_query).df()
        ledger_hashes = dict(zip(ledger_df['entity_id'], ledger_df['entity_hash']))
        
        # Calculate current hashes from raw_db
        entities_query = """
            SELECT id, type, label, attributes_json FROM raw_db.entities
        """
        entities_df = self.world_conn.execute(entities_query).df()
        
        drifted = []
        for _, row in entities_df.iterrows():
            entity_id = row['id']
            # Calculate hash of entity data
            entity_data = f"{row['type']}|{row['label']}|{row['attributes_json']}"
            current_hash = hashlib.sha256(entity_data.encode()).hexdigest()
            
            # Check if hash changed
            if entity_id in ledger_hashes:
                if ledger_hashes[entity_id] != current_hash:
                    drifted.append({
                        'entity_id': entity_id,
                        'type': row['type'],
                        'label': row['label'],
                        'old_hash': ledger_hashes[entity_id],
                        'new_hash': current_hash,
                        'status': 'changed'
                    })
            else:
                # New entity
                drifted.append({
                    'entity_id': entity_id,
                    'type': row['type'],
                    'label': row['label'],
                    'old_hash': None,
                    'new_hash': current_hash,
                    'status': 'new'
                })
        
        return drifted
    
    def update_sync_ledger(self, entity_id: str, accept: bool, notes: str = ""):
        """Update sync_ledger after user decision."""
        if not self.world_conn:
            return
        
        # Get current entity data
        entity_query = """
            SELECT type, label, attributes_json FROM raw_db.entities WHERE id = ?
        """
        result = self.world_conn.execute(entity_query, [entity_id]).fetchone()
        if not result:
            return
        
        entity_data = f"{result[0]}|{result[1]}|{result[2]}"
        entity_hash = hashlib.sha256(entity_data.encode()).hexdigest()
        
        # Upsert into sync_ledger
        self.world_conn.execute("""
            INSERT INTO sync_ledger (entity_hash, entity_id, last_seen, accepted, notes)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
            ON CONFLICT (entity_hash) DO UPDATE SET
                last_seen = excluded.last_seen,
                accepted = excluded.accepted,
                notes = excluded.notes
        """, [entity_hash, entity_id, accept, notes])
        
        self.world_conn.commit()
    
    def close(self):
        """Close database connections."""
        if self.world_conn:
            self.world_conn.close()


class ProjectManager:
    """Manages project discovery and validation for the Sandbox."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            # Default to forge/data/projects/ from project root
            project_root = Path(__file__).parent.parent.parent.parent
            self.data_dir = project_root / "forge" / "data" / "projects"
        else:
            self.data_dir = data_dir
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all available projects in the data directory."""
        if not self.data_dir.exists():
            return []
        
        projects = []
        for project_dir in self.data_dir.iterdir():
            if not project_dir.is_dir():
                continue
            
            project_info = self._validate_project(project_dir)
            if project_info['valid']:
                projects.append({
                    'name': project_dir.name,
                    'path': project_dir,
                    'info': project_info
                })
        
        return sorted(projects, key=lambda x: x['name'])
    
    def _validate_project(self, project_dir: Path) -> Dict[str, Any]:
        """Validate that a directory is a proper project with required files."""
        info = {
            'valid': False,
            'has_config': False,
            'has_intel_db': False,
            'has_world_db': False,
            'config_data': None,
            'entity_count': 0,
            'relationship_count': 0
        }
        
        # Check for config.json
        config_path = project_dir / "config.json"
        if config_path.exists():
            info['has_config'] = True
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    info['config_data'] = json.load(f)
            except Exception:
                pass
        
        # Check for intel.duckdb (required)
        intel_path = project_dir / "intel.duckdb"
        if intel_path.exists():
            info['has_intel_db'] = True
            
            # Try to get entity/relationship counts
            try:
                conn = duckdb.connect(str(intel_path), read_only=True)
                
                # Check if entities table exists
                try:
                    result = conn.execute("SELECT COUNT(*) FROM entities").fetchone()
                    info['entity_count'] = result[0] if result else 0
                except:
                    pass
                
                # Check if relationships table exists  
                try:
                    result = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()
                    info['relationship_count'] = result[0] if result else 0
                except:
                    pass
                
                conn.close()
            except Exception:
                pass
        
        # Check for world.duckdb (optional - will be created by Sandbox)
        world_path = project_dir / "world.duckdb"
        if world_path.exists():
            info['has_world_db'] = True
        
        # Project is valid if it has intel.duckdb
        info['valid'] = info['has_intel_db']
        
        return info


class SyncService:
    """Handles synchronization and drift detection between databases."""
    
    def __init__(self, sandbox_db: SandboxDB):
        self.db = sandbox_db
    
    def get_diff_view(self, entity_id: str) -> Dict[str, Any]:
        """Get side-by-side comparison of entity changes."""
        if not self.db.world_conn:
            return {}
        
        # Get current entity data from raw_db
        current_query = """
            SELECT type, label, attributes_json 
            FROM raw_db.entities 
            WHERE id = ?
        """
        current = self.db.world_conn.execute(current_query, [entity_id]).fetchone()
        
        if not current:
            return {'error': 'Entity not found in raw database'}
        
        # Get old hash from sync_ledger
        old_query = """
            SELECT entity_hash, notes 
            FROM sync_ledger 
            WHERE entity_id = ? AND accepted = TRUE
        """
        old = self.db.world_conn.execute(old_query, [entity_id]).fetchone()
        
        return {
            'entity_id': entity_id,
            'current': {
                'type': current[0],
                'label': current[1],
                'attributes': current[2]
            },
            'old_hash': old[0] if old else None,
            'old_notes': old[1] if old else None,
            'has_changes': old is not None
        }
    
    def accept_changes(self, entity_ids: List[str], notes: str = ""):
        """Accept changes for multiple entities."""
        for entity_id in entity_ids:
            self.db.update_sync_ledger(entity_id, accept=True, notes=notes)
    
    def reject_changes(self, entity_ids: List[str], notes: str = ""):
        """Reject changes for multiple entities."""
        for entity_id in entity_ids:
            self.db.update_sync_ledger(entity_id, accept=False, notes=notes)
