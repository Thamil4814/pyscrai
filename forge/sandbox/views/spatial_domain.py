"""Spatial Domain page - assign coordinates and spatial context to locations.

Allows users to:
- Assign GPS coordinates to location entities
- Add elevation and spatial tags
- View locations on interactive maps
- Define environmental context for simulation
"""

import streamlit as st
from forge.sandbox.session import Session


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