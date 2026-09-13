"""Sonda de #351 (create por contenido) — dos preguntas que la escritura del
porte necesita medidas, no supuestas.

A. ¿``bulk_create`` sobre PostgreSQL devuelve los ``pk`` de las filas
   insertadas, en el orden de entrada? (``INSERT ... RETURNING "id"`` de
   ``odoo19c: odoo/orm/models.py:4893``.) Claves esperadas:
   ``can_return_rows_from_bulk_insert`` es ``True``; los pk asignados son
   enteros crecientes en el orden de la lista.
B. ¿Qué receptores del cuerpo de ``create`` tiene cada adoptante de
   ``DefaultGetMixin`` por su MRO? Se mide por CONTENIDO (el símbolo resuelve a
   un invocable en el MRO), no por ``hasattr`` sobre la instancia.
C. ¿Qué modelos concretos derivan hoy de ``BaseModel``?
D. ¿Un objeto construido con ``_from_ids`` sobre un modelo que NO deriva de
   ``BaseModel`` puede leer ``pk``? (Es lo que decide si hoistear ``_from_ids``
   a ``DefaultGetMixin`` basta.)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.apps import apps  # noqa: E402
from django.db import connection, models, transaction  # noqa: E402
from django.db.models.base import ModelState  # noqa: E402
from orm.environments import env  # noqa: E402
from orm.models import BaseModel, DefaultGetMixin  # noqa: E402


class ProbeBulk(BaseModel):
    name = models.CharField(max_length=16)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_bulk_create_ids'


results = {}
# --- A ---
results['can_return_rows_from_bulk_insert'] = (
    connection.features.can_return_rows_from_bulk_insert)
try:
    with transaction.atomic():
        with connection.schema_editor() as editor:
            editor.create_model(ProbeBulk)
        rows = [ProbeBulk(name=n) for n in ('Ada', 'Grace', 'Edsger')]
        created = ProbeBulk.objects.bulk_create(rows)
        pks = [r.pk for r in created]
        results['bulk_pks'] = pks
        results['bulk_pks_all_int'] = all(isinstance(p, int) for p in pks)
        results['bulk_pks_increasing'] = pks == sorted(pks)
        results['bulk_same_objects'] = all(a is b for a, b in zip(rows, created))
        results['bulk_ids_triple'] = [getattr(r, '_ids', None) for r in created]
        results['bulk_state_adding'] = [r._state.adding for r in created]
        with connection.schema_editor() as editor:
            editor.delete_model(ProbeBulk)
        transaction.set_rollback(True)
except Exception as exc:  # noqa: BLE001
    results['bulk_error'] = f'{type(exc).__name__}: {exc}'

# --- B ---
NEEDED = ['_from_ids', 'browse', 'check_access', '_check_field_access',
          '_has_field_access', '_load_records_split_relational',
          '_load_records_apply_relational', '_load_records_coerce_vals',
          'write', '_check_company', '_check_company_auto',
          '_add_precomputed_values', '_validate_fields', '_fields',
          '_add_missing_default_values', 'default_get', '_inherits',
          '_inherits_fields', 'objects']
adopters = [m for m in apps.get_models() if issubclass(m, DefaultGetMixin)]
results['adopters'] = sorted(m._meta.label for m in adopters)
for m in adopters:
    present = {}
    for name in NEEDED:
        owner = None
        for klass in m.__mro__:
            if name in vars(klass):
                owner = klass.__name__
                break
        present[name] = owner
    results[f'mro:{m._meta.label}'] = present
    results[f'is_basemodel:{m._meta.label}'] = issubclass(m, BaseModel)

# --- C ---
results['basemodel_concrete'] = sorted(
    m._meta.label for m in apps.get_models() if issubclass(m, BaseModel))

# --- D ---
ResPartner = apps.get_model('base', 'ResPartner')
try:
    obj = object.__new__(ResPartner)
    obj._state = ModelState()
    obj.env = env()
    obj._ids = (1,)
    obj._prefetch_ids = obj._ids
    try:
        results['plain_from_ids_pk'] = repr(obj.pk)
    except Exception as exc:  # noqa: BLE001
        results['plain_from_ids_pk'] = f'EXC {type(exc).__name__}: {exc}'
    try:
        results['plain_from_ids_len'] = repr(len(obj))
    except Exception as exc:  # noqa: BLE001
        results['plain_from_ids_len'] = f'EXC {type(exc).__name__}: {exc}'
    try:
        results['plain_from_ids_iter'] = repr([r for r in obj][:1])
    except Exception as exc:  # noqa: BLE001
        results['plain_from_ids_iter'] = f'EXC {type(exc).__name__}: {exc}'
except Exception as exc:  # noqa: BLE001
    results['plain_from_ids_build'] = f'EXC {type(exc).__name__}: {exc}'

for key, value in results.items():
    print(f'{key}: {value}')
