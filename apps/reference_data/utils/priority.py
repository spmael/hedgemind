"""
Utilities for resolving market data source priorities.

Provides functions to get effective priority for a source, checking
org-specific overrides first, then falling back to global priority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.reference_data.models import MarketDataSource

from apps.reference_data.models import MarketDataSourcePriority
from libs.tenant_context import get_current_org_id


def get_effective_priority(
    source: MarketDataSource, data_type: str, org_id: int | None = None
) -> int:
    """
    Get effective priority for a market data source.

    Checks organization-specific priority override first, then falls back to
    global MarketDataSource.priority.

    Args:
        source: MarketDataSource instance.
        data_type: Data type ("fx_rate", "price", "yield_curve", "index_value").
        org_id: Organization ID (if None, uses current org context).

    Returns:
        int: Effective priority value (lower = higher priority).

    Example:
        >>> source = MarketDataSource.objects.get(code="BEAC")
        >>> priority = get_effective_priority(source, "fx_rate", org_id=1)
        >>> # Returns org-specific priority if set, else source.priority
    """
    # Use provided org_id or get from context
    if org_id is None:
        org_id = get_current_org_id()

    # If no org context, return global priority
    if org_id is None:
        return source.priority

    # Check for org-specific override
    try:
        override = MarketDataSourcePriority.objects.get(
            organization_id=org_id,
            data_type=data_type,
            source=source,
        )
        return override.priority
    except MarketDataSourcePriority.DoesNotExist:
        # No override, use global priority
        return source.priority


def get_source_priorities_for_org(
    data_type: str, org_id: int | None = None
) -> dict[int, int]:
    """
    Get priority map for all sources for a given organization and data type.

    Returns a dictionary mapping source_id -> effective_priority, including
    both org-specific overrides and global priorities.

    Args:
        data_type: Data type ("fx_rate", "price", "yield_curve", "index_value").
        org_id: Organization ID (if None, uses current org context).

    Returns:
        dict: Mapping of source_id -> effective_priority.

    Example:
        >>> priorities = get_source_priorities_for_org("fx_rate", org_id=1)
        >>> # Returns: {1: 1, 2: 2, 3: 50, ...}  (source_id: priority)
    """
    from apps.reference_data.models import MarketDataSource

    # Use provided org_id or get from context
    if org_id is None:
        org_id = get_current_org_id()

    # Get all active sources
    sources = MarketDataSource.objects.filter(is_active=True)

    # Build priority map
    priority_map = {}

    if org_id is not None:
        # Get org-specific overrides
        overrides = {
            override.source_id: override.priority
            for override in MarketDataSourcePriority.objects.filter(
                organization_id=org_id,
                data_type=data_type,
            ).select_related("source")
        }

        # Build map: override if exists, else global priority
        for source in sources:
            priority_map[source.id] = overrides.get(source.id, source.priority)
    else:
        # No org context, use global priorities
        for source in sources:
            priority_map[source.id] = source.priority

    return priority_map

