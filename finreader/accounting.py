"""Accounting policy over source-neutral facts, without destination account names."""

from finreader.models import (
    EventKind,
    Holding,
    Journal,
    JournalEntry,
    OpeningState,
    Posting,
    Role,
    Statement,
    ZERO,
)
from finreader.validation import exact_arithmetic, require


@exact_arithmetic
def build_journal(statement: Statement, opening: OpeningState) -> Journal:
    """Build an exactly balanced journal using explicit opening book cost basis."""
    require(
        opening.cash == statement.opening_cash, 'Opening cash differs from statement'
    )
    require(
        len({p.isin for p in statement.securities}) == len(statement.securities),
        'Duplicate statement security',
    )
    require(
        len({e.id for e in statement.events}) == len(statement.events),
        'Duplicate event identity',
    )
    require(
        [e.date for e in statement.events] == sorted(e.date for e in statement.events),
        'Events must be in chronological order',
    )
    holdings = {h.security: h for h in opening.holdings}
    require(len(holdings) == len(opening.holdings), 'Duplicate opening holding')
    require(
        set(holdings) == {p.isin for p in statement.securities},
        'Opening holdings must match statement securities',
    )
    for p in statement.securities:
        h = holdings[p.isin]
        require(
            all(v.is_finite() for v in (h.quantity, h.value, h.nkd)),
            'Non-finite opening holding',
        )
        require(
            h.quantity == p.opening_quantity and h.nkd == p.opening_nkd,
            f'Opening quantity/NKD mismatch: {p.isin}',
        )
        require(
            h.value >= 0 and (h.quantity == 0) == (h.value == 0),
            f'Missing or invalid opening basis: {p.isin}',
        )
    entries: list[JournalEntry] = []
    cash = opening.cash
    for e in statement.events:
        require(e.kind in set(EventKind), 'Unsupported economic event')
        require(
            e.amount.is_finite() and e.nkd.is_finite() and e.quantity.is_finite(),
            'Non-finite event amount',
        )
        require(
            statement.start <= e.date <= statement.end, 'Event outside statement period'
        )
        require(
            e.kind == EventKind.TRANSFER or e.amount > 0,
            'Event amount must be positive',
        )
        require(
            e.nkd >= 0 and (e.kind != EventKind.BUY or e.quantity > 0),
            'Invalid purchase quantity/NKD',
        )
        postings: list[Posting] = []
        cash_change = ZERO
        if e.kind == EventKind.TRANSFER:
            cash_change = e.amount
            postings.append(Posting(Role.EXTERNAL, -e.amount, -e.amount))
        elif e.kind in (EventKind.BROKER_FEE, EventKind.EXCHANGE_FEE):
            cash_change = -e.amount
            postings.append(Posting(Role.FEES, e.amount, e.amount))
        else:
            require(e.security in holdings, 'Event security missing from opening state')
            h = holdings[e.security]
            q, value, nkd = h.quantity, h.value, h.nkd
            if e.kind == EventKind.BUY:
                q += e.quantity
                value += e.amount
                nkd += e.nkd
                cash_change = -e.amount - e.nkd
                postings.append(
                    Posting(Role.BOND, e.quantity, e.amount, e.security, e.security)
                )
                if e.nkd:
                    postings.append(
                        Posting(Role.NKD, e.nkd, e.nkd, security=e.security)
                    )
            elif e.kind == EventKind.COUPON:
                require(q > 0, 'Coupon on an unheld security')
                nkd -= e.amount
                cash_change = e.amount
                postings.append(
                    Posting(Role.NKD, -e.amount, -e.amount, security=e.security)
                )
            elif e.kind == EventKind.PRINCIPAL:
                require(
                    q > 0 and ZERO < e.amount < value,
                    'Principal repayment requires sufficient recorded basis; full redemption unsupported',
                )
                value -= e.amount
                cash_change = e.amount
                postings.append(
                    Posting(Role.BOND, ZERO, -e.amount, e.security, e.security)
                )
            holdings[e.security] = Holding(e.security, q, value, nkd)
        postings.insert(0, Posting(Role.CASH, cash_change, cash_change))
        cash += cash_change
        require(sum((p.value for p in postings), ZERO) == 0, 'Unbalanced event')
        entries.append(
            JournalEntry(e.id, e.date, e.description, e.source_rows, tuple(postings))
        )
    for p in statement.securities:
        h = holdings[p.isin]
        require(h.quantity == p.closing_quantity, 'Journal quantity does not reconcile')
        adjustment = p.closing_nkd - h.nkd
        if adjustment:
            entries.append(
                JournalEntry(
                    f'{statement.id}:nkd:{p.isin}',
                    statement.end,
                    f'Period-end accrued interest: {p.name}',
                    (f'portfolio:{p.isin}',),
                    (
                        Posting(Role.NKD, adjustment, adjustment, security=p.isin),
                        Posting(Role.INCOME, -adjustment, -adjustment),
                    ),
                )
            )
        holdings[p.isin] = Holding(p.isin, h.quantity, h.value, p.closing_nkd)
    require(cash == statement.closing_cash, 'Journal cash does not reconcile')
    return Journal(
        statement,
        tuple(entries),
        OpeningState(cash, tuple(holdings[p.isin] for p in statement.securities)),
    )
