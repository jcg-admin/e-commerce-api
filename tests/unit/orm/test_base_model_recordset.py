"""El núcleo del recordset de ``BaseModel`` — mitad ROJA de TASK-API-0397.

Porta el contrato que ``odoo19c: odoo/orm/models.py:334-7004`` declara en
``BaseModel`` (194 métodos declarados; este archivo cubre los 36 del núcleo
del recordset: 22 del protocolo más los dunder). Cada aserción se escribió
contra el cuerpo de la referencia leído verbatim en el pase que la produjo,
no de memoria.

Arquitectura — la decidió el ejecutor, no este archivo
=======================================================

:ref:`h-api-1083` dejó **tres** formas candidatas a decisión del ejecutor:
extender ``AccessQuerySet``, **construir un BaseModel propio del que deriven
los modelos portados**, o repartir por mixins. La directiva elige la segunda.
Por eso ``BaseModel`` es un modelo abstracto de Django del que cuelga
``TimeStampedModel``, y un recordset es una instancia de la propia clase del
modelo — igual que en la referencia, donde la clase del modelo *es* la clase
del recordset (``odoo19c: odoo/orm/environments.py`` — ``__getitem__``
devuelve ``self.registry[model_name](self, (), ())``).

Divergencia de mecanismo, MEDIDA y declarada
---------------------------------------------

La referencia construye con ``self.__class__(self.env, ids, ids)`` y **no
declara ``_browse``**: medido sobre las dos raíces, ``def _browse`` da 0
declaraciones y ``_browse(`` 0 llamadas en ``odoo19c`` y en ``odoo18c``. Aquí
ese constructor está ocupado: ``django/db/models/base.py:604`` construye la
fila con ``new = cls(*values)``, posicionalmente por campo concreto. Las dos
firmas no pueden coexistir en ``__init__``.

Se porta el contrato entero y se declara la única divergencia: la terna
``(env, _ids, _prefetch_ids)`` se instala por ``BaseModel._from_ids``, que
asigna sin pasar por ``Model.__init__`` — la misma vía que Django ya usa para
``from_db``. El nombre es nuestro y lleva guion bajo a propósito: no
impersona un símbolo de la referencia que no existe.

Los tres regímenes de lectura que gobiernan el diseño
------------------------------------------------------

``odoo19c: odoo/orm/fields.py:1642-1660`` gatea la lectura de campo por el
tamaño del recordset, y son **tres** regímenes, no dos::

    record_len = len(record._ids)
    if record_len != 1:
        if record_len:
            record.ensure_one()        # lanza "Expected singleton"
            assert False, "unreachable"
        value = self.convert_to_cache(False, record, validate=False)
        return self.convert_to_record(value, record)   # vacío -> valor nulo

Por eso una instancia de modelo puede portar ``_ids`` de cualquier tamaño sin
mentir: qué se puede leer lo decide ``len(_ids)``, no el hecho de ser una
instancia de Django.

Criterio de las dos categorías (INVENTORY)
-------------------------------------------

===========================  ==============================================
El stack lo trae hecho       ``tuple``/``set``/``frozenset``/``hash`` de
                             ``cpython`` para la identidad y las operaciones
                             de conjunto; ``itemgetter`` y ``defaultdict``
                             para ``grouped``; ``sorted`` para ``sorted``.
                             ``models.Model`` de ``django`` como base de la
                             que deriva, y su ``Meta.abstract``.
El stack tiene con qué       el recordset en sí. Un ``QuerySet`` de Django es
construirlo                  perezoso y sus homónimos miden otra cosa —
                             ``exists()`` devuelve ``bool`` donde la
                             referencia devuelve un recordset, ``union`` es
                             SQL UNION donde la referencia es
                             ``browse(OrderedSet(ids))``, y ``__iter__``
                             emite filas donde la referencia emite recordsets
                             unitarios con su corte de prefetch. Las
                             primitivas están —``PREFETCH_MAX``,
                             ``split_every`` y ``OrderedSet`` ya viven en
                             ``src/tools``— y no hace falta dependencia de
                             fuera.
===========================  ==============================================

Ninguno de los 14 homónimos que el censo del banco marcó ``STACK`` se reusa:
el nombre coincide y el comportamiento no, que es el sub-patrón C de
``metrica-decide-la-conclusion.md``.
"""
import collections.abc
import operator

