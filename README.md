# pygments-carve

[![CI](https://github.com/markup-carve/pygments-carve/actions/workflows/ci.yml/badge.svg)](https://github.com/markup-carve/pygments-carve/actions/workflows/ci.yml)

Pygments lexer for Carve syntax. It follows the shared Carve grammar inventory and registers the `carve` and `crv` aliases. Read the [Carve documentation](https://markup-carve.github.io/carve/) for the language syntax.

## Install

```sh
pip install git+https://github.com/markup-carve/pygments-carve
```

## Usage

```sh
pygmentize -l carve page.crv
```

## Documentation

- [Carve documentation](https://markup-carve.github.io/carve/)
- [Documentation index](docs/README.md)
- [Development](docs/development.md)

## License

[MIT](LICENSE)
