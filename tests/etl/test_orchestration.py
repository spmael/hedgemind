"""
Tests for ETL orchestration.
"""

from datetime import date

from apps.etl.orchestration.daily_close import run_daily_close


class TestDailyClose:
    """Test cases for daily close orchestration."""

    def test_run_daily_close(self):
        """Test that daily close runs all pipelines."""
        as_of = date(2025, 1, 1)
        results = run_daily_close(as_of=as_of)

        assert len(results) == 2
        assert results[0]["pipeline"] == "fx_daily"
        assert results[1]["pipeline"] == "prices_daily"
        assert all(result["as_of"] == "2025-01-01" for result in results)

    def test_run_daily_close_returns_list(self):
        """Test that daily close returns a list of results."""
        as_of = date(2025, 1, 1)
        results = run_daily_close(as_of=as_of)

        assert isinstance(results, list)
        assert len(results) > 0

    def test_run_daily_close_all_pipelines_executed(self):
        """Test that all expected pipelines are executed."""
        as_of = date(2025, 6, 15)
        results = run_daily_close(as_of=as_of)

        pipeline_names = [result["pipeline"] for result in results]
        assert "fx_daily" in pipeline_names
        assert "prices_daily" in pipeline_names

    def test_run_daily_close_different_dates(self):
        """Test daily close with different as-of dates."""
        dates = [
            date(2025, 1, 1),
            date(2025, 6, 15),
            date(2025, 12, 31),
        ]

        for as_of in dates:
            results = run_daily_close(as_of=as_of)
            assert all(result["as_of"] == as_of.isoformat() for result in results)
