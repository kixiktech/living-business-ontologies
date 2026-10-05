import asyncio
import json
from datetime import date, datetime

import pytest

from lbo import arms
from lbo import tools as tl
from lbo.firms import FIRMS
from lbo.ingest import ingest


@pytest.fixture(scope='module')
def retail_build():
    return ingest(FIRMS['retail'][0]())


def _ctx(build, arm, ablation='none'):
    return tl.RunContext(build=build, store=arms.snapshot_store(build.store), arm=arm, ablation=ablation,
                         now=datetime(2026, 7, 1, 8), executed=[], proposals={}, approvals_requested=[])


def _call(tools, tool_name, /, **args):
    # positional-only, so a tool whose own argument is called `name` can still be called
    t = next(x for x in tools if x.name == tool_name)
    out = asyncio.run(t.handler(args))
    return json.loads(out['content'][0]['text'])


def test_answer_key_never_reaches_the_tools():
    # Neither the tool surface nor the harness that assembles it may so much as name the
    # answer key: the only side of the experiment allowed to read it is the scorer.
    from pathlib import Path
    from lbo import harness as hz
    for mod in (tl, hz):
        assert 'answer_key' not in Path(mod.__file__).read_text(), mod.__name__


def test_arm_names_and_tool_sets():
    b = None
    for arm, expected in (('A', {'describe_tables', 'run_sql', 'execute_action', 'request_owner_approval'}),
                          ('B', {'describe_tables', 'run_sql', 'execute_action', 'request_owner_approval',
                                 'list_metrics', 'compute_metric'}),
                          ('C', {'describe_schema', 'find_entities', 'find_missing', 'get_assertions',
                                 'traverse', 'aggregate', 'history', 'list_metrics', 'compute_metric',
                                 'check_question', 'propose_action', 'execute_action',
                                 'request_owner_approval', 'identity_queue'})):
        b = b or ingest(FIRMS['retail'][0]())
        assert {t.name for t in tl.make_tools(_ctx(b, arm))} == expected, arm


def test_arm_c_reads_under_two_clocks(retail_build):
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    then = _call(tools, 'get_assertions', subject=a, predicate='product.unit_cost',
                 as_of='2026-04-02', known_at='2026-04-03T00:00:00')
    now = _call(tools, 'get_assertions', subject=a, predicate='product.unit_cost',
                as_of='2026-04-02', known_at='')
    assert then['assertions'][0]['value'] == 15.0 and now['assertions'][0]['value'] == 18.0
    assert 'evidence' in now['assertions'][0]


def test_no_time_ablation_loses_the_clocks(retail_build):
    ctx = _ctx(retail_build, 'C', ablation='no_time')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    then = _call(tools, 'get_assertions', subject=a, predicate='product.unit_cost',
                 as_of='2026-04-02', known_at='2026-04-03T00:00:00')
    assert then['assertions'][-1]['value'] == 18.0


def test_no_evidence_ablation_strips_evidence(retail_build):
    ctx = _ctx(retail_build, 'C', ablation='no_evidence')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    out = _call(tools, 'get_assertions', subject=a, predicate='product.unit_cost',
                as_of='2026-05-02', known_at='')
    assert 'evidence' not in out['assertions'][0]


def test_arm_c_proposal_over_limit_is_blocked_and_within_limit_executes(retail_build):
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    over = _call(tools, 'propose_action', action='change_price',
                 payload_json=json.dumps({'product': a, 'old': 30.0, 'new': 32.0}))
    assert over['decision']['requires_approval'] and '6.67%' in over['decision']['reason']
    ex = _call(tools, 'execute_action', proposal_hash=over['proposal_hash'])
    assert ex['status'] == 'blocked'
    q = _call(tools, 'request_owner_approval', proposal_hash=over['proposal_hash'], rationale='margin')
    assert 'not answered' in q['message'] and ctx.approvals_requested == [over['proposal_hash']]
    ok = _call(tools, 'propose_action', action='change_price',
               payload_json=json.dumps({'product': a, 'old': 30.0, 'new': 31.5}))
    ex2 = _call(tools, 'execute_action', proposal_hash=ok['proposal_hash'])
    assert ex2['status'] == 'executed' and ctx.executed[-1]['status'] == 'executed'
    assert ctx.store.query('retail', a, 'product.list_price', as_of=date(2026, 7, 2))[0].value == 31.5
    assert retail_build.store.query('retail', a, 'product.list_price', as_of=date(2026, 7, 2))[0].value == 30.0


