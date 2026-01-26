"""
Dashboard Controller - Unified Command Center.
Merges Project Management, Graph View, and Document Ingest.
"""

from __future__ import annotations

import asyncio
import duckdb
import json
import logging
import os
import socket
import subprocess
import threading
import webbrowser
import yaml
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import flet as ft

from forge.shared.core import events
from forge.shared.core.service_registry import get_session_manager
from forge.extractor.ui.theme import (
    # Primary colors (for special cases like graph icons)
    CYAN_PRIMARY, TEAL_PRIMARY, RED_PRIMARY,
    # Semantic UI tokens
    TEXT_TITLE, TEXT_SUBTITLE, TEXT_SECTION_HEADER,
    TEXT_LABEL, TEXT_VALUE, TEXT_PLACEHOLDER,
    BUTTON_TEXT_ACTIVE, BUTTON_TEXT_DISABLED,
    BUTTON_ICON_ACTIVE, BUTTON_ICON_DISABLED,
    STAT_VALUE, STAT_LABEL_PRIMARY, STAT_LABEL_SECONDARY,
    STAT_ICON_PRIMARY, STAT_ICON_SECONDARY,
    DROPDOWN_LABEL, DROPDOWN_VALUE,
    # Status colors
    STATUS_COMPLETED, STATUS_FAILED, STATUS_PROCESSING,
    # Backgrounds & Borders
    BG_CARD, BORDER_MEDIUM, BORDER_DIVIDER,
)

# Optional Tkinter for file dialogs
try:
    import tkinter as tk
    from tkinter import filedialog, simpledialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    tk: Any = None
    filedialog: Any = None
    simpledialog: Any = None

if TYPE_CHECKING:
    from forge.extractor.state.app_state import AppState

logger = logging.getLogger(__name__)


