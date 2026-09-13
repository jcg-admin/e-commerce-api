"""La suite del inventario de la referencia.

Defiende al AGREGADOR, no al extractor: ``declared_symbols``, ``signature_of``
y ``body_class`` ya tienen su suite en el run del censo de presencia
(``orm-symbol-presence-census-20260910T175850``), y este run los importa en vez
de reescribirlos. Lo que aqui se prueba es lo que este instrumento anade — la
unidad CRUDA con su clase `owner`, el desglose por clase, y que una raiz ausente
emita cero en vez de fabricar.

Todos los sujetos son REALES del arbol de la referencia. Un sujeto fabricado
confirmaria el encuadre de quien escribio el instrumento.
"""
import importlib.util
import os
import pathlib
import sys

import pytest

RUN_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO = RUN_DIR.parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


inventory_module = _load(
    '_inventory_reference_orm', RUN_DIR / 'inventory_reference_orm.py')
roots = _load('_inventory_roots', REPO / 'scripts/reference_roots.py')

ORM_19C = roots.TREE_ROOTS['odoo19c'] / 'odoo' / 'orm'


@pytest.fixture(scope='module')
def orm():
    if not ORM_19C.is_dir():
        pytest.skip(f'la raiz de la referencia no esta montada: {ORM_19C}')
    return inventory_module.inventory(ORM_19C)


def _file(report, name):
    for entry in report['files']:
        if entry['name'] == name:
            return entry
    raise AssertionError(f'{name} no esta en el inventario')


def test_raw_exceeds_unique_where_a_name_repeats_across_classes(orm):
    """La unidad es la OCURRENCIA, no el nombre.

    ``fields_relational.py`` declara ``setup_nonrelated`` en cuatro clases. Un
    agregador que deduplicara por nombre —el defecto que este eje corrige—
    reportaria una sola. Es el discriminador de la suite.
    """
    entry = _file(orm, 'fields_relational.py')
    assert entry['raw'] > entry['unique']
    owners = [owner['name'] for owner in entry['classes']
              for method in owner['methods']
              if method['name'] == 'setup_nonrelated']
    assert len(owners) == 4, owners
    assert len(set(owners)) == 4, 'las cuatro son clases distintas'


def test_a_class_carries_its_own_methods(orm):
    """El desglose es POR CLASE: ``BaseModel`` declara 194 metodos."""
    entry = _file(orm, 'models.py')
    base = [owner for owner in entry['classes'] if owner['name'] == 'BaseModel']
    assert len(base) == 1
    assert len(base[0]['methods']) == 194


def test_an_absent_root_yields_zero_and_does_not_fabricate():
    """``odoo/orm`` NO existe en 18c — su ORM vive plano en ``odoo/``.

    El agregador emite cero archivos y cero simbolos. Un cero fabricado seria
    indistinguible de «medi y no hay», que es el sub-patron D.
    """
    ausente = roots.TREE_ROOTS['odoo18c'] / 'odoo' / 'orm'
    assert not ausente.is_dir(), 'la premisa del caso cambio: 18c ya trae odoo/orm'
    report = inventory_module.inventory(ausente)
    assert report['files'] == []
    assert report['totals']['files'] == 0
    assert report['totals']['symbols'] == 0
    assert report['root_exists'] is False


def test_the_signature_travels_with_the_function(orm):
    """Cada funcion lleva su firma — es el tercer eje del encargo."""
    entry = _file(orm, 'utils.py')
    parse = [f for f in entry['functions'] if f['name'] == 'parse_field_expr']
    assert len(parse) == 1
    assert parse[0]['signature']['params'] == ['field_expr']


def test_totals_are_the_sum_of_the_files(orm):
    """El total no se recuenta por su cuenta: se compone de las filas."""
    total = orm['totals']
    assert total['files'] == len(orm['files'])
    assert total['classes'] == sum(len(e['classes']) for e in orm['files'])
    assert total['module_functions'] == sum(len(e['functions']) for e in orm['files'])
    assert total['methods'] == sum(
        len(c['methods']) for e in orm['files'] for c in e['classes'])
    assert total['symbols'] == (
        total['classes'] + total['module_functions'] + total['methods'])


# --- la sonda de cuerpos `stub` ------------------------------------------
#
# Se prueba aparte porque defiende OTRA afirmacion: no cuantos simbolos hay,
# sino QUE es un cuerpo vacio. El manifiesto llego a decir que «la mayoria son
# metodos abstractos», sin medirlo; estas dos aserciones son lo que impide que
# esa frase vuelva.

stub_probe = _load('_probe_stub_bodies', RUN_DIR / 'probes/probe_stub_bodies.py')


@pytest.fixture(scope='module')
def stubs():
    if not ORM_19C.is_dir():
        pytest.skip(f'la raiz de la referencia no esta montada: {ORM_19C}')
    return stub_probe.classify('odoo19c')


def test_an_overload_is_not_an_empty_implementation(stubs):
    """``typing.overload`` declara una firma; su cuerpo es `...` por el lenguaje.

    El sujeto es real y esta duplicado a proposito en la fuente: ``mapped`` se
    declara dos veces en ``models.py`` con ``@typing.overload`` y una tercera
    con cuerpo. Contar esas dos como metodos sin implementar es medir el significante.
    """
    mapped = [s for s in stubs['stubs']
              if s['file'] == 'models.py' and s['name'] == 'mapped']
    assert len(mapped) == 2
    assert {s['bucket'] for s in mapped} == {'overload'}
    assert all('typing.overload' in s['decorators'] for s in mapped)


def test_the_plain_bucket_separates_abstract_base_from_empty_hook(stubs):
    """Un `stub` sin decorador se discrimina por si alguien lo implementa.

    ``Domain._to_sql`` es base de jerarquia — hay subclases con cuerpo.
    ``DummyRLock.acquire`` no: es un no-op deliberado, y nadie en el paquete
    declara ese nombre con cuerpo. Sin esta separacion los dos casos se
    publican como la misma cosa.
    """
    by_key = {(s['file'], s['owner'], s['name']): s for s in stubs['stubs']}
    base = by_key[('domains.py', 'Domain', '_to_sql')]
    hook = by_key[('registry.py', 'DummyRLock', 'acquire')]
    assert base['bucket'] == hook['bucket'] == 'plain'
    assert base['overridden_elsewhere']
    assert hook['overridden_elsewhere'] == []
    assert (stubs['plain_implemented_elsewhere']
            + stubs['plain_not_implemented_in_package']
            == stubs['by_bucket']['plain'])
