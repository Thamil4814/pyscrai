"""Event Chronology page - create and manage temporal events and narrative contexts.

Allows users to:
- Create narrative events with temporal context
- Define timeline sequences
- Set mood and atmosphere
- Link events to entities and locations
"""

import streamlit as st
from forge.sandbox.session import Session


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