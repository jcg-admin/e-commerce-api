"""Sonda A2 de TASK-API-0417 — la fase ``field.setup(model)`` sobre un campo
de Django con ``related=``: ¿instala ``compute=_compute_related`` y la
lectura resuelve la cadena?

Corrige la sonda A: allí el caso 2 leía DESPUÉS del caso 1 sobre la misma
fila, y el caso 1 había sembrado ``False`` en la caché del campo antes de
reventar en ``default_get``. El ``False`` del caso 2 era el acierto de caché
del caso 1, no la respuesta de la fase. Aquí cada caso tiene su modelo y su
fila; la fase corre ANTES de la primera lectura.

EL VEREDICTO SE MIDE POR CONTENIDO: se espera leer ``'Ada'``; se publica qué
quedó en ``compute``, ``search`` e ``inverse`` tras la fase, con nombre.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
import django  # noqa: E402

django.setup()

from django.db import models  # noqa: E402

import fields  # noqa: E402  — registra los enganches de orm.fields
from orm.models import BaseModel  # noqa: E402


class PartnerProbe0417B(BaseModel):
    name = models.CharField(max_length=32)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_partner_probe_0417b'


class OwnerProbe0417B(BaseModel):
    partner = models.ForeignKey(PartnerProbe0417B, on_delete=models.CASCADE,
                                db_column='partner_id')
    partner_name = models.CharField(max_length=32, related='partner.name')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_owner_probe_0417b'


field = next(f for f in OwnerProbe0417B._meta.get_fields()
             if f.name == 'partner_name')
name_of = lambda x: getattr(x, '__name__', getattr(x, '__func__', x))  # noqa: E731
print(f'antes:  setup_done={getattr(field, "_setup_done", "<sin>")!r} '
      f'compute={field.compute!r} setup_fn={name_of(type(field).setup)!r}')
exit_code = 0
try:
    field.setup(OwnerProbe0417B)
    print(f'despues: setup_done={field._setup_done!r} '
          f'compute={name_of(field.compute)!r} inverse={name_of(field.inverse)!r} '
          f'search={name_of(field.search)!r} related_field={field.related_field.name!r}')
except Exception as exc:  # noqa: BLE001
    print(f'setup: EXC {type(exc).__name__}: {exc}')
    exit_code = 1

owner = OwnerProbe0417B(partner=PartnerProbe0417B(name='Ada'))
EXPECTED = 'Ada'
try:
    got = owner.partner_name
except Exception as exc:  # noqa: BLE001
    got = f'EXC {type(exc).__name__}: {exc}'
verdict = 'OK' if got == EXPECTED else 'FALLA'
if verdict == 'FALLA':
    exit_code = 1
print(f'lectura_con_fase: {verdict} esperado={EXPECTED!r} leido={got!r}')
print(f'EXIT={exit_code}')
sys.exit(exit_code)
