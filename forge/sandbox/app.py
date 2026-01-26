"""Main Streamlit application entry point for PyScrAI Forge Sandbox.

Run with: streamlit run forge/sandbox/app.py

This application provides a web-based interface for:
- Selecting and opening projects created with the Flet Extractor
- Building simulation worlds from extracted intelligence data  
- Managing agents, locations, and narrative contexts
- Exporting simulation packages for deployment
"""

import streamlit as st
from pathlib import Path

from forge.sandbox.session import Session
from forge.sandbox.services.db_manager import SandboxDB, SyncService
from forge.sandbox.components.project_selector import project_selector
from forge.sandbox.components.drift_wizard import render_drift_wizard
from forge.sandbox.views.world_manifest import render_world_manifest
from forge.sandbox.views.agent_forge import render_agent_forge
from forge.sandbox.views.spatial_domain import render_spatial_domain
from forge.sandbox.views.event_chronology import render_event_chronology
from forge.sandbox.views.simulation_lab import render_simulation_lab
from forge.sandbox.views.prefab_factory import render_prefab_factory

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
                # Setting project_path will automatically make session.db available 
                # via st.cache_resource in session.py
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
        
        views = {
            "🌍 World Manifest": "world_manifest",
            "👤 Agent Forge": "agent_forge", 
            "📍 Spatial Domain": "spatial_domain",
            "📅 Event Chronology": "event_chronology",
            "🧪 Simulation Lab": "simulation_lab",
            "🔧 Prefab Factory": "prefab_factory"
        }
        
        for page_label, page_id in views.items():
            if st.button(page_label, key=f"nav_{page_id}"):
                st.session_state['page'] = page_id
    
    # Main content area
    current_page = st.session_state.get('page', 'world_manifest')
    
    # Import and render views based on selection
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

if __name__ == "__main__":
    main()