from collections.abc import Collection, Iterable
from enum import Enum, auto
import pathlib
import re
from typing import Any, Callable, NamedTuple
import pandas as pd
import numpy as np
from io import StringIO

from bs4 import BeautifulSoup, Tag


class Tables(Enum):
    asset_valuation = auto()
    cash_flow_summary = auto()
    portfolio = auto()
    cash_balances = auto()
    cash_flow = auto()
    trades = auto()
    income_expenses = auto()
    income_expenses_consolidated = auto()
    income_expenses_tax_summary = auto()
    securities = auto()

class SberbankBrokerageReport(NamedTuple):
    asset_valuation: tuple[str, pd.DataFrame] | None
    cash_flow_summary: tuple[str, pd.DataFrame] | None
    portfolio: tuple[str, pd.DataFrame] | None
    cash_balances: tuple[str, pd.DataFrame] | None
    cash_flow: tuple[str, pd.DataFrame] | None
    trades: tuple[str, pd.DataFrame] | None
    income_expenses: tuple[str, pd.DataFrame] | None
    income_expenses_consolidated: tuple[str, pd.DataFrame] | None
    income_expenses_tax_summary: tuple[str, pd.DataFrame] | None
    securities: tuple[str, pd.DataFrame] | None
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    creation_date: pd.Timestamp
    contract_code: str
    investor: str
    contract_date: pd.Timestamp


def parse(path: str | pathlib.Path):
    path = pathlib.Path(path)
    with open(path) as f:
        soup = BeautifulSoup(f, "lxml")
    title = soup.find('h3')
    assert title is not None
    title_text = title.get_text(strip=True, separator=' ')
    match = re.fullmatch(r'\s*Отчет брокера\s+за период с (?P<start_date>\d\d\.\d\d.\d{4}) по (?P<end_date>\d\d\.\d\d.\d{4}),\s' +
                         r'дата создания (?P<creation_date>\d\d\.\d\d.\d{4})', title_text)

    assert match is not None
    dates: dict[str, pd.Timestamp] = {
        'start_date': pd.to_datetime(match.group('start_date'), dayfirst=True),
        'end_date': pd.to_datetime(match.group('end_date'), dayfirst=True),
        'creation_date': pd.to_datetime(match.group('creation_date'), dayfirst=True)
    }

    contract = title.find_next_sibling('p')
    assert isinstance(contract, Tag)
    contract_text = contract.get_text(strip=True, separator=' ')
    print(contract_text)
    match = re.match(r'Инвестор: (?P<investor>([а-яёА-ЯЁ]+\s?)+) Договор ' +
                     r'(?P<contract>[A-Z0-9]+)\s+от\s+(?P<contract_date>\d\d\.\d\d.\d{4})', contract_text)
    assert match is not None
    contract_code = match.group('contract')
    investor = match.group('investor')
    dates['contract_date'] = pd.to_datetime(match.group('contract_date'))

    tables = soup.find_all(
        "table",
    )
    result: dict[str, tuple[str, pd.DataFrame]] = {}
    for table in tables:
        title, table_type = _identify_table(table)
        if table_type is None:
            continue
        assert title is not None
        df = _parse_table(table, table_type)
        if table_type in _POSTPROCESS_TABLE:
            df = _POSTPROCESS_TABLE[table_type](df)
        result[table_type.name] = (title, df)

    return SberbankBrokerageReport(
        asset_valuation=result['asset_valuation'],
        cash_flow_summary=result['cash_flow_summary'],
        portfolio=result['portfolio'],
        cash_balances=result['cash_balances'],
        cash_flow=result['cash_flow'],
        trades=result['trades'],
        income_expenses=result['income_expenses'],
        income_expenses_consolidated=result['income_expenses_consolidated'],
        income_expenses_tax_summary=result['income_expenses_tax_summary'],
        securities=result['securities'],
        start_date=dates['start_date'],
        end_date=dates['end_date'],
        creation_date=dates['creation_date'],
        contract_code=contract_code,
        investor=investor,
        contract_date=dates['contract_date']
    )