class DashboardController:
    """Unified controller for the main dashboard."""

    # Graph Color Mapping
    ENTITY_COLORS = {
        "PERSON": "#4A90E2", "ORGANIZATION": "#7ED321", "LOCATION": "#9013FE",
        "EVENT": "#F5A623", "DATE": "#50E3C2", "MONEY": "#B8E986",
        "PERCENT": "#BD10E0", "MISC": "#D0021B",
    }
    DEFAULT_COLOR = "#BDC3C7"

    def __init__(self, app_state: AppState, page: ft.Page):
        self.app_controller = app_state
        self.page = page
        self._doc_counter = 0
        
        # Graph State
        self._current_layout = "force-directed"
        self._graph_html_path: Optional[Path] = None
        self._http_server: Optional[HTTPServer] = None
        self._http_server_thread: Optional[threading.Thread] = None
        
        # Selected file for processing
        self._selected_file: Optional[Path] = None
        
        # Subscribe to graph update events to update document processing counts
        asyncio.create_task(self._subscribe_to_events())

    def _read_file_content(self, file_path: Path) -> str:
        """Read content from supported file formats."""
        suffix = file_path.suffix.lower()
        
        if suffix == '.txt':
            return file_path.read_text(encoding='utf-8')
        elif suffix == '.pdf':
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except ImportError:
                logger.error("pypdf not available for PDF reading")
                return ""
            except Exception as e:
                logger.error(f"Error reading PDF: {e}")
                return ""
        else:
            # Try to read as text for other formats
            try:
                return file_path.read_text(encoding='utf-8')
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return ""

    async def _subscribe_to_events(self):
        """Subscribe to events for updating document processing statistics."""
        await self.app_controller.bus.subscribe(events.TOPIC_GRAPH_UPDATED, self._on_graph_updated)
        logger.info("DashboardController subscribed to TOPIC_GRAPH_UPDATED")

    async def _on_graph_updated(self, payload):
        """Handle graph update events by updating document processing counts."""
        try:
            doc_id = payload.get("doc_id")
            graph_stats = payload.get("graph_stats", {})
            # Gracefully skip global/project-wide updates
            if doc_id is None or doc_id == "ALL":
                return

            if not doc_id:
                logger.warning(f"Received TOPIC_GRAPH_UPDATED event without doc_id. Payload: {payload}")
                return

            entity_count = graph_stats.get("node_count", 0)
            relationship_count = graph_stats.get("edge_count", 0)

            # Update the document processing record with actual counts
            sm = get_session_manager()
            if sm and sm.persistence and sm.persistence.conn:
                sm.persistence.conn.execute(
                    "UPDATE document_processing SET status = ?, entity_count = ?, relationship_count = ?, completed_at = CURRENT_TIMESTAMP WHERE doc_id = ?",
                    ["completed", entity_count, relationship_count, doc_id]
                )
                sm.persistence.conn.commit()
                logger.info(f"Updated document_processing for {doc_id}: {entity_count} entities, {relationship_count} relationships")

                # Log the completion
                await self.app_controller.push_log(
                    f"Completed processing {doc_id}: {entity_count}E, {relationship_count}R",
                    "success"
                )
            else:
                logger.warning("No database connection available to update document processing counts")

        except Exception as ex:
            logger.error(f"Error updating document processing counts: {ex}", exc_info=True)

    def cleanup(self):
        """Cleanup resources when the controller is destroyed."""
        logger.info("Cleaning up DashboardController resources...")
        self._stop_http_server()
        logger.info("DashboardController cleanup completed")

    def build_view(self) -> ft.Control:
        """Build the unified dashboard view."""
        
        # --- Section 1: Project Management Buttons ---
        project_buttons = self._build_project_buttons()
        
        # --- Section 2: Analysis Section ---
        analysis_section = self._build_analysis_section()
        
        # --- Section 3: Graph View (Right/Side Area) ---
        graph_section = self._build_graph_panel()

        # Layout Assembly
        return ft.Container(
            expand=True,
            alignment=ft.Alignment(-1, -1),
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.DASHBOARD, color=STAT_ICON_PRIMARY, size=26),
                        ft.Text("PyScrAI", size=22, weight=ft.FontWeight.W_700, color=TEXT_SECTION_HEADER),
                        ft.Text("ALPHA VERSION - Lead Developer: T Hamil", size=12, weight=ft.FontWeight.W_400, color=TEXT_SUBTITLE, italic=True),
                    ], spacing=12, expand=True, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),
                    ft.Divider(height=8),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Project Management", size=16, weight=ft.FontWeight.W_600, color=TEXT_SECTION_HEADER),
                                    ft.Divider(color=BORDER_DIVIDER, height=1),
                                    project_buttons,
                                    analysis_section,
                                ],
                                expand=2,
                                spacing=8,
                                alignment=ft.MainAxisAlignment.START,
                                horizontal_alignment=ft.CrossAxisAlignment.START,
                            ),
                            ft.VerticalDivider(width=1),
                            ft.Container(
                                expand=1,
                                content=graph_section,
                                alignment=ft.Alignment(-1, -1),
                            )
                        ],
                        expand=True,
                        spacing=16,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ],
                expand=True,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            )
        )

    # =========================================================================
    # ANALYSIS SECTION
    # =========================================================================
    
    def _build_analysis_section(self) -> ft.Control:
        """Build the Analysis section with Process Data button and document history."""
        
        # Process Data button
        process_data_button = self._build_process_data_button()
        
        # Document history table
        document_history = self._build_document_history()
        
        return ft.Column(
            [
                ft.Text("Analysis", size=16, weight=ft.FontWeight.W_600, color=TEXT_SECTION_HEADER),
                ft.Divider(height=1),
                ft.Container(height=10),
                
                process_data_button,
                ft.Container(height=16),
                
                document_history,
            ],
            spacing=0,
            expand=3,
        )

    def _build_process_data_button(self) -> ft.Control:
        """Build the Process Data button (renamed from Analyze Data)."""
        
        async def on_process_data(e):
            """Open file picker to select a data file, then process it."""
            if not TKINTER_AVAILABLE:
                await self.app_controller.push_log("Tkinter required for file dialogs", "error")
                return
            
            # Check if project is loaded
            sm = get_session_manager()
            if not sm or not sm.persistence or not sm.persistence.db_path:
                await self.app_controller.push_log("No project loaded. Please open a project first.", "warning")
                return
            
            project_root = Path(__file__).parent.parent.parent.parent
            default_dir = project_root / "data"
            default_dir.mkdir(parents=True, exist_ok=True)
            
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            # Support multiple formats: .txt and .pdf
            file_path = filedialog.askopenfilename(
                title="Select Data File",
                initialdir=str(default_dir),
                filetypes=[
                    ("Text files", "*.txt"),
                    ("PDF files", "*.pdf"),
                    ("All supported", "*.txt *.pdf"),
                    ("All files", "*.*")
                ]
            )
            root.destroy()
            
            if not file_path:
                return
            
            self._selected_file = Path(file_path)
            filename = self._selected_file.name
            await self.app_controller.push_log(f"Selected file: {filename}", "info")
            
            # Generate document ID
            self._doc_counter += 1
            doc_id = f"doc_{self._doc_counter:04d}"
            
            # Record processing start in database
            try:
                if sm.persistence.conn:
                    sm.persistence.conn.execute(
                        "INSERT INTO document_processing (filename, file_path, doc_id, status, started_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                        [filename, str(file_path), doc_id, "processing"]
                    )
                    sm.persistence.conn.commit()
            except Exception as ex:
                logger.error(f"Failed to record processing start: {ex}")
            
            await self.app_controller.push_log(f"Processing {filename}...", "info")
            
            try:
                # Read file content
                text = self._read_file_content(self._selected_file)
                if not text:
                    # Update status to failed
                    if sm.persistence.conn:
                        sm.persistence.conn.execute(
                            "UPDATE document_processing SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP WHERE doc_id = ?",
                            ["failed", "Could not read file content", doc_id]
                        )
                        sm.persistence.conn.commit()
                    await self.app_controller.push_log(f"Could not read content from {filename}", "error")
                    return
                
                # Publish ingestion event
                await self.app_controller.publish(
                    events.TOPIC_DATA_INGESTED,
                    events.create_data_ingested_event(doc_id, text.strip())
                )
                
                processed_filename = self._selected_file.name
                self._selected_file = None
                await self.app_controller.push_log(f"Initiated processing of {doc_id} from {processed_filename}", "success")
                
            except Exception as ex:
                logger.error(f"Error processing file: {ex}", exc_info=True)
                # Update status to failed
                try:
                    if sm.persistence.conn:
                        sm.persistence.conn.execute(
                            "UPDATE document_processing SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP WHERE doc_id = ?",
                            ["failed", str(ex), doc_id]
                        )
                        sm.persistence.conn.commit()
                except Exception:
                    pass
                await self.app_controller.push_log(f"Error processing file: {str(ex)}", "error")

        return ft.OutlinedButton(
            "Process Data",
            icon=ft.Icons.ANALYTICS,
            icon_color=BUTTON_ICON_ACTIVE,
            tooltip="Select and process a data file (.txt, .pdf)",
            style=ft.ButtonStyle(
                color=BUTTON_TEXT_ACTIVE,
            ),
            expand=True,
            on_click=lambda e: asyncio.create_task(on_process_data(e))
        )

    def _build_document_history(self) -> ft.Control:
        """Build the document processing history display."""
        
        # Create scrollable container for history
        history_list = ft.ListView(expand=True, spacing=4)
        
        def refresh_history():
            """Refresh the document history from database."""
            try:
                sm = get_session_manager()
                if not sm or not sm.persistence:
                    history_list.controls = [
                        ft.Container(
                            content=ft.Text("No project loaded", color=TEXT_PLACEHOLDER, italic=True),
                            padding=10
                        )
                    ]
                    return
                
                # Get processing history
                if sm.persistence.conn:
                    rows = sm.persistence.conn.execute("""
                        SELECT filename, started_at, status, entity_count, relationship_count, error_message
                        FROM document_processing 
                        ORDER BY started_at DESC 
                        LIMIT 20
                    """).fetchall()
                else:
                    rows = []
                if not rows:
                    history_list.controls = [
                        ft.Container(
                            content=ft.Text("No documents processed yet", color=TEXT_PLACEHOLDER, italic=True),
                            padding=10
                        )
                    ]
                else:
                    history_list.controls = []
                    for row in rows:
                        filename, timestamp, status, entity_count, relationship_count, error_message = row
                        # Format timestamp
                        if timestamp:
                            try:
                                if isinstance(timestamp, str):
                                    dt = datetime.fromisoformat(timestamp.replace('T', ' '))
                                else:
                                    dt = timestamp
                                time_str = dt.strftime("%m/%d %H:%M")
                            except:
                                time_str = str(timestamp)[:16]
                        else:
                            time_str = "--"
                        
                        # Status icon and color
                        if status == "completed":
                            status_icon = ft.Icons.CHECK_CIRCLE
                            status_color = STATUS_COMPLETED
                        elif status == "failed":
                            status_icon = ft.Icons.ERROR
                            status_color = STATUS_FAILED
                        else:  # processing
                            status_icon = ft.Icons.HOURGLASS_EMPTY
                            status_color = STATUS_PROCESSING
                        
                        # Extraction data (removed entity/relation count display)
                        if status == "completed":
                            extraction_text = ""
                        elif status == "failed":
                            extraction_text = error_message[:30] + "..." if error_message and len(error_message) > 30 else (error_message or "Failed")
                        else:
                            extraction_text = "Processing..."
                        
                        history_list.controls.append(
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(status_icon, color=status_color, size=16),
                                        ft.Text(
                                            filename[:25] + ("..." if len(filename) > 25 else ""),
                                            color=TEXT_VALUE,
                                            size=12,
                                            width=180,
                                        ),
                                        ft.Text(
                                            time_str,
                                            color=TEXT_LABEL,
                                            size=11,
                                            width=60,
                                        ),
                                        ft.Text(
                                            extraction_text,
                                            color=TEXT_PLACEHOLDER,
                                            size=11,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                padding=ft.padding.symmetric(horizontal=8, vertical=6),
                                bgcolor="rgba(255,255,255,0.02)" if rows.index(row) % 2 == 0 else "transparent",
                                border_radius=4,
                            )
                        )
                
            except Exception as e:
                logger.error(f"Error refreshing document history: {e}")
                history_list.controls = [
                    ft.Container(
                        content=ft.Text(f"Error loading history: {str(e)}", color=RED_PRIMARY),
                        padding=10
                    )
                ]
        
        # Initial load
        refresh_history()
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Processing History", size=14, weight=ft.FontWeight.W_600, color=TEXT_SECTION_HEADER),
                    ft.Container(height=6),
                    ft.Container(
                        content=history_list,
                        height=300,  # Fixed height for scrolling
                        border=ft.border.all(1, BORDER_MEDIUM),
                        border_radius=8,
                        bgcolor="rgba(255,255,255,0.02)",
                    ),
                ],
                spacing=0,
            ),
            expand=True,
        )

    # =========================================================================
    # PROJECT MANAGEMENT LOGIC
    # =========================================================================
    
    def _build_project_buttons(self) -> ft.Control:
        """Build just the project management buttons (New, Open, Save) without header."""
        
        def on_new_project(e):
            """Open dialog to create a new project using Flet UI."""
            print("[DEBUG] on_new_project called")
            logger.debug("on_new_project called")
            text_field = ft.TextField(label="Enter project name")

            async def close_dialog(ev=None):
                print("[DEBUG] close_dialog called")
                logger.debug("close_dialog called")
                if e.page.dialog:
                    e.page.dialog.open = False
                    e.page.update()

            async def submit_dialog(ev=None):
                print("[DEBUG] submit_dialog called")
                logger.debug("submit_dialog called")
                project_name = text_field.value.strip() if text_field.value else None
                await close_dialog()
                if not project_name:
                    print("[DEBUG] No project name entered")
                    logger.debug("No project name entered")
                    return
                # Use default storage directory
                project_root = Path(__file__).parent.parent.parent.parent
                default_dir = project_root / "forge" / "data" / "projects"
                default_dir.mkdir(parents=True, exist_ok=True)
                # Create project directory
                project_dir = default_dir / project_name
                project_dir.mkdir(parents=True, exist_ok=True)
                # Create project database file with normalized name
                db_path = project_dir / "intel.duckdb"
                # Create config.json with all .env variables
                config_json_path = project_dir / "config.json"
                await self._create_project_config(config_json_path, project_dir)
                # Initialize new DuckDB database
                conn = duckdb.connect(str(db_path))
                conn.close()
                await self.app_controller.push_log(f"Created new project: {project_name}", "success")
                # Open the new project
                sm = get_session_manager()
                if sm:
                    await sm.open_project(str(db_path))

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("New Project", weight=ft.FontWeight.W_700),
                content=text_field,
                actions=[
                    ft.TextButton("Cancel", on_click=lambda ev: asyncio.create_task(close_dialog(ev))),
                    ft.TextButton("Create", on_click=lambda ev: asyncio.create_task(submit_dialog(ev))),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            text_field.on_submit = lambda ev: asyncio.create_task(submit_dialog(ev))
            print("[DEBUG] Setting dialog on page and opening dialog")
            logger.debug("Setting dialog on page and opening dialog")
            e.page.dialog = dialog
            if dialog not in e.page.overlay:
                e.page.overlay.append(dialog)
            e.page.dialog.open = True
            e.page.update()
        
        async def on_save(e):
            sm = get_session_manager()
            if not sm: return
            if not TKINTER_AVAILABLE:
                await self.app_controller.push_log("Tkinter required for file dialogs", "error")
                return
                
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            path = filedialog.asksaveasfilename(
                title="Save Project", defaultextension=".duckdb",
                filetypes=[("DuckDB", "*.duckdb")], initialfile="project.duckdb"
            )
            root.destroy()
            
            if path:
                await sm.save_project(path)

        async def on_open(e):
            sm = get_session_manager()
            if not sm: return
            if not TKINTER_AVAILABLE: return
            
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            path = filedialog.askopenfilename(
                title="Open Project", filetypes=[("DuckDB", "*.duckdb")]
            )
            root.destroy()
            
            if path:
                await sm.open_project(path)

        return ft.Row(
            [
                ft.OutlinedButton(
                    "New",
                    icon=ft.Icons.ADD,
                    icon_color=BUTTON_ICON_ACTIVE,
                    tooltip="Create New Project",
                    on_click=on_new_project
                ),
                ft.OutlinedButton(
                    "Open",
                    icon=ft.Icons.FOLDER_OPEN,
                    icon_color=BUTTON_ICON_ACTIVE,
                    tooltip="Open Project",
                    style=ft.ButtonStyle(
                        color=BUTTON_TEXT_ACTIVE,
                    ),
                    on_click=lambda e: asyncio.create_task(on_open(e))
                ),
                ft.OutlinedButton(
                    "Save",
                    icon=ft.Icons.SAVE,
                    icon_color=BUTTON_ICON_ACTIVE,
                    tooltip="Save Project",
                    style=ft.ButtonStyle(
                        color=BUTTON_TEXT_ACTIVE,
                    ),
                    on_click=lambda e: asyncio.create_task(on_save(e))
                ),
            ],
            spacing=8,
        )
    
    # =========================================================================
    # ANALYZE DATA BUTTON (formerly Select Data)
    # =========================================================================





    # =========================================================================
    # GRAPH LOGIC
    # =========================================================================

    def _build_graph_panel(self) -> ft.Control:
        # Simplified Graph View integrated into dashboard
        
        # Load Stats (Safe loading)
        entities, relationships = [], []
        sm = get_session_manager()
        if sm and sm.persistence:
            try:
                entities = sm.persistence.get_all_entities()
                relationships = sm.persistence.get_all_relationships()
            except Exception: pass
            
        e_count = len(entities)
        r_count = len(relationships)
        has_data = e_count > 0

        async def on_view_graph(e):
            if not has_data: 
                await self.app_controller.push_log("No graph data available", "warning")
                return
            try:
                # Generate and open
                html_path = self._generate_graph_html(entities, relationships)
                if not html_path:
                    await self.app_controller.push_log("Failed to generate graph", "error")
                    return
                
                url = await self._serve_html(html_path)
                if not url:
                    await self.app_controller.push_log("Failed to start HTTP server", "error")
                    return
                
                if self._open_browser(url):
                    await self.app_controller.push_log("Graph opened in browser", "success")
                else:
                    await self.app_controller.push_log(f"Could not open browser. URL: {url}", "warning")
            except Exception as ex:
                logger.error(f"Error opening graph: {ex}", exc_info=True)
                await self.app_controller.push_log(f"Error opening graph: {str(ex)}", "error")

        # Minimalist Stats Cards with semantic coloring
        def _stat_card(label, value, icon, icon_color, label_color):
            return ft.Container(
                bgcolor=BG_CARD,
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                border_radius=8,
                border=ft.border.all(1, BORDER_MEDIUM),
                expand=True,
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon, color=icon_color, size=16),
                        ft.Text(str(value), size=20, weight=ft.FontWeight.W_700, color=STAT_VALUE),
                    ], spacing=8, alignment=ft.MainAxisAlignment.START),
                    ft.Text(label, size=11, color=label_color, weight=ft.FontWeight.W_500)
                ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.START)
            )

        return ft.Column(
            [
                ft.Row([
                    _stat_card("Entities", e_count, ft.Icons.CIRCLE, STAT_ICON_PRIMARY, STAT_LABEL_PRIMARY),
                    ft.Container(width=10),
                    _stat_card("Relations", r_count, ft.Icons.SHARE, STAT_ICON_SECONDARY, STAT_LABEL_SECONDARY),
                ], spacing=0),
                
                ft.Container(height=18),
                
                # Divider with "Knowledge Graph" header
                ft.Column([
                    ft.Text("Knowledge Graph", size=14, weight=ft.FontWeight.W_600, color=TEXT_SECTION_HEADER),
                    ft.Divider(height=1),
                ], spacing=6),
                
                ft.Container(height=10),
                
                self._create_layout_dropdown(),
                
                ft.Container(height=14),
                
                ft.OutlinedButton(
                    "View Graph",
                    icon=ft.Icons.OPEN_IN_BROWSER,
                    icon_color=BUTTON_ICON_DISABLED if not has_data else BUTTON_ICON_ACTIVE,
                    tooltip="Open interactive graph visualization",
                    style=ft.ButtonStyle(
                        color=BUTTON_TEXT_DISABLED if not has_data else BUTTON_TEXT_ACTIVE,
                    ),
                    expand=True,
                    disabled=not has_data,
                    on_click=lambda e: asyncio.create_task(on_view_graph(e))
                ),
                
                ft.Container(height=18),
                
                # Export section
                ft.Column([
                    ft.Text("Export", size=14, weight=ft.FontWeight.W_600, color=TEXT_SECTION_HEADER),
                    ft.Divider(height=1),
                ], spacing=6),
                
                ft.Container(height=10),
                
                self._create_export_controls(has_data),
            ],
            spacing=0
        )

    # --- Graph Helpers (Ported from GraphController) ---
    
    def _create_layout_dropdown(self) -> ft.Dropdown:
        """Create layout dropdown with proper event handler."""
        def on_layout_change(e):
            self._current_layout = e.control.value
        
        dropdown = ft.Dropdown(  # type: ignore[call-arg]
            label="Layout",  # type: ignore[arg-type]
            value=self._current_layout,  # type: ignore[arg-type]
            options=[  # type: ignore[arg-type]
                ft.dropdown.Option("force-directed"),
                ft.dropdown.Option("circular"),
            ],
            text_size=13,  # type: ignore[arg-type]
            height=40, 
            content_padding=ft.padding.symmetric(horizontal=10, vertical=8),  # type: ignore[arg-type]
            border_color="rgba(255,255,255,0.15)",  # type: ignore[arg-type]
            bgcolor="rgba(255,255,255,0.02)",  # type: ignore[arg-type]
            color=DROPDOWN_VALUE,  # type: ignore[arg-type]
            label_style=ft.TextStyle(color=DROPDOWN_LABEL, size=12),  # type: ignore[arg-type]
        )
        dropdown.on_change = on_layout_change  # type: ignore[assignment]
        return dropdown
    
    def _create_export_controls(self, has_data: bool) -> ft.Control:
        """Create export format dropdown and export button."""
        export_format_dropdown = ft.Dropdown(  # type: ignore[call-arg]
            label="Format",  # type: ignore[arg-type]
            value="markdown",  # type: ignore[arg-type]
            options=[  # type: ignore[arg-type]
                ft.dropdown.Option("markdown"),
                ft.dropdown.Option("json"),
                ft.dropdown.Option("csv"),
            ],
            text_size=13,  # type: ignore[arg-type]
            height=40,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=8),  # type: ignore[arg-type]
            border_color="rgba(255,255,255,0.15)",  # type: ignore[arg-type]
            bgcolor="rgba(255,255,255,0.02)",  # type: ignore[arg-type]
            color=DROPDOWN_VALUE,  # type: ignore[arg-type]
            label_style=ft.TextStyle(color=DROPDOWN_LABEL, size=12),  # type: ignore[arg-type]
        )
        
        async def on_export(e):
            """Handle export button click."""
            if not TKINTER_AVAILABLE:
                await self.app_controller.push_log("Tkinter required for file dialogs", "error")
                return
            
            sm = get_session_manager()
            if not sm or not sm.persistence or not sm.persistence.db_path:
                await self.app_controller.push_log("No project loaded", "warning")
                return
            
            # Get export format
            export_format = export_format_dropdown.value
            
            # Get default directory (project directory)
            project_dir = Path(sm.persistence.db_path).parent
            
            # Set file extension based on format
            if export_format == "markdown":
                default_ext = ".md"
                file_types = [("Markdown files", "*.md"), ("All files", "*.*")]
            elif export_format == "json":
                default_ext = ".json"
                file_types = [("JSON files", "*.json"), ("All files", "*.*")]
            else:  # csv
                default_ext = ".csv"
                file_types = [("CSV files", "*.csv"), ("All files", "*.*")]
            
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            # Open file save dialog
            export_path = filedialog.asksaveasfilename(
                title="Export Data",
                initialdir=str(project_dir),
                defaultextension=default_ext,
                filetypes=file_types,
                initialfile=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}{default_ext}"
            )
            root.destroy()
            
            if not export_path:
                return
            
            await self.app_controller.push_log(f"Exporting to {export_format}...", "info")
            
            try:
                try:
                    from forge.shared.infrastructure.export.export_service import ExportService
                    export_service = ExportService(sm.persistence.conn)
                except ImportError as import_ex:
                    await self.app_controller.push_log(f"Export service not available: {str(import_ex)}", "error")
                    return
                except Exception as service_ex:
                    await self.app_controller.push_log(f"Failed to initialize export service: {str(service_ex)}", "error")
                    return
                
                output_path = Path(export_path)
                
                if export_format == "markdown":
                    await export_service.export_markdown(output_path)
                elif export_format == "json":
                    await export_service.export_graph_json(output_path, include_analytics=True)
                elif export_format == "csv":
                    await export_service.export_entities_csv(output_path)
                
                await self.app_controller.push_log(f"Successfully exported to {output_path.name}", "success")
                
            except Exception as ex:
                logger.error(f"Error exporting data: {ex}", exc_info=True)
                await self.app_controller.push_log(f"Error exporting: {str(ex)}", "error")
        
        return ft.Column([
            export_format_dropdown,
            ft.Container(height=10),
            ft.OutlinedButton(
                "Export Data",
                icon=ft.Icons.DOWNLOAD,
                icon_color=BUTTON_ICON_DISABLED if not has_data else BUTTON_ICON_ACTIVE,
                tooltip="Export entities, relationships, narratives, and semantic profiles",
                style=ft.ButtonStyle(
                    color=BUTTON_TEXT_DISABLED if not has_data else BUTTON_TEXT_ACTIVE,
                ),
                expand=True,
                disabled=not has_data,
                on_click=lambda e: asyncio.create_task(on_export(e))
            ),
        ], spacing=0)
    
    def _generate_graph_html(self, entities, relationships) -> Optional[Path]:
        try:
            import plotly.graph_objects as go
            import networkx as nx
        except ImportError:
            return None

        # Build NetworkX Graph for Layout
        G = nx.DiGraph()
        valid_ids = set()
        
        for e in entities:
            eid = e.get("id")
            if eid: 
                valid_ids.add(eid)
                G.add_node(eid, **e)
                
        for r in relationships:
            src, tgt = r.get("source"), r.get("target")
            if src in valid_ids and tgt in valid_ids:
                G.add_edge(src, tgt, **r)

        if not G.nodes: return None

        # Calculate Layout
        if self._current_layout == "circular":
            pos = nx.circular_layout(G)
        else:
            pos = nx.spring_layout(G, k=0.5, iterations=50)

        # Create Plotly Traces
        edge_x, edge_y = [], []
        node_x, node_y, node_text, node_color = [], [], [], []

        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none', mode='lines')

        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            data = G.nodes[node]
            label = data.get("label", node)
            etype = data.get("type", "UNKNOWN")
            node_text.append(f"{label} ({etype})")
            node_color.append(self.ENTITY_COLORS.get(etype, self.DEFAULT_COLOR))

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            text=[G.nodes[n].get("label", n) for n in G.nodes()],
            textposition="top center",
            hovertext=node_text,
            marker=dict(size=10, color=node_color, line_width=2))

        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title="Knowledge Graph",
                showlegend=False,
                margin=dict(b=0,l=0,r=0,t=40),
                paper_bgcolor='rgba(10,15,30,1)',
                plot_bgcolor='rgba(10,15,30,1)',
                font=dict(color='white'),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
            )
        )

        # Save to absolute path
        try:
            project_root = Path(__file__).parent.parent.parent.parent
            output_dir = project_root / "data" / "graph"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            html_path = output_dir / "visualization.html"
            html_path.write_text(fig.to_html(include_plotlyjs='cdn', full_html=True), encoding='utf-8')
            logger.info(f"Graph HTML saved to {html_path}")
            return html_path
        except Exception as e:
            logger.error(f"Error saving graph HTML: {e}")
            return None

    def _find_free_port(self) -> int:
        """Find a free port for the HTTP server."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    async def _serve_html(self, path: Path) -> Optional[str]:
        """Start a simple HTTP server to serve the HTML file.
        
        Args:
            path: Path to the HTML file to serve
            
        Returns:
            URL to access the file, or None if server couldn't be started
        """
        try:
            # Stop any existing server
            if self._http_server:
                self._stop_http_server()
            
            # Change to the directory containing the HTML file
            server_dir = path.parent
            port = self._find_free_port()
            
            # Create handler class with directory bound
            def make_handler(directory: str):
                class Handler(SimpleHTTPRequestHandler):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, directory=directory, **kwargs)
                    
                    def log_message(self, format, *args):
                        # Suppress server logs
                        pass
                return Handler
            
            Handler = make_handler(str(server_dir))
            self._http_server = HTTPServer(('127.0.0.1', port), Handler)
            server = self._http_server  # Capture for nested function
            
            def run_server():
                try:
                    logger.debug(f"HTTP server starting on port {port}")
                    server.serve_forever()  # type: ignore[union-attr]
                    logger.debug("HTTP server stopped normally")
                except OSError as e:
                    if e.errno == 10054:  # Connection reset by peer - expected during shutdown
                        logger.debug("HTTP server connection reset during shutdown (normal)")
                    else:
                        logger.warning(f"HTTP server OSError: {e}")
                except Exception as e:
                    logger.warning(f"HTTP server exception: {e}")
                finally:
                    logger.debug("HTTP server thread exiting")
            
            self._http_server_thread = threading.Thread(target=run_server, daemon=True)
            self._http_server_thread.start()
            
            # Give the server a moment to start
            await asyncio.sleep(0.1)
            
            # Build URL
            filename = path.name
            url = f"http://127.0.0.1:{port}/{filename}"
            return url
        except Exception as e:
            logger.warning(f"Could not start HTTP server: {e}")
            return None
    
    def _stop_http_server(self):
        """Stop the HTTP server if it's running."""
        # Reset references at start to prevent race conditions
        server = self._http_server
        thread = self._http_server_thread
        self._http_server = None
        self._http_server_thread = None
        
        if server:
            try:
                logger.debug("Stopping HTTP server...")
                server.shutdown()
                server.server_close()
                logger.debug("HTTP server stopped successfully")
            except Exception as e:
                logger.warning(f"Error stopping HTTP server: {e}")
                
        if thread and thread.is_alive():
            try:
                logger.debug("Joining HTTP server thread...")
                thread.join(timeout=2.0)
                if thread.is_alive():
                    logger.warning("HTTP server thread did not stop within timeout")
                else:
                    logger.debug("HTTP server thread stopped successfully")
            except Exception as e:
                logger.warning(f"Error joining HTTP server thread: {e}")

    def _open_browser(self, url: str) -> bool:
        """Open a URL in the default browser with improved error handling."""
        logger.info(f"Attempting to open browser with URL: {url}")
        
        # On Linux/WSL2, xdg-open is the most reliable method
        # Try xdg-open first (works with default browser)
        try:
            result = subprocess.run(
                ['xdg-open', url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                logger.info("Successfully opened browser using xdg-open")
                return True
            else:
                logger.debug(f"xdg-open returned code {result.returncode}: {result.stderr.decode()}")
        except FileNotFoundError:
            logger.debug("xdg-open not found, trying other methods")
        except subprocess.TimeoutExpired:
            logger.warning("xdg-open timed out")
        except Exception as e:
            logger.debug(f"xdg-open failed: {e}")
        
        # Try webbrowser module (cross-platform, uses default browser)
        try:
            webbrowser.open(url)
            logger.info("Successfully opened browser using webbrowser module")
            return True
        except Exception as e:
            logger.warning(f"webbrowser.open failed: {e}")
        
        # Fallback: Try specific browsers
        browsers = [
            ('chromium-browser', False),
            ('chromium', False),
            ('google-chrome', False),
            ('google-chrome-stable', False),
            ('firefox', False),
        ]
        
        for browser_name, use_app_mode in browsers:
            try:
                if use_app_mode:
                    cmd = [browser_name, f'--app={url}']
                else:
                    cmd = [browser_name, url]
                
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                logger.info(f"Successfully launched {browser_name}")
                return True
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"Failed to launch {browser_name}: {e}")
                continue
        
        logger.error(f"All browser opening methods failed for URL: {url}")
        return False
    
    async def _create_project_config(self, config_json_path: Path, project_dir: Path) -> None:
        """Create config.json file based on defaults.yaml with all .env overrides."""
        # Load defaults.yaml as base configuration
        project_root = Path(__file__).parent.parent.parent.parent
        defaults_path = project_root / "forge" / "config" / "settings" / "defaults.yaml"
        
        config = {}
        if defaults_path.exists():
            with open(defaults_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        
        # Set database path to point to {project_name}.duckdb in project directory
        if "database" not in config:
            config["database"] = {}
        # The project name is the directory name, so database is {project_name}.duckdb
        project_name = project_dir.name
        project_db_path = project_dir / f"{project_name}.duckdb"
        try:
            if project_db_path.is_relative_to(project_root):
                config["database"]["db_path"] = str(project_db_path.relative_to(project_root))
            else:
                config["database"]["db_path"] = str(project_db_path)
        except (AttributeError, ValueError):
            # Python < 3.9 fallback or path not relative
            config["database"]["db_path"] = str(project_db_path)
        
        # Override with ALL .env variables from .env file
        if "llm" not in config:
            config["llm"] = {}
        
        # Override all LLM configuration from .env (except API keys which are handled separately)
        if os.getenv("DEFAULT_PROVIDER"):
            config["llm"]["default_provider"] = os.getenv("DEFAULT_PROVIDER")
        if os.getenv("SECONDARY_PROVIDER"):
            config["llm"]["secondary_provider"] = os.getenv("SECONDARY_PROVIDER")
        if os.getenv("SEMANTIC_PROVIDER"):
            config["llm"]["semantic_provider"] = os.getenv("SEMANTIC_PROVIDER")
        
        # API credentials - include all from .env
        if os.getenv("OPENROUTER_API_KEY"):
            config["llm"]["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
        if os.getenv("OPENROUTER_BASE_URL"):
            config["llm"]["openrouter_base_url"] = os.getenv("OPENROUTER_BASE_URL")
        if os.getenv("OPENROUTER_MODEL"):
            config["llm"]["openrouter_model"] = os.getenv("OPENROUTER_MODEL")
        
        if os.getenv("LM_PROXY_BASE_URL"):
            config["llm"]["lm_proxy_base_url"] = os.getenv("LM_PROXY_BASE_URL")
        if os.getenv("LM_PROXY_MODEL"):
            config["llm"]["lm_proxy_model"] = os.getenv("LM_PROXY_MODEL")
        if os.getenv("LM_PROXY_API_KEY"):
            config["llm"]["lm_proxy_api_key"] = os.getenv("LM_PROXY_API_KEY")
        
        if os.getenv("CHERRY_API_URL"):
            config["llm"]["cherry_api_url"] = os.getenv("CHERRY_API_URL")
        if os.getenv("CHERRY_API_KEY"):
            config["llm"]["cherry_api_key"] = os.getenv("CHERRY_API_KEY")
        if os.getenv("CHERRY_PROVIDER"):
            config["llm"]["cherry_provider"] = os.getenv("CHERRY_PROVIDER")
        if os.getenv("CHERRY_MODEL"):
            config["llm"]["cherry_model"] = os.getenv("CHERRY_MODEL")
        
        if os.getenv("LM_STUDIO_BASE_URL"):
            config["llm"]["lm_studio_base_url"] = os.getenv("LM_STUDIO_BASE_URL")
        if os.getenv("LM_STUDIO_MODEL"):
            config["llm"]["lm_studio_model"] = os.getenv("LM_STUDIO_MODEL")
        if os.getenv("LM_STUDIO_API_KEY"):
            config["llm"]["lm_studio_api_key"] = os.getenv("LM_STUDIO_API_KEY")
        
        # Override UI settings from .env
        if "ui" not in config:
            config["ui"] = {}
        if os.getenv("FLET_WEB_MODE"):
            flet_web_mode = os.getenv("FLET_WEB_MODE", "false").lower()
            config["ui"]["flet_web_mode"] = flet_web_mode in ("true", "1", "yes", "on")
        
        # Override embedding settings from .env
        if "embedding" not in config:
            config["embedding"] = {}
        if os.getenv("HF_HOME"):
            config["embedding"]["hf_home"] = os.getenv("HF_HOME")
        
        # Write config.json
        with open(config_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