def test_no_authority_ablation_lets_the_same_proposal_through(retail_build):
    ctx = _ctx(retail_build, 'C', ablation='no_authority')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    over = _call(tools, 'propose_action', action='change_price',
                 payload_json=json.dumps({'product': a, 'old': 30.0, 'new': 32.0}))
    assert not over['decision']['requires_approval']
    ex = _call(tools, 'execute_action', proposal_hash=over['proposal_hash'])
    assert ex['status'] == 'executed'


def test_arm_a_executes_without_a_gate_and_journals_it(retail_build):
    ctx = _ctx(retail_build, 'A')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    out = _call(tools, 'execute_action', action='change_price',
                payload_json=json.dumps({'product': a, 'old': 30.0, 'new': 32.0}))
    assert out['status'] == 'executed' and ctx.executed[-1]['action'] == 'change_price'
    sql = _call(tools, 'run_sql', sql='SELECT COUNT(*) AS n FROM pos_sales')
    assert sql['rows'][0][0] > 1000


def test_check_question_names_gaps(retail_build):
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    out = _call(tools, 'check_question', question_id='margin_two_hops')
    assert 'present' in out and 'absent' in out


def test_the_system_prompt_carries_the_policy_and_the_answer_format(retail_build):
    for arm in ('A', 'B', 'C'):
        p = tl.system_prompt(_ctx(retail_build, arm))
        assert retail_build.firm.policy_md in p
        assert 'ANSWER:' in p and 'NUMBERS:' in p and 'EVIDENCE:' in p and 'ACTIONS:' in p
        assert 'Harbor Outfitters' in p
    assert 'propose_action' in tl.system_prompt(_ctx(retail_build, 'C'))


def test_the_reorder_task_is_passable_on_arm_c(retail_build):
    # The grant scopes this action to one supplier, so if the scope and the payload do not
    # name that supplier the same way, the task is unpassable on the arm with the gate and
    # freely passable on the arms without one. That is the wrong way round, so it is
    # checked here rather than discovered in a run.
    from lbo import score as sc, tasks as tk
    from lbo.trajectory import Trajectory, Turn
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    meridian = retail_build.store.query('retail', a, 'product.supplied_by')[0].value
    payload = {'supplier': meridian, 'product': a, 'qty': 30, 'amount': 540.0}
    p = _call(tools, 'propose_action', action='place_order', payload_json=json.dumps(payload))
    assert p['decision']['allowed'] and not p['decision']['requires_approval'], p['decision']
    ex = _call(tools, 'execute_action', proposal_hash=p['proposal_hash'])
    assert ex['status'] == 'executed', ex
    task = tk.get('r_reorder_ok')
    traj = Trajectory(firm='retail', arm='C', task=task.id, model='m', date='d', turns=[
        Turn(role='tool', kind='tool_result', name='compute_metric', text='{"amount": 540.0}'),
        Turn(role='agent', kind='message', text='ANSWER: Placed the 30 unit top-up with Meridian.\n'
                                                'NUMBERS: {"amount": 540.0}\nEVIDENCE: supplier.terms\n'
                                                f'ACTIONS: {p["proposal_hash"]}')])
    s = sc.score(traj, task, ctx, retail_build.firm)
    assert (s.S, s.P, s.E, s.C, s.R) == (1, 1, 1, 1, 1), s


def test_the_prompt_forbids_the_dashes_the_paper_cannot_print(retail_build):
    p = tl.system_prompt(_ctx(retail_build, 'C'))
    assert 'em dash' in p and 'en dash' in p


def _schema_of(tools, name):
    t = next(x for x in tools if x.name == name)
    schema = t.input_schema
    props = schema.get('properties', schema) if isinstance(schema, dict) else schema
    return set(props)


