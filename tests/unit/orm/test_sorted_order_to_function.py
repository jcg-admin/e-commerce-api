"""``BaseModel._sorted_order_to_function`` — mitad ROJA de TASK-API-0400.

Porta ``odoo19c: odoo/orm/models.py:6294-6344``. Es lo que ``sorted()`` exige
para sus dos ramas que hoy levantan ``NotImplementedError``: la de cadena
(``records.sorted('name DESC, id')``) y la de ``None``, que ordena por
``_order`` del modelo.

El flujo de la fuente, leído antes de la primera linea
======================================================

``sorted`` (``:6262-6291``) hace tres cosas y ninguna mas::

    if len(self) < 2: return self
    if isinstance(key, str):  key = self._sorted_order_to_function(key)
    elif key is None:         key = self._sorted_order_to_function(self._order)
    ids = tuple(item.id for item in sorted(self, key=key, reverse=reverse))
    return self.__class__(self.env, ids, self._prefetch_ids)

O sea: ``_sorted_order_to_function`` **no ordena**. Construye la ``key`` que
el ``sorted`` de CPython consume — y ahi el stack lo trae hecho: el orden
estable de Timsort y el protocolo de comparacion son de CPython, no nuestros.
Lo que hay que construir es el ENVOLTORIO que hace comparables valores de
tipos mixtos con ``None``, y eso es ``ReversibleComparator`` (``:7066-7094``),
ya portado.

Las cinco ramas de ``order_to_function``, medidas en la fuente
---------------------------------------------------------------

1. ``regex_order`` no casa  -> ``ValueError(f"Invalid order {order!r} to sort")``
2. ``many2one`` sin propiedad, o con ``.id``  -> RECURRE al comodelo con su
   ``_order``, y se protege de un ciclo con ``__m2o_order_seen_sorted`` en el
   contexto: si el campo ya se vio, devuelve ``lambda _: None``.
3. otro campo relacional -> ``ValueError("Invalid order on relational field")``
4. ``boolean`` -> ``field.expression_getter(field_expr)`` tal cual: un
   booleano NO se normaliza a ``None``, porque ``False`` es un valor legitimo
   que debe ordenar antes que ``True``.
5. el resto -> el mismo getter, pero ``False`` se convierte en ``None``, que
   es como la fuente representa "sin valor" fuera del booleano.

La regla de los nulos, que es la parte que no se adivina::

    if nulls: nulls_first = nulls == 'NULLS FIRST'
    else:     nulls_first = reverse

Sin ``NULLS`` explicito, el nulo va **primero si y solo si** el orden es
descendente. Es la convencion de PostgreSQL, y la fuente la reproduce en
memoria para que ``sorted()`` y ``search()`` no discrepen.

*Metrica:* el orden de los ids que devuelve ``sorted`` sobre un recordset con
la cache sembrada a mano.
*Ciega a:* si el mismo orden sale de la base de datos — eso lo decide
``_order_to_sql``, que es otro simbolo y otra tarea.
"""
import pytest

import fields
from django.db import models as django_models
from orm.environments import Environment
from orm.models import BaseModel


class SortParentProbe(BaseModel):
    """El comodelo del ``many2one``: su ``_order`` es el que la rama 2 usa."""

    _name = 'orm.sort.parent.probe'
    _description = "Sort parent probe"
    _order = 'name'

    name = fields.Char('Name')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_sort_parent_probe'


