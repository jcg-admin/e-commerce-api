"""``res.company`` — entidad legal, con jerarquía de sucursales.

Adaptación de ``odoo/addons/base/models/res_company.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 521 líneas).

Colisión con ``company.Company`` — declarada, no resuelta aquí
==============================================================

Este árbol ya tiene ``company.Company``: el **tenant L1** que contrata la
plataforma (DEC-KX-05, ADR-021), con su ``status`` comercial, sus
``CompanySetting`` y el aislamiento de fila L3. ``res.company`` de la
referencia es otra cosa: la **entidad legal** que emite documentos —con su
razón social, su RFC, su moneda funcional y su membrete de reporte— y que
puede tener **sucursales**.

No son el mismo objeto y por eso no se colapsan: un tenant L1 podría operar
más de una entidad legal, y una entidad legal no contrata nada. Se porta el
archivo completo con el nombre de la referencia (``ResCompany``, tabla
``res_company``); reconciliar ambos ejes —o decidir que uno referencia al
otro— es decisión de producto y va en su propio pase, no de rebote desde
``base``.

La delegación al partner, que es la idea estructural del archivo
================================================================

En la referencia una compañía **es un partner** más los datos de compañía:
``name``, ``email``, ``phone``, ``website``, ``vat``, ``company_registry`` y
``logo`` son campos ``related`` a ``partner_id``, no columnas propias. Los de
dirección (``street``, ``street2``, ``zip``, ``city``, ``state_id``,
``country_id``) son ``compute`` **con inverse**: se leen del partner y al
escribirlos se escriben en el partner.

Eso se porta como propiedades con *setter*, que es el equivalente exacto del
par ``compute``/``inverse``: leer delega, escribir propaga. Duplicar las
columnas rompería la invariante de que el partner es la única fuente de la
identidad — la misma razón por la que ``res_users.py`` delega en el partner.

La jerarquía y su ruta materializada
====================================

``parent_path`` es una **ruta materializada** (``'1/4/9/'``): la lista de
ancestros codificada en una columna, para que obtener la cadena completa sea
leer un campo en vez de N consultas. De ahí salen ``parent_ids`` (todos los
ancestros, el propio incluido) y ``root_id`` (el primero). Se porta con su
mantenimiento en ``save()``, que la fuente delega a su ORM.

``_get_company_root_delegated_field_names`` es el mecanismo por el que una
sucursal **hereda de su raíz**: los campos que lista se copian de la raíz y
salen de sólo lectura en el formulario. En la referencia la lista es
``['currency_id']`` — una sucursal no puede tener otra moneda funcional que su
matriz. Se porta como está, incluido el hecho de que sea un método y no una
constante: un addon la extiende añadiendo campos.

Detalles pequeños que un port ingenuo pierde
============================================

- ``_compute_color`` cae a ``root_id.id % 12`` cuando el partner no declara
  color: un color estable derivado del id, no un default fijo. Doce es el
  tamaño de la paleta.
- ``_compute_logo_web`` redimensiona a ``(180, 0)``: **ancho 180, alto libre**.
  El cero no es "sin alto", es "el que salga al preservar la proporción".
- ``uses_default_logo`` compara contra el logotipo por defecto, no contra
  vacío: una compañía que nunca cambió el logo cuenta como "por defecto"
  aunque tenga bytes.
- ``_onchange_country_id`` fija la moneda desde el país. Se porta como método
  explícito porque aquí no hay ``onchange`` del ORM.

Qué NO se porta, con su medición
================================

- **``ZeepOrmCache``** — **PORTADO** en este pase, junto con
  ``_get_zeep_cache__`` y ``_get_zeep_client__``. Este bullet declinaba **uno**
  de los tres símbolos y su razón era *"no hay cliente SOAP en este árbol"*,
  que describe nuestro estado y no un impedimento — el anti-patrón que
  ``porte-completo-no-parcial.md`` prohíbe. El cliente se construyó:
  ``src/tools/zeep/`` porta el envoltorio de seguridad de la referencia
  (``odoo19c: odoo/tools/zeep/``) sobre ``zeep==4.3.3``, ya declarado en
  ``pyproject.toml``. Ver :ref:`h-api-990`.
- **``install_l10n_modules`` / ``uninstalled_l10n_module_ids``** — instalan
  paquetes de localización en caliente. Es el instalador, cuya ausencia
  ``ir_module.py`` ya declara y justifica.
- **``external_report_layout_id``** (``ir.ui.view``) y ``_get_view`` — capa de
  vistas. **Actualizado** (porte de ``ir_ui_view.py``):
  ``grep -rn "^class IrUiView\b" src/`` → **1** clase. [PROVEN] La medición de
  **0** que sostenía la omisión dejó de ser cierta. El campo **sigue** sin
  columna aquí y su desenlace es la tarea **#257**; el precedente que este
  bullet citaba —``ir_filters.action_id``— **ya no difiere**: se convirtió en
  ``base/migrations/0077`` (:ref:`h-api-982`). ``_get_view`` sigue fuera por
  otra razón —
  depende del combinador de XML, que ``ir_ui_view.py`` deja fuera con su
  medición.

Fechas del ejercicio fiscal — sitio divergente, declarado (tarea #207)
========================================================================

``fiscalyear_last_day``/``fiscalyear_last_month`` y
``compute_fiscalyear_dates`` (``odoo19c: account/models/company.py:74-75,
1114-1122``) desbloquean ``fiscal_year_search`` de
``addons/analytic/models/analytic_line.py`` y los ``related`` que
``account/wizard/setup_wizards.py`` declara pendientes.

La referencia los pone en la extensión ``account`` de ``res.company``
(``_inherit``); este árbol replica ese ``_inherit`` con
``apply_account_extensions()`` en ``addons/account/models/res_company.py``,
que ya cuelga los cinco candados de fecha por el mismo mecanismo
(``_add_if_absent`` + ``ready()`` de ``AccountConfig``).

**Aquí NO se usa ese sitio.** El alcance de la tarea #207 restringe la
edición a este archivo — evita una carrera de escritura con otros agentes
que tocan ``account/models/res_company.py`` en la misma tanda. Los dos
campos y el método se declaran **directamente en la clase base**, con la
divergencia citada aquí para que quien la lea sepa que no es la forma
preferida del proyecto, sino la que el alcance de este pase permitía.
Prospectivo: si ``account/models/res_company.py`` gana un tramo libre para
este par, migrar ahí no cambia la firma pública (mismo nombre, mismo
comportamiento) — es un rehome, no un rediseño.

``_check_fiscalyear_last_day`` (``odoo19c: :330-343``) se porta como guard
explícito —no auto-hooked a ``save()``—, mismo patrón que
``validate_hard_lock_date_change`` en ``account/models/res_company.py``: la
referencia la ancla a ``account_opening_date`` (asiento de apertura), campo
que este árbol no porta (Bloque 1, tarea #137). Se resuelve con
``getattr(self, 'account_opening_date', None)`` y cae al año en curso
cuando no existe — es DIVERGENCIA DE MECANISMO, no un recorte: la fuente
también cae al año en curso cuando no hay fecha de apertura.
"""
import base64
import calendar
import logging
from datetime import date

