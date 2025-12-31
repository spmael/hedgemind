"""
Validation rules for portfolio position imports.

Implements business rules and data quality checks for position data.
Supports flexible market value: either provided directly OR computed from quantity * price.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from djmoney.money import Money

from apps.portfolios.models import ValuationSource


class ValidationError(Exception):
    """Validation error with optional error code."""

    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code
        super().__init__(message)


def validate_row(
    row_data: dict[str, Any], portfolio_base_currency: str
) -> dict[str, Any]:
    """
    Validate a single row of position data.

    Supports flexible market value computation:
    - If market_value provided: use it
    - If market_value missing but quantity and price provided: compute market_value = quantity * price
    - If price missing but market_value and quantity provided: compute price = market_value / quantity

    Args:
        row_data: Extracted row data from file.
        portfolio_base_currency: Base currency of the portfolio (for Money field defaults).

    Returns:
        dict: Validated and normalized row data (may have computed fields added).

    Raises:
        ValidationError: If validation fails.
    """
    # Required fields validation
    if "instrument_identifier" not in row_data or not row_data["instrument_identifier"]:
        raise ValidationError(
            "instrument_identifier is required", code="MISSING_INSTRUMENT"
        )

    if "quantity" not in row_data:
        raise ValidationError("quantity is required", code="MISSING_QUANTITY")

    if "currency" not in row_data or not row_data["currency"]:
        raise ValidationError("currency is required", code="MISSING_CURRENCY")

    # Quantity validation
    quantity = row_data["quantity"]
    if not isinstance(quantity, Decimal):
        raise ValidationError(
            "quantity must be a Decimal", code="INVALID_QUANTITY_TYPE"
        )
    if quantity <= 0:
        raise ValidationError(
            "quantity must be positive", code="INVALID_QUANTITY_VALUE"
        )

    # Currency validation
    currency = str(row_data["currency"]).upper().strip()
    if len(currency) != 3:
        raise ValidationError(
            "currency must be a 3-character ISO code", code="INVALID_CURRENCY"
        )
    row_data["currency"] = currency

    # Price validation (optional)
    price = row_data.get("price")
    if price is not None:
        if not isinstance(price, Decimal):
            raise ValidationError("price must be a Decimal", code="INVALID_PRICE_TYPE")
        if price <= 0:
            raise ValidationError("price must be positive", code="INVALID_PRICE_VALUE")

    # Market value validation and computation
    market_value = row_data.get("market_value")

    # If market_value is provided as Money, extract amount and currency
    if isinstance(market_value, Money):
        market_value_amount = market_value.amount
        market_value_currency = market_value.currency
    elif market_value is not None:
        # If it's a Decimal, use it
        if isinstance(market_value, Decimal):
            market_value_amount = market_value
            market_value_currency = currency
        else:
            raise ValidationError(
                "market_value must be a Decimal or Money",
                code="INVALID_MARKET_VALUE_TYPE",
            )
    else:
        market_value_amount = None
        market_value_currency = currency

    # Compute market_value if missing but quantity and price are available
    if market_value_amount is None:
        if price is not None:
            # Compute market_value = quantity * price
            market_value_amount = quantity * price
            market_value_currency = currency
        else:
            raise ValidationError(
                "market_value is required, or both quantity and price must be provided",
                code="MISSING_MARKET_VALUE",
            )

    # Compute price if missing but market_value and quantity are available
    if price is None:
        if market_value_amount is not None:
            # Compute price = market_value / quantity
            try:
                price = market_value_amount / quantity
            except (InvalidOperation, ZeroDivisionError):
                raise ValidationError(
                    "Cannot compute price: division error",
                    code="PRICE_COMPUTATION_ERROR",
                )

    # Validate market_value is positive
    if market_value_amount <= 0:
        raise ValidationError(
            "market_value must be positive", code="INVALID_MARKET_VALUE"
        )

    # Create Money object for market_value
    market_value_money = Money(market_value_amount, market_value_currency)
    row_data["market_value"] = market_value_money
    row_data["price"] = price

    # Book value validation (required)
    if "book_value" not in row_data:
        raise ValidationError("book_value is required", code="MISSING_BOOK_VALUE")

    book_value = row_data["book_value"]
    if isinstance(book_value, Money):
        book_value_amount = book_value.amount
        book_value_currency = book_value.currency
    elif isinstance(book_value, Decimal):
        book_value_amount = book_value
        book_value_currency = currency
    else:
        raise ValidationError(
            "book_value must be a Decimal or Money", code="INVALID_BOOK_VALUE_TYPE"
        )

    if book_value_amount <= 0:
        raise ValidationError("book_value must be positive", code="INVALID_BOOK_VALUE")

    # Ensure book_value uses correct currency
    if isinstance(book_value, Money) and book_value.currency != currency:
        # Convert or use provided currency
        book_value_money = Money(book_value_amount, currency)
    else:
        book_value_money = Money(book_value_amount, book_value_currency)

    row_data["book_value"] = book_value_money

    # Valuation source validation (required)
    if "valuation_source" not in row_data or not row_data["valuation_source"]:
        raise ValidationError(
            "valuation_source is required", code="MISSING_VALUATION_SOURCE"
        )

    valuation_source = str(row_data["valuation_source"]).lower().strip()
    valid_sources = [choice[0] for choice in ValuationSource.choices]
    if valuation_source not in valid_sources:
        raise ValidationError(
            f"Invalid valuation_source: {valuation_source}. Valid: {valid_sources}",
            code="INVALID_VALUATION_SOURCE",
        )
    row_data["valuation_source"] = valuation_source

    # Accrued interest validation (optional)
    if "accrued_interest" in row_data and row_data["accrued_interest"] is not None:
        accrued_interest = row_data["accrued_interest"]
        if isinstance(accrued_interest, Money):
            accrued_amount = accrued_interest.amount
        elif isinstance(accrued_interest, Decimal):
            accrued_amount = accrued_interest
        else:
            raise ValidationError(
                "accrued_interest must be a Decimal or Money",
                code="INVALID_ACCRUED_INTEREST_TYPE",
            )

        if accrued_amount < 0:
            raise ValidationError(
                "accrued_interest must be non-negative", code="INVALID_ACCRUED_INTEREST"
            )

        # Ensure accrued_interest uses correct currency
        row_data["accrued_interest"] = Money(accrued_amount, currency)
    else:
        row_data["accrued_interest"] = None

    return row_data
