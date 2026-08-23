"""Read the shared construct inventory out of carve-grammars, in place.

WHY A READER AND NOT A COPY. ``tests/constructs.json`` used to be a plain
vendored copy of ``tests/lib/constructs.js``. Nothing in the org moved it and
nothing compared it, so it drifted: 173 entries against upstream's 175, missing
``reference image`` and ``collapsed reference image``, both of which this lexer
already scopes correctly (markup-carve/pygments-carve#1). Copying the file
forward would have fixed the number and left the mechanism, so the copy is gone
and the inventory is read from the submodule at ``carve-grammars/``. There is no
second list to drift.

WHY IT IS PARSED RATHER THAN EXECUTED. ``constructs.js`` is an ES module and
this is a Pygments plugin: shelling out to Node would put a foreign toolchain in
a Python test suite for one file. The subset actually used by that file - array
and object literals of quoted strings, booleans and nulls - is small enough to
read directly, and the reader below REFUSES anything outside it rather than
guessing. A parser that silently returns fewer entries is the failure this
module exists to prevent, so ``load_inventory`` also checks upstream's own
declared floor, ``MIN_CONSTRUCTS``, read from the same file.
"""

import pathlib
import re

#: The submodule, and the file inside it that is the inventory.
GRAMMARS = pathlib.Path(__file__).parent.parent / 'carve-grammars'
CONSTRUCTS_JS = GRAMMARS / 'tests' / 'lib' / 'constructs.js'


class InventoryError(RuntimeError):
    """The inventory could not be read, which is never a reason to pass."""


def available():
    """Whether the carve-grammars submodule is checked out."""
    return CONSTRUCTS_JS.is_file()


def _strip_comments(text):
    """Remove ``//`` and ``/* */`` comments, leaving string literals alone."""
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in '"\'':
            j = i + 1
            while j < n:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == ch:
                    break
                j += 1
            if j >= n:
                raise InventoryError('unterminated string literal at offset %d' % i)
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            if j < 0:
                raise InventoryError('unterminated block comment at offset %d' % i)
            i = j + 2
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', '0': '\0',
            '\\': '\\', '"': '"', "'": "'", '\n': ''}


class _Reader:
    """A recursive-descent reader for the literal subset ``constructs.js`` uses."""

    def __init__(self, text, at=0):
        self.text = text
        self.i = at

    def error(self, what):
        near = self.text[self.i:self.i + 60].replace('\n', '\\n')
        return InventoryError('%s at offset %d, near %r' % (what, self.i, near))

    def skip(self):
        while self.i < len(self.text) and self.text[self.i] in ' \t\r\n':
            self.i += 1

    def value(self):
        self.skip()
        if self.i >= len(self.text):
            raise self.error('a value was expected and the file ended')
        ch = self.text[self.i]
        if ch == '[':
            return self.array()
        if ch == '{':
            return self.obj()
        if ch in '"\'':
            return self.string()
        for word, parsed in (('true', True), ('false', False), ('null', None)):
            if self.text.startswith(word, self.i):
                self.i += len(word)
                return parsed
        number = re.match(r'-?\d+(?:\.\d+)?', self.text[self.i:])
        if number:
            self.i += number.end()
            return float(number.group()) if '.' in number.group() else int(number.group())
        # Anything else - a template literal, a concatenation, an identifier -
        # is outside the subset. Refuse it; do not guess a value.
        raise self.error('a value this reader does not understand')

    def string(self):
        quote = self.text[self.i]
        self.i += 1
        out = []
        while True:
            if self.i >= len(self.text):
                raise self.error('unterminated string')
            ch = self.text[self.i]
            if ch == '\\':
                nxt = self.text[self.i + 1:self.i + 2]
                if nxt == 'u':
                    out.append(chr(int(self.text[self.i + 2:self.i + 6], 16)))
                    self.i += 6
                    continue
                if nxt not in _ESCAPES:
                    raise self.error('an escape this reader does not understand')
                out.append(_ESCAPES[nxt])
                self.i += 2
                continue
            if ch == quote:
                self.i += 1
                return ''.join(out)
            out.append(ch)
            self.i += 1

    def array(self):
        self.i += 1
        items = []
        while True:
            self.skip()
            if self.i >= len(self.text):
                raise self.error('unterminated array')
            if self.text[self.i] == ']':
                self.i += 1
                return items
            items.append(self.value())
            self.skip()
            if self.i < len(self.text) and self.text[self.i] == ',':
                self.i += 1

    def obj(self):
        self.i += 1
        record = {}
        while True:
            self.skip()
            if self.i >= len(self.text):
                raise self.error('unterminated object')
            if self.text[self.i] == '}':
                self.i += 1
                return record
            if self.text[self.i] in '"\'':
                key = self.string()
            else:
                name = re.match(r'[A-Za-z_$][\w$]*', self.text[self.i:])
                if not name:
                    raise self.error('a key this reader does not understand')
                key = name.group()
                self.i += name.end()
            self.skip()
            if self.i >= len(self.text) or self.text[self.i] != ':':
                raise self.error('a key with no value')
            self.i += 1
            record[key] = self.value()
            self.skip()
            if self.i < len(self.text) and self.text[self.i] == ',':
                self.i += 1


