"""Sonda D de TASK-API-0417 — la ruta de lectura de un ``ForeignKey`` REAL con
``store=False`` y ``related=`` (con ``to`` explícito), sobre una fila real.

La sonda A midió la CONSTRUCCIÓN (sin columna, sin accessor inverso, fuera de
la migración). Ésta mide la LECTURA, que es lo que ``_install_field_descriptor``
deja a medias: sobre ``fk_nostore_id`` (el ``attname``, sin columna) cuelga el
descriptor de la fuente, pero sobre ``fk_nostore`` (el ``name``) Django ya
colgó su ``ForwardManyToOneDescriptor``, que lee ``fk_nostore_id`` y resuelve
el registro por ``related_model``. Se mide:

- qué descriptor hay en cada nombre de clase;
- qué devuelve ``owner.fk_nostore`` tras el setup: ¿la fila del comodelo
  (contrato de la fuente, ``Many2one.convert_to_record``), un entero, o una
  excepción?;
- cuántas consultas cuesta, y si coincide con ``owner.ctrl_fk``.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import connection, models  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

import fields  # noqa: E402,F401  — registra los enganches de orm.fields
from orm.model_classes import ensure_field_setup  # noqa: E402
from orm.models import BaseModel  # noqa: E402


class ProbeRelDTarget(BaseModel):
    label = models.CharField(max_length=8)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_reld_target'


class ProbeRelDOwner(BaseModel):
    kept = models.CharField(max_length=8)
    ctrl_fk = models.ForeignKey(ProbeRelDTarget, on_delete=models.CASCADE,
                                related_name='reld_owners')
    fk_nostore = models.ForeignKey(ProbeRelDTarget, on_delete=models.CASCADE,
                                   store=False, related='ctrl_fk')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_reld_owner'


fk = ProbeRelDOwner._meta.get_field('fk_nostore')
setup_count = ensure_field_setup()
descriptors = {
    'fk_nostore': type(ProbeRelDOwner.__dict__.get('fk_nostore')).__name__,
    'fk_nostore_id': type(ProbeRelDOwner.__dict__.get('fk_nostore_id')).__name__,
    'ctrl_fk': type(ProbeRelDOwner.__dict__.get('ctrl_fk')).__name__,
    'ctrl_fk_id': type(ProbeRelDOwner.__dict__.get('ctrl_fk_id')).__name__,
}
convert_to_record = type(fk).convert_to_record
convert_owner = getattr(convert_to_record, '__qualname__', repr(convert_to_record))

with connection.cursor() as cursor:
    cursor.execute('DROP TABLE IF EXISTS probe_reld_owner')
    cursor.execute('DROP TABLE IF EXISTS probe_reld_target')
    cursor.execute('CREATE TABLE probe_reld_target (id serial PRIMARY KEY, label varchar(8) NOT NULL)')
    cursor.execute('CREATE TABLE probe_reld_owner (id serial PRIMARY KEY, kept varchar(8) NOT NULL, ctrl_fk_id integer NOT NULL)')
try:
    target = ProbeRelDTarget.objects.create(label='t')
    owner = ProbeRelDOwner.objects.create(kept='k', ctrl_fk=target)
    fetched = ProbeRelDOwner.objects.get(pk=owner.pk)
    with CaptureQueriesContext(connection) as ctx_name:
        try:
            value = fetched.fk_nostore
        except Exception as exc:  # noqa: BLE001 — se mide, no se traga
            value = f'EXC {type(exc).__name__}: {exc}'
    with CaptureQueriesContext(connection) as ctx_attname:
        try:
            value_id = fetched.fk_nostore_id
        except Exception as exc:  # noqa: BLE001
            value_id = f'EXC {type(exc).__name__}: {exc}'
    fresh = ProbeRelDOwner(kept='f', ctrl_fk=target)
    try:
        fresh_value = fresh.fk_nostore
    except Exception as exc:  # noqa: BLE001
        fresh_value = f'EXC {type(exc).__name__}: {exc}'
finally:
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS probe_reld_owner')
        cursor.execute('DROP TABLE IF EXISTS probe_reld_target')

expected = {
    'setup_ran':                   setup_count > 0,
    'compute_installed':           getattr(fk, 'compute', None) is not None,
    # contrato de la fuente: leer un many2one devuelve el registro del comodelo
    'read_by_name_returns_target': type(value) is ProbeRelDTarget and value.pk == target.pk,
    'read_by_attname_returns_id':  value_id == target.pk,
    'fresh_read_returns_target':   type(fresh_value) is ProbeRelDTarget and fresh_value.pk == target.pk,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count)
print("class descriptors:", descriptors)
print("convert_to_record owner:", convert_owner)
print("read by name:", repr(value)[:120], "| type:", type(value).__name__, "| queries:", len(ctx_name))
print("read by attname:", repr(value_id)[:120], "| queries:", len(ctx_attname))
print("fresh read:", repr(fresh_value)[:120], "| type:", type(fresh_value).__name__)
print("VEREDICTO fk_store_false_lectura:", 'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
