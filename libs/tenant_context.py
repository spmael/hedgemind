"""
Thread-local organization context for per-request or per-task execution.

Why use this?
- Enforces organization scoping automatically throughout services and tasks.
- Eliminates the need to thread org_id manually through every function.
- Caution: For Celery or multi-process tasks, always pass org_id as an explicit argument—thread-local context is not shared across processes.
"""
from __future__ import annotations
import threading
from contextlib import contextmanager
from typing import Optional, Generator

_state = threading.local()

def set_current_org_id(org_id: Optional[int]) -> None:
    """
    Sets the current organization ID in thread-local storage.

    Args:
        org_id (Optional[int]): The organization ID to set, or None to clear.
    """
    _state.org_id = org_id

def get_current_org_id() -> Optional[int]:
    """
    Retrieves the current organization ID from thread-local storage.

    Returns:
        Optional[int]: The current organization ID, or None if not set.
    """
    return getattr(_state, "org_id", None)

@contextmanager
def organization_context(org_id: Optional[int]) -> Generator[None, None, None]:
    """
    Context manager to temporarily set the organization ID in thread-local storage.

    On exit, restores the previous organization ID.
    Useful to scope code execution (requests, tasks) to a given organization.

    Args:
        org_id (Optional[int]): The organization ID to set within the context.
    """
    prev_org_id = get_current_org_id()
    set_current_org_id(org_id)
    try:
        yield
    finally:
        set_current_org_id(prev_org_id)