import pytest
from django.db import models as django_models
from django.db.models.query import QuerySet

import fields
from orm.environments import Environment
from orm.models import BaseModel
from tools.constants import PREFETCH_MAX


class RecordsetProbe(BaseModel):
    """Sonda del núcleo: declara ``_name`` porque es el caso que la fuente cubre.

    ``orm.registry.name_of`` lee ``__dict__`` y devuelve ``None`` para un
    modelo que no declara ``_name``; la referencia siempre lo tiene, así que
    el caso sin ``_name`` no se diseña aquí — se declararía aparte.
    """

    _name = 'orm.recordset.probe'
    _description = "Recordset probe"

    label = fields.Char('Label')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_recordset_probe'


class OtherProbe(BaseModel):
    """Segundo modelo: las operaciones binarias exigen ``_name`` distinto."""

    _name = 'orm.recordset.other'
    _description = "Other probe"

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_recordset_other'


@pytest.fixture
def empty(ambient):
    """Recordset vacío de la sonda, sin tocar la base."""
    return RecordsetProbe._from_ids(ambient, (), ())


@pytest.fixture
def ambient():
    """El entorno con el que se construye la terna."""
    return Environment()


class TestBaseModelIsTheBaseTheModelsDeriveFrom:
    """La forma que el ejecutor eligió, no una clase hermana generada."""

    def test_base_model_is_an_abstract_django_model(self):
        assert issubclass(BaseModel, django_models.Model)
        assert BaseModel._meta.abstract

    def test_a_recordset_is_not_a_queryset(self, empty):
        # El homónimo de Django mide otra cosa: perezoso y de filas.
        assert not isinstance(empty, QuerySet)

    def test_the_three_slots_of_the_reference_are_present(self, empty):
        # odoo19c: odoo/orm/models.py:362 -> __slots__ = ['env','_ids','_prefetch_ids']
        assert empty.env is not None
        assert empty._ids == ()
        assert empty._prefetch_ids == ()

    def test_from_ids_does_not_go_through_django_row_construction(self, ambient):
        # django/db/models/base.py:604 -> new = cls(*values); la terna no puede
        # pasar por ahi. _from_ids asigna sin invocar Model.__init__.
        rs = RecordsetProbe._from_ids(ambient, (7,), (7,))
        assert rs._ids == (7,)
        assert rs.__class__ is RecordsetProbe


class TestBrowse:
    """``odoo19c: odoo/orm/models.py`` — ``browse`` normaliza y no consulta."""

    def test_no_argument_gives_the_empty_tuple(self, empty):
        assert empty.browse()._ids == ()

    def test_a_bare_int_becomes_a_one_tuple(self, empty):
        assert empty.browse(7)._ids == (7,)

    def test_an_iterable_becomes_a_tuple_in_its_own_order(self, empty):
        assert empty.browse([7, 18, 12])._ids == (7, 18, 12)

    def test_a_nonexistent_id_survives_in_ids(self, empty):
        # La referencia no comprueba existencia al browsear: eso es exists().
        assert empty.browse([999999])._ids == (999999,)

    def test_a_repeated_id_survives(self, empty):
        # tuple(ids), sin deduplicar: quien deduplica es union/__and__.
        assert empty.browse([7, 7])._ids == (7, 7)

    def test_prefetch_is_the_same_object_as_ids(self, empty):
        # self.__class__(self.env, ids, ids) — el MISMO objeto, no una copia:
        # __iter__ lo compara con `is` para decidir el corte de prefetch.
        rs = empty.browse([7, 18])
        assert rs._prefetch_ids is rs._ids

    def test_browse_keeps_the_environment(self, ambient, empty):
        assert empty.browse([7]).env is ambient


class TestTruthAndSize:

    def test_bool_is_false_when_empty(self, empty):
        assert bool(empty) is False

    def test_bool_is_true_when_populated(self, empty):
        assert bool(empty.browse([7])) is True

    def test_len_is_the_size_of_ids(self, empty):
        assert len(empty.browse([7, 18, 12])) == 3


