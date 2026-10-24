"""A bare emphasis delimiter does not emphasize intraword.

WHY THIS FILE EXISTS. "No bare delimiter emphasizes intraword; the forced
`{X ... X}` family is the deliberate-intraword escape hatch" is normative, and
the grammar states it as two guards instantiated for each of `/ * _ ~ =`:

    bare_opener(d) = <!(alnum | '_' | d | slash_if(d)), d, !(ws | d)
    bare_closer(d) = <&(non_ws), d, !(alnum)

The lexer's five bare rules carried neither, so any non-space run between two
delimiters was emphasis wherever it sat. Across the 1564-document spec corpus,
**16 documents** held a run the lexer scoped whose delimiters SURVIVE into the
expected HTML - which is the corpus saying no span was opened there. The
clearest is a document whose own sentence is the assertion:

    (c) 2024, (r), (tm). Dates like 1/2/2024 stay literal.

renders `<p>(c) 2024, ... Dates like 1/2/2024 stay literal.</p>` and the lexer
scoped `/2/` as `Generic.Emph` (markup-carve/pygments-carve#36).

WHY NOTHING OBJECTED. `test_inline_rules.py` pins one sample per rule and every
bare-emphasis sample is a valid span, so a rule that is too permissive passes.
The construct sweep asks that a payload carries a scope, which an over-colour
also satisfies. `test_corpus.py` reads definitions. All three are one-sided in
the direction this defect sat.

WHAT IS MEASURED HERE is the other direction, and it comes out of the
source/HTML pair rather than a list: a bare delimiter that opens a span is
CONSUMED, so a run whose delimiters are still in the HTML is a span the corpus
did not open.
"""

import pathlib

import pytest

from pygments.token import Generic, Punctuation, Text

from pygments_carve import CarveLexer

import emphasisruns
from coverage import merged
from lexerrules import INLINE, build_lexer, lexer_source, state_rules

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'
DOCUMENTS = sorted(CORPUS.glob('*.crv')) if CORPUS.is_dir() else []

LEXER = CarveLexer()
SOURCE = lexer_source()

corpus = pytest.mark.skipif(
    not DOCUMENTS,
    reason='spec corpus not present; run: git submodule update --init',
)


#: The seven rules as they stood before markup-carve/pygments-carve#36 - the
#: five bare delimiters and the two combined `/*` spellings - with no guard on
#: either end. Rebuilding them is the only mutation that reaches this defect:
#: deleting a rule REMOVES an over-colour, it does not produce one, so every
#: "must NOT be emphasis" pin below would pass against a deletion for the wrong
#: reason.
_UNGUARDED_RULES = """            (r'(/\\*)([^\\n]+?)(\\*/)', bygroups(Punctuation, Generic.Strong, Punctuation)),
            (r'(\\*/)([^\\n]+?)(/\\*)', bygroups(Punctuation, Generic.Strong, Punctuation)),
            (r'(\\*)(\\S(?:[^\\n]*?\\S)?)(\\*)', bygroups(Punctuation, Generic.Strong, Punctuation)),
            (r'(/)(\\S(?:[^\\n]*?\\S)?)(/)', bygroups(Punctuation, Generic.Emph, Punctuation)),
            (r'(_)(\\S(?:[^\\n]*?\\S)?)(_)', bygroups(Punctuation, Generic.Underline, Punctuation)),
            (r'(~)(\\S(?:[^\\n]*?\\S)?)(~)', bygroups(Punctuation, Generic.Deleted, Punctuation)),
            (r'(?<![<>!])(=)(\\S(?:[^\\n]*?\\S)?)(?<![<>!])(=)',
             bygroups(Punctuation, Generic.Inserted, Punctuation)),
"""


def _unguarded_source():
    """``SOURCE`` with the seven guarded rules replaced by the unguarded ones."""
    rules = state_rules(SOURCE, INLINE)
    guarded = [r for r in rules if "(?![^\\W_])" in r[2]]
    assert len(guarded) == 7, 'expected seven guarded rules, found %d' % len(guarded)
    first, past = guarded[0][0], guarded[-1][1]
    lines = SOURCE.split('\n')
    return '\n'.join(lines[:first]) + '\n' + _UNGUARDED_RULES + '\n'.join(lines[past:])


