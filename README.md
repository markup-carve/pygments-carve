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
- **`test_block_rules.py`** does the same for the 28 rules of the block state,
  and adds the two things that state needs. A CORPUS GATE, which needs nobody to
  write a sample: deleting a block rule must change the lexer's reading of at
  least one corpus document, and 27 of the 28 do - the exception is the lone raw
  fence line, recorded by name so it is known rather than assumed. And one pin
  per GUARD CLAUSE, each proved by removing that clause alone: deleting a rule
  tests whether the rule exists and can never test a refusal, since a rule that
  is gone refuses everything its guard refused. Before it, the `-` thematic
  break and the definition-list `:` marker could both be deleted with the suite
  green, though deleting the marker changes how 96 corpus documents are read
  (markup-carve/pygments-carve#41).
- **`test_typography.py`** reads the `arrow`, `comparison` and
  `typographic_symbol` productions out of `spec/resources/grammar.ebnf` in
  place, requires every alternative to be scoped as ONE token holding exactly
  that run, and then removes each `|` branch from the lexer in turn and requires
  an assertion to break. A per-rule pin cannot see an alternation shrink - the
  arrow rule was pinned by `a -> b` while `<->` scoped as `<-` plus a stray `>`
  (markup-carve/pygments-carve#28) - and reading the set from the spec means an
  alternative the language gains is measured the day the pin brings it in.
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
- **`test_lexer_states.py`** asserts, of every state a rule PUSHES, that some
  rule in it matches a bare newline - by consuming it, or by popping at `$`
  before it. A state in neither shape is abandoned at the end of every line,
  which is how `codeblock` came to never run at all and `frontmatter` came to
  escape at its first blank line (markup-carve/pygments-carve#32). The gate is
  mechanical: it names no construct and holds for a state added tomorrow.
- **`test_fence_body.py`** pairs the fences in every corpus document by the
  grammar's own closer rule and requires every character between a pair to carry
  a verbatim scope. It reports zero across the corpus; against the rule shape
  that shipped markup-carve/pygments-carve#32 it reports 71 documents, and the
  suite pins that number too. It also holds the cost of requiring a closer: an
  opener that never finds one scans ahead, so the growth ratio on a file of
  unpairable openers is asserted to stay under the value carve-grammars'
  `scan-superlinear.mjs` calls a finding.
- **`test_round_trip.py`** asserts, for every corpus document, that the
  concatenated token values are the source. A character in no token reaches no
  consumer - an HTML formatter reassembles a document from these - and no scope
  assertion can see it, because a character with no token has no scope to be
  wrong about. It reported 31 documents against the lexer as it stood before
  markup-carve/pygments-carve#33, 28 of them from a `_MARGIN` matched outside
  its capture group under `bygroups` and 3 from the two Pygments defaults; the
  suite pins that split. It also deletes each rule of the block state in turn
  and requires the property to survive every deletion, which is what says the
  defect was one rule rather than a habit spread through the state.
- **`test_bare_emphasis.py`** asks the corpus the one question a bare emphasis
  delimiter answers: a delimiter that opens a span is consumed, so a run the
  lexer scopes whose delimiters SURVIVE into the expected HTML is a span the
  corpus did not open. It reports zero across the corpus; against the rules as
  they stood before markup-carve/pygments-carve#36 it reports 16 named
  documents, so the zero is a measurement rather than a silence. The per-guard
  pins are proved against those unguarded rules rather than against a deletion,
  because deleting a rule removes an over-colour instead of producing one.
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
