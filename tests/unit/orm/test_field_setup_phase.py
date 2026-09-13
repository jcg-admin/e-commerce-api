"""Fase de Field.setup — el descriptor se elige con el campo ya armado.

Ejerce odoo19c: odoo/orm/fields.py:526-550 (Field.setup) y
:604-632 (setup_related, que declara self.compute =
self._compute_related). En la fuente el campo es su propio descriptor, asi
que ese compute rige desde que se asigna. Aqui el descriptor se elige en
contribute_to_class, antes de que compute exista, y _field_setup
lo vuelve a elegir al cerrar (:ref:`h-api-1106`).

El veredicto se mide por CONTENIDO: el valor leido, la clase del descriptor
instalado y el compute que ese descriptor guarda — nunca por la presencia
de un atributo.
"""
import copy

import pytest
from django.db import connection, models
from orm.models import BaseModel  # noqa: E402
from orm.fields import (ComputedFieldDescriptor, FieldDescriptor,
                        _install_field_descriptor)


class CountrySp(models.Model):
    code = models.CharField(max_length=4)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_country_sp'


class PartnerSpBase(BaseModel):
    name = models.CharField(max_length=32)
    country = models.ForeignKey(CountrySp, on_delete=models.CASCADE, null=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_partner_sp_base'


class OwnerSpBase(BaseModel):
    partner = models.ForeignKey(PartnerSpBase, on_delete=models.CASCADE, null=True)
    partner_name = models.CharField(max_length=32, related='partner.name')
    country_code = models.CharField(max_length=4, related='partner.country.code')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_owner_sp_base'


class PartnerSpPlain(models.Model):
    name = models.CharField(max_length=32)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_partner_sp_plain'


class OwnerSpPlain(models.Model):
    partner = models.ForeignKey(PartnerSpPlain, on_delete=models.CASCADE, null=True)
    partner_name = models.CharField(max_length=32, related='partner.name')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_owner_sp_plain'


MODELS = (CountrySp, PartnerSpBase, OwnerSpBase, PartnerSpPlain, OwnerSpPlain)


@pytest.fixture(scope='session')
def tables(django_db_setup, django_db_blocker):
    """Las tablas de sonda se crean fuera de la transaccion del caso."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in MODELS:
                editor.create_model(model)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in reversed(MODELS):
                editor.delete_model(model)


def installed_descriptor(model, name):
    field = model._meta.get_field(name)
    return type(model).__dict__.get(field.attname) or model.__dict__[field.attname]


class TestTheDescriptorIsElectedWithComputeInHand:

    def test_a_related_field_ends_with_the_computed_descriptor(self):
        for model in (OwnerSpPlain, OwnerSpBase):
            descriptor = model.__dict__['partner_name']
            assert type(descriptor) is ComputedFieldDescriptor, model
            assert descriptor.field.compute == descriptor.field._compute_related

    def test_the_selector_promotes_a_base_descriptor_when_compute_arrives(self):
        """Control de anulacion: sin la rama de promocion este caso cae."""
        field = copy.copy(OwnerSpPlain._meta.get_field('partner_name'))

        class Carrier:
            pass

        setattr(Carrier, field.attname, FieldDescriptor(field))
        field.compute = field._compute_related
        _install_field_descriptor(field, Carrier)
        assert type(Carrier.__dict__[field.attname]) is ComputedFieldDescriptor


@pytest.mark.django_db
class TestARelatedReadResolvesByContent:

    def test_one_hop_on_a_plain_row(self, tables):
        partner = PartnerSpPlain.objects.create(name='Ada')
        owner = OwnerSpPlain.objects.create(partner=partner)
        assert OwnerSpPlain.objects.get(pk=owner.pk).partner_name == 'Ada'

    def test_two_hops_on_a_base_model_row(self, tables):
        country = CountrySp.objects.create(code='MX')
        partner = PartnerSpBase.objects.create(name='Ada', country=country)
        owner = OwnerSpBase.objects.create(partner=partner)
        row = OwnerSpBase.objects.get(pk=owner.pk)
        assert row.partner_name == 'Ada'
        assert row.country_code == 'MX'

    def test_a_null_fk_reads_as_empty(self, tables):
        owner = OwnerSpPlain.objects.create(partner=None)
        assert OwnerSpPlain.objects.get(pk=owner.pk).partner_name == ''
