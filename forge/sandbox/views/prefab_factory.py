"""Prefab Factory page - create and manage reusable templates and prefabs.

Allows users to:
- Create Jinja2 templates for simulation components
- Manage reusable entity and scenario templates
- Import/export template libraries
- Generate procedural content
"""

import streamlit as st
from forge.sandbox.session import Session


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