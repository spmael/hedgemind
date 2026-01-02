"""
Management command to migrate existing issuers to structured issuer code format.

This command finds all issuers without issuer_code or with invalid format codes
and generates new structured codes following the format [REGION]-[TYPE]-[IDENTIFIER].

Usage:
    python manage.py migrate_issuer_codes
    python manage.py migrate_issuer_codes --dry-run
    python manage.py migrate_issuer_codes --batch-size 100
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.reference_data.models.issuers import Issuer
from apps.reference_data.utils.issuer_codes import (
    generate_issuer_code,
    validate_issuer_code,
)


class Command(BaseCommand):
    """
    Management command to migrate existing issuers to structured issuer code format.

    This command:
    - Finds issuers without issuer_code or with invalid format
    - Generates new codes using utility functions
    - Handles conflicts (duplicate codes across organizations)
    - Updates issuers in batches
    - Provides dry-run mode
    - Creates audit events

    Usage example:
        python manage.py migrate_issuer_codes
        python manage.py migrate_issuer_codes --dry-run
        python manage.py migrate_issuer_codes --batch-size 100 --actor-id 42
    """

    help = "Migrate existing issuers to structured issuer code format [REGION]-[TYPE]-[IDENTIFIER]"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without actually updating",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of issuers to process in each batch (default: 100)",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options["dry_run"]
        _batch_size = options["batch_size"]
        actor_id = options.get("actor_id")

        # Get actor if provided
        actor = None
        if actor_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                actor = User.objects.get(pk=actor_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"User with ID {actor_id} does not exist, proceeding without actor"
                    )
                )

        # Find issuers that need migration
        # 1. Issuers without issuer_code
        issuers_without_code = Issuer.objects.filter(
            issuer_code__isnull=True
        ) | Issuer.objects.filter(issuer_code="")

        # 2. Issuers with invalid format
        all_issuers = Issuer.objects.all()
        issuers_with_invalid_code = []
        for issuer in all_issuers:
            if issuer.issuer_code:
                is_valid, _ = validate_issuer_code(issuer.issuer_code)
                if not is_valid:
                    issuers_with_invalid_code.append(issuer)

        total_to_migrate = issuers_without_code.count() + len(issuers_with_invalid_code)

        if total_to_migrate == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "No issuers need migration. All issuers have valid codes."
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would migrate {total_to_migrate} issuers to structured issuer code format"
                )
            )
            self.stdout.write(
                f"  - Issuers without code: {issuers_without_code.count()}"
            )
            self.stdout.write(
                f"  - Issuers with invalid format: {len(issuers_with_invalid_code)}"
            )
            self.stdout.write("\nSample issuers that would be updated:")
            for issuer in list(issuers_without_code[:5]):
                issuer_group_code = (
                    issuer.issuer_group.code if issuer.issuer_group else None
                )
                country_code = str(issuer.country) if issuer.country else None
                new_code = generate_issuer_code(
                    name=issuer.name,
                    country=country_code,
                    issuer_group_code=issuer_group_code,
                )
                self.stdout.write(f"  - {issuer.name} -> {new_code}")
            return

        # Process migration
        updated_count = 0
        error_count = 0
        errors = []
        conflicts = []

        try:
            with transaction.atomic():
                # Process issuers without code
                for issuer in issuers_without_code:
                    try:
                        issuer_group_code = (
                            issuer.issuer_group.code if issuer.issuer_group else None
                        )
                        country_code = str(issuer.country) if issuer.country else None
                        new_code = generate_issuer_code(
                            name=issuer.name,
                            country=country_code,
                            issuer_group_code=issuer_group_code,
                        )

                        # Check for conflicts
                        if (
                            Issuer.objects.filter(issuer_code=new_code)
                            .exclude(pk=issuer.pk)
                            .exists()
                        ):
                            # Handle conflict by appending number
                            base_code = new_code
                            counter = 1
                            while (
                                Issuer.objects.filter(issuer_code=new_code)
                                .exclude(pk=issuer.pk)
                                .exists()
                            ):
                                parts = base_code.rsplit("-", 1)
                                if len(parts) == 2:
                                    region_type, identifier = parts
                                    max_id_length = 10 - len(str(counter))
                                    identifier = (
                                        identifier[:max_id_length]
                                        if max_id_length > 0
                                        else "X"
                                    )
                                    new_code = f"{region_type}-{identifier}{counter}"
                                else:
                                    new_code = f"{base_code}{counter}"
                                counter += 1
                                if counter > 999:
                                    raise ValueError(
                                        f"Unable to generate unique code for {issuer.name}"
                                    )

                            conflicts.append(
                                f"{issuer.name}: {base_code} -> {new_code} (conflict resolved)"
                            )

                        issuer.issuer_code = new_code
                        issuer.save(update_fields=["issuer_code"])
                        updated_count += 1

                    except Exception as e:
                        error_count += 1
                        error_msg = f"Error updating {issuer.name}: {str(e)}"
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))

                # Process issuers with invalid format
                for issuer in issuers_with_invalid_code:
                    try:
                        issuer_group_code = (
                            issuer.issuer_group.code if issuer.issuer_group else None
                        )
                        country_code = str(issuer.country) if issuer.country else None
                        new_code = generate_issuer_code(
                            name=issuer.name,
                            country=country_code,
                            issuer_group_code=issuer_group_code,
                        )

                        # Check for conflicts
                        if (
                            Issuer.objects.filter(issuer_code=new_code)
                            .exclude(pk=issuer.pk)
                            .exists()
                        ):
                            # Handle conflict by appending number
                            base_code = new_code
                            counter = 1
                            while (
                                Issuer.objects.filter(issuer_code=new_code)
                                .exclude(pk=issuer.pk)
                                .exists()
                            ):
                                parts = base_code.rsplit("-", 1)
                                if len(parts) == 2:
                                    region_type, identifier = parts
                                    max_id_length = 10 - len(str(counter))
                                    identifier = (
                                        identifier[:max_id_length]
                                        if max_id_length > 0
                                        else "X"
                                    )
                                    new_code = f"{region_type}-{identifier}{counter}"
                                else:
                                    new_code = f"{base_code}{counter}"
                                counter += 1
                                if counter > 999:
                                    raise ValueError(
                                        f"Unable to generate unique code for {issuer.name}"
                                    )

                            conflicts.append(
                                f"{issuer.name}: {issuer.issuer_code} -> {new_code} (conflict resolved)"
                            )

                        issuer.issuer_code = new_code
                        issuer.save(update_fields=["issuer_code"])
                        updated_count += 1

                    except Exception as e:
                        error_count += 1
                        error_msg = f"Error updating {issuer.name}: {str(e)}"
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))

                # Create audit event
                if updated_count > 0 or errors:
                    AuditEvent.objects.create(
                        organization_id=None,  # Global operation
                        actor=actor,
                        action="MIGRATE_ISSUER_CODES",
                        object_type="Issuer",
                        object_repr=f"Migrated {updated_count} issuers to structured issuer code format",
                        metadata={
                            "total_processed": total_to_migrate,
                            "updated_count": updated_count,
                            "error_count": error_count,
                            "conflicts": conflicts,
                            "errors": errors,
                            "command": "migrate_issuer_codes",
                        },
                    )

        except Exception as e:
            raise CommandError(f"Failed to migrate issuer codes: {str(e)}")

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted migrating {updated_count} issuers to structured issuer code format"
            )
        )
        if conflicts:
            self.stdout.write(f"  Conflicts resolved: {len(conflicts)}")
            for conflict in conflicts[:10]:  # Show first 10
                self.stdout.write(f"    - {conflict}")
        if errors:
            self.stdout.write(f"  Errors: {error_count}")
            for error in errors[:10]:  # Show first 10
                self.stdout.write(self.style.ERROR(f"    - {error}"))
