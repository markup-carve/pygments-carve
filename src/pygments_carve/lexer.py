"""Pygments lexer for the Carve markup language.

Carve is a post-Markdown lightweight markup language. Its inline delimiters
deliberately differ from Markdown's, which is why a Markdown lexer produces
actively wrong output on a Carve document rather than merely plain text:

===================  ==================  ==========================
Carve                means               Markdown would read it as
===================  ==================  ==========================
``*bold*``           strong              emphasis
``/italic/``         emphasis            literal slashes
``_under_``          underline           emphasis
``~strike~``         strikethrough       subscript (Djot) / literal
``{=mark=}``         highlight           literal braces
``{^sup^}``          superscript         literal braces
===================  ==================  ==========================

WHY THE BLOCK OPENERS ARE NOT ANCHORED AT COLUMN 0. Carve opens a block at
column 0, or at an enclosing container's content column - nowhere in between.
So ``  # H`` at document level is a paragraph, while the same opener at a list
item's content column is a real heading. Telling those apart needs a container
model that tracks the item's content column. Pygments' state stack could carry
one, but the sibling grammars in carve-grammars (Prism, highlight.js) do not,
and this lexer keeps their trade-off on purpose so the three agree: block
openers match at any indent and knowingly over-colour the rare
indented-at-document-level case, rather than under-colouring the common valid
shape of an indented construct inside a list item. The TextMate grammar in
carve-grammars is the surface that makes the distinction, and the divergence is
documented there under "Where the three grammars deliberately differ".

WHY AN ATTRIBUTE BLOCK IS ONE TOKEN. ``{#id .cls key="v" :lang}`` is emitted
whole as ``Name.Attribute`` rather than split into id, class, key, value and
language parts. Splitting reads better in isolation, but an attribute block can
carry a brace inside a quoted value, a language tag, and a bare key that is not
an attribute at all, and the sibling grammars treat the block as one unit; a
consumer asking "is this text inside an attribute block" must get the same
answer here as it does there.

Spec: https://markup-carve.github.io/carve/
"""

import re

from pygments.lexer import RegexLexer, bygroups, include, using, this
from pygments.token import (
    Comment,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
)

__all__ = ['CarveLexer']

#: A leading margin. A byte order mark at the start of a document is not
#: content, so a block opener behind one is still a block opener.
_MARGIN = r'[ \t\ufeff]*'

#: One attribute block, brace to brace. Quoted values may contain a brace and
#: an escaped quote, so the value alternatives come before the bare-character
#: one; a single nested brace pair is allowed for a braced span written inside.
_ATTRS = (
    r'\{(?=[.:}\'"]|\#[\w-]+[\s}]|[A-Za-z][\w-]*(?:[=\s}]|$))(?:'
    r'"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
    r'|\{[^{}\n]*\}'
    r'|[^{}\n]'
    r')*\}'
)


#: The same block, as a STANDALONE ATTRIBUTE LINE, which may span lines:
#:
#:     {.a
#:     .b}
#:
#: The inline form deliberately cannot, because an unclosed inline `{` would
#: otherwise swallow the rest of the document.
_ATTRS_LINE = _ATTRS.replace(r'[^{}\n]', r'[^{}]').replace(r'\{[^{}]*\}', r'\{[^{}]*\}')


def _label(depth=3):
    """A bracketed label that may itself contain ``depth`` levels of brackets.

    A regex cannot match arbitrarily balanced brackets, and a link label in
    practice nests a level or two (``[t[z]](/u)``). Bounding the nesting keeps
    the common shapes matching instead of stopping at the first inner bracket,
    which is what a naive ``\\[[^\\]]*\\]`` does.
    """
    inner = r'[^\[\]\\\n]|\\.'
    pattern = r'(?:' + inner + r')*'
    for _ in range(depth):
        pattern = r'(?:' + inner + r'|\[' + pattern + r'\])*'
    return r'\[' + pattern + r'\]'


