"""
Yield curve stress calibration.

Implements Phase 4: Translate Narratives into Stress Inputs.

Converts stress narratives into usable haircut bands for the stress engine.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.reference_data.analysis.curve_narratives import (
    NarrativeType,
    define_narrative_causes,
)
from apps.reference_data.models import YieldCurve, YieldCurveStressProfile


def calibrate_haircuts_from_narrative(
    narrative: dict[str, Any],
    historical_period: dict[str, Any] | None = None,
) -> dict[str, Decimal]:
    """
    Convert narrative to haircut bands.

    Args:
        narrative: Narrative dict from map_regime_to_narrative.
        historical_period: Optional historical period data for calibration.

    Returns:
        dict: Haircut percentages with keys:
            - sovereign_haircut_pct
            - corporate_haircut_pct
            - supra_haircut_pct

    Example:
        >>> narrative = {"narrative_type": "acute_sovereign_stress", "severity": "high", ...}
        >>> haircuts = calibrate_haircuts_from_narrative(narrative)
        >>> print(f"Sovereign haircut: {haircuts['sovereign_haircut_pct']}%")
    """
    narrative_type = narrative.get("narrative_type")
    severity = narrative.get("severity", "unknown")

    # Base haircuts by narrative type and severity
    # These are conservative, explicit assumptions
    if narrative_type == NarrativeType.ACUTE_SOVEREIGN_STRESS:
        if severity == "high":
            # High acute stress: significant haircuts
            sovereign = Decimal("15.00")  # 15%
            corporate = Decimal("25.00")  # 25% (higher than sovereign)
            supra = Decimal("10.00")  # 10% (lower than sovereign)
        else:
            # Medium acute stress
            sovereign = Decimal("10.00")
            corporate = Decimal("20.00")
            supra = Decimal("7.00")

    elif narrative_type == NarrativeType.GRADUAL_DETERIORATION:
        if severity == "high":
            # High gradual deterioration
            sovereign = Decimal("12.00")
            corporate = Decimal("22.00")
            supra = Decimal("8.00")
        else:
            # Medium gradual deterioration
            sovereign = Decimal("8.00")
            corporate = Decimal("15.00")
            supra = Decimal("5.00")

    elif narrative_type == NarrativeType.LIQUIDITY_ILLUSION:
        # Missing data: conservative haircuts (we don't know true conditions)
        sovereign = Decimal("20.00")  # Higher uncertainty
        corporate = Decimal("30.00")
        supra = Decimal("15.00")

    elif narrative_type == NarrativeType.FRAGMENTED_CEMAC_STRESS:
        # Fragmented stress: country-specific, moderate haircuts
        sovereign = Decimal("12.00")
        corporate = Decimal("20.00")
        supra = Decimal("8.00")

    else:
        # Unknown or normal: minimal haircuts
        sovereign = Decimal("5.00")
        corporate = Decimal("10.00")
        supra = Decimal("3.00")

    return {
        "sovereign_haircut_pct": sovereign,
        "corporate_haircut_pct": corporate,
        "supra_haircut_pct": supra,
    }


def differentiate_by_issuer_type(narrative: dict[str, Any]) -> dict[str, Decimal]:
    """
    Apply different haircuts by issuer type based on narrative.

    This is a wrapper around calibrate_haircuts_from_narrative that ensures
    issuer differentiation is explicit.

    Args:
        narrative: Narrative dict.

    Returns:
        dict: Haircut percentages by issuer type.

    Example:
        >>> narrative = {"narrative_type": "acute_sovereign_stress", ...}
        >>> haircuts = differentiate_by_issuer_type(narrative)
    """
    return calibrate_haircuts_from_narrative(narrative)


def validate_calibration_assumptions(profile: YieldCurveStressProfile) -> list[str]:
    """
    Validate that calibration assumptions are explicit and deterministic.

    Args:
        profile: YieldCurveStressProfile instance to validate.

    Returns:
        list[str]: List of validation warnings/errors (empty if valid).

    Example:
        >>> profile = YieldCurveStressProfile.objects.get(id=1)
        >>> warnings = validate_calibration_assumptions(profile)
        >>> if warnings:
        ...     print("Validation issues:", warnings)
    """
    warnings = []

    # Check that rationale is provided
    if (
        not profile.calibration_rationale
        or len(profile.calibration_rationale.strip()) < 50
    ):
        warnings.append(
            "Calibration rationale is missing or too brief. "
            "Must explain how haircuts were derived from historical narrative."
        )

    # Check that haircuts are within reasonable bounds
    if profile.sovereign_haircut_pct > 50:
        warnings.append(
            f"Sovereign haircut ({profile.sovereign_haircut_pct}%) is very high (>50%). "
            "Verify this is intentional and documented."
        )

    if profile.corporate_haircut_pct > 50:
        warnings.append(
            f"Corporate haircut ({profile.corporate_haircut_pct}%) is very high (>50%). "
            "Verify this is intentional and documented."
        )

    # Check that corporate >= sovereign (generally expected)
    if profile.corporate_haircut_pct < profile.sovereign_haircut_pct:
        warnings.append(
            "Corporate haircut is lower than sovereign haircut. "
            "This may be intentional but should be documented in rationale."
        )

    # Check that period is valid
    if profile.period_end < profile.period_start:
        warnings.append("Period end date is before period start date.")

    # Check staleness
    if profile.staleness_days and profile.staleness_days > 180:
        warnings.append(
            f"Curve data is stale ({profile.staleness_days} days). "
            "Stress profile may be based on outdated information."
        )

    return warnings


def create_stress_profile_from_narrative(
    curve: YieldCurve,
    narrative: dict[str, Any],
    regime_period: dict[str, Any],
) -> YieldCurveStressProfile:
    """
    Create a YieldCurveStressProfile from a narrative and regime period.

    Args:
        curve: YieldCurve instance.
        narrative: Narrative dict from map_regime_to_narrative.
        regime_period: Regime period dict from detect_regime_periods.

    Returns:
        YieldCurveStressProfile: Created profile instance.

    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> regimes = detect_regime_periods(curve)
        >>> narrative = map_regime_to_narrative(regimes[0], {"country": "CM"})
        >>> profile = create_stress_profile_from_narrative(curve, narrative, regimes[0])
    """
    # Calibrate haircuts
    haircuts = calibrate_haircuts_from_narrative(narrative)

    # Generate rationale
    causes_text = define_narrative_causes(narrative)
    rationale = f"""
