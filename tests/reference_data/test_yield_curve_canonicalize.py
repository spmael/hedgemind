"""
Tests for yield curve canonicalization service.

Tests the canonicalization logic including published_date assumptions,
curve-level staleness maintenance, and staleness calculations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.utils import timezone

from apps.reference_data.models import YieldCurvePoint
from apps.reference_data.services.yield_curves.canonicalize import (
    canonicalize_yield_curves,
)
from tests.factories import YieldCurveFactory, YieldCurvePointObservationFactory


class TestPublishedDateAssumption:
    """Test cases for published_date assumption logic."""

    def test_published_date_assumed_when_observed_at_none(
        self, yield_curve, market_data_source
    ):
        """Test that published_date is assumed when observed_at is None."""
        # Create observation without observed_at
        curve_date = date(2024, 1, 15)
        YieldCurvePointObservationFactory(
            curve=yield_curve,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=curve_date,
            observed_at=None,
        )

        # Canonicalize
        result = canonicalize_yield_curves(curve=yield_curve, as_of_date=curve_date)

        assert result["created"] == 1
        assert result["errors"] == []

        # Check canonical point
        point = YieldCurvePoint.objects.get(
            curve=yield_curve, tenor_days=1825, date=curve_date
        )
        # When observed_at is None, should assume published_date = curve_date
        assert point.last_published_date == curve_date
        assert point.published_date_assumed is True

    def test_published_date_uses_observed_at_date(
        self, yield_curve, market_data_source
    ):
        """Test that published_date uses observed_at.date() when observed_at is provided."""
        # Create observation with observed_at different from curve_date
        curve_date = date(2024, 1, 15)
        observed_at = timezone.now() - timedelta(days=5)
        YieldCurvePointObservationFactory(
            curve=yield_curve,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=curve_date,
            observed_at=observed_at,
        )

        # Canonicalize
        result = canonicalize_yield_curves(curve=yield_curve, as_of_date=curve_date)

        assert result["created"] == 1
        assert result["errors"] == []

        # Check canonical point
        point = YieldCurvePoint.objects.get(
            curve=yield_curve, tenor_days=1825, date=curve_date
        )
        # Should use observed_at.date(), not curve_date
        assert point.last_published_date == observed_at.date()
        assert point.published_date_assumed is False

    def test_published_date_consistent_for_same_curve_date(
        self, yield_curve, market_data_source
    ):
        """Test that same (curve, date) has same published_date for all tenors."""
        # Create observations for multiple tenors on same date
        observed_at = timezone.now() - timedelta(days=3)
        for tenor, tenor_days in [("1Y", 365), ("5Y", 1825), ("10Y", 3650)]:
            YieldCurvePointObservationFactory(
                curve=yield_curve,
                source=market_data_source,
                tenor=tenor,
                tenor_days=tenor_days,
                date=date(2024, 1, 15),
                observed_at=observed_at,
            )

        # Canonicalize
        result = canonicalize_yield_curves(
            curve=yield_curve, as_of_date=date(2024, 1, 15)
        )

        assert result["created"] == 3

        # All points should have same published_date
        points = YieldCurvePoint.objects.filter(
            curve=yield_curve, date=date(2024, 1, 15)
        )
        published_dates = {p.last_published_date for p in points}
        assert len(published_dates) == 1  # All same
        assert published_dates.pop() == observed_at.date()


class TestCurveLevelStalenessMaintenance:
    """Test cases for automatic curve-level staleness maintenance."""

    def test_curve_last_observation_date_updated_after_canonicalization(
        self, yield_curve, market_data_source
    ):
        """Test that curve.last_observation_date is updated after canonicalization."""
        # Initially no observation date
        assert yield_curve.last_observation_date is None

        # Create observations for multiple dates
        dates = [date(2024, 1, 15), date(2024, 2, 15), date(2024, 3, 15)]
        for obs_date in dates:
            YieldCurvePointObservationFactory(
                curve=yield_curve,
                source=market_data_source,
                tenor="5Y",
                tenor_days=1825,
                date=obs_date,
            )

        # Canonicalize
        result = canonicalize_yield_curves(curve=yield_curve)

        assert result["created"] == 3
        assert result["curves_updated"] == 1

        # Refresh curve from DB
        yield_curve.refresh_from_db()
        assert yield_curve.last_observation_date == date(2024, 3, 15)  # Max date

    def test_curve_last_observation_date_updates_on_new_points(
        self, yield_curve, market_data_source
    ):
        """Test that curve.last_observation_date updates when new points are added."""
        # Create initial observation
        YieldCurvePointObservationFactory(
            curve=yield_curve,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=date(2024, 1, 15),
        )

        # Canonicalize
        canonicalize_yield_curves(curve=yield_curve)
        yield_curve.refresh_from_db()
        assert yield_curve.last_observation_date == date(2024, 1, 15)

        # Add newer observation
        YieldCurvePointObservationFactory(
            curve=yield_curve,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=date(2024, 2, 20),
        )

        # Canonicalize again
        canonicalize_yield_curves(curve=yield_curve)
        yield_curve.refresh_from_db()
        assert yield_curve.last_observation_date == date(2024, 2, 20)  # Updated

    def test_curve_last_observation_date_handles_multiple_curves(
        self, market_data_source
    ):
        """Test that each curve's last_observation_date is updated independently."""
        curve1 = YieldCurveFactory(name="Curve 1")
        curve2 = YieldCurveFactory(name="Curve 2")

        # Create observations for different dates
        YieldCurvePointObservationFactory(
            curve=curve1,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=date(2024, 1, 15),
        )
        YieldCurvePointObservationFactory(
            curve=curve2,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=date(2024, 2, 20),
        )

        # Canonicalize all curves
        result = canonicalize_yield_curves()

        assert result["created"] == 2
        assert result["curves_updated"] == 2

        # Each curve should have its own max date
        curve1.refresh_from_db()
        curve2.refresh_from_db()
        assert curve1.last_observation_date == date(2024, 1, 15)
        assert curve2.last_observation_date == date(2024, 2, 20)


