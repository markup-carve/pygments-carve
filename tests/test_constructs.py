"""Every construct in the shared inventory carries a scope, or is recorded here.

The inventory is carve-grammars' ``tests/lib/constructs.js``, READ IN PLACE from
the ``carve-grammars`` submodule. It is the same list the Prism, highlight.js
and TextMate sweeps run, which is the point: a construct cannot be covered on
some surfaces and quietly missing on this one.

It used to be a vendored ``constructs.json``, and the copy is what made that
claim untrue - nothing in the org moved it and nothing compared it, so it sat at
173 entries against upstream's 175 and nobody could see it
(markup-carve/pygments-carve#1). Reading upstream in place means there is no
second list to drift; a new construct arrives with the pin, and this file is
where the decision to lex it or write down why not gets forced.

NOT_COVERED is an allowlist, not a skip list. An entry needs a reason, and an
entry that starts passing FAILS the suite - so a gap that gets fixed cannot sit
here pretending to still be a gap, and the file stays an honest ledger rather
than a place to bury misses.

WHAT THIS SWEEP DOES NOT MEASURE, so nobody leans on it for it. It asks only
that the payload carries SOME non-text token. Any non-text token satisfies that,
which means it cannot tell a construct's own rule from a neighbouring rule that
happens to catch the same payload: sixteen of the forty-six rules in the inline
state could be deleted with this sweep - and the whole suite - still green
(markup-carve/pygments-carve#25). Its job is cross-surface parity, that a
construct covered on Prism or TextMate is not quietly missing here. Rules are
held down by `test_inline_rules.py`, which records the whole scoped run.
"""

import pytest

from pygments_carve import CarveLexer

import inventory
from coverage import load_constructs, payload_of, scope_of

#: construct name -> why this lexer does not scope its payload.
#:
#: Entries where the shared inventory and the engine disagree and this lexer
#: follows the engine. Every other construct in the inventory carries a scope.
#: The mechanism is kept because the inventory grows: a construct added upstream
#: shows up here as a failure, and the choice is then to lex it or to write down
#: why not - never to let it pass unnoticed.
NOT_COVERED = {
    'code callout': 'the engine renders `<1>` outside a fence as text '
                    '(`<1> explains the line` is `<p>&lt;1&gt; explains the line</p>` '
                    'in carve 0.1.11), so scoping it was an over-color; the marker '
                    'inside a fence is `callout marker in fence`, and still scoped',
}

#: Rows the 0.1.14 spec turned into text, which the inventory still samples
#: (markup-carve/carve-grammars#830).
_STALE_TEXT = {
    'typography arrow deprecated reversed': 'markup-carve/carve#4815',
    'typography arrow deprecated forward': 'markup-carve/carve#4815',
    'typography arrow deprecated bidirectional': 'markup-carve/carve#4815',
    'typography symbol copyright': 'markup-carve/carve#4808',
    'typography symbol registered': 'markup-carve/carve#4808',
    'ordered marker alpha': 'markup-carve/carve#4811, one space after a letter marker',
    'ordered marker roman': 'markup-carve/carve#4811, one space after a roman marker',
    'ordered marker roman lowercase run': 'markup-carve/carve#4811, one space after a roman marker',
    'ordered marker roman uppercase run': 'markup-carve/carve#4811, one space after a roman marker',
    'ordered marker roman word': 'markup-carve/carve#4811, one space after a roman marker',
}
NOT_COVERED.update({name: 'text since %s (markup-carve/carve-grammars#830)' % why
                    for name, why in _STALE_TEXT.items()})
NOT_COVERED['an attribute line spans lines'] = (
    'the sample `{.a` + newline + `.b}` is paragraph text: a continuation line must pass '
    'the opening `{` (carve corpus 253-...-does-2, carve#5830; markup-carve/carve-grammars#843)')

LEXER = CarveLexer()
CONSTRUCTS = load_constructs() if inventory.available() else []

pytestmark = pytest.mark.skipif(
    not inventory.available(),
    reason='carve-grammars submodule not present; run: git submodule update --init',
)


def _named(construct):
    return construct['name']


@pytest.mark.parametrize('construct', CONSTRUCTS, ids=_named)
def test_construct_is_scoped(construct):
    name = construct['name']
    payload = payload_of(construct)
    scope = scope_of(LEXER, construct['sample'], payload)

    if name in NOT_COVERED:
        assert scope is None, (
            'construct %r is listed in NOT_COVERED but IS now scoped as %s. '
            'Delete the entry - a fixed gap must not stay on the allowlist.'
            % (name, scope)
        )
        pytest.xfail('recorded gap: %s' % NOT_COVERED[name])

    if construct.get('plain'):
        assert scope is None, (
            'construct %r is plain text in the engine, but its payload %r is '
            'scoped as %s.' % (name, payload, scope)
        )
        return

    assert scope is not None, (
        'construct %r: payload %r carries no scope. Either fix the lexer or add '
        'an entry to NOT_COVERED with a reason.' % (name, payload)
    )


def test_allowlist_names_real_constructs():
    """An allowlist entry for a construct that no longer exists is dead weight."""
    known = {c['name'] for c in CONSTRUCTS}
    unknown = sorted(set(NOT_COVERED) - known)
    assert not unknown, (
        'NOT_COVERED names constructs that are not in the inventory: %s' % unknown
    )


def test_attribute_constructs_are_not_over_claimed():
    """A non-attribute construct must not be swallowed by the attribute rule.

    This is the failure the sibling sweeps in carve-grammars exist to catch: an
    attribute pattern wide enough to eat the construct next to it reports as
    "scoped" while colouring the wrong thing.
    """
    from pygments.token import Name

    # An attribute block is emitted whole as Name.Attribute, so that is the one
    # scope that means "the attribute rule claimed this".
    offenders = []
    for construct in CONSTRUCTS:
        if construct.get('attr') or construct['name'] in NOT_COVERED:
            continue
        scope = scope_of(LEXER, construct['sample'], payload_of(construct))
        if scope is Name.Attribute:
            offenders.append((construct['name'], str(scope)))
    assert not offenders, 'claimed by the attribute rule: %s' % offenders