UNGUARDED = build_lexer(_unguarded_source())


def _emphasized(lexer, source, text):
    """Whether ``text`` lands whole in one emphasis token."""
    marks = (Generic.Strong, Generic.Emph, Generic.Underline,
             Generic.Deleted, Generic.Inserted)
    return any(ttype in marks and value == text for ttype, value in merged(lexer, source))


# ----------------------------------------------------------------------------
# One pin per guard clause
# ----------------------------------------------------------------------------

#: ``(name, source, the run the unguarded rules marked)``. Every one of these is
#: refused by the guards and taken by the rules without them, which is what
#: makes each pin a statement about a guard rather than about a rule.
REFUSED = [
    ('an alnum before the opener - the ticket sentence', 'Dates like 1/2/2024 stay literal.', '2'),
    ('an underscore before the opener', 'a_*b* c', 'b'),
    ('a slash before an underline opener - path protection', 'a/_b_ c', 'b'),
    ('a slash before an italic opener', 'a//b/ c', '/b'),
    # For a SINGLE-character delimiter the opener's two same-delimiter clauses -
    # not preceded by `d`, not followed by `d` - are one adjacency seen from
    # either side, so one doubled sample exercises both.
    ('a doubled delimiter never opens', '**a* y', '*a'),
    ('a doubled highlight run', '==doubled= y', '=doubled'),
    ('the same delimiter after an underline opener', '__a_ y', '_a'),
    ('an alnum after the closer', 'a ~b~c d', 'b'),
    ('a doubled strike run', 'a ~~b~ c', '~b'),
]

#: The valid shape of each delimiter, which the guards must still take. A guard
#: that refused everything would pass every pin above.
ACCEPTED = [
    ('a *b* c', 'b'),
    ('a /b/ c', 'b'),
    ('a _b_ c', 'b'),
    ('a ~b~ c', 'b'),
    ('a =b= c', 'b'),
    ('a /*b*/ c', 'b'),
    ('("*b*") c', 'b'),
    ('a *b*, c', 'b'),
    ('a /b/_c_ d', 'b'),
]


@pytest.mark.parametrize('name,source,run', REFUSED, ids=lambda v: None)
def test_a_guard_refuses_the_run(name, source, run):
    assert not _emphasized(LEXER, source, run), name


@pytest.mark.parametrize('name,source,run', REFUSED, ids=lambda v: None)
def test_the_guard_is_what_refuses_it(name, source, run):
    """Without the guards every one of them is emphasis, which is the defect."""
    assert _emphasized(UNGUARDED, source, run), (
        '%s: the unguarded rules are expected to mark %r in %r; if they no longer '
        'do, this pin is measuring something else.' % (name, run, source))


@pytest.mark.parametrize('source,run', ACCEPTED, ids=lambda v: None)
def test_the_valid_shape_is_still_emphasis(source, run):
    assert _emphasized(LEXER, source, run), source


def test_the_combined_opener_is_guarded_on_its_outer_slash():
    """`a/*b*/` is not bold-italic, and the token run is where that shows.

    The grammar puts the guards on the OUTER `/` of the two-character opener, so
    a `/` behind an alnum does not open one. What follows is not an
    under-colour: `*` is deliberately NOT guarded against a preceding slash, so
    the plain strong rule takes `*b*` and the slashes stay text. The two
    readings give `b` the same TYPE and differ only in their delimiters, which
    is why this reads the run rather than asking whether `b` is emphasized.
    """
    delimiters = ('/*', '*/', '*', '/')
    assert [(t, v) for t, v in LEXER.get_tokens('a/*b*/ c') if v in delimiters] == [
        (Text, '/'), (Punctuation, '*'), (Punctuation, '*'), (Text, '/')]
    assert [(t, v) for t, v in UNGUARDED.get_tokens('a/*b*/ c') if v in delimiters] == [
        (Punctuation, '/*'), (Punctuation, '*/')]
    # The unguarded form of the same opener is still taken where it is valid.
    assert [(t, v) for t, v in LEXER.get_tokens('a /*b*/ c') if v in ('/*', '*/')] == [
        (Punctuation, '/*'), (Punctuation, '*/')]


