"""
Management command to sync market data sources.

This command creates/updates baseline market data source records (deployment-specific,
not static taxonomy). These sources are used for FX rates, prices, yield curves, etc.

This is separate from load_reference_data which handles static taxonomy
(InstrumentGroup, InstrumentType).

The command is idempotent and can be run multiple times safely - it will create
missing sources and update existing ones.

Usage:
    python manage.py sync_market_data_sources
    python manage.py sync_market_data_sources --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.reference_data.models import MarketDataSource


class Command(BaseCommand):
    """
    Management command to sync market data sources.

    This module provides a Django management command for syncing baseline
    market data source records (BVMAC, BEAC, MANUAL, CUSTODIAN, etc.) into
    the database. These sources are deployment-specific and can be updated
    over time as new sources are added.

    Key components:
    - Idempotent source loader: Ensures all baseline sources exist and updates as needed.
    - Deployment-specific: Sources may vary by deployment (not static taxonomy).
    - CLI options: Supports --dry-run for preview and --actor-id for audit attribution.

    Usage example:
        python manage.py sync_market_data_sources
        python manage.py sync_market_data_sources --dry-run
        python manage.py sync_market_data_sources --actor-id 42
    """

    help = "Sync baseline market data sources (idempotent, deployment-specific)"

    # Baseline sources to sync
    BASELINE_SOURCES = [
        {
            "code": "BVMAC",
            "name": "Douala Stock Exchange",
            "priority": 1,
            "source_type": MarketDataSource.SourceType.EXCHANGE,
            "description": "Douala Stock Exchange (Bourse des Valeurs Mobilières de l'Afrique Centrale)",
        },
        {
            "code": "BEAC",
            "name": "Bank of Central African States",
            "priority": 2,
            "source_type": MarketDataSource.SourceType.CENTRAL_BANK,
            "description": "Bank of Central African States (Banque des États de l'Afrique Centrale) - FX rates and official rates",
        },
        {
            "code": "CUSTODIAN",
            "name": "Custodian",
            "priority": 50,
            "source_type": MarketDataSource.SourceType.CUSTODIAN,
            "description": "Custodian-provided market data",
        },
        {
            "code": "MANUAL",
            "name": "Manual Entry",
            "priority": 100,
            "source_type": MarketDataSource.SourceType.MANUAL,
            "description": "Manually entered market data",
        },
    ]

    def add_arguments(self, parser):
        """
        Add command-line arguments.

        Args:
            parser: Argument parser instance.
        """
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created/updated without actually doing it",
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

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would sync {len(self.BASELINE_SOURCES)} market data sources"
                )
            )
            for source_def in self.BASELINE_SOURCES:
                existing = MarketDataSource.objects.filter(
                    code=source_def["code"]
                ).first()
                if existing:
                    self.stdout.write(
                        f"  Would update: {source_def['code']} - {source_def['name']}"
                    )
                else:
                    self.stdout.write(
                        f"  Would create: {source_def['code']} - {source_def['name']}"
                    )
            return

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for source_def in self.BASELINE_SOURCES:
                source, created = MarketDataSource.objects.update_or_create(
                    code=source_def["code"],
                    defaults={
                        "name": source_def["name"],
                        "priority": source_def["priority"],
                        "source_type": source_def["source_type"],
                        "description": source_def.get("description"),
                        "is_active": True,
                    },
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Created: {source.code} - {source.name}")
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Updated: {source.code} - {source.name}")
                    )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed syncing market data sources: "
                f"{created_count} created, {updated_count} updated"
            )
        )
