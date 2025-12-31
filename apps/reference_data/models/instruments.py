"""
Instrument models.

Models for financial instruments, instrument groups, and instrument types.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from djmoney.models.fields import CurrencyField

from apps.reference_data.models.choices import FundCategory, ValuationMethod
from apps.reference_data.models.issuers import Issuer
from libs.models import OrganizationOwnedModel


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
        coupon_frequency (str, optional): Coupon payment frequency (e.g., 'ANNUAL', 'SEMI_ANNUAL').
        first_listing_date (date, optional): Date when the bond was first listed on an exchange.
        original_offering_amount (decimal, optional): Original offering amount at issuance.
        units_outstanding (decimal, optional): Number of units/shares currently outstanding.
        face_value (decimal, optional): Face value or par value of the bond.
        amortization_method (str, optional): Amortization method (e.g., 'BULLET', 'AMORTIZING').
        last_coupon_date (date, optional): Date of the last coupon payment.
        next_coupon_date (date, optional): Date of the next scheduled coupon payment.
        fund_category (str, optional): Fund category indicating asset type composition (for funds).
        fund_launch_date (date, optional): Date when the fund was launched.
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
        ...     coupon_frequency="ANNUAL",
        ...     face_value=1000.0,
        ...     original_offering_amount=100000000.0,
        ...     next_coupon_date=date(2025, 12, 31),
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
        Issuer,
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
    coupon_frequency = models.CharField(
        _("Coupon Frequency"), max_length=255, blank=True, null=True
    )
    first_listing_date = models.DateField(
        _("First Listing Date"),
        blank=True,
        null=True,
        help_text="Date when the bond was first listed on an exchange.",
    )
    original_offering_amount = models.DecimalField(
        _("Original Offering Amount"),
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Original offering amount at issuance.",
    )
    units_outstanding = models.DecimalField(
        _("Units Outstanding"),
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Number of units/shares currently outstanding.",
    )
    face_value = models.DecimalField(
        _("Face Value"),
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Face value or par value of the bond.",
    )
    amortization_method = models.CharField(
        _("Amortization Method"),
        max_length=50,
        blank=True,
        null=True,
        help_text="Amortization method (e.g., 'BULLET', 'AMORTIZING', 'ZERO_COUPON').",
    )
    last_coupon_date = models.DateField(
        _("Last Coupon Date"),
        blank=True,
        null=True,
        help_text="Date of the last coupon payment.",
    )
    next_coupon_date = models.DateField(
        _("Next Coupon Date"),
        blank=True,
        null=True,
        help_text="Date of the next scheduled coupon payment.",
    )
    fund_category = models.CharField(
        _("Fund Category"),
        max_length=20,
        choices=FundCategory.choices,
        blank=True,
        null=True,
        help_text="Fund category indicating asset type composition (DIVERSIFIED, MONEY_MARKET, BOND, EQUITY).",
    )
    fund_launch_date = models.DateField(
        _("Fund Launch Date"),
        blank=True,
        null=True,
        help_text="Date when the fund was launched.",
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
            models.Index(fields=["organization", "maturity_date"]),
            models.Index(fields=["organization", "first_listing_date"]),
            models.Index(fields=["organization", "next_coupon_date"]),
            models.Index(fields=["organization", "fund_category"]),
        ]

    def __str__(self) -> str:
        if self.isin:
            return f"{self.name} ({self.isin})"
        elif self.ticker:
            return f"{self.name} ({self.ticker})"
        return self.name
