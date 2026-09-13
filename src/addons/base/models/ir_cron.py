"""``ir.cron`` — registro de tareas programadas (Odoo ``base``).

Portación fiel de ``IrCron``
(``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_cron.py:54-750``,
Odoo 18; ``scratchpad/odoo19x/odoo/addons/base/models/ir_cron.py:91-895``,
Odoo 19) — la **estructura de control** que persiste una tarea programada
(qué ejecutar, cada cuánto, próxima corrida) — **no** el runner que la
ejecuta. Parte de la iniciativa ``adaptar-familias-odoo-monolito-modular``
(SOL-096), backlog de control núcleo ``ir.*`` (H-BASE-01 C-2). Premisa
verificada por el orquestador: ``ir_cron`` AUSENTE de
``src/addons/base/models/`` antes de este commit (``grep -rl "class IrCron"
src/addons/base/models/`` → vacío).

Delegación a ``ir.actions.server`` — PORTADA
=====================================================================

Odoo modela ``ir.cron`` con ``_inherits = {'ir.actions.server':
'ir_actions_server_id'}`` (19 línea 104-108, enlace en :106-108 como
``Many2one(..., delegate=True, ondelete='restrict', required=True)``): el
"qué ejecutar" vive delegado en la acción servidor, y ``ir.cron`` **sólo
aporta la periodicidad**.

Se porta con el patrón establecido en este árbol para ``_inherits`` — **FK
real + delegación por propiedad**, NO herencia multi-tabla de Django (que
crea un ``OneToOneField(parent_link=True)``, una hija por padre, cuando el
``_inherits`` de Odoo es un ``Many2one``). Mismo criterio que
``product_product.py`` → ``product.template``, ``res_users.py`` →
``res.partner`` y ``mail_mail.py`` → ``mail.message``.

**Revierte la adaptación anterior**, que declaraba ``name``/``model_name``/
``method_name`` como columnas locales. Aquella se justificaba en que "sin el
modelo destino no hay FK fiel que portar"; ``IrActionsServer`` ya existe
(``ir_actions.py:402``), así que la premisa caducó. Prevalece el análisis
actual — principio rector, Clausula 1; directiva del ejecutor 2026-08-01
(*"queremos delegar las cosas, como lo tienes en odoo-tools"*). Ver
H-API-203.

Qué NO cambia con la delegación
---------------------------------

El **motor de ejecución sigue sin portarse**: ``IrActionsServer.run()``
levanta ``NotImplementedError`` a propósito, porque el modo ``code`` evalúa
Python almacenado y quién conecte el evaluador es una decisión aparte (ver
el docstring de ``ir_actions.py``). Delegar mueve el *dato* del "qué
ejecutar" a su hogar fiel; **no** habilita la evaluación de código.

``method_name`` — dónde vive ahora
-----------------------------------

Es una adaptación de proyecto **sin análogo** en la referencia: sustituye la
evaluación del ``code`` Python por una llamada a método
(``getattr(apps.get_model(model_name), method_name)``, que resolverá el
runner diferido). Vive en ``IrActionsServer`` junto a ``code`` y
``model_name`` —no en ``ir.cron``— porque ese es el modelo donde la
referencia pone el "qué ejecutar". Partirlo entre los dos modelos habría
dejado el objetivo a medias en cada uno.

``model_name`` sigue siendo ``Char`` plano en su nuevo hogar, igual que
``ir.filters.model_id`` y ``ir.attachment.res_model`` — la delegación no
cambia ese criterio, sólo dónde está el campo.

El runner del cron — PORTADO COMPLETO (2026-08-26)
=====================================================================

Esta seccion declaraba hasta hoy un **colapso deliberado** frente a la
referencia y una lista de cinco cosas "deliberadamente NO portadas". Esa
declaracion caduco por directiva del ejecutor —*"la implementacion es
completa, x archivo, clase, funcion y firma de funcion"*— y el archivo pasa de
557 lineas a las que tiene ahora contra las **933** de
``odoo19c: odoo/addons/base/models/ir_cron.py``.

Lo que se porto en ese pase, y que antes esta seccion enumeraba como ausente:

- **Las cuatro clases de modulo** — ``BadVersion``, ``BadModuleState``,
  ``CompletionStatus`` y ``ListLogHandler``. Las dos ultimas son stdlib pura
  (``logging`` + ``contextvars``), asi que se portan verbatim.
- **``ir.cron.trigger``** — el disparo puntual, con ``_trigger`` /
  ``_trigger_list`` / ``_notifydb`` / ``_gc_cron_triggers``. Es lo que le
  daba a ``_get_ready_sql_condition`` su rama ``OR``: sin el modelo, un
  ``_trigger`` no despertaba nada porque no habia donde anotarlo.
- **``ir.cron.progress``** — el avance por lotes, con ``_add_progress`` /
  ``_notify_progress`` / ``_commit_progress`` / ``_gc_cron_progress``. Es lo
  que habilita el tercer desenlace, ``PARTIALLY_DONE``: un job largo cede el
  turno y sigue despues en vez de bloquear a los demas.
- **``failure_count`` / ``first_failure_date``** y su
  ``_update_failure_count``, con los **dos** umbrales de la fuente en
  conjuncion: cinco fallos **y** mas de una semana desde el primero. Un job
  que falla cinco veces en un minuto NO se desactiva.
- **``_check_version`` / ``_check_modules_state``** — con su divergencia de
  mecanismo declarada en cada uno: aqui la version del schema la sabe el
  ejecutor de migraciones de Django, y ``ir.module.module`` no tiene los
  estados transitorios ``to install`` / ``to upgrade`` / ``to remove``
  (medido: ``IrModule.STATES`` declara tres, ninguno empieza con ``'to '``).
- **``_process_job`` separado de ``_run_job``**, que es como la fuente los
  tiene: el primero arbitra —decide si el job se corre y como se reprograma
  segun el desenlace—, el segundo corre el bucle y **devuelve** el desenlace.
  El ``match`` de seis ramas de la fuente se porta con sus seis comentarios.
- **``usage``** en ``IrActionsServer`` (``odoo19c: ir_actions.py:608-611``),
  que este arbol nunca porto: es lo que distingue la accion de un cron de una
  suelta, y lo escribe ``IrCron.save()`` al crear.

La divergencia que queda esta declarada **en el metodo que la tiene**, no
aqui: el cursor propio de ``_run_job`` (tarea #42).

Adquisicion: ``FOR NO KEY UPDATE SKIP LOCKED`` via
``QuerySet.select_for_update(skip_locked=True, no_key=True)`` — la misma
capacidad de PostgreSQL que la referencia usa (ADR-028 la desbloqueo;
MariaDB no la daba), **no** un lock de aplicacion en Python. Cada job se
adquiere y ejecuta en su propia transaccion (``transaction.atomic``),
igual que la referencia comitea por-job en ``_process_jobs_loop``.

Campos del brief NO presentes en Odoo 18 ni 19 — OMITIDOS, no inventados
=====================================================================

El brief de esta tarea especulaba dos campos adicionales que **no existen**
en ninguna de las dos fuentes citadas arriba (verificado con ``grep -En
"numbercall|doall" scratchpad/odoo{18,19x}/.../ir_cron.py`` → 0 matches en
ambos archivos):

- **``numbercall``** (contador de ejecuciones restantes, ``-1``=ilimitado):
  campo de versiones muy anteriores de Odoo (pre-10, antes del rediseño a
  ``ir.cron.trigger``); ausente de 18 y 19. NO se agrega — inventarlo sin
  respaldo en la fuente violaría el criterio "fiel a Odoo, no inventado".
- **``doall``** (ejecutar corridas perdidas): mismo caso — campo legado
  ausente de 18 y 19.

Ambos quedan como hallazgo H-BASE-NN candidato (ver reporte del commit)
por si una futura iteración del runner necesita semántica equivalente
("ejecutar N veces y desactivar" / "compensar corridas perdidas");
se implementaría entonces con nombre y semántica propios, sin resucitar
el nombre legado de Odoo si no se porta su comportamiento exacto.

``company_id`` tampoco existe en ``ir.cron`` en ninguna de las dos fuentes
(verificado leyendo el modelo completo en ambas versiones) — se omite por
ausencia real, no se especula (mismo criterio que ``ir_filters.py`` con su
propio ``company_id`` ausente).

``user`` — adaptación deliberada respecto a Odoo
=====================================================================

Odoo declara ``user_id`` ``required=True`` con
``default=lambda self: self.env.user`` (18/19 línea 72/110) — siempre hay
un usuario ejecutor porque Odoo lo resuelve del contexto de sesión al
crear el cron. Este monolito no tiene ese contexto de request implícito al
registrar una tarea programada (p. ej. seed de datos, management command),
así que ``user`` se porta **nullable** (``null=True, blank=True,
on_delete=SET_NULL``) — mismo patrón que ``company`` en
``ir_sequence``/``ir_attachment``: el dueño es opcional a nivel de dato.

Cross-app: ``user`` → ``settings.AUTH_USER_MODEL`` (Odoo ``user_id``).

``user`` SÍ se consume: el callback corre bajo ``user_scope``
--------------------------------------------------------------

La referencia ejecuta el callback **como el usuario del job**
(``env = api.Environment(job_cr, job['user_id'], {...})``,
ir_cron.py:481-483). Aquí el equivalente es ``orm.environments.user_scope``
—el ``with_user`` de ``odoo19c: odoo/orm/models.py:5981-5988``, implementado
con ``ContextVar`` para ser seguro bajo hilos y async—, que ``_callback``
envuelve alrededor de la invocación.

El camino HTTP ya poblaba ese mismo eje (``ir_http.py:257``,
``set_current_uid``); el cron era el único llamador que lo dejaba sin
poblar. Con el scope puesto, ``orm.environments.get_current_user()`` dentro
del método invocado devuelve el ``user`` del cron, que es lo que consumen
``bus/ir_attachment.py``, ``bus/bus_listener_mixin.py`` y
``digest/digest.py``.

**Lo que esto NO alcanza todavía:** ``IrRule._eval_context`` (``ir_rule.py:161``)
recibe ``user`` como parámetro explícito y **no** cae a ``get_current_user()``
cuando el llamador no lo pasa. Así que un cron con ``user`` puesto tiene el
usuario disponible en el contexto, pero las record rules evaluadas dentro no
lo ven salvo que el propio método lo pase. Cambiar ese default altera el
dominio evaluado para **todo** consumidor de record rules, no sólo el cron:
va por separado, con su barrido de llamadores (tarea #127, segunda mitad;
:ref:`h-api-333`).
"""
import calendar
import contextvars
import copy
import logging
import os
import time
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.apps import apps
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

