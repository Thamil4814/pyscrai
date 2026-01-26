# PyScrAI Forge: Sandbox Implementation Blueprint

**Version:** 2.2  
**Date:** January 24, 2026  
**Status:** Approved for Development  
**Reference:** Triad Architecture & World Builder Blueprint (v3.0)

---

## 1. Executive Summary & Clarifications

This blueprint documents the **confirmed implementation specifications** for the PyScrAI Forge Sandbox, a Streamlit-based application for "Refining" extracted intelligence into simulated worlds.

### 1.1 Key Clarifications from Architecture Review

Based on the Triad Architecture (v3.0) and workspace analysis, the following critical implementation details are confirmed:

| Requirement | Confirmed Specification | Rationale |
|-------------|------------------------|-----------|
| **Database Strategy** | Modify Flet Extractor to create `intel.duckdb` instead of `forge_data.duckdb` | The Sandbox requires a predictable, hardcoded filename (`intel.duckdb`) for READ_ONLY attachment. The blueprint explicitly states: "Refactor Flet Launcher ProjectController to use new directory/filename standard." |
| **Project Directory Structure** | Standardize to `data/projects/{Project Name}/` with: <br>• `config.json` <br>• `intel.duckdb` (Launcher) <br>• `world.duckdb` (Sandbox) <br>• `templates/` (Optional) | Creates clear separation of concerns. Launcher manages extraction. Sandbox manages enrichment. |
| **Shared Kernel** | Reuse `forge/shared` for Domain/Core logic. Create `forge/sandbox/services/` for App-specific logic. | Avoids duplication. Domain entities, graph logic, and LLM services are shared. Sandbox-specific sync logic is isolated. |
| **Streamlit Dependencies** | Add to `setup.py`: <br>• `streamlit>=1.35.0` <br>• `streamlit-agraph` <br>• `leafmap` <br>• `jinja2` <br>• `watchdog` | `leafmap` provides Spatial Domain with map overlay. `streamlit-agraph` for knowledge graphs. `watchdog` for auto-reload during dev. |
| **Session Management** | Create `Session` class wrapper around `st.session_state`. | Provides type safety and centralized initialization for complex sandbox state (connections, project path, preferences). |
| **Export Format** | **Zip Archive** containing: <br>• `intel.duckdb` <br>• `world.duckdb` <br>• `manifest.json` <br>• `templates/` | Portable format. Manifest includes timestamp, version, author. Unzip on another machine to run simulation immediately. |

### 1.2 Implementation Scope

This blueprint covers **Phase 1: Foundation & Environment** through **Phase 4: Playground & Export** as specified in the Vision document.

---

## 2. Architecture & Data Flow

### 2.1 Project Directory Structure (Final)

```
data/
└── projects/
    └── {Project Name}/
        ├── config.json                  # Project configuration (Launcher)
        ├── intel.duckdb                 # Raw extracted data (Launcher: RW, Sandbox: RO)
        ├── world.duckdb                 # Semantic overlay + simulation state (Sandbox: RW)
        └── templates/                   # Project-specific Jinja templates (Sandbox)
```

### 2.2 Dual-DB Data Strategy (Updated)

**File A: `intel.duckdb`**  
- **Owner:** Flet Extractor (Read/Write)  
- **Content:** Extracted Entities, Relationships, Raw Text, Source Metadata  
- **Schema:** `entities`, `relationships`, `ui_artifacts`, `semantic_profiles`, `narratives`, `project_config`, `document_processing`  
- **Note:** Modified from `forge_data.duckdb` to `intel.duckdb` per blueprint specification.

**File B: `world.duckdb`**  
- **Owner:** Sandbox (Read/Write)  
- **Content:** Agent Personas, Spatial Coordinates, Narrative State, Simulation Settings  
- **Schema (New):**
  ```sql
  CREATE TABLE active_agents (
      agent_id VARCHAR PRIMARY KEY,           -- Links to intel.duckdb entity ID
      persona_prompt TEXT NOT NULL,           -- LLM system prompt
      goals TEXT,                             -- Agent objectives (JSON)
      capabilities TEXT,                      -- Agent abilities (JSON)
      state TEXT,                             -- Current state (JSON)
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (agent_id) REFERENCES raw_db.entities(id)
  );

  CREATE TABLE spatial_bookmarks (
      location_id VARCHAR PRIMARY KEY,        -- Links to intel.duckdb entity ID
      latitude DOUBLE,
      longitude DOUBLE,
      elevation DOUBLE,
      spatial_tags TEXT,                      -- Environmental descriptors (JSON)
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (location_id) REFERENCES raw_db.entities(id)
  );

  CREATE TABLE narrative_context (
      context_id VARCHAR PRIMARY KEY,
      title TEXT NOT NULL,
      description TEXT,
      mood TEXT,                              -- Narrative tone
      timeline TEXT,                          -- Temporal context
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE simulation_settings (
      setting_id VARCHAR PRIMARY KEY DEFAULT 'global',
      parameters TEXT NOT NULL,               -- JSON: speed, complexity, randomness
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE sync_ledger (
      entity_hash VARCHAR PRIMARY KEY,        -- Hash of entity data from intel.duckdb
      entity_id VARCHAR NOT NULL,             -- The entity ID from intel.duckdb
      last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      accepted BOOLEAN DEFAULT TRUE,          -- Has user accepted this update?
      notes TEXT                              -- User notes on this sync
  );
  ```