from zeep.cache import Base as ZeepCache

import api
import fields
import models
from exceptions import ValidationError
from orm.environments import sudo
from tools import date_utils, zeep
from tools.cache import ormcache
from tools.translate import _
from addons.base.models.report_paperformat import ReportPaperformat
from addons.base.models.res_country import ResCountry, ResCountryState
from addons.base.models.res_currency import ResCurrency
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)

#: Ancho al que se reduce el logotipo para la cabecera — ``(180, 0)`` de la
#: fuente: ancho fijo, alto el que resulte de preservar la proporción.
LOGO_WEB_WIDTH = 180

#: Tamaño de la paleta del color derivado (``id % 12`` en la fuente).
COLOR_PALETTE_SIZE = 12

#: Tipografías del membrete, verbatim de la referencia.
FONT_CHOICES = [
    ('Lato', 'Lato'),
    ('Roboto', 'Roboto'),
    ('Open_Sans', 'Open Sans'),
    ('Montserrat', 'Montserrat'),
    ('Oswald', 'Oswald'),
    ('Raleway', 'Raleway'),
    ('Tajawal', 'Tajawal'),
    ('Fira_Mono', 'Fira Mono'),
]

LAYOUT_BACKGROUND_CHOICES = [
    ('Blank', 'En blanco'),
    ('Demo logo', 'Logotipo de demostración'),
    ('Custom', 'Personalizado'),
]

#: ≙ ``MONTH_SELECTION`` (``odoo19c: account/models/company.py:17-30``) —
#: el vocabulario de la fuente, verbatim y en el mismo orden (mismo criterio
#: que ``ANNUAL_INVENTORY_MONTH_CHOICES`` de ``addons/stock/models/
#: res_company.py``, que reutiliza esta misma lista de meses).
MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
    ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
    ('9', 'September'), ('10', 'October'), ('11', 'November'),
    ('12', 'December'),
]


class ZeepOrmCache(ZeepCache):
    """Caché de XSD/WSDL para ``zeep``, respaldada por la caché del ORM.

    ≙ ``ZeepOrmCache`` (``odoo19c: res_company.py:18-27``).

    ``zeep`` define el contrato en ``zeep.cache.Base``: ``add(url, content)``
    y ``get(url)``. Su implementación por defecto es un SQLite en disco; ésta
    la sustituye por el bucket que ``_get_zeep_cache__`` mantiene en la caché
    ``stable`` del registro, por compañía. Así el WSDL de una autoridad
    tributaria se descarga una vez por proceso y no una por petición.
    """

    def __init__(self, company):
        self.company = company

    def add(self, url, content):
        self.company._get_zeep_cache__()[url] = content

    def get(self, url):
        return self.company._get_zeep_cache__().get(url)


