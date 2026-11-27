"""Snippet definitions and uses (C2-B-236, C2-I-128, C2-B-237)."""

import pytest
from pygments.token import Generic, Name, Punctuation, Text

from pygments_carve import CarveLexer


def lex(source):
    tokens = [(token, value) for _, token, value in CarveLexer().get_tokens_unprocessed(source)]
    assert ''.join(value for _, value in tokens) == source
    return tokens


def variables(source):
    return [value for token, value in lex(source) if token is Name.Variable]


def test_issue_reproduction():
    source = ('{$ver}: 0.2.3\n\nRelease {{ $ver }} of the tool, with *strong* after.\n\n'
              '{{ $ver }}\n\nText after the block use with *strong*.\n')
    tokens = lex(source)
    assert tokens[:4] == [(Punctuation, '{'), (Name.Variable, '$ver'), (Punctuation, '}'),
                          (Punctuation, ':')]
    assert variables(source) == ['$ver', '$ver', '$ver']
    assert tokens.count((Punctuation, '{{')) == 2 and tokens.count((Punctuation, '}}')) == 2
    assert tokens.count((Generic.Strong, 'strong')) == 2
    assert not any(token is Name.Namespace for token, _ in tokens)


@pytest.mark.parametrize('source, name', [
    ('{$ver}: 0.2.3\n', '$ver'),
    ('{$_v}: X\n', '$_v'),
    ('{$9}: X\n', '$9'),
    ('{$a_b-c}: X\n', '$a_b-c'),
    ('{$v .c}: X\n', '$v'),
    ('{$v k="a}b"}: X\n', '$v'),
    ('{$v}{.c}{e=1}: X\n', '$v'),
    ('{$v}:  X\n', '$v'),
    ('﻿{$v}: X\n', '$v'),
    ('{.k}\n{$v .c}: X\n', '$v'),
])
def test_definition(source, name):
    assert variables(source) == [name]


def test_definition_parts():
    tokens = lex('{$brand .badge}{k=v}: *b* `c`\n')
    assert (Name.Attribute, '.badge') in tokens
    assert (Name.Attribute, '{k=v}') in tokens
    assert (Generic.Strong, 'b') in tokens
    assert (Punctuation, ':') in tokens


@pytest.mark.parametrize('source', [
    '{$v}:\n', '{$v}: \n', '{$v}:x\n', '{$v}:\tX\n', '{$v}\n', '\\{$v}: X\n',
    '{$v #x}: a\n', '{$v .c}{#i}: X\n', '{$v}{.c} {.d}: X\n', '{$-v}: X\n',
    '{$v.x}: X\n', '{$vé}: X\n',
    ' {$v}: X\n', 'text\n{$v}: X\n', '> {$v}: X\n', '- {$v}: X\n',
])
def test_no_definition(source):
    assert variables(source) == []


@pytest.mark.parametrize('source', [
    'Version {{ $ver }}.\n',
    '{{ $ver }}\n',
    '{{ $ver }}  \n',
    'a {{  $ver  }} b\n',
    '# H {{ $ver }}\n',
    '| {{ $ver }} |\n',
    '[a {{ $ver }}](u)\n',
    '*a {{ $ver }} b*\n',
    '{*{{ $ver }}*}\n',
    '> {{ $ver }}\n',
    '- {{ $ver }}\n',
    'text\n{{ $ver }}\n',
    '{$w}: a {{ $ver }}\n',
])
def test_use(source):
    tokens = lex(source)
    assert [value for token, value in tokens if token is Name.Variable][-1:] == ['$ver']
    assert (Punctuation, '{{') in tokens and (Punctuation, '}}') in tokens
    assert not any(token is Name.Namespace for token, _ in tokens)


@pytest.mark.parametrize('source', ['{{ $a.crv }}\n', '{{ $v @shift:1 }}\n', '{{ $v#s }}\n', '{{ $-v }}\n'])
def test_include_directive_kept(source):
    assert any(token is Name.Namespace for token, _ in lex(source))
    assert '$v' not in variables(source)


@pytest.mark.parametrize('source', [
    'a {{$v}} b\n', 'a {{\t$v }} b\n', 'a {{ $v\t}} b\n', 'a \\{{ $v }} b\n',
    'a `{{ $v }}` b\n', 'a {{ $vé }} b\n', '{{ "a {{ $v }}.crv" }}\n',
])
def test_no_use(source):
    assert variables(source) == []


def test_text_after_use():
    tokens = lex('a {{ $v }}{.c} *b* [l](u)\n')
    assert (Text, '{.c}') in tokens
    assert not any(token in Name.Attribute for token, _ in tokens)
    assert (Generic.Strong, 'b') in tokens
    assert (Text, '{#i .c k="}"}') in lex('a {{ $v }}{#i .c k="}"} b\n')


def test_block_use_is_one_line():
    tokens = lex('{{ $v }}\n# Next\n')
    assert (Generic.Heading, 'Next') in tokens


@pytest.mark.parametrize('source', ['{.x}\n{{ $name }}\n', '{.k :en}\n{{ $name }}  \n'])
def test_attribute_line_above_block_use_is_text(source):
    # carve#6896: a block snippet use takes no attribute line.
    tokens = lex(source)
    assert not any(token in Name.Attribute for token, _ in tokens)
    assert tokens[0][0] is Text
    assert variables(source) == ['$name']


def test_attribute_line_above_paragraph_kept():
    assert lex('{.x}\n{{ $name }} text\n')[0][0] in Name.Attribute
    assert lex('{.x}\n{$name}: v\n')[0][0] in Name.Attribute
