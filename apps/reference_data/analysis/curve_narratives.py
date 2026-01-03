"""
Yield curve stress narrative definition.

Implements Phase 3: Define Stress Narratives.

Turns regimes into economic stories with historical anchors.
"""

from __future__ import annotations

from typing import Any

from apps.reference_data.analysis.curve_regimes import (
    RegimeType,
    compare_curves_divergence,
    detect_regime_periods,
)
from apps.reference_data.models import YieldCurve


class NarrativeType:
    """Narrative type constants."""

    GRADUAL_DETERIORATION = "gradual_deterioration"
    ACUTE_SOVEREIGN_STRESS = "acute_sovereign_stress"
    LIQUIDITY_ILLUSION = "liquidity_illusion"
    FRAGMENTED_CEMAC_STRESS = "fragmented_cemac_stress"


def map_regime_to_narrative(
    regime_period: dict[str, Any],
    curve_context: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert regime period to narrative.

    Args:
        regime_period: Regime period dict from detect_regime_periods.
        curve_context: Context dict with curve metadata (country, currency, etc.).

    Returns:
        dict: Narrative with keys:
            - narrative_type: Narrative classification
            - period_start: Period start date
            - period_end: Period end date
            - severity: Severity indicator (low/medium/high)
            - causes: List of cause descriptions

    Example:
        >>> regime = {"regime_type": "high_stress", "start_date": date(2020, 3, 1), ...}
        >>> context = {"country": "CM", "currency": "XAF"}
        >>> narrative = map_regime_to_narrative(regime, context)
    """
    regime_type = regime_period.get("regime_type")
    yield_level = regime_period.get("representative_yield", 0.0)

    # Determine narrative type based on regime
    if regime_type == RegimeType.PUBLICATION_BREAKDOWN:
        narrative_type = NarrativeType.LIQUIDITY_ILLUSION
        causes = [
            "Missing or stale yield curve data",
            "Unable to assess true market conditions",
            "Data publication breakdown",
        ]
        severity = "unknown"

    elif regime_type == RegimeType.HIGH_STRESS:
        narrative_type = NarrativeType.ACUTE_SOVEREIGN_STRESS
        causes = [
            "Sovereign yield levels at extreme highs",
            "High volatility in yield movements",
            "Market stress conditions",
        ]
        severity = "high"

    elif regime_type == RegimeType.RISING_STRESS:
        # Check if it's gradual or acute
        period_days = (regime_period["end_date"] - regime_period["start_date"]).days

        if period_days > 180:  # More than 6 months
            narrative_type = NarrativeType.GRADUAL_DETERIORATION
            causes = [
                "Sustained increase in sovereign yields",
                "Gradual deterioration of market conditions",
                "Extended period of rising stress",
            ]
            severity = "medium"
        else:
            narrative_type = NarrativeType.ACUTE_SOVEREIGN_STRESS
            causes = [
                "Sharp increase in sovereign yields",
                "Rapid deterioration of market conditions",
                "Acute stress episode",
            ]
            severity = "high"

    else:  # NORMAL
        narrative_type = None  # No narrative for normal periods
        causes = []
        severity = "low"

    return {
        "narrative_type": narrative_type,
        "period_start": regime_period["start_date"],
        "period_end": regime_period["end_date"],
        "severity": severity,
        "causes": causes,
        "regime_type": regime_type,
        "yield_level": yield_level,
        "curve_context": curve_context,
    }


def anchor_narrative_to_history(
    narrative: dict[str, Any],
    historical_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Link narrative to real historical events.

    Args:
        narrative: Narrative dict from map_regime_to_narrative.
        historical_events: Optional list of historical events with date ranges.

    Returns:
        dict: Narrative with added 'historical_anchors' key.

    Example:
        >>> narrative = {"period_start": date(2020, 3, 1), ...}
        >>> events = [{"name": "COVID-19", "start": date(2020, 3, 1), ...}]
        >>> anchored = anchor_narrative_to_history(narrative, events)
    """
    if historical_events is None:
        historical_events = []

    narrative = narrative.copy()
    anchors = []

    period_start = narrative["period_start"]
    period_end = narrative["period_end"]

    # Find overlapping historical events
    for event in historical_events:
        event_start = event.get("start_date") or event.get("start")
        event_end = event.get("end_date") or event.get("end")

        if event_start and event_end:
            # Check for overlap
            if not (period_end < event_start or period_start > event_end):
                anchors.append(
                    {
                        "event_name": event.get("name", "Unknown Event"),
                        "event_start": event_start,
                        "event_end": event_end,
                        "overlap_type": (
                            "full"
                            if period_start >= event_start and period_end <= event_end
                            else "partial"
                        ),
                    }
                )

    narrative["historical_anchors"] = anchors
    return narrative


def define_narrative_causes(narrative: dict[str, Any]) -> str:
    """
    Generate plain language explanation of narrative causes.

    Args:
        narrative: Narrative dict.

    Returns:
        str: Plain language explanation.

    Example:
        >>> narrative = {"narrative_type": "acute_sovereign_stress", ...}
        >>> explanation = define_narrative_causes(narrative)
    """
    narrative_type = narrative.get("narrative_type")
    causes = narrative.get("causes", [])
    period_start = narrative.get("period_start")
    period_end = narrative.get("period_end")
    _severity = narrative.get("severity", "unknown")

    if not narrative_type:
        return "Normal market conditions - no stress narrative applicable."

    # Build explanation
    period_desc = f"from {period_start} to {period_end}"
    if (period_end - period_start).days < 30:
        period_desc = f"in {period_start.strftime('%B %Y')}"

    explanation_parts = [
        f"During the period {period_desc}, the yield curve exhibited "
        f"{narrative_type.replace('_', ' ').title()} characteristics."
    ]

    if causes:
        explanation_parts.append("Key contributing factors:")
        for cause in causes:
            explanation_parts.append(f"  - {cause}")

    if narrative.get("historical_anchors"):
        explanation_parts.append("\nThis period coincided with:")
        for anchor in narrative["historical_anchors"]:
            explanation_parts.append(
                f"  - {anchor['event_name']} ({anchor['event_start']} to {anchor['event_end']})"
            )

    return "\n".join(explanation_parts)


def compare_narratives_across_countries(curves: list[YieldCurve]) -> dict[str, Any]:
    """
    Identify CEMAC-wide vs country-specific stress narratives.

    Args:
        curves: List of YieldCurve instances to compare.

    Returns:
        dict: Comparison analysis with keys:
            - country_specific: Narratives unique to individual countries
            - cemac_wide: Narratives affecting multiple countries
            - divergence_periods: Periods with significant divergence

    Example:
        >>> curves = YieldCurve.objects.filter(currency="XAF")
        >>> comparison = compare_narratives_across_countries(list(curves))
    """
    if len(curves) < 2:
        return {
            "country_specific": [],
            "cemac_wide": [],
            "divergence_periods": [],
        }

    # Detect regimes for each curve
    all_narratives = []
    curve_narratives = {}

    for curve in curves:
        regimes = detect_regime_periods(curve)
        curve_narratives[curve.id] = []

        for regime in regimes:
            context = {
                "country": str(curve.country),
                "currency": str(curve.currency),
                "curve_name": curve.name,
            }
            narrative = map_regime_to_narrative(regime, context)
            if narrative["narrative_type"]:  # Skip normal periods
                narrative["curve_id"] = curve.id
                all_narratives.append(narrative)
                curve_narratives[curve.id].append(narrative)

    # Group narratives by period overlap
    cemac_wide = []
    country_specific = []

    # Simple overlap detection: narratives within 30 days of each other
    for i, nar1 in enumerate(all_narratives):
        is_cemac_wide = False

        for j, nar2 in enumerate(all_narratives):
            if i != j and nar1["curve_id"] != nar2["curve_id"]:
                # Check if periods overlap or are close
                days_apart = abs((nar1["period_start"] - nar2["period_start"]).days)
                if days_apart <= 30:
                    is_cemac_wide = True
                    break

        if is_cemac_wide:
            if nar1 not in cemac_wide:
                cemac_wide.append(nar1)
        else:
            if nar1 not in country_specific:
                country_specific.append(nar1)

    # Find divergence periods (compare pairs)
    divergence_periods = []
    for i in range(len(curves)):
        for j in range(i + 1, len(curves)):
            divergence = compare_curves_divergence(curves[i], curves[j])
            if divergence["divergence_points"]:
                divergence_periods.append(
                    {
                        "curve1_id": curves[i].id,
                        "curve1_name": curves[i].name,
                        "curve2_id": curves[j].id,
                        "curve2_name": curves[j].name,
                        "divergence_points": divergence["divergence_points"],
                        "average_divergence": divergence["average_divergence"],
                    }
                )

    return {
        "country_specific": country_specific,
        "cemac_wide": cemac_wide,
        "divergence_periods": divergence_periods,
    }
