"""Sonda L de TASK-API-0417 — CONTROL DE ANULACIÓN: con la guarda retirada
(``SET_NULL``), ¿borrar un país revienta?

Par de control de :ref:`h-api-1110` y bloqueante de TASK-API-0412.

**Esta sonda cambió de papel al aterrizar TASK-API-0426, y el cambio es la
evidencia.** Antes medía la política que el campo *heredaba*: ``_apply_ondelete``
resolvía ``'set null'`` para todo ``null=True`` sin ``ondelete`` declarado, y el
recolector de ``delete()`` sólo omite ``DO_NOTHING``. Corrida sin tocar una línea
después del arreglo, reportó ``politica del campo: DO_NOTHING`` y ``sobrevivio:
True`` — su veredicto viró a FALLA porque el fenómeno que afirmaba desapareció
(``scripts/evidence/politica2-2026-09-12T08-23-35-001.log``, conservado).

Ese viraje es lo que ``metrica-decide-la-conclusion.md`` (sub-patrón D) pide de
un control: **tiene que poder fallar**. Así que la sonda pasa a medir el
fenómeno con la guarda **anulada** a mano — se retira el ``DO_NOTHING`` que
``fields_relational.py`` fuerza ahora para todo campo sin columna, y se comprueba
que caen exactamente los borrados que dependen de ella. Un verde aquí con la
guarda retirada diría que el arreglo no arregla nada.

Se mide por contenido: se borra un país RECIÉN creado, con la compañía ya
declarando el campo hacia él, y se reporta el reventón o su ausencia.
"""
import os
import traceback

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields  # noqa: E402,F401
from django.db import connection, models  # noqa: E402
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
#: LA ANULACIÓN: se retira la guarda que ``fields_relational.py`` acaba de
#: instalar —``if not has_column: kwargs['on_delete'] = models.DO_NOTHING``— y se
#: repone la política que el campo heredaría de ``_apply_ondelete``
#: (``'set null'`` para todo ``null=True`` sin ``ondelete`` declarado). El
#: recolector de ``delete()`` sólo omite ``DO_NOTHING``, así que con cualquier
#: otra política recorre el campo y manda a emitir un ``UPDATE`` sobre una
#: columna que no existe.
country_field.remote_field.on_delete = models.SET_NULL
country_field.contribute_to_class(ResCompany, 'country')
mark_model_for_setup(ResCompany)
setup_count = ensure_field_setup()

policy = getattr(country_field.remote_field.on_delete, '__name__', None)

#: Código PROPIO de esta sonda y limpieza por SQL crudo: las dos sondas del par
#: corren a la vez en el pool contra la MISMA base, y con el mismo código la
#: segunda moría en la clave única antes de medir nada
#: (``scripts/evidence/politica-2026-09-12T08-11-44-003.log``). El SQL crudo
#: además esquiva el recolector, que es justo lo que está roto.
CODE = 'Z1'


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
    'the_guard_was_actually_nullified':   policy == 'SET_NULL',
    'delete_survives_matches_the_policy': survives is False,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count, "| politica del campo:", policy)
print("esperado que sobreviva:", False, "| sobrevivio:", survives)
print("borrado del pais:", delete_error or 'sin error')
print("marco del reventon:", delete_frame)
print("VEREDICTO la_politica_decide_el_reventon:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
