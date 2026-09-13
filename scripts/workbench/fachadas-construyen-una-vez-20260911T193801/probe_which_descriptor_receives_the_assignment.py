"""Sonda J de TASK-API-0417 — ¿QUÉ descriptor recibe ``company.country = x``?

Bloqueante de TASK-API-0412. :ref:`h-api-1110` nombra
``ComputedFieldDescriptor.__set__`` (``orm/fields.py:1635``) como el punto donde
cablear el despacho del inverso. Esa elección sólo es correcta si el descriptor
que recibe la asignación es el nuestro — y para un relacional hay DOS ranuras:

- ``field.name`` (``country``) — donde ``ForeignKey.contribute_to_class`` de
  Django cuelga su ``ForwardManyToOneDescriptor``;
- ``field.attname`` (``country_id``) — donde ``_install_field_descriptor``
  (``orm/fields.py:1885-1895``) cuelga el nuestro, verbatim:
  ``current = cls.__dict__.get(field.attname)``.

La hipótesis que la sonda vino a probar —«si el reparto es ése, la asignación
por nombre NUNCA entra en ``:1635``»— quedó **REFUTADA** al medirla
(``scripts/evidence/politica-2026-09-12T08-11-44-001.log``): el reparto de
ranuras es real, y aun así ``company.country = x`` llega a nuestro descriptor,
porque ``ForwardManyToOneDescriptor.__set__`` **encadena** —hace
``setattr(instance, field.attname, ...)``— y esa segunda asignación cae en la
ranura del attname, que es la nuestra. Se conserva la sonda porque la
CONSECUENCIA sí cambia: lo que nuestro descriptor recibe por esa vía es la
CLAVE, no el objeto, así que la marca de pendiente tiene que registrar que el
campo está sucio y no el valor.

La sonda D ya midió el reparto para un FK sin columna de sonda; aquí se mide
sobre el modelo REAL, con la forma que la referencia fija
(``odoo19c: odoo/addons/base/models/res_company.py:69-78``).

Se mide por CONTENIDO, no por presencia: se cuentan las invocaciones reales de
``__set__`` de cada clase de descriptor durante una asignación, porque el
descriptor instalado se puede leer de ``__dict__`` pero eso no dice cuál corre.

El control positivo es ``partner``, un relacional CON columna del mismo modelo:
si el reparto de ranuras fuera un artefacto de la sonda, ``partner`` mostraría
el mismo cuadro que ``country``, y no lo muestra.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields  # noqa: E402,F401
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor  # noqa: E402
from orm.fields import ComputedFieldDescriptor, FieldDescriptor  # noqa: E402
from orm.fields_relational import Many2one  # noqa: E402
from orm.model_classes import ensure_field_setup, mark_model_for_setup  # noqa: E402

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_country import ResCountry  # noqa: E402
from addons.base.models.res_partner import ResPartner  # noqa: E402

set_calls = {'forward': 0, 'computed': 0}
_forward_set = ForwardManyToOneDescriptor.__set__
_computed_set = ComputedFieldDescriptor.__set__


def _counting_forward_set(self, instance, value):
    set_calls['forward'] += 1
    return _forward_set(self, instance, value)


def _counting_computed_set(self, instance, value):
    set_calls['computed'] += 1
    return _computed_set(self, instance, value)


ForwardManyToOneDescriptor.__set__ = _counting_forward_set
ComputedFieldDescriptor.__set__ = _counting_computed_set


def _compute_address(self):
    """≙ ``_compute_address`` — la dirección la pone el partner."""
    self.country = getattr(self.partner, 'country', None)


def _inverse_country(self):
    """≙ ``_inverse_country`` — escribir en la compañía escribe el partner."""
    self.partner.country = self.country
    self.partner.save()


ResCompany._compute_address = _compute_address
ResCompany._inverse_country = _inverse_country

#: SIN ``private_only``: es la forma que tendrá el campo en el árbol. La sonda I
#: lo puso para esquivar el reventón del recolector de ``delete()``, y con eso
#: midió una vía que el porte no va a usar.
country_field = Many2one(ResCountry, compute='_compute_address',
                         inverse='_inverse_country', null=True)
country_field.contribute_to_class(ResCompany, 'country')
mark_model_for_setup(ResCompany)
setup_count = ensure_field_setup()


def _slot(model_cls, attr):
    holder = model_cls.__dict__.get(attr)
    return type(holder).__name__ if holder is not None else '(ausente)'


slots = {
    'country':    _slot(ResCompany, 'country'),
    'country_id': _slot(ResCompany, 'country_id'),
    'partner':    _slot(ResCompany, 'partner'),
    'partner_id': _slot(ResCompany, 'partner_id'),
}

#: La fila se crea por el manejador, no con ``ResCompany(...)``: ``name`` es una
#: property que delega en ``self.partner``, y sin partner la construcción muere
#: en ``RelatedObjectDoesNotExist`` antes de llegar a la medición
#: (``scripts/evidence/ranuras-2026-09-12T08-10-26-001.log``).
row = ResCompany.objects.create(code='probe_slot', name='Probe Slot')
set_calls['forward'] = set_calls['computed'] = 0
assign_error = None
try:
    row.country = None
except Exception as exc:  # noqa: BLE001 — el despacho ES lo que se mide
    assign_error = f'EXC {type(exc).__name__}: {exc}'
after_name = dict(set_calls)

set_calls['forward'] = set_calls['computed'] = 0
attname_error = None
try:
    row.country_id = None
except Exception as exc:  # noqa: BLE001
    attname_error = f'EXC {type(exc).__name__}: {exc}'
after_attname = dict(set_calls)

expected = {
    'setup_ran':            setup_count > 0,
    'our_descriptor_on_attname':
        slots['country_id'] in ('ComputedFieldDescriptor', 'FieldDescriptor'),
    'django_descriptor_on_name':
        slots['country'] == 'ForwardManyToOneDescriptor',
    'assign_by_name_chains_into_ours': after_name['computed'] > 0,
    'assign_by_attname_hits_ours':     after_attname['computed'] > 0,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count)
print("ranuras:", slots)
print("descriptor base disponible:", FieldDescriptor.__name__)
print("asignar por nombre   (company.country    = None):", after_name,
      "| error:", assign_error)
print("asignar por attname  (company.country_id = None):", after_attname,
      "| error:", attname_error)
print("VEREDICTO la_asignacion_por_nombre_alcanza_nuestro_descriptor:",
      'OK' if all(expected.values()) else 'FALLA')

partner_id = row.partner_id
ResCompany.objects.filter(pk=row.pk).delete()
try:
    ResPartner.objects.filter(pk=partner_id).delete()
except Exception as exc:  # noqa: BLE001 — preexistente, medido por la sonda K
    print('limpieza del partner:', f'EXC {type(exc).__name__}: {exc}')
raise SystemExit(0 if all(expected.values()) else 1)
