"""SUPERSEDED por ``probe_company_address_write_reaches_the_partner.py`` — el
eje se mide alli, sobre los modelos REALES.

Esta sonda no puede emitir veredicto y su ``.out`` lo demuestra: sus modelos son
sinteticos, y la primera lectura de uno de ellos dispara ``ensure_field_setup()``
sobre TODO el arbol, que aborta mientras falte ``ResCompany.country``. Se
conserva porque su traza ES la evidencia del radio de explosion: dos modelos sin
relacion alguna con la compañia mueren con el ``KeyError`` de
``company_country_code``.

Sonda G de TASK-API-0417 — al escribir un ``compute=`` + ``inverse=``, ¿se
despacha el inverso declarado, y llega el valor a la columna real?

Bloqueante de TASK-API-0412, y la mitad que la sonda F no mide. H-API-1106 se
titula «el descriptor base no tiene set»: :class:`ComputedFieldDescriptor` sí lo
declara (``orm/fields.py:1635``), pero su cuerpo porta ``Field.__set__`` — los
tres cubos de escritura — y **no** el despacho del inverso, que en la fuente
vive en ``_load_records``/``write`` vía ``_group_written_inverses``
(``orm/models.py:2428-2438``). ``BaseModel.save`` (``:1351``) no tiene conjunto
de escritura, así que no puede agruparlos.

El sujeto es ESCALAR (``Char``), no relacional, a propósito: aísla el despacho
del inverso de la pregunta de construcción que mide la sonda F. Si el relacional
estuviera bloqueado por la tarea **#349**, este eje sigue siendo decidible.

Se mide, por contenido:

- si ``company.street = 'x'`` invoca ``_inverse_street`` (contador);
- si tras ``save()`` lo invoca;
- si el valor aterriza en la COLUMNA real del partner, releída de la base —
  que es el control que ``scripts/evidence/write-2026-09-12T00-27-19-001.log``
  dio en FALLA con los campos declarados ``related=``.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import connection, models  # noqa: E402

import fields  # noqa: E402  — registra los enganches de orm.fields
from orm.model_classes import prepare_field_setup, setup_fields  # noqa: E402
from orm.models import BaseModel  # noqa: E402

#: Contador del despacho: el inverso no devuelve nada, así que su ejecución
#: sólo es observable por efecto.
inverse_calls = []


class ProbeCiwPartner(BaseModel):
    street = models.CharField(max_length=32, blank=True, default='')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_ciw_partner'


class ProbeCiwCompany(BaseModel):
    partner = models.ForeignKey(ProbeCiwPartner, on_delete=models.CASCADE,
                                related_name='ciw_companies')
    street = fields.Char(max_length=32, compute='_compute_address',
                         inverse='_inverse_street')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'probe_ciw_company'

    def _compute_address(self):
        """≙ ``_compute_address`` — la dirección la pone el partner."""
        self.street = self.partner.street

    def _inverse_street(self):
        """≙ ``_inverse_street`` — escribir en la compañía escribe el partner."""
        inverse_calls.append(self.street)
        self.partner.street = self.street
        self.partner.save()


#: **El setup se corre SOBRE LOS MODELOS DE LA SONDA, no sobre el arbol.**
#: ``ensure_field_setup()`` suma sobre *todos* los modelos y la primera cadena
#: rota aborta el barrido entero: medido en
#: ``scripts/evidence/bloqueantes-2026-09-12T07-49-30-00{1,2}.log``, las dos
#: sondas murieron con ``KeyError: 'El campo country de la definicion related de
#: company_country_code no existe en ResCompany.'`` — el defecto que se analiza,
#: cegando su propia medicion. Acotar el sujeto es lo que hace decidible este eje.
PROBE_MODELS = (ProbeCiwPartner, ProbeCiwCompany)
field = ProbeCiwCompany._meta.get_field('street')
for model_cls in PROBE_MODELS:
    prepare_field_setup(model_cls)
setup_count = sum(setup_fields(model_cls) for model_cls in PROBE_MODELS)
descriptor = type(ProbeCiwCompany.__dict__.get('street')).__name__

with connection.cursor() as cursor:
    cursor.execute('DROP TABLE IF EXISTS probe_ciw_company')
    cursor.execute('DROP TABLE IF EXISTS probe_ciw_partner')
    cursor.execute('CREATE TABLE probe_ciw_partner '
                   '(id serial PRIMARY KEY, street varchar(32) NOT NULL)')
    cursor.execute('CREATE TABLE probe_ciw_company '
                   '(id serial PRIMARY KEY, partner_id integer NOT NULL)')
try:
    partner = ProbeCiwPartner.objects.create(street='vieja')
    company = ProbeCiwCompany.objects.create(partner=partner)

    read_before = company.street
    company.street = 'nueva'
    calls_after_assign = len(inverse_calls)
    read_after_assign = company.street

    company.save()
    calls_after_save = len(inverse_calls)

    reread = ProbeCiwPartner.objects.get(pk=partner.pk).street
finally:
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS probe_ciw_company')
        cursor.execute('DROP TABLE IF EXISTS probe_ciw_partner')

expected = {
    'setup_ran':                setup_count is not None,
    'descriptor_has_set':       hasattr(type(ProbeCiwCompany.__dict__.get('street')), '__set__'),
    'compute_reads_partner':    read_before == 'vieja',
    'assignment_is_visible':    read_after_assign == 'nueva',
    'inverse_dispatched':       calls_after_save > 0,
    'write_reaches_the_column': reread == 'nueva',
}
for key, ok in expected.items():
    print(f"{key}: {'OK' if ok else 'FALLA'}")
print("setup_count:", setup_count)
print("class descriptor:", descriptor)
print("store:", getattr(field, 'store', None), "| readonly:", getattr(field, 'readonly', None),
      "| inverse:", getattr(field, 'inverse', None))
print("read before assign:", repr(read_before))
print("read after assign:", repr(read_after_assign))
print("inverse calls after assign:", calls_after_assign, "| after save:", calls_after_save)
print("partner.street releido de la base:", repr(reread))
print("VEREDICTO inverso_despachado_al_escribir:",
      'OK' if all(expected.values()) else 'FALLA')
raise SystemExit(0 if all(expected.values()) else 1)
