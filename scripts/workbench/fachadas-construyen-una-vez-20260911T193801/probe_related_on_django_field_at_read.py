"""Sonda A de TASK-API-0417 — ¿un ``related=`` sobre un campo de Django se
resuelve AL LEER, hoy, sin pasar por ``NonStored``?

La fuente resuelve un related en DOS momentos: ``_get_attrs`` deriva
``store=False`` al montar (``odoo19c: odoo/orm/fields.py:452-458``), y
``setup_related`` instala ``self.compute = self._compute_related`` (``:632``)
en la fase de registro — ``BaseModel._setup_fields`` llama ``field.setup(self)``
por cada campo. La lectura (``Field.__get__ :1736``) sólo ve ``self.compute``.

Aquí la costura de ``api@67252948`` hace la primera mitad en
``contribute_to_class``. La pregunta es la segunda: ¿alguien llama
``field.setup(model)`` sobre un campo corriente? Medido por grep, el único
invocador es ``fields_properties.py:235``. Esta sonda lo mide por CONDUCTA: un
modelo con ``models.CharField(related='partner.name')`` construido por la
costura, leído sin y con ``field.setup(Model)``.

EL VEREDICTO SE MIDE POR CONTENIDO: cada caso declara el valor que espera leer
(``'Ada'``, el nombre del socio) y compara con lo leído. Un ``None`` o un
``False`` es FALLA nombrando la rama por la que salió.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
import django  # noqa: E402

django.setup()

from django.db import models  # noqa: E402

import fields  # noqa: E402  — registra los enganches de orm.fields


class PartnerProbe0417(models.Model):
    name = models.CharField(max_length=32)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_partner_probe_0417'


class OwnerProbe0417(models.Model):
    partner = models.ForeignKey(PartnerProbe0417, on_delete=models.CASCADE,
                                db_column='partner_id')
    #: La forma de la fuente, sin fachada: el vocabulario en el kwarg.
    partner_name = models.CharField(max_length=32, related='partner.name')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_owner_probe_0417'


field = next(f for f in OwnerProbe0417._meta.get_fields()
             if f.name == 'partner_name')
print(f'store={field.store!r} column={field.column!r} concrete={field.concrete!r} '
      f'related={field.related!r} compute={field.compute!r} '
      f'private={field in OwnerProbe0417._meta.private_fields}')
print(f'descriptor={type(vars(OwnerProbe0417)["partner_name"]).__name__}')

partner = PartnerProbe0417(name='Ada')
owner = OwnerProbe0417(partner=partner)
EXPECTED = 'Ada'
exit_code = 0

# Caso 1 — sin llamar setup(): lo que el árbol hace hoy.
try:
    got = owner.partner_name
except Exception as exc:  # noqa: BLE001 — la sonda registra la excepción como veredicto
    got = f'EXC {type(exc).__name__}: {exc}'
verdict = 'OK' if got == EXPECTED else 'FALLA'
if verdict == 'FALLA':
    exit_code = 1
print(f'sin_setup: {verdict} esperado={EXPECTED!r} leido={got!r} '
      f'compute_tras_leer={field.compute!r}')

# Caso 2 — con la fase de la fuente: field.setup(Model) → setup_related.
try:
    field.setup(OwnerProbe0417)
    setup_msg = f'compute={getattr(field.compute, "__name__", field.compute)!r}'
    got2 = owner.partner_name
except Exception as exc:  # noqa: BLE001
    setup_msg = f'EXC {type(exc).__name__}: {exc}'
    got2 = None
verdict2 = 'OK' if got2 == EXPECTED else 'FALLA'
print(f'con_setup: {verdict2} esperado={EXPECTED!r} leido={got2!r} {setup_msg}')
print(f'EXIT={exit_code} (caso 1 es el estado del árbol; caso 2 mide si la '
      f'fase construida resuelve)')
sys.exit(exit_code)
