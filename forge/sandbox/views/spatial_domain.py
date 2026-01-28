"""Spatial Domain page - assign coordinates and spatial context to locations.

Allows users to:
- Assign GPS coordinates to location entities
- Add elevation and spatial tags
- View locations on interactive maps
- Define environmental context for simulation
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from forge.sandbox.session import Session


class SpatialDomainPage:
    """Spatial Domain page implementation."""

    def __init__(self, session: Session):
        self.session = session

    def render(self):
        """Render the Spatial Domain page."""
        st.header("📍 Spatial Domain")
        st.markdown("### Location Mapping & Spatial Context")
        
        if not self.session.db:
            st.error("No database connection.")
            return
        
        try:
            # Load data
            entities_df = self.session.db.get_entities()
            bookmarks_df = self.session.db.get_spatial_bookmarks()
            
            if entities_df.empty:
                st.info("🔍 **No entities found.** Extract some locations first.")
                return
            
            # Filter for locations
            locations_df = entities_df[entities_df['type'] == 'LOCATION']
            
            if locations_df.empty:
                st.info("🔍 **No location entities found.**")
                return
            
            # Merge with bookmarks to see which locations have coordinates
            if not bookmarks_df.empty:
                merged_df = locations_df.merge(
                    bookmarks_df, 
                    left_on='id', 
                    right_on='location_id', 
                    how='left'
                )
            else:
                merged_df = locations_df.copy()
                merged_df['latitude'] = None
                merged_df['longitude'] = None
                merged_df['elevation'] = None
                merged_df['spatial_tags'] = None
            
            # Layout
            col1, col2 = st.columns([1, 2])
            
            with col1:
                self._render_location_editor(merged_df)
            
            with col2:
                self._render_map(merged_df)
                
        except Exception as e:
            st.error(f"❌ Error loading spatial domain: {e}")
            st.code(str(e))

    def _render_location_editor(self, df: pd.DataFrame):
        """Render the location selection and coordinate editor."""
        st.subheader("Location Editor")
        
        # Determine initial selection
        initial_index = 0
        if self.session.selected_entity and self.session.selected_entity['type'] == 'LOCATION':
            selected_label = self.session.selected_entity['label']
            if selected_label in df['label'].values:
                initial_index = df[df['label'] == selected_label].index[0]
                # Reset selected entity once we've used it for navigation?
                # Or keep it so it stays selected in the dropdown.
                # Actually, index in selectbox is based on the list of options.
                labels = df['label'].tolist()
                try:
                    initial_index = labels.index(selected_label)
                except ValueError:
                    initial_index = 0

        selected_label = st.selectbox(
            "Select Location to Edit",
            options=df['label'].tolist(),
            index=initial_index
        )
        
        # Clear focused entity button if one exists
        if self.session.selected_entity:
            if st.button("Clear Navigation Focus"):
                self.session.selected_entity = None
                st.rerun()

        location_data = df[df['label'] == selected_label].iloc[0]
        loc_id = location_data['id']
        
        with st.form(key=f"spatial_form_{loc_id}"):
            st.markdown(f"**Editing:** {selected_label} (`{loc_id}`)")
            
            # Current values or defaults
            curr_lat = location_data['latitude'] if pd.notna(location_data['latitude']) else 0.0
            curr_lon = location_data['longitude'] if pd.notna(location_data['longitude']) else 0.0
            curr_elev = location_data['elevation'] if pd.notna(location_data['elevation']) else 0.0
            curr_tags = location_data['spatial_tags'] if pd.notna(location_data['spatial_tags']) else ""
            
            lat = st.number_input("Latitude", value=float(curr_lat), format="%.6f")
            lon = st.number_input("Longitude", value=float(curr_lon), format="%.6f")
            elev = st.number_input("Elevation (m)", value=float(curr_elev))
            tags = st.text_input("Spatial Tags (comma separated)", value=curr_tags)
            
            submit = st.form_submit_button("Save Spatial Bookmark")
            
            if submit:
                if self.session.db is not None:
                    self.session.db.save_spatial_bookmark(
                        location_id=loc_id,
                        latitude=lat,
                        longitude=lon,
                        elevation=elev,
                        tags=tags
                    )
                    st.success(f"Saved bookmark for {selected_label}")
                    st.rerun()
                else:
                    st.error("No database connection. Cannot save bookmark.")

    def _render_map(self, df: pd.DataFrame):
        """Render interactive map with bookmarked locations."""
        st.subheader("World Map")
        
        # Filter for locations that actually have coordinates
        map_data = df[df['latitude'].notna() & df['longitude'].notna()]
        
        if map_data.empty:
            st.info("No locations with coordinates yet. Use the editor to add some!")
            return
            
        # Create map
        center_lat = map_data['latitude'].mean()
        center_lon = map_data['longitude'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=4)
        
        # Add markers
        for _, row in map_data.iterrows():
            popup_text = f"<b>{row['label']}</b><br>Elev: {row['elevation']}m<br>Tags: {row['spatial_tags']}"
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=popup_text,
                tooltip=row['label']
            ).add_to(m)
            
        st_folium(m, width=700, height=500)


def render_spatial_domain(session: Session):
    """Render the Spatial Domain page."""
    page = SpatialDomainPage(session)
    page.render()
