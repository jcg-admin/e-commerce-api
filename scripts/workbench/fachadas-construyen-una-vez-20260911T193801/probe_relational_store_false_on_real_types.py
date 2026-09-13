"""Sonda A de TASK-API-0417 — ¿un relacional REAL de Django (``ForeignKey``,
``ManyToManyField``) con ``store=False`` es la forma sin columna que la fuente
expresa con un solo tipo y ``store`` como atributo?

Hoy las fachadas devuelven ``NonStored`` en esa rama; esta sonda salta la
fachada y construye el tipo real con ``store=False`` para medir qué hace el
sustrato ya parchado (``set_attributes_from_name`` → ``column=None``;
``contribute_to_class`` → ``private_only``). Cada clave se declara con su
valor esperado y su veredicto INVENTORY:

- ``lo trae hecho``  — hay símbolo instalado y basta llamarlo;
- ``con qué construirlo`` — no hay símbolo, pero las primitivas están;
- ``nativo`` — hay que implementarlo.

Veredicto por contenido, no por presencia: se leen ``concrete_fields``, el
DDL recogido, los accesores del modelo destino, el registro de apps y el
``ModelState`` de migraciones, no ``hasattr``.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.apps import apps  # noqa: E402
from django.core import checks  # noqa: E402
from django.db import connection, models  # noqa: E402
from django.db.migrations.state import ModelState  # noqa: E402

import fields  # noqa: E402,F401  — registra los enganches de orm.fields


class ProbeRelTarget(models.Model):
    label = models.CharField(max_length=8)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_rel_target'


class ProbeRelOwner(models.Model):
    kept = models.CharField(max_length=8)
    ctrl_fk = models.ForeignKey(ProbeRelTarget, on_delete=models.CASCADE,
                                related_name='ctrl_owners')
    ctrl_m2m = models.ManyToManyField(ProbeRelTarget, related_name='ctrl_m2m_owners')
    fk_nostore = models.ForeignKey(ProbeRelTarget, on_delete=models.CASCADE,
                                   store=False, related='ctrl_fk')
    m2m_nostore = models.ManyToManyField(ProbeRelTarget, store=False,
                                         related='ctrl_fk.ctrl_m2m_owners')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_rel_owner'


with connection.schema_editor(collect_sql=True) as editor:
    editor.create_model(ProbeRelOwner)
ddl = '\n'.join(editor.collected_sql)

opts = ProbeRelOwner._meta
fk = opts.get_field('fk_nostore')
m2m = opts.get_field('m2m_nostore')
concrete = sorted(f.name for f in opts.concrete_fields)
m2m_names = sorted(f.name for f in opts.many_to_many)
private = sorted(f.name for f in opts.private_fields)
target_attrs = set(vars(ProbeRelTarget))
through_labels = sorted(
    m._meta.label for m in apps.get_app_config('base').get_models(include_auto_created=True)
    if m._meta.auto_created and 'proberelowner' in m._meta.model_name)
state_fields = list(ModelState.from_model(ProbeRelOwner).fields)
errors = [e for e in checks.run_checks(app_configs=[apps.get_app_config('base')])
          if getattr(e.obj, 'model', None) is ProbeRelOwner]
error_ids = sorted(e.id for e in errors)

expected = {
    # lo trae hecho: private_only + column=None ya aparta al campo del DDL
    'fk_store_false':              fk.store is False,
    'fk_column_none':              fk.column is None,
    'fk_not_concrete':             fk.concrete is False,
    'fk_not_in_concrete_fields':   'fk_nostore' not in concrete,
    'fk_not_in_ddl':               '"fk_nostore_id"' not in ddl,
    'fk_in_private_fields':        'fk_nostore' in private,
    'fk_not_in_migration_state':   'fk_nostore' not in state_fields,
    'ctrl_fk_in_ddl':              '"ctrl_fk_id"' in ddl,
    # con qué construirlo: el reverso y la intermedia dependen del lazy op
    'fk_no_reverse_on_target':     'proberelowner_set' not in target_attrs
                                    and 'fk_nostore' not in target_attrs,
    'fk_remote_model_resolved':    fk.remote_field.model is ProbeRelTarget,
    'm2m_store_false':             m2m.store is False,
    'm2m_not_in_local_m2m':        'm2m_nostore' not in [f.name for f in opts.local_many_to_many],
    'm2m_through_is_none':         m2m.remote_field.through is None,
    'm2m_no_through_model':        all('m2m_nostore' not in t for t in through_labels),
    'm2m_not_in_migration_state':  'm2m_nostore' not in state_fields,
    'm2m_no_reverse_on_target':    'proberelowner_set' not in target_attrs,
    'ctrl_m2m_through_exists':     any('ctrl_m2m' in t for t in through_labels),
    'no_relation_check_errors':    not any(i.startswith('fields.E3') for i in error_ids),
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("concrete_fields:", concrete)
print("many_to_many:", m2m_names)
print("private_fields:", private)
print("through_labels:", through_labels)
print("migration_state_fields:", state_fields)
print("check_error_ids:", error_ids)
print("target_reverse_attrs:", sorted(a for a in target_attrs if 'owner' in a))
print("DDL:", ddl.replace('\n', ' '))
print("VEREDICTO relacional_store_false:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
