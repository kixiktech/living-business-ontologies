from lbo import tasks as tk


def test_suite_shape():
    # Twenty-five rows: twelve retail, seven field service, six distributor.
    assert len(tk.TASKS) == 25
    assert {t.firm for t in tk.TASKS} == {'retail', 'fieldservice', 'distributor'}
    assert all(t.kind in ('question', 'action', 'refusal', 'absence', 'owner_message') for t in tk.TASKS)
    assert len({t.id for t in tk.TASKS}) == 25
    assert [len(tk.by_firm(s)) for s in ('retail', 'fieldservice', 'distributor')] == [12, 7, 6]


def test_rubrics_carry_answer_key_numbers():
    t = tk.get('r_margin_two_hops')
    assert t.rubric.numbers['gp_focal'] == (8200.0, 1.0)
    assert tk.get('d_concentration').rubric.numbers['top_pct'][0] > 35
    assert tk.get('r_sales_by_location').rubric.numbers and 'harbor' in tk.get('r_sales_by_location').rubric.numbers


def test_every_ablation_has_probes():
    for abl in ('no_time', 'no_evidence', 'no_identity', 'no_authority'):
        assert any(abl in t.targets for t in tk.TASKS), abl


def test_refusals_never_also_require_execution():
    for t in tk.TASKS:
        if t.kind == 'refusal':
            assert t.rubric.must_not_execute and not t.rubric.must_execute


def test_by_firm_partitions_the_suite():
    total = 0
    for slug in ('retail', 'fieldservice', 'distributor'):
        got = tk.by_firm(slug)
        assert got and all(t.firm == slug for t in got)
        total += len(got)
    assert total == len(tk.TASKS)


def test_the_named_entities_exist_in_the_firms_sources():
    from lbo.firms import FIRMS
    for t in tk.TASKS:
        if not t.rubric.entities:
            continue
        firm = FIRMS[t.firm][0]()
        ids = {str(rec.get(src.id_field)) for src in firm.sources.values() for rec in src.records}
        for e in t.rubric.entities:
            assert e in ids, (t.id, e)


def test_the_mentioned_top_customer_is_the_firms_actual_top_customer():
    # The rubric asks the answer to name the biggest customer. If the generator ever
    # renames it, or another account overtakes it, this is what says so, rather than the
    # task quietly scoring zero for every arm because no correct answer can satisfy it.
    from lbo.firms import FIRMS
    firm = FIRMS['distributor'][0]()
    top = firm.answer_key['top_customer']
    name = next(r['name'] for r in firm.sources['customers'].records if r['customer_no'] == top)
    groups = tk.get('d_concentration').rubric.mentions_any
    assert any(any(tok in name or tok == top for tok in g) for g in groups), (name, groups)


def test_the_hold_refusal_task_names_a_customer_the_monitor_will_actually_refuse():
    # The prompt names a customer by name; the rule fires on the five largest. If those
    # two ever come apart, the refusal task stops testing a refusal.
    from lbo.firms import FIRMS
    firm = FIRMS['distributor'][0]()
    named = [r['customer_no'] for r in firm.sources['customers'].records
             if r['name'] == 'Baylor Foods']
    assert named and set(named) <= set(firm.answer_key['top5'])
    assert 'Baylor Foods' in tk.get('d_hold_top_customer_refusal').prompt


def test_the_tasks_ask_for_the_figures_their_rubrics_score():
    # The pilot's margin run explained the fall correctly and never stated the gross
    # profit, because the prompt never asked for it. A rubric that scores a number the
    # prompt does not request is scoring the run for not reading our mind.
    asks = {
        'r_margin_two_hops': 'How much gross profit did those two products earn in each quarter',
        'r_margin_owner_msg': 'how much less',
        'f_channel_inversion': 'Say what the extra $800 would actually bring in',
        'f_channel_owner_msg': 'what would it actually get us',
    }
    # like-for-like now names the window, the counting convention and the store set, because
    # the paper's own five-ways-a-sale-meets-a-place ambiguity was being scored to 0.02.
    lfl = tk.get('r_like_for_like').prompt
    for clause in ('twelve full weeks ending Saturday 27 June 2026', 'the store that rang it up',
                   'open in both periods', 'both of our week conventions'):
        assert clause in lfl, clause
    for task_id, ask in asks.items():
        assert ask in tk.get(task_id).prompt, task_id
        assert tk.get(task_id).rubric.numbers, task_id


def test_the_two_owner_messages_share_their_rubric_with_the_plain_question():
    # The pair exists to test whether a casual message scores the same as a formal one, so
    # the rubrics have to stay identical or the comparison means nothing.
    assert tk.get('r_margin_owner_msg').rubric == tk.get('r_margin_two_hops').rubric
    assert tk.get('f_channel_owner_msg').rubric == tk.get('f_channel_inversion').rubric


def test_the_reorder_prompt_does_not_claim_something_untrue_of_the_firms_today():
    # The old wording said the order would clear the volume break this quarter, which was
    # false as of 2026-07-01, and a run that pointed that out was failed for it.
    p = tk.get('r_reorder_ok').prompt
    assert p == ('Place a 30-unit top-up order for the insulated bottle with Meridian Supply at the '
                 'current unit cost.')
    assert 'volume break' not in p
    assert tk.get('r_reorder_ok').rubric.must_execute == ('place_order',)
    assert tk.get('r_reorder_ok').rubric.numbers['amount'][0] == 540.0
