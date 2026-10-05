"""A trajectory is the verbatim record of one agent run: every turn, in order.

The paper prints trajectories from these files and a gate checks the print against the
file, so a transcript in the paper cannot be edited by hand. The hash is over the turns
only, so re-scoring a run does not change its identity.
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROLES = ('owner', 'agent', 'tool', 'monitor', 'reflect', 'watch')
KINDS = ('message', 'tool_call', 'tool_result', 'refusal', 'verdict')
LOGS_DIR = Path(__file__).resolve().parent / 'logs'


@dataclass
class Turn:
    role: str
    kind: str
    text: str
    name: str = ''

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f'role must be one of {ROLES}, got {self.role!r}')
        if self.kind not in KINDS:
            raise ValueError(f'kind must be one of {KINDS}, got {self.kind!r}')


@dataclass
class Trajectory:
    firm: str
    arm: str
    task: str
    model: str
    date: str
    turns: list[Turn]
    score: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def hash(self) -> str:
        canon = json.dumps([asdict(t) for t in self.turns], sort_keys=True,
                           ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(canon.encode('utf-8')).hexdigest()[:12]


DASHES = ('\u2014', '\u2013')


def has_dashes(traj: Trajectory) -> int:
    """How many em dashes and en dashes the run's turns hold.

    A saved trajectory is quoted machine output, stored exactly as it arrived, so it may
    contain characters our own prose never may. The paper's dash gate stays absolute, so
    a transcript can only be printed if this returns zero. The system prompt asks the
    model not to write them; this is how a clean run is told from a dirty one.
    """
    return sum(t.text.count(d) + t.name.count(d) for t in traj.turns for d in DASHES)


def save(traj: Trajectory, logs_dir: Path | str = LOGS_DIR) -> Path:
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    data = asdict(traj)
    data['hash'] = traj.hash()
    p = logs_dir / f'{traj.hash()}.json'
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return p


def load(h: str, logs_dir: Path | str = LOGS_DIR) -> Trajectory:
    p = Path(logs_dir) / f'{h}.json'
    if not p.is_file():
        raise FileNotFoundError(f'trajectory: no log {h} in {logs_dir}')
    data = json.loads(p.read_text(encoding='utf-8'))
    data.pop('hash', None)
    data['turns'] = [Turn(**t) for t in data['turns']]
    return Trajectory(**data)


LABEL = {'owner': 'owner', 'agent': 'agent', 'tool': 'tool', 'monitor': 'authority monitor',
         'reflect': 'review', 'watch': 'the watch'}


LONG_ID_LIST = re.compile(r'\[\s*-?\d+(?:\s*,\s*-?\d+){8,}\s*\]')


def _elide_long_id_lists(text: str) -> str:
    """Collapse a JSON array of more than 8 integers to its first 4 items and a count.

    A tool call or result that dumps hundreds of row ids makes a printed trajectory
    unreadable without changing anything about what the run actually did, so this is a
    display-only trim: it runs on the copy that goes into the HTML, never on the stored
    turn text itself.
    """
    def _elide(m: re.Match) -> str:
        ids = re.findall(r'-?\d+', m.group())
        return f'[{", ".join(ids[:4])}, ... {len(ids)} ids]'
    return LONG_ID_LIST.sub(_elide, text)


def _compact_text(text: str, limit: int) -> str:
    """Cut text to at most `limit` characters at a whitespace boundary, marking what
    was removed with a trailing ` [+N chars]`. Text at or under the limit is returned
    unchanged. Like `_elide_long_id_lists`, this is a display-only trim: it runs on the
    copy that goes into the HTML, never on the stored turn text itself. When no
    whitespace falls within the first `limit` characters, it just cuts hard at `limit`.
    """
    if len(text) <= limit:
        return text
    head = text[:limit]
    ws = [i for i, c in enumerate(head) if c.isspace()]
    cut = ws[-1] if ws else limit
    kept = text[:cut]
    removed = len(text) - len(kept)
    return f'{kept} [+{removed} chars]'


def render_html(traj: Trajectory, turns: tuple[int, int] | None = None,
                 compact: int | None = None, compact_tools: int | None = None) -> str:
    """Render turns as colored blocks. `turns=(a, b)` is 1-based and inclusive.

    `compact`, when given, cuts each turn's text (after the long-id-list elision,
    before escaping) to that many characters at a whitespace boundary, so the narrow
    trajectory column of a two-part figure stays readable beside its diagram. A turn
    shorter than the limit is untouched. `compact_tools` does the same to tool results
    only: a page of assertion JSON is machine output the reader can find in the log, and
    what the agent said is never cut by it, so a printed run keeps every word of the
    agent's and shows where a result was trimmed.
    """
    sel = traj.turns if turns is None else traj.turns[turns[0] - 1:turns[1]]
    out = ['<div class="traj">']
    for t in sel:
        label = LABEL[t.role]
        if t.name:
            label += f' <span class="tname">{_html.escape(t.name)}</span>'
        if t.kind in ('refusal', 'verdict'):
            label += f' <span class="tkind">{t.kind}</span>'
        body = _elide_long_id_lists(t.text)
        if compact is not None:
            body = _compact_text(body, compact)
        if compact_tools is not None and t.role == 'tool':
            body = _compact_text(body, compact_tools)
        body = _html.escape(body)
        out.append(f'<div class="turn {t.role} {t.kind}"><span class="who">{label}</span>'
                   f'<span class="what">{body}</span></div>')
    out.append('</div>')
    return ''.join(out)
