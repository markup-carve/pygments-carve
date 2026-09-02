"""Every smart-typography alternative the spec grammar names is scoped, whole.

WHAT THE OTHER GATES CANNOT SEE. `test_inline_rules.py` proves each RULE is
undeletable. It cannot prove a rule's ALTERNATION is complete, and that is the
hole markup-carve/pygments-carve#28 was filed in: the arrow rule was pinned by
`a -> b`, so `<->` could match as `<-` plus a stray `>`, and `<=`, `>=`, `!=`
and `+-` could be absent, with every gate green. The construct sweep could not
object either - carve-grammars' inventory named one `smart typography` row
sampling `a -- b`, so twelve of the alternatives were pinned on no surface in
the org (carve-grammars#373, fixed there by carve-grammars#377).

SO THE SET IS READ FROM THE SPEC, IN PLACE. `spec/resources/grammar.ebnf` gives

    arrow              = "<--" | "-->" | "<-->" | "<==" | "==>" | "<=>"
                       | "<-" | "->" | "<->" ;
    comparison         = "!=" | "<=" | ">=" ;
    typographic_symbol = "(c)" | "(r)" | "(tm)" | "+-" ;
    em_dash = "---" ;  en_dash = "--" ;  ellipsis = "..." ;

and the assertions below are generated from those productions rather than from a
list written here. An alternative the spec adds is measured the day the pin
brings it in, with nobody having to notice - the same property `test_corpus.py`
gets from the corpus, applied to a production.

WHOLE IS THE POINT. Asking only that the payload carries SOME scope is what let
`<->` pass on the sibling surfaces: `<--` deleted leaves `<-` plus a text `>`,
and a sweep that accepts any overlapping token stays green. carve-grammars#377
needed a `whole` flag for exactly this. Here the assertion is the token's TEXT.

TWO PRODUCTIONS OF `smart_typography` ARE DELIBERATELY NOT COVERED, and
`test_the_covered_productions_are_all_of_smart_typography` fails if a third
appears:

- `smart_quote` is per-character contextual substitution decided by the
  PRECEDING character, not a run - a quote is scoped by nothing on any of the
  four surfaces.
- `braced_en_dash` (`{--}`) is a brace form the engines colour with the
  CriticMarkup deletion rule rather than a typography rule; tracked upstream as
  carve-grammars#376.
"""

import pathlib
import re

import pytest

from pygments.token import Name, Operator, Punctuation, Text

from pygments_carve import CarveLexer

from lexerrules import (
    INLINE,
    build_lexer,
    lexer_source,
    state_rules,
    without_rule,
)

GRAMMAR = (pathlib.Path(__file__).parent.parent / 'spec' / 'resources' / 'grammar.ebnf')

spec = pytest.mark.skipif(
    not GRAMMAR.is_file(),
    reason='spec submodule not present; run: git submodule update --init',
)

#: The productions of `smart_typography` this lexer scopes, and the token type
#: each lands in. Arrows and comparisons are directional and relational
#: operators; the dash runs and the ellipsis are punctuation; the `(c)` family
#: and `+-` render a fixed character, which is what `Name.Constant` already
#: means here for the `:name:` shortcode.
COVERED = {
    'arrow': Operator,
    'comparison': Operator,
    'em_dash': Punctuation,
    'en_dash': Punctuation,
    'ellipsis': Punctuation,
    'typographic_symbol': Name.Constant,
}

#: The two the lexer does not scope, with the reason. See the module docstring.
UNCOVERED = {'smart_quote', 'braced_en_dash'}

LEXER = CarveLexer()
SOURCE = lexer_source()


def production(name, text):
    """The quoted alternatives of an EBNF production, comments stripped."""
    match = re.search(r'^' + re.escape(name) + r'\s*=(.*?);', text, re.S | re.M)
    if not match:
        raise LookupError('the grammar has no production %r any more' % name)
    body = re.sub(r'\(\*.*?\*\)', '', match.group(1), flags=re.S)
    return re.findall(r'"([^"]*)"', body)


def alternatives():
    """``[(production, alternative, token type)]`` read from the spec grammar."""
    text = GRAMMAR.read_text(encoding='utf-8')
    return [(name, alt, ttype)
            for name, ttype in COVERED.items()
            for alt in production(name, text)]


ALTERNATIVES = alternatives() if GRAMMAR.is_file() else []


def scoped(lexer, sample):
    return tuple((t, v) for t, v in lexer.get_tokens(sample)
                 if t not in (Text, Text.Whitespace))


def sample_for(alt):
    """A sample putting the run between spaces, which every alternative allows."""
    return 'a %s b' % alt


# ----------------------------------------------------------------------------
# The set, read from the grammar
# ----------------------------------------------------------------------------

@spec
def test_the_covered_productions_are_all_of_smart_typography():
    """A production added upstream must be covered or named, never neither."""
    text = GRAMMAR.read_text(encoding='utf-8')
    match = re.search(r'^smart_typography\s*=(.*?);', text, re.S | re.M)
    assert match, 'the grammar has no smart_typography production any more'
    named = set(re.findall(r'[a-z_]+', re.sub(r'\(\*.*?\*\)', '', match.group(1), flags=re.S)))
    assert named == set(COVERED) | UNCOVERED, (
        'smart_typography names %s; this file covers %s and excuses %s. A new '
        'production needs a row in COVERED or a reason in UNCOVERED.'
        % (sorted(named), sorted(COVERED), sorted(UNCOVERED)))


