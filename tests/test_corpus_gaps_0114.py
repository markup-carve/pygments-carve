"""The 0.1.14 corpus rows the lexer follows since markup-carve/pygments-carve#131."""

import pytest

from pygments.token import Comment, Generic, Name, String

from pygments_carve import CarveLexer

LEXER = CarveLexer(handlecodeblocks=False)

MARKS = (Generic.Strong, Generic.Emph, Generic.Underline, Generic.Deleted, Generic.Inserted)


def tokens(source):
    return list(LEXER.get_tokens(source))


def text_of(source, ttype):
    return ''.join(v for t, v in tokens(source) if t is ttype)


def marked(source):
    return [v for t, v in tokens(source) if t in MARKS]


# carve#4018, PART 0 S1: a column-0 fence runs to its closer or the end.
@pytest.mark.parametrize('source, body', [
    ('::: note\npara\n```\ncode\n::::\n:::\nafter *b*\n', 'code\n::::\n:::\nafter *b*\n'),
    ('```\nx\n``` junk\n*b*\n', 'x\n``` junk\n*b*\n'),
    ('~~~\nx\n```\n', 'x\n```\n'),
    ('```=html\n<b>*x*</b>\n', '<b>*x*</b>\n'),
    ('```\nlast', 'last'),
])
def test_an_unclosed_column_0_fence_runs_to_the_end(source, body):
    assert text_of(source, String.Backtick) == body


def test_an_unclosed_fence_stops_at_its_closer():
    assert text_of('```\nx\n````\n*b*\n', String.Backtick) == 'x\n'
    assert marked('```\nx\n````\n*b*\n') == ['b']


@pytest.mark.parametrize('source', [
    '- x\n\n  ```js\n  y = *b*\n',   # indented: the container is not tracked
    '- +\n```\na\n\n*b*\n',           # attached by `+`: ends at its first blank (carve#5304)
])
def test_an_opener_the_lexer_cannot_end_claims_nothing(source):
    assert marked(source) == ['b']


def test_an_attached_fence_with_a_closer_keeps_its_blank_lines():
    assert text_of('- +\n```\na\n\nb\n```\n*after*\n', String.Backtick) == 'a\n\nb\n'
    assert marked('- +\n```\na\n\nb\n```\n*after*\n') == ['after']


def test_a_plus_after_prose_attaches_nothing():
    assert text_of('foo +\n```\ncode\n\n*after*\n', String.Backtick) == 'code\n\n*after*\n'
    assert marked('[^n]: +\n```\ncode\n\n*after*\n') == ['after']


# carve#4807: the language survives invalid metadata.
@pytest.mark.parametrize('source', [
    '```js title="x"\ncode\n```\n', '```js {1,3}\ncode\n```\n',
    '```js\t"T"\ncode\n```\n', '```js bad\ncode\n```\n',
])
def test_invalid_metadata_keeps_the_language(source):
    assert (Name.Builtin, 'js') in tokens(source)
    assert text_of(source, String.Backtick) == 'code\n'


@pytest.mark.parametrize('source', [
    '```js, x\n*code*\n```\n', '``` {.x}\n*code*\n```\n', '```  js\n*code*\n```\n',
])
def test_the_fallback_opens_nothing(source):
    """The line is paragraph text; its run opens an inline code span that ends
    where the paragraph does, at the column-0 fence below it."""
    assert marked(source) == []
    spans = [v for t, v in tokens(source) if t is String.Backtick]
    assert spans and spans[0].endswith('*code*'), spans


def test_a_run_as_long_as_the_opener_refuses_the_recovery():
    # `js foo` is an inline code span; the closing run opens an empty fence.
    assert text_of('```js foo``` z\ncode\n```\n', String.Backtick) == 'js foo'


# carve#4836, PART 9 9 R2: a bare span holding its own delimiter between word
# characters does not form.
@pytest.mark.parametrize('source', [
    '/usr/local/', 'the /api/v1/ route', '_my_var_', '*a*b*', '~a~b~', '=a=b=',
])
def test_a_span_holding_its_own_delimiter_does_not_form(source):
    assert marked(source) == []


@pytest.mark.parametrize('source, run', [
    ('/etc/', 'etc'), ('_a_', 'a'), ('/x `a/b` y/', 'x '), ('{/a/b/}', 'a'),
    ('/*a/b*/', 'a'), ('/a\\/b/', 'a'),
])
def test_the_region_excludes_code_braces_and_escapes(source, run):
    assert run in marked(source)


