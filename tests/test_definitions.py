"""A definition is scoped as a definition, wherever on its line it starts.

Two failures are pinned here. A definition written after a block marker
(``- [t]: /t``) used to lose to the marker rules and come out as a shortcut
reference link plus loose text (markup-carve/pygments-carve#20). And a footnote
or abbreviation definition used to push a state nothing pops, so every block
construct after it in the document lost its scope
(markup-carve/pygments-carve#22).

The controls are the point of the file. A shape that is NOT a definition - no
colon, no separator, a tab separator, an abbreviation behind a marker - must
still come out as plain content, or the fix has over-matched.
"""

import pytest

from pygments.token import Generic, Name, Number, Punctuation, Text

from pygments_carve import CarveLexer

LEXER = CarveLexer()


def run(source):
    """The token run for ``source``, with whitespace-only tokens dropped."""
    return [(t, v) for t, v in LEXER.get_tokens(source) if v.strip()]


#: The token run a link reference definition produces for `[t]: /t`.
LINK_DEFINITION = [
    (Punctuation, '['),
    (Name.Label, 't'),
    (Punctuation, ']:'),
    (Name.Tag, '/t'),
]

#: marker text -> the tokens that marker itself contributes.
MARKERS = {
    '': [],
    '- ': [(Punctuation, '-')],
    '* ': [(Punctuation, '*')],
    '1. ': [(Number.Integer, '1.')],
    'a) ': [(Number.Integer, 'a)')],
    '> ': [(Punctuation, '>')],
    '>> ': [(Punctuation, '>>')],
    '* * ': [(Punctuation, '*'), (Punctuation, '*')],
    '> - ': [(Punctuation, '>'), (Punctuation, '-')],
}


@pytest.mark.parametrize('marker', sorted(MARKERS), ids=lambda m: repr(m))
def test_link_definition_after_a_marker_is_a_definition(marker):
    """The marker keeps its own token and the definition keeps its run.

    corpus 442-* pins `- [t]: /t` and `1. [t]: /t` as definitions - their
    expected HTML resolves the call - and 16-reference-link-3/4 pin the `>` and
    `-` shapes.
    """
    assert run(marker + '[t]: /t\n') == MARKERS[marker] + LINK_DEFINITION


def test_marker_led_definition_matches_its_own_line_control():
    """The same definition on its own line is the control for the shape."""
    own_line = run('- lead\n\n[t]: /t\n')[-len(LINK_DEFINITION):]
    assert own_line == LINK_DEFINITION
    assert run('- [t]: /t\n')[-len(LINK_DEFINITION):] == own_line


def test_footnote_definition_after_a_marker_is_a_definition():
    """corpus 117-footnote-definition-inside-a-container-is-collected."""
    assert run('- [^a]: note')[:4] == [
        (Punctuation, '-'),
        (Punctuation, '[^'),
        (Name.Label, 'a'),
        (Punctuation, ']:'),
    ]


# ----------------------------------------------------------------------------
# Controls: shapes that must NOT read as a definition.
# ----------------------------------------------------------------------------

@pytest.mark.parametrize('source', [
    '- [tt] /t\n',      # no colon at all
    '- [tt]:/t\n',      # no separator
    '- [tt]:\t/t\n',    # a tab-first separator makes the line a paragraph
    '- [tt]:\n',        # nothing to define
])
def test_a_non_definition_on_a_marker_line_stays_content(source):
    """Everything after the marker is plain text - no label, no destination."""
    assert run(source)[0] == (Punctuation, '-')
    scoped = [(t, v) for t, v in run(source)[1:] if t is not Text]
    assert not scoped, 'scoped as %r, so the definition rule over-matched' % scoped


@pytest.mark.parametrize('marker', ['- ', '> '])
def test_an_abbreviation_is_defined_at_document_level_only(marker):
    """corpus 179 and 180: a marker line does not define an abbreviation."""
    assert not [v for t, v in run(marker + '*[HTML]: Hyper Text') if t is Name.Entity]
    # ... while the same definition at document level does.
    assert (Name.Entity, 'HTML') in run('*[HTML]: Hyper Text')


# ----------------------------------------------------------------------------
# A definition body ends with its line (markup-carve/pygments-carve#22).
# ----------------------------------------------------------------------------

@pytest.mark.parametrize('definition', ['[^a]: one', '*[A]: one', '[a]: /u'])
def test_a_definition_does_not_swallow_the_next_block(definition):
    assert run(definition + '\n\n# H\n')[-2:] == [
        (Punctuation, '#'),
        (Generic.Heading, 'H'),
    ]


def test_a_second_footnote_definition_is_still_a_definition():
    tokens = run('[^a]: one\n\n[^b]: two\n')
    second = tokens.index((Punctuation, '[^'), 1)
    assert tokens[second:second + 3] == [
        (Punctuation, '[^'),
        (Name.Label, 'b'),
        (Punctuation, ']:'),
    ]
