"""Every rule in the block state is pinned, and every guard clause with it.

WHAT THIS MEASURES. `test_inline_rules.py` records a sample and the whole run of
tokens the lexer colours in it for each of the 46 rules of `inlinecontent`, then
deletes each rule and requires that pin to stop holding
(markup-carve/pygments-carve#25, markup-carve/pygments-carve#29). Nothing did
that for the `block` state, and the gap was measurable the same way: at
`2f4521b`, deleting each of the 28 block rules in turn and running `CI=1 pytest`
against the mutant left **26 noticed and 2 SURVIVORS** - the `-` thematic break
and the definition-list `:` marker (markup-carve/pygments-carve#41).

Both survivors had observable behaviour, so they were missing pins rather than
dead rules. `: def` scoped its marker `Punctuation` with the rule and `Text`
without it, and deleting it changes the lexer's reading of **96 of the 1564
corpus documents**; `----` scoped `Punctuation '----'` with the rule and nothing
without it, and 2 corpus documents change.

TWO INSTRUMENTS, because the pins below are hand-written and a hand-written list
is exactly what was missing.

- The PINS: one sample per rule, recording the whole scoped run, each proved
  sharp by deleting its rule from the lexer source and requiring the pin to stop
  holding.
- The CORPUS GATE, which needs nobody to write a sample: deleting a block rule
  must change the lexer's reading of at least one corpus document. 27 of the 28
  do. The one that does not is the lone RAW fence line, and the pin is its only
  defense; that exception is recorded rather than left to be rediscovered.

WHY A GUARD NEEDS ITS OWN MUTATION. Deleting a rule tests whether the rule
exists. It cannot test a refusal: a rule that is gone also refuses everything
its guard refused, so every "this shape must not be taken" pin passes against a
deletion for the wrong reason. So each of the block state's guard clauses is
removed SEPARATELY, and `GUARDS` records the reading on both sides of that
mutation. This is the same lesson `test_bare_emphasis.py` carries for the inline
state, where two guards survived the first pass (markup-carve/pygments-carve#40).

TWO ANCHORS THAT COULD NOT FAIL were removed from the lexer rather than pinned.
The comment fence and the comment line both ended `([^\\n]*)$`, and `[^\\n]*`
already stops at the line end, so neither `$` could change a match. Measured over
all 1564 corpus documents, dropping both leaves every token stream identical.
A guard that cannot fail is the same defect as a check that cannot fail, and
`test_every_guard_clause_is_pinned` is what keeps the next one from arriving
unpinned.

WHY ONE PIN READS THE RAW RUN. The block line-comment rule emits a line's margin
as ONE `Text` token and the inline fallback emits it one character at a time.
The scoped run drops `Text` and `collapsed` joins it, so both readings make the
two identical and a pin on either would survive the rule's deletion. The margin
is not decoration - a margin that reaches no token at all is how the lexer
stopped reproducing its input in 30 documents
(markup-carve/pygments-carve#33) - so that pin reads the raw run, which is the
only reading that can see it.
"""

import collections
import pathlib
import re
import time

import pytest

from pygments.token import (
    Comment,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
)

from pygments_carve import CarveLexer

from coverage import UNSCOPED
from lexerrules import (
    build_lexer,
    lexer_source,
    rule_patterns,
    state_rules,
    without_clause,
    without_rule,
)

BLOCK = 'block'

#: The state the block state's trailing `include('inline')` pulls in. It is not
#: `inlinecontent`: `inline` is that state plus its plain-text fallbacks.
INCLUDED = 'inline'

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'
DOCUMENTS = sorted(CORPUS.glob('*.crv')) if CORPUS.is_dir() else []

LEXER = CarveLexer()
SOURCE = lexer_source()
RULES = state_rules(SOURCE, BLOCK)

corpus = pytest.mark.skipif(
    not DOCUMENTS,
    reason='spec corpus not present; run: git submodule update --init',
)


def scoped_run(lexer, sample):
    """Every token of ``sample`` that is not plain text, with its text.

    The same `UNSCOPED` the construct sweep and `test_inline_rules.py` use, so
    "scoped" means one thing across the suite.
    """
    return tuple((ttype, value) for ttype, value in lexer.get_tokens(sample)
                 if ttype not in UNSCOPED)