### 2.3 Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     PyScrAI Forge Monorepo                        │
│                    Single .venv Environment                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              forge/shared/ (Shared Kernel)               │    │
│  │  ┌───────────────────────────────────────────────────┐  │    │
│  │  │  Domain Layer: Entities, Graph, LLM Services     │  │    │
│  │  │  (Shared by both Extractor and Sandbox)          │  │    │
│  │  └───────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                    │
│         ┌────────────────────┼────────────────────┐              │
│         │                    │                    │              │
│  ┌──────▼──────┐     ┌─────▼──────┐     ┌───────▼──────┐        │
│  │   Flet      │     │ Filesystem  │     │  Streamlit   │        │
│  │  Extractor  │◄────┤  (Ledger)   │────►│   Sandbox    │        │
│  │  (Mining)   │     │             │     │  (Refining)  │        │
│  └─────────────┘     └─────────────┘     └──────────────┘        │
│         │                    │                    │              │
│  ┌──────▼──────┐     ┌─────▼──────┐     ┌───────▼──────┐        │
│  │ forge/      │     │ data/      │     │ forge/       │        │
│  │ extractor/  │     │ projects/  │     │ sandbox/     │        │
│  │ main.py     │     │ {name}/    │     │ app.py       │        │
│  └─────────────┘     │   │        │     └──────────────┘        │
│                      │   │ intel.duckdb  (RW)  │                │
│                      │   └──────────────┘      │                │
│                      │            └─────────────┘                │
│                      │            world.duckdb (RW)              │
│                      └───────────────────────────────────────────┘
│
└─────────────────────────────────────────────────────────────────┘
```

### 2.4 Workflow & Logic

#### 2.4.1 "Mining" Workflow (Extractor - Updated)

**Modified Task: Change database filename from `forge_data.duckdb` to `intel.duckdb`**

**Flow:**
1. User opens Flet Extractor
2. **Create Project:** User supplies Project Name → System creates `data/projects/{Project Name}/`
3. **Initialize:** System creates `config.json` and **`intel.duckdb`** (not `forge_data.duckdb`)
4. **Open Project:** User browses `data/projects/` → Selects folder
5. **Validation:** Extractor checks for `config.json` and **`intel.duckdb`**
6. **Ingest:** Load documents → Run Extraction Service → Update `intel.duckdb`
7. **Save:** Database saved in project directory as **`intel.duckdb`**

#### 2.4.2 "World Building" Workflow (Sandbox)

**Flow:**
1. User runs: `streamlit run forge/sandbox/app.py`
2. **Select Project:** User browses `data/projects/` → Selects folder
3. **Initialization:**
   - Connect to `world.duckdb` (creates if missing)
   - Attach `intel.duckdb` as `raw_db` (READ_ONLY mode)
4. **Drift Detection (Sync Logic):**
   - Sandbox compares current hash/timestamp of entities in `raw_db` against `sync_ledger`
   - If drift detected: Triggers "Merge/Verify" Wizard
   - Example: "Entity 'Dr. Smith' has new info. Update Persona Context?"
5. **Configuration:** User adds spatial tags, defines agent goals, edits Jinja templates
6. **Save:** Writes to `world.duckdb`

---

## 3. Implementation Plan

### Phase 1: Foundation & Environment (Week 1)

**Goal:** Establish the Sandbox folder structure and unifying dependencies.

**Tasks:**

1. **Update `setup.py` - Add Streamlit Dependencies**
   ```python
   # In install_requires list:
   "streamlit>=1.35.0",       # Core UI framework
   "streamlit-agraph",        # Knowledge Graph visualization
   "leafmap",                 # Spatial Domain / Map overlay
   "jinja2",                  # Narrative template rendering
   "watchdog",                # Auto-reload during development
   ```

2. **Create Sandbox Directory Structure**
   ```
   forge/sandbox/
   ├── __init__.py
   ├── app.py                    # Entry point: streamlit run forge/sandbox/app.py
   ├── session.py                # Session state wrapper class
   ├── services/
   │   ├── __init__.py
   │   ├── db_manager.py         # Dual-DB ATTACH logic & sync service
   │   ├── project_manager.py    # Project discovery and validation
   │   └── export_service.py     # Zip archive generation
   ├── components/
   │   ├── __init__.py
   │   ├── project_selector.py
   │   └── drift_wizard.py
   └── pages/
       ├── __init__.py
       ├── 1_World_Manifest.py   # Factions, Polities, Global Settings
       ├── 2_Agent_Forge.py      # Entity Promotion & Persona Injection
       ├── 3_Spatial_Domain.py   # Location Management / Map Overlay
       ├── 4_Event_Chronology.py # Advanced Event Editing / Narrative
       ├── 5_Simulation_Lab.py   # Interactive Component Testing
       └── 6_Prefab_Factory.py   # Modular Template/Project Management
   ```

3. **Modify Extractor: Change Database Filename**
   - Locate where `DuckDBPersistenceService` is initialized
   - Change database filename from `forge_data.duckdb` to `intel.duckdb`
   - Update `ProjectController` to enforce new directory standard
   - Update validation logic to check for `intel.duckdb` instead of `forge_data.duckdb`

4. **Create Initial Sandbox Files**
   - `forge/sandbox/app.py`: Main Streamlit app with project selector
   - `forge/sandbox/session.py`: Session state wrapper class
   - `forge/sandbox/services/db_manager.py`: Database connection manager

### Phase 2: The "World Creator" UI (Week 2)

**Goal:** Build the interface to visualize Raw Data and create Enriched Data.

**Scope:**

1. **Page 1: World Manifest**
   - Display `intel.duckdb` entities grouped by type
   - Create/Manage global factions and polities
   - Configure project-wide settings (stored in `world.duckdb`)

2. **Page 2: Agent Forge**
   - List promotable entities from `intel.duckdb` (LEFT JOIN with `world.duckdb.active_agents`)
   - Persona Editor: Write System Prompts for actors
   - Goals/Capabilities editor (JSON inputs with validation)
   - Toggle entity activation (active ↔ dormant)

3. **Page 3: Spatial Domain**
   - **Map Component:** Integration of `leafmap` for map overlay
   - Location Management: Assign coordinates to `intel.duckdb` Location entities
   - Spatial Tags: Environmental descriptors for simulation context
   - Save to `world.duckdb.spatial_bookmarks`

4. **Page 4: Event Chronology**
   - Advanced event editor
   - Timeline visualization
   - Narrative context linking
   - Save to `world.duckdb.narrative_context`

5. **Page 5: Simulation Lab**
   - Interactive component testing
   - Text editor with "Render Preview" button
   - Test run individual/multiple components
   - Human interaction mode (singular entity or group)
   - Optional simulation mechanics toggle

6. **Page 6: Prefab Factory**
   - Modular template/project management
   - Sidebar for cross-editor/page utilization
   - Template import/export
   - Store in `world.duckdb` or `templates/` directory

### Phase 3: The Sync Engine (Week 3)

**Goal:** Handle the "Re-Ingestion" scenario.

**Tasks:**

1. **Implement SyncService in `forge/sandbox/services/db_manager.py`**
   ```python
   class SyncService:
       def __init__(self, world_conn, raw_conn):
           self.world = world_conn
           self.raw = raw_conn
       
       def detect_drift(self):
           # Compare entity hashes from raw_db vs sync_ledger
           # Returns: List of entities with changes
       
       def show_diff_view(self, entity_id):
           # Side-by-side comparison of old vs new entity data
           # Returns: HTML/Markdown diff
       
       def apply_update(self, entity_id, accept_changes):
           # Update sync_ledger and optionally world.duckdb
   ```

2. **Build "Diff View" Component**
   - Side-by-side comparison: Old vs New entity data
   - Visual highlighting of changed fields
   - Accept/Reject buttons per entity or batch
   - Show in `components/drift_wizard.py`

3. **Create sync_ledger Table Logic**
   - Table schema as specified in Section 2.2
   - Hash calculation: Use SHA256 of entity data (name + type + attributes)
   - Store timestamps for change tracking

4. **Integration with Session State**
   - Store sync status in `st.session_state`
   - Auto-check for drift on project load
   - Prompt user if drift detected

### Phase 4: Playground & Export (Week 4)

**Goal:** Templating and Simulation Handoff.

**Tasks:**

1. **Playground: Template Renderer**
   - Text editor with syntax highlighting
   - Live preview of Jinja2 template rendering
   - Variable injection from `world.duckdb` (agents, locations, narrative)
   - Test run individual components or multiple components

2. **Export Service**
   - **Zip Archive Format:**
     ```
     {Project Name}_Simulation_Package_{timestamp}.zip
     ├── intel.duckdb          # Raw extraction snapshot
     ├── world.duckdb          # Simulation parameters
     ├── manifest.json         # Metadata
     │   ├── timestamp
     │   ├── version
     │   ├── author
     │   └── project_name
     └── templates/            # Project-specific templates
     ```
   - **Implementation:**
     ```python
     class ExportService:
         def create_package(self, project_path, output_path):
             # 1. Copy intel.duckdb
             # 2. Copy world.duckdb
             # 3. Create manifest.json
             # 4. Copy templates/ if exists
             # 5. Zip everything
             # 6. Return path to archive
     ```

3. **Simulation Handoff**
   - "Export Simulation Package" button in Page 5 (Simulation Lab)
   - Package can be imported into another Sandbox instance
   - Manifest validation on import
   - Database integrity check

---

## 4. Technical Specifications

### 4.1 `forge/sandbox/services/db_manager.py`

```python
import duckdb
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import streamlit as st

