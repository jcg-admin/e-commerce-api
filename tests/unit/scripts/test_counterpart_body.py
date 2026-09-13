"""Control del EMPAREJAMIENTO del motor de comparacion de cuerpos.

``compare()`` consume ``methods_of``, que devuelve ``{nombre: nodo}`` sobre los
metodos declarados en clase. Eso tiene dos consecuencias, y la segunda es peor
que la primera:

1. **Ceguera** — no ve la funcion de modulo, que en ``odoo/tools`` es la forma
   dominante. Medido sobre ``src/orm`` + ``src/tools``: 585 pares visibles de
   826 emparejables, 70.8 % de cobertura.
2. **Comparacion equivocada en silencio** — el dict colapsa por nombre, asi que
   con clases hermanas gana la ultima de cada lado. Nada avisa: el gate compara
   dos cuerpos que no son contraparte y publica su veredicto igual.

Los casos usan positivos REALES del arbol, no fabricados
(``hallazgo-abierto-genera-sucesor.md``): quien escribe el instrumento no puede
validarlo con su propio encuadre.

Medicion que los sostiene: ``scripts/workbench/orm-body-axis-blindness-20260911T021435/``.
"""
import importlib.util
import pathlib
import sys

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parents[3] / 'scripts'


def _load(name):
    """Carga un guion de ``scripts/`` por ruta: no es un paquete importable."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


counterpart_body = _load('counterpart_body')
#: El unico eje vivo sobre el motor. Se carga arriba, no dentro del caso:
#: `no-lazy-imports.md` prohibe el import en cuerpo de funcion.
check_write_path = _load('check_write_path')

#: Positivo real: tres clases declaran ``__init__`` de nuestro lado y una sola
#: del lado de la fuente. ``methods_of`` retiene ``PropertiesDefinition`` (la
#: ultima) y la empareja contra ``Property`` de la fuente — mientras nuestro
#: propio ``Property.__init__`` existe y es la contraparte correcta.
MISPAIRED = pathlib.Path('src/orm/fields_properties.py')

#: Positivo real de la ceguera: ``src/tools/sql.py`` declara sus escritores
#: como funcion de modulo. El eje del camino de escritura no ve NINGUNO.
MODULE_LEVEL = pathlib.Path('src/tools/sql.py')

#: Positivo real de la duena divergente: nuestro puerto disuelve ``BaseModel``
#: en mixins, asi que ``create`` vive en ``DefaultGetMixin`` y en la fuente en
#: ``BaseModel``. Emparejar SOLO por duena perderia estos pares.
DISSOLVED_BASE = pathlib.Path('src/orm/models.py')


def _pairs(path):
    reference = counterpart_body.counterpart(path)
    assert reference is not None and reference.is_file(), path
    return {p.key: p for p in counterpart_body.pair_declarations(path, reference)}


class TestTheCollapseByNameComparesTheWrongBody:
    """El defecto que el emparejamiento nuevo cierra, medido antes de cerrarlo."""

    def test_todays_collapse_keeps_a_different_owner_on_each_side(self):
        # Este caso describe el ESTADO ACTUAL de ``methods_of`` y seguira
        # verde tras el arreglo: es la evidencia de que el defecto existia,
        # no el criterio nuevo.
        reference = counterpart_body.counterpart(MISPAIRED)
        ours = counterpart_body.methods_of(MISPAIRED)['__init__']
        theirs = counterpart_body.methods_of(reference)['__init__']
        our_owner = {d.owner for d in counterpart_body.declarations_of(MISPAIRED)
                     if d.kind == 'function' and d.lineno == ours.lineno}
        their_owner = {d.owner for d in counterpart_body.declarations_of(reference)
                       if d.kind == 'function' and d.lineno == theirs.lineno}
        assert our_owner == {'PropertiesDefinition'}, our_owner
        assert their_owner == {'Property'}, their_owner

    def test_the_new_pairing_puts_property_against_property(self):
        pair = _pairs(MISPAIRED)['Property.__init__']
        assert pair.route == counterpart_body.BY_OWNER
        # Nuestro ``Property.__init__``, no el de ``PropertiesDefinition``.
        assert pair.ours.lineno != counterpart_body.methods_of(
            MISPAIRED)['__init__'].lineno

    def test_the_sibling_gets_its_own_pair_or_none_at_all(self):
        # ``PropertiesDefinition`` no tiene contraparte con ese nombre en la
        # fuente, asi que NO debe aparecer emparejada con nada.
        assert 'PropertiesDefinition.__init__' not in _pairs(MISPAIRED)


class TestTheModuleLevelFunctionIsPaired:
    """La forma dominante de ``odoo/tools`` entra al universo."""

    @pytest.mark.parametrize('symbol', ['create_column', 'drop_constraint'])
    def test_a_module_writer_is_now_visible(self, symbol):
        pair = _pairs(MODULE_LEVEL)[symbol]
        assert pair.route == counterpart_body.MODULE_LEVEL
        assert pair.owner == ''

    def test_todays_extractor_does_not_see_it(self):
        # Control de la ceguera: el instrumento viejo no lo tiene.
        assert 'create_column' not in counterpart_body.methods_of(MODULE_LEVEL)


class TestTheDissolvedBaseKeepsItsPairs:
    """Emparejar SOLO por duena perderia los 63 pares del nucleo del ORM."""

    @pytest.mark.parametrize('symbol', ['create', 'copy'])
    def test_the_mixin_still_pairs_against_base_model(self, symbol):
        matched = [p for p in _pairs(DISSOLVED_BASE).values()
                   if p.name == symbol]
        assert matched, symbol
        assert matched[0].route == counterpart_body.BY_NAME


class TestTheScopePublishesEachRoute:
    """Un denominador que no dice por que via emparejo no es auditable."""

    def test_the_three_routes_sum_to_the_compared_pairs(self):
        _, scope = check_write_path.scan_with_scope(
            list(counterpart_body.tree_files(['src/orm', 'src/tools'])))
        assert (scope.pairs_by_owner + scope.pairs_module_level
                + scope.pairs_by_name) == scope.pairs_compared, scope


class TestTheKeyCarriesTheOwner:
    """Sin la duena, dos hermanas comparten entrada de baseline."""

    def test_a_class_symbol_is_keyed_by_owner_and_name(self):
        finding = counterpart_body.Finding(
            path='src/orm/models.py', symbol='create', owner='DefaultGetMixin',
            ours='a', theirs='b', direction='x')
        assert finding.key == 'src/orm/models.py::DefaultGetMixin.create'

    def test_a_module_symbol_keeps_the_bare_name(self):
        finding = counterpart_body.Finding(
            path='src/tools/sql.py', symbol='create_column', owner='',
            ours='a', theirs='b', direction='x')
        assert finding.key == 'src/tools/sql.py::create_column'
