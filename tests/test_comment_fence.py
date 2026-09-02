"""A comment hides its own body and nothing else.

WHY THIS FILE EXISTS. An unterminated `%%%` used to open a block that ran to the
next blank line, so text the corpus renders as a paragraph was scoped `Comment`
and disappeared - in EIGHT corpus documents, with every gate green
(markup-carve/pygments-carve#30). Nothing objected because `test_corpus.py`
reads DEFINITIONS out of the corpus and none of the eight holds one, and because
the construct sweep runs an inventory that names no unterminated-fence
construct.

THE RULE. An opener with no matching closer ahead "does NOT open a block. The
line degrades to a `comment_line`", and PART 0's layout automaton says the same
from the layout side: "an opener without an exact-width closer is one `%%` line
comment; later lines are classified normally."

WHAT IS MEASURED HERE, IN TWO INSTRUMENTS.

- `classify` - one character per source line, `C` comment, `.` content, `_`
  blank. The whole bug is which lines are commented out, so that is the shape a
  pin records, and it reads as the document does.
- `collapsed` - the token stream with consecutive same-type tokens joined. The
  classification alone cannot tell the block line-comment rule from the inline
  trailing-comment rule, which produce the same scope; the token stream can,
  because only one of them swallows the line's leading margin.

AND THE CORPUS GATE, which is the half that does not need anyone to write a case
down: for every document, no word the corpus RENDERS may sit on a line the lexer
scopes entirely as a comment. It reports zero across 1564 documents now and
reported eight before the fix - six from the family the ticket found plus
`167-unterminated-comment-fence` and `326-...-6`, both older than that bump and
both at COLUMN 0, which is why the column-0 reservation the ticket floated as
the fix would not have closed it.
"""

import collections
import pathlib
import time

import pytest

from pygments.token import Comment, Punctuation, Text

from pygments_carve import CarveLexer

import commentlines
from lexerrules import (
    build_lexer,
    lexer_source,
    rule_patterns,
    state_rules,
    without_rule,
)

BLOCK = 'block'

#: The two rules in the block state that decide what a `%` run is: the whole
#: comment fence, then the line form it degrades to. Held by index because that
#: is what `without_rule` deletes; `test_the_indices_still_name_the_comment_rules`
#: is what keeps the indices honest as the state grows.
FENCE_RULE = 1
LINE_RULE = 2

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'
DOCUMENTS = sorted(CORPUS.glob('*.crv')) if CORPUS.is_dir() else []

LEXER = CarveLexer()
SOURCE = lexer_source()

corpus = pytest.mark.skipif(
    not DOCUMENTS,
    reason='spec corpus not present; run: git submodule update --init',
)


class Pin(collections.namedtuple('Pin', 'name source lines rule tokens')):
    """A sample, the line classification it must get, and the rule that decides."""

    __slots__ = ()

    def __new__(cls, name, source, lines, rule, tokens=None):
        return super().__new__(cls, name, source, lines, rule, tokens)


PINS = [
    Pin('terminated at column 0',
        '%%%\nhidden\n%%%\nafter\n', 'CCC._', FENCE_RULE),
    Pin('terminated at an item content column',
        '- x\n  %%%\n  body\n  %%%\ny\n', '.CCC._', FENCE_RULE),
    Pin('closer carries an insignificant tail',
        '%%% html\nsecret\n%%% end\nafter\n', 'CCC._', FENCE_RULE),
    Pin('a wider fence holds a shorter run',
        '%%%%\nhidden %%% inner\n%%%%\nafter\n', 'CCC._', FENCE_RULE),
    Pin('unterminated at column 0 is the line form',
        'before\n\n%%%\nsecret\n\nafter\n', '._C._._', LINE_RULE),
    Pin('unterminated at an item content column is the line form',
        '- x\n  %%%\ny\n', '.C._', LINE_RULE),
    Pin('a closer past a dedent is not this fence closer',
        '- x\n  %%%\ny\n  %%%\nz\n', '.C.C._', LINE_RULE),
    Pin('a wider line does not close a narrower opener',
        '- x\n  %%%\n  %%%%\nz\n', '.CC._', LINE_RULE),
    Pin('the line form keeps its own margin',
        '  %% note\nafter\n', 'C._', LINE_RULE,
        tokens=((Comment.Preproc, '%%'), (Comment, ' note'), (Text, '\nafter\n'))),
]


def _named(pin):
    return pin.name


