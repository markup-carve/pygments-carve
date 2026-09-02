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
hard breaks, and the dash, arrow and ellipsis runs of smart typography - though
not yet all of that family: `<=`, `>=`, `!=` and `+-` are not scoped, and `<->`
only partly (markup-carve/pygments-carve#28).

## Deliberate limits

**Block openers are not anchored at column 0.** Carve opens a block at column 0
or at an enclosing container's content column - nowhere in between - so `  # H`
at document level is a paragraph while the same opener inside a list item is a
real heading. Distinguishing them needs a container model. This lexer keeps the
same trade-off the Prism and highlight.js grammars make (match at any indent,
over-colour the rare invalid case) so the three surfaces agree; the TextMate
grammar in carve-grammars is the surface that makes the distinction.

**A code fence's body is not scoped at all.** The `codeblock` state has no rule
that matches a bare newline, so Pygments resets the state stack at the end of
the opener line: `# x` inside a ```` ```python ```` block is scoped as a
heading, and no corpus document produces a fence-body token
(markup-carve/pygments-carve#32). The comment fence is not in that shape - it is
matched whole, opener to closer, in one rule, which is what lets it require the
exact-width closer the spec asks for at the opener's own column and degrade to
the line form when there is none.

**An attribute block is one token.** `{#id .cls key="v"}` is emitted whole as
`Name.Attribute` rather than split into parts, matching how the sibling grammars
treat it.

## Tests

```sh
pip install -e '.[test]'
git submodule update --init    # the spec corpus, and carve-grammars
pytest -q
```

The suites, and the split matters:

- **`test_constructs.py`** runs the shared construct inventory - the same list
  the Prism, highlight.js and TextMate sweeps run - and asserts each construct's
  payload lands in a token that is not plain text. That is a cross-surface
  parity check: a construct covered on Prism or TextMate is not quietly missing
  here. It is deliberately *not* what holds the rules down - any non-text token
  satisfies it, so it cannot tell a construct's own rule from a neighbour that
  catches the same payload. The inventory is read in place from
  `carve-grammars/tests/lib/constructs.js`, so there is no local copy to fall
  behind it; `tests/inventory.py` is the reader and `test_inventory.py` is what
  stops it silently returning a short list.
- **`test_inline_rules.py`** records, for every one of the 46 rules in the
  inline state, a sample and the whole run of tokens the lexer colours in it -
  the delimiters included, because a same-type fallback gets those wrong and the
  payload's type right. Then it deletes each rule from the lexer source,
  rebuilds, and requires that rule's pin to stop holding, so the pins are proved
  sharp from inside the suite rather than asserted. Before it, sixteen of those
  rules could be deleted outright with the suite green
  (markup-carve/pygments-carve#25).
- **`test_comment_fence.py`** pins which SOURCE LINES the lexer treats as
  commented out, and asks the corpus the one question a comment answers: a
  comment renders nothing, so no word the expected HTML puts in front of a
  reader may sit on a line the lexer scopes entirely as a comment. That reads a
  property out of the source/HTML pair without anyone naming a construct, the
  way the definition gate does. It reports zero across the corpus; against the
  rule shape that shipped markup-carve/pygments-carve#30 it reports eight
  documents, and the suite pins that number too, so the zero is known to be a
  measurement rather than a silence. The pins are proved sharp against two
  mutants, because deleting a rule can only test what a rule does and four of
  these pins say the fence must REFUSE to open.
- **`test_corpus.py`** lexes every document of the spec corpus and asserts that
  the definitions the corpus pins are scoped as definitions. A corpus case is a
  source next to the HTML it renders to, so the pair says which lines are
  definitions without a parser here - a definition is consumed, so its
  `[label]:` text does not survive into the HTML. This is what a construct list
  cannot do: it measures a construct the day the spec pin brings it in, with
  nobody having to write it down first. It used to assert only that no document
  produces a `Token.Error`, which nothing can - see
  markup-carve/pygments-carve#21.
- **`test_definitions.py`** pins the definition shapes by hand, including the
  controls: a line that is NOT a definition must stay plain content.
- **`test_registration.py`** resolves the lexer the way a consumer does, through
  the entry point, so a packaging mistake fails rather than passing on a direct
  import.
- **`test_submodules.py`** is the one file outside every `skipif`. The corpus
  and construct suites are parametrized over a directory, so an unchecked-out
  submodule collects zero cases and reports green; locally that is a skip, and
  in CI this turns it into a failure.

## Related

The grammar is maintained across surfaces in
[carve-grammars](https://github.com/markup-carve/carve-grammars) (Prism,
highlight.js, TextMate, Tiptap), which is where the construct inventory lives.
[highlightjs-carve](https://github.com/markup-carve/highlightjs-carve) is the
highlight.js side. A chroma lexer for Hugo can be generated from this one with
chroma's own `pygments2chroma_xml.py`.

## License

MIT, see [LICENSE](LICENSE).
