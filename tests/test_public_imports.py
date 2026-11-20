from pygments.lexers import get_lexer_by_name

from pygments_carve.lexer import CarveLexer, CsvLexer, TsvLexer


def test_the_lexers_import_from_the_public_module():
    assert type(get_lexer_by_name('carve')) is CarveLexer
    assert type(get_lexer_by_name('csv')) is CsvLexer
    assert type(get_lexer_by_name('tsv')) is TsvLexer
