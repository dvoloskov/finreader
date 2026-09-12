"""Strict interpretation and reconciliation of supported Sberbank operations."""

from collections import defaultdict
from dataclasses import asdict, replace
from datetime import date, time
from decimal import Decimal, Inexact, ROUND_HALF_UP, localcontext
from enum import Enum
import hashlib
import json
import re
from typing import cast

from finreader.models import (
    EventKind,
    FinancialEvent,
    SecurityPosition,
    Statement,
    ZERO,
)
from finreader.parsers.sberbank.brokerage_report import SberbankBrokerageReport
from finreader.parsers.sberbank.brokerage_report.tables.trades import (
    TradeDirection,
    TradeStatus,
)


from finreader.validation import ReconciliationError, amount, exact_arithmetic, require


def _json_value(value: object) -> str:
    if isinstance(value, Decimal):
        text = format(value, 'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Enum):
        return cast(str, value.value)
    raise TypeError(f'Cannot serialize {type(value).__name__}')


@exact_arithmetic
def normalize_sberbank(report: SberbankBrokerageReport) -> Statement:
    """Validate source totals and translate only the explicitly supported operations."""
    header = report.header
    require(header.start_date <= header.end_date, 'Invalid statement period')
    balances, flows, trades = report.cash_balances, report.cash_flow, report.trades
    portfolio, securities = report.portfolio, report.securities
    if any(t is None for t in (balances, flows, trades, portfolio, securities)):
        raise ReconciliationError(
            'Required tables: cash_balances, cash_flow, trades, portfolio, securities'
        )
    # Narrow once after the explicit public-boundary check.
    assert balances is not None and flows is not None and trades is not None
    assert portfolio is not None and securities is not None
    rub_balances = [row for row in balances.rows if row.currency == 'RUB']
    require(len(rub_balances) == 1, 'Exactly one RUB cash balance/venue is supported')
    for row in balances.rows:
        if row.currency != 'RUB':
            require(
                all(
                    v == 0
                    for v in (
                        row.start,
                        row.change,
                        row.end,
                        row.planned_in,
                        row.planned_out,
                        row.planned_outgoing,
                    )
                ),
                'Nonzero foreign-currency balances are unsupported',
            )
    cash = rub_balances[0]
    require(cash.rate_end in (None, 1), 'RUB cash exchange rate must be one or omitted')
    require(
        not cash.planned_in and not cash.planned_out,
        'Pending cash settlements are unsupported',
    )
    require(
        cash.planned_outgoing in (None, cash.end), 'Pending cash balance is unsupported'
    )
    require(
        cash.start + amount(cash.change, 'cash change') == cash.end,
        'Cash start/change/end mismatch',
    )
    for total in balances.totals:
        require(
            (
                total.start,
                total.change,
                total.end,
                total.planned_in,
                total.planned_out,
                total.planned_outgoing,
            )
            == (
                cash.start,
                cash.change,
                cash.end,
                cash.planned_in,
                cash.planned_out,
                cash.planned_outgoing,
            ),
            'Cash balance total mismatch',
        )
    require(flows.total is not None, 'Missing cash-flow total')
    assert flows.total is not None
    credits = sum((r.credit or ZERO for r in flows.rows), ZERO)
    debits = sum((r.debit or ZERO for r in flows.rows), ZERO)
    require(
        credits == flows.total.credit and debits == flows.total.debit,
        'Cash-flow printed totals do not match rows',
    )
    require(
        cash.start + credits - debits == cash.end,
        'Cash movements do not reconcile closing cash',
    )
    by_isin = {s.isin: s for s in securities.rows}
    by_code = {s.code: s for s in securities.rows}
    require(
        len(by_isin) == len(by_code) == len(securities.rows),
        'Duplicate security identifiers',
    )
    positions: list[SecurityPosition] = []
    for p in portfolio.rows:
        require(
            p.isin in by_isin, f'Portfolio security not in reference table: {p.isin}'
        )
        security = by_isin[p.isin]
        require(security.kind == 'Облигация', f'Unsupported security kind: {p.isin}')
        require(p.name == security.name, f'Security name mismatch: {p.isin}')
        require(p.price_currency == 'RUB', 'Only RUB bonds are supported')
        require(
            p.start_quantity is not None and p.end_quantity is not None,
            f'Missing quantities: {p.isin}',
        )
        require(
            not p.planned_receipts and not p.planned_charges,
            'Pending security settlements are unsupported',
        )
        require(
            p.planned_outgoing in (None, p.end_quantity),
            'Pending security balance is unsupported',
        )
        opening_q, closing_q = (
            Decimal(p.start_quantity or 0),
            Decimal(p.end_quantity or 0),
        )
        require(
            opening_q >= 0 and closing_q >= opening_q,
            'Sales/redemptions/short positions are unsupported',
        )
        require(
            p.change_quantity == closing_q - opening_q,
            f'Quantity change mismatch: {p.isin}',
        )
        opening_nkd = (
            ZERO
            if opening_q == 0 and p.start_nkd is None
            else amount(p.start_nkd, 'opening NKD')
        )
        closing_nkd = (
            ZERO
            if closing_q == 0 and p.end_nkd is None
            else amount(p.end_nkd, 'closing NKD')
        )
        require(opening_nkd >= 0 and closing_nkd >= 0, 'Negative reported NKD')
        opening_nominal = p.start_nominal or ZERO
        closing_nominal = p.end_nominal or ZERO
        require(closing_q == 0 or closing_nominal > 0, 'Full redemption is unsupported')
        positions.append(
            SecurityPosition(
                p.isin,
                security.code,
                security.name,
                opening_q,
                closing_q,
                opening_nkd,
                closing_nkd,
                opening_nominal,
                closing_nominal,
            )
        )
    require(
        len({p.isin for p in positions}) == len(positions),
        'Duplicate portfolio security/venue',
    )
    positions_by_code = {p.code: p for p in positions}
    fingerprint = hashlib.sha256(
        json.dumps(
            asdict(report), default=_json_value, sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()
    source_id = hashlib.sha256(
        ('sberbank:' + header.contract_code).encode()
    ).hexdigest()
    events: list[FinancialEvent] = []
    # A cash-flow settlement aggregates all trades sharing trade date, settlement
    # date, venue and currency. Never match on amount alone.
    groups: dict[tuple[date, date, str, str], list[int]] = defaultdict(list)
    trade_numbers: set[str] = set()
    totals = [ZERO, ZERO, ZERO, ZERO]
    for i, t in enumerate(trades.rows, 1):
        require(
            t.direction == TradeDirection.BUY and t.status == TradeStatus.I,
            f'trades:{i}: only completed purchases supported',
        )
        require(t.currency == 'RUB', 'Only RUB trades supported')
        require(
            t.security_code in positions_by_code,
            f'trades:{i}: missing portfolio security',
        )
        p = positions_by_code[t.security_code]
        require(t.security_name == p.name, f'trades:{i}: security name mismatch')
        require(
            t.trade_number not in trade_numbers and bool(t.trade_number),
            'Duplicate/missing trade number',
        )
        trade_numbers.add(t.trade_number)
        if t.trade_date is None or t.settlement_date is None:
            raise ReconciliationError(f'trades:{i}: missing dates')
        require(
            header.start_date <= t.settlement_date <= header.end_date
            and t.trade_date <= t.settlement_date,
            'Trade settlement outside period or before trade date',
        )
        require(
            t.quantity is not None and t.quantity > 0,
            'Purchase quantity must be positive',
        )
        principal, nkd, broker, exchange = [
            amount(v, f'trades:{i}:{f}')
            for v, f in zip(
                (t.amount, t.nkd, t.broker_fee, t.exchange_fee),
                ('amount', 'nkd', 'broker_fee', 'exchange_fee'),
                strict=True,
            )
        ]
        require(
            principal > 0 and min(nkd, broker, exchange) >= 0,
            'Invalid purchase amounts',
        )
        price = amount(t.price, 'quoted bond price')
        require(price > 0, 'Quoted bond price must be positive')
        event = FinancialEvent(
            f'{fingerprint}:trade:{t.trade_number}',
            EventKind.BUY,
            t.settlement_date,
            principal,
            (f'trades:{i}',),
            f'Purchase {p.name}',
            p.isin,
            Decimal(t.quantity or 0),
            nkd,
            t.trade_date,
            t.trade_number,
            price,
            broker,
            exchange,
        )
        groups[(t.trade_date, t.settlement_date, t.venue, t.currency)].append(
            len(events)
        )
        events.append(event)
        totals = [
            a + b
            for a, b in zip(totals, (principal, nkd, broker, exchange), strict=True)
        ]
    require(trades.total is not None or not trades.rows, 'Missing trade totals')
    if trades.total is not None:
        require(
            totals
            == [
                trades.total.amount,
                trades.total.nkd,
                trades.total.broker_fee,
                trades.total.exchange_fee,
            ],
            'Trade totals do not match rows',
        )
    matched: set[tuple[tuple[date, date, str, str], str]] = set()
    summary = {
        name: ZERO
        for name in (
            'Входящий остаток',
            'Исходящий остаток',
            'Пополнение счета',
            'Вывод средств',
            'Сальдо расчетов по сделкам',
            'Корпоративные действия',
            'Комиссия брокера',
            'Комиссия биржи',
        )
    }
    for i, row in enumerate(flows.rows, 1):
        require(
            header.start_date <= row.date <= header.end_date,
            f'cash_flow:{i}: date outside period',
        )
        require(row.currency == 'RUB', 'Only RUB cash movements supported')
        credit, debit = row.credit or ZERO, row.debit or ZERO
        require(
            credit >= 0 and debit >= 0 and (credit > 0) != (debit > 0),
            f'cash_flow:{i}: exactly one positive credit/debit required',
        )
        signed = credit - debit
        desc = row.description
        match = re.fullmatch(
            r'(Сделка|Комиссия Биржи|Комиссия Брокера оборотная) от (\d{2}\.\d{2}\.\d{4})',
            desc,
        )
        kind: EventKind
        security_id = ''
        if match:
            from datetime import datetime

            trade_date = datetime.strptime(match[2], '%d.%m.%Y').date()
            key = (trade_date, row.date, row.venue, row.currency)
            require(key in groups, f'cash_flow:{i}: unmatched settlement/fee group')
            group = [events[j] for j in groups[key]]
            category = match[1]
            require(
                (key, category) not in matched,
                f'cash_flow:{i}: duplicate settlement/fee group',
            )
            matched.add((key, category))
            if category == 'Сделка':
                expected = sum((t.amount + t.nkd for t in group), ZERO)
                require(
                    signed == -expected, f'cash_flow:{i}: settlement amount mismatch'
                )
                summary['Сальдо расчетов по сделкам'] += signed
                for j in groups[key]:
                    events[j] = replace(
                        events[j],
                        source_rows=(*events[j].source_rows, f'cash_flow:{i}'),
                    )
                continue
            kind = (
                EventKind.EXCHANGE_FEE
                if category == 'Комиссия Биржи'
                else EventKind.BROKER_FEE
            )
            expected = sum(
                (
                    t.exchange_fee if kind == EventKind.EXCHANGE_FEE else t.broker_fee
                    for t in group
                ),
                ZERO,
            )
            require(signed == -expected, f'cash_flow:{i}: commission amount mismatch')
            summary[
                'Комиссия биржи'
                if kind == EventKind.EXCHANGE_FEE
                else 'Комиссия брокера'
            ] += signed
        elif desc in ('Зачисление д/с', 'Списание д/с'):
            require(
                (desc == 'Зачисление д/с') == (signed > 0),
                'Transfer direction mismatch',
            )
            kind = EventKind.TRANSFER
            summary['Пополнение счета' if signed > 0 else 'Вывод средств'] += signed
        else:
            coupon = re.fullmatch(r'Зачисление д/с \(купон \d+ по (.+)\)', desc)
            principal = re.fullmatch(r'Зачисление д/с \(амортизация (.+)\)', desc)
            require(
                coupon is not None or principal is not None,
                f'cash_flow:{i}: unsupported description',
            )
            name = coupon or principal
            assert name is not None
            candidates = [p for p in positions if p.name == name[1]]
            require(
                len(candidates) == 1, f'cash_flow:{i}: ambiguous or unknown security'
            )
            require(signed > 0, 'Coupon/principal repayment must be a credit')
            security_id = candidates[0].isin
            kind = EventKind.COUPON if coupon else EventKind.PRINCIPAL
            summary['Корпоративные действия'] += signed
        events.append(
            FinancialEvent(
                f'{fingerprint}:cash:{i}',
                kind,
                row.date,
                signed if kind == EventKind.TRANSFER else abs(signed),
                (f'cash_flow:{i}',),
                desc,
                security_id,
            )
        )
    for key, indices in groups.items():
        for label, total in [
            ('Сделка', sum((events[j].amount + events[j].nkd for j in indices), ZERO)),
            ('Комиссия Биржи', sum((events[j].exchange_fee for j in indices), ZERO)),
            (
                'Комиссия Брокера оборотная',
                sum((events[j].broker_fee for j in indices), ZERO),
            ),
        ]:
            require(
                total == 0 or (key, label) in matched,
                f'Missing cash-flow reconciliation: {label} {key[0]}',
            )
    for p in positions:
        purchased = sum(
            (
                e.quantity
                for e in events
                if e.kind == EventKind.BUY and e.security == p.isin
            ),
            ZERO,
        )
        require(
            p.opening_quantity + purchased == p.closing_quantity,
            f'Closing quantity mismatch: {p.isin}',
        )
    # Nominal principal is distinct from book basis. Walk backwards so that a
    # newly acquired bond with no opening position still has a known face value.
    for p in positions:
        quantity, nominal = p.closing_quantity, p.closing_nominal
        security_events = sorted(
            (e for e in events if e.security == p.isin),
            key=lambda e: (e.date, e.kind != EventKind.BUY, e.id),
        )
        purchase_days = {e.date for e in security_events if e.kind == EventKind.BUY}
        for event in reversed(security_events):
            if event.kind == EventKind.PRINCIPAL:
                require(
                    event.date not in purchase_days,
                    'Same-day purchase and principal repayment require intraday ordering; unsupported',
                )
                require(quantity > 0, 'Principal repayment on an unheld security')
                nominal += event.amount / quantity
            elif event.kind == EventKind.BUY:
                require(event.quoted_price is not None, 'Missing purchase price')
                assert event.quoted_price is not None
                # Broker principal is rounded to kopecks from the percentage
                # quote. This is an explicit invoice check, not ledger rounding.
                with localcontext() as rounding:
                    rounding.traps[Inexact] = False
                    expected_principal = (
                        event.quantity * nominal * event.quoted_price / 100
                    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                require(
                    event.amount == expected_principal,
                    'Purchase principal differs from nominal and quoted percentage price',
                )
                quantity -= event.quantity
        require(
            quantity == p.opening_quantity,
            'Opening nominal reconciliation quantity mismatch',
        )
        require(
            p.opening_nominal == nominal
            or (p.opening_quantity == 0 and p.opening_nominal == 0),
            'Principal repayments do not reconcile opening/closing nominal',
        )
    for total in portfolio.totals:
        require(
            total.start_nkd == sum((p.opening_nkd for p in positions), ZERO)
            and total.end_nkd == sum((p.closing_nkd for p in positions), ZERO),
            'Portfolio NKD totals mismatch',
        )
    if report.cash_flow_summary is not None:
        summary['Входящий остаток'] = cash.start
        summary['Исходящий остаток'] = cash.end
        seen: set[str] = set()
        for row in report.cash_flow_summary.rows:
            require(
                row.currency == 'RUB' and row.description in summary,
                'Unsupported cash-flow summary category/currency',
            )
            require(row.description not in seen, 'Duplicate cash-flow summary category')
            seen.add(row.description)
            require(
                row.amount == summary[row.description],
                f'Cash-flow summary mismatch: {row.description}',
            )
        require(
            all(value == 0 or name in seen for name, value in summary.items()),
            'Incomplete cash-flow summary',
        )
    return Statement(
        fingerprint,
        source_id,
        header.start_date,
        header.end_date,
        cash.start,
        cash.end,
        tuple(positions),
        tuple(sorted(events, key=lambda e: (e.date, e.kind != EventKind.BUY, e.id))),
    )
