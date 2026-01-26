"""Service registry for cross-module access to initialized services."""

from __future__ import annotations

import atexit
import logging
from typing import Optional, TYPE_CHECKING, Dict, Any, List, Callable

if TYPE_CHECKING:
    from forge.shared.domain.context.session.session_manager import SessionManager

logger = logging.getLogger(__name__)

# Global reference to session manager
_session_manager: Optional["SessionManager"] = None

# Global registry for intelligence services that need database connection updates
_intelligence_services: Dict[str, Any] = {}

# Global cleanup management
_cleanup_registered = False
_cleanup_handlers: List[Callable[[], None]] = []


def set_session_manager(session_manager: "SessionManager") -> None:
    """Set the global session manager instance."""
    global _session_manager
    _session_manager = session_manager


def get_session_manager() -> Optional["SessionManager"]:
    """Get the global session manager instance."""
    return _session_manager


def register_intelligence_service(service_name: str, service: Any) -> None:
    """Register an intelligence service that needs database connection updates."""
    global _intelligence_services
    _intelligence_services[service_name] = service


def get_intelligence_services() -> Dict[str, Any]:
    """Get all registered intelligence services."""
    return _intelligence_services.copy()


def register_cleanup_handler(handler: Callable[[], None]) -> None:
    """Register a cleanup handler to be called on application exit."""
    global _cleanup_handlers, _cleanup_registered
    _cleanup_handlers.append(handler)
    if not _cleanup_registered:
        atexit.register(_cleanup_all)
        _cleanup_registered = True
        logger.debug("Registered atexit cleanup handler")


def _cleanup_all():
    """Clean up all registered handlers."""
    logger.info("Running application cleanup...")
    for handler in _cleanup_handlers:
        try:
            handler()
        except Exception as e:
            logger.warning(f"Error in cleanup handler: {e}")
    logger.info("Application cleanup completed")


def clear_intelligence_services() -> None:
    """Clear all registered intelligence services."""
    global _intelligence_services
    _intelligence_services.clear()