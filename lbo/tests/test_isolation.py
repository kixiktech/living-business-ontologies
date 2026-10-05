"""lbo is the paper's artifact and may become a public repository. It imports nothing
from the company repository it lives in and never names the company."""
import re
from pathlib import Path

LBO = Path(__file__).resolve().parents[1]
BANNED_IMPORTS = re.compile(r'^\s*(from|import)\s+(code|clients|mission_control|simulator|pipeline)\b', re.M)
COMPANY = re.compile(r'kixik', re.I)
# Saved runs and their result records are quoted machine output, stored exactly as it
# arrived. They are exempt from the dash and emoji sweep and from nothing else: the
# company-name and import sweeps still cover them, and the paper's own dash gate stays
# absolute, which is what `trajectory.has_dashes` is for: it tells a printable run from
# the rest rather than letting one be edited into shape.
VERBATIM = ('logs', 'results')


def _py_files():
    return [p for p in LBO.rglob('*.py')]


def _is_verbatim(p: Path) -> bool:
    return any(part in VERBATIM for part in p.relative_to(LBO).parts[:-1])


def test_no_import_from_the_house():
    for p in _py_files():
        assert not BANNED_IMPORTS.search(p.read_text(encoding='utf-8')), p


def test_never_names_the_company():
    # This file's own detector necessarily spells out the banned word; it is the one
    # file in the tree that is allowed to, because it is what looks for it everywhere
    # else.
    for p in LBO.rglob('*'):
        if p == Path(__file__):
            continue
        if p.is_file() and p.suffix in ('.py', '.md', '.json', '.txt', '.svg'):
            assert not COMPANY.search(p.read_text(encoding='utf-8', errors='ignore')), p


def test_no_dashes_or_emoji_in_the_prose_we_write():
    # Same exemption as above: this file's own regex literally contains the banned
    # character range as its boundary, so it is excluded from its own sweep. Saved runs
    # and result records are excluded too, because they are what a model wrote, not what
    # we wrote; see VERBATIM.
    for p in LBO.rglob('*'):
        if p == Path(__file__) or _is_verbatim(p):
            continue
        if p.is_file() and p.suffix in ('.py', '.md', '.json', '.txt'):
            text = p.read_text(encoding='utf-8', errors='ignore')
            assert chr(0x2014) not in text and chr(0x2013) not in text, p
            assert not re.search(r'[\U0001F300-\U0001FAFF☀-➿]', text), p