def raw_run(lexer, sample):
    """Every token, `Text` included. See the module docstring for the one pin
    that needs it."""
    return tuple(lexer.get_tokens(sample))


READINGS = {'scoped': scoped_run, 'raw': raw_run}


class Pin(collections.namedtuple('Pin', 'name sample expect reading note')):
    """A sample, and every token the lexer is expected to colour in it."""

    __slots__ = ()

    def __new__(cls, name, sample, expect, reading='scoped', note=''):
        return super().__new__(cls, name, sample, tuple(expect), reading, note)


#: One pin per rule of the `block` state, IN THE ORDER THE RULES APPEAR. The
#: order is what pairs a pin with its rule, and
#: `test_deleting_a_rule_removes_exactly_that_compiled_rule` is what checks the
#: pairing rather than trusting it.
PINS = [
    Pin('front matter', '---yaml\ntitle: x\n---\n',
        [(Punctuation, '---'), (Keyword.Type, 'yaml'),
         (Comment.Special, 'title: x\n'), (Punctuation, '---')]),
    Pin('comment fence', '%%%\nhidden\n%%%\n',
        [(Comment.Preproc, '%%%'), (Comment, 'hidden\n'), (Comment.Preproc, '%%%')]),
    Pin('comment line', '  %% note\n',
        [(Text, '  '), (Comment.Preproc, '%%'), (Comment, ' note'), (Text, '\n')],
        reading='raw',
        note='The margin is the whole difference from the inline rule below, '
             'and only the raw run can see it.'),
    Pin('raw fence pair', '```=html\npayload\n```\n',
        [(Punctuation, '```'), (Keyword.Type, '=html'),
         (String.Backtick, 'payload\n'), (Punctuation, '```')]),
    Pin('code fence pair', '```python\n# not a heading\n```\n',
        [(Punctuation, '```'), (Name.Builtin, 'python'),
         (String.Backtick, '# not a heading\n'), (Punctuation, '```')]),
    Pin('lone raw fence line', '```=html\nx\n',
        [(Punctuation, '```'), (Keyword.Type, '=html')],
        note='The one rule the corpus cannot see; see the corpus gate below.'),
    Pin('lone code fence line', '```js\nx\n',
        [(Punctuation, '```'), (Name.Builtin, 'js')]),
    Pin('layout container', ':::|\n',
        [(Punctuation, ':::'), (Operator, '|')]),
    Pin('container div', ':::note\n',
        [(Punctuation, ':::'), (Keyword.Namespace, 'note')]),
    Pin('caption line', '^ A caption\n',
        [(Punctuation, '^'), (Generic.Subheading, 'A caption')]),
    Pin('heading', '# Title\n',
        [(Punctuation, '#'), (Generic.Heading, 'Title')]),
    Pin('star thematic break', '***\n',
        [(Punctuation, '***')]),
    Pin('dash thematic break', '----\n',
        [(Punctuation, '----')],
        note='`---` and `- - -` read the same either way - smart typography and '
             'the bullet rule produce the same token - so the sample has to be '
             'one of the two shapes only this rule reaches '
             '(markup-carve/pygments-carve#41).'),
    Pin('underscore thematic break', '___\n',
        [(Punctuation, '___')]),
    Pin('footnote definition', '[^fn]: text\n',
        [(Punctuation, '[^'), (Name.Label, 'fn'), (Punctuation, ']:')]),
    Pin('abbreviation definition', '*[HTML]: HyperText\n',
        [(Punctuation, '*['), (Name.Entity, 'HTML'), (Punctuation, ']:')]),
    Pin('link reference definition', '[ref]: /url\n',
        [(Punctuation, '['), (Name.Label, 'ref'), (Punctuation, ']:'),
         (Name.Tag, '/url')]),
    Pin('definition-list term', ':: Term\n',
        [(Punctuation, '::'), (Generic.Heading, 'Term')]),
    Pin('definition-list definition', ': def\n',
        [(Punctuation, ':')],
        note='The marker is the whole construct here: with the rule gone the '
             'colon is plain text and nothing else in the suite read it '
             '(markup-carve/pygments-carve#41).'),
    Pin('blockquote marker', '> quoted\n',
        [(Punctuation, '>'), (Generic.Emph, ' quoted')]),
    Pin('task item', '- [x] done\n',
        [(Punctuation, '-'), (Name.Constant, '[x]')]),
    Pin('bullet', '- item\n',
        [(Punctuation, '-')]),
    Pin('ordered marker', '1. item\n',
        [(Number.Integer, '1.')]),
    Pin('bare ordinal', '. item\n',
        [(Number.Integer, '.')]),
    Pin('table header row', '|= a | b\n',
        [(Operator, '|='), (Punctuation, '|')]),
    Pin('table row', '| a | b\n',
        [(Punctuation, '|'), (Punctuation, '|')]),
    Pin('standalone attribute block', '{.a\n.b}\n',
        [(Name.Attribute, '{.a\n.b}')],
        note='It spans lines, which is what tells it from the inline form; a '
             'one-line block reads the same either way.'),
    Pin('the included inline state', 'a *b* c\n',
        [(Punctuation, '*'), (Generic.Strong, 'b'), (Punctuation, '*')]),
]