class TestEnsureOne:

    def test_a_singleton_returns_itself(self, empty):
        rs = empty.browse([7])
        assert rs.ensure_one() is rs

    def test_more_than_one_raises_value_error(self, empty):
        # El mensaje se ancla al repr del recordset, no al `ids=(...)` del
        # descriptor de `id`: los dos dicen "Expected singleton", asi que sin
        # el ancla el caso no distingue quien lo lanzo.
        with pytest.raises(ValueError, match=r'Expected singleton: orm\.recordset\.probe'):
            empty.browse([7, 18]).ensure_one()

    def test_empty_also_raises(self, empty):
        # `_id, = self._ids` desempaqueta: cero valores tambien es ValueError.
        with pytest.raises(ValueError, match='Expected singleton'):
            empty.ensure_one()


class TestIteration:
    """La referencia emite recordsets UNITARIOS, no filas."""

    def test_empty_yields_nothing(self, empty):
        assert list(empty) == []

    def test_a_singleton_yields_itself_identically(self, empty):
        rs = empty.browse([7])
        assert next(iter(rs)) is rs

    def test_each_yielded_item_is_a_singleton_recordset(self, empty):
        for rec in empty.browse([7, 18, 12]):
            assert isinstance(rec, RecordsetProbe)
            assert len(rec) == 1

    def test_the_order_is_the_order_of_ids(self, empty):
        assert [r._ids[0] for r in empty.browse([12, 7, 18])] == [12, 7, 18]

    def test_below_the_cut_every_record_shares_the_prefetch_object(self, empty):
        rs = empty.browse([7, 18])
        assert all(r._prefetch_ids is rs._prefetch_ids for r in rs)

    def test_above_the_cut_the_prefetch_is_split(self, empty):
        # size > PREFETCH_MAX and prefetch_ids is ids -> split_every(PREFETCH_MAX, ids)
        rs = empty.browse(range(PREFETCH_MAX + 1))
        assert rs._prefetch_ids is rs._ids
        for rec in rs:
            assert len(rec._prefetch_ids) <= PREFETCH_MAX


class TestMembership:

    def test_a_record_of_the_same_model_is_in_the_set(self, empty):
        assert empty.browse([7]) in empty.browse([7, 18])

    def test_a_record_not_in_the_set_is_not(self, empty):
        assert empty.browse([99]) not in empty.browse([7, 18])

    def test_a_field_name_is_looked_up_in_fields(self, empty):
        assert 'label' in empty

    def test_a_record_of_another_model_raises(self, ambient, empty):
        other = OtherProbe._from_ids(ambient, (7,), (7,))
        with pytest.raises(TypeError, match='inconsistent models in'):
            other in empty

    def test_an_unsupported_operand_raises(self, empty):
        with pytest.raises(TypeError, match='unsupported operand types in'):
            3 in empty


class TestSetOperations:
    """Todas devuelven recordsets; ninguna delega en SQL."""

    def test_concat_keeps_duplicates_and_order(self, empty):
        assert empty.browse([7]).concat(empty.browse([7, 18]))._ids == (7, 7, 18)

    def test_add_is_concat(self, empty):
        assert (empty.browse([7]) + empty.browse([18]))._ids == (7, 18)

    def test_union_deduplicates_preserving_first_occurrence(self, empty):
        assert empty.browse([7, 18]).union(empty.browse([18, 12]))._ids == (7, 18, 12)

    def test_or_is_union(self, empty):
        assert (empty.browse([7]) | empty.browse([7, 18]))._ids == (7, 18)

    def test_sub_preserves_order_of_the_left_side(self, empty):
        assert (empty.browse([12, 7, 18]) - empty.browse([7]))._ids == (12, 18)

    def test_and_preserves_first_occurrence_order(self, empty):
        assert (empty.browse([12, 7, 18]) & empty.browse([18, 12]))._ids == (12, 18)

    @pytest.mark.parametrize('op', ['__add__', '__sub__', '__and__', '__or__'])
    def test_a_mismatched_model_raises(self, ambient, empty, op):
        other = OtherProbe._from_ids(ambient, (7,), (7,))
        with pytest.raises(TypeError, match='inconsistent models in'):
            getattr(empty.browse([7]), op)(other)