class ResCompanyManager(models.AccessManager):
    """El ``create`` de la fuente: la compañía nace CON su partner.

    ``odoo19c: res_company.py:296-300`` fabrica el ``res.partner``
    (``is_company=True``) dentro del ``create`` del modelo — la identidad
    (nombre, contacto) nunca vive en la compañía. Se replica en el manager
    por defecto para que ``ResCompany.objects.create(name=...)`` conserve el
    contrato de la referencia. La moneda es requerida; si no se pasa, se
    hereda de la compañía principal (el default de la fuente:
    ``default=lambda self: self.env.company.currency_id``) y, en el
    bootstrap sin compañías, cae a la moneda de la semilla base (MXN — el
    análogo local del dato de ``res_currency_data.xml``).
    """

    def create(self, **kwargs):
        name = kwargs.pop('name', None)
        if 'partner' not in kwargs and 'partner_id' not in kwargs:
            kwargs['partner'] = ResPartner.objects.create(
                name=name or '', is_company=True)
        elif name is not None:
            partner = kwargs.get('partner')
            if partner is not None:
                partner.name = name
                partner.save(update_fields=['name'])
        if 'currency' not in kwargs and 'currency_id' not in kwargs:
            main = self.model.get_main_company()
            if main is not None:
                kwargs['currency'] = main.currency
            else:
                kwargs['currency'], _ = ResCurrency.objects.get_or_create(
                    name='MXN', defaults={'symbol': '$'})
        return super().create(**kwargs)


