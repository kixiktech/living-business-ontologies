# research/lbo/tests/test_schema.py
from datetime import date
import pytest
from lbo import schema as sc
from lbo.store import Store


def test_admission_rule_refuses_a_type_nobody_asked_for():
    s = sc.Schema('t')
    with pytest.raises(sc.AdmissionError):
        s.add_entity(sc.EntityType('widget', 'core', ('name',), ()))
    with pytest.raises(sc.AdmissionError):
        s.add_relation(sc.RelationType('widget.owned_by', 'widget', 'party', 'core', ()))


def test_core_has_the_shared_vocabulary_and_five_sale_to_location_relations():
    c = sc.core()
    for name in ('party', 'location', 'product', 'order', 'order_line', 'invoice', 'payment',
                 'supplier', 'person'):
        assert name in c.entities, name
    five = {'order_line.rang_up_at', 'order_line.fulfilled_from', 'order_line.stock_drawn_from',
            'order_line.credited_to', 'order_line.counted_in'}
    assert five <= set(c.relations)
    assert all(c.relations[r].target == 'location' for r in five if r != 'order_line.credited_to')
    assert c.relations['order_line.credited_to'].target == 'person'


def test_extend_tags_origin_and_leaves_the_core_untouched():
    c = sc.core()
    n_core = len(c.entities)
    fs = c.extend('fieldservice',
                  [sc.EntityType('job', 'extension', ('scheduled_for',), ('capacity_question',)),
                   sc.EntityType('crew', 'extension', (), ('capacity_question',))],
                  [sc.RelationType('job.performed_by', 'job', 'crew', 'extension', ('capacity_question',))])
    assert len(c.entities) == n_core
    assert fs.entities['job'].origin == 'fieldservice'
    assert fs.entities['party'].origin == 'core'
    assert fs.counts()['fieldservice'] == {'entities': 2, 'relations': 1}
    assert fs.counts()['core']['entities'] == n_core


def test_predicates_include_fields_and_relations():
    c = sc.core()
    p = c.predicates()
    assert 'order_line.qty' in p and 'order_line.fulfilled_from' in p


def test_validate_flags_unknown_predicates_and_wrong_targets():
    c = sc.core()
    s = Store()
    s.assert_('c1', 'order_line:1', 'order_line.qty', 3, date(2026, 1, 1), evidence='pos')
    s.assert_('c1', 'order_line:1', 'order_line.flavour', 'x', date(2026, 1, 1), evidence='pos')
    s.assert_('c1', 'order_line:1', 'order_line.fulfilled_from', 'product:p1', date(2026, 1, 1), evidence='pos')
    problems = c.validate(s, 'c1')
    assert any('order_line.flavour' in p for p in problems)
    assert any('fulfilled_from' in p and 'product:p1' in p for p in problems)
    assert not any('order_line.qty' in p for p in problems)


def test_shared_and_local_counts_across_firms():
    c = sc.core()
    a = c.extend('retail', [sc.EntityType('stock_position', 'extension', ('qty',), ('reorder',))], [])
    b = c.extend('fieldservice', [sc.EntityType('job', 'extension', (), ('capacity',))], [])
    out = sc.shared_and_local([a, b])
    assert out['shared_entities'] == len(c.entities)
    assert out['local_entities'] == 2
    assert out['shared_relations'] == len(c.relations)
