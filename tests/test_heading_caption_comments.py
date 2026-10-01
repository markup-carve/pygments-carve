import pytest
from pygments.token import Comment, Literal
from pygments_carve.lexer import CarveLexer


def token_at(source, needle):
    at = source.index(needle)
    offset = 0
    for kind, value in CarveLexer().get_tokens(source):
        offset += len(value)
        if offset > at:
            return kind
    raise AssertionError(needle)


@pytest.mark.parametrize('prefix', ['# a ', '> # a ', '![alt](x.png)\n^ cap ', '> ![alt](x.png)\n> ^ cap '])
@pytest.mark.parametrize('body', ['`x %% b` c', '``x %% b`` c', '!`x %% b` c', '$`x %% b` c', '`x %% b'])
def test_verbatim_percent_is_not_a_comment(prefix, body):
    source = prefix + body + '\n\nplain tail'
    assert token_at(source, '%%') in Literal
    assert token_at(source, 'plain tail') not in Literal.String
    assert token_at(source, 'plain tail') not in Comment


@pytest.mark.parametrize('prefix', ['# a ', '> # a ', '![alt](x.png)\n^ cap ', '> ![alt](x.png)\n> ^ cap '])
@pytest.mark.parametrize('gap', [' ', '\t'])
def test_real_trailing_comment(prefix, gap):
    source = prefix + '`x`' + gap + '%% hidden'
    assert token_at(source, '%%') in Comment


@pytest.mark.parametrize('prefix', ['# a ', '> # a ', '![alt](x.png)\n^ cap ', '> ![alt](x.png)\n> ^ cap '])
@pytest.mark.parametrize('slashes', [1, 2, 3, 4])
def test_escaped_backtick_parity(prefix, slashes):
    source = prefix + chr(92) * slashes + '`x %% hidden'
    kind = token_at(source, '%%')
    assert (kind in Comment) == (slashes % 2 == 1)
