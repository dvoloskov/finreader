"""
Sberbank brokerage report parser (Layer 1, source-specific).

Public API:
    parse: Parse an HTML report file end-to-end.
    SberbankBrokerageReport: Top-level result container.

Per-table models and parsers are re-exported for downstream (Layer 2)
consumers that need to introspect a single table without re-parsing.
"""

from finreader.parsers.sberbank.brokerage_report._header import (
    ReportHeader,
    parse_header,
)
from finreader.parsers.sberbank.brokerage_report.report import (
    SberbankBrokerageReport,
    parse,
)
from finreader.parsers.sberbank.brokerage_report.tables.asset_valuation import (
    AssetValuation,
    AssetValuationRow,
    AssetValuationTotals,
    parse_asset_valuation,
)
from finreader.parsers.sberbank.brokerage_report.tables.cash_balances import (
    CashBalanceRow,
    CashBalanceTotal,
    CashBalances,
    parse_cash_balances,
)
from finreader.parsers.sberbank.brokerage_report.tables.cash_flow import (
    CashFlow,
    CashFlowRow,
    CashFlowTotal,
    parse_cash_flow,
)
from finreader.parsers.sberbank.brokerage_report.tables.cash_flow_summary import (
    CashFlowSummary,
    CashFlowSummaryRow,
    parse_cash_flow_summary,
)
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses import (
    IncomeExpenseRow,
    IncomeExpenses,
    parse_income_expenses,
)
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses_consolidated import (
    ConsolidatedIncomeExpenseRow,
    IncomeExpensesConsolidated,
    parse_income_expenses_consolidated,
)
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses_tax_summary import (
    IncomeExpensesTaxSummary,
    TaxSummaryRow,
    parse_income_expenses_tax_summary,
)
from finreader.parsers.sberbank.brokerage_report.tables.portfolio import (
    Portfolio,
    PortfolioRow,
    PortfolioTotal,
    parse_portfolio,
)
from finreader.parsers.sberbank.brokerage_report.tables.securities import (
    Securities,
    Security,
    parse_securities,
)
from finreader.parsers.sberbank.brokerage_report.tables.trades import (
    Trade,
    TradeDirection,
    TradeStatus,
    Trades,
    TradesTotal,
    parse_trades,
)

__all__ = [
    # Top-level
    'parse',
    'SberbankBrokerageReport',
    # Header
    'ReportHeader',
    'parse_header',
    # asset_valuation
    'AssetValuation',
    'AssetValuationRow',
    'AssetValuationTotals',
    'parse_asset_valuation',
    # cash_flow_summary
    'CashFlowSummary',
    'CashFlowSummaryRow',
    'parse_cash_flow_summary',
    # portfolio
    'Portfolio',
    'PortfolioRow',
    'PortfolioTotal',
    'parse_portfolio',
    # cash_balances
    'CashBalances',
    'CashBalanceRow',
    'CashBalanceTotal',
    'parse_cash_balances',
    # cash_flow
    'CashFlow',
    'CashFlowRow',
    'CashFlowTotal',
    'parse_cash_flow',
    # trades
    'Trades',
    'Trade',
    'TradesTotal',
    'TradeDirection',
    'TradeStatus',
    'parse_trades',
    # income_expenses (I)
    'IncomeExpenses',
    'IncomeExpenseRow',
    'parse_income_expenses',
    # income_expenses_consolidated (II)
    'IncomeExpensesConsolidated',
    'ConsolidatedIncomeExpenseRow',
    'parse_income_expenses_consolidated',
    # income_expenses_tax_summary (III)
    'IncomeExpensesTaxSummary',
    'TaxSummaryRow',
    'parse_income_expenses_tax_summary',
    # securities
    'Securities',
    'Security',
    'parse_securities',
]