def test_a_mention_name_is_not_the_region():
    assert (Name.Variable.Magic, '@a_b') in tokens('_@a_b_')
    assert marked('*a#b*c*') == []
    # Only a real name: `@1_2` holds no letter, and a tag name stops at a dot.
    assert marked('_@1_2_') == []
    assert marked('_#a.b_c_') == []


@pytest.mark.parametrize('lang', ['3d', 'c/asm', 'c++'])
def test_a_recovered_fence_keeps_the_whole_language_token(lang):
    assert (Name.Builtin, lang) in tokens('```%s bad\nx\n```\n' % lang)


def test_only_the_closing_span_is_refused():
    assert marked('/a/b *c/ d*') == ['c', '/', ' d']


# CARVE-P3-022
def test_an_equals_before_a_greater_than_never_opens():
    assert marked('=>g=') == []
    assert marked('a =foo=> b') == ['foo']


# CARVE-P3-004
@pytest.mark.parametrize('source', [
    '[*x*\ny][]\n', '[*t*][a\nb]\n', '![*x*][a\nb]\n', '![x\ny][]\n', '[[x]\n*y*][r]\n',
])
def test_a_reference_across_a_line_stays_verbatim(source):
    assert marked(source) == []


def test_a_heading_ends_the_label_line():
    assert marked('[*x*\n# h][]\n') == ['x']


# CARVE-P12-026
@pytest.mark.parametrize('marker', ['- ', '> ', '1. ', '> - '])
def test_an_abbreviation_is_defined_behind_a_marker(marker):
    assert (Name.Entity, 'HTML') in tokens(marker + '*[HTML]: Hyper Text\n')


# corpus 337, 864, carve#4907
@pytest.mark.parametrize('source, hidden, shown', [
    ('. - %%%\n%%%\nx *b*\n%%%\n', '', ['b']),
    ('- %%%\n  [r]: /url\n  %%%\n\n[r][]', '  [r]: /url\n', []),
    ('- %%%\n  h\nx *b*\n', '  h\n', ['b']),
    ('- %%%%\n  %%%\n  %%%%\n*b*', '  %%%\n', ['b']),
])
def test_a_marker_line_comment_fence(source, hidden, shown):
    assert text_of(source, Comment) == hidden
    assert marked(source) == shown


# CARVE-P2-035, carve#5080
@pytest.mark.parametrize('source, comment', [
    ('pre\n{% a\n  b %}\n', True),
    ('pre\n{% a\nb %}\n', False),
    ('- {% c\n  d %}\n', False),
    ('- pre\n{% b\nb %}\n', False),
    ('> pre\n> {% a\n> b %}\n', False),
    ('{% a\n %}\nz\n', True),
    ('x {% a\nb %} y\n', True),   # mid-line: the inline production alone
])
def test_a_braced_comment_in_block_position_continues_past_its_brace(source, comment):
    assert any(t is Comment.Preproc and v == '{%' for t, v in tokens(source)) is comment


# 01-layout S4, carve#5830: a multi-line run on a lazy line takes no lazy continuation.
@pytest.mark.parametrize('source, comment', [
    ('- pre\n{% b\n b %}\n', False),
    ('> pre\n{% b\n b %}\n', False),
    ('[^a]: pre\n{% b\n b %}\n\nref[^a]\n', False),
    ('- a\n  - b\n{% c\n  d %}\n  - c\n', False),
    ('- a\n  - b\n  {% c\n   d %}\n', False),
    ('- a\n  more\n{% b\n b %}\n', False),
    ('::: note\npre\n{% b\n b %}\n:::\n', True),
    ('- pre\n  {% b\n   b %}\n', True),
    ('- a\n  - b\n    {% c\n     d %}\n', True),
    ('- pre\n{% b %}\n', True),
    ('- pre\n\n{% b\n b %}\n', True),
    ('- # H\n{% b\n b %}\n', True),
    ('- ```\n  x\n  ```\n{% b\n b %}\n', True),
])
def test_a_multi_line_braced_comment_on_a_lazy_line_is_text(source, comment):
    assert any(t is Comment.Preproc and v == '{%' for t, v in tokens(source)) is comment
