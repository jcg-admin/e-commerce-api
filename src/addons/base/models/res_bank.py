"""``res.bank`` — instituciones bancarias (Odoo ``base``).

Adaptación de ``odoo/addons/base/models/res_bank.py`` (Odoo Community, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03). El banco como
institución (con su BIC/SWIFT y dirección), distinto de la cuenta bancaria
(``res.partner.bank``, cuya validación IBAN vive en el addon ``base_iban``).

Cross-app: ``country`` → ``base.ResCountry``; ``state`` → ``base.ResCountryState``.

Ningún ``Char`` de aquí lleva tope
===================================

Los **6** ``fields.Char`` de ``odoo19c: odoo/addons/base/models/res_bank.py``
declarados en ``ResBank`` se escriben sin tamaño, así que la columna es un
``varchar`` sin límite. Los nuestros llevaban topes inventados —``name`` 128,
``bic`` 16, ``street`` 128, ``zip`` 24, ``email`` 254, ``phone`` 32— que la
fuente no impone.

Es el mismo defecto que :ref:`h-api-750` corrigió en ``ir_module.py``, en otro
archivo: el tope no se sube, se **retira**, porque este stack expresa
exactamente lo que la referencia tiene
(``supports_unlimited_charfield = True`` en el backend PostgreSQL de Django 6).

El de ``bic`` era el más peligroso de los seis: un BIC son 8 u 11 caracteres,
así que 16 parece holgado — hasta que alguien guarda uno con separadores o un
identificador local que no es BIC. El tope arbitrario no protege de nada; sólo
espera para truncar.

Los cuatro ``related`` de este archivo, ya declarados (#252)
==========================================================

La referencia declara aquí cuatro proyecciones de un join, ninguna con
``store``: ``ResBank.country_code`` (``odoo19c: res_bank.py:29``),
``ResPartnerBank.bank_name`` (``:97``), ``bank_bic`` (``:98``) y
``country_code`` (``:102``). Las cuatro están declaradas.

Esta sección decía que se omitían, con una razón que la propia referencia
refutaba: *«un ``related`` almacenado es una copia que puede divergir del
original»*. Eso describe ``store=True``, y la fuente los declara **sin store**
— se calculan al leer, no se copian. Medido sobre los 120 addons que este
árbol porta, la inmensa mayoría de los ``related=`` declarados **no lleva
store** — el reparto lo publica ``python3 scripts/census_related_fields.py``,
que no se transcribe aquí porque crece con la referencia. La razón retirada no
aplicaba a ninguno de ellos (:ref:`h-api-974`, :ref:`h-api-977`).

Lo que se perdía al navegar la FK a mano (``cuenta.bank.country.code``) no era
el valor sino la **búsqueda**: la fuente hace buscable un ``related`` cableando
``self.search = self._search_related`` en ``setup_related``
(``odoo19c: fields.py:637``). Con el mecanismo cableado al arranque, filtrar
por ``country_code`` emite el dominio sobre la cadena.

``res.partner.bank`` — la cuenta, en este mismo archivo (#118)
===============================================================

La referencia declara **las dos clases aquí**: ``odoo19c:
odoo/addons/base/models/res_bank.py`` tiene ``ResBank`` (:16) y
``ResPartnerBank`` (:73), y **no existe** ningún ``base/models/res_partner_bank.py``.
Aquí la cuenta vivía en un archivo propio con ese nombre — el defecto de
:ref:`h-api-578`, agravado porque el nombre ya significa otra cosa un addon más
allá: ``account`` y ``hr`` sí declaran ``res_partner_bank.py``, y ahí aloja su
*extensión*, no la clase base.

Lo que bloqueaba el movimiento era la migración
``0021_alter_respartnerbank_acc_type``, que importaba el módulo viejo por su
ruta para resolver ``_supported_account_types``. Se resolvió actualizando esa
referencia al módulo nuevo: en PostgreSQL ``choices`` es validación, no DDL, así
que el estado de la base no cambia — lo verifica
``makemigrations base --check --dry-run``.

Divergencias declaradas (DEC-KX-03)
====================================

1. **``company`` no se porta.** La referencia lo deriva:
   ``company_id = related='partner_id.company_id'`` (odoo19c: res_bank.py:101).
   Nuestro ``ResPartner`` **no tiene esa FK** — verificado: declara
   ``is_company`` (booleano: empresa vs persona) y ``company_name`` (Char), que
   son otra cosa. Fabricar aquí una FK directa a ``ResCompany`` daría un campo
   que puede divergir de la empresa del contacto, que es exactamente el drift
   que la referencia evita derivándolo. Se omite y se declara: **DESCONOCIDO
   con condición de cierre** — entra cuando ``res.partner`` porte su superficie
   multi-empresa. Registrado como la tarea #139.

2. **``acc_type`` se porta como columna, no como ``compute``.** En la
   referencia es un ``Selection`` calculado por ``retrieve_acc_type()``, un
   método pensado para que un addon lo sobreescriba: ``base`` devuelve siempre
   ``'bank'`` y ``base_iban`` lo cambia a ``'iban'`` cuando el número valida
   como IBAN (odoo19c: res_bank.py:135-139). ``base_iban`` es la **Ola 0 · T-06**
   y todavía no está portado, así que el punto de extensión se preserva como
   método de clase ``retrieve_acc_type()`` —sobreescribible igual que en la
   referencia— y el campo se rellena en ``save()``.

3. **``color`` no se porta.** Es ``compute`` sin ``store`` (odoo19c:
   res_bank.py:104): un índice de paleta para el cliente web de Odoo, que este
   producto no tiene.
"""
import fields
import models
from tools.translate import _
from orm.domains import Domain
from orm.models import search_display_name

