"""``Field.comodel_name`` — el contrato que la referencia declara.

La fuente lo declara como **atributo anotado llano**, no como descriptor::

    class _Relational(Field[BaseModel]):
        relational: typing.Literal[True] = True
        comodel_name: str

``odoo19c: odoo/orm/fields_relational.py:33-36``. Una anotación sin valor no
crea atributo de clase: el nombre lo escribe el ``__init__`` del campo, y
queda en el ``__dict__`` de la instancia. Por eso allá es **escribible**, y
``setup_related`` cuenta con ello::

    for attr, prop in self.related_attrs:
        if attr not in self.__dict__ and prop.startswith('_related_'):
            setattr(self, attr, getattr(field, prop))

``odoo19c: odoo/orm/fields.py:645-649`` — el ``setattr`` es la mitad de
escritura del mecanismo ``related=``.

Aquí el puerto lo instaló como ``property`` de sólo lectura, que es un
descriptor **de datos**: gana sobre el ``__dict__`` de la instancia y rehúsa
la asignación. Ese ``__set__`` es invención del puerto — la fuente no lo
tiene. Lo que NO es invención es la derivación: el constructor de Django
recibe ``to=``, no ``comodel_name=``, así que sin derivar, un ``ForeignKey``
daría ``None`` y rompería la garantía de la fuente (``relational=True`` ⇒ el
campo nombra su comodelo). Ver :ref:`h-api-1094`.

*Métrica:* el valor de ``comodel_name`` tras asignar y sin asignar, y la
presencia de ``__set__`` en el descriptor de clase.
*Ciega a:* si el nombre derivado coincide con el que la fuente usaría para
un modelo que no declare ``_name`` — ahí cae a la etiqueta de Django, que es
divergencia declarada en el propio ``fields.py``, no un defecto de este caso.
"""
import pytest
from django.apps import apps
from django.db import models

from orm import registry as orm_registry


@pytest.fixture
def bank():
    return apps.get_model('base', 'ResBank')


class TestTheNameIsWritableAsTheSourceDeclaresIt:
    """La mitad que el puerto rompió: ``setattr`` sobre un campo."""

    def test_setattr_lands_on_the_instance(self):
        field = models.CharField(max_length=8)

        setattr(field, 'comodel_name', 'sale.order')

        assert field.comodel_name == 'sale.order'

    def test_the_class_attribute_is_not_a_data_descriptor(self):
        """El discriminante: un ``__set__`` en la clase gana sobre el
        ``__dict__`` de la instancia, y es lo que producía el
        ``AttributeError: property … has no setter`` en ``setup_related``.
        """
        descriptor = models.Field.__dict__.get('comodel_name')

        assert descriptor is not None, 'el puerto sí instala algo aquí'
        assert not hasattr(descriptor, '__set__')

    def test_an_explicit_value_wins_over_the_derivation(self, bank):
        """Un campo relacional con nombre asignado NO vuelve a derivarlo."""
        field = bank._meta.get_field('country')
        assert field.comodel_name == 'res.country', 'premisa: deriva solo'

        try:
            setattr(field, 'comodel_name', 'res.partner')
            assert field.comodel_name == 'res.partner'
        finally:
            field.__dict__.pop('comodel_name', None)

        assert field.comodel_name == 'res.country'


class TestTheDerivationSurvives:
    """La mitad que NO se retira: sin ella un ``ForeignKey`` daría ``None``."""

    def test_a_relational_field_without_a_value_derives_its_comodel(self, bank):
        field = bank._meta.get_field('country')

        assert 'comodel_name' not in field.__dict__
        assert field.comodel_name == orm_registry.name_of(field.related_model)
        assert field.comodel_name == 'res.country'

    def test_a_non_relational_field_has_no_comodel(self):
        assert models.CharField(max_length=8).comodel_name is None


class TestTheCopyLoopOfSetupRelatedCanRun:
    """El consumidor real de la escritura — ``:645-649``."""

    def test_the_related_attrs_table_can_be_written_one_by_one(self):
        field = models.CharField(max_length=8)

        for attribute, prop in field.related_attrs:
            if prop.startswith('_related_'):
                setattr(field, attribute, None)

        assert field.comodel_name is None
