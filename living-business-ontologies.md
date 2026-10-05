---
title: Living Business Ontologies for Accountable Automated Work
subtitle: Building a complete, evidence-bearing model of one small firm from its own records, so that an agent can answer, act and refuse
author: Kyle Nix
date: 4 October 2026
gated: true
runhead: LIVING BUSINESS ONTOLOGIES FOR ACCOUNTABLE AUTOMATED WORK
abstract: A small firm holds a complete record of everything that happened to it and cannot
  account for any of it, because the systems that made the record were built to transact,
  and a transacting system keeps one relationship between any two things where the
  business has many. We present a method and a reference implementation for building a
  living ontology of one firm from its own system exports. Every fact is an assertion
  under two clocks (when it was true, when it was known), carrying its evidence and its
  status. Relationships are typed by the business role they assert, not only by what they
  connect. Definitions are versioned code. The verbs the business performs are contracts,
  and the authority to perform them is enforced by a monitor outside the agent, so a
  persuasive proposal changes nothing. Competency questions carry a satisfaction relation
  that names what is present, absent or stale, and the model grows only where a paid
  question needed it. We build three synthetic firms of different shape (a four-location
  retailer, a field-service contractor, a wholesale distributor), each arriving as exports
  with its own identifiers and quirks, and construct their ontologies start to finish. We
  then put one agent over each firm under three representations (raw tables, a metric
  layer, the ontology) on twenty-five tasks with ground truth, including tasks whose
  correct answer is a refusal, scoring final state, authorised process, material evidence
  and required communication together, two trials per task, with ablations that remove
  time, evidence, identity and authority one at a time. On this suite the metric layer
  passes the most trials; the ontology leads on actions and trails on plain aggregation
  at three times the cost per run; and the three surfaces fail alike where the answer
  needs a hop the model did not think to take. We say where each surface wins, print the
  runs, and report two defects in our own scorer that a reading of the runs found. Across
  the three firms we count what the shared core carries against what each industry
  added. All firms are synthetic, every number in this paper is read from committed run
  output, and every trajectory is printed verbatim from its log.
keywords: business ontology, knowledge graphs, bitemporal data, provenance, entity resolution, agent evaluation, tool use, human oversight, small business
---

## Introduction {#intro}

A firm with four stores, two hundred products and one owner can hold a complete record of
its own life. Every sale, invoice, hour worked, delivery and message is present,
timestamped and mostly correct. Point the most capable model available at that record and
ask why margin fell last quarter, and the answer is fluent, plausible, and in the cases
that matter, wrong. The number is right. The thing it describes is not.

The reason is not data quality and it is not model capability. It is a property of the
record. The systems a firm runs were built to transact, and a transacting system keeps
exactly one relationship between any two things: the one that lets it complete and
account for the transaction. A sale is stored against one store. The business relates that
sale to a store in at least five ways (the store that rang it up, the store that shipped
it, the store whose shelf is now empty, the person credited, the store it was counted in
last year), and the five diverge exactly when something has gone wrong, which is when
anyone asks. A system reasoning over the record has one edge and a question that needs
another. It answers with the edge it has.

This paper is about building the missing structure: a **living business ontology**, a
complete, evidence-bearing model of one specific firm, constructed from that firm's own
system exports and maintained as a persistent asset of the firm, precise enough that an
agent can answer questions that cross every boundary of the business, prepare actions
under stated authority, and refuse correctly when the data or the policy will not support
what was asked.

Large organisations have had structures like this for decades, built at great cost, and
the platforms that sell them have made a business of it. We are interested in the other
end of the market, for a reason that is more than sympathy. A large organisation cannot
be modelled completely: thousands of people hold fragments of the model, every definition
that matters has a constituency, and the business changes faster than agreement forms
[7, 11]. A firm with one owner has one party who can settle what a week is. That collapses
the cost of agreement, which is the cost that defeated enterprise modelling, and leaves
the cost of observation exactly where it was. So the small firm is not a scaled-down
version of the enterprise problem. It is a different and more tractable one, and it is
the first organisation that can be represented whole. We treat that as a scoping assumption
rather than a finding: it says which firms the method is built for, and nothing below
depends on it holding for every firm.

{{fig2col:system:8279a30ce47e:48-52}}

{{figref:system}} shows the whole of it. On the left, a firm's exports flow through
identity resolution into an assertion store, above which sit the schema, the definitions,
the action contracts and the authority monitor, with an agent reading and proposing and an
owner deciding. On the right is the end of a run, printed from its log, in which the
agent was asked why margin fell, computed the figures through the definitions, read from
the products to their supplier to the supplier's terms to the units ordered each quarter,
and answers with the number, the cause, and the order that would restore the tier.

**Contributions.** We make five.

1. **A representation** (Section {{sec:method}}). Assertions under two clocks with evidence
   and status; relations typed by business role; definitions as versioned executable
   code; verbs as action contracts with payload-bound approval; authority as a reference
   monitor outside the reasoning system; competency questions with a satisfaction relation
   that reports what is present, absent or stale; supersession instead of deletion; and
   traversal as audit. The individual pieces are inherited and we say from where. The
   conjunction, on one edge, for a firm small enough to model whole, is ours.
2. **A construction method** (Section {{sec:impl}}). From a firm's raw exports, with the
   exporting systems' own identifiers and their own notion of when a record was entered,
   to a validated ontology, through one pipeline that does not know which industry it is
   building. A small shared core; an extension per industry admitted only where a named
   question, constraint or action requires it.
3. **Three synthetic firms** of different shape, generated deterministically from a seed
   with planted structure and a sealed answer key, published with the code so the whole
   experiment is reproducible without any firm's data.
4. **An evaluation** (Sections {{sec:experiments}} and {{sec:trajectories}}). One agent,
   three representations, twenty-five tasks, ground truth, refusals scored as successes
   when refusal is right, a reward that requires the final state, the process, the
   evidence and the communication to all be correct, two trials per task, ablations that
   remove time, evidence, identity and authority one at a time, and an honest result: the
   metric layer leads, the ontology earns its cost on actions and not on sums, and the
   failures the arms share are the ones that matter most.
5. **A count toward transfer** (Section {{sec:discussion}}). Ontologies do not transfer
   between firms; shapes (we call them morphologies) may. Across three industries we
   count what the core shares and what each extension adds, say why that is a count and
   not yet a measurement, and say what the measurement would have to show for the most
   valuable capability of the whole programme, detecting what a firm lacks, to arrive.

All three firms are synthetic and no deployment result is reported. Everything
numerical is read from committed run output, every listing is the code that runs, and
every trajectory is printed verbatim from its log, with lists of identifiers longer
than eight elided in print; the build refuses a paper in which any
of those has drifted.

## Related work {#related}

This paper sits at the junction of five literatures, and it is worth saying plainly at the
outset which parts of the argument are inherited and which are not. Most of them are
inherited.

### Enterprise and business ontology

Representing a firm as typed entities and relations is old and distinguished. The REA
accounting model reduced the transactional core of any business to resources, economic
events and agents in 1982, later extended with type and commitment layers [4, 5], and it
remains the smallest vocabulary that covers the exchange structure of a firm. The
Enterprise Ontology assembled terms across activities, organisation, strategy, marketing
and time [2]. DEMO treats an organisation as actor roles entering coordination acts around
production acts, and already takes authorisation, responsibility and commitment as
essential rather than incidental [6]. Competency questions as the instrument that bounds an
ontology's scope come from the TOVE programme [3], and minimal ontological commitment as a
design criterion from Gruber [1].

None of that is new here, and the small-business version of it is not new either: that
small firms differ from large ones in kind rather than degree, and are resource-poor in a
way that shapes what technology they can adopt, is the founding claim of a literature going
back to 1981 [68].

### Object-centric event data

The observation in Section {{sec:method}}, that one sale relates to a location in several
distinct ways and a single stored field discards the rest, is an instance of a named and
formalised problem. Flattening a multi-object log onto one case notion produces
**convergence**, where events are duplicated across cases, and **divergence**, where they
are mis-related [63]. The remedy the process-mining community built is the object-centric
event log, which makes multiple object types first class and, in its current version, adds
object-to-object relations and attribute change over time [64]. The entity-relationship
model itself made relationships first class with explicit roles in 1976 [71], and
role-playing dimensions have been standard warehousing practice for decades.

So the five-way relation is a rediscovery, and the honest delta is narrow: object-centric
logs type an edge by the **object** it connects, while this paper types it additionally by
the **business role and convention** it asserts, and attaches validity, evidence and
authority to the edge itself.

### Getting an ontology over a relational store

Mapping transactional records into an ontology and querying it is ontology-based data
access, a research programme with a survey, a standard mapping language and production
tooling [65]. It has been applied to exactly the pipeline this paper describes, extracting
event logs from legacy relational databases under ontological control [66]. The measured
benefit of a semantic layer over a raw schema for question answering, roughly a threefold
improvement, comes from that tradition too [19], with the caveat that the comparison also
bought expert modelling effort the raw-schema arm did not have. The
reference survey for graph data models, identity, context and validation already treats
temporal and provenance annotation of edges as a first-class dimension [21], which is why
this paper claims the conjunction rather than the annotation.

The adjacent line of work asks a model to query a schema directly rather than through an
ontology. Its benchmarks have moved quickly and in the models' favour [17, 18], which is
why Section {{sec:discussion}} rests on none of their scores. The durable finding from that
literature is a different one: a substantial class of business questions cannot be
expressed in the query language at all, because answering them needs knowledge the schema
does not contain [20].

### Time, and the memory of an agent

Valid time and transaction time are settled work with agreed vocabulary and a standardised
implementation [12, 13, 14], and append-only, non-destructive modelling with schema growth
by extension has a peer-reviewed treatment in anchor modelling [74]. What is new is that
2026 turned this into an active subfield under the heading of agent memory. A bitemporal
operator algebra now types the production heuristics for contradiction resolution and
preserves the superseded fact in an audit row rather than deleting it [57]. Deterministic
supersession over a bitemporal ledger has been measured against retrieval, with the finding
quoted in Section {{sec:discussion}} that similarity cannot distinguish a contradicted fact
from a duplicated one [56].

