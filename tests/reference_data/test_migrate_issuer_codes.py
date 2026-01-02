"""
Tests for migrate_issuer_codes management command.

Tests the migration command that updates existing issuers to structured
issuer code format.
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.reference_data.models.issuers import Issuer, IssuerGroup
from libs.tenant_context import organization_context
from tests.factories import IssuerFactory, OrganizationFactory


class TestMigrateIssuerCodes:
    """Test cases for migrate_issuer_codes command."""

    def test_migrate_issuer_codes_dry_run(self, org_context_with_org):
        """Test dry-run mode shows what would be updated."""
        # Create issuer and then clear issuer_code to simulate missing code
        issuer = IssuerFactory(name="Test Issuer", country="CM")
        Issuer.objects.filter(pk=issuer.pk).update(issuer_code=None)

        out = StringIO()
        call_command("migrate_issuer_codes", "--dry-run", stdout=out)
        output = out.getvalue()

        assert "DRY RUN" in output
        assert "migrate" in output.lower() or "issuer" in output.lower()

    def test_migrate_issuer_codes_no_issuers_to_migrate(self, org_context_with_org):
        """Test command when all issuers already have valid codes."""
        # Create issuer with valid code
        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")
        IssuerFactory(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group=issuer_group,
            issuer_code="CM-SOV-GOVT",
        )

        out = StringIO()
        call_command("migrate_issuer_codes", stdout=out)
        output = out.getvalue()

        assert (
            "No issuers need migration" in output
            or "All issuers have valid codes" in output
        )

    def test_migrate_issuer_codes_updates_missing_codes(self, org_context_with_org):
        """Test command updates issuers without issuer_code."""
        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")
        issuer = IssuerFactory(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group=issuer_group,
        )
        # Clear issuer_code to simulate missing code (bypass auto-generation)
        Issuer.objects.filter(pk=issuer.pk).update(issuer_code=None)
        issuer.refresh_from_db()

        assert issuer.issuer_code is None

        out = StringIO()
        call_command("migrate_issuer_codes", stdout=out)

        issuer.refresh_from_db()
        assert issuer.issuer_code is not None
        assert issuer.issuer_code.startswith("CM-SOV-")

    def test_migrate_issuer_codes_updates_invalid_codes(self, org_context_with_org):
        """Test command updates issuers with invalid format codes."""
        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")
        issuer = IssuerFactory(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group=issuer_group,
        )
        # Set invalid code using update to bypass validation
        Issuer.objects.filter(pk=issuer.pk).update(issuer_code="INVALID_FORMAT")
        issuer.refresh_from_db()

        out = StringIO()
        call_command("migrate_issuer_codes", stdout=out)

        issuer.refresh_from_db()
        assert issuer.issuer_code != "INVALID_FORMAT"
        assert issuer.issuer_code.startswith("CM-SOV-")

    def test_migrate_issuer_codes_handles_conflicts(self, org_context_with_org):
        """Test command handles conflicts by appending numbers."""
        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")

        # Create issuer with a code that would conflict
        issuer1 = IssuerFactory(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group=issuer_group,
            issuer_code="CM-SOV-GOVT",
        )

        # Create another issuer with different name but same country/group
        # This will generate same base code and trigger conflict resolution
        issuer2 = IssuerFactory(
            name="REPUBLIQUE DU CAMEROUN",  # Different name to avoid unique constraint
            country="CM",
            issuer_group=issuer_group,
        )
        # Clear issuer_code to simulate missing code
        Issuer.objects.filter(pk=issuer2.pk).update(issuer_code=None)
        issuer2.refresh_from_db()

        out = StringIO()
        call_command("migrate_issuer_codes", stdout=out)

        issuer2.refresh_from_db()
        # Should have different code due to conflict resolution
        assert issuer2.issuer_code != issuer1.issuer_code
        assert issuer2.issuer_code.startswith("CM-SOV-")

    def test_migrate_issuer_codes_creates_audit_event(self, org_context_with_org):
        """Test command creates audit event."""
        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")
        issuer = IssuerFactory(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group=issuer_group,
        )
        # Clear issuer_code to simulate missing code
        Issuer.objects.filter(pk=issuer.pk).update(issuer_code=None)

        initial_count = AuditEvent.objects.filter(action="MIGRATE_ISSUER_CODES").count()

        out = StringIO()
        call_command("migrate_issuer_codes", stdout=out)

        final_count = AuditEvent.objects.filter(action="MIGRATE_ISSUER_CODES").count()
        assert final_count > initial_count

        # Check audit event metadata
        event = AuditEvent.objects.filter(action="MIGRATE_ISSUER_CODES").latest(
            "created_at"
        )
        assert event.metadata is not None
        assert "updated_count" in event.metadata
        assert event.metadata["updated_count"] > 0

    def test_migrate_issuer_codes_multiple_organizations(self):
        """Test command works across multiple organizations."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")

        with organization_context(org1.id):
            issuer1 = IssuerFactory(
                name="ETAT DU CAMEROUN",
                country="CM",
                issuer_group=issuer_group,
                issuer_code=None,
            )

        with organization_context(org2.id):
            issuer2 = IssuerFactory(
                name="ETAT DU GABON",
                country="GA",
                issuer_group=issuer_group,
                issuer_code=None,
            )

        # Run command (should work across all orgs)
        out = StringIO()
        call_command("migrate_issuer_codes", stdout=out)

        issuer1.refresh_from_db()
        issuer2.refresh_from_db()

        assert issuer1.issuer_code is not None
        assert issuer2.issuer_code is not None
        assert issuer1.issuer_code.startswith("CM-SOV-")
        assert issuer2.issuer_code.startswith("GA-SOV-")

    def test_migrate_issuer_codes_empty_string_code(self, org_context_with_org):
        """Test command handles issuers with empty string issuer_code."""
        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")
        issuer = IssuerFactory(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group=issuer_group,
        )
        # Set to empty string (simulating old data)
        issuer.issuer_code = ""
        issuer.save(update_fields=["issuer_code"])

        out = StringIO()
        call_command("migrate_issuer_codes", stdout=out)

        issuer.refresh_from_db()
        assert issuer.issuer_code is not None
        assert issuer.issuer_code != ""
        assert issuer.issuer_code.startswith("CM-SOV-")

    def test_migrate_issuer_codes_with_actor_id(self, org_context_with_org, user):
        """Test command accepts actor_id parameter."""
        issuer_group = IssuerGroup.objects.create(code="SOV", name="Sovereign")
        issuer = IssuerFactory(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group=issuer_group,
        )
        # Clear issuer_code to simulate missing code
        Issuer.objects.filter(pk=issuer.pk).update(issuer_code=None)

        out = StringIO()
        call_command("migrate_issuer_codes", f"--actor-id={user.id}", stdout=out)

        # Check audit event has actor
        event = AuditEvent.objects.filter(action="MIGRATE_ISSUER_CODES").latest(
            "created_at"
        )
        assert event.actor == user