def _named(pin):
    return pin.name


def _mutants():
    return [build_lexer(without_rule(SOURCE, i, BLOCK)) for i in range(len(RULES))]


MUTANTS = _mutants()


# ----------------------------------------------------------------------------
# The reading of the lexer source
# ----------------------------------------------------------------------------

def test_the_reading_matches_what_pygments_compiled():
    """The source reading must find the rules Pygments actually compiled.

    Every test below mutates the SOURCE, so a reader that miscounts would mutate
    the wrong lines and pin a shorter list. The block state's last rule is an
    `include`, which compiles to the included state's rules rather than to one
    of its own - so the arithmetic, not a plain length, is what is checked.
    """
    assert RULES[-1][2].strip().startswith('include('), (
        "the block state's last rule is no longer an include; the count below "
        'assumes it is')
    assert len(rule_patterns(LEXER, BLOCK)) == (
        len(RULES) - 1 + len(rule_patterns(LEXER, INCLUDED))), (
        'read %d rule tuples out of the block state and %d out of %r, but '
        'Pygments compiled %d block rules. tests/lexerrules.py can no longer '
        'read the lexer source.'
        % (len(RULES), len(rule_patterns(LEXER, INCLUDED)),
           len(rule_patterns(LEXER, BLOCK))))


def test_every_block_rule_has_a_pin():
    """A rule with no pin is a rule nothing can notice the deletion of."""
    assert len(PINS) == len(RULES), (
        '%d rules in the block state and %d pins. A new rule needs a pin '
        '(sample plus its expected run); a removed rule needs its pin removed '
        'in the same diff, which is what makes the removal reviewable.'
        % (len(RULES), len(PINS)))


@pytest.mark.parametrize('index', range(len(PINS)), ids=[p.name for p in PINS])
def test_deleting_a_rule_removes_exactly_that_compiled_rule(index):
    """Source rule ``index`` is compiled rule ``index``.

    This is what earns the right to say "delete rule N" below. The include is
    the exception: it compiles to every rule of the included state at once, so
    deleting it truncates the compiled list rather than punching a hole in it.
    """
    base = rule_patterns(LEXER, BLOCK)
    got = rule_patterns(MUTANTS[index], BLOCK)
    if index == len(RULES) - 1:
        assert got == base[:index]
    else:
        assert got == base[:index] + base[index + 1:]


# ----------------------------------------------------------------------------
# The pins
# ----------------------------------------------------------------------------

@pytest.mark.parametrize('pin', PINS, ids=_named)
def test_pin_holds(pin):
    """The lexer colours the sample exactly as recorded."""
    assert READINGS[pin.reading](LEXER, pin.sample) == pin.expect, (
        'pin %r no longer holds. If the lexer is right and the pin is stale, '
        'update it - but check the change was intended: this run is the whole '
        'reason deleting a rule cannot pass unnoticed.' % pin.name)


