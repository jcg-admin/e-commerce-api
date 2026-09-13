"""Control del censo de PRESENCIA con firma — TDD, la mitad ROJA primero.

Lo que discrimina no es «cuenta simbolos»: los cinco instrumentos que ya
existen cuentan. Lo que ninguno mide es si el simbolo presente tiene CUERPO,
y ese criterio de cierre —«0 ausentes»— lo satisface un arbol de firmas
vacias. Asi que la columna que este control tiene que defender es ``stub``.

Los sujetos son REALES y del arbol, no fabricados: un caso inventado por quien
escribio el detector hereda su encuadre y confirma su propia lectura.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from census_symbol_presence import (  # noqa: E402
    body_class, signature_of, declared_symbols, REPO,
)


def _symbol(relative_path, name):
    """El registro de un simbolo real del arbol, por nombre."""
    found = [s for s in declared_symbols(REPO / relative_path) if s['name'] == name]
    assert found, f'{name} ya no existe en {relative_path}: el control perdio su sujeto'
    return found[0]


# --- la columna que discrimina: stub vs sustantivo -------------------------

def test_a_pass_only_body_is_a_stub():
    # src/orm/registry.py — el cerrojo nulo: `def acquire(self): pass`
    assert _symbol('src/orm/registry.py', 'acquire')['body'] == 'stub'


def test_a_docstring_only_body_is_a_stub():
    # src/orm/fields.py — «Verbatim: la fuente no hace nada aqui»
    assert _symbol('src/orm/fields.py', '_field_setup_nonrelated')['body'] == 'stub'


def test_a_bare_not_implemented_body_is_a_stub():
    # src/orm/domains.py — `def __eq__(self): raise NotImplementedError`
    assert _symbol('src/orm/domains.py', '__eq__')['body'] == 'stub'


def test_a_conditional_not_implemented_is_substantive():
    # EL QUE DISCRIMINA. src/orm/decorators.py `depends` levanta
    # NotImplementedError DENTRO de un `elif`: un detector por subcadena lo
    # llamaria stub y borraria de la medicion una guarda con logica real.
    assert _symbol('src/orm/decorators.py', 'depends')['body'] == 'substantive'


def test_a_super_only_body_is_substantive():
    # src/orm/registry.py:844 — `super().__init__('_constrains')`. Delegar NO
    # es no hacer nada: el argumento es la decision que el cuerpo toma.
    registry = declared_symbols(REPO / 'src/orm/registry.py')
    delegating = [s for s in registry
                  if s['name'] == '__init__' and s['lineno'] == 844]
    assert delegating, 'el __init__ delegante de registry.py:844 movio de linea'
    assert delegating[0]['body'] == 'substantive'


# --- el otro eje nuevo: la firma ------------------------------------------

def test_signature_drops_the_receiver():
    # `self` / `cls` no son parte del contrato: comparar con ellos haria que un
    # metodo y su equivalente de modulo nunca casaran.
    sig = _symbol('src/orm/registry.py', 'acquire')['signature']
    assert sig['params'] == []


def test_signature_records_defaults_as_flags_not_values():
    # El VALOR del default es cuerpo; lo que el contrato declara es que el
    # parametro es opcional. Guardar el valor haria fallar el emparejamiento
    # ante una constante renombrada.
    import ast
    node = ast.parse('def probe(a, b=1, *rest, key=None, **extra): pass').body[0]
    sig = signature_of(node)
    assert sig['params'] == ['a', 'b']
    assert sig['has_default'] == [False, True]
    assert sig['vararg'] == 'rest'
    assert sig['kwonly'] == ['key']
    assert sig['kwarg'] == 'extra'


def test_body_class_is_computed_from_the_node_not_the_text():
    import ast
    stub = ast.parse('def f():\n    """doc."""\n').body[0]
    assert body_class(stub) == 'stub'
    live = ast.parse('def f():\n    return 1\n').body[0]
    assert body_class(live) == 'substantive'
