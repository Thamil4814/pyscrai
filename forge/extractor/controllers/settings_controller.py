"""Settings Controller - Graphical config.json editor."""

from __future__ import annotations

import asyncio
import json
import logging
import yaml
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import flet as ft

from forge.shared.core.service_registry import get_session_manager

if TYPE_CHECKING:
    from forge.extractor.state.app_state import AppState

logger = logging.getLogger(__name__)


class SettingsController:
    """Controller for editing project configuration."""

    def __init__(self, app_state: AppState, page: ft.Page):
        self.app_controller = app_state
        self.page = page
        self._config_data: Optional[Dict[str, Any]] = None
        self._config_inputs: Dict[str, ft.Control] = {}
        self._current_section = "llm"
        self._cached_views: Dict[str, ft.Control] = {}
        self._settings_content_container: Optional[ft.Container] = None
        self._buttons_wrapper: Optional[ft.Container] = None

    def build_view(self) -> ft.Control:
        """Build the settings editor interface with improved layout."""
        
        # Load current configuration
        self._config_data = self._load_current_config()
        
        if not self._config_data:
            return self._build_no_project_view()
        
        # Build section navigation buttons
        self._buttons_wrapper = ft.Container(content=self._build_section_buttons())
        
        # Build content area for current section
        self._settings_content_container = ft.Container(
            expand=True,
            content=self._build_content_area()
        )
        
        # Action buttons
        action_buttons = ft.Row(
            [
                ft.ElevatedButton(
                    "Save Configuration",
                    icon=ft.Icons.SAVE,
                    on_click=lambda e: asyncio.create_task(self._save_config()),
                    bgcolor=ft.Colors.BLUE_700,
                    color=ft.Colors.WHITE,
                    expand=True,
                ),
                ft.OutlinedButton(
                    "Reset to Defaults",
                    icon=ft.Icons.REFRESH,
                    on_click=lambda e: self._reset_to_defaults(),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE70,
                    ),
                ),
                ft.OutlinedButton(
                    "Reload from File",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: self._reload_config(),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE70,
                    ),
                ),
            ],
            spacing=10,
        )
        
        # Main container with proper layout - using expand=True and ScrollMode.AUTO
        return ft.Container(
            padding=20,
            expand=True,
            content=ft.Column(
                [
                    # Header
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.SETTINGS, size=32, color=ft.Colors.CYAN_300),
                            ft.Text(
                                "Project Configuration",
                                size=24,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    
                    ft.Divider(color="rgba(255, 255, 255, 0.1)", height=20),
                    
                    # Action buttons
                    action_buttons,
                    
                    ft.Container(height=10),
                    
                    # Section navigation
                    self._buttons_wrapper,
                    
                    ft.Divider(color="rgba(255, 255, 255, 0.1)", height=10),
                    
                    # Content area (scrollable)
                    self._settings_content_container,
                ],
                spacing=8,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    def _build_section_buttons(self) -> ft.Control:
        """Build the section navigation buttons."""
        sections = [
            ("llm", "LLM", ft.Icons.CLOUD),
            ("vector", "Vector DB", ft.Icons.STORAGE),
            ("database", "Database", ft.Icons.DATA_OBJECT),
            ("embedding", "Embedding", ft.Icons.PSYCHOLOGY),
            ("ui", "UI", ft.Icons.PALETTE),
            ("processing", "Processing", ft.Icons.SETTINGS_SUGGEST),
        ]
        
        buttons = []
        for section_id, label, icon in sections:
            is_selected = self._current_section == section_id
            # Create a closure to capture the section_id properly
            def make_callback(s):
                return lambda e: asyncio.create_task(self._on_section_change(s))
            
            button = ft.Container(
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                border_radius=8,
                bgcolor="rgba(255, 255, 255, 0.03)" if not is_selected else "rgba(72, 176, 247, 0.2)",
                border=ft.border.all(1, "rgba(255, 255, 255, 0.1)" if not is_selected else "rgba(72, 176, 247, 0.5)"),
                on_click=make_callback(section_id),
                ink=True,
                content=ft.Row(
                    [
                        ft.Icon(icon, size=18, color=ft.Colors.CYAN_400 if is_selected else ft.Colors.WHITE70),
                        ft.Text(
                            label,
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.WHITE if is_selected else ft.Colors.WHITE70,
                        ),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            )
            buttons.append(button)
        
        return ft.Container(
            padding=0,
            content=ft.Row(
                buttons,
                spacing=8,
                wrap=True,
                alignment=ft.MainAxisAlignment.START,
            ),
        )

    async def _on_section_change(self, section: str) -> None:
        """Handle section change from button click."""
        # Preserve current changes
        if self._config_data:
            try:
                self._config_data = self._build_config_from_inputs()
            except Exception as e:
                logger.error(f"Error preserving config state: {e}")

        self._current_section = section

        # Update UI
        if self._buttons_wrapper:
            self._buttons_wrapper.content = self._build_section_buttons()

        if self._settings_content_container:
            self._settings_content_container.content = self._build_content_area()

        try:
            self.page.update()
        except RuntimeError:
            # Ignore runtime errors during shutdown
            pass

    def _build_content_area(self) -> ft.Control:
        """Build the content area for the current section."""
        if not self._config_data:
            return ft.Container()
        
        section_builders = {
            "llm": self._build_llm_content,
            "vector": self._build_vector_content,
            "database": self._build_database_content,
            "embedding": self._build_embedding_content,
            "ui": self._build_ui_content,
            "processing": self._build_processing_content,
        }
        
        builder = section_builders.get(self._current_section, self._build_llm_content)
        content = builder()
        
        return ft.Container(
            expand=True,
            padding=10,
            content=ft.Column(
                [content],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        )

    def _build_llm_content(self) -> ft.Control:
        """Build LLM configuration content."""
        llm_config = (self._config_data or {}).get("llm", {})
        
        # Provider settings in a card
        provider_card = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("Provider Settings", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    ft.Row(
                        [
                            self._create_dropdown_input(
                                "llm.default_provider",
                                "Default Provider",
                                llm_config.get("default_provider", "openrouter"),
                                ["openrouter", "lm_proxy", "cherry", "lm_studio"],
                                width=200,
                            ),
                            self._create_dropdown_input(
                                "llm.secondary_provider",
                                "Secondary Provider",
                                llm_config.get("secondary_provider", "openrouter"),
                                ["openrouter", "lm_proxy", "cherry", "lm_studio"],
                                width=200,
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                    ft.Row(
                        [
                            self._create_dropdown_input(
                                "llm.semantic_provider",
                                "Semantic Provider",
                                llm_config.get("semantic_provider", "openrouter"),
                                ["openrouter", "lm_proxy", "cherry", "lm_studio"],
                                width=200,
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=12,
            ),
        )
        
        # Rate limiting in a card
        rate_limit_card = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("Rate Limiting", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    ft.Row(
                        [
                            self._create_number_input(
                                "llm.rate_limit_max_concurrent",
                                "Max Concurrent",
                                llm_config.get("rate_limit_max_concurrent", 1),
                                min_val=1,
                                max_val=20,
                                width=180,
                            ),
                            self._create_number_input(
                                "llm.rate_limit_min_delay",
                                "Min Delay (s)",
                                llm_config.get("rate_limit_min_delay", 2.0),
                                min_val=0.1,
                                max_val=60.0,
                                is_float=True,
                                width=180,
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
        )
        
        # Model parameters in a card
        model_params_card = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("Model Parameters", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    ft.Row(
                        [
                            self._create_number_input(
                                "llm.entity_extraction_max_tokens",
                                "Entity Tokens",
                                llm_config.get("entity_extraction_max_tokens", 2000),
                                min_val=100,
                                max_val=8000,
                                width=180,
                            ),
                            self._create_number_input(
                                "llm.entity_extraction_temperature",
                                "Temperature",
                                llm_config.get("entity_extraction_temperature", 0.3),
                                min_val=0.0,
                                max_val=2.0,
                                is_float=True,
                                width=180,
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
        )
        
        return ft.Column(
            [
                provider_card,
                rate_limit_card,
                model_params_card,
            ],
            spacing=12,
        )

    def _build_vector_content(self) -> ft.Control:
        """Build Vector DB configuration content."""
        vector_config = (self._config_data or {}).get("vector", {})
        
        content = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("Vector Database Settings", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    self._create_text_input(
                        "vector.url",
                        "Qdrant URL",
                        vector_config.get("url", ":memory:"),
                    ),
                    ft.Row(
                        [
                            self._create_number_input(
                                "vector.similarity_search_threshold",
                                "Similarity Threshold",
                                vector_config.get("similarity_search_threshold", 0.7),
                                min_val=0.0,
                                max_val=1.0,
                                is_float=True,
                                width=220,
                            ),
                            self._create_number_input(
                                "vector.deduplication_threshold",
                                "Deduplication Threshold",
                                vector_config.get("deduplication_threshold", 0.85),
                                min_val=0.0,
                                max_val=1.0,
                                is_float=True,
                                width=220,
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
        )
        
        return content

    def _build_database_content(self) -> ft.Control:
        """Build Database configuration content."""
        db_config = (self._config_data or {}).get("database", {})
        
        content = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("Database Settings", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    ft.TextField(
                        label="Database Path",
                        value=db_config.get("db_path", ""),
                        read_only=True,
                        border_color="rgba(255,255,255,0.2)",
                        hint_text="Read-only: Managed by project system",
                        multiline=True,
                        max_lines=2,
                        text_style=ft.TextStyle(color=ft.Colors.WHITE),
                    ),
                    ft.Row(
                        [
                            self._create_number_input(
                                "database.connection_timeout",
                                "Connection Timeout (s)",
                                db_config.get("connection_timeout", 30.0),
                                min_val=1.0,
                                max_val=300.0,
                                is_float=True,
                                width=220,
                            ),
                            self._create_checkbox_input(
                                "database.wal_mode",
                                "WAL Mode",
                                db_config.get("wal_mode", True),
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
        )
        
        return content

    def _build_embedding_content(self) -> ft.Control:
        """Build Embedding configuration content."""
        embed_config = (self._config_data or {}).get("embedding", {})
        
        content = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("Embedding Settings", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    ft.Row(
                        [
                            self._create_dropdown_input(
                                "embedding.device",
                                "Device",
                                embed_config.get("device", "cuda"),
                                ["cuda", "cpu"],
                                width=180,
                            ),
                            self._create_number_input(
                                "embedding.batch_size",
                                "Batch Size",
                                embed_config.get("batch_size", 32),
                                min_val=1,
                                max_val=256,
                                width=180,
                            ),
                        ],
                        spacing=12,
                    ),
                    self._create_text_input(
                        "embedding.general_model",
                        "General Model",
                        embed_config.get("general_model", "BAAI/bge-base-en-v1.5"),
                    ),
                ],
                spacing=12,
            ),
        )
        
        return content

    def _build_ui_content(self) -> ft.Control:
        """Build UI configuration content."""
        ui_config = (self._config_data or {}).get("ui", {})
        
        content = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("UI Settings", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    ft.Row(
                        [
                            self._create_checkbox_input(
                                "ui.flet_web_mode",
                                "Web Mode",
                                ui_config.get("flet_web_mode", True),
                            ),
                            self._create_number_input(
                                "ui.flet_port",
                                "Port",
                                ui_config.get("flet_port", 8550),
                                min_val=1024,
                                max_val=65535,
                                width=180,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Row(
                        [
                            self._create_dropdown_input(
                                "ui.theme_mode",
                                "Theme",
                                ui_config.get("theme_mode", "dark"),
                                ["dark", "light"],
                                width=180,
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=12,
            ),
        )
        
        return content

    def _build_processing_content(self) -> ft.Control:
        """Build Processing configuration content."""
        proc_config = (self._config_data or {}).get("processing", {})
        
        content = ft.Container(
            padding=16,
            bgcolor="rgba(255, 255, 255, 0.03)",
            border_radius=8,
            border=ft.border.all(1, "rgba(255, 255, 255, 0.1)"),
            content=ft.Column(
                [
                    ft.Text("Processing Settings", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_200),
                    ft.Row(
                        [
                            self._create_checkbox_input(
                                "processing.auto_deduplication",
                                "Auto Deduplication",
                                proc_config.get("auto_deduplication", True),
                            ),
                            self._create_checkbox_input(
                                "processing.auto_relationship_inference",
                                "Auto Relationship",
                                proc_config.get("auto_relationship_inference", True),
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Row(
                        [
                            self._create_checkbox_input(
                                "processing.parallel_processing",
                                "Parallel Processing",
                                proc_config.get("parallel_processing", False),
                            ),
                            self._create_number_input(
                                "processing.semantic_profiler_delay",
                                "Profiler Delay (s)",
                                proc_config.get("semantic_profiler_delay", 0.3),
                                min_val=0.0,
                                max_val=5.0,
                                is_float=True,
                                width=200,
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=12,
            ),
        )
        
        return content

    def _create_text_input(
        self,
        key: str,
        label: str,
        value: Any,
        width: Optional[int] = None,
        password: bool = False,
    ) -> ft.TextField:
        """Create a text input field for configuration."""
        text_field = ft.TextField(
            label=label,
            value=str(value) if value is not None else "",
            password=password,  # type: ignore[arg-type]
            can_reveal_password=password,  # type: ignore[arg-type]
            border_color="rgba(255,255,255,0.2)",
            width=width,
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )
        self._config_inputs[key] = text_field
        return text_field

    def _create_number_input(
        self,
        key: str,
        label: str,
        value: Any,
        min_val: float = 0,
        max_val: float = 100,
        is_float: bool = False,
        width: Optional[int] = None,
    ) -> ft.TextField:
        """Create a number input field for configuration."""
        text_field = ft.TextField(
            label=label,
            value=str(value) if value is not None else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color="rgba(255,255,255,0.2)",
            width=width,
            hint_text=f"Range: {min_val} - {max_val}",
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )
        self._config_inputs[key] = text_field
        return text_field

    def _create_dropdown_input(
        self,
        key: str,
        label: str,
        value: Any,
        options: List[str],
        width: Optional[int] = None,
    ) -> ft.Dropdown:
        """Create a dropdown input for configuration."""
        dropdown = ft.Dropdown(  # type: ignore[call-arg]
            label=label,  # type: ignore[arg-type]
            value=str(value) if value is not None else options[0],  # type: ignore[arg-type]
            options=[ft.dropdown.Option(opt) for opt in options],  # type: ignore[arg-type]
            border_color="rgba(255,255,255,0.2)",  # type: ignore[arg-type]
            width=width or 250,
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            bgcolor="rgba(0,0,0,0.5)",
        )
        self._config_inputs[key] = dropdown
        return dropdown

    def _create_checkbox_input(self, key: str, label: str, value: bool) -> ft.Checkbox:
        """Create a checkbox input for configuration."""
        checkbox = ft.Checkbox(
            label=label,
            value=bool(value),
            fill_color=ft.Colors.CYAN_400,
            check_color=ft.Colors.BLACK,
        )
        self._config_inputs[key] = checkbox
        return checkbox

    def _build_no_project_view(self) -> ft.Control:
        """Display message when no project is loaded."""
        return ft.Container(
            padding=40,
            expand=True,
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.FOLDER_OFF, size=64, color=ft.Colors.WHITE54),
                    ft.Text(
                        "No Project Loaded",
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.WHITE70,
                    ),
                    ft.Text(
                        "Create or open a project to access configuration settings.",
                        size=14,
                        color=ft.Colors.WHITE54,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
        )

    def _load_current_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from current project."""
        try:
            sm = get_session_manager()
            if not sm or not sm.persistence or not sm.persistence.db_path:
                return None
            
            # Get project directory from database path
            db_path = Path(sm.persistence.db_path)
            if db_path.name == ":memory:":
                return None
            
            project_dir = db_path.parent
            config_json_path = project_dir / "config.json"
            
            if not config_json_path.exists():
                return None
            
            with open(config_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None

    async def _save_config(self) -> None:
        """Save configuration changes to file and database."""
        try:
            if not self._config_data:
                await self.app_controller.push_log("No configuration loaded", "warning")
                return
            
            # Build updated config from inputs
            updated_config = self._build_config_from_inputs()
            
            # Validate configuration
            if not self._validate_config(updated_config):
                await self.app_controller.push_log("Invalid configuration values", "error")
                return
            
            # Get project directory
            sm = get_session_manager()
            if not sm or not sm.persistence:
                await self.app_controller.push_log("No project loaded", "error")
                return
            
            db_path = Path(sm.persistence.db_path)
            project_dir = db_path.parent
            config_json_path = project_dir / "config.json"
            
            # Save to config.json
            with open(config_json_path, 'w', encoding='utf-8') as f:
                json.dump(updated_config, f, indent=2)
            
            # Save to database
            sm.persistence.save_project_config(updated_config)
            
            await self.app_controller.push_log("Configuration saved successfully", "success")
            logger.info("Configuration saved to file and database")
            
        except Exception as e:
            await self.app_controller.push_log(f"Error saving configuration: {str(e)}", "error")
            logger.error(f"Error saving configuration: {e}")

    def _build_config_from_inputs(self) -> Dict[str, Any]:
        """Build configuration dictionary from input controls."""
        config = json.loads(json.dumps(self._config_data))  # Deep copy
        
        for key, control in self._config_inputs.items():
            parts = key.split(".")
            section = parts[0]
            field = parts[1]
            
            if section not in config:
                config[section] = {}
            
            # Extract value based on control type
            if isinstance(control, ft.Checkbox):
                config[section][field] = control.value
            elif isinstance(control, (ft.TextField, ft.Dropdown)):
                value_str = control.value
                # Try to convert to appropriate type
                try:
                    # Check if it should be a number
                    if value_str and "." in value_str:
                        config[section][field] = float(value_str)
                    elif value_str and value_str.isdigit():
                        config[section][field] = int(value_str)
                    else:
                        config[section][field] = value_str if value_str else ""
                except (ValueError, AttributeError, TypeError):
                    config[section][field] = value_str if value_str else ""
        
        return config

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration values."""
        try:
            # Basic validation - check required sections exist
            required_sections = ["llm", "vector", "database", "embedding", "ui", "processing"]
            for section in required_sections:
                if section not in config:
                    logger.error(f"Missing required section: {section}")
                    return False
            
            # TODO: Add more specific validation if needed
            return True
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False

    def _reset_to_defaults(self) -> None:
        """Reset configuration to defaults.yaml."""
        try:
            # Load defaults.yaml
            project_root = Path(__file__).parent.parent.parent.parent
            defaults_path = project_root / "forge" / "config" / "settings" / "defaults.yaml"
            
            if defaults_path.exists():
                with open(defaults_path, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f) or {}
                
                # Rebuild view
                asyncio.create_task(self.app_controller.push_log("Configuration reset to defaults", "info"))
                # TODO: Rebuild view to show new values
            
        except Exception as e:
            asyncio.create_task(self.app_controller.push_log(f"Error resetting config: {str(e)}", "error"))
            logger.error(f"Error resetting config: {e}")

    def _reload_config(self) -> None:
        """Reload configuration from config.json file."""
        self._config_data = self._load_current_config()
        asyncio.create_task(self.app_controller.push_log("Configuration reloaded from file", "info"))
        # TODO: Rebuild view to show new values
