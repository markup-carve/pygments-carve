"""The lexer reproduces its input: no character reaches a reader in no token.

WHY THIS FILE EXISTS. Pygments' contract is that concatenating the values of
`get_tokens` gives the source back, and a consumer that reassembles a document
from its tokens - which is what an HTML formatter does - drops on the floor
whatever is in no token. This lexer did not reproduce its input in **32 of the
1564** documents of the spec corpus, and what it lost was almost entirely a
line's leading indentation (markup-carve/pygments-carve#33).

Two causes, and only one of them was a rule.

- `_MARGIN` sat OUTSIDE a capture group in the `%%` line-comment rule, whose
  action is `bygroups`. `bygroups` emits only the groups it is given, so text
  the pattern consumed outside one is never yielded. Twenty-eight documents.
- The other two are Pygments' own defaults, not a rule: `stripnl` strips a
  document's leading and trailing newlines and `ensurenl` appends one that is
  not there. Both are reasonable for a programming language and neither is for
  a language where a fence "keeps the blank line at the end of its content".
  The lexer turns them off; three documents.

The ticket read a thirty-second document, `250-line-endings-and-a-byte-order-
mark-3`, as the first cause "reached with a BOM in the margin". It is neither
cause: Pygments strips a leading byte order mark itself, before any rule runs.

WHAT NOTHING OBJECTED WITH. No suite reassembled a document. The corpus suite
reads definitions, the construct sweep asks for a token type per payload, the
inline pins compare a scoped run with plain text dropped, and the comment gate
asks which lines are commented out - so text emitted in NO token is invisible to
every one of them. It is invisible to a scope assertion by construction: a
character that is in no token has no scope to be wrong about.

WHAT IS NOT THIS LEXER'S TO REPRODUCE. Pygments strips a leading byte order mark
and normalizes CRLF before any rule runs. `preprocessed` below states those two
and is checked against Pygments' own implementation, so the gate cannot quietly
widen into excusing a real loss.
"""

import pathlib

import pytest

from pygments.token import Comment, Text

from pygments_carve import CarveLexer

from lexerrules import build_lexer, lexer_source, state_rules, without_rule

BLOCK = 'block'
LINE_RULE = 2

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'
DOCUMENTS = sorted(CORPUS.glob('*.crv')) if CORPUS.is_dir() else []

LEXER = CarveLexer()
SOURCE = lexer_source()

corpus = pytest.mark.skipif(
    not DOCUMENTS,
    reason='spec corpus not present; run: git submodule update --init',
)


def preprocessed(source):
    """What Pygments hands the rules, which is what they can reproduce.

    A leading byte order mark is removed and line endings are normalized before
    any rule runs. Neither is a lexer's decision, so neither is a loss - and
    `test_the_preprocessing_here_is_the_one_pygments_does` is what stops this
    from drifting into an excuse for one.
    """
    if source.startswith('﻿'):
        source = source[len('﻿'):]
    return source.replace('\r\n', '\n').replace('\r', '\n')


def lost(lexer, source):
    """``(what the lexer emitted, what it was given)`` when they differ."""
    emitted = ''.join(value for _, value in lexer.get_tokens(source))
    expected = preprocessed(source)
    return None if emitted == expected else (emitted, expected)


def test_the_preprocessing_here_is_the_one_pygments_does():
    """`preprocessed` must be Pygments', not a wider one of this suite's making.

    Checked against `Lexer._preprocess_lexer_input` on inputs that exercise
    every transform it makes, so a Pygments release that starts stripping
    something else fails here rather than silently excusing a loss.
    """
    samples = [
        '﻿a\n', 'a\r\nb\r\n', 'a\rb\r', '\n\n a \n\n', 'a', '',
        '﻿\n\n```\nx\n\n', '\ta\n', 'a\n\n\n',
    ]
    for sample in samples:
        assert preprocessed(sample) == LEXER._preprocess_lexer_input(sample), repr(sample)


def test_the_pygments_defaults_that_would_lose_text_are_off():
    """Stated here as well as in the lexer, because a caller can turn them on."""
    assert LEXER.stripnl is False
    assert LEXER.ensurenl is False
    assert CarveLexer(stripnl=True).stripnl is True, 'setdefault, not assignment'


@corpus
@pytest.mark.parametrize('path', DOCUMENTS, ids=lambda p: p.name)
def test_document_round_trips(path):
    source = path.read_text(encoding='utf-8')
    difference = lost(LEXER, source)
    assert difference is None, (
        '%s: the concatenated token values are not the source. A character in no '
        'token reaches no consumer - an HTML formatter reassembles a document from '
        'these. Got %r, expected %r.' % ((path.name,) + (difference or ((), ()))))


@corpus
def test_the_corpus_is_substantial():
    """Guard the guard: an empty corpus would make every case above vacuous."""
    assert len(DOCUMENTS) > 500, 'expected the full corpus, found %d' % len(DOCUMENTS)


