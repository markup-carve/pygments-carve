# Changelog

All notable changes to pygments-carve are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.3] - 2026-10-24

CSV and TSV highlighting is available by language name, and Carve scopes follow the current grammar release.

### Improvements

- Hosts can select the CSV and TSV lexers by name (#113).
- Carve highlighting follows the published carve-grammars 0.1.20 scopes, including wrapped attributes in definitions and quotes (#111).

**Full Changelog**: https://github.com/markup-carve/pygments-carve/compare/0.1.2...0.1.3

## [0.1.2] - 2026-10-23

### Added

- `csv` and `tsv` fence bodies are highlighted: each field gets its own token
  type and the separator is scoped as an operator, colored apart from the
  fields in the default styles. (markup-carve/pygments-carve#95,
  markup-carve/pygments-carve#96, markup-carve/pygments-carve#97,
  markup-carve/pygments-carve#98)

### Changed

- Continuation markers are tokenized as `Operator`.
  (markup-carve/pygments-carve#100)

### Fixed

- A lone `+` line is scoped as a continuation marker only where the engine
  reads one: at an open container's marker column with a non-list block below
  it (markup-carve/carve#3445), and behind quote prefixes only with a space
  after each `>`; `>+`, `>>+` and `>> +` stay text.
  (markup-carve/pygments-carve#92, markup-carve/pygments-carve#99,
  markup-carve/pygments-carve#103)
- `- > +`, a `+` that is the first block of a quote opened on a list item
  line, is scoped as a marker when the next line starts a block it attaches
  (markup-carve/carve#3421). (markup-carve/pygments-carve#106)
- An attribute block after plain brackets stays text, as the engine renders
  it. (markup-carve/pygments-carve#101)
- A `:` left of the `::` column of the definition list it would continue,
  such as a description below a list nested in an item, is paragraph text
  instead of a separator (markup-carve/carve#3458).
  (markup-carve/pygments-carve#107, markup-carve/pygments-carve#108)

## [0.1.1] - 2026-10-14

### Added

- A fence naming a language Pygments knows is highlighted in that language,
  and a raw block's `=FORMAT` names its language the same way. Code callout
  markers and a quote's line markers keep their own scope. The
  `handlecodeblocks` option turns it off, as on Pygments' Markdown lexer.
  (markup-carve/pygments-carve#88)

### Fixed

- Lexing stays linear on long lines. An include directive with no closer
  (`{{ chapter-one.crv#introduction` took 166s), an attribute block holding an
  unclosed run of quotes, and the CriticMarkup substitution were exponential or
  cubic; every bare and braced emphasis opener, code span, link destination,
  footnote reference, citation and autolink with no closer was quadratic.
  (markup-carve/pygments-carve#86)
- A bare emphasis run closes at its first guarded closer. A one-character
  content was tried last, so `(/x/) and a./b/` read as one span and
  `a =f=>g= b` marked `f=>g`; both now read as the engine does.
  (markup-carve/pygments-carve#86)
- An attribute block holding a bare quote is no longer scoped: the engine
  renders `[x]{key=a"b}` as text, and a quoted value on a standalone attribute
  line no longer runs onto the next line. (markup-carve/pygments-carve#86)
- An escaped delimiter, or one inside a code span, a link, an image, a
  reference or an autolink, no longer closes a bare or braced span:
  `a *b\* c` stays text and `{=a \=} b=}` is one mark.
  (markup-carve/pygments-carve#80, markup-carve/pygments-carve#87)
- A code span closes only on a run of its own width, may cross a line of its
  paragraph, and with no partner runs to the end of its paragraph; in a table
  row it stops at the closing pipe. (markup-carve/pygments-carve#87)
- An unclosed `^[` or `:name[` is text. As a pushed state it used to color
  the rest of the document. (markup-carve/pygments-carve#87)
- A list marker, ordered marker or caption on a paragraph's later line is
  paragraph text, and a table row needs its closing pipe.
  (markup-carve/pygments-carve#87)
- A block on a container's marker line is read as a block: `> - item`,
  `> # H`, `- > q`, `- # H` and `: - item` under a term. A fence on an item's or
  a description's marker line, or behind a quote marker, pairs with its closer.
  (markup-carve/pygments-carve#87)
- The content of an emphasis span and an inline link's text are lexed as
  inline content, so `{=a *b* c=}` marks a strong inside the highlight. A
  braced span's own delimiter is literal inside it, as `{*a *b* c*}` renders.
  (markup-carve/pygments-carve#88)
- A bare or braced span and a `{%...%}` template span may cross a line of
  their paragraph. (markup-carve/pygments-carve#88)
- `::: >` and `::: \` scope their sigil like `::: |`, and `<1>` outside a
  fence is text, as the engine renders it. (markup-carve/pygments-carve#88)
- Paragraph text is emitted as runs rather than one token per character.
  (markup-carve/pygments-carve#88)
- A braced span nests, its own kind too: `{*a {*b*} c*}` is a strong inside a
  strong, and an outer opener left without a closer stays literal. A bare
  closer inside a braced span no longer closes a bare span: `*a {=b*=} c*` is
  one strong holding a mark. (markup-carve/pygments-carve#89)
- A lone `+` or a `+ a |` line under a definition term is the term's text,
  as the engine renders it, not a continuation marker or row.
  (markup-carve/pygments-carve#90)
- A lone `+` is a continuation marker only under an open list item, quote or
  description, and a `+ a |` line is a row only directly under a table row.
  At the start of a document, under a table or heading, or after a paragraph
  both are text, as the engine renders them. (markup-carve/pygments-carve#92)

## [0.1.0] - 2026-10-08

### Added

- The reserved include directive `{{ path #section @key:value }}` (PART 9
  section 19, markup-carve/carve#291) is lexed BY PART: the path as
  `Name.Namespace`, the selector as `Name.Label`, and each option as
  `Name.Attribute` plus its value. It used to shred into the constructs its own
  selector is spelled with, so `#intro` in a path came out colored as a
  hashtag.
- A Pygments lexer for Carve, registered through the `pygments.lexers` entry
  point so that installing the package is enough for `carve` and `crv` to work
  as fence words in MkDocs, Sphinx, zensical and every other Pygments consumer.
- Coverage of every construct in carve-grammars' shared inventory, asserted per
  construct rather than assumed: each construct's payload must land in a token
  that is not plain text. The inventory is read in place from the
  `carve-grammars` submodule, so this repo carries no copy of it to fall behind.
- A pin on every rule of the inline state - a sample and the whole run of tokens
  the lexer colours in it - proved sharp by deleting each rule and requiring its
  pin to stop holding. Sixteen of the forty-six rules had been deletable with
  the suite green, because "not plain text" cannot tell a rule from a neighbour
  that catches the same payload. (markup-carve/pygments-carve#25)
- The same for the 28 rules of the block state, plus a pin on each of its guard
  clauses - removed one at a time, because deleting a rule tests that the rule
  exists and can never test a refusal - and a corpus gate requiring a deleted
  block rule to change how at least one corpus document is read. Two rules had
  been deletable with the suite green.
  (markup-carve/pygments-carve#41)
- A corpus suite that lexes every document of the spec corpus and asserts the
  lexer scopes the definitions the corpus itself pins - the ones whose expected
  HTML shows them consumed. It measures a construct on the day the spec pin
  brings it in, with nobody having to name it in a list first.
  (It replaced a zero-`Token.Error` assertion that carried that claim and could
  not fail: the `inline` state's catch-all makes `Token.Error` unreachable.)
