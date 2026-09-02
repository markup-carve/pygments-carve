"""Every rule in the inline state is pinned, and every pin can say no.

WHAT THIS MEASURES, AND WHY THE CONSTRUCT SWEEP DOES NOT. `test_constructs.py`
asks whether a construct's payload lands in a token that is not plain text. Any
non-text token satisfies that, so a rule can be DELETED OUTRIGHT and the sweep
still passes whenever a neighbouring rule happens to catch the payload in a
token of the same shape. Measured at `2c5aa24`: of the 46 rules in the
`inlinecontent` state, deleting any one of SIXTEEN left the whole suite green -
`1776 passed`, exit 0 (markup-carve/pygments-carve#25).

A PER-CONSTRUCT TOKEN TYPE WOULD NOT HAVE CLOSED IT. That was the first guess on
the ticket, and it is not enough: for seven of the sixteen the fallback produces
the very same type. Delete the braced-highlight rule and `wo{=mark=}rd` still
reports `Generic.Inserted` for `mark`, because the bare `=` rule below claims it
- the braces merely stop being `Punctuation`. So what is recorded here is the
whole SCOPED RUN of a sample: every token the lexer colours, with its text. That
is what tells `{=` apart from `=`.

THE PINS ARE PROVED SHARP FROM INSIDE THE SUITE. `test_pin_is_sharp` deletes
each rule from the lexer source, rebuilds the lexer, and requires that pin to
STOP holding. A pin that would survive its own rule's deletion is not a pin, and
that test is what says so - the gate is not trusted on the strength of the
argument above.

Deleting a rule AND its pin together still passes, and that is deliberate: the
diff then shows a pin being removed, which is a reviewable act. What this gate
ends is deletion that nothing anywhere records.

THE FOUR RULES THE SHARED INVENTORY DOES NOT NAME. Arrows, ellipsis, the
mirrored `*/x/*` nesting and `{>>...<<}` have no entry in carve-grammars'
inventory, so no sweep on any surface tests them. They are pinned here rather
than dropped, and the two halves of that are not the same decision:

- ARROWS and ELLIPSIS are real Carve. Corpus `20-smart-typography-arrows-and-
  symbols` renders `-->` as an arrow and `15-heading-ids-4` renders `...` as an
  ellipsis, and all three sibling grammars scope them - TextMate in one
  `smart_typography` pattern of thirteen alternatives. The inventory names that
  construct but pins a single sample, `a -- b`, so twelve of the thirteen are
  untested on every surface in the org. That is an upstream gap, reported as
  markup-carve/carve-grammars#373, not something to fix by editing a list this
  repo reads in place.
- `{>>...<<}` IS NOT CARVE SYNTAX. It is CriticMarkup's own spelling, which the
  spec quotes once as prior art (`docs/case-study/background.md`) and which
  Carve deliberately re-spelled: the comment is `{#note#}`, pinned above as
  `critic comment`. No corpus document uses it, and no sibling grammar carries
  it. The rule therefore colours a run that Carve renders as plain text. Removing
  it is a behavior change with its own reasoning, so it is pinned here - the pin
  records what the lexer does today, and the note keeps that from reading as
  endorsement - and tracked as markup-carve/pygments-carve#27.
"""

import collections

import pytest

from pygments.token import (
    Comment,
    Generic,
    Literal,
    Name,
    Operator,
    Punctuation,
    String,
)

from pygments_carve import CarveLexer

from coverage import UNSCOPED
from lexerrules import (
    build_lexer,
    lexer_source,
    rule_patterns,
    state_rules,
    without_rule,
)


class Pin(collections.namedtuple('Pin', 'name sample expect note')):
    """A sample, and every token the lexer is expected to colour in it."""

    __slots__ = ()

    def __new__(cls, name, sample, expect, note=''):
        return super().__new__(cls, name, sample, tuple(expect), note)


