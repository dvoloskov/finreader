"""
Tests for income_expenses_tax_summary (table III) parsing.

Covers:
- Sample-based parsing with tax_rate attachment from interleaved section rows.
- Missing table -> None.
- &nbsp; (U+00A0) thousands separator handling via inline fixture.
- Multiple tax brackets via inline fixture.
- Empty cells -> None.
- Negative tax_to_withhold preserved.
- Dataclass frozen.
"""

from pathlib import Path
from decimal import Decimal

from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses_tax_summary import (
    IncomeExpensesTaxSummary,
    TaxSummaryRow,
    parse_income_expenses_tax_summary,
)


def _soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, 'lxml')


# Minimal inline table template. The title <p> must precede the <table> for
# find_table_by_title's document-order pairing to match.
_TABLE_TEMPLATE = """
<html><body>
<p>{title}</p>
<table border="1" cellspacing="0" cellpadding="3">
{header}
{rn}
{body}
</table>
</body></html>
"""

_TITLE = 'III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ на 31.01.2024'
_HEADER = (
    '<tr class="table-header">'
    '<td class="c">Сумма дохода, руб.</td>'
    '<td class="c">Облагаемая сумма дохода, руб.</td>'
    '<td class="c">Сумма налога исчисленная, руб.</td>'
    '<td class="c">Сумма налога удержанная, руб.</td>'
    '<td class="c">Сумма налога к удержанию, руб.</td>'
    '<td class="c">Сумма документально подтвержденных расходов, руб.</td>'
    '<td class="c">Сумма стандартных налоговых вычетов, руб.</td>'
    '<td class="c">Сумма убытка, руб.</td>'
    '</tr>'
)
_RN = (
    '<tr class="rn">'
    '<td class="row-number">1</td><td class="row-number">2</td>'
    '<td class="row-number">3</td><td class="row-number">4</td>'
    '<td class="row-number">5</td><td class="row-number">6</td>'
    '<td class="row-number">7</td><td class="row-number">8</td>'
    '</tr>'
)


def _data_row(cells: list[str]) -> str:
    """Build a <tr> with 8 <td> cells from raw (already-embedded) cell strings."""
    tds = ''.join(f'<td>{c}</td>' for c in cells)
    return f'<tr>{tds}</tr>'


def _section_row(text: str, colspan: int = 8) -> str:
    return f'<tr><td class="fontBold" colspan="{colspan}">{text}</td></tr>'


def test_parse_income_expenses_tax_summary_sample(sample_html_path: Path) -> None:
    """Parse table III from the sample: rate attaches from section rows."""
    soup = parse_soup(sample_html_path)
    result = parse_income_expenses_tax_summary(soup)

    assert result is not None
    assert isinstance(result, IncomeExpensesTaxSummary)
    assert len(result.rows) == 2

    # Row 1: before any "Ставка X%" section -> tax_rate None.
    r0 = result.rows[0]
    assert isinstance(r0, TaxSummaryRow)
    assert r0.tax_rate is None
    assert r0.income_amount == Decimal('31186.51')
    assert r0.taxable_amount is None
    assert r0.calculated_tax is None
    assert r0.withheld_tax is None
    assert r0.tax_to_withhold is None
    assert r0.expenses == Decimal('23866.82')
    assert r0.deductions == Decimal('0.00')
    assert r0.loss == Decimal('0.00')

    # Row 2: after "Ставка 13%" section -> tax_rate 13.
    r1 = result.rows[1]
    assert r1.tax_rate == 13
    assert r1.income_amount is None
    assert r1.taxable_amount == Decimal('7319.69')
    assert r1.calculated_tax == Decimal('951.56')
    assert r1.withheld_tax is None  # "&nbsp;" only cell -> None
    assert r1.tax_to_withhold == Decimal('951.56')
    assert r1.expenses is None
    assert r1.deductions is None
    assert r1.loss is None


def test_parse_income_expenses_tax_summary_missing_table(
    sample_html_path: Path,
) -> None:
    """Return None when table III is absent."""
    soup = parse_soup(sample_html_path)
    for p in soup.find_all('p'):
        if p.get_text(strip=True).startswith('III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ'):
            nxt = p.find_next_sibling('table')
            if nxt is not None:
                nxt.decompose()

    assert parse_income_expenses_tax_summary(soup) is None