_LABEL = _label()


#: How many lines a fenced body may hold before the fence stops pairing. See
#: the fence rules below: this is the bound that keeps an unpairable opener from
#: costing a scan of the rest of the document.
_FENCE_BODY_LINES = 512


#: A run of block markers a line may carry before its content: bullets, ordered
#: markers and quote markers, in any nesting. A definition written after one is
#: still a definition (`- [t]: /t`), so the definition rules take this prefix
#: rather than losing the line to the marker rules below them.
_MARKER = (
    r'(?:'
    r'>+'
    r'|(?:\d+|[A-Za-z]+)[.)](?:' + _ATTRS + r')?'
    r'|[-*+.](?:' + _ATTRS + r')?'
    r')'
)
_MARKER_RUN = r'(?:' + _MARKER + r'[ \t]+)*'


#: Characters that can begin an inline construct. A run of anything else is
#: ordinary content and is emitted as ONE token - without this every content
#: character becomes its own token, which is both noisy and unusable to a
#: consumer asking whether a phrase carries a scope.
_INLINE_STARTERS = r'\\%!`${[^<>:@#*/_~=.\-(+'


def _plain_run(extra=''):
    """A run of content characters, excluding ``extra`` as well."""
    return r'[^\n' + _INLINE_STARTERS + extra + r']+'