from addons.base.models.res_country import ResCountry, ResCountryState


def sanitize_account_number(acc_number):
    """Deja sólo alfanuméricos y en mayúsculas — fiel a la referencia.

    ``odoo19c: odoo/addons/base/models/res_bank.py`` la define a nivel de
    módulo y la usa en el ``compute`` de ``sanitized_acc_number`` y en el
    ``search`` de ``acc_number``. Es lo que permite que ``ES91 2100 0418 45``
    y ``es9121000418-45`` se reconozcan como la misma cuenta.
    """
    if not acc_number:
        return ''
    return ''.join(ch for ch in acc_number if ch.isalnum()).upper()


class ResBank(models.Model):
    """``res.bank`` — banco (institución) con su BIC y dirección."""

    _name = 'res.bank'
    _description = 'Bank'
    _order = 'name, id'
    _rec_names_search = ['name', 'bic']

    name         = fields.Char(help_text='Nombre del banco (Odoo name).')
    bic          = fields.Char(
        blank=True, default='', db_index=True,
        help_text='Bank Identifier Code / SWIFT (Odoo bic). A veces se le '
                  'llama BIC o Swift.',
    )
    street       = fields.Char(blank=True, default='', help_text='Odoo street.')
    street2      = fields.Char(blank=True, default='', help_text='Odoo street2.')
    zip          = fields.Char(blank=True, default='', help_text='Odoo zip.')
    city         = fields.Char(blank=True, default='', help_text='Odoo city.')
    state        = fields.Many2one(
        ResCountryState, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='Estado/provincia (Odoo state).',
    )
    country      = fields.Many2one(
        ResCountry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='País (Odoo country).',
    )
    #: ≙ ``country_code`` (``odoo19c: res_bank.py:29``). Sin ``store``, que es
    #: el defecto de la fuente para un ``related`` (``fields.py:455``): no
    #: ocupa columna y se calcula al leer.
    country_code = fields.Char('Country Code', related='country.code')
    email        = fields.Char(blank=True, default='', help_text='Odoo email.')
    phone        = fields.Char(blank=True, default='', help_text='Odoo phone.')
    active       = fields.Boolean(default=True, help_text='Odoo active.')

    class Meta:
        db_table = 'res_bank'
        # Derivado de _order.
        ordering = ['name', 'id']
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``odoo19c: res_bank.py:35-39``).

        El nombre del banco más su BIC, cuando lo tiene. Es lo que consume
        ``__str__``, que aquí es el equivalente del ``display_name`` de la
        fuente.
        """
        return (self.name or '') + (' - ' + self.bic if self.bic else '')

    @classmethod
    def _search_display_name(cls, operator, value):
        """≙ ``_search_display_name`` (``odoo19c: res_bank.py:41-48``).

        Buscar «BBVA» encuentra el banco por nombre; buscar «BBVAMX» lo
        encuentra por BIC. La fuente lo consigue con un dominio en ``|``, y la
        asimetría importa: el BIC se compara **por prefijo**
        (``=ilike value + '%'``) y el nombre **por contenido** (``ilike``).

        Un BIC es un código estructurado que se teclea desde el principio; un
        nombre no. Comparar el BIC por contenido devolvería bancos cuyo código
        contiene la cadena en medio, que no es lo que nadie busca.

        Devuelve un ``Domain``, como la fuente. Los dos operadores que atiende
        son ``ilike`` y ``not ilike``; cualquier otro delega en ``super()``,
        que busca sobre ``_rec_names_search``.
        """
        if operator in ('ilike', 'not ilike') and value:
            domain = (Domain('bic', '=ilike', f'{value}%')
                      | Domain('name', 'ilike', value))
            return ~domain if operator == 'not ilike' else domain
        return search_display_name(cls, operator, value)

    @staticmethod
    def _sanitize_bic(value):
        """El BIC se guarda en mayúsculas, venga como venga.

        La fuente lo hace en ``create`` **y** en ``write``
        (``odoo19c: res_bank.py:50-60``) porque su ORM tiene dos entradas de
        escritura. Aquí las dos son ``save()``, así que la normalización vive
        una vez y ``save()`` la invoca: duplicarla para parecerse a la fuente
        crearía dos copias que pueden divergir.
        """
        return value.upper() if value else value

    def _onchange_country_id(self):
        """≙ ``_onchange_country_id`` (``odoo19c: res_bank.py:62-65``).

        Cambiar el país invalida el estado si ése pertenecía a otro. Sin esto,
        un banco puede quedar con «Jalisco» y país «Francia».
        """
        if self.country_id and self.country_id != (
                self.state.country_id if self.state is not None else None):
            self.state = None

    def _onchange_state(self):
        """≙ ``_onchange_state`` (``odoo19c: res_bank.py:67-70``).

        La dirección contraria: elegir un estado fija su país. La fuente lo
        hace sin condición sobre el país actual —el estado manda— y aquí igual.
        """
        if self.state is not None and self.state.country_id:
            self.country = self.state.country

    def save(self, *args, **kwargs):
        """``create`` y ``write`` de la fuente, que aquí son la misma entrada."""
        self.bic = self._sanitize_bic(self.bic)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self._compute_display_name()


def _supported_account_types():
    """Vocabulario de ``acc_type`` — ≙ el ``selection=lambda`` de la referencia.

    ``odoo19c: res_bank.py:89`` declara el campo como
    ``Selection(selection=lambda x: x.env['res.partner.bank']
    .get_supported_account_types())``. Django acepta un invocable en
    ``choices`` (``django.utils.choices.CallableChoiceIterator``), así que la
    forma se conserva: la lista se resuelve en cada validación, no al importar
    el módulo — que es lo que permite a ``base_iban`` añadir ``iban`` desde su
    ``ready()``, después de que esta clase ya existe.

    Se declara a nivel de módulo porque una referencia a ``ResPartnerBank``
    dentro del cuerpo de la propia clase no resuelve; aquí el nombre se busca
    al invocar, no al definir.
    """
    return ResPartnerBank.get_supported_account_types()


class ResPartnerBank(models.DefaultGetMixin, models.RecordLoaderMixin,
                     models.CheckCompanyMixin, models.Model):
    """``res.partner.bank`` — cuenta bancaria de un contacto."""

    #: Los cuatro atributos de clase que la fuente declara
    #: (``odoo19c: res_bank.py:74-78``). Sin ``_name`` el modelo NO entra en
    #: ``orm.registry.MODELS_BY_NAME``, y entonces el ``_inherits`` que lo
    #: nombra —``account.setup.bank.manual.config``— no resuelve su comodelo y
    #: la delegacion no se cablea: ``ensure_inherits()`` salta al declarante
    #: cuando el comodelo es ``None``. Ese era el segundo eslabon de la tarea
    #: #333, y no fallaba: la delegacion simplemente no existia.
    _name = 'res.partner.bank'
    _rec_name = 'acc_number'
    _description = 'Bank Accounts'
    _order = 'sequence, id'
    #: ≙ ``_check_company_domain = models.check_company_domain_parent_of``
    #: (``:78``): la coherencia de empresa se hereda del padre.
    #: El ``classmethod`` es la forma de ESTE arbol, no un adorno: su
    #: hermano ``CheckCompanyMixin._check_company_domain`` es un
    #: ``@classmethod`` y el consumidor lo invoca sobre la clase. La fuente
    #: asigna la funcion pelada porque alla el consumidor es un recordset,
    #: que es una instancia. Mismo simbolo, misma semantica; lo que cambia
    #: es sobre que se invoca.
    _check_company_domain = classmethod(
        models.check_company_domain_parent_of)

    acc_number = fields.Char(
        max_length=64,
        help_text='Número de cuenta tal como lo escribió el usuario (Odoo '
                  'acc_number, requerido).',
    )
    sanitized_acc_number = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        help_text='``acc_number`` sin separadores y en mayúsculas. Es la '
                  'columna que hace única la cuenta y por la que se busca — '
                  'sin ella, el mismo IBAN escrito con y sin espacios serían '
                  'dos cuentas distintas (Odoo sanitized_acc_number).',
    )
    acc_type = fields.Selection(
        max_length=16, default='bank', choices=_supported_account_types,
        help_text='Tipo inferido del número: ``bank`` en el núcleo, ``iban`` '
                  'cuando base_iban lo valide (Odoo acc_type; ver '
                  'divergencia 2).',
    )
    clearing_number = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Número de compensación, donde el país lo usa (Odoo '
                  'clearing_number).',
    )
    acc_holder_name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Titular de la cuenta, cuando difiere del nombre del '
                  'contacto (Odoo acc_holder_name).',
    )
    partner = fields.Many2one(
        'base.ResPartner', on_delete=models.CASCADE,
        related_name='bank_accounts',
        help_text='Contacto titular de la cuenta (Odoo partner_id, requerido, '
                  'ondelete cascade).',
    )
    bank = fields.Many2one(
        'base.ResBank', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accounts',
        help_text='Institución donde está la cuenta (Odoo bank_id).',
    )
    #: ≙ ``bank_name`` y ``bank_bic`` (``odoo19c: res_bank.py:97-98``), con su
    #: ``readonly=False``: la fuente los deja escribibles a propósito — el
    #: formulario de la cuenta permite corregir el nombre o el BIC del banco
    #: desde ahí, y el inverso lo propaga al banco. Aquí el inverso lo cablea
    #: ``setup_related`` (``fields.py:632``) por la misma condición.
    bank_name = fields.Char('Bank Name', related='bank.name', readonly=False)
    bank_bic = fields.Char('Bank BIC', related='bank.bic', readonly=False)
    #: ≙ ``country_code`` (``odoo19c: res_bank.py:102``). Encadena dos
    #: eslabones: el extremo es el ``country_code`` de ``ResPartner``, que a su
    #: vez es un ``related`` de ``country.code``. Ninguno de los dos ocupa
    #: columna.
    country_code = fields.Char('Country Code', related='partner.country_code')
    currency = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_accounts',
        help_text='Divisa de la cuenta (Odoo currency_id).',
    )
    allow_out_payment = fields.Boolean(
        default=False,
        help_text='La cuenta puede usarse para pagos salientes. Default False '
                  'a propósito, fiel a la referencia: habilitar una cuenta '
                  'para enviar dinero es un acto deliberado (Odoo '
                  'allow_out_payment).',
    )
    sequence = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Cuenta vigente; desactivar la archiva sin borrarla (Odoo '
                  'active).',
    )
    note = fields.Text(
        blank=True, default='', help_text='Notas libres (Odoo note).',
    )

    class Meta:
        db_table = 'res_partner_bank'
        ordering = ['sequence', 'id']
        constraints = [
            # odoo19c: res_bank.py:106-109 — _unique_number. Va sobre el
            # numero SANEADO, no sobre acc_number: es lo que impide registrar
            # dos veces la misma cuenta escrita distinto.
            models.UniqueConstraint(
                fields=['sanitized_acc_number', 'partner'],
                name='unique_partner_bank_account',
            ),
        ]

    @classmethod
    def get_supported_account_types(cls):
        """Vocabulario público de ``acc_type`` — ≙ ``odoo19c: res_bank.py:81``.

        La referencia separa el método público del que los addons
        sobreescriben; se conserva la separación para que un addon extienda
        ``_get_supported_account_types`` sin tocar el punto de consumo.
        """
        return cls._get_supported_account_types()

    @classmethod
    def _get_supported_account_types(cls):
        """Los tipos que el núcleo reconoce — ≙ ``odoo19c: res_bank.py:85``.

        Punto de extensión acumulativo: ``base_iban`` le añade ``iban`` con
        ``chain_method(..., combine=extend_list)``.
        """
        return [('bank', _('Normal'))]

    @classmethod
    def retrieve_acc_type(cls, acc_number):
        """Tipo de cuenta inferido del número.

        Punto de extensión, igual que en la referencia (``odoo19c:
        res_bank.py:135-139``, con su comentario *"To be overridden by
        subclasses in order to support other account_types"*): el núcleo
        devuelve siempre ``bank``, y ``base_iban`` (Ola 0 · T-06) lo cambia a
        ``iban`` cuando el número valida.
        """
        return 'bank'

    def save(self, *args, **kwargs):
        """Deriva las dos columnas que la referencia calcula sobre el número.

        Son ``compute`` con ``store=True`` en la referencia y dependen sólo de
        ``acc_number`` — un campo de la propia fila. Por eso sí se recalculan
        en ``save()``, a diferencia de los ``compute`` que cruzan a otra fila
        (criterio de ``account_reconcile_model.py``, divergencia 4).
        """
        self.sanitized_acc_number = sanitize_account_number(self.acc_number)
        self.acc_type = self.retrieve_acc_type(self.acc_number)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.acc_number or ''
