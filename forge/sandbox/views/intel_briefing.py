"""Intelligence Briefing page - high-level narratives and document metadata.

Provides an executive summary of the extracted intelligence.
"""

import streamlit as st
import pandas as pd
from forge.sandbox.session import Session

class IntelligenceBriefingPage:
    """Intelligence Briefing page implementation."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        """Render the Intelligence Briefing page."""
        st.header("📋 Intelligence Briefing")
        st.markdown("### Executive Summary & Narratives")
        
        if not self.session.db:
            st.error("No database connection.")
            return
            
        try:
            # Load data
            narratives_df = self.session.db.get_narratives()
            metadata_df = self.session.db.get_document_metadata()
            
            if narratives_df.empty:
                st.info("🔍 **No narratives found.** Run the extraction pipeline to generate summaries.")
                return
                
            # Render sections
            self._render_narrative_list(narratives_df, metadata_df)
            
        except Exception as e:
            st.error(f"❌ Error loading intelligence briefing: {e}")
            st.code(str(e))
            
    def _render_narrative_list(self, narratives_df: pd.DataFrame, metadata_df: pd.DataFrame):
        """Render the list of document narratives with metadata."""
        st.subheader("📄 Document Narratives")
        
        for _, row in narratives_df.iterrows():
            doc_id = row['doc_id']
            # Find matching metadata
            metadata = metadata_df[metadata_df['doc_id'] == doc_id] if not metadata_df.empty else pd.DataFrame()
            
            with st.expander(f"**Document: {doc_id}**", expanded=True):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("**Narrative Summary:**")
                    st.write(row['narrative'])
                    
                    st.markdown(f"*Entities: {row['entity_count']} | Relationships: {row['relationship_count']}*")
                
                with col2:
                    if not metadata.empty:
                        m = metadata.iloc[0]
                        st.markdown("**Metadata:**")
                        if m['classification']:
                            st.info(f"**{m['classification']}**")
                        if m['report_id']:
                            st.markdown(f"**ID:** {m['report_id']}")
                        if m['date']:
                            st.markdown(f"**Date:** {m['date']}")
                        if m['authoring_unit']:
                            st.markdown(f"**Unit:** {m['authoring_unit']}")
                        if m['zone']:
                            st.markdown(f"**Zone:** {m['zone']}")
                    else:
                        st.caption("No metadata available")

def render_intel_briefing(session: Session):
    """Render function for the Intelligence Briefing page."""
    page = IntelligenceBriefingPage(session)
    page.render()
