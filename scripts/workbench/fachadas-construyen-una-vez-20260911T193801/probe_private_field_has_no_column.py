"""Sonda de TASK-API-0417 — ¿un campo Django contribuido con ``private_only``
es la forma sin columna que la fuente expresa con ``store=False``?

La referencia declara UN solo tipo por campo y ``store`` es un atributo
(``odoo19c: odoo/orm/fields.py:443-458``); aquí ``store=False`` cambia la
clase (``NonStored``). El candidato de stack: ``Field.contribute_to_class(cls,
name, private_only=True)`` lo aparta de ``concrete_fields`` y de la tabla.
Veredicto por contenido: el DDL recogido, ``concrete_fields`` y
``_meta.get_field``.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import connection, models  # noqa: E402


class ProbePrivateColumn(models.Model):
    kept = models.CharField(max_length=8)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_private_column'


loose = models.CharField(max_length=8)
loose.contribute_to_class(ProbePrivateColumn, 'loose', private_only=True)

with connection.schema_editor(collect_sql=True) as editor:
    editor.create_model(ProbePrivateColumn)
ddl = '\n'.join(editor.collected_sql)

concrete = sorted(f.name for f in ProbePrivateColumn._meta.concrete_fields)
private = sorted(f.name for f in ProbePrivateColumn._meta.private_fields)
got = ProbePrivateColumn._meta.get_field('loose')
expected = {
    'loose_not_in_ddl': '"loose"' not in ddl,
    'kept_in_ddl': '"kept"' in ddl,
    'concrete_fields': concrete == ['id', 'kept'],
    'private_fields': private == ['loose'],
    'get_field_returns_same_object': got is loose,
    'column_attr': got.column == 'loose',
    'concrete_flag': got.concrete is False,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("DDL:", ddl.replace('\n', ' '))
print("VEREDICTO private_only:", 'OK' if all(expected.values()) else 'FALLA')

# Segundo candidato: la forma de ``ForeignObject`` — ``column is None`` hace
# ``concrete False`` (``django/db/models/fields/__init__.py``,
# ``concrete = column is not None`` en ``set_attributes_from_name``).
class ProbeColumnNone(models.Model):
    kept = models.CharField(max_length=8)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_column_none'


class NoColumnChar(models.CharField):
    def get_attname_column(self):
        attname, _column = super().get_attname_column()
        return attname, None


bare = NoColumnChar(max_length=8)
bare.contribute_to_class(ProbeColumnNone, 'bare', private_only=True)
with connection.schema_editor(collect_sql=True) as editor:
    editor.create_model(ProbeColumnNone)
ddl2 = '\n'.join(editor.collected_sql)
got2 = ProbeColumnNone._meta.get_field('bare')
expected2 = {
    'bare_not_in_ddl': '"bare"' not in ddl2,
    'concrete_fields': sorted(f.name for f in ProbeColumnNone._meta.concrete_fields) == ['id', 'kept'],
    'in_fields': 'bare' in [f.name for f in ProbeColumnNone._meta.fields],
    'get_field_same_object': got2 is bare,
    'column_is_none': got2.column is None,
    'concrete_flag_false': got2.concrete is False,
    'instance_init_survives': ProbeColumnNone(kept='k').kept == 'k',
}
for key, ok in expected2.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("VEREDICTO column_none:", 'OK' if all(expected2.values()) else 'FALLA')
raise SystemExit(0 if all(expected2.values()) else 1)
