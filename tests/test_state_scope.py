"""Readings the 0.1.0 audit found wrong, each pinned against the engine.

Every sample here was run through carveToHtml (carve 0.1.11), and the expected
run is what that HTML says the lexer should colour. Each group also rebuilds
the lexer without the mechanism that fixed it and requires the pins to stop
holding, so none of them passes for a reason other than the one stated.
"""

import pytest

from pygments.token import (
    Comment,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
)

from pygments_carve import CarveLexer

from coverage import UNSCOPED, merged
from lexerrules import build_lexer, lexer_source

LEXER = CarveLexer()
SOURCE = lexer_source()


def scoped_run(lexer, sample):
    return tuple((ttype, value) for ttype, value in merged(lexer, sample)
                 if ttype not in UNSCOPED)


def _mutant(*replacements):
    source = SOURCE
    for old, new in replacements:
        assert old in source, 'the mutation target has moved: %r' % old
        source = source.replace(old, new)
    return build_lexer(source)


def _sharp(mutant, pins):
    held = [sample for sample, expect in pins if scoped_run(mutant, sample) == expect]
    assert not held, 'these pins still hold without the mechanism: %r' % held


# ----------------------------------------------------------------------------
# A closer inside an escape, a code span or a link does not close a span
# ----------------------------------------------------------------------------

#: `a *b\* c` renders `<p>a *b* c</p>`: the escaped `*` is literal, so no span
#: opens. `{=a \=} b=}` renders one mark holding `a =} b`, and so on for every
#: braced family. `*a [b*](u)` renders a literal `*a` and a link; `*a `b*` c*`
#: one strong holding a code span.
MASKED = [
    ('a *b\\* c', ((String.Escape, '\\*'),)),
    ('a _b\\_ c', ((String.Escape, '\\_'),)),
    ('a *x*b, \\*x\\*', ((String.Escape, '\\*'), (String.Escape, '\\*'))),
    ('*a [b*](u)', ((Name.Entity, '[b*]'), (Punctuation, '('), (Name.Tag, 'u'),
                    (Punctuation, ')'))),
    ('/a [b/ c](u)', ((Name.Entity, '[b/ c]'), (Punctuation, '('), (Name.Tag, 'u'),
                      (Punctuation, ')'))),
    ('*a `b*` c*', ((Punctuation, '*'), (Generic.Strong, 'a '), (Punctuation, '`'),
                    (String.Backtick, 'b*'), (Punctuation, '`'), (Generic.Strong, ' c'),
                    (Punctuation, '*'))),
    ('/see <http://a.b/c> now/', ((Punctuation, '/'), (Generic.Emph, 'see '),
                                  (Punctuation, '<'), (Name.Tag, 'http://a.b/c'),
                                  (Punctuation, '>'), (Generic.Emph, ' now'),
                                  (Punctuation, '/'))),
] + [
    ('{%sa \\%s} b%s}' % (d, d, d),
     ((Punctuation, '{' + d), (kind, 'a '), (String.Escape, '\\' + d), (kind, '} b'),
      (Punctuation, d + '}')))
    for d, kind in [('*', Generic.Strong), ('/', Generic.Emph), ('_', Generic.Underline),
                    ('~', Generic.Deleted), ('^', Generic.Emph), (',', Generic.Emph),
                    ('=', Generic.Inserted), ('+', Generic.Inserted), ('-', Generic.Deleted)]
]


@pytest.mark.parametrize('sample,expect', MASKED, ids=[m[0] for m in MASKED])
def test_a_closer_inside_a_tighter_construct_does_not_close(sample, expect):
    assert scoped_run(LEXER, sample) == expect


def test_the_masks_are_what_refuse_those_closers():
    _sharp(_mutant(('span = _tight(text, m.start(), unclosed)', 'span = None')), MASKED)


