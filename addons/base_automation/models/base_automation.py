"""``base.automation`` — addon ``base_automation``.

Adaptación de Odoo ``base_automation/models/base_automation.py``
(odoo-tools@..., odoo19c:, LGPL-3). El modelo declarativo de una regla de
automatización: dispara acciones-servidor (``ir.actions.server``, ya
portadas en ``src/addons/base/models/ir_actions.py``) cuando un modelo
cumple un evento (crear/escribir/borrar/webhook/tiempo) y un dominio.

Decisión de mecanismo — dispatch de triggers (declarada, no silenciosa)
=========================================================================

La referencia dispara las automatizaciones **parcheando en caliente** los
métodos ``create``/``write``/``unlink``/``_compute_field_value`` de CADA
modelo objetivo (``_register_hook``/``_unregister_hook``, con los closures
``make_create``/``make_write``/``make_unlink``/``make_compute_field_value``/
``make_onchange``/``make_message_post`` y el helper ``patch()``). Ese
mecanismo existe porque el registro de Odoo no tiene un bus de eventos
genérico por-modelo — parchear la clase es SU forma de conseguir uno.

Django **ya tiene ese bus**: ``django.db.models.signals`` se dispara para
TODO modelo sin que nadie lo registre por-clase. Replicar el parcheo aquí
sería reconstruir con más código un mecanismo que el framework ya da. Por
eso el dispatch vive en ``models/signals.py`` — **tres receptores globales**
(``pre_save``/``post_save``/``post_delete``, ``sender=None``) conectados
UNA vez en ``BaseAutomationConfig.ready()``, no un patch por regla. Mismo
contrato de comportamiento (una regla activa en el modelo+trigger correcto
se ejecuta), mecanismo distinto y más simple. Los símbolos
``_register_hook``/``_unregister_hook``/``make_create``/``make_write``/
``make_unlink``/``make_compute_field_value``/``patch`` de la referencia NO
se portan — están sustituidos por ``signals.py`` en su totalidad.

Lo que SÍ requiere una pieza ausente y queda bloqueado (declarado, no
omitido en silencio)
=========================================================================

- **``on_change`` (``make_onchange``, dispatch de ``on_change_field_ids``
  contra ``Model._onchange_methods``).** Bloqueado — no existe motor de
  onchange de formulario en este backend headless DRF (mismo gap que
  ``onboarding.onboarding`` con su panel web: ver
  ``addons/onboarding/models/onboarding_onboarding.py``, sección "GAP").
  El CAMPO (``on_change_field_ids``) y su cómputo por dominio SÍ se portan
  (son datos, no requieren UI); sólo el disparo queda sin conectar.
- **``on_message_received``/``on_message_sent`` (``make_message_post``,
  parcheo de ``MailThread.message_post``).** Bloqueado por: enganchar esto
  sin monkey-patch exige que ``MailThread.message_post``
  (``addons/mail/models/mail_thread.py``) emita una señal Django propia —
  igual que ``addons.base.models.signals.res_users_created`` habilita el
  patrón de ``digest``. Modificar ``mail_thread.py`` está fuera de los tres
  directorios permitidos en este pase. El vocabulario (``MAIL_TRIGGERS``,
  el valor en ``trigger``) se porta completo; el dispatch, no.
- **``_compute_field_value`` (recomputo de campos que dispara
  automatizaciones).** Bloqueado — esta capa no tiene un motor de recompute
  genérico por-campo (``@api.depends`` con grafo de dependencias); los
  campos calculados aquí son ``@property`` o columnas recalculadas ad hoc
  por cada addon, sin un punto único donde interceptar "cualquier campo se
  acaba de recalcular".
- **``trg_date_calendar_id`` con ajuste de calendario laboral
  (``calendar.plan_days``).** Bloqueado por pieza concreta ausente:
  ``ResourceCalendar.plan_days`` no existe en ``addons/resource/`` (medido:
  ``grep -n "def plan_days" addons/resource/models/resource_calendar.py``
  → vacío). El campo FK se porta; ``_search_time_based_automation_records``
  cae al cálculo de fecha simple (sin ajustar por días laborables) cuando
  el trigger es ``on_time``/``trg_date_range_type == 'day'`` con calendario
  — divergencia de comportamiento declarada, no un crash silencioso.

Vocabulario Odoo-Studio (``x_studio_*``) — omitido de los dominios de
``_get_trigger_specific_field``: no hay Studio en esta plataforma, así que
esos nombres alternativos de campo nunca podrían matchear nada. No es un
símbolo omitido — es un valor de lista literal sin referente.

Decisión de mecanismo — ``action_server_ids`` / ``base_automation_id``
=========================================================================

La referencia declara ``base_automation_id`` (Many2one) SOBRE
``ir.actions.server`` (en su ``base_automation/models/ir_actions_server.py``,
un ``_inherit``) y expone ``action_server_ids`` como el O2M inverso aquí.
Django no admite declarar un campo nuevo sobre una clase de modelo ya
definida en otro addon (los campos se fijan al evaluar el cuerpo de la
clase, antes de que exista la app que la extiende) — mismo problema que
resolvió ``account_payment`` con ``PaymentGatewayJournal`` (ver su
docstring, ``addons/account_payment/models/account_journal.py``): una
tabla-liga nueva, propia del addon que extiende, en vez de una columna en
el modelo ajeno. ``BaseAutomationAction`` (abajo) es esa tabla-liga —
reemplaza el Many2one de la referencia por un OneToOne
``action -> automation``, misma cardinalidad (una acción, a lo sumo una
regla dueña). ``action_server_ids`` se conserva como el nombre del
accesor (``@property``), fiel a la referencia, aunque su mecanismo interno
sea la tabla-liga y no un O2M directo.
"""
import api
import datetime
import logging
import re
import time
import calendar
from datetime import timedelta
from uuid import uuid4

from django.apps import apps as django_apps
from django.db import connection, models
from django.utils import timezone

import fields
from addons.base.models import IrActionsServer, IrCron, IrLogging, IrModel
from addons.base.models.ir_model import IrModelFields, IrModelFieldsSelection
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.mail.models import MailActivityMixin, MailThread
from addons.resource.models.resource_calendar import ResourceCalendar
from exceptions import UserError, ValidationError
from orm import domains
from orm.environments import get_current_user
from tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

#: ≙ DOMAIN_FIELDS_RE de la referencia — extrae nombres de campo de un
#: dominio en notación de tripletas ``[('campo', 'op', valor), ...]``.
DOMAIN_FIELDS_RE = re.compile(r"""
    [([]\s*
    (?P<quote>['"])
    (?P<field>[a-z]\w*)
    (?:\.[.\w]*)?
    (?P=quote)
    (?:[^,]*?,){2}
    [^,]*?[()[\]]
""", re.VERBOSE)

#: ≙ CREATE_TRIGGERS de la referencia.
CREATE_TRIGGERS = [
    'on_create',
    'on_create_or_write',
    'on_priority_set',
    'on_stage_set',
    'on_state_set',
    'on_tag_set',
    'on_user_set',
]

#: ≙ WRITE_TRIGGERS de la referencia.
WRITE_TRIGGERS = [
    'on_write',
    'on_archive',
    'on_unarchive',
    'on_create_or_write',
    'on_priority_set',
    'on_stage_set',
    'on_state_set',
    'on_tag_set',
    'on_user_set',
]

