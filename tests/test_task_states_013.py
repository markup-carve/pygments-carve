"""Task marker scopes for the spec 0.1.13 states."""

import pytest
from pygments.token import Name
from pygments_carve import CarveLexer


@pytest.mark.parametrize('state', ['/', '!', '_'])
def test_task_state_is_scoped_in_bullet_items(state):
    tokens = list(CarveLexer().get_tokens('- [%s] work\n' % state))
    assert (Name.Constant, '[%s]' % state) in tokens


@pytest.mark.parametrize('state', ['/', '!', '_'])
def test_task_state_is_not_scoped_in_ordered_items(state):
    tokens = list(CarveLexer().get_tokens('1. [%s] work\n' % state))
    assert (Name.Constant, '[%s]' % state) not in tokens
