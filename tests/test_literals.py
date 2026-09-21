"""Every shape carve-grammars rules is NOT a construct stays unscoped here.

carve-grammars keeps two lists in ``tests/lib/constructs.js``: ``CONSTRUCTS``,
which ``test_constructs.py`` reads, and ``LITERALS``, the shapes that must not
be scoped as the construct they resemble. Only the first was read, so when
carve-grammars ruled ``[a]: /u zzz``, ``[a]: /u  "T"`` and ``+ foo`` to be
prose, this lexer kept highlighting them and nothing failed
(markup-carve/pygments-carve#51).

Pygments has one token vocabulary, not the per-grammar selectors a ``LITERALS``
row names, so the default is stricter: the payload lexes as plain text. A row
whose payload is correctly scoped as a DIFFERENT construct is listed in
``OTHER_CONSTRUCT`` with the exact token type. A row this lexer still gets wrong
is listed in ``KNOWN_DIVERGENCES``. A row arriving upstream is in neither, so
it has to lex as text or this file goes red.
"""

import pytest

from pygments.token import Generic, Keyword, Name, Punctuation

from pygments_carve import CarveLexer

import inventory
from coverage import scope_of

_ITALIC = 'the engine reads an italic run, not a combined one'
_CONTAINER = 'the generic container kind word'

#: row name -> (token type, why that scope is the right reading).
OTHER_CONSTRUCT = {
    'a braced en dash is not an empty deletion':
        (Punctuation, 'typography; a deletion body would be Generic.Deleted'),
    'a mirrored bold-italic closer glued to a word closes nothing':
        (Generic.Emph, _ITALIC),
    'a slash before the mirrored bold-italic opener opens nothing':
        (Generic.Emph, _ITALIC),
    'a mirrored bold-italic opener glued to a word opens nothing':
        (Generic.Emph, _ITALIC),
    'a colon in an attribute id':
        (Name.Variable.Instance, 'the engine renders `#a` as a tag'),
    'a quoted title makes a figure opener a generic container':
        (Keyword.Namespace, _CONTAINER),
    'a [label] makes a figure opener a generic container':
        (Keyword.Namespace, _CONTAINER),
    'a tab does not separate a composite figure opener':
        (Keyword.Namespace, 'the generic container rule takes a tab; the sibling '
                            'grammars make the same trade'),
    'a lone plus is not a table continuation':
        (Punctuation, 'a `continuation_marker`'),
}

_TICKET = 'markup-carve/pygments-carve#52'
_COMBINED = 'read as a combined run; the engine renders an italic'
_LETTERS = 'any letter run is taken as an ordered marker'
_NO_CONTENT = 'a marker needs content after its attribute block'
_NO_TERM = 'no term gate on the `:` marker'
_BOM = 'a U+FEFF is skipped at every line start, not only offset 0'

#: row name -> why this lexer still scopes the payload. All in ``_TICKET``.
KNOWN_DIVERGENCES = {
    'a space after the bold-italic opener is not a combined run': _COMBINED,
    'a space before the bold-italic closer is not a combined run': _COMBINED,
    'a space after the bold-italic opener is refused by that guard alone': _COMBINED,
    'bullet whose attribute block has no content after it': _NO_CONTENT,
    'mixed-case roman run is not a marker': _LETTERS,
    'mixed-case roman run is not a marker, other order': _LETTERS,
    'a two-letter mixed-case roman run is not a marker': _LETTERS,
    'ordered marker whose attribute block has no content after it': _NO_CONTENT,
    'bare dot marker whose attribute block has no content after it': _NO_CONTENT,
    'a description line after plain prose has no term above it': _NO_TERM,
    'a description line below a tab-disqualified term marker': _NO_TERM,
    'a colon in an attribute class': 'the attribute block admits an invalid class name',
    'a dash-first id': 'the attribute block admits an invalid id',
    'a byte order mark below the first line': _BOM,
    'a byte order mark below the first line of a definition list': _BOM,
}

LEXER = CarveLexer()
LITERALS = inventory.load_literals() if inventory.available() else []

pytestmark = pytest.mark.skipif(
    not inventory.available(),
    reason='carve-grammars submodule not present; run: git submodule update --init',
)


def _named(literal):
    return literal['name']


@pytest.mark.parametrize('literal', LITERALS, ids=_named)
def test_literal_is_not_scoped_as_a_construct(literal):
    name = literal['name']
    scope = scope_of(LEXER, literal['sample'], literal['payload'])

    if name in OTHER_CONSTRUCT:
        expected, why = OTHER_CONSTRUCT[name]
        assert scope is expected, (
            '%r: payload %r is expected as %s (%s), got %s'
            % (name, literal['payload'], expected, why, scope))
        return

    if name in KNOWN_DIVERGENCES:
        assert scope is not None, (
            '%r now lexes as text. Delete its KNOWN_DIVERGENCES entry.' % name)
        pytest.xfail('%s (%s)' % (KNOWN_DIVERGENCES[name], _TICKET))

    assert scope is None, (
        'carve-grammars rules %r not to be the construct it resembles, and this '
        'lexer scopes its payload %r as %s. Fix the lexer, or list the row with a '
        'reason.' % (name, literal['payload'], scope))


def test_the_lists_name_real_rows():
    known = {literal['name'] for literal in LITERALS}
    listed = set(OTHER_CONSTRUCT) | set(KNOWN_DIVERGENCES)
    assert not listed - known, 'not in LITERALS: %s' % sorted(listed - known)
    assert not set(OTHER_CONSTRUCT) & set(KNOWN_DIVERGENCES)


def test_the_ticket_rows_are_read():
    """The three rows markup-carve/pygments-carve#51 was filed on."""
    rows = {literal['sample'] for literal in LITERALS}
    assert {'[a]: /u zzz\n', '[a]: /u  "T"\n', '+ foo\n'} <= rows
