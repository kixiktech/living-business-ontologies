# research/lbo/schema.py
"""The schema: a small shared core, extended per industry only on demand.

The admission rule is the discipline that keeps it small: every type must be required by
an identified query, constraint or action, named in `required_by`. A type admitted for
completeness is maintenance with no claim on it, so the constructor refuses it.

Layers follow the paper: core, extension, meaning (definitions and evidence), control
(goals, decisions, policies, grants, actions, outcomes).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

LAYERS = ('core', 'extension', 'meaning', 'control')


class AdmissionError(ValueError):
    pass


@dataclass(frozen=True)
class EntityType:
    name: str
    layer: str
    fields: tuple[str, ...]
    required_by: tuple[str, ...]
    origin: str = 'core'


@dataclass(frozen=True)
class RelationType:
    name: str            # full predicate, e.g. order_line.fulfilled_from
    source: str          # entity type name
    target: str          # entity type name
    layer: str
    required_by: tuple[str, ...]
    origin: str = 'core'
    directional: bool = True


class Schema:
    def __init__(self, name: str):
        self.name = name
        self.entities: dict[str, EntityType] = {}
        self.relations: dict[str, RelationType] = {}

    def add_entity(self, et: EntityType) -> None:
        if not et.required_by:
            raise AdmissionError(f'{et.name}: no query, constraint or action requires it')
        if et.layer not in LAYERS:
            raise ValueError(f'{et.name}: layer {et.layer!r} not in {LAYERS}')
        self.entities[et.name] = et

    def add_relation(self, rt: RelationType) -> None:
        if not rt.required_by:
            raise AdmissionError(f'{rt.name}: no query, constraint or action requires it')
        if rt.layer not in LAYERS:
            raise ValueError(f'{rt.name}: layer {rt.layer!r} not in {LAYERS}')
        self.relations[rt.name] = rt

    def extend(self, name: str, entities: list[EntityType], relations: list[RelationType]) -> 'Schema':
        out = Schema(name)
        out.entities = dict(self.entities)
        out.relations = dict(self.relations)
        for et in entities:
            out.add_entity(replace(et, origin=name))
        for rt in relations:
            out.add_relation(replace(rt, origin=name))
        return out

    def predicates(self) -> set[str]:
        p = {f'{et.name}.{f}' for et in self.entities.values() for f in et.fields}
        return p | set(self.relations)

    def counts(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for et in self.entities.values():
            out.setdefault(et.origin, {'entities': 0, 'relations': 0})['entities'] += 1
        for rt in self.relations.values():
            out.setdefault(rt.origin, {'entities': 0, 'relations': 0})['relations'] += 1
        return out

    def validate(self, store, client: str) -> list[str]:
        known = self.predicates()
        problems: list[str] = []
        for a in store.query(client):
            if a.predicate not in known:
                problems.append(f'unknown predicate {a.predicate} on {a.subject} (assertion {a.id})')
                continue
            rt = self.relations.get(a.predicate)
            if rt is not None and not rt.name.startswith('identity.'):
                if not (isinstance(a.value, str) and a.value.split(':', 1)[0] == rt.target):
                    problems.append(f'{a.predicate} on {a.subject} points at {a.value!r}, '
                                    f'expected a {rt.target} (assertion {a.id})')
        return problems


def core() -> Schema:
    """The shared core: the exchange structure of any firm, plus the five ways a sale
    relates to a place. Each type names what requires it."""
    s = Schema('core')
    E, R = EntityType, RelationType
    for et in [
        E('party', 'core', ('name', 'email', 'phone'), ('customer_questions', 'identity')),
        E('person', 'core', ('name', 'role', 'hourly_cost', 'employed'), ('labour_questions', 'credited_to')),
        E('location', 'core', ('name', 'sqft'), ('sales_per_sqft', 'reorder')),
        E('product', 'core', ('sku', 'name', 'category', 'unit_cost', 'list_price'), ('margin', 'reorder')),
        E('supplier', 'core', ('name', 'terms'), ('margin_two_hops',)),
        E('order', 'core', ('placed_at', 'channel'), ('sales', 'customer_questions')),
        E('order_line', 'core', ('qty', 'unit_price', 'sold_at'), ('sales', 'margin')),
        E('invoice', 'core', ('issued_at', 'due_at', 'amount', 'currency', 'state', 'gross_profit',
                              'chased_on'), ('receivables', 'sales')),
        E('payment', 'core', ('paid_at', 'amount', 'method'), ('cash', 'receivables')),
        E('schedule', 'core', ('hours',), ('labour_questions',)),
        E('metric_definition', 'meaning', ('version', 'grain', 'basis'), ('every_measure',)),
        E('decision', 'control', ('question', 'taken_at', 'proposed', 'decided', 'kind', 'gap', 'conditions'),
          ('journal',)),
        E('action', 'control', ('status',), ('journal',)),
        E('grant', 'control', ('principal', 'action', 'scope', 'limits'), ('authority',)),
        E('message', 'control', ('audience', 'to', 'text', 'sent_on'), ('journal',)),
    ]:
        s.add_entity(et)
    for rt in [
        R('order.placed_by', 'order', 'party', 'core', ('customer_questions',)),
        R('order_line.of_order', 'order_line', 'order', 'core', ('sales',)),
        R('order_line.of_product', 'order_line', 'product', 'core', ('sales', 'margin')),
        R('order_line.rang_up_at', 'order_line', 'location', 'core', ('manager_bonus',)),
        R('order_line.fulfilled_from', 'order_line', 'location', 'core', ('sales_per_sqft',)),
        R('order_line.stock_drawn_from', 'order_line', 'location', 'core', ('reorder',)),
        R('order_line.credited_to', 'order_line', 'person', 'core', ('commission',)),
        R('order_line.counted_in', 'order_line', 'location', 'core', ('like_for_like',)),
        R('product.supplied_by', 'product', 'supplier', 'core', ('margin_two_hops',)),
        R('invoice.for_order', 'invoice', 'order', 'core', ('receivables',)),
        R('invoice.billed_to', 'invoice', 'party', 'core', ('receivables',)),
        R('payment.settles', 'payment', 'invoice', 'core', ('receivables',)),
        R('person.works_at', 'person', 'location', 'core', ('labour_questions',)),
        R('identity.source_id', 'party', 'party', 'meaning', ('identity',), directional=False),
        R('identity.same_as', 'party', 'party', 'meaning', ('identity',), directional=False),
        R('decision.about', 'decision', 'order', 'control', ('journal',)),
        R('action.of_decision', 'action', 'decision', 'control', ('journal',)),
    ]:
        s.add_relation(rt)
    return s


def shared_and_local(schemas: list[Schema]) -> dict[str, int]:
    ents = [set(s.entities) for s in schemas]
    rels = [set(s.relations) for s in schemas]
    shared_e = set.intersection(*ents) if ents else set()
    shared_r = set.intersection(*rels) if rels else set()
    return {
        'shared_entities': len(shared_e),
        'shared_relations': len(shared_r),
        'local_entities': sum(len(e - shared_e) for e in ents),
        'local_relations': sum(len(r - shared_r) for r in rels),
    }
