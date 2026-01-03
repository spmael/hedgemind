"""
Management command to analyze yield curve data quality and generate availability matrix.

Supports Phase 0 (Data Inventory) and Phase 1 (Normalization) analysis.

Usage:
    # Phase 0: Generate inventory and availability matrix
    python manage.py analyze_yield_curves --phase 0

    # Phase 0: Analyze specific curve
    python manage.py analyze_yield_curves --phase 0 --curve-id 1

    # Phase 0: Output to JSON file
    python manage.py analyze_yield_curves --phase 0 --output results.json
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.reference_data.analysis.curve_quality import (
    analyze_curve_coverage,
    calculate_publication_gaps,
    generate_availability_matrix,
    inventory_curves,
    normalize_curves_for_comparison,
)
from apps.reference_data.models import YieldCurve


class Command(BaseCommand):
    """
    Management command for analyzing yield curve data quality.

    Implements Phase 0 (Data Inventory & Governance) analysis.
    """

    help = "Analyze yield curve data quality and generate availability matrix (Phase 0)"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--phase",
            type=int,
            choices=[0, 1],
            default=0,
            help="Analysis phase: 0=Inventory, 1=Normalization (default: 0)",
        )
        parser.add_argument(
            "--curve-id",
            type=int,
            help="Specific curve ID to analyze (if not provided, analyzes all curves)",
        )
        parser.add_argument(
            "--curve-name",
            type=str,
            help="Specific curve name to analyze",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output file path for JSON results (optional)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date for analysis (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="End date for analysis (YYYY-MM-DD)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        phase = options.get("phase", 0)
        curve_id = options.get("curve_id")
        curve_name = options.get("curve_name")
        output_file = options.get("output")

        # Parse dates if provided
        start_date = None
        end_date = None
        if options.get("start_date"):
            from datetime import date as date_type

            start_date = date_type.fromisoformat(options["start_date"])
        if options.get("end_date"):
            from datetime import date as date_type

            end_date = date_type.fromisoformat(options["end_date"])

        if phase == 0:
            self._handle_phase_0(
                curve_id, curve_name, start_date, end_date, output_file
            )
        elif phase == 1:
            self._handle_phase_1(curve_id, curve_name, output_file)
        else:
            raise CommandError(f"Unknown phase: {phase}")

    def _handle_phase_0(
        self,
        curve_id: int | None,
        curve_name: str | None,
        start_date: date | None,
        end_date: date | None,
        output_file: str | None,
    ):
        """Handle Phase 0: Data inventory and governance."""
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("Phase 0: Data Inventory & Governance"))
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Get curves to analyze
        if curve_id:
            try:
                curves = [YieldCurve.objects.get(id=curve_id)]
            except YieldCurve.DoesNotExist:
                raise CommandError(f"YieldCurve with id={curve_id} not found")
        elif curve_name:
            try:
                curves = [YieldCurve.objects.get(name=curve_name)]
            except YieldCurve.DoesNotExist:
                raise CommandError(f"YieldCurve with name='{curve_name}' not found")
        else:
            curves = list(YieldCurve.objects.filter(is_active=True))

        if not curves:
            self.stdout.write(self.style.WARNING("No active curves found"))
            return

        # Generate inventory
        self.stdout.write("Generating curve inventory...")
        inventory = inventory_curves()

        self.stdout.write(f"Total curves: {inventory['total_curves']}")
        self.stdout.write(f"Total points: {inventory['total_points']}")
        self.stdout.write("")

        # Analyze each curve
        results = {
            "inventory": inventory,
            "curve_analyses": [],
            "availability_matrix": None,
        }

        for curve in curves:
            self.stdout.write(
                f"Analyzing: {curve.name} ({curve.currency}, {curve.country})"
            )
            self.stdout.write("-" * 80)

            # Coverage analysis
            coverage = analyze_curve_coverage(curve, start_date, end_date)
            self.stdout.write(
                f"  Available tenors: {len(coverage['available_tenors'])}"
            )
            self.stdout.write(
                f"  Coverage: {coverage['coverage_pct']:.1f}% ({coverage['total_observed_months']}/{coverage['total_expected_months']} months)"
            )
            self.stdout.write(f"  Missing months: {len(coverage['missing_months'])}")

            if coverage["available_tenors"]:
                self.stdout.write(
                    f"  Tenor range: {min(coverage['available_tenors'])} - {max(coverage['available_tenors'])} days"
                )

            # Gap analysis
            gaps = calculate_publication_gaps(curve)
            self.stdout.write(f"  Longest gap: {gaps['longest_gap_days']} days")
            if gaps["longest_gap_start"]:
                self.stdout.write(
                    f"    From: {gaps['longest_gap_start']} to {gaps['longest_gap_end']}"
                )
            self.stdout.write(f"  Average gap: {gaps['average_gap_days']:.1f} days")
            self.stdout.write(f"  Frequency: {gaps['frequency_observed']}")

            # Staleness
            if curve.last_observation_date:
                self.stdout.write(
                    f"  Last observation: {curve.last_observation_date} ({curve.staleness_days} days ago)"
                )
            else:
                self.stdout.write("  Last observation: N/A")

            self.stdout.write("")

            results["curve_analyses"].append(
                {
                    "curve_id": curve.id,
                    "curve_name": curve.name,
                    "coverage": coverage,
                    "gaps": gaps,
                    "staleness_days": curve.staleness_days,
                }
            )

        # Generate availability matrix
        self.stdout.write("Generating availability matrix...")
        matrix = generate_availability_matrix()
        results["availability_matrix"] = matrix

        self.stdout.write(f"Countries: {matrix['summary']['total_countries']}")
        self.stdout.write(f"Tenors: {matrix['summary']['total_tenors']}")
        self.stdout.write("")

        # Output results
        if output_file:
            output_path = Path(output_file)
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            self.stdout.write(self.style.SUCCESS(f"✓ Results saved to: {output_file}"))
        else:
            # Print summary
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS("Analysis complete"))
            self.stdout.write("=" * 80)

    def _handle_phase_1(
        self,
        curve_id: int | None,
        curve_name: str | None,
        output_file: str | None,
    ):
        """Handle Phase 1: Normalization."""
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("Phase 1: Normalize Without Distortion"))
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Get curves
        if curve_id:
            try:
                curves = [YieldCurve.objects.get(id=curve_id)]
            except YieldCurve.DoesNotExist:
                raise CommandError(f"YieldCurve with id={curve_id} not found")
        elif curve_name:
            try:
                curves = [YieldCurve.objects.get(name=curve_name)]
            except YieldCurve.DoesNotExist:
                raise CommandError(f"YieldCurve with name='{curve_name}' not found")
        else:
            curves = list(YieldCurve.objects.filter(is_active=True))

        if not curves:
            self.stdout.write(self.style.WARNING("No active curves found"))
            return

        # Normalize curves for comparison
        self.stdout.write("Normalizing curves for comparison...")
        normalized = normalize_curves_for_comparison(curves)

        self.stdout.write(f"Total dates: {len(normalized['dates'])}")
        self.stdout.write(f"Common dates: {len(normalized['common_dates'])}")
        self.stdout.write(f"Core tenors: {normalized['core_tenors']}")
        self.stdout.write("")

        # Output results
        if output_file:
            results = {
                "normalized_data": normalized,
            }
            output_path = Path(output_file)
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            self.stdout.write(self.style.SUCCESS(f"✓ Results saved to: {output_file}"))
        else:
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS("Normalization complete"))
            self.stdout.write("=" * 80)
