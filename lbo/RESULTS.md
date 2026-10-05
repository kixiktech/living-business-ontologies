# Results

The numbers here are copied from `results/summary.json` and `results/tables/*.json`,
which are the only sources the paper reads. Regenerate with `python3 -m lbo.report`.

| | |
|---|---|
| Model | claude-sonnet-5 through the Claude Agent SDK |
| Runs | 164 (150 across the three arms, k = 2 per task; 14 ablation runs, k = 1), all made on 2026-09-29 after the tools and prompts were frozen (equal prompts, commit 2e0ee4a) |
| Tasks | 25 across three firms |
| Cost | $24.12 in total; mean per run A $0.081, B $0.084, C $0.247 (C is 3.04 times A, 2.93 times B) |
| Turns | mean per run A 10.56, B 10.04, C 21.94 (C is 2.08 times A) |
| Capped | none: the runtime reported every run as completed. 11 runs reached 40 turns or more by its count (A 2, B 1, C 6, ablations 2); an earlier label called those capped, corrected 2026-09-29 |
| Calendar | runs that wrote the machine's date into a query: A 9, B 5, C 7 of 50 each |

| Arm | Retail pass^1 | Field service pass^1 | Distributor pass^1 | All pass^1 | Both trials passed |
|---|---|---|---|---|---|
| A, raw tables | 66.67 | 57.14 | 83.33 | 68 | 68 |
| B, metric layer | 75 | 64.29 | 83.33 | 74 | 72 |
| C, ontology | 70.83 | 64.29 | 75 | 70 | 64 |

By kind (pass^1, A / B / C): absence 100 / 100 / 100; action 60 / 70 / 80; owner
message 0 / 0 / 0; question 70 / 80 / 65; refusal 75 / 75 / 75.

Failed runs, 44 of 150: A 16 (wrong number 9, invented number 3, missing communication
2, missing action 2); B 13 (8, 2, 2, 1); C 15 (wrong number 8, missing communication 5,
invented number 2).

Ablations on arm C, each on its own target tasks (pass^1, ablated / full model on the
same tasks): no identity 66.67 / 100 (3 tasks); no evidence 0 / 25 (2); no time
66.67 / 66.67 (3); no authority 83.33 / 66.67 (6). At one trial per task a single run is
a third of a row or more; these are reported as noise.

Schema: the core carries 15 entity types and 17 relation types shared by all three
firms; the extensions add 3 and 5 (retail), 6 and 9 (field service), 5 and 6
(distributor).

## What changed between the first pass and the final surface

A pilot of three tasks on the ontology arm ran before the experiment, and both the
surface and the scorer changed after it. What changed between that first pass and the
final surface, all recorded in the change log published with the code: the ontology
arm gained an aggregation tool, a metric filter, an absence query and honest paging
after the pilot showed it paging through sixty-row windows of a list; the scorer learned
to match numbers by value, to accept one arithmetic step on evidence, and to refuse a
number the run merely typed into a query; four task prompts were made to ask for the
figures they are scored on; the per-run budget rose to one dollar. Every run affected by
a change to the surface was rerun on the final surface; every run was re-graded with the
final scorer. (This paragraph is Section 5.1 of the paper, word for word; the change log is `CHANGELOG.md`.)

## What changed after the rerun (scorer only; no run was remade)

The equal-prompt rerun first scored A 72, B 76, C 72 (pass^1). Two scorer corrections
followed, both applied to every arm, both rescored with `python3 -m lbo.rescore`, which
keeps the previous verdict in each record under `score_before_rescore`:

1. **The customer-message rubric forbade the verb, not the audience.** One ontology trial
   sent the draft to the owner (audience internal), the compliant alternative the prompt
   asks for, and scored as an unauthorised write. The rubric now carries
   `payload_predicate={'send_message': ('audience', '==', 'customer')}`. Moved C
   f_customer_message seed 1 from fail to pass; C 72 to 74.
2. **The parts and ratio credits were coincidence generators.** The first scorer credited
   any rubric number that two reported figures added or subtracted to, or divided to.
   With twenty figures in an answer some pair makes almost anything: ten overdue invoices
   plus a thirty-one made the 41.3-day DSO; two channel budgets (800 and 1,000) made the
   -200 return; a pair of unrelated figures made the 94 utilisation. The credit is now
   `Rubric.decomposable`, a tuple of keys, used only for the margin totals given per
   product, and `Rubric.alternatives` accepts days late (32) where the key asks days to
   pay (62) on 30-day terms. Moved: C d_chase_and_aging s0, B d_chase_and_aging s0,
   A r_distinct_customers s0 and s1, B f_channel_owner_msg s0, C d_concentration s0 from
   pass to fail; B d_concentration s0 from fail to pass; and the no_evidence ablation on
   f_channel_inversion from pass to fail. A 72 to 68, B 76 to 74, C 74 to 70.

The paper discloses both in Section 5.1.
