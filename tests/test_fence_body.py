"""A fenced body is opaque, and front matter survives a blank line.

WHY THIS FILE EXISTS. The lexer's docstring said "a fence body is opaque:
nothing inside it is Carve" while the state that was supposed to deliver that
NEVER RAN - it was pushed with the cursor on the opener's newline, no rule in it
matched a newline, and Pygments reset the stack before one body character was
read. Across the 1564-document spec corpus, no document produced a fence-body
token at all: `# x` inside a ```` ```python ```` block was scoped as a heading
and `*b*` as bold (markup-carve/pygments-carve#32). Front matter escaped the
same way at its first blank line.

WHAT IS MEASURED, IN TWO INSTRUMENTS.

- The CORPUS GATE, which needs nobody to write a fence down: `fencebodies` pairs
  the fences in a source by the grammar's own rule, and every character between
  a pair must carry a VERBATIM scope. It reports zero across the corpus now and
  71 documents against the pre-fix rule shape, so the zero is known to be a
  measurement rather than a silence.
- PINS on the shapes a corpus of three-line bodies does not reach: a fence that
  holds a shorter fence as sample text, an indented run that is body rather than
  a closer, an opener that never pairs, and front matter over a blank line.

AND THE COST. Requiring a closer means an opener that never finds one scans what
is left of the document, so `test_the_closer_search_is_linear` holds the bound
that keeps a file of unpairable openers from being quadratic.
"""

import pathlib
import time

import pytest

from pygments.token import Comment, Generic, Keyword, Name, Punctuation, String, Text

from pygments_carve import CarveLexer
from pygments_carve.lexer import _FENCE_BODY_LINES

import commentlines
import fencebodies
from lexerrules import build_lexer, lexer_source, rule_patterns, state_rules, without_rule

BLOCK = 'block'

#: The block rules that decide a fence. Held by index because that is what
#: `without_rule` deletes; `test_the_indices_still_name_the_fence_rules` keeps
#: them honest as the state grows.
FRONTMATTER_RULE = 0
RAW_PAIR_RULE = 3
CODE_PAIR_RULE = 4
LONE_RAW_RULE = 5
LONE_CODE_RULE = 6

#: What a fenced body may be scoped as. `Name.Constant` is the code-callout
#: marker, which the spec puts INSIDE a fence on purpose (`callout marker in
#: fence` in the shared construct inventory); everything else is verbatim text.
VERBATIM = (String.Backtick, Name.Constant)

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'
DOCUMENTS = sorted(CORPUS.glob('*.crv')) if CORPUS.is_dir() else []

LEXER = CarveLexer()
SOURCE = lexer_source()

corpus = pytest.mark.skipif(
    not DOCUMENTS,
    reason='spec corpus not present; run: git submodule update --init',
)


def test_the_indices_still_name_the_fence_rules():
    """A rule inserted above them would silently move the mutations elsewhere."""
    rules = state_rules(SOURCE, BLOCK)
    assert '---' in rules[FRONTMATTER_RULE][2]
    for index in (RAW_PAIR_RULE, CODE_PAIR_RULE):
        assert r'(\2)(\3\4*)' in rules[index][2], 'block rule %d is no longer a fence pair' % index
    assert '=[a-zA-Z]' in rules[RAW_PAIR_RULE][2], 'block rule %d is not the RAW pair' % RAW_PAIR_RULE
    for index in (LONE_RAW_RULE, LONE_CODE_RULE):
        text = rules[index][2]
        assert '`{3,}|~{3,}' in text and r'(\2)' not in text, (
            'block rule %d is no longer a lone fence line' % index)


# ----------------------------------------------------------------------------
# Pins
# ----------------------------------------------------------------------------

