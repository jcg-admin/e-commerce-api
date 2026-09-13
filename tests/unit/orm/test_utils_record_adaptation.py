"""Las cuatro piezas de la adaptación del recordset: ``record_ids``,
``as_record_list``, ``model_of`` y ``browse``.

En la fuente un *recordset* es una sola cosa: un objeto que lleva a la vez el
modelo (``_name``), los ids (``_ids``) y las filas. De ahí salen gratis
``records.browse(...)``, ``records._ids`` y ``record.id``. Aquí un conjunto de
filas es una instancia de modelo de Django o un ``QuerySet``, así que ese objeto
único no existe y la firma de la fuente no se puede portar literal: se parte en
cuatro funciones de ``orm/utils.py``, y estos casos fijan el contrato de las
cuatro.

Es divergencia de **mecanismo**, no de alcance: donde la fuente escribe
``records._ids`` aquí va ``record_ids(records)``, y el resto del cuerpo queda
igual.

``orm.utils.browse`` — la vuelta de ``record_ids``, y el orden que preserva.

``BaseModel.browse`` (``odoo19c: odoo/orm/models.py:5883``) construye un
recordset a partir de una tupla de ids **sin tocar la base**: su cuerpo es
``self.__class__(self.env, ids, ids)``. Aquí no hay recordset —un conjunto de
filas es un ``QuerySet``— así que la firma no se puede portar literal y el
mecanismo diverge en dos puntos que estos casos fijan:

1. **El orden.** La fuente conserva el orden en que se pasaron los ids, porque
   los guarda en una tupla. Un ``filter(pk__in=…)`` de Django devuelve las filas
   en el orden que decida el motor —o el ``Meta.ordering`` del modelo—, así que
   el orden hay que **reconstruirlo** con ``Case``/``When``.
2. **La pereza.** La fuente no consulta nada: un id inexistente produce un
   recordset que falla al leerse. Aquí la consulta decide qué filas hay, y un id
   inexistente se cae del resultado en silencio.

Qué haría fallar a estos casos
==============================

``ResPartner`` declara ``Meta.ordering = ['complete_name', '-id']``
(``src/addons/base/models/res_partner.py:654``), así que el caso del orden es un
**control que discrimina**: si el ``Case``/``When`` desapareciera, la consulta
saldría ordenada por nombre —no por la secuencia pedida— y el caso caería. Un
caso que sólo comprobara *«browse devuelve las tres filas»* sería verde con y
sin el mecanismo (sub-patrón D de ``metrica-decide-la-conclusion``).
"""
import pytest
from django.db.models import QuerySet

import fields
from addons.base.models.res_partner import ResPartner
from orm.environments import Environment
from orm.models import BaseModel
from orm.utils import as_record_list, browse, model_of, record_ids


class UtilsRecordsetProbe(BaseModel):
    """Sonda que lleva la terna: es lo que la rama nueva tiene que ver.

    El nombre NO puede ser ``RecordsetProbe``: la llave del registro de
    Django es ``app_label`` mas el nombre de la CLASE en minusculas, no el
    ``_name`` de la referencia ni el ``db_table``. Con los tres archivos de
    ``tests/unit/orm`` recolectados juntos, esa sonda choca con la de
    ``test_base_model_recordset.py`` y la recoleccion entera aborta con
    ``RuntimeError: Conflicting 'recordsetprobe' models``. Corriendo el
    archivo solo no se ve: el defecto solo existe en el universo completo.
    """

    _name = 'orm.utils.recordset.probe'
    _description = "Recordset probe for record_ids"

    label = fields.Char('Label')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_utils_recordset_probe'


@pytest.mark.django_db
class TestTheBrowsePreservesTheOrderItWasGiven:
    """El orden de los ids es el contrato, no el del motor."""

    @pytest.fixture
    def three_partners(self):
        """Tres filas cuyo orden alfabético es el inverso del de creación."""
        zulu = ResPartner.objects.create(name='Zulu')
        mike = ResPartner.objects.create(name='Mike')
        alpha = ResPartner.objects.create(name='Alfa')
        return zulu, mike, alpha

    def test_the_given_sequence_survives(self, three_partners):
        """Pedidos en orden de creación, salen en orden de creación."""
        zulu, mike, alpha = three_partners
        ids = [zulu.pk, mike.pk, alpha.pk]
        assert record_ids(browse(ResPartner, ids)) == tuple(ids)

    def test_the_reversed_sequence_survives_too(self, three_partners):
        """Y al revés — es lo que distingue conservar de coincidir.

        Con un solo orden probado, un ``order_by('id')`` accidental pasaría el
        caso anterior. Este lo tumba.
        """
        zulu, mike, alpha = three_partners
        ids = [alpha.pk, zulu.pk, mike.pk]
        assert record_ids(browse(ResPartner, ids)) == tuple(ids)

    def test_the_model_ordering_does_not_win(self, three_partners):
        """El ``Meta.ordering`` del modelo no gobierna el resultado.

        ``ResPartner`` ordena por ``complete_name``, así que sin el
        ``Case``/``When`` estas tres filas saldrían Alfa, Mike, Zulu.
        """
        zulu, mike, alpha = three_partners
        output = list(browse(ResPartner, [mike.pk, zulu.pk, alpha.pk]))
        assert [p.name for p in output] == ['Mike', 'Zulu', 'Alfa']