#: ≙ MAIL_TRIGGERS de la referencia. Vocabulario portado; dispatch
#: bloqueado (ver docstring del módulo).
MAIL_TRIGGERS = ('on_message_received', 'on_message_sent')

#: ≙ CREATE_WRITE_SET de la referencia.
CREATE_WRITE_SET = set(CREATE_TRIGGERS + WRITE_TRIGGERS)

#: ≙ TIME_TRIGGERS de la referencia.
TIME_TRIGGERS = [
    'on_time',
    'on_time_created',
    'on_time_updated',
]

def advance_date(value, unit, count):
    """≙ ``DATE_RANGE[unit] * count`` de la referencia (``relativedelta``).

    DIVERGENCIA declarada: ``python-dateutil`` no es dependencia de este
    proyecto (mismo veredicto medido que ``hr/models/hr_employee.py`` y
    ``web/controllers/json.py`` — ``grep -n dateutil pyproject.toml uv.lock``
    → vacío). El avance por meses se calcula con aritmética de calendario
    propia y la misma semántica que ``relativedelta(months=n)``: mismo día
    del mes destino, recortado al último día cuando no existe.
    """
    if not unit or not count:
        return value
    if unit == 'minutes':
        return value + timedelta(minutes=count)
    if unit == 'hour':
        return value + timedelta(hours=count)
    if unit == 'day':
        return value + timedelta(days=count)
    if unit == 'month':
        total = value.month - 1 + count
        year = value.year + total // 12
        month = total % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)
    raise ValueError(f'trg_date_range_type desconocido: {unit!r}')

#: ≙ DATE_RANGE_FACTOR de la referencia — minutos por unidad, para el
#: cálculo del intervalo del cron (``_get_cron_interval``).
DATE_RANGE_FACTOR = {
    'minutes': 1,
    'hour': 60,
    'day': 24 * 60,
    'month': 30 * 24 * 60,
    None: 0,
}

#: ≙ TIMEDELTA_TYPES de la referencia — usado por ``_update_cron`` para
#: comparar el intervalo actual del cron contra el propuesto.
TIMEDELTA_TYPES = {
    'minutes': lambda interval: timedelta(minutes=interval),
    'hours': lambda interval: timedelta(hours=interval),
    'days': lambda interval: timedelta(days=interval),
    'weeks': lambda interval: timedelta(weeks=interval),
    'months': lambda interval: timedelta(days=30 * interval),
}


def default_webhook_uuid():
    """Default de ``webhook_uuid`` — ≙ ``lambda self: str(uuid4())`` de la
    referencia. Función nombrada porque el serializador de migraciones de
    Django rechaza lambdas (``Cannot serialize function: lambda``)."""
    return str(uuid4())


def get_webhook_request_payload(request=None):
    """≙ ``get_webhook_request_payload`` de la referencia.

    La referencia lee ``odoo.http.request`` (thread-local del framework
    HTTP de Odoo). Aquí no hay ese thread-local — el ``request`` de DRF se
    recibe explícito desde el controller (``controllers/main.py``) y se
    reenvía. Con ``request=None`` (p. ej. invocado fuera de una vista)
    devuelve ``None``, igual que la referencia sin request activo.
    """
    if request is None:
        return None
    try:
        return request.data
    except Exception:  # noqa: BLE001 — cuerpo no-JSON o vacío
        return dict(request.query_params)


def _get_domain_fields(model_row, domain):
    """≙ ``_get_domain_fields`` de la referencia.

    ``ir.model.fields._get(model, field)`` no existe en este árbol (no se
    portó ese classmethod) — se sustituye por una consulta directa sobre
    ``IrModelFields``, mismo resultado (la fila del campo, o nada si no
    existe), sin modificar ``ir_model.py``.
    """
    found = IrModelFields.objects.none()
    if not domain or model_row is None:
        return found
    ids = []
    for match in DOMAIN_FIELDS_RE.finditer(domain):
        field_name = match.groupdict().get('field')
        if not field_name:
            continue
        row = IrModelFields.objects.filter(
            model_id=model_row, name=field_name).first()
        if row is not None:
            ids.append(row.pk)
    if ids:
        found = IrModelFields.objects.filter(pk__in=ids)
    return found


def _domain_fields_differences(model_row, domain1, domain2):
    """≙ ``_domain_fields_differences`` de la referencia."""
    empty = IrModelFields.objects.none()
    if model_row is None:
        return empty, empty
    d1_ids = set(_get_domain_fields(model_row, domain1).values_list('pk', flat=True))
    d2_ids = set(_get_domain_fields(model_row, domain2).values_list('pk', flat=True))
    in_d1_only = IrModelFields.objects.filter(pk__in=(d1_ids - d2_ids))
    in_d2_only = IrModelFields.objects.filter(pk__in=(d2_ids - d1_ids))
    return in_d1_only, in_d2_only


class BaseAutomationAction(TimeStampedModel):
    """Tabla-liga acción-servidor ↔ regla de automatización.

    Reemplaza el Many2one ``ir.actions.server.base_automation_id`` de la
    referencia — ver la sección "Decisión de mecanismo" del docstring del
    módulo. ``OneToOneField`` en ``action`` porque cada ``ir.actions.
    server`` pertenece a lo sumo a una regla (misma cardinalidad que el
    Many2one original).
    """

    action = models.OneToOneField(
        IrActionsServer, on_delete=models.CASCADE,
        related_name='base_automation_link', verbose_name='Acción servidor',
    )
    automation = models.ForeignKey(
        'base_automation.BaseAutomation', on_delete=models.CASCADE,
        related_name='action_links', verbose_name='Regla de automatización',
    )

    class Meta:
        db_table = 'base_automation_action'
        verbose_name = 'Liga acción-automatización'
        verbose_name_plural = 'Ligas acción-automatización'

    def __str__(self):
        return f'{self.action_id} -> {self.automation_id}'


