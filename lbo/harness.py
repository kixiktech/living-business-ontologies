# research/lbo/harness.py
"""One task, on one arm, through the Agent SDK, recorded verbatim and scored.

The agent is the same in every arm: the same model, the same policy in the same system
prompt, the same task text, the same turn and budget caps. Only the tool set differs,
and only the tool set is ever allowed to differ, because that is the claim the paper
makes. Nothing the scorer knows reaches the session.

    python3 -m lbo.harness --arms A B C --k 3 --ablations none,no_time,no_evidence

is idempotent: a run already in results/runs is not run again.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock,
                              ToolResultBlock, ToolUseBlock, UserMessage, create_sdk_mcp_server, query)

from . import score as sc
from . import tasks as tk
from . import tools as tl
from .arms import snapshot_store
from .ingest import Build, ingest
from .trajectory import LOGS_DIR, Trajectory, Turn
from .trajectory import save as save_trajectory

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
PREFIX = 'mcp__lbo__'
MAX_RESULT_CHARS = 4000

_LOCAL_PATH = re.compile(r'/(?:Users|home)/[^\s\'"]+')
# The company's name may not be written literally anywhere in this package, which is what
# `tests/test_isolation.py` enforces, so the pattern that removes it is built from its
# letters rather than spelled out. This package is the paper's artifact and may one day be
# a public repository.
_COMPANY = re.compile(''.join(chr(c) for c in (107, 105, 120, 105, 107)), re.I)
# The runtime the agent runs under knows whose login it is, and one service cycle used
# that address as the owner's. Any address outside the synthetic firms' example.com is
# the operator's, and it does not belong in a record.
_EMAIL = re.compile(r'\b[\w.+-]+@(?!example\.com\b)[\w-]+(?:\.[\w-]+)+\b')


def scrub(text: str) -> str:
    """Take the local machine out of a saved run.

    When a tool result is too large to keep inline, the host writes it to a file and hands
    the model a preview naming that file by its absolute path: a path on whoever happened
    to run the experiment, under a directory named after the company. That lands in the
    trajectory, and a trajectory is a thing the paper prints verbatim.

    The caps and the inline annotation in `tools.py` are what stop it arriving. This is
    the second line, because a record is written once and read for years, and nothing
    downstream can unpublish what a leak has already put in a paper.
    """
    return _EMAIL.sub('<email>', _COMPANY.sub('<redacted>', _LOCAL_PATH.sub('<local path>', text)))


@dataclass(frozen=True)
class RunSpec:
    task_id: str
    arm: str
    ablation: str = 'none'
    model: str = 'claude-sonnet-5'
    seed_index: int = 0
    max_turns: int = 40
    max_budget_usd: float = 1.0


def run_key(spec: RunSpec) -> tuple[str, str, str, int]:
    return (spec.task_id, spec.arm, spec.ablation, spec.seed_index)


# ---- assembling one run --------------------------------------------------------------

_NO_IDENTITY: dict[str, Build] = {}


def _no_identity_build(slug: str) -> Build:
    """The same firm ingested with no deterministic identity keys: every source id
    becomes its own entity, which is what a system without an identity decision has."""
    from .firms import FIRMS
    if slug not in _NO_IDENTITY:
        _NO_IDENTITY[slug] = ingest(FIRMS[slug][0](), identity_keys={})
    return _NO_IDENTITY[slug]


def prepare(spec: RunSpec, builds: dict[str, Build]) -> tuple[tl.RunContext, list]:
    task = tk.get(spec.task_id)
    build = _no_identity_build(task.firm) if spec.ablation == 'no_identity' else builds[task.firm]
    ctx = tl.RunContext(build=build, store=snapshot_store(build.store), arm=spec.arm,
                        ablation=spec.ablation)
    return ctx, tl.make_tools(ctx)


def allowed_tools(tools: list) -> list[str]:
    return [f'{PREFIX}{t.name}' for t in tools]


ENDINGS = ('completed', 'max_turns', 'max_budget', 'error')


def _ended_by(subtype: str, num_turns: int, max_turns: int) -> str:
    """Why the run stopped.

    A run that answers and a run that is cut off mid-thought can both produce a final
    message, so the paper has to be able to report cap hits separately rather than let
    them sit inside the failure rate looking like bad reasoning. The verdict is the
    runtime's own subtype and nothing else. The first version also called a success
    "capped" when its turn count reached the cap, and every run it called capped had in
    fact completed: the runtime's count and its cap are not the same unit (a completed
    run reported sixty-six turns under a cap of forty), so the count says nothing about
    whether the cap was hit. The count is kept on the record as `num_turns` and reported
    as what it is.
    """
    s = (subtype or '').lower()
    if 'max_turn' in s:
        return 'max_turns'
    if 'budget' in s:
        return 'max_budget'
    if s == 'success':
        return 'completed'
    return 'error'


def _result_text(block: ToolResultBlock) -> str:
    c = block.content
    if isinstance(c, list):
        parts = []
        for item in c:
            if isinstance(item, dict):
                parts.append(str(item.get('text', item)))
            else:
                parts.append(str(item))
        c = '\n'.join(parts)
    return str(c)[:MAX_RESULT_CHARS]


async def arun(spec: RunSpec, builds: dict[str, Build]) -> tuple[Trajectory, sc.Score]:
    task = tk.get(spec.task_id)
    ctx, tools = prepare(spec, builds)
    server = create_sdk_mcp_server('lbo', tools=tools)
    options = ClaudeAgentOptions(
        tools=[], allowed_tools=allowed_tools(tools), mcp_servers={'lbo': server},
        strict_mcp_config=True, permission_mode='dontAsk', setting_sources=[],
        max_turns=spec.max_turns, max_budget_usd=spec.max_budget_usd, model=spec.model,
        system_prompt=tl.system_prompt(ctx))

    turns: list[Turn] = [Turn(role='owner', kind='message', text=task.prompt)]
    names: dict[str, str] = {}
    meta: dict = {'seed_index': spec.seed_index, 'ablation': spec.ablation, 'arm': spec.arm,
                  'cost_usd': 0.0, 'num_turns': 0, 'max_turns': spec.max_turns,
                  'ended_by': 'error',
                  'sdk_version': importlib.metadata.version('claude-agent-sdk')}

    # This process runs inside a Claude Code session; the nested-session guard refuses the
    # subprocess unless the marker is out of the environment for the duration of the call.
    outer = os.environ.pop('CLAUDECODE', None)
    started = time.perf_counter()
    try:
        async for m in query(prompt=task.prompt, options=options):
            if isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, TextBlock):
                        if b.text.strip():
                            turns.append(Turn(role='agent', kind='message', text=b.text))
                    elif isinstance(b, ToolUseBlock):
                        name = b.name[len(PREFIX):] if b.name.startswith(PREFIX) else b.name
                        names[b.id] = name
                        turns.append(Turn(role='agent', kind='tool_call', name=name,
                                          text=json.dumps(b.input, default=str)))
            elif isinstance(m, UserMessage):
                for b in (m.content if isinstance(m.content, list) else []):
                    if not isinstance(b, ToolResultBlock):
                        continue
                    name = names.get(b.tool_use_id, '')
                    text = _result_text(b)
                    turns.append(Turn(role='tool', kind='tool_result', name=name, text=text))
                    if name == 'execute_action' and ('"blocked"' in text or '"refused"' in text):
                        turns.append(Turn(role='monitor', kind='refusal', name=name, text=text))
            elif isinstance(m, ResultMessage):
                meta['cost_usd'] = float(m.total_cost_usd or 0.0)
                meta['num_turns'] = int(m.num_turns or 0)
                meta['usage'] = m.usage
                meta['ended_by'] = _ended_by(m.subtype, meta['num_turns'], spec.max_turns)
                if m.subtype != 'success':
                    meta['error'] = m.subtype
    except Exception as e:                                  # noqa: BLE001 - a failed run is data
        meta['error'] = f'{type(e).__name__}: {e}'
        meta['ended_by'] = 'error'
    finally:
        if outer is not None:
            os.environ['CLAUDECODE'] = outer
    meta['duration_s'] = round(time.perf_counter() - started, 2)
    meta['executed'] = list(ctx.executed)
    meta['approvals_requested'] = list(ctx.approvals_requested)

    traj = Trajectory(firm=task.firm, arm=spec.arm, task=task.id, model=spec.model,
                      date=date.today().isoformat(), turns=turns, meta=meta)
    s = sc.score(traj, task, ctx, ctx.build.firm)
    traj.turns.append(Turn(role='reflect', kind='verdict',
                           text=f'S={s.S} P={s.P} E={s.E} C={s.C} R={s.R} '
                                f'failure={s.failure or "none"}; ' + '; '.join(s.notes)))
    traj.score = asdict(s)
    return traj, s


def run(spec: RunSpec, builds: dict[str, Build]) -> tuple[Trajectory, sc.Score]:
    return asyncio.run(arun(spec, builds))


# ---- saving ---------------------------------------------------------------------------

def save_run(traj: Trajectory, score: sc.Score, results_dir: Path | str = RESULTS_DIR,
             logs_dir: Path | str = LOGS_DIR) -> Path:
    # Scrub before anything is written and before the hash is taken, so the identity of a
    # run is the identity of what was actually saved. An error message can carry a local
    # path too, so it goes through the same pass.
    for t in traj.turns:
        t.text = scrub(t.text)
    if isinstance(traj.meta.get('error'), str):
        traj.meta['error'] = scrub(traj.meta['error'])
    save_trajectory(traj, logs_dir)
    runs = Path(results_dir) / 'runs'
    runs.mkdir(parents=True, exist_ok=True)
    rec = {'hash': traj.hash(), 'task': traj.task, 'firm': traj.firm, 'arm': traj.arm,
           'ablation': traj.meta.get('ablation', 'none'), 'model': traj.model,
           'seed_index': traj.meta.get('seed_index', 0), 'score': asdict(score),
           'cost_usd': traj.meta.get('cost_usd', 0.0), 'num_turns': traj.meta.get('num_turns', 0),
           'ended_by': traj.meta.get('ended_by', 'error'), 'date': traj.date}
    p = runs / f'{traj.hash()}.json'
    p.write_text(json.dumps(rec, indent=1) + '\n', encoding='utf-8')
    return p


def done_keys(results_dir: Path | str = RESULTS_DIR) -> set[tuple[str, str, str, int]]:
    out = set()
    for p in sorted((Path(results_dir) / 'runs').glob('*.json')):
        r = json.loads(p.read_text(encoding='utf-8'))
        out.add((r['task'], r['arm'], r['ablation'], r['seed_index']))
    return out


# ---- the plan of runs -------------------------------------------------------------------

def plan(*, arms: tuple[str, ...], k: int, task_ids: tuple[str, ...] | None,
         ablations: tuple[str, ...], model: str, max_turns: int = 40,
         max_budget_usd: float = 1.0) -> list[RunSpec]:
    """Every run the experiment asks for. The ablations only ever run on arm C, because
    an ablation is a piece of arm C's surface taken away."""
    chosen = [t for t in tk.TASKS if task_ids is None or t.id in task_ids]
    out: list[RunSpec] = []
    for ablation in ablations:
        if ablation != 'none' and 'C' not in arms:
            continue
        for t in chosen:
            if ablation != 'none' and ablation not in t.targets:
                continue
            for arm in (arms if ablation == 'none' else ('C',)):
                for seed in range(k):
                    out.append(RunSpec(t.id, arm, ablation, model, seed, max_turns, max_budget_usd))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='run the lbo experiment, one task at a time')
    ap.add_argument('--arms', nargs='+', default=['A', 'B', 'C'])
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--tasks', default='all')
    ap.add_argument('--ablations', default='none')
    ap.add_argument('--model', default='claude-sonnet-5')
    ap.add_argument('--max-turns', type=int, default=40)
    ap.add_argument('--max-budget-usd', type=float, default=1.0)
    ap.add_argument('--results-dir', default=str(RESULTS_DIR))
    a = ap.parse_args(argv)

    task_ids = None if a.tasks == 'all' else tuple(x for x in a.tasks.replace(',', ' ').split() if x)
    ablations = tuple(x for x in a.ablations.replace(',', ' ').split() if x)
    specs = plan(arms=tuple(a.arms), k=a.k, task_ids=task_ids, ablations=ablations, model=a.model,
                 max_turns=a.max_turns, max_budget_usd=a.max_budget_usd)
    done = done_keys(a.results_dir) if (Path(a.results_dir) / 'runs').is_dir() else set()
    todo = [s for s in specs if run_key(s) not in done]
    print(f'{len(specs)} runs planned, {len(specs) - len(todo)} already recorded, {len(todo)} to run')

    from .firms import FIRMS
    builds = {slug: ingest(FIRMS[slug][0]()) for slug in {tk.get(s.task_id).firm for s in todo}}
    spent = 0.0
    for i, spec in enumerate(todo, 1):
        traj, s = run(spec, builds)
        save_run(traj, s, a.results_dir)
        spent += traj.meta.get('cost_usd', 0.0)
        print(f'{i:4d}/{len(todo)}  {spec.task_id:28s} {spec.arm} {spec.ablation:12s} seed{spec.seed_index} '
              f'R={s.R} {s.failure or "ok":22s} ${traj.meta.get("cost_usd", 0.0):.4f}')
    print(f'done; ${spent:.2f} spent on {len(todo)} runs')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
