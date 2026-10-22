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

from pygments.token import Comment, Generic, Keyword, Name, Number, Operator, Punctuation, String, Text

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

#: Fence bodies are read verbatim here, so what these pins hold is how a fence
#: PAIRS, not which languages Pygments happens to know. Handing a body to its
#: language's lexer is pinned in test_fence_body.py.
LEXER = CarveLexer(handlecodeblocks=False)


def build_verbatim(source):
    return build_lexer(source, handlecodeblocks=False)
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
    mutant = build_verbatim(without_rule(SOURCE, index, BLOCK))
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


REGRESSION = build_verbatim(_regression_source())


@pytest.mark.parametrize('pin', PINS, ids=_named)
def test_pin_is_sharp(pin):
    """Some mutation must break every pin, or the pin is inert."""
    name, source, tokens, index = pin
    deleted = commentlines.collapsed(build_verbatim(without_rule(SOURCE, index, BLOCK)), source)
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
    """The zero above is only meaningful if this gate can reach a hundred and seventy-five.

    Run over the same 2223 documents, the pre-#32 rule shape leaves live Carve
    markup inside a fenced body in all but one document that holds one - the
    exception being a body whose only content is whitespace, which carries no
    scope either way. The count moves with the corpus, not with the rules: it
    was fifty-eight over 1564 documents, sixty-three over 1748, and sixty-nine
    over 1869. The thirty-six added by the bump to carve 9d6d06c are all new
    documents; no document already in the corpus changed its verdict.

    The bump to carve bb09baea adds one, and it was measured the same way: the
    hit list was taken at the pin this repository shipped (8b68a460, 2220
    documents, 105 hits) and again at bb09baea (2223 documents, 106 hits), each
    in its own process. The two lists differ by a single membership change,
    547-an-info-string-does-not-change-how-a-flush-left-fence-folds-into-a-description-body-3.crv
    joining. No document already in the corpus changed its verdict, and the two
    sibling documents the same category adds hold no live markup to find.

    The bump to carve 2d473af7 adds two, measured the same way: 106 hits over
    the 2225 documents at bae59dad, 108 over the 2322 at 2d473af7. Both are new
    documents from markup-carve/carve#2890, the `-4` and `-13` cases of
    553-a-below-column-line-continues-a-paragraph-only-where-one-is-open, and
    no document already in the corpus changed its verdict.

    The bump to carve 21879d7 adds twenty-five, measured the same way: 108 hits
    over the 2322 documents at 2d473af7, 133 over the 2508 at 21879d7. All
    twenty-five are new documents from the fence-in-a-container sections 556
    to 592, and no document already in the corpus changed its verdict.

    The bump to carve 99906e2 adds forty-two, measured the same way: 133 hits
    over the 2508 documents at 1a75124, 175 over the 2974 at 99906e2. All
    forty-two are new documents, carve-js main renders each as its corpus
    HTML, and no document already in the corpus changed its verdict.
    """
    hits = [p.name for p in DOCUMENTS
            if _non_verbatim(REGRESSION, p.read_text(encoding='utf-8'))]
    assert len(hits) == 175, len(hits)


# ----------------------------------------------------------------------------
# Fences inside a container, and the engine's reading of every pairing
# ----------------------------------------------------------------------------

ITEM_FENCE_RULE = 7
QUOTED_FENCE_RULE = 8


def _documents_with_html():
    for path in DOCUMENTS:
        html = path.with_suffix('.html')
        if html.is_file():
            yield path, path.read_text(encoding='utf-8'), html.read_text(encoding='utf-8')


def _live_in_containers(lexer):
    """``[(document, body, wrong scopes)]`` for every container fence body the
    engine renders as code and the lexer scopes as something else."""
    out = []
    for path, source, html in _documents_with_html():
        for body in fencebodies.container_bodies(source):
            if not fencebodies.confirmed(source, html, body):
                continue
            wrong = {t: v for t, v in fencebodies.scopes_in(lexer, source, body).items()
                     if t not in VERBATIM}
            if wrong:
                out.append((path.stem, body, wrong))
    return out


def test_the_container_rules_are_where_the_index_says():
    rules = state_rules(SOURCE, BLOCK)
    assert '_ITEM_FENCE' in rules[ITEM_FENCE_RULE][2]
    assert '_QUOTED_FENCE' in rules[QUOTED_FENCE_RULE][2]


@corpus
def test_no_container_fence_body_is_scoped_as_carve():
    """The top-level reader steps past a fence behind `>` or on a marker line,
    because the fence is not at the start of its line, so the gate above never
    saw one. This reads them, and asks only about the bodies the engine's HTML
    renders as code."""
    assert _live_in_containers(LEXER) == []


