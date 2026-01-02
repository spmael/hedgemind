"""
Issuer and rating models.

Models for entities that issue financial instruments and their credit ratings.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from apps.reference_data.utils.issuer_codes import (
    generate_issuer_code,
    validate_issuer_code,
)
from libs.models import OrganizationOwnedModel


class IssuerGroup(models.Model):
    """
    Hierarchical issuer group classification model.

    Supports nested groups (e.g., Financial -> Bank, Insurance) for flexible
    issuer categorization. Groups are organization-scoped but can share common
    top-level categories across organizations.

    Attributes:
        name (str): Group name (e.g., "Bank", "Sovereign").
        code (str): Short code identifier (e.g., "BANK", "SOV").
        parent (IssuerGroup, optional): Parent group for hierarchical structure.
        description (str, optional): Description of the group.
        is_active (bool): Whether this group is currently active.
        sort_order (int): Order for display/selection.
        created_at (datetime): When the record was created.
        updated_at (datetime): When the record was last updated.

    Example:
        >>> financial = IssuerGroup.objects.create(name="Financial", code="FIN")
        >>> bank = IssuerGroup.objects.create(name="Bank", code="BANK", parent=financial)
    """

    name = models.CharField(_("Name"), max_length=255)
    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Short code identifier (e.g., 'BANK', 'SOV').",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        verbose_name=_("Parent Group"),
        help_text="Parent group for hierarchical structure.",
    )
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    sort_order = models.IntegerField(_("Sort Order"), default=0)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Issuer Group")
        verbose_name_plural = _("Issuer Groups")
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["parent", "is_active"]),
        ]

    def __str__(self) -> str:
        """Return full path for hierarchical display."""
        if self.parent:
            return f"{self.parent} > {self.name}"
        return self.name

    def get_full_path(self) -> str:
        """Get full hierarchical path."""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)


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
        issuer_group (IssuerGroup, optional): Group classification (foreign key to IssuerGroup).
        rating (str, optional): Credit rating (e.g., "AAA", "BB+").
        rating_agency (str, optional): Rating agency that provided the rating.
        is_active (bool): Whether this issuer is currently active.
        created_at (datetime): When the issuer record was created.
        updated_at (datetime): When the issuer record was last updated.

    Example:
        >>> sovereign_group = IssuerGroup.objects.get(code="SOV")
        >>> issuer = Issuer.objects.create(
        ...     name="Republic of Cameroon",
        ...     country="CM",
        ...     issuer_group=sovereign_group
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
        unique=True,
        db_index=True,
        help_text=(
            "Stable identifier code following format [REGION]-[TYPE]-[IDENTIFIER] "
            "(e.g., CM-SOV-GOVT, GA-BNK-BANQUEDEGAB). "
            "Auto-generated if not provided. Globally unique."
        ),
    )
    short_name = models.CharField(
        _("Short Name"), max_length=255, blank=True, null=True
    )
    lei = models.CharField(
        _("LEI"),
        max_length=20,
        blank=True,
        null=True,
        help_text="Legal Entity Identifier (20-character code).",
    )
    country = CountryField(_("Country"), max_length=2, blank=True, null=True)
    issuer_group = models.ForeignKey(
        "IssuerGroup",
        on_delete=models.SET_NULL,
        related_name="issuers",
        null=True,
        blank=True,
        verbose_name=_("Issuer Group"),
        help_text="Group classification for this issuer.",
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

    def clean(self) -> None:
        """
        Validate issuer code format if provided.

        Raises:
            ValidationError: If issuer code format is invalid.
        """
        super().clean()
        if self.issuer_code:
            is_valid, error_message = validate_issuer_code(self.issuer_code)
            if not is_valid:
                raise ValidationError({"issuer_code": error_message})

    def save(self, *args, **kwargs) -> None:
        """
        Save issuer, auto-generating issuer_code if missing.

        Auto-generates issuer_code following the format [REGION]-[TYPE]-[IDENTIFIER]
        if not provided. Validates format if issuer_code is manually provided.
        """
        # Auto-generate issuer_code if missing
        if not self.issuer_code:
            issuer_group_code = self.issuer_group.code if self.issuer_group else None
            country_code = str(self.country) if self.country else None
            self.issuer_code = generate_issuer_code(
                name=self.name,
                country=country_code,
                issuer_group_code=issuer_group_code,
            )

            # Handle potential uniqueness conflicts by appending a number
            # Use _base_manager to check global uniqueness (bypass organization filter)
            if self.pk:
                # For updates, check if code conflicts with other issuers
                base_code = self.issuer_code
                counter = 1
                while (
                    Issuer._base_manager.filter(issuer_code=self.issuer_code)
                    .exclude(pk=self.pk)
                    .exists()
                ):
                    # Append number to identifier part
                    parts = base_code.rsplit("-", 1)
                    if len(parts) == 2:
                        region_type, identifier = parts
                        # Truncate identifier if needed to fit max_length
                        max_id_length = 10 - len(str(counter))
                        identifier = (
                            identifier[:max_id_length] if max_id_length > 0 else "X"
                        )
                        self.issuer_code = f"{region_type}-{identifier}{counter}"
                    else:
                        self.issuer_code = f"{base_code}{counter}"
                    counter += 1
                    if counter > 999:  # Safety limit
                        raise ValueError("Unable to generate unique issuer code")
            else:
                # For new issuers, check conflicts before saving
                base_code = self.issuer_code
                counter = 1
                while Issuer._base_manager.filter(
                    issuer_code=self.issuer_code
                ).exists():
                    # Append number to identifier part
                    parts = base_code.rsplit("-", 1)
                    if len(parts) == 2:
                        region_type, identifier = parts
                        # Truncate identifier if needed to fit max_length
                        max_id_length = 10 - len(str(counter))
                        identifier = (
                            identifier[:max_id_length] if max_id_length > 0 else "X"
                        )
                        self.issuer_code = f"{region_type}-{identifier}{counter}"
                    else:
                        self.issuer_code = f"{base_code}{counter}"
                    counter += 1
                    if counter > 999:  # Safety limit
                        raise ValueError("Unable to generate unique issuer code")

        # Validate issuer code format before saving
        if self.issuer_code:
            is_valid, error_message = validate_issuer_code(self.issuer_code)
            if not is_valid:
                raise ValidationError({"issuer_code": error_message})

        super().save(*args, **kwargs)

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
