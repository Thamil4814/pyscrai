"""Project selector component for the Sandbox application.

Allows users to browse and select projects from the data/projects directory.
"""

import streamlit as st
from pathlib import Path
from typing import Optional
from forge.sandbox.services.db_manager import ProjectManager

def project_selector() -> Optional[Path]:
    """Render project selection UI and return selected project path."""
    
    st.title("🛠️ PyScrAI Forge - Sandbox")
    st.markdown("### Select a Project")
    st.markdown("Choose an existing project to open in the Sandbox for world building and simulation setup.")
    
    # Initialize project manager
    project_manager = ProjectManager()
    projects = project_manager.list_projects()
    
    if not projects:
        st.error("**No projects found!**")
        st.markdown("""
        To use the Sandbox, you need to create a project first using the **Flet Extractor**:
        
        1. Run `python -m forge.extractor.main`
        2. Create a new project and ingest documents
        3. Return here to build your simulation world
        """)
        
        # Show where projects should be located
        data_dir = project_manager.data_dir
        st.info(f"Looking for projects in: `{data_dir}`")
        
        return None
    
    # Display available projects
    st.markdown(f"**Found {len(projects)} project(s):**")
    
    selected_project = None
    
    for project in projects:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**📁 {project['name']}**")
                info = project['info']
                
                # Show project stats
                if info['entity_count'] > 0 or info['relationship_count'] > 0:
                    st.markdown(f"*{info['entity_count']} entities, {info['relationship_count']} relationships*")
                else:
                    st.markdown("*No data extracted yet*")
            
            with col2:
                # Show project status
                status_items = []
                if info['has_intel_db']:
                    status_items.append("✅ Intel DB")
                else:
                    status_items.append("❌ Intel DB")
                    
                if info['has_world_db']:
                    status_items.append("✅ World DB")
                else:
                    status_items.append("⚪ World DB")
                
                if info['has_config']:
                    status_items.append("✅ Config")
                else:
                    status_items.append("⚪ Config")
                
                st.markdown(" | ".join(status_items))
            
            with col3:
                # Select button
                if st.button(f"Open", key=f"open_{project['name']}", type="primary"):
                    if not info['has_intel_db']:
                        st.error(f"Project '{project['name']}' is missing intel.duckdb. Run the Extractor first.")
                    else:
                        selected_project = project['path']
            
            st.markdown("---")
    
    if selected_project:
        st.success(f"Opening project: {selected_project.name}")
        return selected_project
    
    return None