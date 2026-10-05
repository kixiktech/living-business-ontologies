# research/lbo/questions.py
"""The competency questions each firm's model has to be able to answer.

Their declared requirements are what `check_question` reports on, and the dependency
closure of a task is read off them. A question that nothing in the schema can supply is
the admission rule failing out loud, which is the point: the model is sized by the
questions, not the other way round.
"""
from __future__ import annotations

from datetime import date

from .closure import CompetencyQuestion as Q
from .closure import Requirement as R

Q2 = (date(2026, 4, 1), date(2026, 7, 1))
Q1 = (date(2026, 1, 1), date(2026, 4, 1))

RETAIL = [
    Q('margin_two_hops',
      'Why did gross margin fall in 2026Q2 against 2026Q1, and what would restore it?', (
          R('assertion', predicate='order_line.sold_at'),
          R('assertion', predicate='product.unit_cost', covers=(Q1[0], Q2[1])),
          R('assertion', predicate='product.supplied_by'),
          R('assertion', predicate='supplier.terms'),
          R('assertion', predicate='purchase_order.qty'),
          R('assertion', predicate='purchase_order.cut_for'),
          R('definition', definition='gross_profit'),
          R('definition', definition='quarter_units_ordered'))),
    Q('like_for_like',
      'Is the business growing on a like-for-like basis over the last twelve weeks?', (
          R('assertion', predicate='order_line.sold_at'),
          R('assertion', predicate='order_line.counted_in'),
          R('assertion', predicate='location.name'))),
    Q('price_change', 'May the data team change a list price?', (
        R('assertion', predicate='product.list_price'),
        R('grant', action='change_price'))),
    Q('reorder', 'May the data team place a top-up order with the supplier?', (
        R('assertion', predicate='purchase_order.qty'),
        R('grant', action='place_order'))),
]

FIELDSERVICE = [
    Q('channel_capacity',
      'Which lead channel should get more spend, given who can do the work?', (
          R('assertion', predicate='lead.via_channel'),
          R('assertion', predicate='job.from_lead'),
          R('assertion', predicate='job.in_service_line'),
          R('assertion', predicate='service_line.requires'),
          R('assertion', predicate='person.holds'),
          R('assertion', predicate='schedule.hours'),
          R('definition', definition='net_contribution'),
          R('definition', definition='tech_utilisation_pct'))),
    Q('certified_techs', 'Who is able to perform backflow jobs today?', (
        R('assertion', predicate='person.holds'),
        R('assertion', predicate='person.employed'),
        R('assertion', predicate='service_line.requires'))),
]

DISTRIBUTOR = [
    Q('credit_hold', 'Should a pending order for a customer over its credit limit ship?', (
        R('assertion', predicate='sales_order.status'),
        R('assertion', predicate='credit_terms.limit'),
        R('assertion', predicate='invoice.amount'),
        R('assertion', predicate='payment.settles'),
        R('grant', action='hold_order'))),
    Q('route_review', 'Does every route pay for itself?', (
        R('assertion', predicate='invoice.delivered_on_route'),
        R('assertion', predicate='invoice.gross_profit'),
        R('assertion', predicate='route.quarter_cost'),
        R('definition', definition='route_contribution'))),
    Q('reorder_lead_time', 'Which product will run out before its supplier can deliver?', (
        R('assertion', predicate='stock_position.qty'),
        R('assertion', predicate='stock_position.daily_demand'),
        R('assertion', predicate='supplier_lead_time.days'))),
]

BY_FIRM = {'retail': RETAIL, 'fieldservice': FIELDSERVICE, 'distributor': DISTRIBUTOR}


def for_firm(slug: str) -> dict[str, Q]:
    return {q.id: q for q in BY_FIRM.get(slug, [])}
