"""Explicit source-contract and destination-account mappings."""

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import cast

from finreader.gnucash.book import Book
from finreader.models import Posting, Role, Statement
from finreader.validation import require


@dataclass(frozen=True)
class SecurityMapping:
    """Bind one source ISIN to existing bond and accrued-interest accounts."""

    isin: str
    bond: str
    nkd: str
    commodity: str


@dataclass(frozen=True)
class Mapping:
    """Private destination configuration, never part of the neutral financial core."""

    contract_code: str
    broker_root: str
    cash: str
    external: str
    fees: str
    income: str
    securities: tuple[SecurityMapping, ...]

    def account(self, posting: Posting) -> str:
        """Resolve a logical posting role to one explicitly configured account."""
        if posting.role in (Role.BOND, Role.NKD):
            matches = [s for s in self.securities if s.isin == posting.security]
            require(len(matches) == 1, 'Unmapped or ambiguous security')
            return matches[0].bond if posting.role == Role.BOND else matches[0].nkd
        return {
            Role.CASH: self.cash,
            Role.EXTERNAL: self.external,
            Role.FEES: self.fees,
            Role.INCOME: self.income,
        }[posting.role]


def _string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    require(
        isinstance(value, str) and bool(value),
        f'Mapping requires nonempty string: {key}',
    )
    return cast(str, value)


def load_mapping(path: str | Path) -> Mapping:
    """Read strict TOML and reject misspelled or incomplete configuration keys."""
    with Path(path).open('rb') as stream:
        data = cast(dict[str, object], tomllib.load(stream))
    keys = {
        'contract_code',
        'broker_root',
        'cash',
        'external',
        'fees',
        'income',
        'securities',
    }
    require(set(data) == keys, 'Mapping keys must be: ' + ', '.join(sorted(keys)))
    raw = data['securities']
    require(isinstance(raw, dict), 'Mapping securities must be a table keyed by ISIN')
    securities: list[SecurityMapping] = []
    for isin, fields in cast(dict[str, object], raw).items():
        require(isinstance(fields, dict), f'Invalid security mapping: {isin}')
        entry = cast(dict[str, object], fields)
        require(
            set(entry) == {'bond', 'nkd', 'commodity'},
            'Security mapping keys: bond, nkd, commodity',
        )
        securities.append(
            SecurityMapping(
                isin,
                _string(entry, 'bond'),
                _string(entry, 'nkd'),
                _string(entry, 'commodity'),
            )
        )
    return Mapping(
        _string(data, 'contract_code'),
        _string(data, 'broker_root'),
        _string(data, 'cash'),
        _string(data, 'external'),
        _string(data, 'fees'),
        _string(data, 'income'),
        tuple(securities),
    )


def validate_mapping(mapping: Mapping, book: Book, statement: Statement) -> None:
    """Check account identities, types, commodities and broker coverage before export."""
    import hashlib

    require(
        hashlib.sha256(('sberbank:' + mapping.contract_code).encode()).hexdigest()
        == statement.source_id,
        'Mapping contract does not match report',
    )
    accounts = {a.path: a for a in book.accounts}
    commodities = {c.key: c for c in book.commodities}
    require(
        mapping.broker_root in accounts and bool(mapping.broker_root),
        'Missing broker root',
    )
    require(
        {s.isin for s in mapping.securities} == {p.isin for p in statement.securities},
        'Mapping securities must exactly match statement portfolio',
    )
    require(
        len({s.isin for s in mapping.securities}) == len(mapping.securities),
        'Duplicate mapped security',
    )
    rules = [
        (mapping.cash, {'ASSET', 'BANK', 'CASH'}, 'CURRENCY::RUB'),
        (mapping.external, {'ASSET', 'BANK', 'CASH', 'LIABILITY'}, 'CURRENCY::RUB'),
        (mapping.fees, {'EXPENSE'}, 'CURRENCY::RUB'),
        (mapping.income, {'INCOME'}, 'CURRENCY::RUB'),
    ]
    for s in mapping.securities:
        require(
            s.commodity in commodities and not s.commodity.startswith('CURRENCY::'),
            'Unknown bond commodity',
        )
        require(
            commodities[s.commodity].cusip in ('', s.isin),
            'Commodity ISIN conflicts with mapping',
        )
        rules.extend(
            [
                (s.bond, {'STOCK', 'MUTUAL'}, s.commodity),
                (s.nkd, {'ASSET', 'BANK'}, 'CURRENCY::RUB'),
            ]
        )
    paths = [path for path, _, _ in rules]
    require(
        len(paths) == len(set(paths)),
        'Each mapped role/security must use a distinct account',
    )
    for path, types, commodity in rules:
        require(path in accounts, f'Mapped account not found: {path}')
        account = accounts[path]
        require(
            account.type in types and not account.placeholder,
            f'Invalid/placeholder account type: {path}',
        )
        require(
            account.commodity == commodity and account.fraction > 0,
            f'Account commodity/precision mismatch: {path}',
        )
    broker_paths = {
        a.path for a in book.accounts if a.path.startswith(mapping.broker_root + ':')
    }
    managed = {
        mapping.cash,
        *(s.bond for s in mapping.securities),
        *(s.nkd for s in mapping.securities),
    }
    require(managed <= broker_paths, 'Cash, bonds and NKD must belong to broker root')
    require(
        mapping.external not in broker_paths,
        'External funding account must be outside broker root',
    )
    unknown = broker_paths - managed
    from decimal import Decimal

    quantities = dict.fromkeys(unknown, Decimal(0))
    values = dict.fromkeys(unknown, Decimal(0))
    for transaction in book.transactions:
        if transaction.date >= statement.start:
            continue
        for split in transaction.splits:
            if split.account in unknown:
                quantities[split.account] += split.quantity
                values[split.account] += split.value
    require(
        not any(quantities.values()) and not any(values.values()),
        'Broker has unmapped opening balances; reconcile full portfolio first',
    )