class CarveLexer(RegexLexer):
    """Lexer for the Carve markup language."""

    name = 'Carve'
    url = 'https://markup-carve.github.io/carve/'
    aliases = ['carve', 'crv']
    filenames = ['*.crv', '*.carve']
    mimetypes = ['text/x-carve']
    version_added = '0.1'

    # MULTILINE so that `^` anchors a block opener to the start of ITS line
    # rather than the start of the document - without it every block rule here
    # is dead past the first line. No IGNORECASE: Carve is case-sensitive, and
    # `::: NOTE` is not the `note` admonition.
    flags = re.MULTILINE

    tokens = {
        'root': [
            include('block'),
        ],

        # ------------------------------------------------------------------
        # Block level
        # ------------------------------------------------------------------
        'block': [
            # Front matter, matched WHOLE, only at the very start of the
            # document. `\A` is what keeps a `---yaml` line mid-document from
            # opening one, and the required closer is what keeps a state from
            # having to span the body - a state cannot, because none of its
            # rules matched a bare newline and Pygments resets the stack at
            # every line it cannot match (markup-carve/pygments-carve#32).
            #
            # A closer is REQUIRED here for the same reason the grammar
            # requires one: `frontmatter` carries a `&(...)` guard demanding a
            # closing `---` ahead, and "with no closer the guard fails, so a
            # bare `---` at document start is an ordinary thematic break". The
            # thematic-break rule below is what then takes the line.
            (r'\A(\ufeff?)(---)([a-zA-Z][\w-]*)?([ \t]*\n)'
             r'((?:[^\n]*\n)*?)'
             r'(---)([ \t]*)$',
             bygroups(Text, Punctuation, Keyword.Type, Text, Comment.Special,
                      Punctuation, Text)),

            # A comment fence is matched WHOLE - opener, body and closer in
            # one rule - and the one-line comment follows it, because `%%%`
            # also matches the line form.
            #
            # Whole is what makes an UNTERMINATED opener fall through to the
            # line form, which is the rule: an opener with no matching closer
            # ahead "does NOT open a block. The line degrades to a
            # `comment_line`." A separate state cannot decide that - it has
            # already been entered by the time the input runs out
            # (markup-carve/pygments-carve#30). It is also the only shape that
            # can carry the opener's own WIDTH (`%%%%` closes on `%%%%` alone,
            # which is how a comment nests a shorter fence) and its COLUMN
            # (every line up to the closer carries the opener's indent or is
            # blank; a line further left has left the container, so a closer
            # past it belongs to no open fence) into the search for the closer.
            #
            # The `(?!\2)` on the blank alternative is not decoration. Without
            # it both alternatives match a whitespace-only line whenever the
            # opener is at column 0, and an opener with no closer then
            # backtracks exponentially: 22 such lines took 0.8s, and each
            # further line doubles it.
            (r'^(\ufeff?)([ \t]*)(%%%+)([^\n]*)(\n)'
             r'((?:\2[^\n]*\n|(?!\2)[ \t]*\n)*?)'
             r'(\2)(\3)(?!%)([^\n]*)$',
             bygroups(Text, Text, Comment.Preproc, Comment, Text,
                      Comment, Text, Comment.Preproc, Comment)),
            (r'^' + _MARGIN + r'(%%)([^\n]*)$', bygroups(Comment.Preproc, Comment)),

            # A code or raw fence is matched WHOLE - opener, body and closer in
            # one rule - and the lone-fence line follows the pair, because an
            # opener also matches it.
            #
            # WHOLE IS WHAT MAKES THE BODY OPAQUE. A separate state cannot hold
            # it: none of that state's rules matched a bare newline, and
            # Pygments resets the stack to `root` at every line no rule
            # matches, so the state was abandoned before one body character was
            # read and `# x` inside a Python block was scoped as a heading
            # (markup-carve/pygments-carve#32). Whole is also the only shape
            # that can carry the opener's own CHARACTER and WIDTH (`\3\4*`: the
            # grammar's `char(close) = char(open) and len(close) >= len(open)`)
            # and its COLUMN (`\2`, exactly - "a closing run indented PAST its
            # opener is not a delimiter but code content", which is what lets a
            # fence hold a fence as sample text) into the search for the closer.
            #
            # The body alternative is a single one, `[^\n]*\n`, taken lazily.
            # There is exactly one way to split a span into whole lines, so the
            # closer search never backtracks the way a second, overlapping
            # alternative made it (markup-carve/pygments-carve#34).
            #
            # `_FENCE_BODY_LINES` IS THE BOUND ON THAT SEARCH, and it is load
            # bearing. An opener that never finds its closer scans what is left
            # of the document, so a file of openers that cannot pair - `` ```x ``
            # repeated - costs one scan per line and the whole is QUADRATIC.
            # Measured unbounded, doubling the input from 12000 to 96000
            # characters of it multiplied the time by 3.05, 2.89 and 4.46, up to
            # 35.9s; bounded, by 2.54, 2.25 and 2.15, up to 3.5s - which is 3.6x
            # what this lexer costs on 96000 characters of ordinary prose, and
            # the ratio near 2 that carve-grammars' `scan-superlinear.mjs` calls
            # linear.
            #
            # WHAT THE BOUND TRADES AWAY: a fence whose body is longer than
            # `_FENCE_BODY_LINES` does not pair, and its opener degrades to the
            # lone-fence line below. The longest body in the 1564-document spec
            # corpus is 3 lines and the longest across the spec's own
            # documentation is 76.
            #
            # A raw block's `=FORMAT` routes the payload to that output format
            # verbatim. It is emitted as one token including the `=`, because
            # the format word without its sigil is not the construct.
            (r'^(\ufeff?)([ \t]*)((`|~)\4{2,})([ \t]*)(=[a-zA-Z][\w+.-]*)([^\n]*)(\n)'
             r'((?:[^\n]*\n){0,' + str(_FENCE_BODY_LINES) + r'}?)'
             r'(\2)(\3\4*)([ \t]*)$',
             bygroups(Text, Text, Punctuation, None, Text, Keyword.Type,
                      using(this, state='infostring'), Text,
                      using(this, state='fencebody'), Text, Punctuation, Text)),
            (r'^(\ufeff?)([ \t]*)((`|~)\4{2,})([ \t]*)([a-zA-Z][\w+#.-]*)?([^\n]*)(\n)'
             r'((?:[^\n]*\n){0,' + str(_FENCE_BODY_LINES) + r'}?)'
             r'(\2)(\3\4*)([ \t]*)$',
             bygroups(Text, Text, Punctuation, None, Text, Name.Builtin,
                      using(this, state='infostring'), Text,
                      using(this, state='fencebody'), Text, Punctuation, Text)),

            # A FENCE LINE THIS LEXER DOES NOT PAIR: an opener with no matching
            # closer ahead, and the closer of a pair the rules above did not
            # take. It colours the delimiter run and its info string and claims
            # nothing under it.
            #
            # WHAT THAT TRADES AWAY, written down rather than left to be
            # rediscovered: an unterminated fence at document level really does
            # open a code block that runs to the end of what encloses it, and
            # here it does not. The line-based sibling grammars make the same
            # trade for the same reason - inside a container an opener with no
            # closer opens nothing, and a body that ran to end of input there
            # would swallow the container's own closer and every block after
            # it. Burial is the direction that loses a reader's text
            # (markup-carve/pygments-carve#30).
            (r'^(' + _MARGIN + r')(`{3,}|~{3,})([ \t]*)(=[a-zA-Z][\w+.-]*)',
             bygroups(Text, Punctuation, Text, Keyword.Type)),
            (r'^(' + _MARGIN + r')(`{3,}|~{3,})([ \t]*)([a-zA-Z][\w+#.-]*)?([^\n]*)',
             bygroups(Text, Punctuation, Text, Name.Builtin,
                      using(this, state='infostring'))),

            # Container divs. A reserved kind word (note, tip, figure, ...) names
            # a known container; `:::` followed by `|` is the layout form.
            (r'^(' + _MARGIN + r')(:{3,})([ \t]*)(\|)', bygroups(Text, Punctuation, Text, Operator)),
            (r'^(' + _MARGIN + r')(:{3,})([ \t]*)([a-zA-Z][\w-]*)?([^\n]*)',
             bygroups(Text, Punctuation, Text, Keyword.Namespace,
                      using(this, state='infostring'))),

            # A caption line attaches to the block above or below it.
            (r'^(' + _MARGIN + r')(\^)([ \t]+)', bygroups(Text, Punctuation, Text), 'caption'),

            # Headings. Carve has no setext form, so a `#` run is the only
            # spelling and a trailing `{...}` is NOT an attribute block here.
            (r'^(' + _MARGIN + r')(#{1,6})([ \t]+)',
             bygroups(Text, Punctuation, Text), 'heading'),

            # Thematic break, before the list rules so `---` is not a bullet.
            (r'^' + _MARGIN + r'(?:\*[ \t]*){3,}$', Punctuation),
            (r'^' + _MARGIN + r'(?:-[ \t]*){3,}$', Punctuation),
            (r'^' + _MARGIN + r'(?:_[ \t]*){3,}$', Punctuation),

            # Definition markers: footnote, link reference, abbreviation. The
            # separator after the colon must START WITH A LITERAL SPACE - a
            # tab-first separator makes the line an ordinary paragraph.
            #
            # A leading marker run is part of the shape: a definition is a
            # definition on `- [t]: /t` too, and the corpus resolves the call in
            # those documents. A marker line that instead folds into an open
            # paragraph is over-coloured here, the same way an indented block
            # opener is - telling the two apart needs the container model this
            # lexer deliberately does not carry. The body runs in `defbody`
            # rather than `inline`,
            # because `inline` has no pop rule - `block` includes it, so a pop
            # there would pop the root state - and an unpopped body swallows
            # every block construct in the rest of the document.
            (r'^(' + _MARGIN + r')(' + _MARKER_RUN + r')(\[\^)([^\]\n]+)(\]:)( )',
             bygroups(Text, using(this, state='markerrun'), Punctuation, Name.Label,
                      Punctuation, Text), 'defbody'),
            # No marker run on the abbreviation form: an abbreviation is defined
            # at document level only, so `- *[HTML]: ...` and `> *[HTML]: ...`
            # are paragraph text (corpus 179, 180).
            (r'^(' + _MARGIN + r')(\*\[)([^\]\n]+)(\]:)( )',
             bygroups(Text, Punctuation, Name.Entity, Punctuation, Text), 'defbody'),
            (r'^(' + _MARGIN + r')(' + _MARKER_RUN + r')(\[)([^\]\n]+)(\]:)( )',
             bygroups(Text, using(this, state='markerrun'), Punctuation, Name.Label,
                      Punctuation, Text), 'linkdest'),

            # A definition-list term (`::`) and its definition (`:`).
            (r'^(' + _MARGIN + r')(::)([ \t]+)', bygroups(Text, Punctuation, Text), 'heading'),
            (r'^(' + _MARGIN + r')(:)(?=[ \t])', bygroups(Text, Punctuation)),

            # Blockquote marker. A marker must be followed by a space or end the
            # line; `>foo` is a paragraph.
            (r'^(' + _MARGIN + r')(>+)(?=[ \t]|$)', bygroups(Text, Punctuation), 'quoteline'),

            # Task items before plain bullets, so the state marker is its own
            # token. The state is any single character, not only a space or an
            # x: `[>]` is deferred and `[-]` is dropped.
            (r'^(' + _MARGIN + r')((?:[-*+]|\d+[.)]|[A-Za-z]+[.)])(?:' + _ATTRS + r')?)'
             r'([ \t]+)(\[[^\]\n]\])',
             bygroups(Text, Punctuation, Text, Name.Constant)),

            # Bullets. A run of markers on one line opens nested lists at once
            # (`- - A`), and attributes may be glued straight onto the marker.
            (r'^(' + _MARGIN + r')((?:[-*+][ \t]+)*[-*+](?:' + _ATTRS + r')?)(?=[ \t]|$)',
             bygroups(Text, Punctuation)),

            # Ordered markers: numeric, alphabetic, roman, and the bare `.` that
            # continues the enclosing sequence. Any of them may carry glued
            # attributes.
            (r'^(' + _MARGIN + r')((?:\d+|[A-Za-z]+)[.)](?:' + _ATTRS + r')?)(?=[ \t]|$)',
             bygroups(Text, Number.Integer)),
            (r'^(' + _MARGIN + r')(\.(?:' + _ATTRS + r')?)(?=[ \t]|$)',
             bygroups(Text, Number.Integer)),

            # Tables. The header marker, the alignment run and the separator row
            # are their own tokens; cell content is lexed inline.
            (r'^(' + _MARGIN + r')(\|=[<>^v~]*)', bygroups(Text, Operator), 'tablerow'),
            (r'^(' + _MARGIN + r')(\|)', bygroups(Text, Punctuation), 'tablerow'),

            # A standalone attribute block, which may span lines.
            (r'^(' + _MARGIN + r')(' + _ATTRS_LINE + r')', bygroups(Text, Name.Attribute)),

            include('inline'),
        ],

        # A fence body, reached only through the whole-fence rules above, which
        # hand it the text BETWEEN the delimiters. Nothing in it is Carve - the
        # one exception is the code-callout marker, which the spec puts inside
        # a fence on purpose (`callout marker in fence` in the shared construct
        # inventory).
        #
        # It is not a pushed state and cannot be one: a body spans lines, and a
        # pushed state is abandoned at the first newline no rule matches. Here
        # `[^<]+` matches a newline like any other character, which is also
        # what makes the body reproduce its input.
        'fencebody': [
            (r'<\d+>', Name.Constant),
            (r'[^<]+|<', String.Backtick),
        ],

        # The remainder of a fence or container opener line: a quoted title, a
        # bracketed label, and an attribute block.
        'infostring': [
            (r'"[^"\n]*"', String.Double),
            (r'\[[^\]\n]*\]', Name.Label),
            (_ATTRS, Name.Attribute),
            (r'[^\n]', Text),
        ],

        'heading': [
            (r'$', Text, '#pop'),
            include('inlinecontent'),
            (_plain_run(), Generic.Heading),
            (r'[^\n]', Generic.Heading),
        ],

        'quoteline': [
            (r'$', Text, '#pop'),
            include('inlinecontent'),
            (_plain_run(), Generic.Emph),
            (r'[^\n]', Generic.Emph),
        ],

        'caption': [
            (r'$', Text, '#pop'),
            include('inlinecontent'),
            (_plain_run(), Generic.Subheading),
            (r'[^\n]', Generic.Subheading),
        ],

        'tablerow': [
            (r'$', Text, '#pop'),
            # A header cell marker, optionally carrying an alignment run. The
            # pipe is part of it, so `|=` reads as one construct.
            (r'\|=[<>^v~]*', Operator),
            # A separator row cell, in the native and the GFM spelling.
            (r'(?<=\|)[ \t]*:?-{2,}:?[ \t]*(?=\|)', Punctuation),
            (r'(?<=\|)[ \t]*[<>^v~]{1,2}[ \t]*(?=\|)', Operator),
            (r'\|', Punctuation),
            include('inlinecontent'),
            (_plain_run(r'|'), Text),
            (r'[^\n|]', Text),
        ],

        # The marker run a definition line may carry, tokenized the way the
        # marker rules in `block` tokenize the same markers on their own.
        'markerrun': [
            (r'(?:\d+|[A-Za-z]+)[.)](?:' + _ATTRS + r')?', Number.Integer),
            (r'\.(?:' + _ATTRS + r')?', Number.Integer),
            (r'[-*+](?:' + _ATTRS + r')?', Punctuation),
            (r'>+', Punctuation),
            (r'[ \t]+', Text),
        ],

        # A definition's body: inline content that ends with its line.
        'defbody': [
            (r'$', Text, '#pop'),
            include('inline'),
        ],

        'linkdest': [
            (r'$', Text, '#pop'),
            (r'<[^>\n]*>', Name.Tag),
            (r'"[^"\n]*"', String.Double),
            (r'[^\s\n]+', Name.Tag),
            # Any Unicode whitespace, not only space and tab: a destination can
            # be preceded by U+202F and friends, and a class of two characters
            # leaves the state with nothing to match.
            (r'[^\S\n]+', Text),
        ],

        # ------------------------------------------------------------------
        # Inline level
        # ------------------------------------------------------------------
        'inline': [
            include('inlinecontent'),
            (r'\n', Text),
            (r'.', Text),
        ],

        'inlinecontent': [
            # An escape wins over every delimiter that follows it. A backslash
            # at END OF LINE escapes nothing - it is a hard break, and needs its
            # own rule because the general form requires a following character.
            (r'\\(?=\n|$)', String.Escape),
            (r'\\[!-/:-@\[-`{-~]', String.Escape),

            # A trailing comment runs to end of line from anywhere on it.
            (r'(%%)([^\n]*)$', bygroups(Comment.Preproc, Comment)),

            # Verbatim families first: nothing inside them is markup. The
            # literal form is a `!` PREFIX on a code span, not a trailing
            # attribute, and it has to be tried before plain inline code or the
            # `!` would be read as text and the span as ordinary code.
            (r'(!)(`+)([^\n]*?)(\2)',
             bygroups(Operator, Punctuation, Literal, Punctuation)),
            (r'(\$\$)(`+)([^\n]*?)(\2)',
             bygroups(Operator, Punctuation, String.Other, Punctuation)),
            (r'(\$)(`+)([^\n]*?)(\2)',
             bygroups(Operator, Punctuation, String.Other, Punctuation)),
            (r'(`+)([^\n]*?)(\1)', bygroups(Punctuation, String.Backtick, Punctuation)),

            # CriticMarkup substitution and comment, before the forced family:
            # `{~old~>new~}` also matches the forced-strike shape.
            (r'(\{~)([^\n]*?)(~>)([^\n]*?)(~\})',
             bygroups(Punctuation, Generic.Deleted, Operator, Generic.Inserted, Punctuation)),
            (r'(\{#)([^\n]*?)(#\})', bygroups(Punctuation, Comment, Punctuation)),

            # The braced FORCED emphasis family. Braces make a delimiter apply
            # where the bare form would not - `my{_path_}name` is underline
            # inside a word - so the content is emphasis and the braces are its
            # delimiters, not an attribute block.
            (r'(\{\*)([^\n]+?)(\*\})', bygroups(Punctuation, Generic.Strong, Punctuation)),
            (r'(\{/)([^\n]+?)(/\})', bygroups(Punctuation, Generic.Emph, Punctuation)),
            (r'(\{_)([^\n]+?)(_\})', bygroups(Punctuation, Generic.Underline, Punctuation)),
            (r'(\{~)([^\n]+?)(~\})', bygroups(Punctuation, Generic.Deleted, Punctuation)),

            # Braced inline families. Sup and sub are braced-only in Carve: a
            # bare `^x^` or `,x,` is literal text.
            (r'(\{\^)([^\n]+?)(\^\})', bygroups(Punctuation, Generic.Emph, Punctuation)),
            (r'(\{,)([^\n]+?)(,\})', bygroups(Punctuation, Generic.Emph, Punctuation)),
            (r'(\{=)([^\n]+?)(=\})', bygroups(Punctuation, Generic.Inserted, Punctuation)),
            (r'(\{\+)([^\n]+?)(\+\})', bygroups(Punctuation, Generic.Inserted, Punctuation)),
            (r'(\{-)([^\n]+?)(-\})', bygroups(Punctuation, Generic.Deleted, Punctuation)),
            (r'(\{%)(.*?)(%\})', bygroups(Comment.Preproc, Comment, Comment.Preproc)),

            # An inline footnote carries content; a reference carries a label.
            (r'\^\[', Punctuation, 'inlinefootnote'),
            (r'(\[\^)([^\]\n]+)(\])', bygroups(Punctuation, Name.Label, Punctuation)),

            # A citation before a link: both open with `[`, and `[@key]` or
            # `[+@key]` would otherwise be read as a link label.
            (r'(\[)(\+?@[^\]\n]+)(\])', bygroups(Punctuation, Name.Variable, Punctuation)),

            # Image, then link, then a bare span. All three share the `[...]`
            # shape and differ only in the prefix and what follows.
            (r'(!' + _LABEL + r')(\()([^)\n]*)(\))',
             bygroups(String.Other, Punctuation, Name.Tag, Punctuation)),
            (r'(!' + _LABEL + r')(' + _LABEL + r')', bygroups(String.Other, Name.Label)),
            (r'(' + _LABEL + r')(\()([^)\n]*)(\))',
             bygroups(Name.Entity, Punctuation, Name.Tag, Punctuation)),
            (r'(' + _LABEL + r')(' + _LABEL + r')', bygroups(Name.Entity, Name.Label)),
            (r'(' + _LABEL + r')(?=' + _ATTRS + r')', Name.Entity),

            # A cross-reference to a heading id.
            (r'(</)(#[\w-]+)(>)', bygroups(Punctuation, Name.Namespace, Punctuation)),
            # An autolink.
            (r'(<)([a-zA-Z][\w+.-]*:[^>\s]+|[^>\s@]+@[^>\s]+)(>)',
             bygroups(Punctuation, Name.Tag, Punctuation)),

            # The `:name[...]` extension form.
            (r'(:)([a-zA-Z][\w-]*)(\[)', bygroups(Punctuation, Name.Function, Punctuation),
             'rolebody'),

            # A code callout marker, and a symbol shortcode - whose name may
            # start with a sign, as in `:+1:`.
            (r'<\d+>', Name.Constant),
            (r'(?<![\w:]):[\w+-]+:(?![\w:])', Name.Constant),

            # An attribute block attached to the construct before it.
            (_ATTRS, Name.Attribute),

            # Bare emphasis delimiters. Carve's bare set is / * _ ~ = and each
            # needs a non-space inner boundary so `a / b` stays literal.
            (r'(/\*)([^\n]+?)(\*/)', bygroups(Punctuation, Generic.Strong, Punctuation)),
            (r'(\*/)([^\n]+?)(/\*)', bygroups(Punctuation, Generic.Strong, Punctuation)),
            (r'(\*)(\S(?:[^\n]*?\S)?)(\*)', bygroups(Punctuation, Generic.Strong, Punctuation)),
            (r'(/)(\S(?:[^\n]*?\S)?)(/)', bygroups(Punctuation, Generic.Emph, Punctuation)),
            (r'(_)(\S(?:[^\n]*?\S)?)(_)', bygroups(Punctuation, Generic.Underline, Punctuation)),
            (r'(~)(\S(?:[^\n]*?\S)?)(~)', bygroups(Punctuation, Generic.Deleted, Punctuation)),
            # A bare `=` carrying a comparison or an arrow tail on its left is
            # not a highlight delimiter: PART 9's inline precedence excepts "a
            # delimiter that begins a multi-char smart-typography pattern ...
            # the pattern is consumed first". `< > !` is every character the
            # language puts in front of a `=` to make one.
            #
            # BOTH ends are guarded, one more than Prism, whose closer is
            # unguarded. The engine guards both: `x =y z<= w` renders
            # `x =y z≤ w`, no mark at all. Nothing is guarded on the RIGHT,
            # also from the engine - `=>` is not an arrow any more, so
            # `a =foo=> b` marks `foo` and `a =>foo= b` marks `>foo`.
            (r'(?<![<>!])(=)(\S(?:[^\n]*?\S)?)(?<![<>!])(=)',
             bygroups(Punctuation, Generic.Inserted, Punctuation)),

            # A mention and a tag, each one token: the sigil is part of the name
            # rather than punctuation beside it.
            (r'(?<![\w/])@[\w][\w.-]*', Name.Variable.Magic),
            (r'(?<![\w&])\#[\w][\w-]*', Name.Variable.Instance),

            # Smart typography: the spec grammar's `arrow`, `comparison` and
            # `typographic_symbol` plus the dash and ellipsis runs. Nineteen
            # alternatives, the set Prism and highlight.js carry.
            #
            # Longest first, or a shorter alternative that prefixes a longer one
            # wins: `<->` before `<-`, `<==` before `<=`. `<==>` is deliberately
            # NOT one of them - it is `<==` and then a literal `>`, rendering
            # `⇐>`, and matching it whole was an over-colour.
            (r'<-->|<--|-->|<=>|<==|==>|<->|<-|->|!=|<=|>=', Operator),
            (r'(?<!-)---(?!-)|(?<!-)--(?!-)', Punctuation),
            (r'\.\.\.', Punctuation),
            # `(c) (r) (tm) +-` render fixed characters, the same kind of thing
            # the `:name:` shortcode above produces, so they share its type.
            # Lowercase only: `(C)` and `(TM)` stay literal.
            (r'\(c\)|\(r\)|\(tm\)|\+-', Name.Constant),
        ],

        'inlinefootnote': [
            (r'\]', Punctuation, '#pop'),
            include('inlinecontent'),
            (_plain_run(r'\]'), Generic.Emph),
            (r'[^\]\n]', Generic.Emph),
            (r'\n', Text),
        ],

        'rolebody': [
            (r'\]', Punctuation, '#pop'),
            include('inlinecontent'),
            (_plain_run(r'\]'), Name.Function),
            (r'[^\]\n]', Name.Function),
            (r'\n', Text),
        ],
    }
