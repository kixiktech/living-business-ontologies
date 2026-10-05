"""Conceptual diagrams for the papers, as inline SVG.

House style, chosen to match the reference papers rather than our brand: black on white,
hairline strokes, sans-serif labels, ink and grey for structure. Colour is used sparingly
and only where it carries meaning (a role, an outcome, a layer of the ontology), drawn
from the one palette in `lbo.palette` that also colours the listings and the charts. A
figure here should still read as a diagram in a conference paper, not an illustration.

Geometry. The text measure is 5.7in, about 547px at 96dpi. Every figure uses a viewBox
560 wide and scales to 100%, so nothing is ever rendered below its design size. Type is
never smaller than 9px in the viewBox, because the visual gate fails below 8px and a
figure that has to be zoomed is a figure nobody reads.

Numbers and captions are NOT written here. `paper_kit` assigns them from order of
appearance, so inserting a figure cannot silently break a reference to a later one.
"""

from __future__ import annotations

# ----------------------------------------------------------------------------------
# shared primitives
# ----------------------------------------------------------------------------------

FONT = 'font-family="Helvetica,Arial,sans-serif"'
from lbo.palette import INK, GREY, FAINT, PAPER, ROLE, TINT, LAYER


def _svg(w: int, h: int, body: str) -> str:
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" '
            f'role="img">'
            f'<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
            f'<marker id="af" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{FAINT}"/></marker></defs>'
            f'{body}</svg>')


def _box(x, y, w, h, label, sub=None, dashed=False, faint=False,
         fill=None, stroke=None, fill_opacity=1.0):
    col = stroke if stroke is not None else (FAINT if faint else INK)
    text_col = INK if fill is not None else col
    dash = ' stroke-dasharray="4 3"' if dashed else ''
    fill_attr = fill if fill is not None else 'none'
    op = f' fill-opacity="{fill_opacity}"' if fill is not None and fill_opacity != 1.0 else ''
    out = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill_attr}"{op} '
           f'stroke="{col}" stroke-width="1"{dash}/>')
    ty = y + h / 2 + (0 if sub is None else -4)
    out += (f'<text x="{x + w / 2}" y="{ty + 3.5}" {FONT} font-size="10.5" fill="{text_col}" '
            f'text-anchor="middle">{label}</text>')
    if sub:
        out += (f'<text x="{x + w / 2}" y="{ty + 16}" {FONT} font-size="8.8" fill="{GREY}" '
                f'text-anchor="middle">{sub}</text>')
    return out


def _txt(x, y, s, size=9.5, fill=INK, anchor='start', style=''):
    return (f'<text x="{x}" y="{y}" {FONT} font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{style}>{s}</text>')


def _arrow(x1, y1, x2, y2, faint=False, dashed=False, col=None):
    """A hairline arrow. `col` overrides the default ink/faint stroke with a palette
    colour; since the shared markers are fixed to ink and faint, a coloured arrow draws
    its own small arrowhead instead of reusing the `<defs>` marker."""
    if col is not None:
        import math
        dash = ' stroke-dasharray="3 3"' if dashed else ''
        ang = math.atan2(y2 - y1, x2 - x1)
        hx, hy = x2 - 6 * math.cos(ang), y2 - 6 * math.sin(ang)
        lx, ly = hx - 3 * math.sin(ang), hy + 3 * math.cos(ang)
        rx, ry = hx + 3 * math.sin(ang), hy - 3 * math.cos(ang)
        head = (f'<polygon points="{x2},{y2} {lx:.1f},{ly:.1f} {rx:.1f},{ry:.1f}" '
                f'fill="{col}"/>')
        return (f'<line x1="{x1}" y1="{y1}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{col}" '
                f'stroke-width="1"{dash}/>{head}')
    color = FAINT if faint else INK
    dash = ' stroke-dasharray="3 3"' if dashed else ''
    mk = 'af' if faint else 'a'
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="1"{dash} marker-end="url(#{mk})"/>')


def _line(x1, y1, x2, y2, col=INK, dashed=False, w=1):
    dash = ' stroke-dasharray="4 3"' if dashed else ''
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" '
            f'stroke-width="{w}"{dash}/>')


# ----------------------------------------------------------------------------------
# Figure: the trace gap
# ----------------------------------------------------------------------------------

