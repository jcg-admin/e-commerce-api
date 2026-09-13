"""Sonda de #351 (create por contenido) — ¿un recordset construido con
``_from_ids`` sobre un modelo derivado de ``BaseModel`` con dos filas
persistidas tiene el protocolo que ``create`` necesita para devolverlo?

Claves esperadas, por contenido (``odoo19c: odoo/orm/models.py:4849-4948``
devuelve ``self.browse(ids)`` con la cache poblada): tamaño, orden de
iteración, lectura de un campo por registro, desempaquetado y ``ensure_one``.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import connection, models, transaction  # noqa: E402
from orm.environments import env  # noqa: E402
from orm.models import BaseModel  # noqa: E402


class ProbeRecordset(BaseModel):
    name = models.CharField(max_length=16)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_recordset_from_ids'


results = {}
try:
    with transaction.atomic():
        with connection.schema_editor() as editor:
            editor.create_model(ProbeRecordset)
        first = ProbeRecordset.objects.create(name='Ada')
        second = ProbeRecordset.objects.create(name='Grace')
        ids = (first.pk, second.pk)
        rs = ProbeRecordset._from_ids(env(), ids, ids)
        try:
            results['len_is_two'] = len(rs) == 2
        except Exception as exc:  # noqa: BLE001
            results['len_is_two'] = f'EXC {type(exc).__name__}: {exc}'
        try:
            results['iter_pk_in_order'] = [r.pk for r in rs] == list(ids)
        except Exception as exc:  # noqa: BLE001
            results['iter_pk_in_order'] = f'EXC {type(exc).__name__}: {exc}'
        try:
            results['iter_name_reads'] = [r.name for r in rs] == ['Ada', 'Grace']
        except Exception as exc:  # noqa: BLE001
            results['iter_name_reads'] = f'EXC {type(exc).__name__}: {exc}'
        try:
            one, two = rs
            results['unpack_two'] = (one.pk, two.pk) == ids
        except Exception as exc:  # noqa: BLE001
            results['unpack_two'] = f'EXC {type(exc).__name__}: {exc}'
        try:
            single = ProbeRecordset._from_ids(env(), ids[:1], ids[:1])
            results['singleton_returns_self'] = single.ensure_one() is single
        except Exception as exc:  # noqa: BLE001
            results['singleton_returns_self'] = f'EXC {type(exc).__name__}: {exc}'
        try:
            results['browse_from_empty'] = len(ProbeRecordset._from_ids(env(), (), ()).browse(ids)) == 2
        except Exception as exc:  # noqa: BLE001
            results['browse_from_empty'] = f'EXC {type(exc).__name__}: {exc}'
        raise RuntimeError('rollback')
except RuntimeError:
    pass

for key, value in results.items():
    print(f"{key}: {'OK' if value is True else 'FALLA ' + str(value)}")
ok = all(v is True for v in results.values())
print('VEREDICTO recordset_from_ids:', 'OK' if ok else 'FALLA')
raise SystemExit(0 if ok else 1)
