"""``res.currency`` — moneda ISO 4217 (Odoo ``base``).

Portación fiel de ``res_currency.py`` (Odoo 18:23-47 / 19:21-49, arquitectura
idéntica). Espina base de la adaptación de familias (SOL-096):
account/sale/pricing dependen de moneda.

``round``/``compare_amounts``/``is_zero`` — centralizados aquí (H-API-325,
tarea #115). Fieles a ``odoo19c: res_currency.py:216-261`` con una
divergencia deliberada: la referencia opera sobre ``float`` con
``tools.float_round`` (normaliza dividiendo entre ``rounding``, redondea el
entero más cercano compensando el error de representación IEEE-754 con un
épsilon, y desnormaliza). Este proyecto usa ``Decimal`` para dinero — nunca
``float`` (ver ``account/models/account_tax.py::_d``) — y ``Decimal`` es
exacto en base 10, así que el épsilon de compensación no tiene nada que
corregir: el algoritmo se reduce a dividir entre ``rounding``, redondear el
cociente al entero con ``ROUND_HALF_UP`` (empate se aleja de 0, misma
semántica que el HALF-UP por defecto de la referencia) y multiplicar de
vuelta. Es el mismo algoritmo que ``AccountCashRounding.round()``
(``account/models/account_cash_rounding.py``) ya usa para su propio
``rounding``/``rounding_method`` — aquí se le añade la normalización de
escala a ``decimal_places`` (la división Decimal no preserva por sí sola el
número de decimales visibles, aunque el valor numérico ya sea exacto).

El motor de tipos de cambio SÍ está portado (corregido en este pase)
=================================================================

Esta sección declaraba **ocho** símbolos del motor multi-divisa —``rate``,
``inverse_rate``, ``rate_string``, ``rate_ids``, ``_compute_current_rate``,
``_get_rates``, ``_get_conversion_rate``, ``_convert``— como no portados «sin
consumidor: este núcleo aún no tiene una segunda divisa activa».

**La premisa era cierta y dejó de serlo.** ``res.currency.rate`` se portó
entero en ``api@43f91c31`` (:ref:`h-api-851`): sus diez métodos existen, con la
restricción ``rate > 0`` y la unicidad por día. El consumidor que faltaba es
exactamente esa clase, y ahora está.

Por eso el motor se porta aquí, no se difiere: ``principio-rector-rup-arquitectura.md``
Cláusula 2 — estado heredado que el análisis actual muestra incorrecto se
corrige en el mismo pase, no se respeta por ser previo. «Sin consumidor»
tampoco era uno de los tres desenlaces válidos de
``porte-completo-no-parcial.md``; era un cuarto, inventado.

Lo que hubo que construir, y por qué no estaba bloqueado
=========================================================

``format`` es una línea que delega en ``tools.format_amount``, que delega en
``ResLang.format``. Ninguno de los dos existía, y la primera redacción de este
docstring los declaró **bloqueo con sucesor**. Medido, no lo eran: los tres
eslabones se construyeron en este mismo pase, y ninguno pasa de cuarenta
líneas.

===========================  ==========================================
Símbolo construido           Dónde, y sobre qué mecanismo
===========================  ==========================================
``split`` / ``intersperse``  ``res_lang.py`` — el hogar de la fuente
``ResLang.format``           ``res_lang.py`` — sobre esos dos
``tools.get_lang``           ``tools/misc.py``, con
                             ``django.utils.translation``
``tools.format_amount``      ``tools/misc.py``, sobre ``ResLang.format``
``tools.parse_date``         ``tools/misc.py``, sobre
                             ``django.utils.formats``
===========================  ==========================================

**El agrupamiento no es un ``f'{x:,.2f}'``**, y por eso se porta el algoritmo
de la fuente en vez de resolverlo con la biblioteca estándar: el separador de
miles no siempre reparte de tres en tres. ``[3, 2, 0]`` es el sistema indio y
da ``12,34,567``. Verificado contra los ejemplos de la fuente, los cinco casos
coinciden.

``num2words``, que ``amount_to_text`` necesita para escribir el importe en
palabras, **no está instalado** — y no se añade: la fuente lo declara opcional
y degrada con un aviso, así que portar esa degradación **es** el porte fiel.
El método existe, avisa y devuelve ``''``; el día que la biblioteca esté, el
mismo código escribe el importe sin tocarse.

``_get_view`` / ``_get_view_cache_key`` — mismo criterio que en
``res_currency_rate.py``: lo que **hacen** es calcular etiquetas desde la
moneda de la empresa y hacer que la representación cacheada varíe con ella. Lo
que diverge es el destino —el mapa lo consume el serializer, no un xpath sobre
un árbol XML—, y eso se declara en cada método.

``create`` / ``unlink`` / ``write`` se portan con su nombre. Su conducta
—disparar el toggle del grupo multi-divisa e invalidar el caché de
``get_all_currencies``— vive además en ``save()`` y ``delete()``, para que una
escritura directa tampoco la esquive.
La restricción ``rounding>0`` **SÍ está portada** (corregido en este pase)
=========================================================================

Esta sección la declaraba DESCONOCIDO con esta razón: *«requiere una migración
de CheckConstraint»*, y su condición de cierre era *«cuando exista un endpoint
de escritura de ``rounding`` que lo amerite»*.

Las dos partes estaban mal. Una migración es el **costo** de portar una
restricción, no un impedimento — ``porte-completo-no-parcial.md`` lo llama por
su nombre: *«este ORM no tiene ese constructor» describe el punto de partida,
no cierra nada*. Y esperar a que exista un escritor invierte el orden: una
restricción de tabla existe para que el escritor **no pueda** dejar la fila
inconsistente; llegar después del escritor es llegar tarde.

``_rounding_gt_zero`` es además un **objeto de tabla** de la referencia, no un
método: su hogar aquí es ``Meta.constraints``, con el nombre conservado
(``atributos-de-clase-de-modelo.md``). Vive ahí desde este pase. La guarda de
división por cero de ``round()``/``is_zero()`` sigue donde estaba: cubre el
método, y la restricción cubre la fila — son dos capas, no una alternativa.


``res.currency.rate`` — el historial de tipos de cambio
=========================================================

Vive en este archivo porque la referencia lo declara aquí: ``odoo19c: odoo/addons/base/models/res_currency.py:346`` es la misma
clase en el mismo módulo. Estuvo en un ``res_currency_rate.py`` propio y eso era el defecto de :ref:`h-api-578` —un archivo en una raíz
espejada que la fuente no tiene—; ``check_porte_completo`` lo reportaba como CLASE FUERA DE SITIO. Cerrado en la tarea **#119**.

El bloqueo que aquel archivo declaraba para no moverse —*«arrastra migraciones que importan el módulo por ruta»*— **era falso**: medido,
ninguna migración de ``src/addons/base/migrations/`` importa
``addons.base.models.res_currency_rate``. El caso hermano de
``ResPartnerBank`` (**#118**) sí lo tiene, y por eso ése sigue aparte.

Adaptación de ``odoo/addons/base/models/res_currency.py`` (clase
``ResCurrencyRate``, Odoo Community, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03). Una fila = el tipo de cambio de una moneda en una
fecha para una empresa.
"""
import datetime
import logging
import math
from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import F