def _identify_table(table: Tag) -> tuple[str | None, Tables | None]:
    tables_map: dict[str, Tables] = {
        "Оценка активов, руб.": Tables.asset_valuation,
        "Сводная информация по движению денежных средств за период (основной рынок)": Tables.cash_flow_summary,
        "Портфель Ценных Бумаг": Tables.portfolio,
        'Денежные средства': Tables.cash_balances,
        'Движение денежных средств за период': Tables.cash_flow,
        'Сделки купли/продажи ценных бумаг': Tables.trades,
        'I. ДОХОДЫ И РАСХОДЫ': Tables.income_expenses,
        'II. ДОХОДЫ И РАСХОДЫ': Tables.income_expenses_consolidated,
        'III. ИТОГОВЫЙ ФИНАНСОВЫЙ РЕЗУЛЬТАТ': Tables.income_expenses_tax_summary,
        'Справочник Ценных Бумаг': Tables.securities
    }
    assert table.name == "table"
    p = table.previous_sibling
    if p is not None:
        p = p.previous_sibling
    if p is None or not isinstance(p, Tag) or p.name != 'p':
        return None, None

    title = p.get_text(strip=True)
    for key in tables_map.keys():
        if title.startswith(key):
            return (title, tables_map.get(key, None))
    return (title, None)


def _parse_table(table: Tag, type: Tables):
    data = pd.read_html(StringIO(str(table)), **_PARSE_PARAMETERS.get(type, {}))  # pyright: ignore[reportAny]
    assert len(data) == 1
    return data[0]


_PARSE_PARAMETERS: dict[Tables, dict[str, Any]] = {  # pyright: ignore[reportExplicitAny]
    Tables.asset_valuation: {"header": (0, 1), "skiprows": (2,), "index_col": 0},
    Tables.cash_flow_summary: {"header": 0, "skiprows": (1,), "index_col": 0},
    Tables.portfolio: {"header": (0, 1), "skiprows": (2,), "index_col": (0)},
    Tables.cash_balances: {"header": 0, "skiprows": (1,), 'index_col': 0},
    Tables.cash_flow: {'header': 0, 'skiprows': (1, )},
    Tables.trades: {'header': 0, 'skiprows': (1,)},
    Tables.income_expenses: {'header': 0, 'skiprows': (1,)},
    Tables.income_expenses_consolidated: {'header': 0, 'skiprows': (1,), 'index_col': 0},
    Tables.income_expenses_tax_summary: {'header': 0, 'skiprows': (1,),},
    Tables.securities: {'header': 0, 'skiprows': (1,)}
}

def _postprocess_table(table: pd.DataFrame,
                       index_to_drop: Collection[str] | None=None,
                       nan_to_drop: Iterable[int] | None=None,
                       drop_by_value: Iterable[tuple[str, str | int | float]] | None = None)  -> pd.DataFrame:
    res = table
    if index_to_drop is not None:

        for ind in index_to_drop:
            assert ind in table.index
        res = table.drop(index_to_drop)
    if nan_to_drop is not None:
        for i in nan_to_drop:
            assert res.iloc[i].isna().all()
        nan_to_drop_ind = [res.index[i] for i in nan_to_drop]
        res = res.drop(nan_to_drop_ind)
    if drop_by_value is not None:
        for column, val in drop_by_value:
            res = res.drop(res.index[res[column]==val])
    return res

def _postprocess_income_expenses_tax_summary(table: pd.DataFrame):
    tax_rate_column = 'Ставка, %'
    res = table.assign(**{tax_rate_column: np.nan})
    tax_rate = None
    ind_to_drop: list[int] = []
    for i, row in res.iterrows():
        assert isinstance(i, int)
        if i == 0:
            continue
        if tax_rate is None:
            match = re.fullmatch(r'Ставка (\d+)%', str(row.iloc[0]))  # pyright: ignore[reportAny]
            assert match is not None
            tax_rate = int(match.group(1))
            ind_to_drop.append(i)
            continue
        res.loc[i, tax_rate_column] = tax_rate
        tax_rate = None
    res = res.drop(ind_to_drop)
    return res


_POSTPROCESS_TABLE: dict[Tables, Callable[[pd.DataFrame,], pd.DataFrame]] = {
    Tables.portfolio: lambda table: _postprocess_table(
        table,
        index_to_drop =[
            'Площадка: Фондовый рынок',
            'Итого по площадке Фондовый рынок, RUB',
            'Итого по Основному рынку, RUB'
        ],
        nan_to_drop=[-1,]
    ),
    Tables.cash_balances: lambda table: _postprocess_table(
        table,
        index_to_drop=[
            'Итого по площадке Основной рынок',
            'Итого в рублевой оценке по курсам Банка России'
        ],
    ),
    Tables.cash_flow: lambda table: _postprocess_table(
        table,
        drop_by_value=[('Дата', 'Итого, RUB')]

    ),
    Tables.trades: lambda table: _postprocess_table(
        table,
        drop_by_value=[('Дата заключения', 'Итого, RUB'),
                       ('Дата заключения', 'Площадка: Фондовый рынок')]
    ),
    Tables.income_expenses_tax_summary: _postprocess_income_expenses_tax_summary
}