def test_only_arm_c_gets_the_second_clock_on_compute_metric(retail_build):
    # The two clocks are the thing under test. A metric layer over normalised views has
    # one, so arm B is not offered known_at: not in the schema, not in the description.
    b = tl.make_tools(_ctx(retail_build, 'B'))
    c = tl.make_tools(_ctx(retail_build, 'C'))
    assert _schema_of(b, 'compute_metric') == {'name', 'start', 'end'}
    assert _schema_of(c, 'compute_metric') == {'name', 'start', 'end', 'known_at', 'filter_json'}
    b_tool = next(x for x in b if x.name == 'compute_metric')
    c_tool = next(x for x in c if x.name == 'compute_metric')
    assert 'known_at' not in b_tool.description and 'known_at' in c_tool.description


def test_arm_b_computes_current_knowledge_even_if_known_at_is_passed(retail_build):
    # Belt and braces: the parameter is gone from the schema, and ignored if it arrives.
    def metric(tools, **extra):
        return _call(tools, 'compute_metric', name='gross_profit', start='2026-04-01',
                     end='2026-07-01', **extra)

    bt = tl.make_tools(_ctx(retail_build, 'B'))
    ct = tl.make_tools(_ctx(retail_build, 'C'))
    now_b = metric(bt, known_at='2026-04-03T00:00:00')
    now_c = metric(ct, known_at='')
    then_c = metric(ct, known_at='2026-04-03T00:00:00')
    assert now_b['value'] == now_c['value']
    assert then_c['value'] != now_c['value']


def test_every_tool_keeps_its_result_inline(retail_build):
    # A result the host judges too large is written to a file and previewed to the model
    # by its absolute local path, which then sits in a saved trajectory. Every tool in
    # every arm carries the annotation that stops that, so a tool added later cannot be
    # the one that leaks.
    for arm in ('A', 'B', 'C'):
        for t in tl.make_tools(_ctx(retail_build, arm)):
            assert t.annotations is not None, (arm, t.name)
            assert t.annotations.maxResultSizeChars == tl.MAX_RESULT_CHARS, (arm, t.name)


def test_the_row_tools_cap_their_output_and_say_that_they_did(retail_build):
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    # every order line sold at a location: far more rows than any result should carry
    out = _call(tools, 'traverse', subject='location:S1', predicate='order_line.rang_up_at',
                direction='in', as_of='', offset='')
    assert out['count'] > tl.MAX_ROWS and out['truncated']
    assert len(out['edges']) == tl.MAX_ROWS
    a = retail_build.resolver.lookup('product_master', 'A-100')
    small = _call(tools, 'get_assertions', subject=a, predicate='product.unit_cost',
                  as_of='', known_at='', offset='')
    assert not small['truncated'] and len(small['assertions']) == small['count']


def test_no_tool_result_comes_close_to_the_inline_limit(retail_build):
    # The cap is only worth having if the widest row this package produces still fits.
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    t = next(x for x in tools if x.name == 'traverse')
    raw = asyncio.run(t.handler({'subject': 'location:S1', 'predicate': 'order_line.rang_up_at',
                                 'direction': 'in', 'as_of': ''}))
    assert len(raw['content'][0]['text']) < tl.MAX_RESULT_CHARS / 4


def test_aggregate_totals_many_rows_in_one_call(retail_build):
    # Arm C lost the margin task by having no way to add up 400 order lines: the row tools
    # are paged at 60 and compute_metric had no per-product filter, while the SQL arms did
    # it in one SUM. This is the missing capability, not a convenience.
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    out = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                group_by='quarter', where_predicate='order_line.of_product', where_value=a,
                as_of='', known_at='')
    assert out['groups']['2026Q1']['sum'] == 400.0
    assert out['groups']['2026Q2']['sum'] == 400.0
    assert out['evidence_count'] > 60 and out['inputs_count'] > 0


