"""``res.country`` / ``res.country.state`` — geografía política (Odoo ``base``).

Portación fiel de ``res_country.py`` (Odoo 18 / 19 idéntico). Espina base de la
adaptación de familias (SOL-096): direcciones/impuestos dependen de país+estado.
"""
import re

from django.core.exceptions import ValidationError

import fields
import models
from tools.translate import _

#: Plantilla por defecto — ≙ el ``default`` de ``address_format``
#: (``odoo19c: res_country.py:52``), verbatim.
DEFAULT_ADDRESS_FORMAT = (
    '%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s'
)

#: Dónde va el nombre del cliente — ≙ el Selection de ``name_position``.
NAME_POSITIONS = (
    ('before', 'Antes de la dirección'),
    ('after', 'Después de la dirección'),
)

#: Claves admitidas en ``address_format`` — ≙ la lista que arma
#: ``_check_address_format`` (``odoo19c: res_country.py:155``):
#: ``_formatting_address_fields()`` —que devuelve ``ADDRESS_FIELDS``
#: (``res_partner.py:25``)— más los cinco derivados que añade en la misma línea.
ADDRESS_FORMAT_KEYS = (
    'street', 'street2', 'zip', 'city', 'state_id', 'country_id',
    'state_code', 'state_name', 'country_code', 'country_name', 'company_name',
)

#: Los DOS códigos sin bandera propia — ≙ ``NO_FLAG_COUNTRIES``
#: (``odoo19c: res_country.py:26-29``), verbatim: la Antártida y Svalbard +
#: Jan Mayen, que son jurisdicciones separadas sin bandera dedicada.
NO_FLAG_COUNTRIES = ('AQ', 'SJ')

#: Territorios cuya bandera es la de otro país — ≙ ``FLAG_MAPPING``
#: (``odoo19c: res_country.py:13-24``), verbatim. Sin esta tabla la ruta
#: apuntaría a un archivo que no existe para diez códigos.
FLAG_MAPPING = {
    'GF': 'fr', 'BV': 'no', 'BQ': 'nl', 'GP': 'fr', 'HM': 'au',
    'YT': 'fr', 'RE': 'fr', 'MF': 'fr', 'UM': 'us', 'XI': 'uk',
}


