"""PyScrAI Forge - Main application entry point."""

from __future__ import annotations

import asyncio
import atexit
import logging
import logging.handlers
import os
import threading
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

import flet as ft
from forge.extractor.state import Store
from forge.shared.core.event_bus import EventBus
from forge.extractor.ui.layouts.shell import build_shell
from forge.shared.domain.ingestion.extraction.service import DocumentExtractionService
from forge.shared.domain.knowledge.resolution.service import EntityResolutionService
from forge.shared.domain.knowledge.graph.service import GraphAnalysisService
from forge.shared.infrastructure.persistence.duckdb_service import DuckDBPersistenceService
from forge.shared.infrastructure.embeddings.embedding_service import EmbeddingService
from forge.shared.infrastructure.vector.qdrant_service import QdrantService
from forge.shared.domain.knowledge.resolution.deduplication_service import DeduplicationService
from forge.shared.domain.analysis.profiler import SemanticProfilerService
from forge.shared.domain.synthesis.narrative import NarrativeSynthesisService
from forge.shared.domain.synthesis.reporting import EntityCardService
from forge.shared.domain.synthesis.streaming import IntelligenceStreamingService
from forge.shared.domain.knowledge.graph.advanced_analyzer import AdvancedGraphAnalysisService
from forge.shared.domain.workflow.interaction.workflow_service import UserInteractionWorkflowService
from forge.shared.infrastructure.export.export_service import ExportService
from forge.shared.infrastructure.llm.provider_factory import ProviderFactory
from forge.extractor.ui.renderer import set_event_bus
from forge.shared.domain.context.session.session_manager import SessionManager
from forge.shared.core.service_registry import set_session_manager, register_intelligence_service
import duckdb

# Load environment variables from .env file in project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Set HF_HOME before any huggingface/sentence_transformers imports
# This ensures sentence transformers uses the configured cache directory
hf_home = os.getenv("HF_HOME")
if hf_home is not None:
    os.environ["HF_HOME"] = hf_home

# Configure comprehensive logging
# File handler: Log everything (configurable via LOG_LEVEL env var, default: DEBUG) to data/logs/forge.log (cross-platform)
# Console handler: Only log WARNING and ERROR to terminal
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_file_path = LOGS_DIR / "forge.log"

# Get log level from environment variable (default: DEBUG)
log_level_str = os.getenv("LOG_LEVEL", "DEBUG").upper()
log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
file_log_level = log_level_map.get(log_level_str, logging.DEBUG)

# Create root logger
root_logger = logging.getLogger()
root_logger.setLevel(file_log_level)  # Set to configured level

# Remove existing handlers to avoid duplicates
root_logger.handlers.clear()

# File handler - comprehensive logging (configured level)
file_handler = logging.handlers.RotatingFileHandler(
    log_file_path,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(file_log_level)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

# Console handler - only warnings and errors
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Only WARNING and ERROR
console_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

# Suppress verbose third-party library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("hpack.hpack").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("flet_controls").setLevel(logging.WARNING)
logging.getLogger("flet_transport").setLevel(logging.WARNING)
logging.getLogger("fletx.core.state").setLevel(logging.CRITICAL)  # Suppress observer errors during shutdown

# Suppress asyncio warnings on Windows during shutdown
if os.name == 'nt':
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)
logger.info(f"Logging configured: file={log_file_path}, console=WARNING+")