@corpus
def test_the_corpus_has_container_fences_to_measure():
    confirmed = sum(1 for _, source, html in _documents_with_html()
                    for body in fencebodies.container_bodies(source)
                    if fencebodies.confirmed(source, html, body))
    assert confirmed >= 15, confirmed


@corpus
def test_the_container_gate_reports_a_body_without_the_container_rules():
    mutant = build_verbatim(without_rule(without_rule(SOURCE, QUOTED_FENCE_RULE, BLOCK),
                                         ITEM_FENCE_RULE, BLOCK))
    assert len(_live_in_containers(mutant)) >= 10


@corpus
def test_a_paired_body_is_one_the_engine_renders():
    """Every body the reader pairs is checked against the engine's HTML.

    These thirty-one are not: the reader and the lexer pair a fence where the
    engine reads a container the lexer does not model. Each is an opener
    indented off column 0 at document level (`11-fenced-code-16` renders an
    inline code span), or a fence under a list item, a description or a quote
    in a nested host whose content column decides where the fence belongs.
    That is the documented limit of block openers not anchored at column 0,
    recorded so a change in either direction shows up here.

    The bump to carve 99906e2 adds eleven new documents. Three `633-*` hold a
    fence one column in below a nested item, which carve-js main renders as an
    inline code span, like `11-fenced-code-16`. Eight `617-*` hold a `csv` or
    `tsv` fence under `{table}`, which the engine renders as a table, not as
    code. carve-js main renders all eleven as their corpus HTML.
    """
    unconfirmed = sorted({path.stem for path, source, html in _documents_with_html()
                          for body in fencebodies.bodies(source)
                          if fencebodies.confirmed(source, html, body) is False})
    assert unconfirmed == [
        '11-fenced-code-16',
        '276-a-fence-opened-on-a-list-marker-line-body-below-the-content-column-7',
        '476-an-item-s-fence-is-read-once-whatever-block-it-follows',
        '476-an-item-s-fence-is-read-once-whatever-block-it-follows-2',
        '478-a-definition-body-s-open-code-fence-ends-at-a-line-below-its-column-3',
        '478-a-definition-body-s-open-code-fence-ends-at-a-line-below-its-column-5',
        '480-a-bare-colon-opener-in-a-description-body-is-an-opener-7',
        '509-a-fence-closer-below-a-nested-item-s-column-ends-containers-down-to-its-owner-10',
        '509-a-fence-closer-below-a-nested-item-s-column-ends-containers-down-to-its-owner-11',
        '509-a-fence-closer-below-a-nested-item-s-column-ends-containers-down-to-its-owner-12',
        '531-an-opener-under-a-quote-in-a-nested-host-opens-at-one-column-only-10',
        '531-an-opener-under-a-quote-in-a-nested-host-opens-at-one-column-only-11',
        '531-an-opener-under-a-quote-in-a-nested-host-opens-at-one-column-only-13',
        '531-an-opener-under-a-quote-in-a-nested-host-opens-at-one-column-only-2',
        '531-an-opener-under-a-quote-in-a-nested-host-opens-at-one-column-only-3',
        '531-an-opener-under-a-quote-in-a-nested-host-opens-at-one-column-only-4',
        '531-an-opener-under-a-quote-in-a-nested-host-opens-at-one-column-only-5',
        '558-a-container-boundary-is-read-at-the-container-s-own-column-4',
        '558-a-container-boundary-is-read-at-the-container-s-own-column-5',
        '561-a-line-block-payload-span-pairs-past-the-content-column-2',
        '617-csv-and-tsv-table-bodies',
        '617-csv-and-tsv-table-bodies-10',
        '617-csv-and-tsv-table-bodies-2',
        '617-csv-and-tsv-table-bodies-4',
        '617-csv-and-tsv-table-bodies-5',
        '617-csv-and-tsv-table-bodies-6',
        '617-csv-and-tsv-table-bodies-8',
        '617-csv-and-tsv-table-bodies-9',
        '633-a-first-block-marker-on-an-indented-opener-reads-two-columns-20',
        '633-a-first-block-marker-on-an-indented-opener-reads-two-columns-24',
        '633-a-first-block-marker-on-an-indented-opener-reads-two-columns-28',
    ], unconfirmed


def test_the_html_check_can_say_no():
    body = fencebodies.bodies('```\nx\n```\n')[0]
    assert fencebodies.confirmed('```\nx\n```\n', '<pre><code>x\n</code></pre>', body)
    assert fencebodies.confirmed('```\nx\n```\n', '<p><code>x</code></p>', body) is False


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
    return build_verbatim(SOURCE.replace(lines[0] + '\n', '', 1))


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