def test_an_unclosed_code_run_masks_a_bare_closer_but_not_a_braced_one():
    """Corpus 12: `*a ` b*` is a literal `*a` and a code span to the end of the
    paragraph, while `{*`a*}` is a strong holding an unclosed code span."""
    assert scoped_run(LEXER, '*a ` b*') == (
        (Punctuation, '`'), (String.Backtick, ' b*'))
    assert scoped_run(LEXER, 'x{*`a*} here') == (
        (Punctuation, '{*'), (Punctuation, '`'), (String.Backtick, 'a'), (Punctuation, '*}'))


# ----------------------------------------------------------------------------
# Code spans
# ----------------------------------------------------------------------------

#: `x `a` `b c` renders two spans, the second running to the paragraph's end,
#: and a span may cross a line of its paragraph but not a blank line.
CODE = [
    ('x `a` `b c', ((Punctuation, '`'), (String.Backtick, 'a'), (Punctuation, '`'),
                    (Punctuation, '`'), (String.Backtick, 'b c'))),
    ('x `a\nb` y', ((Punctuation, '`'), (String.Backtick, 'a\nb'), (Punctuation, '`'))),
    ('x ``a` y', ((Punctuation, '``'), (String.Backtick, 'a` y'))),
    ('x !`a\nb', ((Operator, '!'), (Punctuation, '`'), (Literal, 'a\nb'))),
    ('x `a\n\nb` y', ((Punctuation, '`'), (String.Backtick, 'a'),
                      (Punctuation, '`'), (String.Backtick, ' y'))),
    ('x `a\n# H', ((Punctuation, '`'), (String.Backtick, 'a'),
                   (Punctuation, '#'), (Generic.Heading, 'H'))),
    ('| a `b | c |', ((Punctuation.Table, '|'), (Punctuation, '`'), (String.Backtick, 'b | c '),
                      (Punctuation.Table, '|'))),
    ('| a `b |{.c}', ((Punctuation.Table, '|'), (Punctuation, '`'), (String.Backtick, 'b '),
                      (Punctuation.Table, '|'), (Name.Attribute, '{.c}'))),
]


@pytest.mark.parametrize('sample,expect', CODE, ids=[c[0] for c in CODE])
def test_a_code_span_reads_to_its_partner_or_its_paragraph_end(sample, expect):
    assert scoped_run(LEXER, sample) == expect


def test_the_paragraph_reach_is_what_reads_them():
    _sharp(_mutant(("reach='paragraph', unclosed=True)", "unclosed=False)")), CODE[:5])


# ----------------------------------------------------------------------------
# An unclosed inline note or role is text
# ----------------------------------------------------------------------------

#: `x ^[a` then a blank line and `# H` renders the bracket literally and a
#: heading; as a pushed state the note used to run to the end of the document.
NOTES = [
    ('x ^[a\n\n# H', ((Punctuation, '#'), (Generic.Heading, 'H'))),
    ('x :r[a b\n\n# H', ((Punctuation, '#'), (Generic.Heading, 'H'))),
    ('x ^[a\nb] c', ((Punctuation, '^['), (Generic.Emph, 'a'), (Generic.Emph, 'b'),
                     (Punctuation, ']'))),
]


@pytest.mark.parametrize('sample,expect', NOTES, ids=[n[0] for n in NOTES])
def test_an_inline_note_opens_only_on_a_closer_in_its_paragraph(sample, expect):
    assert scoped_run(LEXER, sample) == expect


def test_the_guard_is_what_keeps_them_text():
    _sharp(_mutant(
        ("(_Scan(r'\\^\\[', '', r'\\]', reach='paragraph', whole=False),", "(r'\\^\\[',"),
        ("(_Scan(r'(:)([a-zA-Z][\\w-]*)(\\[)', '', r'\\]', reach='paragraph', whole=False),",
         "(r'(:)([a-zA-Z][\\w-]*)(\\[)',"),
        ("            (r'\\n' + _PARAGRAPH_BREAK, Text, '#pop'),\n", '')),
        NOTES[:2])


# ----------------------------------------------------------------------------
# A paragraph line, and blocks nested in a container
# ----------------------------------------------------------------------------