class TestIdentity:

    def test_equality_ignores_order(self, empty):
        assert empty.browse([7, 18]) == empty.browse([18, 7])

    def test_equality_ignores_repetition(self, empty):
        # set(self._ids) == set(other._ids)
        assert empty.browse([7, 7]) == empty.browse([7])

    def test_a_different_model_is_not_equal(self, ambient, empty):
        other = OtherProbe._from_ids(ambient, (7,), (7,))
        assert not (empty.browse([7]) == other)

    def test_hash_ignores_order(self, empty):
        assert hash(empty.browse([7, 18])) == hash(empty.browse([18, 7]))

    def test_lt_compares_as_sets(self, empty):
        assert empty.browse([7]) < empty.browse([7, 18])

    def test_le_is_true_for_the_empty_recordset(self, empty):
        # ``if not self or self in other: return True`` — atajo 1 de :6625.
        assert empty.browse([]) <= empty.browse([7])

    def test_le_is_true_for_a_singleton_the_other_contains(self, empty):
        # Atajo 2: ``self in other`` pasa por ``__contains__``, que exige
        # ``len(self) == 1``. Un recordset de 2 NO lo toma y cae al conjunto.
        assert empty.browse([7]) <= empty.browse([7, 18])

    def test_le_is_true_for_equal_sets_by_the_set_path(self, empty):
        # Los dos atajos fallan aqui (no esta vacio; ``len`` es 2, asi que
        # ``__contains__`` da False) y decide ``set(ids) <= set(ids)``.
        assert empty.browse([7, 18]) <= empty.browse([18, 7])

    def test_le_is_false_when_it_is_not_a_subset(self, empty):
        assert not (empty.browse([7, 99]) <= empty.browse([7, 18]))

    def test_gt_is_a_strict_superset(self, empty):
        assert empty.browse([7, 18]) > empty.browse([7])

    def test_gt_is_false_for_equal_sets(self, empty):
        # Estricto: la referencia usa ``>``, no ``>=`` — :6638.
        assert not (empty.browse([7, 18]) > empty.browse([18, 7]))

    def test_ge_is_true_against_the_empty_recordset(self, empty):
        # ``if not other or other in self`` — atajo 1 de :6646, y mide al OTRO.
        assert empty.browse([7]) >= empty.browse([])

    def test_ge_is_true_for_a_singleton_it_contains(self, empty):
        assert empty.browse([7, 18]) >= empty.browse([18])

    def test_ge_is_true_for_equal_sets_by_the_set_path(self, empty):
        assert empty.browse([7, 18]) >= empty.browse([18, 7])

    def test_ge_is_false_when_it_is_not_a_superset(self, empty):
        assert not (empty.browse([7, 18]) >= empty.browse([7, 99]))

    def test_the_four_comparisons_refuse_another_model(self, ambient, empty):
        # ``NotImplemented`` en los cuatro: Python prueba el reflejado y
        # levanta ``TypeError``. El control DISCRIMINA porque un ``return
        # False`` en vez de ``NotImplemented`` pasaria los casos de arriba y
        # caeria aqui.
        other = OtherProbe._from_ids(ambient, (7,), (7,))
        mine = empty.browse([7])
        for operation in (operator.lt, operator.le, operator.gt, operator.ge):
            with pytest.raises(TypeError):
                operation(mine, other)

    def test_the_four_comparisons_are_declared_here_not_inherited(self):
        # Control ESTRUCTURAL, y su razon esta medida: el control de conducta
        # NO discrimina ``__gt__``. Retirando los tres operadores caen los 8
        # casos de ``le_``/``ge_`` y los 2 de ``gt_`` SOBREVIVEN, porque Python
        # refleja ``a > b`` a ``b.__lt__(a)`` y ``__lt__`` sigue ahi. Un
        # control que no puede fallar es un adorno (sub-patron D de
        # ``metrica-decide-la-conclusion``), asi que lo que se mide aqui es el
        # PORTE — que los cuatro esten declarados, como en :6617-6654— y no la
        # conducta, que ya miden los casos de arriba.
        for name in ('__lt__', '__le__', '__gt__', '__ge__'):
            assert name in BaseModel.__dict__, name

    def test_repr_is_name_then_ids(self, empty):
        assert repr(empty.browse([7, 18])) == "orm.recordset.probe(7, 18)"

    def test_str_of_a_multi_recordset_is_its_repr(self, empty):
        # Control que DISCRIMINA el override de ``__str__``. Sin el,
        # ``Model.__str__`` de Django lee ``self.pk`` -> el descriptor de ``id``
        # -> ``ValueError`` sobre un recordset de N. Medido: con el override
        # mutado a ``Model.__str__``, este caso cae y los otros 64 no.
        assert str(empty.browse([7, 18])) == "orm.recordset.probe(7, 18)"

    def test_int_of_a_singleton_is_its_id(self, empty):
        assert int(empty.browse([7])) == 7

    def test_ids_property_is_a_list(self, empty):
        assert empty.browse([7, 18]).ids == [7, 18]


