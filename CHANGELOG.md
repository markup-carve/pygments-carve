# Changelog

All notable changes to pygments-carve are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing released yet. The initial capability set:

### Added

- A Pygments lexer for Carve, registered through the `pygments.lexers` entry
  point so that installing the package is enough for `carve` and `crv` to work
  as fence words in MkDocs, Sphinx, zensical and every other Pygments consumer.
- Coverage of every construct in carve-grammars' shared inventory, asserted
  per construct rather than assumed. The inventory is read in place from the
  `carve-grammars` submodule, so this repo carries no copy of it to fall behind.
- A corpus suite that lexes the full spec corpus and requires no `Token.Error`,
  which is what catches constructs the inventory does not name.
