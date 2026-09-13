"""Sonda A3 de TASK-API-0417 — la fase ``setup_related``, cuando SE ALCANZA,
¿instala ``compute`` y la lectura resuelve la cadena?

A2 midió que ``field.setup(model)`` retorna sin hacer nada: el defecto de
clase ``_setup_done = True`` (``orm/fields.py:2153``) hace que
``_field_setup`` corte en su primera línea. Esta sonda pone el defecto en
``False`` —lo que la fuente declara al construir— y vuelve a medir. Es el
control de la pieza: si con la fase alcanzable la lectura da ``'Ada'``, lo que
falta es sólo el disparo de la fase; si no, falta más.

EL VEREDICTO SE MIDE POR CONTENIDO: valor esperado ``'Ada'``; se publica qué
instaló la fase, por nombre.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
import django  # noqa: E402

django.setup()

from django.db import models  # noqa: E402

import fields  # noqa: E402  — registra los enganches de orm.fields
from orm.models import BaseModel  # noqa: E402


class PartnerProbe0417C(BaseModel):
    name = models.CharField(max_length=32)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_partner_probe_0417c'


class OwnerProbe0417C(BaseModel):
    partner = models.ForeignKey(PartnerProbe0417C, on_delete=models.CASCADE,
                                db_column='partner_id')
    partner_name = models.CharField(max_length=32, related='partner.name')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_owner_probe_0417c'


field = next(f for f in OwnerProbe0417C._meta.get_fields()
             if f.name == 'partner_name')
name_of = lambda x: getattr(x, '__name__', x)  # noqa: E731
exit_code = 0
field._setup_done = False   # lo que la fuente declara al construir (:300)
try:
    field.setup(OwnerProbe0417C)
    print(f'fase: compute={name_of(field.compute)!r} inverse={name_of(field.inverse)!r} '
          f'search={name_of(field.search)!r} '
          f'related_field={getattr(field.related_field, "name", None)!r} '
          f'readonly={field.readonly!r} store={field.store!r}')
except Exception as exc:  # noqa: BLE001
    print(f'fase: EXC {type(exc).__name__}: {exc}')
    exit_code = 1

owner = OwnerProbe0417C(partner=PartnerProbe0417C(name='Ada'))
EXPECTED = 'Ada'
try:
    got = owner.partner_name
except Exception as exc:  # noqa: BLE001
    import traceback
    got = f'EXC {type(exc).__name__}: {exc}'
    tb = traceback.extract_tb(exc.__traceback__)[-1]
    print(f'  en {tb.filename.split("/")[-1]}:{tb.lineno} {tb.line}')
verdict = 'OK' if got == EXPECTED else 'FALLA'
if verdict == 'FALLA':
    exit_code = 1
print(f'lectura_con_fase_alcanzable: {verdict} esperado={EXPECTED!r} leido={got!r}')
print(f'EXIT={exit_code}')
sys.exit(exit_code)
