"""Tests for _header.py module."""

import pytest
from datetime import date

from bs4 import BeautifulSoup

from finreader.parsers.sberbank.brokerage_report._common import parse_soup
from finreader.parsers.sberbank.brokerage_report._header import (
    parse_header,
    ReportHeader,
)


def test_parse_header_from_sample() -> None:
    """Test parsing header from the sample HTML file."""
    soup = parse_soup('tests/data/sberbank_report_sample.html')
    header = parse_header(soup)

    # Check all fields match expected values from sample
    assert header.investor == 'Иванов Иван Иванович'
    assert header.contract_code == 'TEST001'
    assert str(header.start_date) == '2024-01-01'
    assert str(header.end_date) == '2024-01-31'
    assert str(header.creation_date) == '2024-02-01'
    assert str(header.contract_date) == '2023-01-01'


def test_parse_header_malformed_period() -> None:
    """Test that malformed period string raises descriptive ValueError."""
    html = """
    <html>
        <body>
            <h3>
                Отчет брокера
                <br>
                malformed period text
                <br>
            </h3>
            <p>
                Инвестор: Иванов Иван Иванович
                <br>Договор TEST001 от 01.01.2023</br>
            </p>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'lxml')
    with pytest.raises(ValueError, match='Cannot parse report header'):
        _ = parse_header(soup)


def test_parse_header_malformed_investor_contract() -> None:
    """Test that malformed investor/contract string raises descriptive ValueError."""
    html = """
    <html>
        <body>
            <h3>
                Отчет брокера
                <br>
                за период с 01.01.2024 по 31.01.2024, дата создания 01.02.2024
                <br>
            </h3>
            <p>
                malformed investor contract line
            </p>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'lxml')
    with pytest.raises(ValueError, match='Cannot parse report header'):
        _ = parse_header(soup)


def test_parse_header_missing_h3() -> None:
    """Test that missing h3 raises descriptive ValueError."""
    html = """
    <html>
        <body>
            <p>
                Инвестор: Иванов Иван Иванович
                <br>Договор TEST001 от 01.01.2023</br>
            </p>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'lxml')
    with pytest.raises(ValueError, match='Cannot parse report header'):
        _ = parse_header(soup)


def test_parse_header_missing_investor_p() -> None:
    """Test that missing investor p raises descriptive ValueError."""
    html = """
    <html>
        <body>
            <h3>
                Отчет брокера
                <br>
                за период с 01.01.2024 по 31.01.2024, дата создания 01.02.2024
                <br>
            </h3>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'lxml')
    with pytest.raises(ValueError, match='Cannot parse report header'):
        _ = parse_header(soup)


def test_report_header_frozen() -> None:
    """Test that ReportHeader is frozen (immutable)."""
    header = ReportHeader(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        creation_date=date(2024, 2, 1),
        investor='Иванов Иван Иванович',
        contract_code='TEST001',
        contract_date=date(2023, 1, 1),
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        setattr(header, 'investor', 'Another Name')


def test_parse_header_with_hyphenated_investor() -> None:
    """Test that investor names with hyphens are parsed correctly."""
    html = """
    <html>
        <body>
            <h3>
                Отчет брокера
                <br>
                за период с 01.01.2024 по 31.01.2024, дата создания 01.02.2024
                <br>
            </h3>
            <p>
                Инвестор: Иванов-Иванов Иван Иванович
                <br>Договор TEST002 от 01.01.2023</br>
            </p>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'lxml')
    header = parse_header(soup)
    assert header.investor == 'Иванов-Иванов Иван Иванович'
    assert header.contract_code == 'TEST002'
