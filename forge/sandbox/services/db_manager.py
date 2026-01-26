# forge/sandbox/services/db_manager.py
import duckdb
from pathlib import Path
from typing import Optional, Union
import streamlit as st

class SandboxDB:
    def __init__(self, project_path: Union[str, Path]):
        # Always resolve to forge/data/projects/{project_name} if not already absolute
        p = Path(project_path)
        if not p.is_absolute() and not str(p).replace('\\','/').startswith('forge/data/projects/'):
            p = Path('forge/data/projects') / p.name
        self.project_path = p
        self.db_path = self.project_path / "world.duckdb"
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self):
        """Connect to the unified world.duckdb."""
        if not self.project_path.exists():
            self.project_path.mkdir(parents=True, exist_ok=True)
            
        self.conn = duckdb.connect(str(self.db_path))
        
        # Initialize schema
        self._init_schema()
        return self

    def _init_schema(self):
        """Create both extraction AND sandbox tables in the same DB."""
        if not self.conn:
            return
            
        # Extraction Tables (formerly in intel.duckdb)
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS rel_seq START 1;
            CREATE TABLE IF NOT EXISTS entities (
                id VARCHAR PRIMARY KEY,
                type VARCHAR,
                label VARCHAR,
                attributes_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY DEFAULT nextval('rel_seq'),
                source VARCHAR,
                target VARCHAR,
                type VARCHAR,
                confidence DOUBLE,
                doc_id VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Sandbox Tables
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS active_agents (
                agent_id VARCHAR PRIMARY KEY,
                persona_prompt TEXT NOT NULL,
                goals TEXT,
                capabilities TEXT,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS spatial_bookmarks (
                location_id VARCHAR PRIMARY KEY,
                latitude DOUBLE,
                longitude DOUBLE,
                elevation DOUBLE,
                spatial_tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS narrative_context (
                context_id VARCHAR PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                mood TEXT,
                timeline TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS simulation_settings (
                setting_id VARCHAR PRIMARY KEY DEFAULT 'global',
                parameters TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def get_entities(self):
        """Get all entities as a DataFrame."""
        import pandas as pd
        if not self.conn:
            return pd.DataFrame()
        return self.conn.execute("SELECT * FROM entities").df()
    
    def get_relationships(self):
        """Get all relationships as a DataFrame."""
        import pandas as pd
        if not self.conn:
            return pd.DataFrame()
        return self.conn.execute("SELECT * FROM relationships").df()
    
    def get_promotable_entities(self):
        """Get entities that can be promoted to active agents."""
        import pandas as pd
        if not self.conn:
            return pd.DataFrame()
        
        query = """
            SELECT e.*, 
                   CASE WHEN a.agent_id IS NOT NULL THEN true ELSE false END as is_active,
                   a.persona_prompt, a.goals, a.capabilities, a.state
            FROM entities e
            LEFT JOIN active_agents a ON e.id = a.agent_id
        """
        return self.conn.execute(query).df()
    
    def get_active_agents(self):
        """Get all active agents with entity details."""
        import pandas as pd
        if not self.conn:
            return pd.DataFrame()
        
        query = """
            SELECT e.id, e.type, e.label, a.agent_id, a.persona_prompt, a.goals, a.capabilities, a.state
            FROM active_agents a
            JOIN entities e ON a.agent_id = e.id
        """
        return self.conn.execute(query).df()
    
    def get_spatial_bookmarks(self):
        """Get all spatial bookmarks."""
        import pandas as pd
        if not self.conn:
            return pd.DataFrame()
        return self.conn.execute("SELECT * FROM spatial_bookmarks").df()
    
    def get_narrative_contexts(self):
        """Get all narrative contexts."""
        import pandas as pd
        if not self.conn:
            return pd.DataFrame()
        return self.conn.execute("SELECT * FROM narrative_context").df()
    
    def get_raw_entity_count(self):
        """Get total count of entities."""
        if not self.conn:
            return 0
        return self.conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    
    def get_entity_details(self, entity_id: str):
        """Get detailed entity information."""
        if not self.conn:
            return None
        result = self.conn.execute("SELECT * FROM entities WHERE id = ?", [entity_id]).fetchone()
        return result
    
    def save_agent_persona(self, agent_id: str, persona_prompt: str, goals: str, capabilities: str, state: str):
        """Save or update an agent persona."""
        if not self.conn:
            return
        
        self.conn.execute("""
            INSERT INTO active_agents (agent_id, persona_prompt, goals, capabilities, state, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (agent_id) 
            DO UPDATE SET 
                persona_prompt = EXCLUDED.persona_prompt,
                goals = EXCLUDED.goals,
                capabilities = EXCLUDED.capabilities,
                state = EXCLUDED.state,
                updated_at = CURRENT_TIMESTAMP
        """, [agent_id, persona_prompt, goals, capabilities, state])
        self.conn.commit()
    
    def delete_agent(self, agent_id: str):
        """Delete an active agent."""
        if not self.conn:
            return
        
        self.conn.execute("DELETE FROM active_agents WHERE agent_id = ?", [agent_id])
        self.conn.commit()
    
    def get_agent_details(self, agent_id: str):
        """Get agent persona details."""
        if not self.conn:
            return None
        
        result = self.conn.execute(
            "SELECT persona_prompt, goals, capabilities, state FROM active_agents WHERE agent_id = ?", 
            [agent_id]
        ).fetchone()
        return result

# Helper for Streamlit
@st.cache_resource
def get_db_connection(project_path: Path):
    db = SandboxDB(project_path)
    db.connect()
    return db
