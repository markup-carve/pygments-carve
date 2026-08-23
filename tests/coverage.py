"""Shared helpers for measuring what the lexer actually scopes.

The weak version of this test is "the lexer runs without raising". A lexer that
emits every character as ``Token.Text`` passes that, and passes a zero-Error
check over the whole corpus too, while highlighting nothing. So the measure here
is per construct: the payload that construct exists to demonstrate must land in
a token whose type is not plain text.
"""

import os

import pytest

from pygments.token import Error, Text

import inventory

#: Token types that mean "not scoped".
UNSCOPED = (Text, Text.Whitespace)


def load_constructs():
    """The construct inventory, read from the carve-grammars submodule.

    It used to be a vendored copy that nothing compared against upstream, and it
    had drifted three ways (markup-carve/pygments-carve#1). There is no copy any
    more, so the only way this list can be wrong is that the submodule pin is
    old - which is a commit in git that a reviewer sees, not a silent edit.
    """
    return inventory.load_inventory()


def refuse_skip_in_ci(present, what, remedy):
    """Skip locally when a submodule is absent, and REFUSE that skip in CI.

    A suite whose only gate is a corpus it did not check out reports a green
    tick for zero documents. Locally that is a convenience; in CI it is a
    silent pass, so there it fails instead.
    """
    if present:
        return
    if os.environ.get('CI'):
        pytest.fail(
            '%s is not there and this is CI, where it is not optional - a skip here '
            'is a green tick over nothing. Check out the submodules: %s' % (what, remedy)
        )
    pytest.skip('%s not present; run: %s' % (what, remedy))


def payload_of(construct):
    """The text that must carry a scope.

    ``enginePayload`` exists for the few constructs the line-based sibling
    grammars tokenize at a coarser granularity than TextMate does; this lexer is
    in that family, so it uses the same payload they do when one is given.
    """
    return construct.get('enginePayload') or construct['payload']


def scope_of(lexer, source, payload):
    """The first non-text token type covering ``payload``, or None."""
    for ttype, value in lexer.get_tokens(source):
        if payload in value and ttype not in UNSCOPED and ttype is not Error:
            return ttype
    return None


def error_tokens(lexer, source):
    """Every ``Token.Error`` the lexer emits for ``source``."""
    return [value for ttype, value in lexer.get_tokens(source) if ttype is Error]
