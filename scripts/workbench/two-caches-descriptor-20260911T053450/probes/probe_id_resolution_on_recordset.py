"""Cómo resuelven ``id``, ``pk`` y un campo llano sobre un recordset.

Es el paso 1 del rediseño: decide si ``id`` necesita su propio descriptor de
NO datos —el cuerpo de ``Id.__get__`` de la referencia, que lee ``record._ids``—
o si el descriptor genérico basta.

El sujeto es un ``BaseModel``: ``_from_ids`` es un ``classmethod`` de esa
clase, y ``ResUsers`` no la hereda (``models.DefaultGetMixin, TimeStampedModel``),
así que una sonda contra ``ResUsers`` mide la ausencia del constructor, no la
resolución del atributo.

*Metrica:* lo que ``getattr`` devuelve —o la excepción que levanta— para
``id``, ``pk`` y un campo llano sobre un recordset construido con
``_from_ids``, con la cache del campo llano sembrada.
*Ciega a:* el coste de cada acceso, y a lo que ocurriría con una fila real de
la base (``managed = False``: no hay tabla que leer).
"""
import traceback

import django

django.setup()

import fields  # noqa: E402  (django.setup() es precondición del import)
from orm.environments import Environment  # noqa: E402
from orm.models import BaseModel  # noqa: E402


class IdProbe(BaseModel):
    """Sonda mínima: un campo llano y el ``id`` que Django declara solo."""

    _name = 'orm.id.probe'
    _description = "Id probe"

    label = fields.Char('Label')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_id_probe'


def show(title, thunk):
    try:
        print(f'{title:<28} -> {thunk()!r}')
    except BaseException as error:            # noqa: BLE001 — se mide la excepción
        print(f'{title:<28} -> {type(error).__name__}: {error}')
        traceback.print_exc(limit=4)


ambient = Environment()
singleton = IdProbe._from_ids(ambient, (7,), (7,))
IdProbe._meta.get_field('label')._insert_cache(singleton, ['uno'])

print('--- singleton: un solo id en la terna ---')
show('rs.id', lambda: singleton.id)
show('rs.pk', lambda: singleton.pk)
show('rs.label', lambda: singleton.label)

several = IdProbe._from_ids(ambient, (7, 18, 33), (7, 18, 33))
IdProbe._meta.get_field('label')._insert_cache(several, ['uno', 'dos', 'tres'])

print()
print('--- tres ids en la terna ---')
show('rs.id', lambda: several.id)
show('rs.pk', lambda: several.pk)
show('rs.label', lambda: several.label)

empty = IdProbe._from_ids(ambient, (), ())
print()
print('--- terna vacia ---')
show('rs.id', lambda: empty.id)
show('rs.label', lambda: empty.label)

print()
print('--- que atributo de clase sirve cada nombre ---')
for name in ('id', 'label'):
    print(f'{name:<8} {type(getattr(IdProbe, name)).__name__}')
print(f"pk       {type(BaseModel.__mro__[-2].__dict__.get('pk')).__name__}")
