"""
Tests for load_reference_data management command.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from apps.reference_data.models import InstrumentGroup, InstrumentType


class TestLoadReferenceData:
    """Test cases for load_reference_data command."""

    def test_load_reference_data_dry_run(self):
        """Test dry-run mode."""
        out = StringIO()
        call_command("load_reference_data", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "Loading canonical reference data" in output

    def test_load_reference_data_calls_both_commands(self):
        """Test command calls both load_instrument_groups and load_instrument_types."""
        # Patch call_command in the command module's namespace
        with patch(
            "apps.reference_data.management.commands.load_reference_data.call_command"
        ) as mock_call:
            out = StringIO()
            call_command("load_reference_data", stdout=out)

            # Should call both commands
            assert mock_call.call_count == 2
            calls = [call[0][0] for call in mock_call.call_args_list]
            assert "load_instrument_groups" in calls
            assert "load_instrument_types" in calls

    def test_load_reference_data_with_actor_id(self, user):
        """Test command passes actor-id to subcommands."""
        # Patch call_command in the command module's namespace
        with patch(
            "apps.reference_data.management.commands.load_reference_data.call_command"
        ) as mock_call:
            out = StringIO()
            call_command("load_reference_data", f"--actor-id={user.id}", stdout=out)

            # Check actor_id was passed to subcommands
            for call in mock_call.call_args_list:
                kwargs = call[1] if len(call) > 1 else {}
                assert kwargs.get("actor_id") == user.id

    def test_load_reference_data_creates_data(self):
        """Test command actually creates groups and types."""
        # Clear existing data
        InstrumentType.objects.all().delete()
        InstrumentGroup.objects.all().delete()

        out = StringIO()
        call_command("load_reference_data", stdout=out)

        # Should have created groups and types
        assert InstrumentGroup.objects.count() > 0
        assert InstrumentType.objects.count() > 0

    def test_load_reference_data_idempotent(self):
        """Test command can be run multiple times safely."""
        out1 = StringIO()
        call_command("load_reference_data", stdout=out1)

        initial_group_count = InstrumentGroup.objects.count()
        initial_type_count = InstrumentType.objects.count()

        out2 = StringIO()
        call_command("load_reference_data", stdout=out2)

        # Counts should be same (idempotent)
        assert InstrumentGroup.objects.count() == initial_group_count
        assert InstrumentType.objects.count() == initial_type_count
