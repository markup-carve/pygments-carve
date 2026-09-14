# pygments-carve

[![CI](https://github.com/markup-carve/pygments-carve/actions/workflows/ci.yml/badge.svg)](https://github.com/markup-carve/pygments-carve/actions/workflows/ci.yml)

[Carve](https://markup-carve.github.io/carve/) lexer for
[Pygments](https://pygments.org/).

Installing it is enough. Pygments discovers the lexer through the
`pygments.lexers` entry point, so `carve` and `crv` become working fence words
everywhere Pygments is the highlighter - MkDocs, Sphinx, zensical, `pygmentize`,
and anything built on them:

```sh
pip install pygments-carve
```

````markdown
```carve
# Heading /italic/ *bold*
```
````

## Why Carve needs its own lexer

Carve is a post-Markdown markup language whose inline delimiters deliberately
differ from Markdown's. A Markdown lexer does not merely under-highlight a Carve
document, it highlights it *wrongly*:

| Carve         | means         | Markdown reads it as    |
|---------------|---------------|-------------------------|
| `*bold*`      | strong        | emphasis                |
| `/italic/`    | emphasis      | literal slashes         |
| `_under_`     | underline     | emphasis                |
| `~strike~`    | strikethrough | subscript, or literal   |
| `{=mark=}`    | highlight     | literal braces          |
| `{^sup^}`     | superscript   | literal braces          |

## What it covers

Every construct in Carve's shared grammar inventory: front matter, headings,
lists (numeric, alphabetic, roman and bare-dot markers, task items in all their
states, markers carrying glued attributes), tables with header and alignment
markers, blockquotes, fenced and raw blocks, container divs and figure groups,
captions, definition lists, comments in both the line and fence spellings, and
the definition markers for footnotes, link references and abbreviations.

Inline: the emphasis families in Carve's spelling plus their braced forced
forms, code and inline literals, math, links, images, spans, attributes,
footnotes and inline footnotes, citations, cross-references, autolinks,
extensions (`:name[...]`), symbols, code callouts, mentions, tags, escapes,
hard breaks, and smart typography - all nineteen alternatives the spec grammar
names under `arrow`, `comparison` and `typographic_symbol` plus the dash and
ellipsis runs, which is the set Prism and highlight.js carry. Two productions of
`smart_typography` are not scoped and are named as such in
`tests/test_typography.py`: `smart_quote`, which is per-character contextual
substitution rather than a run, and the braced en dash `{--}`.

## Deliberate limits

**Block openers are not anchored at column 0.** Carve opens a block at column 0
or at an enclosing container's content column - nowhere in between - so `  # H`
at document level is a paragraph while the same opener inside a list item is a
real heading. Distinguishing them needs a container model. This lexer keeps the
same trade-off the Prism and highlight.js grammars make (match at any indent,
over-colour the rare invalid case) so the three surfaces agree; the TextMate
grammar in carve-grammars is the surface that makes the distinction.

**A fence is matched whole, and an unpaired opener claims nothing.** A code
fence, a raw block, front matter and a comment fence are each matched by ONE
rule spanning opener, body and closer, because a Pygments state cannot hold a
body: the stack resets at every newline no rule matches, so a state pushed on
the opener's newline is abandoned before one body character is read
(markup-carve/pygments-carve#32). Whole is also what carries the opener's width,
character and column into the search for its closer. The trade is at the other
end: an opener with no closer ahead really does open a code block that runs to
the end of what encloses it, and here it colours its own line and claims nothing
under it - the reading the line-based sibling grammars take, because a body that
ran to end of input inside a container would swallow the container's own closer
and every block after it. An opener whose info string is outside the three
shapes the grammar admits does not pair either, because such a line opens no
block at all and the corpus renders it as a paragraph. Nor does a body longer
than 512 lines; that bound is what keeps a file of openers that can never pair
from costing a scan of the document per line.

**Pygments' `stripnl` and `ensurenl` are off.** They strip a document's leading
and trailing newlines and append one that is not there, which is reasonable for
a programming language and not for Carve: a fence keeps the blank line at the end
of its content, and the spec forbids encoding a blank payload line and no payload
line identically. A caller who wants the Pygments behavior can still pass either
option (markup-carve/pygments-carve#33).

**A `=` run is closed by the nearest guarded delimiter, not by a delimiter
stack.** The word-boundary guards the grammar states for the bare set are
carried on both ends, but the run resolution behind them is not: this lexer has
no delimiter-stack model, so `a =f=>g= b` marks `f=>g` where the engine marks
`f`. Pinned in `test_bare_emphasis.py` so it cannot drift into something else
(markup-carve/pygments-carve#36).

**An attribute block is one token.** `{#id .cls key="v"}` is emitted whole as
`Name.Attribute` rather than split into parts, matching how the sibling grammars
treat it.

## Related

The grammar is maintained across surfaces in
[carve-grammars](https://github.com/markup-carve/carve-grammars) (Prism,
highlight.js, TextMate, Tiptap), which is where the construct inventory lives.
[highlightjs-carve](https://github.com/markup-carve/highlightjs-carve) is the
highlight.js side. A chroma lexer for Hugo can be generated from this one with
chroma's own `pygments2chroma_xml.py`.

## Development

Contributor setup, testing, and maintenance notes are in the [development guide](docs/development.md).