def test_a_forced_span_bypasses_both_guards():
    """The escape hatch the rule points at: `{X ... X}` emphasizes intraword."""
    assert _emphasized(LEXER, 'my{_path_}name', 'path')
    assert _emphasized(LEXER, 'a1{*b*}2c', 'b')


def test_a_run_closes_at_its_first_guarded_closer():
    """A run is closed by the first delimiter that satisfies the closer guards.

    `a =f=>g= b` used to mark `f=>g` and was recorded as a divergence from the
    engine, put down to the lexer having no delimiter stack. It was a quantifier:
    the content was `\\S(?:[^\\n]*?\\S)?`, and that optional group is greedy, so a
    one-character content was tried only after every longer one had failed.
    Five corpus documents carried the same misreading, `01-emphasis-8` among
    them: `(/x/) and a./b/` renders two spans, and the lexer read one.
    """
    assert _emphasized(LEXER, 'a =f=>g= b', 'f')
    assert _emphasized(LEXER, '(/x/) and a./b/', 'x')
    assert _emphasized(LEXER, '(/x/) and a./b/', 'b')
    # `=>` is not an arrow any more, so `a =>foo= b` marks `>foo`.
    assert _emphasized(LEXER, 'a =>foo= b', '>foo')


# ----------------------------------------------------------------------------
# The corpus gate
# ----------------------------------------------------------------------------

def _case(path):
    html = path.with_suffix('.html')
    return (path.read_text(encoding='utf-8'),
            html.read_text(encoding='utf-8') if html.is_file() else None)


@corpus
@pytest.mark.parametrize('path', DOCUMENTS, ids=lambda p: p.name)
def test_no_document_scopes_a_span_the_corpus_did_not_open(path):
    source, html = _case(path)
    if html is None:
        pytest.skip('no rendered HTML beside %s' % path.name)
    unopened = emphasisruns.unopened(LEXER, source, html)
    assert not unopened, (
        '%s: the lexer scopes %s as emphasis, and the corpus renders the '
        'delimiters, so no span was opened there.'
        % (path.name, ', '.join(map(repr, unopened))))


@corpus
def test_the_corpus_has_emphasis_runs_to_measure():
    """Guard the guard: a reader that finds no run asserts nothing."""
    total = sum(len(emphasisruns.runs(LEXER, p.read_text(encoding='utf-8')))
                for p in DOCUMENTS)
    assert total > 40, 'only %d bare emphasis runs across the corpus' % total


def test_an_escaped_copy_of_a_run_is_not_the_run_surviving():
    """The HTML is read per document, and an escaped copy is in it too.

    Corpus `471-braced-emphasis-can-nest-its-own-kind-11` writes one span and,
    in the next paragraph, the same text with every delimiter escaped. The
    second paragraph is what puts `*x*` in the HTML; the span was opened.
    """
    source = '\\{*x*}\n\n\\{\\*x\\*\\}\n'
    html = '<p>{<strong>x</strong>}</p>\n<p>{*x*}</p>\n'
    assert emphasisruns.runs(LEXER, source) == [(2, '*x*')]
    assert emphasisruns.unopened(LEXER, source, html) == []
    # One escaped copy accounts for one occurrence and no more.
    assert emphasisruns.unopened(
        UNGUARDED, '\\*x\\* and a*x*\n', '<p>*x* and a*x*</p>\n') == ['*x*']


