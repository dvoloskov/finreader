"""Pytest configuration for Sberbank brokerage report tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_html_path() -> Path:
    """Path to the anonymised sample HTML report."""
    return (
        Path(__file__).parent.parent.parent.parent
        / 'data'
        / 'sberbank_report_sample.html'
    )
