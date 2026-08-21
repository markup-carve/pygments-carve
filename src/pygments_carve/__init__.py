"""Carve markup language lexer for Pygments.

Registered through the ``pygments.lexers`` entry point, so installing this
package is enough - ``pygments.lexers.get_lexer_by_name('carve')`` and the
``carve`` / ``crv`` fence words in MkDocs, Sphinx, zensical and any other
Pygments consumer start working with no further configuration.
"""

from pygments_carve.lexer import CarveLexer

__all__ = ['CarveLexer']
__version__ = '0.1.0'
