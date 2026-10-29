"""Table and caption tokens retain their Pygments parent types."""

import pytest
from pygments.token import Generic, Operator, Punctuation, Text

from pygments_carve import CarveLexer


@pytest.mark.parametrize('source, expected', [
    ('|= a |\n', [(Operator.Table.Header, '|='), (Punctuation.Table, '|')]),
    ('|=< a |\n', [(Operator.Table.Header, '|='), (Operator.Table.Alignment, '<'),
                  (Punctuation.Table, '|')]),
    ('|=~> a |\n', [(Operator.Table.Header, '|='), (Operator.Table.Alignment, '~>'),
                   (Punctuation.Table, '|')]),
    ('|=?v a |\n', [(Operator.Table.Header, '|='), (Operator.Table.Alignment, '?v'),
                   (Punctuation.Table, '|')]),
    ('|?v a |\n', [(Punctuation.Table, '|'), (Operator.Table.Alignment, '?v'),
                  (Punctuation.Table, '|')]),
    ('|< a |\n', [(Punctuation.Table, '|'), (Operator.Table.Alignment, '<'),
                 (Punctuation.Table, '|')]),
    ('|<|\n', [(Punctuation.Table, '|'), (Operator.Table.Colspan, '<'),
              (Punctuation.Table, '|')]),
    ('| ^ |\n', [(Punctuation.Table, '|'), (Operator.Table.Rowspan, ' ^ '),
                (Punctuation.Table, '|')]),
    ('| < |\n', [(Punctuation.Table, '|'), (Operator.Table.Colspan, ' < '),
                (Punctuation.Table, '|')]),
    ('| ~> |\n', [(Punctuation.Table, '|'), (Operator.Table.Alignment, ' ~> '),
                 (Punctuation.Table, '|')]),
    ('| a |\n+ b |\n', [(Punctuation.Table, '|'), (Punctuation.Table, '|'),
                       (Punctuation.Table.Continuation, '+'), (Punctuation.Table, '|')]),
    ('^ caption\n', [(Punctuation.Caption, '^'),
                    (Generic.Subheading.Caption, 'caption')]),
])
def test_table_and_caption_subtypes(source, expected):
    actual = [(token, value) for token, value in CarveLexer().get_tokens(source)
              if token not in Text]
    assert actual == expected
    assert ''.join(value for _, value in CarveLexer().get_tokens(source)) == source


@pytest.mark.parametrize('subtype, parent', [
    (Operator.Table.Header, Operator),
    (Operator.Table.Alignment, Operator),
    (Operator.Table.Rowspan, Operator),
    (Operator.Table.Colspan, Operator),
    (Punctuation.Table, Punctuation),
    (Punctuation.Table.Continuation, Punctuation),
    (Punctuation.Caption, Punctuation),
    (Generic.Subheading.Caption, Generic.Subheading),
])
def test_subtype_inherits_existing_style(subtype, parent):
    assert subtype in parent


def test_glued_colspan_cell_is_not_alignment():
    for source in ('| a |< |\n', '|< |\n'):
        tokens = [(t, v) for t, v in CarveLexer().get_tokens(source) if v.strip()]
        assert (Operator.Table.Colspan, '<') in [(t, v.strip()) for t, v in tokens], source
