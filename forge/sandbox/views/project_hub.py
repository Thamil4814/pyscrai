import streamlit as st
from pathlib import Path
import json
import duckdb

class ProjectHub:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent.parent.resolve()
        self.projects_root = self.base_dir / "forge" / "data" / "projects"
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def render(self, session):
        st.title("📂 Project Hub")
        st.markdown("Select an existing simulation environment or forge a new one.")

        tab_load, tab_create = st.tabs(["Load Project", "Create New"])

        with tab_load:
            self._render_load_tab(session)
        
        with tab_create:
            self._render_create_tab(session)

    def _render_load_tab(self, session):
        projects = [p for p in self.projects_root.iterdir() if p.is_dir()]
        
        if not projects:
            st.warning("No projects found.")
            return

        for p in projects:
            col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
            with col1:
                st.markdown(f"**{p.name}**")
                st.caption(f"Path: {p}")
            with col2:
                if st.button("Load", key=f"btn_load_{p.name}", use_container_width=True):
                    session.load_project(p)
                    st.rerun()
            with col3:
                delete_style = """
                    <style>
                    .stButton > button[data-testid='baseButton'][key^='btn_delete_'] {
                        background-color: #ff4d4f;
                        color: white;
                        border: 1px solid #ff4d4f;
                    }
                    </style>
                """
                st.markdown(delete_style, unsafe_allow_html=True)
                confirm_key = f"confirm_delete_{p.name}"
                if st.session_state.get(confirm_key):
                    if st.button("Are you sure? Click to confirm", key=f"btn_confirm_delete_{p.name}", use_container_width=True):
                        import shutil
                        try:
                            shutil.rmtree(p)
                            st.success(f"Deleted project {p.name}")
                            del st.session_state[confirm_key]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete: {e}")
                else:
                    if st.button("Delete", key=f"btn_delete_{p.name}", use_container_width=True):
                        st.session_state[confirm_key] = True
                
            st.divider()

    def _render_create_tab(self, session):
        with st.form("new_project_form"):
            name = st.text_input("Project Name", placeholder="e.g. Operation_Red_Sky")
            submitted = st.form_submit_button("Create Project")
            
            if submitted and name:
                safe_name = "".join([c for c in name if c.isalnum() or c in ('_', '-')])
                new_path = self.projects_root / safe_name
                
                if new_path.exists():
                    st.error("Project already exists!")
                else:
                    self._create_structure(new_path)
                    st.success(f"Created {safe_name}")
                    session.load_project(new_path)
                    st.rerun()

    def _create_structure(self, path: Path):
        path.mkdir(parents=True)
        (path / "source_docs").mkdir()
        
        conn = duckdb.connect(str(path / "world.duckdb"))
        conn.close()
        
        with open(path / "config.json", "w") as f:
            json.dump({"name": path.name, "version": "1.0"}, f)
