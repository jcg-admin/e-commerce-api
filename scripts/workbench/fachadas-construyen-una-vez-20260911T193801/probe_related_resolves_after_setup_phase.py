"""Sonda A4 de TASK-API-0417 — con la fase portada, ¿un ``related=`` sobre un
campo de Django resuelve la cadena al leer?

A3 midió que, alcanzada la fase, ``compute`` quedaba instalado pero la lectura
moría en ``_invoke_compute_method`` (``getattr(record, <método ligado>)``).
Esta sonda mide las dos piezas portadas juntas —la fase al arranque y el
despacho por ``determine``— sobre CUATRO formas del modelo, porque el
mecanismo tiene que valer para las cuatro:

1. par de ``orm.models.BaseModel`` (recordset: itera);
2. par de ``django.db.models.Model`` llano (la fila NO itera);
3. cadena de dos saltos ``owner.partner.country.code``;
4. FK en ``NULL`` — el eslabón vacío, que allá es un recordset vacío.

Las filas se PERSISTEN antes de leer. La primera versión construía filas sin
guardar (``pk=None``) y fallaba en las dos formas por una razón que NO es de
0417: ``_filter_not_equal_ids`` (``orm/fields.py``) descarta los ids ``None``
a propósito —la caché se indexa por pk y el ``NewId`` es TASK-API-0327—, así
que un cómputo sobre una fila sin guardar no puede poblar la caché y
``__get__`` levanta ``Compute method failed to assign``. Medir sobre filas
sin pk mide ese mecanismo, no la fase. Las tablas se crean con
``connection.schema_editor()`` y se retiran al final, igual que el fixture
``tables`` de ``tests/unit/orm/test_field_definition_collection.py``.

EL VEREDICTO SE MIDE POR CONTENIDO: cada caso declara el valor esperado y se
compara el leído; y se publica qué instaló la fase, por nombre.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import connection, models  # noqa: E402

import fields  # noqa: E402,F401  — registra los enganches de orm.fields
from orm.models import BaseModel  # noqa: E402

print(f'apps.ready={apps.ready}')


class CountryA4(models.Model):
    code = models.CharField(max_length=4)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_country_a4'


class PartnerA4Base(BaseModel):
    name = models.CharField(max_length=32)
    country = models.ForeignKey(CountryA4, on_delete=models.CASCADE, null=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_partner_a4_base'


class OwnerA4Base(BaseModel):
    partner = models.ForeignKey(PartnerA4Base, on_delete=models.CASCADE, null=True)
    partner_name = models.CharField(max_length=32, related='partner.name')
    country_code = models.CharField(max_length=4, related='partner.country.code')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_owner_a4_base'


class PartnerA4Plain(models.Model):
    name = models.CharField(max_length=32)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_partner_a4_plain'


class OwnerA4Plain(models.Model):
    partner = models.ForeignKey(PartnerA4Plain, on_delete=models.CASCADE, null=True)
    partner_name = models.CharField(max_length=32, related='partner.name')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_owner_a4_plain'


def field_of(model, name):
    return next(f for f in model._meta.get_fields() if f.name == name)


name_of = lambda x: getattr(x, '__name__', x)  # noqa: E731
exit_code = 0
for model, fname in ((OwnerA4Base, 'partner_name'), (OwnerA4Base, 'country_code'),
                     (OwnerA4Plain, 'partner_name')):
    f = field_of(model, fname)
    print(f'fase {model.__name__}.{fname}: setup_done={f._setup_done!r} '
          f'compute={name_of(f.compute)!r} inverse={name_of(f.inverse)!r} '
          f'search={name_of(f.search)!r} related_field='
          f'{getattr(f.related_field, "name", None)!r} store={f.store!r} '
          f'column={f.column!r}')

MODELS = (CountryA4, PartnerA4Base, OwnerA4Base, PartnerA4Plain, OwnerA4Plain)


def persist():
    """Las filas de las cuatro formas, ya con pk; devuelve sus lectores."""
    mx = CountryA4.objects.create(code='MX')
    ada_base = PartnerA4Base.objects.create(name='Ada', country=mx)
    owner_base = OwnerA4Base.objects.create(partner=ada_base)
    ada_plain = PartnerA4Plain.objects.create(name='Ada')
    owner_plain = OwnerA4Plain.objects.create(partner=ada_plain)
    orphan = OwnerA4Plain.objects.create(partner=None)
    return [
        ('base_un_salto', lambda: OwnerA4Base.objects.get(pk=owner_base.pk).partner_name, 'Ada'),
        ('base_dos_saltos', lambda: OwnerA4Base.objects.get(pk=owner_base.pk).country_code, 'MX'),
        ('plain_un_salto', lambda: OwnerA4Plain.objects.get(pk=owner_plain.pk).partner_name, 'Ada'),
        ('fk_nula', lambda: OwnerA4Plain.objects.get(pk=orphan.pk).partner_name,
         getattr(field_of(PartnerA4Plain, 'name'), 'falsy_value', None)),
    ]


with connection.schema_editor() as editor:
    for model in MODELS:
        editor.create_model(model)
try:
    for label, read, expected in persist():
        try:
            got = read()
        except Exception as exc:  # noqa: BLE001
            import traceback
            got = f'EXC {type(exc).__name__}: {exc}'
            tb = traceback.extract_tb(exc.__traceback__)[-1]
            print(f'  en {tb.filename.split("/")[-1]}:{tb.lineno} {tb.line}')
        verdict = 'OK' if got == expected else 'FALLA'
        if verdict == 'FALLA':
            exit_code = 1
        print(f'{label}: {verdict} esperado={expected!r} leido={got!r}')
finally:
    with connection.schema_editor() as editor:
        for model in reversed(MODELS):
            editor.delete_model(model)
print(f'EXIT={exit_code}')
sys.exit(exit_code)
