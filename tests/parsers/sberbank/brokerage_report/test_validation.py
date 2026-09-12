"""Public-parser regression tests for strict source validation."""

from pathlib import Path
from decimal import Decimal

from bs4 import BeautifulSoup
import pytest

from finreader.parsers.sberbank.brokerage_report import parse
from finreader.parsers.sberbank.brokerage_report.tables.cash_flow import parse_cash_flow
from finreader.parsers.sberbank.brokerage_report.tables.asset_valuation import (
    parse_asset_valuation,
)
from finreader.parsers.sberbank.brokerage_report.tables.income_expenses import (
    parse_income_expenses,
)


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', 'not-money'])
def test_invalid_cash_value_has_context(value: str) -> None:
    """Invalid amounts never disappear or leak Decimal implementation errors."""
    soup = BeautifulSoup(
        f'<p>Движение денежных средств за период</p><table><tr><td>01.01.2024</td><td>Рынок</td><td>Зачисление</td><td>RUB</td><td>{value}</td><td>0</td></tr></table>',
        'lxml',
    )
    with pytest.raises(ValueError, match=r'Движение.*row 1, field credit:'):
        _ = parse_cash_flow(soup)


@pytest.mark.parametrize('change', ['short', 'extra', 'date', 'missing', 'duplicate'])
def test_reject_malformed_report(tmp_path: Path, change: str) -> None:
    """The top-level API rejects malformed supported data."""
    soup = BeautifulSoup(
        Path('tests/data/sberbank_report_coherent.html').read_text(), 'lxml'
    )
    title = next(
        p for p in soup.find_all('p') if p.get_text().startswith('Движение денежных')
    )
    table = title.find_next('table')
    assert table is not None
    row = table.find('tr')
    assert row is not None
    cells = row.find_all('td')
    if change == 'short':
        cells[-1].decompose()
    elif change == 'extra':
        _ = row.append(soup.new_tag('td'))
    elif change == 'date':
        cells[0].string = '32.01.2024'
    elif change == 'missing':
        cells[2].string = ''
    else:
        import copy

        _ = table.insert_after(copy.copy(title), copy.copy(table))
    path = tmp_path / 'bad.html'
    _ = path.write_text(str(soup))
    with pytest.raises(ValueError, match='Движение денежных'):
        _ = parse(path)


def test_zero_asset_totals_are_preserved() -> None:
    """Zero is a value, not a missing total."""
    soup = BeautifulSoup(
        '<p>Оценка активов, руб.</p><table><tr class="summary-row"><td>Итого</td><td>0</td><td>0</td><td>0</td></tr></table>',
        'lxml',
    )
    result = parse_asset_valuation(soup)
    assert result is not None and result.total is not None
    assert result.total.start_total == Decimal(0)


def test_present_empty_tax_table_is_not_absent() -> None:
    """Preserve the report-level absent/empty distinction for table I too."""
    result = parse_income_expenses(
        BeautifulSoup('<p>I. ДОХОДЫ И РАСХОДЫ</p><table></table>', 'lxml')
    )
    assert result is not None and result.rows == []


def test_coherent_fixture_parses() -> None:
    """The independent fixture retains exact values and grouped trades."""
    result = parse('tests/data/sberbank_report_coherent.html')
    assert result.trades is not None and len(result.trades.rows) == 2
    assert result.cash_balances is not None
    assert result.cash_balances.rows[0].end == Decimal('14039')


@pytest.mark.parametrize(
    'title,width',
    [
        ('Оценка активов, руб.', 10),
        ('Сводная информация по движению денежных средств', 3),
        ('Портфель Ценных Бумаг', 18),
        ('Денежные средства', 9),
        ('Движение денежных средств', 6),
        ('Сделки купли/продажи', 16),
        ('I. ДОХОДЫ', 7),
        ('II. ДОХОДЫ', 9),
        ('III. ИТОГОВЫЙ', 8),
        ('Справочник Ценных Бумаг', 6),
    ],
)
@pytest.mark.parametrize('extra', [True, False])
def test_all_table_shapes_are_strict(
    tmp_path: Path, title: str, width: int, extra: bool
) -> None:
    """No public table parser silently discards a malformed source data row."""
    soup = BeautifulSoup(
        Path('tests/data/sberbank_report_sample.html').read_text(), 'lxml'
    )
    heading = next(
        p for p in soup.find_all('p') if p.get_text(strip=True).startswith(title)
    )
    table = heading.find_next('table')
    assert table is not None
    row = next(
        r
        for r in table.find_all('tr')
        if len(r.find_all('td')) == width
        and not r.get('class')
        and r.get('align') != 'center'
    )
    if extra:
        _ = row.append(soup.new_tag('td'))
    else:
        row.find_all('td')[-1].decompose()
    path = tmp_path / 'malformed.html'
    _ = path.write_text(str(soup))
    with pytest.raises(ValueError, match='expected .* cells'):
        _ = parse(path)
