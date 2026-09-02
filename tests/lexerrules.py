"""Read the lexer's own rule list out of its source, and build it without a rule.

This is what lets a test DELETE a rule and ask whether anything notices. A gate
that cannot answer that question is the failure this module exists to measure:
before markup-carve/pygments-carve#25, sixteen of the forty-six rules in
``inlinecontent`` could be removed outright with the whole suite still green.

WHY THE SOURCE AND NOT THE COMPILED STATE. Pygments compiles a state into a list
of ``(match, action, new_state)`` triples, and the action is a closure - there is
no way back from one to the tuple a maintainer would delete. Deleting the LINES
is the mutation a maintainer actually performs, so that is the mutation modeled
here. ``rule_patterns`` then checks the reading against what Pygments compiled,
so a parser that miscounts fails loudly instead of testing a shorter list.
"""

import inspect
import re

import pygments_carve.lexer

#: The inline state every inline construct passes through.
INLINE = 'inlinecontent'


def lexer_source():
    """The lexer module's source text."""
    return inspect.getsource(pygments_carve.lexer)


def _bracket_delta(line):
    """Net bracket depth of ``line``, ignoring comments and string literals."""
    depth = 0
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch == '#':
            break
        if ch in '\'"':
            i += 1
            while i < n:
                if line[i] == '\\':
                    i += 2
                    continue
                if line[i] == ch:
                    break
                i += 1
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        i += 1
    return depth


def state_rules(source, state=INLINE):
    """``[(first_line, past_last_line, text)]``, one per rule tuple in ``state``.

    Line indices are into ``source.split('\\n')``, so a rule can be removed by
    slicing the lines out - which is exactly what ``without_rule`` does.
    """
    opener = re.search(r"^        '%s': \[\n" % re.escape(state), source, re.M)
    if not opener:
        raise LookupError('the lexer has no state called %r any more' % state)
    lines = source.split('\n')
    depth, start = 0, None
    rules = []
    for i in range(source[:opener.end()].count('\n'), len(lines)):
        text = lines[i].strip()
        if depth == 0:
            if text == '],':
                break
            if not text or text.startswith('#'):
                continue
            start = i
        depth += _bracket_delta(lines[i])
        if depth == 0 and start is not None:
            rules.append((start, i + 1, '\n'.join(lines[start:i + 1])))
            start = None
    if depth != 0 or start is not None:
        raise SyntaxError('a rule tuple in %r never closes' % state)
    return rules


def without_rule(source, index, state=INLINE):
    """``source`` with rule ``index`` of ``state`` deleted."""
    first, past, _ = state_rules(source, state)[index]
    lines = source.split('\n')
    return '\n'.join(lines[:first] + lines[past:])


def build_lexer(source):
    """A ``CarveLexer`` built from ``source`` rather than from the import.

    The module is executed into a throwaway namespace, so the mutant class is
    never registered anywhere and cannot leak into another test.
    """
    namespace = {'__name__': 'pygments_carve._mutant'}
    exec(compile(source, '<mutant lexer>', 'exec'), namespace)
    return namespace['CarveLexer']()


def rule_patterns(lexer, state=INLINE):
    """The regex source of each compiled rule in ``state``, in order.

    Pygments stores the bound ``match`` of a compiled pattern; ``__self__`` is
    the pattern it belongs to.
    """
    return [rex.__self__.pattern for rex, _, _ in lexer._tokens[state]]
