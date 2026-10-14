"""Find the fenced bodies in a Carve source, the way the grammar pairs them.

A code or raw fence is the one construct whose content is NOT Carve, so "which
characters are inside one" is a question that can be answered from the source
alone - no HTML needed, and no construct list to keep up to date. That is what
lets ``test_fence_body.py`` ask the lexer about every fence the spec corpus
holds without anybody writing the fences down.

The pairing rule is the grammar's, not an approximation of it
(``code_fence_close``, PART 9 §2, plus COLUMN-EXACT DELIMITERS): the closer uses
the SAME fence character as its opener, is AT LEAST as long, carries nothing but
whitespace after the run, and sits at the opener's OWN column. A run indented
past the opener is body - which is what lets a fence hold a fence as sample
text, the shape most documents describing Carve are made of.

A comment fence and front matter are skipped, not paired: their bodies are
comment and metadata, and a ``` inside one is neither an opener nor a closer.
"""

import html as htmlmod
import re

#: A fence line: indent, a homogeneous run of one fence character, and its tail.
_FENCE = re.compile(r'^([ \t]*)((`)\3{2,}|(~)\4{2,})([^\n]*)$')

#: A CONFORMING opener tail: the raw block's `=FORMAT`, or one of the three
#: shapes `code_fence_info` admits. Anything else is an INVALID-FENCE FALLBACK -
#: ```` ```js title="x" ```` opens no block, and the corpus renders it as a
#: paragraph - so a reader that paired on one would be asking the lexer to bury
#: a paragraph.
_INFO = re.compile(
    r'^ ?(?:=[a-zA-Z][\w+.-]*'
    r'|[A-Za-z0-9_+#./-]+(?: +"[^"\n]*")?(?: +\[[^\]\n]*\])?'
    r'|"[^"\n]*"(?: +\[[^\]\n]*\])?'
    r'|\[[^\]\n]*\])?[ \t]*$'
)

#: A comment fence, whose body this reader steps over rather than pairing.
_COMMENT = re.compile(r'^([ \t]*)(%{3,})([^\n]*)$')


class Body:
    """One fenced body: the source span between the delimiter lines.

    ``skip`` holds the spans inside it that belong to an enclosing container -
    a quote's marker on each line - and ``indent`` the width a container's
    content column takes off each line. ``raw`` is the raw block's format.
    """

    def __init__(self, start, end, opener, line, skip=(), indent='', raw=None):
        self.start = start
        self.end = end
        self.opener = opener
        self.line = line
        self.skip = tuple(skip)
        self.indent = indent
        self.raw = raw

    @property
    def lines(self):
        return self.line

    def __repr__(self):
        return 'Body(line %d, %r)' % (self.line, self.opener)


def _closes(opener, indent, run, tail, open_indent):
    return (indent == open_indent
            and run[0] == opener[0]
            and len(run) >= len(opener)
            and not tail.strip())


def bodies(source):
    """Every fenced body in ``source``, as spans into it.

    Front matter is stepped over first, then each line is read in order. An
    opener with no closer ahead pairs with nothing and yields no body, which is
    the same answer the lexer gives.
    """
    lines = source.split('\n')
    offsets, at = [], 0
    for line in lines:
        offsets.append(at)
        at += len(line) + 1

    index = 0
    # Front matter, only at the very start, and only when it closes.
    if lines and re.match(r'^﻿?---(?:[a-zA-Z][\w-]*)?[ \t]*$', lines[0]):
        for j in range(1, len(lines)):
            if re.match(r'^---[ \t]*$', lines[j]):
                index = j + 1
                break

    found = []
    while index < len(lines):
        line = lines[index]
        comment = _COMMENT.match(line)
        if comment:
            for j in range(index + 1, len(lines)):
                closer = _COMMENT.match(lines[j])
                if (closer and closer.group(1) == comment.group(1)
                        and len(closer.group(2)) == len(comment.group(2))):
                    index = j + 1
                    break
            else:
                index += 1
            continue
        match = _FENCE.match(line)
        if not match:
            index += 1
            continue
        if not _INFO.match(match.group(5)):
            index += 1
            continue
        indent, run = match.group(1), match.group(2)
        raw = re.match(r' ?=([a-zA-Z][\w+.-]*)', match.group(5))
        for j in range(index + 1, len(lines)):
            other = _FENCE.match(lines[j])
            if other and _closes(run, other.group(1), other.group(2), other.group(5), indent):
                found.append(Body(offsets[index + 1], offsets[j], run, index + 1,
                                  indent=indent, raw=raw and raw.group(1)))
                index = j + 1
                break
        else:
            index += 1
    return found