#: Characters that would make the array literal the HEAD of a larger expression
#: rather than the whole value - ``[...].concat(more)``, ``[...].filter(f)``,
#: ``[...] .concat`` and so on. Reading only the literal there would return a
#: SUBSET of the inventory and report it as the whole thing, which the
#: ``MIN_CONSTRUCTS`` floor need not catch: upstream can append rows without
#: raising its own floor. So the suffix is refused rather than ignored.
_EXPRESSION_SUFFIX = set('.([`+-*/%?,=<>&|^')


def read_exported_array(source, name):
    """The array literal exported as ``name``, as Python data.

    The literal has to BE the exported value. A trailing expression is refused,
    not silently dropped - see ``_EXPRESSION_SUFFIX``.
    """
    text = _strip_comments(source)
    match = re.search(r'export\s+const\s+%s\s*=\s*\[' % re.escape(name), text)
    if not match:
        raise InventoryError('constructs.js exports no array called %r any more' % name)
    reader = _Reader(text, match.end() - 1)
    array = reader.array()
    reader.skip()
    tail = text[reader.i:reader.i + 1]
    if tail in _EXPRESSION_SUFFIX:
        raise InventoryError(
            '%s is not a plain array literal any more - it is followed by %r, so this reader '
            'would have returned only the first %d entries and called that the inventory'
            % (name, text[reader.i:reader.i + 40].strip(), len(array))
        )
    return array


def read_exported_int(source, name):
    """The integer exported as ``name``."""
    text = _strip_comments(source)
    match = re.search(r'export\s+const\s+%s\s*=\s*(-?\d+)' % re.escape(name), text)
    if not match:
        raise InventoryError('constructs.js exports no integer called %r any more' % name)
    return int(match.group(1))


def load_inventory(path=None):
    """Every construct carve-grammars asserts across its own grammar sweeps.

    Raises rather than returning a short list: a reader that quietly finds three
    entries would report a green construct sweep over three constructs.
    """
    path = pathlib.Path(path) if path else CONSTRUCTS_JS
    if not path.is_file():
        raise InventoryError(
            '%s is not there - the carve-grammars submodule is not checked out. '
            'Run: git submodule update --init' % path
        )
    source = path.read_text(encoding='utf-8')
    constructs = read_exported_array(source, 'CONSTRUCTS')
    floor = read_exported_int(source, 'MIN_CONSTRUCTS')
    if len(constructs) < floor:
        raise InventoryError(
            'read %d constructs from %s, and that file declares a floor of %d - '
            'the reader lost entries, so every sweep over them would be vacuous'
            % (len(constructs), path, floor)
        )
    for construct in constructs:
        missing = [key for key in ('name', 'sample', 'payload') if not construct.get(key)]
        if missing:
            raise InventoryError(
                'a construct is missing %s: %r' % (', '.join(missing), construct)
            )
    return constructs
