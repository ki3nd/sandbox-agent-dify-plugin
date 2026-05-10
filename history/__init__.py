"""History storage for sandbox agent."""

from history.models import Turn, TurnMessage, HistoryData

__all__ = [
    # Models
    "Turn",
    "TurnMessage",
    "HistoryData",
]


# Lazy imports for components that depend on dify_plugin
def get_converter():
    """Get converter module (requires dify_plugin)."""
    from history import converter
    return converter


def get_manager():
    """Get HistoryManager class (requires dify_plugin)."""
    from history.manager import HistoryManager
    return HistoryManager