# Suppress Windows-specific asyncio connection reset errors during shutdown
if os.name == 'nt':  # Windows
    def suppress_connection_reset_error(loop, context):
        """Suppress ConnectionResetError exceptions during shutdown on Windows."""
        exception = context.get('exception')
        if isinstance(exception, ConnectionResetError):
            # This is expected during shutdown on Windows with ProactorEventLoop
            logger.debug("Suppressed ConnectionResetError during shutdown")
            return
        # For other exceptions, use default handler
        loop.default_exception_handler(context)
    
    # This will be applied to event loops created later
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def init_services(store: Store) -> None:
    """Initialize all services asynchronously with centralized configuration."""
    
    # Initialize the application state (wire event bus subscriptions)
    await store.app.initialize()
    logger.info("AppState initialized")
    
    # Load project configuration for service initialization
    from forge.shared.core.configuration import get_project_config_for_service, validate_critical_config
    project_config = get_project_config_for_service()
    
    # Validate critical configuration
    if project_config and not validate_critical_config(project_config):
        logger.error("Critical configuration validation failed, using system defaults")
        await store.app.publish("logs.event", {
            "message": "⚠ Configuration validation failed, using defaults",
            "level": "warning"
        })
        project_config = {}  # Fall back to defaults
    
    # Initialize primary LLM provider early (needed for extraction and intelligence services)
    try:
        llm_provider, _ = ProviderFactory.create_from_env(project_config=project_config)
        logger.info("Primary LLM provider initialized with project configuration")
    except Exception as e:
        logger.warning(f"Could not initialize primary LLM provider: {e}")
        logger.warning("Some services may not function correctly without LLM provider")
        await store.app.publish("logs.event", {
            "message": f"LLM provider initialization failed: {str(e)}",
            "level": "warning"
        })
        llm_provider = None
    
    # Initialize semantic LLM provider (for semantic profiling)
    try:
        semantic_llm_provider, _ = ProviderFactory.create_semantic_provider_from_env(project_config=project_config)
        logger.info("Semantic LLM provider initialized with project configuration")
    except Exception as e:
        logger.warning(f"Could not initialize semantic LLM provider: {e}")
        logger.warning("SemanticProfilerService will use primary provider if available")
        await store.app.publish("logs.event", {
            "message": "Semantic LLM provider fallback to primary",
            "level": "warning"
        })
        semantic_llm_provider = llm_provider  # Fall back to primary provider

    # Initialize and start DocumentExtractionService (needs LLM provider)
    extraction_service = DocumentExtractionService(store.app.bus, llm_provider)
    await extraction_service.start()
    logger.info("DocumentExtractionService started")

    # Initialize and start EntityResolutionService (needs LLM provider)
    resolution_service = EntityResolutionService(store.app.bus, llm_provider)
    await resolution_service.start()
    logger.info("EntityResolutionService started")

    # Initialize and start GraphAnalysisService
    graph_service = GraphAnalysisService(store.app.bus)
    await graph_service.start()
    logger.info("GraphAnalysisService started")

    # Initialize and start DuckDBPersistenceService
    persistence_service = DuckDBPersistenceService(store.app.bus)
    await persistence_service.start()
    logger.info("DuckDBPersistenceService started")

    # Initialize and start EmbeddingService
    embedding_service = EmbeddingService(store.app.bus)
    await embedding_service.start()
    logger.info("EmbeddingService started")

    # Initialize and start QdrantService
    qdrant_service = QdrantService(store.app.bus)
    await qdrant_service.start()
    logger.info("QdrantService started")

    # Use persistence_service.conn for intelligence services (will be updated when projects are opened)
    # Ensure schema is created in the initial connection
    if persistence_service.conn:
        # Schema should already be created by persistence_service.start(), but ensure it exists
        try:
            persistence_service._create_schema()
        except Exception:
            pass  # Schema might already exist
    
    db_connection = persistence_service.conn
    logger.info(f"Using persistence service connection for intelligence services: {persistence_service.db_path}")

    # Initialize and start DeduplicationService (requires LLM provider)
    if llm_provider:
        deduplication_service = DeduplicationService(
            store.app.bus,
            qdrant_service,
            llm_provider,
            db_connection
        )
        await deduplication_service.start()
        logger.info("DeduplicationService started")
    else:
        logger.warning("DeduplicationService not started: LLM provider unavailable")

    # Initialize and start SemanticProfilerService (uses semantic LLM provider)
    if semantic_llm_provider:
        profiler_service = SemanticProfilerService(
            store.app.bus,
            semantic_llm_provider,
            db_connection
        )
        await profiler_service.start()
        register_intelligence_service("SemanticProfilerService", profiler_service)
        logger.info("SemanticProfilerService started with semantic provider")
    elif llm_provider:
        # Fall back to primary provider if semantic provider not available
        profiler_service = SemanticProfilerService(
            store.app.bus,
            llm_provider,
            db_connection
        )
        await profiler_service.start()
        register_intelligence_service("SemanticProfilerService", profiler_service)
        logger.info("SemanticProfilerService started with primary provider (semantic provider unavailable)")
    else:
        logger.warning("SemanticProfilerService not started: No LLM provider available")

    # Initialize and start EntityCardService
    entity_card_service = EntityCardService(store.app.bus, db_connection)
    await entity_card_service.start()
    register_intelligence_service("EntityCardService", entity_card_service)
    logger.info("EntityCardService started")

    # Initialize and start NarrativeSynthesisService (requires LLM provider)
    if llm_provider:
        narrative_service = NarrativeSynthesisService(
            store.app.bus,
            llm_provider,
            db_connection
        )
        await narrative_service.start()
        logger.info("NarrativeSynthesisService started")
    else:
        logger.warning("NarrativeSynthesisService not started: LLM provider unavailable")

    # Initialize and start AdvancedGraphAnalysisService (requires LLM provider)
    if llm_provider:
        advanced_graph_service = AdvancedGraphAnalysisService(
            store.app.bus,
            llm_provider,
            db_connection
        )
        await advanced_graph_service.start()
        register_intelligence_service("AdvancedGraphAnalysisService", advanced_graph_service)
        logger.info("AdvancedGraphAnalysisService started")
    else:
        logger.warning("AdvancedGraphAnalysisService not started: LLM provider unavailable")
    
    # Initialize and start UserInteractionWorkflowService
    workflow_service = UserInteractionWorkflowService(store.app.bus)
    await workflow_service.start()
    logger.info("UserInteractionWorkflowService started")
    
    # Initialize and start IntelligenceStreamingService
    streaming_service = IntelligenceStreamingService(store.app.bus)
    await streaming_service.start()
    logger.info("IntelligenceStreamingService started")
    
    # Initialize ExportService (no async start needed)
    export_service = ExportService(db_connection)
    logger.info("ExportService initialized")
    
    # Set event bus in renderer for component actions
    set_event_bus(store.app.bus)
    logger.info("Event bus set in renderer")
    
    # Initialize SessionManager but DO NOT auto-restore
    session_manager = SessionManager(
        store.app.bus,  # Pass EventBus instead of AppController
        persistence_service, 
        qdrant_service, 
        embedding_service
    )
    set_session_manager(session_manager)
    logger.info("Session Manager initialized (Ready for manual restore)")