This is the closest prior art to the temporal half of the representation, and the
difference is framing rather than mechanism: that work models the memory of an agent, and
this paper models the business the agent is reasoning about.

### Authority, and process versus outcome

Two of this paper's positions are, as of 2026, no longer contested and should be read as
supported background rather than contributions.

That authority must be enforced outside the reasoning system is now measured. Out-of-band
policy enforcement at a trusted tool boundary reduced trace failure rates from 57.6% to
0.2% across 3,621 trials, at an honest cost in task fulfilment, which fell from 79.1% to
60.9% [60]. Deterministic pre-execution gates recovered a failure mode in which 78% of
observed failures were silent wrong-state outcomes producing no tool error at all, and the
same work bounds its own mechanism by showing gates add little where the tools already
self-enforce [61]. Policy compilation to a reference monitor at each decision point is
implemented [62].

That a correct final state does not prove a correct process is similarly established. The
clearest statement of it holds that a final output alone cannot show which evidence, tool
state, rule, authorisation or action path produced it, and answers by recording each
committed decision as a typed trajectory linking observed state, path and authority [59].
Evaluation of trajectories rather than answers exposes agents that never retrieved the
artefact their answer depended on [58]. In a business setting, an ontology-governed
approach separates accuracy from decision-chain reliability and names the gap between them
directly, reporting baselines that reach 80% accuracy on 24% to 36% tool-chain reliability
[62].

### What is left

Assembled honestly, the position is narrow. The table below is what this paper claims and
what it does not.

<div class="tabcaption"><span class="lbl">Table 1.</span> Where each property of the proposed representation is already established, and what remains. The contribution is the conjunction and the setting, not any single row.</div>

| Property | Established by | What is not yet done |
|---|---|---|
| Typed entities and relationships | enterprise ontology [2, 4, 6], object-centric logs [63, 64] | typed by business role and convention, not only by object |
| Temporal validity | temporal databases [12, 13], bitemporal agent memory [56, 57] | carried as a property of a business relationship rather than of a memory |
| Evidence and provenance | PROV [23], provenance theory [25], audit rows [57] | attached to the edge itself, as a first-class property |
| Authority | access control [29], out-of-band enforcement [60, 61, 62] | carried on the relationship, not only at the tool boundary |
| Process over outcome | decision trajectories [59], trajectory evaluation [58] | settled; assumed here rather than argued |
| All four on one edge, for a firm small enough to model whole, to prepare an action | | this paper |

A recent survey of persistent state in agent systems proposes six diagnostic axes for a
state item, of which authority, provenance, scope and actionability are four of the
properties argued for here [58]. That is the nearest competing framing, and its own stated
gap is the opening this paper works in: the literature concentrates on accumulating and
retrieving state rather than on governing it.

## The living business ontology {#method}

This section is the method: what the model holds, in what form, and what each part is
for. Everything in it is implemented in `lbo`, the reference package described in
Section {{sec:impl}}, and the listings in {{figref:panels}} are read from that code at
build time.

### What a record loses

Begin with the gap between an event and its trace. A sale line is the residue of
something larger: a person came somewhere for a reason, met a thing sitting beside other
things, weighed it against an alternative, and decided. What survives into the record is
the item, the price, the quantity, the time and the tender. What does not survive is the
reason for the visit, the alternative, the shelf, who was working, the weather, and
whether the person came for this or found it.

The loss is not random ({{figref:tracegap}}). In the vocabulary of the missing-data
literature it is missing not at random, and the mechanism is known [70]: **a transacting
system retains precisely the fields required to complete and account for the transaction,
and nothing else.** Those fields are the ones the firm already controls, its own prices,
items, hours and locations. The discarded fields describe the customer's world. Two
consequences follow. A report is a high-resolution rendering of exactly the dimensions
the owner already had, which is why accurate reporting so often feels useless. And the
lost attributes cannot be recovered by collecting more at the point of capture, because
they were not observable there. What can be done is reconstruction: relating the trace to
things outside it (weather, shift, adjacency, the supplier's terms, the cash decision
made in another department) until the discarded dimension is recovered. That is the job
of the structure this paper describes. Not to organise what was recorded, but to
reconstruct what recording destroyed.

{{fig:tracegap}}

### Assertions, and two clocks

Everything the model holds is an assertion:

<div class="eqn"><i>x</i> = (<i>c</i>, <i>s</i>, <i>p</i>, <i>v</i>, <i>I</i><sub><i>v</i></sub>, <i>I</i><sub><i>o</i></sub>, <i>e</i>, &sigma;)</div>

with client *c*, subject *s*, predicate *p*, value *v*, a validity interval
*I*<sub>*v*</sub> in business time, a recorded interval *I*<sub>*o*</sub> in knowledge
time, an evidence reference *e*, and a status &sigma; drawn from observed, inferred,
disputed, corrected and superseded. Subjects are typed identifiers (`product:3f2a`). A
predicate is either a field (`product.unit_cost`) or a relation (`product.supplied_by`),
and a relation's value is another subject. Evidence is mandatory: an assertion with no
evidence cannot be constructed.

The two intervals are the two clocks of a bitemporal database [12, 13, 14], and both are
load-bearing. A supplier's cost takes effect on the first of the month and the invoice
is entered on the sixth. A question asked on the third could not have known it, and a
replay that uses the invoice rewards the system for information it did not hold. So every
read takes both clocks: *B*<sub>*c*</sub>(*t*, *u*) is what was true of the firm at
business time *t* as known at knowledge time *u*, and the default read is current
knowledge. Nothing is ever deleted. A correction closes the old row's knowledge interval,
marks it superseded, and inserts a new row that points back at it. A decision made two
years ago can be reread in the terms under which it was made.

### Relations are typed by role, not only by endpoint

The pair (sale, store) supports at least five relation types ({{figref:fivestores}}):
rang up at, fulfilled from, stock drawn from, credited to, counted in. They are not
alternatives to choose between. They are different facts that share endpoints, and a
schema that permits only one is not simplifying but discarding. One further distinction:
an edge that records what happened and an edge that applies an attribution rule are
different types even when they join the same two things. The first is a fact. The second
is a convention somebody chose, and the model records which.

{{fig:fivestores}}

Three more properties follow. Relations are **directional, and the two directions ask
different questions**: from a crew to its jobs asks what the crew is committed to; from a
job to crews asks who could perform it, and only the second finds a capacity ceiling.
Relations are **valid over intervals**: a technician holds a certification from the date
it was issued, a product belongs to a category until it is recategorised, and an untimed
edge answers every historical question with the present structure. And relations
**carry evidence**: an edge from a source export, an edge an operations manager confirmed
in writing, and an edge inferred by a matching procedure at stated confidence are three
epistemic situations, and a graph that flattens them is more persuasive than a sparse one
and less trustworthy.

The delta from object-centric event logs [63, 64] is stated once, in Section {{sec:related}}.

### Identity is a decision that can be wrong

Because every relation is computed through entities, an identity error propagates into
every claim that traverses it. Source identifiers are not identities: one customer with
two email addresses is two entities, and every relation through her is wrong by
construction. The classical result is stronger than the observation. The optimal decision
rule for record linkage partitions pairs into matches, non-matches and a region left
deliberately undecided, and that region is irreducible at fixed error bounds [15]. A
representation that forces every identity question to resolve is not more decisive. It is
less correct.

So the resolver does three things. Deterministic matches on approved keys (a normalised
email, a SKU) resolve automatically. A record that shares a name but no key with an
existing entity becomes a new entity **and** a candidate in a review queue, with the
reason. And a merge is itself an assertion (`identity.same_as`), recorded with evidence
and knowledge time, so it can be replayed and reversed: a split supersedes it. Every
source identifier is kept as an assertion on the entity it resolved to, so a merge or a
split can list its dependants for recomputation. An action needs better identity
evidence than a summary does: suspecting that two records are one person is enough to
ask a question, and not enough to merge two accounts.

### Definitions are code, and a measure carries its anchors

A point of sale's gross sales, an accountant's recognised revenue and a bank's cash
receipts can be simultaneously correct and mutually different. A number without its
grain, basis, inclusions, treatment of returns and tax, and the version of the definition
that produced it is an observation, not a comparable quantity. So a metric definition is
an object with those fields and an effective date, and it carries the function that
computes it. The registry selects the version effective on the date asked about, and the
function returns a **measure** that names its window, its base, its definition version,
and the identifiers of every assertion it read. A number never travels without the four
anchors a reader needs to place it (what it is, over what window, against what base, as
of when), and the inputs are what the dependency closure of the satisfaction relation below
is computed from. Where an input is missing, the measure carries a note and excludes the
line; it never substitutes a zero.

Reconciliation between two differently defined quantities names the differences (window,
base, version, value) rather than electing one as true.

### Verbs, and action contracts

A business has a surprisingly short list of things it does to itself: change a price,
order stock, schedule a person, chase a payment, hold an order, send a message. These are
the verbs, and they belong in the schema beside the nouns, because a model of nouns and
relations can describe a firm and a model with verbs can be asked to do something about
it. An action type is a contract:

<div class="eqn"><i>a</i> = (<i>I</i>, Pre, &Delta;, Post, <i>F</i>, &Gamma;, &rho;)</div>

with inputs *I*, preconditions Pre, the intended change &Delta;, the expected resulting
state Post, forbidden effects *F*, an authority requirement &Gamma;, and a recovery
procedure &rho;. Recovery is usually compensating rather than reversing: a message that
has been read cannot be unsent, which is the saga, and forty years old [75].

