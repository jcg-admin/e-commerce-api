"""Sonda I de TASK-API-0417 — con el campo declarado, ¿la escritura llega a la
COLUMNA del partner?

Segunda mitad de la sonda H, que sólo midió el cierre de la costura. El sujeto
son los modelos REALES —``ResCompany`` / ``ResPartner`` / ``ResCountry``— porque
el radio de explosión impide medir sobre modelos de sonda: cualquier lectura
dispara ``ensure_field_setup()`` y el árbol entero aborta mientras falte el campo
(``scripts/evidence/bloqueantes2-2026-09-12T07-50-09-00{1,2}.log``).

El campo se declara **en el proceso**, no en el árbol, con la forma de la
referencia (``compute='_compute_address'`` + ``inverse='_inverse_country'``). Se
mide por contenido:

- que la lectura devuelva el país del partner (el cómputo corre);
- que ``company.country = otro`` despache el inverso declarado — contador, porque
  el inverso no devuelve nada y su ejecución sólo es observable por efecto;
- que el valor llegue a ``res_partner.country_id`` RELEÍDA de la base, que es el
  control que ``write-2026-09-12T00-27-19-001.log`` dio en FALLA con ``related=``.

El eje de la escritura es el que decide si TASK-API-0412 necesita además cablear
el despacho del inverso: ``BaseModel.save`` (``orm/models.py:1351``) no tiene
conjunto de escritura, así que no puede agrupar inversos como
``_load_records`` (``:2428-2438``).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields  # noqa: E402,F401
from orm.fields_relational import Many2one  # noqa: E402
from orm.model_classes import ensure_field_setup, mark_model_for_setup  # noqa: E402

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_country import ResCountry  # noqa: E402
from addons.base.models.res_partner import ResPartner  # noqa: E402

inverse_calls = []


def _compute_address(self):
    """≙ ``_compute_address`` — la dirección la pone el partner."""
    self.country = getattr(self.partner, 'country', None)


def _inverse_country(self):
    """≙ ``_inverse_country`` — escribir en la compañía escribe el partner."""
    inverse_calls.append(self.country)
    self.partner.country = self.country
    self.partner.save()


ResCompany._compute_address = _compute_address
ResCompany._inverse_country = _inverse_country

#: ``private_only=True`` es como la costura contribuye un campo sin columna
#: (sonda A: sin columna, sin tabla de relación y sin accesor inverso). Sin él,
#: ``contribute_to_class`` instala el accesor inverso y el recolector de
#: ``delete()`` intenta consultar una columna ``None`` — medido en
#: ``scripts/evidence/direccion-2026-09-12T07-51-51-001.log``:
#: ``TypeError: argument of type 'NoneType' is not iterable``.
country_field = Many2one(ResCountry, compute='_compute_address',
                         inverse='_inverse_country', null=True,
                         related_name='+')
country_field.contribute_to_class(ResCompany, 'country', private_only=True)
mark_model_for_setup(ResCompany)
setup_count = ensure_field_setup()

read_value = read_error = None
calls_after_assign = calls_after_save = 0
reread = reread_error = None
company = mexico = canada = None
try:
    mexico, _ = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'Mexico'})
    canada, _ = ResCountry.objects.get_or_create(code='CA', defaults={'name': 'Canada'})
    company = ResCompany.objects.create(code='probe_addr', name='Probe Addr')
    company.partner.country = mexico
    company.partner.save()

    fetched = ResCompany.objects.get(pk=company.pk)
    try:
        read_value = fetched.country
    except Exception as exc:  # noqa: BLE001
        read_error = f'EXC {type(exc).__name__}: {exc}'

    fetched.country = canada
    calls_after_assign = len(inverse_calls)
    fetched.save()
    calls_after_save = len(inverse_calls)

    try:
        reread = ResPartner.objects.get(pk=company.partner_id).country
    except Exception as exc:  # noqa: BLE001
        reread_error = f'EXC {type(exc).__name__}: {exc}'
    cleanup_error = None
except Exception as exc:  # noqa: BLE001 — se mide, no se traga
    cleanup_error = f'EXC {type(exc).__name__}: {exc}'
finally:
    if company is not None:
        partner_id = company.partner_id
        try:
            ResCompany.objects.filter(pk=company.pk).delete()
            ResPartner.objects.filter(pk=partner_id).delete()
        except Exception as exc:  # noqa: BLE001
            print('limpieza:', f'EXC {type(exc).__name__}: {exc}')

expected = {
    'setup_ran':                setup_count > 0,
    'read_runs_the_compute':    read_error is None and getattr(read_value, 'code', None) == 'MX',
    'inverse_dispatched':       calls_after_save > 0,
    'write_reaches_the_column': reread_error is None and getattr(reread, 'code', None) == 'CA',
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count, "| error del cuerpo:", cleanup_error)
print("read:", repr(read_value)[:120], "| error:", read_error)
print("inverse calls tras asignar:", calls_after_assign, "| tras save:", calls_after_save)
print("partner.country releido:", repr(reread)[:120], "| error:", reread_error)
print("VEREDICTO escritura_llega_a_la_columna_del_partner:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
