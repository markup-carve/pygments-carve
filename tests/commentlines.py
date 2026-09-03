"""Read a corpus case for the one property a comment has: it renders nothing.

A comment is invisible, so every source line the lexer scopes ENTIRELY as a
comment must contribute nothing to the HTML the corpus says the document renders
to. That is a property the corpus states without anyone naming a construct, the
same way ``corpusdefs`` reads definitions out of the source/HTML pair - and it is
the property markup-carve/pygments-carve#30 broke, in eight documents, under a
green suite.

WHY WORDS AND NOT LINES. A line's text does not survive into the HTML verbatim:
`{+ins+}` becomes `<ins>ins</ins>` and a marker is dropped. So the reading is per
WORD, and only for words that appear on no other line - a word the document also
uses outside the comment says nothing about whether the comment was hidden.

IT IS ONE-SIDED, deliberately. The reverse - content the lexer leaves plain that
the corpus does not render - is the under-colouring direction, which this lexer
takes knowingly wherever it has no container model (see the README). Burial is
the direction that loses a reader's text.
"""

import html as htmlmod
import re

from pygments.token import Comment

#: A word: any run of alphanumerics. `_` is excluded because it is a Carve
#: delimiter, so a run around one is two words in the source and one in the HTML.
WORD = re.compile(r'[^\W_]+', re.UNICODE)


def _per_line(lexer, source):
    """Each source line, with ``True`` comment, ``False`` content, ``None`` blank."""
    scoped = bytearray(len(source))
    for start, ttype, value in lexer.get_tokens_unprocessed(source):
        if ttype in Comment:
            for i in range(start, min(start + len(value), len(source))):
                scoped[i] = 1
    out, offset = [], 0
    for line in source.split('\n'):
        flags = [scoped[offset + i] for i, ch in enumerate(line) if not ch.isspace()]
        out.append((line, all(flags) if flags else None))
        offset += len(line) + 1
    return out


def comment_lines(lexer, source):
    """``(lines whose every non-space character is comment-scoped, the rest)``."""
    read = _per_line(lexer, source)
    return ([l for l, f in read if f is True],
            [l for l, f in read if f is False])


def rendered_words(html):
    """Every word the expected HTML puts in front of a reader."""
    return set(WORD.findall(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', html))))


def buried(lexer, source, html):
    """Words the lexer hides in a comment that the corpus renders as content."""
    hidden, shown = comment_lines(lexer, source)
    words = set()
    for line in hidden:
        words |= set(WORD.findall(line))
    for line in shown:
        words -= set(WORD.findall(line))
    return sorted(words & rendered_words(html))


def classify(lexer, source):
    """One character per source line: ``C`` comment, ``.`` content, ``_`` blank.

    The bug this file exists for is entirely a question of which lines are
    commented out, so this is the shape a pin records.
    """
    return ''.join({True: 'C', False: '.', None: '_'}[f]
                   for _, f in _per_line(lexer, source))


def collapsed(lexer, source):
    """The token stream with consecutive same-type tokens joined.

    Plain content is emitted one character per token, which makes the raw run
    unreadable as a pin. What it costs is granularity: the block line-comment
    rule emits a line's margin as ONE `Text` token and the inline fallback emits
    it one character at a time, and joining them makes those two identical. The
    one pin that turns on it reads the raw run instead.
    """
    out = []
    for ttype, value in lexer.get_tokens(source):
        if out and out[-1][0] is ttype:
            out[-1][1] += value
        else:
            out.append([ttype, value])
    return tuple((t, v) for t, v in out)