@pytest.mark.parametrize('index', range(len(PINS)), ids=[p.name for p in PINS])
def test_pin_is_sharp(index):
    """Deleting the rule must stop its pin from holding.

    THE GATE PROVING IT CAN SAY NO. Without this the pins above are a claim;
    with it, every one of the 28 block rules is known to be undeletable in
    silence - which two of them were not (markup-carve/pygments-carve#41).
    """
    pin = PINS[index]
    assert READINGS[pin.reading](MUTANTS[index], pin.sample) != pin.expect, (
        'block rule %d was deleted and pin %r still holds, so that rule can be '
        'removed with nothing objecting. Give the pin a sample that only this '
        'rule can produce.' % (index, pin.name))


# ----------------------------------------------------------------------------
# The corpus gate
# ----------------------------------------------------------------------------

def _rule(name):
    """The index of the rule pin ``name`` describes.

    Held by name rather than by number so a rule inserted above one of these
    moves the reference with it. What pairs a name with a rule is
    `test_pin_is_sharp`, which is the same thing the order itself rests on.
    """
    return [i for i, pin in enumerate(PINS) if pin.name == name][0]


#: The one block rule no corpus document distinguishes: an opener that names a
#: raw format and never finds its closer. Every other rule changes the reading
#: of at least one document, so for this one the pin above is the only defense.
#: If the corpus grows a case, this test says so and the exception goes.
CORPUS_BLIND = _rule('lone raw fence line')


SOURCES = [p.read_text(encoding='utf-8') for p in DOCUMENTS]
BASE_READINGS = [tuple(LEXER.get_tokens(s)) for s in SOURCES]


def _changed(lexer, limit=None):
    """The documents ``lexer`` reads differently from the real one.

    ``limit`` stops the scan once that many are found. Most mutants differ on
    the first few documents, and lexing all 1564 to prove "at least one" costs
    more than the whole rest of this file.
    """
    out = []
    for path, source, before in zip(DOCUMENTS, SOURCES, BASE_READINGS):
        if tuple(lexer.get_tokens(source)) != before:
            out.append(path.stem)
            if limit is not None and len(out) >= limit:
                break
    return out


@corpus
@pytest.mark.parametrize('index', range(len(PINS)), ids=[p.name for p in PINS])
def test_the_corpus_notices_a_deleted_rule(index):
    """An instrument that needs nobody to write a sample down."""
    changed = _changed(MUTANTS[index], limit=None if index == CORPUS_BLIND else 1)
    if index == CORPUS_BLIND:
        assert not changed, (
            'block rule %d used to be invisible to the corpus, and %d documents '
            'now change when it is deleted. Drop it from CORPUS_BLIND.'
            % (index, len(changed)))
    else:
        assert changed, (
            'deleting block rule %d (%r) changes the lexer\'s reading of no '
            'corpus document at all, so only its pin stands between that rule '
            'and silent removal.' % (index, PINS[index].name))


@corpus
def test_the_corpus_reads_the_two_rules_the_ticket_was_filed_on():
    """The two survivors, and the documents that can see them.

    The definition marker is read widely; the dash thematic break is read by
    exactly two documents, which is why every ordinary sample of it was blunt.
    """
    assert sorted(_changed(MUTANTS[_rule('dash thematic break')])) == [
        '249-trailing-whitespace-after-a-block-marker',
        '326-a-column-0-line-after-a-container-s-last-block-when-that-block-'
        'left-no-paragraph-open-4',
    ]
    assert len(_changed(MUTANTS[_rule('definition-list definition')],
                        limit=51)) == 51


def test_the_dash_break_keeps_a_trailing_whitespace_run():
    """The second shape only this rule reaches, and the reason it is a shape.

    A break written with trailing whitespace is still one break: the rule takes
    the run whole, while smart typography takes `---` and leaves the spaces
    behind. Corpus `249-trailing-whitespace-after-a-block-marker` is the
    document that turns on it.
    """
    assert scoped_run(LEXER, '---  \n') == ((Punctuation, '---  '),)
    assert scoped_run(MUTANTS[_rule('dash thematic break')], '---  \n') == (
        (Punctuation, '---'),)


# ----------------------------------------------------------------------------
# One pin per guard clause
# ----------------------------------------------------------------------------

#: A lookaround, or an anchor that is not the `^` every block rule carries.
#: `test_every_guard_clause_is_pinned` reads the block rules with this and
#: requires the table below to account for every one it finds.
CLAUSE = re.compile(r"\(\?<?[=!][^()]*(?:\([^()]*\)[^()]*)*\)|\\A|(?<!\\)\$")