def _fig_trace_gap() -> str:
    EVENT = ['the person and why they came', 'what they compared it against',
             'where the item sat, and beside what', 'who was working that hour',
             'the weather, and whether they walked', 'the item, price, quantity',
             'the time and the tender']
    KEPT = {5, 6}
    b = [_txt(6, 14, 'THE EVENT', 9, GREY, style=' letter-spacing="1.2"'),
         _txt(6, 26, 'what actually happened', 8.6, GREY),
         _txt(554, 14, 'THE RECORD', 9, GREY, anchor='end', style=' letter-spacing="1.2"'),
         _txt(554, 26, 'what the till writes', 8.6, GREY, anchor='end'),
         _line(300, 34, 300, 214, FAINT, dashed=True),
         _txt(300, 228, 'discarded at capture', 8.6, GREY, anchor='middle')]
    y = 50
    for i, item in enumerate(EVENT):
        kept = i in KEPT
        b.append(_txt(6, y + 4, item, 9.5, INK if kept else GREY))
        if kept:
            b.append(_arrow(236, y, 392, y, col=ROLE['pass']))
            b.append(_box(396, y - 11, 158, 22, item.split(',')[0], stroke=ROLE['pass']))
        else:
            b.append(_line(236, y, 292, y, FAINT))
            b.append(f'<circle cx="296" cy="{y}" r="2.5" fill="{ROLE["fail"]}"/>')
        y += 27
    # The rule and the note sit BELOW the last row. At 196 and 212 they ran through the
    # sixth and seventh kept boxes, which start at y=185 and y=212.
    b.append(_line(396, 238, 554, 238, FAINT))
    b.append(_txt(554, 254, 'every surviving field is one the firm already controls',
                  8.8, GREY, anchor='end'))
    return _svg(560, 264, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: one sale, five stores
# ----------------------------------------------------------------------------------

def _fig_five_stores() -> str:
    # Labels are kept short on purpose: the run between the fan and the box is 78px,
    # and "inventory drawn from" at 9px overran its box in the first build.
    EDGES = [('rang up at', 'the manager bonus'),
             ('fulfilled from', 'sales per square foot'),
             ('stock drawn from', 'the reorder decision'),
             ('credited to', 'the commission run'),
             ('counted in', 'the like-for-like comparison')]
    b = [_box(6, 96, 104, 34, 'one sale', fill=TINT['tool']),
         _txt(58, 148, 'the record stores', 8.8, GREY, anchor='middle'),
         _txt(58, 160, 'one field: Store', 8.8, GREY, anchor='middle')]
    y = 28
    for label, question in EDGES:
        b.append(_line(110, 113, 168, y + 11, FAINT))
        b.append(_arrow(176, y + 11, 250, y + 11, col=LAYER['core']))
        b.append(_txt(176, y + 6, label, 8.8, INK))
        b.append(_box(254, y, 92, 22, 'a location'))
        b.append(_txt(356, y + 15, 'answers ' + question, 9, GREY))
        y += 37
    return _svg(560, 200, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: what a relation has to carry
# ----------------------------------------------------------------------------------

def _fig_relation() -> str:
    b = [_box(40, 20, 110, 30, 'technician'),
         _box(400, 20, 110, 30, 'service line'),
         _line(150, 35, 400, 35),
         f'<circle cx="275" cy="35" r="3" fill="{INK}"/>',
         _txt(275, 16, 'one relation, four obligations', 9, GREY, anchor='middle')]
    items = [('KIND', 'is certified for, not merely scheduled on.', 'A record and a rule are different edges.',
              TINT['agent'], ROLE['agent']),
             ('DIRECTION', 'from the technician: what am I committed to.', 'From the service line: who can do it. Only one finds a ceiling.',
              TINT['monitor'], ROLE['monitor']),
             ('INTERVAL', 'held from the date issued, until it lapses.', 'An untimed edge answers history with today.',
              TINT['reflect'], ROLE['reflect']),
             ('EVIDENCE', 'read from an export, confirmed in writing,', 'or inferred at stated confidence. Not the same thing.',
              TINT['pass'], ROLE['pass'])]
    # One short dashed drop from the relation to the list beneath it. The first version
    # fanned a dashed line from the relation to each of the four items, and every one of
    # those lines crossed the gloss text it was pointing at.
    b.append(_line(275, 40, 275, 62, FAINT, dashed=True))
    y = 78
    for name, l1, l2, fill, stroke in items:
        b.append(f'<rect x="4" y="{y - 12}" width="82" height="16" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="1"/>')
        b.append(_txt(10, y, name, 9, INK, style=' letter-spacing="1"'))
        b.append(_txt(96, y, l1, 9.5, INK))
        b.append(_txt(96, y + 13, l2, 9, GREY))
        y += 38
    return _svg(560, 236, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: the traversal in the margin case
# ----------------------------------------------------------------------------------

def _fig_traversal() -> str:
    STEPS = [('margin fell', '$1,800 at fixed volume', True),
             ('two products', 'one supplier', True),
             ('supplier terms', 'volume break at 500', False),
             ('order history', '610, then 470', False),
             ('a cash decision', 'to cover a tax payment', False)]
    b = [_txt(6, 14, 'THE SYMPTOM', 9, GREY, style=' letter-spacing="1.2"'),
         _txt(554, 14, 'THE ANSWER', 9, GREY, anchor='end', style=' letter-spacing="1.2"')]
    x = 6
    for i, (label, sub, in_pos) in enumerate(STEPS):
        is_last = i == len(STEPS) - 1
        b.append(_box(x, 30, 100, 40, label, sub, fill=TINT['owner'] if is_last else None))
        b.append(_txt(x + 50, 84, 'in the till' if in_pos else 'not in the till',
                      8.6, GREY if in_pos else INK, anchor='middle'))
        if i < len(STEPS) - 1:
            b.append(_arrow(x + 100, 50, x + 110, 50, col=ROLE['agent']))
        x += 113
    b.append(_line(6, 100, 554, 100, FAINT))
    b.append(_txt(6, 116, 'The accounting decomposition stops at the first box. It is correct, '
                          'and it restates the symptom.', 9.2, GREY))
    b.append(_txt(6, 130, 'The action lives at the last one: order 30 units more, '
                          'in a different function and a different quarter.', 9.2, INK))
    return _svg(560, 140, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: three grades of error signal
# ----------------------------------------------------------------------------------

def _fig_error_signal() -> str:
    COLS = ['arithmetic', 'identity', 'completeness', 'prediction', 'meaning']
    ROWS = [('agreement between', 'independent derivations', [1, 1, 1, 0, 0], 'cheap, immediate'),
            ('delayed reality', '', [0, 0, 0, 1, 0], 'weeks late, confounded'),
            ('a person who knows', 'the business', [1, 1, 1, 1, 1], 'scarce, and degrades')]
    # The grid is narrow enough that the right-hand notes fit inside the 560 measure.
    # At x0=176 and cw=66 the notes started at x=514 and were simply cut off by the
    # viewBox, so the paper shipped "cheap, imme" and "scarce, and".
    x0, cw = 150, 56
    b = []
    for j, c in enumerate(COLS):
        b.append(_txt(x0 + j * cw + cw / 2, 20, c, 8.8, GREY, anchor='middle'))
    b.append(_line(x0 - 6, 28, x0 + len(COLS) * cw, 28, FAINT))
    ROW_COLORS = [ROLE['tool'], ROLE['monitor'], ROLE['owner']]
    y = 48
    for (name, sub, marks, note), head_col in zip(ROWS, ROW_COLORS):
        b.append(_txt(6, y + 2, name, 9.5, head_col))
        if sub:
            b.append(_txt(6, y + 14, sub, 9.5, head_col))
        for j, m in enumerate(marks):
            cx = x0 + j * cw + cw / 2
            if m:
                b.append(f'<rect x="{cx - 17}" y="{y - 8}" width="34" height="16" '
                         f'fill="{INK}" opacity="0.10"/>')
                b.append(_txt(cx, y + 3.5, 'catches', 8.4, INK, anchor='middle'))
            else:
                b.append(_txt(cx, y + 3.5, 'blind', 8.4, FAINT, anchor='middle'))
        b.append(_txt(x0 + len(COLS) * cw + 8, y + 3.5, note, 8.8, GREY))
        y += 44
    b.append(_line(x0 - 6, 158, x0 + len(COLS) * cw, 158, FAINT))
    b.append(_txt(6, 176, 'Only the third catches a correct number describing the wrong thing, '
                          'and it is the one that runs out.', 9.2, INK))
    return _svg(560, 186, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: graduated autonomy
# ----------------------------------------------------------------------------------

def _fig_autonomy() -> str:
    """A ladder, read from the bottom.

    The first version was a staircase: four boxes stepping up and to the right, with each
    gate's evidence written in the 34px gap between them. Two lines of nineteen characters
    do not fit in 34px, so every gate label was drawn straight over the box to its right.
    A vertical ladder gives the evidence the whole width of the measure and removes the
    collision entirely rather than shrinking the type until it just about fits.
    """
    LEVELS = [('STANDING AUTHORITY', 'a bounded class of actions', 'within stated limits'),
              ('APPROVED ACTION', 'execute one specific', 'reviewed payload'),
              ('PREPARE', 'investigate, compute,', 'assemble a decision packet'),
              ('OBSERVE', 'read approved sources,', 'run accepted checks')]
    GATES = ['repeated state and process correctness',
             'packets useful, and review time that does not grow',
             'mappings verified, freshness handled honestly']
    LEVEL_FILLS = [LAYER['control'], LAYER['meaning'], LAYER['extension'], LAYER['core']]
    b = []
    for i, (name, l1, l2) in enumerate(LEVELS):
        y = 14 + i * 76
        b.append(f'<rect x="6" y="{y}" width="180" height="44" '
                 f'fill="{LEVEL_FILLS[i % len(LEVEL_FILLS)]}" fill-opacity="0.16" '
                 f'stroke="{INK}" stroke-width="1"/>')
        b.append(_txt(96, y + 16, name, 9, INK, anchor='middle', style=' letter-spacing="0.6"'))
        b.append(_txt(96, y + 28, l1, 8.8, GREY, anchor='middle'))
        b.append(_txt(96, y + 39, l2, 8.8, GREY, anchor='middle'))
        if i < len(GATES):
            # the gap between this box and the one below it, climbing
            gy = y + 44
            b.append(_arrow(96, gy + 30, 96, gy + 2))
            b.append(_txt(210, gy + 20, 'EVIDENCE', 8.8, GREY,
                          style=' letter-spacing="0.8"'))
            b.append(_txt(272, gy + 20, GATES[i], 9, INK))
    b.append(_txt(6, 318, 'Granted per client, per capability, per scope. Never a global '
                          'setting, and every grant has an owner and a revocation path.',
                  9.2, GREY))
    return _svg(560, 328, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: the decision loop
# ----------------------------------------------------------------------------------

def _fig_loop() -> str:
    import math
    STEPS = ['observe', 'notice', 'investigate', 'prepare', 'verify',
             'approve', 'execute', 'measure', 'learn']
    # cy leaves room above the ring for the `observe` label, whose baseline sits at
    # cy - (r + 30) + 3. At cy=118 that put the cap heights above the viewBox and the
    # top of the word was clipped away.
    cx, cy, r = 280, 126, 86
    b = []
    n = len(STEPS)
    for i, s in enumerate(STEPS):
        a = -math.pi / 2 + 2 * math.pi * i / n
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        human = s in ('approve',)
        fill = ROLE['pass'] if human else PAPER
        stroke = ROLE['pass'] if human else INK
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="1"/>')
        lx = cx + (r + 30) * math.cos(a)
        ly = cy + (r + 30) * math.sin(a)
        anchor = 'middle' if abs(math.cos(a)) < 0.35 else ('start' if math.cos(a) > 0 else 'end')
        b.append(_txt(lx, ly + 3, s, 9.5, INK, anchor=anchor))
        a2 = -math.pi / 2 + 2 * math.pi * (i + 0.62) / n
        b.append(_arrow(cx + r * math.cos(a + 0.22), cy + r * math.sin(a + 0.22),
                        cx + r * math.cos(a2), cy + r * math.sin(a2), faint=True))
    b.append(_txt(cx, cy - 4, 'one loop, per client,', 9.2, GREY, anchor='middle'))
    b.append(_txt(cx, cy + 9, 'running unattended', 9.2, GREY, anchor='middle'))
    # The key sits bottom left. At x=464 it needed 166px of a 560 measure and the last
    # third of the sentence was cut off by the edge of the viewBox.
    b.append(f'<circle cx="12" cy="250" r="5" fill="{ROLE["pass"]}" stroke="{ROLE["pass"]}"/>')
    b.append(_txt(26, 253, 'the only step that waits for a person', 9, INK))
    return _svg(560, 262, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: three kinds of absence
# ----------------------------------------------------------------------------------

def _fig_absence() -> str:
    b = [_txt(6, 14, 'WHAT IS MISSING', 9, GREY, style=' letter-spacing="1.2"')]
    KINDS = [('an absent instance', 'a row that should exist and does not',
              'the population', 'this model'),
             ('an absent relation', 'two things that should be joined and are not',
              "the schema's obligations", 'this model'),
             ('an absent type', 'a whole category this firm has never had',
              'a reference population', 'many models')]
    LAYER_FILLS = [LAYER['core'], LAYER['extension'], LAYER['meaning']]
    y = 36
    for i, (name, gloss, needs, source) in enumerate(KINDS):
        is_key = source == 'many models'
        b.append(_box(6, y, 150, 38, name, fill=LAYER_FILLS[i % len(LAYER_FILLS)],
                     fill_opacity=0.16))
        b.append(_txt(166, y + 16, gloss, 9.5, INK))
        b.append(_txt(166, y + 29, 'found against ' + needs, 9, GREY))
        b.append(_arrow(432, y + 19, 452, y + 19, faint=not is_key,
                        col=ROLE['pass'] if is_key else None))
        b.append(_box(456, y + 5, 98, 28, source, faint=not is_key,
                     stroke=ROLE['pass'] if is_key else None))
        y += 52
    b.append(_line(6, 196, 554, 196, FAINT))
    b.append(_txt(6, 214, 'The third is where the value concentrates, and it is the one a single '
                          'model can never reach:', 9.2, INK))
    b.append(_txt(6, 227, 'you cannot see that a firm lacks a revenue line by studying that firm. '
                          'There is nothing there to study.', 9.2, INK))
    return _svg(560, 236, ''.join(b))



# ----------------------------------------------------------------------------------
# Figure: how a decision comes to match the owner
# ----------------------------------------------------------------------------------

def _fig_convergence() -> str:
    """The mechanism by which delegation becomes possible: the gap between what the
    system proposes and what the owner decides is itself the training signal, and it is
    recorded rather than discarded."""
    b = [_txt(6, 14, 'ONE DECISION, REPEATED', 9, GREY, style=' letter-spacing="1.2"')]
    # three rounds, gap narrowing
    rounds = [(40, 'round 1', 86), (210, 'round 2', 44), (380, 'round 8', 12)]
    for x, label, gap in rounds:
        b.append(_txt(x + 60, 34, label, 9, GREY, anchor='middle'))
        # proposal marker and decision marker, separated by the gap
        px, dx = x + 60 - gap / 2, x + 60 + gap / 2
        b.append(f'<circle cx="{px}" cy="62" r="4.5" fill="none" stroke="{ROLE["agent"]}"/>')
        b.append(f'<circle cx="{dx}" cy="62" r="4.5" fill="{ROLE["pass"]}"/>')
        b.append(_line(px, 62, dx, 62, INK, dashed=True))
        b.append(_txt(x + 60, 84, f'gap recorded', 8.6, INK, anchor='middle'))
        b.append(_txt(x + 60, 96, 'as a constraint', 8.6, GREY, anchor='middle'))
        if x < 380:
            b.append(_arrow(x + 128, 62, x + 196, 62, faint=True))
    b.append(_txt(6, 120, 'what the system proposed', 8.8, GREY))
    b.append(f'<circle cx="150" cy="117" r="4.5" fill="none" stroke="{ROLE["agent"]}"/>')
    b.append(_txt(200, 120, 'what the owner decided', 8.8, GREY))
    b.append(f'<circle cx="330" cy="117" r="4.5" fill="{ROLE["pass"]}"/>')
    b.append(_line(6, 138, 554, 138, FAINT))
    b.append(_txt(6, 156, 'The difference between the two is the only training signal that '
                          'matters, and it is thrown away by every system', 9.2, INK))
    b.append(_txt(6, 169, 'that records the decision and not the proposal beside it. Kept, it '
                          'is what makes the next proposal closer, and what', 9.2, INK))
    b.append(_txt(6, 182, 'eventually lets an owner hand over a class of decision without '
                          'handing over the judgement behind it.', 9.2, INK))
    return _svg(560, 190, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: the whole system
# ----------------------------------------------------------------------------------

def _fig_system() -> str:
    """Sources on the left flow through identity into the store; the layers stack below
    it; the agent reads and proposes; the monitor gates; the owner decides.

    On the geometry, because it was cut twice. Every label here is sized by hand against
    its box: sub-labels at 8.8px run about 4.4px a character, so a 164px box holds about
    37 characters and no more. The first draft put a 54-character gloss in a 166px box
    and a 44-character tuple in a box 32px too narrow for it, and both silently spilled
    across their borders. The gap between the layer stack and the right-hand column is
    42px on purpose: the word `journal` has to sit in it.
    """
    b = []
    srcs = [('point of sale', 'own ids, one store field'),
            ('ledger', 'effective and entered dates'),
            ('payroll, CRM, schedule', 'own ids, own vocabulary'),
            ('terms, certifications', 'documents')]
    for i, (l, s) in enumerate(srcs):
        y = 18 + i * 46
        b.append(_box(6, y, 126, 36, l, s, fill=TINT['tool'], stroke=ROLE['tool']))
        b.append(_arrow(132, y + 18, 158, 118, col=ROLE['tool']))
    b.append(_txt(69, 12, 'EXPORTS', 8.8, GREY, anchor='middle', style=' letter-spacing="1.2"'))
    b.append(_box(160, 96, 88, 44, 'identity', 'keys, queue, merges',
                  fill=TINT['reflect'], stroke=ROLE['reflect']))
    b.append(_arrow(248, 118, 268, 118, col=ROLE['reflect']))
    # the store
    b.append(_box(268, 66, 164, 104, '', None, fill=PAPER, stroke=LAYER['core']))
    b.append(_txt(350, 84, 'assertion store', 10.5, INK, anchor='middle',
                  style=' font-weight="600"'))
    b.append(_txt(350, 102, '(c, s, p, v, I_v, I_o, e, sigma)', 9, INK, anchor='middle'))
    b.append(_txt(350, 122, 'two clocks; evidence on every row;', 8.8, GREY, anchor='middle'))
    b.append(_txt(350, 134, 'supersession, nothing deleted', 8.8, GREY, anchor='middle'))
    b.append(_txt(350, 156, 'core + one industry extension', 8.8, LAYER['core'],
                  anchor='middle'))
    # the layers, below the store
    layers = [('definitions', 'versioned; window, base, inputs', LAYER['meaning']),
              ('competency questions', 'present, absent, stale, gaps', LAYER['meaning']),
              ('action contracts', 'pre, delta, post, forbidden', LAYER['control']),
              ('authority monitor', 'grants, limits; outside the agent', ROLE['monitor'])]
    for i, (l, s, col) in enumerate(layers):
        y = 184 + i * 40
        b.append(_box(268, y, 164, 34, l, s, fill=PAPER, stroke=col))
    b.append(_line(350, 170, 350, 184, GREY))
    # agent, execute, owner: the right-hand column
    b.append(_box(474, 66, 80, 44, 'agent', 'reads, proposes',
                  fill=TINT['agent'], stroke=ROLE['agent']))
    b.append(_arrow(474, 84, 432, 96, col=ROLE['agent']))
    b.append(_txt(466, 74, 'read', 8.8, ROLE['agent'], anchor='end'))
    b.append(_arrow(514, 110, 514, 304, col=ROLE['agent'], dashed=True))
    b.append(_txt(518, 200, 'propose', 8.8, ROLE['agent']))
    # `execute` is centred on the authority monitor band, so the arrow between them
    # leaves that box rather than the gap above it.
    b.append(_box(474, 306, 80, 30, 'execute', 'or refuse',
                  fill=TINT['monitor'], stroke=ROLE['monitor']))
    b.append(_arrow(432, 321, 474, 321, col=ROLE['monitor']))
    # `journal` sits in the 42px gap, clear of the layer boxes to its left. In the draft
    # it was anchored over the arrowhead and the arrow ran through the word.
    b.append(_txt(453, 312, 'journal', 8.8, ROLE['monitor'], anchor='middle'))
    b.append(_arrow(514, 336, 514, 360, col=ROLE['monitor']))
    b.append(_box(474, 362, 80, 30, 'owner', 'decides',
                  fill=TINT['owner'], stroke=ROLE['owner']))
    # The owner's return path. The label is two lines ABOVE the line rather than one
    # long line sitting on it, which is what the draft did.
    b.append(_line(474, 377, 212, 377, ROLE['owner'], dashed=True))
    b.append(_arrow(212, 377, 212, 142, col=ROLE['owner'], dashed=True))
    b.append(_txt(350, 356, 'settles a definition, grants authority,', 8.8, ROLE['owner'],
                  anchor='middle'))
    b.append(_txt(350, 368, 'approves a proposal, decides the gap', 8.8, ROLE['owner'],
                  anchor='middle'))
    return _svg(560, 400, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: the layers of the model
# ----------------------------------------------------------------------------------

def _band(x, y, w, h, label, sub, col, tint):
    out = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{tint}" '
           f'stroke="{col}" stroke-width="1"/>')
    out += _txt(x + 10, y + h / 2 - 1, label, 10.5, INK, style=' font-weight="600"')
    out += _txt(x + 10, y + h / 2 + 12, sub, 8.8, GREY)
    return out


def _fig_layers() -> str:
    """What each layer holds, and what it is for."""
    rows = [('control', 'decisions, actions, grants, messages',
             'what may be done, by whom, and what was done',
             ROLE['monitor'], TINT['monitor']),
            ('meaning', 'definitions, identity, evidence, competency questions',
             'what a number means and whether it can be answered',
             LAYER['meaning'], TINT['monitor']),
            ('extension', 'per industry: jobs and crews; routes and terms',
             'admitted only where a named question requires it',
             LAYER['extension'], TINT['agent']),
            ('core', 'party, person, location, product, order, invoice, payment',
             'the exchange structure of any firm',
             LAYER['core'], TINT['agent']),
            ('store', 'assertions under two clocks',
             'the only thing that holds facts',
             ROLE['tool'], TINT['tool'])]
    b = []
    for i, (name, holds, purpose, col, tint) in enumerate(rows):
        y = 14 + i * 52
        b.append(_band(6, y, 300, 44, name, holds, col, tint))
        b.append(_txt(318, y + 26, purpose, 9, GREY))
    b.append(_txt(6, 290, 'agent tools read every layer; writes enter through the control '
                          'layer only', 8.8, INK))
    return _svg(560, 300, ''.join(b))


# ----------------------------------------------------------------------------------
# Figure: the three arms
# ----------------------------------------------------------------------------------

MONO = ' style="font-family:Menlo,monospace"'
# A second font-family ATTRIBUTE would be a duplicate and the browser keeps the first,
# so the monospace has to arrive as a style property to win over the presentation
# attribute _txt already writes.


def _fig_arms() -> str:
    """The same agent, policy and prompt against three surfaces."""
    cols = [('Arm A: raw tables', 'the exports as SQL, as delivered',
             ['describe_tables', 'run_sql', 'execute_action', 'request_owner_approval'],
             ROLE['tool'], TINT['tool'], 'no authority layer'),
            ('Arm B: metric layer', 'normalised views, approved definitions',
             ['describe_tables', 'run_sql', 'list_metrics', 'compute_metric',
              'execute_action', 'request_owner_approval'],
             ROLE['monitor'], TINT['monitor'], 'no authority layer'),
            ('Arm C: ontology', 'typed relations, two clocks, evidence',
             ['describe_schema', 'find_entities', 'get_assertions', 'traverse', 'history',
              'compute_metric', 'check_question', 'propose_action', 'execute_action*'],
             ROLE['agent'], TINT['agent'], '* through the monitor')]
    b = [_box(6, 4, 548, 20, 'same agent, same policy text, same prompt, same model, '
                             'same turn and cost budget', None, fill=PAPER, stroke=FAINT)]
    for i, (title, sub, tools, col, tint, foot) in enumerate(cols):
        x = 6 + i * 186
        b.append(_box(x, 30, 176, 34, title, sub, fill=tint, stroke=col))
        for j, t in enumerate(tools):
            b.append(_txt(x + 10, 84 + j * 14, t, 8.8, INK, style=MONO))
        b.append(_txt(x + 10, 84 + len(tools) * 14 + 6, foot, 8.8, col))
    return _svg(560, 226, ''.join(b))


# ----------------------------------------------------------------------------------
# registry
# ----------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------
# Figure: the service loop, as run (the internal paper's Figure 1)
# ----------------------------------------------------------------------------------

def _fig_service() -> str:
    """Eight stages in two columns. A solid box is a stage the reference implementation
    runs in every cycle; a dashed box is doctrine the run does not exercise. The sub-line
    names what actually does the stage, which is the point: three of the eight are code
    with no model in them."""
    STAGES = [
        ('observe', 'freshness: every export against the firm\u2019s clock', ROLE['tool'], True),
        ('notice', 'the watch: rules that read through competency questions', ROLE['tool'], True),
        ('investigate and prepare', 'the agent, on the ontology surface', ROLE['agent'], True),
        ('verify', 'the scorer: state, process, evidence, communication', ROLE['reflect'], True),
        ('decide', 'the owner (a script per firm, in this run)', ROLE['owner'], True),
        ('execute', 'the monitor, then the journal', ROLE['monitor'], True),
        ('measure', 'a later cycle, on records that arrived since', ROLE['pass'], True),
        ('learn', 'a candidate lesson; promotion not built', ROLE['fail'], False),
    ]
    b = []
    w, h, gap_y, x0, x1, y0 = 236, 40, 14, 20, 304, 18
    pos = {}
    for i, (label, sub, col, built) in enumerate(STAGES):
        colx = x0 if i < 4 else x1
        y = y0 + (i % 4) * (h + gap_y)
        pos[i] = (colx, y)
        b.append(_box(colx, y, w, h, label, sub, dashed=not built, fill=col, fill_opacity=0.14, stroke=col))
    for i in range(7):
        (ax, ay), (bx, by) = pos[i], pos[i + 1]
        if i == 3:
            b.append(_arrow(ax + w, ay + h / 2, bx, by - 0 + h / 2 - (h + gap_y) * 3, faint=True))
        else:
            b.append(_arrow(ax + w / 2, ay + h, bx + w / 2, by, faint=True))
    # the return: learn feeds the next cycle's observe
    lx, ly = pos[7]
    ox, oy = pos[0]
    b.append(_line(lx + w / 2, ly + h, lx + w / 2, ly + h + 14, col=FAINT, dashed=True))
    b.append(_line(lx + w / 2, ly + h + 14, ox + w / 2, ly + h + 14, col=FAINT, dashed=True))
    b.append(_arrow(ox + w / 2, ly + h + 14, ox + w / 2, oy - 6, faint=True, dashed=True))
    b.append(_txt(280, ly + h + 26, 'next cycle', 8.8, GREY, anchor='middle'))
    b.append(_txt(x0, ly + h + 44, 'solid: runs in every cycle of this paper. dashed: doctrine, not exercised by the run.', 8.8, GREY))
    return _svg(560, ly + h + 52, ''.join(b))


FIGURES: dict[str, tuple[str, str]] = {
    'tracegap': (_fig_trace_gap(),
                 'What a transacting system keeps, and what it drops. The loss is not random: '
                 'a system built to complete a sale retains exactly the fields needed to '
                 'complete and account for it, and those are the ones the firm already '
                 'controls. Everything describing the customer’s world is discarded at '
                 'capture, which is why an accurate report can feel useless.'),
    'fivestores': (_fig_five_stores(),
                   'One sale relates to a location in at least five distinct ways, and in a '
                   'firm that ships from one site and rings at another they resolve to '
                   'different locations. Each answers a different question and each is '
                   'defensible. The point of sale records one.'),
    'relation': (_fig_relation(),
                 'The four properties a relation carries if it is to be worth traversing. A '
                 'foreign key has none of them: it can be followed, but it cannot be '
                 'interrogated, timed, or believed to a stated degree.'),
    'traversal': (_fig_traversal(),
                  'The margin case, as a traversal. The accounting decomposition is correct '
                  'and stops at the first box. Three of the five hops are absent from the '
                  'point of sale entirely, and the action lives at the far end, in a function '
                  'that would not describe itself as having made a pricing decision.'),
    'errorsignal': (_fig_error_signal(),
                    'Three kinds of error signal a business emits, and what each can catch. '
                    'The first two are cheap and automatable. Only the third catches a figure '
                    'that is exactly right and about something other than what the reader will '
                    'take it to be, and it is the one that degrades under load.'),
    'autonomy': (_fig_autonomy(),
                 'Responsibility is earned per capability, not switched on. Each gate is a '
                 'specific piece of evidence, and the level above it is unavailable until '
                 'that evidence exists.'),
    'loop': (_fig_loop(),
             'The service as one cycle. Everything except approval can run without a person, '
             'which is what makes the count of approvals a design variable rather than an '
             'administrative detail.'),
    'convergence': (_fig_convergence(),
                    'How delegation would become possible, as designed and not yet measured. The '
                    'gap between what the system proposed and what the owner actually decided is '
                    'recorded as a constraint rather than discarded, so that the proposal can '
                    'move toward the owner\u2019s judgement over repetitions of the same decision. '
                    'The narrowing drawn here is the design; this paper\u2019s run records the gap '
                    'once per decision and cannot show it narrow. What is delegated is a class '
                    'of decision; what is learned is the judgement that governs it.'),
    'absence': (_fig_absence(),
                'Three kinds of absence, and what each requires to be visible. The first two '
                'fall out of one complete model. The third needs a reference population, which '
                'is why the most valuable capability is the last one to arrive.'),
    'system': (_fig_system(),
               'The whole system. Every export arrives with its own identifiers and its '
               'own vocabulary, so nothing reaches the store until identity has resolved '
               'it; the store then holds one kind of row, under two clocks, with its '
               'evidence attached and nothing ever deleted. The layers below say what a '
               'number means, whether a question can be answered at all, what an action '
               'is allowed to change, and who may authorise it. The agent reads every '
               'layer and writes to none: it proposes, the monitor decides whether the '
               'proposal may execute and records what happened, and the owner settles '
               'the things a model cannot settle for itself.'),
    'layers': (_fig_layers(),
               'What each layer holds, and what it is for. The split that matters is the '
               'last one: the store holds facts and nothing else, so a definition, a '
               'grant and a decision are all first-class objects with their own '
               'histories rather than conventions living in somebody’s head.'),
    'service': (_fig_service(),
                'The service loop as it runs in this paper. Freshness and the watch are code and '
                'run before any model is involved; the agent investigates and prepares on the '
                'ontology surface; the scorer, the owner and the monitor each hold one stage; a '
                'later cycle measures against records that arrived since; and the cycle ends in a '
                'candidate lesson that nothing promotes.'),
    'arms': (_fig_arms(),
             'The three arms of the evaluation. The agent, the policy text, the prompt, '
             'the model and the turn and cost budgets are identical across all three. '
             'The only thing that varies is what the agent can see and what it is '
             'allowed to do, which is what makes a difference in outcome attributable '
             'to the representation rather than to the model.'),
}


# ----------------------------------------------------------------------------------
# panel figures: several listings in one numbered figure
# ----------------------------------------------------------------------------------
#
# A panel set is NOT a drawing. Each cell is a slice of a file that actually runs, named
# the way `{{listing:...}}` names one, so the figure is read from the implementation at
# build time and cannot drift from it. `paper_kit` resolves the slices, lays them out as
# a grid, letters the sub-captions, and registers the result under the set's own name so
# it shares one numbering sequence with the diagrams and the charts.

# ----------------------------------------------------------------------------------
# captions for figures whose body is a saved run
# ----------------------------------------------------------------------------------
#
# A trajectory is printed from its log file at build time, so its caption cannot live
# beside it in the Markdown without being a second place to edit. It lives here, keyed
# by what the run is FOR rather than by the run's hash, so re-running an experiment
# changes the hash in one placeholder and leaves the caption alone.

CAPTIONS: dict[str, str] = {
    'system': 'The whole system, and the end of one run through it. Every export enters '
              'through identity and lands in the assertion store under two clocks; the '
              'layers above it say what a number means and what may be done about it; the '
              'agent reads and proposes, the monitor decides whether the proposal may '
              'execute, and the owner settles anything the model cannot. On the right, the '
              'agent has the four gross-profit figures and reads the supplier, the terms '
              'and the units ordered each quarter, which is where the cause is.',
    'margin': 'The margin question, answered two hops out. The agent reaches the '
              'supplier, its terms and the quarter that missed the volume break, which is '
              'where the cause is, rather than stopping at the cost line, which is where '
              'the symptom is. It does not take the last hop to the memo that says why the '
              'order was cut, and lost on communication for it.',
    'channel': 'The channel question, where the obvious answer inverts and no arm saw '
               'it. The agent pages through the channel\u2019s leads, reads its spend, and '
               'answers with a careful account of why the per-lead figure is an average; '
               'it never reaches the certification or the technician behind the jobs.',
    'refusal': 'The refusal that stops one sentence short. Both proposals are allowed '
               'under the grant and need the owner because each exceeds the limit; the '
               'monitor says so with the percentage; the agent queues both, executes '
               'neither, and answers with the limit. It does not offer the two prices '
               'that would pass, and neither did any trial on any arm.',
    'clock': 'The reminder sent on the wrong calendar. The raw-table run computes days '
             'overdue from the machine\u2019s date, which the runtime supplied, rather than '
             'the firm\u2019s, which the prompt stated; by that count every open invoice '
             'is late, and the reminders go out with no authority layer to stop them.',
    'build': 'The retailer built from its exports, as it ran. One turn per source, with what '
             'each produced; the four customers whose records share a name and no key, '
             'queued for a person; the grants loaded from the owner; and the summary.',
    'service': 'The service loop as it runs in this paper, beside the opening of one cycle. On the '
               'left, eight stages: freshness and the watch are code and run before any model is '
               'involved; the agent investigates and prepares on the ontology surface; the scorer, '
               'the owner and the monitor each hold one stage; a later cycle measures against '
               'records that arrived since; the cycle ends in a candidate lesson that nothing '
               'promotes. On the right, the retailer\u2019s watch has tripped twice, the catch is '
               'due, and the agent begins by finding the product and asking the absence query.',
    'cycle_open': 'The opening of a cycle. The watch\u2019s two trips are the first turns of the '
                  'record because the watch ran first; the third turn is the loop handing the agent '
                  'the trip it is due to write up, with the sentence that nobody asked; the agent\u2019s '
                  'first two moves are to find the product and to ask the absence query with the '
                  'predicate named without its type prefix, which the tool did not know and so '
                  'returned every product; the catch later repeats that count.',
    'cycle_catch': 'A catch nobody asked for. Freshness passes, the watch trips on a rule read '
                   'through a competency question, and the agent is handed the trip and told '
                   'nobody asked; it checks the fact with the tools and writes the catch with the '
                   'number, what it usually means, and the decision that is the owner\u2019s.',
    'cycle_question': 'An owner\u2019s question, in the service loop. The same task and the same '
                      'scorer as the public paper, with the watch\u2019s report of the morning printed '
                      'before the question arrives.',
    'cycle_action': 'An action under authority. The proposal runs through the monitor, executes '
                    'within the grant, and is journaled as assertions on the action itself.',
    'cycle_followup': 'A follow-up two weeks on. The cycle runs on 15 July; the records entered '
                      'since the first cycle are visible under the second clock, and the answer '
                      'rests on them. A replay of the first cycle still cannot see them.',
    'cycle_delegation': 'A delegated decision. The agent proposes, the monitor says the proposal '
                        'needs the owner, the scripted owner amends or declines with a condition, '
                        'the decision is recorded with the gap, and only the owner\u2019s payload '
                        'can execute.',
    'route': 'The route that does not pay for itself. The current quarter has no '
             'invoices yet, so the agent asks for the one that closed; one route\u2019s '
             'contribution is negative against its booked cost, and every figure arrives '
             'with its window and basis attached.',
}


#
# On the SIZE of a slice, which the first version got wrong. A panel is half the
# measure, which is about 183pt of text, and at 7.6pt Menlo that is forty characters
# to a line. The source here is written at a hundred columns, so a line wraps two or
# three times and a twenty-six line function becomes fifty-five printed lines. The
# first build of this figure ran over three pages, because `break-inside: avoid` can
# only hold a figure that fits on a page in the first place. Count wrapped lines, not
# source lines, and keep the four panels inside about thirty-five of them.
#
# Which is why panel (b) is six lines and not the whole of `change_price_contract`.
# The function is twenty-six source lines running to a hundred and four columns, so in
# a forty character column it prints as about fifty-five lines, and the top row alone
# would be taller than the page. Nothing in the other row can buy that space back.
# The caption below therefore describes what these six lines actually show, rather
# than what the whole function would have shown. If the slice is ever widened, widen
# the caption with it: a caption that promises more than the panel prints is the same
# defect as a wrong number, and it is the one nobody checks.

PANELS: dict[str, tuple[list[tuple[str, str]], str]] = {
    'residue': ([
        ('the decision record, written on every owner reply', 'lbo/decisions.py:60-72'),
        ('the candidate lesson, written at the end of every cycle', 'lbo/service.py:217-224'),
    ], 'What a cycle leaves behind. The decision record keeps what was proposed beside what was '
       'decided, the gap per field and the owner\u2019s condition, as assertions in the firm\u2019s '
       'own store. The candidate lesson carries the scorer\u2019s verdict and its notes as evidence '
       'and a status the code cannot set to anything but candidate; nothing reads it back yet.'),
    'owner': ([
        ('the retailer\u2019s owner', 'lbo/owner.py:37-43'),
        ('the distributor\u2019s owner', 'lbo/owner.py:53-72'),
    ], 'Two of the three owner scripts, as they ran. Each is a function from an action and a '
       'payload to a reply: approve, amend with the payload the owner would sign, or decline, '
       'always with the condition in the owner\u2019s words. A script cannot be surprised, which '
       'is the ceiling of the run and is said in the text.'),
    'panels': ([
        ('the record everything is held in', 'lbo/store.py:48-61'),
        ('what an action may never do, and what it declares',
         'lbo/actions.py:149-154'),
        ('the operating policy, in the owner’s words',
         'lbo/firms/data/retail/policy.md:3-12'),
        ('a competency question', 'lbo/questions.py:20-29'),
    ], 'The method as code, read from the files that run. An assertion carries its own '
       'two clocks, its evidence and what it supersedes. An action contract ends with '
       'the one thing it may never do, and then declares itself: its inputs, the four '
       'functions that check and apply it, the authority it runs under, the risk it '
       'carries, and whether and how it can be undone. The policy is the owner’s '
       'own words, and the competency question is the standard the model is sized '
       'against.'),
}
