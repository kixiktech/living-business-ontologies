"""Markdown to a gated, stamped, letter-size PDF for a long-form paper.

Chrome flows and paginates the HTML; a reportlab overlay stamps the running head and
the folio into the reserved margin, because a `position: fixed` running head keeps the
coordinates it computed on page one and `counter(page)` renders as a literal 0 outside
`@page` margin boxes, which Chrome does not support. Cross-references are computed from
heading slugs and a hand-typed section number fails the build. Every listing, table,
chart and printed run is read from the files beside this module at build time, and the
build refuses a manuscript in which any of them has drifted.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# Page geometry, in inches. The side margins are set so the measure lands near 72
# characters at 11pt, which is the band academic serif setting is comfortable in. The
# top and bottom margins are deliberately larger than they need to be for text: the
# stamped runhead and folio live inside them.
PAGE_W, PAGE_H = 8.5, 11.0
MARGIN_TOP, MARGIN_BOTTOM = 1.15, 1.15
MARGIN_SIDE = 1.40
RUNHEAD_FROM_TOP = 0.72          # inches from the top edge to the runhead baseline
FOLIO_FROM_BOTTOM = 0.64         # inches from the bottom edge to the folio baseline

EM_DASH, EN_DASH = '—', '–'


# ----------------------------------------------------------------------------------
# stylesheet
# ----------------------------------------------------------------------------------

def paper_css() -> str:
    """The whole look. White, justified, Times New Roman, numbered sections.

    ON THE FONT CHOICE, which was made twice.

    STIX Two Text was the obvious pick: a Times-compatible family built for scientific
    publishing, installed here, with full Greek and math coverage. It rendered beautifully
    and it was wrong, for a reason invisible on screen.

    Chrome on this machine cannot subset and embed STIX Two Text. It falls back to
    emitting the body text as Type3 fonts with NO embedded font file, which are glyph
    drawing procedures rather than a real typeface. The page looks perfect. The text is
    degraded for extraction, indexing and accessibility, and Type3 is exactly what a
    preprint server does not want. Measured across seven installed serif families, STIX
    was the ONLY one that did this; Times New Roman, Georgia, Charter, Palatino, Hoefler
    Text and Iowan Old Style all embed correctly as subset Type0 and all carry the Greek
    the notation needs.

    So: Times New Roman, which is also the face a reader unconsciously expects from a
    paper. `check_fonts` below enforces the outcome rather than the choice, so swapping
    the family later is safe as long as the replacement actually embeds.
    """
    from lbo.palette import pygments_css, ROLE, TINT
    PYGMENTS_CSS = pygments_css()
    return f"""