import fields
import api
import models
from orm.environments import get_context, get_current_company
from orm.utils import COLLECTION_TYPES
from orm.domains import Domain
from tools.misc import format_amount, get_lang
from datetime import date
from decimal import Decimal, InvalidOperation
from orm.environments import get_current_company
from tools.misc import parse_date

_logger = logging.getLogger(__name__)

try:
    from num2words import num2words
except ImportError:
    # ≙ el mismo try/except del módulo de la fuente
    # (``odoo19c: res_currency.py:13-17``). La biblioteca es opcional allá y
    # aquí no está instalada; ``amount_to_text`` degrada con aviso, que es
    # exactamente lo que la fuente hace.
    _logger.warning(
        'La biblioteca num2words no está instalada; el importe en palabras '
        'no estará disponible.')
    num2words = None


class ResCurrency(models.DefaultGetMixin, models.RecordLoaderMixin,
                  models.CheckCompanyMixin, models.Model):
    """``res.currency`` — moneda ISO 4217 (Odoo base).

    Fiel a ``res_currency.py`` (18:23-47 / 19:21-49): ``name`` (código ISO 4217,
    3 letras), ``full_name``, ``symbol``, ``rounding`` (factor), ``decimal_places``
    (compute = ``ceil(log10(1/rounding))``, o18:41 / o19:39), ``position``
    (before/after), ``active``, ``currency_unit_label``. Más ``round``/
    ``compare_amounts``/``is_zero`` (o19:216-261, ver docstring del módulo).
    """

    POSITION_AFTER  = 'after'
    POSITION_BEFORE = 'before'
    POSITION_CHOICES = [
        (POSITION_AFTER, 'Después del importe'),
        (POSITION_BEFORE, 'Antes del importe'),
    ]

    _name = 'res.currency'
    _description = "Currency"
    _rec_names_search = ['name', 'full_name']
    _order = 'active desc, name'

    name                = fields.Char(
        max_length=3, unique=True,
        help_text='Código de moneda ISO 4217 (Odoo res.currency.name).',
    )
    full_name           = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Nombre de la moneda (Odoo full_name).',
    )
    symbol              = fields.Char(
        max_length=8,
        help_text='Signo de la moneda (Odoo symbol).',
    )
    rounding            = fields.Monetary(
        max_digits=12, decimal_places=6, default=Decimal('0.01'),
        help_text='Factor de redondeo (Odoo rounding).',
    )
    decimal_places      = fields.Integer(
        default=2,
        help_text='Decimales, computado de rounding (Odoo decimal_places).',
    )
    position            = fields.Selection(
        max_length=6, choices=POSITION_CHOICES, default=POSITION_AFTER,
        help_text='Posición del símbolo (Odoo position).',
    )
    active              = fields.Boolean(
        default=True, help_text='Moneda activa (Odoo active).',
    )
    currency_unit_label = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Etiqueta de la unidad (Odoo currency_unit_label).',
    )
    currency_subunit_label = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Etiqueta de la subunidad (Odoo currency_subunit_label). '
                  'La consume amount_to_text para la parte fraccionaria.',
    )
    iso_numeric         = fields.Integer(
        null=True, blank=True,
        help_text='Código numérico ISO 4217 (Odoo iso_numeric).',
    )

    class Meta:
        db_table = 'res_currency'
        # Derivado de ``_order``: ``active desc, name``. El orden importa y no
        # es cosmético — una divisa archivada no debe encabezar un selector por
        # tener un nombre que empieza por A. El nuestro decía sólo ``['name']``.
        ordering = ['-active', 'name']
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'
        constraints = [
            # ≙ ``_rounding_gt_zero`` (``odoo19c: res_currency.py:52-55``), un
            # objeto de tabla de la referencia. Su hogar aquí es
            # ``Meta.constraints`` con el nombre conservado
            # (``atributos-de-clase-de-modelo.md``).
            #
            # El docstring del módulo lo declaraba DESCONOCIDO porque «requiere
            # una migración de CheckConstraint». Eso es un **costo**, no un
            # bloqueo: la guarda de división por cero de ``round()`` corta antes
            # de dividir, pero no impide que una escritura deje la fila con
            # ``rounding <= 0``, que es justo lo que la restricción existe para
            # impedir.
            models.CheckConstraint(
                condition=models.Q(rounding__gt=0),
                name='res_currency_rounding_gt_zero',
                violation_error_message='El factor de redondeo debe ser mayor que 0.',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # === Puntos de entrada del ORM ========================================

    def save(self, *args, **kwargs):
        """El punto único de escritura: computa, valida y propaga.

        ``create`` y ``write`` de la referencia son los nombres públicos y
        pasan por aquí; la conducta vive en este sitio para que una escritura
        directa —``objects.create``, ``instance.save()``— tampoco la esquive.
        """
        self._compute_decimal_places()
        self._check_company_currency_stays_active()
        res = super().save(*args, **kwargs)
        type(self)._toggle_group_multi_currency()
        type(self)._invalidate_all_currencies_cache()
        return res

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: res_currency.py:65-70``)."""
        res = super().delete(*args, **kwargs)
        type(self)._toggle_group_multi_currency()
        type(self)._invalidate_all_currencies_cache()
        return res

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: res_currency.py:65-70``).

        El nombre público del borrado en la referencia. Aquí delega en
        ``delete()``, que es donde Django engancha — y donde vive la conducta,
        para que un borrado directo tampoco se salte el toggle ni la
        invalidación del caché.
        """
        return self.delete()

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: res_currency.py:57-63``).

        Su cuerpo llama a ``super().create``, dispara el toggle del grupo
        multi-divisa e invalida el caché de ``get_all_currencies``. Las dos
        últimas ocurren por la vía de ``save()``, que la fila recorre.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        return super().create(vals_list)

    def write(self, vals):
        """≙ ``write`` (``odoo19c: res_currency.py:72-81``).

        La fuente invalida el caché sólo cuando el cambio toca uno de los cinco
        campos que ``get_all_currencies`` publica, y dispara el toggle sólo
        cuando toca ``active``. Aquí ``save()`` hace las dos incondicionalmente
        — es más caro y no puede quedarse corto, que en un caché es el error
        que importa.
        """
        for field, value in vals.items():
            setattr(self, field, value)
        self.save()
        return True

    # === Derivados =========================================================

    def _compute_decimal_places(self):
        """≙ ``_compute_decimal_places`` (``odoo19c: res_currency.py:162-168``).

        ``ceil(log10(1/rounding))`` cuando ``0 < rounding < 1``; 0 si no. Es lo
        que hace que un ``rounding`` de ``0.01`` publique dos decimales y uno
        de ``0.05`` también dos — el número de decimales no es el del factor,
        es el de su magnitud.
        """
        r = float(self.rounding or 0)
        if 0 < r <= 1:
            self.decimal_places = int(math.ceil(math.log10(1 / r)))
        else:
            self.decimal_places = 0
        return self.decimal_places

    @property
    def rate_ids(self):
        """Las tasas de esta moneda — el ``rate_ids`` One2many de la fuente.

        Sale ordenado por el ``_order`` de ``res.currency.rate``
        (``name desc, id``), así que ``rate_ids[:1]`` es la **más reciente**,
        que es lo que ``_compute_date`` asume.
        """
        return self.rates.all()

    def _compute_date(self):
        """≙ ``_compute_date`` (``odoo19c: res_currency.py:170-173``).

        La fecha de la última tasa, o ``None``. La consume la property
        ``date``.
        """
        latest = self.rate_ids.first()
        return latest.name if latest is not None else None

    @property
    def date(self):
        """La fecha de la última tasa — ≙ ``_compute_date``."""
        return self._compute_date()

    def _compute_is_current_company_currency(self):
        """≙ ``_compute_is_current_company_currency`` (``odoo19c: :142-145``).

        La consume la property ``is_current_company_currency``.
        """
        company_id = get_current_company()
        if company_id is None:
            return False
        company = self.companies.model.objects.filter(pk=company_id).first()
        return company is not None and company.currency_id == self.pk

    @property
    def is_current_company_currency(self):
        """≙ ``_compute_is_current_company_currency``."""
        return self._compute_is_current_company_currency()

    # === Motor de tipos de cambio =========================================

    @classmethod
    def _get_rates(cls, currencies, company, date):
        """≙ ``_get_rates`` (``odoo19c: res_currency.py:117-138``).

        ``{currency_id: tasa}`` a la fecha dada, con el mismo triple respaldo
        de la fuente, en su orden: la última tasa **anterior o igual** a
        ``date``; si no hay, la **más antigua** que exista; si tampoco,
        ``1.0``.

        El segundo escalón parece raro y no lo es: una moneda cuya primera tasa
        es posterior a la fecha pedida se convierte con esa primera en vez de
        tratarse como si valiera uno. Sin él, un asiento retroactivo saldría
        sin convertir.

        El orden por empresa es ``company_id`` ascendente con los nulos al
        final, que en PostgreSQL es el default del ``ASC``: la tasa **propia de
        la empresa gana** a la global, y sólo si no hay propia entra la global.

        Las tasas viven siempre en la empresa raíz (``_check_company_id`` de
        ``res.currency.rate``), así que se resuelve contra ``root_id``.
        """
        currencies = list(currencies)
        if not currencies:
            return {}
        rate_model = cls.rates.rel.related_model
        root = company.root_id if company is not None else None
        company_filter = models.Q(company__isnull=True)
        if root is not None:
            company_filter = company_filter | models.Q(company=root)

        rates = {}
        for currency in currencies:
            base = rate_model.objects.filter(company_filter, currency=currency,
                                             rate__gt=0)
            found = base.filter(name__lte=date).order_by(
                F('company_id').asc(nulls_last=True), '-name').first()
            if found is None:
                found = base.order_by(
                    F('company_id').asc(nulls_last=True), 'name').first()
            rates[currency.pk] = (found.rate if found is not None
                                  else Decimal('1.0'))
        return rates

    def _compute_current_rate(self, to_currency=None, company=None, date=None):
        """≙ ``_compute_current_rate`` (``odoo19c: res_currency.py:145-159``).

        Devuelve ``(rate, inverse_rate, rate_string)`` — los tres derivados que
        la fuente asigna de una vez, porque los tres salen de la misma
        consulta y separarlos la repetiría tres veces.

        ``rate_string`` es ``''`` cuando la moneda **es** la de la empresa: no
        hay nada que rotular en «1 MXN = 1.000000 MXN».

        **Asimetría de la fuente, portada verbatim:** resuelve ``company``
        desde el contexto y luego pide las tasas con ``self.env.company``, no
        con esa. Se porta igual — el parámetro ``company`` gobierna la moneda
        de destino y el rótulo; las tasas salen de la empresa en contexto.
        """
        date = date or datetime.date.today()
        company_id = get_current_company()
        env_company = (self.companies.model.objects.filter(pk=company_id).first()
                       if company_id is not None else None)
        company = company or env_company
        to_currency = to_currency or (company.currency if company is not None
                                      else self)

        rates = type(self)._get_rates([self, to_currency], env_company, date)
        divisor = rates.get(to_currency.pk) or Decimal('1.0')
        rate = (rates.get(self.pk) or Decimal('1.0')) / divisor
        inverse_rate = Decimal('1.0') / rate if rate else Decimal('1.0')

        if company is not None and self.pk == company.currency_id:
            rate_string = ''
        else:
            rate_string = f'1 {to_currency.name} = {rate:.6f} {self.name}'
        return rate, inverse_rate, rate_string

    @property
    def rate(self):
        """La tasa actual — ≙ ``_compute_current_rate``."""
        return self._compute_current_rate()[0]

    @property
    def inverse_rate(self):
        """El recíproco de la tasa actual — ≙ ``_compute_current_rate``."""
        return self._compute_current_rate()[1]

    @property
    def rate_string(self):
        """El rótulo «1 X = n Y» — ≙ ``_compute_current_rate``."""
        return self._compute_current_rate()[2]

    @classmethod
    def _get_conversion_rate(cls, from_currency, to_currency, company=None,
                             date=None):
        """≙ ``_get_conversion_rate`` (``odoo19c: res_currency.py:271-281``).

        El factor por el que hay que multiplicar un importe en
        ``from_currency`` para expresarlo en ``to_currency``. **1 exacto**
        cuando son la misma — la fuente corta antes de consultar, y no es una
        optimización: evita que un redondeo de ida y vuelta mueva un importe
        que no debía moverse.
        """
        if from_currency.pk == to_currency.pk:
            return Decimal('1')
        date = date or datetime.date.today()
        root = company.root_id if company is not None else None
        rates = cls._get_rates([from_currency, to_currency], root, date)
        origin = rates.get(from_currency.pk) or Decimal('1.0')
        return (rates.get(to_currency.pk) or Decimal('1.0')) / origin

    def _convert(self, from_amount, to_currency, company=None, date=None,
                 round=True):
        """≙ ``_convert`` (``odoo19c: res_currency.py:283-302``).

        Convierte ``from_amount`` de esta moneda a ``to_currency``.

        La fuente devuelve ``0.0`` cuando el importe es falso **sin consultar
        tasa alguna**, y redondea con la moneda **de destino**, no con la de
        origen: los decimales que valen son los de la moneda en que queda
        expresado el importe.
        """
        if not from_amount:
            return Decimal('0')
        amount = Decimal(str(from_amount)) * type(self)._get_conversion_rate(
            self, to_currency, company, date)
        return to_currency.round(amount) if round else amount

    @classmethod
    def _select_companies_rates(cls):
        """≙ ``_select_companies_rates`` (``odoo19c: res_currency.py:304-319``).

        El SQL que da, por moneda y empresa, la ventana de vigencia de cada
        tasa: ``date_start`` es su propia fecha y ``date_end`` la de la
        siguiente. Lo consumen los informes que necesitan convertir **cada
        línea a la tasa que regía ese día**, no a la de hoy.

        Se porta verbatim: los nombres de tabla y columna coinciden
        (``res_currency_rate``, ``res_company``, ``currency_id``,
        ``company_id``), así que no hay nada que traducir.
        """
        return """
            SELECT
                r.currency_id,
                COALESCE(r.company_id, c.id) as company_id,
                r.rate,
                r.name AS date_start,
                (SELECT name FROM res_currency_rate r2
                 WHERE r2.name > r.name AND
                       r2.currency_id = r.currency_id AND
                       (r2.company_id is null or r2.company_id = c.id)
                 ORDER BY r2.name ASC
                 LIMIT 1) AS date_end
            FROM res_currency_rate r
            JOIN res_company c ON (r.company_id is null or r.company_id = c.id)
        """

    # === Grupo multi-divisa ================================================

    @classmethod
    def _toggle_group_multi_currency(cls):
        """≙ ``_toggle_group_multi_currency`` (``odoo19c: :83-92``).

        La pertenencia al grupo multi-divisa **se deriva del conteo** de
        monedas activas: más de una lo activa, una o ninguna lo desactiva.
        Nadie la escribe a mano, que es lo que la mantiene cierta.

        Mismo mecanismo que ``UsersMultiCompany`` para el grupo multi-empresa
        (``res_users.py``), y por la misma razón: un permiso que describe un
        hecho del sistema no se administra, se calcula.
        """
        if cls.objects.filter(active=True).count() > 1:
            cls._activate_group_multi_currency()
        else:
            cls._deactivate_group_multi_currency()

    @classmethod
    def _group_pair(cls):
        """``(group_user, group_multi_currency)`` o ``(None, None)``.

        Sin contraparte de nombre: la fuente escribe los dos ``env.ref`` en
        línea, idénticos, en los dos métodos de abajo.
        """
        ir_model_data = models.apps.get_model('base', 'IrModelData')
        res_groups = models.apps.get_model('base', 'ResGroups')
        user_id = ir_model_data._xmlid_to_res_id('base.group_user')
        multi_id = ir_model_data._xmlid_to_res_id('base.group_multi_currency')
        if not user_id or not multi_id:
            # ≙ el ``if group_user and group_mc:`` de la fuente — mientras la
            # siembra no haya dejado los xmlid, la pregunta no tiene sentido.
            return None, None
        return (res_groups.objects.filter(pk=user_id).first(),
                res_groups.objects.filter(pk=multi_id).first())

    @classmethod
    def _activate_group_multi_currency(cls):
        """≙ ``_activate_group_multi_currency`` (``odoo19c: :93-98``)."""
        group_user, group_mc = cls._group_pair()
        if group_user is not None and group_mc is not None:
            group_user.apply_group(group_mc)

    @classmethod
    def _deactivate_group_multi_currency(cls):
        """≙ ``_deactivate_group_multi_currency`` (``odoo19c: :99-104``)."""
        group_user, group_mc = cls._group_pair()
        if group_user is not None and group_mc is not None:
            group_user.remove_group(group_mc)

    def _check_company_currency_stays_active(self):
        """≙ ``_check_company_currency_stays_active`` (``odoo19c: :105-115``).

        Una moneda asignada a una empresa no se archiva. Sin la guarda, la
        empresa queda apuntando a una moneda inactiva y todo importe suyo pasa
        a convertirse contra una tasa que ya nadie mantiene.

        Las dos exenciones de la fuente se portan con sus nombres:
        ``install_mode`` —durante la instalación el ``active`` aún no refleja
        la asignación— y ``force_deactivate``, que existe para que un test
        pueda ejercitar el camino mono-divisa.
        """
        context = get_context()
        if context.get('install_mode') or context.get('force_deactivate'):
            return
        if self.active or self.pk is None:
            return
        if self.companies.exists():
            raise ValidationError(
                'Esta moneda está asignada a una empresa, así que no se puede '
                'desactivar.')

    # === Presentación ======================================================

    @classmethod
    def _all_currencies_cache_key(cls):
        """La llave del caché de ``get_all_currencies``.

        Sin contraparte de nombre: allá el ``@ormcache(cache='stable')`` la
        genera el decorador.
        """
        return 'base:res_currency:all_currencies'

    @classmethod
    def _invalidate_all_currencies_cache(cls):
        """≙ el ``self.env.registry.clear_cache('stable')`` de ``create`` /
        ``write`` / ``unlink``."""
        cache.delete(cls._all_currencies_cache_key())

    @classmethod
    def get_all_currencies(cls):
        """≙ ``get_all_currencies`` (``odoo19c: res_currency.py:262-269``).

        Las monedas activas con lo que hace falta para **formatear** un importe
        —nombre, símbolo, posición y decimales— indexadas por id. La fuente la
        memoriza con ``@ormcache(cache='stable')``; aquí con
        ``django.core.cache``, y la invalidan los tres puntos de escritura.

        El ``69`` del par ``digits`` es la precisión total que la fuente
        publica junto a los decimales; se porta verbatim porque es parte del
        contrato que el cliente lee.
        """
        key = cls._all_currencies_cache_key()
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = {
            currency.pk: {
                'name': currency.name,
                'symbol': currency.symbol,
                'position': currency.position,
                'digits': [69, currency.decimal_places],
            }
            for currency in cls.objects.filter(active=True)
        }
        cache.set(key, result)
        return result

    def format(self, amount):
        """≙ ``format`` (``odoo19c: res_currency.py:212-221``).

        El importe con su símbolo, redondeado y agrupado según la
        localización. Una línea, como en la fuente: el trabajo vive en
        ``tools.format_amount``.

        El ``amount + 0.0`` de la fuente existe para quitar el signo de un
        ``-0.0``; con ``Decimal`` eso lo resuelve ya ``round()``, que devuelve
        ``Decimal('0')`` sin signo.
        """
        return format_amount(amount, self)

    def amount_to_text(self, amount):
        """≙ ``amount_to_text`` (``odoo19c: res_currency.py:175-210``).

        El importe **en palabras**, que es lo que un cheque o una factura
        impresa exige por ley en varias jurisdicciones.

        ``num2words`` es opcional en la fuente y no está instalada aquí, así
        que este método degrada con aviso y devuelve ``''`` — que es
        literalmente lo que la fuente hace en la misma condición. El resto del
        cuerpo se porta: partir el importe en entero y fracción con los
        decimales de la moneda, y unir cada parte con su etiqueta.
        """
        if num2words is None:
            _logger.warning(
                "Falta la biblioteca 'num2words'; no se puede escribir el "
                "importe en palabras.")
            return ''

        lang = get_lang()
        iso_code = getattr(lang, 'iso_code', None) or 'en'

        def _num2words(number):
            try:
                return num2words(number, lang=iso_code).title()
            except NotImplementedError:
                return num2words(number, lang='en').title()

        integral, _sep, fractional = (
            f'{amount:.{self.decimal_places}f}'.partition('.'))
        integer_value = int(integral)
        if self.is_zero(Decimal(str(amount)) - integer_value):
            return f'{_num2words(integer_value)} {self.currency_unit_label}'
        return (f'{_num2words(integer_value)} {self.currency_unit_label} y '
                f'{_num2words(int(fractional or 0))} '
                f'{self.currency_subunit_label}')

    @classmethod
    def _company_currency_name(cls, company=None):
        """El nombre de la moneda de la empresa — el insumo de las dos de abajo.

        Sin contraparte de nombre: la fuente lo escribe en línea, dos veces.
        """
        if company is None:
            company_id = get_current_company()
            if company_id is None:
                return ''
            company = cls.companies.rel.related_model.objects.filter(
                pk=company_id).first()
        if company is None or company.currency_id is None:
            return ''
        return company.currency.name

    @classmethod
    def _get_view_cache_key(cls, view_type='form', company=None, **options):
        """≙ ``_get_view_cache_key`` (``odoo19c: res_currency.py:321-326``).

        La conducta que se porta: **la representación cacheada varía con la
        moneda de la empresa**. Si no varía, dos empresas con monedas
        distintas comparten unas etiquetas que contradicen a una de las dos.

        Lo que diverge es el destino —allá una vista XML, aquí la
        representación del serializer— y por eso el método devuelve la llave y
        no toca ningún caché: quien cachea decide dónde.
        """
        return (cls._name, view_type, tuple(sorted(options.items())),
                cls._company_currency_name(company))

    @classmethod
    def _get_view(cls, view_type='form', company=None, **options):
        """≙ ``_get_view`` (``odoo19c: res_currency.py:328-343``).

        Las etiquetas de los cuatro campos de tasa según la moneda de la
        empresa. Los cuatro, no dos: la fuente empareja ``company_rate`` con
        ``rate`` bajo un rótulo, e ``inverse_company_rate`` con
        ``inverse_rate`` bajo el otro.

        A diferencia de ``res.currency.rate``, aquí la fuente lo aplica a
        ``list`` **y** a ``form``.
        """
        if view_type not in ('list', 'form'):
            return {}
        currency_name = cls._company_currency_name(company)
        if not currency_name:
            return {}
        return {
            'company_rate': f'Unidades por {currency_name}',
            'rate': f'Unidades por {currency_name}',
            'inverse_company_rate': f'{currency_name} por unidad',
            'inverse_rate': f'{currency_name} por unidad',
        }

    def round(self, amount):
        """Redondea ``amount`` al múltiplo de ``self.rounding`` más cercano
        (Odoo ``round``, o18:216-223 / o19:216-223).

        Divergencia deliberada con ``float``: ver docstring del módulo. El
        algoritmo se reduce a dividir entre ``rounding``, redondear el
        cociente al entero con ``ROUND_HALF_UP`` (empate se aleja de 0) y
        multiplicar de vuelta — luego se normaliza la escala del resultado a
        ``decimal_places``, porque la división ``Decimal`` no la preserva
        por sí sola (p. ej. ``300`` en vez de ``300.00``, aunque el valor
        numérico ya sea exacto).

        :param amount: importe a redondear (``Decimal`` o convertible).
        :return: ``Decimal`` redondeado a la precisión de ``self.rounding``.
        """
        amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        if amount == 0 or not self.rounding:
            return Decimal('0')
        rounding = Decimal(str(self.rounding))
        quantized = (amount / rounding).to_integral_value(rounding=ROUND_HALF_UP) * rounding
        quantum = Decimal('1').scaleb(-self.decimal_places)
        return quantized.quantize(quantum)

    def compare_amounts(self, amount1, amount2):
        """Compara ``amount1`` y ``amount2`` ya redondeados según ``self``
        (Odoo ``compare_amounts``, o18:225-246 / o19:225-246).

        Redondea AMBOS montos antes de comparar — no la diferencia entre
        ellos (ver la advertencia en ``is_zero`` abajo, heredada de la
        referencia: no son equivalentes). Con ``Decimal``, ``round()``
        devuelve siempre un múltiplo exacto de ``rounding``, así que
        comparar por igualdad tras redondear basta; la referencia necesita
        además ``float_is_zero(delta)`` porque la desnormalización en
        ``float`` puede introducir un error de representación incluso
        después de "redondear" — ``Decimal`` no lo tiene.

        :param amount1: primer importe a comparar.
        :param amount2: segundo importe a comparar.
        :return: ``-1``, ``0`` o ``1`` según ``amount1`` sea menor, igual o
            mayor que ``amount2``, a la precisión de ``self.rounding``.
        """
        a1 = self.round(amount1)
        a2 = self.round(amount2)
        if a1 == a2:
            return 0
        return -1 if a1 < a2 else 1

    def is_zero(self, amount):
        """``True`` si ``amount`` redondea a 0 según ``self.rounding`` (Odoo
        ``is_zero``, o18:248-261 / o19:248-261).

        Advertencia heredada de la referencia: ``is_zero(a1 - a2)`` NO
        equivale a ``compare_amounts(a1, a2) == 0`` — éste redondea ANTES
        de restar, aquél redondea la diferencia. Ejemplo (precisión de 2
        decimales): ``0.006`` y ``0.002`` son "iguales" para
        ``is_zero(0.006 - 0.002)`` (``0.004`` redondea a ``0.00``), pero
        distintos para ``compare_amounts(0.006, 0.002)`` (``0.01`` vs
        ``0.00``, redondeados por separado).

        :param amount: importe a comparar contra el cero de esta moneda.
        :return: ``True`` si ``amount`` es lo bastante pequeño para
            tratarse como cero a la precisión de ``self.rounding``.
        """
        return self.round(amount) == 0