Stress profile calibrated from historical narrative: {narrative.get('narrative_type', 'unknown')}

Historical Period: {narrative['period_start']} to {narrative['period_end']}
Regime Type: {narrative.get('regime_type', 'unknown')}
Severity: {narrative.get('severity', 'unknown')}

Narrative Context:
{causes_text}

Calibrated Haircuts:
- Sovereign: {haircuts['sovereign_haircut_pct']}%
- Corporate: {haircuts['corporate_haircut_pct']}%
- Supranational: {haircuts['supra_haircut_pct']}%

These haircuts are based on historical yield curve stress patterns observed during
the specified period. Corporate issuers receive higher haircuts than sovereign issuers
due to higher credit risk. Supranational issuers receive lower haircuts due to
multilateral support structures.

Note: These are deterministic, explicit assumptions. No interpolation or curve fitting
was used in calibration.
""".strip()

    # Create or update profile
    profile, created = YieldCurveStressProfile.objects.update_or_create(
        curve=curve,
        narrative=narrative.get("narrative_type"),
        period_start=narrative["period_start"],
        period_end=narrative["period_end"],
        defaults={
            "regime_type": narrative.get("regime_type", ""),
            "sovereign_haircut_pct": haircuts["sovereign_haircut_pct"],
            "corporate_haircut_pct": haircuts["corporate_haircut_pct"],
            "supra_haircut_pct": haircuts["supra_haircut_pct"],
            "calibration_rationale": rationale,
            "is_active": True,
        },
    )

    # Update staleness from curve
    profile.save()  # Triggers staleness update

    return profile
