"""
Action logging components for the intelligent sandbox system.

Handles comprehensive logging of all sandbox activities and execution history.
"""

from .interfaces import ActionLoggerInterface
from .logger import ActionLogger
from .database import DatabaseActionLogger
from .models import Action, LogQuery, LogSummary
from .history import ExecutionHistoryTracker, VerifiedOutcome, OutcomeStatus

def create_logger(storage_type: str = "memory", db_path: str = None) -> ActionLoggerInterface:
    """
    Factory function to create appropriate logger instance.
    
    Args:
        storage_type: Type of storage ("memory" or "database")
        db_path: Path to database file (for database storage)
        
    Returns:
        ActionLoggerInterface implementation
    """
    if storage_type == "database":
        return DatabaseActionLogger(db_path)
    elif storage_type == "memory":
        return ActionLogger()
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")

__all__ = [
    'ActionLoggerInterface',
    'ActionLogger',
    'DatabaseActionLogger',
    'Action',
    'LogQuery',
    'LogSummary',
    'ExecutionHistoryTracker',
    'VerifiedOutcome',
    'OutcomeStatus',
    'create_logger'
]