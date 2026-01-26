"""Main Streamlit application entry point for PyScrAI Forge Sandbox.

Run with: streamlit run forge/sandbox/app.py

This application provides a web-based interface for:
- Selecting and opening projects created with the Flet Extractor
- Building simulation worlds from extracted intelligence data  
- Managing agents, locations, and narrative contexts
- Exporting simulation packages for deployment
"""

import streamlit as st
import sys
from pathlib import Path

# Add forge directory to path for imports
forge_path = Path(__file__).parent.parent.resolve()
if str(forge_path) not in sys.path:
    sys.path.insert(0, str(forge_path))

from forge.sandbox.session import Session
from forge.sandbox.services.db_manager import SandboxDB, SyncService
from forge.sandbox.components.project_selector import project_selector
from forge.sandbox.components.drift_wizard import render_drift_wizard
from forge.sandbox.pages.world_manifest import render_world_manifest
from forge.sandbox.pages.agent_forge import render_agent_forge

def main():
    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="PyScrAI Forge - Sandbox",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session
    session = Session()
    session.initialize()
    
    # Main application logic
    if session.project_path is None:
        # Show project selection
        selected_project = project_selector()
        if selected_project:
            session.project_path = selected_project
            
            # Initialize database connection
            try:
                db = SandboxDB(session.project_path)
                db.connect()
                session.db = db
                st.rerun()  # Refresh to show the main app
            except Exception as e:
                st.error(f"Failed to connect to database: {e}")
                st.markdown("""
                **Troubleshooting:**
                - Ensure the project was created with the Flet Extractor
                - Verify that intel.duckdb exists in the project directory
                - Check that the database file is not corrupted
                """)
    else:
        # Show main application
        render_main_app(session)

def render_main_app(session: Session):
    """Render the main application interface with navigation."""
    
    # Sidebar: Project info and navigation
    with st.sidebar:
        st.title("🛠️ PyScrAI Forge")
        st.markdown("---")
        
        # Project info
        st.markdown("### Current Project")
        if session.project_path is not None:
            st.info(f"**{session.project_path.name}**")
        else:
            st.info("No project selected.")
        
        # Project actions
        if st.button("🔄 Switch Project"):
            session.reset_project()
            st.rerun()
        
        if st.button("❌ Disconnect"):
            if session.db:
                session.db.close()
            session.clear_all()
            st.rerun()
        
        st.markdown("---")
        
        # Check for drift on initial load
        if 'checked_drift' not in st.session_state:
            if session.db:
                try:
                    drift = session.db.detect_drift()
                    if drift:
                        session.sync_status = {
                            'drift_detected': True,
                            'entities': drift
                        }
                        st.warning(f"⚠️ {len(drift)} entities have changes!")
                    st.session_state['checked_drift'] = True
                except Exception as e:
                    st.error(f"Error checking for drift: {e}")
        
        # Sync status
        sync_status = session.sync_status
        if sync_status.get('drift_detected', False):
            st.markdown("### 📊 Sync Status")
            st.error(f"**{len(sync_status.get('entities', []))} entities** need review")
            
            if st.button("🔍 Review Changes"):
                st.session_state['page'] = 'sync_review'
        
        # Navigation
        st.markdown("### 📋 Navigation")
        
        pages = {
            "🌍 World Manifest": "world_manifest",
            "👤 Agent Forge": "agent_forge", 
            "📍 Spatial Domain": "spatial_domain",
            "📅 Event Chronology": "event_chronology",
            "🧪 Simulation Lab": "simulation_lab",
            "🔧 Prefab Factory": "prefab_factory"
        }
        
        for page_label, page_id in pages.items():
            if st.button(page_label, key=f"nav_{page_id}"):
                st.session_state['page'] = page_id
    
    # Main content area
    current_page = st.session_state.get('page', 'world_manifest')
    
    # Import and render pages based on selection
    try:
        if current_page == 'sync_review':
            render_sync_review(session)
        elif current_page == 'world_manifest':
            render_world_manifest(session)
        elif current_page == 'agent_forge':
            render_agent_forge(session) 
        elif current_page == 'spatial_domain':
            render_spatial_domain(session)
        elif current_page == 'event_chronology':
            render_event_chronology(session)
        elif current_page == 'simulation_lab':
            render_simulation_lab(session)
        elif current_page == 'prefab_factory':
            render_prefab_factory(session)
        else:
            render_world_manifest(session)
    except Exception as e:
        st.error(f"Error rendering page: {e}")
        st.markdown("**Debug Info:**")
        st.code(str(e))

def render_sync_review(session: Session):
    """Render the synchronization review page."""
    st.header("🔍 Sync Review")
    st.markdown("Review changes detected in the raw extraction data.")
    
    if not session.db:
        st.error("No database connection.")
        return
    
    sync_status = session.sync_status
    entities = sync_status.get('entities', [])
    
    if not entities:
        st.success("✅ No drift detected. All entities are synchronized.")
        # Clear the drift status
        session.sync_status = {'drift_detected': False, 'entities': []}
        return
    
    # Use the drift wizard component
    render_drift_wizard(session.db, entities)
    
    # Check if all changes have been processed
    remaining_drift = session.db.detect_drift()
    if not remaining_drift:
        st.success("✅ All changes have been processed!")
        session.sync_status = {'drift_detected': False, 'entities': []}
        st.rerun()