@spec
def test_there_are_nineteen_alternatives():
    """The count Prism and highlight.js carry, and the floor for the sweep below."""
    assert len(ALTERNATIVES) == 19, [a for _, a, _ in ALTERNATIVES]


@spec
@pytest.mark.parametrize('name,alt,ttype', ALTERNATIVES,
                         ids=[a for _, a, _ in ALTERNATIVES])
def test_the_alternative_is_scoped_whole(name, alt, ttype):
    """One token, the whole run, and the type the production maps to."""
    assert scoped(LEXER, sample_for(alt)) == ((ttype, alt),), (
        '%s alternative %r is not scoped as one %s token holding exactly %r'
        % (name, alt, ttype, alt))


# ----------------------------------------------------------------------------
# Every alternative is load-bearing
# ----------------------------------------------------------------------------

def typography_parts(source):
    """``[(rule index, part index, text)]`` for each `|` branch of each rule.

    The rules are found by the alternatives they hold rather than by position,
    so inserting a rule above them does not silently move the mutation.
    """
    wanted = {alt for _, alt, _ in ALTERNATIVES} or {'<-->', '...', '(c)'}
    out = []
    for index, (_, _, text) in enumerate(state_rules(source, INLINE)):
        literal = re.search(r"\(r'([^']*)'", text)
        if not literal:
            continue
        parts = literal.group(1).split('|')
        # A regex split on `|` is only meaningful when every branch stands
        # alone; a rule with a `|` inside a group yields fragments that do not
        # compile, and those are not typography rules.
        try:
            hit = any(re.fullmatch(branch, alt) for branch in parts for alt in wanted)
        except re.error:
            continue
        if not hit:
            continue
        out.extend((index, part, parts[part]) for part in range(len(parts)))
    return out


PARTS = typography_parts(SOURCE) if GRAMMAR.is_file() else []


def without_alternative(source, rule_index, part_index):
    """``source`` with one `|` branch removed from one rule.

    A rule holding a single branch - the ellipsis - has its whole rule removed,
    which is the same mutation for it: the branch IS the rule.
    """
    first, past, text = state_rules(source, INLINE)[rule_index]
    literal = re.search(r"\(r'([^']*)'", text)
    parts = literal.group(1).split('|')
    if len(parts) == 1:
        return without_rule(source, rule_index, INLINE)
    rebuilt = text.replace(literal.group(1),
                           '|'.join(parts[:part_index] + parts[part_index + 1:]), 1)
    lines = source.split('\n')
    return '\n'.join(lines[:first] + rebuilt.split('\n') + lines[past:])


@spec
def test_the_parts_found_are_the_nineteen():
    """Guard the guard: a reader that finds three branches sweeps three."""
    assert len(PARTS) == len(ALTERNATIVES), [p[2] for p in PARTS]


@spec
@pytest.mark.parametrize('rule,part,text', PARTS, ids=[p[2] for p in PARTS])
def test_every_alternative_is_load_bearing(rule, part, text):
    """Removing one `|` branch must break one of the assertions above.

    This is the gate the ticket asked for in its last paragraph: the rule sweep
    proves a rule undeletable, not that its alternation is complete, and an
    alternative silently lost is exactly how `<->` came to be scoped as `<-`
    plus a stray `>`.
    """
    mutant = build_lexer(without_alternative(SOURCE, rule, part))
    broken = [alt for _, alt, ttype in ALTERNATIVES
              if scoped(mutant, sample_for(alt)) != ((ttype, alt),)]
    assert broken, (
        'branch %r was removed from inline rule %d and all nineteen '
        'alternatives still scope whole, so it carries nothing.' % (text, rule))


# ----------------------------------------------------------------------------
# The shapes that are NOT one alternative
# ----------------------------------------------------------------------------

@spec
def test_a_double_arrow_before_a_gt_is_not_one_run():
    """`<==>` is `<==` and then a literal `>`, and renders `⇐>`.

    PART 9's typography table states it, and the reference renderer confirms it:
    `a <==> b` gives `a ⇐&gt; b`. The lexer used to carry `<==>` as its own
    alternative and coloured the whole run.
    """
    assert scoped(LEXER, 'a <==> b') == ((Operator, '<=='),)


@spec
@pytest.mark.parametrize('sample,expect', [
    # A bare `=` touching a typography run is not a highlight delimiter. PART 9's
    # inline precedence excepts "a delimiter that begins a multi-char
    # smart-typography pattern ... the pattern is consumed first".
    ('key => value, and p <= q', ((Operator, '<='),)),
    ('Canonical: <== ==> <=>', ((Operator, '<=='), (Operator, '==>'), (Operator, '<=>'))),
    # BOTH ends are guarded. The reference renderer gives `x =y z≤ w` - no mark
    # anywhere - where an unguarded closer would mark `y z<`.
    ('x =y z<= w', ((Operator, '<='),)),
    # And a real highlight still closes with a comparison later on the line.
    ('a =m= b <= c', ((Punctuation, '='), ('mark', 'm'), (Punctuation, '='),
                      (Operator, '<='))),
])
def test_a_bare_equals_beside_a_pattern_is_not_a_highlight(sample, expect):
    got = scoped(LEXER, sample)
    expect = tuple((t, v) if t != 'mark' else (got[1][0], v) for t, v in expect)
    assert got == expect, got
