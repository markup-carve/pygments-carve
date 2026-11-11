"""An inline attribute block attaches to the element right before it (pygments-carve#142).

Each reading is carveToHtml's at carve-js main: with no element right before
it, `{...}` is paragraph text (`08-attributes.ebnf`, inline `attributes`).
"""

import pytest

from pygments.token import Name

from pygments_carve import CarveLexer

LEXER = CarveLexer(handlecodeblocks=False)


def attributes(source):
    return [v for t, v in LEXER.get_tokens(source) if t is Name.Attribute]


@pytest.mark.parametrize('source', [
    '{.x} a\n',
    '{.x}a\n',
    '{.x}{.y} a\n',
    '{k=v} a\n',
    'p\n{.x} a\n',
    'a {.x} b\n',
    'a{.x}\n',
    'a  {.x}\n',
    '*b* {.x}\n',
    '`c` {.x}\n',
    '[a] {.x}\n',
    '*a{.x}*\n',
    '# a {#id}\n',
    '# a*{.x}\n',
    '| a {.x} |\n',
    '- {.x} a\n',
    '> {.x} a\n',
    '"q"{.x}\n',
    'a\\\\{.x}\n',
    '@cite{.x}\n',
    '- 1.{k=v}a\n',
])
def test_an_attribute_block_with_no_element_before_it_is_text(source):
    assert attributes(source) == []


@pytest.mark.parametrize('source,expect', [
    ('[a]{.x} b\n', ['{.x}']),
    ('*b*{.x}\n', ['{.x}']),
    ('_u_{.x}\n', ['{.x}']),
    ('`c`{.x}\n', ['{.x}']),
    ('[a](u){.x}\n', ['{.x}']),
    ('<http://x.y>{.x}\n', ['{.x}']),
    (':+1:{.x}\n', ['{.x}']),
    ('{=a=}{.x}\n', ['{.x}']),
    ('![i](u){.x}\n', ['{.x}']),
    (':r[a]{.x}\n', ['{.x}']),
    ('[a]{.x}{.y}\n', ['{.x}', '{.y}']),
    ('[a]{.x} {.y}\n', ['{.x}']),
    ('# a [b]{.x}\n', ['{.x}']),
])
def test_an_attribute_block_after_an_element_is_an_attribute(source, expect):
    assert attributes(source) == expect


@pytest.mark.parametrize('source,expect', [
    ('{.x}\npara\n', ['{.x}']),
    ('p\n{.x}\nnext\n', ['{.x}']),
    ('> {.x .y}\nnext\n', ['{.x .y}']),
    ('1. {.p}{.q}\nnext\n', ['{.p}', '{.q}']),
    ('- [ ] {.x}\nnext\n', ['{.x}']),
    ('- [ ] 1.{.x} a\n', ['{.x}']),
])
def test_an_attribute_line_still_attaches_to_its_block(source, expect):
    assert attributes(source) == expect


# `attr_pad = {space}`: the block may be padded inside its braces.
@pytest.mark.parametrize('source,expect', [
    ('[a]{ .x}\n', ['{ .x}']),
    ('[a]{ .x }\n', ['{ .x }']),
    ('*b*{ #i}\n', ['{ #i}']),
    ('[a]{ }\n', ['{ }']),
    ('{ .x}\nnext\n', ['{ .x}']),
    ('p\n{ .x}\nnext\n', ['{ .x}']),
])
def test_a_padded_attribute_block_is_an_attribute(source, expect):
    assert attributes(source) == expect