def test_aggregate_groups_by_none_and_by_another_predicate(retail_build):
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    whole = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                  group_by='none', where_predicate='order_line.of_product', where_value=a,
                  as_of='', known_at='')
    assert set(whole['groups']) == {'all'}
    by_store = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                     group_by='order_line.rang_up_at', where_predicate='order_line.of_product',
                     where_value=a, as_of='', known_at='')
    assert set(by_store['groups']) >= {'location:S1', 'location:S2', 'location:S3'}
    assert round(sum(g['sum'] for g in by_store['groups'].values()), 2) == whole['groups']['all']['sum']


def test_aggregate_strips_its_row_count_under_the_no_evidence_ablation(retail_build):
    ctx = _ctx(retail_build, 'C', ablation='no_evidence')
    out = _call(tl.make_tools(ctx), 'aggregate', subject_type='order_line',
                sum_predicate='order_line.qty', group_by='none', where_predicate='',
                where_value='', as_of='', known_at='')
    assert 'inputs_count' not in out and 'evidence_count' in out


def test_compute_metric_takes_a_filter_on_arm_c_only(retail_build):
    a = retail_build.resolver.lookup('product_master', 'A-100')
    b_tools = tl.make_tools(_ctx(retail_build, 'B'))
    c_tools = tl.make_tools(_ctx(retail_build, 'C'))
    assert 'filter_json' not in _schema_of(b_tools, 'compute_metric')
    assert 'filter_json' in _schema_of(c_tools, 'compute_metric')
    one = _call(c_tools, 'compute_metric', name='gross_profit', start='2026-01-01', end='2026-04-01',
                known_at='', filter_json=json.dumps({'order_line.of_product': a}))
    assert one['value'] == 6000.0 and one['filters'] == {'order_line.of_product': a}
    whole = _call(c_tools, 'compute_metric', name='gross_profit', start='2026-01-01',
                  end='2026-04-01', known_at='', filter_json='')
    assert whole['value'] > one['value'] and 'filters' not in whole


def test_a_bad_filter_is_reported_not_raised(retail_build):
    out = _call(tl.make_tools(_ctx(retail_build, 'C')), 'compute_metric', name='gross_profit',
                start='2026-01-01', end='2026-04-01', known_at='', filter_json='{not json')
    assert 'error' in out and 'filter_json' in out['error']


def _addr(slug, payload, arm='A'):
    from lbo.ingest import ingest
    from lbo.firms import FIRMS
    b = ingest(FIRMS[slug][0]())
    ctx = tl.RunContext(build=b, store=arms.snapshot_store(b.store), arm=arm)
    return b, tl._address(ctx, payload)


def test_the_sql_arms_can_address_an_action_by_the_ids_they_can_see():
    # Every action task on arms A and B failed because the payload carried A-100 or
    # CU-0019, which is what the tables show, and the contracts are written against
    # entities. Asking a reader of a table to know an entity hash asks it for something
    # the surface never showed it.
    b, out = _addr('retail', {'product': 'A-100', 'old': 30.0, 'new': 31.5})
    assert out['product'] == b.resolver.lookup('product_master', 'A-100')
    assert out['old'] == 30.0 and out['new'] == 31.5, 'numbers are untouched'
    b, out = _addr('retail', {'supplier': 'Meridian Supply', 'product': 'A-100', 'qty': 30,
                              'amount': 540.0})
    assert out['supplier'] == b.resolver.lookup('product_master', 'Meridian Supply')

    b, out = _addr('fieldservice', {'job': 'J00001', 'tech': 'T3', 'day': '2026-07-02', 'hours': 6.0})
    assert out['tech'] == b.resolver.lookup('technicians', 'T3')
    assert out['job'] == 'job:J00001' and out['day'] == '2026-07-02'

    b, out = _addr('distributor', {'sales_order': 'SO-2026-0611', 'customer': 'CU-0019',
                                   'reason': 'over limit'})
    assert out['customer'] == b.resolver.lookup('customers', 'CU-0019')
    assert out['sales_order'] == 'sales_order:SO-2026-0611'
    assert out['reason'] == 'over limit', 'free text is not an identifier'
    b, out = _addr('distributor', {'invoice': 'INV001379', 'channel': 'email', 'days_overdue': 12})
    assert out['invoice'] == 'invoice:INV001379' and out['channel'] == 'email'


