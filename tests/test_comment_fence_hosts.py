"""A `%%%` comment fence in every host, against the spec model at carve main
(markup-carve/pygments-carve#146, #147)."""

import time

import pytest

from pygments.token import Comment, Punctuation, Text

from pygments_carve import CarveLexer

LEXER = CarveLexer(handlecodeblocks=False)


def shown(source):
    """The words outside comment tokens."""
    return ''.join(v for t, v in LEXER.get_tokens(source) if t not in Comment).split()


@pytest.mark.parametrize('source, words', [
    # #146: an unclosed fence hides the rest of its host (carve#4907, corpus 167).
    ('p\n\n%%%\nx\n\ny\n', ['p']),
    ('p\n%%%\nx\n', ['p']),
    ('  %%%\nx\ny\n', []),
    ('- i\n\n  %%%\n  a\n b\n\nc\n', ['-', 'i', 'b', 'c']),
    ('- i\n\n    %%%\n  a\nb\n', ['-', 'i', 'b']),
    ('- x\n  %%%\ny\n  %%%\nz\n', ['-', 'x', 'y']),
    ('- %%%\n  a\nb\n  %%%\nc\n', ['-', 'b']),
    # #146: a task item's marker-line fence pairs like a bullet's.
    ('- [ ] %%%\n  x\n%%%\n\nVIS\n', ['-', '[', ']', 'VIS']),
    ('- [ ] %%%\n x\nb\n', ['-', '[', ']', 'x', 'b']),
    ('- [ ]   %%%\n  a\n   b\nc\n', ['-', '[', ']', 'c']),
    ('- [ ] - %%%\n%%%\n\nw\n', ['-', '[', ']', '-', 'w']),
    # A `%%` line is column-exempt: it never ends a span by missing its owner.
    ('- %%%\n  a\n%%%%\nb\n', ['-', 'b']),
    ('- %%%\n  a\n%% q\nb\n', ['-', 'b']),
    # #147: a fence in a quote, ended by the quote or closed unmarked (corpus 888).
    ('> %%%\n> x\n> %%%\n\ny\n', ['>', '>', '>', 'y']),
    ('> %%%\n> a\nb\n', ['>', '>', 'b']),
    ('> %%%\n> a\n%%%\nb\n', ['>', '>', 'b']),
    ('%%%\na\n> %%%\nb\n', []),
    ('> p\n>\n>   %%%\n> a\n', ['>', 'p', '>', '>', '>']),
    ('- > %%%\n  > a\nb\n', ['-', '>', '>', 'b']),
    ('- > %%%\n\n  > w\n', ['-', '>', '>', 'w']),
    # The owner is found however far above the opener its marker line is.
    ('- i\n' + '  x\n' * 100 + '  %%%\n  s\nout\n', ['-', 'i'] + ['x'] * 100 + ['out']),
    # An indented `%%%` in a line block is verse (CARVE-P9-044).
    ('::: |\n    %%%\n  x\n    %%%\n:::\n', [':::', '|', 'x', ':::']),
])
def test_a_comment_fence_hides_what_the_model_hides(source, words):
    assert shown(source) == words


def test_a_quoted_fence_keeps_its_markers_as_punctuation():
    assert list(LEXER.get_tokens('> %%%\n> x\n> %%%\n\ny\n')) == [
        (Punctuation, '>'), (Text, ' '), (Comment.Preproc, '%%%'), (Text, '\n'),
        (Punctuation, '>'), (Text, ' '), (Comment, 'x\n'),
        (Punctuation, '>'), (Text, ' '), (Comment.Preproc, '%%%'), (Text, '\n'),
        (Text, '\n'), (Text, 'y'), (Text, '\n')]


@pytest.mark.parametrize('source', [
    '- %%%\n' + '  x\n' * 32000,
    '> %%%\n' + '> x\n' * 32000,
    'p\n' * 8000 + '  %%%\n' + 'x\n' * 8000,
    '- i\n' + '  x\n  %%%\n  s\n  %%%\n' * 8000,
])
def test_a_long_fence_body_is_read_once(source):
    start = time.perf_counter()
    list(LEXER.get_tokens(source))
    assert time.perf_counter() - start < 10
