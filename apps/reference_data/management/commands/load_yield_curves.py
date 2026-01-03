"""
Management command to load canonical yield curve definitions.

This command loads common government yield curves for CEMAC region countries
(XAF currency) into the database. These curves are shared across all organizations
(global reference data).

The command is idempotent and can be run multiple times safely - it will create
missing curves and update existing ones.

Note: This command only creates YieldCurve records (metadata). Yield curve points
(observations) must be imported separately using the import_yield_curve_excel command.

Usage:
    python manage.py load_yield_curves
    python manage.py load_yield_curves --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.reference_data.canonical_data import get_canonical_yield_curves
from apps.reference_data.models import YieldCurve


class Command(BaseCommand):
    """
    Management command to load canonical yield curve definitions.

    This module provides a Django management command for loading common
    government yield curves (e.g., Cameroon, Gabon, Congo) into the database
    as global reference data shared across all organizations.

    Key components:
    - Idempotent curve loader: Ensures all required curves exist and updates as needed.
    - Audit log integration: Records audit entries for created/updated curves.
    - CLI options: Supports --dry-run for preview and --actor-id for audit attribution.

    Usage example:
        python manage.py load_yield_curves
        python manage.py load_yield_curves --dry-run
        python manage.py load_yield_curves --actor-id 42

    Note:
        This command only creates YieldCurve records (metadata). To import actual
        yield curve points (observations), use the import_yield_curve_excel command.
    """

    help = (
        "Load canonical yield curve definitions (idempotent, global reference data). "
        "Yield curve points must be imported separately via import_yield_curve_excel."
    )

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

        canonical_curves = get_canonical_yield_curves()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would load {len(canonical_curves)} yield curves (global reference data)"
                )
            )
            for curve_def in canonical_curves:
                self.stdout.write(
                    f"  - {curve_def['name']} ({curve_def['currency']}, {curve_def['country']})"
                )
            return

        # Load curves as global reference data
        created_count = 0
        updated_count = 0
        errors = []

        try:
            with transaction.atomic():
                for curve_def in canonical_curves:
                    try:
                        curve, created = YieldCurve.objects.get_or_create(
                            currency=curve_def["currency"],
                            name=curve_def["name"],
                            defaults={
                                "curve_type": curve_def["curve_type"],
                                "country": curve_def["country"],
                                "description": curve_def["description"],
                                "is_active": True,
                            },
                        )

                        if created:
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Created curve: {curve_def['name']} "
                                    f"({curve_def['currency']}, {curve_def['country']})"
                                )
                            )
                        else:
                            # Update fields if they changed
                            updated = False
                            if curve.curve_type != curve_def["curve_type"]:
                                curve.curve_type = curve_def["curve_type"]
                                updated = True
                            if curve.country != curve_def["country"]:
                                curve.country = curve_def["country"]
                                updated = True
                            if curve.description != curve_def["description"]:
                                curve.description = curve_def["description"]
                                updated = True

                            if updated:
                                curve.save()
                                updated_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Updated curve: {curve_def['name']} "
                                        f"({curve_def['currency']}, {curve_def['country']})"
                                    )
                                )
                            else:
                                self.stdout.write(
                                    f"Curve already exists: {curve_def['name']} "
                                    f"({curve_def['currency']}, {curve_def['country']})"
                                )
                    except Exception as e:
                        error_msg = (
                            f"Error processing curve {curve_def['name']}: {str(e)}"
                        )
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))

                # Create audit event (organization_id is None for global reference data)
                if created_count > 0 or updated_count > 0 or errors:
                    AuditEvent.objects.create(
                        organization_id=None,  # Global reference data
                        actor=actor,
                        action="LOAD_REFERENCE_DATA",
                        object_type="YieldCurve",
                        object_repr=f"Loaded {len(canonical_curves)} canonical yield curves",
                        metadata={
                            "curves_loaded": len(canonical_curves),
                            "curves_created": created_count,
                            "curves_updated": updated_count,
                            "errors": errors,
                            "command": "load_yield_curves",
                            "scope": "global",
                        },
                    )

        except Exception as e:
            raise CommandError(f"Failed to load yield curves: {str(e)}")

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted loading {len(canonical_curves)} yield curves (global reference data)"
            )
        )
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Errors: {len(errors)}")
        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    - {error}"))

        # Reminder about importing points
        if created_count > 0:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Note: Yield curve points (observations) must be imported separately "
                    "using: python manage.py import_yield_curve_excel"
                )
            )
