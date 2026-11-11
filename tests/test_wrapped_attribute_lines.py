"""Wrapped attribute lines and the `+` hosts they sit under (pygments-carve#139).

Each sample's reading is the spec model's at carve main: a continuation line of
a block attribute is indented past its block's opening `{` (PART 9 attributes,
`continuation`), or the opener is paragraph text.
"""

import time

import pytest

from pygments.token import Generic, Name, String

from pygments_carve import CarveLexer

LEXER = CarveLexer(handlecodeblocks=False)


def tokens(source):
    return list(LEXER.get_tokens(source))


def attributes(source):
    return [v for t, v in tokens(source) if t is Name.Attribute]


def body(source):
    return ''.join(v for t, v in tokens(source) if t is String.Backtick)


def strong(source):
    return [v for t, v in tokens(source) if t is Generic.Strong]


# Corpus 253-...-does-2 and 1057-a-refused-root-run-releases-a-heading.
@pytest.mark.parametrize('source', [
    '{.a\n.b}\n\nparagraph\n',
    '{.x\n.y}\n# H\n',
    '{.x\n}\npara\n',
    '{\n.x}\npara\n',
    '  {.x\n  .y}\npara\n',
    '- +\n  {.x\n  .y}\n  para\n',
    '[^a]: +\n{.x\n.y}\npara\n\nx[^a]\n',
])
def test_a_continuation_short_of_its_brace_is_paragraph_text(source):
    assert attributes(source) == []


def test_a_glued_block_measures_its_own_brace():
    assert not [v for v in attributes('{.x}{.y\n    .z}\npara\n') if '\n' in v]


@pytest.mark.parametrize('source, attrs', [
    ('{.x\n .y}\npara\n', ['{.x\n .y}']),
    ('{.x\n\t.y}\npara\n', ['{.x\n\t.y}']),
    ('{.x\n }\npara\n', ['{.x\n }']),
    ('  {.x\n   .y}\npara\n', ['{.x\n   .y}']),
    ('{.x}{.y\n     .z}\npara\n', ['{.x}{.y\n     .z}']),
    ('{k="a b"\n .y}\npara\n', ['{k="a b"\n .y}']),
    ('- +\n  {.x\n   .y}\n  para\n', ['{.x\n   .y}']),
])
def test_a_continuation_past_its_brace_wraps_the_attribute_line(source, attrs):
    assert attributes(source) == attrs


def test_the_reproduction():
    """Under the #5830 ruling the fence is a column-0 opener outside the item,
    and its unclosed body runs to the end of the document."""
    source = '- +\n{.x\n.y}\n```\nx\n\n*b*\n'
    assert attributes(source) == []
    assert body(source) == 'x\n\n*b*\n'


@pytest.mark.parametrize('host', ['- +', '1. +', '[^a]: +', ':: t\n: +'])
def test_a_wrapped_attribute_line_keeps_a_fence_attached(host):
    """The fence under it ends at its first blank (carve#5304)."""
    source = host + '\n{.x\n .y}\n```\nx\n\n*b*\n'
    assert body(source) == 'x\n'
    assert strong(source) == ['b']


@pytest.mark.parametrize('source', [
    ': +\n{.x}\n```\nx\n\n*b*\n',
    't\n: +\n{.x\n .y}\n```\nx\n\n*b*\n',
    ':: t\nmore\n: +\n{.x}\n```\nx\n\n*b*\n',
])
def test_a_colon_line_outside_a_description_list_hosts_nothing(source):
    assert body(source) == 'x\n\n*b*\n'


@pytest.mark.parametrize('source', [
    ':: t\n\n: +\n{.x}\n```\nx\n\n*b*\n',
    ':: t\n: a\n\n: +\n{.x}\n```\nx\n\n*b*\n',
    ':: t\n  \n: +\n{.x}\n```\nx\n\n*b*\n',
    ':: t\n\t\n: +\n{.x}\n```\nx\n\n*b*\n',
])
def test_a_description_hosts_a_fence(source):
    assert body(source) == 'x\n'


def _elapsed(source):
    start = time.perf_counter()
    list(LEXER.get_tokens(source))
    return time.perf_counter() - start


@pytest.mark.parametrize('unit', [
    ': a\n: +\n{.x\n .y}\n```\nx\n```\n',
    ' z\n' * 3 + '```\nx\n```\n',
])
def test_the_host_walk_is_linear(unit):
    """Ratio, not a stopwatch: doubling the input stays under x3."""
    def cost(chars):
        source = ':: t\n' + unit * (chars // len(unit))
        return min(_elapsed(source) for _ in range(3))

    small, large = cost(12000), cost(24000)
    assert large / max(small, 1e-6) < 3, (small, large)


@pytest.mark.parametrize('source, attrs', [
    ('{\n .x}\npara\n', ['{\n .x}']),
    ('p\n{\n .x}\npara\n', ['{\n .x}']),
    # A `{` line short of the item's content column closes the list; the
    # model and the engines measure its brace as if flush left.
    ('- +\n {.x\n .y}\npara\n', ['{.x\n .y}']),
    ('1. +\n  {.x\n .y}\npara\n', ['{.x\n .y}']),
    ('- a\n\n {.x\n .y}\npara\n', ['{.x\n .y}']),
    ('- a\n  \n {.x\n .y}\npara\n', ['{.x\n .y}']),
    ('- +\n \n {.x\n .y}\npara\n', ['{.x\n .y}']),
    # Directly under item text it is a lazy line; at the marker's own column
    # under a nested `+` it is the `+`'s block.
    ('- a\n {.x\n .y}\npara\n', []),
    ('  - +\n  {.x\n  .y}\npara\n', []),
    ('- a\n\n  {.x\n .y}\npara\n', []),
])
def test_where_a_wrapped_block_is_measured(source, attrs):
    assert attributes(source) == attrs
