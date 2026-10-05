from datetime import date, datetime
from lbo.firms import common as cm


def test_quarters_cover_the_period_in_order():
    q = cm.quarters()
    assert [x[0] for x in q] == ['2025Q1', '2025Q2', '2025Q3', '2025Q4', '2026Q1', '2026Q2']
    assert q[0][1] == cm.START and q[-1][2] == cm.END
    assert cm.quarter_of(date(2026, 5, 15)) == '2026Q2'


def test_weeks_respect_the_boundary_convention():
    sun = cm.weeks(date(2026, 3, 1), date(2026, 4, 1), week_starts=6)   # Sunday start
    sat = cm.weeks(date(2026, 3, 1), date(2026, 4, 1), week_starts=5)   # Saturday start
    assert all(a.weekday() == 6 and (b - a).days == 7 for a, b in sun)
    assert all(a.weekday() == 5 and (b - a).days == 7 for a, b in sat)
    assert sun != sat


def test_money_and_pct():
    assert cm.money(10.005) == 10.01 or cm.money(10.005) == 10.0   # banker's or half-up, both are 2dp
    assert cm.pct(1, 3) == 33.33 and cm.pct(1, 0) == 0.0


def test_write_sources_and_fingerprint_are_deterministic(tmp_path):
    src = cm.Source('pos', datetime(2026, 7, 1), [{'id': 1, 'x': 'a'}], 'id', 'a point of sale export')
    f = cm.Firm('demo', 'Demo Co', 'retail', 1, {'pos': src}, '# policy\n', [], {'k': 1}, [])
    paths = cm.write_sources(f, tmp_path)
    assert paths and (tmp_path / 'demo' / 'pos.json').exists()
    assert cm.fingerprint(f) == cm.fingerprint(f) and len(cm.fingerprint(f)) == 12
    assert (cm.write_answer_key(f, tmp_path)).read_text().strip().startswith('{')
    assert cm.write_policy(f, tmp_path).read_text() == '# policy\n'