class TestIndexing:

    def test_an_int_index_gives_a_singleton(self, empty):
        assert empty.browse([12, 7, 18])[1]._ids == (7,)

    def test_a_slice_gives_a_subset(self, empty):
        assert empty.browse([12, 7, 18])[0:2]._ids == (12, 7)

    def test_a_string_key_reads_the_field(self, empty):
        # self._fields[key].__get__(self) — sobre el vacio da el valor nulo,
        # no lanza: es el tercer regimen de fields.py:1648-1651.
        assert empty['label'] is False or empty['label'] == ''


class TestEnvironmentDerivation:
    """Las cuatro conservan el MISMO objeto de prefetch — la fuente lo dice."""

    def test_with_env_keeps_ids_and_prefetch(self, ambient, empty):
        rs = empty.browse([7, 18])
        derived = rs.with_env(ambient)
        assert derived._ids is rs._ids
        assert derived._prefetch_ids is rs._prefetch_ids

    def test_with_context_derives_the_environment(self, empty):
        rs = empty.browse([7]).with_context(probe_key=True)
        assert rs.env.context['probe_key'] is True
        assert rs._ids == (7,)

    def test_with_prefetch_defaults_to_own_ids(self, empty):
        rs = empty.browse([7, 18])
        assert rs.with_prefetch()._prefetch_ids is rs._ids

    def test_with_prefetch_accepts_a_wider_set(self, empty):
        rs = empty.browse([7]).with_prefetch((7, 18, 12))
        assert rs._prefetch_ids == (7, 18, 12)
        assert rs._ids == (7,)

    def test_sudo_returns_self_when_the_flag_already_matches(self, empty):
        rs = empty.browse([7])
        assert rs.sudo(rs.env.su) is rs

    def test_sudo_rejects_a_non_boolean(self, empty):
        with pytest.raises(AssertionError):
            empty.browse([7]).sudo('yes')


class TestProjection:

    def test_filtered_keeps_order_and_returns_a_recordset(self, empty):
        rs = empty.browse([12, 7, 18])
        kept = rs.filtered(lambda r: r._ids[0] != 7)
        assert kept._ids == (12, 18)

    def test_an_empty_function_returns_self(self, empty):
        rs = empty.browse([7])
        assert rs.filtered(None) is rs

    def test_mapped_with_an_empty_path_returns_self(self, empty):
        rs = empty.browse([7])
        assert rs.mapped('') is rs

    def test_sorted_below_two_returns_self(self, empty):
        rs = empty.browse([7])
        assert rs.sorted() is rs

    def test_sorted_by_key_reorders_the_ids(self, empty):
        rs = empty.browse([12, 7, 18])
        assert rs.sorted(key=lambda r: r._ids[0])._ids == (7, 12, 18)

    def test_grouped_returns_recordsets_sharing_the_prefetch(self, empty):
        rs = empty.browse([12, 7, 18])
        groups = rs.grouped(lambda r: r._ids[0] % 2)
        assert set(groups) == {0, 1}
        assert all(g._prefetch_ids is rs._prefetch_ids for g in groups.values())


class TestExistsIsNotTheDjangoHomonym:

    def test_exists_returns_a_recordset_not_a_bool(self, empty):
        # QuerySet.exists() devuelve bool; la referencia devuelve un recordset.
        # Sobre el vacio `if not ids: return self` — sin consulta.
        assert empty.exists() is empty


class TestOriginAndCache:

    def test_origin_of_real_records_is_self(self, empty):
        rs = empty.browse([7, 18])
        assert rs._origin is rs

    def test_cache_is_a_mapping_view(self, empty):
        assert isinstance(empty.browse([7])._cache, collections.abc.Mapping)