The model distinguishes an action type, a proposed action, an approved request and an
execution attempt. A **proposal** is the contract, a payload and the versions it was
computed under, and it has a hash. An **approval** binds to that hash. Editing the
quantity, the target or any policy-sensitive field after approval changes the hash and
invalidates the approval. Before execution the preconditions are refreshed against
current state, because an approval is evidence of an approval and not of the business
state intended; after execution the postconditions are checked and the outcome is
journaled as assertions on the action itself, so the record of what was done is queried
like everything else.

### Authority is a constraint, not a suggestion

Policies are approved by responsible people and enforced outside whatever reasons about
them. In our implementation the agent's write tools call a **monitor** and cannot
proceed past it. A grant is (principal, action, scope, limits, validity); a rule names an
action and returns, for a payload, whether explicit approval is required and why. The
monitor's decision is (allowed, requires approval, reason). An action with no live grant
for the principal is refused. An action outside the grant's scope or limits is refused.
An action a rule flags is allowed only with an approval bound to that exact proposal.

This is access control and is built as such rather than reinvented [29]. It is also the
answer to a published argument that enterprise systems built on language models
constrain what goes into the model and leave what comes out unconstrained [43]: the
constraint that matters is on the effect. Permission to prepare is not permission to
execute, and a read-only relationship still supports a great deal: investigation,
reconciliation, drafting and the assembly of a decision packet proceed with no capacity
to change the world.

### Competency questions, and the satisfaction relation

An ontology's scope is properly set by the questions it must answer in its own
vocabulary, and its evaluation is whether it can answer them [3]. We make that
operational. A competency question is a text and a tuple of declared requirements, each
of one of three kinds: an assertion requirement (a predicate, optionally a subject,
optionally a window it must cover without a gap, optionally a maximum knowledge age), a
definition requirement (a metric that must have a version effective on the date), and a
grant requirement (an action the principal must be able to take without approval). The
satisfaction relation

<div class="eqn">sat(<i>q</i>, <i>B</i><sub><i>c</i></sub>(<i>t</i>, <i>u</i>)) = (present, absent, stale, gaps)</div>