class ResCompany(TimeStampedModel):
    """Entidad legal que emite documentos (``res.company``).

    Absorbe también el eje L1 de plataforma (``code``/``status``/``is_system``)
    del modelo ``Company`` paralelo que se disolvió — una sola tabla, como la
    referencia. Ver ``analisis-extension-de-company-tres-motores``.
    """

    _name = 'res.company'
    _description = 'Companies'
    _order = 'sequence, name'
    _inherit = ['format.address.mixin', 'format.vat.label.mixin']
    _parent_store = True

    objects = ResCompanyManager()

    #: Campos que una sucursal hereda de su raíz. Es un método en la fuente
    #: para que un addon lo extienda; aquí, un ``classmethod`` por lo mismo.
    #: ``fiscalyear_last_day``/``fiscalyear_last_month`` se suman aquí — ≙
    #: ``_get_company_root_delegated_field_names`` de ``account``
    #: (``odoo19c: company.py:311-316``): una sucursal no fija su propio
    #: cierre de ejercicio, hereda el de su matriz.
    _ROOT_DELEGATED_FIELDS = ('currency', 'fiscalyear_last_day',
                              'fiscalyear_last_month')

    #: Campos de dirección que viven en el partner y se leen a través de él.
    _ADDRESS_FIELDS = (
        'street', 'street2', 'city', 'zip', 'state', 'country',
    )

    partner = fields.Many2one(
        ResPartner, on_delete=models.PROTECT, db_index=True,
        related_name='companies', verbose_name='Partner',
        help_text='Odoo partner_id. La identidad de la compañía vive aquí.',
    )
    #: ≙ ``bank_ids`` (``odoo19c: res_company.py:77``), verbatim salvo los
    #: nombres de las FK —allá ``partner_id.bank_ids``, aquí
    #: ``partner.bank_accounts``—. Sin ``store``, que es el defecto de la
    #: fuente para un ``related``: no ocupa columna y navega al leerse.
    #:
    #: Su ``readonly=False`` no es adorno: dice que el conjunto se puede
    #: escribir desde la empresa, y el inverso lo lleva al titular
    #: (``NonStored.inverse_related``). Que el extremo sea un manager y no un
    #: valor es justo lo que hacía falta construir (:ref:`h-api-979`).
    bank_ids = fields.One2many(related='partner.bank_accounts',
                               readonly=False)
    active = fields.Boolean(default=True, verbose_name='Activa')
    sequence = fields.Integer(
        default=10, verbose_name='Secuencia',
        help_text='Ordena las compañías en el selector (Odoo sequence).',
    )

    # === Eje L0 (operador de plataforma) ==================================
    # La referencia no modela un operador de plataforma, así que estos tres
    # campos no tienen análogo. Lo que SÍ gobierna la referencia es *dónde*
    # van: el criterio es la cardinalidad, no el dominio (``auth_ldap`` de
    # ``odoo19c:``/``odoo18c:`` reparte por ahí — ``_inherit`` sobre
    # ``res.company`` para el dato 1:1, modelo propio ``res.company.ldap``
    # para el 1:N). Los tres son 1:1 con la compañía, así que son columnas.
    # En Odoo los aportaría la familia L0 vía ``_inherit``; Django no tiene
    # ese mecanismo distribuido para el esquema, así que viven aquí.
    # Ver ``analisis-extension-de-company-tres-motores``.

    class Status(models.TextChoices):
        TRIAL = 'trial', 'En prueba'
        ACTIVE = 'active', 'Activo'
        SUSPENDED = 'suspended', 'Suspendido'
        CANCELLED = 'cancelled', 'Cancelado'

    code = models.SlugField(
        max_length=50, unique=True, null=True, blank=True,
        verbose_name='Código',
        help_text='Identificador estable del tenant L1 en la plataforma.',
    )
    status = fields.Selection(
        max_length=12, choices=Status.choices, default=Status.TRIAL,
        verbose_name='Estado',
        help_text='Ciclo de vida de la contratación. Distinto de ``active``, '
                  'que es el archivado de Odoo.',
    )
    is_system = fields.Boolean(
        default=False, verbose_name='Compañía de sistema',
        help_text='Compañía de datos compartidos de plataforma (L0), no un '
                  'tenant.',
    )
    billing_email = fields.Char(
        max_length=254, blank=True, default='',
        verbose_name='Correo de facturación',
        help_text='DIVERGENCIA DECLARADA: la referencia no separa el correo '
                  'de contacto del de facturación en ``res.company`` — su '
                  '``email`` es ``related`` al partner y la facturación sale '
                  'del partner de la factura. Se conserva como columna propia '
                  'porque el negocio sí los distingue; si se unifican, este '
                  'campo desaparece a favor de la property ``email``.',
    )
    parent = fields.Many2one(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        db_index=True, related_name='child_ids', verbose_name='Compañía matriz',
        help_text='Odoo parent_id, con ondelete restrict.',
    )
    parent_path = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Ruta de ancestros',
        help_text="Ruta materializada '1/4/9/' — evita N consultas para "
                  'obtener la cadena de matrices.',
    )
    currency = fields.Many2one(
        ResCurrency, on_delete=models.PROTECT, db_index=True,
        related_name='companies', verbose_name='Moneda',
    )
    user_ids = fields.Many2many(
        ResUsers, blank=True, related_name='company_ids',
        through='ResCompanyUsersRel', verbose_name='Usuarios aceptados',
    )

    # — Membrete de los documentos impresos —
    report_header = fields.Html(
        blank=True, default='', verbose_name='Lema de la compañía',
        help_text='Se incluye en la cabecera o el pie del documento impreso, '
                  'según el diseño elegido.',
    )
    report_footer = fields.Html(
        blank=True, default='', verbose_name='Pie de reporte')
    company_details = fields.Html(
        blank=True, default='', verbose_name='Detalles de la compañía')
    paperformat = fields.Many2one(
        ReportPaperformat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='companies', verbose_name='Formato de papel',
    )
    font = fields.Selection(
        max_length=32, choices=FONT_CHOICES, default='Lato',
        verbose_name='Tipografía')
    primary_color = fields.Char(
        max_length=32, blank=True, default='', verbose_name='Color primario')
    secondary_color = fields.Char(
        max_length=32, blank=True, default='', verbose_name='Color secundario')
    layout_background = fields.Selection(
        max_length=16, choices=LAYOUT_BACKGROUND_CHOICES, default='Blank',
        verbose_name='Fondo del diseño')
    layout_background_image = fields.Image(
        upload_to='company/layout/', null=True, blank=True,
        verbose_name='Imagen de fondo')

    # === Ejercicio fiscal (Odoo account) ==================================
    # ≙ ``fiscalyear_last_day``/``fiscalyear_last_month``
    # (``odoo19c: account/models/company.py:74-75``). Sitio divergente
    # declarado en el docstring del módulo: la referencia los pone en la
    # extensión ``account`` de ``res.company``; aquí van directos en la
    # clase base por el alcance de la tarea #207. Ver ese docstring.
    fiscalyear_last_day = fields.Integer(
        default=31, verbose_name='Último día del ejercicio fiscal',
        help_text='Día del mes en que cierra el ejercicio fiscal de esta '
                  'compañía (Odoo fiscalyear_last_day).',
    )
    fiscalyear_last_month = fields.Selection(
        max_length=2, choices=MONTH_SELECTION, default='12',
        verbose_name='Último mes del ejercicio fiscal',
        help_text='Mes en que cierra el ejercicio fiscal de esta compañía '
                  '(Odoo fiscalyear_last_month).',
    )

    class Meta:
        db_table = 'res_company'
        # ``odoo19c: res_company.py:34`` declara ``_order = 'sequence, name'``.
        # Aquí ``name`` es una **propiedad delegada** al partner, no una
        # columna, así que el orden equivalente atraviesa la FK: ordenar por
        # ``name`` a secas es un error de Django (models.E015).
        ordering = ['sequence', 'partner__name', 'id']
        verbose_name = 'Compañía'
        verbose_name_plural = 'Compañías'
        constraints = [
            # ``_name_uniq`` de la fuente: "The company name must be unique!".
            # El nombre vive en el partner, así que la unicidad se declara
            # sobre el partner: una entidad legal por partner.
            models.UniqueConstraint(
                fields=['partner'], name='res_company_partner_uniq'),
        ]

    def __str__(self):
        return self.name

    # === Delegación al partner ===========================================

    @property
    def name(self):
        """``related='partner_id.name'`` — la razón social vive en el partner."""
        return self.partner.name

    @name.setter
    def name(self, value):
        self.partner.name = value

    @property
    def email(self):
        return self.partner.email

    @email.setter
    def email(self, value):
        self.partner.email = value

    @property
    def phone(self):
        return self.partner.phone

    @phone.setter
    def phone(self, value):
        self.partner.phone = value

    @property
    def website(self):
        return getattr(self.partner, 'website', '')

    @property
    def billing_name(self):
        """Razón social — ``related`` a ``partner.commercial_company_name``.

        No es columna propia: la referencia deriva la razón social de la
        entidad comercial del partner (``odoo19c: res_partner.py:306``,
        ``compute=_compute_commercial_company_name``), y este árbol ya porta
        esa cadena. Duplicarla aquí habría sido el mismo error que el modelo
        ``Company`` paralelo que esta fusión disuelve.
        """
        return self.partner.commercial_company_name

    @property
    def vat(self):
        """``related='partner_id.vat'`` — el identificador fiscal."""
        return getattr(self.partner, 'vat', '')

    @property
    def logo(self):
        """``related='partner_id.image_1920'``."""
        return getattr(self.partner, 'image_1920', None)

    # === Dirección: compute + inverse =====================================
    #
    # ≙ ``odoo19c: base/models/res_company.py:69-79`` — los seis campos de
    # dirección son ``compute='_compute_address'`` con un ``inverse`` nombrado.
    # **Eran seis ``@property`` con su ``setter``**, y esa forma tenía un
    # defecto que no era de estilo: un ``@property`` no vive en ``_meta``, así
    # que ninguna cadena ``related=`` puede navegarlo. Medido antes de
    # corregirlo: ``SiteConfigSettings.company_country_code`` y
    # ``company_country_group_codes`` —las dos cadenas que pasan por
    # ``company.country``— rompían con *falta ResCompany.country*, con un solo
    # eslabón ausente para las dos (TASK-API-0412).
    #
    # Los nombres **no llevan el sufijo** ``_id`` de la fuente: es la
    # convención de este árbol para un ``Many2one`` (``partner``, ``currency``,
    # ``parent``), y el mapa a la fuente lo lleva el ``help_text`` de cada uno.

    #: ≙ ``_get_company_address_field_names`` (``:121-124``), con su docstring:
    #: *"Return a list of fields coming from the address partner to match on
    #: company address fields. Fields are labeled same on both models."*
    #: Ese *"labeled same"* es lo que hace que el compute y los seis inversos
    #: puedan ser un solo ``getattr``/``setattr`` por nombre.
    ADDRESS_FIELD_NAMES = ('street', 'street2', 'city', 'zip', 'state',
                           'country')

    street = fields.Char(compute='_compute_address', inverse='_inverse_street',
                         help_text='Odoo street.')
    street2 = fields.Char(compute='_compute_address',
                          inverse='_inverse_street2',
                          help_text='Odoo street2.')
    #: El ``if name == 'state'`` de ``orm/fields.py`` fija ``copy=False`` sobre
    #: este campo porque su nombre es ``state``; allá la regla no lo toca
    #: porque el campo se llama ``state_id``. El resultado es el mismo: un
    #: calculado sin columna ya sale ``copy=False`` por el bloque de
    #: ``compute``, así que la coincidencia de nombre no cambia nada.
    zip = fields.Char(compute='_compute_address', inverse='_inverse_zip',
                      help_text='Odoo zip.')
    city = fields.Char(compute='_compute_address', inverse='_inverse_city',
                       help_text='Odoo city.')
    state = fields.Many2one(
        ResCountryState, compute='_compute_address',
        inverse='_inverse_state', verbose_name='Fed. State',
        help_text='Odoo state_id.')
    country = fields.Many2one(
        ResCountry, compute='_compute_address',
        inverse='_inverse_country', verbose_name='Country',
        help_text='Odoo country_id.')
    #: ≙ ``country_code`` (``:79``), que allá es
    #: ``fields.Char(related='country_id.code', depends=['country_id'])``.
    #: Era un ``@property`` y por eso la cadena de ``SiteConfigSettings`` no
    #: podía navegarlo.
    country_code = fields.Char(related='country.code', depends=['country'])

    @classmethod
    def _get_company_address_field_names(cls):
        """Los campos que se copian del partner — ≙ ``:121-124``.

        **Divergencia de mecanismo declarada: aquí es un método de clase.** La
        fuente lo declara de instancia y lo llama desde el ``lambda`` de
        ``@api.depends`` (``:135``), donde ``self`` es el recordset vacío del
        modelo — una cosa que es instancia y modelo a la vez. En este stack el
        lector de dependencias invoca ``deps(model)`` con la **clase**
        (``orm/fields.py:4158``), así que un método de instancia revienta con
        *missing 1 required positional argument*. Medido antes de corregirlo:
        ``scripts/evidence/aceptacion-0412-2026-09-12T08-55-*.log``.
        """
        return list(cls.ADDRESS_FIELD_NAMES)

    def _get_company_address_update(self, partner):
        """≙ ``_get_company_address_update`` (``:126-128``), verbatim salvo el
        acceso: allá ``partner[fname]`` sobre un recordset, aquí ``getattr``
        sobre la fila."""
        return {fname: getattr(partner, fname)
                for fname in self._get_company_address_field_names()}

    @api.depends(lambda self: [f'partner.{fname}'
                               for fname in
                               self._get_company_address_field_names()])
    def _compute_address(self):
        """La dirección se LEE del partner — ≙ ``_compute_address`` (``:136-141``).

        La fuente no toma los campos del partner directamente: pide su
        dirección de contacto con ``address_get(adr_pref=['contact'])``, que es
        una **búsqueda en profundidad** por los hijos dentro de la frontera de
        empresa. Una compañía con una sucursal de tipo ``contact`` colgada usa
        la dirección de la sucursal, no la del titular; un ``getattr`` plano
        sobre ``self.partner`` daría la del titular y sería otro dato.

        Divergencias de mecanismo, las de siempre en este árbol: el bucle
        ``for company in self.filtered(...)`` se colapsa a una fila, y
        ``company.update(...)`` —que allá escribe sobre el recordset— es aquí
        el ``setattr`` por nombre. La elevación la aporta el alcance de
        ``orm.environments.sudo``, no un recordset elevado.

        **Sin partner no computa, y eso es FIEL, no un recorte.** La fuente
        abre con ``for company in self.filtered(lambda company: company.partner_id)``
        (``:138``): una compañía sin partner sale del bucle y su dirección
        queda sin tocar. El ``return`` temprano de aquí es esa misma conducta
        sobre una fila.

        **Dos guardas que la fuente NO tiene, declaradas:**

        - ``address_data.get('contact')`` contra su ``if address_data['contact']``
          (``:140``). La fuente confía en que la clave exista; aquí un
          ``address_get`` que no la devuelva da ``None`` en vez de ``KeyError``.
        - ``if source is None: return``. La fuente hace ``browse(id)``, que
          nunca devuelve ``None`` — un id inexistente allá revienta con
          ``MissingError`` al leerlo. Aquí un ``contact`` colgado apuntando a
          una fila borrada deja la dirección sin computar **en silencio**, que
          es menos ruidoso que la fuente. Su sucesor es **TASK-GEN-0633**.
        """
        partner = self.partner if self.partner_id else None
        if partner is None:
            return
        with sudo():
            address_data = partner.address_get(adr_pref=['contact'])
            contact_id = address_data.get('contact')
            if not contact_id:
                return
            source = (partner if contact_id == partner.pk
                      else type(partner).objects.filter(pk=contact_id).first())
            if source is None:
                return
            for fname, value in self._get_company_address_update(source).items():
                setattr(self, fname, value)

    def _inverse_street(self):
        """≙ ``_inverse_street`` (``:143-145``)."""
        self._write_address_to_partner('street')

    def _inverse_street2(self):
        """≙ ``_inverse_street2`` (``:147-149``)."""
        self._write_address_to_partner('street2')

    def _inverse_zip(self):
        """≙ ``_inverse_zip`` (``:151-153``)."""
        self._write_address_to_partner('zip')

    def _inverse_city(self):
        """≙ ``_inverse_city`` (``:155-157``)."""
        self._write_address_to_partner('city')

    def _inverse_state(self):
        """≙ ``_inverse_state`` (``:159-161``)."""
        self._write_address_to_partner('state')

    def _inverse_country(self):
        """≙ ``_inverse_country`` (``:163-165``)."""
        self._write_address_to_partner('country')

    def _write_address_to_partner(self, fname):
        """El cuerpo común de los seis inversos — ``partner_id.<f> = self.<f>``.

        Los seis de la fuente son la misma línea con otro nombre de campo
        (``:143-165``); aquí se factoriza porque además hay que **persistir**,
        que es la divergencia de mecanismo: allá la asignación sobre el
        recordset ya escribe —el caché del ORM es su canal de escritura— y
        aquí una asignación de Django no emite SQL.

        Se guarda el partner ENTERO, no ``update_fields=[fname]``: cambiar un
        campo de dirección debe disparar ``ResPartner.save`` completo, que es
        quien propaga la dirección a los hijos (``_fields_sync``). Acotar los
        campos saltaría esa propagación, que la fuente sí produce.

        **El ``return`` sin partner es FIEL — medido, no supuesto.** La fuente
        escribe ``company.partner_id.street = company.street`` (``:145``) sin
        guarda: sobre un ``partner_id`` vacío eso llega a ``Field.__set__``
        (``odoo19c: odoo/orm/fields.py:1807-1841``), que reparte ``records._ids``
        en tres cubos y, con la tupla vacía, no entra en ninguno — **no-op
        silencioso**, no excepción. La guarda de aquí produce el mismo
        desenlace de forma explícita.
        """
        partner = self.partner if self.partner_id else None
        if partner is None:
            return
        setattr(partner, fname, getattr(self, fname))
        if partner.pk:
            partner.save()

    # === Jerarquía ========================================================

    def _compute_parent_path(self):
        """Ruta materializada del ancestro, terminada en ``/``."""
        if self.parent_id is None:
            return f'{self.pk}/'
        return f'{self.parent.parent_path}{self.pk}/'

    @property
    def parent_ids(self):
        """Todos los ancestros, el propio incluido — ``_compute_parent_ids``.

        Sale de leer ``parent_path``, no de recorrer la cadena: ése es el
        propósito de la ruta materializada.
        """
        model = type(self)
        if not self.parent_path:
            return model.objects.filter(pk=self.pk)
        ids = [int(i) for i in self.parent_path.split('/') if i]
        return model.objects.filter(pk__in=ids)

    @property
    def root_id(self):
        """La raíz de la jerarquía — el primero de ``parent_ids``."""
        return self.parent_ids.order_by('pk').first() or self

    @classmethod
    def get_company_root_delegated_field_names(cls):
        """Campos que una sucursal copia de su raíz.

        La fuente devuelve ``['currency_id']``: una sucursal no puede tener
        otra moneda funcional que su matriz. Es un método —no una constante—
        para que un addon lo extienda.
        """
        return list(cls._ROOT_DELEGATED_FIELDS)

    def apply_root_delegation(self):
        """Copia desde la raíz los campos delegados, como hace la fuente."""
        root = self.root_id
        if root.pk == self.pk:
            return
        for fname in self.get_company_root_delegated_field_names():
            setattr(self, fname, getattr(root, fname))

    # === Derivados de presentación ========================================

    @property
    def color(self):
        """Color del partner de la raíz, o uno estable derivado de su id.

        El respaldo ``id % 12`` de la fuente da un color **estable** por
        compañía en vez de un default fijo; 12 es el tamaño de la paleta.

        ≙ ``_compute_color`` (``odoo19c: base/models/res_company.py``).
        """
        root = self.root_id
        declared = getattr(root.partner, 'color', None)
        if declared:
            return declared
        return (root.pk or 0) % COLOR_PALETTE_SIZE

    @property
    def logo_web(self):
        """Logotipo reducido a 180 px de **ancho**, alto proporcional.

        El ``(180, 0)`` de la fuente no significa "sin alto": significa el que
        resulte de preservar la proporción.

        ≙ ``_compute_logo_web`` (``odoo19c: base/models/res_company.py``).
        """
        return getattr(self.partner, 'image_256', None) or self.logo

    def logo_png_b64(self) -> str:
        """Bytes del logotipo como base64, o ``''`` si no hay o no es PNG.

        El consumidor es el descriptor del reporte (T-006 de
        ``integrar-libharu``): el helper sólo acepta PNG (ADR-017), así que
        otro formato degrada aquí — el descriptor nunca lleva bytes que el
        helper no pueda incrustar. La firma se comprueba sobre los bytes
        reales, no sobre la extensión del archivo. Es método (no property)
        para que el resolver de variables de DTL lo invoque desde la
        plantilla en BD: ``{{ docs.company.logo_png_b64 }}``.
        """
        logo = self.logo
        if not logo:
            return ''
        try:
            logo.open('rb')
            data = logo.read()
            logo.close()
        except (OSError, ValueError):
            # silent OK because un archivo perdido en disco no debe tumbar
            # el recibo: el logo es adorno, el documento es el entregable.
            return ''
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            return ''
        return base64.b64encode(data).decode('ascii')

    def uses_default_logo(self, default_logo=None):
        """¿La compañía sigue con el logotipo por defecto?

        Compara contra el logotipo por defecto, no contra vacío: una compañía
        que nunca lo cambió cuenta como "por defecto" aunque tenga bytes.
        """
        logo = self.logo
        return not logo or (default_logo is not None and logo == default_logo)

    # === Resolución de la compañía principal ==============================

    @classmethod
    def get_main_company(cls):
        """La compañía principal — ``_get_main_company`` de la referencia.

        Adaptación de ``odoo19c: odoo/addons/base/models/res_company.py:436-440``
        (idéntico en ``odoo18c:``): allá se resuelve ``env.ref('base.main_company')``
        con fallback al primero por ``id``. El camino primario exige
        ``ir.model.data`` (no portado), así que aquí rige el fallback de la
        propia fuente — determinista y ABSTRACTO: ``base`` no nombra a ningún
        tenant. Las compañías de sistema quedan fuera: son plataforma, no la
        principal.
        """
        return cls.objects.filter(is_system=False).order_by('id').first()

    @classmethod
    def get_system_company(cls):
        """La compañía de datos compartidos de plataforma (``is_system``).

        **No tiene análogo en la referencia**: Odoo no modela un operador de
        plataforma sobre las compañías. Es eje L0 propio, y por eso no lleva
        fallback — si no existe, existe el problema, y devolver otra compañía
        en su lugar mezclaría datos de plataforma con los de un tenant.
        Se resuelve por la bandera ``is_system`` (abstracta): la compañía
        concreta la siembra el addon dueño del eje (``sale_subscription``).
        """
        return cls.objects.filter(is_system=True).order_by('id').first()

    # === Camino de creación ==============================================

    @classmethod
    def create_company(cls, name, currency=None, **values):
        """Azúcar sobre el ``create`` del manager (que fabrica el partner).

        ABSTRACTO: ninguna empresa concreta se nombra aquí; la compañía de
        sistema es DATO del addon que la declara
        (``sale_subscription/data``) y las L1 se crean por bootstrap
        (``company_create``), no por código.
        """
        if currency is not None:
            values['currency'] = currency
        return cls.objects.create(name=name, **values)

    # === Reglas de coherencia =============================================

    def onchange_state(self):
        """Fijar el estado fija el país — ``_onchange_state``."""
        state = self.state
        if state is not None and getattr(state, 'country_id', None):
            self.country = state.country

    def onchange_country(self):
        """Fijar el país fija la moneda — ``_onchange_country_id``."""
        country = self.country
        if country is not None and getattr(country, 'currency_id', None):
            self.currency = country.currency

    # === Ejercicio fiscal (Odoo account) ==================================

    def compute_fiscalyear_dates(self, current_date):
        """El rango del ejercicio fiscal que contiene ``current_date``.

        ≙ ``compute_fiscalyear_dates`` (``odoo19c:
        account/models/company.py:1114-1122``), verbatim: delega en
        ``tools.date_utils.get_fiscal_year`` — el mismo algoritmo que la
        fuente porta como ``odoo/tools/date_utils.py::get_fiscal_year`` y
        que este árbol ya tiene construido (``src/tools/date_utils.py``).

        El ``self.ensure_one()`` de la fuente no se porta: aquí ``self`` es
        **una** fila, no un conjunto de registros — la misma divergencia de
        mecanismo que ``_get_zeep_client__`` ya declara para el mismo motivo.

        :param current_date: una fecha del ejercicio a resolver.
        :return: ``{'date_from': ..., 'date_to': ...}``, las fronteras del
            ejercicio.
        """
        date_from, date_to = date_utils.get_fiscal_year(
            current_date, day=self.fiscalyear_last_day,
            month=int(self.fiscalyear_last_month))
        return {'date_from': date_from, 'date_to': date_to}

    def _check_fiscalyear_last_day(self):
        """El día de cierre existe en el mes de cierre — ≙
        ``_check_fiscalyear_last_day`` (``odoo19c: :330-343``).

        Guard EXPLÍCITO, no auto-hooked a ``save()`` — mismo patrón que
        ``validate_hard_lock_date_change`` (``account/models/
        res_company.py``): quien escribe estos dos campos lo llama antes de
        persistir.

        El 29 de febrero se acepta siempre, verbatim del comentario de la
        fuente: *"if the user explicitly chooses the 29th of February we
        allow it: there is no 'fiscalyear_last_year' so we do not know his
        intentions."*

        DIVERGENCIA DE MECANISMO — ``account_opening_date`` (el año de
        referencia de la fuente) no está portado en este árbol (Bloque 1,
        tarea #137); se resuelve con ``getattr`` y cae al año en curso
        cuando no existe, que es lo que la fuente hace cuando tampoco hay
        fecha de apertura (``:337-338``, ``else: year = datetime.now()
        .year``).
        """
        if self.fiscalyear_last_day == 29 and self.fiscalyear_last_month == '2':
            return
        opening_date = getattr(self, 'account_opening_date', None)
        year = opening_date.year if opening_date else date.today().year
        max_day = calendar.monthrange(year, int(self.fiscalyear_last_month))[1]
        if self.fiscalyear_last_day <= 0 or self.fiscalyear_last_day > max_day:
            raise ValidationError(_('Invalid fiscal year last day'))

    def save(self, *args, **kwargs):
        """Mantiene la ruta materializada, que allá mantiene el ORM."""
        super().save(*args, **kwargs)
        path = self._compute_parent_path()
        if path != self.parent_path:
            self.parent_path = path
            super().save(update_fields=['parent_path'])

    @ormcache('self.id', cache='stable')
    def _get_zeep_cache__(self):
        """El bucket que ``tools.zeep`` usa para XSD y WSDL.

        ≙ ``_get_zeep_cache__`` (``odoo19c: res_company.py:511-514``).

        Devuelve un ``dict`` vacío la primera vez y **el mismo** en las
        siguientes: la caché ``stable`` guarda el objeto, no una copia, así
        que ``ZeepOrmCache.add`` escribe en él y ``get`` lo relee. Por eso el
        método es de instancia y su clave lleva ``self.id`` — el bucket es por
        compañía, no del proceso.

        El guion bajo doble del sufijo es el de la fuente y se conserva: marca
        que el método existe para el mecanismo, no para llamarse desde una
        vista.
        """
        return {}

    def _get_zeep_client__(self, url, *args, **kwargs):
        """Un ``Client`` de ``tools.zeep`` que cachea sus XSD y WSDL aquí.

        ≙ ``_get_zeep_client__`` (``odoo19c: res_company.py:515-521``).

        El transporte se toma de ``kwargs`` si viene, y sólo se le pone la
        caché **si no trae una**: quien pase su propio transporte con caché
        decide, y este método no se la pisa.

        El ``ensure_one()`` de la fuente no se porta: aquí ``self`` es **una**
        fila, no un conjunto de registros — la misma divergencia de mecanismo
        ya declarada en ``res_partner.py:2423``.
        """
        transport = kwargs.setdefault('transport', zeep.Transport())
        if not transport.cache:
            transport.cache = ZeepOrmCache(self)
        return zeep.Client(url, *args, **kwargs)


