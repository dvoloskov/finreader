"""
Top-level assembly of the Sberbank brokerage report.

This module defines the :class:`SberbankBrokerageReport` container that holds
the parsed header plus all 10 tables, and the :func:`parse` entry point that
wires the per-module parsers together.

The container is strictly source-faithful to the Sberbank report structure.
It intentionally does NOT model anything universal (no Layer-2
``BrokerageReport`` abstraction here).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report._header import (
    ReportHeader,
    parse_header,
)
from finreader.parsers.sberbank.brokerage_report.tables.asset_valuation import (
    AssetValuation,
    parse_asset_valuation,
)
from finreader.parsers.sberbank.brokerage_report.tables.cash_balances import (
    CashBalances,
    parse_cash_balances,
)
from finreader.parsers.sberbank.brokerage_report.tables.cash_flow import (
    CashFlow,
    parse_cash_flow,
)
from finreader.parsers.sberbank.brokerage_report.tables.cash_flow_summary import (
    CashFlowSummary,
    parse_cash_flow_summary,
)
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses import (
    IncomeExpenses,
    parse_income_expenses,
)
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses_consolidated import (
    IncomeExpensesConsolidated,
    parse_income_expenses_consolidated,
)
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses_tax_summary import (
    IncomeExpensesTaxSummary,
    parse_income_expenses_tax_summary,
)
from finreader.parsers.sberbank.brokerage_report.tables.portfolio import (
    Portfolio,
    parse_portfolio,
)
from finreader.parsers.sberbank.brokerage_report.tables.securities import (
    Securities,
    parse_securities,
)
from finreader.parsers.sberbank.brokerage_report.tables.trades import (
    Trades,
    parse_trades,
)

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


@dataclass(frozen=True)
class SberbankBrokerageReport:
    """
    Fully-assembled Sberbank brokerage report (Layer 1 source model).

    ``header`` is always populated (parsing raises if the header is absent).
    Every table field is ``Optional``: a missing table in the source HTML
    yields ``None`` rather than an empty stub, so callers can distinguish
    "table absent" from "table present but empty".

    Attributes:
        header: Report header (period, investor, contract).
        asset_valuation: ``Оценка активов`` table or ``None``.
        cash_flow_summary: ``Сводная информация по движению денежных средств``
            table or ``None``.
        portfolio: ``Портфель Ценных Бумаг`` table or ``None``.
        cash_balances: ``Денежные средства`` table or ``None``.
        cash_flow: ``Движение денежных средств за период`` table or ``None``.
        trades: ``Сделки купли/продажи ценных бумаг`` table or ``None``.
        income_expenses: ``I. ДОХОДЫ И РАСХОДЫ`` table or ``None``.
        income_expenses_consolidated: ``II. ДОХОДЫ И РАСХОДЫ`` table or
            ``None``.
        income_expenses_tax_summary: ``III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ``
            table or ``None``.
        securities: ``Справочник Ценных Бумаг`` table or ``None``.

    """

    header: ReportHeader
    asset_valuation: AssetValuation | None
    cash_flow_summary: CashFlowSummary | None
    portfolio: Portfolio | None
    cash_balances: CashBalances | None
    cash_flow: CashFlow | None
    trades: Trades | None
    income_expenses: IncomeExpenses | None
    income_expenses_consolidated: IncomeExpensesConsolidated | None
    income_expenses_tax_summary: IncomeExpensesTaxSummary | None
    securities: Securities | None


def parse(path: str | Path) -> SberbankBrokerageReport:
    """
    Parse a Sberbank brokerage HTML report end-to-end.

    Parses the file once into a :class:`~bs4.BeautifulSoup` tree and dispatches
    to the header parser plus each of the 10 table parsers. Each table parser
    independently returns ``None`` if its table is absent from the source, so a
    report missing one or more tables still parses successfully (only ``header``
    is mandatory).

    Args:
        path: Path to the Sberbank brokerage report HTML file.

    Returns:
        Fully-populated :class:`SberbankBrokerageReport`.

    Raises:
        ValueError: If the report header cannot be parsed (propagated from
            :func:`parse_header`).
        FileNotFoundError: If ``path`` does not exist.

    """
    soup: BeautifulSoup = parse_soup(path)
    return SberbankBrokerageReport(
        header=parse_header(soup),
        asset_valuation=parse_asset_valuation(soup),
        cash_flow_summary=parse_cash_flow_summary(soup),
        portfolio=parse_portfolio(soup),
        cash_balances=parse_cash_balances(soup),
        cash_flow=parse_cash_flow(soup),
        trades=parse_trades(soup),
        income_expenses=parse_income_expenses(soup),
        income_expenses_consolidated=parse_income_expenses_consolidated(soup),
        income_expenses_tax_summary=parse_income_expenses_tax_summary(soup),
        securities=parse_securities(soup),
    )
