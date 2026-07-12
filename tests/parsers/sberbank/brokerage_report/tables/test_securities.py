"""Test suite for securities table parser."""

from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report.tables.securities import (
    parse_securities,
)


def test_parse_securities() -> None:
    """Test parsing securities table with 7 rows."""
    html = """
    <p>
        <br>Справочник Ценных Бумаг</br>
    </p>
    <table border="1" cellspacing="0" cellpadding="3">
        <tr class="table-header">
            <td class="c">Наименование</td>
            <td class="c">Код</td>
            <td class="c">ISIN ценной бумаги</td>
            <td class="c">Эмитент</td>
            <td class="c">Вид, Категория, Тип, иная информация</td>
            <td class="c">Выпуск, Транш, Серия</td>
        </tr>
        <tr class="rn">
            <td class="row-number">1</td>
            <td class="row-number">2</td>
            <td class="row-number">3</td>
            <td class="row-number">4</td>
            <td class="row-number">5</td>
            <td class="row-number">6</td>
        </tr>
        <tr>
            <td class="l">Облигация А</td>
            <td class="c">RU000TEST001</td>
            <td class="c">RU000TEST001</td>
            <td class="c">Эмитент А</td>
            <td class="c">Облигация</td>
            <td class="c">Выпуск А </td>
        </tr>
        <tr>
            <td class="l">Облигация Б</td>
            <td class="c">RU000TEST002</td>
            <td class="c">RU000TEST002</td>
            <td class="c">Эмитент Б</td>
            <td class="c">Облигация</td>
            <td class="c">Выпуск Б </td>
        </tr>
        <tr>
            <td class="l">Облигация В</td>
            <td class="c">RU000TEST003</td>
            <td class="c">RU000TEST003</td>
            <td class="c">Эмитент В</td>
            <td class="c">Облигация</td>
            <td class="c">Выпуск В </td>
        </tr>
        <tr>
            <td class="l">Облигация Г</td>
            <td class="c">RU000TEST004</td>
            <td class="c">RU000TEST004</td>
            <td class="c">Эмитент Г</td>
            <td class="c">Облигация</td>
            <td class="c">Выпуск Г </td>
        </tr>
        <tr>
            <td class="l">Облигация Д</td>
            <td class="c">RU000TEST005</td>
            <td class="c">RU000TEST005</td>
            <td class="c">Эмитент Д</td>
            <td class="c">Облигация</td>
            <td class="c">Выпуск Д </td>
        </tr>
        <tr>
            <td class="l">Облигация Е</td>
            <td class="c">RU000TEST006</td>
            <td class="c">RU000TEST006</td>
            <td class="c">Эмитент Е</td>
            <td class="c">Облигация</td>
            <td class="c">Выпуск Е </td>
        </tr>
        <tr>
            <td class="l">Облигация Ж</td>
            <td class="c">RU000TEST007</td>
            <td class="c">RU000TEST007</td>
            <td class="c">Эмитент Ж</td>
            <td class="c">Облигация</td>
            <td class="c">Выпуск Ж </td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = parse_securities(soup)

    assert result is not None
    assert len(result.rows) == 7

    # Check first row
    assert result.rows[0].name == 'Облигация А'
    assert result.rows[0].code == 'RU000TEST001'
    assert result.rows[0].isin == 'RU000TEST001'
    assert result.rows[0].issuer == 'Эмитент А'
    assert result.rows[0].kind == 'Облигация'
    assert result.rows[0].issue == 'Выпуск А'
    # Critical: trailing whitespace must be stripped
    assert not result.rows[0].issue.endswith(' ')

    # Check last row
    assert result.rows[6].name == 'Облигация Ж'
    assert result.rows[6].code == 'RU000TEST007'
    assert result.rows[6].isin == 'RU000TEST007'
    assert result.rows[6].issuer == 'Эмитент Ж'
    assert result.rows[6].kind == 'Облигация'
    assert result.rows[6].issue == 'Выпуск Ж'
    assert not result.rows[6].issue.endswith(' ')

    # Verify all rows have stripped issue fields
    for row in result.rows:
        assert not row.issue.endswith(' '), (
            f"Issue field has trailing whitespace: '{row.issue}'"
        )
        assert not row.code.endswith(' '), (
            f"Code field has trailing whitespace: '{row.code}'"
        )
        assert not row.isin.endswith(' '), (
            f"ISIN field has trailing whitespace: '{row.isin}'"
        )


def test_parse_securities_missing_table() -> None:
    """Test that None is returned when securities table is absent."""
    html = '<html><body>No securities table here</body></html>'
    soup = BeautifulSoup(html, 'html.parser')
    result = parse_securities(soup)
    assert result is None