GUARD_FIELDS = 'name index clause occurrence sample refused taken'


class Guard(collections.namedtuple('Guard', GUARD_FIELDS)):
    """One guard clause, and the reading on both sides of removing it."""

    __slots__ = ()

    def __new__(cls, name, index, clause, occurrence, sample=None,
                refused=None, taken=None):
        return super().__new__(cls, name, index, clause, occurrence, sample,
                               None if refused is None else tuple(refused),
                               None if taken is None else tuple(taken))


GUARDS = [
    Guard('front matter opens only at the start of the document', 0, r'\A', 0,
          'p\n\n---yaml\nt: x\n---\n',
          [(Punctuation, '---'), (Punctuation, '---')],
          [(Punctuation, '---'), (Keyword.Type, 'yaml'),
           (Comment.Special, 't: x\n'), (Punctuation, '---')]),
    Guard('a front matter closer takes no trailing text', 0, '$', 0,
          '---yaml\nt: x\n--- junk\n',
          [(Punctuation, '---'), (Punctuation, '---')],
          [(Punctuation, '---'), (Keyword.Type, 'yaml'),
           (Comment.Special, 't: x\n'), (Punctuation, '---')]),
    # The blank-line guard changes no token at all; what it changes is the cost.
    # `test_the_blank_line_guard_is_what_bounds_the_closer_search` is its pin.
    Guard('a blank line inside a comment fence is not tried twice', 1, r'(?!\2)', 0),
    Guard('a wider run does not close a narrower comment fence', 1, '(?!%)', 0,
          '%%%\nhidden\n%%%%\n',
          [(Comment.Preproc, '%%'), (Comment, '%'),
           (Comment.Preproc, '%%'), (Comment, '%%')],
          [(Comment.Preproc, '%%%'), (Comment, 'hidden\n'),
           (Comment.Preproc, '%%%'), (Comment, '%')]),
    Guard('a raw block takes no title', 3, r"(?= ?=[a-zA-Z][\w+.-]*[ \t]*$)", 0,
          '```=html "T"\npayload\n```\n',
          [(Punctuation, '```'), (Keyword.Type, '=html'), (Punctuation, '```')],
          [(Punctuation, '```'), (Keyword.Type, '=html'), (String.Double, '"T"'),
           (String.Backtick, 'payload\n'), (Punctuation, '```')]),
    Guard('a raw block closer takes no trailing text', 3, '$', 1,
          '```=html\nx\n``` junk\n',
          [(Punctuation, '```'), (Keyword.Type, '=html'),
           (Punctuation, '```'), (Name.Builtin, 'junk')],
          [(Punctuation, '```'), (Keyword.Type, '=html'),
           (String.Backtick, 'x\n'), (Punctuation, '```')]),
    Guard('an info string outside the three shapes opens no block', 4,
          r"(?= ?(?:' + _FENCE_INFO + r')?[ \t]*$)", 0,
          '```js bad\ncode\n```\n',
          [(Punctuation, '```'), (Name.Builtin, 'js'), (Punctuation, '```')],
          [(Punctuation, '```'), (Name.Builtin, 'js'),
           (String.Backtick, 'code\n'), (Punctuation, '```')]),
    Guard('a code fence closer takes no trailing text', 4, '$', 1,
          '```\nx\n``` junk\n',
          [(Punctuation, '```'), (Punctuation, '```'), (Name.Builtin, 'junk')],
          [(Punctuation, '```'), (String.Backtick, 'x\n'), (Punctuation, '```')]),
    Guard('a star break is the whole line', 11, '$', 0, '*** text\n',
          [], [(Punctuation, '*** ')]),
    Guard('a dash break is the whole line', 12, '$', 0, '--- text\n',
          [(Punctuation, '---')], [(Punctuation, '--- ')]),
    Guard('an underscore break is the whole line', 13, '$', 0, '___ text\n',
          [], [(Punctuation, '___ ')]),
    Guard('a definition marker needs a space after it', 18, r'(?=[ \t])', 0,
          ':foo\n', [], [(Punctuation, ':')]),
    Guard('a blockquote marker needs a space after it', 19, r'(?=[ \t]|$)', 0,
          '>foo\n', [], [(Punctuation, '>'), (Generic.Emph, 'foo')]),
    Guard('a bullet needs a space after it', 21, r'(?=[ \t]|$)', 0,
          '-foo\n', [], [(Punctuation, '-')]),
    Guard('an ordered marker needs a space after it', 22, r'(?=[ \t]|$)', 0,
          '1.foo\n', [], [(Number.Integer, '1.')]),
    Guard('a bare ordinal needs a space after it', 23, r'(?=[ \t]|$)', 0,
          '.foo\n', [], [(Number.Integer, '.')]),
]

