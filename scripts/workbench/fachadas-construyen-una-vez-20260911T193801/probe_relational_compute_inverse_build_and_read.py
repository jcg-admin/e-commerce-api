"""Sonda F de TASK-API-0417 — ¿se puede CONSTRUIR y LEER un relacional
``compute=`` + ``inverse=`` sin columna, que es la forma que la referencia fija
para las seis direcciones de ``res.company``?

Bloqueante de TASK-API-0412. ``odoo19c: addons/base/models/res_company.py:69-78``
declara ``street``/``street2``/``zip``/``city``/``state_id``/``country_id`` como
``compute='_compute_address'`` con un ``inverse=`` NOMBRADO por campo — nunca
``related=``. Antes de declarar esas seis aquí hay que medir si el relacional de
esa forma se construye: la tarea **#349** («Reconstruir un campo relacional desde
``_args__``: ``to`` y ``on_delete`` no llegan a ``Field.__init__``») sigue
abierta, y si bloquea, el arreglo no es este pase.

Se mide, por contenido y no por presencia:

- que el campo se construya y quede en ``_meta.fields`` sin columna
  (``store=False`` derivado de ``compute``, ``readonly=False`` derivado de
  ``inverse``);
- que el ``setup`` del campo cierre sin excepción sobre los modelos de la sonda;
- que el comodelo siga apuntando al destino real tras el setup;
- que la LECTURA devuelva el registro que el cómputo asignó, sobre fila traída
  de la base y sobre fila nueva sin pk.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import connection, models  # noqa: E402

import fields  # noqa: E402,F401  — registra los enganches de orm.fields
from orm.fields_relational import Many2one  # noqa: E402
from orm.model_classes import prepare_field_setup, setup_fields  # noqa: E402
from orm.models import BaseModel  # noqa: E402


class ProbeCiCountry(BaseModel):
    code = models.CharField(max_length=2)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_ci_country'


class ProbeCiPartner(BaseModel):
    country = models.ForeignKey(ProbeCiCountry, on_delete=models.CASCADE,
                                null=True, related_name='ci_partners')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_ci_partner'


class ProbeCiCompany(BaseModel):
    partner = models.ForeignKey(ProbeCiPartner, on_delete=models.CASCADE,
                                related_name='ci_companies')
    #: La forma de la referencia: cómputo con inverso nombrado, sin columna.
    country = Many2one(ProbeCiCountry, models.CASCADE, null=True,
                       related_name='ci_companies_country',
                       compute='_compute_address',
                       inverse='_inverse_country')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_ci_company'

    def _compute_address(self):
        """≙ ``_compute_address`` — la dirección la pone el partner."""
        self.country = self.partner.country

    def _inverse_country(self):
        """≙ ``_inverse_country`` — escribir en la compañía escribe el partner."""
        self.partner.country = self.country
        self.partner.save()


built = None
build_error = None
try:
    built = ProbeCiCompany._meta.get_field('country')
except Exception as exc:  # noqa: BLE001 — la construcción ES lo que se mide
    build_error = f'EXC {type(exc).__name__}: {exc}'

#: **El setup se corre SOBRE LOS MODELOS DE LA SONDA, no sobre el arbol.**
#: ``ensure_field_setup()`` suma sobre *todos* los modelos y la primera cadena
#: rota aborta el barrido entero: medido en
#: ``scripts/evidence/bloqueantes-2026-09-12T07-49-30-00{1,2}.log``, las dos
#: sondas murieron con ``KeyError: 'El campo country de la definicion related de
#: company_country_code no existe en ResCompany.'`` — el defecto que se analiza,
#: cegando su propia medicion. Acotar el sujeto es lo que hace decidible este eje.
PROBE_MODELS = (ProbeCiCountry, ProbeCiPartner, ProbeCiCompany)
setup_count = None
setup_error = None
try:
    for model_cls in PROBE_MODELS:
        prepare_field_setup(model_cls)
    setup_count = sum(setup_fields(model_cls) for model_cls in PROBE_MODELS)
except Exception as exc:  # noqa: BLE001
    setup_error = f'EXC {type(exc).__name__}: {exc}'

concrete = [f.name for f in ProbeCiCompany._meta.concrete_fields]
remote_model = None
if built is not None and getattr(built, 'remote_field', None) is not None:
    remote_model = getattr(built.remote_field, 'model', None)

read_value = read_fresh = None
if build_error is None and setup_error is None:
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS probe_ci_company')
        cursor.execute('DROP TABLE IF EXISTS probe_ci_partner')
        cursor.execute('DROP TABLE IF EXISTS probe_ci_country')
        cursor.execute('CREATE TABLE probe_ci_country '
                       '(id serial PRIMARY KEY, code varchar(2) NOT NULL)')
        cursor.execute('CREATE TABLE probe_ci_partner '
                       '(id serial PRIMARY KEY, country_id integer NULL)')
        cursor.execute('CREATE TABLE probe_ci_company '
                       '(id serial PRIMARY KEY, partner_id integer NOT NULL)')
    try:
        country = ProbeCiCountry.objects.create(code='MX')
        partner = ProbeCiPartner.objects.create(country=country)
        company = ProbeCiCompany.objects.create(partner=partner)
        fetched = ProbeCiCompany.objects.get(pk=company.pk)
        try:
            read_value = fetched.country
        except Exception as exc:  # noqa: BLE001
            read_value = f'EXC {type(exc).__name__}: {exc}'
        fresh = ProbeCiCompany(partner=partner)
        try:
            read_fresh = fresh.country
        except Exception as exc:  # noqa: BLE001
            read_fresh = f'EXC {type(exc).__name__}: {exc}'
    finally:
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS probe_ci_company')
            cursor.execute('DROP TABLE IF EXISTS probe_ci_partner')
            cursor.execute('DROP TABLE IF EXISTS probe_ci_country')

expected = {
    'field_builds':        build_error is None,
    'setup_closes':        setup_error is None,
    'store_is_false':      built is not None and getattr(built, 'store', None) is False,
    'readonly_is_false':   built is not None and getattr(built, 'readonly', None) is False,
    'has_no_column':       'country' not in concrete and 'country_id' not in concrete,
    'remote_is_the_target': remote_model is ProbeCiCountry,
    'read_returns_target': type(read_value) is ProbeCiCountry,
    'fresh_read_returns_target': type(read_fresh) is ProbeCiCountry,
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("build_error:", build_error)
print("setup_error:", setup_error)
print("setup_count:", setup_count)
print("concrete fields:", concrete)
print("remote_field.model:", getattr(remote_model, '__name__', remote_model))
print("read by name:", repr(read_value)[:160], "| type:", type(read_value).__name__)
print("fresh read:", repr(read_fresh)[:160], "| type:", type(read_fresh).__name__)
print("VEREDICTO relacional_compute_inverso_construye_y_lee:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
