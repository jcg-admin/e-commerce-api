"""Sonda B de TASK-API-0417 — la ruta de lectura de un escalar REAL de Django
(``CharField``) con ``store=False`` y ``default=``, sin ``compute`` ni
``related``.

El sujeto es un ``BaseModel``: la rama por defecto de la fuente llama a
``record.default_get`` (``odoo19c: odoo/orm/fields.py:1792``), que vive en el
modelo, no en el campo. Hoy la fachada ``Char`` devuelve ``NonStored`` en esa rama; esta sonda salta
la fachada y mide, sobre ``models.CharField(store=False, default=...)``:

- ``store`` sigue en ``False`` DESPUÉS de ``contribute_to_class`` —
  ``_setup_attrs__`` re-deriva desde ``_args__``, y ``apply_source_defaults``
  vacía ``kwargs``, así que el valor podría perderse en el camino;
- la lectura sobre una fila traída de la base y sobre una instancia nueva
  devuelve el ``default`` con **cero** consultas (``CaptureQueriesContext``):
  el ``DeferredAttribute`` de Django haría ``refresh_from_db`` en el fallo de
  caché, y sin columna eso es un ``ProgrammingError``.

Veredicto INVENTORY por clave, como en la sonda A.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import connection, models  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

import fields  # noqa: E402,F401  — registra los enganches de orm.fields
from orm.models import BaseModel  # noqa: E402


class ProbeScalarRow(BaseModel):
    kept = models.CharField(max_length=8)
    loose = models.CharField(max_length=8, store=False, default='dflt')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_scalar_row'


loose = ProbeScalarRow._meta.get_field('loose')
with connection.schema_editor(collect_sql=True) as editor:
    editor.create_model(ProbeScalarRow)
ddl = '\n'.join(editor.collected_sql)

#: El DDL va por ``cursor()`` y no por ``schema_editor()``: éste envuelve en
#: ``atomic`` y su ``commit`` dispara el ``flush`` del entorno, que sin
#: ``default_env`` pide el xmlid ``base.public_user`` — ausente fuera de los
#: fixtures de pytest. En autocommit el DDL por cursor no pasa por ahí.
with connection.cursor() as cursor:
    cursor.execute('DROP TABLE IF EXISTS probe_scalar_row')
    cursor.execute('CREATE TABLE probe_scalar_row (id serial PRIMARY KEY, kept varchar(8) NOT NULL)')
try:
    row = ProbeScalarRow.objects.create(kept='k')
    fetched = ProbeScalarRow.objects.get(pk=row.pk)
    with CaptureQueriesContext(connection) as ctx_fetched:
        try:
            fetched_value = fetched.loose
        except Exception as exc:  # noqa: BLE001 — se mide, no se traga
            fetched_value = f'EXC {type(exc).__name__}: {exc}'
    fresh = ProbeScalarRow(kept='f')
    with CaptureQueriesContext(connection) as ctx_fresh:
        try:
            fresh_value = fresh.loose
        except Exception as exc:  # noqa: BLE001
            fresh_value = f'EXC {type(exc).__name__}: {exc}'
    fresh.loose = 'set'
    assigned_value = fresh.loose
    with CaptureQueriesContext(connection) as ctx_save:
        try:
            fresh.save()
            save_result = 'ok'
        except Exception as exc:  # noqa: BLE001
            save_result = f'EXC {type(exc).__name__}: {exc}'
finally:
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS probe_scalar_row')

expected = {
    'type_is_charfield':         type(loose) is models.CharField,
    'store_false_after_contribute': loose.store is False,
    'column_none':               loose.column is None,
    'not_in_ddl':                '"loose"' not in ddl,
    'fetched_reads_default':     fetched_value == 'dflt',
    # La fuente consulta ``ir.default`` UNA vez en frío (``ormcache`` miss,
    # ``odoo19c: ir_default.py:171-175``) y ninguna en caliente: el veredicto
    # mide QUÉ consulta, no cuántas.
    'fetched_cold_query_is_ir_default':
        len(ctx_fetched) <= 1
        and all('ir_default' in q['sql'] for q in ctx_fetched),
    'fresh_reads_default':       fresh_value == 'dflt',
    'fresh_zero_queries':        len(ctx_fresh) == 0,
    'assignment_sticks':         assigned_value == 'set',
    'save_ignores_loose':        save_result == 'ok'
                                 and all('loose' not in q['sql'] for q in ctx_save),
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("fetched_value:", fetched_value, "| fresh_value:", fresh_value,
      "| save:", save_result)
print("queries fetched/fresh/save:", len(ctx_fetched), len(ctx_fresh), len(ctx_save))
print("cold queries:", [q['sql'][:80] for q in ctx_fetched])
print("DDL:", ddl.replace('\n', ' '))
print("VEREDICTO escalar_store_false:", 'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