PINS = [
    ('a fence body is not Carve',
     '```python\n# not a heading\nx = "a *b* c"\n```\n',
     ((Punctuation, '```'), (Name.Builtin, 'python'), (Text, '\n'),
      (String.Backtick, '# not a heading\nx = "a *b* c"\n'),
      (Punctuation, '```'), (Text, '\n')),
     CODE_PAIR_RULE),
    ('a callout marker is the one thing a body still scopes',
     '``` js\nconst a = 1 <1>\n```\n',
     ((Punctuation, '```'), (Text, ' '), (Name.Builtin, 'js'), (Text, '\n'),
      (String.Backtick, 'const a = 1 '), (Name.Constant, '<1>'),
      (String.Backtick, '\n'), (Punctuation, '```'), (Text, '\n')),
     CODE_PAIR_RULE),
    ('a wider fence holds a shorter run as sample text',
     '````\n```js\nx\n```\n````\n',
     ((Punctuation, '````'), (Text, '\n'), (String.Backtick, '```js\nx\n```\n'),
      (Punctuation, '````'), (Text, '\n')),
     CODE_PAIR_RULE),
    ('a run indented past the opener is body, not a closer',
     '```\n  ```\n*still code*\n```\n',
     ((Punctuation, '```'), (Text, '\n'), (String.Backtick, '  ```\n*still code*\n'),
      (Punctuation, '```'), (Text, '\n')),
     CODE_PAIR_RULE),
    ('a tilde fence is not closed by backticks',
     '~~~\nx\n```\n~~~\n',
     ((Punctuation, '~~~'), (Text, '\n'), (String.Backtick, 'x\n```\n'),
      (Punctuation, '~~~'), (Text, '\n')),
     CODE_PAIR_RULE),
    ('a raw block routes its payload verbatim',
     '```=html\n<b>*x*</b>\n```\n',
     ((Punctuation, '```'), (Keyword.Type, '=html'), (Text, '\n'),
      (String.Backtick, '<b>*x*</b>\n'), (Punctuation, '```'), (Text, '\n')),
     RAW_PAIR_RULE),
    ('a fence at an item content column pairs at that column',
     '- x\n\n  ```js\n  y\n  ```\n',
     ((Punctuation, '-'), (Text, ' x\n\n  '), (Punctuation, '```'),
      (Name.Builtin, 'js'), (Text, '\n'), (String.Backtick, '  y\n'),
      (Text, '  '), (Punctuation, '```'), (Text, '\n')),
     CODE_PAIR_RULE),
    ('an opener that never pairs claims nothing under it',
     '```js\nx = *b*\n',
     ((Punctuation, '```'), (Name.Builtin, 'js'), (Text, '\nx = '),
      (Punctuation, '*'), (Generic.Strong, 'b'), (Punctuation, '*'), (Text, '\n')),
     LONE_CODE_RULE),
    ('front matter survives a blank line',
     '---yaml\ntitle: x\n\nother: y\n---\n',
     ((Punctuation, '---'), (Keyword.Type, 'yaml'), (Text, '\n'),
      (Comment.Special, 'title: x\n\nother: y\n'), (Punctuation, '---'), (Text, '\n')),
     FRONTMATTER_RULE),
    ('front matter with no closer is a thematic break',
     '---\ntitle: x\n',
     ((Punctuation, '---'), (Text, '\ntitle: x\n')),
     FRONTMATTER_RULE),
]


def _named(pin):
    return pin[0]


@pytest.mark.parametrize('pin', PINS, ids=_named)
def test_pin_holds(pin):
    name, source, tokens, _ = pin
    got = commentlines.collapsed(LEXER, source)
    assert got == tokens, 'pin %r: got %r' % (name, got)


@pytest.mark.parametrize('index', sorted({p[3] for p in PINS}))
def test_deleting_a_rule_removes_exactly_that_compiled_rule(index):
    """What earns the right to say "delete rule N" below."""
    base = rule_patterns(LEXER, BLOCK)
    mutant = build_lexer(without_rule(SOURCE, index, BLOCK))
    assert rule_patterns(mutant, BLOCK) == base[:index] + base[index + 1:]


#: The rule shape that shipped markup-carve/pygments-carve#32: an opener that
#: pushes a state, and a state none of whose rules match a newline. Building it
#: back is what proves the pins and the corpus gate can say NO - and it is the
#: only mutation that can, because four of the pins say a fence must REFUSE to
#: pair and deleting a rule only ever tests what a rule does.
_REGRESSION_STATES = """        'frontmatter': [
            (r'^(---)([ \\t]*)$', bygroups(Punctuation, Text), '#pop'),
            (r'[^\\n]+\\n?', Comment.Special),
        ],

        'codeblock': [
            (r'^[ \\t]*(?:`{3,}|~{3,})[ \\t]*$', Punctuation, '#pop'),
            (r'<\\d+>', Name.Constant),
            (r'[^\\n<]+|<', String.Backtick),
        ],

"""

_REGRESSION_OPENERS = """            (r'\\A(\\ufeff?)(---)([a-zA-Z][\\w-]*)?([ \\t]*\\n)',
             bygroups(Text, Punctuation, Keyword.Type, Text), 'frontmatter'),
            (r'^(' + _MARGIN + r')(`{3,}|~{3,})([ \\t]*)(=[a-zA-Z][\\w+.-]*)',
             bygroups(Text, Punctuation, Text, Keyword.Type), 'codeblock'),
            (r'^(' + _MARGIN + r')(`{3,}|~{3,})([ \\t]*)([a-zA-Z][\\w+#.-]*)?([^\\n]*)',
             bygroups(Text, Punctuation, Text, Name.Builtin,
                      using(this, state='infostring')), 'codeblock'),
"""


