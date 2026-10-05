from datetime import date
from lbo.firms import common as cm, fieldservice as fs


def test_build_is_deterministic():
    assert cm.fingerprint(fs.build()) == cm.fingerprint(fs.build())
    assert set(fs.build().sources) == {'crm_leads', 'jobs', 'schedule', 'technicians', 'certifications',
                                       'ledger', 'payroll'}


def test_channel_numbers_are_planted_exactly():
    k = fs.build().answer_key
    a, b = k['channels']['A'], k['channels']['B']
    assert (a['leads'], a['jobs'], a['job_margin'], a['spend']) == (100, 20, 8000.0, 1000.0)
    assert (b['leads'], b['jobs'], b['job_margin'], b['spend']) == (40, 18, 10800.0, 800.0)
    assert a['net_per_lead'] == 70.0 and b['net_per_lead'] == 250.0
    assert a['job_margin_per_job'] == 400.0 and b['job_margin_per_job'] == 600.0


def test_backflow_jobs_all_ride_on_one_technician_at_94_percent():
    f = fs.build()
    k = f.answer_key
    jobs = [r for r in f.sources['jobs'].records
            if r['channel'] == 'B' and cm.quarter_of(date.fromisoformat(r['performed_on'])) == k['focal_quarter']]
    assert jobs and all(r['service_line'] == 'backflow' and r['tech'] == 'T3' for r in jobs)
    assert k['utilisation_pct'] == 94.0 and k['constraint_tech'] == 'T3'
    assert k['realistic_return_on_800'] == 600.0 - 800.0


def test_stale_certification_and_divergence_plants():
    f = fs.build()
    k = f.answer_key
    certs = f.sources['certifications'].records
    assert any(r['tech'] == 'T5' and r['certification'] == 'backflow-tester' for r in certs)
    assert 'left_on' not in certs[0]
    techs = {r['tech_id']: r for r in f.sources['technicians'].records}
    assert techs['T5']['left_on'] == '2026-02-28'
    assert len(k['scheduled_vs_performed_divergences']) == 2
