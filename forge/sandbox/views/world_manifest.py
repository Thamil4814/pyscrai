"""World Manifest page - overview of all extracted entities and relationships.

Displays statistics, entity listings, and provides access to the foundational
data that will be enhanced in other Sandbox pages.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any
from forge.sandbox.session import Session

class WorldManifestPage:
    """World Manifest page implementation."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        """Render the World Manifest page."""
        st.header("🌍 World Manifest")
        st.markdown("### Foundation Intelligence Overview")
        st.markdown("This is your extracted intelligence foundation. Review the entities, relationships, and data quality before building your simulation world.")
        
        if not self.session.db:
            st.error("No database connection.")
            return
        
        try:
            # Load data
            entities_df = self._load_entities()
            relationships_df = self._load_relationships()
            
            if entities_df.empty:
                self._render_empty_state()
                return
            
            # Render sections
            self._render_summary_metrics(entities_df, relationships_df)
            self._render_entity_distribution(entities_df)
            self._render_entity_explorer(entities_df)
            self._render_relationship_overview(relationships_df)
            
        except Exception as e:
            st.error(f"❌ Error loading world manifest: {e}")
            st.code(str(e))
    
    def _load_entities(self) -> pd.DataFrame:
        """Load entities using repository method."""
        if not self.session.db:
            return pd.DataFrame()
        return self.session.db.get_entities()
    
    def _load_relationships(self) -> pd.DataFrame:
        """Load relationships using repository method."""
        if not self.session.db:
            return pd.DataFrame()
        return self.session.db.get_relationships()
    
    def _render_empty_state(self):
        """Render empty state when no data is available."""
        st.info("🔍 **No entities found**")
        st.markdown("""
        Your project doesn't have any extracted entities yet. To populate your world:
        
        1. 📄 **Add Documents:** Use the Flet Extractor to ingest documents
        2. 🤖 **Run Extraction:** Process documents to identify entities and relationships
        3. 🔄 **Return Here:** Your extracted intelligence will appear in this manifest
        
        Once you have entities, you can promote them to active agents, assign locations, and build rich simulation contexts.
        """)
    
    def _render_summary_metrics(self, entities_df: pd.DataFrame, relationships_df: pd.DataFrame):
        """Render high-level summary metrics."""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📊 Total Entities",
                len(entities_df),
                help="All extracted entities from your documents"
            )
        
        with col2:
            st.metric(
                "🔗 Total Relationships", 
                len(relationships_df),
                help="Connections between entities"
            )
        
        with col3:
            unique_types = len(entities_df['type'].unique()) if not entities_df.empty else 0
            st.metric(
                "🏷️ Entity Types",
                unique_types,
                help="Different categories of entities (PERSON, LOCATION, etc.)"
            )
        
        with col4:
            # Calculate network density
            if len(entities_df) > 1 and not relationships_df.empty:
                max_possible = len(entities_df) * (len(entities_df) - 1)
                density = round((len(relationships_df) / max_possible) * 100, 1)
                st.metric(
                    "🕸️ Network Density",
                    f"{density}%",
                    help="How interconnected your entities are"
                )
            else:
                st.metric("🕸️ Network Density", "0%")
    
    def _render_entity_distribution(self, entities_df: pd.DataFrame):
        """Render entity type distribution charts."""
        st.subheader("📈 Entity Distribution")
        
        if entities_df.empty:
            st.info("No entity data to display.")
            return
        
        # Entity type counts
        type_counts = entities_df['type'].value_counts()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Bar chart of entity types
            fig_bar = px.bar(
                x=type_counts.index,
                y=type_counts.values,
                labels={'x': 'Entity Type', 'y': 'Count'},
                title="Entities by Type"
            )
            fig_bar.update_layout(height=400)
            st.plotly_chart(fig_bar, width='stretch')
        
        with col2:
            # Pie chart 
            fig_pie = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                title="Type Distribution"
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, width='stretch')
    
    def _render_entity_explorer(self, entities_df: pd.DataFrame):
        """Render interactive entity explorer."""
        st.subheader("🔍 Entity Explorer")
        
        if entities_df.empty:
            st.info("No entities to explore.")
            return
        
        # Filters
        col1, col2 = st.columns(2)
        
        with col1:
            # Type filter
            available_types = sorted(entities_df['type'].unique())
            selected_types = st.multiselect(
                "Filter by Type",
                available_types,
                default=available_types,
                help="Select which entity types to display"
            )
        
        with col2:
            # Search filter
            search_term = st.text_input(
                "Search Entities",
                placeholder="Search by label...",
                help="Filter entities by name/label"
            )
        
        # Apply filters
        filtered_df = entities_df[entities_df['type'].isin(selected_types)]
        
        if search_term:
            filtered_df = filtered_df[
                filtered_df['label'].str.contains(search_term, case=False, na=False)
            ]
        
        # Display filtered results
        st.markdown(f"**Showing {len(filtered_df)} of {len(entities_df)} entities**")
        
        # Group by type for display
        for entity_type in selected_types:
            type_entities = filtered_df[filtered_df['type'] == entity_type]
            
            if not type_entities.empty:
                with st.expander(f"**{entity_type.title()}** ({len(type_entities)} entities)", expanded=False):
                    
                    for _, entity in type_entities.iterrows():
                        self._render_entity_card(entity)
    
    def _render_entity_card(self, entity: pd.Series):
        """Render individual entity card."""
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**🏷️ {entity['label']}**")
                st.markdown(f"*ID: {entity['id']}*")
            
            with col2:
                # Show attributes preview
                if entity['attributes_json']:
                    try:
                        import json
                        attrs = json.loads(entity['attributes_json'])
                        if attrs:
                            # Show first few attributes
                            preview_attrs = list(attrs.items())[:2]
                            for key, value in preview_attrs:
                                st.markdown(f"• **{key}:** {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}")
                            if len(attrs) > 2:
                                st.markdown(f"*...and {len(attrs) - 2} more attributes*")
                    except:
                        st.markdown("*Raw attributes available*")
            
            with col3:
                # Action buttons
                if st.button(f"👤 Make Agent", key=f"agent_{entity['id']}", help="Promote to active agent"):
                    # Set in session for navigation to Agent Forge
                    self.session.selected_entity = {
                        'id': entity['id'],
                        'label': entity['label'],
                        'type': entity['type'],
                        'is_active': False
                    }
                    st.session_state['page'] = 'agent_forge'
                    st.rerun()
            
            st.markdown("---")
    
    def _render_relationship_overview(self, relationships_df: pd.DataFrame):
        """Render relationship summary and analysis."""
        st.subheader("🔗 Relationship Overview")
        
        if relationships_df.empty:
            st.info("No relationships found.")
            return
        
        # Relationship type analysis
        rel_type_counts = relationships_df['type'].value_counts()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Top Relationship Types:**")
            for rel_type, count in rel_type_counts.head(10).items():
                st.markdown(f"• **{rel_type}:** {count} connections")
        
        with col2:
            # Confidence distribution
            st.markdown("**Confidence Distribution:**")
            if 'confidence' in relationships_df.columns:
                avg_confidence = relationships_df['confidence'].mean()
                high_conf = len(relationships_df[relationships_df['confidence'] > 0.8])
                med_conf = len(relationships_df[
                    (relationships_df['confidence'] > 0.5) & 
                    (relationships_df['confidence'] <= 0.8)
                ])
                low_conf = len(relationships_df[relationships_df['confidence'] <= 0.5])
                
                st.markdown(f"• **High (>80%):** {high_conf} relationships")
                st.markdown(f"• **Medium (50-80%):** {med_conf} relationships") 
                st.markdown(f"• **Low (≤50%):** {low_conf} relationships")
                st.markdown(f"• **Average:** {avg_confidence:.2f}")
        
        # Sample relationships
        st.markdown("**Sample Relationships:**")
        sample_rels = relationships_df.head(5)
        for _, rel in sample_rels.iterrows():
            confidence = f" ({rel['confidence']:.2f})" if 'confidence' in rel and pd.notna(rel['confidence']) else ""
            st.markdown(f"• **{rel['source']}** → *{rel['type']}* → **{rel['target']}**{confidence}")
        
        if len(relationships_df) > 5:
            st.markdown(f"*...and {len(relationships_df) - 5} more relationships*")

def render_world_manifest(session: Session):
    """Render function for the World Manifest page."""
    page = WorldManifestPage(session)
    page.render()