@pytest.mark.django_db
class TestTheBrowseAcceptsTheFourFormsOfItsArgument:
    """La fuente admite un entero, un iterable y el vacío; aquí también."""

    def test_no_argument_is_the_empty_set(self):
        """``browse()`` sin ids — ≙ ``if not ids: ids = ()``."""
        empty = browse(ResPartner)
        assert isinstance(empty, QuerySet)
        assert record_ids(empty) == ()

    def test_an_empty_iterable_is_the_empty_set(self):
        """Una lista vacía toma la misma rama que la ausencia."""
        assert record_ids(browse(ResPartner, [])) == ()

    def test_a_bare_int_is_not_iterated(self):
        """``ids.__class__ is int`` — un entero se envuelve, no se recorre.

        Sin esa rama, ``tuple(7)`` levanta ``TypeError``.
        """
        partner = ResPartner.objects.create(name='Solo')
        assert record_ids(browse(ResPartner, partner.pk)) == (partner.pk,)

    def test_a_generator_is_consumed_once(self, django_assert_num_queries):
        """Un generador vale como iterable — se materializa en el constructor."""
        partner = ResPartner.objects.create(name='Generador')
        ids = (pk for pk in [partner.pk])
        assert record_ids(browse(ResPartner, ids)) == (partner.pk,)


@pytest.mark.django_db
class TestTheBrowseIsTheInverseOfRecordIds:
    """La vuelta de ``record_ids``: lo que uno produce, el otro consume."""

    def test_the_round_trip_returns_the_same_ids(self):
        """``record_ids(browse(M, ids)) == ids`` para ids existentes."""
        pks = [ResPartner.objects.create(name=f'Ida {i}').pk for i in range(3)]
        assert record_ids(browse(ResPartner, pks)) == tuple(pks)

    def test_a_queryset_round_trips_through_both(self):
        """Y en el otro sentido: de un ``QuerySet`` a sus ids y de vuelta."""
        ResPartner.objects.create(name='Vuelta')
        qs = ResPartner.objects.filter(name='Vuelta')
        assert record_ids(browse(ResPartner, record_ids(qs))) == record_ids(qs)


@pytest.mark.django_db
class TestTheDivergencesAreDeclaredAndMeasured:
    """Las dos formas en que este ``browse`` no puede ser el de la fuente."""

    def test_an_unknown_id_is_dropped_instead_of_deferred(self):
        """La fuente difiere el fallo; aquí la consulta lo descarta.

        No es un descuido: un ``QuerySet`` es una consulta, no una tupla de
        ids. El caso fija la conducta para que el día que se construya un
        recordset perezoso, caiga y se re-decida.
        """
        partner = ResPartner.objects.create(name='Existe')
        nonexistent = ResPartner.objects.order_by('-pk').first().pk + 1000
        assert record_ids(browse(ResPartner, [partner.pk, nonexistent])) == (partner.pk,)

    def test_a_repeated_id_appears_once(self):
        """La fuente guarda ``(7, 7)``; una fila no se puede duplicar en SQL."""
        partner = ResPartner.objects.create(name='Repetido')
        assert record_ids(browse(ResPartner, [partner.pk, partner.pk])) == (partner.pk,)


