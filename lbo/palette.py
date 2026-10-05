"""The one color system for every figure, chart, listing and trajectory in both papers.

Roles color the turns of a trajectory and the actors in a diagram. Outcomes color
pass and fail. Layers color the four strata of the ontology. Everything else is ink.
The values are muted on purpose: the reference papers (tau-bench, Reflexion, ICM) use
pale tints behind text and mid-saturation strokes, never primaries.
"""
from __future__ import annotations

import re

INK = '#111111'
GREY = '#777777'
FAINT = '#bbbbbb'
PAPER = '#ffffff'

ROLE = {
    'agent':   '#3b6fb6',   # steel blue
    'owner':   '#c0566a',   # rose
    'tool':    '#6b6b6b',   # tool grey
    'monitor': '#b8862b',   # amber: the authority monitor
    'reflect': '#7b5fb5',   # lavender
    'pass':    '#3a8a4e',   # green
    'fail':    '#c0392b',   # red
}

TINT = {
    'agent':   '#e3ecf7',
    'owner':   '#f7e4e8',
    'tool':    '#ececec',
    'monitor': '#f6ecd6',
    'reflect': '#ebe5f6',
    'pass':    '#e1f0e5',
    'fail':    '#f6e0dd',
}

LAYER = {
    'core':      '#2f5d8a',
    'extension': '#6c95c2',
    'meaning':   '#c9772b',
    'control':   '#e2a866',
}

ALL: frozenset[str] = frozenset(
    list(ROLE.values()) + list(TINT.values()) + list(LAYER.values())
    + [INK, GREY, FAINT, PAPER])


def pygments_style():
    """A light pygments style whose every color is in ALL.

    Strings in rose, keywords in blue, comments in green italic, numbers in amber,
    which is the look of the tau-bench listings.
    """
    from pygments.style import Style
    from pygments.token import (Comment, Keyword, Name, Number, Operator, String, Text)

    class PaperStyle(Style):
        background_color = PAPER
        styles = {
            Text:               INK,
            Comment:            f'italic {ROLE["pass"]}',
            Keyword:            f'bold {ROLE["agent"]}',
            Keyword.Constant:   ROLE['agent'],
            Name.Function:      ROLE['agent'],
            Name.Class:         ROLE['agent'],
            Name.Tag:           ROLE['reflect'],
            Name.Attribute:     ROLE['monitor'],
            String:             ROLE['owner'],
            Number:             ROLE['monitor'],
            Operator:           INK,
        }
    return PaperStyle


def pygments_css() -> str:
    """The listing stylesheet, scrubbed to the palette.

    HtmlFormatter bakes in its own defaults for highlighted lines (`.hll`) and line
    numbers (`.linenos`, `.special`) regardless of what PaperStyle sets, because those
    features have never been asked for. We never turn either on, so the rules are
    dropped rather than let their colours (`#ffffcc`, `#000000`, `#ffffc0`, none of
    them ours) leak into a built paper. Pygments also renders hex colours as 3-digit
    where possible and upper-case throughout, so every colour is expanded and
    lower-cased before the membership check, which raises rather than let an
    off-palette colour through silently.
    """
    from pygments.formatters import HtmlFormatter
    raw = HtmlFormatter(style=pygments_style()).get_style_defs('.listing')

    lines = [ln for ln in raw.splitlines()
             if '.hll' not in ln and 'linenos' not in ln
             and '.special' not in ln and '.lineno' not in ln]
    css = '\n'.join(lines)

    def _expand(m: re.Match) -> str:
        h = m.group(0)
        if len(h) == 4:  # '#abc' -> '#aabbcc'
            h = '#' + ''.join(c * 2 for c in h[1:])
        return h.lower()

    css = re.sub(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?', _expand, css)

    for h in re.findall(r'#[0-9a-fA-F]{6}', css):
        if h not in ALL:
            raise ValueError(f'pygments_css: colour {h} is not in the palette')
    return css