#: One pin per rule of the `inlinecontent` state, IN THE ORDER THE RULES APPEAR.
#: The order is what pairs a pin with its rule, and `test_pin_is_sharp` is what
#: checks the pairing rather than trusting it.
PINS = [
    Pin('hard break', 'a \\\n',
        [(String.Escape, '\\')]),
    Pin('escaped delimiter', 'a \\* b',
        [(String.Escape, '\\*')]),
    Pin('trailing comment', 'a %% note',
        [(Comment.Preproc, '%%'), (Comment, ' note')]),
    Pin('literal code span', 'a !`x` b',
        [(Operator, '!'), (Punctuation, '`'), (Literal, 'x'), (Punctuation, '`')]),
    Pin('display math', 'a $$`x` b',
        [(Operator, '$$'), (Punctuation, '`'), (String.Other, 'x'), (Punctuation, '`')]),
    Pin('inline math', 'a $`x` b',
        [(Operator, '$'), (Punctuation, '`'), (String.Other, 'x'), (Punctuation, '`')]),
    Pin('inline code', 'a `x` b',
        [(Punctuation, '`'), (String.Backtick, 'x'), (Punctuation, '`')]),
    Pin('critic substitution', 'a {~old~>new~} b',
        [(Punctuation, '{~'), (Generic.Deleted, 'old'), (Operator, '~>'),
         (Generic.Inserted, 'new'), (Punctuation, '~}')]),
    Pin('critic comment', 'a {#note#} b',
        [(Punctuation, '{#'), (Comment, 'note'), (Punctuation, '#}')]),
    Pin('forced bold', 'wo{*bar*}rd',
        [(Punctuation, '{*'), (Generic.Strong, 'bar'), (Punctuation, '*}')]),
    Pin('forced italic', 'wo{/b/}rd',
        [(Punctuation, '{/'), (Generic.Emph, 'b'), (Punctuation, '/}')]),
    Pin('forced underline', 'wo{_path_}rd',
        [(Punctuation, '{_'), (Generic.Underline, 'path'), (Punctuation, '_}')]),
    Pin('forced strike', 'wo{~gone~}rd',
        [(Punctuation, '{~'), (Generic.Deleted, 'gone'), (Punctuation, '~}')]),
    Pin('superscript', 'wo{^2^}rd',
        [(Punctuation, '{^'), (Generic.Emph, '2'), (Punctuation, '^}')]),
    Pin('subscript', 'wo{,2,}rd',
        [(Punctuation, '{,'), (Generic.Emph, '2'), (Punctuation, ',}')]),
    Pin('highlight brace', 'wo{=mark=}rd',
        [(Punctuation, '{='), (Generic.Inserted, 'mark'), (Punctuation, '=}')]),
    Pin('critic insert', 'a {+ins+} b',
        [(Punctuation, '{+'), (Generic.Inserted, 'ins'), (Punctuation, '+}')]),
    Pin('critic delete', 'a {-del-} b',
        [(Punctuation, '{-'), (Generic.Deleted, 'del'), (Punctuation, '-}')]),
    Pin('annotation', 'a {>>note<<} b',
        [(Punctuation, '{>>'), (Comment, 'note'), (Punctuation, '<<}')],
        note='NOT CARVE. See the module docstring.'),
    Pin('template span', 'a {%tpl%} b',
        [(Comment.Preproc, '{%'), (Comment, 'tpl'), (Comment.Preproc, '%}')]),
    Pin('inline footnote', 'a ^[note] b',
        [(Punctuation, '^['), (Generic.Emph, 'note'), (Punctuation, ']')]),
    Pin('footnote reference', 'a [^fn] b',
        [(Punctuation, '[^'), (Name.Label, 'fn'), (Punctuation, ']')]),
    Pin('citation', 'a [@key] b',
        [(Punctuation, '['), (Name.Variable, '@key'), (Punctuation, ']')]),
    Pin('inline image', 'a ![alt](i.png) b',
        [(String.Other, '![alt]'), (Punctuation, '('), (Name.Tag, 'i.png'),
         (Punctuation, ')')]),
    Pin('reference image', 'a ![alt][r] b',
        [(String.Other, '![alt]'), (Name.Label, '[r]')]),
    Pin('link', 'a [t](/u) b',
        [(Name.Entity, '[t]'), (Punctuation, '('), (Name.Tag, '/u'), (Punctuation, ')')]),
    Pin('reference link', 'a [t][r] b',
        [(Name.Entity, '[t]'), (Name.Label, '[r]')]),
    Pin('label carrying attributes', 'a [t]{.c} b',
        [(Name.Entity, '[t]'), (Name.Attribute, '{.c}')]),
    Pin('cross-reference', 'a </#sec> b',
        [(Punctuation, '</'), (Name.Namespace, '#sec'), (Punctuation, '>')]),
    Pin('autolink', 'a <https://e.com> b',
        [(Punctuation, '<'), (Name.Tag, 'https://e.com'), (Punctuation, '>')]),
    Pin('role', 'a :name[body] b',
        [(Punctuation, ':'), (Name.Function, 'name'), (Punctuation, '['),
         (Name.Function, 'body'), (Punctuation, ']')]),
    Pin('code callout', 'a <1> b',
        [(Name.Constant, '<1>')]),
    Pin('symbol shortcode', 'a :smile: b',
        [(Name.Constant, ':smile:')]),
    Pin('attribute block', 'a x{.c} b',
        [(Name.Attribute, '{.c}')]),
    Pin('bold-italic', 'a /*both*/ b',
        [(Punctuation, '/*'), (Generic.Strong, 'both'), (Punctuation, '*/')]),
    Pin('italic-bold', 'a */both/* b',
        [(Punctuation, '*/'), (Generic.Strong, 'both'), (Punctuation, '/*')],
        note='The mirrored nesting; the inventory names only `/*x*/`.'),
    Pin('bold', 'a *b* c',
        [(Punctuation, '*'), (Generic.Strong, 'b'), (Punctuation, '*')]),
    Pin('italic', 'a /i/ c',
        [(Punctuation, '/'), (Generic.Emph, 'i'), (Punctuation, '/')]),
    Pin('underline', 'a _u_ c',
        [(Punctuation, '_'), (Generic.Underline, 'u'), (Punctuation, '_')]),
    Pin('strike', 'a ~s~ c',
        [(Punctuation, '~'), (Generic.Deleted, 's'), (Punctuation, '~')]),
    Pin('highlight bare', 'a =m= c',
        [(Punctuation, '='), (Generic.Inserted, 'm'), (Punctuation, '=')]),
    Pin('mention', 'a @user b',
        [(Name.Variable.Magic, '@user')]),
    Pin('tag', 'a #tag b',
        [(Name.Variable.Instance, '#tag')]),
    Pin('arrow', 'a -> b',
        [(Operator, '->')],
        note='Unnamed upstream: the inventory pins only the en dash.'),
    Pin('en dash', 'a -- b',
        [(Punctuation, '--')]),
    Pin('ellipsis', 'a ... b',
        [(Punctuation, '...')],
        note='Unnamed upstream: the inventory pins only the en dash.'),
]


