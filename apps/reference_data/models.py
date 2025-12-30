"""
Reference data models for securities, issuers, and market data.

This module provides the core reference data models that support portfolio
management and risk analytics. All business reference data is scoped to
organizations to support multi-tenant isolation.

Key components:
- Issuer: Entity that issues securities (governments, corporations, etc.)
- Instrument: Financial instruments (bonds, equity, deposits, funds, etc.)
- FXRate: Foreign exchange rates for currency conversion
- YieldCurvePoint: Yield curve data points for fixed income valuation

All models use OrganizationOwnedModel to ensure automatic organization scoping.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from djmoney.models.fields import CurrencyField

from libs.models import OrganizationOwnedModel


class Issuer(OrganizationOwnedModel):
    """
    Issuer model representing entities that issue financial instruments.

    Issuers can be governments, corporations, financial institutions, or other
    entities that issue securities. This model supports issuer-level exposure
    analysis and concentration risk calculations.

    Attributes:
        name (str): Full legal name of the issuer.
        short_name (str, optional): Short name or abbreviation.
        country (str): Country code of the issuer's domicile.
        issuer_group (str, optional): Group classification (e.g., "Sovereign", "Corporate").
        rating (str, optional): Credit rating (e.g., "AAA", "BB+").
        rating_agency (str, optional): Rating agency that provided the rating.
        is_active (bool): Whether this issuer is currently active.
        created_at (datetime): When the issuer record was created.
        updated_at (datetime): When the issuer record was last updated.

    Example:
        >>> issuer = Issuer.objects.create(
        ...     name="Republic of Cameroon",
        ...     country="CM",
        ...     issuer_group="Sovereign"
        ... )
        >>> print(issuer.name)
        Republic of Cameroon
    """

    name = models.CharField(_("Name"), max_length=255)
    short_name = models.CharField(
        _("Short Name"), max_length=255, blank=True, null=True
    )
    country = CountryField(_("Country"), max_length=2, blank=True, null=True)
    issuer_group = models.CharField(
        _("Issuer Group"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Group classification (e.g., 'Sovereign', 'Corporate')",
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Issuer")
        verbose_name_plural = _("Issuers")
        indexes = [
            models.Index(fields=["organization", "name"]),
            models.Index(fields=["organization", "country"]),
            models.Index(fields=["organization", "issuer_group"]),
        ]
        unique_together = [["organization", "name"]]

    def __str__(self) -> str:
        return self.name


class IssuerRating(models.Model):
    """
    Represents a credit rating assigned to an Issuer by a specific rating agency at a point in time.

    Supports multiple agencies rating the same issuer, and maintains the historical evolution of
    issuer ratings over time.

    Attributes:
        issuer (Issuer): The issuer being rated.
        agency (RatingAgency): The agency assigning the rating.
        rating (str): The assigned credit rating (e.g., "AAA", "BB+").
        date_assigned (date): The date when this rating became effective.
        is_active (bool): Whether this rating is currently active for this issuer/agency.
        created_at (datetime): When this record was created.

    Example:
        >>> issuer = Issuer.objects.get(name="Republic of Cameroon")
        >>> IssuerRating.objects.create(
        ...     issuer=issuer,
        ...     agency="S&P",
        ...     rating="BB",
        ...     outlook="Stable",
        ...     date_assigned=date(2024, 4, 1)
        ... )
    """

    class RatingAgency(models.TextChoices):
        S_P = "S&P", "Standard & Poor's"
        MOODY_S = "Moody's", "Moody's"
        FITCH = "Fitch", "Fitch"
        BLOOMFIELD = "Bloomfield", "Bloomfield"

    issuer = models.ForeignKey(
        "Issuer",
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name=_("Issuer"),
        help_text="The issuer to which this rating applies.",
    )
    agency = models.CharField(
        _("Rating Agency"),
        max_length=255,
        choices=RatingAgency.choices,
        help_text="Agency that assigned the rating (e.g., 'S&P', 'Moody's', 'Fitch').",
    )
    rating = models.CharField(
        _("Rating"),
        max_length=255,
        help_text="Credit rating assigned (e.g., 'AAA', 'BB+').",
    )
    date_assigned = models.DateField(
        _("Date Assigned"), help_text="Date this rating became effective."
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text="Whether this rating is currently the active rating from this agency.",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Issuer Rating")
        verbose_name_plural = _("Issuer Ratings")
        ordering = ["-date_assigned", "agency"]
        indexes = [
            models.Index(fields=["issuer", "agency"]),
            models.Index(fields=["issuer", "date_assigned"]),
            models.Index(fields=["agency", "is_active"]),
        ]
        unique_together = [["issuer", "agency", "date_assigned"]]

    def __str__(self) -> str:
        """
        String representation for the issuer rating.

        Returns:
            str: Human-readable string of the form "Issuer - Agency: Rating (as of date)".
        """
        return f"{self.issuer.name} - {self.agency}: {self.rating} (as of {self.date_assigned})"


class InstrumentGroup(models.Model):
    """
    Grouping model for financial instruments.

    InstrumentGroup allows classification and organization of financial instruments
    for reporting, analytics, or reference data purposes. Groups may represent sectors,
    product types, or institution-specific categories for use in exposure calculations
    or risk reports.

    Attributes
    ----------
    name : str
        Human-readable name for the instrument group.
    description : str, optional
        Detailed description of the group, including intended use or mapping logic.
    created_at : datetime
        Timestamp when this record was created (auto-managed).
    updated_at : datetime
        Timestamp when this record was last modified.

    Example
    -------
        >>> group = InstrumentGroup.objects.create(name="Government Bonds")
        >>> print(group.name)
        Government Bonds

    Note
    ----
    Groups should have unique names. This classification affects analytics
    calculations and grouping in board/regulatory reports.
    """

    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True, null=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Instrument Group")
        verbose_name_plural = _("Instrument Groups")
        indexes = [
            models.Index(fields=["name"]),
        ]
        unique_together = [["name"]]

    def __str__(self) -> str:
        return self.name


class InstrumentType(models.Model):
    """
    Represents a type of financial instrument.

    Attributes:
        name (str): The name of the instrument type.
        description (str): The description of the instrument type.
    """

    group = models.ForeignKey(
        "InstrumentGroup",
        on_delete=models.CASCADE,
        related_name="types",
        verbose_name=_("Instrument Group"),
        help_text="The group to which this type belongs.",
    )
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True, null=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Instrument Type")
        verbose_name_plural = _("Instrument Types")
        indexes = [
            models.Index(fields=["group", "name"]),
        ]
        unique_together = [["group", "name"]]

    def __str__(self) -> str:
        return f"{self.group.name} - {self.name}"


class ValuationMethod(models.TextChoices):
    """
    Valuation method choices for instruments.

    Defines how the instrument is valued:
    - MARK_TO_MARKET: Public assets with market prices
    - MARK_TO_MODEL: Modeled valuations (future use)
    - EXTERNAL_APPRAISAL: Third-party valuation
    - MANUAL_DECLARED: Manual entry by institution
    """

    MARK_TO_MARKET = "mark_to_market", _("Mark to Market")
    MARK_TO_MODEL = "mark_to_model", _("Mark to Model")
    EXTERNAL_APPRAISAL = "external_appraisal", _("External Appraisal")
    MANUAL_DECLARED = "manual_declared", _("Manual Declared")


class Instrument(OrganizationOwnedModel):
    """
    Instrument model representing financial instruments in portfolios.

    Instruments are the core reference data entities that represent securities,
    bonds, equities, deposits, and other financial assets. This model supports
    both public market instruments and private assets with appropriate
    valuation methods.

    Attributes:
        isin (str, optional): International Securities Identification Number.
        ticker (str, optional): Trading ticker symbol.
        name (str): Full name or description of the instrument.
        instrument_group (InstrumentGroup): Group of instrument.
        instrument_type (InstrumentType): Type of instrument.
        currency (str): Currency code of the instrument.
        issuer (Issuer, optional): Issuer of the instrument (for bonds, equity).
        country (str): Country code of the instrument's domicile.
        sector (str, optional): Economic sector classification.
        maturity_date (date, optional): Maturity date for fixed income instruments.
        coupon_rate (decimal, optional): Coupon rate for bonds (as percentage).
        valuation_method (str): How this instrument is valued.
        is_active (bool): Whether this instrument is currently active.
        created_at (datetime): When the instrument record was created.
        updated_at (datetime): When the instrument record was last updated.

    Note:
        For private assets, use MANUAL_DECLARED valuation method and store
        declared values rather than attempting market pricing.

    Example:
        >>> issuer = Issuer.objects.get(name="Republic of Cameroon")
        >>> bond = Instrument.objects.create(
        ...     isin="CM1234567890",
        ...     name="Cameroon 5Y Government Bond",
        ...     instrument_group=InstrumentGroup.objects.get(name="Government Bonds"),
        ...     instrument_type=InstrumentType.objects.get(name="Bond"),
        ...     currency="XAF",
        ...     issuer=issuer,
        ...     country="CM",
        ...     maturity_date=date(2029, 12, 31),
        ...     coupon_rate=5.5,
        ...     valuation_method=ValuationMethod.MARK_TO_MARKET
        ... )
    """

    isin = models.CharField(
        _("ISIN"),
        max_length=255,
        blank=True,
        null=True,
        help_text="International Securities Identification Number.",
    )
    ticker = models.CharField(
        _("Ticker"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Trading ticker symbol.",
    )
    name = models.CharField(
        _("Name"),
        max_length=255,
        help_text="Full name or description of the instrument.",
    )
    instrument_group = models.ForeignKey(
        "InstrumentGroup",
        on_delete=models.CASCADE,
        related_name="instruments",
        verbose_name=_("Instrument Group"),
        help_text="The group to which this instrument belongs.",
    )
    instrument_type = models.ForeignKey(
        "InstrumentType",
        on_delete=models.CASCADE,
        related_name="instruments",
        verbose_name=_("Instrument Type"),
        help_text="The type of this instrument.",
    )
    currency = CurrencyField(
        _("Currency"), max_length=3, default=settings.DEFAULT_CURRENCY
    )
    issuer = models.ForeignKey(
        "Issuer",
        on_delete=models.CASCADE,
        related_name="instruments",
        verbose_name=_("Issuer"),
        help_text="The issuer of this instrument.",
    )
    country = CountryField(_("Country"), max_length=2, blank=True, null=True)
    sector = models.CharField(
        _("Sector"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Economic sector classification.",
    )
    maturity_date = models.DateField(_("Maturity Date"), blank=True, null=True)
    coupon_rate = models.DecimalField(
        _("Coupon Rate"),
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Coupon rate for bonds (as percentage).",
    )
    valuation_method = models.CharField(
        _("Valuation Method"),
        max_length=255,
        choices=ValuationMethod.choices,
        default=ValuationMethod.MARK_TO_MARKET,
        help_text="How this instrument is valued.",
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Instrument")
        verbose_name_plural = _("Instruments")
        indexes = [
            models.Index(fields=["organization", "isin"]),
            models.Index(fields=["organization", "ticker"]),
            models.Index(fields=["organization", "instrument_group"]),
            models.Index(fields=["organization", "instrument_type"]),
            models.Index(fields=["organization", "currency"]),
            models.Index(fields=["organization", "issuer"]),
            models.Index(fields=["organization", "country"]),
        ]

    def __str__(self) -> str:
        if self.isin:
            return f"{self.name} ({self.isin})"
        elif self.ticker:
            return f"{self.name} ({self.ticker})"
        return self.name
