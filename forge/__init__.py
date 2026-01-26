"""PyScrAI Forge package."""

from .shared.core.event_bus import EventBus

# Store and AppState require fletx, so import them lazily/optionally
try:
    from .extractor.state.store import Store
    from .extractor.state.app_state import AppState
    __all__ = ["Store", "AppState", "EventBus"]
except ImportError:
    # fletx not installed (e.g., in test environments)
    __all__ = ["EventBus"]
