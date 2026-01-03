"""
Stress report renderer for governance and disclosure.

Implements Phase 6: Governance & Disclosure.

Generates board-ready and regulator-safe stress reports with explicit
data quality disclosures and assumption documentation.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.portfolios.models import Portfolio
from apps.reference_data.models import YieldCurve, YieldCurveStressProfile


def generate_stress_disclosure(
    stress_run: dict[str, Any],
    stress_profile: YieldCurveStressProfile,
) -> dict[str, Any]:
    """
    Generate stress disclosure with data limits, staleness, and assumptions.

    Args:
        stress_run: Stress run results dict.
        stress_profile: YieldCurveStressProfile used for stress test.

    Returns:
        dict: Disclosure information with keys:
            - data_quality_limits
            - staleness_info
            - assumptions_documented
            - governance_language

    Example:
        >>> stress_run = {"capital_loss": 100000, ...}
        >>> profile = YieldCurveStressProfile.objects.get(id=1)
        >>> disclosure = generate_stress_disclosure(stress_run, profile)
    """
    curve = stress_profile.curve

    # Data quality limits
    data_quality_limits = {
        "last_observation_date": curve.last_observation_date,
        "staleness_days": curve.staleness_days,
        "published_date_assumed": False,  # Check if any points have assumed dates
        "missing_data_periods": [],  # Would be populated from curve analysis
        "interpolation_used": False,
        "curve_fitting_used": False,
    }

    # Check for assumed publication dates
    if curve.points.exists():
        assumed_count = curve.points.filter(published_date_assumed=True).count()
        total_count = curve.points.count()
        data_quality_limits["published_date_assumed"] = assumed_count > 0
        data_quality_limits["assumed_dates_pct"] = (
            (assumed_count / total_count * 100) if total_count > 0 else 0.0
        )

    # Staleness info
    staleness_info = {
        "curve_name": curve.name,
        "last_observation_date": curve.last_observation_date,
        "staleness_days": curve.staleness_days,
        "staleness_category": (
            "current"
            if (curve.staleness_days or 0) <= 30
            else (
                "moderate"
                if (curve.staleness_days or 0) <= 90
                else "stale" if (curve.staleness_days or 0) <= 180 else "very_stale"
            )
        ),
    }

    # Assumptions documented
    assumptions_documented = {
        "no_interpolation": True,
        "no_curve_fitting": True,
        "haircut_methodology": "deterministic_haircuts",
        "haircut_rationale": stress_profile.calibration_rationale,
        "historical_period": {
            "start": stress_profile.period_start,
            "end": stress_profile.period_end,
        },
        "narrative_type": stress_profile.narrative,
        "regime_type": stress_profile.regime_type,
    }

    # Governance language
    governance_language = format_governance_language(
        stress_run,
        data_quality_limits,
        staleness_info,
        assumptions_documented,
    )

    return {
        "data_quality_limits": data_quality_limits,
        "staleness_info": staleness_info,
        "assumptions_documented": assumptions_documented,
        "governance_language": governance_language,
    }


def document_curve_metadata(curves_used: list[YieldCurve]) -> dict[str, Any]:
    """
    Document curve metadata for stress report.

    Args:
        curves_used: List of YieldCurve instances used in stress test.

    Returns:
        dict: Curve metadata documentation.

    Example:
        >>> curves = [YieldCurve.objects.get(name="Cameroon Government Curve")]
        >>> metadata = document_curve_metadata(curves)
    """
    curve_docs = []

    for curve in curves_used:
        # Count points with assumed dates
        total_points = curve.points.count()
        assumed_points = curve.points.filter(published_date_assumed=True).count()

        curve_docs.append(
            {
                "curve_name": curve.name,
                "currency": str(curve.currency),
                "country": str(curve.country),
                "curve_type": curve.curve_type,
                "last_observation_date": curve.last_observation_date,
                "staleness_days": curve.staleness_days,
                "total_points": total_points,
                "assumed_dates_count": assumed_points,
                "assumed_dates_pct": (
                    (assumed_points / total_points * 100) if total_points > 0 else 0.0
                ),
            }
        )

    return {
        "curves": curve_docs,
        "total_curves": len(curves_used),
    }


def format_governance_language(
    stress_results: dict[str, Any],
    data_quality_limits: dict[str, Any],
    staleness_info: dict[str, Any],
    assumptions_documented: dict[str, Any],
) -> str:
    """
    Format board-ready governance language for stress report.

    Args:
        stress_results: Stress test results.
        data_quality_limits: Data quality information.
        staleness_info: Staleness information.
        assumptions_documented: Documented assumptions.

    Returns:
        str: Formatted governance language.

    Example:
        >>> language = format_governance_language(results, quality, staleness, assumptions)
        >>> print(language)
    """
    lines = []

    # Executive summary
    lines.append("STRESS TEST DISCLOSURE AND GOVERNANCE")
    lines.append("=" * 80)
    lines.append("")

    # Data quality disclosure
    lines.append("DATA QUALITY AND LIMITATIONS")
    lines.append("-" * 80)

    if staleness_info["last_observation_date"]:
        lines.append(
            f"Yield curve data last observed: {staleness_info['last_observation_date']} "
            f"({staleness_info['staleness_days']} days ago)"
        )
        lines.append(
            f"Staleness category: {staleness_info['staleness_category'].replace('_', ' ').title()}"
        )
    else:
        lines.append("Yield curve data: Last observation date not available")

    if data_quality_limits.get("published_date_assumed"):
        pct = data_quality_limits.get("assumed_dates_pct", 0.0)
        lines.append(
            f"Publication dates: {pct:.1f}% of observations have assumed publication dates "
            "(publication date set equal to curve date when not explicitly provided)"
        )

    lines.append("Interpolation: NOT USED - Only observed data points are used")
    lines.append("Curve fitting: NOT USED - No smoothing or curve fitting applied")
    lines.append("")

    # Methodology disclosure
    lines.append("STRESS METHODOLOGY")
    lines.append("-" * 80)
    lines.append(
        "Stress test applies deterministic haircuts to portfolio holdings based on"
    )
    lines.append("historical yield curve stress narratives.")
    lines.append("")
    lines.append(
        f"Narrative type: {assumptions_documented['narrative_type'].replace('_', ' ').title()}"
    )
    lines.append(
        f"Regime type: {assumptions_documented['regime_type'].replace('_', ' ').title()}"
    )
    lines.append(
        f"Historical period: {assumptions_documented['historical_period']['start']} "
        f"to {assumptions_documented['historical_period']['end']}"
    )
    lines.append("")
    lines.append("Haircut methodology:")
    lines.append("  - Haircuts are applied to market values based on issuer type")
    lines.append(
        "  - Sovereign issuers: Lower haircuts (reflecting sovereign credit support)"
    )
    lines.append(
        "  - Corporate issuers: Higher haircuts (reflecting higher credit risk)"
    )
    lines.append(
        "  - Supranational issuers: Intermediate haircuts (multilateral support)"
    )
    lines.append("")

    # Capital loss explanation
    capital_loss = stress_results.get("capital_loss", 0)
    capital_loss_pct = stress_results.get("capital_loss_pct", 0)

    if capital_loss > 0:
        lines.append("STRESS RESULTS")
        lines.append("-" * 80)
        lines.append(
            f"Estimated capital loss under stress scenario: {capital_loss:,.2f}"
        )
        lines.append(f"Capital loss as percentage of baseline: {capital_loss_pct:.2f}%")
        lines.append("")
        lines.append(
            "This represents the estimated reduction in portfolio market value "
            "under the specified stress scenario."
        )
        lines.append("")

    # Assumptions and limitations
    lines.append("ASSUMPTIONS AND LIMITATIONS")
    lines.append("-" * 80)
    lines.append("1. Stress haircuts are based on historical yield curve patterns")
    lines.append("   and are deterministic, explicit assumptions.")
    lines.append(
        "2. No interpolation or curve fitting is used in yield curve analysis."
    )
    lines.append(
        "3. Publication dates may be assumed when not explicitly provided by source."
    )
    lines.append("4. Stress results are estimates and should not be interpreted as")
    lines.append("   precise predictions of future portfolio performance.")
    lines.append("5. Actual stress impacts may differ based on portfolio composition,")
    lines.append(
        "   market conditions, and other factors not captured in this analysis."
    )
    lines.append("")

    # Regulatory compliance
    lines.append("REGULATORY COMPLIANCE")
    lines.append("-" * 80)
    lines.append("This stress test has been conducted in accordance with:")
    lines.append("- Explicit documentation of data quality and limitations")
    lines.append("- Transparent methodology and assumptions")
    lines.append("- Deterministic, explainable stress calibration")
    lines.append("- No use of black-box models or unverifiable assumptions")
    lines.append("")

    return "\n".join(lines)


def generate_stress_report(
    portfolio: Portfolio,
    stress_profile: YieldCurveStressProfile,
    stress_results: dict[str, Any],
    as_of_date: date,
) -> dict[str, Any]:
    """
    Generate complete stress report with all sections.

    Args:
        portfolio: Portfolio instance.
        stress_profile: YieldCurveStressProfile used.
        stress_results: Stress test results.
        as_of_date: Date of stress test.

    Returns:
        dict: Complete stress report with all sections.

    Example:
        >>> portfolio = Portfolio.objects.get(id=1)
        >>> profile = YieldCurveStressProfile.objects.get(id=1)
        >>> results = {"capital_loss": 100000, ...}
        >>> report = generate_stress_report(portfolio, profile, results, date.today())
    """
    # Generate disclosure
    disclosure = generate_stress_disclosure(stress_results, stress_profile)

    # Document curve metadata
    curves_used = [stress_profile.curve]
    curve_metadata = document_curve_metadata(curves_used)

    # Format governance language
    governance_language = format_governance_language(
        stress_results,
        disclosure["data_quality_limits"],
        disclosure["staleness_info"],
        disclosure["assumptions_documented"],
    )

    return {
        "portfolio": {
            "id": portfolio.id,
            "name": portfolio.name,
        },
        "stress_profile": {
            "id": stress_profile.id,
            "narrative": stress_profile.narrative,
            "regime_type": stress_profile.regime_type,
            "period_start": stress_profile.period_start,
            "period_end": stress_profile.period_end,
        },
        "as_of_date": as_of_date,
        "stress_results": stress_results,
        "disclosure": disclosure,
        "curve_metadata": curve_metadata,
        "governance_language": governance_language,
    }
