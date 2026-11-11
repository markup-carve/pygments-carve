"""An autolink body takes only the characters the spec admits
(06-inline-links-images.ebnf; markup-carve/pygments-carve#149)."""

import pytest

from pygments.token import Name, Punctuation

from pygments_carve import CarveLexer

LEXER = CarveLexer(handlecodeblocks=False)


def autolinks(source):
    tokens = list(LEXER.get_tokens(source))
    return [tokens[i + 1][1] for i in range(len(tokens) - 2)
            if tokens[i] == (Punctuation, '<') and tokens[i + 1][0] is Name.Tag
            and tokens[i + 2] == (Punctuation, '>')]


@pytest.mark.parametrize('body', [
    'ab@c.d', 'a.b+c_d-e@f-g.h.ij', 'mailto:a@b', 'http://a.b/c?d=e#f',
    'http://a[b]', 'x:y', 'https://e\u00e9.com/',
])
def test_an_autolink(body):
    assert autolinks('w <%s> w\n' % body) == [body]


@pytest.mark.parametrize('body', [
    # email_autolink = {email_char}+, '@', {email_char}+, '.', {letter}+
    'a[b@c', 'a@b', 'a@b.c1', 'a@b.', '@b.c', 'a@@b.c', 'a!b@c.de', 'a@c[d.ef',
    'x@y:z',
    # url_char excludes these, and format characters
    'http://a"b', 'http://a{b', 'http://a}b', 'http://a|b', 'http://a^b',
    'http://a`b', 'http://a\\b', 'https://e\u200b.com/', 'https://e\ufeff.com/',
    'https://e\u0890.com/', 'https://e\U000110bd.com/',
])
def test_not_an_autolink(body):
    assert autolinks('w <%s> w\n' % body) == []


def test_a_bracket_after_a_refused_autolink_opens_a_span():
    tokens = list(LEXER.get_tokens('<a[b@c> x]{.x}\n'))
    assert tokens[0][1] == '<' and tokens[0][0] is not Punctuation
    assert (Name.Attribute, '{.x}') in tokens
