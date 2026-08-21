"""Shared helpers for measuring what the lexer actually scopes.

The weak version of this test is "the lexer runs without raising". A lexer that
emits every character as ``Token.Text`` passes that, and passes a zero-Error
check over the whole corpus too, while highlighting nothing. So the measure here
is per construct: the payload that construct exists to demonstrate must land in
a token whose type is not plain text.
"""

import json
import pathlib

from pygments.token import Error, Text

CONSTRUCTS_PATH = pathlib.Path(__file__).parent / 'constructs.json'

#: Token types that mean "not scoped".
UNSCOPED = (Text, Text.Whitespace)


def load_constructs():
    """The construct inventory, vendored from carve-grammars."""
    return json.loads(CONSTRUCTS_PATH.read_text(encoding='utf-8'))


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
