"""Marker-line comment fences, attached fences and fallback lines, against the
spec model at carve main (markup-carve/pygments-carve#134, #135, #136)."""

import time

import pytest

from pygments.token import Comment, Generic, String

from pygments_carve import CarveLexer

LEXER = CarveLexer(handlecodeblocks=False)


def tokens(source):
    return list(LEXER.get_tokens(source))


def text_of(source, ttype):
    return ''.join(v for t, v in tokens(source) if t in ttype)


def strong(source):
    return [v for t, v in tokens(source) if t is Generic.Strong]


# pygments-carve#134: a footnote's content column is two past its `[^`; a
# description's is where its `%%%` starts.
@pytest.mark.parametrize('source, hidden, shown', [
    ('[^n]: %%%\n  *hidden*\n  %%%\n\nx[^n]\n', '  *hidden*\n', []),
    ('[^n]:    %%%\n  *a*\n\n*b*[^n]\n', '  *a*\n\n', ['b']),
    ('[^n]: %%%\n *a*\n\n*b*[^n]\n', '', ['a', 'b']),
    ('[^n]: %%%%\n  %%%\n  *a*\n  %%%%\n  *b*\n\nx[^n]\n', '  %%%\n  *a*\n', ['b']),
    ('- [^n]: %%%\n  *a*\n    *b*\n\nx[^n]\n', '', ['a', 'b']),
    ('- [^n]: %%%\n    *a*\n  *b*\n\nx[^n]\n', '    *a*\n', ['b']),
    (':: t\n: %%%\n  *a*\n  %%%\n*b*\n', '  *a*\n', ['b']),
    (':: t\n: %%%\n  *a*\n\n*b*\n', '  *a*\n\n', ['b']),
    (':: t\n:    %%%\n    *a*\n', '', ['a']),
    (':: t\n:    %%%\n     *a*\n', '     *a*\n', []),
])
def test_a_footnote_or_description_marker_line_comment_fence(source, hidden, shown):
    assert text_of(source, (Comment,)) == hidden
    assert strong(source) == shown


@pytest.mark.parametrize('source, shown', [
    ('> - %%%\n      *a*\n*b*\n', ['a', 'b']),
    ('> [^n]: %%%\n      *a*\n*b*\n\nx[^n]\n', ['a', 'b']),
    ('> - %%%\n>   *a*\n\n>   *b*\n', ['b']),
    ('> - %%%\n>   *a*\n>\n>   *b*\n', []),
])
def test_a_quoted_marker_line_comment_fence_ends_where_the_quote_does(source, shown):
    assert strong(source) == shown


# pygments-carve#135, carve#5304: one-line attribute lines between the `+`
# and its fence, flush left or at the host's content column.
@pytest.mark.parametrize('source, body, shown', [
    ('[^a]: +\n{.x}\n```\nx\n\nsee *b*[^a]\n', 'x\n', ['b']),
    ('[^a]: +\n  {.x}\n```\nx\n\nsee *b*[^a]\n', 'x\n', ['b']),
    ('[^a]: +\n{.x}\n{#y}\n```\nx\n\nsee *b*[^a]\n', 'x\n', ['b']),
    ('- +\n{.x}\n~~~\nx\n\n*b*\n', 'x\n', ['b']),
    (':: t\n: +\n{.x}\n```\nx\n\n*b*\n', 'x\n', ['b']),
    ('1. +\n   {.x}\n```\nx\n\n*b*\n', 'x\n', ['b']),
    ('1. +\n  {.x}\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    ('> +\n  {.x}\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    ('para +\n{.x}\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    ('- +\n\n{.x}\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    # Only one marker at column 0 hosts the fence; prose ending in `: +`,
    # a nested or an indented marker does not.
    ('hello: +\n{.x}\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    ('hello: +\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    ('- - +\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    ('  - +\n```\nx\n\n*b*\n', 'x\n\n*b*\n', []),
    ('-   +\n```\nx\n\n*b*\n', 'x\n', ['b']),
    ('1) +\n```\nx\n\n*b*\n', 'x\n', ['b']),
])
def test_an_attribute_line_between_the_plus_and_its_fence(source, body, shown):
    assert text_of(source, (String.Backtick,)) == body
    assert strong(source) == shown


# pygments-carve#136, CARVE-P2-005: the closed run of a fallback line is a
# code span, and the rest of the paragraph pairs as usual.
@pytest.mark.parametrize('source, code, shown', [
    ('```js foo``` z\n*code*\n', 'js foo', ['code']),
    ('```js foo``` z *a*\n', 'js foo', ['a']),
    ('p\n\n````a b```` *a*\n*b*\n', 'a b', ['a', 'b']),
    ('```js, x``` *a*\n', 'js, x', ['a']),
    ('``` "x\n*a*\n', ' "x\n*a*', []),
])
def test_a_fallback_line_that_closes_its_own_code_span(source, code, shown):
    assert text_of(source, (String.Backtick,)) == code
    assert strong(source) == shown


def test_attribute_lines_under_a_plus_stay_linear():
    """Each fence walks back over the attribute lines above it once."""
    def elapsed(n):
        source = '- +\n' + '{.x}\n' * n + '```\nx\n\n' + '```\n' * n
        start = time.perf_counter()
        tokens(source)
        return time.perf_counter() - start
    small, large = elapsed(500), elapsed(4000)
    assert large < max(small, 0.01) * 24, (small, large)