class SandboxDB:
    """Manages dual-DB setup with ATTACH for READ_ONLY raw data."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.world_path = self.project_path / "world.duckdb"
        self.raw_path = self.project_path / "intel.duckdb"
        self.world_conn = None
        self.raw_conn = None
        
    def connect(self):
        """Connect to world.duckdb and attach intel.duckdb as READ_ONLY."""
        # Ensure directory exists
        self.world_path.parent.mkdir(parents=True, exist_ok=True)
        
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES raw_db.entities(id)
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES raw_db.entities(id)
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
    
    def get_promotable_entities(self):
        """Get entities from intel.duckdb that are not yet active agents."""
        if not self.world_conn:
            return []
        
        return self.world_conn.execute("""
            SELECT 
                r.id, r.type, r.label, r.attributes_json,
                CASE WHEN w.agent_id IS NOT NULL THEN TRUE ELSE FALSE END as is_active
            FROM raw_db.entities r
            LEFT JOIN active_agents w ON r.id = w.agent_id
            ORDER BY r.type, r.label
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
        if self.raw_conn:
            self.raw_conn.close()
```

### 4.2 `forge/sandbox/session.py`

```python
import streamlit as st
from typing import Optional, Dict, Any
from pathlib import Path

class Session:
    """Wrapper around st.session_state for type safety and centralized management."""
    
    @property
    def project_path(self) -> Optional[Path]:
        """Get current project path."""
        path_str = st.session_state.get('project_path')
        return Path(path_str) if path_str else None
    
    @project_path.setter
    def project_path(self, value: Optional[Path]):
        """Set current project path."""
        st.session_state['project_path'] = str(value) if value else None
    
    @property
    def db(self):
        """Get sandbox database connection."""
        return st.session_state.get('db')
    
    @db.setter
    def db(self, value):
        """Set sandbox database connection."""
        st.session_state['db'] = value
    
    @property
    def sync_status(self) -> Dict[str, Any]:
        """Get sync status."""
        return st.session_state.get('sync_status', {'drift_detected': False, 'entities': []})
    
    @sync_status.setter
    def sync_status(self, value: Dict[str, Any]):
        """Set sync status."""
        st.session_state['sync_status'] = value
    
    @property
    def user_preferences(self) -> Dict[str, Any]:
        """Get user preferences."""
        return st.session_state.get('user_preferences', {})
    
    @user_preferences.setter
    def user_preferences(self, value: Dict[str, Any]):
        """Set user preferences."""
        st.session_state['user_preferences'] = value
    
    def initialize(self):
        """Initialize session with default values."""
        if 'initialized' not in st.session_state:
            st.session_state['initialized'] = True
            st.session_state['project_path'] = None
            st.session_state['db'] = None
            st.session_state['sync_status'] = {'drift_detected': False, 'entities': []}
            st.session_state['user_preferences'] = {}
    
    def reset(self):
        """Reset session state."""
        keys_to_remove = ['project_path', 'db', 'sync_status', 'user_preferences']
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
```

### 4.3 `forge/sandbox/app.py`

```python
import streamlit as st
import sys
from pathlib import Path

