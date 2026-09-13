"""Sonda N de TASK-API-0417 — ¿en QUÉ cubo de ``__set__`` cae cada camino de
escritura, y deja marca el camino de LECTURA?

Bloqueante de TASK-API-0412. La sonda J midió que ``company.country = x`` llega
a ``ComputedFieldDescriptor.__set__`` (``orm/fields.py:1635``). Eso fija el SITIO
de la marca de pendiente, y deja abiertas las dos preguntas que deciden su
GUARDA:

1. **El cómputo escribe el mismo campo.** ``_compute_address`` hace
   ``self.country = ...``, así que leer ``company.country`` entra en ``__set__``.
   Si esa entrada deja marca, el ``save()`` siguiente despacharía el inverso y
   escribiría sobre el partner el valor que el partner acaba de dar — pisando
   cualquier edición hecha por el otro lado. La guarda prevista es el cubo
   ``is_protected``, y sólo sirve si el entorno protege de verdad durante un
   cómputo disparado por ``__get__`` (no por ``recompute``).

2. **El cubo de fila nueva puede ser inalcanzable.**
   ``_model_init_marking_the_load`` (``orm/fields.py:1385``) marca
   ``_orm_building``; si lo marca en TODO ``__init__`` y no sólo en ``from_db``,
   entonces ``ResCompany.objects.create(code=…, country=mx)`` —la vía de kwargs
   de Django— nunca deja marca, y el camino habría que cubrirlo por otra vía.

Se mide por conducta: se envuelve ``__set__`` con un testigo que reproduce los
cuatro predicados del reparto —``_orm_building``, ``is_protected``, ``pk``
ausente, fila real— y registra el cubo por camino ejercido. No se mide la
presencia del cubo en el código: se mide cuál se toma.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields  # noqa: E402,F401
from orm.environments import env as get_environment  # noqa: E402
from orm.fields import ComputedFieldDescriptor  # noqa: E402
from orm.fields_relational import Many2one  # noqa: E402
from orm.model_classes import ensure_field_setup, mark_model_for_setup  # noqa: E402

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_country import ResCountry  # noqa: E402
from addons.base.models.res_partner import ResPartner  # noqa: E402

current_path = ['(sin camino)']
buckets = []
_original_set = ComputedFieldDescriptor.__set__


def _bucket_for(field, instance):
    """Reproduce el reparto de ``ComputedFieldDescriptor.__set__`` sin ejecutarlo."""
    if instance.__dict__.get('_orm_building'):
        return 'orm_building'
    if get_environment().is_protected(field, instance.pk):
        return 'is_protected'
    if not instance.pk:
        return 'new_row'
    return 'real_row'


def _witnessing_set(self, instance, value):
    if self.field.name == 'country':
        buckets.append((current_path[0], _bucket_for(self.field, instance)))
    return _original_set(self, instance, value)


ComputedFieldDescriptor.__set__ = _witnessing_set


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

mexico, _ = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'Mexico'})
canada, _ = ResCountry.objects.get_or_create(code='CA', defaults={'name': 'Canada'})

errors = {}
company = None
try:
    current_path[0] = 'create_by_kwargs'
    company = ResCompany.objects.create(code='probe_bucket', name='Probe Bucket',
                                        country=mexico)
except Exception as exc:  # noqa: BLE001 — el camino puede no admitir el kwarg
    errors['create_by_kwargs'] = f'EXC {type(exc).__name__}: {exc}'
    current_path[0] = 'create_without_the_field'
    company = ResCompany.objects.create(code='probe_bucket', name='Probe Bucket')

try:
    company.partner.country = mexico
    company.partner.save()

    current_path[0] = 'load_from_db'
    fetched = ResCompany.objects.get(pk=company.pk)

    current_path[0] = 'read_runs_the_compute'
    _ = fetched.country

    current_path[0] = 'assign_on_a_real_row'
    fetched.country = canada
except Exception as exc:  # noqa: BLE001
    errors['cuerpo'] = f'EXC {type(exc).__name__}: {exc}'
finally:
    current_path[0] = '(limpieza)'
    if company is not None:
        try:
            ResCompany.objects.filter(pk=company.pk).delete()
        except Exception as exc:  # noqa: BLE001
            print('limpieza:', f'EXC {type(exc).__name__}: {exc}')

by_path = {}
for path, bucket in buckets:
    by_path.setdefault(path, []).append(bucket)

read_buckets = by_path.get('read_runs_the_compute', [])
expected = {
    'setup_ran':                       setup_count > 0,
    'the_read_writes_the_field':       len(read_buckets) > 0,
    'the_read_is_protected':           read_buckets == ['is_protected'] * len(read_buckets),
    'the_real_row_bucket_is_reached':  'real_row' in by_path.get('assign_on_a_real_row', []),
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count)
print("cubos por camino:", by_path)
print("errores:", errors)
print("VEREDICTO la_guarda_del_computo_es_el_cubo_protegido:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
