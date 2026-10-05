# lbo

A reference implementation of a living business ontology for one small firm, built as
the artifact of the paper *Living Business Ontologies for Accountable Automated Work*.

Everything the ontology holds is an assertion under two clocks:

    x = (client, subject, predicate, value, valid_from, valid_to, recorded_at, recorded_until, evidence, status)

Modules, in the order the paper introduces them:

| Module | What it is |
|---|---|
| `store.py` | the assertion store: business time, knowledge time, supersession, contradictions |
| `schema.py` | the shared core, per-industry extensions, the admission rule, layer counts |
| `identity.py` | source ids to entities; deterministic keys; a review queue; reversible merges |
| `definitions.py` | metric definitions as versioned code; measures that carry window, base, inputs |
| `closure.py` | competency questions and the satisfaction relation; the dependency closure |
| `authority.py` | grants with scope and limits; rules that require approval; the monitor |
| `actions.py` | action contracts; proposals; payload-bound approvals; execution and its journal |
| `trajectory.py` | verbatim, hash-pinned logs of agent runs, and how the paper prints them |
| `contracts_extra.py` | four more verbs: send a message, schedule a job, chase a payment, hold an order |
| `questions.py` | the competency questions each firm's model has to be able to answer |
| `firms/` | three seeded synthetic firms, each arriving as exports with its own identifiers |
| `ingest.py` | one pipeline, three industries: exports in, a built and validated ontology out |
| `build_firms.py` | writes the firms to disk and pins their fingerprints |
| `arms.py` | what each arm can see: store snapshots, and the raw and normalised SQL surfaces |
| `tools.py` | the tool set per arm, and the one system prompt all three share |
| `tasks.py` | the task suite and the rubric that says what a right answer contains |
| `score.py` | S, P, E, C and R; pass^k; the failure classes; all computed, none judged |
| `harness.py` | one task, on one arm, through the Agent SDK, recorded verbatim and scored |
| `report.py` | every table and chart the paper reads, computed from the run records |
| `palette.py` | the one color system for figures, charts, listings and trajectories |

Run the tests from the directory above this one:

    python3 -m pytest lbo -q

The live test is skipped unless `LBO_LIVE=1` is set, because it calls a model and costs
money. To run the experiment and build what the paper reads:

    python3 -m lbo.harness --arms A B C --k 3
    python3 -m lbo.report

This package imports nothing from the repository around it. Outside the standard
library it uses `claude-agent-sdk` (the harness and the tool definitions) and
`matplotlib` (the charts). Everything from `store.py` through `ingest.py`, which is the
paper's machinery proper, is standard library only.
