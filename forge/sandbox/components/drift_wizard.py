"""Drift wizard component for reviewing entity changes.

Provides UI components for visualizing and managing entity drift
between intel.duckdb and world.duckdb.
"""

import streamlit as st
from typing import List, Dict, Any
from forge.sandbox.services.db_manager import SandboxDB

def render_drift_wizard(db: SandboxDB, drift_entities: List[Dict[str, Any]]):
    """Render the drift detection and review interface.
    
    Args:
        db: SandboxDB instance
        drift_entities: List of entities with detected changes
    """
    if not drift_entities:
        st.success("✅ No drift detected. All entities are synchronized.")
        return
    
    st.warning(f"⚠️ Detected changes in {len(drift_entities)} entities")
    st.markdown("""
    **What is drift?** When you re-run the Extractor on new documents, 
    entities may be updated with new information. Review these changes
    to decide what to incorporate into your simulation world.
    """)
    
    # Group by status
    new_entities = [e for e in drift_entities if e['status'] == 'new']
    changed_entities = [e for e in drift_entities if e['status'] == 'changed']
    
    # Tabs for different types of changes
    tab1, tab2 = st.tabs([f"📥 New ({len(new_entities)})", f"🔄 Changed ({len(changed_entities)})"])
    
    with tab1:
        if new_entities:
            st.markdown("**New entities detected in intel.duckdb:**")
            render_new_entities(db, new_entities)
        else:
            st.info("No new entities detected.")
    
    with tab2:
        if changed_entities:
            st.markdown("**Entities with updated information:**")
            render_changed_entities(db, changed_entities)
        else:
            st.info("No changed entities detected.")
    
    # Bulk actions
    st.markdown("---")
    render_bulk_actions(db, drift_entities)

def render_new_entities(db: SandboxDB, entities: List[Dict[str, Any]]):
    """Render interface for new entities."""
    for entity in entities:
        with st.expander(f"🆕 {entity['label']} ({entity['type']})"):
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**Entity ID:** `{entity['entity_id']}`")
                st.markdown(f"**Type:** {entity['type']}")
                
                # Show entity details if available
                try:
                    if not db or not db.world_conn:
                        st.error("No database connection.")
                        continue
                    details = db.world_conn.execute("""
                        SELECT attributes_json FROM raw_db.entities 
                        WHERE id = ?
                    """, [entity['entity_id']]).fetchone()
                    if details and details[0]:
                        import json
                        try:
                            attrs = json.loads(details[0])
                            st.markdown("**Attributes:**")
                            for key, value in attrs.items():
                                st.markdown(f"• **{key}:** {value}")
                        except:
                            st.markdown(f"**Raw attributes:** {details[0]}")
                except Exception as e:
                    st.error(f"Error loading entity details: {e}")
            
            with col2:
                accept_key = f"accept_new_{entity['entity_id']}"
                if st.button("✅ Accept", key=accept_key, type="primary"):
                    db.update_sync_ledger(entity['entity_id'], accept=True, notes="Accepted new entity")
                    st.success("Accepted!")
                    st.rerun()
                
                reject_key = f"reject_new_{entity['entity_id']}"
                if st.button("❌ Ignore", key=reject_key):
                    db.update_sync_ledger(entity['entity_id'], accept=False, notes="Ignored new entity")
                    st.warning("Ignored!")
                    st.rerun()

def render_changed_entities(db: SandboxDB, entities: List[Dict[str, Any]]):
    """Render interface for changed entities."""
    for entity in entities:
        with st.expander(f"🔄 {entity['label']} ({entity['type']})"):
            
            # Get entity diff details
            try:
                if not db or not db.world_conn:
                    st.error("No database connection.")
                    continue
                current_data = db.world_conn.execute("""
                    SELECT attributes_json FROM raw_db.entities 
                    WHERE id = ?
                """, [entity['entity_id']]).fetchone()
                st.markdown("**Current Data (intel.duckdb):**")
                if current_data and current_data[0]:
                    try:
                        import json
                        attrs = json.loads(current_data[0])
                        for key, value in attrs.items():
                            st.markdown(f"• **{key}:** {value}")
                    except:
                        st.markdown(current_data[0])
                else:
                    st.markdown("*No attributes found*")
                
                # Action buttons
                col1, col2 = st.columns(2)
                
                with col1:
                    accept_key = f"accept_change_{entity['entity_id']}"
                    if st.button("✅ Accept Changes", key=accept_key, type="primary"):
                        db.update_sync_ledger(entity['entity_id'], accept=True, notes="Accepted entity changes")
                        st.success("Changes accepted!")
                        st.rerun()
                
                with col2:
                    reject_key = f"reject_change_{entity['entity_id']}"
                    if st.button("❌ Keep Old", key=reject_key):
                        db.update_sync_ledger(entity['entity_id'], accept=False, notes="Kept old entity version")
                        st.warning("Kept old version!")
                        st.rerun()
                        
            except Exception as e:
                st.error(f"Error loading entity changes: {e}")

def render_bulk_actions(db: SandboxDB, entities: List[Dict[str, Any]]):
    """Render bulk action buttons."""
    st.subheader("🔧 Bulk Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Accept All", type="primary"):
            for entity in entities:
                db.update_sync_ledger(entity['entity_id'], accept=True, notes="Bulk accept all changes")
            st.success(f"Accepted {len(entities)} entity changes!")
            st.rerun()
    
    with col2:
        if st.button("❌ Reject All"):
            for entity in entities:
                db.update_sync_ledger(entity['entity_id'], accept=False, notes="Bulk reject all changes") 
            st.warning(f"Rejected {len(entities)} entity changes!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()