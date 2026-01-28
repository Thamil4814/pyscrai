"""Network Analysis page - interactive knowledge graph visualization.

Visualizes relationships between entities and provides network metrics.
"""

import streamlit as st
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config
from forge.sandbox.session import Session
from typing import Optional

class NetworkAnalysisPage:
    """Network Analysis page implementation."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def render(self):
        """Render the Network Analysis page."""
        st.header("🕸️ Network Analysis")
        st.markdown("### Knowledge Graph Visualization")
        
        if not self.session.db:
            st.error("No database connection.")
            return
            
        try:
            # Load data
            entities_df = self.session.db.get_entities()
            relationships_df = self.session.db.get_relationships()
            
            if entities_df.empty or relationships_df.empty:
                st.info("🔍 **No network data found.** Extracted entities and relationships will appear here.")
                return
            
            # Check for pre-selected entity from session
            selected_id = None
            if self.session.selected_entity:
                selected_id = self.session.selected_entity.get('id')
                st.info(f"📍 Focusing on: **{self.session.selected_entity.get('label')}**")
                if st.button("Clear Focus"):
                    self.session.selected_entity = None
                    st.rerun()

            # Filters
            self._render_filters(entities_df, relationships_df, selected_id)
            
        except Exception as e:
            st.error(f"❌ Error loading network analysis: {e}")
            st.code(str(e))
            
    def _render_filters(self, entities_df: pd.DataFrame, relationships_df: pd.DataFrame, focus_id: Optional[str] = None):
        """Render graph filters and the graph itself."""
        with st.sidebar:
            st.subheader("Graph Controls")
            
            # Entity type filter
            all_types = sorted(entities_df['type'].unique())
            selected_types = st.multiselect("Entity Types", all_types, default=all_types)
            
            # Confidence filter
            min_confidence = st.slider("Min Confidence", 0.0, 1.0, 0.4)
            
            # Relationship type filter
            all_rel_types = sorted(relationships_df['type'].unique())
            selected_rel_types = st.multiselect("Relationship Types", all_rel_types, default=all_rel_types)
            
            # Limit nodes for performance
            max_nodes = st.number_input("Max Nodes", 10, 1000, 200)

        # Filter data
        filtered_entities = entities_df[entities_df['type'].isin(selected_types)]
        filtered_relationships = relationships_df[
            (relationships_df['type'].isin(selected_rel_types)) & 
            (relationships_df['confidence'] >= min_confidence)
        ]
        
        # If focusing on a specific node, ensure it and its neighbors are included
        if focus_id:
            # Get neighbors
            relevant_rels = filtered_relationships[
                (filtered_relationships['source'] == focus_id) | 
                (filtered_relationships['target'] == focus_id)
            ]
            neighbor_ids = set(relevant_rels['source']).union(set(relevant_rels['target']))
            neighbor_ids.add(focus_id)
            
            # Filter entities to focus area
            filtered_entities = entities_df[entities_df['id'].isin(neighbor_ids)]
            filtered_relationships = relevant_rels
        else:
            # Normal filtering
            entity_ids = set(filtered_entities['id'])
            filtered_relationships = filtered_relationships[
                (filtered_relationships['source'].isin(entity_ids)) & 
                (filtered_relationships['target'].isin(entity_ids))
            ]
            
            # Apply node limit
            if len(filtered_entities) > max_nodes:
                # Prioritize entities with more connections? For now just head
                filtered_entities = filtered_entities.head(max_nodes)
                entity_ids = set(filtered_entities['id'])
                filtered_relationships = filtered_relationships[
                    (filtered_relationships['source'].isin(entity_ids)) & 
                    (filtered_relationships['target'].isin(entity_ids))
                ]
            
        self._render_graph(filtered_entities, filtered_relationships, focus_id)
        
    def _render_graph(self, entities_df: pd.DataFrame, relationships_df: pd.DataFrame, focus_id: Optional[str] = None):
        """Render the interactive graph using streamlit-agraph."""
        nodes = []
        edges = []
        
        # Color mapping for entity types
        type_colors = {
            "PERSON": "#1f77b4",   # Blue
            "ORGANIZATION": "#ff7f0e", # Orange
            "LOCATION": "#2ca02c", # Green
            "EVENT": "#d62728",    # Red
            "UNKNOWN": "#7f7f7f"   # Gray
        }
        
        # Create Nodes
        for _, row in entities_df.iterrows():
            e_type = row['type']
            color = type_colors.get(e_type, "#9467bd") # Purple for others
            
            nodes.append(Node(
                id=row['id'],
                label=row['label'],
                size=15,
                color=color,
                title=f"Type: {e_type}"
            ))
            
        # Create Edges
        for _, row in relationships_df.iterrows():
            edges.append(Edge(
                source=row['source'],
                target=row['target'],
                label=row['type'],
                title=f"Confidence: {row['confidence']:.2f}"
            ))
            
        config = Config(
            width=1000,
            height=600,
            directed=True,
            physics=True,
            hierarchical=False,
            # **{"interaction": {"hover": True}}
        )
        
        return_value = agraph(nodes=nodes, edges=edges, config=config)
        
        if return_value:
            st.info(f"Selected: {return_value}")
            # Could show details of selected node here

def render_network_analysis(session: Session):
    """Render function for the Network Analysis page."""
    page = NetworkAnalysisPage(session)
    page.render()