def test_nbsp_thousands_separator_handled() -> None:
    r"""
    A value using U+00A0 as thousands separator parses to the right Decimal.

    Real Sberbank reports use '&nbsp;' as a thousands separator in the tax
    tables (the anonymised sample does NOT). This inline fixture forces that
    path: '1\u00a0234.56' must become Decimal('1234.56').
    """
    body = _data_row(['1\xa0234.56', '', '', '', '', '', '', ''])
    html = _TABLE_TEMPLATE.format(title=_TITLE, header=_HEADER, rn=_RN, body=body)
    soup = _soup_from_html(html)
    result = parse_income_expenses_tax_summary(soup)

    assert result is not None
    assert len(result.rows) == 1
    assert result.rows[0].income_amount == Decimal('1234.56')


def test_multiple_tax_brackets_attach_correct_rate() -> None:
    """Multiple 'Ставка X%' sections each attach their rate to following rows."""
    body = (
        _data_row(['100.00', '', '', '', '', '', '', ''])  # rate None
        + _section_row('Ставка 13%')
        + _data_row(['', '200.00', '', '', '', '', '', ''])  # rate 13
        + _section_row('Ставка 15%')
        + _data_row(['', '300.00', '', '', '', '', '', ''])  # rate 15
    )
    html = _TABLE_TEMPLATE.format(title=_TITLE, header=_HEADER, rn=_RN, body=body)
    soup = _soup_from_html(html)
    result = parse_income_expenses_tax_summary(soup)

    assert result is not None
    assert len(result.rows) == 3
    assert result.rows[0].tax_rate is None
    assert result.rows[0].income_amount == Decimal('100.00')
    assert result.rows[1].tax_rate == 13
    assert result.rows[1].taxable_amount == Decimal('200.00')
    assert result.rows[2].tax_rate == 15
    assert result.rows[2].taxable_amount == Decimal('300.00')


def test_no_section_rows_all_rates_none() -> None:
    """With no 'Ставка X%' section rows, every data row has tax_rate None."""
    body = _data_row(['10.00', '', '', '', '', '5.00', '', ''])
    html = _TABLE_TEMPLATE.format(title=_TITLE, header=_HEADER, rn=_RN, body=body)
    soup = _soup_from_html(html)
    result = parse_income_expenses_tax_summary(soup)

    assert result is not None
    assert len(result.rows) == 1
    assert result.rows[0].tax_rate is None


def test_negative_tax_to_withhold_preserved() -> None:
    """'Сумма налога к удержанию ... со знаком минус' may be negative."""
    body = _data_row(['', '100.00', '13.00', '', '-13.00', '', '', ''])
    html = _TABLE_TEMPLATE.format(
        title=_TITLE,
        header=_HEADER,
        rn=_RN,
        body=_section_row('Ставка 13%') + body,
    )
    soup = _soup_from_html(html)
    result = parse_income_expenses_tax_summary(soup)

    assert result is not None
    assert len(result.rows) == 1
    assert result.rows[0].tax_rate == 13
    assert result.rows[0].tax_to_withhold == Decimal('-13.00')


def test_empty_cells_become_none() -> None:
    """Every empty cell maps to None rather than zero."""
    body = _data_row(['', '', '', '', '', '', '', ''])
    html = _TABLE_TEMPLATE.format(title=_TITLE, header=_HEADER, rn=_RN, body=body)
    soup = _soup_from_html(html)
    result = parse_income_expenses_tax_summary(soup)

    assert result is not None
    row = result.rows[0]
    assert row.income_amount is None
    assert row.taxable_amount is None
    assert row.calculated_tax is None
    assert row.withheld_tax is None
    assert row.tax_to_withhold is None
    assert row.expenses is None
    assert row.deductions is None
    assert row.loss is None
    assert row.tax_rate is None


def test_tax_summary_dataclasses_are_frozen() -> None:
    """Dataclasses must be frozen per plan conventions."""
    row = TaxSummaryRow(
        income_amount=None,
        taxable_amount=None,
        calculated_tax=None,
        withheld_tax=None,
        tax_to_withhold=None,
        expenses=None,
        deductions=None,
        loss=None,
        tax_rate=None,
    )
    try:
        setattr(row, 'income_amount', Decimal('1.00'))
    except (AttributeError, Exception):
        return
    raise AssertionError('TaxSummaryRow should be frozen')