@pytest.mark.django_db
class TestTheTripleWinsOverThePkOfTheRow:
    """La premisa de este archivo cambio con TASK-API-0397.

    La cabecera dice *"aqui un conjunto de filas es una instancia de modelo de
    Django o un QuerySet, asi que ese objeto unico no existe"*. Desde que
    ``BaseModel`` lleva la terna ``(env, _ids, _prefetch_ids)``, **si existe**:
    una instancia de modelo puede portar N ids. Y ``record_ids`` seguia
    resolviendo por ``isinstance(records, models.Model) -> (records.pk,)``, que
    sobre esa instancia va al descriptor de ``id`` y levanta ``ValueError:
    Expected singleton``.

    Es el defecto que el propio docstring de ``record_ids`` prometia no tener:
    *"donde la fuente escribe ``records._ids``, aqui se escribe
    ``record_ids(records)``"* — y nunca leia ``_ids``.
    """

    def test_a_multi_recordset_gives_its_ids(self):
        environment = Environment()
        records = UtilsRecordsetProbe._from_ids(environment, (7, 18, 33), (7, 18, 33))
        assert record_ids(records) == (7, 18, 33)

    def test_the_order_of_the_triple_survives(self):
        environment = Environment()
        records = UtilsRecordsetProbe._from_ids(environment, (33, 7), (33, 7))
        assert record_ids(records) == (33, 7)

    def test_a_plain_django_row_still_answers_with_its_pk(self):
        # Control que DISCRIMINA: la rama nueva no puede comerse la vieja.
        # Una fila que construye Django NO lleva ``_ids`` y sigue resolviendo
        # por ``pk``. Si la rama del ``_ids`` se pusiera despues, este caso
        # seguiria pasando y los dos de arriba caerian — por eso hacen falta
        # los tres.
        assert record_ids(UtilsRecordsetProbe(id=99)) == (99,)


@pytest.mark.django_db
class TestTheModelOfReadsTheClassOffTheRows:
    """:func:`~orm.utils.model_of` — la vuelta de ``type(recordset)``."""

    def test_an_instance_gives_its_class(self):
        assert model_of(ResPartner.objects.create(name='Uno')) is ResPartner

    def test_a_queryset_gives_its_model(self):
        assert model_of(ResPartner.objects.all()) is ResPartner

    def test_an_empty_queryset_gives_it_too(self):
        """Sin filas también: la clase la lleva la consulta, no el resultado."""
        assert model_of(ResPartner.objects.none()) is ResPartner

    def test_the_class_itself_passes_through(self):
        """Es la forma con que lo llama ``browse(model_of(records), …)``."""
        assert model_of(ResPartner) is ResPartner

    def test_a_bare_iterable_is_refused(self):
        """Y una lista **no**, a propósito.

        Adivinar la clase por el primer elemento consumiría un generador, y
        devolver ``None`` ante lo desconocido convertiría el fallo en un
        ``AttributeError`` lejano. El caso fija la frontera para que no se
        relaje por comodidad: si alguien añadiera la rama del iterable, este
        caso caería y la decisión se volvería a tomar.
        """
        with pytest.raises(TypeError):
            model_of([ResPartner.objects.create(name='Uno')])

    def test_something_that_is_not_a_model_is_refused(self):
        with pytest.raises(TypeError):
            model_of('ResPartner')


@pytest.mark.django_db
class TestTheAsRecordListGivesTheRowsThemselves:
    """:func:`~orm.utils.as_record_list` — la contraparte de ``record_ids``.

    Un cómputo, un inverso o una escritura de caché se invocan sobre la
    **fila**, no sobre su id; ésta es la mitad que entrega el objeto.
    """

    def test_none_is_the_empty_list(self):
        assert as_record_list(None) == []

    def test_one_instance_is_wrapped_not_iterated(self):
        """Una instancia de modelo **es** iterable de sus campos en ningún
        sentido útil: se envuelve, no se recorre."""
        partner = ResPartner.objects.create(name='Solo')
        assert as_record_list(partner) == [partner]

    def test_a_queryset_is_materialised(self):
        ResPartner.objects.create(name='Lista')
        rows = as_record_list(ResPartner.objects.filter(name='Lista'))
        assert [f.name for f in rows] == ['Lista']

    def test_a_generator_is_materialised_too(self):
        """Devuelve una **lista** y no un generador porque el llamador la
        recorre más de una vez, igual que :func:`record_ids` devuelve tupla."""
        partner = ResPartner.objects.create(name='Perezoso')
        rows = as_record_list(f for f in [partner])
        assert rows == [partner]
        assert rows == [partner]

    def test_it_is_the_counterpart_of_record_ids(self):
        """Las dos mitades del mismo objeto: los ids y las filas."""
        partners = [ResPartner.objects.create(name=f'Par {i}') for i in range(2)]
        rowset = ResPartner.objects.filter(pk__in=[s.pk for s in partners])
        assert (sorted(f.pk for f in as_record_list(rowset))
                == sorted(record_ids(rowset)))
