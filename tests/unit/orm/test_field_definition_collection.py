"""La fase que recoge las definiciones de campo por clase (TASK-API-0416).

La fuente monta un campo en tres pasos y **en este orden**: recoge sus
definiciones recorriendo la MRO, fusiona lo que cada una declaró, y sólo
entonces deriva ``store`` (``odoo19c: odoo/orm/model_classes.py:366-381`` →
``odoo/orm/fields.py:443-465``). La clase del campo la fija el último eslabón;
el almacenamiento **nunca** enruta nada.

Este puerto tenía los tres pasos invertidos: el ``store`` se derivaba en la
fachada, al construir, y la clase se elegía con él — antes de que existiera
ninguna cadena que fusionar. Una redeclaración no podía corregir nada porque el
campo ya estaba construido cuando la MRO aparecía.

Qué haría fallar a estos casos:

- que un ``compute=`` acabe con columna, que es lo que producía derivar
  ``store`` **después** de que ``get_attname_column`` ya hubiera decidido;
- que la fusión pierda lo que declaró la base, o lo que el hijo pisa;
- que el campo fusionado se rellene con ``__dict__.update`` en vez de
  construirse, y quede con ``max_length`` y sin su ``MaxLengthValidator``;
- que un campo sin columna quede sin descriptor y una lectura devuelva el
  descriptor en vez de despachar el cómputo.
"""
import pytest
from django.core.validators import MaxLengthValidator
from django.db import connection
from django.db import models as django_models

import api
import fields
from orm.fields import _collect_field_definitions


class LabelMixin:
    """Base **llana** — no desciende de ``models.Model``, a propósito.

    Es la única forma por la que la rama de fusión es alcanzable hoy: Django
    **prohíbe** redeclarar en la subclase un campo de una base abstracta suya
    (``FieldError: Local field … clashes with field of the same name from base
    class``), así que una cadena de longitud > 1 sólo puede venir de una base
    que Django no reconozca como modelo.
    """

    label = django_models.CharField('Label', compute='_compute_label',
                                    max_length=9)


class MergedProbe(LabelMixin, django_models.Model):
    """El hijo redeclara: la cadena tiene dos eslabones."""

    label = django_models.CharField(inverse='_inverse_label', max_length=32)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_merged_probe'

    @api.depends()
    def _compute_label(self):
        self.label = 'calculado'

    def _inverse_label(self):
        pass


