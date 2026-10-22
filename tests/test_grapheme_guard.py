"""A delimiter followed by a grapheme extender is text (CARVE-P3-025).

A combining or spacing mark (Mn, Mc, Me), a variation selector U+FE00-U+FE0F or
U+200D after a delimiter makes it the first code point of a larger character,
such as the keycap `*` U+FE0F U+20E3. It neither opens nor closes, and a later
delimiter still pairs across it. The same guard sits on every braced opener,
the editorial frames and `{%` included, and on the `*` of `/*`.

The samples are the examples of spec section 600; each expectation is the
delimiter run the engine's HTML shows as markup.
"""

import pytest

from pygments.token import Comment, Operator, Punctuation

from pygments_carve import CarveLexer

from lexerrules import build_lexer, lexer_source

LEXER = CarveLexer()
SOURCE = lexer_source()
GUARD = "_WHOLE = '(?!' + _extender_class() + ')'"

KEYCAP = '️⃣'

PINS = [
    ('*' + KEYCAP + 'abc*', []),
    ('*a*' + KEYCAP, []),
    ('*a*́ b*', ['*', '*']),
    ('_︎x _y_', ['_', '_']),
    ('~a~‍b~', ['~', '~']),
    ('*x* *' + KEYCAP + ' *y*', ['*', '*', '*', '*']),
    ('{*' + KEYCAP + 'abc*}', []),
    ('/*️a*/', ['/', '/']),
    ('*ाx *y*', ['*', '*']),
    ('{^⃣x^}', []),
    ('{,︎x,}', []),
    ('{+⃣x+} {+y+}', ['{+', '+}']),
    ('{-︎x-} {-y-}', ['{-', '-}']),
    ('{~́a~>b~} {~c~>d~}', ['{~', '~>', '~}']),
    ('{#' + KEYCAP + ' x#} {#y#}', ['{#', '#}']),
    ('a{% y %}b {%ाx%}', ['{%', '%}']),
]


def delimiters(lexer, sample):
    return [v for t, v in lexer.get_tokens(sample)
            if t in (Punctuation, Operator, Comment.Preproc)]


@pytest.mark.parametrize('sample,expect', PINS, ids=[ascii(s) for s, _ in PINS])
def test_a_delimiter_inside_a_larger_character_is_text(sample, expect):
    assert delimiters(LEXER, sample) == expect


def test_the_pins_need_the_guard():
    assert SOURCE.count(GUARD) == 1, 'the guard definition has moved'
    unguarded = build_lexer(SOURCE.replace(GUARD, "_WHOLE = ''"))
    held = [sample for sample, _ in PINS
            if list(unguarded.get_tokens(sample)) == list(LEXER.get_tokens(sample))]
    assert not held, held