class TestStalenessCalculations:
    """Test cases for staleness_days property calculations."""

    def test_yield_curve_point_staleness_days(self, yield_curve, market_data_source):
        """Test YieldCurvePoint.staleness_days property."""
        # Create point with published date 10 days ago
        # Use a fixed date in the past to avoid timing issues
        today = date.today()
        published_date = today - timedelta(days=10)
        curve_date = date(2024, 1, 15)  # Fixed date for curve

        YieldCurvePointObservationFactory(
            curve=yield_curve,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=curve_date,
            observed_at=timezone.make_aware(
                datetime.combine(published_date, datetime.min.time())
            ),
        )

        canonicalize_yield_curves(curve=yield_curve, as_of_date=curve_date)

        point = YieldCurvePoint.objects.get(
            curve=yield_curve, tenor_days=1825, date=curve_date
        )
        # Staleness is calculated from today, so it should be approximately 10 days
        # Allow for 1 day variance due to test execution timing
        assert 9 <= point.staleness_days <= 11

    def test_yield_curve_point_staleness_none_when_no_published_date(
        self, yield_curve, market_data_source
    ):
        """Test that staleness_days is None when last_published_date is None."""
        # This shouldn't happen in practice (assumption sets it), but test edge case
        # Need to provide required fields: rate, tenor, selection_reason
        from apps.reference_data.models.choices import SelectionReason

        point = YieldCurvePoint.objects.create(
            curve=yield_curve,
            tenor="5Y",
            tenor_days=1825,
            rate=5.50,  # Required field
            date=date(2024, 1, 15),
            chosen_source=market_data_source,
            last_published_date=None,
            published_date_assumed=False,
            selection_reason=SelectionReason.AUTO_POLICY,
            selected_at=timezone.now(),
        )

        assert point.staleness_days is None

    def test_yield_curve_staleness_days(self, yield_curve, market_data_source):
        """Test YieldCurve.staleness_days property."""
        # Create point with observation date 15 days ago
        obs_date = date.today() - timedelta(days=15)
        YieldCurvePointObservationFactory(
            curve=yield_curve,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=obs_date,
        )

        canonicalize_yield_curves(curve=yield_curve, as_of_date=obs_date)

        yield_curve.refresh_from_db()
        assert yield_curve.staleness_days == 15

    def test_yield_curve_staleness_none_when_no_observation_date(self, yield_curve):
        """Test that curve staleness_days is None when last_observation_date is None."""
        assert yield_curve.last_observation_date is None
        assert yield_curve.staleness_days is None

    def test_staleness_future_date_handles_negative(
        self, yield_curve, market_data_source
    ):
        """Test that staleness handles future dates (negative days)."""
        # Create point with future date (shouldn't happen but test edge case)
        future_date = date.today() + timedelta(days=5)
        YieldCurvePointObservationFactory(
            curve=yield_curve,
            source=market_data_source,
            tenor="5Y",
            tenor_days=1825,
            date=future_date,
        )

        canonicalize_yield_curves(curve=yield_curve, as_of_date=future_date)

        yield_curve.refresh_from_db()
        # Staleness should be negative for future dates
        assert yield_curve.staleness_days == -5


class TestPrecedence:
    """Test cases for precedence: curve-level vs point-level staleness."""

    def test_curve_level_staleness_is_primary_indicator(
        self, yield_curve, market_data_source
    ):
        """Test that curve-level staleness is the primary indicator."""
        # Create points with different published dates
        dates = [date(2024, 1, 15), date(2024, 2, 15), date(2024, 3, 15)]
        for i, obs_date in enumerate(dates):
            # Vary published dates (older for earlier curve dates)
            published_at = timezone.now() - timedelta(days=30 + i * 5)
            YieldCurvePointObservationFactory(
                curve=yield_curve,
                source=market_data_source,
                tenor="5Y",
                tenor_days=1825,
                date=obs_date,
                observed_at=published_at,
            )

        canonicalize_yield_curves(curve=yield_curve)

        # Curve-level staleness should be based on max curve_date, not published dates
        yield_curve.refresh_from_db()
        assert yield_curve.last_observation_date == date(2024, 3, 15)
        # Curve staleness is days since last observation date (curve_date)
        assert yield_curve.staleness_days is not None

        # Point-level published_date is for audit/detail
        points = YieldCurvePoint.objects.filter(curve=yield_curve)
        for point in points:
            assert point.last_published_date is not None  # For audit trail
            assert point.published_date_assumed is False  # From observed_at
