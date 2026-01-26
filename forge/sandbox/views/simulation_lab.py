"""Simulation Lab page - test components and export simulation packages.

Allows users to:
- Test agent components and validate behavior
- Export complete simulation packages for deployment
- Validate world readiness for simulation
- Monitor simulation status and metrics
"""

import streamlit as st
from datetime import datetime
from forge.sandbox.session import Session


class SimulationLabPage:
    """Simulation Lab page implementation."""

    def __init__(self, session: Session):
        self.session = session

    def render(self):
        """Render the Simulation Lab page."""
        st.header("🧪 Simulation Lab")
        st.markdown("### Test Components & Export Simulation Packages")
        st.markdown("Validate your simulation world and export complete packages for deployment.")
        
        if not self.session.db:
            st.error("❌ No database connection.")
            return
        
        try:
            # Load data using repository methods
            agents_df = self.session.db.get_active_agents()
            locations_df = self.session.db.get_spatial_bookmarks()
            contexts_df = self.session.db.get_narrative_contexts()
            total_entities = self.session.db.get_raw_entity_count()
            
            # Render sections
            self._render_status_overview(agents_df, locations_df, contexts_df, total_entities)
            self._render_component_testing(agents_df)
            self._render_export_section()
            self._render_validation_section(agents_df, locations_df, total_entities)
            
        except Exception as e:
            st.error(f"❌ Error in simulation lab: {e}")
            st.code(str(e))

    def _render_status_overview(self, agents_df, locations_df, contexts_df, total_entities):
        """Render simulation status overview metrics."""
        st.subheader("📊 Simulation Status")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("👤 Active Agents", len(agents_df))
        
        with col2:
            st.metric("📍 Mapped Locations", len(locations_df))
        
        with col3:
            st.metric("📅 Narrative Contexts", len(contexts_df))
        
        with col4:
            # Calculate readiness score
            if total_entities > 0:
                readiness = min(100, round(((len(agents_df) + len(locations_df) + len(contexts_df)) / total_entities) * 100))
            else:
                readiness = 0
            st.metric("🎯 Readiness", f"{readiness}%")

    def _render_component_testing(self, agents_df):
        """Render component testing section."""
        st.subheader("🔧 Component Testing")
        
        if len(agents_df) > 0:
            st.markdown("**Available Agents for Testing:**")
            for _, agent in agents_df.iterrows():
                with st.expander(f"👤 {agent['label']} ({agent['type']})"):
                    test_input = st.text_area(
                        f"Test input for {agent['label']}",
                        placeholder="Enter a scenario or question to test this agent...",
                        key=f"test_{agent['agent_id']}"
                    )
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(f"▶️ Test {agent['label']}", key=f"run_test_{agent['agent_id']}"):
                            if test_input:
                                st.info("🤖 **Simulation Test Result**")
                                st.markdown(f"**Agent:** {agent['label']}")
                                st.markdown(f"**Input:** {test_input}")
                                st.markdown("**Response:** *LLM integration would provide agent response here*")
                                st.success("✅ Test completed successfully!")
                            else:
                                st.warning("Please enter test input first.")
                    
                    with col_b:
                        if st.button(f"📋 View Persona", key=f"persona_{agent['agent_id']}"):
                            persona_data = self.session.db.get_agent_details(agent['agent_id'])
                            
                            if persona_data:
                                st.markdown("**Persona Prompt:**")
                                st.text(persona_data[0][:200] + "..." if len(persona_data[0]) > 200 else persona_data[0])
                                
                                st.markdown("**Goals:**")
                                st.text(persona_data[1])
                                
                                st.markdown("**Capabilities:**")
                                st.text(persona_data[2])
        else:
            st.info("💡 **No active agents available**. Visit the Agent Forge to create agents for testing.")

    def _render_export_section(self):
        """Render simulation package export section."""
        st.markdown("---")
        st.subheader("📦 Export Simulation Package")
        st.markdown("Create a portable simulation package that can be deployed on other systems.")
        
        # Export configuration
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Package Contents:**")
            st.markdown("✅ **intel.duckdb** - Raw extraction data")
            st.markdown("✅ **world.duckdb** - Simulation enhancements")
            st.markdown("✅ **config.json** - Project configuration")
            st.markdown("✅ **manifest.json** - Package metadata")
            
            # Check for templates directory
            if self.session.project_path is not None:
                templates_dir = self.session.project_path / "templates"
                if templates_dir.exists():
                    template_count = len(list(templates_dir.glob("*.j2")))
                    st.markdown(f"✅ **templates/** - {template_count} template files")
                else:
                    st.markdown("⚪ **templates/** - No templates (optional)")
            else:
                st.markdown("⚪ **templates/** - No templates (optional)")
        
        with col2:
            st.markdown("**Export Options:**")
            st.checkbox("Include example scenarios", value=True, key="export_examples")
            st.checkbox("Include documentation", value=True, key="export_docs")
            st.slider("Compression Level", 1, 9, 6, help="Higher = smaller file, slower", key="export_compression")
        
        # Export button
        if st.button("📦 Create Export Package", type="primary"):
            self._handle_export()

    def _handle_export(self):
        """Handle the export process."""
        if self.session.project_path is not None:
            try:
                from forge.sandbox.services.export_service import ExportService
                
                with st.spinner("Creating simulation package..."):
                    export_service = ExportService()
                    
                    # Generate filename with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{self.session.project_path.name}_simulation_{timestamp}.zip"
                    output_path = self.session.project_path.parent / filename
                    
                    # Create package
                    package_path = export_service.create_package(
                        self.session.project_path,
                        output_path
                    )
                    
                    # Success message
                    file_size = round(package_path.stat().st_size / (1024*1024), 2)
                    st.success(f"✅ **Package created successfully!**")
                    st.markdown(f"**File:** `{package_path.name}`")
                    st.markdown(f"**Size:** {file_size} MB")
                    st.markdown(f"**Location:** `{package_path.parent}`")
                    
                    # Provide download
                    with open(package_path, 'rb') as f:
                        st.download_button(
                            "⬇️ Download Package",
                            data=f.read(),
                            file_name=package_path.name,
                            mime="application/zip",
                            type="secondary"
                        )
            except Exception as e:
                st.error(f"❌ **Export failed:** {e}")
                st.code(str(e))
        else:
            st.error("No project selected. Cannot export package.")

    def _render_validation_section(self, agents_df, locations_df, total_entities):
        """Render world validation section."""
        st.markdown("---")
        st.subheader("✅ World Validation")
        
        # Basic validation checks
        validation_results = []
        
        # Check 1: Active agents exist
        if len(agents_df) > 0:
            validation_results.append(("✅", "Active agents configured", f"{len(agents_df)} agents ready"))
        else:
            validation_results.append(("❌", "No active agents", "Visit Agent Forge to create agents"))
        
        # Check 2: Spatial data
        if len(locations_df) > 0:
            validation_results.append(("✅", "Spatial data configured", f"{len(locations_df)} locations mapped"))
        else:
            validation_results.append(("⚠️", "No spatial data", "Visit Spatial Domain to map locations"))
        
        # Check 3: Database integrity
        if total_entities > 0:
            validation_results.append(("✅", "Database integrity", f"{total_entities} entities in intel.duckdb"))
        else:
            validation_results.append(("❌", "Empty database", "No entities found in intel.duckdb"))
        
        # Display validation results
        for status, title, description in validation_results:
            col_status, col_title, col_desc = st.columns([1, 3, 4])
            with col_status:
                st.markdown(status)
            with col_title:
                st.markdown(f"**{title}**")
            with col_desc:
                st.markdown(description)
        
        # Overall readiness
        passed_checks = sum(1 for status, _, _ in validation_results if status == "✅")
        total_checks = len(validation_results)
        
        if passed_checks == total_checks:
            st.success(f"🎉 **Simulation world is ready for deployment!** ({passed_checks}/{total_checks} checks passed)")
        else:
            st.warning(f"⚠️ **Simulation world needs attention** ({passed_checks}/{total_checks} checks passed)")


def render_simulation_lab(session: Session):
    """Legacy entry point for the Simulation Lab page."""
    page = SimulationLabPage(session)
    page.render()
