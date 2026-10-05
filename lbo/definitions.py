# research/lbo/definitions.py
"""Definitions are part of the model, and they are code.

A metric definition specifies grain, units, basis, inclusions and its own effective
version, and it carries the function that computes it. A Measure it produces names its
window, its base and the assertions it read, so a number never travels without the four
anchors and a reader can always ask what it was computed from.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable

from .store import Store


@dataclass(frozen=True)
class Measure:
    name: str
    value: Any
    window: tuple[date, date]          # [start, end)
    base: str
    as_of: datetime | None
    definition_version: str
    inputs: tuple[int, ...]
    notes: tuple[str, ...] = ()


ComputeFn = Callable[[Store, str, tuple[date, date], datetime | None, dict | None],
                     tuple[Any, tuple[int, ...], tuple[str, ...]]]


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    version: str
    grain: str
    units: str
    basis: str
    inclusions: tuple[str, ...]
    effective_from: date
    compute: ComputeFn


class Registry:
    def __init__(self):
        self._defs: dict[str, list[MetricDefinition]] = {}

    def register(self, d: MetricDefinition) -> None:
        self._defs.setdefault(d.name, []).append(d)
        self._defs[d.name].sort(key=lambda x: x.effective_from)

    def get(self, name: str, as_of: date) -> MetricDefinition:
        live = [d for d in self._defs.get(name, []) if d.effective_from <= as_of]
        if not live:
            raise KeyError(f'no version of {name} effective on {as_of}')
        return live[-1]

    def compute(self, name: str, store: Store, client: str, window: tuple[date, date],
                known_at: datetime | None = None, as_of: date | None = None,
                filters: dict | None = None) -> Measure:
        d = self.get(name, as_of or window[1])
        value, inputs, notes = d.compute(store, client, window, known_at, filters)
        return Measure(name=name, value=value, window=window, base=d.basis, as_of=known_at,
                       definition_version=d.version, inputs=tuple(inputs), notes=tuple(notes))


def reconcile(a: Measure, b: Measure) -> list[str]:
    diffs = []
    if a.window != b.window:
        diffs.append(f'window: {a.window} vs {b.window}')
    if a.base != b.base:
        diffs.append(f'base: {a.base!r} vs {b.base!r}')
    if a.definition_version != b.definition_version:
        diffs.append(f'definition version: {a.definition_version} vs {b.definition_version}')
    if a.value != b.value:
        diffs.append(f'value: {a.value} vs {b.value}')
    return diffs


# ---- the core definitions ------------------------------------------------------------

def matches(store: Store, client: str, subject: str, filters: dict | None,
            known_at: datetime | None = None) -> bool:
    """Does this subject carry every predicate and value the caller asked for?

    A measure is often wanted for one product, one route or one service line, and the
    alternative to saying so here is reading every line out through a paged tool and
    adding them up by hand, which is not the same capability.
    """
    if not filters:
        return True
    for pred, want in filters.items():
        if not any(r.value == want for r in store.query(client, subject, pred, known_at=known_at)):
            return False
    return True


def _lines_in_window(store: Store, client: str, window, known_at, filters=None):
    """Every order line whose sold_at falls in [start, end), with its product, qty, price.

    Every lookup here is filtered by `known_at`, the same as the cost lookup in
    `_cost_of_goods`: a sale itself has a knowledge time too (when it was entered), and a
    replay only sees what had actually been recorded by that point. No special-casing.
    """
    out = []
    for a in store.query(client, predicate='order_line.sold_at', known_at=known_at):
        day = date.fromisoformat(a.value)
        if not (window[0] <= day < window[1]):
            continue
        ln = a.subject
        if not matches(store, client, ln, filters, known_at):
            continue
        prod = store.query(client, ln, 'order_line.of_product', known_at=known_at)
        qty = store.query(client, ln, 'order_line.qty', known_at=known_at)
        price = store.query(client, ln, 'order_line.unit_price', known_at=known_at)
        if not (prod and qty and price):
            continue
        out.append((ln, day, prod[0], qty[0], price[0]))
    return out


def _gross_sales(store, client, window, known_at, filters=None):
    total, inputs = 0.0, []
    for ln, day, prod, qty, price in _lines_in_window(store, client, window, known_at, filters):
        total += qty.value * price.value
        inputs += [qty.id, price.id]
    return round(total, 2), tuple(inputs), ()


def _cost_of_goods(store, client, window, known_at, filters=None):
    """quantity times the unit cost valid on the sale date, read under known_at."""
    total, inputs, notes = 0.0, [], []
    for ln, day, prod, qty, price in _lines_in_window(store, client, window, known_at, filters):
        cost = store.query(client, prod.value, 'product.unit_cost', as_of=day, known_at=known_at)
        if not cost:
            notes.append(f'{ln}: no unit cost for {prod.value} valid on {day}; excluded from cost')
            continue
        total += qty.value * cost[0].value
        inputs += [qty.id, cost[0].id, prod.id]
    return round(total, 2), tuple(inputs), tuple(notes)


def _gross_profit(store, client, window, known_at, filters=None):
    gs, gsi, _ = _gross_sales(store, client, window, known_at, filters)
    cg, cgi, notes = _cost_of_goods(store, client, window, known_at, filters)
    return round(gs - cg, 2), gsi + cgi, notes


def _gross_margin_pct(store, client, window, known_at, filters=None):
    gs, gsi, _ = _gross_sales(store, client, window, known_at, filters)
    gp, gpi, notes = _gross_profit(store, client, window, known_at, filters)
    if gs == 0:
        return 0.0, gsi, notes + ('gross sales are zero; margin undefined, reported as 0.0',)
    return round(gp / gs * 100, 2), gpi, notes


def core_registry() -> Registry:
    r = Registry()
    r.register(MetricDefinition('gross_sales', 'v1', 'order line', 'usd',
                                'quantity times unit price, before returns and tax',
                                ('all order lines with a sale date in the window',), date(2000, 1, 1), _gross_sales))
    r.register(MetricDefinition('cost_of_goods', 'v1', 'order line', 'usd',
                                'quantity times the unit cost valid on the sale date',
                                ('lines whose product has a cost valid on the sale date',), date(2000, 1, 1), _cost_of_goods))
    r.register(MetricDefinition('gross_profit', 'v1', 'order line', 'usd',
                                'gross sales less cost of goods at the unit cost valid on the sale date',
                                ('as gross_sales and cost_of_goods',), date(2000, 1, 1), _gross_profit))
    r.register(MetricDefinition('gross_margin_pct', 'v1', 'window', 'percent',
                                'gross profit as a percentage of gross sales, two decimals',
                                ('as gross_profit',), date(2000, 1, 1), _gross_margin_pct))
    return r
