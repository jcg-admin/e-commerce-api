"""``scripts/port_order.py`` — el censo que ordena el porte de una raiz.

El guion responde dos preguntas distintas con **un solo** instrumento, y ahi
estaba su ceguera: para enumerar los nodos de la referencia basta con clases y
funciones —son las unidades que se ordenan—, pero para responder «¿ya esta
aqui?» eso deja fuera todo simbolo que este arbol declare de otra forma.

Medido antes del arreglo: de los 27 que la columna ``aqui`` daba por ausentes,
**12 existian** —``Boolean``, ``Char``, ``Date``, ``Datetime``, ``Field``,
``Float``, ``Integer``, ``Many2oneReference``, ``Model``, ``Reference``,
``Selection``, ``Text``—, declarados como **asignacion** de nivel superior
(``Boolean = make_dispatcher(...)``) o re-exportados con un ``import``. Es el
sub-patron C de ``metrica-decide-la-conclusion.md``: el instrumento mide la
FORMA de la declaracion y se concluye sobre la PRESENCIA del simbolo.

Los casos de ``TestDeclaredHere`` se escribieron ANTES del arreglo y fallaban
con el instrumento viejo.
"""
import importlib.util
import pathlib
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parents[3] / 'scripts' / 'orden_de_porte.py'
_spec = importlib.util.spec_from_file_location('orden_de_porte', _PATH)
port_order = importlib.util.module_from_spec(_spec)
sys.modules['orden_de_porte'] = port_order
_spec.loader.exec_module(port_order)


@pytest.fixture
def root(tmp_path):
    """Una raiz sintetica con las cuatro formas de declarar un simbolo."""
    (tmp_path / 'a.py').write_text(
        'from otro import Reexported\n'
        'from otro import Renamed as Alias\n'
        '\n'
        'Assigned = make_dispatcher("Assigned")\n'
        'Annotated: int = 3\n'
        '\n'
        '\n'
        'class Klass:\n'
        '    def method_not_top_level(self):\n'
        '        pass\n'
        '\n'
        '\n'
        'def function():\n'
        '    inner_not_top_level = 1\n'
        '    return inner_not_top_level\n'
    )
    return tmp_path


class TestTopLevelSymbols:
    """Enumera los NODOS que se ordenan: clases y funciones, nada mas.

    Este lado NO cambia. Meter aqui las asignaciones cambiaria el grafo de la
    referencia —entrarian sus constantes de modulo— y con el los niveles, que
    es lo que el guion existe para calcular.
    """

    def test_it_takes_the_class_and_the_function(self, root):
        assert set(port_order.top_level_symbols(root)) == {'Klass', 'function'}

    def test_it_ignores_what_is_not_top_level(self, root):
        found = port_order.top_level_symbols(root)
        assert 'method_not_top_level' not in found
        assert 'inner_not_top_level' not in found


class TestDeclaredHere:
    """Responde «¿el nombre ya se declara aqui?» — CUALQUIER forma cuenta."""

    def test_it_takes_the_class_and_the_function(self, root):
        here = port_order.declared_here(root)
        assert {'Klass', 'function'} <= here

    def test_it_takes_the_plain_assignment(self, root):
        """``Boolean = make_dispatcher(...)`` es el caso real que lo destapo."""
        assert 'Assigned' in port_order.declared_here(root)

    def test_it_takes_the_annotated_assignment(self, root):
        assert 'Annotated' in port_order.declared_here(root)

    def test_it_takes_what_the_module_re_exports(self, root):
        """Un simbolo importado esta disponible desde esta raiz: cuenta."""
        assert 'Reexported' in port_order.declared_here(root)

    def test_the_alias_counts_by_its_local_name(self, root):
        here = port_order.declared_here(root)
        assert 'Alias' in here
        assert 'Renamed' not in here

    def test_it_still_ignores_what_is_not_top_level(self, root):
        here = port_order.declared_here(root)
        assert 'method_not_top_level' not in here
        assert 'inner_not_top_level' not in here

    def test_it_sees_strictly_more_than_the_node_enumeration(self, root):
        """El control: si las dos funciones dieran lo mismo, el arreglo no
        existiria y estos casos pasarian por accidente."""
        nodes = set(port_order.top_level_symbols(root))
        here = port_order.declared_here(root)
        assert nodes < here

    def test_the_missing_root_is_empty_not_an_error(self, tmp_path):
        assert port_order.declared_here(tmp_path / 'no-existe') == set()


class TestAgainstTheRealTree:
    """Control positivo sobre el arbol real, no sobre una raiz fabricada."""

    def test_the_dispatcher_declared_types_are_seen(self):
        here = port_order.declared_here(
            port_order.REPO.joinpath(*port_order.OUR_SUBPATH))
        # Los doce que el instrumento viejo daba por ausentes.
        assert {'Boolean', 'Char', 'Date', 'Datetime', 'Field', 'Float',
                'Integer', 'Many2oneReference', 'Model', 'Reference',
                'Selection', 'Text'} <= here

    def test_what_is_genuinely_absent_stays_absent(self):
        """Y el instrumento arreglado NO absuelve a los que faltan de verdad.

        ``Registry`` salio de esta lista al portarse como clase (tarea #342),
        y su salida es el control funcionando: el caso se puso rojo el mismo
        pase en que la clase aterrizo. ``BaseModel`` salio por lo mismo en
        **TASK-API-0397**. Los tres que quedan siguen sin declararse en
        ``src/orm/`` bajo ninguna forma.
        """
        here = port_order.declared_here(
            port_order.REPO.joinpath(*port_order.OUR_SUBPATH))
        assert not ({'MetaModel', 'add_to_registry',
                     'setup_model_classes'} & here)

    def test_the_ported_registry_is_seen(self):
        """El control en el otro sentido: lo que SI se porto, se ve.

        Sin este caso, borrar un nombre de la lista de arriba pasaria verde
        tanto si el simbolo se porto como si nadie lo miro.
        """
        here = port_order.declared_here(
            port_order.REPO.joinpath(*port_order.OUR_SUBPATH))
        assert 'Registry' in here
        # Y el que salio de la lista de arriba en TASK-API-0397: sin este
        # renglon, quitar un nombre de aquella lista pasaria verde tanto si el
        # simbolo aterrizo como si alguien lo borro por comodidad.
        assert 'BaseModel' in here