def _run_async_init(store: Store) -> None:
    """Run async initialization in a separate thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Set exception handler for Windows connection reset errors
    if os.name == 'nt':
        def suppress_connection_reset_error(loop, context):
            exception = context.get('exception')
            if isinstance(exception, ConnectionResetError):
                logger.debug("Suppressed ConnectionResetError during shutdown")
                return
            loop.default_exception_handler(context)
        loop.set_exception_handler(suppress_connection_reset_error)
    
    try:
        loop.run_until_complete(init_services(store))
        # Don't run forever - let the loop close properly
        logger.info("Services initialization completed")
    except Exception as e:
        logger.error(f"Error in async initialization: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        # Clean shutdown of the event loop
        try:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Wait for cancellation to complete
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            logger.warning(f"Error cleaning up tasks: {e}")
        finally:
            loop.close()


def main(page: ft.Page) -> None:
    """Main Flet application entry point."""
    logger.info("Initializing PyScrAI Forge...")

    # Hide the top bar and make the window frameless/transparent
    page.window.title_bar_hidden = False
    # page.window.title = "PyScrAI - Tyler Hamilton"
    page.window.bgcolor = ft.Colors.TRANSPARENT  # Use capital 'C'
    page.bgcolor = ft.Colors.TRANSPARENT         # Use capital 'C'

    # Initialize the EventBus and Store (replaces AppController)
    event_bus = EventBus()
    store = Store.initialize(event_bus)

    # Start services asynchronously in a background thread
    # This allows the UI to render immediately while services initialize
    init_thread = threading.Thread(
        target=_run_async_init,
        args=(store,),
        daemon=True,
        name="ServiceInitThread",
    )
    init_thread.start()

    # Build the shell UI immediately
    # SessionManager will be initialized in background thread and accessed via registry
    shell_view = build_shell(page, store)
    page.views.append(shell_view)
    # View is already added, no need for route navigation

    logger.info("Application initialized successfully")


if __name__ == "__main__":
    # Support web mode for testing via environment variable
    # When FLET_WEB_MODE=true, run in web mode (accessible via HTTP for Playwright)
    # Otherwise, run as desktop app (FLET_APP)
    if os.getenv("FLET_WEB_MODE") == "true":
        port = int(os.getenv("FLET_PORT", "8550"))
        logger.info(f"Starting Flet app in WEB mode on port {port} (for testing)")
        
        # DETERMINE RENDERER: Default to "html" for testing unless overridden
        # "html" exposes text nodes to DOM, required for Playwright text selectors
        renderer_env = os.getenv("FLET_WEB_RENDERER", "html").lower()
        renderer = ft.WebRenderer.AUTO if renderer_env == "auto" else ft.WebRenderer.CANVAS_KIT
        logger.info(f"Using web renderer: {renderer_env}")

        # Try FLET_APP_WEB first (no browser window), fall back to WEB_BROWSER if needed
        # In WSL2, we can suppress browser by unsetting DISPLAY if needed
        view_mode = ft.AppView.FLET_APP_WEB
        # If DISPLAY is not set or we want to suppress browser, FLET_APP_WEB should work
        # Otherwise WEB_BROWSER will open a browser window (but Playwright can still connect)
        if os.getenv("FLET_FORCE_WEB_BROWSER") == "true":
            view_mode = ft.AppView.WEB_BROWSER
        
        ft.run(
            main, 
            view=view_mode, 
            port=port, 
            host="127.0.0.1",
            web_renderer=renderer  # <--- CRITICAL FIX
        )
    else:
        logger.info("Starting Flet app in DESKTOP mode")
        ft.run(main, view=ft.AppView.FLET_APP)
