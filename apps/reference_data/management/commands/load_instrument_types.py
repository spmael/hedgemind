"""
Management command to load canonical instrument types.

This command loads the industry-standard instrument types (e.g., COMMON_STOCK,
GOVERNMENT_BOND, DEPOSIT, etc.) into the database. Types are loaded within their
respective groups (EQUITY, FIXED_INCOME, etc.).

These types are shared across all organizations (global reference data). The
command is idempotent and can be run multiple times safely - it will create
missing types and update existing ones.

Prerequisites:
    Instrument groups must be loaded first using load_instrument_groups command.

Usage:
    python manage.py load_instrument_types
    python manage.py load_instrument_types --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.reference_data.canonical_data import get_canonical_groups
from apps.reference_data.models import InstrumentGroup, InstrumentType


class Command(BaseCommand):
    """
    Management command to load canonical instrument types.

    This command is idempotent and creates audit log entries for all operations.
    Types are loaded as global reference data (shared across all organizations).
    It requires that instrument groups be loaded first.
    """

    help = "Load canonical instrument types (idempotent, global reference data)"

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
            total_types = sum(len(group["types"]) for group in canonical_groups)
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would load {total_types} types across {len(canonical_groups)} groups "
                    "(global reference data)"
                )
            )
            for group_def in canonical_groups:
                self.stdout.write(f"\n{group_def['code']}: {group_def['name']}")
                for type_def in group_def["types"]:
                    self.stdout.write(f"  - {type_def['code']}: {type_def['name']}")
            return

        # Load types as global reference data
        created_count = 0
        updated_count = 0
        errors = []
        missing_groups = []

        try:
            with transaction.atomic():
                for group_def in canonical_groups:
                    # Get or verify the group exists
                    try:
                        group = InstrumentGroup.objects.get(name=group_def["code"])
                    except InstrumentGroup.DoesNotExist:
                        missing_groups.append(group_def["code"])
                        error_msg = (
                            f"Group '{group_def['code']}' not found. "
                            "Please run load_instrument_groups first."
                        )
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))
                        continue

                    # Load types for this group
                    for type_def in group_def["types"]:
                        try:
                            instrument_type, created = (
                                InstrumentType.objects.get_or_create(
                                    group=group,
                                    name=type_def["code"],
                                    defaults={
                                        "description": type_def["description"],
                                    },
                                )
                            )

                            if created:
                                created_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Created type: {group_def['code']}.{type_def['code']} - {type_def['name']}"
                                    )
                                )
                            else:
                                # Update description if it changed
                                if (
                                    instrument_type.description
                                    != type_def["description"]
                                ):
                                    instrument_type.description = type_def[
                                        "description"
                                    ]
                                    instrument_type.save(update_fields=["description"])
                                    updated_count += 1
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f"Updated type: {group_def['code']}.{type_def['code']} - {type_def['name']}"
                                        )
                                    )
                                else:
                                    self.stdout.write(
                                        f"Type already exists: {group_def['code']}.{type_def['code']} - {type_def['name']}"
                                    )
                        except Exception as e:
                            error_msg = f"Error processing type {group_def['code']}.{type_def['code']}: {str(e)}"
                            errors.append(error_msg)
                            self.stdout.write(self.style.ERROR(error_msg))

                # Create audit event (organization_id is None for global reference data)
                total_types = sum(len(group["types"]) for group in canonical_groups)
                if created_count > 0 or updated_count > 0 or errors:
                    AuditEvent.objects.create(
                        organization_id=None,  # Global reference data
                        actor=actor,
                        action="LOAD_REFERENCE_DATA",
                        object_type="InstrumentType",
                        object_repr=f"Loaded {total_types} canonical types",
                        metadata={
                            "types_loaded": total_types,
                            "types_created": created_count,
                            "types_updated": updated_count,
                            "missing_groups": missing_groups,
                            "errors": errors,
                            "command": "load_instrument_types",
                            "scope": "global",
                        },
                    )

        except Exception as e:
            raise CommandError(f"Failed to load instrument types: {str(e)}")

        # Summary
        total_types = sum(len(group["types"]) for group in canonical_groups)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted loading {total_types} instrument types (global reference data)"
            )
        )
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Errors: {len(errors)}")
        if missing_groups:
            self.stdout.write(
                self.style.WARNING(f"  Missing groups: {', '.join(missing_groups)}")
            )
        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    - {error}"))
