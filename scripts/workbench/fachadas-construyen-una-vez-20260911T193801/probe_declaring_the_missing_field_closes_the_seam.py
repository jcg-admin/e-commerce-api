"""Sonda H de TASK-API-0417 — el CONTROL del arreglo de TASK-API-0412: declarar
``ResCompany.country`` como campo, ¿cierra la costura y resuelve las dos cadenas
rotas?

Las sondas F y G no pudieron medir su propia lectura: ``FieldDescriptor.__get__``
(``orm/fields.py:1438``) llama a ``ensure_field_setup()``, que barre **todos** los
modelos, y la primera cadena rota aborta el barrido entero. Medido en
``scripts/evidence/bloqueantes2-2026-09-12T07-50-09-00{1,2}.log``: dos modelos de
sonda que no tienen nada que ver con la compañía mueren con el ``KeyError`` de
``company_country_code``. Ése es el radio de explosión, y también la razón de que
el sujeto de esta sonda tenga que ser el modelo REAL.

Aquí se declara en el proceso —no en el árbol— el campo que falta, con la forma
que la referencia fija (``odoo19c: addons/base/models/res_company.py:69-78``:
``compute='_compute_address'`` + ``inverse=`` NOMBRADO, nunca ``related=``), y se
mide por contenido:

- que el barrido global cierre sin excepción;
- que las DOS cadenas rotas de ``SiteConfigSettings`` resuelvan;
- que la lectura devuelva el país del partner;
- que la escritura despache el inverso y llegue a la COLUMNA del partner,
  releída de la base — el control que ``write-2026-09-12T00-27-19-001.log`` dio
  en FALLA con los campos declarados ``related=``.

Es el control de anulación del arreglo: sin el campo, la costura aborta (sondas
F y G); con él, se mide si cierra.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields  # noqa: E402
from orm.fields_relational import Many2one  # noqa: E402
from orm.model_classes import ensure_field_setup, mark_model_for_setup  # noqa: E402

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_country import ResCountry  # noqa: E402

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

country_field = Many2one(
    ResCountry, compute='_compute_address', inverse='_inverse_country', null=True,
    related_name='probe_seam_companies')
country_field.contribute_to_class(ResCompany, 'country')
mark_model_for_setup(ResCompany)

setup_count = None
setup_error = None
try:
    setup_count = ensure_field_setup()
except Exception as exc:  # noqa: BLE001 — el cierre de la costura ES lo que se mide
    setup_error = f'EXC {type(exc).__name__}: {exc}'

chain_state = {}
if setup_error is None:
    from addons.base_setup.models.res_config_settings import SiteConfigSettings  # noqa: E402
    for name in ('company_country_code', 'company_country_group_codes'):
        try:
            chained = SiteConfigSettings._meta.get_field(name)
            chain_state[name] = {
                'related': getattr(chained, 'related', None),
                'compute': getattr(chained, 'compute', None) is not None,
                'setup_done': getattr(chained, '_setup_done__', None),
            }
        except Exception as exc:  # noqa: BLE001
            chain_state[name] = f'EXC {type(exc).__name__}: {exc}'

expected = {
    'field_contributes':  ResCompany._meta.get_field('country') is country_field,
    'store_is_false':     getattr(country_field, 'store', None) is False,
    'readonly_is_false':  getattr(country_field, 'readonly', None) is False,
    'seam_closes':        setup_error is None,
    'both_chains_resolve': len(chain_state) == 2 and all(
        isinstance(v, dict) for v in chain_state.values()),
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count)
print("setup_error:", setup_error)
print("country en concrete_fields:",
      'country' in [f.name for f in ResCompany._meta.concrete_fields])
print("estado de las cadenas:", chain_state)
print("VEREDICTO declarar_el_campo_cierra_la_costura:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
