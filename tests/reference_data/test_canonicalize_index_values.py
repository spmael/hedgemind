"""
Tests for index values canonicalization service.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.utils import timezone

from apps.reference_data.models import MarketIndexValue, MarketIndexValueObservation
from apps.reference_data.services.indices.canonicalize import canonicalize_index_values
from tests.factories import (
    MarketDataSourceFactory,
    MarketIndexFactory,
    MarketIndexValueObservationFactory,
)


class TestCanonicalizeIndexValues:
    """Test cases for index values canonicalization service."""

    def test_canonicalize_index_values_basic(self, market_index, market_data_source):
        """Test basic canonicalization of index values."""
        # Create observations with different priorities
        source1 = MarketDataSourceFactory(priority=1)  # Higher priority
        source2 = MarketDataSourceFactory(priority=10)  # Lower priority

        obs1 = MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=100.0,
            source=source1,
        )
        obs2 = MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=101.0,
            source=source2,
        )

        result = canonicalize_index_values(
            index_code=market_index.code,
            as_of_date=date(2024, 1, 1),
        )

        assert result["created"] == 1
        assert result["updated"] == 0
        assert result["skipped"] == 0
        assert len(result["errors"]) == 0

        # Verify canonical value uses higher priority source
        canonical = MarketIndexValue.objects.get(
            index=market_index, date=date(2024, 1, 1)
        )
        assert canonical.chosen_source == source1
        assert canonical.value == 100.0
        assert canonical.observation == obs1

    def test_canonicalize_index_values_date_range(self, market_index, market_data_source):
        """Test canonicalization with date range."""
        source = MarketDataSourceFactory(priority=1)

        # Create observations for multiple dates
        MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=100.0,
            source=source,
        )
        MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 2),
            value=101.0,
            source=source,
        )
        MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 3),
            value=102.0,
            source=source,
        )

        result = canonicalize_index_values(
            index_code=market_index.code,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
        )

        assert result["created"] == 2
        assert MarketIndexValue.objects.filter(index=market_index).count() == 2

    def test_canonicalize_index_values_revision_priority(
        self, market_index, market_data_source
    ):
        """Test canonicalization uses most recent revision when same priority."""
        source = MarketDataSourceFactory(priority=1)

        obs1 = MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=100.0,
            source=source,
            revision=0,
        )
        obs2 = MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=101.0,
            source=source,
            revision=1,  # More recent revision
        )

        result = canonicalize_index_values(
            index_code=market_index.code,
            as_of_date=date(2024, 1, 1),
        )

        assert result["created"] == 1

        # Verify canonical value uses most recent revision
        canonical = MarketIndexValue.objects.get(
            index=market_index, date=date(2024, 1, 1)
        )
        assert canonical.observation == obs2
        assert canonical.value == 101.0

    def test_canonicalize_index_values_invalid_index_code(self):
        """Test canonicalization fails gracefully for invalid index code."""
        result = canonicalize_index_values(index_code="INVALID")

        assert result["created"] == 0
        assert result["updated"] == 0
        assert len(result["errors"]) == 1
        assert "not found" in result["errors"][0].lower()

    def test_canonicalize_index_values_all_indices(self, market_index, market_data_source):
        """Test canonicalization processes all indices when index_code not specified."""
        source = MarketDataSourceFactory(priority=1)

        # Create another index
        index2 = MarketIndexFactory(code="INDEX2")

        MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=100.0,
            source=source,
        )
        MarketIndexValueObservationFactory(
            index=index2,
            date=date(2024, 1, 1),
            value=200.0,
            source=source,
        )

        result = canonicalize_index_values()

        assert result["created"] == 2
        assert MarketIndexValue.objects.count() == 2

    def test_canonicalize_index_values_updates_existing(
        self, market_index, market_data_source
    ):
        """Test canonicalization updates existing canonical values."""
        source1 = MarketDataSourceFactory(priority=1)
        source2 = MarketDataSourceFactory(priority=2)

        # Create existing canonical value
        MarketIndexValue.objects.create(
            index=market_index,
            date=date(2024, 1, 1),
            value=99.0,
            chosen_source=source2,
            selection_reason="auto_policy",
            selected_at=timezone.now(),
        )

        # Create new observation with higher priority
        obs = MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=100.0,
            source=source1,
        )

        result = canonicalize_index_values(
            index_code=market_index.code,
            as_of_date=date(2024, 1, 1),
        )

        assert result["created"] == 0
        assert result["updated"] == 1

        # Verify canonical value was updated
        canonical = MarketIndexValue.objects.get(
            index=market_index, date=date(2024, 1, 1)
        )
        assert canonical.chosen_source == source1
        assert canonical.value == 100.0
        assert canonical.observation == obs

    def test_canonicalize_index_values_only_active_sources(
        self, market_index, market_data_source
    ):
        """Test canonicalization only uses active sources."""
        source_active = MarketDataSourceFactory(priority=1, is_active=True)
        source_inactive = MarketDataSourceFactory(priority=2, is_active=False)

        obs_active = MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=100.0,
            source=source_active,
        )
        MarketIndexValueObservationFactory(
            index=market_index,
            date=date(2024, 1, 1),
            value=101.0,
            source=source_inactive,
        )

        result = canonicalize_index_values(
            index_code=market_index.code,
            as_of_date=date(2024, 1, 1),
        )

        assert result["created"] == 1

        # Verify canonical value uses only active source
        canonical = MarketIndexValue.objects.get(
            index=market_index, date=date(2024, 1, 1)
        )
        assert canonical.chosen_source == source_active
        assert canonical.value == 100.0
        assert canonical.observation == obs_active

