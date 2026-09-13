"""Sonda C de TASK-API-0417 — un relacional ``related=`` SIN ``to`` explícito.

La fuente construye ``Many2one(related='ctrl_fk')`` sin nombrar el comodelo:
lo copia de ``related_attrs`` al hacer ``setup_related``
(``odoo19c: odoo/orm/fields.py:643-647`` → ``_related_comodel_name``). Django
exige un ``to`` en ``ForeignKey.__init__``; el marcador de posición es
``'self'`` con ``DO_NOTHING``, y esta sonda mide qué deja cada fase:

- los checks del sistema (``fields.E300``/``E320``/``E304``) sobre el modelo;
- ``related_model``/``remote_field.model`` ANTES y DESPUÉS de ``setup`` —
  ¿queda en el marcador ``'self'`` o en el comodelo real del destino?;
- si ``related_attrs`` ya trae ``comodel_name`` y ``setup_related`` lo copia;
- el ``ModelState`` de migraciones;
- la lectura sobre una fila real tras el setup: qué devuelve y con qué tipo.

Veredicto INVENTORY por clave, como en las sondas A y B. Las claves que
describen el ESTADO (no un contrato) se imprimen sin veredicto.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.apps import apps  # noqa: E402
from django.core import checks  # noqa: E402
from django.db import connection, models  # noqa: E402
from django.db.migrations.state import ModelState  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

import fields  # noqa: E402,F401  — registra los enganches de orm.fields
from orm.model_classes import ensure_field_setup  # noqa: E402
from orm.models import BaseModel  # noqa: E402


class ProbeRelCTarget(BaseModel):
    label = models.CharField(max_length=8)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_relc_target'


class ProbeRelCMid(BaseModel):
    ctrl_fk = models.ForeignKey(ProbeRelCTarget, on_delete=models.CASCADE,
                                related_name='relc_mids')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_relc_mid'


class ProbeRelCOwner(BaseModel):
    kept = models.CharField(max_length=8)
    mid = models.ForeignKey(ProbeRelCMid, on_delete=models.CASCADE,
                            related_name='relc_owners')
    # SIN ``to``: el marcador es 'self'; el comodelo real es ProbeRelCTarget,
    # que sólo se conoce al recorrer ``mid.ctrl_fk`` en el setup.
    fk_nostore = models.ForeignKey('self', models.DO_NOTHING, store=False,
                                   related='mid.ctrl_fk')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_relc_owner'


fk = ProbeRelCOwner._meta.get_field('fk_nostore')
before = {
    'related_model': fk.related_model,
    'remote_model': fk.remote_field.model,
    'related_model_cached': 'related_model' in fk.__dict__,
    'comodel_name': fk.comodel_name,
    'comodel_in_dict': 'comodel_name' in fk.__dict__,
}
related_attr_keys = sorted(k for k, _ in fk.related_attrs)
errors = [e for e in checks.run_checks(app_configs=[apps.get_app_config('base')])
          if getattr(e.obj, 'model', None) is ProbeRelCOwner]
error_ids = sorted(e.id for e in errors)
state_fields = list(ModelState.from_model(ProbeRelCOwner).fields)

setup_count = ensure_field_setup()
after = {
    'related_model': fk.related_model,
    'remote_model': fk.remote_field.model,
    'related_model_cached': 'related_model' in fk.__dict__,
    'comodel_name': fk.comodel_name,
    'comodel_in_dict': 'comodel_name' in fk.__dict__,
    'related_field': getattr(fk, 'related_field', None),
    'compute': getattr(fk, 'compute', None),
    'search': getattr(fk, 'search', None),
}
descriptors = {
    'fk_nostore': type(ProbeRelCOwner.__dict__.get('fk_nostore')).__name__,
    'fk_nostore_id': type(ProbeRelCOwner.__dict__.get('fk_nostore_id')).__name__,
}

with connection.cursor() as cursor:
    for t in ('probe_relc_owner', 'probe_relc_mid', 'probe_relc_target'):
        cursor.execute(f'DROP TABLE IF EXISTS {t}')
    cursor.execute('CREATE TABLE probe_relc_target (id serial PRIMARY KEY, label varchar(8) NOT NULL)')
    cursor.execute('CREATE TABLE probe_relc_mid (id serial PRIMARY KEY, ctrl_fk_id integer NOT NULL)')
    cursor.execute('CREATE TABLE probe_relc_owner (id serial PRIMARY KEY, kept varchar(8) NOT NULL, mid_id integer NOT NULL)')
try:
    target = ProbeRelCTarget.objects.create(label='t')
    mid = ProbeRelCMid.objects.create(ctrl_fk=target)
    owner = ProbeRelCOwner.objects.create(kept='k', mid=mid)
    fetched = ProbeRelCOwner.objects.get(pk=owner.pk)
    with CaptureQueriesContext(connection) as ctx:
        try:
            value = fetched.fk_nostore
        except Exception as exc:  # noqa: BLE001 — se mide, no se traga
            value = f'EXC {type(exc).__name__}: {exc}'
    with CaptureQueriesContext(connection) as ctx_id:
        try:
            value_id = fetched.fk_nostore_id
        except Exception as exc:  # noqa: BLE001
            value_id = f'EXC {type(exc).__name__}: {exc}'
finally:
    with connection.cursor() as cursor:
        for t in ('probe_relc_owner', 'probe_relc_mid', 'probe_relc_target'):
            cursor.execute(f'DROP TABLE IF EXISTS {t}')

expected = {
    'no_relation_check_errors':      not error_ids,
    'not_in_migration_state':        'fk_nostore' not in state_fields,
    'related_attrs_carry_comodel':   'comodel_name' in related_attr_keys,
    'setup_ran':                     setup_count > 0,
    'setup_related_field_is_ctrl_fk': getattr(after['related_field'], 'name', None) == 'ctrl_fk',
    'setup_copies_comodel_name':     after['comodel_in_dict'] and after['comodel_name'] != before['comodel_name'],
    # el contrato de la fuente: tras el setup el comodelo es el del destino
    'remote_model_is_target_after_setup': after['remote_model'] is ProbeRelCTarget,
    'related_model_is_target_after_setup': after['related_model'] is ProbeRelCTarget,
    'read_returns_target_row':       getattr(value, 'pk', None) == target.pk
                                     and type(value) is ProbeRelCTarget,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("check_error_ids:", error_ids)
print("migration_state_fields:", state_fields)
print("related_attr_keys:", related_attr_keys)
print("setup_count:", setup_count)
print("before:", {k: (v.__name__ if isinstance(v, type) else v) for k, v in before.items()})
print("after:", {k: (v.__name__ if isinstance(v, type) else (getattr(v, 'name', None) if k == 'related_field' else (getattr(v, '__name__', v) if callable(v) else v))) for k, v in after.items()})
print("class descriptors:", descriptors)
print("read value:", repr(value)[:120], "| type:", type(value).__name__, "| queries:", len(ctx))
print("read value_id:", repr(value_id)[:120], "| queries:", len(ctx_id))
print("VEREDICTO related_sin_to:", 'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
