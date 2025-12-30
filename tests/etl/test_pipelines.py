"""
Tests for ETL pipelines.
"""

from datetime import date

from apps.etl.pipelines.market_data_fx_daily import run_fx_daily
from apps.etl.pipelines.prices_daily import run_prices_daily


class TestFXDailyPipeline:
    """Test cases for FX daily pipeline."""

    def test_run_fx_daily_placeholder(self):
        """Test that placeholder returns expected structure."""
        as_of = date(2025, 1, 1)
        result = run_fx_daily(as_of=as_of)

        assert result["pipeline"] == "fx_daily"
        assert result["status"] == "not_implemented"
        assert result["as_of"] == "2025-01-01"
        assert "message" in result
        assert isinstance(result, dict)

    def test_run_fx_daily_different_dates(self):
        """Test FX daily pipeline with different dates."""
        dates = [
            date(2025, 1, 1),
            date(2025, 6, 15),
            date(2025, 12, 31),
        ]

        for as_of in dates:
            result = run_fx_daily(as_of=as_of)
            assert result["as_of"] == as_of.isoformat()
            assert result["pipeline"] == "fx_daily"


class TestPricesDailyPipeline:
    """Test cases for prices daily pipeline."""

    def test_run_prices_daily_placeholder(self):
        """Test that placeholder returns expected structure."""
        as_of = date(2025, 1, 1)
        result = run_prices_daily(as_of=as_of)

        assert result["pipeline"] == "prices_daily"
        assert result["status"] == "not_implemented"
        assert result["as_of"] == "2025-01-01"
        assert "message" in result
        assert isinstance(result, dict)

    def test_run_prices_daily_different_dates(self):
        """Test prices daily pipeline with different dates."""
        dates = [
            date(2025, 1, 1),
            date(2025, 6, 15),
            date(2025, 12, 31),
        ]

        for as_of in dates:
            result = run_prices_daily(as_of=as_of)
            assert result["as_of"] == as_of.isoformat()
            assert result["pipeline"] == "prices_daily"