class ResCompanyUsersRel(models.Model):
    """Tabla de relación ``res_company_users_rel`` — usuario ↔ compañía aceptada.

    La referencia la declara desde ambos lados con sus nombres de columna
    explícitos (``odoo-tools@622ddc2a``):

    - ``odoo19c: odoo/addons/base/models/res_company.py:68`` —
      ``user_ids = fields.Many2many('res.users', 'res_company_users_rel', 'cid', 'user_id')``
    - ``odoo19c: odoo/addons/base/models/res_users.py:247`` —
      ``company_ids = fields.Many2many('res.company', 'res_company_users_rel', 'user_id', 'cid')``

    (mismos nombres en ``odoo18c:``, líneas ``:54`` y ``:403``.)

    Django nombraría las columnas ``rescompany_id``/``resusers_id`` al
    autogenerar la tabla; el ``through`` explícito existe **sólo** para fijar
    ``cid``/``user_id`` como en la referencia. No añade campos propios, así
    que ``.add()``/``.remove()`` siguen funcionando sin ``through_defaults``.
    """

    cid = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, db_column='cid',
        related_name='+', verbose_name='Compañía',
    )
    user_id = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, db_column='user_id',
        related_name='+', verbose_name='Usuario',
    )

    class Meta:
        db_table            = 'res_company_users_rel'
        constraints         = [
            models.UniqueConstraint(
                fields=['cid', 'user_id'], name='res_company_users_rel_uniq'),
        ]
        verbose_name        = 'Usuario aceptado de la compañía'
        verbose_name_plural = 'Usuarios aceptados de la compañía'

    def __str__(self) -> str:
        return f'{self.cid_id}:{self.user_id_id}'