@corpus
def test_the_gate_reports_the_documents_the_ticket_was_filed_on():
    """The zero above is only meaningful if this gate can reach seventeen.

    Run over the same 2200 documents, the unguarded rules scope a run whose
    delimiters survive into the expected HTML in exactly these. The ticket
    measured SEVENTEEN; the extra one is `11-fenced-code-15`, where the run sat
    in a fenced body and markup-carve/pygments-carve#38 stopped lexing those as
    Carve before this change was written.

    The `455-*-2` entry arrived with a corpus bump rather than with a rule
    change: its tilde fence opens on a nested item lead, so the unguarded rules
    read the `~~~` as a bare-emphasis run while the corpus renders the
    delimiters. The guarded lexer still reports zero on it, like every other
    document here. The `465-*` and two `467-*` entries arrived the same way,
    with markup-carve/carve#2043 and markup-carve/carve#2046, and the three
    `484-*` entries with markup-carve/carve#2160, whose subject is a delimiter
    sitting immediately after `_` or `/`. The `519-*` entry and the two
    `535-*` entries arrived with the bump to carve 9d6d06c, on the same
    shape: a fence or an overindented marker inside a quoted item, which the
    unguarded rules read as a bare run.

    Five of those left when blocks nested in a container started being read
    as blocks: `276-*-5`, `455-*-2`, `519-*-2` and the two `535-*` entries
    hold a fence or a marker behind `>`, `-` or `:`, which the container
    rules now take before the inline state sees the delimiters.

    The `595-*-2` entry and the four `600-*` entries arrived with the bump to
    carve 99906e2, all new documents. carve-js main renders each one as its
    corpus HTML, and the guarded lexer reports zero on them; the `600-*` ones
    hold a delimiter followed by a combining mark or a keycap.
    The spec 0.1.12 corpus adds `19-*-35`, which the unguarded rules also
    misread while the guarded lexer keeps its delimiters as text.
    """
    hits = sorted(p.stem for p in DOCUMENTS
                  if _case(p)[1] is not None
                  and emphasisruns.unopened(UNGUARDED, *_case(p)))
    assert hits == [
        '01-emphasis-10',
        '01-emphasis-11',
        '01-emphasis-14',
        '01-emphasis-2',
        '01-emphasis-9',
        '129-emphasis-opener-slash-adjacency',
        '129-emphasis-opener-slash-adjacency-2',
        '129-emphasis-opener-slash-adjacency-3',
        '131-emphasis-span-closes-before-a-following-delimiter',
        '19-smart-typography-dashes-and-quotes-35',
        '20-smart-typography-arrows-and-symbols',
        '272-an-autolink-body-admits-non-ascii-and-excludes-format-characters'
        '-10',
        '272-an-autolink-body-admits-non-ascii-and-excludes-format-characters'
        '-5',
        '272-an-autolink-body-admits-non-ascii-and-excludes-format-characters'
        '-7',
        '465-an-underscore-pair-in-text-is-escaped-where-the-line-would-pair-'
        'it',
        '467-a-bare-closer-does-not-reach-inside-a-link-destination',
        '467-a-bare-closer-does-not-reach-inside-a-link-destination-2',
        '484-a-delimiter-after-an-underscore-or-slash-opens-only-when-that-on'
        'e-pairs',
        '484-a-delimiter-after-an-underscore-or-slash-opens-only-when-that-on'
        'e-pairs-2',
        '484-a-delimiter-after-an-underscore-or-slash-opens-only-when-that-on'
        'e-pairs-6',
        '595-a-bare-closer-does-not-reach-inside-a-cross-reference-2',
        '600-a-delimiter-that-is-part-of-a-larger-character-is-text',
        '600-a-delimiter-that-is-part-of-a-larger-character-is-text-14',
        '600-a-delimiter-that-is-part-of-a-larger-character-is-text-2',
        '600-a-delimiter-that-is-part-of-a-larger-character-is-text-7',
        '76-doubled-emphasis-delimiters',
        '79-two-char-delimiter-runs',
    ], hits


def test_the_reader_reports_an_unopened_run_when_there_is_one():
    """The gate must be able to say YES on a document it is handed."""
    source = 'Dates like 1/2/2024 stay literal.\n'
    html = '<p>Dates like 1/2/2024 stay literal.</p>'
    assert emphasisruns.unopened(UNGUARDED, source, html) == ['/2/']
    assert emphasisruns.unopened(LEXER, source, html) == []


def test_the_reader_says_nothing_about_a_span_the_corpus_opened():
    assert emphasisruns.unopened(LEXER, 'a *b* c\n', '<p>a <strong>b</strong> c</p>') == []