# Add forge directory to path for imports
forge_path = Path(__file__).parent.parent.parent.resolve()
if str(forge_path) not in sys.path:
    sys.path.insert(0, str(forge_path))

from forge.sandbox.session import Session
from forge.sandbox.services.db_manager import SandboxDB
from forge.sandbox.components.project_selector import project_selector
from forge.sandbox.pages import (
    WorldManifest, AgentForge, SpatialDomain, 
    EventChronology, SimulationLab, PrefabFactory
)

def main():
    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="PyScrAI Forge - Sandbox",
        page_icon="🛠️",
        layout="wide"
    )
    
    # Initialize session
    session = Session()
    session.initialize()
    
    # Sidebar: Navigation
    st.sidebar.title("🛠️ PyScrAI Forge")
    st.sidebar.markdown("---")
    
    # Project selection
    if session.project_path is None:
        selected_project = project_selector()
        if selected_project:
            session.project_path = selected_project
            
            # Initialize database connection
            try:
                db = SandboxDB(session.project_path)
                db.connect()
                session.db = db
                st.sidebar.success(f"Connected to: {session.project_path.name}")
            except Exception as e:
                st.error(f"Failed to connect to database: {e}")
                return
    else:
        # Show current project
        st.sidebar.info(f"Project: **{session.project_path.name}**")
        
        # Navigation pages
        pages = {
            "1. World Manifest": WorldManifest,
            "2. Agent Forge": AgentForge,
            "3. Spatial Domain": SpatialDomain,
            "4. Event Chronology": EventChronology,
            "5. Simulation Lab": SimulationLab,
            "6. Prefab Factory": PrefabFactory,
        }
        
        selected_page = st.sidebar.radio("Navigation", list(pages.keys()))
        
        # Render selected page
        page_class = pages[selected_page]
        page = page_class(session)
        page.render()
        
        # Check for drift on initial load
        if 'checked_drift' not in st.session_state:
            try:
                drift = session.db.detect_drift()
                if drift:
                    session.sync_status = {
                        'drift_detected': True,
                        'entities': drift
                    }
                    st.sidebar.warning(f"⚠️ {len(drift)} entities have changed!")
                st.session_state['checked_drift'] = True
            except Exception as e:
                st.sidebar.error(f"Error checking drift: {e}")

