"""No state in this lexer can be abandoned at the end of a line.

WHY THIS FILE EXISTS. Pygments resets the state stack to ``root`` at every
newline no rule matches, so a state whose rules all stop at ``[^\\n]`` is
abandoned at the end of every line. Two states were in that shape and one of
them therefore NEVER RAN: ``codeblock`` was pushed with the cursor on the
opener's newline, no rule matched it, and the stack reset before a single body
character was read - so ``# x`` inside a Python code block was scoped as a
heading and ``*b*`` as bold, in a lexer whose docstring said "a fence body is
opaque". ``frontmatter`` had the same shape and escaped at the first blank line
(markup-carve/pygments-carve#32).

THE GATE IS MECHANICAL, which is the point: it does not need anyone to name a
construct, and it holds for a state added tomorrow. A state that is PUSHED must
be able to match at position 0 of a bare ``"\\n"``, either by consuming it or by
popping at ``$`` before it. There are only those two shapes, and a state in
neither is dead code the day it is written.

The three states reached through ``using(this, state=...)`` rather than a push
are a separate question and are checked separately below.
"""

import re

import pytest

from pygments_carve import CarveLexer

from lexerrules import build_lexer, lexer_source

LEXER = CarveLexer()
SOURCE = lexer_source()

#: The states a rule hands a GROUP to, rather than pushing. Each is listed with
#: the reason it is not on the gate below.
USING_STATES = {
    # The rest of a fence or container opener LINE. Its group is `[^\n]*`, so
    # the text it is given never holds a newline.
    'infostring': 'its group is a single line by construction',
    # The marker run a definition line carries before its content, likewise
    # matched within one line.
    'markerrun': 'its group is a single line by construction',
    # The one that DOES span lines - and therefore does match a newline, which
    # `test_the_multi_line_using_state_survives_a_newline` asserts rather than
    # exempting.
    'fencebody': 'spans lines, and is asserted to match a newline below',
}


def _pushed_states(tokens):
    """Every state name a rule in ``tokens`` pushes."""
    found = set()
    for rules in tokens.values():
        for rule in rules:
            if not isinstance(rule, tuple) or len(rule) < 3:
                continue
            target = rule[2]
            for name in (target if isinstance(target, tuple) else (target,)):
                if isinstance(name, str) and not name.startswith('#'):
                    found.add(name)
    return found


def _survives_a_newline(lexer, state):
    """Whether some rule in ``state`` matches at position 0 of ``"\\n"``."""
    return any(rex('\n', 0) for rex, _, _ in lexer._tokens[state])


#: `root` is not pushed by anything - it is where a document starts - so it
#: would fall through a gate that only reads pushes.
STATES = sorted(_pushed_states(CarveLexer.tokens) | {'root'})


def test_the_gate_has_states_to_measure():
    """Guard the guard: a reader that finds no state asserts nothing."""
    assert len(STATES) > 5, STATES


@pytest.mark.parametrize('state', STATES)
def test_a_pushed_state_survives_a_newline(state):
    assert _survives_a_newline(LEXER, state), (
        "state %r has no rule that matches a bare newline, so Pygments abandons "
        "it at the end of every line. Either give it a rule that consumes '\\n', "
        "or a rule that pops at '$', or match the construct whole in one rule "
        "the way the fence and the comment fence are matched." % state
    )


def test_the_multi_line_using_state_survives_a_newline():
    """A `using` state handed a MULTI-LINE group needs the same property.

    It is not reached by a push, so the gate above does not read it, and it is
    the one state in `USING_STATES` whose text spans lines.
    """
    assert _survives_a_newline(LEXER, 'fencebody')


def test_the_using_states_are_the_recorded_ones():
    """A new `using(this, state=...)` target has to be classified, not inherited.

    The gate above reads PUSHES. A state reached only by handing it a group is
    invisible to it, so the set is pinned here and a new one fails until
    somebody says which of the two shapes it is in.
    """
    found = set(re.findall(r"using\(this, state='([^']+)'\)", SOURCE))
    assert found == set(USING_STATES), sorted(found ^ set(USING_STATES))


#: The two states as they stood before markup-carve/pygments-carve#32: a
#: `codeblock` pushed by an opener that stops short of its own newline, and a
#: `frontmatter` whose body rule needs at least one non-newline character.
#: Rebuilding them is the only way to prove the gate can say NO - deleting a
#: rule cannot produce a state that is dead, it can only make one deader.
_REGRESSION_STATES = """        'frontmatter': [
            (r'^(---)([ \\t]*)$', bygroups(Punctuation, Text), '#pop'),
            (r'[^\\n]+\\n?', Comment.Special),
        ],

        'codeblock': [
            (r'^[ \\t]*(?:`{3,}|~{3,})[ \\t]*$', Punctuation, '#pop'),
            (r'<\\d+>', Name.Constant),
            (r'[^\\n<]+|<', String.Backtick),
        ],

"""

#: An opener for each, so both states are PUSHED and the gate reads them.
_REGRESSION_OPENERS = """            (r'\\A(\\ufeff?)(---)([a-zA-Z][\\w-]*)?([ \\t]*\\n)',
             bygroups(Text, Punctuation, Keyword.Type, Text), 'frontmatter'),
            (r'^(' + _MARGIN + r')(`{3,}|~{3,})([ \\t]*)([a-zA-Z][\\w+#.-]*)?([^\\n]*)',
             bygroups(Text, Punctuation, Text, Name.Builtin,
                      using(this, state='infostring')), 'codeblock'),
"""


def _regression_source():
    anchor = "        'root': [\n            include('block'),\n"
    assert anchor in SOURCE, 'no anchor to re-insert the pre-#32 openers into'
    out = SOURCE.replace(anchor, anchor + _REGRESSION_OPENERS, 1)
    state_anchor = "        'fencebody': ["
    assert state_anchor in out, 'no anchor to re-insert the pre-#32 states before'
    return out.replace(state_anchor, _REGRESSION_STATES + state_anchor, 1)


def test_the_gate_reports_the_two_states_the_ticket_was_filed_on():
    """The pass above is only meaningful if this gate can reach those two.

    Put the pre-#32 `codeblock` and `frontmatter` back and the gate names both
    and nothing else - which is also the count the ticket reported: one state
    that never ran at all, and one that escaped at the first blank line.
    """
    mutant = build_lexer(_regression_source())
    dead = sorted(s for s in _pushed_states(type(mutant).tokens) | {'root'}
                  if not _survives_a_newline(mutant, s))
    assert dead == ['codeblock', 'frontmatter'], dead
