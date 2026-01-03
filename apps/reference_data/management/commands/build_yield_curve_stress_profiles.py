"""
Management command to build yield curve stress profiles.

Runs Phase 0-4 pipeline:
- Phase 0: Data inventory
- Phase 1: Normalization
- Phase 2: Regime detection
- Phase 3: Narrative definition
- Phase 4: Stress calibration (creates YieldCurveStressProfile records)

Usage:
    # Build profiles for all curves
    python manage.py build_yield_curve_stress_profiles --all-curves

    # Build profile for specific curve
    python manage.py build_yield_curve_stress_profiles --curve-id 1

    # Build profile for specific curve by name
    python manage.py build_yield_curve_stress_profiles --curve-name "Cameroon Government Curve"
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.reference_data.analysis.curve_narratives import map_regime_to_narrative
from apps.reference_data.analysis.curve_regimes import detect_regime_periods
from apps.reference_data.analysis.curve_stress_calibration import (
    create_stress_profile_from_narrative,
    validate_calibration_assumptions,
)
from apps.reference_data.models import YieldCurve, YieldCurveStressProfile


class Command(BaseCommand):
    """
    Management command for building yield curve stress profiles.

    Implements Phase 0-4 pipeline to create YieldCurveStressProfile records.
    """

    help = "Build yield curve stress profiles from historical narratives (Phase 0-4)"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--all-curves",
            action="store_true",
            help="Build profiles for all active curves",
        )
        parser.add_argument(
            "--curve-id",
            type=int,
            help="Specific curve ID to build profile for",
        )
        parser.add_argument(
            "--curve-name",
            type=str,
            help="Specific curve name to build profile for",
        )
        parser.add_argument(
            "--deactivate-old",
            action="store_true",
            help="Deactivate existing profiles for curves being processed",
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Only validate existing profiles, don't create new ones",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        all_curves = options.get("all_curves", False)
        curve_id = options.get("curve_id")
        curve_name = options.get("curve_name")
        deactivate_old = options.get("deactivate_old", False)
        validate_only = options.get("validate_only", False)

        # Determine which curves to process
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
        elif all_curves:
            curves = list(YieldCurve.objects.filter(is_active=True))
        else:
            raise CommandError("Must specify --all-curves, --curve-id, or --curve-name")

        if not curves:
            self.stdout.write(self.style.WARNING("No curves found to process"))
            return

        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.SUCCESS("Building Yield Curve Stress Profiles (Phase 0-4)")
        )
        self.stdout.write("=" * 80)
        self.stdout.write("")

        if validate_only:
            self._validate_profiles(curves)
        else:
            self._build_profiles(curves, deactivate_old)

    def _build_profiles(
        self,
        curves: list[YieldCurve],
        deactivate_old: bool,
    ):
        """Build stress profiles for curves."""
        total_profiles_created = 0
        total_profiles_updated = 0
        total_errors = 0

        for curve in curves:
            self.stdout.write(
                f"Processing: {curve.name} ({curve.currency}, {curve.country})"
            )
            self.stdout.write("-" * 80)

            # Deactivate old profiles if requested
            if deactivate_old:
                old_count = YieldCurveStressProfile.objects.filter(
                    curve=curve, is_active=True
                ).update(is_active=False)
                if old_count > 0:
                    self.stdout.write(f"  Deactivated {old_count} existing profiles")

            # Phase 2: Detect regime periods
            self.stdout.write("  Phase 2: Detecting regime periods...")
            try:
                regime_periods = detect_regime_periods(curve)
                self.stdout.write(f"    Found {len(regime_periods)} regime periods")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    Error detecting regimes: {e}"))
                total_errors += 1
                continue

            if not regime_periods:
                self.stdout.write(self.style.WARNING("    No regime periods found"))
                continue

            # Phase 3: Map regimes to narratives
            self.stdout.write("  Phase 3: Mapping regimes to narratives...")
            narratives_created = 0

            for regime_period in regime_periods:
                try:
                    # Build context
                    context = {
                        "country": str(curve.country),
                        "currency": str(curve.currency),
                        "curve_name": curve.name,
                    }

                    # Map to narrative
                    narrative = map_regime_to_narrative(regime_period, context)

                    # Skip if no narrative (normal periods)
                    if not narrative.get("narrative_type"):
                        continue

                    # Phase 4: Create stress profile
                    self.stdout.write(
                        f"    Creating profile for: {narrative['narrative_type']} "
                        f"({narrative['period_start']} to {narrative['period_end']})"
                    )

                    profile = create_stress_profile_from_narrative(
                        curve, narrative, regime_period
                    )

                    # Validate
                    warnings = validate_calibration_assumptions(profile)
                    if warnings:
                        self.stdout.write(
                            self.style.WARNING("    Validation warnings:")
                        )
                        for warning in warnings:
                            self.stdout.write(f"      - {warning}")

                    narratives_created += 1
                    total_profiles_created += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"    Error creating profile: {e}")
                    )
                    total_errors += 1

            self.stdout.write(f"  Created {narratives_created} stress profiles")
            self.stdout.write("")

        # Summary
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("Summary"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Curves processed: {len(curves)}")
        self.stdout.write(f"Profiles created: {total_profiles_created}")
        self.stdout.write(f"Profiles updated: {total_profiles_updated}")
        self.stdout.write(f"Errors: {total_errors}")
        self.stdout.write("")

    def _validate_profiles(self, curves: list[YieldCurve]):
        """Validate existing stress profiles."""
        self.stdout.write("Validating existing stress profiles...")
        self.stdout.write("")

        total_warnings = 0
        total_errors = 0

        for curve in curves:
            profiles = YieldCurveStressProfile.objects.filter(
                curve=curve, is_active=True
            )

            self.stdout.write(f"{curve.name}: {profiles.count()} active profiles")

            for profile in profiles:
                warnings = validate_calibration_assumptions(profile)

                if warnings:
                    total_warnings += len(warnings)
                    self.stdout.write(
                        self.style.WARNING(f"  Profile {profile.id} warnings:")
                    )
                    for warning in warnings:
                        self.stdout.write(f"    - {warning}")
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"  Profile {profile.id}: ✓ Valid")
                    )

            self.stdout.write("")

        self.stdout.write("=" * 80)
        self.stdout.write(f"Total warnings: {total_warnings}")
        self.stdout.write(f"Total errors: {total_errors}")
        self.stdout.write("")
