"""Every `pip install` a reader is told to run must be one that works today.

`README.md` advertised `pip install pygments-carve` while PyPI had never served
the name, and nothing here could see it: no suite reads the documentation, and a
publish workflow that does not exist cannot report its own absence
(markup-carve/pygments-carve#59). This gate keys off PUBLISHED_TO_PYPI rather
than off the network, so it holds in CI with no egress; the release that first
uploads a distribution flips it in the same change.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Flip to True in the change that first publishes a distribution to PyPI.
PUBLISHED_TO_PYPI = False

ROOT = Path(__file__).resolve().parent.parent
SCANNED = sorted(ROOT.glob('*.md')) + sorted(ROOT.glob('docs/*.md')) + [ROOT / 'pyproject.toml']

PIP_INSTALL = re.compile(r'pip3?\s+install\s+(?P<args>[^\n`]*)')


def distribution_name() -> str:
    """Read `project.name` without tomllib, which the 3.9 leg of CI does not have."""
    text = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    match = re.search(r'(?m)^name\s*=\s*[\'"]([^\'"]+)[\'"]', text)
    assert match is not None, 'pyproject.toml declares no project name'
    return match.group(1)


def unserved_installs(text: str, name: str) -> list[str]:
    """Commands that install the distribution BY NAME from an index."""
    hits = []
    for match in PIP_INSTALL.finditer(text):
        args = match.group('args')
        targets = [a for a in args.split() if not a.startswith('-')]
        for target in targets:
            bare = target.strip('\'"')
            # A path, a VCS URL or an extras spec on a path all build from source.
            if bare.startswith(('.', '/', 'git+', 'http')) or bare.lstrip('.').startswith('['):
                continue
            if bare.split('[')[0].replace('_', '-') == name:
                hits.append(match.group(0).strip())
    return hits


@pytest.mark.skipif(PUBLISHED_TO_PYPI, reason='the distribution is on PyPI, so the name resolves')
@pytest.mark.parametrize('path', SCANNED, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_install_from_an_index_that_does_not_serve_it(path: Path) -> None:
    if not path.exists():
        pytest.skip('%s is not present' % path.name)
    hits = unserved_installs(path.read_text(encoding='utf-8'), distribution_name())
    assert hits == [], (
        '%s tells a reader to install %s from an index, and PUBLISHED_TO_PYPI is False: %r'
        % (path.relative_to(ROOT), distribution_name(), hits)
    )


def test_the_scan_reports_the_text_that_shipped_the_defect() -> None:
    """The control. A zero above is a measurement only if a positive exists."""
    before = 'pip install pygments-carve\n'
    assert unserved_installs(before, 'pygments-carve') == ['pip install pygments-carve']


def test_the_scan_accepts_the_install_paths_that_work() -> None:
    working = (
        "pip install git+https://github.com/markup-carve/pygments-carve\n"
        "pip install -e '.[test]'\n"
        "pip install .\n"
    )
    assert unserved_installs(working, 'pygments-carve') == []


def test_the_scan_reads_the_name_from_the_metadata() -> None:
    """A rename must move the gate with it, not silence it."""
    assert distribution_name() == 'pygments-carve'
