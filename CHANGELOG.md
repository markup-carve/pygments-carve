# Changelog

All notable changes to pygments-carve are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing released yet. The initial capability set:

### Added

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
- A corpus suite that lexes every document of the spec corpus and asserts the
  lexer scopes the definitions the corpus itself pins - the ones whose expected
  HTML shows them consumed. It measures a construct on the day the spec pin
  brings it in, with nobody having to name it in a list first.
  (It replaced a zero-`Token.Error` assertion that carried that claim and could
  not fail: the `inline` state's catch-all makes `Token.Error` unreachable.)