class SortProbe(BaseModel):
    """Sonda de orden: un texto, un entero, un booleano y un ``many2one``."""

    _name = 'orm.sort.probe'
    _description = "Sort probe"
    _order = 'label'

    label = fields.Char('Label')
    rank = fields.Integer('Rank')
    flag = fields.Boolean('Flag')
    parent_id = fields.Many2one(
        'base.SortParentProbe', on_delete=django_models.PROTECT,
        related_name='children', null=True, string='Parent')
    tags = fields.Many2many('base.SortParentProbe', related_name='tagged',
                            blank=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_sort_probe'


@pytest.fixture
def ambient():
    """El entorno es AMBIENTE, no fresco — y la cache de campo vive en la
    transaccion, no en el objeto.

    Medido: ``Environment() is Environment()`` da ``True``, y tambien
    ``a.transaction is b.transaction``. ``Field._insert_cache`` usa
    ``setdefault`` —fiel a ``odoo19c: odoo/orm/fields.py:1595``—, asi que una
    segunda siembra del MISMO id se ignora en silencio: sin este reset, un caso
    lee el valor que sembro el caso anterior y el rojo no dice eso.
    ``invalidate_all`` es el unico reset real.
    """
    env = Environment()
    env.invalidate_all()
    return env


def seed(model, ambient, values_by_id, field_name):
    """Siembra la cache del campo y devuelve el recordset de esos ids.

    La sonda es ``managed = False``: no hay tabla que leer, asi que el valor
    entra por ``Field._insert_cache``, que es la MISMA via por la que
    ``_fetch_query`` lo deja (``:3930``). No es un atajo del test: es el
    camino que la fuente usa para poblar la cache.
    """
    ids = tuple(values_by_id)
    records = model._from_ids(ambient, ids, ids)
    field = model._meta.get_field(field_name)
    field._insert_cache(records, [values_by_id[i] for i in ids])
    return records


class TestTheStringBranch:

    def test_it_orders_by_a_plain_field_name(self, ambient):
        records = seed(SortProbe, ambient, {7: 'c', 18: 'a', 33: 'b'}, 'label')
        assert records.sorted('label').ids == [18, 33, 7]

    def test_desc_reverses_it(self, ambient):
        records = seed(SortProbe, ambient, {7: 'c', 18: 'a', 33: 'b'}, 'label')
        assert records.sorted('label DESC').ids == [7, 33, 18]

    def test_an_invalid_order_raises(self, ambient):
        records = seed(SortProbe, ambient, {7: 'c', 18: 'a'}, 'label')
        with pytest.raises(ValueError, match='Invalid order'):
            records.sorted('label ASCENDING')


class TestTheNoneBranch:

    def test_none_uses_the_model_order(self, ambient):
        # ``_order = 'label'`` en la sonda: sin ``key`` ordena por ahi.
        records = seed(SortProbe, ambient, {7: 'c', 18: 'a', 33: 'b'}, 'label')
        assert records.sorted().ids == [18, 33, 7]


class TestTheNullRule:

    def test_without_nulls_the_null_goes_last_when_ascending(self, ambient):
        # ``nulls_first = reverse`` y ``reverse`` es False -> el nulo al final.
        records = seed(SortProbe, ambient, {7: 'b', 18: False, 33: 'a'}, 'label')
        assert records.sorted('label').ids == [33, 7, 18]

    def test_without_nulls_the_null_goes_first_when_descending(self, ambient):
        records = seed(SortProbe, ambient, {7: 'b', 18: False, 33: 'a'}, 'label')
        assert records.sorted('label DESC').ids == [18, 7, 33]

    def test_nulls_last_overrides_the_descending_default(self, ambient):
        records = seed(SortProbe, ambient, {7: 'b', 18: False, 33: 'a'}, 'label')
        assert records.sorted('label DESC NULLS LAST').ids == [7, 33, 18]

    def test_nulls_first_overrides_the_ascending_default(self, ambient):
        records = seed(SortProbe, ambient, {7: 'b', 18: False, 33: 'a'}, 'label')
        assert records.sorted('label NULLS FIRST').ids == [18, 33, 7]


class TestTheBooleanBranchIsNotNormalised:

    def test_false_orders_before_true_and_is_not_a_null(self, ambient):
        # Rama 4: el booleano NO pasa por la normalizacion a ``None``. Si
        # pasara, ``False`` se volveria nulo y con orden ascendente iria al
        # FINAL — justo al reves. El caso DISCRIMINA esa rama.
        records = seed(SortProbe, ambient, {7: True, 18: False, 33: True}, 'flag')
        assert records.sorted('flag').ids[0] == 18


class TestTheRelationalBranches:

    @pytest.mark.xfail(strict=True, reason=(
        'TASK-API-0402 — ``parent_id`` sirve un ``ForeignKeyDeferredAttribute``, '
        'y la guarda de instalacion de ``FieldDescriptor`` es exacta por tipo: '
        'no lo sustituye. El acceso cae al camino de Django y pide base. La '
        'recursion al comodelo esta portada y verificada por lectura; lo que '
        'falta es que la fila que Django construye lleve la terna del '
        'recordset, que es el alcance de esa tarea.'))
    def test_a_many2one_recurses_into_the_comodel_order(self, ambient):
        parents = seed(SortParentProbe, ambient, {1: 'zeta', 2: 'alfa'}, 'name')
        assert parents.ids == [1, 2]
        records = seed(SortProbe, ambient, {7: 1, 18: 2}, 'parent_id')
        # El comodelo ordena por ``name``: alfa (2) antes que zeta (1), asi
        # que el registro 18 —cuyo padre es 2— va primero.
        assert records.sorted('parent_id').ids == [18, 7]

    def test_a_non_many2one_relational_field_raises(self, ambient):
        records = seed(SortProbe, ambient, {7: 'a', 18: 'b'}, 'label')
        with pytest.raises(ValueError, match='relational'):
            records.sorted('tags')


class TestSeveralTerms:

    def test_two_terms_break_the_tie(self, ambient):
        records = seed(SortProbe, ambient, {7: 'a', 18: 'a', 33: 'b'}, 'label')
        ranks = SortProbe._meta.get_field('rank')
        ranks._insert_cache(records, [2, 1, 0])
        assert records.sorted('label, rank').ids == [18, 7, 33]