# ----------------------------------------------------------------------------
# The gate must be able to say NO
# ----------------------------------------------------------------------------

#: The `%%` line-comment rule with its margin OUTSIDE the capture group, which
#: is how it stood before markup-carve/pygments-carve#33. Rebuilding it is the
#: only mutation that reaches this defect: deleting the rule does not lose the
#: margin, it hands the line to `inline`, which emits every character.
_REGRESSION_LINE_RULE = """            (r'^' + _MARGIN + r'(%%)([^\\n]*)$', bygroups(Comment.Preproc, Comment)),
"""


def _regression_source():
    rules = state_rules(SOURCE, BLOCK)
    first, past, text = rules[LINE_RULE]
    assert '(%%)' in text, 'block rule %d is no longer the line form' % LINE_RULE
    lines = SOURCE.split('\n')
    return '\n'.join(lines[:first]) + '\n' + _REGRESSION_LINE_RULE + '\n'.join(lines[past:])


REGRESSION = build_lexer(_regression_source())

#: The same source with the two Pygments defaults left on.
DEFAULTS = build_lexer(
    SOURCE.replace("options.setdefault('stripnl', False)", "options.setdefault('stripnl', True)")
          .replace("options.setdefault('ensurenl', False)", "options.setdefault('ensurenl', True)"))


def test_the_smallest_repro_is_reproduced_and_the_old_rule_loses_it():
    """A comment carrying a margin: two spaces that were in no token."""
    assert list(LEXER.get_tokens('  %% note\n')) == [
        (Text, '  '), (Comment.Preproc, '%%'), (Comment, ' note'), (Text, '\n')]
    assert list(REGRESSION.get_tokens('  %% note\n')) == [
        (Comment.Preproc, '%%'), (Comment, ' note'), (Text, '\n')]


@corpus
def test_the_gate_reports_the_documents_the_ticket_was_filed_on():
    """The pass above is only meaningful if this gate can reach thirty-one.

    Run over the same 1564 documents with the margin outside its group and the
    two Pygments defaults back on - the state this repository was in when the
    ticket was filed - the gate names 31, and they split cleanly: 28 from the
    rule and 3 from the defaults, with no document in both sets.

    The ticket counted 32, comparing against the SOURCE rather than against what
    Pygments hands the rules. The 32nd is `250-line-endings-and-a-byte-order-
    mark-3`, whose byte order mark Pygments strips itself before any rule runs -
    so it is not the `%%` rule "reached with a BOM in the margin", which is what
    the ticket read it as, and no lexer change could have made it round-trip.
    """
    def count(lexer):
        return len([p for p in DOCUMENTS if lost(lexer, p.read_text(encoding='utf-8'))])

    both = build_lexer(
        _regression_source()
        .replace("options.setdefault('stripnl', False)", "options.setdefault('stripnl', True)")
        .replace("options.setdefault('ensurenl', False)", "options.setdefault('ensurenl', True)"))
    assert count(both) == 31, count(both)
    assert count(REGRESSION) == 28, count(REGRESSION)
    assert count(DEFAULTS) == 3, count(DEFAULTS)
    assert count(LEXER) == 0, count(LEXER)


def test_a_fence_keeps_the_blank_line_at_the_end_of_its_content():
    """The three documents the Pygments defaults cost, in one sample.

    "Zero payload lines contribute nothing; one blank payload line contributes
    one newline. An implementation MUST NOT encode those two source shapes
    identically." With `stripnl` on they came out identically.
    """
    one = ''.join(v for _, v in LEXER.get_tokens('```\nx\n\n'))
    none = ''.join(v for _, v in LEXER.get_tokens('```\nx\n'))
    assert one == '```\nx\n\n' and none == '```\nx\n'
    assert ''.join(v for _, v in DEFAULTS.get_tokens('```\nx\n\n')) == \
        ''.join(v for _, v in DEFAULTS.get_tokens('```\nx\n'))


@corpus
@pytest.mark.parametrize('index', range(len(state_rules(lexer_source(), BLOCK))))
def test_no_block_rule_can_drop_text_when_deleted(index):
    """Deleting any block rule must not make the lexer lose characters.

    A rule that is gone hands its line to the rule below it, and every one of
    those reproduces what it consumes. So this holds under every deletion, and
    it is the sweep that says the margin defect was ONE rule rather than a habit
    spread through the state - which is what the ticket's per-rule reading
    claimed and this measures.
    """
    mutant = build_lexer(without_rule(SOURCE, index, BLOCK))
    losers = [p.name for p in DOCUMENTS if lost(mutant, p.read_text(encoding='utf-8'))]
    assert not losers, 'deleting block rule %d loses text in %d documents: %r' % (
        index, len(losers), losers[:5])