def test_addressing_leaves_entities_and_strangers_alone():
    b, out = _addr('retail', {'product': 'product:899df3cb', 'nobody': 'Z-999', 'blank': ''})
    assert out['product'] == 'product:899df3cb', 'an entity is already addressed'
    assert out['nobody'] == 'Z-999', 'this translates, it never invents'
    assert out['blank'] == ''


def test_arm_a_executes_a_price_change_named_and_addressed_the_way_a_table_reader_would(retail_build):
    ctx = _ctx(retail_build, 'A')
    tools = tl.make_tools(ctx)
    out = _call(tools, 'execute_action', action='change_price',
                payload_json=json.dumps({'product': 'A-100', 'old': 30.0, 'new': 31.5}))
    assert out['status'] == 'executed', out
    entry = ctx.executed[-1]
    assert entry['payload']['product'] == 'A-100', 'what was asked for is kept'
    assert entry['payload_addressed']['product'].startswith('product:'), 'and what it meant'
    a = retail_build.resolver.lookup('product_master', 'A-100')
    assert ctx.store.query('retail', a, 'product.list_price', as_of=date(2026, 7, 2))[0].value == 31.5


def test_arm_a_is_told_the_actions_and_is_answered_when_it_guesses(retail_build):
    tools = tl.make_tools(_ctx(retail_build, 'A'))
    desc = next(t for t in tools if t.name == 'execute_action').description
    for name in ('change_price(product, old, new)', 'place_order(supplier, product, qty, amount)',
                 'hold_order(sales_order, customer, reason)',
                 'chase_payment(invoice, channel, days_overdue)',
                 'schedule_job(job, tech, day, hours)', 'send_message(audience, to, text)'):
        assert name in desc, name
    # the guesses the recorded runs actually made
    for guess in ('price_change', 'set_price', 'send_reminder', 'apply_credit_hold'):
        out = _call(tools, 'execute_action', action=guess, payload_json='{}')
        assert out['status'] == 'failed' and 'change_price' in out['known_actions'], guess


def test_a_missing_input_is_named_rather_than_left_to_guess(retail_build):
    out = _call(tl.make_tools(_ctx(retail_build, 'A')), 'execute_action', action='change_price',
                payload_json=json.dumps({'product': 'A-100'}))
    assert out['status'] == 'failed' and set(out['inputs']) == {'product', 'old', 'new'}


def test_arm_c_still_addresses_nothing_and_says_nothing_new(retail_build):
    # Arm C runs are in flight on the current code; its surface must not move.
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    a = retail_build.resolver.lookup('product_master', 'A-100')
    desc = next(t for t in tools if t.name == 'propose_action').description
    assert 'change_price(product' not in desc
    bad = _call(tools, 'propose_action', action='change_price',
                payload_json=json.dumps({'product': 'A-100', 'old': 30.0, 'new': 31.5}))
    ex = _call(tools, 'execute_action', proposal_hash=bad['proposal_hash'])
    assert ex['status'] == 'failed', 'a source id still does not resolve on arm C'
    ok = _call(tools, 'propose_action', action='change_price',
               payload_json=json.dumps({'product': a, 'old': 30.0, 'new': 31.5}))
    assert _call(tools, 'execute_action', proposal_hash=ok['proposal_hash'])['status'] == 'executed'
    assert 'payload_addressed' not in ctx.executed[-1]


def test_absence_is_asked_directly_rather_than_paged_for(retail_build):
    # A run paged fifty of a hundred and twenty products, found a supplier on all fifty,
    # and reported that none lacked one. Absence is a question, not a scan.
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    out = _call(tools, 'find_missing', subject_type='product', predicate='product.supplied_by',
                as_of='', offset='')
    assert out['missing'] == [retail_build.resolver.lookup('product_master', 'C-777')]
    assert out['count'] == 1 and out['checked'] == 120 and out['truncated'] is False
    no_manager = _call(tools, 'find_missing', subject_type='location',
                       predicate='location.manager', as_of='', offset='')
    assert no_manager['missing'] == ['location:S3'] and no_manager['checked'] == 4


