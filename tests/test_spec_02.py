"""Exercise every 0.2 conformance source with the public lexer."""

import json
import os
from pathlib import Path

import pytest
from pygments.token import Error

from pygments_carve import CarveLexer

ROOT = Path(os.environ.get('CARVE_SPEC_02', 'spec-02'))
CORPUS = ROOT / 'spec' / '0.2' / 'conformance'
if not CORPUS.is_dir() and not os.environ.get('CI'):
    pytest.skip('clone carve next2 to spec-02 for corpus checks', allow_module_level=True)

GRAMMAR_CASES = Path(__file__).resolve().parents[1] / 'carve-grammars' / 'tests' / 'carve-spec-cases.json'


def inputs():
    assert GRAMMAR_CASES.is_file(), 'the pinned 0.2 grammar inventory is missing'
    assert CORPUS.is_dir(), 'the 0.2 spec corpus is missing'
    rows = []
    for file in ('examples.json', 'clause-cases.json'):
        payload = json.loads((CORPUS / file).read_text())
        rows.extend((row['id'], row['input']) for row in payload.get('examples', payload.get('cases', []))
                    if isinstance(row.get('input'), str))
    assert len(rows) >= 900, f'only {len(rows)} 0.2 corpus sources'
    return rows


@pytest.mark.parametrize('case, source', inputs())
def test_public_lexer_preserves_every_spec_source(case, source):
    tokens = list(CarveLexer().get_tokens(source))
    assert ''.join(value for _, value in tokens) == source.replace('\r\n', '\n').replace('\r', '\n'), case
    assert not any(token in Error for token, _ in tokens), case


def test_shared_grammar_cases_are_in_the_spec_corpus():
    spec_ids = {case for case, _ in inputs()}
    upgrade = json.loads((ROOT / 'spec' / '0.2' / 'data' / 'upgrade-map.json').read_text())
    spec_ids.update(row['id'] for row in upgrade['source'])
    shared_ids = {row['id'] for row in json.loads(GRAMMAR_CASES.read_text())}
    assert len(shared_ids) >= 26
    assert shared_ids <= spec_ids