def test_the_indices_still_name_the_comment_rules():
    """A rule inserted above them would silently move the mutations elsewhere."""
    rules = state_rules(SOURCE, BLOCK)
    assert '%%%+' in rules[FENCE_RULE][2], 'block rule %d is no longer the fence' % FENCE_RULE
    assert "(%%)" in rules[LINE_RULE][2], 'block rule %d is no longer the line form' % LINE_RULE


@pytest.mark.parametrize('pin', PINS, ids=_named)
def test_pin_holds(pin):
    got = commentlines.classify(LEXER, pin.source)
    assert got == pin.lines, (
        'pin %r: expected %r, got %r for %r' % (pin.name, pin.lines, got, pin.source))
    if pin.tokens is not None:
        assert commentlines.collapsed(LEXER, pin.source) == pin.tokens


@pytest.mark.parametrize('index', sorted({p.rule for p in PINS}))
def test_deleting_a_rule_removes_exactly_that_compiled_rule(index):
    """The lines removed are the ones behind that compiled pattern.

    This is what earns the right to say "delete rule N" below. The block state
    ends in an ``include``, so its compiled list is longer than its source list;
    the equality is asserted only over the rules that precede the include, which
    is where both mutated rules sit.
    """
    base = rule_patterns(LEXER, BLOCK)
    mutant = build_lexer(without_rule(SOURCE, index, BLOCK))
    assert rule_patterns(mutant, BLOCK) == base[:index] + base[index + 1:]


#: The rule pair that shipped markup-carve/pygments-carve#30: an opener that
#: pushes a state, and a state that closes on any run of three or more. Building
#: it back is the only mutation that can test a NEGATIVE property - the fence
#: rule must decline to match an unterminated opener - because deleting a rule
#: only ever tests what a rule does, never what it refuses to do. Four of the
#: pins below say the fence must NOT open, and this is what proves they can say
#: so; `test_the_pins_catch_the_regression_they_were_written_for` also runs the
#: corpus gate against it, which is the measurement the ticket was filed on.
_REGRESSION_OPENER = """            (r'^' + _MARGIN + r'(%%%+)([^\\n]*)(\\n)',
             bygroups(Comment.Preproc, Comment, Text), 'commentfence'),
"""

_REGRESSION_STATE = """        'commentfence': [
            (r'^[ \\t]*(%%%+)([ \\t]*)$', bygroups(Comment.Preproc, Text), '#pop'),
            (r'[^\\n]+\\n?', Comment),
        ],

"""


def _regression_source():
    """``SOURCE`` with the whole-fence rule put back the way it was in #30."""
    rules = state_rules(SOURCE, BLOCK)
    first, past, _ = rules[FENCE_RULE]
    lines = SOURCE.split('\n')
    out = '\n'.join(lines[:first]) + '\n' + _REGRESSION_OPENER + '\n'.join(lines[past:])
    anchor = "        'codeblock': ["
    assert anchor in out, 'no anchor to re-insert the commentfence state before'
    return out.replace(anchor, _REGRESSION_STATE + anchor, 1)


REGRESSION = build_lexer(_regression_source())


def _reading(lexer, source):
    return commentlines.classify(lexer, source), commentlines.collapsed(lexer, source)


@pytest.mark.parametrize('pin', PINS, ids=_named)
def test_pin_is_sharp(pin):
    """Some mutant must break every pin, or the pin is inert.

    Two mutants, because the pins assert two kinds of thing. Deleting the rule a
    pin names tests what that rule DOES. It cannot test what the fence rule
    REFUSES to do - delete it and an unterminated `%%%` still degrades, by a
    different route - so the pins for the degraded shapes are proved against the
    regression mutant instead. What this test forbids is a pin no mutation
    reaches, which is a pin recording nothing.
    """
    base = _reading(LEXER, pin.source)
    deleted = _reading(build_lexer(without_rule(SOURCE, pin.rule, BLOCK)), pin.source)
    regressed = _reading(REGRESSION, pin.source)
    assert deleted != base or regressed != base, (
        'pin %r survives both mutations - block rule %d deleted, and the #30 rule '
        'shape restored - so nothing anywhere would notice it going wrong.'
        % (pin.name, pin.rule))


def test_the_pins_catch_the_regression_they_were_written_for():
    """The #30 shape must MIS-CLASSIFY these four, not merely differ somewhere.

    Recorded rather than guessed: the fourth is the closer tail, which the old
    state also got wrong because its `#pop` demanded a bare closer line, so
    `%%% end` never closed anything. The fifth degraded shape - a wider line
    under a narrower opener - is classified the same either way and is held by
    its token run instead, which is why `test_pin_is_sharp` reads both.
    """
    broken = [p.name for p in PINS
              if commentlines.classify(REGRESSION, p.source) != p.lines]
    assert broken == [
        'closer carries an insignificant tail',
        'unterminated at column 0 is the line form',
        'unterminated at an item content column is the line form',
        'a closer past a dedent is not this fence closer',
    ], broken