LEXER = CarveLexer()
SOURCE = lexer_source()
RULES = state_rules(SOURCE)


def scoped_run(lexer, sample):
    """Every token of ``sample`` that is not plain text, with its text.

    The same `UNSCOPED` the construct sweep uses, so "scoped" means one thing in
    this suite. Keeping the token TEXT is the point: the delimiters are what a
    same-type fallback gets wrong.
    """
    return tuple((ttype, value) for ttype, value in lexer.get_tokens(sample)
                 if ttype not in UNSCOPED)


def _named(pin):
    return pin.name


def test_the_reading_matches_what_pygments_compiled():
    """The source reading must find the rules Pygments actually compiled.

    Every test below mutates the SOURCE. A reader that finds forty of
    forty-six rules would mutate the wrong lines and pin a shorter list, so the
    reading is checked against the compiled state rather than assumed.
    """
    compiled = rule_patterns(LEXER)
    assert len(RULES) == len(compiled), (
        'read %d rule tuples out of the inline state, but Pygments compiled %d. '
        'tests/lexerrules.py can no longer read the lexer source.'
        % (len(RULES), len(compiled))
    )


def test_every_inline_rule_has_a_pin():
    """A rule with no pin is a rule nothing can notice the deletion of."""
    assert len(PINS) == len(RULES), (
        '%d rules in the inline state and %d pins. A new rule needs a pin '
        '(sample plus its expected scoped run); a removed rule needs its pin '
        'removed in the same diff, which is what makes the removal reviewable.'
        % (len(RULES), len(PINS))
    )


@pytest.mark.parametrize('pin', PINS, ids=_named)
def test_pin_holds(pin):
    """The lexer colours the sample exactly as recorded."""
    assert scoped_run(LEXER, pin.sample) == pin.expect, (
        'pin %r no longer holds. If the lexer is right and the pin is stale, '
        'update it - but check the change was intended: this run is the whole '
        'reason deleting a rule cannot pass unnoticed.' % pin.name
    )


@pytest.mark.parametrize('index', range(len(PINS)), ids=[p.name for p in PINS])
def test_deleting_a_rule_removes_exactly_that_compiled_rule(index):
    """Source rule ``index`` is compiled rule ``index``.

    This is what earns the right to say "delete rule N" in the test below: the
    lines removed from the source are the ones behind that compiled pattern, so
    a pin proved sharp against them is proved sharp against the real rule.
    """
    assert index < len(RULES), 'no rule %d to delete; see the pin count' % index
    base = rule_patterns(LEXER)
    mutant = build_lexer(without_rule(SOURCE, index))
    assert rule_patterns(mutant) == base[:index] + base[index + 1:]


@pytest.mark.parametrize('index', range(len(PINS)), ids=[p.name for p in PINS])
def test_pin_is_sharp(index):
    """Deleting the rule must stop its pin from holding.

    THE GATE PROVING IT CAN SAY NO. Without this, the pins above are a claim;
    with it, every one of the 46 rules is known to be undeletable in silence.
    """
    assert index < len(RULES), 'no rule %d to delete; see the pin count' % index
    pin = PINS[index]
    mutant = build_lexer(without_rule(SOURCE, index))
    assert scoped_run(mutant, pin.sample) != pin.expect, (
        'rule %d was deleted and pin %r still holds, so that rule can be '
        'removed with nothing objecting. Give the pin a sample that only this '
        'rule can produce.' % (index, pin.name)
    )
