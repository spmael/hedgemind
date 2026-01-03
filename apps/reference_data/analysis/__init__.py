"""
Yield curve analysis package.

Provides analysis functions for yield curve data quality, regime detection,
narrative definition, and stress calibration.

This package implements Phase 0-4 of the yield curve stress analysis pipeline:
- Phase 0-1: Data inventory and normalization (curve_quality.py)
- Phase 2: Stress regime detection (curve_regimes.py)
- Phase 3: Narrative definition (curve_narratives.py)
- Phase 4: Stress calibration (curve_stress_calibration.py)

ETL Integration:
    After canonicalizing yield curves, call run_yield_curve_analysis() to:
    1. Analyze curve data quality (Phase 0-1)
    2. Detect stress regimes (Phase 2)
    3. Define narratives (Phase 3)
    4. Build stress profiles (Phase 4)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.reference_data.analysis.curve_narratives import (
    compare_narratives_across_countries,
    map_regime_to_narrative,
)
from apps.reference_data.analysis.curve_quality import (
    analyze_curve_coverage,
    calculate_publication_gaps,
    generate_availability_matrix,
    inventory_curves,
)
from apps.reference_data.analysis.curve_regimes import (
    compare_curves_divergence,
    detect_regime_periods,
)
from apps.reference_data.analysis.curve_stress_calibration import (
    create_stress_profile_from_narrative,
)

__all__ = [
    # Phase 0-1
    "inventory_curves",
    "analyze_curve_coverage",
    "calculate_publication_gaps",
    "generate_availability_matrix",
    # Phase 2
    "detect_regime_periods",
    "compare_curves_divergence",
    # Phase 3
    "map_regime_to_narrative",
    "compare_narratives_across_countries",
    # Phase 4
    "create_stress_profile_from_narrative",
    # ETL Integration
    "run_yield_curve_analysis",
]


def run_yield_curve_analysis(
    curve_id: int | None = None,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    Run complete yield curve analysis pipeline (Phase 0-4).

    This function should be called after canonicalizing yield curves to:
    1. Analyze data quality (Phase 0-1)
    2. Detect stress regimes (Phase 2)
    3. Define narratives (Phase 3)
    4. Build stress profiles (Phase 4)

    Args:
        curve_id: Specific curve ID to analyze (if None, analyzes all active curves).
        as_of_date: Date for analysis (if None, uses today).

    Returns:
        dict: Analysis results with keys:
            - curves_analyzed: Number of curves processed
            - profiles_created: Number of stress profiles created
            - errors: List of errors encountered

    Example:
        >>> from apps.reference_data.analysis import run_yield_curve_analysis
        >>> results = run_yield_curve_analysis(curve_id=1)
        >>> print(f"Created {results['profiles_created']} stress profiles")

    Note:
        This function is designed to be called from ETL orchestration after
        canonicalization. It can be integrated into daily_close.py or run
        as a separate management command.
    """
    from apps.reference_data.models import YieldCurve

    if as_of_date is None:
        from datetime import date as date_type

        as_of_date = date_type.today()

    # Get curves to analyze
    if curve_id:
        curves = [YieldCurve.objects.get(id=curve_id)]
    else:
        curves = list(YieldCurve.objects.filter(is_active=True))

    curves_analyzed = 0
    profiles_created = 0
    errors = []

    for curve in curves:
        try:
            # Phase 2: Detect regimes
            regime_periods = detect_regime_periods(curve)

            # Phase 3-4: Map to narratives and create profiles
            for regime_period in regime_periods:
                context = {
                    "country": str(curve.country),
                    "currency": str(curve.currency),
                    "curve_name": curve.name,
                }

                narrative = map_regime_to_narrative(regime_period, context)

                if narrative.get("narrative_type"):
                    _profile = create_stress_profile_from_narrative(
                        curve, narrative, regime_period
                    )
                    profiles_created += 1

            curves_analyzed += 1

        except Exception as e:
            errors.append(f"Error analyzing curve {curve.id} ({curve.name}): {str(e)}")

    return {
        "curves_analyzed": curves_analyzed,
        "profiles_created": profiles_created,
        "errors": errors,
    }