@corpus
def test_the_corpus_gate_reports_the_documents_the_ticket_was_filed_on():
    """The zero above is only meaningful if this reader can reach eight.

    Run over the same 1564 documents, the #30 rule shape buries content the
    corpus renders in exactly these - the six the ticket found plus two older
    ones at COLUMN 0, which is why reserving the multi-line fence for column 0
    would not have closed it.
    """
    hits = []
    for path in DOCUMENTS:
        html = path.with_suffix('.html')
        if not html.is_file():
            continue
        if commentlines.buried(REGRESSION, path.read_text(encoding='utf-8'),
                               html.read_text(encoding='utf-8')):
            hits.append(path.name)
    assert sorted(hits) == sorted([
        '167-unterminated-comment-fence.crv',
        '326-a-column-0-line-after-a-container-s-last-block-when-that-block-'
        'left-no-paragraph-open-6.crv',
        '443-an-unterminated-comment-fence-in-a-list-item-is-the-line-form.crv',
        '443-an-unterminated-comment-fence-in-a-list-item-is-the-line-form-4.crv',
        '443-an-unterminated-comment-fence-in-a-list-item-is-the-line-form-5.crv',
        '443-an-unterminated-comment-fence-in-a-list-item-is-the-line-form-6.crv',
        '443-an-unterminated-comment-fence-in-a-list-item-is-the-line-form-7.crv',
        '443-an-unterminated-comment-fence-in-a-list-item-is-the-line-form-8.crv',
    ]), hits


def test_an_unterminated_fence_over_blank_lines_stays_linear():
    """The body alternatives must not both match the same line.

    They did in the first cut of this rule: with the opener at column 0 the
    indent backreference is empty, so `\\2[^\\n]*\\n` and `[ \\t]*\\n` both matched a
    whitespace-only line, and an opener with no closer explored every split of
    them. Cost doubled per line - 22 lines took 0.8s, 30 lines did not finish.

    The ceiling below is not a stopwatch margin on a fast run. At 40 lines the
    ambiguous form is 2**18 times the 22-line cost, which is days; a machine
    under any load either finishes this in milliseconds or does not finish.
    """
    start = time.perf_counter()
    tokens = list(LEXER.get_tokens('%%%\n' + ' \n' * 40 + 'after\n'))
    assert time.perf_counter() - start < 5
    assert (Comment.Preproc, '%%') in [(t, v) for t, v in tokens]


# ----------------------------------------------------------------------------
# The corpus gate
# ----------------------------------------------------------------------------

@corpus
@pytest.mark.parametrize('path', DOCUMENTS, ids=lambda p: p.name)
def test_no_document_hides_content_the_corpus_renders(path):
    source = path.read_text(encoding='utf-8')
    html = path.with_suffix('.html')
    if not html.is_file():
        pytest.skip('no rendered HTML beside %s' % path.name)
    hidden = commentlines.buried(LEXER, source, html.read_text(encoding='utf-8'))
    assert not hidden, (
        '%s: the corpus renders %s, and the lexer puts every one of them on a line '
        'it scopes entirely as a comment. A comment renders nothing, so this is '
        'content the reader loses.' % (path.name, ', '.join(map(repr, hidden))))


@corpus
def test_the_corpus_has_comments_to_measure():
    """Guard the guard: a reader that finds no comment asserts nothing."""
    total = sum(len(commentlines.comment_lines(LEXER, p.read_text(encoding='utf-8'))[0])
                for p in DOCUMENTS)
    assert total > 100, 'only %d comment-scoped lines across the corpus' % total


def test_the_reader_reports_a_burial_when_there_is_one():
    """The gate must be able to say YES, or the zero above measures nothing.

    A stub that scopes the whole document as a comment is the case the reader
    has to report: every rendered word is then on a comment line.
    """
    class AllComment:
        def get_tokens_unprocessed(self, source):
            yield 0, Comment, source

    hidden = commentlines.buried(AllComment(), '- x\n  %%%\ny\n',
                                 '<ul><li>x</li></ul><p>y</p>')
    assert hidden == ['x', 'y'], hidden


def test_the_reader_reports_nothing_when_nothing_is_commented():
    class NoComment:
        def get_tokens_unprocessed(self, source):
            yield 0, Punctuation, source

    assert commentlines.buried(NoComment(), '- x\n  %%%\ny\n',
                               '<ul><li>x</li></ul><p>y</p>') == []
