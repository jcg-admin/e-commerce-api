"""Sonda E de TASK-API-0417 — traza del ``related=`` sobre una fila NUEVA.

La sonda D midió que ``owner.fk_nostore`` devuelve el registro del comodelo
sobre una fila real y revienta sobre una instancia sin ``pk`` con
*«Compute method failed to assign None(None,).fk_nostore»*. Esta sonda traza
la fila nueva paso a paso para nombrar la causa, en dos tipos —FK y escalar—
para saber si es del relacional o del cómputo en general:

- qué devuelve ``record_ids(fresh)``;
- qué queda en ``fresh.__dict__`` tras ``compute_value``;
- qué claves tiene la caché del campo tras el cómputo;
- si ``_cache_missing_ids(fresh)`` sigue nombrando a la fila.

El comodelo tiene tabla real (DDL por ``cursor``, como las sondas C y D):
``ForwardManyToOneDescriptor.__get__`` consulta el comodelo tras leer la
clave, así que un destino sólo en memoria mide un artefacto de la sonda y
no la costura. Las consultas de cada primera lectura se cuentan.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import connection, models  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

import fields  # noqa: E402,F401
from orm.environments import env as get_environment  # noqa: E402
from orm.model_classes import ensure_field_setup  # noqa: E402
from orm.models import BaseModel  # noqa: E402
from orm.utils import record_ids  # noqa: E402


class ProbeRelETarget(BaseModel):
    label = models.CharField(max_length=8)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_rele_target'


class ProbeRelEOwner(BaseModel):
    kept = models.CharField(max_length=8)
    ctrl_fk = models.ForeignKey(ProbeRelETarget, on_delete=models.CASCADE,
                                related_name='rele_owners')
    fk_nostore = models.ForeignKey(ProbeRelETarget, on_delete=models.CASCADE,
                                   store=False, related='ctrl_fk')
    label_nostore = models.CharField(max_length=8, store=False,
                                     related='ctrl_fk.label')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_rele_owner'


ensure_field_setup()
env = get_environment()
with connection.cursor() as cursor:
    cursor.execute('DROP TABLE IF EXISTS probe_rele_owner')
    cursor.execute('DROP TABLE IF EXISTS probe_rele_target')
    cursor.execute('CREATE TABLE probe_rele_target (id serial PRIMARY KEY, label varchar(8) NOT NULL)')
    cursor.execute('CREATE TABLE probe_rele_owner (id serial PRIMARY KEY, kept varchar(8) NOT NULL, ctrl_fk_id integer NOT NULL)')
try:
    target = ProbeRelETarget.objects.create(label='t')
    run_probe = True
except Exception as exc:  # noqa: BLE001 — se mide
    print("EXC creando el comodelo:", type(exc).__name__, exc)
    run_probe = False

# 1. La PRIMERA lectura sobre una fila nueva, sin cómputo previo — el caso
#    que la sonda D midió en rojo.
first = ProbeRelEOwner(kept='f', ctrl_fk=target)
first_reads, first_queries = {}, {}
for name in ('label_nostore', 'fk_nostore'):
    with CaptureQueriesContext(connection) as ctx:
        try:
            first_reads[name] = getattr(first, name)
        except Exception as exc:  # noqa: BLE001 — se mide
            first_reads[name] = f'EXC {type(exc).__name__}: {exc}'
    first_queries[name] = len(ctx)
    print(f"first read {name}:", repr(first_reads[name])[:100],
          "| type:", type(first_reads[name]).__name__,
          "| queries:", first_queries[name])

# 2. La traza: cómputo explícito y qué queda en cada almacén.
fresh = ProbeRelEOwner(kept='f', ctrl_fk=target)
print("record_ids(fresh):", record_ids(fresh))
print("fresh.pk:", fresh.pk, "| _ids:", getattr(fresh, '_ids', 'sin terna'))
report = {}
for name in ('label_nostore', 'fk_nostore'):
    field = ProbeRelEOwner._meta.get_field(name)
    before_dict = {k: v for k, v in fresh.__dict__.items() if name in k}
    try:
        field.compute_value(fresh)
        computed = 'ok'
    except Exception as exc:  # noqa: BLE001 — se mide
        computed = f'EXC {type(exc).__name__}: {exc}'
    after_dict = {k: v for k, v in fresh.__dict__.items() if name in k}
    cache_keys = list(field._get_cache(env).keys())
    missing = list(field._cache_missing_ids(fresh))
    try:
        read = getattr(fresh, name)
    except Exception as exc:  # noqa: BLE001
        read = f'EXC {type(exc).__name__}: {exc}'
    report[name] = dict(
        readonly=field.readonly, store=field.store,
        computed=computed, before_dict=before_dict, after_dict=after_dict,
        cache_keys=cache_keys, missing=missing,
        read=f'{type(read).__name__} pk={getattr(read, "pk", read)!r}')
    for k, v in report[name].items():
        print(f"{name}.{k}: {v}")

with connection.cursor() as cursor:
    cursor.execute('DROP TABLE IF EXISTS probe_rele_owner')
    cursor.execute('DROP TABLE IF EXISTS probe_rele_target')

expected = {
    'scalar_first_read_ok':  first_reads['label_nostore'] == 't',
    'scalar_first_read_zero_queries': first_queries['label_nostore'] == 0,
    'fk_first_read_ok':      type(first_reads['fk_nostore']) is ProbeRelETarget
                             and first_reads['fk_nostore'].pk == target.pk,
    'scalar_read_after_compute_ok': report['label_nostore']['read'] == "str pk='t'",
    'fk_read_after_compute_ok':
        report['fk_nostore']['read'] == f'ProbeRelETarget pk={target.pk}',
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("VEREDICTO related_fila_nueva:", 'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
