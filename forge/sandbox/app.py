import streamlit as st
from forge.sandbox.session import Session
from forge.sandbox.views.project_hub import ProjectHub
from forge.sandbox.views.extraction_lab import ExtractionLab
from forge.sandbox.views.world_manifest import WorldManifestPage
from forge.sandbox.views.agent_forge import AgentForgePage
from forge.sandbox.views.simulation_lab import SimulationLabPage

st.set_page_config(page_title="Unified Forge", page_icon="🛠️", layout="wide")

def main():
    session = Session()
    session.initialize()

    if not session.project_path:
        ProjectHub().render(session)
    
    else:
        with st.sidebar:
            st.caption(f"Active: {session.project_path.name}")
            
            nav_selection = st.radio(
                "Module",
                options=[
                    "Extraction Lab",
                    "World Manifest",
                    "Agent Forge",
                    "Simulation Lab"
                ],
                key="main_nav"
            )
            
            st.divider()
            if st.button("Close Project", icon="🚪"):
                session.clear_project()
                st.rerun()

        if nav_selection == "Extraction Lab":
            ExtractionLab().render(session)
        elif nav_selection == "World Manifest":
            page = WorldManifestPage(session)
            page.render()
        elif nav_selection == "Agent Forge":
            page = AgentForgePage(session)
            page.render()
        elif nav_selection == "Simulation Lab":
            page = SimulationLabPage(session)
            page.render()

if __name__ == "__main__":
    main()
