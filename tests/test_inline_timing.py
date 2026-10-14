"""No inline construct costs more than linear time on one long line.

WHAT THIS MEASURES. Each shape below is a unit repeated along ONE line: an
opener that never finds its closer, or a run built to make a pattern try many
ways of matching. A pattern that scans to the end of the line from every opener
is quadratic on it, and one that can split the same text two ways is worse. An
audit measured all of these on the 0.1.0 lexer: `{{ chapter-one.crv#introduction`
took 166 seconds, an unclosed run of 30 quotes in an attribute block 2 seconds
(x2.6 per two more), 8000 characters of `{~a ~>` 83 seconds, and every bare and
braced emphasis opener grew x2.6 to x4 per doubling.

The assertion is the GROWTH, not a stopwatch reading: absolute times on a
machine carrying other load measure the load. Quadrupling the input must not
multiply the time by more than `LIMIT`, which is the x3-per-doubling threshold
carve-grammars' `scan-superlinear.mjs` uses, squared and rounded down. Linear
shapes measure x4 to x5 here; the quadratic ones measured x10 and up. A ratio
over the limit is measured again before it fails, so one noisy run cannot fail
the suite but a superlinear shape, which is over on every run, still does.

`test_the_sweep_can_say_no` rebuilds the lexer with the old patterns and
requires the same measure to fail on them, so the gate is not trusted on the
strength of the numbers above.
"""

import signal
import time

import pytest

from pygments_carve import CarveLexer

from lexerrules import build_lexer, lexer_source

LEXER = CarveLexer()
SOURCE = lexer_source()

SIZES = (4000, 16000)
LIMIT = 8
ATTEMPTS = 3

#: Seconds one measurement may take before it counts as unbounded. The linear
#: shapes take well under one at the larger size.
BUDGET = 10

#: ``name -> unit``. Every unit is repeated to fill the line, so a shape holds
#: hundreds of openers and none of them closes.
SHAPES = {
    'bold': '*a ',
    'italic': '/a ',
    'underline': '_a ',
    'strike': '~a ',
    'highlight': '=a ',
    'bold-italic': '/*a ',
    'italic-bold': '*/a ',
    'forced pair': '{*a {/b ',
    'braced highlight': '{=a ',
    'critic deletion': '{-a ',
    'critic substitution': '{~a ~>',
    'critic comment': '{#a ',
    'template': '{%a ',
    'code span': '`a ',
    'backtick run': '`',
    'literal code': '!`a ',
    'math': '$`a ',
    'link destination': '[a](',
    'unclosed label': '[a [b] ',
    'image destination': '![a](',
    'footnote reference': '[^a ',
    'citation': '[@a ',
    'inline footnote': '^[a ',
    'role': ':r[a ',
    'autolink': '<a:b',
    'attribute block': 'x{.a ',
    'attribute quotes': 'x {a "b ',
    'include opener': '{{ a ',
    'include path': '{{ ch-1.crv#intro',
    'include unpadded': '{{ a}}',
    # A closer behind an escape, a code span or a link is masked, and the masks
    # are found once per document like the closers.
    'escaped closer': '*a \\* ',
    'code before an opener': '`a` *b ',
    'link before an opener': '[a](u) *b ',
}

#: Shapes repeated line after line: openers whose search crosses lines.
MULTILINE = {
    'quoted fence opener': '> ```\n',
    'item fence opener': '- ```\n',
    'paragraph of markers': 'a\n- b\n',
    'unclosed code per line': 'a `b\n',
    'unclosed inline note per line': 'a ^[b\n',
}

#: Block lines whose content is lexed by a state of its own rather than `inline`.
LINES = {
    'heading': '# ',
    'quote': '> ',
    'caption': '^ ',
    'table row': '| ',
}


class _OverBudget(Exception):
    pass


def _on_alarm(signum, frame):
    raise _OverBudget()


def _elapsed(lexer, source, budget):
    """Seconds to lex ``source``, or infinity past ``budget`` where POSIX allows.

    `re` checks for signals while it matches, so an alarm stops even an
    exponential pattern. Without `setitimer` a runaway shape just runs long.
    """
    timer = getattr(signal, 'setitimer', None)
    if timer is not None:
        old = signal.signal(signal.SIGALRM, _on_alarm)
        timer(signal.ITIMER_REAL, budget)
    try:
        start = time.perf_counter()
        list(lexer.get_tokens(source))
        return time.perf_counter() - start
    except _OverBudget:
        return float('inf')
    finally:
        if timer is not None:
            timer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)