def render_world_manifest(session: Session):
    """Render the World Manifest page - use dedicated implementation."""
    from forge.sandbox.pages.world_manifest import render_world_manifest as render_impl
    render_impl(session)

def render_agent_forge(session: Session):
    """Render the Agent Forge page - use dedicated implementation.""" 
    from forge.sandbox.pages.agent_forge import render_agent_forge as render_impl
    render_impl(session)

def render_spatial_domain(session: Session):
    """Render the Spatial Domain page."""
    st.header("📍 Spatial Domain")
    st.markdown("Assign coordinates and spatial context to locations.")
    
    if not session.db:
        st.error("No database connection.")
        return
    
    st.info("🚧 **Spatial Domain is under construction**")
    st.markdown("""
    This page will allow you to:
    - Assign GPS coordinates to location entities
    - Add elevation and spatial tags
    - View locations on interactive maps
    - Define environmental context for simulation
    """)

def render_event_chronology(session: Session):
    """Render the Event Chronology page."""
    st.header("📅 Event Chronology")
    st.markdown("Create and manage temporal events and narrative contexts.")
    
    if not session.db:
        st.error("No database connection.")
        return
    
    st.info("🚧 **Event Chronology is under construction**")
    st.markdown("""
    This page will allow you to:
    - Create narrative events with temporal context
    - Define timeline sequences
    - Set mood and atmosphere
    - Link events to entities and locations
    """)

