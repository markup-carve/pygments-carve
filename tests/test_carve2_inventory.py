"""One scope check for each 0.2 upgrade or clause inventory row."""

import pytest
from pygments.lexers import get_lexer_by_name
from pygments.token import Comment, Generic, Keyword, Literal, Name, Number, Operator, Punctuation, Text

from pygments_carve import Carve2Lexer, CarveLexer


LEXER = Carve2Lexer()


def scoped(source):
    return [(token, value) for token, value in LEXER.get_tokens(source)
            if token not in Text and value.strip()]


@pytest.mark.parametrize('case, source, present, absent', [
    ('U-001', 'text\n# Heading\n', None, Generic.Heading),
    ('U-014', '- first\n+\n> note\n', Punctuation, Operator),
    ('U-031', '{.note}\n\nParagraph.\n', None, Name.Attribute),
    ('U-032', '{.a\n .b}\nParagraph.\n', None, Name.Attribute),
    ('U-044', 'para\n\n___\n', None, Punctuation),
    ('U-045', '* * *\n\n- - -\n', Punctuation, None),
    ('U-049', '```\ncode\n   ```\nafter\n', Literal.String.Backtick, Name.Other),
    ('U-050', '%%%\nhidden\n%%% visible?\nafter\n', Comment, None),
    ('U-055', '| a | b |\n|---|--:|\n| 1 | 2 |\n', Punctuation.Table, Operator.Table.Alignment),
    ('U-056', '|=< a |=> b |=~ c |\n', Operator.Table.Header, Operator.Table.Alignment),
    ('U-063', '| a | b |\n\n^ Caption\n', Punctuation.Table, Punctuation.Caption),
    ('U-065', 'an _underlined_ word\n', None, Generic.Underline),
    ('U-066', 'a ~struck~ word\n', None, Generic.Deleted),
    ('U-067', 'a =marked= word\n', None, Generic.Inserted),
    ('U-068', '/*bold italic*/ and */bold italic/*\n', Generic.Strong, None),
    ('U-069', '{~old~>new~}\n', Generic.Deleted, Operator),
    ('U-101', '= Heading\n', Generic.Heading, None),
    ('U-103', 'a. one\nb. two\n', Number.Integer, None),
    ('U-104', '::: > "T"\nquoted\n:::\n', Operator, None),
    ('U-105', '```=html "T"\n<b>x</b>\n```\n', Keyword.Type, Literal.String.Backtick),
    ('U-106', ':: term\nmore term text\n: first description\n', Generic.Subheading, None),
    ('U-107', '| a | b |\n^ first\n^ second\n', Generic.Subheading.Caption, None),
    ('U-289', '{{ a.crv @shift:1 }}\n', Name.Namespace, None),
    ('CC-112', 'a\n%% #region x\nb', Comment.Special, None),
    ('CC-893', '|=< a |\n', Operator.Table.Header, Operator.Table.Alignment),
    ('CC-894', '|={<} a |\n', Operator.Table.Alignment, None),
])
def test_inventory_scope(case, source, present, absent):
    tokens = scoped(source)
    if present is not None:
        assert any(token is present for token, _ in tokens), (case, tokens)
    if absent is not None:
        assert not any(token is absent for token, _ in tokens), (case, tokens)


def test_comment_closer_requires_only_whitespace_after_the_run():
    tokens = scoped('%%%\nhidden\n%%% visible?\nafter\n%%%\n')
    assert any(token is Comment and 'after' in value for token, value in tokens)
    assert sum(token is Comment.Preproc for token, _ in tokens) == 2


def test_wider_comment_closer_is_entirely_a_delimiter():
    tokens = scoped('%%%\nbody\n%%%%\nafter\n')
    assert ''.join(value for token, value in tokens if token is Comment.Preproc) == '%%%%%%%'
    assert not any(token is Comment and '%' in value for token, value in tokens)


def test_a_later_caret_is_caption_text():
    tokens = scoped('| a | b |\n^ first\n^ second\n')
    assert sum(token is Punctuation.Caption for token, _ in tokens) == 1
    assert any(token is Generic.Subheading.Caption and '^' in value for token, value in tokens)


@pytest.mark.parametrize('source', ['- +\n```\nx\n```\n', '> +\n- item\n'])
def test_first_block_plus_is_text(source):
    assert not any(value == '+' and token is Punctuation for token, value in scoped(source))


def test_new_alias_and_legacy_lexer_stay_separate():
    assert isinstance(get_lexer_by_name('carve2'), Carve2Lexer)
    assert isinstance(get_lexer_by_name('carve'), CarveLexer)
    assert (Generic.Underline, 'u') in list(CarveLexer().get_tokens('_u_'))
    assert not any(token is Generic.Underline for token, _ in LEXER.get_tokens('_u_'))


@pytest.mark.parametrize('source, token', [
    ('***\n', Punctuation),
    ('{^sup^}', Generic.Emph),
    ('{,sub,}', Generic.Emph),
    ('{_under_}', Generic.Underline),
    ('{~strike~}', Generic.Deleted),
    ('{=mark=}', Generic.Inserted),
])
def test_new_positive_shapes(source, token):
    assert any(actual is token for actual, _ in scoped(source))
