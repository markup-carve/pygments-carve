"""The lexer produces no Error tokens over the spec corpus.

This is a weak check on its own - a lexer that emits everything as plain text
also passes it - which is why test_constructs.py measures scope. What this adds
is the other half: over 1300 real documents, no input drives the state machine
into a position where nothing matches. That is the failure a construct list
cannot find, because it only contains constructs someone thought of.
"""

import pathlib

import pytest

from pygments_carve import CarveLexer

from coverage import error_tokens

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'
DOCUMENTS = sorted(CORPUS.glob('*.crv')) if CORPUS.is_dir() else []

pytestmark = pytest.mark.skipif(
    not DOCUMENTS,
    reason='spec corpus not present; run: git submodule update --init',
)

LEXER = CarveLexer()


@pytest.mark.parametrize('path', DOCUMENTS, ids=lambda p: p.name)
def test_document_lexes_without_error_tokens(path):
    source = path.read_text(encoding='utf-8')
    errors = error_tokens(LEXER, source)
    assert not errors, '%s produced Error tokens: %r' % (path.name, errors[:5])


def test_corpus_is_substantial():
    """Guard the guard: an empty corpus would make every case above vacuous."""
    assert len(DOCUMENTS) > 500, 'expected the full corpus, found %d' % len(DOCUMENTS)