# ----------------------------------------------------------------------------
# A body in a language Pygments knows is read in that language
# ----------------------------------------------------------------------------

DELEGATING = CarveLexer()


def _body_run(lexer, source):
    """The tokens between the opener's newline and the closer, joined by type."""
    tokens = list(lexer.get_tokens(source))
    assert ''.join(v for _, v in tokens) == source, 'the delegated body lost text'
    return tokens


def test_a_body_is_read_by_its_language():
    """As Pygments' Markdown lexer does, behind the same `handlecodeblocks`."""
    run = _body_run(DELEGATING, '```python\n# not a heading\nx = "a *b* c"\n```\n')
    assert (Comment.Single, '# not a heading') in run
    assert (String.Double, 'a *b* c') in run
    assert not [v for t, v in run if t in (Generic.Heading, Generic.Strong)]


@pytest.mark.parametrize('language,body,expected', [
    ('csv', 'Plan,Seats,Price per month\nStarter,1,"$0"\nTeam,10,"$49, billed yearly"\n',
     [(Operator.Word, ','), (String, '"$0"'), (String, '"$49, billed yearly"')]),
    ('csv', 'a,"two\nlines",b\n',
     [(String, '"two\nlines"'), (Operator.Word, ',')]),
    ('csv', 'a,"say ""hi""",b\n',
     [(String.Escape, '""'), (String, 'hi')]),
    ('tsv', 'a,b\t"two\tparts"\tc\n',
     [(Generic.Strong, 'a,b'), (String, '"two\tparts"'), (Operator.Word, '\t')]),
    ('csv', 'a,b"c,d\n',
     [(Generic.Strong, 'b"c'), (Operator.Word, ',')]),
    ('csv', 'a,"quoted"tail,b\n',
     [(String, '"quoted"'), (Generic.Strong, 'tail')]),
    ('csv', 'a,"unfinished\nmore',
     [(String, '"unfinished\nmore\n')]),
])
def test_delimited_fence_body(language, body, expected):
    run = _body_run(DELEGATING, '```' + language + '\n' + body + '\n```\n')
    joined = []
    for ttype, value in run:
        if joined and joined[-1][0] is ttype:
            joined[-1] = (ttype, joined[-1][1] + value)
        else:
            joined.append((ttype, value))
    for token in expected:
        assert token in joined
    assert not any(t is String.Backtick for t, _ in run)


@pytest.mark.parametrize('language,body', [
    ('csv', 'Plan,Seats\nStarter,1,"$0"\nTeam,"a""b",x"y\nz,"q"t\n'),
    ('tsv', 'Plan\tSeats\nStarter\t1\t"$0"\n'),
])
def test_every_delimited_field_is_typed(language, body):
    run = _body_run(DELEGATING, '```' + language + '\n' + body + '```\n')
    assert (Generic.Strong, 'Plan') in run
    assert (String.Other, 'Starter') in run and (String.Other, '1') in run
    assert not [v for t, v in run if t is Text and v.strip()]


def test_a_callout_stays_a_callout_in_any_language():
    run = _body_run(DELEGATING, '``` js\nconst a = 1 <1>\n```\n')
    assert (Name.Constant, '<1>') in run
    assert (Keyword.Declaration, 'const') in run


def test_a_raw_block_is_read_by_its_format():
    run = _body_run(DELEGATING, '```=html\n<b>x</b>\n```\n')
    assert (Name.Tag, 'b') in run


def test_a_quoted_body_keeps_the_quote_markers():
    run = _body_run(DELEGATING, '> ```py\n> x = 1 <2>\n> ```\n')
    assert (Punctuation, '> ') in run and (Name.Constant, '<2>') in run
    assert (Number.Integer, '1') in run


def test_a_body_in_an_item_is_read_by_its_language():
    run = _body_run(DELEGATING, '- ```py\n  # c\n  ```\n')
    assert (Comment.Single, '# c') in run


@pytest.mark.parametrize('source', [
    '```nosuchlanguage\nx *y*\n```\n',
    '```\nx *y*\n```\n',
])
def test_an_unknown_or_missing_language_is_read_verbatim(source):
    assert (String.Backtick, 'x *y*\n') in _body_run(DELEGATING, source)


def test_the_option_turns_it_off():
    run = _body_run(LEXER, '```python\n# c\n```\n')
    assert (String.Backtick, '# c\n') in run
