"""
Management command to load canonical instrument groups.

This command loads the industry-standard instrument groups (EQUITY, FIXED_INCOME,
CASH_EQUIVALENT, FUND, PRIVATE_ASSET, DERIVATIVE, OTHER) into the database.
These groups are shared across all organizations (global reference data).

The command is idempotent and can be run multiple times safely - it will create
missing groups and update existing ones.

Usage:
    python manage.py load_instrument_groups
    python manage.py load_instrument_groups --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.reference_data.canonical_data import get_canonical_groups
from apps.reference_data.models import InstrumentGroup


class Command(BaseCommand):
    """
    Management command to load canonical instrument groups.

    This module provides a Django management command for loading
    the industry-standard instrument groups (EQUITY, FIXED_INCOME,
    CASH_EQUIVALENT, FUND, PRIVATE_ASSET, DERIVATIVE, OTHER) into the database
    as global reference data shared across all organizations.

    Key components:
    - Idempotent group loader: Ensures all required groups exist and updates as needed.
    - Audit log integration: Records audit entries for created/updated groups.
    - CLI options: Supports --dry-run for preview and --actor-id for audit attribution.

    Usage example:
        python manage.py load_instrument_groups
        python manage.py load_instrument_groups --dry-run
        python manage.py load_instrument_groups --actor-id 42
    """

    help = "Load canonical instrument groups (idempotent, global reference data)"

    def add_arguments(self, parser):
        """
        Add command-line arguments.

        Args:
            parser: Argument parser instance.
        """
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating it",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """
        Execute the command.

        Args:
            *args: Positional arguments.
            **options: Command options.
        """
        dry_run = options["dry_run"]
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

        canonical_groups = get_canonical_groups()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would load {len(canonical_groups)} groups (global reference data)"
                )
            )
            for group_def in canonical_groups:
                self.stdout.write(f"  - {group_def['code']}: {group_def['name']}")
            return

        # Load groups as global reference data
        created_count = 0
        updated_count = 0
        errors = []

        try:
            with transaction.atomic():
                for group_def in canonical_groups:
                    try:
                        group, created = InstrumentGroup.objects.get_or_create(
                            name=group_def["code"],
                            defaults={
                                "description": group_def["description"],
                            },
                        )

                        if created:
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Created group: {group_def['code']} - {group_def['name']}"
                                )
                            )
                        else:
                            # Update description if it changed
                            if group.description != group_def["description"]:
                                group.description = group_def["description"]
                                group.save(update_fields=["description"])
                                updated_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Updated group: {group_def['code']} - {group_def['name']}"
                                    )
                                )
                            else:
                                self.stdout.write(
                                    f"Group already exists: {group_def['code']} - {group_def['name']}"
                                )
                    except Exception as e:
                        error_msg = (
                            f"Error processing group {group_def['code']}: {str(e)}"
                        )
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))

                # Create audit event (organization_id is None for global reference data)
                if created_count > 0 or updated_count > 0 or errors:
                    AuditEvent.objects.create(
                        organization_id=None,  # Global reference data
                        actor=actor,
                        action="LOAD_REFERENCE_DATA",
                        object_type="InstrumentGroup",
                        object_repr=f"Loaded {len(canonical_groups)} canonical groups",
                        metadata={
                            "groups_loaded": len(canonical_groups),
                            "groups_created": created_count,
                            "groups_updated": updated_count,
                            "errors": errors,
                            "command": "load_instrument_groups",
                            "scope": "global",
                        },
                    )

        except Exception as e:
            raise CommandError(f"Failed to load instrument groups: {str(e)}")

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted loading {len(canonical_groups)} instrument groups (global reference data)"
            )
        )
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Errors: {len(errors)}")
        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    - {error}"))