def _regression_source():
    """``SOURCE`` with the pre-#32 openers ahead of the whole-fence rules."""
    rules = state_rules(SOURCE, BLOCK)
    first = rules[FRONTMATTER_RULE][0]
    lines = SOURCE.split('\n')
    out = '\n'.join(lines[:first]) + '\n' + _REGRESSION_OPENERS + '\n'.join(lines[first:])
    anchor = "        'fencebody': ["
    assert anchor in out, 'no anchor to re-insert the pre-#32 states before'
    return out.replace(anchor, _REGRESSION_STATES + anchor, 1)


REGRESSION = build_lexer(_regression_source())


@pytest.mark.parametrize('pin', PINS, ids=_named)
def test_pin_is_sharp(pin):
    """Some mutation must break every pin, or the pin is inert."""
    name, source, tokens, index = pin
    deleted = commentlines.collapsed(build_lexer(without_rule(SOURCE, index, BLOCK)), source)
    regressed = commentlines.collapsed(REGRESSION, source)
    assert deleted != tokens or regressed != tokens, (
        'pin %r survives both mutations - block rule %d deleted, and the #32 rule '
        'shape restored - so nothing anywhere would notice it going wrong.'
        % (name, index))


def test_the_regression_shape_scopes_a_fence_body_as_carve():
    """The shape the ticket was filed on, reproduced exactly."""
    run = [(str(t), v) for t, v in REGRESSION.get_tokens(
        '```python\n# not a heading\nx = "a *b* c"\n```\n')]
    assert ('Token.Generic.Heading', 'not a heading') in run, run
    assert ('Token.Generic.Strong', 'b') in run, run
    # ... and the state it pushed produced nothing at all.
    assert not [v for t, v in REGRESSION.get_tokens('```python\nx\n```\n')
                if t is String.Backtick]


# ----------------------------------------------------------------------------
# The corpus gate
# ----------------------------------------------------------------------------

def _non_verbatim(lexer, source):
    """``[(body, {token type: text})]`` for every body scoped as something else."""
    out = []
    for body in fencebodies.bodies(source):
        wrong = {t: v for t, v in fencebodies.scopes_in(lexer, source, body).items()
                 if t not in VERBATIM}
        if wrong:
            out.append((body, {str(t): v for t, v in wrong.items()}))
    return out


@corpus
@pytest.mark.parametrize('path', DOCUMENTS, ids=lambda p: p.name)
def test_no_fenced_body_is_scoped_as_carve(path):
    source = path.read_text(encoding='utf-8')
    live = _non_verbatim(LEXER, source)
    assert not live, (
        '%s: a fenced body is verbatim - nothing inside one is Carve - and the '
        'lexer scopes these characters inside one as markup: %r' % (path.name, live))


@corpus
def test_the_corpus_has_fenced_bodies_to_measure():
    """Guard the guard: a reader that pairs no fence asserts nothing."""
    total = sum(len(fencebodies.bodies(p.read_text(encoding='utf-8'))) for p in DOCUMENTS)
    assert total > 50, 'only %d fenced bodies paired across the corpus' % total


@corpus
def test_the_corpus_gate_reports_the_documents_the_ticket_was_filed_on():
    """The zero above is only meaningful if this gate can reach fifty-eight.

    Run over the same 1564 documents, the pre-#32 rule shape leaves live Carve
    markup inside a fenced body in all but one document that holds one - the
    exception being a body whose only content is whitespace, which carries no
    scope either way.
    """
    hits = [p.name for p in DOCUMENTS
            if _non_verbatim(REGRESSION, p.read_text(encoding='utf-8'))]
    assert len(hits) == 58, len(hits)


def test_the_reader_reports_live_markup_when_there_is_some():
    """The gate must be able to say YES on a document it is handed."""
    assert _non_verbatim(REGRESSION, '```py\n# x\n```\n')
    assert not _non_verbatim(LEXER, '```py\n# x\n```\n')


# ----------------------------------------------------------------------------
# The cost of requiring a closer
# ----------------------------------------------------------------------------

def test_a_body_longer_than_the_bound_does_not_pair():
    """The bound is a real ceiling, and this is where it is stated."""
    def paired(n):
        doc = '```\n' + 'x\n' * n + '```\n'
        return any(t is String.Backtick and '\n' in v for t, v in LEXER.get_tokens(doc))
    assert paired(_FENCE_BODY_LINES)
    assert not paired(_FENCE_BODY_LINES + 1)