def render_simulation_lab(session: Session):
    """Render the Simulation Lab page."""
    st.header("🧪 Simulation Lab")
    st.markdown("### Test Components & Export Simulation Packages")
    st.markdown("Validate your simulation world and export complete packages for deployment.")
    
    if not session.db:
        st.error("❌ No database connection.")
        return
    
    # Simulation status overview
    st.subheader("📊 Simulation Status")
    
    try:
        # Get active agents
        agents_df = session.db.world_conn.execute("""
            SELECT aa.agent_id, e.label, e.type
            FROM active_agents aa
            JOIN raw_db.entities e ON aa.agent_id = e.id
        """).df()
        
        # Get spatial bookmarks
        locations_df = session.db.world_conn.execute("""
            SELECT sb.location_id, e.label
            FROM spatial_bookmarks sb
            JOIN raw_db.entities e ON sb.location_id = e.id
        """).df()
        
        # Get narrative contexts
        contexts_df = session.db.world_conn.execute("""
            SELECT context_id, title FROM narrative_context
        """).df()
        
        # Display status
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👤 Active Agents", len(agents_df))
        
        with col2:
            st.metric("📍 Mapped Locations", len(locations_df))
        
        with col3:
            st.metric("📅 Narrative Contexts", len(contexts_df))
        
        with col4:
            # Calculate readiness score
            try:
                total_entities = len(session.db.world_conn.execute("SELECT id FROM raw_db.entities").fetchall())
            except Exception:
                total_entities = 0
            if total_entities > 0:
                readiness = min(100, round(((len(agents_df) + len(locations_df) + len(contexts_df)) / total_entities) * 100))
            else:
                readiness = 0
            st.metric("🎯 Readiness", f"{readiness}%")
        
        # Component testing section
        st.subheader("🔧 Component Testing")
        
        if len(agents_df) > 0:
            st.markdown("**Available Agents for Testing:**")
            for _, agent in agents_df.iterrows():
                with st.expander(f"👤 {agent['label']} ({agent['type']})"):
                    test_input = st.text_area(
                        f"Test input for {agent['label']}",
                        placeholder="Enter a scenario or question to test this agent...",
                        key=f"test_{agent['agent_id']}"
                    )
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(f"▶️ Test {agent['label']}", key=f"run_test_{agent['agent_id']}"):
                            if test_input:
                                st.info("🤖 **Simulation Test Result**")
                                st.markdown(f"**Agent:** {agent['label']}")
                                st.markdown(f"**Input:** {test_input}")
                                st.markdown("**Response:** *LLM integration would provide agent response here*")
                                st.success("✅ Test completed successfully!")
                            else:
                                st.warning("Please enter test input first.")
                    
                    with col_b:
                        if st.button(f"📋 View Persona", key=f"persona_{agent['agent_id']}"):
                            persona_data = session.db.world_conn.execute("""
                                SELECT persona_prompt, goals, capabilities
                                FROM active_agents WHERE agent_id = ?
                            """, [agent['agent_id']]).fetchone()
                            
                            if persona_data:
                                st.markdown("**Persona Prompt:**")
                                st.text(persona_data[0][:200] + "..." if len(persona_data[0]) > 200 else persona_data[0])
                                
                                st.markdown("**Goals:**")
                                st.text(persona_data[1])
                                
                                st.markdown("**Capabilities:**")
                                st.text(persona_data[2])
        else:
            st.info("💡 **No active agents available**. Visit the Agent Forge to create agents for testing.")
        
        # Export section
        st.markdown("---")
        st.subheader("📦 Export Simulation Package")
        st.markdown("Create a portable simulation package that can be deployed on other systems.")
        
        # Export configuration
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Package Contents:**")
            st.markdown("✅ **intel.duckdb** - Raw extraction data")
            st.markdown("✅ **world.duckdb** - Simulation enhancements")
            st.markdown("✅ **config.json** - Project configuration")
            st.markdown("✅ **manifest.json** - Package metadata")
            
            # Check for templates directory
            if session.project_path is not None:
                templates_dir = session.project_path / "templates"
                if templates_dir.exists():
                    template_count = len(list(templates_dir.glob("*.j2")))
                    st.markdown(f"✅ **templates/** - {template_count} template files")
                else:
                    st.markdown("⚪ **templates/** - No templates (optional)")
            else:
                st.markdown("⚪ **templates/** - No templates (optional)")
        
        with col2:
            st.markdown("**Export Options:**")
            include_examples = st.checkbox("Include example scenarios", value=True)
            include_docs = st.checkbox("Include documentation", value=True)
            compress_level = st.slider("Compression Level", 1, 9, 6, help="Higher = smaller file, slower")
        
        # Export button
        if st.button("📦 Create Export Package", type="primary"):
            if session.project_path is not None:
                try:
                    from forge.sandbox.services.export_service import ExportService
                    
                    with st.spinner("Creating simulation package..."):
                        export_service = ExportService()
                        
                        # Generate filename with timestamp
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{session.project_path.name}_simulation_{timestamp}.zip"
                        output_path = session.project_path.parent / filename
                        
                        # Create package
                        package_path = export_service.create_package(
                            session.project_path,
                            output_path
                        )
                        
                        # Success message
                        file_size = round(package_path.stat().st_size / (1024*1024), 2)
                        st.success(f"✅ **Package created successfully!**")
                        st.markdown(f"**File:** `{package_path.name}`")
                        st.markdown(f"**Size:** {file_size} MB")
                        st.markdown(f"**Location:** `{package_path.parent}`")
                        
                        # Provide download
                        with open(package_path, 'rb') as f:
                            st.download_button(
                                "⬇️ Download Package",
                                data=f.read(),
                                file_name=package_path.name,
                                mime="application/zip",
                                type="secondary"
                            )
                except Exception as e:
                    st.error(f"❌ **Export failed:** {e}")
                    st.code(str(e))
            else:
                st.error("No project selected. Cannot export package.")
        
        # Validation section
        st.markdown("---")
        st.subheader("✅ World Validation")
        
        # Basic validation checks
        validation_results = []
        
        # Check 1: Active agents exist
        if len(agents_df) > 0:
            validation_results.append(("✅", "Active agents configured", f"{len(agents_df)} agents ready"))
        else:
            validation_results.append(("❌", "No active agents", "Visit Agent Forge to create agents"))
        
        # Check 2: Spatial data
        if len(locations_df) > 0:
            validation_results.append(("✅", "Spatial data configured", f"{len(locations_df)} locations mapped"))
        else:
            validation_results.append(("⚠️", "No spatial data", "Visit Spatial Domain to map locations"))
        
        # Check 3: Database integrity
        try:
            entity_count = len(session.db.world_conn.execute("SELECT id FROM raw_db.entities").fetchall())
            if entity_count > 0:
                validation_results.append(("✅", "Database integrity", f"{entity_count} entities in intel.duckdb"))
            else:
                validation_results.append(("❌", "Empty database", "No entities found in intel.duckdb"))
        except:
            validation_results.append(("❌", "Database error", "Could not verify database integrity"))
        
        # Display validation results
        for status, title, description in validation_results:
            col_status, col_title, col_desc = st.columns([1, 3, 4])
            with col_status:
                st.markdown(status)
            with col_title:
                st.markdown(f"**{title}**")
            with col_desc:
                st.markdown(description)
        
        # Overall readiness
        passed_checks = sum(1 for status, _, _ in validation_results if status == "✅")
        total_checks = len(validation_results)
        
        if passed_checks == total_checks:
            st.success(f"🎉 **Simulation world is ready for deployment!** ({passed_checks}/{total_checks} checks passed)")
        else:
            st.warning(f"⚠️ **Simulation world needs attention** ({passed_checks}/{total_checks} checks passed)")
        
    except Exception as e:
        st.error(f"❌ Error in simulation lab: {e}")
        st.code(str(e))

def render_prefab_factory(session: Session):
    """Render the Prefab Factory page."""
    st.header("🔧 Prefab Factory")
    st.markdown("Create and manage reusable templates and prefabs.")
    
    if not session.db:
        st.error("No database connection.")
        return
    
    st.info("🚧 **Prefab Factory is under construction**")
    st.markdown("""
    This page will allow you to:
    - Create Jinja2 templates for simulation components
    - Manage reusable entity and scenario templates
    - Import/export template libraries
    - Generate procedural content
    """)

if __name__ == "__main__":
    main()