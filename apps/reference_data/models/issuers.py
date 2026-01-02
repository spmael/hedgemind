"""
Issuer and rating models.

Models for entities that issue financial instruments and their credit ratings.
"""

from __future__ import annotations

from django.db import models
from django.db.models import UniqueConstraint
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from libs.models import OrganizationOwnedModel


class Issuer(OrganizationOwnedModel):
    """
    Issuer model representing entities that issue financial instruments.

    Issuers can be governments, corporations, financial institutions, or other
    entities that issue securities. This model supports issuer-level exposure
    analysis and concentration risk calculations.

    Attributes:
        name (str): Full legal name of the issuer.
        issuer_code (str): Stable identifier code for cross-org consistency (globally unique).
        short_name (str, optional): Short name or abbreviation.
        lei (str, optional): Legal Entity Identifier (20-character code).
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
    issuer_code = models.CharField(
        _("Issuer Code"),
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stable identifier code for cross-org consistency (globally unique).",
    )
    short_name = models.CharField(
        _("Short Name"), max_length=255, blank=True, null=True
    )
    lei = models.CharField(
        _("LEI"),
        max_length=30,
        blank=True,
        null=True,
        help_text="Legal Entity Identifier (20-character code).",
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
            models.Index(fields=["issuer_code"]),
        ]
        unique_together = [["organization", "name"]]
        constraints = [
            UniqueConstraint(
                fields=["organization", "issuer_code"], name="unique_issuer_per_org"
            )
        ]

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
