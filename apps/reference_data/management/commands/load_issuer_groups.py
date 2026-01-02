"""
Management command to load canonical issuer groups with hierarchical structure.

This command loads the standard issuer group hierarchy into the database as
global reference data shared across all organizations.

Hierarchy:
├── Sovereign (Government)
├── Supranational/Multilateral
├── Government-Related Entity (GRE) / Quasi-Sovereign
├── Financial
│   ├── Bank
│   ├── Insurance
│   ├── Asset Manager
│   └── Other Financial (leasing, microfinance)
└── Corporate (Non-Financial)
    ├── Industrial
    ├── Consumer
    ├── Energy
    └── Utilities

Usage:
    python manage.py load_issuer_groups
    python manage.py load_issuer_groups --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.reference_data.models.issuers import IssuerGroup


def get_canonical_issuer_groups() -> list[dict]:
    """
    Get canonical issuer group definitions with hierarchical structure.
    
    Returns:
        list: List of group definitions, each with code, name, description, parent_code, and sort_order.
    """
    return [
        # Top-level groups
        {
            "code": "SOV",
            "name": "Sovereign (Government)",
            "description": "National governments and sovereign entities",
            "parent_code": None,
            "sort_order": 10,
        },
        {
            "code": "SUPRA",
            "name": "Supranational/Multilateral",
            "description": "International organizations and multilateral development banks",
            "parent_code": None,
            "sort_order": 20,
        },
        {
            "code": "GRE",
            "name": "Government-Related Entity (GRE) / Quasi-Sovereign",
            "description": "Entities owned or controlled by governments with implicit or explicit government support",
            "parent_code": None,
            "sort_order": 30,
        },
        {
            "code": "FIN",
            "name": "Financial",
            "description": "Financial institutions and services companies",
            "parent_code": None,
            "sort_order": 40,
        },
        {
            "code": "CORP",
            "name": "Corporate (Non-Financial)",
            "description": "Non-financial corporations and businesses",
            "parent_code": None,
            "sort_order": 50,
        },
        # Financial sub-groups
        {
            "code": "BANK",
            "name": "Bank",
            "description": "Commercial banks, investment banks, and banking institutions",
            "parent_code": "FIN",
            "sort_order": 41,
        },
        {
            "code": "INS",
            "name": "Insurance",
            "description": "Insurance companies and insurance-related entities",
            "parent_code": "FIN",
            "sort_order": 42,
        },
        {
            "code": "AM",
            "name": "Asset Manager",
            "description": "Asset management companies and investment managers",
            "parent_code": "FIN",
            "sort_order": 43,
        },
        {
            "code": "MF",
            "name": "Microfinance",
            "description": "Microfinance institutions and microcredit organizations",
            "parent_code": "FIN",
            "sort_order": 44,
        },
        {
            "code": "FIN_OTHER",
            "name": "Other Financial",
            "description": "Other financial institutions (leasing companies, factoring, etc.)",
            "parent_code": "FIN",
            "sort_order": 45,
        },
        # Corporate sub-groups
        {
            "code": "IND",
            "name": "Industrial",
            "description": "Industrial and manufacturing companies",
            "parent_code": "CORP",
            "sort_order": 51,
        },
        {
            "code": "CONS",
            "name": "Consumer",
            "description": "Consumer goods and services companies",
            "parent_code": "CORP",
            "sort_order": 52,
        },
        {
            "code": "ENERGY",
            "name": "Energy",
            "description": "Energy sector companies (oil, gas, renewables, etc.)",
            "parent_code": "CORP",
            "sort_order": 53,
        },
        {
            "code": "UTIL",
            "name": "Utilities",
            "description": "Utility companies (electricity, water, telecommunications, etc.)",
            "parent_code": "CORP",
            "sort_order": 54,
        },
    ]


class Command(BaseCommand):
    """
    Management command to load canonical issuer groups with hierarchical structure.
    
    This command loads the standard issuer group hierarchy as global reference data
    shared across all organizations. The command is idempotent and can be run
    multiple times safely.
    
    Usage example:
        python manage.py load_issuer_groups
        python manage.py load_issuer_groups --dry-run
        python manage.py load_issuer_groups --actor-id 42
    """

    help = "Load canonical issuer groups with hierarchical structure (idempotent, global reference data)"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating it",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options["dry_run"]
        actor_id = options.get("actor_id")

        # Get actor if provided
        actor = None
        if actor_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                actor = User.objects.get(pk=actor_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"User with ID {actor_id} does not exist, proceeding without actor"
                    )
                )

        canonical_groups = get_canonical_issuer_groups()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would load {len(canonical_groups)} issuer groups (global reference data)"
                )
            )
            for group_def in canonical_groups:
                parent_info = f" (parent: {group_def['parent_code']})" if group_def["parent_code"] else ""
                self.stdout.write(f"  - {group_def['code']}: {group_def['name']}{parent_info}")
            return

        # Load groups as global reference data
        created_count = 0
        updated_count = 0
        errors = []
        parent_map = {}  # Map parent codes to IssuerGroup instances

        try:
            with transaction.atomic():
                # Sort groups: top-level first, then children
                top_level = [g for g in canonical_groups if g["parent_code"] is None]
                children = [g for g in canonical_groups if g["parent_code"] is not None]
                ordered_groups = top_level + children

                for group_def in ordered_groups:
                    try:
                        # Get parent if specified
                        parent = None
                        if group_def["parent_code"]:
                            if group_def["parent_code"] not in parent_map:
                                errors.append(
                                    f"Parent group '{group_def['parent_code']}' not found for {group_def['code']}"
                                )
                                continue
                            parent = parent_map[group_def["parent_code"]]

                        group, created = IssuerGroup.objects.get_or_create(
                            code=group_def["code"],
                            defaults={
                                "name": group_def["name"],
                                "description": group_def["description"],
                                "parent": parent,
                                "sort_order": group_def["sort_order"],
                            },
                        )

                        if created:
                            created_count += 1
                            parent_info = f" (parent: {group_def['parent_code']})" if parent else ""
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Created group: {group_def['code']} - {group_def['name']}{parent_info}"
                                )
                            )
                        else:
                            # Update if any fields changed
                            updated = False
                            if group.name != group_def["name"]:
                                group.name = group_def["name"]
                                updated = True
                            if group.description != group_def["description"]:
                                group.description = group_def["description"]
                                updated = True
                            if group.parent != parent:
                                group.parent = parent
                                updated = True
                            if group.sort_order != group_def["sort_order"]:
                                group.sort_order = group_def["sort_order"]
                                updated = True

                            if updated:
                                group.save()
                                updated_count += 1
                                parent_info = f" (parent: {group_def['parent_code']})" if parent else ""
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Updated group: {group_def['code']} - {group_def['name']}{parent_info}"
                                    )
                                )
                            else:
                                self.stdout.write(
                                    f"Group already exists: {group_def['code']} - {group_def['name']}"
                                )

                        # Store in parent map for children to reference
                        parent_map[group_def["code"]] = group

                    except Exception as e:
                        error_msg = (
                            f"Error processing group {group_def['code']}: {str(e)}"
                        )
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))

                # Create audit event (organization_id is None for global reference data)
                if created_count > 0 or updated_count > 0 or errors:
                    AuditEvent.objects.create(
                        organization_id=None,  # Global reference data
                        actor=actor,
                        action="LOAD_REFERENCE_DATA",
                        object_type="IssuerGroup",
                        object_repr=f"Loaded {len(canonical_groups)} canonical issuer groups",
                        metadata={
                            "groups_loaded": len(canonical_groups),
                            "groups_created": created_count,
                            "groups_updated": updated_count,
                            "errors": errors,
                            "command": "load_issuer_groups",
                            "scope": "global",
                        },
                    )

        except Exception as e:
            raise CommandError(f"Failed to load issuer groups: {str(e)}")

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted loading {len(canonical_groups)} issuer groups (global reference data)"
            )
        )
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Errors: {len(errors)}")
        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    - {error}"))

