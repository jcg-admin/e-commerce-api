"""``scripts/census_class.py`` — el censo de una clase por AST.

El defecto que cierra
=====================

El procedimiento que ``atributos-de-clase-de-modelo.md`` publica como «el
comando» recorre **solo** ``ast.Assign``. La regla gobierna 24 atributos de
ORM —``_name``, ``_description``, ``_order``, ``_table``, ``_inherit``…— y
**los 28 que ``BaseModel`` declara son ``ast.AnnAssign``**: asignacion
anotada, que es otro nodo. Medido sobre ``odoo19c: odoo/orm/models.py``::

    BaseModel: Assign=3  AnnAssign=28  total=31
      Assign   : __slots__, id, display_name
      AnnAssign: pool, _fields__, _fields, _auto, _register, _abstract, ...

Corrido con el instrumento viejo contra la clase que DECLARA el contrato, el
censo publica **3** atributos y ninguno de los 24 que la regla legisla.

La ceguera NO es general, y decirlo importa: medido sobre tres modelos de
addon —``stock_picking.py``, ``sale_order.py``, ``res_company.py``— hay
**236 ``Assign`` y 0 ``AnnAssign``**. La forma anotada vive en el NUCLEO
(``odoo/orm/models.py`` 28, ``odoo/orm/fields.py`` 49). O sea: el comando
funciona para el caso corriente —portar un modelo de addon— y falla
exactamente cuando se va a leer CUAL ES el contrato.

*Metrica:* sentencias del cuerpo de clase por tipo de nodo AST, por archivo.
*Ciega a:* un atributo instalado fuera del cuerpo de la clase
(``setattr(cls, ...)``, un decorador, una metaclase) — ninguno de los tres
aparece como sentencia del cuerpo y por tanto ningun recorrido de este tipo
los ve.
"""
import ast
import importlib.util
import os
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_PATH = _ROOT / 'scripts' / 'census_class.py'
_spec = importlib.util.spec_from_file_location('census_class', _PATH)
census_class = importlib.util.module_from_spec(_spec)
sys.modules['census_class'] = census_class
_spec.loader.exec_module(census_class)

sys.path.insert(0, str(_ROOT / 'scripts'))
import reference_roots  # noqa: E402

REFERENCE_MODELS = pathlib.Path(reference_roots.tree('odoo19c')) / 'odoo/orm/models.py'


@pytest.fixture(scope='module')
def base_model():
    if not REFERENCE_MODELS.is_file():
        pytest.skip(f'la referencia no esta montada: {REFERENCE_MODELS}')
    return census_class.census(REFERENCE_MODELS, ['BaseModel'])['BaseModel']


class TestTheAnnotatedFormIsSeen:

    def test_base_model_declares_thirty_one_class_attributes(self, base_model):
        # Control POSITIVO real de la referencia, no fabricado: 3 + 28.
        assert len(base_model.attributes) == 31

    def test_the_three_plain_assignments_are_there(self, base_model):
        names = [a.name for a in base_model.attributes]
        assert {'__slots__', 'id', 'display_name'} <= set(names)

    def test_every_orm_attribute_the_rule_governs_is_annotated(self, base_model):
        # Estos son los que el instrumento viejo NO veia. Si alguien revierte
        # el recorrido a solo ``Assign``, este caso cae y los otros dos no:
        # DISCRIMINA la correccion, no solo la presencia del guion.
        annotated = {a.name for a in base_model.attributes if a.annotated}
        assert {'_name', '_description', '_order', '_table', '_inherit',
                '_rec_name', '_check_company_auto', '_parent_store'} <= annotated

    def test_the_plain_ones_are_not_marked_annotated(self, base_model):
        plain = {a.name for a in base_model.attributes if not a.annotated}
        assert plain == {'__slots__', 'id', 'display_name'}


class TestItAlsoSeesTheOrdinaryAddonForm(object):

    def test_a_plain_assignment_in_an_addon_model_is_seen(self, tmp_path):
        # La forma corriente: ``_name = 'x'`` sin anotacion. El instrumento
        # nuevo no puede perderla al ganar la anotada.
        source = tmp_path / 'addon_model.py'
        source.write_text(
            "class StockPicking:\n"
            "    _name = 'stock.picking'\n"
            "    _description = 'Transfer'\n")
        got = census_class.census(source, ['StockPicking'])['StockPicking']
        assert [a.name for a in got.attributes] == ['_name', '_description']
        assert not any(a.annotated for a in got.attributes)


class TestMethodsAndRange:

    def test_it_reports_the_methods_too(self, base_model):
        assert 'browse' in {m.name for m in base_model.methods}

    def test_the_range_comes_from_the_ast_node(self, base_model):
        assert base_model.lineno < base_model.end_lineno
