# Change log

What changed between the first pass at the experiment and the runs the paper reports,
in the order it happened. Section 5.1 of the paper summarises this file. Every entry here
was applied to every arm alike unless it says otherwise, and every run affected by a
change to a tool surface or a prompt was rerun on the final surface.

## 2026-09-28, before the experiment

- **The pilot.** Three tasks on the ontology arm, one trial each, $0.79. All three runs
  reasoned correctly (the 470-unit order against the 500-unit break; the technician at
  94%; the credit hold applied under the grant) and all three scored zero on rubric
  mechanics: the scorer matched numbers by key name, and a total the run had summed from
  two tool figures counted as invented.
- **After the pilot.** The scorer matches numbers by value; the evidence check accepts
  one arithmetic step over two tool figures; four task prompts were reworded to ask for
  the figures they are scored on; the turn cap is forty and the reason a run ended is
  recorded. The pilot runs were deleted as stale.
- **Interim read at ninety runs.** The ontology arm lacked aggregation (no per-product
  metric filter; traversal paged in sixty-row windows), so it reported unit economics
  where the rubric asked for dollar totals; owner-given numbers scored as invented; two
  ontology runs ended on the fifty-cent budget.
- **Round four.** The ontology arm gains an aggregation tool and a metric filter; the
  evidence check grounds numbers the owner gave in the prompt and numbers executed as a
  payload; a rubric total may be satisfied by its parts; the like-for-like prompt names
  its basis and windows; the per-run budget rises to one dollar; `lbo.rescore` re-grades
  recorded runs from their logs and `lbo.prune` removes runs to be redone.
- **Round five.** A rubric number equal to the sum or difference of two other satisfied
  rubric numbers is satisfied, with no chaining. Numbers a run typed into a tool call are
  not evidence; only the prompt and executed payloads ground a number the run did not read.
- **Arms A and B.** Their action tool did not list the firm's actions or accept source
  identifiers, so every action task failed on both arms. The tool description gained the
  action list and identifier addressing through the resolver; their action and refusal
  tasks were rerun. The ontology arm was not touched.
- **The margin rubrics.** The thirty-unit phrase group was dropped: a forward-looking
  answer was being failed for omitting a historical figure.
- **Round nine.** Every list tool reports its count, whether it was truncated, and an
  offset (the absence tasks had been declared on a population cut at fifty); an absence
  query (`find_missing`); grouping on the aggregation path; the evidence check accepts a
  percentage change and a ratio when the operands are reported; the reorder prompt made
  honest as of the firm's date; pass^k labelled by k.

## 2026-09-29, the reported runs

- **Equal prompts.** An adversarial review of the manuscript found the ontology arm's
  prompt carrying strategy hints the other arms lacked, and the metric layer's carrying a
  note the raw-table arm lacked. The prompts were made identical apart from the tool
  inventory and the whole comparison was rerun: 164 runs, $24.12. Nothing made before this
  is reported.
- **Two scorer corrections after the rerun, found by reading the runs.** The
  customer-message rubric forbade the verb where it meant the audience; it now carries a
  payload predicate on the audience. The parts credit and the ratio credit could be
  satisfied by coincidence among twenty reported figures; the parts credit is now declared
  per rubric key and used only for the margin totals, the ratio credit is removed, and the
  concentration rubric accepts days late where it asks days to pay. Rescored with
  `lbo.rescore`; every record keeps its previous verdict under `score_before_rescore`;
  the moved verdicts are listed in `RESULTS.md`.
- **The ending label.** The harness had labelled a run as stopped by the turn cap whenever
  the runtime's turn count reached forty. Every run so labelled had been reported by the
  runtime as completed. The label now comes from the runtime alone and the records were
  relabelled; no verdict moved.
