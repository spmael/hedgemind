"""
Management command to load all canonical reference data.

This command loads both instrument groups and types in a single operation.
It's a convenience wrapper around load_instrument_groups and load_instrument_types.

These are global reference data (shared across all organizations) - static taxonomy only.

Note: This command handles static taxonomy (InstrumentGroup, InstrumentType).
For market data sources (deployment-specific), use sync_market_data_sources command.

Usage:
    python manage.py load_reference_data
    python manage.py load_reference_data --dry-run
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    Management command to load all canonical reference data.

    This module provides a Django management command for loading both the
    industry-standard instrument groups and instrument types (canonical data)
    into the database in a single operation.

    Key components:
    - Sequentially loads both instrument groups and types via delegated
      commands (`load_instrument_groups`, `load_instrument_types`).
    - Loads global reference data shared across all organizations (multi-tenant safe).
    - Supports idempotent operation: safe to re-run multiple times.
    - CLI options: Supports --dry-run for preview and --actor-id for audit attribution.

    Usage example:
        python manage.py load_reference_data
        python manage.py load_reference_data --dry-run
        python manage.py load_reference_data --actor-id 42
    """

    help = (
        "Load all canonical reference data (groups and types) - global reference data, "
        "static taxonomy only. Use sync_market_data_sources for market data sources."
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

        self.stdout.write(
            self.style.SUCCESS(
                "Loading canonical reference data (global, shared across all organizations)..."
            )
        )

        # Build call_command options
        call_options = {}
        if dry_run:
            call_options["dry_run"] = True
        if actor_id:
            call_options["actor_id"] = actor_id

        try:
            # Load groups first
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("Step 1: Loading instrument groups...")
            self.stdout.write("=" * 60)
            call_command("load_instrument_groups", **call_options)

            # Load types second (depends on groups)
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("Step 2: Loading instrument types...")
            self.stdout.write("=" * 60)
            call_command("load_instrument_types", **call_options)

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(
                self.style.SUCCESS(
                    "Completed loading reference data (global reference data)"
                )
            )
            self.stdout.write("=" * 60)

        except CommandError as e:
            raise CommandError(f"Failed to load reference data: {str(e)}")