def test_the_closer_search_is_linear():
    """A file of openers that can never pair must not be quadratic.

    Every ```` ```x ```` line is an opener and none of them is a closer, so each
    one scans ahead for a closer it will not find. Unbounded that is one scan of
    the document per line: measured, doubling the input from 12000 to 96000
    characters multiplied the time by 3.05, 2.89 and 4.46 - and 96000 characters
    took 35.9 seconds. The bound is what makes the same doubling 2.15.

    The assertion is the RATIO, not a stopwatch reading: absolute times on a
    machine carrying other load measure the load. That is the same measure
    carve-grammars' `scan-superlinear.mjs` reports, and its threshold - a ratio
    over 3 is a finding - is the one used here.
    """
    def cost(chars):
        source = '```x\n' * (chars // 5)
        best = min(_elapsed(source) for _ in range(3))
        return best

    small, large = cost(12000), cost(24000)
    assert large / max(small, 1e-6) < 3, (
        'doubling the input multiplied the time by %.2f, which is the quadratic '
        'the closer search is bounded to avoid (%.3fs then %.3fs)'
        % (large / max(small, 1e-6), small, large))


def _elapsed(source):
    start = time.perf_counter()
    list(LEXER.get_tokens(source))
    return time.perf_counter() - start


# ----------------------------------------------------------------------------
# An info string outside the grammar's three shapes opens no block
# ----------------------------------------------------------------------------

#: A sample, the body text an opener must NOT claim, and the corpus case that
#: says so. Each of these renders as a PARAGRAPH - the fence does not open - so
#: a rule that paired on it would bury the paragraph, which is the direction
#: that loses a reader's text. The last has no corpus case and came out of
#: review of this change.
INVALID_INFO = [
    ('```js title="x"\ncode\n```\n', 'code', '11-fenced-code-11'),
    ('```php [Composer] "x"\ncode\n```\n', 'code', '11-fenced-code-12'),
    ('```js\t"T"\nx\n```\n', 'x', '258-code-fence-metadata-slots-must-be-a-space-too-4'),
    ('```\tphp\nx\n```\n', 'x', '330-a-tab-after-a-fence-or-a-frontmatter-opener-depends-on-where-it-sits'),
    ('```  php\nx = 1\n```\n', 'x = 1', '263-a-code-fence-opener-takes-exactly-one-space'),
    ('```js bad\n# heading\n```\n', '# heading', None),
    # A raw block takes no title and no label, so its guard is the format word
    # alone - a separate line, and separately proved.
    ('```=html "T"\npayload\n```\n', 'payload', None),
]


def _buries(lexer, source, body):
    return any(t is String.Backtick and body in v for t, v in lexer.get_tokens(source))


def _without_guard(marker):
    """``SOURCE`` with the one opener guard whose line holds ``marker`` removed.

    This is the mutation that proves the pins below say something. Deleting the
    pairing rule cannot: a rule that is gone also fails to pair, so every "must
    NOT claim a body" pin would pass against it for the wrong reason.
    """
    lines = [l for l in SOURCE.split('\n') if marker in l]
    assert len(lines) == 1, 'expected one guard line holding %r, found %d' % (marker, len(lines))
    return build_lexer(SOURCE.replace(lines[0] + '\n', '', 1))


UNGUARDED = _without_guard('+ _FENCE_INFO +')
UNGUARDED_RAW = _without_guard('(?= ?=[a-zA-Z]')


@pytest.mark.parametrize('sample,body,case', INVALID_INFO, ids=lambda v: None)
def test_an_invalid_info_string_claims_no_body(sample, body, case):
    assert not _buries(LEXER, sample, body), (
        '%r is not one of the three shapes `code_fence_info` admits, so it opens '
        'no block - and this pairs on it and buries %r.' % (sample, body))


@pytest.mark.parametrize('sample,body,case', INVALID_INFO, ids=lambda v: None)
def test_the_guard_is_what_refuses_an_invalid_info_string(sample, body, case):
    """Remove the guard and every one of them buries its body."""
    mutant = UNGUARDED_RAW if sample.startswith('```=') else UNGUARDED
    assert _buries(mutant, sample, body), (
        'without the info-string guard %r is expected to bury %r; if it no '
        'longer does, this pin is measuring something else.' % (sample, body))


@corpus
@pytest.mark.parametrize('sample,body,case',
                         [c for c in INVALID_INFO if c[2]], ids=lambda v: None)
def test_the_corpus_says_those_openers_render_a_paragraph(sample, body, case):
    """The pins above are the corpus's reading, not this suite's invention."""
    html = (CORPUS / (case + '.html')).read_text(encoding='utf-8')
    assert '<pre>' not in html, html
    assert '<p><code>' in html, html
