"""
Orchestration logic for daily close ETL processing.

This module provides the orchestration entrypoint to run all required market data ETL
pipelines for the daily "close-of-business" cycle. Here, you can coordinate execution
of FX, security prices, and other market data pipeline tasks for a given as-of date.
Extend this file whenever new daily ETL pipelines or dependencies are needed.
"""
from __future__ import annotations
from datetime import date
from apps.etl.pipelines.market_data_fx_daily import run_fx_daily
from apps.etl.pipelines.prices_daily import run_prices_daily


def run_daily_close(as_of: date) -> list[dict]:
    """
    Runs the daily close orchestration for market data pipelines for a given as-of date.

    This function coordinates the execution of multiple ETL pipelines required for daily "close-of-business"
    processing, ensuring that all key market data sources (such as FX rates and security prices) are refreshed
    for the specified date. Additional market data pipelines (e.g., curves_daily, fund_navs_daily/weekly, 
    corporate_actions) should be added as needed in the future.

    Args:
        as_of (date): The as-of date for which all market data pipelines should be run.

    Returns:
        list[dict]: A list of result dictionaries from each invoked pipeline containing status, metadata, etc.
    """
    results = []
    results.append(run_fx_daily(as_of=as_of))
    results.append(run_prices_daily(as_of=as_of))
    return results