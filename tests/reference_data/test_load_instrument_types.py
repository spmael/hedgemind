"""
Tests for load_instrument_types management command.
"""

from io import StringIO

from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.reference_data.models import InstrumentGroup, InstrumentType


class TestLoadInstrumentTypes:
    """Test cases for load_instrument_types command."""

    def test_load_instrument_types_handles_missing_groups(self):
        """Test command handles missing groups gracefully (doesn't crash)."""
        # Delete all groups
        InstrumentGroup.objects.all().delete()

        out = StringIO()
        call_command("load_instrument_types", stdout=out)
        output = out.getvalue()

        # Command should complete but show errors
        assert (
            "Missing groups" in output or "error" in output.lower() or "Error" in output
        )

    def test_load_instrument_types_dry_run(self):
        """Test dry-run mode shows what would be created."""
        # Ensure groups exist
        call_command("load_instrument_groups", stdout=StringIO())

        out = StringIO()
        call_command("load_instrument_types", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "DRY RUN" in output
        assert "types" in output.lower()

    def test_load_instrument_types_creates_types(self):
        """Test command creates canonical instrument types."""
        # Ensure groups exist
        call_command("load_instrument_groups", stdout=StringIO())

        initial_count = InstrumentType.objects.count()

        out = StringIO()
        call_command("load_instrument_types", stdout=out)
        output = out.getvalue()

        # Should have created types
        final_count = InstrumentType.objects.count()
        assert final_count > initial_count
        assert "Created" in output or "already exists" in output

    def test_load_instrument_types_idempotent(self):
        """Test command can be run multiple times safely."""
        # Ensure groups exist
        call_command("load_instrument_groups", stdout=StringIO())

        out1 = StringIO()
        call_command("load_instrument_types", stdout=out1)

        initial_count = InstrumentType.objects.count()

        out2 = StringIO()
        call_command("load_instrument_types", stdout=out2)

        # Count should be same (idempotent)
        final_count = InstrumentType.objects.count()
        assert final_count == initial_count

    def test_load_instrument_types_with_actor_id(self, user):
        """Test command creates audit event with actor."""
        # Ensure groups exist
        call_command("load_instrument_groups", stdout=StringIO())

        out = StringIO()
        call_command("load_instrument_types", f"--actor-id={user.id}", stdout=out)

        # Check audit event was created
        audit_events = AuditEvent.objects.filter(
            action="LOAD_REFERENCE_DATA",
            object_type="InstrumentType",
            actor=user,
        )
        assert audit_events.exists()

    def test_load_instrument_types_audit_event_created(self):
        """Test command creates audit event."""
        # Ensure groups exist
        call_command("load_instrument_groups", stdout=StringIO())

        initial_count = AuditEvent.objects.filter(
            action="LOAD_REFERENCE_DATA",
            object_type="InstrumentType",
        ).count()

        out = StringIO()
        call_command("load_instrument_types", stdout=out)

        final_count = AuditEvent.objects.filter(
            action="LOAD_REFERENCE_DATA",
            object_type="InstrumentType",
        ).count()

        assert final_count > initial_count
