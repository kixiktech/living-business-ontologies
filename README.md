# Living Business Ontologies for Accountable Automated Work

Kyle Nix, October 2026. Working paper.

A method and a reference implementation for building a living ontology of one small
firm from its own system exports, so that an agent can answer, act and refuse. Every
fact is an assertion under two clocks (when it was true, when it was known) with its
evidence and its status; relationships are typed by the business role they assert;
definitions are versioned code; actions are contracts; authority is enforced by a
monitor outside the agent. Three synthetic firms (a four-location retailer, a
field-service contractor, a wholesale distributor) are built start to finish, and one
agent is put over each under three surfaces (raw tables, a metric layer, the ontology)
on twenty-five tasks with ground truth, two trials per task, scored by code.

**The result, in one line.** On this suite the metric layer passes the most trials; the
ontology leads on actions and trails on plain aggregation at three times the cost per
run; the three surfaces fail alike where the answer needs a hop the model did not
think to take.

**Read it:** [`build/living-business-ontologies.pdf`](build/living-business-ontologies.pdf)
(54 pages). The source is `living-business-ontologies.md`.

## What is here

| Path | What it is |
|---|---|
| `living-business-ontologies.md` | the manuscript, with every table, chart, listing and printed run as a placeholder the build resolves from the files below |
| `build/` | the built PDF |
| `lbo/` | the reference implementation: assertion store, schema, identity, definitions, competency questions, action contracts, authority monitor, the three firm generators, the one ingestion pipeline, the three arms, the task suite, the scorer, the harness, the report |
| `lbo/firms/data/` | the three synthetic firms as exports, with their sealed answer keys and fingerprints |
| `lbo/results/` | every run record (`runs/`), the summary and the tables the paper reads |
| `lbo/logs/` | every run transcript, verbatim, under its hash; the paper prints from these |
| `lbo/RESULTS.md`, `lbo/CHANGELOG.md` | the numbers in one page, and what changed between the first pass and the reported runs |
| `paper_kit.py`, `paper_figures.py`, `case_gates.py` | the typesetter and its gates |

## Reproducing

```bash
pip install -r requirements.txt
python3 -m pytest                                   # the package suite; no model call
python3 -m lbo.build_firms                          # regenerate the firms; fingerprints must match
python3 -m lbo.harness --arms A B C --k 2 --tasks all   # rerun the experiment (calls a model; costs money)
python3 -m lbo.rescore                              # re-grade every saved run with the current scorer
python3 -m lbo.report                               # rewrite every table and chart from the run records
python3 -c "import paper_kit as pk; pk.build('living-business-ontologies.md', 'build/living-business-ontologies')"
```

The build refuses a manuscript in which any printed run, listing, table or chart has
drifted from the committed files, in which a section number is hand-typed, or in which
a number in the results sections cannot be traced to a results file. The PDF is
rendered by headless Chrome and needs a Chrome or Chromium binary on the path.

All three firms are synthetic and generated from fixed seeds. No real firm's records
are used anywhere in this repository.

## Licence

Code under the MIT License (`LICENSE`). The manuscript and the PDF under CC BY 4.0
(`LICENSE-PAPER`).

## Citing

Nix, K. (2026). Living Business Ontologies for Accountable Automated Work. Working
paper. (SSRN link to follow.)