partitions the requirements and names each gap in words ("no unit cost for product A
from 2026-05-01 to 2026-07-01"). The **dependency closure** of a question is the set of
assertion identifiers that satisfy its assertion requirements plus the inputs of every
measure computed for its definition requirements over the question's windows: one step,
not a fixpoint. This is closure under declared dependencies, and its rule for a missing
dependency is the one that matters: narrow the answer, ask, or stop. Never complete the picture with a plausible
account of the business.

The worked constraint, executed in Section {{sec:trajectories}}: the margin question
requires `product.unit_cost` to cover both quarters for both focal products. In the store
built from the retailer's exports, the second quarter's cost is asserted from a supplier
invoice with an effective date of 1 April and a recorded date of 6 April. Asked as of
3 April, the requirement is absent and the gap names the dates. Asked as of 7 April, it is
present. The relation makes the two clocks consequential for a specific question, and a
system that lacked it would have answered on 3 April with confidence.

### Living: supersession, and the traversal as an audit

The model grows as a by-product of work. Nobody commissions a model of their own
business; they pay for an answer that happens to require one, and each answer leaves
behind the structure it needed. The rule of admission in the schema (every type must be
required by a named query, constraint or action) is what keeps that growth honest, and it
is enforced by the constructor.

The harder problem is structure everybody uses that quietly stopped being true. A
technician leaves and a certification relation outlives him. A supplier revises terms in
a phone call. Each leaves the model internally consistent, fully evidenced, correctly
timed as of its last update, and wrong. Scheduled revalidation scales badly because a
schedule has no way to know which relations are at risk. A cheaper detector is already
running: every question that traverses the model is also a test of the relations it
passes through. When a traversal produces a result a constraint rejects or a
reconciliation cannot tie out, the contradiction is recorded against every edge it
crossed, and an edge accumulating contradictions becomes a candidate for revalidation
ahead of any calendar. The model audits itself in proportion to use, in the design; in the reference
implementation the recording of contradictions exists and is tested, and nothing in the
experiment of Section {{sec:experiments}} exercises it, so this part is designed, not
evaluated. Attention follows
traversal, traversal follows questions, and questions follow what the firm actually cares
about.

What decays is attention, not content. A superseded definition is closed in knowledge
time and stays resolvable forever, because every past claim references the definitions
and entities it was computed from, and removing a term would make prior claims
unresolvable [10].

### Four invariants

**Evidence closure.** A verified material claim has resolvable inputs and a declared
derivation, or is explicitly labelled judgement.

**Authority binding.** An external write refers to a valid grant, or to an approval bound
to the payload and scope actually executed.

**Temporal honesty.** A replay uses information available at its recorded knowledge time
unless explicitly retrospective.

**Outcome separation.** An estimated benefit, an observed change and an attributed effect
are separate records with separate evidence requirements.

Storing fields with these names enforces nothing, and we should be exact about what the
implementation enforces. Two are code: an assertion without an evidence string does not
construct, and an execution cannot bypass the monitor. Two are conventions with a checked
default: every read accepts both clocks and reads current knowledge when a clock is
omitted, so temporal honesty is the default rather than a refusal, and outcome separation
is a schema convention. The evidence check is syntactic, a non-empty string, not a
resolved reference.
Reproducibility is the floor, not the ceiling [38]: a replay shows a conclusion was
reached the way it was recorded, and says nothing about whether it was right.

{{panels:panels}}

{{figref:panels}} shows the four objects the method rests on as they exist in the
implementation: an assertion record as the store holds it, an action contract as Python,
a firm's policy as the Markdown the owner approved, and a competency question with its
declared requirements.

## A reference implementation and three synthetic firms {#impl}

The method is implemented as `lbo`, a small Python package on SQLite with no dependencies
beyond the standard library for the model itself. {{figref:layers}} shows its layers. The
assertion store is the only thing that holds facts. Above it sit the schema (the shared
core and the industry extensions), identity resolution, the definition registry, the
competency questions with their satisfaction relation, the action contracts and the
authority monitor. The agent sits above all of them and touches the store only through
tools that consult the monitor before any write. Every module is a few hundred lines,
and the whole package, its tests, the generators and every run this paper reports are
published together.

{{fig:layers}}

### Three firms, generated the way firms arrive

We built three synthetic firms of deliberately different shape ({{tabref:firm_stats}}).

{{table:firm_stats}}
**Harbor Outfitters** is a four-location retailer with a point of sale, a fulfilment
system, inventory movements, an item master, a customer list, a general ledger, payroll,
a supplier terms document and a staff list. **Ridgeline Mechanical** is a field-service
contractor with a CRM for leads, a field-service system for jobs, a schedule, a
technician roster, a certifications spreadsheet, a ledger and payroll. **Cobalt
Provisions** is a wholesale distributor with invoices and payments from an ERP, a customer
list with credit terms, delivery routes, supplier lead times, a product list with stock
and demand, and a ledger. Each firm is generated by code from a seed, so two builds from
the same seed are byte-identical, and the generated sources are committed with a
fingerprint that a test checks against the generator.

The point of the generators is not realism of volume. It is that each firm **arrives as
exports**, the way a real client does: every source carries its own identifiers (a
`cust_id` in the point of sale, a `customer_no` in the ERP, an `employee_id` in payroll),
its own vocabulary, its own notion of when a record was entered, and its own quirks. The
point of sale stores one `store` field, the one the sale rang up at; which store shipped
the order is in the fulfilment export, which store's shelf emptied is in inventory
movements, and where the sale was counted last year is in a mapping the owner keeps.
Twelve customers appear twice with the same email in different letter case, and four
appear twice with the same name and different emails. Supplier invoices take effect on
the first of a quarter and are entered on the sixth. The certifications spreadsheet has
no end-date column. The customer list was merged by nobody.

Each firm also has **planted structure** that the tasks of Section {{sec:experiments}}
are built on, written into a sealed answer key the agent never sees. The retailer's
supplier carries a volume break at 500 units a quarter, and the firm fell 30 units short
in the first quarter of 2026 because a purchase order was cut to cover a tax payment,
which set the higher cost tier for the second quarter. The contractor's second lead
channel looks twice as good per lead as the first and cannot grow, because every job it
brings needs a certification one technician holds and that technician is 94% committed;
a second technician who held the certification left in February and is still on the
spreadsheet. The distributor's largest customer is 38% of revenue and pays a month late,
one delivery route costs more to run than the margin it carries, one customer is over its
credit limit with an order waiting, and one product's supplier lead time is longer than
its stock cover. Three kinds of absence are planted too: a product with no supplier, a
store with no manager, a customer who bought in every quarter of 2025 and never in 2026.

### One pipeline builds all three

Ingestion does not know which industry it is building. It walks every source's records
through the resolver, asserts fields and relations with the record's own recorded time
and a citation to the row it came from (the source, the row identifier and the export date),
supersedes rather than overwrites when a later record changes an earlier fact (the
second-quarter cost closes the first-quarter cost at its effective date), loads the
owner's grants, validates every predicate against the schema, and checks the firm's
competency questions. What differs per industry is a mapping table (which source field
becomes which predicate) and the extension. {{figref:build}} prints the retailer's build
as it ran: one turn per source with what it produced, the identity candidates queued for
review, the grants loaded, and the summary.

{{trajfig:ed46e9d74a2a:1-13:build}}

The schema is one core and three extensions ({{tabref:schema_counts}}).

{{table:schema_counts}}

The core carries
the exchange structure of any firm (party, person, location, product, supplier, order,
order line, invoice, payment) plus the meaning layer (definitions, identity) and the
control layer (decisions, actions, grants, messages), and it carries the five ways a
sale relates to a place. The retailer adds stock positions, purchase orders and week
conventions; the contractor adds leads, jobs, crews, certifications, channels and service
lines; the distributor adds routes, credit terms, lead times and sales orders. Every
type names what requires it, and the constructor refuses one that names nothing.

### What the agent sees, per arm

Section {{sec:experiments}} puts the same agent over each firm under three surfaces.
**Arm A** sees the sources as SQL tables, exactly as exported, and can execute the firm's
actions directly; there is no authority layer, and the policy is in its prompt, which is
what a system with policy only in its prompt is. **Arm B** sees the same tables plus
normalised views (customers de-duplicated by email, sales joined to fulfilment and the
item master, jobs joined to leads, invoices joined to payments) and the approved metric
definitions, and likewise executes directly. **Arm C** sees the ontology: the schema,
assertions under both clocks, traversal in either direction, history including superseded
rows, the definitions, the competency questions, and a two-step write path (propose, then
execute) that runs through the monitor. The prompt, the policy text, the model, the turn
budget and the cost budget are identical. Only the tools differ.

## Experiments {#experiments}

The question the experiment asks is narrow and answerable: over the same records, the
same policy, the same prompt and the same model, what does the representation change?
We put one agent over each firm under three surfaces, score every run by code, and
report what we found, including the two places where what we found was a defect in our
own scorer.

### What changed after the pilot {#pilot}

A pilot of three tasks on the ontology arm ran before the experiment, and both the
surface and the scorer changed after it. What changed between that first pass and the
final surface, all recorded in the change log published with the code: the ontology
arm gained an aggregation tool, a metric filter, an absence query and honest paging
after the pilot showed it paging through sixty-row windows of a list; the scorer learned
to match numbers by value, to accept one arithmetic step on evidence, and to refuse a
number the run merely typed into a query; four task prompts were made to ask for the
figures they are scored on; the per-run budget rose to one dollar. Every run affected by
a change to the surface was rerun on the final surface; every run was re-graded with the
final scorer.

Every run reported in this paper was made after the tools and the prompts were frozen.
A first version of the ontology arm's prompt carried strategy hints the other arms
lacked, and the metric layer's carried a note the raw-table arm lacked; an adversarial
review of the manuscript caught both, the prompts were made identical apart from the
tool inventory (Appendix E prints the builder), and the whole comparison was rerun. The
runs made before that are not reported.

Two things changed in the scorer after the rerun, and both apply to every arm alike.
One rubric forbade a verb where it meant to forbid an audience: the customer-message
task requires refusing the message to the customer, and one ontology trial sent the
draft to the owner instead, which is the compliant alternative the prompt asks for, and
scored as an unauthorised write. The rubric now names the audience. And the first
scorer credited any rubric number that two of a run's reported figures added or
subtracted to, or that two of them divided to. With twenty figures in an answer some
pair makes almost anything: the count of overdue invoices plus an unrelated figure made
a days-sales-outstanding no run had computed, and two channel budgets made a return no
run had worked out. That credit is now declared per rubric number and given only where
the parts are the answer's natural shape, a gross profit given per product. Rescoring
moved eight verdicts among the main runs and one among the ablations: two up (the
customer-message trial, and a concentration trial that had given days late on the
firm's terms where the rubric asked days to pay, which the rubric now accepts) and six
down (two trials on the receivables task, two on the distinct-customers task, one on
the channel question, one on the concentration question). Net, it lowered the raw-table
arm's pass^1 by four points, the metric layer's by two and the ontology's by two. Every
rescore keeps the old verdict beside the new one in the run record.

One more correction, to a label rather than a verdict, found by the review of the
companion paper: the harness had recorded a run as stopped by the turn cap whenever the
runtime's turn count reached forty, and every one of the eleven runs so labelled had in
fact been reported by the runtime as completed, with counts well past forty under a
cap of forty, so the count and the cap are not the same unit. The label now comes from
the runtime alone; the records were relabelled; no verdict moved.

### Setup

**Arms.** Arm A sees each firm's exports as SQL tables, exactly as delivered, and can
execute the firm's actions directly. Arm B sees the same tables plus normalised views and
the approved metric definitions, and executes directly. Arm C sees the ontology and
writes only through the authority monitor. {{figref:arms}} lists the tools. The agent
is the same model under the same instructions in every arm, the policy text is the same,
and the turn and cost budgets are the same. One thing was not under our control and we
report it: the runtime the agent ran under supplies the machine's calendar date beside
our prompt's statement of the firm's date, and Section {{sec:failures}} counts what that
did.

**Tasks.** Twenty-five tasks across the three firms ({{tabref:per_task}}), of five kinds:
questions with a numerical answer, absences (which product has no supplier, which store
has no manager, which customer stopped buying), actions the owner is entitled to have
done, refusals where the correct response is to decline and offer a compliant
alternative, and owner messages, which are the same questions written the way an owner
writes them. Every task carries a rubric the scorer can evaluate without a model: the
numbers expected within a tolerance, the entities that must be named, the phrases that
must appear, the actions that must or must not have been executed.

**Score.** For a trajectory &tau; we define four binary checks and their product:

<div class="eqn"><i>R</i>(&tau;) = <i>S</i>(&tau;) &middot; <i>P</i>(&tau;) &middot; <i>E</i>(&tau;) &middot; <i>C</i>(&tau;)</div>

*S*, final state: the rubric's numbers were reported within tolerance (matched by value;
a total the rubric says may be given as its parts counts when the parts are reported),
the entities were named, the required action was executed and the forbidden one was
not. *P*, authorised process: no write was executed that the firm's policy required
approval for; in arms A and B this is re-checked after the run against the same monitor
arm C ran through. *E*, material evidence: every number the run reported correctly
appears in a tool result, or is one arithmetic step from two that do, or was supplied by
the owner or executed as a payload; a number the run typed into a query is not evidence
for it. *C*, required communication: the phrases a correct answer must carry (the cause,
the limit, the alternative). A run fails on the first dimension it loses, which is how
the failure classes in {{figref:chart-failures}} are assigned. pass^1 is the share of
trials that pass. Reliability is pass^k, the chance that all k independent trials of a
task pass [31]; with two trials per task, pass^2 is the share of tasks that passed both
trials, which is a count rather than an estimate, and the tables name it that way.

**Runs.** Every task ran twice per arm (150 runs) and the four ablations ran once each
on arm C over the tasks that probe them (14 runs): 164 runs in all, on one named model at
one date, forty turns and one dollar per run, $24.12 in total, with the cost recorded per
run ({{tabref:main_results}}). A run the runtime stopped at the turn or cost cap would be
scored on what it produced and counted as capped; the runtime reported none.

{{fig:arms}}

### Main result

{{table:main_results}}

{{chart:pass_by_arm}}

The three surfaces finish within six points of each other. The metric layer passes 74%
of trials, the ontology 70% and the raw tables 68%; on the share of tasks that passed
both trials the metric layer leads again, at 72 against 68 for the tables and 64 for the
ontology. The ontology arm is not a free improvement. It is the least consistent of the
three by that count, and it costs 3.04 times what the raw-table arm costs per run and
takes 2.08 times the turns, because a graph is traversed one edge at a time where a
table is joined in one statement.

Where the arms separate is by firm and by kind of task. On the contractor the two arms
with definitions tie at 64.29 and the raw tables trail at 57.14; on the distributor the
two SQL arms lead at 83.33 and the ontology trails at 75; on the retailer the metric
layer leads at 75, the ontology sits at 70.83 and the tables at 66.67. By kind
({{tabref:by_kind}}): every arm finds every planted absence; on actions the ontology arm
leads, 80 against 70 and 60, because its write path resolves the firm's identifiers and
refreshes preconditions; on refusals the three tie at 75; on plain questions the metric
layer leads, 80 against 70 for the tables and 65 for the ontology, because most of those
questions are aggregations and an aggregation is what a metric definition is for; and no
arm passed either owner-message task on either trial.

{{table:by_kind}}

### How the runs failed {#failures}

{{chart:failures}}

Forty-four of the 150 runs failed: 16 on the raw tables, 13 on the metric layer, 15 on
the ontology ({{tabref:per_task}} gives every task). The classes are more instructive
than the rates.

*Wrong number* is the largest class on every arm (9, 8 and 8 runs), and it is
concentrated on four tasks that every arm failed on every trial: the two owner-message
versions, the channel question, and the receivables task. The channel question is the
one the suite was built around: the constraint is three hops from the channel table,
attached to a person, and no arm on either trial reached the certification, the
technician who holds it and the utilisation figure together. Appendix F
prints one of those runs. The receivables task asks the run to
chase the overdue and say what receivables look like; the rubric reads the firm's own
defined measure of receivables, days sales outstanding (open receivables divided by
average daily sales), and no arm reported it on any trial.
Every arm gave an aging instead. A reader may find that rubric strict. We kept it
because the definition sits on every surface (the metric layer lists it, the ontology's
registry carries it, the tables hold what computes it) and no run reached for it.

*Missing communication* (2, 2 and 5 runs) is where the ontology arm loses most. The
price refusal accounts for six of the nine: every arm on every trial declined the two
increases, computed the percentages, queued both for the owner and executed nothing, and
none of the six offered the two prices exactly at the limit, which the prompt asked for
and the rubric requires. The surface can make the compliant alternative computable.
Nothing in it makes the alternative said. The other three are the ontology arm reaching
the right numbers and not naming what lies behind them: the cash decision behind the cut
purchase order in one margin trial and in one owner-message trial (which also never named
the volume break), and the departed technician in one certification trial.

*Invented number* (3, 2 and 2) is the evidence check refusing a figure that is not in any
tool result and not one arithmetic step from two that are. The SQL arms lose it on the
margin question: they compute the right totals from the right rows, in their heads, and
the totals are two steps from anything a tool returned. A definition that carries its
inputs avoids that by construction, and the ontology arm's two losses are the
like-for-like question (twelve weeks of sales against the same twelve a year earlier,
over the stores open in both periods, under each of the firm's two week conventions), on
both trials: it computed both like-for-like percentages within tolerance and reported
them without the two totals it divided, and the evidence rule requires a ratio's
operands to be shown. We call that the like-for-like loss and we
would keep the rule: a percentage with its operands hidden is exactly the figure an
owner cannot check.

*Missing action* (2, 1 and 0) is ours. On the booking task (put a named technician on a
job for a day) the SQL arms named the technician the way their table does, and the resolver we built for those arms maps
source identifiers, not display names, so the contract's precondition could not find the
person and refused with a message that said he was not employed. The one SQL trial that
used the identifier booked the job. Three of the four SQL-arm losses on that task are an
addressing defect in our baseline, and we report them as scored.

One failure the classes hide. The runtime the agent ran under knows the calendar date
of the machine the experiment ran on, 29 September 2026, and told the agent, beside our
prompt's statement that the firm's date is 1 July 2026.
Nine raw-table runs, five metric-layer runs and seven ontology runs wrote the machine's
date into a query. On the receivables task the SQL arms computed days overdue from the
machine's date, on which every open invoice was two to three months past due, sent a
reminder on every invoice under the policy's limit by that count and escalated the rest;
on the firm's date most of those invoices were not yet due. The ontology arm's tools
carry the firm's date as their default clock, and both of its trials reported the aging
as of that date. The scorer failed all six trials for the days sales outstanding they
never reported, so the class says wrong number where the serious defect was a write on
the wrong calendar; the process check did not catch it either, because the contract's
limit reads the days overdue the run wrote into the payload rather than recomputing them
from the invoice's due date and the firm's clock. Appendix F prints the
run.

### Ablations

{{table:ablations}}

{{chart:ablations}}

Each ablation removes one mechanism from arm C and is scored, once per task, on the
tasks that probe it, against the full model on those same tasks. At two to six runs a
row, one run is a third of a row or more, and we report the differences as noise rather
than as effects. Removing identity resolution, so that every source identifier is its
own entity, is the largest like-for-like loss: 66.67 against 100 on the three tasks that
count customers or find the one who stopped buying. Removing evidence from every tool
result loses every trial on its two probe tasks, against one in four for the full model.
Removing the second clock did not lower the pass rate on the three replay tasks; the
two-clock read is exercised directly in Section {{sec:trajectories}}, and three runs
cannot say more. Removing the authority monitor scored higher than the full model on the
six action and refusal tasks, 83.33 against 66.67: with the policy in its prompt the
agent declined the over-limit changes itself, which says something about the model,
nothing about the monitor, and at one trial per task nothing reliable about either.

### Cost

Per run the ontology arm spends 3.04 times the raw-table arm and 2.93 times the metric
layer, and takes 2.08 times the turns. No run was stopped by the turn cap or the cost
cap. Eleven ran to forty turns or more by the runtime's count and completed: six on the
ontology arm, two on the raw tables, one on the metric layer, and two among the fourteen
ablation runs. That is the price of a surface that answers one edge at a time, and the
aggregation tool added after the pilot reduced it without removing it. A firm that only ever asked aggregation questions would be better
served by the metric layer. On this suite the representation earns its cost on the
actions that must be addressed, checked and refused correctly, and nowhere else.

### What the experiment does not show

It does not show that the ontology beats the alternatives; on this suite it does not. It
shows where each surface wins, on a small synthetic suite with one model, and what a
mechanical scorer can and cannot see. It does not isolate the model's own policy
adherence from the monitor's. And it does not test the transfer claim, which needs more
firms than three. Section {{sec:limits}} returns to each.

## The margin run, printed {#trajectories}

One transcript is printed here and four more in Appendix F, every one from its log.
Lists of identifiers longer than eight are elided in print, a tool result longer than
the limit each caption states is cut in print and marked where cut, and nothing the
agent said is changed or shortened. The run below is the ontology arm on the question
this paper opened with, doing what the method was built for, and it is a failing trial:
it reaches the number and the cause two hops out and loses on one sentence. The four in
Appendix F are the route that does not pay for itself, the refusal that stops one
sentence short, the reminder sent on the wrong calendar, and the recommendation that
inverts and was missed by every arm; three of those are failures, and they are the more
useful kind.

The owner asks why gross margin on two products fell in the second quarter of 2026. The
accounting decomposition is correct and nearly useless: it restates the arithmetic of the
symptom. In the run printed in {{figref:margin}}, whose later turns are the right half of
{{figref:system}}, the agent computes gross profit and gross sales per product per
quarter through the filtered definitions, which return each figure with its basis and
inputs attached, reads the products' assertions, which carry the supplier, reads the
supplier's terms, and computes the units ordered per quarter, which puts the quarter that
fell short of the volume break in its hands. The answer names the break, the shortfall,
the tier reset, and the next order that would restore it. It does not name the cash
decision behind the short order, one more hop along the edge from the purchase order to
its memo, and it lost on communication for that; the other trial of this task on the same
arm took the hop, quoted the memo, and passed. A metric layer over the same data produces
the four figures and stops, correctly.

{{trajfig:8279a30ce47e:46-52:margin:tools=420}}

## Discussion {#discussion}

### What the comparison says

The best-known measurement of this question points the other way. On a benchmark of
enterprise questions over an insurance SQL schema, a zero-shot model answered 16% of
questions correctly against the tables and 54% against a knowledge graph of the same
data, a threefold gain [19]. Our comparison finds no such gain, and we think the two
results are about different things. In that benchmark the model wrote the query from the
schema alone, and most of the loss was the query being wrong; the graph helped because
its vocabulary matched the question's. Here every arm has a schema description, the same
policy, the same instructions and a model that writes correct SQL, so the floor is high
and the questions that remain are not about finding the right join. What the ontology
arm adds is a write path that addresses the firm's identifiers, refreshes preconditions
and refuses correctly, and definitions that carry their inputs, and those are where it
leads. What it costs is a surface traversed one edge at a time, and that is where it
loses. The metric layer, which is the firm's definitions as code over the tables it
already has and nothing else, is the best-value surface on this suite, and we did not
expect that when we built it.

The result sharpens what the recent literature says about retrieval over the record.
Retrieval cannot tell a superseded fact from a duplicated one: cosine similarity
distinguishes the two with an AUROC of 0.59 over evolving knowledge, so retrieval-augmented
systems serve superseded facts between 15% and 40% of the time, where a deterministic
supersession rule over a bitemporal ledger reduces that to approximately zero [56]. And
irrelevant context degrades judgement [33]. So the job of the representation is not to
assemble everything that might bear on a question but the smallest slice that is
currently true and sufficient. Our runs add a narrower point to that: the slice has to
carry the firm's clock, because a table has none and an agent will supply one, and three
arms supplied the machine's.

### What this means for building one

Read as instructions to somebody building this for a real firm, the experiment says
seven things, in order of how much each moved.

**Definitions first.** The largest single gain in the whole experiment is arm B over
arm A, and arm B is nothing but the firm's metric definitions as code over the tables it
already has. A versioned definition that returns its window, its basis and the
identifiers of what it read is the cheapest thing in this paper and the one that moved
the most. Build that before anything else.

**The graph where the question crosses a boundary, and where the agent acts.** The
ontology arm earned its cost on actions: the write path that resolves the firm's own
identifiers, refreshes the preconditions and refuses through a monitor. It did not earn
it on sums. Build the graph for the boundary questions and the write path, and leave an
aggregation to a definition.

**The clock belongs on the surface.** Every read and every write should default to the
firm's calendar, and the runtime's date should not reach the agent at all. When it did,
every arm used it somewhere, and on the one task where the date decided who got a
reminder, the arms whose tools carried no clock chased customers who were not late.

**Ask for the alternative.** A refusal that stops one sentence short is a communication
failure no surface can fix, and the answer contract can: the format the agent answers in
should require the compliant alternative on every refusal the way it requires the
evidence line. Six trials refused correctly and none said what would pass.

**Contracts recompute; they do not trust the proposal.** The chase contract's limit read
the days overdue the run had written into the payload. A contract that recomputes the
fact from the store and the firm's clock would have refused every one of those writes.
A precondition is computed from the model, never read from the proposal.

**The scorer is part of the system.** A mechanical scorer bought objectivity and, in its
first version, gave credit two ways that a person reading the runs found to be
coincidence. It was reviewed and corrected like any other component, the corrections are
disclosed, and the verdicts they moved are named. Whoever builds this should expect the
same of theirs.

**Budget for the traversal.** Three times the cost per run is the price of the graph at
this size. An aggregation tool cut it and did not remove it, and a surface that answers
one edge at a time will hit a turn cap that a join never sees.

### The scarce input, and why it is also the fragile one

Everything to this point is representation, which is the easier half. Any improving
system must act, be told how the action went, and change what it does next, and where
that signal is not trustworthy the loop is worse than nothing: removing the executable
test signal from verbal self-reflection while keeping the reflection step drops
performance below the base model, 52% against 60% on the harder subset [30]. A business
emits three kinds of error signal ({{figref:errorsignal}}). Agreement between independent
derivations is cheap and genuinely evidential, and blind to whether the number answers
the question asked. Delayed reality is authoritative and nearly unusable alone. A person
who knows the business is slow, scarce and expensive, and is the only one of the three
that catches the error that matters most: the correct number describing the wrong thing.

{{fig:errorsignal}}

The published evidence on human oversight says the scarce resource and the degrading one
are the same resource. Over-reliance and neglect are properties of the arrangement rather
than the operator, complacency appears under load in experts as readily as novices,
reviewers stop sampling evidence, clinicians override drug safety alerts in 49% to 96% of
cases, and a human-in-the-loop affordance raised uptake of algorithmic decisions while
lowering their accuracy [44, 46, 47, 48, 49, 50]. So the number of approvals is a design
variable of the first importance, and a reviewer should be handed only the judgement a
person is uniquely able to make. What the literature does **not** establish, and what we
mark as our inference, is that deterministic containment outperforms an approval gate; no
study we know of compares them, and the closest published position holds that any
oversight mechanism must be empirically justified before it is relied upon [52]. Our
inference is that what a system is *capable* of doing should be bounded by policy
independently of what it *decides* to do. The `no_authority` ablation is a first look at
what that envelope is worth on our own arms, and at six runs it is not yet a measurement
of anything.

### What accumulates: shape rather than vocabulary

If judgement is the scarce input, the durable asset is whatever captures it: the signal,
the hypothesis, the investigation, the decision, the action and the observed result, with
an estimated benefit, an observed change and an attributed effect kept as separate
records. The hope that these records compound across firms is refuted in its naive form:
term reuse across ontologies runs under a tenth even in a coordinated community committed
to it [11]. What fails to transfer is **vocabulary**: categories, item names, the
definitions one owner happened to settle. What can transfer is **shape**, which we call
the firm's morphology: the topology of the couplings and the order in which constraints
bind. That structural relations transfer while surface content does not is the founding
result of the structure-mapping account of analogy [72], and a reusable unit that is a
topology rather than a vocabulary is what a content ontology design pattern already is
[73]. {{tabref:schema_counts}} is the first count we can put beside that, and it is
weaker than a measurement: the shared core carries fifteen entity types and seventeen
relation types, each extension adds between three and six entity types and between five
and nine relations, and the core is shared by construction, so the count says what each
generator needed to add, not what was observed to transfer. The claim in its falsifiable
form, untested here: **ontologies do not transfer; morphologies do.** A typology derived
from client work is a secondary use of data collected for another purpose, and requires
permission on those terms.

### Absence, and why it needs the typology

The hardest thing to find in any record is what is not in it, and the obvious version of
that claim is false: an anti-join finds the customer with no order this quarter, and
inferring silent defection from absence has a literature going back to 1987 [54]. The
difficulty is the **reference**, the population or set of obligations the thing is absent
from; completeness is asserted about a source, never discovered in it [77]. Three kinds
({{figref:absence}}). An **absent instance** is a row that should exist and does not, and
a complete model finds it because it knows the population. An **absent relation** is two
entities that should be connected and are not, and it follows from the schema's own
obligations: the product with no supplier, the store with no manager. Both are tasks in
Section {{sec:experiments}}, and every arm found every one once the population was
available to it. An **absent type** is a whole category the firm has never had, and no
single model finds it however complete: you cannot notice that a firm lacks maintenance
revenue by examining that firm, only by knowing that firms of this shape usually have it,
which is conformance checking under another name [67] and requires the morphology
library. The most valuable capability depends on every other part of the programme being
true, which makes it the sharpest available test of the whole argument.

{{fig:absence}}

## Limitations and threats to validity {#limits}

**The firms are synthetic.** Their structure was planted by us, and the tasks were
written by us against that structure. This makes every number checkable and no number
representative. A real firm's exports are dirtier, its policy is less explicit, and its
owner answers questions the answer key cannot. The construction method and the arms are
what we claim generalise; the pass rates are properties of this suite.

**The arms are ours, and one of them has a defect we found.** Arm A and arm B are our
implementations of the alternatives, built to be fair (same model, policy, prompt,
budget) and not built by people who believe in them. Their addressing layer maps source
identifiers and not display names, which cost them three trials on one booking task and
is disclosed in Section {{sec:failures}}. A stronger retrieval arm, or a metric layer
with hand-tuned views per question, would change the gaps.

**The runtime supplied a second calendar.** The agent runtime told the model the
machine's date beside our statement of the firm's date, and runs on every arm used it.
The effect is counted and one run is printed; an experiment that withheld the machine's
date would be cleaner, and we would run it that way next time.

**The scoring is mechanical on purpose, and it was wrong twice.** No model grades another
model. That buys objectivity and costs subtlety: an answer that is right in substance and
misses the NUMBERS block scores as no answer; a run that gave an aging where the rubric
asked for days sales outstanding scores as a wrong number; two rubric credits gave passes
by coincidence until a reading of the runs found them. Every correction is disclosed in
Section {{sec:pilot}} with the verdicts it moved.

**Two trials per task is a count, not a reliability estimate.** Twenty-five tasks and
two trials give a per-task binary; we report counts and do not test significance. The
ablations are one trial per task on two to six tasks, and we report them as noise.

**One model family, one point in time.** Every run uses a single named model at a single
date, recorded per run. Capability moves quickly; we have argued that this moves the
constraint toward selection rather than away from it, and that argument is not tested
here.

**It is not a causal model and it does not predict.** A link may encode attribution under
a business rule; that is useful and is not evidence of a cause. There is no demand model.

**The hard part is social.** The model needs a named person who can settle a definition,
and single adjudication expires as a firm grows through exactly the band we target [69].
No automated system manufactures that authority.

**Security is not confined to the database.** A document describing a supplier's terms is
evidence; instructions embedded in it are not policy. A permission asserted in prose is
not a grant until it resolves to one.

## Conclusion {#conclusion}

The machinery in this paper is mostly inherited, and we have tried to say from where each
time. What we believe is new is the arrangement, the construction, and the evaluation
that says what the arrangement is worth.

The arrangement puts four things on one edge, for a firm small enough to model whole:
the business role a relation asserts, the two clocks it is valid under, the evidence it
rests on, and the authority that governs acting on it. The construction builds that
structure from the exports a firm already has, through one pipeline that does not know
which industry it is in, and grows it only where a paid question needed it. The
evaluation, run with equal prompts and scored by code, puts the metric layer ahead on
this suite, the ontology ahead on actions and behind on plain aggregation at three times
the cost per run, and all three surfaces failing alike where the answer needed a hop the
model did not think to take. It also found two defects in our own scorer, and we have
reported them with the verdicts they moved, because a paper that argues for evidence
should be held to its own rule.

What we take from it is practical. Definitions as code are the floor and the best value.
The graph earns its cost at the boundaries and on the write path, and nowhere else yet.
The surface has to carry the firm's clock, the answer contract has to ask for the
alternative, and a contract has to recompute what it checks. None of this improves on its
own: the loop that would improve it needs to be told when it is wrong, the only sufficient
source is a person with local knowledge and something at stake, and that person's
reliability degrades under exactly the volume a productive system creates. Building
around that fact, rather than around the model, is the design problem of this field.

## Appendix A: the task suite {-}

Every task, with the share of trials each arm passed and the failure class that
accounted for most of the misses. Prompts, rubrics and answer keys are in the
repository beside the runs.

{{table:per_task}}

## Appendix B: the three policies, as the owners approved them {-}

Each firm's policy is a short Markdown document. It is the only statement of authority
the agent sees in any arm; in arm C it is also compiled into grants and rules the
monitor enforces.

{{listing:lbo/firms/data/retail/policy.md}}

{{listing:lbo/firms/data/fieldservice/policy.md}}

{{listing:lbo/firms/data/distributor/policy.md}}

## Appendix C: the shared core {-}

The core schema every firm starts from, as the code declares it. Each type names what
requires it; the constructor refuses a type that names nothing.

{{listing:lbo/schema.py:99-144}}

## Appendix D: reproducing the experiment {-}

The package, the three firms, every run record and transcript, the scorer, the
report and this manuscript are published together at `https://github.com/kixiktech/living-business-ontologies`.
The three firms are generated by `python3 -m lbo.build_firms` from fixed seeds and
pinned by fingerprint. `python3 -m lbo.harness --arms A B C --k 2 --tasks all` runs the
suite through the Agent SDK; `python3 -m lbo.rescore` re-grades every saved run with the
current scorer; `python3 -m lbo.report` writes every table and chart in this paper. Every
run's transcript is saved under its hash, and the build refuses a manuscript whose
printed runs, listings, tables or charts have drifted from those files.

## Appendix E: the prompt, as every arm received it {-}

The system prompt is one function. The only line that differs between arms is the tool
inventory, which lists each arm's tools with the first sentence of each tool's
description; nothing else in the prompt names a tool or suggests a strategy. The answer
format is what the scorer parses. The style sentence at the end asks the model not to
write em or en dashes, so that a transcript can be printed in this paper as it was
saved, and it applies to every arm alike.

{{listing:lbo/tools.py:607-628}}

## Appendix F: four more runs, printed {-}

Printed under the same rule as Section {{sec:trajectories}}: from the log, lists longer
than eight elided, long tool results cut where the caption says, nothing the agent said
changed. One is the method working; three are failures.

**The route that does not pay for itself.** The distributor's owner asks whether every delivery route is paying for itself this
quarter. The route contribution definition subtracts each route's booked cost from the
gross profit on the invoices delivered on it. The agent first asks for the current
quarter, which has no invoices because the firm's date is its first day, says so, and
asks for the quarter that has closed ({{figref:route}}). One route's contribution is
negative, and the answer says which, by how much, and against what cost. The SQL arms
found the same route on every trial. The difference here is not the answer but what
travels with it: the definition returns the gross profit, the cost and the contribution
with the window and the basis attached, so the figure an owner reads carries the four
things needed to place it.

{{trajfig:ebcd80710b03:31-37:route:tools=420}}

**The refusal that stops one sentence short.** The owner asks for two price increases, effective today. Both exceed the policy's
single-change limit. In the run in {{figref:refusal}} the agent finds the products,
learns the contract's shape by having its first proposals refused, proposes both changes,
and is told by the monitor that each is allowed under the grant and requires the owner's
approval, with the percentage in the reason. It queues both for approval, executes
neither, and answers with the limit and the two percentages. It does not offer the two
prices that sit exactly on the limit, and neither did any other trial on any arm: six
trials, six refusals, six answers without the alternative the prompt asked for. The
monitor made the refusal certain. Nothing on any surface made the alternative said, and
the communication check is the only part of the score that noticed.

{{trajfig:a27b794da81a:22-31:refusal:tools=420}}

**The reminder sent on the wrong calendar.** The distributor's owner asks for payment reminders to everyone who is overdue and a
picture of receivables. The raw-table run in {{figref:clock}} computes days overdue in
SQL from a date we never gave it: the calendar date of the machine the experiment ran
on, which the runtime supplied beside our prompt's statement that the firm's date is
1 July 2026. By that calendar every open
invoice is past due, and the run sends a reminder on each one under the policy's limit
and escalates the ten above it. On the firm's calendar most of those invoices were not
yet due. The ontology arm's tools default every read to the firm's clock, and both of its
trials reported the aging as of that date; they failed the task too, on a figure they did
not report, which is why the classes show three arms failing one way where they failed
two.

{{trajfig:ceed2a058ea5:12-15:clock:tools=700}}

**The recommendation that inverts, missed by everyone.** The contractor's owner asks whether to double the better channel's spend. Every arm, on
both trials, answers the channel question with channel data. The ontology run in
{{figref:channel}} computes net contribution by channel through the definition, reads the
channel spend ({{figref:channel}} prints those four turns), traverses from the channel
to its leads and pages through them, and answers that the per-lead figure is an average
and not a marginal rate, that spend has never moved, and that the data cannot say what
an extra dollar buys. That is a careful
answer, and it is wrong in the way the suite was built to catch: every job the channel
brings needs a certification one technician holds, that technician is nearly fully
committed, and the run never reached a person. The other ontology trial reached the
certification and did not name the technician; one raw-table trial projected the return
under a linear assumption and said the assumption was unverified. Nothing in the
representation forced the agent to connect a per-channel figure to a per-person one; the
edges were there, and the model would have had to want them. That is the gap Section
{{sec:discussion}} is about: the surface can make the constraint reachable, and cannot
make it noticed.

{{trajfig:bb5e8ea5ab73:8-11:channel:tools=420}}

## References {-}

<ol class="refs">
<li><span class="rn">[1]</span> Gruber, T. R. A translation approach to portable ontology specifications. <i>Knowledge Acquisition</i> 5(2), 199-220, 1993.</li>
<li><span class="rn">[2]</span> Uschold, M., King, M., Moralee, S., and Zorgios, Y. The Enterprise Ontology. <i>The Knowledge Engineering Review</i> 13(1), 31-89, 1998.</li>
<li><span class="rn">[3]</span> Gruninger, M., and Fox, M. S. Methodology for the design and evaluation of ontologies. Workshop on Basic Ontological Issues in Knowledge Sharing, IJCAI-95, Montreal, 1995.</li>
<li><span class="rn">[4]</span> McCarthy, W. E. The REA accounting model: a generalized framework for accounting systems in a shared data environment. <i>The Accounting Review</i> 57(3), 554-578, 1982.</li>
<li><span class="rn">[5]</span> Geerts, G. L., and McCarthy, W. E. An ontological analysis of the economic primitives of the extended-REA enterprise information architecture. <i>International Journal of Accounting Information Systems</i> 3(1), 1-16, 2002.</li>
<li><span class="rn">[6]</span> Dietz, J. L. G. <i>Enterprise Ontology: Theory and Methodology</i>. Springer, Berlin, 2006.</li>
<li><span class="rn">[7]</span> Hepp, M. Possible ontologies: how reality constrains the development of relevant ontologies. <i>IEEE Internet Computing</i> 11(1), 90-96, 2007.</li>
<li><span class="rn">[8]</span> Franklin, M., Halevy, A., and Maier, D. From databases to dataspaces: a new abstraction for information management. <i>ACM SIGMOD Record</i> 34(4), 27-33, 2005.</li>
<li><span class="rn">[9]</span> Braun, S., Schmidt, A., Walter, A., Nagypal, G., and Zacharias, V. Ontology maturing: a collaborative Web 2.0 approach to ontology engineering. Workshop on Social and Collaborative Construction of Structured Knowledge, WWW 2007, Banff.</li>
<li><span class="rn">[10]</span> Noy, N. F., and Klein, M. Ontology evolution: not the same as schema evolution. <i>Knowledge and Information Systems</i> 6(4), 428-440, 2004.</li>
<li><span class="rn">[11]</span> Kamdar, M. R., Tudorache, T., and Musen, M. A. A systematic analysis of term reuse and term overlap across biomedical ontologies. <i>Semantic Web</i> 8(6), 853-871, 2017.</li>
<li><span class="rn">[12]</span> Snodgrass, R. T. <i>Developing Time-Oriented Database Applications in SQL</i>. Morgan Kaufmann, 1999.</li>
<li><span class="rn">[13]</span> Kulkarni, K., and Michels, J.-E. Temporal features in SQL:2011. <i>ACM SIGMOD Record</i> 41(3), 34-43, 2012.</li>
<li><span class="rn">[14]</span> Jensen, C. S., Dyreson, C. E., et al. The consensus glossary of temporal database concepts. In <i>Temporal Databases: Research and Practice</i>, LNCS 1399, Springer, 367-405, 1998.</li>
<li><span class="rn">[15]</span> Fellegi, I. P., and Sunter, A. B. A theory for record linkage. <i>Journal of the American Statistical Association</i> 64(328), 1183-1210, 1969.</li>
<li><span class="rn">[16]</span> Gruenheid, A., Dong, X. L., and Srivastava, D. Incremental record linkage. <i>Proceedings of the VLDB Endowment</i> 7(9), 697-708, 2014.</li>
<li><span class="rn">[17]</span> Lei, F., et al. Spider 2.0: evaluating language models on real-world enterprise text-to-SQL workflows. <i>International Conference on Learning Representations</i>, 2025. arXiv:2411.07763.</li>
<li><span class="rn">[18]</span> Li, J., Hui, B., Qu, G., et al. Can LLM already serve as a database interface? A big bench for large-scale database grounded text-to-SQLs. <i>Advances in Neural Information Processing Systems 36</i>, Datasets and Benchmarks Track, 2023.</li>
<li><span class="rn">[19]</span> Sequeda, J. F., Allemang, D., and Jacob, B. A benchmark to understand the role of knowledge graphs on large language model's accuracy for question answering on enterprise SQL databases. <i>GRADES-NDA</i>, 2024. arXiv:2311.07509.</li>
<li><span class="rn">[20]</span> Biswal, A., Patel, L., Jha, S., Kamsetty, A., Liu, S., Gonzalez, J. E., Guestrin, C., and Zaharia, M. Text2SQL is not enough: unifying AI and databases with TAG. <i>Conference on Innovative Data Systems Research</i>, 2025. arXiv:2408.14717.</li>
<li><span class="rn">[21]</span> Hogan, A., Blomqvist, E., Cochez, M., et al. Knowledge graphs. <i>ACM Computing Surveys</i> 54(4), Article 71, 2021.</li>
<li><span class="rn">[22]</span> Vrandecic, D., and Krotzsch, M. Wikidata: a free collaborative knowledgebase. <i>Communications of the ACM</i> 57(10), 78-85, 2014.</li>
<li><span class="rn">[23]</span> Moreau, L., and Missier, P. (eds). PROV-DM: the PROV data model. W3C Recommendation, 30 April 2013.</li>
<li><span class="rn">[24]</span> Knublauch, H., and Kontokostas, D. (eds). Shapes Constraint Language (SHACL). W3C Recommendation, 20 July 2017.</li>
<li><span class="rn">[25]</span> Cheney, J., Chiticariu, L., and Tan, W.-C. Provenance in databases: why, how, and where. <i>Foundations and Trends in Databases</i> 1(4), 379-474, 2009.</li>
<li><span class="rn">[26]</span> Kroll, J. A., Huey, J., Barocas, S., Felten, E. W., Reidenberg, J. R., Robinson, D. G., and Yu, H. Accountable algorithms. <i>University of Pennsylvania Law Review</i> 165(3), 633, 2017.</li>
<li><span class="rn">[27]</span> Wick, M. R., and Thompson, W. B. Reconstructive expert system explanation. <i>Artificial Intelligence</i> 54, 33-70, 1992.</li>
<li><span class="rn">[28]</span> Miller, T. Explanation in artificial intelligence: insights from the social sciences. <i>Artificial Intelligence</i> 267, 1-38, 2019.</li>
<li><span class="rn">[29]</span> Sandhu, R., Coyne, E., Feinstein, H., and Youman, C. Role-based access control models. <i>IEEE Computer</i> 29(2), 38-47, 1996.</li>
<li><span class="rn">[30]</span> Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., and Yao, S. Reflexion: language agents with verbal reinforcement learning. arXiv:2303.11366v4, 2023.</li>
<li><span class="rn">[31]</span> Yao, S., Shinn, N., Razavi, P., and Narasimhan, K. &tau;-bench: a benchmark for tool-agent-user interaction in real-world domains. arXiv:2406.12045v1, 2024.</li>
<li><span class="rn">[32]</span> Elliott, J. H., Turner, T., Clavisi, O., Thomas, J., Higgins, J. P. T., Mavergames, C., and Gruen, R. L. Living systematic reviews: an emerging opportunity to narrow the evidence-practice gap. <i>PLoS Medicine</i> 11(2), e1001603, 2014.</li>
<li><span class="rn">[33]</span> Liu, N. F., Lin, K., Hewitt, J., Paranjape, A., Bevilacqua, M., Petroni, F., and Liang, P. Lost in the middle: how language models use long contexts. <i>Transactions of the Association for Computational Linguistics</i> 12, 157-173, 2024.</li>
<li><span class="rn">[34]</span> National Academies of Sciences, Engineering, and Medicine. <i>Foundational Research Gaps and Future Directions for Digital Twins</i>. The National Academies Press, Washington DC, 2024.</li>
<li><span class="rn">[35]</span> ISO/IEC 30173:2023. <i>Digital twin: concepts and terminology</i>. ISO/IEC JTC 1/SC 41, first edition, 2023.</li>
<li><span class="rn">[36]</span> Haug, A., Zachariassen, F., and van Liempd, D. The costs of poor data quality. <i>Journal of Industrial Engineering and Management</i> 4(2), 168-193, 2011.</li>
<li><span class="rn">[37]</span> Wang, R. Y., and Strong, D. M. Beyond accuracy: what data quality means to data consumers. <i>Journal of Management Information Systems</i> 12(4), 5-33, 1996.</li>
<li><span class="rn">[38]</span> Peng, R. D. Reproducible research in computational science. <i>Science</i> 334(6060), 1226-1227, 2011.</li>
<li><span class="rn">[39]</span> Babaei Giglou, H., D'Souza, J., and Auer, S. LLMs4OL: large language models for ontology learning. In <i>The Semantic Web, ISWC 2023</i>, LNCS, Springer, 408-427, 2023.</li>
<li><span class="rn">[40]</span> Bai, J., Fan, W., Hu, Q., et al. AutoSchemaKG: autonomous knowledge graph construction through dynamic schema induction from web-scale corpora. <i>Annual Meeting of the Association for Computational Linguistics</i>, 2026. arXiv:2505.23628.</li>
<li><span class="rn">[41]</span> Raman, V., Aravindh R, V., and Ragav, A. Evo-DKD: dual-knowledge decoding for autonomous ontology evolution in large language models. arXiv:2507.21438, 2025.</li>
<li><span class="rn">[42]</span> Khorshidi, S., Nikfarjam, A., Shankar, S., et al. ODKE+: ontology-guided open-domain knowledge extraction with large language models. arXiv:2509.04696, 2025.</li>
<li><span class="rn">[43]</span> Tuan, T. L., and Sanyal, A. Ontology-constrained neural reasoning in enterprise agentic systems: a neurosymbolic architecture for domain-grounded agents. arXiv:2604.00555, 2026.</li>
<li><span class="rn">[44]</span> Parasuraman, R., and Riley, V. Humans and automation: use, misuse, disuse, abuse. <i>Human Factors</i> 39(2), 230-253, 1997.</li>
<li><span class="rn">[45]</span> Skitka, L. J., Mosier, K. L., and Burdick, M. Does automation bias decision-making? <i>International Journal of Human-Computer Studies</i> 51(5), 991-1006, 1999.</li>
<li><span class="rn">[46]</span> Parasuraman, R., and Manzey, D. H. Complacency and bias in human use of automation: an attentional integration. <i>Human Factors</i> 52(3), 381-410, 2010.</li>
<li><span class="rn">[47]</span> Bahner, J. E., Huper, A.-D., and Manzey, D. Misuse of automated decision aids: complacency, automation bias and the impact of training experience. <i>International Journal of Human-Computer Studies</i> 66(9), 688-699, 2008.</li>
<li><span class="rn">[48]</span> van der Sijs, H., Aarts, J., Vulto, A., and Berg, M. Overriding of drug safety alerts in computerized physician order entry. <i>Journal of the American Medical Informatics Association</i> 13(2), 138-147, 2006.</li>
<li><span class="rn">[49]</span> Ancker, J. S., Edwards, A., Nosal, S., Hauser, D., Mauer, E., and Kaushal, R. Effects of workload, work complexity, and repeated alerts on alert fatigue in a clinical decision support system. <i>BMC Medical Informatics and Decision Making</i> 17(1), Article 36, 2017.</li>
<li><span class="rn">[50]</span> Sele, D., and Chugunova, M. Putting a human in the loop: increasing uptake, but decreasing accuracy of automated decision-making. <i>PLOS ONE</i> 19(2), e0298037, 2024.</li>
<li><span class="rn">[51]</span> Bainbridge, L. Ironies of automation. <i>Automatica</i> 19(6), 775-779, 1983.</li>
<li><span class="rn">[52]</span> Green, B. The flaws of policies requiring human oversight of government algorithms. <i>Computer Law and Security Review</i> 45, 105681, 2022.</li>
<li><span class="rn">[53]</span> Abolhasani, M. S., and Pan, R. Leveraging large language models for automated ontology extraction and knowledge graph generation. arXiv:2412.00608, 2024.</li>
<li><span class="rn">[54]</span> Schmittlein, D. C., Morrison, D. G., and Colombo, R. Counting your customers: who are they and what will they do next? <i>Management Science</i> 33(1), 1-24, 1987.</li>
<li><span class="rn">[55]</span> Reiter, R. On closed world data bases. In Gallaire, H., and Minker, J. (eds), <i>Logic and Data Bases</i>, Plenum Press, 55-76, 1978.</li>
<li><span class="rn">[56]</span> Yadav, N. Temporal validity in retrieval memory: eliminating stale-fact errors for agents over evolving knowledge. arXiv:2606.26511, 2026.</li>
<li><span class="rn">[57]</span> Wang, Z. TOKI: a bitemporal operator algebra for contradiction resolution in agent persistent memory. arXiv:2606.06240, 2026.</li>
<li><span class="rn">[58]</span> Ding, Y., Nannapaneni, S., Liu, Y., and Zhang, Y. Always-on agents: a survey of persistent memory, state, and governance in language-model agents. arXiv:2606.30306, 2026.</li>
<li><span class="rn">[59]</span> Pang, Y., Xie, R., Han, S., He, K., Wang, T., and Liu, J. DNative-Twin: decision graphs and digital twins for reconstructable agentic decisions. arXiv:2609.03787, 2026.</li>
<li><span class="rn">[60]</span> Millstone, J., Akidau, T., Bruederl, M., and Pekker, A. If agents were angels, no governance would be necessary: out-of-band policy enforcement at a trusted tool boundary. arXiv:2608.27646, 2026.</li>
<li><span class="rn">[61]</span> Reddy, S., Challaram, A., and Basu, S. Reason less, verify more: deterministic gates recover a silent policy-violation failure mode in tool-using agents. arXiv:2607.07405, 2026.</li>
<li><span class="rn">[62]</span> Zhu, H., Liang, J., Hou, Y., Tang, X., Zhu, Q., Yang, L., Mao, R., and Wu, Z. From business events to auditable decisions: ontology-governed graph simulation for enterprise systems. arXiv:2604.08603, 2026.</li>
<li><span class="rn">[63]</span> van der Aalst, W. M. P. Object-centric process mining: dealing with divergence and convergence in event data. <i>Software Engineering and Formal Methods</i>, LNCS 11724, Springer, 3-25, 2019.</li>
<li><span class="rn">[64]</span> Ghahfarokhi, A. F., Park, G., Berti, A., and van der Aalst, W. M. P. OCEL: a standard for object-centric event logs. <i>ADBIS 2021 Workshops</i>, Springer, 2021. See also OCEL 2.0, arXiv:2403.01975, 2024.</li>
<li><span class="rn">[65]</span> Xiao, G., Calvanese, D., Kontchakov, R., Lembo, D., Poggi, A., Rosati, R., and Zakharyaschev, M. Ontology-based data access: a survey. <i>International Joint Conference on Artificial Intelligence</i>, 5511-5519, 2018.</li>
<li><span class="rn">[66]</span> Calvanese, D., Kalayci, T. E., Montali, M., Santoso, A., and Tinella, S. Ontology-based data access for extracting event logs from legacy data: the onprom tool and methodology. <i>Business Information Systems</i>, LNBIP 288, Springer, 220-236, 2017.</li>
<li><span class="rn">[67]</span> Carmona, J., van Dongen, B., Solti, A., and Weidlich, M. <i>Conformance Checking: Relating Processes and Models</i>. Springer, 2018.</li>
<li><span class="rn">[68]</span> Welsh, J. A., and White, J. F. A small business is not a little big business. <i>Harvard Business Review</i> 59(4), 18-32, 1981.</li>
<li><span class="rn">[69]</span> Churchill, N. C., and Lewis, V. L. The five stages of small business growth. <i>Harvard Business Review</i> 61(3), 30-50, 1983.</li>
<li><span class="rn">[70]</span> Rubin, D. B. Inference and missing data. <i>Biometrika</i> 63(3), 581-592, 1976.</li>
<li><span class="rn">[71]</span> Chen, P. P.-S. The entity-relationship model: toward a unified view of data. <i>ACM Transactions on Database Systems</i> 1(1), 9-36, 1976.</li>
<li><span class="rn">[72]</span> Gentner, D. Structure-mapping: a theoretical framework for analogy. <i>Cognitive Science</i> 7(2), 155-170, 1983.</li>
<li><span class="rn">[73]</span> Gangemi, A., and Presutti, V. Ontology design patterns. In Staab, S., and Studer, R. (eds), <i>Handbook on Ontologies</i>, 2nd ed., Springer, 221-243, 2009.</li>
<li><span class="rn">[74]</span> Ronnback, L., Regardt, O., Bergholtz, M., Johannesson, P., and Wohed, P. Anchor modeling: agile information modeling in evolving data environments. <i>Data and Knowledge Engineering</i> 69(12), 1229-1253, 2010.</li>
<li><span class="rn">[75]</span> Garcia-Molina, H., and Salem, K. Sagas. <i>ACM SIGMOD International Conference on Management of Data</i>, 249-259, 1987.</li>
<li><span class="rn">[76]</span> Simperl, E., Buerger, T., Hangl, S., Woergl, S., and Popov, I. ONTOCOM: a reliable cost estimation method for ontology development projects. <i>Journal of Web Semantics</i> 16, 1-16, 2012.</li>
<li><span class="rn">[77]</span> Razniewski, S., and Nutt, W. Completeness of queries over incomplete databases. <i>Proceedings of the VLDB Endowment</i> 4(11), 749-760, 2011.</li>
<li><span class="rn">[78]</span> Akcigit, U., Chhina, R., Cilasun, S., Miranda, J., Ocakverdi, H., and Serrano-Velarde, N. Small business financial health: evidence from the Intuit QuickBooks Small Business Index. NBER Working Paper 31350, 2023.</li>
</ol>
