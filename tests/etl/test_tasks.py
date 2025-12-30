"""
Tests for ETL Celery tasks.
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from apps.etl.tasks import ping_etl, run_daily_close_task


class TestETLTasks:
    """Test cases for ETL tasks."""

    def test_ping_etl(self):
        """Test ping_etl task returns expected structure."""
        result = ping_etl()

        assert result["ok"] is True
        assert "timestamp" in result
        assert isinstance(result["timestamp"], str)

    def test_ping_etl_timestamp_format(self):
        """Test that ping_etl returns ISO format timestamp."""
        result = ping_etl()

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(result["timestamp"])
        assert isinstance(parsed, datetime)

    @patch("apps.etl.tasks.run_daily_close")
    def test_run_daily_close_task_success(self, mock_run_daily_close, organization):
        """Test run_daily_close_task with valid organization."""
        as_of_date = date(2025, 1, 1)
        mock_run_daily_close.return_value = [
            {"pipeline": "fx_daily", "status": "success"},
            {"pipeline": "prices_daily", "status": "success"},
        ]

        # For bind=True tasks, call .run() method directly
        result = run_daily_close_task.run(
            org_id=organization.id, as_of_iso_date=as_of_date.isoformat()
        )

        # Note: task reassigns org_id to Organization object (line 20 in tasks.py)
        assert result["org_id"] == organization
        assert result["as_of_iso_date"] == as_of_date.isoformat()
        assert "results" in result
        mock_run_daily_close.assert_called_once()

    def test_run_daily_close_task_invalid_org(self):
        """Test run_daily_close_task raises error for invalid organization."""
        from django.core.exceptions import ObjectDoesNotExist

        as_of_date = date(2025, 1, 1)

        with pytest.raises(ObjectDoesNotExist):
            run_daily_close_task.run(
                org_id=99999, as_of_iso_date=as_of_date.isoformat()
            )

    def test_run_daily_close_task_inactive_org(self, organization):
        """Test run_daily_close_task raises error for inactive organization."""
        from django.core.exceptions import ObjectDoesNotExist

        organization.is_active = False
        organization.save()

        as_of_date = date(2025, 1, 1)

        with pytest.raises(ObjectDoesNotExist):
            run_daily_close_task.run(
                org_id=organization.id,
                as_of_iso_date=as_of_date.isoformat(),
            )