class ResCountry(models.Model):
    """``res.country`` — país (Odoo base).

    Fiel a ``res_country.py`` (18:32-68 / 19 idéntico): ``name`` (requerido),
    ``code`` (ISO 3166-1 alpha-2, único), ``currency`` (FK res.currency),
    ``phone_code``. ``state_ids`` es el reverso de ``ResCountryState.country``.

    Los cuatro atributos de clase son los que la fuente declara
    (``atributos-de-clase-de-modelo.md``); se completaron en la tarea **#132**,
    que necesita ``_name`` para que el registro por nombre pueda responder a la
    guarda de modelo de ``IrFieldsConverter._xmlid_to_record_id``.
    """

    _name = 'res.country'
    _description = 'Country'
    _order = 'name, id'
    _rec_names_search = ['name', 'code']

    name        = fields.Char(
        max_length=120,
        help_text='Nombre del país (Odoo res.country.name).',
    )
    code        = fields.Char(
        max_length=2, unique=True, null=True, blank=True,
        help_text='Código ISO 3166-1 alpha-2 (Odoo code).',
    )
    currency    = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='countries',
        help_text='Moneda del país (Odoo currency_id).',
    )
    phone_code  = fields.Integer(
        null=True, blank=True,
        help_text='Código telefónico del país (Odoo phone_code).',
    )
    address_format = fields.Text(
        blank=True, default=DEFAULT_ADDRESS_FORMAT,
        help_text='Plantilla con la que se compone una dirección de este país '
                  '(Odoo address_format).',
    )
    name_position = fields.Selection(
        max_length=8, choices=NAME_POSITIONS, default='before',
        help_text='Dónde va el nombre del cliente respecto de la dirección '
                  '(Odoo name_position).',
    )
    vat_label = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Cómo se llama el identificador fiscal en este país — «RFC» '
                  'en México, «NIF» en España (Odoo vat_label).',
    )
    state_required = fields.Boolean(
        default=False,
        help_text='El estado es obligatorio en una dirección de este país '
                  '(Odoo state_required).',
    )
    zip_required = fields.Boolean(
        default=True,
        help_text='El código postal es obligatorio (Odoo zip_required).',
    )
    #: ≙ ``country_group_codes`` (``odoo19c: res_country.py:68``), que allá es
    #: ``fields.Json(compute="_compute_country_group_codes")`` — un computado
    #: SIN ``store``. Era un ``@property`` aquí, y su docstring lo justificaba
    #: con *"no hay columna que migrar"*: eso explica la referencia, no nuestra
    #: diferencia. Un ``@property`` no vive en ``_meta``, así que ninguna cadena
    #: ``related=`` puede navegarlo — que es lo que rompía
    #: ``company_country_group_codes`` de ``SiteConfigSettings``.
    country_group_codes = fields.Json(
        compute='_compute_country_group_codes', store=False)

    # `country_groups` NO se declara aquí: ya existe como el `related_name` del
    # M2M que `ResCountryGroup.country_ids` declara sobre la tabla
    # `res_country_res_country_group_rel` — la misma que nombra
    # `odoo19c: res_country.py:66`. Declararlo de este lado creaba una SEGUNDA
    # relación con el mismo accesor (fields.E302/E303) en vez de reusar la que
    # ya modelaba el vínculo.

    class Meta:
        db_table = 'res_country'
        ordering = ['name']
        verbose_name = 'País'
        verbose_name_plural = 'Países'

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Normaliza el código a mayúsculas — ≙ ``create``/``write``.

        ≙ ``odoo19c: res_country.py:111-114,120-121``, que hace
        ``vals['code'] = vals['code'].upper()`` en **ambos**. No es cosmética:
        el índice único vive sobre ``code``, y sin la normalización ``'mx'`` y
        ``'MX'`` son dos filas distintas que la restricción no impide. Un
        segundo México con el código en minúsculas rompe toda búsqueda por país
        sin que nada falle en el momento de crearlo.

        Lo que **no** se porta de esos dos overrides es el
        ``registry.clear_cache('stable'|'templates')``: es la invalidación del
        caché del ORM de la referencia (``tools.ormcache``), un mecanismo que
        este stack no tiene. Divergencia de mecanismo, no recorte —
        aquí no hay caché que invalidar.
        """
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    def get_address_fields(self):
        """Las claves que su plantilla de dirección usa — ≙ ``get_address_fields``.

        ≙ ``odoo19c: res_country.py:138-140``. Extrae los ``%(clave)s`` del
        ``address_format``: es lo que dice **qué campos pedir** al capturar una
        dirección de este país. México pide estado (``state_code``); el Reino
        Unido, el nombre del estado y no su código.
        """
        return re.findall(r'\((.+?)\)', self.address_format or '')

    @classmethod
    def phone_code_for(cls, code):
        """El código telefónico de un país — ≙ ``_phone_code_for``.

        ≙ ``odoo19c: res_country.py:107-109``. Allá lleva ``ormcache`` porque
        se consulta en cada validación de teléfono; aquí es una consulta
        directa, y añadir un caché sin haber medido la presión sería optimizar
        a ciegas.
        """
        country = cls.objects.filter(code=(code or '').upper()).first()
        return country.phone_code if country else None

    def _compute_country_group_codes(self):
        """Los códigos de sus agrupaciones — ≙ ``_compute_country_group_codes``
        (``odoo19c: odoo/addons/base/models/res_country.py:162-168``).

        **Devuelve ``['']`` cuando no hay ninguna**, y eso no es una rareza: la
        fuente lo documenta en su propio docstring —*"If a country has no
        associated country groups, assign [''] to country_group_codes"*— porque
        su ORM guardaría la lista vacía como ``False``, y quien la recorriera
        iteraría sobre un booleano. Aquí no hay ese riesgo, pero el valor se
        conserva porque es **contrato**: ``account_fiscal_country`` compara
        contra esta lista, y cambiar ``['']`` por ``[]`` alteraría el resultado
        de esa comparación para todo país sin agrupación.
        """
        return [g.code for g in self.country_groups.all() if g.code] or ['']

    @property
    def image_url(self):
        """La bandera — ≙ ``_compute_image_url`` (``odoo19c: res_country.py:143``).

        Ruta estática derivada del código ISO. ``None`` para los códigos que la
        referencia excluye por no tener bandera propia.
        """
        if not self.code or self.code.upper() in NO_FLAG_COUNTRIES:
            return None
        code = FLAG_MAPPING.get(self.code.upper(), self.code.lower())
        return f'/base/static/img/country_flags/{code}.png'

    def clean(self):
        """Rechaza una plantilla de dirección con una clave que no existe.

        ≙ ``_check_address_format`` (``odoo19c: res_country.py:152-160``). Sin
        esta guarda, la plantilla rota no falla al guardarse sino al **componer
        una dirección**, que es lejos del sitio del error y en un camino que
        el usuario no asocia con el país.
        """
        super().clean()
        if not self.address_format:
            return
        try:
            self.address_format % {key: 1 for key in ADDRESS_FORMAT_KEYS}
        except (ValueError, KeyError) as exc:
            raise ValidationError(
                _('La plantilla de dirección contiene una clave inválida.')
            ) from exc


class ResCountryState(models.Model):
    """``res.country.state`` — estado/provincia de un país (Odoo base).

    Fiel a ``res_country.py`` (18:162-171 / 19 idéntico): ``country`` (FK,
    requerido), ``name`` (requerido), ``code`` (requerido). Único (country, code)
    replica el ``_sql_constraints`` ``name_code_uniq`` de Odoo.

    Atributos de clase completados en la tarea **#132**, igual que en
    :class:`ResCountry`.
    """

    _name = 'res.country.state'
    _description = 'Country state'
    _order = 'code, id'
    _rec_names_search = ['name', 'code']

    country = fields.Many2one(
        'base.ResCountry', on_delete=models.CASCADE, related_name='state_ids',
        help_text='País (Odoo country_id).',
    )
    name    = fields.Char(
        max_length=120, help_text='Nombre del estado (Odoo name).',
    )
    code    = fields.Char(
        max_length=8, help_text='Código del estado (Odoo code).',
    )

    class Meta:
        db_table = 'res_country_state'
        constraints = [
            models.UniqueConstraint(
                fields=['country', 'code'], name='unique_state_country_code',
            ),
        ]
        ordering = ['country', 'code']
        verbose_name = 'Estado / provincia'
        verbose_name_plural = 'Estados / provincias'

    def __str__(self) -> str:
        return f'{self.name} ({self.country.code})'
