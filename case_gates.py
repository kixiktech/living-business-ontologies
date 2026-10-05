"""Gates for the one defect class a figure-trace cannot see.

WHY THIS EXISTS, IN ONE PARAGRAPH.

The paper argues that agreement between independent derivations "confirms that a number
is the number and is completely blind to whether that number answers the question asked",
and then names the errors only a human catches: a window that flatters, a base that is
gross where the reader hears net. The paper's own test suite recomputed every arithmetic
identity in the three worked cases, passed 57 of 57, and shipped all three of the
following, found by a reviewer reading by hand:

  1. WINDOW.     Case 1 sold 600 units "in a week" while its supplier volume break was
                 500 units "per quarter". That is a firm selling 7,800 units a quarter
                 and ordering 470. The stated action was also impossible: $1,800 was a
                 weekly figure labelled quarterly, and it exceeded its own ceiling.
  2. BASE.       Case 2 defined contribution in its table as net of channel spend
                 ($10,000, so $555.56 a job) and then used $600.00 a job in the prose,
                 which is gross of it. One word, two bases, fourteen lines apart.
  3. POPULATION. Case 2 said "sixteen of B's eighteen jobs" needed the certification and
                 then computed capacity from "eighteen jobs consumed 94%". Two numbers,
                 one population, two sentences apart.

Every one of them passed every check that existed. So these three gates exist, each built
from the defect that motivated it, and each tested against the original broken text rather
than only against the repaired text. A gate that has never been shown to fire is a gate
nobody should trust.

HONEST LIMITS, stated because the paper demands it of everyone else.

These are lexical and structural checks over prose. They cannot understand a sentence.
`check_window_consistency` finds period words and asks whether a case mixes them without
reconciling; it will not notice a window that is consistent and wrong. `check_base_named`
asks whether a per-unit money figure has a base word near it; it cannot tell whether the
base named is the correct one. `check_population_consistency` compares counts attached to
the same noun; it cannot tell which count is right. They catch the shapes that actually
bit us. They are a floor, not a proof, and the stranger read stays required.
"""

from __future__ import annotations

import re

# Period words, and the number-words we write out in prose.
PERIODS = ('week', 'weekly', 'quarter', 'quarterly', 'month', 'monthly',
           'year', 'yearly', 'annual', 'annually', 'day', 'daily')
NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
    'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
    'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
    'nineteen': 19, 'twenty': 20,
}
# Wording that explicitly reconciles two periods, so a mix is deliberate rather than a slip.
RECONCILERS = (
    'per ordering quarter', 'on that one', 'over that same', 'across the quarter',
    'the tier earned in one quarter sets', 'quarterly demand runs',
    'a quarter, and', 'annualis', 'annualiz', 'which is the whole of the gap',
)


def split_cases(markdown: str) -> dict[str, str]:
    """Split the worked-cases section into one block per case, keyed by its heading."""
    body = markdown.split('## Three worked cases', 1)
    if len(body) < 2:
        return {}
    section = body[1].split('\n## ', 1)[0]
    parts = re.split(r'^### (.+)$', section, flags=re.M)[1:]
    return {parts[i].strip(): parts[i + 1] for i in range(0, len(parts) - 1, 2)}