#: `para` then `- x`, `1. y` and `^ z` is one paragraph; a blank line ends it.
#: `> - item`, `> # H`, `- > q`, `- # H` and `: - item` under a term each nest a
#: block in their container.
BLOCKS = [
    ('para\n- not a list\n1. not a list\n^ not a caption\n\n- list',
     ((Punctuation, '-'),)),
    ('> - item', ((Punctuation, '>'), (Punctuation, '-'))),
    ('> # H', ((Punctuation, '>'), (Punctuation, '#'), (Generic.Heading, 'H'))),
    ('- > q', ((Punctuation, '-'), (Punctuation, '>'), (Generic.Emph, ' q'))),
    ('- # H', ((Punctuation, '-'), (Punctuation, '#'), (Generic.Heading, 'H'))),
    ('1. # H', ((Number.Integer, '1.'), (Punctuation, '#'), (Generic.Heading, 'H'))),
    (':: T\n: - item', ((Punctuation, '::'), (Generic.Heading, 'T'),
                        (Punctuation, ':'), (Punctuation, '-'))),
]


@pytest.mark.parametrize('sample,expect', BLOCKS, ids=[b[0] for b in BLOCKS])
def test_a_block_reads_where_its_container_holds_it(sample, expect):
    assert scoped_run(LEXER, sample) == expect


def test_the_nested_tail_is_what_reads_them():
    _sharp(_mutant(("_NESTED_TAIL = r'(?:([ \\t]+)(?='", "_NESTED_TAIL = r'(?:([ \\t]+)(?!)(?='")),
           BLOCKS[1:])


def test_a_caption_under_an_image_line_is_still_a_caption():
    """The image line is the caption's host, so it opens no paragraph."""
    assert scoped_run(LEXER, '![a](u)\n^ cap') == (
        (String.Other, '![a]'), (Punctuation, '('), (Name.Tag, 'u'), (Punctuation, ')'),
        (Punctuation.Caption, '^'), (Generic.Subheading.Caption, 'cap'))
    assert scoped_run(LEXER, 'text ![a](u)\n^ cap') == (
        (String.Other, '![a]'), (Punctuation, '('), (Name.Tag, 'u'), (Punctuation, ')'))


#: A fence in a container pairs only where the engine closes it.
FENCES = [
    ('- ```py\n  x\n```\n', ((Punctuation, '-'), (Punctuation, '```'), (Name.Builtin, 'py'),
                             (Punctuation, '```'))),
    ('- ```py\n  x\n   ```\n', ((Punctuation, '-'), (Punctuation, '```'), (Name.Builtin, 'py'),
                                (Punctuation, '```'))),
    ('> ```py\n# x\n> ```\n', ((Punctuation, '>'), (Punctuation, '```'), (Name.Builtin, 'py'),
                               (Punctuation, '#'), (Generic.Heading, 'x'),
                               (Punctuation, '>'), (Punctuation, '```'))),
]


@pytest.mark.parametrize('sample,expect', FENCES, ids=[f[0] for f in FENCES])
def test_a_container_fence_needs_its_closer_inside_the_container(sample, expect):
    """A closer left of the item's content column, past it, or a body line that
    leaves the quote: no pair, so the opener stays a lone fence line."""
    assert scoped_run(LEXER, sample) == expect


def test_a_quoted_fence_body_keeps_its_markers():
    """Each body line's `>` is the quote's, and the rest is the payload; a raw
    format is scoped as at document level."""
    run = scoped_run(CarveLexer(handlecodeblocks=False), '> ```=html\n> <b>x</b>\n>\n> ```\n')
    assert run[:4] == ((Punctuation, '>'), (Punctuation, '```'), (Keyword.Type, '=html'),
                       (Punctuation, '> '))
    assert ''.join(v for t, v in run if t is String.Backtick) == '<b>x</b>\n\n'
    assert run[-2:] == ((Punctuation, '>'), (Punctuation, '```'))
    assert [v for t, v in run if t is Punctuation] == ['>', '```', '> ', '>', '>', '```']


# ----------------------------------------------------------------------------
# A table row needs its closing pipe
# ----------------------------------------------------------------------------

