"""The submodules this suite measures against are not optional in CI.

Both gates here are parametrized over a directory: the spec corpus for
``test_corpus.py`` and the shared construct inventory for
``test_constructs.py``. An absent submodule collects ZERO cases, and zero
passing cases is reported as a green tick - the same silent pass
markup-carve/carve-wasm#38 closed one repo over.

Locally an absent submodule is a convenience, so it skips. This file is
deliberately NOT under either module's ``skipif``, so in CI it is the one place
the absence is a failure.
"""

import pathlib

from coverage import refuse_skip_in_ci
import inventory

CORPUS = pathlib.Path(__file__).parent.parent / 'spec' / 'tests' / 'corpus'


def test_the_spec_corpus_is_mandatory_in_ci():
    refuse_skip_in_ci(
        CORPUS.is_dir() and any(CORPUS.glob('*.crv')),
        'the spec corpus (%s)' % CORPUS,
        'git submodule update --init',
    )


def test_the_construct_inventory_is_mandatory_in_ci():
    refuse_skip_in_ci(
        inventory.available(),
        'the carve-grammars submodule (%s)' % inventory.CONSTRUCTS_JS,
        'git submodule update --init',
    )
