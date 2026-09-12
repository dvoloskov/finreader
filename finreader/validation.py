"""Shared validation and exact arithmetic for financial boundaries."""

from collections.abc import Callable
from decimal import Decimal, DecimalException, Inexact, localcontext
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec('P')
T = TypeVar('T')


class ReconciliationError(ValueError):
    """Facts are incomplete, unsupported, ambiguous or inconsistent."""


def require(condition: bool, message: str) -> None:
    """Reject invalid facts without assertions or silent corrections."""
    if not condition:
        raise ReconciliationError(message)


def amount(value: Decimal | None, field: str) -> Decimal:
    """Read a required finite decimal without treating missing data as zero."""
    if value is None:
        raise ReconciliationError(f'{field}: missing amount')
    require(value.is_finite(), f'{field}: non-finite amount')
    return value


def exact_arithmetic(function: Callable[P, T]) -> Callable[P, T]:
    """Isolate arithmetic from caller context and reject inexact calculations."""

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        with localcontext() as context:
            context.prec = 80
            context.traps[Inexact] = True
            try:
                return function(*args, **kwargs)
            except DecimalException as error:
                raise ReconciliationError(
                    'Financial arithmetic cannot be represented exactly'
                ) from error

    return wrapped
