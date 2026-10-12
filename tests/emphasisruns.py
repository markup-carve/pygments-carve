"""Read a corpus case for the one thing a bare emphasis run cannot be.

A bare delimiter that opens a span is CONSUMED - the span becomes a tag and the
delimiters are gone. So if the run the lexer scoped appears in the expected HTML
with its delimiters still on it, the corpus is saying no span was opened there.
That is a property the source/HTML pair states without anyone naming a
construct, the same way ``corpusdefs`` reads definitions and ``commentlines``
reads comments out of it.

IT IS ONE-SIDED, deliberately, and in the safe direction. A run whose CONTENT
holds markup does not survive into the HTML verbatim even when the delimiters
stayed literal, so this reader says nothing about it. Under-reporting costs a
measurement; a false report would cost a wrong failure.

The HTML is read per document, so the same text written a second time with its
delimiters backslash-escaped puts them in the HTML without saying anything
about the run. Each escaped copy accounts for one occurrence, and a run is
reported only when the HTML holds more than those. An unescaped copy accounts
for nothing: it is as likely to be the thing the lexer should have read.
"""

import html as htmlmod
import re

from pygments.token import Generic, Punctuation

#: Delimiter -> the token type the lexer gives that run's content.
BARE = {
    '*': Generic.Strong,
    '/': Generic.Emph,
    '_': Generic.Underline,
    '~': Generic.Deleted,
    '=': Generic.Inserted,
}


def runs(lexer, source):
    """Every bare emphasis run the lexer scopes, as ``(offset, source text)``.

    A run is the shape the five bare rules emit and nothing else: a
    single-character ``Punctuation`` delimiter, the content under the token type
    that delimiter carries, and the same delimiter again. The braced forced
    family emits a TWO-character delimiter, so it cannot be mistaken for one.
    """
    tokens = list(lexer.get_tokens_unprocessed(source))
    found = []
    for i in range(1, len(tokens) - 1):
        start, ttype, value = tokens[i]
        opener, closer = tokens[i - 1], tokens[i + 1]
        if opener[1] is not Punctuation or closer[1] is not Punctuation:
            continue
        delimiter = opener[2]
        if len(delimiter) != 1 or closer[2] != delimiter:
            continue
        if BARE.get(delimiter) is not ttype:
            continue
        found.append((opener[0], delimiter + value + delimiter))
    return found


def _count(text, html):
    escaped = (text.replace('&', '&amp;').replace('<', '&lt;')
                   .replace('>', '&gt;').replace('"', '&quot;'))
    return max(html.count(text), html.count(escaped),
               htmlmod.unescape(html).count(text))


def _escaped_copies(text, source, found):
    """How often ``text`` is spelled with backslash escapes outside every run."""
    out, at = [], 0
    for offset, run in found:
        if offset < at:
            continue
        out.append(source[at:offset])
        at = offset + len(run)
    out.append(source[at:])
    # NUL keeps the text on either side of a removed run from joining up.
    rest = '\0'.join(out)
    resolved = re.sub(r'\\([!-/:-@\[-`{-~])', r'\1', rest)
    return resolved.count(text) - rest.count(text)


def unopened(lexer, source, html):
    """Runs the lexer scopes whose delimiters survive into the expected HTML."""
    found = runs(lexer, source)
    return [text for _, text in found
            if _count(text, html) > _escaped_copies(text, source, found)]