def _line(unit, size, prefix=''):
    return prefix + unit * (size // len(unit))


def growth(lexer, unit, prefix='', budget=BUDGET, attempts=ATTEMPTS):
    """How many times longer the larger size takes, best of ``attempts``."""
    small_size, large_size = SIZES
    worst = 0.0
    for _ in range(attempts):
        small = min(_elapsed(lexer, _line(unit, small_size, prefix), budget)
                    for _ in range(3))
        if small == float('inf'):
            return small
        large = _elapsed(lexer, _line(unit, large_size, prefix), budget)
        ratio = large / max(small, 1e-6)
        if ratio <= LIMIT:
            return ratio
        worst = ratio
    return worst


@pytest.mark.parametrize('name', sorted(SHAPES))
def test_the_shape_is_linear(name):
    ratio = growth(LEXER, SHAPES[name])
    assert ratio <= LIMIT, (
        '%s: quadrupling a line of %r multiplied the time by %.1f on every one '
        'of %d attempts, which is superlinear.'
        % (name, SHAPES[name], ratio, ATTEMPTS))


@pytest.mark.parametrize('name', sorted(MULTILINE))
def test_the_shape_is_linear_over_lines(name):
    ratio = growth(LEXER, MULTILINE[name])
    assert ratio <= LIMIT, (
        '%s: quadrupling %r line after line multiplied the time by %.1f.'
        % (name, MULTILINE[name], ratio))


@pytest.mark.parametrize('name', sorted(LINES))
@pytest.mark.parametrize('unit', ['*a ', '[a]('], ids=repr)
def test_the_shape_is_linear_in_a_block_line(name, unit):
    ratio = growth(LEXER, unit, LINES[name])
    assert ratio <= LIMIT, (
        'a %s holding %r: quadrupling it multiplied the time by %.1f.'
        % (name, unit, ratio))


#: ``(name, the pattern as it was, the rule text it replaces, a shape it fails)``.
#: Each old pattern is spliced back over its rule, and the sweep must call it
#: superlinear.
_OLD = [
    ('a bare closer scanned for, not looked up',
     r"""(r'(?<![\w*])(\*)(?!\*)(\S(?:[^\n]*?\S)?)(\*)(?![^\W_])',""",
     """(_Scan(r'(?<![\\w*])(\\*)(?!\\*)', r'(\\S(?:[^\\n]*?\\S)?)(\\*)(?![^\\W_])',
                   r'(?<=\\S)\\*(?![^\\W_])', least=1, masked='bare'),""",
     '*a '),
    ('the CriticMarkup substitution, scanned twice',
     r"""(r'(\{~)([^\n]*?)(~>)([^\n]*?)(~\})',""",
     r"""(_Scan(r'(\{~)', r'([^\n]*?)(~>)([^\n]*?)(~\})', (r'~>', r'~\}'), masked='bare'),""",
     '{~a ~>'),
    ('an include part separator that could be empty',
     r"""(r'(\{\{)([ \t]+)((?:"(?:\\.|[^"\\])*"|[^#@}\s"][^#@}\s]*))((?:#[A-Za-z0-9_][A-Za-z0-9_-]*)?(?:[ \t]*[^\s}]+)*)([ \t]+)(\}\})',""",
     r"""(_Scan(r'(\{\{)([ \t]+)((?:"(?:\\.|[^"\\])*"|[^#@}\s"][^#@}\s]*))',
                   r'((?:(?<=")[^\s}]+|[#@][^\s}]*)?(?:[ \t]+[^\s}]+)*)([ \t]+)(\}\})',
                   r'\}\}', stop=True),""",
     '{{ ch-1.crv#intro'),
    ('a quote both attribute alternatives could take',
     r"""    r'|(?!(?<=[{\s])[.#](?!\w[\w-]*[\s}]))[^{}\n]'""",
     r"""    r'|(?!(?<=[{\s])[.#](?!\w[\w-]*[\s}]))[^{}\n"\']'""",
     None),
]


@pytest.mark.parametrize('name,old,new,unit', _OLD, ids=[o[0] for o in _OLD])
def test_the_sweep_can_say_no(name, old, new, unit):
    assert SOURCE.count(new) == 1, 'the rule this pin replaces has moved: %r' % new
    mutant = build_lexer(SOURCE.replace(new, old))
    if unit is None:
        # The quotes blow up within one block, so the run is the block's length
        # rather than the line's: 24 quotes against 6.
        small = _elapsed(mutant, 'x {a ' + '"' * 6, 2)
        large = _elapsed(mutant, 'x {a ' + '"' * 24, 2)
        assert large / max(small, 1e-6) > LIMIT, name
        assert _elapsed(LEXER, 'x {a ' + '"' * 24, 2) < 1, name
        return
    assert growth(mutant, unit, budget=2, attempts=1) > LIMIT, (
        '%s: the old pattern is expected to fail the sweep; if it no longer '
        'does, the sweep cannot see the defect it was written for.' % name)