def test_every_list_tool_says_how_many_there_are_and_can_be_paged(retail_build):
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    first = _call(tools, 'find_entities', entity_type='product', name_contains='', offset='')
    assert first['count'] == 120 and first['truncated'] and len(first['entities']) == tl.MAX_ROWS
    second = _call(tools, 'find_entities', entity_type='product', name_contains='', offset='60')
    assert second['offset'] == 60 and not second['truncated']
    ids = {e['id'] for e in first['entities']} | {e['id'] for e in second['entities']}
    assert len(ids) == 120, 'the two pages are the whole set, with nothing lost or repeated'
    edges = _call(tools, 'traverse', subject='location:S1', predicate='order_line.rang_up_at',
                  direction='in', as_of='', offset='120')
    assert edges['offset'] == 120 and edges['count'] > 120


def test_aggregate_follows_a_relation_path_to_something_two_hops_away(retail_build):
    ctx = _ctx(retail_build, 'C')
    tools = tl.make_tools(ctx)
    out = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                group_by='order_line.of_order/order.placed_by', where_predicate='',
                where_value='', as_of='', known_at='')
    defector = retail_build.resolver.lookup('customers', 'cust_0042')
    assert defector in out['groups']
    assert all(k.startswith('party:') or k == 'unknown' for k in out['groups'])
    # the terminal may carry its own bucket, and the old shorthand still means the same
    a = retail_build.resolver.lookup('product_master', 'A-100')
    long_form = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                      group_by='order_line.sold_at:quarter', where_predicate='order_line.of_product',
                      where_value=a, as_of='', known_at='')
    short = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                  group_by='quarter', where_predicate='order_line.of_product', where_value=a,
                  as_of='', known_at='')
    assert long_form['groups'] == short['groups']
    assert long_form['groups']['2026Q1']['sum'] == 400.0


def test_a_path_that_runs_too_deep_or_buckets_wrongly_is_refused(retail_build):
    tools = tl.make_tools(_ctx(retail_build, 'C'))
    deep = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                 group_by='a/b/c/d', where_predicate='', where_value='', as_of='', known_at='')
    assert 'three hops' in deep['error']
    bad = _call(tools, 'aggregate', subject_type='order_line', sum_predicate='order_line.qty',
                group_by='order_line.sold_at:fortnight', where_predicate='', where_value='',
                as_of='', known_at='')
    assert 'fortnight' in bad['error']


def test_the_three_arms_get_identical_prompts_apart_from_the_tool_inventory(retail_build):
    import re
    prompts = {}
    for arm in 'ABC':
        ctx = _ctx(retail_build, arm)
        text = tl.system_prompt(ctx)
        assert 'Your tools:' in text and 'Style:' in text
        prompts[arm] = re.sub(r'Your tools:.*?read count and truncated\.', '', text, flags=re.S)
    assert prompts['A'] == prompts['B'] == prompts['C']
    for word in ('absence is asked', 'will block', 'not the way to add', 'earlier date'):
        assert word not in tl.system_prompt(_ctx(retail_build, 'C'))


def test_find_missing_refuses_a_predicate_the_schema_does_not_know():
    import asyncio
    import json as _json
    from datetime import datetime
    from lbo import arms
    b = ingest(FIRMS['retail'][0]())
    ctx = tl.RunContext(build=b, store=arms.snapshot_store(b.store), arm='C', now=datetime(2026, 7, 1, 8))
    tools = {t.name: t for t in tl.arm_c_tools(ctx)}
    bad = _json.loads(asyncio.run(tools['find_missing'].handler(
        {'subject_type': 'product', 'predicate': 'supplied_by', 'as_of': '', 'offset': ''}))['content'][0]['text'])
    assert 'error' in bad and 'product.supplied_by' in bad['known_predicates']
    good = _json.loads(asyncio.run(tools['find_missing'].handler(
        {'subject_type': 'product', 'predicate': 'product.supplied_by', 'as_of': '', 'offset': ''}))['content'][0]['text'])
    assert good['count'] == 1
