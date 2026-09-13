"""Sonda M de TASK-API-0417 — con la guarda puesta, ¿el campo sin columna nace en
``DO_NOTHING`` y sobrevive el borrado del país?

Par de control de :ref:`h-api-1110` y cierre de TASK-API-0426.

**La mutación se retiró al aterrizar el arreglo.** Mientras el defecto vivía,
esta sonda forzaba ``country_field.remote_field.on_delete = models.DO_NOTHING``
a mano para demostrar que la política era la causa. Ese arreglo ya está en
``fields_relational.py`` —``if not has_column: kwargs['on_delete'] =
models.DO_NOTHING``, para TODO campo sin columna y no sólo para el ``related=``
sin ``to``— así que la línea manual sobraba y escondía lo que ahora hay que
medir: que la guarda lo hace **sola**.

Por eso la sonda declara el campo tal cual y afirma **dos** cosas por contenido:
que la política resuelta ES ``DO_NOTHING`` sin que nadie la toque, y que el
borrado sobrevive. Su hermana L es el control de anulación —retira la guarda y
comprueba que el borrado vuelve a reventar—, así que el par sigue discriminando.

Se mide por contenido: se borra un país RECIÉN creado, con la compañía ya
declarando el campo hacia él, y se reporta el reventón o su ausencia.
"""
import os
import traceback

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields  # noqa: E402,F401
from django.db import connection  # noqa: E402
from orm.fields_relational import Many2one  # noqa: E402
from orm.model_classes import ensure_field_setup, mark_model_for_setup  # noqa: E402

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_country import ResCountry  # noqa: E402


def _compute_address(self):
    """≙ ``_compute_address`` — la dirección la pone el partner."""
    self.country = getattr(self.partner, 'country', None)


def _inverse_country(self):
    """≙ ``_inverse_country`` — escribir en la compañía escribe el partner."""
    self.partner.country = self.country
    self.partner.save()


ResCompany._compute_address = _compute_address
ResCompany._inverse_country = _inverse_country

country_field = Many2one(ResCountry, compute='_compute_address',
                         inverse='_inverse_country', null=True)
#: SIN MUTACIÓN: el campo se declara tal cual. ``DO_NOTHING`` es lo único que el
#: recolector salta (``deletion.py``: ``if related.field.remote_field.on_delete
#: is DO_NOTHING: continue``), y ahora lo fuerza la propia construcción del campo
#: para todo ``not has_column``.
country_field.contribute_to_class(ResCompany, 'country')
mark_model_for_setup(ResCompany)
setup_count = ensure_field_setup()

policy = getattr(country_field.remote_field.on_delete, '__name__', None)

#: Código PROPIO de esta sonda y limpieza por SQL crudo: las dos sondas del par
#: corren a la vez en el pool contra la MISMA base, y con el mismo código la
#: segunda moría en la clave única antes de medir nada
#: (``scripts/evidence/politica-2026-09-12T08-11-44-003.log``). El SQL crudo
#: además esquiva el recolector, que es justo lo que está roto.
CODE = 'Z2'


def _purge():
    with connection.cursor() as cursor:
        cursor.execute('DELETE FROM res_country WHERE code = %s', [CODE])


_purge()
delete_error = delete_frame = None
country = None
try:
    country = ResCountry.objects.create(code=CODE, name='Probe Ondelete')
    ResCountry.objects.filter(pk=country.pk).delete()
    country = None
except Exception as exc:  # noqa: BLE001 — el reventón ES lo que se mide
    delete_error = f'EXC {type(exc).__name__}: {exc}'
    frames = traceback.extract_tb(exc.__traceback__)
    delete_frame = ' | '.join(f'{f.filename.split("/")[-1]}:{f.lineno} {f.name}'
                              for f in frames[-3:])
finally:
    try:
        _purge()
    except Exception as exc:  # noqa: BLE001
        print('limpieza:', f'EXC {type(exc).__name__}: {exc}')

survives = delete_error is None
expected = {
    'setup_ran':          setup_count > 0,
    'no_column':          getattr(country_field, 'column', 'sentinel') is None,
    'the_guard_forces_do_nothing':        policy == 'DO_NOTHING',
    'delete_survives_matches_the_policy': survives is True,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count, "| politica del campo:", policy)
print("esperado que sobreviva:", True, "| sobrevivio:", survives)
print("borrado del pais:", delete_error or 'sin error')
print("marco del reventon:", delete_frame)
print("VEREDICTO la_politica_decide_el_reventon:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
