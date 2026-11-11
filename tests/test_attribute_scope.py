"""What an inline attribute block attaches to depends on more than its line.

A footnote reference is one only with a definition in the document
(pygments-carve#143), and a `]` closes a span opened anywhere earlier in its
paragraph (pygments-carve#144). Each reading is carveToHtml's at carve-js main.
"""

import pytest

from pygments.token import Name, Punctuation, Text

from pygments_carve import CarveLexer

LEXER = CarveLexer(handlecodeblocks=False)


def attributes(source):
    return [v for t, v in LEXER.get_tokens(source) if t is Name.Attribute]


def footnote_refs(source):
    tokens = list(LEXER.get_tokens(source))
    return [tokens[n + 1][1] for n in range(len(tokens) - 2)
            if tokens[n] == (Punctuation, '[^') and tokens[n + 1][0] is Name.Label
            and tokens[n + 2] == (Punctuation, ']')]


@pytest.mark.parametrize('source', [
    '[^n]{.x} a\n',
    '[^n]{.x}{.y} a\n',
    '> [^n]{.x} a\n',
    '{+[^n]{.x}+} a\n',
    '[^N]{.x} a\n\n[^n]: d\n',
    '[^n]{.x} a\n\n[^n]:\n',
    '[^n]{.x} a\n\n```\n[^n]: d\n```\n',
])
def test_an_undefined_footnote_reference_is_text(source):
    assert footnote_refs(source) == []
    assert attributes(source) == []


@pytest.mark.parametrize('source', [
    '[^n]{.x} a\n\n[^n]: d\n',
    '[^n]: d\n\n[^n]{.x} a\n',
    '[^a  b]{.x} a\n\n[^a b]: d\n',
    '[^n]{.x} a\n\n> [^n]: d\n',
    '[^n]{.x} a\n\n- [^n]: d\n',
    '[^n]: %%%\n  c\n  %%%\n\n[^n]{.x} a\n',
    '{+[^n]{.x}+} a\n\n[^n]: d\n',
])
def test_a_defined_footnote_reference_takes_its_block(source):
    assert len(footnote_refs(source)) == 1
    assert attributes(source)[0] == '{.x}'


def test_the_reproduction_of_143_is_text():
    assert [t for t, v in LEXER.get_tokens('[^n]{.x} a\n') if v.strip()] == [Text] * 5


@pytest.mark.parametrize('source', [
    'a]{.x} b\n',
    'b] c]{.x} d\n',
    '\\[a\nb]{.x} c\n',
    '[a] b\nc]{.x} d\n',
    '[a\n\nb]{.x} c\n',
    '# [a\nb]{.x} c\n',
    '- [a\n- b]{.x} c\n',
    '[a\n> b]{.x} c\n',
    '`[`a\nb]{.x} c\n',
    '```\n[a\n```\nb]{.x} c\n',
    '^[a](u){.x} c\n',
    ':r[a b](u){.x} c\n',
    '[a\n---\nb]{.x}\n',
    '[a\n%%%\nz\n%%%\nb]{.x}\n',
    '[a\n::: d\nb]{.x}\n',
    '[a\n| t |\nb]{.x}\n',
    '[a\n{.y}\nb]{.x}\n',
    '[a\n[^m]: d\nb]{.x}\n',
    '- [a\n. b]{.x}\n',
    ':' + 'a' * 80 + '[x](u){.x}\n',
    '%% [\nx]{.x}\n',
    '{% [ %}\nx]{.x}\n',
    '[a](foo[bar) x]{.x}\n',
    '[a](foo[bar)\nx]{.x}\n',
    '<http://a[b>\nx]{.x}\n',
    '[p]{key="[a"} x]{.x}\n',
    '[a\n| t |{.r}\nb]{.x}\n',
])
def test_a_closer_with_no_open_span_takes_no_block(source):
    assert '{.x}' not in attributes(source)


@pytest.mark.parametrize('source', [
    '[a\nb]{.x} c\n',
    '> [a\n> b]{.x} c\n',
    '> [a\nb]{.x} c\n',
    '- [a\n  b]{.x} c\n',
    '[a\n- b]{.x} c\n',
    '[a [b\n- b]{.x} c\n',
    '^[a\nb]{.x} c\n',
    '\\^[a](u){.x} c\n',
    '[a\n%% c\nb]{.x}\n',
    '[a\n--\nb]{.x}\n',
    '[a\n. b]{.x}\n',
    '[a\n+ b\nb]{.x}\n',
    '- [a\n+ b\nb]{.x}\n',
    '[a\n[r]: /u\nb]{.x}\n',
    '| [a]{.x} |\n',
    ':1r[x](u){.x}\n',
    '[a {% x %}\nb]{.x}\n',
    '[[a](u)\nb]{.x}\n',
    '[x](a(b(c)d)e){.x}\n',
    '[a]{.k}[b\nc]{.x}\n',
    '[a\n|x| foo\nb]{.x}\n',
])
def test_a_span_opened_earlier_in_the_paragraph_takes_its_block(source):
    assert attributes(source)[-1] == '{.x}'
