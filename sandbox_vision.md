PyScrAI Forge: Triad Architecture & World Builder Blueprint

Version: 2.2

Date: January 24, 2026

Status: Approved for Development



1. Executive Summary

This blueprint defines the separation of PyScrAI Forge into two distinct applications sharing a single dependency environment and kernel.



The Extractor (Flet): Responsible for "Mining." It handles Ingestion, Extraction, and Raw Database creation. It is agnostic of simulation logic.

The Sandbox (Streamlit): Responsible for "Refining." It handles Entity Promotion, Spatial Enrichment, Persona Assignment, and Narrative Context.

The Shared Ledger (File System): The Project Directory serves as the bridge. A robust "Read-Only Origin / Writeable World" database strategy ensures data integrity.

2. Architecture & Data Flow

2.1 The Monorepo Structure (Single .venv)

Both applications run from the same virtual environment to share heavy libraries (DuckDB, PyTorch, Spacy).



forge/

├── main.py                  # Entry point for Flet Extractor

├── shared/                  # The Unified Kernel (Domain, Infra, Core)

├── extractor/                # Flet UI logic (Extraction focus)

└── sandbox/                 # NEW: Streamlit UI logic (Simulation focus)

    ├── app.py               # Entry point: streamlit run forge/sandbox/app.py

    ├── session.py           # Streamlit Session State Management

    └── pages/

        ├── 1_World_Manifest.py      # Factions, Polities, Global Settings 

        ├── 2_Agent_Forge.py         # Entity Promotion & Persona Injection

        ├── 3_Spatial_Domain.py      # Location Management / Environment & Optional Map Overlay

        ├── 4_Event_Chronology.py    # Advanced Event Editing / Narrative 

        ├── 5_Simulation_Lab.py      # Interactive Component Testing

        └── 6_Prefab_Factory.py      # Modular Template/Prefab/project Management (Side bar for cross editor/page utilization) 

2.2 The "Dual-DB" Data Strategy

To handle the "Bidirectional Sync" without corruption, we utilize DuckDB's ability to attach multiple database files.



File A: intel.duckdb (The Raw Source)

Owner: Flet Extractor (Read/Write), Sandbox (Read-Only).

Content: Extracted Entities, Relationships, Raw Text, Source Metadata.

Schema: raw_entities, raw_relationships, sources.

File B: world.duckdb (The Semantic Overlay)

Owner: Sandbox (Read/Write).

Content: Agent Personas, Spatial Coordinates, Narrative State, Simulation Settings.

Schema:

active_agents: Links to intel.duckdb UUIDs + Persona Prompt.

spatial_bookmarks: Links to intel.duckdb Location UUIDs + Lat/Lon.

sync_ledger: Tracks the last_seen_hash of entities from intel.duckdb.

3. Workflow & Logic

3.1 The "Mining" Workflow (Extractor)

User opens Flet Extractor.

Project Management:

Create Project:

User supplies a Project Name (e.g., "NeoTokyo").

System creates a subdirectory: data/projects/{Project Name}/.

System initializes config.json and a database file named intel.duckdb (hardcoded) inside this directory.

Open Project:

User browses the data/projects/ directory.

User selects a Project Folder (not a file).

Validation: The Extractor enforces that the selected directory must contain both config.json and intel.duckdb. If missing, the folder is considered invalid.

Ingests new Documents.

Extraction Service runs $\rightarrow$ Updates intel.duckdb.

Critical: Extractor does not check world.duckdb. It only cares about extraction accuracy.

Saves database exclusively in project directory as intel.duckdb.

3.2 The "World Building" Workflow (Sandbox)

User runs streamlit run forge/sandbox/app.py.

Selects Project Directory.

Initialization:

Connects to world.duckdb (creates if missing).

Attaches intel.duckdb as raw_db (READ_ONLY).

Drift Detection (The Sync Logic):

Sandbox compares the current hash/timestamp of entities in raw_db against the sync_ledger in world.duckdb.

If Drift Detected: Triggers "Merge/Verify" Wizard.

