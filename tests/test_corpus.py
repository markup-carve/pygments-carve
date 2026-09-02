"""Every definition the spec corpus pins is scoped as a definition.

WHAT THIS REPLACED, AND WHY. This file used to assert only that no corpus
document produces a ``Token.Error``. Nothing can: the ``inline`` state ends in
``(r'.', Text)``, which matches every character, and Pygments emits ``Error``
only where no rule matches. 70773 probes - random strings, every lone codepoint
to U+02FF, 40000 mutations of real corpus documents - produced zero
(markup-carve/pygments-carve#21). The check read as the repo's cover for
"constructs the inventory does not name" while being unable to fail, and
markup-carve/pygments-carve#20 - a definition on a marker line, mis-scoped in
three shapes - passed it in nine documents.

What replaced it asks something the corpus can lose. A corpus case is a source
next to the HTML the spec says it renders to, so the pair says which lines are
definitions: a definition is consumed and its ``[label]:`` text does not survive
into the HTML. This suite reads those out per document and asks the lexer to
scope them. That is the property a construct list cannot check, for the reason
the old docstring gave and the old assertion did not deliver: it measures a
construct the day the spec pin brings it in, with nobody having to name it
first.

It is deliberately one-sided. A definition-SHAPED line the corpus leaves literal
is not asserted the other way round, because the lexer over-colours some of them
knowingly - it carries no container model, so an indented definition at document
level and a marker line folding into an open paragraph are out of its reach. The
discrimination that matters is proved instead by
``test_the_gate_rejects_a_definition_whose_separator_is_broken``: the same reader
must say NO to a mutated line, or it would be measuring nothing again.
"""

import pathlib

import pytest

from pygments_carve import CarveLexer

import corpusdefs
from coverage import error_tokens

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'
DOCUMENTS = sorted(CORPUS.glob('*.crv')) if CORPUS.is_dir() else []

pytestmark = pytest.mark.skipif(
    not DOCUMENTS,
    reason='spec corpus not present; run: git submodule update --init',
)

LEXER = CarveLexer()


def _case(path):
    source = path.read_text(encoding='utf-8')
    html = path.with_suffix('.html')
    return source, (html.read_text(encoding='utf-8') if html.is_file() else '')


@pytest.mark.parametrize('path', DOCUMENTS, ids=lambda p: p.name)
def test_document_definitions_are_scoped(path):
    source, html = _case(path)
    missed = [
        (d.line, corpusdefs.scope_run(LEXER, source, d))
        for d in corpusdefs.definitions(source, html)
        if not corpusdefs.is_scoped(LEXER, source, d)
    ]
    assert not missed, (
        '%s: the corpus consumes these lines as definitions, the lexer does not '
        'scope them as one: %r' % (path.name, missed)
    )

    # Free to check on a document already lexed, and currently unable to fail -
    # the inline state's catch-all makes Error unreachable. Kept to notice if
    # that stops being true, not as coverage; see this file's docstring.
    assert not error_tokens(LEXER, source)


def test_corpus_is_substantial():
    """Guard the guard: an empty corpus would make every case above vacuous."""
    assert len(DOCUMENTS) > 500, 'expected the full corpus, found %d' % len(DOCUMENTS)


def test_the_corpus_pins_definitions_to_measure():
    """Guard the guard: a reader that finds nothing asserts nothing.

    The count is a floor, not a fixture - it moves up as the spec grows, and it
    is here so that a reader broken into silence fails instead of passing 1554
    empty documents.
    """
    total = sum(len(corpusdefs.definitions(*_case(p))) for p in DOCUMENTS)
    assert total > 100, 'only %d definitions found across the corpus' % total


def test_the_gate_rejects_a_definition_whose_separator_is_broken():
    """The reader must be able to say NO, or it is measuring nothing.

    A definition needs a literal space after the colon; without one the line is
    an ordinary paragraph. Every real definition in the corpus is mutated that
    way here, and the lexer must stop reading it as a definition. This is the
    in-suite proof that the assertion above discriminates - the property the
    check it replaced could not demonstrate.
    """
    checked = 0
    for path in DOCUMENTS:
        source, html = _case(path)
        for definition in corpusdefs.definitions(source, html):
            broken = source[:definition.offset] + source[definition.offset:].replace(
                definition.literal + ' ', definition.literal.replace(']:', ']:\t'), 1)
            if broken == source:
                continue
            checked += 1
            assert not corpusdefs.is_scoped(LEXER, broken, definition), (
                '%s: %r still reads as a definition with a tab separator, so the '
                'gate does not discriminate' % (path.name, definition.line)
            )
    assert checked > 100, 'only %d mutations exercised' % checked
