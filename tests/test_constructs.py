"""Every construct in the shared inventory carries a scope, or is recorded here.

The inventory is carve-grammars' ``tests/lib/constructs.js``, vendored as
``constructs.json``. It is the same list the Prism, highlight.js and TextMate
sweeps run, which is the point: a construct cannot be covered on some surfaces
and quietly missing on this one.

NOT_COVERED is an allowlist, not a skip list. An entry needs a reason, and an
entry that starts passing FAILS the suite - so a gap that gets fixed cannot sit
here pretending to still be a gap, and the file stays an honest ledger rather
than a place to bury misses.
"""

import pytest

from pygments_carve import CarveLexer

from coverage import load_constructs, payload_of, scope_of

#: construct name -> why this lexer does not scope its payload.
#:
#: Empty, and meant to stay that way. All 173 constructs in the shared inventory
#: carry a scope. The mechanism is kept because the inventory grows: a construct
#: added upstream shows up here as a failure, and the choice is then to lex it or
#: to write down why not - never to let it pass unnoticed.
NOT_COVERED = {}

LEXER = CarveLexer()
CONSTRUCTS = load_constructs()


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
        if construct['attr'] or construct['name'] in NOT_COVERED:
            continue
        scope = scope_of(LEXER, construct['sample'], payload_of(construct))
        if scope is Name.Attribute:
            offenders.append((construct['name'], str(scope)))
    assert not offenders, 'claimed by the attribute rule: %s' % offenders