#: A fence opened inside a container on the same line: behind a quote's
#: markers, or on a list item's or a description's marker line.
_CONTAINER_FENCE = re.compile(
    r'^(?P<quote>[ \t]*>+[ \t]?)?(?P<marker>[ \t]*(?:[-*]|\d+[.)]|[a-zA-Z][.)]|\.|:) +)?'
    r'(?P<run>(`)\4{2,}|(~)\5{2,})(?P<tail>[^\n]*)$')


def container_bodies(source):
    """Every fenced body opened behind `>` or on a marker line, as spans.

    The top-level reader steps past these lines, because the fence is not at
    the start of its line. The pairing is the same rule, read inside the
    container: behind a quote every line carries the opener's markers and the
    closer sits right after them; on a marker line the closer sits at the
    item's content column and no line in between reaches left of it.
    """
    lines = source.split('\n')
    offsets, at = [], 0
    for line in lines:
        offsets.append(at)
        at += len(line) + 1
    found = []
    index = 0
    while index < len(lines):
        match = _CONTAINER_FENCE.match(lines[index])
        if (not match or not (match.group('quote') or match.group('marker'))
                or not _INFO.match(match.group('tail'))):
            index += 1
            continue
        run = match.group('run')
        raw = re.match(r' ?=([a-zA-Z][\w+.-]*)', match.group('tail'))
        quote = match.group('quote') or ''
        depth = quote.count('>')
        column = len(quote) + len(match.group('marker') or '')
        skip, closed = [], None
        for j in range(index + 1, min(len(lines), index + 513)):
            line = lines[j]
            if quote:
                marker = re.match(r'[ \t]*>{%d}[ \t]?' % depth, line)
                if not marker:
                    break
                if line.startswith(quote) and re.match(
                        re.escape(run[0]) + '{%d,}[ \t]*$' % len(run), line[len(quote):]):
                    closed = j
                    break
                skip.append((offsets[j], offsets[j] + marker.end()))
            elif line.strip():
                indent = len(line) - len(line.lstrip(' \t'))
                if indent < column:
                    break
                if indent == column and re.match(
                        re.escape(run[0]) + '{%d,}[ \t]*$' % len(run), line[indent:]):
                    closed = j
                    break
        if closed is None:
            index += 1
            continue
        found.append(Body(offsets[index + 1], offsets[closed], run, index + 1, skip=skip,
                          indent='' if quote else ' ' * column, raw=raw and raw.group(1)))
        index = closed + 1
    return found


_PRE = re.compile(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', re.S)


def confirmed(source, html, body):
    """Whether the engine's HTML renders ``body`` as a code block's content.

    None where the HTML cannot say: a raw block in a format other than HTML is
    dropped from it. A raw HTML block's payload is in the HTML as it stands.
    """
    lines = source[body.start:body.end].splitlines(True)
    if body.skip:
        text = ''.join(re.sub(r'^[ \t]*>+[ \t]?', '', line) for line in lines)
    else:
        text = ''.join(line[len(body.indent):] if line.startswith(body.indent)
                       else line.lstrip(' \t') for line in lines)
    if body.raw:
        if body.raw != 'html':
            return None
        return text.rstrip('\n') in html
    return text in [htmlmod.unescape(code) for code in _PRE.findall(html)]


def scopes_in(lexer, source, body):
    """``{token type: text}`` for every token overlapping ``body``'s span.

    A span in ``body.skip`` is the container's, not the body's, and is left out.
    """
    seen = {}
    for start, ttype, value in lexer.get_tokens_unprocessed(source):
        if start >= body.end or start + len(value) <= body.start:
            continue
        if any(lo <= start and start + len(value) <= hi for lo, hi in body.skip):
            continue
        overlap = value[max(0, body.start - start):len(value) - max(0, start + len(value) - body.end)]
        if overlap.strip():
            seen.setdefault(ttype, overlap)
    return seen