SAMPLED = [g for g in GUARDS if g.sample is not None]


def _guarded(guard):
    return guard.name


def test_every_guard_clause_is_pinned():
    """A guard added to a block rule must arrive with a pin.

    The rules are read for lookarounds and anchors and the result compared with
    the table, so a new guard cannot be added and left untested - which is the
    half of the sweep deletion cannot reach.
    """
    found = collections.Counter(
        (i, clause) for i, (_, _, text) in enumerate(RULES)
        for clause in CLAUSE.findall(text))
    assert found, (
        'the block rules read as carrying no guard clause at all, so this '
        'comparison asserts nothing. CLAUSE can no longer read them.')
    listed = collections.Counter((g.index, g.clause) for g in GUARDS)
    assert found == listed, (
        'the block state carries guard clauses the table does not: %r; and the '
        'table names clauses the state no longer carries: %r.'
        % (sorted(found - listed), sorted(listed - found)))


@pytest.mark.parametrize('guard', SAMPLED, ids=_guarded)
def test_the_guard_refuses_the_shape(guard):
    assert scoped_run(LEXER, guard.sample) == guard.refused, (
        'guard %r: %r no longer reads as recorded.' % (guard.name, guard.sample))


@pytest.mark.parametrize('guard', SAMPLED, ids=_guarded)
def test_removing_the_guard_takes_the_shape(guard):
    """The mutation that proves the pin above says something.

    Deleting the whole rule would make every one of these pass for the wrong
    reason, so the clause is removed on its own and the rule left in place.
    """
    mutant = build_lexer(
        without_clause(SOURCE, guard.index, guard.clause, guard.occurrence, BLOCK))
    assert scoped_run(mutant, guard.sample) == guard.taken, (
        'without guard %r the lexer is expected to read %r as %r; if it no '
        'longer does, this pin is measuring something else.'
        % (guard.name, guard.sample, guard.taken))


def _elapsed(lexer, source, repeats=3):
    def once():
        start = time.perf_counter()
        list(lexer.get_tokens(source))
        return time.perf_counter() - start
    return min(once() for _ in range(repeats))


def test_the_blank_line_guard_is_what_keeps_the_fence_search_cheap():
    """The one guard whose removal changes the cost rather than the tokens.

    Without `(?!\\2)` both alternatives of the body match a whitespace-only line
    whenever the opener sits at column 0, so an opener with no closer backtracks
    exponentially - the lexer's own comment records 22 such lines at 0.8s, each
    further line doubling it. The tokens are identical either way, so no pin on
    a reading can see this.

    The assertion is the RATIO across a fixed pair of sizes, not a stopwatch
    reading: absolute times on a machine carrying other load measure the load.
    Measured here, eight more blank lines cost the guarded lexer 1.5x and the
    unguarded one 180x.
    """
    unguarded = build_lexer(without_clause(SOURCE, 1, r'(?!\2)', 0, BLOCK))

    def blanks(n):
        return '%%%\n' + ' \n' * n

    def ratio(lexer):
        small = _elapsed(lexer, blanks(12))
        large = _elapsed(lexer, blanks(20))
        return large / max(small, 1e-9)

    guarded_ratio = ratio(LEXER)
    assert guarded_ratio < 3, (
        'eight more whitespace-only lines under an unclosed comment fence '
        'multiplied the time by %.2f, which is the growth the guard exists to '
        'stop.' % guarded_ratio)
    unguarded_ratio = ratio(unguarded)
    assert unguarded_ratio > 8, (
        'without the guard the same eight lines are expected to be far more '
        'than eight times the work (measured 180x); they were %.2fx, so this '
        'pin is measuring something else.' % unguarded_ratio)
