"""PyScrAI Forge package."""

from importlib import import_module
from typing import Any

from .shared.core.event_bus import EventBus

__all__ = ["EventBus"]

# Store and AppState depend on optional fletx; import dynamically when present
try:
    Store = import_module("forge.extractor.state.store").Store  # type: ignore[attr-defined]
    AppState = import_module("forge.extractor.state.app_state").AppState  # type: ignore[attr-defined]
    __all__ = ["Store", "AppState", "EventBus"]
except Exception:
    # Keep exports lean when optional deps are absent
    Store = Any  # type: ignore[assignment]
    AppState = Any  # type: ignore[assignment]