def test_a_row_attribute_block_may_follow_the_closing_pipe():
    assert scoped_run(LEXER, '| a |{.c}\n') == (
        (Punctuation.Table, '|'), (Punctuation.Table, '|'), (Name.Attribute, '{.c}'))
    assert scoped_run(LEXER, '| a | b\n') == ()


# ----------------------------------------------------------------------------
# Braced spans nest, and a bare closer inside one closes nothing
# ----------------------------------------------------------------------------

#: Engine readings (carve 0.1.11): a braced span nests its own kind, an
#: unpaired outer opener stays literal, a closer inside a later span is that
#: span's, and a bare closer inside a braced span does not close a bare span.
NESTED = [
    ('{*a {*b*} c*}', ((Punctuation, '{*'), (Generic.Strong, 'a '), (Punctuation, '{*'),
                       (Generic.Strong, 'b'), (Punctuation, '*}'), (Generic.Strong, ' c'),
                       (Punctuation, '*}'))),
    ('{=a {=b=} c=}', ((Punctuation, '{='), (Generic.Inserted, 'a '), (Punctuation, '{='),
                       (Generic.Inserted, 'b'), (Punctuation, '=}'), (Generic.Inserted, ' c'),
                       (Punctuation, '=}'))),
    ('{*a {*b*}', ((Punctuation, '{*'), (Generic.Strong, 'b'), (Punctuation, '*}'))),
    ('{*a {*b c*}', ((Punctuation, '{*'), (Generic.Strong, 'b c'), (Punctuation, '*}'))),
    ('{*a {/b*} c/}', ((Punctuation, '{/'), (Generic.Emph, 'b*} c'), (Punctuation, '/}'))),
    ('{*a {/b c*}', ((Punctuation, '{*'), (Generic.Strong, 'a {/b c'), (Punctuation, '*}'))),
    ('{*a {# {* x #} b*}', ((Punctuation, '{*'), (Generic.Strong, 'a '), (Punctuation, '{#'),
                            (Comment, ' {* x '), (Punctuation, '#}'), (Generic.Strong, ' b'),
                            (Punctuation, '*}'))),
]

BARE_IN_BRACED = [
    ('*a {=b*=} c*', ((Punctuation, '*'), (Generic.Strong, 'a '), (Punctuation, '{='),
                      (Generic.Inserted, 'b*'), (Punctuation, '=}'), (Generic.Strong, ' c'),
                      (Punctuation, '*'))),
    ('*a {=b*=}', ((Punctuation, '{='), (Generic.Inserted, 'b*'), (Punctuation, '=}'))),
]


@pytest.mark.parametrize('sample,expect', NESTED + BARE_IN_BRACED,
                         ids=[n[0] for n in NESTED + BARE_IN_BRACED])
def test_a_braced_span_nests_and_holds_its_closers(sample, expect):
    assert scoped_run(LEXER, sample) == expect


def test_an_escaped_comment_opener_hides_no_braced_span():
    assert (Punctuation, '{*') in scoped_run(LEXER, '\\{# {*x*} #}')


def test_a_braced_en_dash_opens_no_span():
    """`{--}` is one token: a later `-}` does not pair with it, so it hides no
    bare closer (the engine closes the strong at `b*`)."""
    sample = '*a {--} b* c-} d*'
    expect = ((Punctuation, '*'), (Generic.Strong, 'a '), (Punctuation, '{--}'),
              (Generic.Strong, ' b'), (Punctuation, '*'))
    assert scoped_run(LEXER, sample) == expect
    _sharp(_mutant(("r'\\{--\\}|\\{[#%]'", "r'\\{[#%]'")), [(sample, expect)])


def test_pairing_from_the_last_opener_is_what_nests_them():
    _sharp(_mutant(('    for m in reversed(openers):', '    for m in openers:')), NESTED[:3])


def test_the_braced_masks_are_what_hold_a_bare_closer():
    _sharp(_mutant(('        spans += _braced_pairs(text).items()\n', '')), BARE_IN_BRACED)
