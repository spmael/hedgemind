"""
Tests for load_instrument_groups management command.
"""

from io import StringIO

from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.reference_data.models import InstrumentGroup


class TestLoadInstrumentGroups:
    """Test cases for load_instrument_groups command."""

    def test_load_instrument_groups_dry_run(self):
        """Test dry-run mode shows what would be created."""
        out = StringIO()
        call_command("load_instrument_groups", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "DRY RUN" in output
        assert "groups" in output.lower()

    def test_load_instrument_groups_creates_groups(self):
        """Test command creates canonical instrument groups."""
        # Count existing groups
        initial_count = InstrumentGroup.objects.count()

        out = StringIO()
        call_command("load_instrument_groups", stdout=out)
        output = out.getvalue()

        # Should have created groups
        final_count = InstrumentGroup.objects.count()
        assert final_count > initial_count
        assert "Created" in output or "already exists" in output

    def test_load_instrument_groups_idempotent(self):
        """Test command can be run multiple times safely."""
        out1 = StringIO()
        call_command("load_instrument_groups", stdout=out1)

        initial_count = InstrumentGroup.objects.count()

        out2 = StringIO()
        call_command("load_instrument_groups", stdout=out2)

        # Count should be same (idempotent)
        final_count = InstrumentGroup.objects.count()
        assert final_count == initial_count

    def test_load_instrument_groups_with_actor_id(self, user):
        """Test command creates audit event with actor."""
        out = StringIO()
        call_command("load_instrument_groups", f"--actor-id={user.id}", stdout=out)

        # Check audit event was created
        audit_events = AuditEvent.objects.filter(
            action="LOAD_REFERENCE_DATA",
            object_type="InstrumentGroup",
            actor=user,
        )
        assert audit_events.exists()

    def test_load_instrument_groups_audit_event_created(self):
        """Test command creates audit event."""
        initial_count = AuditEvent.objects.filter(
            action="LOAD_REFERENCE_DATA",
            object_type="InstrumentGroup",
        ).count()

        out = StringIO()
        call_command("load_instrument_groups", stdout=out)

        final_count = AuditEvent.objects.filter(
            action="LOAD_REFERENCE_DATA",
            object_type="InstrumentGroup",
        ).count()

        assert final_count > initial_count

    def test_load_instrument_groups_creates_canonical_groups(self):
        """Test that canonical groups are created."""
        out = StringIO()
        call_command("load_instrument_groups", stdout=out)

        # Check for expected canonical groups
        expected_groups = ["EQUITY", "FIXED_INCOME", "CASH_EQUIVALENT", "FUND"]
        for group_name in expected_groups:
            assert InstrumentGroup.objects.filter(name=group_name).exists()
