"""
Management command to canonicalize instrument prices.

Selects the best price observations based on source priority and creates
canonical InstrumentPrice records.

Usage:
    # Canonicalize all prices
    python manage.py canonicalize_prices

    # Canonicalize for specific instrument
    python manage.py canonicalize_prices --instrument-id CM0000020305

    # Canonicalize for date range
    python manage.py canonicalize_prices --start-date 2024-01-01 --end-date 2024-12-31

    # Canonicalize for specific price type
    python manage.py canonicalize_prices --price-type close
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from apps.reference_data.services.prices.canonicalize import canonicalize_prices


class Command(BaseCommand):
    """
    Management command for canonicalizing instrument price observations.

    This command selects the best price observation for each (instrument, date, price_type)
    combination based on source priority hierarchy and creates canonical InstrumentPrice records.

    Key Features:
    - Processes all instruments or filters by instrument_id
    - Supports date range filtering
    - Supports price type filtering
    - Uses source priority to select best observation
    - Handles revision numbers (most recent wins)

    Usage Example:
        python manage.py canonicalize_prices \
            --instrument-id CM0000020305 \
            --start-date 2024-01-01 \
            --end-date 2024-12-31 \
            --price-type close
    """

    help = "Canonicalize instrument price observations"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--instrument-id",
            type=str,
            help="Instrument identifier (ISIN or ticker) to canonicalize",
        )
        parser.add_argument(
            "--as-of-date",
            type=str,
            help="Single date to canonicalize (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date for date range (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="End date for date range (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--price-type",
            type=str,
            help="Price type to canonicalize (e.g., 'close', 'ask', 'bid')",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        # Parse dates
        as_of_date = None
        if options.get("as_of_date"):
            try:
                as_of_date = date.fromisoformat(options["as_of_date"])
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        f"Invalid as_of_date format: {options['as_of_date']}. Use YYYY-MM-DD"
                    )
                )
                return

        start_date = None
        if options.get("start_date"):
            try:
                start_date = date.fromisoformat(options["start_date"])
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        f"Invalid start_date format: {options['start_date']}. Use YYYY-MM-DD"
                    )
                )
                return

        end_date = None
        if options.get("end_date"):
            try:
                end_date = date.fromisoformat(options["end_date"])
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        f"Invalid end_date format: {options['end_date']}. Use YYYY-MM-DD"
                    )
                )
                return

        instrument_id = options.get("instrument_id")
        price_type = options.get("price_type")

        self.stdout.write("Canonicalizing instrument prices...")
        if instrument_id:
            self.stdout.write(f"Instrument: {instrument_id}")
        if as_of_date:
            self.stdout.write(f"Date: {as_of_date}")
        elif start_date or end_date:
            self.stdout.write(f"Date range: {start_date or 'all'} to {end_date or 'all'}")
        if price_type:
            self.stdout.write(f"Price type: {price_type}")
        self.stdout.write("")

        try:
            result = canonicalize_prices(
                instrument_id=instrument_id,
                as_of_date=as_of_date,
                start_date=start_date,
                end_date=end_date,
                price_type=price_type,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created {result['created']} canonical prices, "
                    f"updated {result['updated']}, "
                    f"skipped {result['skipped']}"
                )
            )

            if result.get("errors"):
                self.stdout.write("")
                self.stdout.write(
                    self.style.ERROR(f"✗ {len(result['errors'])} errors:")
                )
                for error in result["errors"][:20]:  # Show first 20
                    self.stdout.write(f"  - {error}")
                if len(result["errors"]) > 20:
                    self.stdout.write(f"  ... and {len(result['errors']) - 20} more")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Canonicalization failed: {str(e)}"))
            raise

