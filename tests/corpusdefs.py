"""The definitions a corpus document contains, according to the corpus.

A corpus case is a ``.crv`` source next to the HTML the spec says it renders to.
That pairing is what makes the definitions in a document knowable without a
parser here: a definition is consumed, so its ``[label]:`` text does NOT appear
in the expected HTML, while a definition-shaped line that stays literal does.
The corpus decides, this module only reads the decision.

Used by test_corpus.py to ask the lexer, per document, whether it scopes those
lines as definitions. That is a check the corpus can lose: a construct arriving
in a new spec revision is measured the day it lands, without anybody adding it
to a list first.

The reader errs towards measuring LESS, never towards a wrong reading. Where a
document renders the same ``[label]:`` text literally somewhere and also uses it
as a definition, the literal test cannot tell the two occurrences apart, and
both are dropped. That costs a measurement; guessing which one to keep would
cost a false failure, which is worse. No corpus document is in that shape today,
and ``test_the_corpus_pins_definitions_to_measure`` is the floor that notices if
the reader ever falls silent.
"""

import re

#: A block marker a line may carry before its content. A list or ordered marker
#: may have an attribute block glued straight onto it (`-{#k} [t]: /t`), so the
#: reader has to step over one or it would stop seeing the definition behind it.
_MARKER = r'(?:>+|(?:[-*+]|(?:\d+|[A-Za-z]+)[.)]|\.)(?:\{[^{}\n]*\})?)'

#: A definition line: markers, then the opener, label, colon, a literal space
#: separator and a non-empty payload.
_DEFINITION = re.compile(
    r'^[ \t]*((?:' + _MARKER + r'[ \t]+)*)(\[\^|\*\[|\[)([^\[\]\n]+)(\]:)( )(\S)'
)

#: A fence opener or closer. A definition inside one is payload, not markup.
_FENCE = re.compile(r'^[ \t]*(`{3,}|~{3,}|%{3,})')

#: Opener -> the token VALUE the lexer must emit for the label of that kind.
KINDS = {
    '[': 'Name.Label',
    '[^': 'Name.Label',
    '*[': 'Name.Entity',
}


class Definition:
    """One definition line, and where its opener starts in the source."""

    def __init__(self, offset, opener, label, line):
        self.offset = offset
        self.opener = opener
        self.label = label
        self.line = line

    @property
    def literal(self):
        """The text that would appear in the HTML if the line stayed literal."""
        return self.opener + self.label + ']:'

    def __repr__(self):
        return 'Definition(%r)' % self.line


def candidates(source):
    """Every definition-SHAPED line in ``source``, fences excluded.

    A line qualifies where a definition can open: after a blank line, at the
    start of the document, or behind a block marker - which starts a new block
    wherever it appears.
    """
    found = []
    offset = 0
    fence = None
    blank = True
    for line in source.split('\n'):
        opener = _FENCE.match(line)
        if opener:
            char = opener.group(1)[0]
            fence = char if fence is None else (None if char == fence else fence)
            blank, offset = False, offset + len(line) + 1
            continue
        if fence is None:
            match = _DEFINITION.match(line)
            if match and (blank or match.group(1)):
                found.append(Definition(offset + match.start(2), match.group(2),
                                        match.group(3), line))
        blank, offset = not line.strip(), offset + len(line) + 1
    return found


def _appears_literally(definition, html):
    text = definition.literal
    escaped = (text.replace('&', '&amp;').replace('<', '&lt;')
                   .replace('>', '&gt;').replace('"', '&quot;'))
    return text in html or escaped in html


def definitions(source, html):
    """The candidates the expected HTML shows were consumed as definitions.

    A candidate whose literal text survives into the HTML is not a definition -
    an indented one at document level, an invalid destination, a line that folds
    into an open paragraph. Those are dropped rather than asserted the other way
    round, because the lexer over-colours some of them on purpose: it carries no
    container model, so it cannot see the column that decides them.
    """
    return [d for d in candidates(source) if not _appears_literally(d, html)]


def scope_run(lexer, source, definition):
    """The first three tokens the lexer emits at ``definition``'s opener."""
    return [(str(ttype), value)
            for index, ttype, value in lexer.get_tokens_unprocessed(source)
            if index >= definition.offset][:3]


def is_scoped(lexer, source, definition):
    """Whether the lexer reads ``definition`` as the definition it is.

    The run has to be the opener as ``Punctuation``, the label under the token
    type for its kind, and ``]:`` as ONE ``Punctuation`` token. Asking only for
    a label token somewhere is not enough: an inline footnote REFERENCE also
    emits ``Name.Label`` for its label, and then leaves the colon behind as
    stray text - which is exactly the mis-scoping this gate exists to catch.
    """
    run = scope_run(lexer, source, definition)
    if len(run) < 3:
        return False
    return (run[0] == ('Token.Punctuation', definition.opener)
            and run[1] == ('Token.' + KINDS[definition.opener], definition.label)
            and run[2] == ('Token.Punctuation', ']:'))
