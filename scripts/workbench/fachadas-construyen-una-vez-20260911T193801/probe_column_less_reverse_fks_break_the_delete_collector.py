"""Sonda K de TASK-API-0417 — ¿el reventón del recolector de ``delete()`` es del
campo nuevo, o ya estaba en el árbol?

La sonda I dejó ``limpieza: EXC TypeError: argument of type 'NoneType' is not
iterable`` al borrar el partner
(``scripts/evidence/direccion2-2026-09-12T07-52-24-001.log``), y su comentario se
lo atribuyó al campo que ella misma declara. Esa atribución no está medida: el
campo nuevo apunta a ``ResCountry``, así que **no puede estar** entre las
relaciones inversas que el recolector de ``ResPartner`` recorre. TASK-API-0424 la
recoge como si lo estuviera.

El discriminador no es correr el borrado sin el campo —sin él la costura aborta y
nada corre—, sino **medir el universo**: el recolector de ``delete(X)`` recorre
las FK que apuntan **a X**, y salta exactamente una política:
``if related.field.remote_field.on_delete is DO_NOTHING: continue``. Una FK sin
columna que NO sea ``DO_NOTHING`` es una que el recolector va a intentar
consultar compilando un ``Col`` con ``column=None``.

Se mide por contenido y en dos pasos:

1. el censo de FK sin columna del árbol ENTERO, con su política, **antes** de
   declarar nada — ``_meta`` no dispara el descriptor, así que la costura rota no
   lo ciega;
2. con el campo declarado, el borrado real, nombrando la relación que revienta.

Si el censo ya trae FK sin columna apuntando a ``ResPartner`` con política
distinta de ``DO_NOTHING``, el defecto es PREEXISTENTE y necesita hallazgo propio.

**Su censo cambió al aterrizar TASK-API-0426, y el cambio es la evidencia del
alcance.** Antes del arreglo las políticas medidas eran ``['None', 'RESTRICT']``;
ahora son ``['DO_NOTHING', 'None']`` sobre las mismas 95 FK sin columna. El
``RESTRICT`` desapareció porque ``fields_relational.py`` fuerza ``DO_NOTHING``
para todo ``not has_column``, no sólo para el ``related=`` sin ``to``.

Las que siguen en ``None`` **no son deuda del arreglo**: son relaciones que no
tienen ``on_delete`` que fijar —M2M e inversas—, y entre ellas los dos M2M sin
columna que apuntan a ``ResPartner`` (``base.ResPartnerCategory.partners`` y
``fleet.FleetVehicleModel.vendors``). Ése es el sucesor **TASK-API-0425**, que
esta misma sonda midió como preexistente.
"""
import os
import traceback

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields  # noqa: E402,F401
from django.apps import apps  # noqa: E402
from django.db.models import DO_NOTHING  # noqa: E402
from orm.fields_relational import Many2one  # noqa: E402
from orm.model_classes import ensure_field_setup, mark_model_for_setup  # noqa: E402

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_country import ResCountry  # noqa: E402
from addons.base.models.res_partner import ResPartner  # noqa: E402


def _policy_name(field):
    on_delete = getattr(field.remote_field, 'on_delete', None)
    return getattr(on_delete, '__name__', repr(on_delete))


#: Paso 1 — el censo, ANTES de declarar el campo que falta.
column_less = []
for model_cls in apps.get_models():
    for field in model_cls._meta.get_fields():
        if not getattr(field, 'is_relation', False) or not hasattr(field, 'column'):
            continue
        if getattr(field, 'column', 'sentinel') is not None:
            continue
        column_less.append({
            'model': f'{model_cls._meta.app_label}.{model_cls.__name__}',
            'field': field.name,
            'comodel': getattr(getattr(field, 'related_model', None), '__name__', None),
            'policy': _policy_name(field),
        })

pointing_at_partner = [
    {'model': f'{rel.related_model._meta.app_label}.{rel.related_model.__name__}',
     'field': rel.field.name,
     'policy': _policy_name(rel.field)}
    for rel in ResPartner._meta.related_objects
    if getattr(rel.field, 'column', 'sentinel') is None
]
dangerous_at_partner = [r for r in pointing_at_partner if r['policy'] != 'DO_NOTHING']

#: Paso 2 — con el campo declarado (la costura sólo cierra así), el borrado real.
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
country_field.contribute_to_class(ResCompany, 'country')
mark_model_for_setup(ResCompany)
setup_count = ensure_field_setup()

new_field_policy = _policy_name(country_field)
new_field_has_column = getattr(country_field, 'column', 'sentinel') is not None

delete_error = delete_frame = None
partner = None
try:
    partner = ResPartner.objects.create(name='Probe Collector')
    ResPartner.objects.filter(pk=partner.pk).delete()
    partner = None
except Exception as exc:  # noqa: BLE001 — el reventón ES lo que se mide
    delete_error = f'EXC {type(exc).__name__}: {exc}'
    frames = traceback.extract_tb(exc.__traceback__)
    delete_frame = ' | '.join(f'{f.filename.split("/")[-1]}:{f.lineno} {f.name}'
                              for f in frames[-3:])
finally:
    if partner is not None:
        try:
            ResPartner.objects.filter(pk=partner.pk).update(active=False)
        except Exception as exc:  # noqa: BLE001
            print('limpieza:', f'EXC {type(exc).__name__}: {exc}')

expected = {
    'setup_ran':               setup_count > 0,
    'new_field_has_no_column': new_field_has_column is False,
    'new_field_does_not_point_at_partner':
        getattr(country_field.related_model, '__name__', None) != 'ResPartner',
    'partner_already_had_column_less_reverse_fks': len(pointing_at_partner) > 0,
    'the_culprit_predates_the_new_field': len(dangerous_at_partner) > 0,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count)
print("FK sin columna en el arbol:", len(column_less))
print("politicas del censo:", sorted({r['policy'] for r in column_less}))
print("sin DO_NOTHING en el censo:",
      [r for r in column_less if r['policy'] != 'DO_NOTHING'][:10])
print("apuntando a ResPartner sin columna:", pointing_at_partner)
print("...de esas, sin DO_NOTHING:", dangerous_at_partner)
print("campo nuevo -> comodelo:", getattr(country_field.related_model, '__name__', None),
      "| politica:", new_field_policy, "| columna:", getattr(country_field, 'column', 'sentinel'))
print("borrado del partner:", delete_error or 'sin error')
print("marco del reventon:", delete_frame)
print("VEREDICTO el_reventon_no_lo_causa_el_campo_nuevo:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
