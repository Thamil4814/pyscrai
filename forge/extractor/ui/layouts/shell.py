from __future__ import annotations

from typing import List, Optional

import flet as ft

from forge.extractor.state import Store
from forge.shared.core.service_registry import get_session_manager, register_cleanup_handler
from forge.shared.core import events
from forge.extractor.ui.renderer import render_schema
from forge.extractor.ui.theme import (
    # Primary colors (for theme seed, special cases)
    CYAN_PRIMARY, RED_PRIMARY,
    # Semantic UI tokens
    TEXT_TITLE, TEXT_SUBTITLE, TEXT_SECTION_HEADER,
    TEXT_LABEL, TEXT_VALUE, TEXT_PLACEHOLDER,
    BUTTON_TEXT_ACTIVE, BUTTON_ICON_ACTIVE,
    PANEL_HEADER,
    # Backgrounds
    BG_NAV, BG_GRADIENT_START, BG_GRADIENT_MID, BG_GRADIENT_END,
    BG_CARD, BG_INDICATOR,
    # Borders
    BORDER_SUBTLE, BORDER_LIGHT, BORDER_DIVIDER,
    # Legacy (still needed for nav rail)
    TEXT_BRIGHT, TEXT_MUTED,
    # Log Panel
    get_log_color, LOG_PANEL_TITLE, LOG_PANEL_CLOSE,
)
# Import controllers
from forge.extractor.controllers.dashboard_controller import DashboardController
from forge.extractor.controllers.settings_controller import SettingsController
from forge.extractor.controllers.intelligence_controller import IntelligenceController


def apply_shell_theme(page: ft.Page) -> None:
    """Apply a dark, high-contrast baseline theme with improved readability."""
    page.theme = ft.Theme(
        font_family="Space Grotesk",
        color_scheme_seed=CYAN_PRIMARY,
        visual_density=ft.VisualDensity.COMFORTABLE,
        use_material3=True,
    )
    page.bgcolor = "#000000"  # Pure black
    page.padding = 0


def _nav_destinations(items: List[dict]) -> List[ft.NavigationRailDestination]:
    destinations: List[ft.NavigationRailDestination] = []
    for item in items:
        icon_name = str(item.get("icon", "dashboard")).upper()
        icon = getattr(ft.Icons, icon_name, ft.Icons.DASHBOARD)
        destinations.append(
            ft.NavigationRailDestination(icon=icon, label=item.get("label", ""))
        )
    return destinations