class BaseAutomation(MailThread, MailActivityMixin, TimeStampedModel):
    """``base.automation`` — regla de automatización declarativa."""

    _description = 'Automation Rule'

    TRIGGER_CHOICES = [
        ('on_stage_set', 'Stage is set to'),
        ('on_user_set', 'User is set'),
        ('on_tag_set', 'Tag is added'),
        ('on_state_set', 'State is set to'),
        ('on_priority_set', 'Priority is set to'),
        ('on_archive', 'On archived'),
        ('on_unarchive', 'On unarchived'),
        ('on_create', 'On create'),
        ('on_create_or_write', 'On create and edit'),
        ('on_write', 'On update'),  # deprecated en la referencia
        ('on_unlink', 'On deletion'),
        ('on_change', 'On UI change'),
        ('on_time', 'Based on date field'),
        ('on_time_created', 'After creation'),
        ('on_time_updated', 'After last update'),
        ('on_message_received', 'On incoming message'),
        ('on_message_sent', 'On outgoing message'),
        ('on_webhook', 'On webhook'),
    ]

    RANGE_MODE_CHOICES = [('after', 'After'), ('before', 'Before')]
    RANGE_TYPE_CHOICES = [
        ('minutes', 'Minutes'), ('hour', 'Hours'),
        ('day', 'Days'), ('month', 'Months'),
    ]

    # ≙ CRITICAL_FIELDS / RANGE_FIELDS de la referencia — qué campos, al
    # cambiar, invalidan el cron / el registro de dispatch.
    CRITICAL_FIELDS = ['model_id', 'active', 'trigger', 'on_change_field_ids']
    RANGE_FIELDS = ['trg_date_range', 'trg_date_range_type']

    name = fields.Char(
        max_length=255, required=True, translate=True,
        verbose_name='Nombre de la regla',
        help_text='Odoo name (tracking=True en la referencia: sin chatter '
                  'genérico portado, el seguimiento de cambios no aplica).',
    )
    description = fields.Html(blank=True, default='', verbose_name='Descripción')
    model_id = fields.Many2one(
        IrModel, on_delete=models.CASCADE, db_index=True,
        related_name='base_automations', verbose_name='Modelo',
        help_text='Modelo objetivo (Odoo model_id, domain abstract=False).',
        db_column='model_id',
    )
    # Odoo model_name (related="model_id.model", inverse="_inverse_model_name",
    # store implícito). Columna real sincronizada en save() — mismo criterio
    # que IrActionsServer.model_name (Char plano, no FK) y el mismo patrón
    # de "related, store=True" resuelto sin motor de compute genérico.
    model_name = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Nombre técnico del modelo',
        help_text='Sincronizado desde model_id.model en save() (Odoo '
                  'model_name, related+inverse).',
    )
    url = fields.Char(
        max_length=255, blank=True, default='', verbose_name='URL del webhook',
        help_text='Calculado en save() cuando trigger=on_webhook (Odoo url, '
                  'compute, no store).',
    )
    webhook_uuid = fields.Char(
        max_length=64, default=default_webhook_uuid,
        verbose_name='UUID del webhook',
    )
    record_getter = fields.Char(
        max_length=1024, blank=True,
        default="model.env[payload.get('_model')].browse(int(payload.get('_id')))",
        verbose_name='Localizador de registro',
        help_text='Código evaluado con safe_eval para ubicar el registro '
                  'sobre el que corre el webhook (Odoo record_getter).',
    )
    log_webhook_calls = fields.Boolean(default=False, verbose_name='Registrar llamadas')
    active = fields.Boolean(default=True, verbose_name='Activa')

    trigger = fields.Selection(
        max_length=32, choices=TRIGGER_CHOICES, blank=True, default='',
        verbose_name='Disparador',
    )
    trg_selection_field_id = fields.Many2one(
        IrModelFieldsSelection, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='base_automations', verbose_name='Campo de selección disparador',
        db_column='trg_selection_field_id',
    )
    trg_field_ref_model_name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Modelo de referencia',
    )
    # ≙ Many2oneReference de la referencia — id plano, sin FK real (mismo
    # criterio que IrAttachment.res_id; ver docstring del módulo).
    trg_field_ref = fields.Integer(
        null=True, blank=True, verbose_name='Referencia disparadora',
    )
    trg_date_id = fields.Many2one(
        IrModelFields, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Campo de fecha disparador',
        help_text='Cuándo evaluar la condición (Odoo trg_date_id).',
        db_column='trg_date_id',
    )
    trg_date_range = fields.Integer(null=True, blank=True, verbose_name='Retraso')
    trg_date_range_mode = fields.Selection(
        max_length=8, choices=RANGE_MODE_CHOICES, blank=True, default='',
        verbose_name='Modo del retraso',
    )
    trg_date_range_type = fields.Selection(
        max_length=8, choices=RANGE_TYPE_CHOICES, blank=True, default='',
        verbose_name='Unidad del retraso',
    )
    trg_date_calendar_id = fields.Many2one(
        ResourceCalendar, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='base_automations', verbose_name='Calendario laboral',
        help_text='GAP — ResourceCalendar.plan_days no está portado; ver '
                  'docstring del módulo.',
        db_column='trg_date_calendar_id',
    )
    filter_pre_domain = fields.Char(
        max_length=2048, blank=True, default='', verbose_name='Dominio antes',
        help_text='Debe cumplirse ANTES de la escritura (Odoo filter_pre_domain).',
    )
    previous_domain = fields.Char(
        max_length=2048, blank=True, default='', verbose_name='Dominio previo',
        help_text='No-store en la referencia (default=filter_domain); aquí '
                  'columna real por el mismo motivo que el resto de la '
                  'cadena de cómputo (sin motor @api.depends genérico).',
    )
    filter_domain = fields.Char(
        max_length=2048, blank=True, default='', verbose_name='Dominio de aplicación',
        help_text='Debe cumplirse para ejecutar la regla (Odoo filter_domain).',
    )
    last_run = fields.Datetime(null=True, blank=True, verbose_name='Última corrida')
    #: Los dos ≙ ``odoo19c: base_automation.py:240-252``, que la fuente declara
    #: ``compute=..., readonly=False, store=True``. Los tres se portan; el
    #: volcado del M2M lo hace ``orm.models._flush_m2m``, porque Django prohíbe
    #: el ``setattr`` sobre el lado directo de un muchos-a-muchos (#313).
    on_change_field_ids = fields.Many2many(
        IrModelFields, blank=True, related_name='+',
        compute='_compute_on_change_field_ids', store=True, readonly=False,
        verbose_name='Campos disparadores de onchange',
        help_text='Poblado por dominio; dispatch bloqueado (ver docstring).',
    )
    trigger_field_ids = fields.Many2many(
        IrModelFields, blank=True, related_name='automations_watching',
        compute='_compute_trigger_field_ids', store=True, readonly=False,
        verbose_name='Campos disparadores',
        help_text='Si vacío, se vigilan todos los campos (Odoo trigger_field_ids).',
    )

    class Meta:
        db_table = 'base_automation'
        ordering = ['id']
        verbose_name = 'Regla de automatización'
        verbose_name_plural = 'Reglas de automatización'

    def __str__(self):
        return self.name

    @property
    def action_server_ids(self):
        """≙ ``action_server_ids`` de la referencia — vía la tabla-liga
        ``BaseAutomationAction`` (ver "Decisión de mecanismo" del
        docstring del módulo). Requiere ``pk`` (accede al reverso

        ≙ ``_compute_action_server_ids`` (``odoo19c: base_automation/models/base_automation.py``).
        ``action_links``, que no existe sobre una instancia sin guardar)."""
        if self.pk is None:
            return IrActionsServer.objects.none()
        return IrActionsServer.objects.filter(base_automation_link__automation=self)

    # -- Sincronización de campos derivados (≙ cadena de @api.depends) ------

    def _compute_model_name(self):
        """≙ el lado LECTOR de ``related="model_id.model"`` (``:134``).

        La declaración del campo decía *"sincronizado desde ``model_id.model``
        en ``save()``"* y **eso no ocurría**: la única travesía escrita era la
        inversa (:meth:`_inverse_model_name`, de nombre a FK). Medido con una
        regla creada con ``model_id`` y sin ``model_name``: la columna quedaba
        en ``''``, así que el ``Char`` almacenado mentía sobre su origen y todo
        lo que lee ``model_name`` —el dispatch de ``signals.py``, la
        comparación de ``_compute_action_server_ids``— quedaba ciego.

        Un ``related`` de la fuente tiene dos sentidos: lee del extremo y
        escribe hacia él por su ``inverse``. Aquí el sentido lector va en la
        cadena de ``_recompute_dependent_fields`` —el punto de entrada único
        que este puerto usa en vez del motor ``@api.depends``— y el escritor
        sigue en ``_inverse_model_name``, con el nombre que la fuente le da.

        No pisa un ``model_name`` puesto a mano cuando todavía no hay FK: ése
        es el insumo del sentido inverso, y ``save()`` lo resuelve antes.
        """
        if self.model_id is not None:
            self.model_name = self.model_id.model

    def _inverse_model_name(self):
        """≙ ``_inverse_model_name`` de la referencia — el lado ESCRITOR."""
        if self.model_name:
            self.model_id = IrModel.objects.filter(model=self.model_name).first()

    def _compute_url(self):
        """≙ ``_compute_url``."""
        if self.trigger != 'on_webhook':
            self.url = ''
        else:
            self.url = f'/web/hook/{self.webhook_uuid}'

    def _get_trigger_specific_field(self):
        """≙ ``_get_trigger_specific_field`` de la referencia.

        Los nombres alternativos ``x_studio_*`` de la fuente se omiten —
        no hay Odoo Studio en esta plataforma (ver docstring del módulo).
        """
        domain = None
        if self.trigger == 'on_create_or_write':
            model_row = self.model_id
            return _get_domain_fields(model_row, self.filter_domain)
        if self.trigger == 'on_stage_set':
            domain = dict(ttype='many2one', name__in=['stage_id'])
        elif self.trigger == 'on_tag_set':
            domain = dict(ttype='many2many', name__in=['tag_ids'])
        elif self.trigger == 'on_priority_set':
            domain = dict(ttype='selection', name__in=['priority'])
        elif self.trigger == 'on_state_set':
            domain = dict(ttype='selection', name__in=['state'])
        elif self.trigger == 'on_user_set':
            domain = dict(
                relation='res.users', ttype__in=['many2one', 'many2many'],
                name__in=['user_id', 'user_ids'],
            )
        elif self.trigger in ('on_archive', 'on_unarchive'):
            domain = dict(ttype='boolean', name__in=['active'])
        elif self.trigger == 'on_time_created':
            domain = dict(ttype='datetime', name='create_date')
        elif self.trigger == 'on_time_updated':
            domain = dict(ttype='datetime', name='write_date')
        else:
            return IrModelFields.objects.none()
        if self.model_id is None:
            return IrModelFields.objects.none()
        return IrModelFields.objects.filter(model_id=self.model_id, **domain)

    # -- Cadena de cómputo, descompuesta 1:1 con la referencia --------------
    #
    # Odoo recalcula estos campos SÓLO cuando la dependencia cambió Y el
    # campo no fue escrito explícitamente en el mismo create/write (el
    # compute con readonly=False cede ante una escritura manual). Django no
    # distingue "campo tocado por el caller" de "campo con su default" — el
    # criterio adoptado, declarado aquí una vez para las cuatro que aplica:
    # **recomputar sólo si el campo sigue vacío**, nunca pisar un valor ya
    # presente. Es más fiel al comportamiento real de Odoo (que respeta la
    # escritura manual) que un reset incondicional — un reset ciego en cada
    # save() sería tan infiel como omitir el campo.

    def _compute_trigger(self):
        """≙ ``_compute_trigger`` (``self.trigger = False`` en la
        referencia — SIEMPRE, porque ahí el onchange de ``model_id``
        vuelve a poblarlo de inmediato). Aquí sólo se limpia si ``model_id``
        quedó vacío — nunca se pisa un ``trigger`` que el caller puso."""
        if self.model_id is None:
            self.trigger = ''

    def _compute_trg_date_id(self):
        """≙ ``_compute_trg_date_id``."""
        if self.trigger not in TIME_TRIGGERS:
            self.trg_date_id = None
            return
        if self.trg_date_id is None:
            field_qs = self._get_trigger_specific_field()
            self.trg_date_id = field_qs.first() if field_qs else None

    def _compute_trg_date_range_data(self):
        """≙ ``_compute_trg_date_range_data``."""
        if self.trigger not in TIME_TRIGGERS:
            self.trg_date_range = None
            self.trg_date_range_type = ''
            self.trg_date_range_mode = ''
            return
        if not self.trg_date_range_type:
            self.trg_date_range_type = 'hour'
        if not self.trg_date_range_mode:
            self.trg_date_range_mode = 'after'

    def _onchange_trg_date_range_data(self):
        """≙ ``_onchange_trg_date_range_data`` (``@api.onchange``).

        Bloqueado como disparo de UI (no hay onchange de formulario, ver
        docstring del módulo) — pero su efecto (normalizar el signo de
        ``trg_date_range`` según ``trg_date_range_mode``) es dato puro y se
        aplica igual en el propio ``save()``, sin depender de un evento de
        edición en vivo."""
        if (self.trg_date_range or 0) < 0:
            self.trg_date_range = abs(self.trg_date_range)
            if self.trigger == 'on_time':
                self.trg_date_range_mode = (
                    'before' if self.trg_date_range_mode == 'after' else 'after')

    def _compute_trg_date_calendar_id(self):
        """≙ ``_compute_trg_date_calendar_id``."""
        if (self.trigger not in TIME_TRIGGERS or not self.trg_date_id
                or self.trg_date_range_type != 'day'):
            self.trg_date_calendar_id = None

    def _compute_trg_selection_field_id(self):
        """≙ ``_compute_trg_selection_field_id`` — ver nota de la sección:
        no se resetea un valor ya presente."""
        return

    def _compute_trg_field_ref(self):
        """≙ ``_compute_trg_field_ref`` — ver nota de la sección."""
        return

    def _compute_trg_field_ref_model_name(self):
        """≙ ``_compute_trg_field_ref_model_name``."""
        if self.trigger not in ('on_stage_set', 'on_tag_set') or self.trg_field_ref is None:
            self.trg_field_ref_model_name = ''
            return
        field_qs = self._get_trigger_specific_field()
        field_row = field_qs.first() if field_qs else None
        self.trg_field_ref_model_name = field_row.relation if field_row else ''

    def _compute_filter_pre_domain(self):
        """≙ ``_compute_filter_pre_domain``."""
        if self.trigger == 'on_tag_set':
            field_qs = self._get_trigger_specific_field()
            field_row = field_qs.first() if field_qs else None
            value = self.trg_field_ref
            self.filter_pre_domain = (
                repr([(field_row.name, 'not in', [value])])
                if field_row and value else '')
        else:
            self.filter_pre_domain = ''

    def _compute_filter_domain(self):
        """≙ ``_compute_filter_domain``."""
        if self.trigger not in ('on_create_or_write', *TIME_TRIGGERS):
            field_qs = self._get_trigger_specific_field()
            field_row = field_qs.first() if field_qs else None
        else:
            field_row = None
        self.filter_domain = ''
        if not field_row:
            return
        if self.trigger in ('on_state_set', 'on_priority_set'):
            value = (self.trg_selection_field_id.value
                     if self.trg_selection_field_id else None)
            self.filter_domain = repr([(field_row.name, '=', value)]) if value else ''
        elif self.trigger == 'on_stage_set':
            value = self.trg_field_ref
            self.filter_domain = repr([(field_row.name, '=', value)]) if value else ''
        elif self.trigger == 'on_tag_set':
            value = self.trg_field_ref
            self.filter_domain = repr([(field_row.name, 'in', [value])]) if value else ''
        elif self.trigger == 'on_user_set':
            self.filter_domain = repr([(field_row.name, '!=', False)])
        elif self.trigger == 'on_archive':
            self.filter_domain = repr([(field_row.name, '=', False)])
        elif self.trigger == 'on_unarchive':
            self.filter_domain = repr([(field_row.name, '=', True)])

    def _recompute_dependent_fields(self):
        """Orquesta la cadena ``_compute_*``/``_onchange_*`` de arriba
        sobre ESTA instancia, antes de persistir — reemplaza el motor
        ``@api.depends`` (sin equivalente genérico en este ORM): el punto
        de entrada único es ``save()``."""
        self._compute_model_name()
        self._compute_trigger()
        self._compute_trg_date_id()
        self._compute_trg_date_range_data()
        self._onchange_trg_date_range_data()
        self._compute_trg_date_calendar_id()
        self._compute_trg_selection_field_id()
        self._compute_trg_field_ref()
        self._compute_trg_field_ref_model_name()
        self._compute_filter_pre_domain()
        self._compute_filter_domain()
        self._compute_url()

    def _has_trigger_onchange(self):
        """≙ ``_has_trigger_onchange``. Sin consumidor propio en este
        árbol (la referencia lo usa para invalidar la caché de plantillas
        QWeb — ``env.registry.clear_cache('templates')``, mecanismo
        ausente aquí); se porta el predicado, no el efecto."""
        return bool(self.active and self.trigger == 'on_change'
                    and self.on_change_field_ids.exists())

    def _onchange_domain(self):
        """≙ ``_onchange_domain`` (``@api.onchange('filter_domain')``).

        BLOQUEADO — dispara mientras el usuario edita ``filter_domain`` en
        un formulario en vivo, sincronizando ``on_change_field_ids``/
        ``trigger_field_ids`` con el delta del dominio ANTES de guardar. Sin
        motor de onchange (ver docstring del módulo) no hay "antes de
        guardar" que observar; ``_sync_m2m_dependent_fields`` ya alcanza el
        mismo resultado final recalculando desde cero en cada ``save()`` —
        más caro, mismo dato, sin el delta incremental de la referencia."""
        raise NotImplementedError(
            '_onchange_domain depende de un motor de onchange de '
            'formulario, ausente en este backend headless.')

    def _onchange_trigger(self):
        """≙ ``_onchange_trigger`` (``@api.onchange('trigger')``).
        BLOQUEADO — ver ``_onchange_domain``; ``trigger_field_ids`` se
        recalcula igual en ``_sync_m2m_dependent_fields``."""
        raise NotImplementedError(
            '_onchange_trigger depende de un motor de onchange de '
            'formulario, ausente en este backend headless.')

    def _onchange_trigger_or_actions(self):
        """≙ ``_onchange_trigger_or_actions`` (``@api.onchange``).
        BLOQUEADO — devuelve un ``{'warning': {...}}`` para el cliente web
        de Odoo; no hay cliente web que lo consuma. Las DOS condiciones que
        detecta (acción no-código con ``on_change``; acción de mensajería
        con ``on_unlink``) SÍ se portan como validación dura en
        ``_check_trigger_state`` (``ValidationError`` en vez de warning
        descartable — más estricto que la referencia, nunca más laxo)."""
        raise NotImplementedError(
            '_onchange_trigger_or_actions es un warning de UI; su '
            'validación equivalente vive en _check_trigger_state.')

    def _compute_trigger_field_ids(self):
        """≙ ``_compute_trigger_field_ids``. Requiere ``pk`` (M2M) — ver
        ``_sync_m2m_dependent_fields``, que la invoca después del save."""
        if self.trigger == 'on_create_or_write':
            self.trigger_field_ids.set(
                _get_domain_fields(self.model_id, self.filter_domain))
        elif self.trigger not in TIME_TRIGGERS:
            field_qs = self._get_trigger_specific_field()
            self.trigger_field_ids.set(field_qs if field_qs else [])
        else:
            self.trigger_field_ids.clear()

    def _compute_on_change_field_ids(self):
        """≙ ``_compute_on_change_field_ids``. El campo se puebla por
        dominio; el DISPATCH de onchange está bloqueado (ver docstring del
        módulo — ``_onchange_domain``/``_onchange_trigger``)."""
        if self.trigger == 'on_change':
            self.on_change_field_ids.set(
                _get_domain_fields(self.model_id, self.filter_domain))
        else:
            self.on_change_field_ids.clear()

    def _sync_m2m_dependent_fields(self):
        """Orquesta ``_compute_trigger_field_ids`` +
        ``_compute_on_change_field_ids`` — separadas de
        ``_recompute_dependent_fields`` porque un M2M de Django exige
        ``pk`` (la referencia sí puede escribir un M2M en memoria antes
        del ``INSERT``; aquí no), así que este paso corre DESPUÉS de
        ``super().save()`` — ver ``save()``."""
        self._compute_trigger_field_ids()
        self._compute_on_change_field_ids()

    def _check_trigger(self):
        """≙ ``_check_trigger`` (constrains 'trigger', 'model_id').

        ``IrModel.is_mail_thread`` no existe en este árbol (medido: 0 hits
        en ``src/addons/base/models/ir_model.py``) — ``getattr(...,
        False)`` lo trata como falso siempre, así que esta validación
        **rechaza toda regla con trigger en ``MAIL_TRIGGERS``**, sin
        excepción. Es la lectura fail-closed correcta: el dispatch de esos
        triggers ya está bloqueado (ver docstring del módulo), así que
        permitir configurarlos crearía una regla inerte en vez de un error
        claro en el momento de crearla."""
        if (self.trigger in MAIL_TRIGGERS
                and self.model_id is not None
                and not getattr(self.model_id, 'is_mail_thread', False)):
            raise ValidationError(
                'Mail event can not be configured on model %s. Only models '
                'with discussion feature can be used.' % self.model_id.name)

    def _check_time_trigger(self):
        """≙ ``_check_time_trigger``."""
        if (self.trigger in TIME_TRIGGERS
                and (self.trg_date_range or 0) < 0):
            raise ValidationError(
                "Delay must be positive. Set 'Delay mode' to 'Before' to "
                'negate the delay.')

    def _compute_action_server_ids(self):
        """≙ ``_compute_action_server_ids`` — al cambiar ``model_id``,
        desvincula (no borra) las acciones que apuntaban a otro modelo.
        Requiere ``pk`` (opera sobre la tabla-liga ``BaseAutomationAction``);
        se invoca desde ``save()`` después del ``INSERT``/``UPDATE``.

        ``IrActionsServer`` no tiene ``model_id`` (FK) — sólo ``model_name``
        (``Char`` plano, ver ``src/addons/base/models/ir_actions.py``); la
        comparación de la referencia (``action.model_id != rule.model_id``)
        se traduce a comparar contra ``self.model_id.model`` (el nombre
        técnico, mismo valor que ``BaseAutomation.model_name`` sincroniza)."""
        if self.pk is None or self.model_id is None:
            return
        stale = BaseAutomationAction.objects.filter(
            automation=self).exclude(action__model_name=self.model_id.model)
        stale.delete()

    def _update_registry(self):
        """≙ ``_update_registry`` de la referencia — no-op declarado.

        La referencia re-parchea los modelos objetivo
        (``_unregister_hook``+``_register_hook``) cada vez que una regla
        cambia, porque su mecanismo de dispatch vive en un patch instalado
        una vez por proceso. El reemplazo de este árbol
        (``models/signals.py``, receptores globales) consulta la base en
        cada evento — SIEMPRE ve el estado actual de ``base.automation``
        sin necesitar reinstalación. No hay nada que actualizar."""
        return

    def _check_action_server_model(self):
        """≙ ``_check_action_server_model`` (constrains model_id,
        action_server_ids). Ver ``_compute_action_server_ids`` — la
        comparación es contra ``model_name`` (``IrActionsServer`` no tiene
        ``model_id``), no contra la FK."""
        if self.pk is None or self.model_id is None:
            return
        failing = self.action_server_ids.exclude(model_name=self.model_id.model)
        if failing.exists():
            names = ', '.join(failing.values_list('name', flat=True))
            raise ValidationError(
                'Target model of actions %s are different from rule model.'
                % names)

    def _check_trigger_state(self):
        """≙ ``_check_trigger_state`` (constrains trigger, action_server_ids).

        La segunda mitad (``mail_post``/``followers``/``next_activity``)
        es DIVERGENTE, declarado: ``IrActionsServer.STATE_CHOICES`` de este
        árbol (``src/addons/base/models/ir_actions.py``) sólo tiene seis
        valores —``object_write``/``object_create``/``object_copy``/
        ``code``/``webhook``/``multi``—, ninguno de los tres de la
        referencia (motor de mensajería/seguidores/actividades de
        ``ir.actions.server`` no portado). El filtro queda escrito fiel al
        vocabulario de la referencia mientras no aplique — SIEMPRE vacío
        hoy, no un ``NotImplementedError``, porque no rechaza nada que sí
        pudiera ocurrir: es la forma correcta de "esto no puede pasar
        todavía", no un bloqueo activo."""
        if self.pk is None:
            return
        no_code = self.action_server_ids.exclude(state='code')
        if self.trigger == 'on_change' and no_code.exists():
            raise ValidationError(
                '"On live update" automation rules can only be used with '
                '"Execute Python Code" action type.')
        mail_states = ['mail_post', 'followers', 'next_activity']
        mail_actions = self.action_server_ids.filter(state__in=mail_states)
        if self.trigger == 'on_unlink' and mail_actions.exists():
            raise ValidationError(
                'Email, follower or activity action types cannot be used '
                'when deleting records, as there are no more records to '
                'apply these changes to!')

    def clean(self):
        """Punto único de validación — Django ``full_clean()`` invoca
        ``clean()``; el llamador decide si lo ejecuta (no todo ``save()``
        de Django corre validators automáticamente, a diferencia de los
        ``@api.constrains`` de la referencia, que SIEMPRE corren).

        Sólo dos de las cuatro validaciones van aquí: ``_check_trigger``/
        ``_check_time_trigger`` no necesitan ``pk``. ``_check_action_server_
        model``/``_check_trigger_state`` SÍ (leen ``action_server_ids``, que
        vive en la tabla-liga y exige la fila ya guardada) — se invocan
        explícitamente después de vincular acciones, no desde aquí. Quien
        cree/edite una regla vía código llama ``full_clean()`` para las dos
        primeras y las otras dos a mano tras poblar ``action_server_ids``."""
        super().clean()
        self._check_trigger()
        self._check_time_trigger()

    def save(self, *args, **kwargs):
        """≙ create()/write() de la referencia — recomputa la cadena
        derivada y actualiza cron+dispatch cuando cambian campos críticos.
        """
        creating = self.pk is None
        if not self.model_id and self.model_name:
            self._inverse_model_name()
        self._recompute_dependent_fields()
        super().save(*args, **kwargs)
        self._sync_m2m_dependent_fields()
        self._compute_action_server_ids()
        if creating or self._critical_fields_changed():
            self._update_cron()
            self._update_registry()
            self._has_trigger_onchange()  # ≙ invalidación de caché — sin efecto (ver docstring)
        self._critical_snapshot = self._current_critical_snapshot()

    def delete(self, *args, **kwargs):
        """≙ ``unlink()`` de la referencia."""
        result = super().delete(*args, **kwargs)
        self._update_cron()
        self._update_registry()
        return result

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: base_automation.py:491-498``).

        Conserva el nombre de la fuente. Es la puerta que allá vigila la
        creación de reglas —crear una regla cambia lo que el cron tiene que
        mirar y lo que el dispatch tiene que enganchar—, y aquí esa mitad la
        hacía sólo ``save()``. Las dos coexisten a propósito, igual que en
        ``addons/base_sparse_field/models/ir_model_fields.py``: ésta es la
        puerta que la fuente vigila, y ``save()`` cubre el camino de Django
        (``instance.campo = x; instance.save()``).

        Acepta un ``dict`` suelto además de la lista, como el
        ``@api.model_create_multi`` de la fuente. Devuelve la lista de reglas
        creadas.

        La invalidación de caché de plantillas de la fuente
        (``registry.clear_cache('templates')`` tras ``_has_trigger_onchange``)
        **no tiene receptor aquí**: no hay motor de onchange que memorice
        atributos de plantilla —la divergencia está declarada en el docstring
        del módulo— así que se conserva la consulta y no su efecto, que es lo
        que ``save()`` ya hacía.
        """
        automations = [cls.objects.create(**vals) for vals in vals_list]
        for automation in automations:
            automation._update_cron()
            automation._update_registry()
            automation._has_trigger_onchange()
        return automations

    def write(self, **vals):
        """≙ ``write`` (``odoo19c: base_automation.py:500-511``).

        Conserva el nombre y, con él, la asimetría que la fuente escribe: un
        cambio en ``CRITICAL_FIELDS`` actualiza cron **y** dispatch; uno que
        sólo toca ``RANGE_FIELDS`` actualiza **sólo** el cron. ``save()`` no
        puede distinguirlas —para cuando corre, la instancia ya trae los
        valores nuevos y no sabe cuáles entraron—, así que esa mitad del
        comportamiento sólo existe por esta puerta.

        La firma es ``**vals`` y el cuerpo es *poner los atributos y guardar*,
        el idioma ya fijado por ``addons/stock/models/stock_location.py:575``.
        Devuelve ``self``.
        """
        entrantes = set(vals)
        for name, value in vals.items():
            setattr(self, name, value)
        super().save()
        if entrantes.intersection(self.CRITICAL_FIELDS):
            self._update_cron()
            self._update_registry()
            self._has_trigger_onchange()
        elif entrantes.intersection(self.RANGE_FIELDS):
            self._update_cron()
        self._critical_snapshot = self._current_critical_snapshot()
        return self

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: base_automation.py:513-521``).

        Conserva el nombre; el cuerpo delega en :meth:`delete`, que es donde
        vive la actualización de cron y dispatch. Existe para que el símbolo de
        la fuente se pueda llamar por su nombre desde un puerto hermano, sin
        que quien lea la referencia tenga que saber que aquí se llama de otra
        forma.
        """
        return self.delete()

    def _current_critical_snapshot(self):
        return tuple(getattr(self, f, None) for f in self.CRITICAL_FIELDS)

    def _critical_fields_changed(self):
        previous = getattr(self, '_critical_snapshot', None)
        if previous is None:
            return True
        return previous != self._current_critical_snapshot()

    def copy(self):
        """≙ ``copy()`` de la referencia — duplica la regla y sus acciones."""
        action_pks = list(self.action_server_ids.values_list('pk', flat=True))
        clone = BaseAutomation.objects.get(pk=self.pk)
        clone.pk = None
        clone._state.adding = True
        clone.webhook_uuid = str(uuid4())
        clone.save()
        for action_pk in action_pks:
            action_clone = IrActionsServer.objects.get(pk=action_pk)
            action_clone.pk = None
            action_clone._state.adding = True
            action_clone.save()
            BaseAutomationAction.objects.create(action=action_clone, automation=clone)
        return clone

    # -- Acciones ------------------------------------------------------

    def action_open_scheduled_action(self):
        """≙ ``action_open_scheduled_action``."""
        cron = (IrCron.objects
                .filter(ir_actions_server__model_name='base_automation.BaseAutomation',
                        ir_actions_server__method_name='_cron_process_time_based_actions')
                .first())
        if not cron:
            raise UserError(
                'The scheduled action for Automation Rules seems to have '
                'vanished.')
        return cron

    def action_rotate_webhook_uuid(self):
        """≙ ``action_rotate_webhook_uuid``."""
        self.webhook_uuid = str(uuid4())
        self.save()

    def action_view_webhook_logs(self):
        """≙ ``action_view_webhook_logs`` — devuelve el queryset de logs
        de este webhook (la referencia devuelve una act_window; aquí no
        hay cliente web al que devolvérsela, así que se entrega el
        queryset directamente para que un endpoint DRF lo serialice)."""
        return IrLogging.objects.filter(path='base_automation(%s)' % self.pk)

    # -- Evaluación de dominios / webhook --------------------------------

    def _get_eval_context(self, payload=None):
        """≙ ``_get_eval_context``."""
        model = django_apps.get_model(self.model_name) if self.model_name else None
        # DIVERGENCIA declarada: la referencia expone además ``dateutil`` al
        # código de la regla; aquí no es dependencia del proyecto (ver
        # ``advance_date``), así que el contexto no lo publica.
        context = {
            'datetime': datetime,
            'time': time,
            'user': get_current_user(),
            'model': model,
        }
        if payload is not None:
            context['payload'] = payload
        return context

    def _records_matching_domain(self, model_cls, domain_str, pks):
        """Traduce ``domain_str`` (notación Odoo, texto) a un filtro real
        sobre la base — sustituye ``filtered_domain`` (evaluación en
        memoria) de la referencia por una re-consulta (``domains.to_q`` +
        ``QuerySet.filter``), mismo patrón que ``ir_rule.build_domain``."""
        if not domain_str or not pks:
            return model_cls.objects.filter(pk__in=pks) if pks else model_cls.objects.none()
        parsed = safe_eval(domain_str, self._get_eval_context())
        q = domains.to_q(parsed, model=model_cls)
        return model_cls.objects.filter(pk__in=pks).filter(q)

    def _filter_pre(self, model_cls, pks):
        """≙ ``_filter_pre`` — precondición, evaluada ANTES de escribir."""
        if not self.filter_pre_domain:
            return list(pks)
        matched = self._records_matching_domain(
            model_cls, self.filter_pre_domain, pks)
        return list(matched.values_list('pk', flat=True))

    def _filter_post_export_domain(self, model_cls, pks):
        """≙ ``_filter_post_export_domain`` — postcondición, evaluada
        DESPUÉS de escribir; devuelve también el dominio usado (para el
        ``domain_post`` que ``_process`` reenvía al contexto de ejecución
        de la acción — inerte hoy, ver docstring de ``_process``)."""
        if not self.filter_domain:
            return list(pks), None
        matched = self._records_matching_domain(
            model_cls, self.filter_domain, pks)
        return list(matched.values_list('pk', flat=True)), self.filter_domain

    def _filter_post(self, model_cls, pks):
        """≙ ``_filter_post`` — delega en ``_filter_post_export_domain``,
        descartando el dominio (mismo patrón que la referencia)."""
        matched_pks, _domain = self._filter_post_export_domain(model_cls, pks)
        return matched_pks

    def _check_trigger_fields(self, model_cls, pk, old_values):
        """≙ ``_check_trigger_fields`` — ¿algún campo vigilado cambió?"""
        watched = list(self.trigger_field_ids.values_list('name', flat=True))
        if not watched:
            return True
        if old_values is None:
            return True
        row_old = old_values.get(pk, {})
        current = model_cls.objects.filter(pk=pk).values(*watched).first() or {}
        return any(
            name in row_old and current.get(name) != row_old.get(name)
            for name in watched
        )

    def _add_postmortem(self, exc):
        """≙ ``_add_postmortem`` — anota la excepción con el origen (regla
        + nombre) antes de dejarla escapar. La referencia condiciona esto a
        ``self.env.user._is_internal()``; sin esa distinción de usuario
        aquí, se anota siempre (estrictamente más informativo, nunca
        menos)."""
        exc.base_automation_context = {
            'exception_class': 'base_automation',
            'base_automation': {'id': self.pk, 'name': self.name},
        }

    def _process(self, model_cls, pks, domain_post=None, old_values=None):
        """≙ ``_process`` — ejecuta las ``action_server_ids`` de esta
        regla sobre los ``pks`` que aún no fueron procesados en este
        contexto. Sin el ``env.context['__action_done']`` de la
        referencia (mecanismo de recursión de su Environment); la guarda
        de recursión aquí es que el propio caller (signals.py) no
        reinvoca ``_process`` para el mismo ``(regla, pk)`` en la misma
        señal — ver signals.py.

        ``domain_post`` se acepta y no se usa (ver ``_filter_post_export_
        domain``): en la referencia viaja al contexto del modo ``code``,
        que ``IrActionsServer.run()`` no evalúa en este árbol."""
        pks = [p for p in pks if self._check_trigger_fields(model_cls, p, old_values)]
        if not pks:
            return
        for action in self.action_server_ids.all():
            for pk in pks:
                try:
                    action.run()
                except NotImplementedError:
                    _logger.warning(
                        'base.automation %s: accion %s no ejecutable '
                        '(motor de ir.actions.server.run() no portado)',
                        self.pk, action.pk)
                except Exception as exc:
                    self._add_postmortem(exc)
                    _logger.exception(
                        'base.automation %s: fallo ejecutando accion %s '
                        'sobre %s#%s', self.pk, action.pk, model_cls.__name__, pk)
                    raise

    def _execute_webhook(self, payload):
        """≙ ``_execute_webhook``."""
        msg = 'Webhook #%s triggered with payload %s'
        _logger.debug(msg, self.pk, payload)
        if self.log_webhook_calls:
            self._log_webhook(msg % (self.pk, payload))

        model_cls = django_apps.get_model(self.model_name) if self.model_name else None
        record_pk = None
        if self.record_getter and model_cls is not None:
            try:
                record_pk = safe_eval(
                    self.record_getter,
                    self._get_eval_context(payload=payload)).pk
            except Exception:
                msg = 'Webhook #%s could not be triggered because the ' \
                      'record_getter failed'
                _logger.warning(msg, self.pk, exc_info=True)
                if self.log_webhook_calls:
                    self._log_webhook(msg % self.pk, level='ERROR')
                raise

        if model_cls is None or record_pk is None or not model_cls.objects.filter(
                pk=record_pk).exists():
            msg = ('Webhook #%s could not be triggered because no record '
                   'to run it on was found.')
            _logger.warning(msg, self.pk)
            if self.log_webhook_calls:
                self._log_webhook(msg % self.pk, level='ERROR')
            raise ValidationError(
                'No record to run the automation on was found.')

        try:
            self._process(model_cls, [record_pk])
        except Exception:
            msg = 'Webhook #%s failed with error'
            _logger.warning(msg, self.pk, exc_info=True)
            if self.log_webhook_calls:
                self._log_webhook(msg % self.pk, level='ERROR')
            raise

    def _prepare_loggin_values(self, **values):
        """≙ ``_prepare_loggin_values`` de la referencia — el nombre con
        la errata ("loggin", no "logging") se preserva verbatim: es el
        símbolo real de la fuente, no un typo propio."""
        defaults = {
            'name': 'Webhook Log', 'type': 'server',
            'dbname': connection.settings_dict.get('NAME', ''),
            'level': 'INFO', 'path': 'base_automation(%s)' % self.pk,
            'func': '', 'line': '',
        }
        defaults.update(values)
        return defaults

    def _log_webhook(self, message, level='INFO'):
        """Persiste la fila que arma ``_prepare_loggin_values`` — la
        referencia inlinea ``ir_logging_sudo.create(...)`` en cada punto de
        llamada; aquí se colapsa en un método para no repetir el
        ``IrLogging.objects.create`` cuatro veces (mismo dato final)."""
        IrLogging.objects.create(
            **self._prepare_loggin_values(message=message, level=level))

    # -- Cron: intervalo dinámico + ejecución time-based -------------------

    @classmethod
    def _get_actions(cls, model_name, triggers):
        """≙ ``_get_actions`` de la referencia. Invocado por
        ``models/signals.py`` — el reemplazo del dispatch por parcheo."""
        return cls.objects.filter(
            active=True, model_name=model_name, trigger__in=triggers)

    def _update_cron(self):
        """≙ ``_update_cron``."""
        cron = (IrCron.objects
                .filter(ir_actions_server__model_name='base_automation.BaseAutomation',
                        ir_actions_server__method_name='_cron_process_time_based_actions')
                .first())
        if not cron:
            return
        automations = BaseAutomation.objects.filter(
            active=True, trigger__in=TIME_TRIGGERS)
        interval_number, interval_type = self._get_cron_interval(automations)
        actual = TIMEDELTA_TYPES[cron.interval_type](cron.interval_number)
        proposed = TIMEDELTA_TYPES[interval_type](interval_number)
        cron.active = automations.exists()
        if proposed < actual:
            cron.interval_type = interval_type
            cron.interval_number = interval_number
        cron.save()

    def _get_cron_interval(self, automations=None):
        """≙ ``_get_cron_interval``."""
        if automations is None:
            automations = BaseAutomation.objects.filter(
                active=True, trigger__in=TIME_TRIGGERS)
        delays = [
            abs(a.trg_date_range or 0) * DATE_RANGE_FACTOR[a.trg_date_range_type or None]
            for a in automations
        ]
        delays = [d for d in delays if d]
        interval = min(max(1, min(delays) // 10), 4 * 60) if delays else 4 * 60
        interval_type = 'minutes'
        if interval % 60 == 0:
            interval //= 60
            interval_type = 'hours'
        return interval, interval_type

    def _get_calendar(self):
        """≙ ``_get_calendar`` (``@api.model`` en la referencia, punto de
        extensión — un módulo satélite puede sobreescribirlo para resolver
        el calendario por-registro). Aquí ``self`` alcanza porque no hay
        ``record`` con calendario propio que priorizar (esa variante
        tampoco está portada — ver ``ResourceCalendar.plan_days`` en el
        docstring del módulo)."""
        return self.trg_date_calendar_id

    def _search_time_based_automation_records(self, model_cls, until):
        """≙ ``_search_time_based_automation_records``.

        Rama de calendario laboral (``trg_date_calendar_id`` +
        ``trg_date_range_type == 'day'``) DEGRADADA — ``ResourceCalendar.
        plan_days`` no está portado (ver docstring del módulo): cae al
        cálculo de fecha simple sin ajuste por días laborables."""
        if self.trg_date_calendar_id_id is not None and self.trg_date_range_type == 'day':
            _logger.warning(
                'base.automation %s: trg_date_calendar_id fijado pero '
                'ResourceCalendar.plan_days no está portado; usando '
                'cálculo de fecha simple sin ajuste laboral.', self.pk)

        if not self.trg_date_id:
            _logger.warning(
                'Missing date trigger field in automation rule `%s`', self.name)
            return model_cls.objects.none()

        date_field_name = self.trg_date_id.name
        last_run = self.last_run or timezone.datetime.fromtimestamp(0, tz=timezone.utc)
        range_sign = 1 if self.trg_date_range_mode == 'before' else -1
        date_range = range_sign * (self.trg_date_range or 0)
        unit = self.trg_date_range_type or None
        relative_until = advance_date(until, unit, date_range)
        relative_last_run = advance_date(last_run, unit, date_range)

        domain = models.Q()
        if self.filter_domain:
            parsed = safe_eval(self.filter_domain, self._get_eval_context())
            domain = domains.to_q(parsed, model=model_cls)

        time_domain = models.Q(**{
            f'{date_field_name}__gte': relative_last_run,
            f'{date_field_name}__lt': relative_until,
        })
        is_date_automation_last = (
            date_field_name == 'date_automation_last'
            and hasattr(model_cls, 'created_at'))
        if is_date_automation_last:
            time_domain |= models.Q(**{
                f'{date_field_name}__isnull': True,
                'created_at__gte': relative_last_run,
                'created_at__lt': relative_until,
            })
        return model_cls.objects.filter(domain & time_domain)

    @classmethod
    def _check(cls, automatic=False):
        """≙ ``_check`` de la referencia (``@api.deprecated`` desde 19.0,
        conservado por compatibilidad hacia atrás — mismo criterio aquí:
        preservado como shim, no como API a usar en código nuevo)."""
        if not automatic:
            raise RuntimeError(
                'can run time-based automations only in automatic mode')
        cls._cron_process_time_based_actions()

    @classmethod
    def _cron_process_time_based_actions(cls):
        """≙ ``_cron_process_time_based_actions`` de la referencia — el
        guion bajo se conserva (``getattr`` no distingue público/privado;
        sólo es convención, así que preservarlo no rompe el dispatch de
        ``IrCron._callback``: ``getattr(model, method_name)`` resuelve
        este nombre igual con o sin guion — ver ``data/__init__.py`` para
        el valor exacto sembrado en ``method_name``).

        La referencia lo declara ``@api.model`` (instancia-o-clase
        indistinto en Odoo); aquí ``@classmethod`` es el equivalente para
        ``getattr(ModelClass, method_name)()`` — ``IrCron._callback``
        resuelve la clase con ``apps.get_model(model_name)``, no una
        instancia.
        """
        automations = cls.objects.filter(active=True, trigger__in=TIME_TRIGGERS)
        final_exception = None
        now = timezone.now()
        for automation in automations:
            if not automation.model_name:
                continue
            model_cls = django_apps.get_model(automation.model_name)
            _logger.info("Starting time-based automation rule `%s`.", automation.name)
            records = automation._search_time_based_automation_records(model_cls, now)
            pks = list(records.values_list('pk', flat=True))
            try:
                automation._process(model_cls, pks)
            except Exception as exc:  # noqa: BLE001
                _logger.exception(
                    'Error in time-based automation rule `%s`.', automation.name)
                final_exception = exc
                continue
            automation.last_run = now
            automation.save()
            _logger.info("Time-based automation rule `%s` done.", automation.name)
        if final_exception is not None:
            raise final_exception