class DirectProbe(django_models.Model):
    """Una sola declaración: la cadena tiene un eslabón (atajo ``_direct``)."""

    label = django_models.CharField('Label', compute='_compute_label',
                                    max_length=9)
    source = django_models.IntegerField('Source', null=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_direct_probe'

    @api.depends('source')
    def _compute_label(self):
        self.label = f'v{self.source}'


def field_of(model, name):
    """El campo, esté en ``local_fields`` o en ``private_fields``."""
    return next(f for f in model._meta.get_fields() if f.name == name)


@pytest.fixture(scope='session')
def tables(django_db_setup, django_db_blocker):
    """La tabla de la sonda, una vez por sesión y fuera de la transacción."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            editor.create_model(DirectProbe)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            editor.delete_model(DirectProbe)


class TestTheChainComesFromTheMro:
    """La recolección ≙ ``_init_model_class_fields`` (``:366-374``)."""

    def test_a_plain_base_contributes_its_declaration(self):
        chain = _collect_field_definitions(
            field_of(MergedProbe, 'label'), MergedProbe, 'label')
        assert len(chain) == 1, 'el campo ya fusionado no reentra'

    def test_the_merged_field_records_its_two_links(self):
        assert len(field_of(MergedProbe, 'label')._base_fields__) == 2

    def test_the_single_declaration_takes_the_direct_shortcut(self):
        assert field_of(DirectProbe, 'label')._base_fields__ == ()


class TestTheMergeKeepsBothEnds:
    """La fusión une los ``_args__`` en orden base → hijo (``:378-381``)."""

    def test_the_compute_of_the_base_survives(self):
        assert field_of(MergedProbe, 'label').compute == '_compute_label'

    def test_the_inverse_of_the_child_survives(self):
        assert field_of(MergedProbe, 'label').inverse == '_inverse_label'

    def test_the_child_overrides_the_base(self):
        assert field_of(MergedProbe, 'label').max_length == 32

    def test_the_positional_label_of_the_base_survives(self):
        """Llegó como primer posicional y sólo sobrevive si se nombró."""
        assert field_of(MergedProbe, 'label').verbose_name == 'Label'


class TestTheMergedFieldIsCONSTRUCTED:
    """El control de la divergencia: la fuente basta con ``_base_fields__``
    porque su ``__init__`` no deriva nada; aquí ``CharField.__init__``
    materializa la ``cached_property`` ``validators``, así que un campo
    rellenado con ``__dict__.update`` queda con ``max_length`` y sin validador.
    """

    def test_the_max_length_validator_is_materialized(self):
        validators = field_of(MergedProbe, 'label').validators
        assert any(isinstance(v, MaxLengthValidator) and v.limit_value == 32
                   for v in validators), validators


class TestTheStoreIsDerivedBeforeTheColumn:
    """``compute=`` sin ``store=`` implica ``store=False`` (``:446``), y sin
    ``store`` no hay columna: la derivación tiene que ir ANTES del montaje."""

    @pytest.mark.parametrize('model', (MergedProbe, DirectProbe))
    def test_the_field_does_not_store(self, model):
        assert field_of(model, 'label').store is False

    @pytest.mark.parametrize('model', (MergedProbe, DirectProbe))
    def test_the_field_has_no_column(self, model):
        assert field_of(model, 'label').column is None

    @pytest.mark.parametrize('model', (MergedProbe, DirectProbe))
    def test_the_field_is_not_concrete(self, model):
        assert field_of(model, 'label').concrete is False

    @pytest.mark.parametrize('model', (MergedProbe, DirectProbe))
    def test_the_field_is_private_not_local(self, model):
        names = [f.name for f in model._meta.local_fields]
        privates = [f.name for f in model._meta.private_fields]
        assert 'label' not in names and 'label' in privates, (names, privates)

    def test_a_field_without_the_declaration_keeps_its_column(self):
        """El control: sin ``compute=`` la rama con columna sigue viva."""
        source = field_of(DirectProbe, 'source')
        assert source.store is True and source.column == 'source'


class TestTheReadDispatchesTheCompute:
    """Django cuelga su descriptor sólo ``if self.column``, así que un campo
    sin columna sale de ``contribute_to_class`` sin ninguno. Sin la rama que
    lo instala, la lectura resolvía por la MRO al ``Field`` crudo de la base.
    """

    def test_the_class_attribute_is_not_the_raw_field(self):
        assert not isinstance(vars(DirectProbe)['label'],
                              django_models.Field)

    @pytest.mark.django_db
    def test_reading_it_dispatches_the_compute(self, tables):
        DirectProbe.objects.all().delete()
        DirectProbe.objects.create(source=7)
        assert DirectProbe.objects.first().label == 'v7'

    @pytest.mark.django_db
    def test_the_select_does_not_ask_for_the_missing_column(self, tables):
        """Si el campo siguiera concreto, cada ``SELECT`` pediría una columna
        que no existe y la consulta reventaría con ``ProgrammingError``."""
        DirectProbe.objects.all().delete()
        DirectProbe.objects.create(source=1)
        assert DirectProbe.objects.count() == 1


class TestTheFacadeKeepsItsShape:
    """El enrutado de las fachadas sigue vivo: este pase construye la costura,
    no retira todavía el camino que hoy decide qué clase se construye."""

    def test_a_facade_compute_still_has_no_column(self):
        assert fields.Char(compute='_compute_x').store is False
