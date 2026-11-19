"""Nested same-lexer runs must not depend on Python's recursion limit."""

import pytest
from pygments.token import Error, Generic, Punctuation

from pygments_carve import CarveLexer


@pytest.mark.parametrize('source, expected', [
    ('> ' * 200 + 'x\n', Punctuation),
    ('{^' * 200 + 'x' + '^}' * 200, Generic.Emph),
    ('- ' * 200 + 'x\n', Punctuation),
    ('{_' * 200 + 'x' + '_}' * 200, Generic.Underline),
])
def test_deep_same_lexer_nesting(source, expected):
    tokens = list(CarveLexer().get_tokens(source))
    assert ''.join(value for _, value in tokens) == source
    assert not any(token in Error for token, _ in tokens)
    assert any(token is expected for token, _ in tokens)
