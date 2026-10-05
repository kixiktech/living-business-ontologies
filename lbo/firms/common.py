# research/lbo/firms/common.py
"""The generator framework: seeded, deterministic, and honest about time.

A Source is what a real integration hands over: a list of records in the source's own
vocabulary, with the source's own ids and the time each record was entered. The
ontology is built from these by `ingest`, never written directly, so the build the
paper prints is the build a real firm would get.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

NOW = datetime(2026, 7, 1, 8, 0)
START = date(2025, 1, 1)
END = date(2026, 7, 1)


@dataclass
class Source:
    name: str
    exported_at: datetime
    records: list[dict]
    id_field: str
    description: str


@dataclass
class Firm:
    slug: str
    name: str
    industry: str
    seed: int
    sources: dict[str, Source]
    policy_md: str
    grants: list[dict]
    answer_key: dict
    notes: list[str] = field(default_factory=list)


def quarters() -> list[tuple[str, date, date]]:
    out = []
    y, m = START.year, START.month
    while date(y, m, 1) < END:
        q = (m - 1) // 3 + 1
        s = date(y, m, 1)
        m2, y2 = (m + 3, y) if m + 3 <= 12 else (m + 3 - 12, y + 1)
        e = date(y2, m2, 1)
        out.append((f'{y}Q{q}', s, e))
        y, m = y2, m2
    return out


def quarter_of(d: date) -> str:
    return f'{d.year}Q{(d.month - 1) // 3 + 1}'


def weeks(start: date, end: date, week_starts: int) -> list[tuple[date, date]]:
    """Whole weeks inside [start, end), each beginning on the given Python weekday."""
    d = start
    while d.weekday() != week_starts:
        d += timedelta(days=1)
    out = []
    while d + timedelta(days=7) <= end:
        out.append((d, d + timedelta(days=7)))
        d += timedelta(days=7)
    return out


def money(x: float) -> float:
    return round(float(x) + 0.0, 2)


def pct(a: float, b: float) -> float:
    return round(100.0 * a / b, 2) if b else 0.0


def _json_default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def write_sources(firm: Firm, out_dir: Path | str) -> list[Path]:
    d = Path(out_dir) / firm.slug
    d.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, src in firm.sources.items():
        p = d / f'{name}.json'
        p.write_text(json.dumps(asdict(src), indent=1, default=_json_default) + '\n', encoding='utf-8')
        paths.append(p)
    return paths


def write_answer_key(firm: Firm, out_dir: Path | str) -> Path:
    d = Path(out_dir) / firm.slug
    d.mkdir(parents=True, exist_ok=True)
    p = d / 'answer_key.json'
    p.write_text(json.dumps(firm.answer_key, indent=1, default=_json_default, sort_keys=True) + '\n',
                 encoding='utf-8')
    return p


def write_policy(firm: Firm, out_dir: Path | str) -> Path:
    d = Path(out_dir) / firm.slug
    d.mkdir(parents=True, exist_ok=True)
    p = d / 'policy.md'
    p.write_text(firm.policy_md, encoding='utf-8')
    return p


def fingerprint(firm: Firm) -> str:
    canon = json.dumps({k: asdict(v) for k, v in sorted(firm.sources.items())},
                       sort_keys=True, default=_json_default, separators=(',', ':'))
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()[:12]