import fields
import models
from addons.base.models.ir_actions import IrActionsServer
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_module import IrModule
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import LockError, UserError
from orm.environments import context_scope, get_context, user_scope
from tools.constants import GC_UNLINK_LIMIT

_logger = logging.getLogger(__name__)

# === Constantes de la referencia (``odoo19c: ir_cron.py:32-40``) ===========
# Se portan verbatim, con su comentario: son la politica de reintento y de
# desactivacion, y cambiar uno cambia la conducta observable del planificador.

#: Ventana tras la cual se asume que los crons estan atascados por estado
#: zombi de modulos. La fuente comenta: *"chosen with a fair roll of the dice"*.
MAX_FAIL_TIME = timedelta(hours=5)
#: Vueltas minimas del bucle de progreso antes de ceder el turno.
MIN_RUNS_PER_JOB = 10
#: Segundos minimos del bucle de progreso antes de ceder el turno.
MIN_TIME_PER_JOB = 10
#: Tiempos de espera consecutivos que convierten el job en fallido.
CONSECUTIVE_TIMEOUT_FOR_FAILURE = 3
#: Fallos minimos antes de desactivar. Se exigen AMBOS umbrales, no uno.
MIN_FAILURE_COUNT_BEFORE_DEACTIVATION = 5
#: Antiguedad minima del primer fallo antes de desactivar.
MIN_DELTA_BEFORE_DEACTIVATION = timedelta(days=7)

#: Funcion a llamar en vez de ``pg_notify`` (``ODOO_NOTIFY_FUNCTION`` de la
#: fuente). Verificado en PostgreSQL 16.13: ``pg_notify`` existe en
#: ``pg_proc``.
NOTIFY_FUNCTION = os.getenv('KAUPAMEX_NOTIFY_FUNCTION', 'pg_notify')

#: Si esta puesta, cada alta y cada cambio de agenda de un cron avisa a los
#: workers por el canal (``ODOO_NOTIFY_CRON_CHANGES`` de la fuente,
#: ``odoo19c: ir_cron.py:134-140`` y ``:696-709``). Sin ella el worker que
#: duerme en el canal no se entera de un cron reprogramado o reactivado hasta
#: su siguiente sondeo, que es justo lo que la variable existe para evitar.
NOTIFY_CRON_CHANGES = bool(os.getenv('KAUPAMEX_NOTIFY_CRON_CHANGES'))



class BadVersion(Exception):
    """≙ ``BadVersion`` (``odoo19c: ir_cron.py:43-44``).

    La version del codigo no coincide con la de la base.
    """


class BadModuleState(Exception):
    """≙ ``BadModuleState`` (``odoo19c: ir_cron.py:47-48``).

    Hay un modulo instalandose o actualizandose.
    """


class CompletionStatus:
    """≙ ``CompletionStatus`` (``odoo19c: ir_cron.py:61-64``).

    Los tres desenlaces de una corrida. La fuente comenta *"inherit from
    enum.StrEnum in 3.11"*; aqui el interprete es 3.12, pero se porta con la
    **forma de la fuente** —tres constantes de cadena— para que el simbolo y
    sus valores sean los mismos. Convertirla en ``StrEnum`` seria adelantarse
    a un cambio que la referencia todavia no hizo.
    """
    FULLY_DONE = 'fully done'
    PARTIALLY_DONE = 'partially done'
    FAILED = 'failed'


class ListLogHandler(logging.Handler):
    """≙ ``ListLogHandler`` (``odoo19c: ir_cron.py:67-88``).

    Captura en una lista los registros de log emitidos **dentro del bloque**,
    por contexto. Lo consume ``method_direct_trigger`` para saber si el job
    dejo una excepcion en el log y devolversela a quien disparo.

    Es stdlib pura —``logging`` + ``contextvars``— asi que se porta verbatim:
    no hay nada de Odoo que adaptar.
    """

    def __init__(self, logger, level=logging.NOTSET):
        super().__init__(level)
        self.logger = logger
        self.list_log_handler = contextvars.ContextVar(
            'list_log_handler', default=None)

    def emit(self, record):
        logs = self.list_log_handler.get(None)
        if logs is None:
            return
        record = copy.copy(record)
        logs.append(record)

    def __enter__(self):
        # fija una lista en el contexto actual
        logs = []
        self.list_log_handler.set(logs)
        self.logger.addHandler(self)
        return logs

    def __exit__(self, *exc):
        self.logger.removeHandler(self)

INTERVAL_CHOICES = [
    ('minutes', 'Minutes'),
    ('hours', 'Hours'),
    ('days', 'Days'),
    ('weeks', 'Weeks'),
    ('months', 'Months'),
]