class ResCurrencyRate(models.DefaultGetMixin, models.RecordLoaderMixin,
                      models.CheckCompanyMixin, models.Model):
    """``res.currency.rate`` — tipo de cambio de una moneda en una fecha."""

    _name = 'res.currency.rate'
    _description = "Currency Rate"
    _rec_names_search = ['name', 'rate']
    _order = "name desc, id"

    name         = fields.Date(
        db_index=True,
        help_text='Fecha del tipo de cambio (Odoo name, requerido).',
    )
    rate         = fields.Monetary(
        max_digits=24, decimal_places=12, default=Decimal('1.0'),
        help_text='Tasa por unidad de la moneda de tasa 1 (Odoo rate). Es la '
                  'ÚNICA de las tres que se almacena.',
    )
    currency     = fields.Many2one(
        'base.ResCurrency', on_delete=models.CASCADE, related_name='rates',
        db_index=True,
        help_text='Moneda (Odoo currency_id).',
    )
    company      = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='currency_rates',
        null=True, blank=True,
        help_text='Empresa (Odoo company_id). Null = la tasa aplica a todas.',
    )

    class Meta:
        db_table = 'res_currency_rate'
        # Derivado de ``_order``: ``name desc, id``.
        ordering = ['-name', 'id']
        constraints = [
            # ≙ ``_unique_name_per_day`` (``odoo19c: res_currency.py:379-382``).
            models.UniqueConstraint(
                fields=['currency', 'company', 'name'],
                name='unique_currency_rate_per_day',
            ),
            # ≙ ``_currency_rate_check`` (``odoo19c: res_currency.py:383-386``),
            # objeto de tabla de la referencia. Su hogar aquí es
            # ``Meta.constraints`` con el nombre conservado
            # (``atributos-de-clase-de-modelo.md``).
            #
            # Una tasa de 0 no es «sin tasa»: hace que toda conversión que la
            # use dé 0 o reviente al invertirla. La restricción impide la fila,
            # que es lo que ningún método puede impedir.
            models.CheckConstraint(
                condition=models.Q(rate__gt=0),
                name='res_currency_rate_currency_rate_check',
                violation_error_message='El tipo de cambio debe ser estrictamente positivo.',
            ),
        ]
        verbose_name = 'Tipo de cambio'
        verbose_name_plural = 'Tipos de cambio'

    def _get_latest_rate(self):
        """≙ ``_get_latest_rate`` (``odoo19c: res_currency.py:404-412``).

        La última tasa **anterior** a la de esta fila, para la misma moneda y
        empresa. Es lo que da sentido a ``company_rate``: una tasa nueva se
        interpreta contra la que había.

        El ``< self.name`` es estricto en la fuente y aquí igual: la del mismo
        día es **esta**, no la anterior.
        """
        if not self.name:
            raise ValidationError(
                'La fecha de la tasa está vacía. Hay que ponerla.')
        company = self.company or self._current_company()
        return type(self).objects.filter(
            currency=self.currency_id,
            company=company,
            name__lt=self.name,
            rate__gt=0,
        ).order_by('name').last()

    @classmethod
    def _get_last_rates_for_companies(cls, companies):
        """≙ ``_get_last_rates_for_companies`` (``odoo19c: :414-421``).

        La última tasa de la moneda **de cada empresa**, indexada por empresa.
        Cae a 1 cuando no hay ninguna — que es lo correcto: sin tasa, la moneda
        de la empresa vale una unidad de sí misma.

        El filtro de la fuente es ``x.company_id == company or not
        x.company_id``: cuenta también la tasa **sin empresa**, que es la
        global. Se porta entero; quedarse sólo con la de la empresa haría que
        una instalación que sólo declara tasas globales midiera 1 siempre.
        """
        rates = {}
        for company in companies:
            if company is None:
                continue
            latest = cls.objects.filter(
                currency=company.currency_id,
                rate__gt=0,
            ).filter(
                models.Q(company=company) | models.Q(company__isnull=True)
            ).order_by('name').last()
            rates[company.pk] = latest.rate if latest is not None else Decimal('1.0')
        return rates

    def _compute_rate(self):
        """≙ ``_compute_rate`` (``odoo19c: res_currency.py:423-425``).

        El default de la columna cuando nadie la fija: la tasa anterior, o 1.
        """
        if self.rate:
            return self.rate
        latest = self._get_latest_rate()
        return latest.rate if latest is not None else Decimal('1.0')

    def _compute_company_rate(self):
        """≙ ``_compute_company_rate`` (``odoo19c: res_currency.py:427-431``).

        La tasa relativa a la moneda de la empresa: ``rate`` dividido entre la
        última tasa de esa moneda. Con la moneda de la empresa como la de tasa
        1, el divisor es 1 y las dos coinciden — que es el caso de una
        instalación mono-divisa.
        """
        company = self.company or self._current_company()
        divisor = self._divisor_for(company)
        return self._compute_rate() / divisor

    def _inverse_company_rate(self, company_rate):
        """≙ ``_inverse_company_rate`` (``odoo19c: res_currency.py:433-437``).

        El lado de escritura: fijar ``company_rate`` reescribe ``rate``, que es
        la única columna. Devuelve el valor en vez de asignarlo — quien lo llama
        decide si guarda.
        """
        company = self.company or self._current_company()
        return Decimal(company_rate) * self._divisor_for(company)

    def _compute_inverse_company_rate(self):
        """≙ ``_compute_inverse_company_rate`` (``odoo19c: :439-443``).

        El recíproco de ``company_rate``. La fuente cae a 1 cuando la tasa de la
        empresa es falsa, y con eso evita la división por cero; aquí igual.
        """
        company_rate = self._compute_company_rate() or Decimal('1.0')
        return Decimal('1.0') / company_rate

    def _inverse_inverse_company_rate(self, inverse_company_rate):
        """≙ ``_inverse_inverse_company_rate`` (``odoo19c: :445-449``).

        El lado de escritura del recíproco, con la misma caída a 1.
        """
        value = Decimal(inverse_company_rate) or Decimal('1.0')
        return self._inverse_company_rate(Decimal('1.0') / value)

    def _onchange_rate_warning(self):
        """≙ ``_onchange_rate_warning`` (``odoo19c: res_currency.py:451-464``).

        Avisa —no rechaza— cuando la tasa nueva se aleja más de un 20 % de la
        anterior. Es la mitad de ``warning`` del ``onchange`` de la fuente, y
        aquí sí se porta: devuelve el diccionario, y el motor de avisos que le
        falta a ``ir.actions.server`` no hace falta porque el llamador es quien
        decide qué hacer con él.

        ``None`` = no hay nada que avisar.
        """
        latest = self._get_latest_rate()
        if latest is None or not latest.rate:
            return None
        difference = (latest.rate - self.rate) / latest.rate
        if abs(difference) <= Decimal('0.2'):
            return None
        return {
            'warning': {
                'title': f'Aviso para {self.currency.name}',
                'message': (
                    'La tasa nueva está bastante lejos de la anterior.\n'
                    'Un tipo de cambio incorrecto causa problemas críticos; '
                    'conviene verificarla.'
                ),
            },
        }

    def _check_company_id(self):
        """≙ ``_check_company_id`` (``odoo19c: res_currency.py:466-469``).

        Una tasa pertenece a una empresa **matriz**, nunca a una sucursal. La
        razón está en el modelo: una sucursal hereda la moneda de su raíz
        (``get_company_root_delegated_field_names``), así que una tasa colgada
        de ella describiría una moneda que no es suya.
        """
        if self.company is not None and self.company.parent_id:
            raise ValidationError(
                'Los tipos de cambio sólo se crean para empresas matrices.')

    @staticmethod
    def _sanitize_vals(vals):
        """≙ ``_sanitize_vals`` (``odoo19c: res_currency.py:388-393``).

        Cuál de las tres tasas gana cuando llegan varias. El orden de la fuente
        es explícito y se porta verbatim: ``rate`` gana sobre ``company_rate``,
        y ``company_rate`` sobre ``inverse_company_rate``.

        Es lógica de dominio, no del ORM — por eso se porta aunque
        ``create``/``write`` sean un ``save()`` aquí.
        """
        vals = dict(vals)
        if 'inverse_company_rate' in vals and (
                'company_rate' in vals or 'rate' in vals):
            del vals['inverse_company_rate']
        if 'company_rate' in vals and 'rate' in vals:
            del vals['company_rate']
        return vals

    def save(self, *args, **kwargs):
        """El punto único de escritura del ORM: valida antes de tocar la fila.

        ``create`` y ``write`` de abajo son los puntos de entrada de la
        referencia y pasan por aquí; la guarda vive en este sitio para que una
        escritura directa —``objects.create``, ``instance.save()``— tampoco la
        esquive.
        """
        self._check_company_id()
        return super().save(*args, **kwargs)

    @classmethod
    def _rate_from_vals(cls, vals, base=None):
        """El valor de ``rate`` que resulta de las tres formas de escribirlo.

        Sin contraparte de nombre en la fuente: allá esta resolución la hace su
        ORM al disparar los ``inverse`` de los dos campos computados. Aquí no
        hay quien los dispare, así que el paso es explícito — y es lo que da
        llamador a ``_sanitize_vals`` y a los dos ``_inverse_*``, que sin él
        eran código muerto.

        ``base`` es la fila que se está escribiendo, o ``None`` al crear. **No
        es opcional en la práctica**: el divisor sale de la empresa y la moneda
        de la fila, y en un ``write`` esos dos valores viven en la fila, no en
        ``vals``. Medido: sin ``base``, ``row.write({'company_rate': 4})`` con
        un divisor de 2 guardaba **4** en vez de 8 — la resolución corría contra
        una instancia vacía cuyo divisor caía a 1.

        Devuelve ``(vals_limpios, rate_o_None)``.
        """
        vals = cls._sanitize_vals(vals)
        derived = ('company_rate', 'inverse_company_rate')
        if not any(key in vals for key in derived):
            return vals, vals.get('rate')

        context = {key: value for key, value in vals.items()
                   if key not in derived and key != 'rate'}
        if base is not None:
            probe = base
            for key, value in context.items():
                setattr(probe, key, value)
        else:
            probe = cls(**context)

        if 'company_rate' in vals:
            rate = probe._inverse_company_rate(vals.pop('company_rate'))
        else:
            rate = probe._inverse_inverse_company_rate(
                vals.pop('inverse_company_rate'))
        vals['rate'] = rate
        return vals, rate

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: res_currency.py:399-402``).

        Su cuerpo es ``super().create([self._sanitize_vals(v) for v in
        vals_list])``, precedido de la invalidación que aquí no aplica (ver el
        docstring del módulo). La resolución de las tres tasas —lo que este
        método porta— se aplica a cada ``vals`` antes de delegar, como allá.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        return super().create([cls._rate_from_vals(vals)[0] for vals in vals_list])

    def write(self, vals):
        """≙ ``write`` (``odoo19c: res_currency.py:394-397``).

        Escribe ``vals`` sobre esta fila resolviendo antes cuál de las tres
        tasas gana. Es el punto donde ``_sanitize_vals`` importa: sin él, una
        petición que trae ``rate`` **y** ``company_rate`` deja que gane el
        último que el diccionario recorra.
        """
        vals, _rate = self._rate_from_vals(vals, base=self)
        for field, value in vals.items():
            setattr(self, field, value)
        self.save()
        return True

    @classmethod
    def _search_display_name(cls, operator, value):
        """≙ ``_search_display_name`` (``odoo19c: res_currency.py:479-485``).

        Lo que la fuente hace es **una** cosa: pasar el valor por ``parse_date``
        antes de delegar en la búsqueda por ``_rec_names_search``. Sin ese
        paso, teclear ``15/03/2026`` en el buscador de un campo ``Date`` no
        encuentra nada — y el que busca no se entera de por qué.

        ``parse_date`` no existía en ``src/tools`` y se construyó ahí, sobre
        ``django.utils.formats``, que es el mecanismo nativo equivalente al
        *locale* de babel que usa la fuente.

        La delegación de la fuente va a ``super()``, que busca sobre
        ``_rec_names_search = ['name', 'rate']`` y deja que el optimizador de
        dominios resuelva el tipo de cada uno.

        DIVERGENCIA declarada, de MECANISMO y con bloqueo medido: aquí esa
        delegación **no se puede hacer todavía**. ``name`` es un ``Date`` y
        ``rate`` un decimal; un dominio sobre los dos con un valor que no es
        ni fecha ni número llega a Django y levanta ``ValidationError`` antes
        de que nadie lo optimice. La fuente no tiene ese problema porque su
        familia de optimizadores por tipo colapsa la condición imposible a
        ``FALSE`` primero — y esa familia está **bloqueada** aquí: los seis
        optimizadores de fecha necesitan ``model.env``, medido inexistente.
        Sucesores registrados: **#209** (el ``env``) y **#225** (la familia).

        Mientras tanto el reparto por tipo se hace aquí, con el mismo
        resultado observable: la fecha si parseó, el número si el valor es
        numérico, y nada si no es ninguno de los dos. Devuelve ``Domain``.
        """
        if isinstance(value, COLLECTION_TYPES):
            parsed = [parse_date(item) for item in value]
            dates = [item for item in parsed if isinstance(item, date)]
            matched = Domain('name', 'in', dates) if dates else Domain.FALSE
        else:
            parsed = parse_date(value)
            if isinstance(parsed, date):
                matched = Domain('name', '=', parsed)
            else:
                try:
                    matched = Domain('rate', '=', Decimal(str(parsed)))
                except (InvalidOperation, ValueError, TypeError):
                    matched = Domain.FALSE
        if operator in ('not ilike', 'not in', '!='):
            return ~matched
        return matched

    @classmethod
    def _company_currency_name(cls, company=None):
        """El nombre de la moneda de la empresa — el insumo de las dos de abajo.

        Sin contraparte de nombre: la fuente lo escribe en línea, dos veces,
        como ``(browse(context['company_id']) or env.company).currency_id.name``.
        """
        if company is None:
            company_id = get_current_company()
            if company_id is None:
                return ''
            company = cls.company.field.related_model.objects.filter(
                pk=company_id).first()
        if company is None or company.currency_id is None:
            return ''
        return company.currency.name

    @classmethod
    def _get_view_cache_key(cls, view_type='list', company=None, **options):
        """≙ ``_get_view_cache_key`` (``odoo19c: res_currency.py:487-491``).

        La conducta —lo único que hay que portar— es que **la representación
        cacheada varíe con la moneda de la empresa**. Si no varía, dos empresas
        con monedas distintas comparten unas etiquetas que las contradicen a
        una de las dos.

        Lo que diverge es el destino: allá la representación es una vista XML
        cacheada por el servidor de vistas; aquí es la del serializer DRF, y el
        caché es ``django.core.cache``. Por eso el método devuelve la **llave**
        y no toca ningún caché — quien cachea decide dónde.
        """
        return (cls._name, view_type, tuple(sorted(options.items())),
                cls._company_currency_name(company))

    @classmethod
    def _get_view(cls, view_type='list', company=None, **options):
        """≙ ``_get_view`` (``odoo19c: res_currency.py:493-506``).

        La conducta es calcular **dos etiquetas** a partir de la moneda de la
        empresa: ``company_rate`` se lee «unidades por PESO» e
        ``inverse_company_rate`` «PESO por unidad». Sin ellas, una columna
        rotulada «Tasa» no dice en qué dirección va, que es exactamente la
        pregunta que un tipo de cambio plantea.

        La fuente las inyecta con un ``xpath`` sobre el árbol de la vista y
        sólo en ``view_type == 'list'``. Aquí se devuelven como mapa
        ``campo → etiqueta`` para que las consuma el serializer (o el
        ``@extend_schema`` que publica el contrato); el recorrido del XML es el
        mecanismo, y ése sí diverge.

        ``{}`` cuando el tipo de vista no es de lista, igual que la fuente.
        """
        if view_type != 'list':
            return {}
        currency_name = cls._company_currency_name(company)
        if not currency_name:
            return {}
        return {
            'company_rate': f'Unidades por {currency_name}',
            'inverse_company_rate': f'{currency_name} por unidad',
        }

    # --- ayudantes de este porte, sin contraparte de nombre en la fuente ---

    def _current_company(self):
        """La empresa RAÍZ en contexto, o ``None``.

        La fuente escribe ``self.env.company.root_id`` en cuatro sitios; aquí
        vive una vez. No lleva el nombre de ningún símbolo de la referencia
        porque no lo tiene: allá es un atributo del ``env``.

        El ``.root_id`` no es adorno: ``_check_company_id`` prohíbe que una
        tasa cuelgue de una sucursal, así que buscar la tasa anterior con la
        sucursal en contexto no encontraría ninguna. Omitirlo hacía que toda
        conversión bajo una sucursal cayera al 1.0 por defecto.
        """
        company_id = get_current_company()
        if company_id is None:
            return None
        company = type(self).company.field.related_model.objects.filter(
            pk=company_id).first()
        return company.root_id if company is not None else None

    def _divisor_for(self, company):
        """La última tasa de la moneda de ``company``, o 1 si no hay empresa."""
        if company is None:
            return Decimal('1.0')
        return type(self)._get_last_rates_for_companies([company]).get(
            company.pk, Decimal('1.0'))

    def __str__(self) -> str:
        return f'{self.currency_id} @ {self.name}: {self.rate}'
