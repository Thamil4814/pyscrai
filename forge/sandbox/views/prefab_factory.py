"""Prefab Factory page - create and manage reusable templates and prefabs.

Allows users to:
- Create Jinja2 templates for simulation components
- Manage reusable entity and scenario templates
- Import/export template libraries
- Generate procedural content
"""

import streamlit as st
from forge.sandbox.session import Session


class PrefabFactoryPage:
    """Prefab Factory page implementation."""

    def __init__(self, session: Session):
        self.session = session

    def render(self):
        """Render the Prefab Factory page."""
        st.header("🔧 Prefab Factory")
        st.markdown("Create and manage reusable templates and prefabs.")
        
        if not self.session.db:
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


def render_prefab_factory(session: Session):
    """Render the Prefab Factory page."""
    page = PrefabFactoryPage(session)
    page.render()