def _add_months(dt, months):
    """Suma ``months`` meses calendario a ``dt``, con *clamping* de día de
    mes (equivalente observable a ``dateutil.relativedelta(months=months)``
    para el caso de overflow de día — p. ej. 31 de enero + 1 mes → último
    día de febrero). Implementado con stdlib porque ``dateutil`` no es
    dependencia del proyecto (ver docstring del módulo)."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


#: ≙ ``_intervalTypes`` (``odoo19c: ir_cron.py:52-58``) — la tabla que
#: traduce ``interval_type`` a un incremento. Se conserva el nombre de la
#: fuente, con su capitalizacion, porque es el simbolo que un porte busca.
#:
#: DIVERGENCIA DE MECANISMO, declarada: la fuente devuelve un
#: ``relativedelta``; ``dateutil`` no es dependencia de este proyecto
#: (verificado: ausente de ``pyproject.toml`` y de la instalacion ``uv``), asi
#: que cada entrada devuelve una funcion que **suma** sobre el ``datetime``.
#: Para ``months`` eso exige ``_add_months``, que replica el *clamping* de dia
#: de mes de ``relativedelta`` con stdlib.
_intervalTypes = {
    'days': lambda dt, interval: dt + timedelta(days=interval),
    'hours': lambda dt, interval: dt + timedelta(hours=interval),
    'weeks': lambda dt, interval: dt + timedelta(days=7 * interval),
    'months': lambda dt, interval: _add_months(dt, interval),
    'minutes': lambda dt, interval: dt + timedelta(minutes=interval),
}


def _resolve_tz(user=None):
    """≙ ``Environment.tz`` (``odoo19c: odoo/orm/environments.py:286-294``).

    El mismo orden que la fuente: ``context['tz']`` primero, la zona del
    usuario despues, UTC de respaldo. Y su misma tolerancia — una zona
    invalida se registra en DEBUG y **no** aborta el cron; degradar a UTC es
    preferible a que una tarea programada muera por un dato de perfil.

    DIVERGENCIA de biblioteca, declarada: la fuente usa ``pytz``; aqui es
    ``zoneinfo`` de la biblioteca estandar, que es lo que Django 6 consume
    (``pytz`` no esta en el arbol — medido). El comportamiento observable es
    el mismo, incluido el cambio de horario de verano, que es la razon de que
    la conversion exista.
    """
    name = get_context().get('tz')
    if not name and user is not None:
        name = getattr(user, 'tz', '') or ''
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            _logger.debug('Zona horaria invalida %r', name, exc_info=True)
    return dt_timezone.utc


def _add_interval(dt, number, interval_type):
    """Avanza ``dt`` por ``number`` unidades de ``interval_type``.

    Es el consumidor de ``_intervalTypes``; existe porque en la fuente esa
    tabla se aplica inline dentro de ``_reschedule_later`` y aqui hace falta
    un punto unico que valide la clave.
    """
    try:
        avanzar = _intervalTypes[interval_type]
    except KeyError:
        raise ValueError(
            f'interval_type desconocido: {interval_type!r}') from None
    return avanzar(dt, number)


class IrCron(models.DefaultGetMixin, models.RecordLoaderMixin,
             models.CheckCompanyMixin, models.Model):
    """``ir.cron`` — registro de horario de una tarea programada + runner.

    El registro de horario (qué ejecutar + cada cuánto + próxima corrida)
    y el runner que hace polling y ejecuta las tareas ``active=True`` con
    ``nextcall`` vencido (``_process_jobs``/``_acquire_one_job``/
    ``_run_job``/``_callback``) viven en la misma clase — igual que en la
    referencia. Ver docstring del módulo para el detalle de qué del runner
    de Odoo se portó y qué se excluyó deliberadamente."""

    # Los cinco atributos de clase que la fuente declara
    # (``odoo19c: ir_cron.py:99-104``). Se portan verbatim y NO sustituyen a
    # su forma Django: ``_description`` convive con ``Meta.verbose_name``,
    # ``_order`` con ``Meta.ordering``. Ver ``atributos-de-clase-de-modelo.md``.
    _name = 'ir.cron'
    _order = 'cron_name, id'
    _description = 'Scheduled Actions'
    _allow_sudo_commands = False
    #: La clave nombra el campo de ESTE arbol, no el de la fuente. Alla es
    #: ``ir_actions_server_id`` porque la FK lleva el sufijo; aqui la FK se
    #: llama ``ir_actions_server`` (decision #141) y ``_inherits`` la sigue,
    #: como ya hacen ``ResUsers`` (``{'res.partner': 'partner'}``) y
    #: ``WebsitePage`` (``{'ir.ui.view': 'view'}``). Hasta hoy este declaraba
    #: el nombre de la fuente, asi que ``ensure_inherits`` no encontraba el
    #: campo y la delegacion nunca se cableaba: la FK no llevaba ``delegate``
    #: y ``_check_inherits`` la rechaza. Ver :ref:`h-api-1052`.
    _inherits = {'ir.actions.server': 'ir_actions_server'}

    #: Las cuatro columnas que el ``LEFT JOIN last_cron_progress`` de
    #: ``_acquire_one_job`` (``odoo19c: ir_cron.py:355-370``) cuelga del job.
    #: En la fuente el job es un ``dict`` y esas claves llegan de la consulta;
    #: aqui es una instancia, asi que se declaran a nivel de CLASE con el
    #: mismo valor que la fuente normaliza (``job[f] = job[f] or 0``). Sin
    #: esto un job no adquirido —el que construye un test o un llamador
    #: directo— no tenia los atributos y ``_process_job`` reventaba.
    progress_id = None
    done_counter = 0
    remaining_counter = 0
    timed_out_counter = 0

    # Enlace de _inherits (Odoo ir_actions_server_id, ir_cron.py:106-108):
    # Many2one required con ondelete='restrict' (≙ PROTECT). NO es herencia
    # multi-tabla — ver el docstring del módulo.
    ir_actions_server = fields.Many2one(
        IrActionsServer, on_delete=models.PROTECT, db_index=True,
        related_name='crons',
        help_text=(
            'Acción que este cron ejecuta (Odoo ir_actions_server_id, '
            '_inherits). El "qué ejecutar" —name, model_name, method_name— '
            'vive ahí y se delega; ir.cron sólo aporta la periodicidad.'
        ),
    )
    interval_number = fields.Integer(
        default=1,
        help_text='Repetir cada x (Odoo interval_number).',
    )
    interval_type = fields.Selection(
        max_length=8, choices=INTERVAL_CHOICES, default='months',
        help_text='Unidad del intervalo (Odoo interval_type).',
    )
    nextcall = fields.Datetime(
        default=timezone.now,
        help_text='Próxima fecha de ejecución planeada (Odoo nextcall).',
    )
    lastcall = fields.Datetime(
        null=True, blank=True,
        help_text='Última ejecución exitosa (Odoo lastcall).',
    )
    priority = fields.Integer(
        default=5,
        help_text=(
            'Prioridad: 0 = más alta, 10 = más baja (Odoo priority, '
            'consumida por el runner diferido para ordenar el polling).'
        ),
    )
    active = fields.Boolean(default=True, help_text='Odoo active.')
    failure_count = fields.Integer(
        default=0,
        help_text=(
            'Fallos consecutivos de este job. Se reinicia al tener exito '
            '(Odoo failure_count).'
        ),
    )
    first_failure_date = fields.Datetime(
        null=True, blank=True,
        help_text=(
            'Primera vez que el cron fallo. Se reinicia al tener exito '
            '(Odoo first_failure_date).'
        ),
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ir_crons',
        help_text=(
            'Usuario de ejecución (Odoo user_id — ahí required con '
            'default=env.user; aquí nullable porque no hay contexto de '
            'request implícito al registrar la tarea). El runner lo aplica '
            'con orm.environments.user_scope, así que get_current_user() '
            'dentro del método invocado lo devuelve. Caveat: IrRule.'
            'eval_context aún no cae a ese usuario — ver docstring del '
            'módulo.'
        ),
    )

    class Meta:
        db_table = 'ir_cron'
        ordering = ['ir_actions_server__name', 'id']
        verbose_name = 'Tarea programada'
        verbose_name_plural = 'Tareas programadas'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(interval_number__gt=0),
                name='ir_cron_interval_number_positivo',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # ---- Campos delegados (≙ _inherits de ir.actions.server) ----
    # Solo lectura, como el resto de delegaciones del árbol (product_product,
    # res_users, mail_mail). Para escribirlos se toca la acción servidor.

    @property
    def name(self):
        """El nombre de la acción (Odoo ``cron_name``, computado desde el
        ``name`` de la ``ir.actions.server`` delegada)."""
        return self.ir_actions_server.name

    @property
    def model_name(self):
        """El modelo técnico objetivo (delegado; Odoo ``model_id``)."""
        return self.ir_actions_server.model_name

    @property
    def method_name(self):
        """El método a invocar (delegado; ocupa el lugar del ``code`` de la
        referencia — ver el docstring de ``ir_actions.py``)."""
        return self.ir_actions_server.method_name

    def _compute_next(self):
        """Calcula el próximo ``nextcall`` avanzando por
        ``interval_number``×``interval_type`` desde el ``nextcall`` actual
        (réplica simplificada de ``_intervalTypes`` de Odoo — ver
        docstring del módulo). NO hace loop "hasta superar now()": esa
        política de recuperación de corridas perdidas es responsabilidad
        del runner diferido (``_reschedule_later`` en Odoo), no del
        registro de horario. Devuelve el valor calculado sin guardarlo —
        el runner decide cuándo persistirlo junto con ``lastcall``."""
        return _add_interval(self.nextcall, self.interval_number, self.interval_type)

    # ---- Runner: adquisición, ejecución y reprogramación de jobs --------
    # (== _acquire_one_job / _run_job / _process_jobs / _callback de Odoo,
    # ver docstring del módulo para el colapso deliberado frente a la
    # referencia.)

    @property
    def cron_name(self):
        """≙ ``_compute_cron_name`` (``odoo19c: ir_cron.py:129-132``).

        La fuente lo declara ``compute='_compute_cron_name', store=True`` —una
        columna materializada— para poder ordenar por ella
        (``_order = 'cron_name, id'``). Aqui es una ``property`` y el orden lo
        da ``Meta.ordering = ['ir_actions_server__name', 'id']``, que produce
        el mismo criterio con un JOIN en vez de una columna duplicada.

        Es el mismo valor que ``name``; los dos existen porque la fuente los
        distingue: ``name`` viene delegado del ``_inherits`` y ``cron_name``
        es su copia materializada.
        """
        return self.ir_actions_server.name

    @classmethod
    def default_get(cls, fields_wanted=None):
        """≙ ``default_get`` (``odoo19c: ir_cron.py:142-148``).

        El cuerpo de la fuente es de dos lineas y hace una sola cosa: mete
        ``default_state='code'`` en el contexto si el llamador no trajo uno, y
        delega. Su comentario lo explica: *"only 'code' state is supported for
        cron job so set it as default"*.

        Ese modo **si** existe aqui: ``'code'`` es una de las seis
        ``IrActionsServer.STATE_CHOICES`` (``ir_actions.py:565``), y ``state``
        llega a ``ir.cron`` por el mismo ``_inherits`` que alla. Asi que se
        porta tal cual, sin adaptacion.

        > **Actualizado (tarea #113).** Este cuerpo declaraba cuatro defaults
        > propios —``interval_number``, ``interval_type``, ``priority``,
        > ``active``— y **no llamaba a ``super()``**, porque no habia base a
        > la que llamar. Los cuatro ya los declara su campo con ``default=``,
        > que es donde la fuente tambien los pone, asi que la base los
        > responde sola; el dict duplicado ademas **pisaba al contexto**, que
        > es justo lo contrario del orden que la fuente fija. Y el docstring
        > decia que el estado *"no aplica"*: era falso, el modo esta portado.
        """
        with context_scope(**({} if get_context().get('default_state')
                              else {'default_state': 'code'})):
            return super().default_get(fields_wanted or [])

    @classmethod
    def _get_ready_sql_condition(cls):
        """≙ ``_get_ready_sql_condition`` (``odoo19c: ir_cron.py:283-294``).

        Listo = ``active`` **y** (su ``nextcall`` vencio **o** tiene un
        disparo pendiente en ``ir_cron_trigger``). La rama del ``OR`` es la
        que este arbol no tenia: sin ella un ``_trigger`` no despertaba nada.

        La fuente lo escribe como ``SQL`` crudo con un subselect; aqui es un
        ``Q`` con ``__in`` sobre el mismo subselect, que el ORM compila a la
        misma forma.
        """
        ahora = timezone.now()
        return models.Q(active=True) & (
            models.Q(nextcall__lte=ahora)
            | models.Q(pk__in=IrCronTrigger.objects
                       .filter(call_at__lte=ahora)
                       .values_list('cron_id', flat=True))
        )

    @classmethod
    def _get_all_ready_jobs(cls, using=DEFAULT_DB_ALIAS):
        """≙ ``_get_all_ready_jobs`` (``odoo19c: ir_cron.py:296-305``).

        Todos los jobs listos, en el orden de la fuente:
        ``ORDER BY failure_count, priority, id`` — el que mas ha fallado va
        **primero**, no ultimo. Es deliberado en la fuente y se conserva: un
        job que falla se reintenta pronto hasta que la desactivacion decide.
        """
        return list(
            cls.objects.using(using)
            .filter(cls._get_ready_sql_condition())
            .order_by('failure_count', 'priority', 'id')
        )

    @staticmethod
    def _check_version(using=DEFAULT_DB_ALIAS):
        """≙ ``_check_version`` (``odoo19c: ir_cron.py:239-252``).

        La fuente compara ``ir_module_module.latest_version`` de ``base``
        contra la version del codigo y levanta ``BadVersion`` si difieren.

        DIVERGENCIA DE MECANISMO, medida y declarada: aqui los "modulos" son
        apps de Django versionadas por **migraciones**, no filas con version
        propia. El equivalente exacto de "el codigo espera un schema que la
        base no tiene" es una migracion sin aplicar, y eso lo sabe el propio
        Django. Se porta contra ese mecanismo.
        """
        executor = MigrationExecutor(connection)
        pendientes = executor.migration_plan(
            executor.loader.graph.leaf_nodes())
        if pendientes:
            raise BadVersion()

    @staticmethod
    def _check_modules_state(jobs, using=DEFAULT_DB_ALIAS):
        """≙ ``_check_modules_state`` (``odoo19c: ir_cron.py:254-281``).

        La fuente busca filas con ``state LIKE 'to %'`` —modulo instalandose o
        actualizandose— y levanta ``BadModuleState`` salvo que los jobs lleven
        atascados mas de ``MAX_FAIL_TIME``, en cuyo caso fuerza
        ``reset_modules_state``.

        DIVERGENCIA DE MECANISMO, declarada: ``ir.module.module`` esta portado
        aqui (``ir_module.py``) pero **sin** los estados transitorios ``to
        install`` / ``to upgrade`` / ``to remove``, porque en este arbol una
        app se instala aplicando migraciones y no hay una fase en que la fila
        quede a medias. Sin esos estados no hay nada que consultar: el metodo
        conserva la firma y la logica de umbral, y su consulta devuelve cero
        por construccion.

        La mitad que SI se porta es la del umbral, porque es la que decide:
        con jobs atascados mas de ``MAX_FAIL_TIME`` la fuente deja de
        bloquear. Aqui esa rama es inalcanzable mientras ``cambios`` sea cero;
        se declara asi en vez de omitirla, para que el dia que ``ir.module``
        gane sus estados el metodo ya este completo.

        **Veredicto de la tarea #46 (2026-08-27): los estados transitorios NO
        se portan, y la divergencia queda cerrada.** La tarea pedia decidir si
        este arbol tiene una fase en que la fila queda a medias. Medido: no la
        tiene. ``_derive_state`` (``update_module_list``) es funcion pura de
        ``(manifest, INSTALLED_APPS)``, ``INSTALLED_APPS`` se congela en
        ``django.setup()`` y el comando escribe el estado final dentro de una
        transaccion — no hay escritor incremental que pueda dejar un ``to %``.

        Y el peligro que la fuente protege —no correr crons mientras el schema
        muta— **si esta cubierto en este arbol**, por el hermano
        ``_check_version``: una migracion sin aplicar levanta ``BadVersion``.
        No falta proteccion; el mismo riesgo se detecta por otra senal, y esa
        senal ya esta portada. Implementar estados que nadie puede escribir
        seria inventar una capacidad.

        **La tercera rama de la fuente NO se porta, y se declara aqui.** Tras
        superar el umbral la fuente llama a ``reset_modules_state(cr.dbname)``
        (``odoo19c: ir_cron.py:279-281``) para limpiar los estados zombis. Aqui
        no hay estado que resetear —es la misma ausencia de arriba—, asi que el
        porte llega hasta *dejar de bloquear* y para. Se nombra en vez de
        omitirse: un simbolo de la fuente que no aparece ni en el codigo ni en
        la declaracion es porte parcial silencioso.

        Cobertura: ``tests/unit/base/test_ir_cron_guardas_de_arranque.py``
        ejercita la rama del umbral **inyectando a mano** la fila que el arbol
        no sabe producir, que es la unica forma de saber si la logica del
        umbral funciona o es decorado. Control con la guarda anulada: caen 2 de
        6, los dos que esperan bloqueo.
        """
        # Medido: ``IrModule.STATES`` declara TRES estados —``uninstallable``,
        # ``uninstalled``, ``installed``— y ninguno empieza con ``'to '``. La
        # consulta es fiel a la fuente y da cero por construccion; se escribe
        # asi, y no como un ``return`` seco, para que gane conducta el dia que
        # ``ir.module`` porte sus estados transitorios.
        cambios = (IrModule.objects.using(using)
                   .filter(state__startswith='to ').count())
        if not cambios:
            return
        if not jobs:
            raise BadModuleState()
        # max(nextcall, write_date) evita reiniciar el estado de modulos
        # durante una instalacion en curso, como declara la fuente.
        mas_viejo = min(
            max(job.nextcall, getattr(job, 'write_date', None) or job.nextcall)
            for job in jobs)
        if timezone.now() - mas_viejo < MAX_FAIL_TIME:
            raise BadModuleState()

    def _notify_admin(self, message):
        """≙ ``_notify_admin`` (``odoo19c: ir_cron.py:386-395``).

        Docstring de la fuente, verbatim: *"The base implementation of this
        method does nothing. It is supposed to be overridden with some actual
        communication mechanism."* Se porta con esa misma conducta —un
        ``warning`` al log— para que quien la sobrescriba encuentre el gancho.
        """
        _logger.warning(message)

    @classmethod
    def _acquire_one_job(cls, job_id, using=DEFAULT_DB_ALIAS, *, include_not_ready=False):
        """Adquiere para actualización el job ``job_id`` sin bloquear si
        otro worker ya lo tiene (== ``_acquire_one_job`` de Odoo,
        ir_cron.py:308-388). ``FOR NO KEY UPDATE SKIP LOCKED`` vía
        ``select_for_update(skip_locked=True, no_key=True)`` — la misma
        capacidad de PostgreSQL que la referencia usa (ADR-028), no un lock
        de aplicación en Python. Debe llamarse dentro de una transacción
        (``transaction.atomic``) que el caller cierra tras ``_run_job()``;
        Django lo exige (``TransactionManagementError`` si no).

        ``include_not_ready=True`` (== Odoo ``method_direct_trigger``)
        adquiere el job aunque no esté listo todavía — no usado por el
        polling normal, disponible para un disparo manual futuro.

        Devuelve la instancia adquirida, o ``None`` si otro worker ya la
        tenía tomada o si dejó de estar lista entre el listado y la
        adquisición."""
        qs = (
            cls.objects.using(using)
            .select_for_update(skip_locked=True, no_key=True)
            .filter(pk=job_id)
        )
        if not include_not_ready:
            qs = qs.filter(cls._get_ready_sql_condition())
        job = qs.first()
        if job is None:
            return None

        # El ``LEFT JOIN last_cron_progress`` de la fuente
        # (``odoo19c: ir_cron.py:355-370``): el ultimo avance de este cron,
        # colgado del job. La fuente lo trae en la misma consulta porque su
        # cursor devuelve un dict; aqui es un atributo del objeto, con el
        # mismo ``ORDER BY id DESC LIMIT 1`` y el mismo ``or 0`` que la
        # fuente aplica a las tres columnas.
        ultimo = (IrCronProgress.objects.using(using)
                  .filter(cron_id=job.pk).order_by('-id').first())
        job.progress_id = ultimo.pk if ultimo is not None else None
        job.done_counter = (ultimo.done if ultimo is not None else 0) or 0
        job.remaining_counter = (
            ultimo.remaining if ultimo is not None else 0) or 0
        job.timed_out_counter = (
            ultimo.timed_out_counter if ultimo is not None else 0) or 0
        return job

    def _callback(self):
        """Invoca el método delegado por la acción servidor (==
        ``_callback`` de Odoo, ir_cron.py:671-696). La referencia llama
        ``ir.actions.server.browse(id).run()``; en este árbol
        ``IrActionsServer.run()`` levanta ``NotImplementedError`` a
        propósito (el modo ``code`` no se evalúa, ver ``ir_actions.py``).
        La alternativa sancionada por este proyecto
        (``ir_actions.py:436-444``) es ``method_name``/``model_name``: el
        runner —este método— la invoca directamente, sin pasar por
        ``.run()``. Deja escapar la excepción del método invocado; quien la
        atrapa es ``_run_job()``.

        Corre bajo ``user_scope(self.user_id)`` — el equivalente del
        ``env = api.Environment(job_cr, job['user_id'], ...)`` de la
        referencia (ir_cron.py:481-483). ``user_id`` es el atributo de la FK
        de Django (el id crudo), no una consulta extra. Con ``user`` nulo el
        scope se fija a ``None``, que es el estado que ya tiene el proceso
        worker: poner el contextmanager de todos modos mantiene un solo
        camino y garantiza que el valor previo se **restaure** al salir, sin
        filtrar el usuario de un job al siguiente.

        **Y bajo ``context_scope``, que es la otra mitad de ese
        ``api.Environment``.** La referencia le pasa un dict —``{'lastcall':
        job['lastcall'], 'cron_id': job['id'], 'cron_end_time': …}``
        (ir_cron.py:481-486)— y sus callbacks lo leen de ``self.env.context``.
        Aquí el espejo es ``orm.environments.context_scope``, así que las dos
        claves que tienen lector se ponen igual. ``cron_end_time`` **no** se
        pone: pertenece al bucle de progreso por lotes que ``_run_job``
        declara no portado, y sembrarla sin ese bucle sería declarar una
        capacidad inexistente.

        Sin esto, ``ir.autovacuum._run_vacuum_cleaner`` —cuyo guard exige el
        ``cron_id``, como en la fuente— era **inalcanzable desde el cron**:
        ``method()`` no lleva argumentos. Ver :ref:`h-api-752`."""
        model = apps.get_model(self.model_name)
        method = getattr(model, self.method_name)
        with user_scope(self.user_id), context_scope(
                cron_id=self.pk, lastcall=self.lastcall):
            method()

    @classmethod
    def _process_job(cls, job, using=DEFAULT_DB_ALIAS):
        """≙ ``_process_job`` (``odoo19c: ir_cron.py:398-455``).

        Es el arbitro: decide si el job siquiera se corre, lo corre, y decide
        como se reprograma segun el desenlace. Su docstring en la fuente
        enumera los tres:

        - ``fully done`` — se reprograma por su intervalo normal;
        - ``partially done`` — se reprograma **ASAP**, para que siga en cuanto
          los demas listos hayan tenido su turno;
        - ``failed`` — se reprograma por el intervalo, y la desactivacion la
          decide ``_update_failure_count`` con sus dos umbrales.

        La guarda del principio es la que este arbol no tenia: si la pasada
        anterior se quedo sin tiempo ``CONSECUTIVE_TIMEOUT_FOR_FAILURE`` veces
        **y** no hizo nada, el job se declara fallido **sin correrlo**. Sin
        ella un job que cuelga se reintenta para siempre.
        """
        job._clear_schedule(job)
        failed_by_timeout = (
            job.timed_out_counter >= CONSECUTIVE_TIMEOUT_FOR_FAILURE
            and not job.done_counter
        )

        if not failed_by_timeout:
            status = cls._run_job(job)
        else:
            status = CompletionStatus.FAILED
            if job.progress_id is not None:
                IrCronProgress.objects.filter(pk=job.progress_id).update(
                    timed_out_counter=0)
            _logger.error('Job %r (%s) se quedo sin tiempo',
                          job.cron_name, job.pk)

        job._update_failure_count(job, status)

        if status in (CompletionStatus.FULLY_DONE, CompletionStatus.FAILED):
            job._reschedule_later(job)
        elif status == CompletionStatus.PARTIALLY_DONE:
            job._reschedule_asap(job)
        else:
            raise RuntimeError(f'inalcanzable {status=}')

    @classmethod
    def _run_job(cls, job):
        """≙ ``_run_job`` (``odoo19c: ir_cron.py:456-568``).

        Corre el callback **en bucle** hasta que el job se declara completo,
        agota ``MIN_RUNS_PER_JOB`` vueltas, o agota ``MIN_TIME_PER_JOB``
        segundos. Es lo que convierte un job largo en varias pasadas cortas en
        vez de una que bloquea al resto.

        El ``match`` de la fuente se porta con su forma y sus seis ramas, cada
        una con su comentario: distinguen "fallo sin avanzar nada" (FAILED) de
        "fallo habiendo comiteado avance" (sigue), y "termino" de "quedan
        registros" (PARTIALLY_DONE).

        DIVERGENCIA declarada: la fuente abre un **cursor propio**
        (``cls.pool.cursor()``) para que el job comitee sin tocar la
        transaccion del planificador. Aqui el job corre en la conexion en
        curso; ``_commit_progress`` comitea sobre ella. La consecuencia es
        real y se declara: un ``rollback`` del llamador se lleva el avance
        comiteado, cosa que en la fuente no pasaria. Sucesor: tarea #42.
        """
        timed_out_counter = job.timed_out_counter
        start_time = time.monotonic()
        status = None
        loop_count = 0
        done = remaining = 0
        _logger.info('Job %r (%s) arranca', job.cron_name, job.pk)

        cron_end_time = start_time + MIN_TIME_PER_JOB
        while status is None and (loop_count < MIN_RUNS_PER_JOB
                                  or time.monotonic() < cron_end_time):
            cron, progress = job._add_progress(
                timed_out_counter=timed_out_counter)

            success = False
            try:
                with context_scope(ir_cron_progress_id=progress.pk,
                                   cron_end_time=cron_end_time):
                    cron._callback()
                success = True
            except Exception:  # noqa: BLE001 — un job no tumba al planificador
                _logger.exception(
                    'Job %r (%s) fallo en su accion servidor #%s',
                    job.cron_name, job.pk, job.ir_actions_server_id)
            finally:
                progress.refresh_from_db()
                done, remaining = progress.done, progress.remaining
                match (success, done, remaining):
                    case (False, d, r) if d and r:
                        # Fallo, pero alcanzo a comitear avance. Con suerte
                        # el fallo es temporal.
                        pass
                    case (False, _, _):
                        # Fallo sin comitear nada esta vez: fallido, aunque
                        # hubiera avanzado en una vuelta previa.
                        status = CompletionStatus.FAILED
                    case (True, _, 0):
                        # Termino: o no usa la API de progreso, o dijo que no
                        # le queda nada.
                        status = CompletionStatus.FULLY_DONE
                        if progress.deactivate:
                            job.active = False
                    case (True, 0, _) if loop_count == 0:
                        # Supo que quedan registros pero no proceso ninguno.
                        status = CompletionStatus.PARTIALLY_DONE
                        _logger.warning('Job %r (%s) no proceso ningun registro',
                                        job.cron_name, job.pk)
                    case (True, 0, _):
                        # Avanzo en una vuelta previa, en esta no.
                        status = CompletionStatus.PARTIALLY_DONE
                    case (True, _, _):
                        # Proceso algunos pero no todos. Sigue el bucle.
                        pass

                loop_count += 1
                IrCronProgress.objects.filter(pk=progress.pk).update(
                    timed_out_counter=0)
                timed_out_counter = 0
                _logger.debug(
                    'Job %r (%s) proceso %s registros, quedan %s',
                    job.cron_name, job.pk, done, remaining)

        status = status or CompletionStatus.PARTIALLY_DONE
        _logger.info(
            'Job %r (%s) %s (#vueltas %s; hechos %s; quedan %s; duro %.2fs)',
            job.cron_name, job.pk, status, loop_count, done, remaining,
            time.monotonic() - start_time)
        return status

    def method_direct_trigger(self, using=DEFAULT_DB_ALIAS):
        """Corre este cron **ahora**, en el hilo actual (≙
        ``method_direct_trigger``, ``odoo19c: odoo/addons/base/models/
        ir_cron.py:150-184``).

        Es el disparo bajo demanda de la referencia, y su forma importa: el
        job *se corre como lo correría el planificador*, no por un camino
        paralelo. Por eso adquiere el mismo lock de fila y pasa por
        ``_run_job`` → ``_callback``, que es lo que pone el ``user_scope``
        del usuario del cron y su ``context_scope``. Un llamador que
        invocara el método del job directamente **no** tendría ninguna de
        las dos cosas, y un guard como el de
        ``auto_backup.DbBackup._take_dump`` —que exige ser el usuario del
        cron— lo rechazaría.

        ``include_not_ready=True`` es lo que separa este camino del polling:
        adquiere el job aunque su ``nextcall`` no haya vencido. El parámetro
        ya estaba en ``_acquire_one_job`` declarado para este uso; aquí gana
        su consumidor.

        DIVERGENCIA de transacción, declarada: la fuente corre el job en un
        **cursor nuevo** y por eso antepone ``env.invalidate_all(flush=True)``
        —su caché de entorno quedaría rancia al escribir la otra transacción—.
        Aquí el job corre en la misma conexión, dentro de un
        ``transaction.atomic``, así que no hay dos cursores que reconciliar ni
        caché de entorno que invalidar. La consecuencia se declara porque es
        real: si el callback falla y la transacción del llamador aborta
        después, la reprogramación de ``_reschedule_later`` se va con ella,
        cosa que en la fuente no pasaría.

        DIVERGENCIA de retorno, declarada: la fuente devuelve ``True`` o un
        dict ``ir.actions.client`` con la excepción serializada para que su
        cliente la muestre. Aquí no hay canal de acción de cliente —
        ``IrActionsServer.run()`` levanta ``NotImplementedError`` a
        propósito—, así que devuelve ``True`` a secas: el fallo del callback
        ya lo registra ``_run_job`` en el log, y quien dispara lee el
        resultado en los datos que el job escribió.

        La guarda de acceso de la fuente (``check_access('write')``) tampoco
        se transcribe: aquí la autorización es por capacidad y vive en el
        gate de la vista que llama, no en el modelo (DEC-11).

        :raises UserError: si el job ya lo tiene tomado otro worker.
        """
        with transaction.atomic(using=using):
            job = type(self)._acquire_one_job(
                self.pk, using=using, include_not_ready=True)
            if job is None:
                raise UserError(
                    "El trabajo %r ya se está ejecutando" % (self.name,))
            # ``ListLogHandler`` es de la fuente (``ir_cron.py:167-168``) y su
            # razon de ser es esta: capturar el log de ERROR de la corrida para
            # saber si dejo una excepcion. La fuente devuelve con ella un
            # ``ir.actions.client`` para que su cliente la muestre; aqui no hay
            # ese canal, asi que se registra el resumen y se devuelve True —
            # divergencia declarada abajo.
            with ListLogHandler(_logger, logging.ERROR) as capture:
                type(self)._process_job(job, using=using)
            registro = next(
                (lr for lr in capture if getattr(lr, 'exc_info', None)), None)
            if registro is not None:
                _logger.error(
                    'El disparo directo del job %r (%s) dejo una excepcion en '
                    'el log; el resultado se lee en los datos que escribio.',
                    self.name, self.pk)
        return True

    # ---- Disparo puntual (≙ _trigger / _trigger_list / _notifydb) ------

    def _trigger(self, at=None):
        """≙ ``_trigger`` (``odoo19c: ir_cron.py:734-762``).

        Docstring de la fuente: *"Schedule a cron job to be executed soon
        independently of its ``nextcall`` field value."* Admite un
        ``datetime``, un iterable de ellos, o nada —que significa ahora—.

        La implementacion real vive en ``_trigger_list``, que es el metodo que
        la fuente recomienda sobrescribir.

        :return: los disparos creados.
        """
        if at is None:
            at_list = [timezone.now()]
        elif isinstance(at, datetime):
            at_list = [at]
        else:
            at_list = list(at)
            assert all(isinstance(x, datetime) for x in at_list)
        return self._trigger_list(at_list)

    def _trigger_list(self, at_list):
        """≙ ``_trigger_list`` (``odoo19c: ir_cron.py:764-792``).

        Si el cron esta **inactivo**, descarta los disparos que ya vencieron:
        no despertarian nada y solo dejarian basura para el recolector. Los
        futuros si se guardan, porque el cron puede reactivarse antes.
        """
        ahora = timezone.now()
        if not self.active:
            at_list = [x for x in at_list if x > ahora]
        if not at_list:
            return IrCronTrigger.objects.none()

        triggers = IrCronTrigger.objects.bulk_create(
            [IrCronTrigger(cron=self, call_at=x) for x in at_list])
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug('Job %r (%s) correra en %s', self.name, self.pk,
                          ', '.join(map(str, at_list)))
        if min(at_list) <= ahora:
            self._notifydb()
        return triggers

    @classmethod
    def _notifydb(cls):
        """≙ ``_notifydb`` (``odoo19c: ir_cron.py:793-801``).

        Despierta a los workers con ``NOTIFY`` de PostgreSQL. Verificado en el
        motor de esta sesion: ``pg_notify`` existe en ``pg_proc``
        (PostgreSQL 16.13).

        DIVERGENCIA declarada: la fuente abre una conexion a la base
        ``postgres`` para emitir el ``NOTIFY`` **fuera** de la transaccion del
        cron, y lo hace en ``postcommit``. Aqui se emite en la conexion en
        curso: Django no expone un gancho ``postcommit`` con la forma de la
        fuente, y ``transaction.on_commit`` es su equivalente, que quien
        llama puede envolver. El efecto observable —el canal recibe el
        aviso— es el mismo; lo que cambia es que un ``rollback`` posterior se
        lo lleva. Sucesor: tarea #42.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT {connection.ops.quote_name(NOTIFY_FUNCTION)}'
                f'(%s, %s)', ['cron_trigger', connection.settings_dict['NAME']])
        _logger.debug('workers de cron notificados')

    # ---- API de progreso (≙ _add_progress / _notify_progress /
    #      _commit_progress) ------------------------------------------------

    def _add_progress(self, *, timed_out_counter=None):
        """≙ ``_add_progress`` (``odoo19c: ir_cron.py:802-822``).

        Crea el registro de avance de esta pasada y lo mete en el contexto.

        El ``timed_out_counter + 1`` es de la fuente y tiene su comentario:
        *"we use timed_out_counter + 1 so that if the current execution times
        out, the counter already takes it into account"* — el contador se
        adelanta para que un proceso muerto deje su rastro sin poder
        escribirlo.

        :return: el par ``(cron, progress)``.
        """
        progress = IrCronProgress.objects.create(
            cron=self, remaining=0, done=0,
            timed_out_counter=(0 if timed_out_counter is None
                               else timed_out_counter + 1),
        )
        return self, progress

    def _notify_progress(self, *, done, remaining, deactivate=False):
        """≙ ``_notify_progress`` (``odoo19c: ir_cron.py:823-844``).

        DEPRECADO en la fuente desde 19: *"Since 19.0, use _commit_progress"*.
        Se porta con esa marca —y no se omite— porque un addon adaptado de 18
        puede llamarlo, y su ausencia lo dejaria sin diagnostico.
        """
        contexto = get_context()
        progress_id = contexto.get('ir_cron_progress_id')
        if not progress_id:
            return
        if done < 0 or remaining < 0:
            raise ValueError(
                '`done` y `remaining` deben ser enteros positivos.')
        progress = IrCronProgress.objects.filter(pk=progress_id).first()
        if progress is None:
            return
        assert progress.cron_id == contexto.get('cron_id'), \
            'Avance sobre el cron_id equivocado'
        progress.remaining = remaining
        progress.done = done
        progress.deactivate = deactivate
        progress.save(update_fields=['remaining', 'done', 'deactivate'])

    @staticmethod
    def _commit_if_possible():
        """Comitea si el llamador no esta dentro de un ``atomic``.

        DIVERGENCIA DE MECANISMO, medida y declarada: la fuente comitea con
        ``self.env.cr.commit()`` sobre su propio cursor, y ahi siempre se
        puede. Django **prohibe** ``transaction.commit()`` dentro de un bloque
        ``atomic`` —``TransactionManagementError: This is forbidden when an
        'atomic' block is active``, medido— y la suite corre cada caso dentro
        de uno.

        La conducta que se conserva es la que importa: fuera de un ``atomic``
        el avance se persiste de verdad, que es para lo que existe
        ``_commit_progress``. Dentro de uno el ``save()`` ya escribio y el
        commit lo hara quien abrio el bloque.
        """
        if transaction.get_connection().in_atomic_block:
            return
        transaction.commit()

    @classmethod
    def _commit_progress(cls, processed=0, *, remaining=None,
                         deactivate=False):
        """≙ ``_commit_progress`` (``odoo19c: ir_cron.py:845-888``).

        La API que un metodo de cron llama para decir "llevo N hechos" y
        ceder el turno con el trabajo ya comiteado.

        Fuera de un cron —sin ``ir_cron_progress_id`` en contexto— solo
        comitea y devuelve ``inf``, que es lo que la fuente hace: asi el
        mismo metodo sirve llamado a mano.

        :return: los segundos que le quedan a esta corrida.
        """
        contexto = get_context()
        progress = IrCronProgress.objects.filter(
            pk=contexto.get('ir_cron_progress_id')).first()
        if progress is None:
            # No se llamo desde un cron: solo comitea.
            cls._commit_if_possible()
            return float('inf')
        assert processed >= 0, 'processed debe ser positivo'
        assert (remaining or 0) >= 0, 'remaining debe ser positivo'
        assert progress.cron_id == contexto.get('cron_id'), \
            'Avance sobre el cron_id equivocado'
        if remaining is None:
            remaining = max(progress.remaining - processed, 0)
        progress.remaining = remaining
        progress.done = progress.done + processed
        campos = ['remaining', 'done']
        if deactivate:
            progress.deactivate = True
            campos.append('deactivate')
        progress.save(update_fields=campos)
        cls._commit_if_possible()
        return max(contexto.get('cron_end_time', float('inf'))
                   - time.monotonic(), 0)

    # ---- Reprogramacion y conteo de fallos ------------------------------

    def _clear_schedule(self, job=None):
        """≙ ``_clear_schedule`` (``odoo19c: ir_cron.py:622-632``).

        Docstring de la fuente: *"Remove triggers for the given job."* Borra
        los disparos **ya vencidos**, no los futuros: un disparo programado
        para mañana sobrevive a la corrida de hoy.
        """
        ahora = timezone.now().replace(microsecond=0)
        cron_id = job.pk if job is not None else self.pk
        IrCronTrigger.objects.filter(
            cron_id=cron_id, call_at__lte=ahora).delete()

    def _reschedule_later(self, job=None):
        """≙ ``_reschedule_later`` (``odoo19c: ir_cron.py:634-658``).

        Avanza ``nextcall`` por el intervalo hasta superar ahora, y escribe
        ``lastcall``. El bucle es de la fuente: un cron parado una semana no
        dispara siete veces seguidas al volver.

        **La suma es en la zona del usuario**, como en la fuente: convierte,
        suma, y vuelve a UTC. El comentario de la fuente dice por que, y es la
        razon entera de que el paso exista:

            When adding a day or more, the user may want to keep the same hour
            each day. The interval won't be fixed, but the hour will stay the
            same, even when changing DST.

        Un cron diario a las 09:00 en ``America/Mexico_City`` seguiria a las
        09:00 tras el cambio de horario; sumando en UTC pasaria a las 08:00 o
        las 10:00, y ahi se quedaria. La zona se resuelve con ``_resolve_tz``,
        que es ``Environment.tz`` de la fuente: ``context['tz']`` primero, la
        del usuario del cron despues, UTC de respaldo.
        """
        job = job if job is not None else self
        ahora = timezone.now().replace(microsecond=0)
        nextcall = job.nextcall
        zone = _resolve_tz(job.user)
        while nextcall <= ahora:
            nextcall = _add_interval(
                nextcall.astimezone(zone), job.interval_number,
                job.interval_type).astimezone(dt_timezone.utc)
        type(self).objects.filter(pk=job.pk).update(
            nextcall=nextcall, lastcall=ahora)
        job.nextcall = nextcall
        job.lastcall = ahora

    def _reschedule_asap(self, job=None):
        """≙ ``_reschedule_asap`` (``odoo19c: ir_cron.py:659-669``).

        Docstring de la fuente: *"Reschedule the job to be executed ASAP,
        after the other cron jobs had a chance to run."* Un disparo con la
        hora actual: entra en la cola de listos y espera su turno, sin
        adelantarse a los demas.
        """
        job = job if job is not None else self
        ahora = timezone.now().replace(microsecond=0)
        IrCronTrigger.objects.create(cron_id=job.pk, call_at=ahora)

    def _update_failure_count(self, job, status):
        """≙ ``_update_failure_count`` (``odoo19c: ir_cron.py:570-620``).

        Los DOS umbrales de la fuente, y son conjuncion, no disyuncion: el
        cron se desactiva cuando lleva ``MIN_FAILURE_COUNT_BEFORE_DEACTIVATION``
        fallos **y** el primero es de hace mas de
        ``MIN_DELTA_BEFORE_DEACTIVATION``. Un job que falla cinco veces en un
        minuto NO se desactiva; uno que falla cinco veces en dos semanas si.

        Con cualquier otro desenlace el contador y la fecha se reinician.
        """
        ahora = timezone.now().replace(microsecond=0)
        if status == CompletionStatus.FAILED:
            failure_count = job.failure_count + 1
            first_failure_date = job.first_failure_date or ahora
            active = job.active
            if (failure_count >= MIN_FAILURE_COUNT_BEFORE_DEACTIVATION
                    and first_failure_date + MIN_DELTA_BEFORE_DEACTIVATION
                    < ahora):
                failure_count = 0
                first_failure_date = None
                active = False
                self._notify_admin(
                    'El cron %r (%s) se desactivo tras fallar %s veces. Hay '
                    'mas informacion en el log del servidor alrededor de %s.'
                    % (job.cron_name, job.pk,
                       MIN_FAILURE_COUNT_BEFORE_DEACTIVATION, ahora))
        else:
            failure_count = 0
            first_failure_date = None
            active = job.active

        type(self).objects.filter(pk=job.pk).update(
            failure_count=failure_count,
            first_failure_date=first_failure_date,
            active=active,
        )
        job.failure_count = failure_count
        job.first_failure_date = first_failure_date
        job.active = active

    # ---- Las dos acciones de apertura (≙ action_open_*) ------------------

    def action_open_parent_action(self):
        """≙ ``action_open_parent_action`` (``odoo19c: ir_cron.py:889-891``).

        Delega en la accion servidor, igual que la fuente. El bloqueo que
        este metodo declaraba —``IrActionsServer`` sin campo ``parent``— se
        cerro: el campo esta portado en ``ir_actions.py`` con el
        ``ondelete='cascade'`` y el indice de la fuente.
        """
        return self.ir_actions_server.action_open_parent_action()

    def action_open_scheduled_action(self):
        """≙ ``action_open_scheduled_action`` (``odoo19c: ir_cron.py:892-894``).

        Delega igual. El inverso que la fuente llama ``ir_cron_ids`` es aqui
        el ``related_name='crons'`` de la FK de este mismo modelo, asi que
        siempre existio — lo que faltaba era el metodo del otro lado.
        """
        return self.ir_actions_server.action_open_scheduled_action()

    @classmethod
    def _process_jobs(cls, using=DEFAULT_DB_ALIAS):
        """≙ ``_process_jobs`` (``odoo19c: ir_cron.py:185-213``).

        El punto de entrada del planificador: verifica version y estado de
        modulos, lista los listos, y delega el bucle en
        ``_process_jobs_loop``. Las excepciones de las dos guardas se atrapan
        aqui con su ``warning``, igual que la fuente, para que una base en
        estado raro no tumbe al worker.

        Devuelve el numero de jobs procesados, que es divergencia declarada:
        la fuente devuelve ``None`` y el conteo lo consume el subcomando
        ``cron`` de este arbol para su salida.
        """
        try:
            cls._check_version(using=using)
            jobs = cls._get_all_ready_jobs(using=using)
            if not jobs:
                return 0
            cls._check_modules_state(jobs, using=using)
            return cls._process_jobs_loop(
                using=using, job_ids=[job.pk for job in jobs])
        except BadVersion:
            _logger.warning(
                'Se omite la base %s: su version de base no coincide.',
                connection.settings_dict['NAME'])
        except BadModuleState:
            _logger.warning(
                'Se omite la base %s por modulos a instalar/actualizar/quitar.',
                connection.settings_dict['NAME'])
        except ProgrammingError:
            raise
        except Exception:  # noqa: BLE001 — la fuente atrapa igual de ancho
            _logger.warning('Excepcion en el cron:', exc_info=True)
        return 0

    @classmethod
    def _process_jobs_loop(cls, using=DEFAULT_DB_ALIAS, *, job_ids=()):
        """≙ ``_process_jobs_loop`` (``odoo19c: ir_cron.py:215-237``).

        Docstring de la fuente: *"The `cron_cr` is used to lock the currently
        processed job and relased by committing after each job."* Aqui el
        equivalente del commit por job es un ``transaction.atomic`` por
        iteracion, que suelta el lock de fila al salir.

        El ``TransactionRollbackError`` que la fuente atrapa es un error de
        serializacion cuando otro worker comiteo el ``nextcall`` justo antes;
        su equivalente en este stack es ``OperationalError``, que psycopg
        levanta para esa familia.

        Devuelve el numero de jobs procesados (adquiridos y corridos, con
        exito o con fallo — lo que no cuenta es un job que otro worker ya
        tenia tomado).
        """
        procesados = 0
        for job_id in job_ids:
            try:
                with transaction.atomic(using=using):
                    job = cls._acquire_one_job(job_id, using=using)
                    if job is None:
                        _logger.debug(
                            'el job %s lo esta procesando otro worker, se omite',
                            job_id)
                        continue
                    _logger.debug('job %s adquirido', job_id)
                    cls._process_job(job, using=using)
            except OperationalError:
                _logger.debug(
                    'el job %s lo proceso otro worker, se omite', job_id)
                continue
            procesados += 1
            _logger.debug('job %s actualizado y liberado', job_id)
        return procesados

    # ---- Escritura: create / write / unlink / toggle de la referencia ----

    def save(self, *args, **kwargs):
        """≙ ``create`` (``odoo19c: ir_cron.py:134-140``) y ``write``
        (``:696-709``).

        Django no separa las dos operaciones; el discriminador es
        ``self._state.adding``, igual que en ``ir_sequence.py``.

        - al **crear**, la fuente fija ``vals['usage'] = 'ir_cron'`` en la
          accion servidor delegada, que es lo que la distingue de una accion
          suelta;
        - al **escribir**, la fuente toma ``lock_for_update`` y levanta
          ``UserError`` si el job esta corriendo. Aqui el equivalente es
          ``select_for_update(nowait=True)``, que falla en vez de esperar.
          Sin ese candado, editar el intervalo de un cron en plena corrida
          producia una escritura que la corrida pisaba al reprogramar.

        Las dos ramas de la fuente terminan igual: si
        ``NOTIFY_CRON_CHANGES`` esta puesta, avisan a los workers por el
        canal. La fuente lo registra en ``cr.postcommit``; aqui es
        ``transaction.on_commit``, que es su equivalente en este ORM.

        La condicion de escritura de la fuente es
        ``'nextcall' in vals or vals.get('active')``. Aqui ``vals`` es
        ``update_fields``: cuando no se pasa, Django escribe **todos** los
        campos, asi que ``nextcall`` esta en la escritura y la condicion se
        cumple — no es una aproximacion laxa, es la traduccion exacta.
        """
        creating = self._state.adding
        campos = set(kwargs.get('update_fields') or ())
        if not creating:
            try:
                with transaction.atomic():
                    list(type(self).objects
                         .select_for_update(nowait=True).filter(pk=self.pk))
            except (OperationalError, LockError):
                raise UserError(
                    'El registro no se puede modificar ahora mismo: esta '
                    'tarea programada se esta ejecutando. Intente de nuevo '
                    'en unos minutos.'
                ) from None
        resultado = super().save(*args, **kwargs)
        if creating and self.ir_actions_server_id:
            IrActionsServer.objects.filter(
                pk=self.ir_actions_server_id).update(usage='ir_cron')
        if NOTIFY_CRON_CHANGES:
            cambia_agenda = creating or not campos or 'nextcall' in campos \
                or ('active' in campos and self.active)
            if cambia_agenda:
                transaction.on_commit(type(self)._notifydb)
        return resultado

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` via ``_unlink_unless_running``
        (``odoo19c: ir_cron.py:710-720``).

        La fuente lo declara ``@api.ondelete(at_uninstall=False)``: un gancho
        que corre antes de borrar y rehusa si el job esta corriendo. Aqui el
        gancho es este ``delete()``, que llama al mismo guard.
        """
        self._unlink_unless_running()
        return super().delete(*args, **kwargs)

    def _unlink_unless_running(self):
        """≙ ``_unlink_unless_running`` (``odoo19c: ir_cron.py:710-720``).

        Toma el candado de fila sin esperar; si no lo consigue, el job esta
        corriendo y el borrado se rehusa con el mensaje de la fuente.
        """
        try:
            with transaction.atomic():
                list(type(self).objects
                     .select_for_update(nowait=True).filter(pk=self.pk))
        except (OperationalError, LockError):
            raise UserError(
                'El registro no se puede modificar ahora mismo: esta tarea '
                'programada se esta ejecutando. Intente de nuevo en unos '
                'minutos.'
            ) from None

    def toggle(self, model, domain):
        """≙ ``toggle`` (``odoo19c: ir_cron.py:721-733``).

        Activa el cron si el dominio dado tiene al menos un registro, y lo
        desactiva si no. Es como un addon enciende su cron solo cuando hay
        trabajo que hacer.

        El guard de base neutralizada es de la fuente y se conserva con su
        comentario: *"Prevent deactivated cron jobs from being re-enabled
        through side effects on neutralized databases."*
        """
        if SystemParameter.get_param('database.is_neutralized'):
            return True
        activo = bool(apps.get_model(model).objects.filter(**domain).exists())
        try:
            with transaction.atomic():
                list(type(self).objects
                     .select_for_update(nowait=True).filter(pk=self.pk))
        except (OperationalError, LockError):
            return True
        self.active = activo
        return self.save(update_fields=['active'])



class IrCronTrigger(models.Model):
    """``ir.cron.trigger`` — ≙ ``IrCronTrigger`` (``odoo19c: ir_cron.py:897-916``).

    Un disparo puntual: "corre este cron a esta hora", **independiente** de su
    ``nextcall``. Es la mitad que hacia que ``_trigger`` no existiera en este
    arbol y que ``_get_ready_sql_condition`` no tuviera su rama ``OR``.

    Sin este modelo un cron solo podia correr por su intervalo: no habia forma
    de que un flujo de negocio pidiera "procesa esto en cuanto puedas", que es
    para lo unico que existe ``_trigger`` en la referencia.
    """

    _name = 'ir.cron.trigger'
    _description = 'Triggered actions'
    _rec_name = 'cron_id'
    _allow_sudo_commands = False

    cron = fields.Many2one(
        'base.IrCron', on_delete=models.CASCADE, db_index=True,
        related_name='trigger_ids',
        help_text='Cron a disparar (Odoo cron_id).')
    call_at = fields.Datetime(
        db_index=True,
        help_text='Momento en que el cron debe correr (Odoo call_at).')

    class Meta:
        db_table = 'ir_cron_trigger'
        verbose_name = 'Disparo de tarea programada'
        verbose_name_plural = 'Disparos de tareas programadas'

    def __str__(self):
        return f'{self.cron_id} @ {self.call_at}'

    @classmethod
    def _gc_cron_triggers(cls):
        """≙ ``_gc_cron_triggers`` (``odoo19c: ir_cron.py:906-915``).

        Comentario de la fuente, verbatim: *"active cron jobs are cleared by
        `_clear_schedule` when the job starts"* — asi que esto solo barre los
        disparos de crons **inactivos** con mas de una semana.

        Devuelve ``(hechos, quedan)`` como la fuente, que es el contrato que
        ``ir.autovacuum`` consume para saber si debe volver.
        """
        limite = timezone.now() + timedelta(weeks=-1)
        ids = list(cls.objects.filter(
            call_at__lt=limite, cron__active=False,
        ).values_list('pk', flat=True)[:GC_UNLINK_LIMIT])
        cls.objects.filter(pk__in=ids).delete()
        return len(ids), len(ids) == GC_UNLINK_LIMIT


class IrCronProgress(TimeStampedModel):
    """``ir.cron.progress`` — ≙ ``IrCronProgress`` (``odoo19c: ir_cron.py:918-933``).

    El avance de una corrida por lotes: cuantos registros lleva hechos, cuantos
    le quedan, y cuantas veces consecutivas se le agoto el tiempo. Es lo que
    permite el tercer desenlace de ``CompletionStatus`` —``partially done``— y
    con el que un job largo ceda el turno y siga despues en vez de bloquear al
    resto.

    Sin este modelo un job era ``FULLY_DONE`` o ``FAILED`` en una sola pasada,
    que es como estaba este arbol: el docstring del modulo lo declaraba como
    colapso deliberado. Ese colapso queda cerrado.
    """

    _name = 'ir.cron.progress'
    _description = 'Progress of Scheduled Actions'
    _rec_name = 'cron_id'

    # Hereda de ``TimeStampedModel`` y NO de ``models.Model``: la fuente no
    # declara ``_log_access = False`` en esta clase, asi que su ORM le agrega
    # las cuatro columnas de auditoria — y su propio recolector las consume
    # (``_gc_cron_progress`` filtra por ``create_date``). Sin ellas el
    # recolector no tenia por donde barrer.
    cron = fields.Many2one(
        'base.IrCron', on_delete=models.CASCADE, db_index=True,
        related_name='progress_ids',
        help_text='Cron cuyo avance se registra (Odoo cron_id).')
    remaining = fields.Integer(default=0, help_text='Odoo remaining.')
    done = fields.Integer(default=0, help_text='Odoo done.')
    deactivate = fields.Boolean(
        default=False,
        help_text='Desactivar el cron al terminar (Odoo deactivate).')
    timed_out_counter = fields.Integer(
        default=0,
        help_text=(
            'Veces consecutivas que la corrida se quedo sin tiempo '
            '(Odoo timed_out_counter).'
        ),
    )

    class Meta:
        db_table = 'ir_cron_progress'
        verbose_name = 'Avance de tarea programada'
        verbose_name_plural = 'Avances de tareas programadas'

    def __str__(self):
        return f'{self.cron_id}: {self.done} hechos, {self.remaining} restan'

    @classmethod
    def _gc_cron_progress(cls):
        """≙ ``_gc_cron_progress`` (``odoo19c: ir_cron.py:929-933``).

        Barre los avances de mas de una semana. La fuente filtra por
        ``create_date``, que aqui es ``created_at`` de ``TimeStampedModel``.
        """
        limite = timezone.now() - timedelta(weeks=1)
        ids = list(cls.objects.filter(created_at__lt=limite)
                   .values_list('pk', flat=True)[:GC_UNLINK_LIMIT])
        cls.objects.filter(pk__in=ids).delete()
        return len(ids), len(ids) == GC_UNLINK_LIMIT
