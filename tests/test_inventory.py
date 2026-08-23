"""The inventory reader, and the two conditions that would make it lie.

WHAT THIS EXISTS FOR. ``tests/constructs.json`` was a vendored copy of
carve-grammars' ``tests/lib/constructs.js`` that nothing in the org moved and
nothing compared. It had drifted three ways at once
(markup-carve/pygments-carve#1): two constructs missing outright, and a third
whose ``textmate`` selector said ``string.other.link.title`` where upstream says
``string.other.image.alt`` - a field this suite does not read, which is exactly
why nobody saw it. The copy is gone; the list is read from the submodule.

That trades one silent failure for two, and both are covered here:

- A READER THAT SILENTLY FINDS FEWER ENTRIES. ``test_constructs.py`` is
  parametrized over whatever comes back, so a reader that returns three
  constructs reports a green sweep over three constructs. Every row below that
  feeds the reader something it cannot parse asserts it RAISES.
- A SUBMODULE THAT IS NOT THERE. An absent submodule collects zero cases, and
  zero passing cases is a green tick. That half lives in ``test_submodules.py``,
  which is outside every ``skipif`` so it can still fail when nothing else runs.
"""

import textwrap

import pytest

import inventory
from coverage import refuse_skip_in_ci


@pytest.mark.skipif(not inventory.available(), reason='carve-grammars submodule not present')
def test_the_inventory_is_substantial():
    """Guard the guard: a short read would make every construct case vacuous."""
    constructs = inventory.load_inventory()
    source = inventory.CONSTRUCTS_JS.read_text(encoding='utf-8')
    floor = inventory.read_exported_int(source, 'MIN_CONSTRUCTS')
    assert len(constructs) >= floor, (
        'read %d constructs against upstream\'s own declared floor of %d' % (len(constructs), floor)
    )
    names = {c['name'] for c in constructs}
    # The two the vendored copy was missing, named so this file fails if a
    # future edit reintroduces the shape rather than only the symptom.
    assert {'reference image', 'collapsed reference image'} <= names


@pytest.mark.skipif(not inventory.available(), reason='carve-grammars submodule not present')
def test_every_construct_carries_what_the_sweep_needs():
    for construct in inventory.load_inventory():
        for key in ('name', 'sample', 'payload'):
            assert construct.get(key), '%r has no %s' % (construct, key)


SOUND = textwrap.dedent('''
    // a line comment, and a "quoted" one that is not a string
    /* a block comment */
    export const CONSTRUCTS = [
        { name: 'a', sample: 'x\\ny', payload: 'x', textmate: 'markup.a', attr: true },
        { name: "b", sample: "z", payload: "z", textmate: null, skip: { prism: 'why' } },
    ];
    export const MIN_CONSTRUCTS = 2
''')


def test_a_sound_module_reads_back_exactly():
    """The fixtures below mean nothing unless the sound case is read correctly."""
    read = inventory.read_exported_array(SOUND, 'CONSTRUCTS')
    assert read == [
        {'name': 'a', 'sample': 'x\ny', 'payload': 'x', 'textmate': 'markup.a', 'attr': True},
        {'name': 'b', 'sample': 'z', 'payload': 'z', 'textmate': None, 'skip': {'prism': 'why'}},
    ]
    assert inventory.read_exported_int(SOUND, 'MIN_CONSTRUCTS') == 2


#: (what is wrong, the module source, the words the complaint has to carry).
REFUSED = [
    (
        'a value outside the literal subset',
        "export const CONSTRUCTS = [ { name: 'a', sample: 'x'.repeat(3), payload: 'x' } ];",
        'does not understand',
    ),
    (
        'a template literal',
        'export const CONSTRUCTS = [ { name: `a`, sample: "x", payload: "x" } ];',
        'does not understand',
    ),
    (
        'an unterminated string',
        "export const CONSTRUCTS = [ { name: 'a, sample: 'x', payload: 'x' } ];",
        'unterminated',
    ),
    (
        'an array that never closes',
        "export const CONSTRUCTS = [ { name: 'a', sample: 'x', payload: 'x' },",
        'unterminated',
    ),
    (
        'the export having been renamed away',
        "export const INVENTORY = [ { name: 'a', sample: 'x', payload: 'x' } ];",
        'exports no array',
    ),
    (
        'the literal being only the head of a larger expression',
        "export const CONSTRUCTS = [ { name: 'a', sample: 'x', payload: 'x' } ].concat(MORE);",
        'not a plain array literal',
    ),
    (
        'a filter applied to the literal',
        "export const CONSTRUCTS = [ { name: 'a', sample: 'x', payload: 'x' } ]\n    .filter(Boolean);",
        'not a plain array literal',
    ),
]


@pytest.mark.parametrize('what, source, complaint', REFUSED, ids=[row[0] for row in REFUSED])
def test_the_reader_refuses_what_it_cannot_read(what, source, complaint):
    """It raises rather than returning a short list, which would read as green."""
    with pytest.raises(inventory.InventoryError) as raised:
        inventory.read_exported_array(source, 'CONSTRUCTS')
    assert complaint in str(raised.value), str(raised.value)


def test_a_plain_literal_is_still_accepted_after_the_suffix_rule():
    """The suffix rule must not reject the shape upstream actually writes."""
    for tail in (';', '', '\n\nexport const LITERALS = [];'):
        source = "export const CONSTRUCTS = [ { name: 'a', sample: 'x', payload: 'x' } ]%s" % tail
        assert len(inventory.read_exported_array(source, 'CONSTRUCTS')) == 1, tail


def test_a_short_read_is_refused_against_the_declared_floor(tmp_path):
    """Upstream declares its own floor, so a reader that loses entries fails."""
    short = tmp_path / 'constructs.js'
    short.write_text(
        "export const CONSTRUCTS = [ { name: 'a', sample: 'x', payload: 'x' } ];\n"
        'export const MIN_CONSTRUCTS = 173\n',
        encoding='utf-8',
    )
    with pytest.raises(inventory.InventoryError) as raised:
        inventory.load_inventory(short)
    assert 'floor of 173' in str(raised.value), str(raised.value)


def test_a_missing_file_is_refused_rather_than_reported_empty(tmp_path):
    with pytest.raises(inventory.InventoryError) as raised:
        inventory.load_inventory(tmp_path / 'nope.js')
    assert 'submodule is not checked out' in str(raised.value), str(raised.value)


def test_the_ci_refusal_can_actually_refuse(monkeypatch):
    """The guard above is only worth having if it fails when the file is absent."""
    # pytest's own outcomes derive from BaseException, not Exception.
    monkeypatch.setenv('CI', 'true')
    with pytest.raises(BaseException) as raised:
        refuse_skip_in_ci(False, 'the thing', 'a remedy')
    assert 'not optional' in str(raised.value), str(raised.value)
    # ... and outside CI the same absence is a skip, not a failure.
    monkeypatch.delenv('CI', raising=False)
    with pytest.raises(BaseException) as skipped:
        refuse_skip_in_ci(False, 'the thing', 'a remedy')
    assert 'a remedy' in str(skipped.value)
    assert type(raised.value) is not type(skipped.value), (
        'a refusal and a skip came back as the same outcome, so the guard cannot tell CI apart'
    )
    # Present is neither.
    assert refuse_skip_in_ci(True, 'the thing', 'a remedy') is None
