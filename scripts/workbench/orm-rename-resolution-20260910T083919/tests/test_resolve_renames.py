"""Control de la resolucion por prefijo — TDD, la mitad ROJA primero.

Lo que discrimina no es «encuentra algo»: es que **no** resuelva un simbolo
que nuestro arbol no tiene bajo ninguna forma. Un emparejador que aceptara
cualquier sufijo daria verde con y sin el mecanismo.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from resolve_renames import resolve, DISSOLUTION_PREFIXES  # noqa: E402


def test_literal_name_wins_over_prefix():
    assert resolve('read', {'read', '_field_read'}) == 'read'


def test_dissolved_method_resolves_under_the_field_prefix():
    assert resolve('get_description', {'_field_get_description'}) == '_field_get_description'


def test_leading_underscore_is_not_lost():
    # `_description_depends` -> `_field_description_depends`: el guion bajo de la
    # fuente NO viaja al centro del nombre.
    assert resolve('_description_depends', {'_field_description_depends'}) \
        == '_field_description_depends'


def test_a_truly_absent_symbol_resolves_to_nothing():
    # EL QUE DISCRIMINA. `to_sql` no esta en nuestro fields.py bajo ninguna
    # forma; si el emparejador lo resolviera, su verde no mediria nada.
    assert resolve('to_sql', {'_field_read', 'condition_to_q'}) is None


def test_suffix_match_is_refused():
    # Un emparejador laxo aceptaria `x_read` para `read`. Ese es el modo de
    # fallo que convierte el instrumento en un adorno.
    assert resolve('read', {'already_read'}) is None


def test_prefixes_are_declared_not_inferred():
    assert '_field_' in DISSOLUTION_PREFIXES


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_'):
            try:
                fn()
                print(f'  ok    {nombre}')
            except AssertionError as exc:
                print(f'  FALLA {nombre} — {exc}')
                fallos += 1
    print(f'\naserciones: {sum(1 for n in globals() if n.startswith("test_"))}  fallo: {fallos}')
    raise SystemExit(1 if fallos else 0)
