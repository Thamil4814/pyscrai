"""Session state management wrapper for Streamlit applications.

Provides type-safe access to st.session_state and centralized initialization
for complex sandbox state including database connections and project data.
"""

import streamlit as st
from typing import Optional, Dict, Any
from pathlib import Path

class Session:
    """Wrapper around st.session_state for type safety and centralized management."""
    
    @property
    def project_path(self) -> Optional[Path]:
        """Get current project path."""
        path_str = st.session_state.get('project_path')
        return Path(path_str) if path_str else None
    
    @project_path.setter
    def project_path(self, value: Optional[Path]):
        """Set current project path."""
        st.session_state['project_path'] = str(value) if value else None
    
    @property
    def db(self):
        """Get sandbox database connection using cached resource."""
        if self.project_path:
            from forge.sandbox.services.db_manager import get_db_connection
            return get_db_connection(self.project_path)
        return None
    
    @db.setter
    def db(self, value):
        """No longer used as db is managed via st.cache_resource."""
        pass
    
    @property
    def sync_status(self) -> Dict[str, Any]:
        """Get sync status (deprecated)."""
        return st.session_state.get('sync_status', {'drift_detected': False, 'entities': []})
    
    @sync_status.setter
    def sync_status(self, value: Dict[str, Any]):
        """Set sync status (deprecated)."""
        st.session_state['sync_status'] = value
    
    @property
    def user_preferences(self) -> Dict[str, Any]:
        """Get user preferences."""
        return st.session_state.get('user_preferences', {})
    
    @user_preferences.setter
    def user_preferences(self, value: Dict[str, Any]):
        """Set user preferences."""
        st.session_state['user_preferences'] = value
    
    @property
    def selected_entity(self) -> Optional[Dict[str, Any]]:
        """Get currently selected entity for editing."""
        return st.session_state.get('selected_entity')
    
    @selected_entity.setter
    def selected_entity(self, value: Optional[Dict[str, Any]]):
        """Set currently selected entity."""
        st.session_state['selected_entity'] = value
    
    def initialize(self):
        """Initialize session with default values."""
        if 'initialized' not in st.session_state:
            st.session_state['initialized'] = True
            st.session_state['project_path'] = None
            st.session_state['user_preferences'] = {}
            st.session_state['selected_entity'] = None
    
    def reset_project(self):
        """Reset project-specific session state while keeping preferences."""
        keys_to_remove = ['project_path', 'selected_entity']
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
    
    def clear_all(self):
        """Reset all session state."""
        keys_to_remove = ['project_path', 'user_preferences', 'selected_entity']
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
    
    def load_project(self, project_path: Path):
        """Load a project and update session state."""
        self.project_path = project_path
        st.cache_resource.clear()
    
    def clear_project(self):
        """Clear the current project from session."""
        self.reset_project()
        st.cache_resource.clear()