Example: "Entity 'Dr. Smith' has new extracted info from Document C. Update Persona Context?"

Configuration: User adds spatial tags, defines agent goals, edits Jinja templates.

Save: Writes to world.duckdb.

4. Implementation Plan

Phase 1: Foundation & Environment (Week 1)

Goal: Establish the Sandbox folder structure and unifying dependencies.

Tasks:

Update setup.py: Add streamlit, streamlit-agraph, leafmap, jinja2.

Create forge/sandbox/ directory structure.

Create forge/sandbox/app.py (Project Selector).

Create forge/sandbox/services/db_manager.py: Logic to handle the specific DuckDB ATTACH commands for the dual-db setup.

Phase 2: The "World Creator" UI (Week 2)

Goal: Build the interface to visualize Raw Data and create Enriched Data.

Scope:

Locations: Enrich data on locations as well as configuring overall project environment. (Where)

Events: Advanced event editor. (What)

Entities: Refine and add attributes / prompts. (Who)

Persona Editor: Write System Prompts for created Actors (LLM Agents which take control of specific entities, polities, factions, as well as specific areas covering the environment/events/advanced relationships or other simulated mechanics).

Spatial Overlay: Integration of a map component to assign coordinates to Location entities.

Phase 3: The Sync Engine (Week 3)

Goal: Handle the "Re-Ingestion" scenario.

Tasks:

Implement SyncService in the Shared Kernel (but used by Sandbox).

Build the "Diff View" component in Streamlit (Side-by-side comparison of old vs. new entity data).

Create the sync_ledger table logic to store hashes of accepted data.

Phase 4: Playground & Export (Week 4)

Goal: Templating and Simulation Handoff.

Tasks:

Playground: Streamlit page with a text editor and "Render Preview" button.

Features: Ability to ‘test run’ individual components / multiple components (i.e., three specified entities with the location manager), allowing the human to ‘interact’ with either a singular entity or a group, with or without simulation mechanics involved.

Export: Button to bundle intel.duckdb + world.duckdb + templates into a "Simulation Run Package."

5. Technical Specifications

5.1 Sandbox Database Manager (db_manager.py) (EXAMPLE)

import duckdb



class SandboxDB:

    def __init__(self, project_path):

        self.con = duckdb.connect(f"{project_path}/world.duckdb")

        # Attach the raw data as read-only

        self.con.execute(f"ATTACH '{project_path}/intel.duckdb' AS raw_db (READ_ONLY)")

        

    def get_promotable_entities(self):

        # Query combining raw data with world status

        return self.con.execute("""

            SELECT 

                r.id, r.name, r.category, 

                CASE WHEN w.agent_id IS NOT NULL THEN TRUE ELSE FALSE END as is_active

            FROM raw_db.entities r

            LEFT JOIN active_agents w ON r.id = w.agent_id

        """).df()

5.2 Required Libraries (Add to setup.py)

streamlit: The UI framework.

streamlit-agraph or pyvis: For Knowledge Graph exploration.

folium or streamlit-folium: For the Spatial Layer.

watchdog: (Optional) To auto-refresh Streamlit if DuckDB changes externally (advanced).

6. Risks & Mitigations

Risk

Mitigation

Database Locking

Ensure Sandbox closes the connection to intel.duckdb immediately after query execution, or strictly enforce READ_ONLY mode which DuckDB handles better concurrently.

UUID Drift

If Flet re-extraction changes UUIDs, the world.duckdb links break. Mitigation: The Extractor's deduplication service must be deterministic (hashing name + category) to preserve UUIDs across runs.

Schema Mismatch

Extractor updates schema. Mitigation: Sandbox db_manager must include a version check. If intel.duckdb version > world.duckdb supported version, prompt user to update Sandbox.

7. Immediate Next Actions

Approve this Blueprint.

Run Dependency Update: pip install streamlit streamlit-folium (and update setup.py).

Create Branch: feature/sandbox-init.

Execute Phase 1 Tasks.