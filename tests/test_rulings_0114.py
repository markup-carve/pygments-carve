"""The 0.1.14 rulings this lexer follows, each against the carve-js main reading."""

import pytest

from pygments.token import Comment, Generic, Keyword, Name, Number, Operator, Punctuation, Text

from pygments_carve import CarveLexer

LEXER = CarveLexer()


def scoped(source):
    return [(t, v) for t, v in LEXER.get_tokens(source)
            if t not in (Text, Text.Whitespace) and v.strip()]


# carve#5016, #4402
@pytest.mark.parametrize('source, expect', [
    ('---\n\nPara *b*\n\n# H\n',
     [(Punctuation, '---'), (Comment.Special, '\nPara *b*\n\n# H\n')]),
    ('---', [(Punctuation, '---')]),
    ('--- toml\na = 1\n', [(Punctuation, '---'), (Keyword.Type, 'toml'),
                           (Comment.Special, 'a = 1\n')]),
    ('---yaml\na: 1\n---\n# H\n', [(Punctuation, '---'), (Keyword.Type, 'yaml'),
                                   (Comment.Special, 'a: 1\n'), (Punctuation, '---'),
                                   (Punctuation, '#'), (Generic.Heading, 'H')]),
])
def test_front_matter_needs_no_closer(source, expect):
    assert scoped(source) == expect


@pytest.mark.parametrize('source', ['---  yaml\n*b*\n', '---\tyaml\n*b*\n'])
def test_a_wide_or_tab_format_slot_opens_no_front_matter(source):
    assert (Generic.Strong, 'b') in scoped(source)


# carve#5091 D3, #4980
def test_braced_alignment_is_table_alignment():
    tokens = scoped('|={>} Qty |= N |\n|{> .num} 12 |{?v} y |\n')
    assert [v for t, v in tokens if t is Operator.Table.Alignment] == ['>', '>', '?v']
    assert (Name.Attribute, ' .num') in tokens


def test_braced_strikethrough_in_a_cell_is_not_alignment():
    tokens = scoped('|{~ x ~} | b |\n')
    assert not [v for t, v in tokens if t is Operator.Table.Alignment]
    assert (Generic.Deleted, ' x ') in tokens


def test_an_attributed_alignment_block_holds_no_span_placeholder():
    tokens = scoped('|{> .x} ^ |\n')
    assert (Operator.Table.Alignment, '>') in tokens
    assert (Operator.Table.Rowspan, '^') not in tokens


@pytest.mark.parametrize('source, aligned', [
    ('|{> _foo} x |\n', False),
    ('|{> _k=v} x |\n', True),
])
def test_a_bare_key_does_not_start_with_an_underscore(source, aligned):
    assert ((Operator.Table.Alignment, '>') in scoped(source)) is aligned


def test_an_unpadded_alignment_block_is_content():
    assert not [v for t, v in scoped('|{>}x |\n') if t is Operator.Table.Alignment]


def test_span_placeholders_with_alignment_and_in_header_cells():
    tokens = scoped('|={<} ^ |{~} < |\n|= ^ |= < |\n')
    spans = (Operator.Table.Rowspan, Operator.Table.Colspan)
    assert [t for t, v in tokens if t in spans] == [
        Operator.Table.Rowspan, Operator.Table.Colspan,
        Operator.Table.Rowspan, Operator.Table.Colspan]


def test_the_deprecated_glued_prefix_stays_highlighted():
    tokens = scoped('|=> Q |<^ 1 |\n')
    assert [v for t, v in tokens if t is Operator.Table.Alignment] == ['>', '<^']


# carve#4815, #4851, #4808
@pytest.mark.parametrize('source', ['a -> b', 'a <- b', 'a <-> b', '(c) and (r)'])
def test_removed_typography_is_text(source):
    assert scoped(source) == []


@pytest.mark.parametrize('source, expect', [
    ('a--->b', [(Punctuation, '---')]),
    ('a<---b', [(Punctuation, '---')]),
    ('<--->', [(Punctuation, '---')]),
    ('a <-- b --> c', [(Operator, '<--'), (Operator, '-->')]),
])
def test_an_arrow_needs_its_exact_hyphen_run(source, expect):
    assert scoped(source) == expect


# carve#4809
@pytest.mark.parametrize('source, expect', [
    ('#123 @5 #1.2', []),
    ('#v2 @a1 #fff', [(Name.Variable.Instance, '#v2'), (Name.Variable.Magic, '@a1'),
                      (Name.Variable.Instance, '#fff')]),
])
def test_a_mention_or_tag_name_holds_a_letter(source, expect):
    assert scoped(source) == expect


# carve#4811
@pytest.mark.parametrize('source, marker', [
    ('a.  first\n', 'a.'),
    ('iv.  fourth\n', 'iv.'),
    ('a.{.c}  x\n', 'a.{.c}'),
    ('a) one\n', 'a)'),
    ('10. x\n', '10.'),
])
def test_ordered_markers(source, marker):
    assert scoped(source)[0] == (Number.Integer, marker)


@pytest.mark.parametrize('source', ['a. first\n', 'J. R. R. Tolkien\n', 'iv. fourth\n'])
def test_a_letter_marker_with_one_space_is_prose(source):
    assert not [t for t, v in scoped(source) if t is Number.Integer]


# carve#4894
def test_a_term_is_one_line():
    tokens = scoped(':: a\nb\n: c\n')
    assert tokens[:2] == [(Punctuation, '::'), (Generic.Heading, 'a')]
    assert (Punctuation, ':') not in tokens
    assert scoped(':: t\n\n: d\n')[-1] == (Punctuation, ':')
