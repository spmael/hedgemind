"""
Portfolio ingestion service package.

Provides services for importing portfolio positions from CSV/Excel files
into PositionSnapshot records with full validation and error tracking.
"""

from apps.portfolios.ingestion.import_excel import import_portfolio_from_file

__all__ = ["import_portfolio_from_file"]