def _strip(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(text.split())


def check_window_consistency(case_name: str, case_text: str) -> list[str]:
    """A case runs on one declared window, or says plainly how two relate.

    Built from defect 1: "sells two products in a week" sitting beside "500 units per
    quarter", which makes the case describe a firm ordering 0.78 weeks of supply.
    """
    flat = _strip(case_text).lower()

    # Only MEASUREMENT windows count. A period word is a measurement window when it is
    # attached to a quantity: "600 units a quarter", "per quarter", "$1,800 a week",
    # "over a quarter". A period word used as a SUBJECT ("two definitions of a week",
    # "the week boundary") or as a comparison ("the prior year") is not a window, and
    # the first version of this gate fired on Case 3 for exactly that reason, where the
    # whole case is ABOUT what a week is. A gate that cries wolf gets switched off.
    windows = set()
    for period in PERIODS:
        for m in re.finditer(rf'\b{period}\b', flat):
            before = flat[max(0, m.start() - 30):m.start()]
            if re.search(r'(per|a|each|every|one)\s+$', before) or \
               re.search(r'(over|within|across|during)\s+(a|the|that|one|same)\s+$', before) or \
               re.search(r'[\d,]+\s+(units?|jobs?)\s+(a|per)\s+$', before):
                root = period.rstrip('ly') if period.endswith('ly') else period
                root = root.replace('annual', 'year').replace('dai', 'day').rstrip('l')
                windows.add(root)
    if len(windows) <= 1:
        return []
    if any(r in flat for r in RECONCILERS):
        return []
    return [f'{case_name}: quantities are stated on more than one window {sorted(windows)} '
            f'with no sentence relating them. Declare one, or state the conversion.']


def check_base_named(case_name: str, case_text: str) -> list[str]:
    """A per-unit money figure names the base it is per-unit OF, nearby.

    Built from defect 2: "$600.00" used for a quantity the table had already defined
    differently, with nothing in the sentence saying which basis applied.
    """
    flat = _strip(case_text)
    out = []
    BASE_WORDS = ('margin', 'contribution', 'gross', 'net', 'before', 'after',
                  'less', 'revenue', 'profit', 'basis', 'base', 'column')
    for m in re.finditer(r'\$[\d,]+(?:\.\d{2})?\s+(?:a|per)\s+(\w+)', flat):
        window = flat[max(0, m.start() - 190): m.end() + 190].lower()
        if not any(b in window for b in BASE_WORDS):
            out.append(f'{case_name}: {m.group(0)!r} gives a rate with no base named '
                       f'within 190 characters. Say what it is measured out of.')
    return out


def check_population_consistency(case_name: str, case_text: str) -> list[str]:
    """Surface every subset-then-whole pattern for a human to confirm.

    Built from defect 3: "Sixteen of B's eighteen jobs are in a service line requiring a
    certification" followed two sentences later by "eighteen jobs consumed 94% of the
    capacity". The capacity belongs to the certified technician, so the computation should
    have used sixteen. Both numbers were correct. The sentence joining them was not.

    This gate deliberately does NOT try to decide which count is right, because that is
    semantic and the paper's own argument is that this class of error is what a human is
    for. It finds the pattern and hands it over: a subset was carved out, and the whole
    population is used again nearby in a computation. Confirm which one the computation
    means. That is a check a reader can act on in ten seconds, and it is exactly the
    ambiguity that shipped.
    """
    flat = _strip(case_text).lower()
    out = []
    COMPUTE_NEAR = ('consumed', 'capacity', 'committed', '%', 'per cent', 'percent',
                    'divided', 'yields', 'brings', 'totals', 'each')
    for m in re.finditer(r'\b(\w+)\s+of\s+[^.]{0,30}?\b(\w+)\s+(\w+s)\b', flat):
        sub_raw, whole_raw, noun = m.group(1), m.group(2), m.group(3)
        if sub_raw not in NUMBER_WORDS or whole_raw not in NUMBER_WORDS:
            continue
        sub, whole = NUMBER_WORDS[sub_raw], NUMBER_WORDS[whole_raw]
        if sub >= whole:
            continue
        for later in re.finditer(rf'\b{whole_raw}\s+{noun}\b', flat):
            if later.start() <= m.end():
                continue
            window = flat[later.start(): later.end() + 120]
            if any(c in window for c in COMPUTE_NEAR):
                out.append(
                    f'{case_name}: {sub} of {whole} {noun} is carved out, then all {whole} '
                    f'{noun} are used in a computation nearby. Confirm which population '
                    f'that computation means.')
                break
    return out


ALL_GATES = (check_window_consistency, check_base_named, check_population_consistency)


def run(markdown: str) -> list[str]:
    """Every gate over every worked case."""
    problems = []
    for name, text in split_cases(markdown).items():
        for gate in ALL_GATES:
            problems += gate(name, text)
    return problems