@page {{
  size: {PAGE_W}in {PAGE_H}in;
  margin: {MARGIN_TOP}in {MARGIN_SIDE}in {MARGIN_BOTTOM}in {MARGIN_SIDE}in;
}}
html, body {{ margin: 0; padding: 0; background: #ffffff; color: #101010; }}
body {{
  font-family: "Times New Roman", Times, "Liberation Serif", serif;
  font-size: 11pt;
  line-height: 1.50;
  text-align: justify;
  -webkit-hyphens: auto; hyphens: auto;
  -webkit-font-feature-settings: "liga" 1, "onum" 0;
}}

/* --- title block ------------------------------------------------------------- */
.titleblock {{ text-align: center; margin: 0 0 20pt; }}
h1.title {{
  font-size: 18pt; line-height: 1.22; font-weight: 600;
  margin: 0 0 6pt; text-align: center; -webkit-hyphens: none; hyphens: none;
}}
.subtitle {{
  font-size: 11.5pt; font-style: italic; color: #333;
  margin: 0 0 16pt; text-align: center; -webkit-hyphens: none; hyphens: none;
}}
.author {{ font-size: 11.5pt; margin: 0 0 2pt; text-align: center; }}
.affil  {{ font-size: 10pt; color: #444; margin: 0 0 2pt; text-align: center; }}
.dateline {{ font-size: 10pt; color: #444; margin: 6pt 0 0; text-align: center; }}
.classification {{
  font-size: 8.5pt; letter-spacing: 0.10em; text-transform: uppercase;
  color: #555; margin: 10pt 0 0; text-align: center;
}}

/* --- abstract ---------------------------------------------------------------- */
.abstract {{ margin: 0 0.30in 16pt; font-size: 10pt; line-height: 1.46; }}
.abstract .lbl {{
  text-align: center; font-size: 10.5pt; font-weight: 600;
  margin: 0 0 5pt; letter-spacing: 0.02em;
}}
.abstract p {{ text-indent: 0; margin: 0 0 6pt; }}
.keywords {{ margin: 0 0.30in 20pt; font-size: 9.5pt; color: #333; text-align: left; }}
.keywords .lbl {{ font-style: italic; }}

/* --- headings ---------------------------------------------------------------- */
h2 {{
  font-size: 12pt; font-weight: 600; margin: 17pt 0 6pt;
  text-align: left; -webkit-hyphens: none; hyphens: none;
  break-after: avoid; page-break-after: avoid;
}}
h3 {{
  font-size: 11pt; font-weight: 600; font-style: italic; margin: 12pt 0 4pt;
  text-align: left; -webkit-hyphens: none; hyphens: none;
  break-after: avoid; page-break-after: avoid;
}}
h2 .num, h3 .num {{ font-weight: 600; font-style: normal; margin-right: 0.5em; }}

/* --- body -------------------------------------------------------------------- */
p {{ margin: 0 0 0pt; text-indent: 1.5em; orphans: 2; widows: 2; }}
h2 + p, h3 + p, .abstract p, blockquote p, li p, figure p, .eqn + p {{ text-indent: 0; }}
p + p {{ margin-top: 3.5pt; }}
em {{ font-style: italic; }}
strong {{ font-weight: 600; }}
code, .mono {{ font-family: Menlo, "SFMono-Regular", monospace; font-size: 9.2pt; }}

blockquote {{
  margin: 9pt 0.34in; padding: 0; font-size: 10.2pt; line-height: 1.45;
  border-left: 1.2px solid #bbb; padding-left: 0.22in;
}}

ul, ol {{ margin: 6pt 0 6pt 0; padding-left: 1.5em; }}
li {{ margin: 0 0 3pt; text-align: justify; }}

/* --- displayed equations ------------------------------------------------------ */
.eqn {{
  margin: 9pt 0; text-align: center; font-size: 11pt;
  break-inside: avoid; page-break-inside: avoid;
}}
.eqn i, .eqn var {{ font-style: italic; }}

/* --- figures and tables ------------------------------------------------------- */
figure {{
  margin: 11pt 0; text-align: center;
  break-inside: avoid; page-break-inside: avoid;
}}
figure svg {{ max-width: 100%; height: auto; }}
figcaption, .tabcaption {{
  font-size: 9.2pt; line-height: 1.40; color: #222;
  text-align: left; margin: 6pt 0 0; text-indent: 0;
}}
.tabcaption {{ margin: 0 0 5pt; break-after: avoid; page-break-after: avoid; }}
table.tbl caption {{ caption-side: top; text-align: left; padding: 0 0 5pt; }}
.tbl-long table.tbl {{ break-inside: auto; page-break-inside: auto; }}
.tbl-long table.tbl tr {{ break-inside: avoid; page-break-inside: avoid; }}
table.tbl thead {{ display: table-header-group; }}
figcaption .lbl, .tabcaption .lbl {{ font-weight: 600; }}

table {{
  border-collapse: collapse; width: 100%; font-size: 9.4pt; line-height: 1.34;
  margin: 0 0 11pt;
}}
table.tbl {{ break-inside: avoid; page-break-inside: avoid; }}
table.tbl thead th {{
  border-top: 1.1px solid #222; border-bottom: 0.6px solid #666;
  padding: 4pt 5pt 3.5pt; text-align: left; font-weight: 600; vertical-align: bottom;
}}
table.tbl tbody td {{
  border: 0; padding: 3.2pt 5pt; text-align: left; vertical-align: top;
}}
table.tbl tbody tr:last-child td {{ border-bottom: 1.1px solid #222; }}
table.tbl td.num, table.tbl th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

/* --- references --------------------------------------------------------------- */
ol.refs {{ font-size: 9.6pt; line-height: 1.38; padding-left: 0; list-style: none; margin: 0; }}
ol.refs li {{
  margin: 0 0 4.5pt; padding-left: 1.9em; text-indent: -1.9em; text-align: left;
  -webkit-hyphens: none; hyphens: none;
}}
ol.refs li .rn {{ display: inline-block; width: 1.9em; text-indent: 0; }}

/* --- misc --------------------------------------------------------------------- */
hr.sep {{ border: 0; border-top: 0.6px solid #bbb; margin: 14pt 0; }}
.nobreak {{ break-inside: avoid; page-break-inside: avoid; }}

/* --- listings ------------------------------------------------------------------ */
pre.listing {{
  font-family: "Menlo", "DejaVu Sans Mono", monospace; font-size: 8.4pt; line-height: 1.38;
  background: #fafafa; border: 0.6px solid #d8d8d8; padding: 7pt 9pt; margin: 8pt 0 10pt;
  white-space: pre-wrap; word-break: break-word; break-inside: avoid;
  text-align: left; hyphens: none; -webkit-hyphens: none;
}}
pre.listing code {{ font-family: inherit; }}
{PYGMENTS_CSS}

/* --- panel figures --------------------------------------------------------------- */
/* A figure whose body is HTML rather than SVG: a grid of listings, each with its own
   lettered sub-caption, under one figure number. */
.figpanel {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8pt; }}
.figpanel .panel {{ text-align: left; }}
.figpanel pre.listing {{ font-size: 7.6pt; margin: 0; }}
.panel .subcap {{ font-size: 8.6pt; text-align: center; margin-top: 2pt; }}

/* --- the two-part figure: a diagram beside a run ---------------------------------- */
.fig2col {{ display: grid; grid-template-columns: 46% 54%; gap: 8pt; align-items: start; }}
.fig2col > div {{ text-align: left; }}
.fig2col .traj {{ font-size: 7.4pt; margin: 0; }}
.fig2col .turn .who {{ flex: 0 0 74pt; font-size: 7.4pt; }}

/* --- trajectories --------------------------------------------------------------- */
.traj {{ margin: 8pt 0 10pt; font-family: "Menlo", "DejaVu Sans Mono", monospace;
  font-size: 8.2pt; line-height: 1.36; break-inside: avoid; text-align: left;
  hyphens: none; -webkit-hyphens: none; }}
.turn {{ display: flex; gap: 6pt; padding: 3.2pt 6pt; margin: 0 0 2.4pt; border-left: 2.4pt solid; text-align: left; }}
.turn .who {{ flex: 0 0 92pt; font-weight: 600; font-size: 7.6pt; letter-spacing: .3px; text-transform: uppercase; text-align: left; }}
.turn .what {{ flex: 1 1 auto; white-space: pre-wrap; word-break: break-word; text-align: left; }}
.turn .tname {{ text-transform: none; font-weight: 400; }}
.turn .tkind {{ text-transform: none; font-weight: 400; font-style: italic; }}
.turn.owner   {{ background: {TINT['owner']};   border-color: {ROLE['owner']}; }}
.turn.agent   {{ background: {TINT['agent']};   border-color: {ROLE['agent']}; }}
.turn.tool    {{ background: {TINT['tool']};    border-color: {ROLE['tool']}; }}
.turn.monitor {{ background: {TINT['monitor']}; border-color: {ROLE['monitor']}; }}
.turn.reflect {{ background: {TINT['reflect']}; border-color: {ROLE['reflect']}; }}
.turn.refusal {{ background: {TINT['fail']};    border-color: {ROLE['fail']}; }}
.turn.verdict {{ background: {TINT['pass']};    border-color: {ROLE['pass']}; }}
"""


# ----------------------------------------------------------------------------------
# markdown -> html
# ----------------------------------------------------------------------------------

def _markdown(src: str) -> str:
    """CommonMark plus tables, with raw HTML passed through.

    Raw HTML matters: figures, displayed equations and the reference list are written as
    HTML in the source because Markdown has no vocabulary for them.
    """
    from markdown_it import MarkdownIt
    md = MarkdownIt('commonmark', {'html': True, 'typographer': True}).enable('table')
    # smartquotes must be enabled EXPLICITLY. In the commonmark preset it is not in the
    # active rule set, so `typographer: True` on its own silently does nothing and the
    # paper ships with straight quotes. Verified by probing the preset directly.
    md.enable('smartquotes')
    # typographer=True switches on TWO rules. `smartquotes` is wanted: straight quotes
    # read as a text file and curly ones are part of why a paper looks like a paper.
    # `replacements` is NOT wanted and is actively dangerous here, because it rewrites
    # `--` into an en dash and `---` into an em dash, which are the two characters this
    # module exists to keep out. It would inject them AFTER check_dashes has read the
    # source and passed. So it is disabled, and check_dashes also runs on the rendered
    # HTML, because a gate that only reads the input cannot see what the renderer added.
    md.disable('replacements')
    return md.render(src)


def _number_sections(html: str) -> tuple[str, list[tuple[str, str, str]], dict[str, str]]:
    """Prefix h2 with 1,2,3 and h3 with 1.1,1.2, and collect anchors.

    Numbering is computed rather than typed, for the reason the house already learned
    about page numbers: a number typed beside a heading is copy, and inserting a section
    silently makes every later one wrong while every gate still passes.

    Heading syntax, stripped from the rendered title:
        ## What accumulates {#accumulates}     numbered, and addressable as `accumulates`
        ## References {-}                      not numbered, not in the running sequence

    Returns (html, toc, anchors) where anchors maps slug -> computed number.
    """
    toc: list[tuple[str, str, str]] = []
    anchors: dict[str, str] = {}
    state = {'h2': 0, 'h3': 0}

    def repl(m: re.Match) -> str:
        level, attrs, title = m.group(1), m.group(2) or '', m.group(3)

        slug = None
        sm = re.search(r'\s*\{#([A-Za-z0-9_-]+)\}', title)
        if sm:
            slug = sm.group(1)
            title = title[:sm.start()] + title[sm.end():]

        nonum = False
        nm = re.search(r'\s*\{-\}', title)
        if nm:
            nonum = True
            title = title[:nm.start()] + title[nm.end():]

        plain = re.sub(r'<[^>]+>', '', title).strip()
        if nonum:
            toc.append(('', level, plain))
            return f'<{level}{attrs}>{title}</{level}>'

        if level == 'h2':
            state['h2'] += 1
            state['h3'] = 0
            num = str(state['h2'])
        else:
            state['h3'] += 1
            num = f"{state['h2']}.{state['h3']}"
        if slug:
            anchors[slug] = num
        toc.append((num, level, plain))
        return f'<{level}{attrs}><span class="num">{num}</span>{title}</{level}>'

    html = re.sub(r'<(h2|h3)([^>]*)>(.*?)</\1>', repl, html, flags=re.S)
    return html, toc, anchors


def _resolve_refs(html: str, anchors: dict[str, str]) -> tuple[str, list[str]]:
    """Replace {{sec:slug}} with the computed section number.

    Returns (html, problems). A reference to a slug that does not exist is a hard
    failure rather than a silent passthrough, because the failure mode being prevented
    is a sentence that points confidently at the wrong section.
    """
    problems: list[str] = []

    def repl(m: re.Match) -> str:
        slug = m.group(1)
        if slug not in anchors:
            problems.append(f'cross-reference to unknown section {{{{sec:{slug}}}}}')
            return f'[?{slug}]'
        return anchors[slug]

    return re.sub(r'\{\{sec:([A-Za-z0-9_-]+)\}\}', repl, html), problems


def check_typed_section_numbers(src: str, label: str) -> list[str]:
    """Refuse a hand-typed section number in the prose.

    Four of these were wrong on this module's first real paper, every one off by one,
    because sections were reordered and the sentences pointing at them were not. The
    numbers are computed, so a typed one is guaranteed to rot. Use {{sec:slug}}.
    """
    out = []
    body = src.split('\n---\n', 1)[-1]
    # Normalised, not per line. The Markdown is hard-wrapped, so "Section 13" is
    # routinely split as "Section\n13" and a line-based scan reports clean. The first
    # version of this gate did exactly that and missed one.
    flat = ' '.join(body.split())
    for m in re.finditer(r'\bSections?\s+\d+', flat):
        out.append(f'{label}: hand-typed {m.group(0)!r}; use a {{{{sec:slug}}}} '
                   f'reference so it cannot go stale. Context: '
                   f'{flat[max(0, m.start() - 60):m.end() + 40]}')
    return out


def _figures(html: str, figures: dict) -> tuple[str, list[str]]:
    """Resolve {{fig:name}} into a numbered <figure>, and {{figref:name}} into "Figure N".

    Numbers are computed from order of appearance, for the same reason section numbers
    are: a figure number typed into a sentence is copy, and inserting a figure silently
    makes every later reference wrong while every gate still passes.

    A figure BODY is any block of HTML, not only an `<svg>`. The diagrams in
    `paper_figures` are SVG; a panel set is a `<div class="figpanel">` grid of listings
    and a two-part figure is a `<div class="fig2col">`. They all number together, because
    a reader counts figures and does not care what is inside one.
    """
    problems: list[str] = []
    order: dict[str, int] = {}
    for m in re.finditer(r'\{\{fig:([A-Za-z0-9_-]+)\}\}', html):
        name = m.group(1)
        if name not in order:
            order[name] = len(order) + 1

    def place(m: re.Match) -> str:
        name = m.group(1)
        if name not in figures:
            problems.append(f'unknown figure {{{{fig:{name}}}}}')
            return ''
        body, caption = figures[name]
        n = order[name]
        return (f'<figure id="fig-{name}">{body}'
                f'<figcaption><span class="lbl">Figure {n}.</span> {caption}</figcaption>'
                f'</figure>')

    html = re.sub(r'\{\{fig:([A-Za-z0-9_-]+)\}\}', place, html)

    def ref(m: re.Match) -> str:
        name = m.group(1)
        if name not in order:
            problems.append(f'reference to a figure that is never placed: {{{{figref:{name}}}}}')
            return '[?fig]'
        return f'Figure {order[name]}'

    html = re.sub(r'\{\{figref:([A-Za-z0-9_-]+)\}\}', ref, html)
    return html, problems


def _tables(html: str) -> str:
    """Give every Markdown table the booktabs-ish class, and right-align numeric cells."""
    html = html.replace('<table>', '<table class="tbl">')

    def cell(m: re.Match) -> str:
        tag, inner = m.group(1), m.group(2)
        probe = re.sub(r'<[^>]+>', '', inner).strip()
        numeric = bool(re.fullmatch(r'[-+$(]?[\d,.]+[%)]?', probe)) and any(c.isdigit() for c in probe)
        return f'<{tag} class="num">{inner}</{tag}>' if numeric else m.group(0)

    return re.sub(r'<(td|th)>(.*?)</\1>', cell, html, flags=re.S)


def _listing_html(code: str, lexer) -> str:
    """Highlight `code` with the paper's pygments style and wrap it as a listing.
    Shared by fenced-code highlighting and the {{listing:...}} placeholder, so there is
    exactly one place that knows what a listing's markup looks like."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from lbo.palette import pygments_style

    fmt = HtmlFormatter(style=pygments_style(), nowrap=True)
    out = highlight(code, lexer, fmt)
    return f'<pre class="listing"><code>{out}</code></pre>'


def _highlight_code(html: str) -> str:
    """Highlight fenced code that names a language; leave the rest alone.

    markdown-it emits <pre><code class="language-python">ESCAPED</code></pre>. We
    unescape, run pygments with the paper palette, and wrap as a listing. Code with no
    language stays a plain <pre>, which is what a transcript wants.
    """
    import html as _html
    from pygments.lexers import get_lexer_by_name

    def repl(m: re.Match) -> str:
        lang, body = m.group(1), _html.unescape(m.group(2))
        try:
            lexer = get_lexer_by_name(lang)
        except Exception:
            return m.group(0)
        return _listing_html(body, lexer)

    return re.sub(r'<pre><code class="language-([A-Za-z0-9_+-]+)">(.*?)</code></pre>',
                  repl, html, flags=re.S)


RESEARCH_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(RESEARCH_DIR, 'lbo', 'results')
CHARTS_DIR = os.path.join(RESEARCH_DIR, 'lbo', 'charts')


def _provide_listing(arg: str) -> str:
    """{{listing:path}} or {{listing:path:START-END}}, path relative to research/.

    The code printed in the paper is read from the file that runs, at build time, so a
    listing cannot drift from the implementation. A missing file or an out-of-range
    slice raises, and compose turns that into a failed build.
    """
    from pygments.lexers import get_lexer_for_filename

    path, _, rng = arg.partition(':')
    full = os.path.join(RESEARCH_DIR, path)
    if not os.path.isfile(full):
        raise ValueError(f'listing: no such file {path}')
    lines = open(full, encoding='utf-8').read().splitlines()
    if rng:
        a, _, b = rng.partition('-')
        a, b = int(a), int(b or a)
        if a < 1 or b > len(lines) or a > b:
            raise ValueError(f'listing: {path} has {len(lines)} lines, asked for {rng}')
        lines = lines[a - 1:b]
    body = '\n'.join(lines) + '\n'
    return _listing_html(body, get_lexer_for_filename(full))


def _provide_trajectory(arg: str) -> str:
    """{{trajectory:HASH}} or {{trajectory:HASH:A-B}} prints a saved run verbatim."""
    from lbo import trajectory as tj
    h, _, rng = arg.partition(':')
    traj = tj.load(h, tj.LOGS_DIR)
    turns = None
    if rng:
        a, _, b = rng.partition('-')
        turns = (int(a), int(b or a))
    return tj.render_html(traj, turns)


PROVIDERS: dict = {
    'listing': _provide_listing,
    'trajectory': _provide_trajectory,
}


def _placeholders(html: str, providers: dict) -> tuple[str, list[str]]:
    """Resolve {{name:arg}} for every registered provider. Unknown names are left for
    the figure and section stages, which have their own resolvers."""
    problems: list[str] = []

    def repl(m: re.Match) -> str:
        name, arg = m.group(1), m.group(2)
        if name not in providers:
            return m.group(0)
        try:
            return providers[name](arg)
        except Exception as e:  # noqa: BLE001
            problems.append(f'{name}:{arg}: {e}')
            return ''

    html = re.sub(r'\{\{([a-z]+):([^}]+)\}\}', repl, html)
    html = re.sub(r'<p>((?:<pre class="listing">|<div class="traj">).*?(?:</pre>|</div></div>))</p>',
                  r'\1', html, flags=re.S)
    return html, problems


def _tables_from_results(html: str) -> tuple[str, list[str]]:
    """{{table:NAME}} renders lbo/results/tables/NAME.json; {{tabref:NAME}} -> "Table N"."""
    import json as _json
    problems: list[str] = []
    order: dict[str, int] = {}
    # A table written by hand in the source (a `<div class="tabcaption">` with its own
    # number) counts too, so a generated table never repeats a number a reader has
    # already met; the hand-numbered ones have to come first in the document.
    hand = len(re.findall(r'<div class="tabcaption"><span class="lbl">Table \d+\.', html))
    for m in re.finditer(r'\{\{table:([A-Za-z0-9_/-]+)\}\}', html):
        order.setdefault(m.group(1), hand + len(order) + 1)

    def _table_path(name: str) -> str:
        # `service/NAME` reads the service loop's tables, kept apart from the public
        # experiment's so neither paper can quote the other's by accident
        if name.startswith('service/'):
            return os.path.join(str(RESULTS_DIR), 'service', 'tables', f'{name.split("/", 1)[1]}.json')
        return os.path.join(str(RESULTS_DIR), 'tables', f'{name}.json')

    def place(m: re.Match) -> str:
        name = m.group(1)
        path = _table_path(name)
        if not os.path.isfile(path):
            problems.append(f'table:{name}: no file {path}')
            return ''
        try:
            spec = _json.load(open(path, encoding='utf-8'))
            bold = {tuple(x) for x in spec.get('bold', [])}
            align = spec.get('align')
            head = ''.join(f'<th>{_esc(str(c))}</th>' for c in spec['columns'])
            rows = []
            for r, row in enumerate(spec['rows']):
                cells = []
                for c, v in enumerate(row):
                    s = _esc(str(v))
                    if (r, c) in bold:
                        s = f'<b>{s}</b>'
                    numeric = (align[c] == 'r') if align else isinstance(v, (int, float))
                    cells.append(f'<td class="num">{s}</td>' if numeric else f'<td>{s}</td>')
                rows.append('<tr>' + ''.join(cells) + '</tr>')
            n = order[name]
            # The caption is an element OF the table, not a block above it: a table taller
            # than a page has to break, and when the caption was a sibling Chrome broke
            # between the two and printed a caption alone at the foot of a page.
            cap = (f'<caption class="tabcaption"><span class="lbl">Table {n}.</span> '
                   f'{_esc(spec["caption"])}</caption>')
        except Exception as e:  # noqa: BLE001
            problems.append(f'table:{name}: {e}')
            return ''
        # A short table is kept on one page. A long one is allowed to break, with its
        # header repeated, because holding it whole pushes it to the next page and leaves
        # most of a page empty behind it.
        wrap = 'nobreak' if len(rows) <= 12 else 'tbl-long'
        return (f'<div class="{wrap}"><table class="tbl">{cap}<thead><tr>{head}</tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>')

    html = re.sub(r'\{\{table:([A-Za-z0-9_/-]+)\}\}', place, html)

    def ref(m: re.Match) -> str:
        name = m.group(1)
        if name not in order:
            problems.append(f'tabref:{name}: table never placed')
            return '[?tab]'
        return f'Table {order[name]}'

    html = re.sub(r'\{\{tabref:([A-Za-z0-9_/-]+)\}\}', ref, html)
    html = re.sub(r'<p>(<div class="(?:nobreak|tbl-long)"><table class="tbl"><caption.*?</table></div>)</p>',
                  r'\1', html, flags=re.S)
    return html, problems


def _charts(html: str, figures: dict) -> list[str]:
    """{{chart:NAME}} registers lbo/charts/NAME.svg as figure `chart-NAME` and becomes
    {{fig:chart-NAME}}, so charts and diagrams share one numbering."""
    problems: list[str] = []
    for m in re.finditer(r'\{\{chart:([A-Za-z0-9_-]+)\}\}', html):
        name = m.group(1)
        svg = os.path.join(str(CHARTS_DIR), f'{name}.svg')
        cap = os.path.join(str(CHARTS_DIR), f'{name}.caption.txt')
        if not (os.path.isfile(svg) and os.path.isfile(cap)):
            problems.append(f'chart:{name}: need {svg} and {cap}')
            continue
        try:
            figures[f'chart-{name}'] = (open(svg, encoding='utf-8').read().strip(),
                                        open(cap, encoding='utf-8').read().strip())
        except Exception as e:  # noqa: BLE001
            problems.append(f'chart:{name}: {e}')
    return problems


def _panel_sets() -> dict:
    """paper_figures.PANELS, or an empty mapping when the module is not importable.
    Kept separate so tests can monkeypatch the dict on the module and be seen here."""
    try:
        import paper_figures
        return getattr(paper_figures, 'PANELS', {})
    except ImportError:
        return {}


def _panels(html: str, figures: dict) -> list[str]:
    """{{panels:NAME}} builds one figure out of several listings.

    `paper_figures.PANELS[NAME]` is `([(sub_caption, listing_spec), ...], caption)`, where
    a listing spec is exactly what `{{listing:...}}` takes. Each cell is resolved through
    the same reader, so a panel showing a contract shows the contract that runs. The set
    is registered as figure NAME and the placeholder becomes {{fig:NAME}}, which is what
    puts panels, diagrams and charts in one numbering sequence.
    """
    problems: list[str] = []
    specs = _panel_sets()
    for m in re.finditer(r'\{\{panels:([A-Za-z0-9_-]+)\}\}', html):
        name = m.group(1)
        if name not in specs:
            problems.append(f'panels:{name}: no such panel set in paper_figures.PANELS')
            continue
        entries, caption = specs[name]
        try:
            cells = []
            for i, (subcap, spec) in enumerate(entries):
                letter = chr(ord('a') + i)
                cells.append(f'<div class="panel">{_provide_listing(spec)}'
                             f'<div class="subcap">({letter}) {subcap}</div></div>')
        except Exception as e:  # noqa: BLE001
            problems.append(f'panels:{name}: {e}')
            continue
        figures[name] = (f'<div class="figpanel">{"".join(cells)}</div>', caption)
    return problems


def _run_caption(key: str) -> str:
    """paper_figures.CAPTIONS[key], or raise. An unknown key is a hard failure for the
    same reason an unknown section is: a figure with the wrong caption under it is worse
    than no figure, and nothing downstream would notice."""
    try:
        import paper_figures
        caps = getattr(paper_figures, 'CAPTIONS', {})
    except ImportError:
        caps = {}
    if key not in caps:
        raise ValueError(f'no caption {key!r} in paper_figures.CAPTIONS')
    return caps[key]


def _turn_range(rng: str) -> tuple[int, int]:
    a, _, b = rng.partition('-')
    return int(a), int(b or a)


def _split_with_optional(arg: str, n: int, optional_at: int) -> list[str] | None:
    """Split a placeholder argument on colons where one slot may be left out.

    Both run-figure placeholders take an optional turn range and put it in a different
    place: `trajfig:HASH[:A-B]:KEY` in the middle, `fig2col:NAME:HASH[:A-B]` at the end.
    Returns `n` parts with '' standing in for the omitted slot, or None when the count
    is one the placeholder does not accept.
    """
    parts = arg.split(':')
    if len(parts) == n:
        return parts
    if len(parts) == n - 1:
        return parts[:optional_at] + [''] + parts[optional_at:]
    return None


def _trajfigs(html: str, figures: dict) -> tuple[str, list[str]]:
    """{{trajfig:HASH:KEY}} or {{trajfig:HASH:A-B:KEY}}: a saved run as a numbered figure.

    `{{trajectory:...}}` prints a run inline, which is right for a long transcript the
    prose walks through. This is the other case: a short slice a sentence points AT, so
    it needs a number and a caption. The figure takes the caption key as its name, so
    {{figref:KEY}} resolves and the run's hash never appears in a cross-reference.
    """
    problems: list[str] = []

    def place(m: re.Match) -> str:
        # an optional trailing `tools=N` trims tool results to N characters in print,
        # marked where cut; the agent's own turns are never trimmed by it
        arg, tools = m.group(1), None
        if ':tools=' in arg:
            arg, _, n = arg.rpartition(':tools=')
            tools = int(n)
        parts = _split_with_optional(arg, 3, 1)
        if parts is None:
            problems.append(f'trajfig:{m.group(1)}: expected HASH[:A-B]:CAPTION_KEY[:tools=N]')
            return ''
        h, rng, key = parts
        try:
            from lbo import trajectory as tj
            caption = _run_caption(key)
            if tools is not None:
                caption += (f' Tool results longer than {tools} characters are cut in print, '
                            'marked where cut; the agent\'s turns are complete.')
            traj = tj.load(h, tj.LOGS_DIR)
            body = tj.render_html(traj, _turn_range(rng) if rng else None, compact_tools=tools)
        except Exception as e:  # noqa: BLE001
            problems.append(f'trajfig:{m.group(1)}: {e}')
            return ''
        figures[key] = (body, caption)
        return f'{{{{fig:{key}}}}}'

    return re.sub(r'\{\{trajfig:([^}]+)\}\}', place, html), problems


def _fig2cols(html: str, figures: dict) -> tuple[str, list[str]]:
    """{{fig2col:SVGNAME:HASH[:A-B]}}: a diagram on the left, a run on the right.

    One figure, because the two halves are one argument: this is the shape, and this is
    what it looked like when it ran. The figure takes the DIAGRAM's name, so a reference
    written before the run existed keeps working.

    Choose the diagram for the space. The left column is 46% of the measure, so a 560
    wide drawing lands at under half its design size and 8.8px labels print smaller
    still. A diagram with a handful of boxes survives that; a dense one does not, and
    belongs in a figure of its own.
    """
    problems: list[str] = []

    def place(m: re.Match) -> str:
        parts = _split_with_optional(m.group(1), 3, 2)
        if parts is None:
            problems.append(f'fig2col:{m.group(1)}: expected SVGNAME:HASH[:A-B]')
            return ''
        svgname, h, rng = parts
        try:
            from lbo import trajectory as tj
            if svgname not in figures:
                raise ValueError(f'no diagram {svgname!r} in paper_figures.FIGURES')
            svg = figures[svgname][0]
            caption = _run_caption(svgname)
            traj = tj.load(h, tj.LOGS_DIR)
            run = tj.render_html(traj, _turn_range(rng) if rng else None, compact=240)
        except Exception as e:  # noqa: BLE001
            problems.append(f'fig2col:{m.group(1)}: {e}')
            return ''
        figures[svgname] = (f'<div class="fig2col"><div>{svg}</div><div>{run}</div></div>',
                            caption)
        return f'{{{{fig:{svgname}}}}}'

    return re.sub(r'\{\{fig2col:([^}]+)\}\}', place, html), problems


# ----------------------------------------------------------------------------------
# document
# ----------------------------------------------------------------------------------

@dataclass
class Paper:
    title: str
    author: str
    date: str
    body_md: str
    subtitle: str = ''
    affiliation: str = ''
    abstract_md: str = ''
    keywords: str = ''
    classification: str = ''
    runhead: str = ''
    contact: str = ''
    toc: list = field(default_factory=list)


def _front_matter(src: str) -> tuple[dict, str]:
    """Parse a leading `---` block of `key: value` pairs. Values may be multi-line when
    indented under the key. Deliberately small; this is not YAML and does not need to be.
    """
    if not src.startswith('---'):
        return {}, src
    end = src.find('\n---', 3)
    if end == -1:
        return {}, src
    head, body = src[3:end], src[end + 4:]
    meta: dict[str, str] = {}
    key = None
    for line in head.splitlines():
        if not line.strip():
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$', line)
        if m and not line.startswith((' ', '\t')):
            key = m.group(1)
            meta[key] = m.group(2).strip()
        elif key:
            meta[key] = (meta[key] + ' ' + line.strip()).strip()
    return meta, body.lstrip('\n')


def compose(src: str) -> tuple[str, Paper]:
    """Markdown source with front matter -> a complete HTML document."""
    meta, body_md = _front_matter(src)
    paper = Paper(
        title=meta.get('title', 'Untitled'),
        subtitle=meta.get('subtitle', ''),
        author=meta.get('author', ''),
        affiliation=meta.get('affiliation', ''),
        date=meta.get('date', ''),
        abstract_md=meta.get('abstract', ''),
        keywords=meta.get('keywords', ''),
        classification=meta.get('classification', ''),
        runhead=meta.get('runhead', ''),
        contact=meta.get('contact', ''),
        body_md=body_md,
    )

    body = _markdown(body_md)
    body, toc, anchors = _number_sections(body)
    body, ref_problems = _resolve_refs(body, anchors)
    body, ph_problems = _placeholders(body, PROVIDERS)
    body, tab_problems = _tables_from_results(body)
    try:
        import paper_figures
        figures = dict(paper_figures.FIGURES)
    except ImportError:
        figures = {}
    chart_problems = _charts(body, figures)
    body = re.sub(r'\{\{chart:([A-Za-z0-9_-]+)\}\}', r'{{fig:chart-\1}}', body)
    panel_problems = _panels(body, figures)
    body = re.sub(r'\{\{panels:([A-Za-z0-9_-]+)\}\}', r'{{fig:\1}}', body)
    body, traj_problems = _trajfigs(body, figures)
    body, two_problems = _fig2cols(body, figures)
    body, fig_problems = _figures(body, figures)
    all_problems = (ref_problems + ph_problems + tab_problems + chart_problems
                    + panel_problems + traj_problems + two_problems + fig_problems)
    if all_problems:
        raise SystemExit('paper_kit: ' + '; '.join(all_problems))
    body = _tables(body)
    body = _highlight_code(body)
    paper.toc = toc

    head = [f'<h1 class="title">{_esc(paper.title)}</h1>']
    if paper.subtitle:
        head.append(f'<div class="subtitle">{_esc(paper.subtitle)}</div>')
    if paper.author:
        head.append(f'<div class="author">{_esc(paper.author)}</div>')
    if paper.affiliation:
        head.append(f'<div class="affil">{_esc(paper.affiliation)}</div>')
    if paper.contact:
        head.append(f'<div class="affil">{_esc(paper.contact)}</div>')
    if paper.date:
        head.append(f'<div class="dateline">{_esc(paper.date)}</div>')
    if paper.classification:
        head.append(f'<div class="classification">{_esc(paper.classification)}</div>')

    blocks = [f'<div class="titleblock">{"".join(head)}</div>']
    if paper.abstract_md:
        inner = _markdown(paper.abstract_md)
        blocks.append(f'<div class="abstract"><div class="lbl">Abstract</div>{inner}</div>')
    if paper.keywords:
        blocks.append(
            f'<div class="keywords"><span class="lbl">Keywords:</span> {_esc(paper.keywords)}</div>')
    blocks.append(body)

    doc = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{_esc(paper.title)}</title>'
        f'<style>{paper_css()}</style></head><body>\n'
        + '\n'.join(blocks)
        + '\n</body></html>\n'
    )
    return doc, paper


def _esc(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


# ----------------------------------------------------------------------------------
# render and stamp
# ----------------------------------------------------------------------------------

def render_pdf(html_path: str, pdf_path: str) -> None:
    """Render with headless Chrome.

    The paths are made absolute before the file:// URL is built. A relative path yields
    `file://build/paper.html`, which Chrome parses as a HOST named `build`, fails to
    reach, and then renders its own "This site can't be reached" error page into a
    perfectly valid one-page PDF. Nothing raises. That is how this function shipped its
    first defect, and it is why `verify_render` below exists.
    """
    html_path, pdf_path = os.path.abspath(html_path), os.path.abspath(pdf_path)
    subprocess.run(
        [CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
         '--run-all-compositor-stages-before-draw', '--virtual-time-budget=8000',
         '--print-to-pdf=' + pdf_path, 'file://' + html_path],
        check=True, capture_output=True, text=True,
    )


def verify_render(pdf_path: str, words: int, title: str) -> list[str]:
    """Check the RENDERED ARTEFACT, not the source that produced it.

    Every other gate in this module reads the Markdown or the HTML. None of them can see
    a render that succeeded at the process level and produced the wrong document. Three
    checks, each earned:

      1. A browser error page rendered instead of the paper.
      2. A page count implausible for the word count, which catches a silently truncated
         or collapsed render.
      3. The title absent from page one, which catches a wrong or stale input file.
    """
    import pypdf
    out: list[str] = []
    reader = pypdf.PdfReader(pdf_path)
    pages = len(reader.pages)
    first = reader.pages[0].extract_text() or ''

    for marker in ('ERR_', "site can", 'webpage at', 'ERR_INVALID_URL'):
        if marker in first:
            out.append(f'{pdf_path}: a browser error page was rendered, not the paper')
            break

    # 300 words a page is a loose floor for 11pt justified prose; 700 a loose ceiling.
    lo, hi = max(1, words // 700), max(2, words // 300 + 3)
    if not lo <= pages <= hi:
        out.append(f'{pdf_path}: {pages} pages for {words:,} words is outside the '
                   f'plausible band {lo} to {hi}; the render is probably truncated')

    probe = ' '.join(title.split()[:4]).lower()
    if probe and probe not in ' '.join(first.split()).lower():
        out.append(f'{pdf_path}: page one does not carry the title {title!r}')
    return out


def stamp(pdf_in: str, pdf_out: str, runhead: str = '', folio: bool = True,
          skip_first: bool = True) -> int:
    """Draw the running head and folio into the reserved page margins.

    This is done after rendering rather than in CSS because a `position: fixed` element
    in Chrome repeats on every page but keeps the position it computed on page one, so
    it walks into the body text. Stamping also lets page one carry neither, which is how
    the reference papers are set.
    """
    import pypdf
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    src = pypdf.PdfReader(pdf_in)
    out = pypdf.PdfWriter()
    n = len(src.pages)
    for i, page in enumerate(src.pages):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        if not (skip_first and i == 0):
            if runhead:
                c.setFont('Times-Roman', 8.2)
                c.setFillGray(0.42)
                c.drawCentredString(letter[0] / 2.0,
                                    letter[1] - RUNHEAD_FROM_TOP * 72, runhead)
            if folio:
                c.setFont('Times-Roman', 9.2)
                c.setFillGray(0.28)
                c.drawCentredString(letter[0] / 2.0, FOLIO_FROM_BOTTOM * 72, str(i + 1))
        c.showPage()      # always emit a page, even when nothing was drawn on it
        c.save()
        buf.seek(0)
        page.merge_page(pypdf.PdfReader(buf).pages[0])
        out.add_page(page)
    with open(pdf_out, 'wb') as fh:
        out.write(fh)
    return n


# ----------------------------------------------------------------------------------
# gates
# ----------------------------------------------------------------------------------

def check_dashes(text: str, label: str) -> list[str]:
    """No em dashes, no en dashes, anywhere a person outside the company reads (Kix,
    2026-09-09). Kept for these papers on purpose even though every other house copy rule
    is dropped: a founder's research paper published in 2026 gets read for whether a
    machine wrote it, and the em dash is the most cited tell there is.
    """
    bad = []
    for i, line in enumerate(text.splitlines(), 1):
        for ch, name in ((EM_DASH, 'EM DASH'), (EN_DASH, 'EN DASH')):
            if ch in line:
                col = line.index(ch)
                bad.append(f'{label}:{i}:{col}: {name} in: {line[max(0, col-42):col+42].strip()}')
    return bad


def check_typography(html: str, label: str) -> list[str]:
    """Cheap structural checks that a visual gate cannot see and a reader always does."""
    out = []
    if re.search(r'</(h2|h3)>\s*</(body|div)>', html):
        out.append(f'{label}: a heading is the last thing in the document')
    # A printed run and a printed listing are quoted machine output: a SQL result is a
    # JSON array of arrays and prints as '[[', which is not a placeholder anyone left.
    prose = re.sub(r'<div class="traj">.*?</div></div>', ' ', html, flags=re.S)
    prose = re.sub(r'<pre class="listing">.*?</pre>', ' ', prose, flags=re.S)
    for stray in ('TODO', 'TKTK', 'FIXME', 'XXX', '[[', ']]'):
        if stray in prose:
            out.append(f'{label}: placeholder {stray!r} left in the text')
    for ch in html:
        if unicodedata.category(ch) == 'Co':
            out.append(f'{label}: private-use character U+{ord(ch):04X} in the text')
            break
    return out


def check_fonts(pdf_path: str) -> list[str]:
    """Every font must be a real, embedded typeface. No Type3.

    This exists because the first version of these papers shipped with the entire body
    text as Type3 fonts carrying no embedded font file, and nothing noticed: the pages
    rendered perfectly, the visual gate passed, and the defect is invisible unless you
    open the font dictionaries. Type3 fonts are glyph drawing procedures rather than a
    typeface, they degrade text extraction and accessibility, and preprint servers do not
    want them.

    Base-14 fonts (Times-Roman, Helvetica) are permitted unembedded, because they are
    guaranteed present in every conforming reader and are what the folio overlay uses.
    """
    import pypdf
    BASE14_OK = {'Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic',
                 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Courier'}
    problems, type3, unembedded = [], 0, set()
    reader = pypdf.PdfReader(pdf_path)
    for page in reader.pages:
        res = page.get('/Resources')
        if res is None:
            continue
        for _name, ref in (res.get_object().get('/Font') or {}).items():
            fo = ref.get_object()
            subtype = str(fo.get('/Subtype', ''))
            base = str(fo.get('/BaseFont', '')).lstrip('/')
            if subtype == '/Type3':
                type3 += 1
                continue
            if base.split('+')[-1] in BASE14_OK:
                continue
            desc = fo.get('/FontDescriptor')
            if desc is None and subtype == '/Type0':
                kids = fo.get('/DescendantFonts')
                if kids:
                    desc = kids.get_object()[0].get_object().get('/FontDescriptor')
            d = desc.get_object() if desc is not None else {}
            if not any(k in d for k in ('/FontFile', '/FontFile2', '/FontFile3')):
                unembedded.add(base or '<unnamed>')
    if type3:
        problems.append(
            f'{pdf_path}: {type3} Type3 font reference(s). The body face is not embedding. '
            f'Change the font family; see check_fonts in paper_kit.')
    if unembedded:
        problems.append(f'{pdf_path}: fonts present but not embedded: {sorted(unembedded)}')
    return problems


def write_metadata(pdf_path: str, paper: 'Paper') -> None:
    """Put the paper's identity inside the file.

    A PDF whose Title is empty and whose Producer reads 'pypdf' looks like a draft
    somebody exported by accident. Preprint servers, reference managers and Google
    Scholar all read these fields, and a reader who saves the file sees the Title in
    their window bar rather than a filename.
    """
    import datetime
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    stamp = datetime.datetime.now().strftime("D:%Y%m%d%H%M%S") + "Z"
    writer.add_metadata({
        '/Title': paper.title,
        '/Author': paper.author,
        '/Subject': paper.subtitle or paper.title,
        '/Keywords': paper.keywords,
        '/Creator': 'paper_kit',
        '/Producer': 'paper_kit (headless Chrome + pypdf)',
        '/CreationDate': stamp,
        '/ModDate': stamp,
    })
    with open(pdf_path, 'wb') as fh:
        writer.write(fh)


# ----------------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------------

def build(md_path: str, out_stem: str, verbose: bool = True) -> dict:
    """Markdown source -> gated, stamped PDF. Returns a small report dict."""
    src = open(md_path, encoding='utf-8').read()

    label = os.path.basename(md_path)
    problems = check_dashes(src, label)
    problems += check_typed_section_numbers(src, label)
    # The window / base / population gates. These catch the one class a figure trace
    # cannot: a correct number describing the wrong thing. Three such defects shipped in
    # the worked examples while 57 arithmetic tests passed. See research/case_gates.py.
    try:
        import case_gates
        problems += [f'{label}: {p}' for p in case_gates.run(src)]
    except ImportError:
        print('WARNING: case_gates not importable; case checks skipped', file=sys.stderr)
    doc, paper = compose(src)
    problems += check_typography(doc, os.path.basename(md_path))
    if problems:
        for p in problems:
            print('GATE FAIL: ' + p, file=sys.stderr)
        raise SystemExit(f'paper_kit: {len(problems)} problem(s); nothing was written.')

    html_path, raw_pdf, pdf_path = out_stem + '.html', out_stem + '.raw.pdf', out_stem + '.pdf'
    with open(html_path, 'w', encoding='utf-8') as fh:
        fh.write(doc)
    render_pdf(html_path, raw_pdf)

    words = len(re.sub(r'<[^>]+>', ' ', doc).split())
    # The rendered document, not just the source that produced it.
    rendered_dashes = check_dashes(doc, os.path.basename(html_path))
    if rendered_dashes:
        for d in rendered_dashes:
            print('GATE FAIL (rendered): ' + d, file=sys.stderr)
        raise SystemExit('paper_kit: the renderer introduced a banned dash.')

    render_problems = verify_render(raw_pdf, words, paper.title)
    if render_problems:
        for p in render_problems:
            print('RENDER GATE FAIL: ' + p, file=sys.stderr)
        raise SystemExit('paper_kit: the rendered PDF did not pass verification.')

    pages = stamp(raw_pdf, pdf_path, runhead=paper.runhead)
    os.remove(raw_pdf)
    write_metadata(pdf_path, paper)

    font_problems = check_fonts(pdf_path)
    if font_problems:
        for p in font_problems:
            print('FONT GATE FAIL: ' + p, file=sys.stderr)
        raise SystemExit('paper_kit: the PDF has font problems; see above.')
    report = {
        'title': paper.title, 'pages': pages, 'words': words,
        'html': html_path, 'pdf': pdf_path,
        'sections': sum(1 for n, lvl, _ in paper.toc if lvl == 'h2' and n),
        'bytes': os.path.getsize(pdf_path),
    }
    if verbose:
        print(f"  {paper.title}")
        print(f"    {report['sections']} sections | {words:,} words | {pages} pages "
              f"| {report['bytes']:,} bytes")
        print(f"    {pdf_path}")
    return report