if __name__ == "__main__":
    main()
```

### 4.4 `forge/sandbox/pages/__init__.py`

```python
# Empty file to make pages directory a Python package
```

### 4.5 `forge/sandbox/pages/1_World_Manifest.py`

```python
import streamlit as st
import pandas as pd
from forge.sandbox.session import Session

class WorldManifest:
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        st.header("🌍 World Manifest")
        st.markdown("Manage global factions, polities, and project settings.")
        
        if not self.session.db:
            st.error("No database connection. Please select a project.")
            return
        
        try:
            # Get all entities from raw database
            entities_df = self.session.db.world_conn.execute("""
                SELECT id, type, label, attributes_json, created_at 
                FROM raw_db.entities 
                ORDER BY type, label
            """).df()
            
            if entities_df.empty:
                st.info("No entities found in the raw database. Please ingest documents first.")
                return
            
            # Display entities grouped by type
            for entity_type in sorted(entities_df['type'].unique()):
                st.subheader(f"**{entity_type.title()}**")
                
                type_entities = entities_df[entities_df['type'] == entity_type]
                
                # Show in table
                st.dataframe(
                    type_entities[['id', 'label', 'created_at']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Expand for attributes
                with st.expander(f"View {entity_type} attributes"):
                    for _, row in type_entities.iterrows():
                        try:
                            import json
                            attrs = json.loads(row['attributes_json'])
                            st.json(attrs)
                        except:
                            st.write(row['attributes_json'])
                
                st.markdown("---")
            
        except Exception as e:
            st.error(f"Error loading world manifest: {e}")
```

### 4.6 `forge/sandbox/pages/2_Agent_Forge.py`

```python
import streamlit as st
import json
from forge.sandbox.session import Session

class AgentForge:
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        st.header("👤 Agent Forge")
        st.markdown("Create agent personas from extracted entities.")
        
        if not self.session.db:
            st.error("No database connection. Please select a project.")
            return
        
        try:
            # Get promotable entities
            prom_df = self.session.db.get_promotable_entities()
            
            if prom_df.empty:
                st.info("No promotable entities found.")
                return
            
            # Create columns for layout
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Available Entities")
                
                # Filter by active status
                active_only = st.checkbox("Show active only", value=False)
                if active_only:
                    prom_df = prom_df[prom_df['is_active'] == True]
                
                # Display entities
                for _, row in prom_df.iterrows():
                    is_active = row['is_active']
                    status = "✅ Active" if is_active else "⏸️ Dormant"
                    
                    with st.expander(f"{row['label']} ({status})"):
                        st.write(f"**ID:** {row['id']}")
                        st.write(f"**Type:** {row['type']}")
                        
                        if st.button(f"{'Edit' if is_active else 'Activate'}", key=f"btn_{row['id']}"):
                            st.session_state['selected_entity'] = {
                                'id': row['id'],
                                'label': row['label'],
                                'type': row['type'],
                                'is_active': is_active
                            }
                
                # Check if entity selected
                if 'selected_entity' in st.session_state:
                    selected = st.session_state['selected_entity']
                    
                    with col2:
                        st.subheader(f"Edit Persona: {selected['label']}")
                        
                        # Check existing persona
                        existing = self.session.db.world_conn.execute("""
                            SELECT persona_prompt, goals, capabilities, state 
                            FROM active_agents 
                            WHERE agent_id = ?
                        """, [selected['id']]).fetchone()
                        
                        if existing:
                            prompt = existing[0] if existing[0] else ""
                            goals = existing[1] if existing[1] else "[]"
                            capabilities = existing[2] if existing[2] else "[]"
                            state = existing[3] if existing[3] else "{}"
                        else:
                            prompt = f"You are {selected['label']}, a {selected['type'].lower()}."
                            goals = "[]"
                            capabilities = "[]"
                            state = "{}"
                        
                        # Persona prompt editor
                        persona_prompt = st.text_area(
                            "System Prompt",
                            value=prompt,
                            height=200,
                            help="This prompt will be sent to the LLM when this agent is active."
                        )
                        
                        # Goals editor
                        st.subheader("Goals")
                        goals_input = st.text_area(
                            "Agent Goals (JSON array)",
                            value=goals,
                            height=100
                        )
                        
                        # Capabilities editor
                        st.subheader("Capabilities")
                        capabilities_input = st.text_area(
                            "Agent Capabilities (JSON array)",
                            value=capabilities,
                            height=100
                        )
                        
                        # State editor
                        st.subheader("Initial State")
                        state_input = st.text_area(
                            "Agent State (JSON object)",
                            value=state,
                            height=100
                        )
                        
                        # Save button
                        if st.button("💾 Save Agent", type="primary"):
                            try:
                                # Validate JSON
                                json.loads(goals_input)
                                json.loads(capabilities_input)
                                json.loads(state_input)
                                
                                # Save to database
                                self.session.db.world_conn.execute("""
                                    INSERT INTO active_agents 
                                        (agent_id, persona_prompt, goals, capabilities, state)
                                    VALUES (?, ?, ?, ?, ?)
                                    ON CONFLICT (agent_id) DO UPDATE SET
                                        persona_prompt = excluded.persona_prompt,
                                        goals = excluded.goals,
                                        capabilities = excluded.capabilities,
                                        state = excluded.state,
                                        updated_at = CURRENT_TIMESTAMP
                                """, [selected['id'], persona_prompt, goals_input, capabilities_input, state_input])
                                
                                self.session.db.world_conn.commit()
                                st.success("Agent saved successfully!")
                                
                                # Reset selection
                                del st.session_state['selected_entity']
                                
                            except json.JSONDecodeError as e:
                                st.error(f"Invalid JSON: {e}")
                            except Exception as e:
                                st.error(f"Error saving agent: {e}")
                        
                        # Deactivate button
                        if st.button("❌ Deactivate Agent", type="secondary"):
                            self.session.db.world_conn.execute("""
                                DELETE FROM active_agents WHERE agent_id = ?
                            """, [selected['id']])
                            self.session.db.world_conn.commit()
                            st.success("Agent deactivated!")
                            del st.session_state['selected_entity']
        
        except Exception as e:
            st.error(f"Error loading agent forge: {e}")
```

### 4.7 `forge/sandbox/pages/3_Spatial_Domain.py`

```python
import streamlit as st
import pandas as pd
import json
from forge.sandbox.session import Session

class SpatialDomain:
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        st.header("📍 Spatial Domain")
        st.markdown("Assign spatial coordinates to locations and configure environmental context.")
        
        if not self.session.db:
            st.error("No database connection. Please select a project.")
            return
        
        try:
            # Get location entities
            locations_df = self.session.db.world_conn.execute("""
                SELECT e.id, e.label, e.attributes_json,
                       sb.latitude, sb.longitude, sb.elevation, sb.spatial_tags
                FROM raw_db.entities e
                LEFT JOIN spatial_bookmarks sb ON e.id = sb.location_id
                WHERE e.type = 'LOCATION'
                ORDER BY e.label
            """).df()
            
            if locations_df.empty:
                st.info("No location entities found in the raw database.")
                return
            
            # Display locations with coordinates
            st.subheader("Location Coordinates")
            
            for _, row in locations_df.iterrows():
                with st.expander(f"{row['label']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**ID:** {row['id']}")
                        st.write(f"**Attributes:**")
                        try:
                            attrs = json.loads(row['attributes_json'])
                            for key, value in attrs.items():
                                st.write(f"  • {key}: {value}")
                        except:
                            st.write(row['attributes_json'])
                    
                    with col2:
                        # Coordinate inputs
                        lat = st.number_input(
                            "Latitude", 
                            value=float(row['latitude']) if row['latitude'] else 0.0,
                            key=f"lat_{row['id']}"
                        )
                        lon = st.number_input(
                            "Longitude", 
                            value=float(row['longitude']) if row['longitude'] else 0.0,
                            key=f"lon_{row['id']}"
                        )
                        elev = st.number_input(
                            "Elevation (m)", 
                            value=float(row['elevation']) if row['elevation'] else 0.0,
                            key=f"elev_{row['id']}"
                        )
                        
                        # Spatial tags
                        spatial_tags_input = st.text_area(
                            "Spatial Tags (JSON)",
                            value=row['spatial_tags'] if row['spatial_tags'] else "{}",
                            height=80,
                            key=f"tags_{row['id']}"
                        )
                        
                        # Save button
                        if st.button(f"Save Coordinates", key=f"save_{row['id']}"):
                            try:
                                json.loads(spatial_tags_input)
                                
                                self.session.db.world_conn.execute("""
                                    INSERT INTO spatial_bookmarks 
                                        (location_id, latitude, longitude, elevation, spatial_tags)
                                    VALUES (?, ?, ?, ?, ?)
                                    ON CONFLICT (location_id) DO UPDATE SET
                                        latitude = excluded.latitude,
                                        longitude = excluded.longitude,
                                        elevation = excluded.elevation,
                                        spatial_tags = excluded.spatial_tags,
                                        updated_at = CURRENT_TIMESTAMP
                                """, [row['id'], lat, lon, elev, spatial_tags_input])
                                
                                self.session.db.world_conn.commit()
                                st.success(f"Coordinates saved for {row['label']}!")
                                
                                # Rerun to update display
                                st.rerun()
                                
                            except json.JSONDecodeError as e:
                                st.error(f"Invalid JSON in spatial tags: {e}")
                            except Exception as e:
                                st.error(f"Error saving coordinates: {e}")
            
            # Map visualization (using leafmap)
            st.subheader("Spatial Overview")
            st.info("Map visualization will be available with leafmap integration.")
            
        except Exception as e:
            st.error(f"Error loading spatial domain: {e}")
```

### 4.8 `forge/sandbox/pages/4_Event_Chronology.py`

```python
import streamlit as st
import json
from forge.sandbox.session import Session

class EventChronology:
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        st.header("📅 Event Chronology")
        st.markdown("Create and manage narrative events with temporal context.")
        
        if not self.session.db:
            st.error("No database connection. Please select a project.")
            return
        
        try:
            # Show existing narrative contexts
            contexts = self.session.db.world_conn.execute("""
                SELECT context_id, title, description, mood, timeline 
                FROM narrative_context 
                ORDER BY context_id
            """).fetchall()
            
            if contexts:
                st.subheader("Existing Narrative Contexts")
                for ctx in contexts:
                    with st.expander(f"{ctx[1]} ({ctx[3]})"):
                        st.write(f"**ID:** {ctx[0]}")
                        st.write(f"**Timeline:** {ctx[4]}")
                        st.write(f"**Description:** {ctx[2]}")
            
            # Create new context
            st.subheader("Create New Narrative Context")
            
            col1, col2 = st.columns(2)
            
            with col1:
                title = st.text_input("Context Title")
                mood = st.selectbox("Mood", ["Neutral", "Tense", "Hopeful", "Dark", "Mysterious", "Epic"])
                timeline = st.text_input("Timeline (e.g., 'Day 1', 'Year 3021')")
            
            with col2:
                description = st.text_area("Description", height=100)
            
            if st.button("Create Context"):
                if title:
                    import uuid
                    context_id = str(uuid.uuid4())
                    
                    self.session.db.world_conn.execute("""
                        INSERT INTO narrative_context 
                            (context_id, title, description, mood, timeline)
                        VALUES (?, ?, ?, ?, ?)
                    """, [context_id, title, description, mood, timeline])
                    
                    self.session.db.world_conn.commit()
                    st.success(f"Created context: {title}")
                    st.rerun()
                else:
                    st.error("Title is required")
        
        except Exception as e:
            st.error(f"Error loading event chronology: {e}")
```

### 4.9 `forge/sandbox/pages/5_Simulation_Lab.py`

```python
import streamlit as st
from forge.sandbox.session import Session

class SimulationLab:
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        st.header("🧪 Simulation Lab")
        st.markdown("Test and interact with simulation components.")
        
        if not self.session.db:
            st.error("No database connection. Please select a project.")
            return
        
        # Component selection
        st.subheader("Select Components")
        
        # Get active agents
        agents = self.session.db.world_conn.execute("""
            SELECT aa.agent_id, e.label, aa.persona_prompt
            FROM active_agents aa
            JOIN raw_db.entities e ON aa.agent_id = e.id
            ORDER BY e.label
        """).fetchall()
        
        if not agents:
            st.info("No active agents found. Create agents in Agent Forge first.")
            return
        
        # Agent selection
        selected_agents = []
        for agent in agents:
            if st.checkbox(f"{agent[1]}", key=f"sel_{agent[0]}"):
                selected_agents.append(agent[0])
        
        # Location selection
        locations = self.session.db.world_conn.execute("""
            SELECT sb.location_id, e.label
            FROM spatial_bookmarks sb
            JOIN raw_db.entities e ON sb.location_id = e.id
            ORDER BY e.label
        """).fetchall()
        
        st.subheader("Select Location")
        selected_location = None
        if locations:
            location_options = {loc[1]: loc[0] for loc in locations}
            selected_location = st.selectbox(
                "Location",
                options=list(location_options.keys()),
                index=0
            )
            selected_location = location_options[selected_location]
        
        # Interactive mode
        st.subheader("Interactive Mode")
        st.markdown("Test run selected components.")
        
        test_text = st.text_area(
            "Test Input",
            placeholder="Enter text to interact with selected agents...",
            height=150
        )
        
        if st.button("▶️ Run Test", type="primary"):
            if test_text:
                st.info("LLM interaction would happen here with:")
                st.write(f"• Agents: {[a[1] for a in agents if a[0] in selected_agents]}")
                st.write(f"• Location: {selected_location}")
                st.write(f"• Input: {test_text}")
                # In production, this would call LLM services
            else:
                st.warning("Please enter test input")
        
        # Export package
        st.markdown("---")
        st.subheader("Export Simulation Package")
        
        if st.button("📦 Create Export Package", type="secondary"):
            try:
                from forge.sandbox.services.export_service import ExportService
                export = ExportService()
                
                package_path = export.create_package(
                    self.session.project_path,
                    self.session.project_path.parent / f"{self.session.project_path.name}_simulation.zip"
                )
                
                st.success(f"✅ Package created: {package_path}")
                st.download_button(
                    "⬇️ Download Package",
                    data=open(package_path, 'rb').read(),
                    file_name=package_path.name,
                    mime="application/zip"
                )
                
            except Exception as e:
                st.error(f"Error creating package: {e}")
```

### 4.10 `forge/sandbox/pages/6_Prefab_Factory.py`

```python
import streamlit as st
import json
from pathlib import Path
from forge.sandbox.session import Session

class PrefabFactory:
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        st.header("🔧 Prefab Factory")
        st.markdown("Create and manage reusable templates and prefabs.")
        
        if not self.session.db:
            st.error("No database connection. Please select a project.")
            return
        
        # Templates directory
        templates_dir = self.session.project_path / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        # List existing templates
        st.subheader("Existing Templates")
        
        template_files = list(templates_dir.glob("*.j2"))
        if template_files:
            for template_file in template_files:
                with st.expander(template_file.stem):
                    content = template_file.read_text()
                    st.code(content, language="jinja2")
                    
                    if st.button(f"Delete {template_file.name}", key=f"del_{template_file.name}"):
                        template_file.unlink()
                        st.rerun()
        else:
            st.info("No templates found. Create one below.")
        
        # Create new template
        st.subheader("Create New Template")
        
        template_name = st.text_input("Template Name", placeholder="e.g., 'character_intro'")
        template_content = st.text_area(
            "Template Content (Jinja2)",
            placeholder="e.g., Hello, {{ name }}! You are {{ role }}.",
            height=200
        )
        
        if st.button("Create Template"):
            if template_name and template_content:
                template_file = templates_dir / f"{template_name}.j2"
                template_file.write_text(template_content)
                st.success(f"Created template: {template_name}.j2")
                st.rerun()
            else:
                st.error("Template name and content are required")
        
        # Prefab management
        st.markdown("---")
        st.subheader("Manage Prefabs")
        
        # Show prefab examples (entities with tags)
        entities = self.session.db.world_conn.execute("""
            SELECT id, type, label, attributes_json 
            FROM raw_db.entities
            WHERE attributes_json IS NOT NULL
            ORDER BY type, label
        """).fetchall()
        
        if entities:
            # Filter by type
            entity_types = list(set([e[1] for e in entities]))
            selected_type = st.selectbox("Filter by Type", ["All"] + entity_types)
            
            if selected_type != "All":
                entities = [e for e in entities if e[1] == selected_type]
            
            # Display prefabs
            for entity in entities:
                with st.expander(f"{entity[2]} ({entity[1]})"):
                    try:
                        attrs = json.loads(entity[3])
                        st.json(attrs)
                    except:
                        st.write(entity[3])
        else:
            st.info("No prefabs available. Create entities in the Extractor first.")
