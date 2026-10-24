"""The lexer is reachable the way a Pygments consumer actually reaches it."""

import pytest
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.util import ClassNotFound

from pygments.token import Operator, String

from pygments_carve import CarveLexer
from pygments_carve.lexer import CsvLexer, TsvLexer

ALIASES = ['carve', 'crv']


@pytest.mark.parametrize('alias', ALIASES)
def test_alias_resolves_through_the_entry_point(alias):
    """This is what makes a fence word work in MkDocs, Sphinx or zensical.

    It passes only when the package is installed, because the lookup goes
    through the pygments.lexers entry point rather than a direct import.
    """
    try:
        lexer = get_lexer_by_name(alias)
    except ClassNotFound:
        pytest.fail(
            'alias %r does not resolve. The package must be installed for the '
            'pygments.lexers entry point to be registered: pip install -e .' % alias
        )
    assert isinstance(lexer, CarveLexer)


@pytest.mark.parametrize('filename', ['doc.crv', 'doc.carve'])
def test_filename_resolves(filename):
    assert isinstance(get_lexer_for_filename(filename), CarveLexer)


def test_declares_every_alias():
    for alias in ALIASES:
        assert alias in CarveLexer.aliases


@pytest.mark.parametrize(('alias', 'expected', 'separator'), [
    ('csv', CsvLexer, ','),
    ('tsv', TsvLexer, '\t'),
])
def test_delimited_alias_resolves_through_entry_point(alias, expected, separator):
    lexer = get_lexer_by_name(alias)
    assert isinstance(lexer, expected)
    tokens = list(lexer.get_tokens(f'name{separator}value\na{separator}b\n'))
    assert any(token is Operator.Word and value == separator for token, value in tokens)
    assert any(token in String and 'a' in value for token, value in tokens)