def build_shell(page: ft.Page, store: Store) -> ft.View:
    # Log Panel State
    log_panel_visible = [True]  # Mutable for closure

    def close_log_panel(e=None):
        log_panel_visible[0] = False
        log_panel_container.visible = False
        page.update()

    def open_log_panel(e=None):
        log_panel_visible[0] = True
        log_panel_container.visible = True
        page.update()

    # Persistent column for logs
    log_list_column = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)

    def _sync_logs(e=None):
        logs = list(store.app.logs.value)
        logs = sorted(logs, key=lambda x: x.get('ts', 0), reverse=True)[-100:]
        log_controls = []
        import datetime

        for entry in logs:
            msg = entry.get('message', '')
            level = entry.get('level', 'info')
            ts = entry.get('ts', 0)
            time_str = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else ''
            color = get_log_color(level)
            log_controls.append(
                ft.Row([
                    ft.Text(level.upper(), size=11, color=color, width=60),
                    ft.Text(time_str, size=11, color=LOG_PANEL_TITLE, width=70),
                    ft.Text(msg, size=12, color=color, expand=True),
                ], spacing=8)
            )
        log_list_column.controls = log_controls
        page.update()

    def render_log_panel():
        return ft.Container(
            width=380,
            bgcolor="rgba(20,20,20,0.98)",
            border=ft.border.all(1, LOG_PANEL_TITLE),
            border_radius=8,
            padding=12,
            content=ft.Column([
                ft.Row([
                    ft.Text("Log", size=16, weight=ft.FontWeight.W_700, color=LOG_PANEL_TITLE, expand=True),
                    ft.IconButton(ft.Icons.CLOSE, icon_color=LOG_PANEL_CLOSE, tooltip="Close Log", on_click=close_log_panel, style=None),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=1, color=LOG_PANEL_TITLE),
                ft.Container(
                    content=log_list_column,
                    expand=True,
                    height=420,
                ),
            ], spacing=8),
        )

    apply_shell_theme(page)

    # Initialize controllers (they still need refactoring but can use store.app for now)
    dashboard_controller = DashboardController(store.app, page)
    settings_controller = SettingsController(store.app, page)
    intelligence_controller = IntelligenceController(store.app, page)
    
    # Register dashboard controller for cleanup on app exit
    register_cleanup_handler(dashboard_controller.cleanup)

    # --- UI primitives ---
    nav_rail = ft.NavigationRail(
        label_type=ft.NavigationRailLabelType.ALL,
        # Only label_type is valid in constructor; set other properties below
    )
    nav_rail.bgcolor = BG_NAV
    nav_rail.indicator_color = CYAN_PRIMARY
    nav_rail.selected_label_text_style = ft.TextStyle(color=TEXT_BRIGHT)
    nav_rail.unselected_label_text_style = ft.TextStyle(color=TEXT_MUTED)
    nav_rail.min_width = 80
    nav_rail.min_extended_width = 180
    nav_rail.destinations = _nav_destinations(store.app.nav_items.value)
    nav_rail.selected_index = 0

    status_text = ft.Text(store.app.status_text.value, color=TEXT_LABEL, size=12)

    # Ingestion progress indicator with dynamic text
    processing_status_text = ft.Text("Processing data...", color=BUTTON_TEXT_ACTIVE, size=12, weight=ft.FontWeight.W_500)
    ingestion_indicator = ft.Container(
        visible=False,
        padding=8,
        bgcolor=BG_INDICATOR,
        border_radius=8,
        content=ft.Row(
            [
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=CYAN_PRIMARY),
                processing_status_text,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        ),
    )

    # Main Content Container
    content_container = ft.Container(
        expand=True,
        content=dashboard_controller.build_view(),  # Default to unified dashboard
    )

    # Intelligence Workspace (Scrollable)
    workspace = ft.Column(
        controls=[ft.Text("Awaiting Intel", color=TEXT_PLACEHOLDER, size=15, italic=True)],
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

    def _sync_nav() -> None:
        nav_rail.destinations = _nav_destinations(store.app.nav_items.value)
        ids = [item.get("id") for item in store.app.nav_items.value]
        if store.app.nav_selected.value in ids:
            nav_rail.selected_index = ids.index(store.app.nav_selected.value)
        page.update()

    def _sync_status() -> None:
        status_text.value = store.app.status_text.value
        page.update()

    def _sync_workspace() -> None:
        if not store.app.workspace_schemas.value:
            workspace.controls = [ft.Text("Awaiting Intel", color=TEXT_PLACEHOLDER, size=15, italic=True)]
        else:
            # Use the Logs renderer to render schemas
            rendered_components: List[ft.Control] = []
            for schema in store.app.workspace_schemas.value:
                try:
                    component = render_schema(schema)
                    rendered_components.append(component)
                except Exception as e:
                    # Fallback to error display if rendering fails
                    rendered_components.append(
                        ft.Container(
                            bgcolor="rgba(255,59,48,0.1)",
                            padding=12,
                            border_radius=8,
                            border=ft.border.all(1, RED_PRIMARY),
                            content=ft.Text(
                                f"Render error: {str(e)}",
                                color=RED_PRIMARY,
                                size=13,
                            ),
                        )
                    )
            workspace.controls = rendered_components
        try:
            page.update()
        except RuntimeError:
            # Session destroyed, ignore update
            pass
    
    # Track processing state - use a set to track active processing stages
    active_processing_stages: set = set()

    # Track project operations
    project_operation_active = [False]
    project_operation_text = ft.Text("Ready", color=TEXT_LABEL, size=12, weight=ft.FontWeight.W_500)

    def _update_processing_indicator():
        """Update the processing indicator based on active stages."""
        if active_processing_stages:
            ingestion_indicator.visible = True
            # Show the most recent/relevant stage
            if "narratives" in active_processing_stages:
                processing_status_text.value = "Generating document narrative..."
            elif "semantic_profiles" in active_processing_stages:
                processing_status_text.value = "Generating semantic profiles..."
            elif "data_ingestion" in active_processing_stages:
                processing_status_text.value = "Processing data..."
            else:
                processing_status_text.value = "Processing..."
        else:
            ingestion_indicator.visible = False
            processing_status_text.value = "Processing data..."

        # Update project operation indicator
        if project_operation_active[0]:
            project_operation_indicator.visible = True
        else:
            project_operation_indicator.visible = False

        try:
            page.update()
        except RuntimeError:
            pass

    # Project operation indicator
    project_operation_indicator = ft.Container(
        visible=False,
        padding=8,
        bgcolor=BG_INDICATOR,
        border_radius=8,
        content=ft.Row(
            [
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=CYAN_PRIMARY),
                project_operation_text,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        ),
    )
    
    async def _on_data_ingested(payload):
        """Handle data ingestion start event."""
        active_processing_stages.add("data_ingestion")
        _update_processing_indicator()
    
    async def _on_entity_extracted(payload):
        """Handle entity extraction completion event."""
        # Keep indicator visible - more processing steps to come
        pass
    
    async def _on_graph_updated(payload):
        """Handle graph update completion event."""
        # Remove data ingestion stage, but semantic profiling may still be active
        active_processing_stages.discard("data_ingestion")
        _update_processing_indicator()
        
        # Rebuild dashboard if currently viewing it to show updated stats
        current_nav = store.app.nav_selected.value
        if current_nav == "dashboard":
            content_container.content = dashboard_controller.build_view()
            try:
                page.update()
            except RuntimeError:
                pass
    
    async def _on_intelligence_processing_start(payload):
        """Handle intelligence processing start event."""
        stage = payload.get("stage", "unknown")
        message = payload.get("message", "Processing...")
        active_processing_stages.add(stage)
        processing_status_text.value = message
        ingestion_indicator.visible = True
        try:
            page.update()
        except RuntimeError:
            pass
    
    async def _on_intelligence_processing_end(payload):
        """Handle intelligence processing end event."""
        stage = payload.get("stage", "unknown")
        active_processing_stages.discard(stage)
        _update_processing_indicator()
    
    async def _on_project_opened(payload):
        """Handle project opened event - rebuild dashboard to refresh UI state."""
        # End project operation indicator
        project_operation_active[0] = False
        project_operation_text.value = "Ready"
        _update_processing_indicator()

        # Check if we're currently on the dashboard view
        current_nav = store.app.nav_selected.value
        if current_nav == "dashboard":
            # Rebuild the dashboard to refresh stats, buttons, etc.
            content_container.content = dashboard_controller.build_view()
            try:
                page.update()
            except RuntimeError:
                pass

    async def _on_project_opening_start(payload):
        """Handle project opening start event."""
        project_operation_active[0] = True
        project_operation_text.value = "Opening project..."
        _update_processing_indicator()

    async def _on_project_saving_start(payload):
        """Handle project saving start event."""
        project_operation_active[0] = True
        project_operation_text.value = "Saving project..."
        _update_processing_indicator()

    async def _on_project_saving_end(payload):
        """Handle project saving end event."""
        project_operation_active[0] = False
        project_operation_text.value = "Ready"
        _update_processing_indicator()

    async def _on_session_restore_start(payload):
        """Handle session restore start event."""
        project_operation_active[0] = True
        project_operation_text.value = "Restoring session..."
        _update_processing_indicator()

    async def _on_session_restore_end(payload):
        """Handle session restore end event."""
        project_operation_active[0] = False
        project_operation_text.value = "Ready"
        _update_processing_indicator()
    
    # Subscribe to ingestion events
    import asyncio
    asyncio.create_task(store.app.bus.subscribe(events.TOPIC_DATA_INGESTED, _on_data_ingested))
    asyncio.create_task(store.app.bus.subscribe(events.TOPIC_ENTITY_EXTRACTED, _on_entity_extracted))
    asyncio.create_task(store.app.bus.subscribe(events.TOPIC_GRAPH_UPDATED, _on_graph_updated))
    asyncio.create_task(store.app.bus.subscribe(events.TOPIC_INTELLIGENCE_PROCESSING_START, _on_intelligence_processing_start))
    asyncio.create_task(store.app.bus.subscribe(events.TOPIC_INTELLIGENCE_PROCESSING_END, _on_intelligence_processing_end))
    asyncio.create_task(store.app.bus.subscribe(events.TOPIC_PROJECT_OPENED, _on_project_opened))

    # Subscribe to project operation events
    asyncio.create_task(store.app.bus.subscribe("project.opening.start", _on_project_opening_start))
    asyncio.create_task(store.app.bus.subscribe("project.saving.start", _on_project_saving_start))
    asyncio.create_task(store.app.bus.subscribe("project.saving.end", _on_project_saving_end))
    asyncio.create_task(store.app.bus.subscribe("session.restore.start", _on_session_restore_start))
    asyncio.create_task(store.app.bus.subscribe("session.restore.end", _on_session_restore_end))

    def _on_nav_change(e: ft.ControlEvent) -> None:
        rail = e.control
        if hasattr(rail, 'selected_index'):
            idx = rail.selected_index  # type: ignore[reportAttributeAccessIssue]
            items = store.app.nav_items.value
            if 0 <= idx < len(items):
                nav_id = items[idx].get("id", "")
                store.app.set_nav(nav_id)
                
                # Switch Views
                if nav_id == "dashboard":
                    # Rebuild dashboard to refresh stats
                    content_container.content = dashboard_controller.build_view()
                
                elif nav_id == "intel":
                    # Show Intelligence Dashboard (Workspace)
                    content_container.content = ft.Container(
                        expand=True,
                        alignment=ft.Alignment(-1, -1),  # Top-left alignment
                        padding=ft.padding.only(left=20, right=20, top=16, bottom=20),
                        content=ft.Column([
                            ft.Text("Intel Dashboard", size=24, weight=ft.FontWeight.W_700, color=TEXT_TITLE),
                            ft.Divider(color=BORDER_DIVIDER, height=1),
                            workspace,
                        ], spacing=16, alignment=ft.MainAxisAlignment.START, scroll=ft.ScrollMode.AUTO)
                    )
                
                elif nav_id == "settings":
                    # Show Settings Editor
                    content_container.content = settings_controller.build_view()
        page.update()

    nav_rail.on_change = _on_nav_change  # type: ignore[assignment]

    # --- Listener Bindings ---
    store.app.nav_items.listen(_sync_nav)
    store.app.nav_selected.listen(_sync_nav)
    store.app.status_text.listen(_sync_status)
    store.app.workspace_schemas.listen(_sync_workspace)
    store.app.logs.listen(_sync_logs)


    # Log Panel Container
    log_panel_container = ft.Container(
        visible=log_panel_visible[0],
        content=render_log_panel(),
        padding=ft.padding.only(left=8, right=8, top=0, bottom=0),
    )

    # --- Main Layout ---
    chrome = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[BG_GRADIENT_START, BG_GRADIENT_MID, BG_GRADIENT_END],
        ),
        content=ft.Row(
            [
                nav_rail,
                ft.VerticalDivider(width=1, color=BORDER_DIVIDER),
                ft.Container(
                    expand=True,
                    padding=0,
                    content=ft.Column(
                        [
                            # Header Bar with status indicators
                            ft.Row(
                                [
                                    project_operation_indicator,
                                    ingestion_indicator,
                                    ft.Container(expand=True),  # Spacer
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                height=36,
                            ),
                            ft.Row(
                                [
                                    ft.Container(
                                        expand=True,
                                        content=content_container,
                                        padding=0,
                                        bgcolor=BG_CARD,
                                        border_radius=0,
                                        border=None,
                                    ),
                                    log_panel_container,
                                ],
                                expand=True,
                                spacing=0,
                            ),
                        ],
                        spacing=0,
                    ),
                ),
            ],
            expand=True,
        ),
    )

    # Initial Sync
    _sync_nav()
    _sync_status()
    _sync_workspace()
    _sync_logs()

    return ft.View(
        route="/",
        controls=[chrome],
        bgcolor=ft.Colors.BLACK,
        padding=0,
    )
