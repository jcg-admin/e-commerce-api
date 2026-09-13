"""``ir.actions.*`` — la familia de acciones que el cliente puede disparar.

Adaptación de ``odoo/addons/base/models/ir_actions.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 1463 líneas). La referencia declara
**nueve** modelos en este archivo; aquí se portan los siete que tienen forma de
dato, y los dos restantes se declaran con su medición al final.

Una acción es "qué pasa cuando el usuario pulsa esto": abrir una ventana, ir a
una URL, ejecutar código en el servidor, cerrar el diálogo. La familia importa
más allá de su propio uso: **cinco archivos ya portados la esperan** —
``ir_cron`` (que allá delega su "qué ejecutar" en ``ir.actions.server``),
``ir_filters.action_id``, ``report_paperformat.report_ids``,
``res_company.external_report_layout_id`` e ``ir_embedded_actions`` entero
(H-API-142).

Cómo se traduce el ``_inherit`` de la referencia
================================================

Odoo usa aquí **herencia por prototipo**: ``ir.actions.act_window`` declara
``_inherit = ['ir.actions.actions']`` pero ``_table = 'ir_act_window'`` — copia
los campos del padre a una tabla propia. El equivalente exacto en Django es un
**modelo abstracto**, así que los campos comunes viven en ``IrActionsBase`` y
cada subtipo concreto los hereda con su propia tabla:

===========================  ======================  =====================
Modelo de la referencia      Tabla                   Aquí
===========================  ======================  =====================
``ir.actions.actions``       ``ir_actions``          ``IrActionsActions``
``ir.actions.act_window``    ``ir_act_window``       ``IrActionsActWindow``
``ir.actions.act_url``       ``ir_act_url``          ``IrActionsActUrl``
``ir.actions.client``        ``ir_act_client``       ``IrActionsClient``
``ir.actions.server``        ``ir_act_server``       ``IrActionsServer``
``ir.actions.act_window.view`` ``ir_act_window_view`` ``IrActionsActWindowView``
``ir.actions.todo``          ``ir_actions_todo``     ``IrActionsTodo``
``ir.actions.act_window_close`` ``ir_actions``       **proxy** de ``IrActionsActions``
===========================  ======================  =====================

La última fila es el caso interesante: ``act_window_close`` **comparte tabla**
con el padre (``_table = 'ir_actions'``) y sólo fija ``type``. En Django eso es
literalmente un ``proxy = True``: misma tabla, otra clase, otro default. Darle
tabla propia habría inventado una tabla que la referencia no tiene.

Detalles conservados que un port ingenuo pierde
===============================================

- **``path`` tiene tres reglas, no una.** Además del patrón
  ``[a-z][a-z0-9_-]*``, la referencia **reserva dos prefijos**: ``m-`` y
  ``action-``. Sin ellos, una acción puede reclamar una URL que el cliente ya
  usa para otra cosa. Se portan los tres chequeos con sus mensajes.
- **``_compute_views`` resuelve una precedencia de tres fuentes** —
  ``view_ids`` (explícito), ``view_mode`` (lista separada por comas) y
  ``view_id`` (vista de referencia). El orden importa: los modos declarados en
  ``view_ids`` van primero; de los que faltan, **si ``view_id`` es de uno de
  ellos, ése se adelanta**; el resto va con vista vacía. Ese adelanto es la
  línea que se pierde al portar "más o menos".
- **``mobile_view_mode``** cae a ``kanban``, y si ese modo no está disponible
  se usa el mismo que en pantalla ancha. Es un default con respaldo, no un
  valor fijo.
- **``limit = 80``** — el tamaño de página por defecto de la vista de lista.
- **``target`` no tiene los mismos valores en todos los subtipos**:
  ``act_window`` y ``client`` usan ``current``/``new``/``fullscreen``/``main``;
  ``act_url`` usa ``new``/``self``/``download``. Son vocabularios distintos y
  se declaran por separado.

Qué NO se porta, con su medición
================================

- **El motor de ejecución de ``ir.actions.server``** — **ya se porta.** Esta
  viñeta declaraba que los seis modos entraban sólo como *vocabulario* y que
  ``run()`` dejaba el punto de extensión declarado y levantaba. Medido hoy
  (2026-08-30T04:12:53) eso es falso: ``_run_action_multi``,
  ``_run_action_object_write``, ``_run_action_object_create``,
  ``_run_action_object_copy`` y ``_run_action_webhook`` están escritos, y
  ``run()`` los despacha por ``_action_runner``.

  Lo que **sí** sigue fuera es la **superficie de ejecución de código**, y son
  dos sitios: el corredor ``_run_action_code_multi`` —con su ayudante
  ``LoggerProxy``— y, dentro de ``_eval_value``, **una de sus ocho** ramas, la
  de ``evaluation_type == 'equation'``. Es la misma decisión que
  ``ir_rule.domain_force`` (``api@020e965``): montar un evaluador sobre entrada
  almacenada exige decidir explícitamente el evaluador y su contexto.

  El corredor está en ``scripts/divergencias_declaradas.txt``, que es donde el
  gate lo lee. La rama **no** puede estarlo: el registro indexa por símbolo y
  ``_eval_value`` sí existe, así que su divergencia vive en el ``raise`` con su
  motivo —levanta en vez de escribir el texto del programa en el campo y
  llamarlo éxito— y en esta nota.

  La medición que sostenía el bloqueo de los otros cuatro —sus insumos cuelgan
  de ``ir.model.fields`` y ``model_name`` sigue ``Char``— resultó **no ser
  bloqueante**: ``crud_model_id``, ``link_field_id`` y ``update_field_id`` son
  hoy ``Many2one`` reales a ``IrModel``/``IrModelFields``, y ``resource_ref``
  es una ``GenericForeignKey``. Lo único que ``model_name`` como ``Char``
  impide es la FK de ``model_id``, que es otra cosa y sigue en **#139**.

- **Cobertura de ``IrActionsServer`` contra la fuente, medida.** Símbolos
  declarados en el cuerpo de la clase, por AST, sumando lo que
  ``IrActionsBase`` aporta:

  ==========  =========  =========  ==========
  eje         referencia  aquí       ausentes
  ==========  =========  =========  ==========
  métodos            44         51           3
  campos             42         54           4
  ==========  =========  =========  ==========

  Los **3 métodos**: ``_run_action_code_multi`` (la divergencia de arriba) y
  ``create``/``write``, que aquí son un solo ``save()`` — deuda **contada**, no
  divergencia, registrada en **#77**.

  Los **4 campos** son todos renombres o reversos, ninguno un hueco:
  ``parent_id`` es ``parent``; ``child_ids`` e ``ir_cron_ids`` son los
  ``related_name`` de ``parent`` y de la FK de ``IrCron`` (``crons``); y
  ``model_id`` es ``model_name`` (``Char``) hasta que **#139** lo convierta.

  *Métrica:* ``FunctionDef``/``AsyncFunctionDef`` y ``Assign``/``AnnAssign``
  con destino ``Name`` en el cuerpo de la clase, en la referencia y aquí.
  *Ciega a:* un símbolo que llegue por herencia sin línea propia en el cuerpo
  —por eso ``IrActionsBase`` se suma a mano— y a un campo nuestro que cubra el
  mismo papel con otro nombre sin nota; los cuatro que lo hacen se
  descontaron uno a uno arriba.

- **``model_id`` como FK a ``ir.model``.** ``grep -rn "^class IrModel\b" src/``
  → **1** clase. [PROVEN] La medición que justificaba el ``Char`` —**0**
  clases— dejó de ser cierta. El campo **sigue** siendo ``model_name``
  (``Char``): convertirlo a FK migra esta tabla, y eso es la tarea **#139**.
  El precedente que este bullet citaba —``ir_filters.action_id``— **ya no
  difiere**: se convirtió en ``base/migrations/0077`` (:ref:`h-api-982`), así
  que «va en su propio pase» dejó de tener respaldo y el desenlace es la
  tarea, no la espera. Mismo estado en
  ``ir_rule``, ``ir_filters`` e ``ir_attachment``. Registrado como **#139**.

  El **ancla de columna 0** no es cosmética: sin ella el grep cuenta también
  los docstrings que *citan* el comando —el de ``ir_rule.py`` ya lo hacía— y
  el auto-conteo de H-API-141 reaparece de forma transitiva, ahora entre
  archivos distintos. Una definición de clase empieza en la columna 0; una
  cita dentro de un docstring va indentada. El patrón anclado distingue las
  dos sin depender de excluir archivos a mano.

- **``group_ids`` y ``_can_execute_action_on_records``** — los grupos que
  pueden ejecutar la acción. Aquí la autorización efectiva es **por capacidad**
  (DEC-11, ``HasCapability``, fail-closed), no una lista de grupos colgada del
  registro. Es la misma divergencia ya declarada para ``ir.model.access`` en
  ``ir_model.py``: portar la columna no cambiaría quién decide.

- **``params``/``params_store`` de ``ir.actions.client``** — un ``Binary``
  computado con inverse que serializa argumentos arbitrarios. Se porta
  ``params_store`` como ``Json``, que es lo que de verdad guarda, en vez de un
  binario opaco: aquí no hay que preservar el formato de pickle de nadie.
"""
import json
import logging
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import api
import fields
import models
import requests
from babel import dates as babel_dates
from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

from addons.base.models.ir_model import (
    IrModel, IrModelFields, IrModelFieldsSelection)
from addons.base.models.ir_sequence import IrSequence
from addons.base.models.res_groups import ResGroups
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import UserError
from fields import Command, Domain
from addons.base.models.ir_model import IrModelData
from orm.environments import (context_scope, get_context,
                              get_current_user, sudo)
from orm.models_transient import TransientModel
from orm.registry import model_by_key
from tools.misc import get_diff, get_lang, unquote
from tools.safe_eval import test_python_expr

_logger = logging.getLogger(__name__)

#: ``VIEW_TYPES`` verbatim de ``ir_actions.py:401-408``.
VIEW_TYPES = [
    ('list', 'Lista'),
    ('form', 'Formulario'),
    ('graph', 'Gráfica'),
    ('pivot', 'Tabla dinámica'),
    ('calendar', 'Calendario'),
    ('kanban', 'Kanban'),
]

#: Patrón admitido para ``path`` — verbatim de la fuente.
PATH_PATTERN = re.compile(r'[a-z][a-z0-9_-]*')

#: Prefijos que la referencia reserva para el cliente.
RESERVED_PATH_PREFIXES = ('m-', 'action-')

#: Palabra que la referencia reserva **entera**, no como prefijo
#: (``odoo19c: ir_actions.py:93-94``). Va aparte de los prefijos porque el
#: chequeo es por igualdad: ``newsletter`` es una ruta valida.
RESERVED_PATH_WORD = 'new'

BINDING_TYPE_CHOICES = [
    ('action', 'Acción'),
    ('report', 'Reporte'),
]


class IrActionsBase(models.DefaultGetMixin, models.CopyMixin, models.OriginMixin,
                    TimeStampedModel):
    """Campos comunes de toda acción — el ``_inherit`` de la referencia.

    Abstracto porque allá la herencia es **por prototipo**: cada subtipo copia
    estos campos a su propia tabla en vez de compartirla.

    ``models.CopyMixin`` y ``models.OriginMixin`` entran aquí y no en un subtipo
    suelto porque allá ``copy``, ``copy_data`` y ``_origin`` viven en
    ``BaseModel``: **todo** modelo los tiene. Aquí son mixins explícitos, así
    que el sitio fiel es el abstracto que las siete acciones comparten, no la
    única que además los consume (``IrActionsServer``: redefine ``copy_data``,
    ``:1320-1326``, y lee el código guardado para decidir si anota revisión,
    ``:730``). Ninguno declara campos: no hay migración.
    """

    name = fields.Char(max_length=255, verbose_name='Nombre de la acción')
    type = fields.Char(max_length=64, verbose_name='Tipo de acción')
    path = fields.Char(
        max_length=64, blank=True, default=None, unique=True, null=True,
        verbose_name='Ruta en la URL',
        help_text='Debe ser única (Odoo _path_unique). default=None, no '
                  "'': la referencia declara el campo sin default "
                  '(``path = fields.Char(...)``, odoo19c: ir_actions.py:70) '
                  'y un Char sin valor se escribe NULL en Odoo, no cadena '
                  'vacía — con NULL el UNIQUE admite múltiples acciones sin '
                  'ruta (H-API-332: default=\'\' colisionaba en la segunda '
                  'ir.actions.server creada sin path explícito).',
    )
    help = fields.Html(
        blank=True, default='', verbose_name='Descripción de la acción',
        help_text='Texto de ayuda opcional que describe la vista destino.',
    )
    binding_model_name = fields.Char(
        max_length=120, blank=True, default='', db_index=True,
        verbose_name='Modelo de anclaje',
        help_text='Odoo binding_model_id. Con valor, la acción aparece en la '
                  'barra lateral de ese modelo.',
    )
    binding_type = fields.Selection(
        max_length=16, choices=BINDING_TYPE_CHOICES, default='action',
        verbose_name='Tipo de anclaje')
    binding_view_types = fields.Char(
        max_length=64, default='list,form', verbose_name='Vistas de anclaje')

    class Meta:
        abstract = True

    def _for_xml_id(self, full_xml_id):
        """Devuelve el contenido de la acción con ese identificador externo.

        ≙ ``_for_xml_id`` (``odoo19c: ir_actions.py:225-234``).

        :param full_xml_id: el id de la acción sin espacio de nombres (el
            atributo ``@id`` del archivo XML)
        :return: una vista de lectura de la ``ir.actions.action`` segura para
            uso web

        La fuente afirma con ``assert isinstance(...)`` que el registro
        resuelto es del tipo del receptor; aquí la comprobación es
        ``isinstance(record, type(self))``, que dice lo mismo sin pasar por el
        registro de modelos.
        """
        record = IrModelData.ref(full_xml_id)
        assert isinstance(record, type(self)), (
            'Se esperaba una accion de tipo %s, llego %s'
            % (type(self).__name__, type(record).__name__))
        return record._get_action_dict()

    def _get_action_dict(self):
        """Devuelve el contenido de esta acción, acotado a lo legible.

        ≙ ``_get_action_dict`` (``odoo19c: ir_actions.py:236-245``).

        La fuente arma el diccionario con ``self.sudo().read()[0]`` y filtra
        por :meth:`_get_readable_fields`. Aquí el ``read()`` de Odoo —que
        devuelve los valores de los campos de un registro— es el recorrido de
        ``_meta.fields`` del ORM, que es lo mismo con el constructor de este
        stack. El ``sudo()`` de la fuente es el contexto homónimo de
        ``orm.environments``, ya usado en este archivo.
        """
        readable_fields = self._get_readable_fields()
        with sudo():
            return {
                field.name: getattr(self, field.name)
                for field in self._meta.fields
                if field.name in readable_fields
            }

    def _get_readable_fields(self):
        """Los campos que es seguro leer desde el cliente.

        ≙ ``_get_readable_fields`` (``odoo19c: ir_actions.py:246-259``), con
        su docstring verbatim: *"return the list of fields that are safe to
        read. Fetched via /web/action/load or _for_xml_id method. Only fields
        used by the web client should included. Accessing content useful for
        the server-side must be done manually with superuser"*.

        La fuente lo declara en ``ir.actions.actions``, que allá es a la vez el
        modelo concreto y el portador de los campos comunes. Aquí esos dos
        papeles están repartidos —``IrActionsBase`` lleva los campos,
        ``IrActionsActions`` es la fila— y el método vive en el portador,
        porque es de quien heredan los subtipos: ``IrActionsServer`` y
        ``IrActionsReport`` ya lo extendían con ``super()``, que hasta ahora no
        tenía a quién llamar (:ref:`h-api-921`).
        """
        return {
            'binding_model_id', 'binding_type', 'binding_view_types',
            'display_name', 'help', 'id', 'name', 'type', 'xml_id',
            'path',
        }

    def __str__(self):
        return self.name

    def clean(self):
        """≙ ``_check_path`` (``odoo19c: ir_actions.py:82-96``) — sus CUATRO
        chequeos.

        Son cuatro y no tres, que es lo que este puerto tenia. El cuarto —
        ``path == "new"``— **no lo cubre ninguno de los otros**: ``new`` cumple
        el patron y no empieza por ninguno de los dos prefijos reservados, asi
        que pasaba entero. La fuente lo separa a proposito y su mensaje lo
        dice: *"'new' is reserved, and can not be used as path."*

        Y compara por **igualdad**, no por prefijo: ``newsletter`` es una ruta
        legitima. Escribirlo con ``startswith`` prohibiria rutas que la fuente
        admite.
        """
        super().clean()
        if not self.path:
            return
        if not PATH_PATTERN.fullmatch(self.path):
            raise ValidationError(
                'La ruta sólo admite minúsculas alfanuméricas, guion bajo y '
                'guion, y debe empezar por letra.'
            )
        for prefix in RESERVED_PATH_PREFIXES:
            if self.path.startswith(prefix):
                raise ValidationError("'%s' es un prefijo reservado." % prefix)
        if self.path == RESERVED_PATH_WORD:
            raise ValidationError(
                "'%s' está reservada y no se puede usar como ruta."
                % RESERVED_PATH_WORD)


class IrActionsActions(IrActionsBase):
    """La acción genérica (``ir.actions.actions``, tabla ``ir_actions``)."""

    class Meta:
        db_table = 'ir_actions'
        ordering = ['name', 'id']
        verbose_name = 'Acción'
        verbose_name_plural = 'Acciones'


class IrActionsActWindowClose(IrActionsActions):
    """Cierra el diálogo actual (``ir.actions.act_window_close``).

    **Proxy**: la referencia le da ``_table = 'ir_actions'``, la misma tabla
    que el padre, y sólo fija el ``type``. Darle tabla propia habría inventado
    una que la fuente no tiene.
    """

    TYPE = 'ir.actions.act_window_close'

    class Meta:
        proxy = True
        verbose_name = 'Acción de cierre de ventana'
        verbose_name_plural = 'Acciones de cierre de ventana'

    def save(self, *args, **kwargs):
        if not self.type:
            self.type = self.TYPE
        return super().save(*args, **kwargs)


class IrActionsActWindow(IrActionsBase):
    """Abre una ventana sobre un modelo (``ir.actions.act_window``)."""

    TARGET_CHOICES = [
        ('current', 'Ventana actual'),
        ('new', 'Ventana nueva'),
        ('fullscreen', 'Pantalla completa'),
        ('main', 'Acción principal de la ventana actual'),
    ]

    domain = fields.Char(
        max_length=1024, blank=True, default='', verbose_name='Dominio',
        help_text='Filtrado opcional del destino, como expresión Python. '
                  'Este archivo NO lo evalúa — ver el docstring del módulo.',
    )
    context = fields.Json(
        default=dict, verbose_name='Contexto',
        help_text='Odoo context. Allá es texto de una expresión Python; aquí '
                  'es JSON, que es lo que de verdad se guarda.',
    )
    res_id = fields.Integer(
        null=True, blank=True, verbose_name='ID del registro',
        help_text="Sólo cuando view_mode es 'form'.",
    )
    res_model = fields.Char(
        max_length=120, db_index=True, verbose_name='Modelo destino')
    target = fields.Selection(
        max_length=16, choices=TARGET_CHOICES, default='current',
        required=False, verbose_name='Ventana destino')
    view_mode = fields.Char(
        max_length=120, default='list,form', verbose_name='Modos de vista',
        help_text="Lista separada por comas: 'form', 'list', 'calendar'…",
    )
    mobile_view_mode = fields.Char(
        max_length=32, default='kanban', verbose_name='Modo de vista móvil',
        help_text='Primer modo en pantallas pequeñas. Si no está entre los '
                  'disponibles, se usa el mismo que en pantalla ancha.',
    )
    usage = fields.Char(
        max_length=64, blank=True, default='', verbose_name='Uso')
    limit = fields.Integer(
        default=80, verbose_name='Límite',
        help_text='Tamaño de página por defecto de la vista de lista.',
    )
    groups = fields.Many2many(
        ResGroups, blank=True, related_name='act_window_ids',
        db_table='ir_act_window_group_rel', verbose_name='Grupos')
    filter = fields.Boolean(default=False, verbose_name='Filtro')
    cache = fields.Boolean(
        default=True, verbose_name='Caché de datos',
        help_text='Cachea los datos de lista, kanban y formulario para '
                  'acelerar la carga.',
    )

    class Meta:
        db_table = 'ir_act_window'
        ordering = ['name', 'id']
        verbose_name = 'Acción de ventana'
        verbose_name_plural = 'Acciones de ventana'

    @property
    def views(self):
        """Lista ordenada de ``(view_id, modo)`` — ``_compute_views``.

        Resuelve la precedencia de tres fuentes, y el orden es el de la
        fuente: primero los modos que ``view_ids`` declara explícitamente;
        después los de ``view_mode`` que falten, **adelantando el de
        ``view_id``** si está entre ellos; el resto, con vista vacía.
        """
        declared = [(v.view_id, v.view_mode) for v in self.view_ids.all()]
        got_modes = [mode for _vid, mode in declared]
        all_modes = [m for m in (self.view_mode or '').split(',') if m]
        missing = [m for m in all_modes if m not in got_modes]

        result = list(declared)
        reference = getattr(self, 'view_id', None)
        reference_type = getattr(reference, 'type', None)
        if missing and reference_type in missing:
            # El adelanto de view_id: la línea que se pierde al portar
            # "más o menos".
            missing.remove(reference_type)
            result.append((reference.pk, reference_type))
        result.extend((None, mode) for mode in missing)
        return result

    def clean(self):
        """≙ ``_check_model`` (``:270-276``) y ``_check_view_mode``
        (``:300-307``), ademas del ``_check_path`` que hereda.

        **El modelo.** La fuente comprueba ``res_model`` **y**
        ``binding_model_id`` contra su ``env``, que es el registro de modelos
        cargados. El equivalente aqui es ``orm.registry.MODELS_BY_NAME``, que
        indexa por el nombre punteado que declara ``_name`` — el mismo espacio
        de nombres que la fuente consulta.

        Sin esta guarda el error sale **al abrir la accion**, lejos de donde se
        escribio, y quien la escribio ya no esta mirando.

        **El modo de vista.** Dos comprobaciones, y la segunda sorprende:
        ``'list, form'`` parece correcto y no lo es. La fuente parte por coma
        **sin recortar**, asi que el segundo modo queda como ``' form'`` y no
        resuelve contra ningun tipo de vista. Rechazar el espacio es mas util
        que aceptarlo y fallar despues.

        **Divergencia de nombre, declarada:** el ``binding_model_id`` de la
        fuente es aqui ``binding_model_name`` (``Char``), la misma conversion
        diferida a FK que ``model_name`` — ver el docstring del modulo.
        """
        super().clean()
        for fname in ('res_model', 'binding_model_name'):
            model_name = getattr(self, fname, '')
            # Se admiten las DOS formas de nombrar un modelo, por la misma
            # razón que en los otros tres sitios: la columna guarda el label
            # de Django y ``MODELS_BY_NAME`` indexa por ``_name``. Con la
            # pertenencia cruda, ``'base.ResPartner'`` —un nombre válido— se
            # rechazaba como inválido.
            if model_name and model_by_key(model_name) is None:
                raise ValidationError(
                    'Nombre de modelo inválido “%s” en la definición de la '
                    'acción.' % model_name)
        modes = (self.view_mode or '').split(',')
        if len(modes) != len(set(modes)):
            raise ValidationError(
                'Los modos de view_mode no se pueden repetir: %s' % modes)
        if any(' ' in mode for mode in modes):
            raise ValidationError(
                'No se admiten espacios en view_mode: “%s”' % self.view_mode)

    def resolve_mobile_view_mode(self):
        """``mobile_view_mode`` con su respaldo al modo de pantalla ancha."""
        available = [m for m in (self.view_mode or '').split(',') if m]
        if self.mobile_view_mode in available:
            return self.mobile_view_mode
        return available[0] if available else self.mobile_view_mode


class IrActionsActWindowView(TimeStampedModel):
    """Una vista concreta de una acción de ventana (``ir.actions.act_window.view``)."""

    sequence = fields.Integer(null=True, blank=True, verbose_name='Secuencia')
    view_id = fields.Integer(
        null=True, blank=True, verbose_name='Vista',
        help_text='Odoo view_id (Many2one a ir.ui.view). Entero mientras '
                  'ir_ui_view.py no esté portado.',
    )
    view_mode = fields.Selection(
        max_length=16, choices=VIEW_TYPES, verbose_name='Tipo de vista')
    act_window = fields.Many2one(
        IrActionsActWindow, on_delete=models.CASCADE, db_index=True,
        related_name='view_ids', verbose_name='Acción')
    multi = fields.Boolean(
        default=False, verbose_name='En varios documentos',
        help_text='Si está activo, la acción no aparece en la barra derecha '
                  'de un formulario.',
    )

    class Meta:
        db_table = 'ir_act_window_view'
        ordering = ['sequence', 'id']
        verbose_name = 'Vista de acción de ventana'
        verbose_name_plural = 'Vistas de acción de ventana'
        constraints = [
            # ``_unique_mode_per_action`` de la fuente.
            models.UniqueConstraint(
                fields=['act_window', 'view_mode'],
                name='ir_act_window_view_unique_mode_per_action'),
        ]

    def __str__(self):
        return f'{self.act_window_id}: {self.view_mode}'


class IrActionsActUrl(IrActionsBase):
    """Navega a una URL (``ir.actions.act_url``)."""

    TYPE = 'ir.actions.act_url'

    #: Vocabulario **distinto** al de ``act_window``: aquí no hay
    #: ``current``/``fullscreen``/``main``, y sí ``self`` y ``download``.
    TARGET_CHOICES = [
        ('new', 'Ventana nueva'),
        ('self', 'Esta ventana'),
        ('download', 'Descargar'),
    ]

    url = fields.Text(verbose_name='URL de la acción')
    target = fields.Selection(
        max_length=16, choices=TARGET_CHOICES, default='new',
        verbose_name='Destino de la acción')

    class Meta:
        db_table = 'ir_act_url'
        ordering = ['name', 'id']
        verbose_name = 'Acción de URL'
        verbose_name_plural = 'Acciones de URL'


class IrActionsClient(IrActionsBase):
    """Acción resuelta por el cliente (``ir.actions.client``)."""

    TYPE = 'ir.actions.client'

    TARGET_CHOICES = IrActionsActWindow.TARGET_CHOICES

    tag = fields.Char(
        max_length=120, verbose_name='Etiqueta de la acción de cliente',
        help_text='Identificador que el cliente resuelve a un componente.',
    )
    target = fields.Selection(
        max_length=16, choices=TARGET_CHOICES, default='current',
        verbose_name='Ventana destino')
    res_model = fields.Char(
        max_length=120, blank=True, default='', verbose_name='Modelo destino')
    context = fields.Json(default=dict, verbose_name='Contexto')
    params_store = fields.Json(
        default=dict, blank=True, verbose_name='Parámetros',
        help_text='Odoo params_store. Allá es Binary con un compute/inverse '
                  'que lo serializa; aquí es Json, que es lo que guarda.',
    )

    class Meta:
        db_table = 'ir_act_client'
        ordering = ['name', 'id']
        verbose_name = 'Acción de cliente'
        verbose_name_plural = 'Acciones de cliente'


class ServerActionHistoryWizard(TransientModel):
    """≙ ``ServerActionHistoryWizard`` (``odoo19c: ir_actions.py:464-500``).

    El asistente que compara el código vigente de una acción de servidor con
    el de una revisión guardada, y permite restaurarla.

    **Sigue siendo útil aunque el modo ``code`` no se evalúe aquí**: guardar y
    comparar el texto es una cosa, ejecutarlo es otra. La divergencia
    declarada del módulo cubre la evaluación, no el historial.
    """

    _name = 'server.action.history.wizard'
    _description = 'Server Action History Wizard'

    action = fields.Many2one(
        'base.IrActionsServer', on_delete=models.CASCADE, null=True,
        blank=True, related_name='history_wizards', verbose_name='Acción')
    revision = fields.Many2one(
        'base.IrActionsServerHistory', on_delete=models.CASCADE, null=True,
        blank=True, related_name='wizards', verbose_name='Revisión')

    class Meta:
        # Con tabla real, como todo transitorio de la fuente
        # (``_auto = True``, ``odoo19c: odoo/orm/models_transient.py:18``). El
        # ``managed = False`` que había aquí dejaba al asistente sin dónde
        # guardarse, y su suite fallaba con ``relation … does not exist``.
        db_table = 'server_action_history_wizard'
        verbose_name = 'Asistente de historial de acción de servidor'
        verbose_name_plural = 'Asistentes de historial de acción de servidor'

    @classmethod
    def _default_revision(cls):
        """≙ ``_default_revision`` (``:469-475``) — la última revisión distinta.

        La fuente lee ``default_action_id`` del contexto; aquí el contexto es
        ``orm.environments.get_context()``, el mismo dato por la vía del stack.
        """
        action_id = get_context().get('default_action_id')
        if not action_id:
            return None
        action = IrActionsServer.objects.filter(pk=action_id).first()
        if action is None:
            return None
        return IrActionsServerHistory.objects.filter(
            action=action).exclude(code=action.code or '').first()

    #: ≙ ``current_code = fields.Text(related='action_id.code')`` (``:480``).
    #: Un ``related`` de la fuente es lectura derivada, y aquí lo es también:
    #: ``NonStored`` computa al leer y no añade columna.
    current_code = fields.NonStored(
        default=lambda wizard: (wizard.action.code if wizard.action else ''),
        help_text='Odoo current_code. El código vigente de la acción.',
    )

    def _compute_code_diff(self):
        """≙ ``_compute_code_diff`` (``:487-497``).

        La tabla HTML con la diferencia, o falso si no hay ninguna. El
        ``dark_color_scheme`` de la fuente sale de la cookie ``color_scheme``
        de la petición; aquí sale del contexto, que es donde este árbol pone
        lo que la petición aporta al ORM — misma información, otro canal.
        """
        revision_code = self.revision.code if self.revision else ''
        actual_code = self.action.code if self.action else ''
        if actual_code == revision_code:
            return False
        return get_diff(
            (actual_code or '', 'Código actual'),
            (revision_code or '', 'Código de la revisión'),
            dark_color_scheme=get_context().get('color_scheme') == 'dark',
        )

    #: ≙ ``code_diff = fields.Html(compute=…, sanitize_tags=False)`` (``:479``).
    #: El ``sanitize_tags=False`` de la fuente permite el ``<style>`` que
    #: ``get_diff`` adjunta; aquí no hay saneador que desactivar, así que el
    #: parámetro no tiene receptor y su efecto ya se cumple.
    code_diff = fields.NonStored(
        default=lambda wizard: wizard._compute_code_diff(),
        help_text='Odoo code_diff. La diferencia entre el código vigente y '
                  'el de la revisión, como tabla HTML.',
    )

    def restore_revision(self):
        """≙ ``restore_revision`` (``:499-501``) — devuelve el código guardado."""
        self.action.code = self.revision.code
        self.action.save(update_fields=['code'])


class IrActionsServerHistory(TimeStampedModel):
    """≙ ``IrActionsServerHistory`` (``odoo19c: ir_actions.py:503-539``).

    Una fila por versión del código de una acción de servidor. La escribe
    ``IrActionsServer.save()`` cuando el código cambia, y la poda
    ``_gc_histories`` cuando una acción acumula más de ``_max_entries_per_action``.
    """

    _name = 'ir.actions.server.history'
    _description = 'Server Action History'
    _order = 'create_date desc, id desc'
    #: ≙ ``_max_entries_per_action = 100`` (``:508``) — el tope por acción.
    _max_entries_per_action = 100

    action = fields.Many2one(
        'base.IrActionsServer', on_delete=models.CASCADE,
        related_name='code_history', verbose_name='Acción')
    code = fields.Text(blank=True, default='', verbose_name='Código')

    class Meta:
        db_table = 'ir_actions_server_history'
        #: ≙ ``_order = 'create_date desc, id desc'``. ``create_date`` es aquí
        #: ``created_at``, que es la forma que este árbol adoptó del
        #: log-access (``timestamped_mixin.py``).
        ordering = ['-created_at', '-id']
        verbose_name = 'Historial de acción de servidor'
        verbose_name_plural = 'Historiales de acción de servidor'

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``:513-527``) — *"fecha - autor"*.

        La fecha se formatea con ``babel.dates.format_datetime`` y el idioma
        de ``get_lang()``, igual que la fuente, y se convierte a la zona del
        usuario antes de imprimirla.

        **El autor no se imprime, y es una divergencia ya declarada, no un
        hueco de este porte:** la fuente lo saca de ``create_uid``, una de las
        cuatro columnas de log-access que su ORM inyecta en todo modelo. Aquí
        el mixin aporta las dos de *cuándo* (``created_at``/``updated_at``) y
        ninguna de las de *quién*; la alternativa —auto-inyectarlas en la capa
        ``orm/``, que es donde la referencia las pone— está registrada como
        DEC-09 de ``adoptar-arquitectura-server-service-odoo``. El día que
        exista, esta etiqueta recupera su segunda mitad sin tocar nada más.
        """
        if not self.created_at:
            return False
        lang = get_lang()
        user = get_current_user()
        zone = getattr(user, 'tz', None) if user is not None else None
        moment = self.created_at.replace(microsecond=0)
        tzinfo = None
        if zone:
            try:
                tzinfo = ZoneInfo(zone)
            except ZoneInfoNotFoundError:
                # silent OK because una zona inválida guardada en el perfil no
                # debe tumbar la etiqueta: la fuente cae al valor sin
                # convertir con el mismo criterio (``datetime.astimezone(
                # tzinfo) if tzinfo else datetime``, ``:521``).
                tzinfo = None
        if tzinfo is not None:
            moment = moment.astimezone(tzinfo)
        return babel_dates.format_datetime(
            moment, tzinfo=tzinfo,
            locale=(lang.code if lang is not None else 'en_US'))

    @api.autovacuum
    def _gc_histories(self):
        """≙ ``_gc_histories`` (``:529-539``) — poda las revisiones sobrantes.

        La fuente agrupa por acción con ``_read_group`` y un ``having`` sobre
        el conteo; aquí el mismo predicado es un ``annotate(Count)`` +
        ``filter``, que es como este ORM expresa un ``HAVING``. De cada acción
        que pasa el tope se conservan las ``_max_entries_per_action`` primeras
        **en el orden del modelo** —las más recientes— y se borra el resto.
        """
        crowded = (
            IrActionsServerHistory.objects.values('action')
            .annotate(total=Count('id'))
            .filter(total__gt=IrActionsServerHistory._max_entries_per_action)
            .values_list('action', flat=True))
        to_clean = []
        for action_id in crowded:
            ids = list(
                IrActionsServerHistory.objects
                .filter(action_id=action_id)
                .values_list('id', flat=True))
            to_clean.extend(ids[IrActionsServerHistory._max_entries_per_action:])
        if to_clean:
            IrActionsServerHistory.objects.filter(pk__in=to_clean).delete()


#: ≙ ``WEBHOOK_SAMPLE_VALUES`` (``odoo19c: ir_actions.py:542-558``) — el valor
#: de ejemplo por tipo de campo, para la carga de muestra que el formulario
#: enseña cuando el modelo todavía no tiene ningún registro.
WEBHOOK_SAMPLE_VALUES = {
    'integer': 42,
    'float': 42.42,
    'monetary': 42.42,
    'char': 'Hello World',
    'text': 'Hello World',
    'html': '<p>Hello World</p>',
    'boolean': True,
    'selection': 'option1',
    'date': '2020-01-01',
    'datetime': '2020-01-01 00:00:00',
    'binary': '<base64_data>',
    'many2one': 47,
    'many2many': [42, 47],
    'one2many': [42, 47],
    'reference': 'res.partner,42',
    None: 'some_data',
}


class ServerActionWithWarningsError(UserError):
    """≙ ``ServerActionWithWarningsError`` (``odoo19c: ir_actions.py:562``).

    La levanta ``_run`` cuando la acción trae avisos: una acción mal
    configurada **no corre**. Hereda de ``UserError`` como allá, así que el
    manejador de errores la trata como un rechazo de negocio y no como un
    fallo del servidor.
    """


class IrActionsServer(IrActionsBase):
    """Acción ejecutada en el servidor (``ir.actions.server``).

    Los seis modos se portan como **vocabulario** —clasifican la acción— pero
    el motor que los ejecuta no; ver el docstring del módulo.
    """

    _name = 'ir.actions.server'
    _description = 'Server Actions'
    _table = 'ir_act_server'
    _inherit = ['ir.actions.actions']
    _order = 'sequence,name,id'
    _allow_sudo_commands = False

    TYPE = 'ir.actions.server'

    STATE_CHOICES = [
        ('object_write', 'Actualizar registro'),
        ('object_create', 'Crear registro'),
        ('object_copy', 'Duplicar registro'),
        ('code', 'Ejecutar código'),
        ('webhook', 'Enviar notificación webhook'),
        ('multi', 'Varias acciones'),
    ]

    #: ≙ ``usage`` (``odoo19c: ir_actions.py:608-611``) — lo que distingue una
    #: accion suelta de la que respalda a un ``ir.cron``. Lo escribe
    #: ``IrCron.save()`` al crear, igual que la fuente lo fija en ``create``
    #: (``ir_cron.py:137``). Sin este campo la accion de un cron era
    #: indistinguible de cualquier otra, y el filtro de la fuente —*"Used to
    #: filter menu and home actions from the user form"*— no tenia por donde.
    USAGE_CHOICES = [
        ('ir_actions_server', 'Acción de servidor'),
        ('ir_cron', 'Acción programada'),
    ]

    #: ≙ ``update_m2m_operation`` (``odoo19c: ir_actions.py:667-672``).
    UPDATE_M2M_OPERATION_CHOICES = [
        ('add', 'Añadiendo'),
        ('remove', 'Quitando'),
        ('set', 'Fijándolo a'),
        ('clear', 'Vaciándolo'),
    ]

    #: ≙ ``update_boolean_value`` (``:673``).
    UPDATE_BOOLEAN_VALUE_CHOICES = [
        ('true', 'Sí (verdadero)'),
        ('false', 'No (falso)'),
    ]

    #: ≙ ``evaluation_type`` (``:682-686``). ``equation`` es el único de los
    #: tres que evalúa Python — la divergencia declarada en el docstring del
    #: módulo — y ``_eval_value`` lo rechaza explícitamente en vez de callarlo.
    EVALUATION_TYPE_CHOICES = [
        ('value', 'Actualizar'),
        ('sequence', 'Secuencia'),
        ('equation', 'Calcular'),
    ]

    #: ≙ ``automated_name`` (``odoo19c: ir_actions.py:606``) —
    #: ``fields.Char(compute='_compute_name', store=True)``. Guarda el nombre
    #: que la acción **se generaría** a sí misma, para poder distinguir un
    #: ``name`` que el usuario escribió de uno que la acción puso sola. Sin
    #: esta columna ``_compute_name`` no tendría con qué comparar y pisaría
    #: siempre el nombre del usuario.
    automated_name = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Nombre automático',
        help_text='Odoo automated_name. El nombre que la acción se pondría '
                  'sola; si coincide con name, name se regenera al cambiar '
                  'de tipo.',
    )

    state = fields.Selection(
        max_length=16, choices=STATE_CHOICES, verbose_name='Tipo')
    usage = fields.Selection(
        max_length=20, choices=USAGE_CHOICES, default='ir_actions_server',
        verbose_name='Uso',
        help_text='Odoo usage. ir_cron cuando la accion respalda a una tarea '
                  'programada.',
    )
    sequence = fields.Integer(
        default=5, verbose_name='Secuencia',
        help_text='Orden de ejecución en una acción de tipo "varias".',
    )
    model_name = fields.Char(
        max_length=120, db_index=True, verbose_name='Modelo',
        help_text='Odoo model_id. Label del modelo; 0 clases IrModel en este '
                  'árbol.',
    )
    code = fields.Text(
        blank=True, default='', verbose_name='Código',
        help_text='Bloque Python del modo "code". Este archivo NO lo evalúa.',
    )
    # Adaptación de proyecto (sin análogo en la referencia): sustituye la
    # EVALUACIÓN de ``code`` por una llamada a método resuelta en runtime
    # (``getattr(apps.get_model(model_name), method_name)``). Vive aquí, y no
    # en ``ir.cron``, porque este es el modelo donde la referencia pone el
    # "qué ejecutar" — ``ir.cron`` sólo aporta la periodicidad y lo delega.
    method_name = fields.Char(
        max_length=128, blank=True, default='', verbose_name='Método',
        help_text='Método a invocar sobre model_name. Alternativa segura al '
                  'code Python del modo "code"; este archivo tampoco lo invoca.',
    )
    #: ≙ ``parent_id`` (``odoo19c: ir_actions.py:648``) — el enlace del modo
    #: ``multi``: una acción compuesta encadena a sus hijas. La fuente declara
    #: ``ondelete='cascade'`` e ``index=True``; los dos se conservan.
    #:
    #: El inverso ``child_ids`` (``:649-650``) es aquí ``related_name``: en
    #: Django la relación se declara una vez y el reverso lo da el ORM. Su
    #: ``domain`` y su ``copy=True`` NO se portan — el primero es filtro de
    #: vista y el segundo es semántica de ``copy()``, que este árbol resuelve
    #: en el serializer. Divergencia declarada, no omisión.
    parent = fields.Many2one(
        'self', on_delete=models.CASCADE, db_index=True,
        null=True, blank=True, related_name='child_ids',
        verbose_name='Acción padre',
        help_text='Odoo parent_id. Acción compuesta que encadena a ésta.',
    )

    # ---- La superficie de configuración que los corredores consumen -------
    #
    # Estaba declarada bloqueada por *"cuelgan de ``ir.model.fields`` como FK
    # y ``model_name`` sigue siendo ``Char``"*. La premisa caducó: ``IrModel``
    # (``ir_model.py:317``) e ``IrModelFields`` (``:468``) existen, así que las
    # FK se declaran contra ellos y el ``Char`` sólo queda como el nombre
    # técnico del modelo sobre el que la acción corre (tarea #139 lo convierte).

    #: ≙ ``crud_model_id`` (``odoo19c: ir_actions.py:651-655``) — el modelo
    #: sobre el que ``object_create``/``object_copy``/``object_write`` operan.
    crud_model_id = fields.Many2one(
        IrModel, on_delete=models.CASCADE, null=True, blank=True,
        related_name='crud_server_actions', verbose_name='Registro a crear',
        help_text='Odoo crud_model_id. Modelo destino del CRUD.',
        db_column='crud_model_id',
    )
    #: ≙ ``link_field_id`` (``:657-659``) — el campo por el que se engancha el
    #: registro recién creado al registro activo.
    link_field_id = fields.Many2one(
        IrModelFields, on_delete=models.CASCADE, null=True, blank=True,
        related_name='link_server_actions', verbose_name='Campo de enlace',
        help_text='Odoo link_field_id. Campo que ata el registro nuevo al '
                  'registro sobre el que corre la acción.',
        db_column='link_field_id',
    )
    #: ≙ ``update_field_id`` (``:663``) — el campo que ``object_write`` escribe.
    update_field_id = fields.Many2one(
        IrModelFields, on_delete=models.CASCADE, null=True, blank=True,
        related_name='update_server_actions',
        verbose_name='Campo a actualizar',
        help_text='Odoo update_field_id. Último campo de update_path.',
        db_column='update_field_id',
    )
    #: ≙ ``update_path`` (``:664``) — la ruta punteada hasta ese campo.
    update_path = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Ruta del campo a actualizar',
        help_text="Odoo update_path. Ruta punteada, p. ej. 'partner_id.name'.",
    )
    #: ≙ ``update_related_model_id`` (``:665``).
    update_related_model_id = fields.Many2one(
        IrModel, on_delete=models.CASCADE, null=True, blank=True,
        related_name='update_related_server_actions',
        verbose_name='Modelo relacionado del campo',
        db_column='update_related_model_id',
    )
    #: ≙ ``update_m2m_operation`` (``:667-672``).
    update_m2m_operation = fields.Selection(
        max_length=8, choices=UPDATE_M2M_OPERATION_CHOICES, default='add',
        verbose_name='Operación Many2many')
    #: ≙ ``update_boolean_value`` (``:673``).
    update_boolean_value = fields.Selection(
        max_length=8, choices=UPDATE_BOOLEAN_VALUE_CHOICES, default='true',
        verbose_name='Valor booleano')
    #: ≙ ``value`` (``:675-681``) — el valor a escribir, o el nombre a crear.
    value = fields.Text(
        blank=True, default='', verbose_name='Valor',
        help_text='Odoo value. En modo "equation" es una expresión Python; '
                  'este archivo NO la evalúa (ver el docstring del módulo).',
    )
    #: ≙ ``evaluation_type`` (``:682-686``).
    evaluation_type = fields.Selection(
        max_length=16, choices=EVALUATION_TYPE_CHOICES, default='value',
        verbose_name='Tipo de valor')
    #: ≙ ``html_value`` (``:687``).
    html_value = fields.Html(
        blank=True, default='', verbose_name='Valor HTML')
    #: ≙ ``sequence_id`` (``:688``) — la numeración del modo ``sequence``.
    sequence_id = fields.Many2one(
        IrSequence, on_delete=models.CASCADE, null=True, blank=True,
        related_name='server_actions', verbose_name='Secuencia a usar',
        db_column='sequence_id')
    #: ≙ ``resource_ref`` (``:689-690``): ``fields.Reference``, que en Odoo es
    #: la cadena ``'modelo,id'``. Aquí el mecanismo declarado por
    #: ``orm/fields_reference.py`` es el ``GenericForeignKey`` de Django, que
    #: exige el par ``content_type``/``object_id``. Las dos columnas son el
    #: precio del mecanismo, no campos inventados: juntas guardan lo mismo.
    resource_ref_content_type = fields.Many2one(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
        related_name='server_actions', verbose_name='Tipo del registro')
    resource_ref_id = fields.Integer(
        null=True, blank=True, verbose_name='Id del registro')
    resource_ref = GenericForeignKey(
        'resource_ref_content_type', 'resource_ref_id')
    #: ≙ ``selection_value`` (``:691-692``).
    selection_value = fields.Many2one(
        IrModelFieldsSelection, on_delete=models.CASCADE, null=True, blank=True,
        related_name='server_actions', verbose_name='Valor de selección')
    #: ≙ ``webhook_url`` (``:703``).
    webhook_url = fields.Char(
        max_length=1024, blank=True, default='', verbose_name='URL del webhook')
    #: ≙ ``webhook_field_ids`` (``:704-709``) — con su tabla de relación, que
    #: la fuente nombra explícitamente.
    webhook_field_ids = fields.Many2many(
        IrModelFields, blank=True,
        db_table='ir_act_server_webhook_field_rel',
        related_name='webhook_server_actions',
        verbose_name='Campos del webhook')

    #: ≙ ``group_ids`` (``odoo19c: ir_actions.py:661-662``) — los grupos que
    #: pueden ejecutar la acción; vacío significa *todos*. La fuente nombra su
    #: tabla de relación (``ir_act_server_group_rel``) y sus dos columnas
    #: (``act_id``/``gid``); la tabla se conserva, los nombres de columna los
    #: pone Django y no son parte del contrato de nadie.
    #:
    #: Lo consume ``_can_execute_action_on_records``, que es el guardián de
    #: ``run()``: sin grupos declarados la comprobación cae al permiso de
    #: escritura sobre el modelo, como allá.
    group_ids = fields.Many2many(
        ResGroups, blank=True, db_table='ir_act_server_group_rel',
        related_name='server_actions', verbose_name='Grupos permitidos',
        help_text='Odoo group_ids. Grupos que pueden ejecutar la acción. '
                  'Vacío = cualquiera con permiso de escritura en el modelo.',
    )

    # ---- Lo derivado: en la fuente son ``compute``; aquí, no persistidos ---
    #
    # Los siete se declaran con ``fields.NonStored`` —el mecanismo que este
    # árbol construyó para el ``store=False`` de la referencia— porque ninguno
    # tiene columna allá tampoco. Los dos ``related`` de la fuente
    # (``crud_model_name``, ``update_field_type``) entran en el mismo saco: un
    # ``related`` es lectura derivada de otra fila, que es exactamente lo que
    # un ``NonStored`` con ``default`` invocable resuelve.

    #: ≙ ``allowed_states`` (``odoo19c: ir_actions.py:630``) —
    #: ``fields.Json(compute='_compute_allowed_states')``. La lista de estados
    #: que el formulario ofrece; la fuente la calcula desde la propia
    #: ``selection`` del campo ``state`` para que un addon que la extienda no
    #: tenga que tocar dos sitios.
    allowed_states = fields.NonStored(
        default=lambda action: action._compute_allowed_states(),
        help_text='Odoo allowed_states. Los estados que el formulario ofrece.',
    )
    #: ≙ ``available_model_ids`` (``:637``) — los modelos sobre los que el
    #: usuario puede declarar una acción. La fuente los acota con
    #: ``ir.model.access._get_allowed_models()``; aquí el equivalente es el
    #: censo de modelos reflejados, y la autorización efectiva la sigue
    #: decidiendo la capacidad (DEC-11) en la vista.
    available_model_ids = fields.NonStored(
        default=lambda action: action._compute_available_model_ids(),
        help_text='Odoo available_model_ids. Modelos disponibles.',
    )
    #: ≙ ``show_code_history`` (``:646``) — si existe alguna revisión del
    #: código distinta de la vigente.
    show_code_history = fields.NonStored(
        default=lambda action: action._compute_show_code_history(),
        help_text='Odoo show_code_history. Si hay historial que ofrecer.',
    )
    #: ≙ ``crud_model_name = fields.Char(related='crud_model_id.model')``
    #: (``:657``). Falso cuando no hay modelo destino, como el ``related`` de
    #: la fuente sobre un Many2one vacío.
    crud_model_name = fields.NonStored(
        default=lambda action: (
            action.crud_model_id.model if action.crud_model_id else False),
        help_text='Odoo crud_model_name. Nombre técnico del modelo destino.',
    )
    #: ≙ ``update_field_type = fields.Selection(related='update_field_id.ttype')``
    #: (``:667``).
    update_field_type = fields.NonStored(
        default=lambda action: (
            action.update_field_id.ttype if action.update_field_id else False),
        help_text='Odoo update_field_type. Tipo del campo a actualizar.',
    )
    #: ≙ ``value_field_to_show`` (``:694-701``) — cuál de los seis campos de
    #: valor enseña el formulario. La fuente deja escrito en el propio nombre
    #: del método que es candidato a retirarse en favor del ``ttype`` en la
    #: vista; se porta con esa nota, no como diseño propio.
    value_field_to_show = fields.NonStored(
        default=lambda action: action._compute_value_field_to_show(),
        help_text='Odoo value_field_to_show. Qué campo de valor mostrar.',
    )
    #: ≙ ``webhook_sample_payload`` (``:709``) — la carga de ejemplo que el
    #: formulario enseña para que quien configura el webhook vea la forma del
    #: JSON antes de que exista ningún envío.
    webhook_sample_payload = fields.NonStored(
        default=lambda action: action._compute_webhook_sample_payload(),
        help_text='Odoo webhook_sample_payload. Carga de ejemplo del webhook.',
    )

    class Meta:
        db_table = 'ir_act_server'
        ordering = ['sequence', 'name', 'id']
        verbose_name = 'Acción de servidor'
        verbose_name_plural = 'Acciones de servidor'

    # ---- Las dos acciones de apertura de la referencia -------------------

    def action_open_parent_action(self):
        """≙ ``action_open_parent_action`` (``odoo19c: ir_actions.py:1328-1335``).

        Devuelve el descriptor ``ir.actions.act_window`` que abre la accion
        padre. ``ir.cron`` delega aqui (``ir_cron.py:889-891``), que es por
        que el metodo vive en este modelo y no alli.

        Sin ``parent`` declarado —el estado hasta este pase— no habia a que
        apuntar y el metodo era una firma vacia.
        """
        return {
            'type': 'ir.actions.act_window',
            'target': 'current',
            'views': [[False, 'form']],
            'res_model': self.TYPE,
            'res_id': self.parent_id,
        }

    def action_open_scheduled_action(self):
        """≙ ``action_open_scheduled_action`` (``odoo19c: :1337-1344``).

        Abre el ``ir.cron`` que esta accion respalda. La fuente lo resuelve
        con ``self.ir_cron_ids.ids[0]``; aqui el inverso de la FK de
        ``IrCron`` se llama ``crons``, y **incluye los inactivos** sin hacer
        nada: el manager por defecto de Django no filtra, que es exactamente
        lo que la fuente pide con ``context={'active_test': False}``
        (``:641``).

        Devuelve ``None`` cuando la accion no respalda ningun cron — la
        fuente indexaria ``[0]`` y reventaria con ``IndexError``. Divergencia
        declarada: un descriptor que apunta a nada no es mas util que
        ninguno, y aqui el llamador es una vista React que sabe leer el
        ``None``.
        """
        cron = self.crons.first()
        if cron is None:
            return None
        return {
            'type': 'ir.actions.act_window',
            'target': 'current',
            'views': [[False, 'form']],
            'res_model': 'ir.cron',
            'res_id': cron.pk,
        }

    @classmethod
    def _warning_depends(cls):
        """≙ ``_warning_depends`` (``odoo19c: ir_actions.py:744-757``).

        Los nombres de los que ``warning`` depende. Se declaran **con los
        nombres de la fuente**, incluidos los de campos que este árbol aún no
        tiene: la lista es el contrato de dependencia, y recortarla escondería
        qué falta. Los que no existen aquí no se recalculan porque no hay quien
        los escriba, no porque la lista los omita.
        """
        return [
            'state',
            'model_id',
            'group_ids',
            'parent_id',
            'child_ids.warning',
            'child_ids.model_id',
            'child_ids.group_ids',
            'update_path',
            'update_field_type',
            'evaluation_type',
            'webhook_field_ids',
        ]

    def _get_warning_messages(self, seen=None):
        """≙ ``_get_warning_messages`` (``odoo19c: ir_actions.py:761-799``).

        Los motivos por los que esta acción está mal configurada, uno por
        mensaje. La fuente tiene **seis** ramas; aquí se portan las dos que
        tienen receptor, y las otras cuatro están medidas abajo con su
        desenlace — ninguna se omite en silencio.

        Portadas
        ========

        1. **El modelo de una hija no coincide** con el del padre. Aquí la
           comparación es sobre ``model_name`` (``Char``) en vez de sobre la FK
           ``model_id``; la conversión a FK es la tarea **#139** y no cambia
           esta rama, sólo el tipo del lado que compara.
        2. **Alguna hija trae aviso.** Es la rama recursiva —``recursive=True``
           en el campo de la fuente— y es la que ``_check_children`` consume.

        Con desenlace declarado
        =======================

        3. ``group_ids`` — **divergencia de mecanismo, no bloqueo**: aquí la
           autorización efectiva es por CAPACIDAD (DEC-11, ``HasCapability``,
           fail-closed), no una lista de grupos colgada del registro. Es la
           misma divergencia que ``ir.model.access`` declara. Portar la columna
           no cambiaría quién decide, así que la rama no tiene qué comparar.
        4. ``update_path`` con campo ``Json`` — BLOQUEADO por ``update_path``,
           que es campo del modo ``object_write``. Sucesor: tarea **#117**.
        5. ``evaluation_type == 'sequence'`` — BLOQUEADO por
           ``evaluation_type``. Sucesor: tarea **#117**.
        6. ``webhook_field_ids`` con campo restringido por grupo — BLOQUEADO
           por ``webhook_field_ids``. Sucesor: tarea **#117**.

        :param seen: los ids ya visitados, para que la recursión de la rama 2
            no se cuelgue si alguien dejó un ciclo en la base. La fuente no lo
            necesita porque su ``recursive=True`` lo resuelve el ORM; aquí el
            recorrido es nuestro y la parada también.
        """
        seen = set() if seen is None else seen
        if self.pk in seen:
            return []
        seen = seen | {self.pk}

        warnings = []
        children = list(self.child_ids.all()) if self.pk else []

        if self.model_name:
            children_with_different_model = [
                child for child in children
                if child.model_name != self.model_name]
            if children_with_different_model:
                warnings.append(
                    'Las siguientes acciones hijas deberían tener el mismo '
                    'modelo (%s): %s'
                    % (self.model_name,
                       ', '.join(child.name
                                 for child in children_with_different_model)))

        children_with_warnings = [
            child for child in children
            if child._get_warning_messages(seen)]
        if children_with_warnings:
            warnings.append(
                'Las siguientes acciones hijas tienen avisos: %s'
                % ', '.join(child.name for child in children_with_warnings))

        return warnings

    def _compute_warning(self):
        """≙ ``_compute_warning`` (``odoo19c: ir_actions.py:804-810``).

        Une los motivos con línea en blanco, o deja el campo en falso. El
        ``False`` —y no la cadena vacía— es de la fuente y es lo que hace que
        ``child_ids.filtered('warning')`` seleccione sólo a las que avisan.
        """
        warnings = self._get_warning_messages()
        return '\n\n'.join(warnings) if warnings else False

    #: ≙ ``warning`` (``odoo19c: ir_actions.py:639``):
    #: ``fields.Text(compute='_compute_warning', recursive=True)``.
    #:
    #: Es **no persistido**, como allá: se calcula al leerlo y no tiene
    #: columna. El mecanismo es ``orm.fields_nonstored.NonStored``, que este
    #: árbol construyó para el ``store=False`` de la referencia. Se declara
    #: con ``fields.NonStored`` y no con ``fields.Text(store=False, …)``
    #: porque ``Text`` no acepta ese parámetro en este árbol —sólo ``Char`` lo
    #: despacha—; el efecto es el mismo y el sitio, el de la fuente.
    warning = fields.NonStored(
        default=lambda action: action._compute_warning(),
        help_text='Odoo warning. Por qué esta acción está mal configurada.',
    )

    # ---- El nombre automático y el resto de la superficie derivada -------

    def _compute_allowed_states(self):
        """≙ ``_compute_allowed_states`` (``odoo19c: ir_actions.py:799-800``).

        La lista sale de la propia ``selection`` del campo ``state``, no de una
        constante paralela: así un addon que añada un modo lo ve ofrecido sin
        tocar dos sitios. Es lo que hacen las dos extensiones de Enterprise que
        redefinen este método.
        """
        return [value for value, __ in self._meta.get_field('state').choices]

    def _compute_available_model_ids(self):
        """≙ ``_compute_available_model_ids`` (``:851-856``).

        La fuente acota con ``ir.model.access._get_allowed_models()``. Aquí la
        autorización efectiva la decide la **capacidad** (DEC-11,
        ``HasCapability``, fail-closed) en la vista, no una lista colgada del
        registro; este cómputo devuelve el censo de modelos reflejados, que es
        el universo del que la vista después recorta. Divergencia de
        mecanismo, declarada: el conjunto es igual o mayor, y quien decide no
        cambia.
        """
        return list(IrModel.objects.values_list('id', flat=True))

    def _generate_action_name(self):
        """≙ ``_generate_action_name`` (``:819-831``) — el nombre que se pone sola.

        Tres modos tienen etiqueta propia porque nombran su destino; el resto
        cae a la etiqueta de su ``state``. ``object_copy`` sin registro elegido
        devuelve la forma incompleta de la fuente (*"Duplicar ..."*), que es
        deliberada: el formulario la enseña mientras falta el dato.
        """
        if self.state == 'object_create':
            return 'Crear %s' % (
                self.crud_model_id.name if self.crud_model_id else '')
        if self.state == 'object_write':
            return 'Actualizar %s' % (
                self.crud_model_id.name if self.crud_model_id else '')
        if self.state == 'object_copy':
            if not self.crud_model_id or not self.resource_ref:
                return 'Duplicar ...'
            return 'Duplicar %s' % self.resource_ref
        return dict(self.STATE_CHOICES).get(self.state, '')

    @classmethod
    def _name_depends(cls):
        """≙ ``_name_depends`` (``:833-838``) — de qué depende el nombre.

        Se declara como método y no como lista literal por la misma razón que
        ``_warning_depends``: la fuente lo hace así para que una extensión
        pueda añadir su propia dependencia sin reescribir el decorador.
        """
        return ['state', 'crud_model_id', 'resource_ref']

    def _compute_name(self):
        """≙ ``_compute_name`` (``:840-845``).

        ``was_automated`` es el pivote: sólo se pisa ``name`` si el que había
        era el que la acción se había puesto sola. Sin ``automated_name`` no
        habría con qué compararlo y el cómputo borraría el nombre del usuario
        en cada guardado.
        """
        was_automated = (self.name or '') == (self.automated_name or '')
        self.automated_name = self._generate_action_name()
        if was_automated:
            self.name = self.automated_name

    @api.onchange('name')
    def _onchange_name(self):
        """≙ ``_onchange_name`` (``:847-851``) — vaciar el nombre lo repuebla."""
        if not self.name:
            self.automated_name = self._generate_action_name()
            self.name = self.automated_name

    def _compute_show_code_history(self):
        """≙ ``_compute_show_code_history`` (``:788-796``).

        Cierto sólo si hay alguna revisión **distinta** de la vigente: una
        acción cuyo historial es su propio código no tiene nada que comparar.
        """
        if self.state != 'code' or not self.pk:
            return False
        return IrActionsServerHistory.objects.filter(
            action_id=self.pk).exclude(code=self.code or '').exists()

    def _compute_value_field_to_show(self):
        """≙ ``_compute_value_field_to_show`` (``:1244-1257``).

        La fuente deja escrito en el propio nombre del método que es candidato
        a retirarse en favor del ``ttype`` en la vista; se porta con esa nota.
        """
        if self.evaluation_type == 'sequence':
            return 'sequence_id'
        ttype = self.update_field_id.ttype if self.update_field_id else None
        if ttype in ('one2many', 'many2one', 'many2many'):
            return 'resource_ref'
        if ttype == 'selection':
            return 'selection_value'
        if ttype == 'boolean':
            return 'update_boolean_value'
        if ttype == 'html':
            return 'html_value'
        return 'value'

    def _compute_webhook_sample_payload(self):
        """≙ ``_compute_webhook_sample_payload`` (``:858-877``).

        Si el modelo ya tiene algún registro, la muestra se arma con él; si no,
        con el valor de ejemplo por tipo de ``WEBHOOK_SAMPLE_VALUES``. Las
        claves pasan por ``stringify_keys`` antes de serializar, igual que
        allá: la carga puede traer mapas con claves que no son cadena.
        """
        if self.state != 'webhook':
            return False
        payload = {
            '_id': 1,
            '_model': self.model_name,
            '_action': '%s(#%s)' % (self.name, self.pk),
        }
        if self.model_name:
            model = model_by_key(self.model_name)
            sample = model.objects.first() if model is not None else None
            for field_row in (self.webhook_field_ids.all() if self.pk else []):
                if sample is not None:
                    payload['_id'] = sample.pk
                    payload[field_row.name] = getattr(
                        sample, field_row.name, None)
                else:
                    payload[field_row.name] = WEBHOOK_SAMPLE_VALUES.get(
                        field_row.ttype, WEBHOOK_SAMPLE_VALUES[None])
        return json.dumps(stringify_keys(payload), indent=4, sort_keys=True,
                          default=str)

    @classmethod
    def _get_children_domain(cls):
        """≙ ``_get_children_domain`` (``:811-817``), verbatim.

        Es el dominio que el formulario aplica al elegir hijas: del mismo
        modelo, todavía sin padre, y distinta de la que se está editando.

        ``model_id`` e ``id`` van envueltos en ``unquote`` **a propósito**: el
        cliente los resuelve contra el registro que tiene abierto, así que
        tienen que llegarle como nombres desnudos y no como las cadenas
        ``'model_id'`` e ``'id'``. Sin la clase, el ``repr`` del dominio los
        entrecomilla y el filtro compara contra un literal.
        """
        return Domain([
            ('model_id', '=', unquote('model_id')),
            ('parent_id', '=', False),
            ('id', '!=', unquote('id')),
        ])

    def _check_python_code(self):
        """≙ ``_check_python_code`` (``:960-965``) — valida, **nunca ejecuta**.

        Delega en ``test_python_expr(expr, mode='exec')``, que hace las dos
        cosas que la fuente le pide: compilar —donde se detecta la sintaxis
        rota— y validar los **opcodes** del bytecode resultante contra
        ``_SAFE_OPCODES``.

        La segunda mitad estuvo bloqueada mientras ``tools/safe_eval.py``
        validaba el AST con una whitelist de la forma de un dominio —correcta
        para ``ir.rule``, insuficiente para ``mode='exec'``—. Ese bloqueo se
        cerró con el porte completo del módulo (tarea **#140**), así que aquí
        ya no hay media validación: se llama al mismo guardián que la fuente.

        ``filtered('code')`` de la fuente se lee aquí como la guarda de salida:
        una acción sin código no tiene nada que validar. El ``sudo()`` no tiene
        destinatario —esta lectura es del propio registro, no pasa por reglas
        de fila—.

        El contrato de ``test_python_expr`` es invertido a propósito, verbatim
        de la fuente: devuelve el **mensaje** cuando algo va mal y ``False``
        cuando todo está bien. Un ``if msg`` sobre esa salida es lo que separa
        el rechazo del silencio.
        """
        if not self.code:
            return
        msg = test_python_expr(expr=self.code.strip(), mode='exec')
        if msg:
            raise ValidationError(msg)

    def _get_readable_fields(self):
        """≙ ``_get_readable_fields`` (``:1225-1228``).

        La fuente amplía la lista del padre con ``group_ids`` y ``model_name``.
        Aquí la **allowlist efectiva** es el ``Meta.fields`` explícito del
        serializer DRF —divergencia de mecanismo declarada a nivel de archivo
        en ``ir_actions_report.py:92-93``—, así que este método existe para que
        una extensión encuentre el enganche donde la fuente lo pone, y su
        salida es la misma unión.
        """
        return super()._get_readable_fields() | {'group_ids', 'model_name'}

    def history_wizard_action(self):
        """≙ ``history_wizard_action`` (``:1236-1245``) — abre el comparador."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Historial de código',
            'target': 'new',
            'views': [(False, 'form')],
            'res_model': 'server.action.history.wizard',
            'context': {'default_action_id': self.pk},
        }

    def _can_execute_action_on_records(self, records):
        """≙ ``_can_execute_action_on_records`` (``:1202-1234``) — el guardián.

        Dos caminos, como allá:

        - con ``group_ids`` declarados, basta pertenecer a uno de ellos;
        - sin ellos, se exige permiso de **escritura** sobre el modelo, y
          además sobre las filas concretas cuando las hay. La fuente distingue
          los dos porque una automatización de tipo ``onchange`` corre sobre
          registros que todavía no existen en la base.

        El rechazo se registra antes de levantar, con el mismo detalle que la
        fuente: qué acción, qué usuario y sobre qué modelo.
        """
        action_groups = list(self.group_ids.all()) if self.pk else []
        user = get_current_user()
        if action_groups:
            user_groups = (
                set(user.all_group_ids) if user is not None
                and hasattr(user, 'all_group_ids') else set())
            if not (set(action_groups) & user_groups):
                raise AccessError(
                    'No tiene permisos suficientes para ejecutar esta acción.')
            return

        model = model_by_key(self.model_name)
        login = getattr(user, 'login', None)
        if model is not None and hasattr(model, 'check_access'):
            try:
                model.check_access('write')
            except AccessError:
                _logger.warning(
                    'Acción de servidor prohibida %r ejecutada mientras el '
                    'usuario %s no tiene acceso a %s.',
                    self.name, login, self.model_name)
                raise AccessError(
                    'No tiene permisos suficientes para ejecutar esta acción.')

        if records is not None and hasattr(records, 'check_access'):
            try:
                records.check_access('write')
            except AccessError:
                _logger.warning(
                    'Acción de servidor prohibida %r ejecutada mientras el '
                    'usuario %s no tiene acceso a %s.',
                    self.name, login, records)
                raise AccessError(
                    'No tiene permisos suficientes para ejecutar esta acción.')

    @classmethod
    def _selection_target_model(cls):
        """≙ ``_selection_target_model`` (``:1259-1261``) — los pares del Reference."""
        return [(row.model, row.name)
                for row in IrModel.objects.all().order_by('model')]

    @api.onchange('crud_model_id')
    def _set_crud_model_id(self):
        """≙ ``_set_crud_model_id`` (``:1263-1271``).

        Cambiar el modelo destino invalida dos elecciones que colgaban del
        anterior: la referencia de ``object_copy`` y el campo de enlace.
        """
        if (self.state == 'object_copy' and self.resource_ref
                and getattr(self.resource_ref, '_name', None)
                != (self.crud_model_id.model if self.crud_model_id else None)):
            self.resource_ref_content_type = None
            self.resource_ref_id = None
        link = self.link_field_id
        if link is not None:
            target = self.crud_model_id.model if self.crud_model_id else None
            if not (link.model == self.model_name and link.relation == target):
                self.link_field_id = None

    @api.onchange('resource_ref')
    def _set_resource_ref(self):
        """≙ ``_set_resource_ref`` (``:1273-1277``) — la referencia va al valor."""
        if self.value_field_to_show == 'resource_ref' and self.resource_ref_id:
            self.value = str(self.resource_ref_id)

    @api.onchange('selection_value')
    def _set_selection_value(self):
        """≙ ``_set_selection_value`` (``:1279-1283``) — la opción va al valor."""
        if self.value_field_to_show == 'selection_value' and self.selection_value:
            self.value = self.selection_value.value

    def copy_data(self, default=None, seen=None):
        """≙ ``copy_data`` (``:1320-1326``) — el duplicado se nombra como tal.

        La fuente itera ``vals_list`` porque allá ``self`` es un recordset y
        ``super().copy_data()`` responde **uno por registro**. Aquí una
        instancia **es** un registro y la base devuelve un ``dict``: es la
        divergencia que ``CopyMixin.copy_data`` declara —*"Devuelve un dict, no
        una lista … la forma plural la recupera quien la necesite iterando"*—.
        El bucle de la fuente se lee entonces como su caso de un solo elemento;
        el resto del cuerpo es verbatim.

        ``seen`` viaja porque la base lo usa como guarda contra la recursión de
        una relación circular, y una sobrescritura que lo tragara la anularía:
        ``copy`` lo pasa al duplicar las hijas, que en este modelo son otras
        acciones (``child_ids``) y pueden encadenarse.

        ``None`` de la base —el registro ya se visitó— sale tal cual: añadirle
        el sufijo a un duplicado que no se va a crear sería inventar valores.
        """
        default = default or {}
        values = super().copy_data(default=default, seen=seen)
        if values is not None and not default.get('name'):
            values['name'] = '%s (copia)' % (values.get('name', ''),)
        return values

    #: ≙ ``sensible_default_fields`` (``:599``), traducida a nuestros nombres.
    #: Los cuatro primeros pierden el sufijo ``_id`` por la convención de FK
    #: del árbol (tarea **#141**); ``state`` y ``active`` no lo llevaban.
    SENSIBLE_DEFAULT_FIELDS = ['partner', 'user', 'users', 'stage', 'state',
                               'active']

    @classmethod
    def _default_update_path(cls):
        """≙ ``_default_update_path`` (``:594-603``).

        El primer campo *sensato* que el modelo por defecto tenga y no sea de
        sólo lectura. La lista de candidatos es la de la fuente, en su orden;
        no es heurística nuestra.

        **La lista se traduce, y una entrada colisiona.** Al quitar el sufijo
        ``_id`` de las FK, ``state_id`` de la fuente pasa a llamarse ``state``
        aquí — y ``state`` ya es una entrada de esta lista, con otro
        significado: allá nombra el **estado de flujo** del registro. Medido
        sobre las dos raíces de addon de ``odoo19c``, el campo llamado ``state``
        es ``Selection`` en **98** declaraciones, ``Many2one`` en **1**
        (``res_bank.py:27``, la entidad federativa) y ``Char`` en **1**. La
        acepción de la lista es la de las 98.

        Por eso ``state`` se acepta sólo cuando **no es una relación**: sin ese
        discriminador, ``res.partner`` —cuyo ``state_id`` de la fuente aquí se
        llama ``state``— devolvía la entidad federativa como campo por defecto
        a actualizar, en vez de ``active``. No es heurística: es la traducción
        del significado que la fuente le da a esa entrada.

        Se recorren los campos **propios** del modelo y no ``_meta.get_fields()``
        entero, porque aquél incluye las relaciones inversas que otro modelo
        declara con ``related_name``. La fuente itera ``model._fields``, que son
        sólo los suyos; contar las inversas mediría otra población.

        ``editable`` es el ``readonly`` de la fuente con el signo invertido: es
        el atributo con que Django dice lo mismo.
        """
        model_id = get_context().get('default_model_id')
        if not model_id:
            return ''
        row = IrModel.objects.filter(pk=model_id).first()
        if row is None:
            return ''
        model = model_by_key(row.model)
        if model is None:
            return ''
        own = {f.name: f for f in model._meta.get_fields()
               if getattr(f, 'concrete', False)}
        for field_name in cls.SENSIBLE_DEFAULT_FIELDS:
            field = own.get(field_name)
            if field is None or not getattr(field, 'editable', True):
                continue
            if field_name == 'state' and field.is_relation:
                continue
            return field_name
        return ''

    def _check_children(self):
        """≙ ``_check_children`` (``odoo19c: ir_actions.py:967-973``), entero.

        Las **dos** mitades de la fuente, con sus mensajes:

        - *"Recursion found in child server actions"* — el modo ``multi``
          existe **para** encadenar, así que la guarda tiene que distinguir una
          cadena legítima de un ciclo: recorre hacia arriba y para cuando se
          repite. Sin ella, ``_run_action_multi`` —que itera ``child_ids`` y
          llama ``run()`` en cada hija— no tendría condición de parada.
        - *"Following child actions have warnings"* — una acción no se guarda
          si alguna de sus hijas está mal configurada. Estuvo declarada
          bloqueada por ``warning``, que ahora existe (tarea **#116**).
        """
        seen = set()
        current = self.parent
        while current is not None:
            if current.pk == self.pk or current.pk in seen:
                raise ValidationError(
                    'Recursión encontrada en las acciones de servidor hijas.')
            seen.add(current.pk)
            current = current.parent

        children_with_warnings = [
            child for child in (self.child_ids.all() if self.pk else [])
            if child.warning]
        if children_with_warnings:
            raise ValidationError(
                'Las siguientes acciones hijas tienen avisos: %s'
                % ', '.join(child.name for child in children_with_warnings))

    def save(self, *args, **kwargs):
        """``@api.constrains('parent_id', 'child_ids')`` de la fuente.

        Aquí también se dispara ``_compute_name``. En la fuente lo dispara el
        ORM: ``automated_name`` es ``Char(compute='_compute_name', store=True)``
        con ``@api.depends(lambda self: self._name_depends())`` (``:843``), así
        que el motor lo recalcula cada vez que cambia una de sus tres
        dependencias. Aquí el cómputo con columna se invoca explícitamente
        antes del ``super().save()`` —misma forma que ``complete_name`` en
        ``res_partner``—: ``store=True`` significa que el valor se persiste, no
        que se derive en cada lectura.

        Va **antes** del ``super()`` por eso mismo: después, la fila ya se
        escribió y las dos columnas irían a disco en un segundo ``UPDATE``.

        Aquí se registra también la revisión del código. La fuente lo hace en
        **dos** métodos —``create`` (``:720-726``) anota la primera y ``write``
        (``:730-732``) cada cambio posterior—; en este stack los dos caminos
        pasan por ``save``, así que la rama la decide si la fila ya existe.
        """
        creating = self._state.adding or self.pk is None
        previous_code = None if creating else (self._origin.code or '')

        self._check_children()
        self._check_python_code()
        self._compute_name()
        result = super().save(*args, **kwargs)
        self._record_code_revision(creating, previous_code)
        return result

    def _record_code_revision(self, creating, previous_code):
        """Anota la revisión del código — ≙ ``create`` (``:720-726``) y
        ``write`` (``:730-732``).

        Al **crear**, la fuente anota la primera revisión sólo si ``"code" in
        vals``: una acción que nace sin código no tiene nada que versionar. Su
        equivalente aquí es que el campo traiga texto — el ``in vals`` de allá
        distingue *ausente* de *vacío*, y aquí ambos llegan como cadena vacía
        porque la columna declara ``default=''``.

        Al **escribir**, la guarda de la fuente es ``new_code != self.code``,
        donde ``self.code`` es el valor **guardado**: dentro de ``write`` el
        registro todavía no se ha actualizado. Aquí ``self`` ya trae el valor
        nuevo cuando ``save`` corre, así que el anterior se lee de
        ``self._origin`` **antes** del ``super()`` y llega como parámetro. Sin
        eso la comparación sería del valor consigo mismo y toda escritura
        anotaría una revisión.

        Va **después** del ``super()`` y no antes: la revisión apunta a la
        acción por clave ajena, y al crear esa clave no existe hasta que la
        fila se escribe.
        """
        code = self.code or ''
        if creating:
            if code:
                IrActionsServerHistory.objects.create(action=self, code=code)
            return
        if code and code != previous_code:
            IrActionsServerHistory.objects.create(action=self, code=code)

    # ---- El motor de ejecución (#117) -------------------------------------
    #
    # Cinco de los seis modos corren aquí. El sexto —``code``— sigue sin
    # correr, y **por su propia razón**: evalúa Python almacenado, la misma
    # divergencia que ``ir_rule.domain_force``. Igual que la rama ``equation``
    # de ``_eval_value``. Las dos levantan con su motivo; ninguna calla.

    def _get_runner(self):
        """≙ ``_get_runner`` (``odoo19c: ir_actions.py:980-987``).

        Devuelve ``(corredor, multi)``. Primero busca ``_run_action_<state>_multi``
        —que opera sobre todos los registros activos de una vez— y si no
        existe cae al ``_run_action_<state>`` simple, que ``_run`` invoca una
        vez por registro activo.

        Se resuelve sobre ``type(self)`` y no sobre ``self`` a propósito: la
        fuente usa ``self.env.registry[self._name]``, o sea la **clase**, para
        que una subclase que redefina el corredor gane sin que el método
        quede ligado a esta instancia.
        """
        model = type(self)
        runner = getattr(model, f'_run_action_{self.state}_multi', None)
        if runner is not None:
            return runner, True
        return getattr(model, f'_run_action_{self.state}', None), False

    def _run_action_multi(self, eval_context=None):
        """≙ ``_run_action_multi`` (``:1019-1023``).

        Encadena a las hijas **en su orden**, y devuelve el último resultado
        que no sea falso. El ``sorted()`` de la fuente es el ``_order`` del
        modelo (``sequence,name,id``), que aquí es el ``ordering`` del ``Meta``
        — o sea que el reverso ya llega ordenado y no hace falta repetirlo.
        """
        result = False
        for child in self.child_ids.all():
            result = child.run() or result
        return result

    def _run_action_object_write(self, eval_context=None):
        """≙ ``_run_action_object_write`` (``:1025-1038``).

        Escribe el valor calculado en el campo al final de ``update_path``,
        sobre el registro activo. La fuente tiene dos ramas: la de
        ``onchange_self`` —el formulario aún sin guardar— y la de la ruta.

        La primera **no se porta y no es omisión**: ``onchange_self`` es el
        registro en edición que el cliente web de la referencia mantiene vivo
        entre pulsaciones, y este árbol no tiene ese mecanismo (su equivalente
        es el estado del formulario React, que vive en el navegador). La rama
        que sí tiene receptor es la de la ruta, y es la que corre.
        """
        values = self._eval_value(eval_context=eval_context)
        if not self.update_field_id or not self.update_path:
            return False
        target = self._target_records_of_path()
        if target is None:
            return False
        target.write({self.update_field_id.name: values[self.pk]})
        return False

    def _run_action_object_create(self, eval_context=None):
        """≙ ``_run_action_object_create`` (``:1097-1109``).

        Crea un registro del modelo destino con ``value`` como nombre, y si
        hay ``link_field_id`` lo engancha al registro activo.
        """
        target_model = self._crud_model()
        if target_model is None:
            return False
        new_id, _name = target_model.name_create(self.value)
        self._link_to_active_record(new_id)
        return False

    def _run_action_object_copy(self, eval_context=None):
        """≙ ``_run_action_object_copy`` (``:1084-1095``).

        Duplica el registro que ``resource_ref`` señala y, si hay
        ``link_field_id``, engancha la copia al registro activo.
        """
        source = self.resource_ref
        if source is None:
            return False
        duplicate = source.copy()
        self._link_to_active_record(duplicate.pk)
        return False

    def _run_action_webhook(self, eval_context=None):
        """≙ ``_run_action_webhook`` (``:1038-1083``).

        Arma la carga y la envía **después del commit**, que es lo que la
        fuente consigue con ``self.env.cr.postcommit.add``: aquí es
        ``transaction.on_commit``, el mismo mecanismo con otro nombre. Su
        gemelo ``postrollback`` —que sólo registra el aviso de que la llamada
        se canceló— no tiene análogo en Django y se resuelve al revés: como
        nada se encola hasta el commit, un rollback simplemente no envía.

        El envío usa ``requests``, que es la librería que la fuente importa.
        La estrategia es la suya: *"send and forget"* con un segundo de
        espera, para no bloquear al usuario si el destino es lento.
        """
        record = self._active_record()
        if record is None:
            return False
        if not self.webhook_url:
            raise UserError(
                'Con gusto envío el webhook, pero hace falta una URL a la que '
                'llegar.')
        payload = {
            '_model': self.model_name,
            '_id': record.pk,
            '_action': f'{self.name}(#{self.pk})',
        }
        for field_row in self.webhook_field_ids.all():
            payload[field_row.name] = getattr(record, field_row.name, None)
        body = json.dumps(payload, sort_keys=True, default=str)
        url = self.webhook_url

        def _post():
            _logger.debug('Llamada webhook a %s — inicio', url)
            try:
                response = requests.post(
                    url, data=body,
                    headers={'Content-Type': 'application/json'}, timeout=1)
                response.raise_for_status()
                _logger.info('Llamada webhook a %s — correcta', url)
            except requests.exceptions.ReadTimeout:
                _logger.warning(
                    'La llamada webhook agotó su segundo de espera — pudo '
                    'llegar o no. Si pasa a menudo, el sistema destino es '
                    'lento o no funciona.')
            except requests.exceptions.RequestException as error:
                _logger.warning('La llamada webhook falló: %s', error)

        _logger.info('Llamada webhook a %s', url)
        transaction.on_commit(_post)
        return False

    # ---- Los ayudantes que los corredores comparten -----------------------

    def _crud_model(self):
        """La clase Django del modelo destino del CRUD, o ``None``.

        ≙ ``self.env[self.crud_model_id.model]``. Devolver ``None`` en vez de
        reventar es lo mismo que hace ``IrModel.django_model``: una fila puede
        sobrevivir al modelo que reflejaba.
        """
        name = self.crud_model_id.model if self.crud_model_id else self.model_name
        if not name:
            return None
        try:
            return apps.get_model(name)
        except (LookupError, ValueError):
            return None

    def _active_record(self):
        """El registro sobre el que la acción corre — ``browse(active_id)``."""
        active_id = get_context().get('active_id')
        if not active_id or not self.model_name:
            return None
        try:
            model = apps.get_model(self.model_name)
        except (LookupError, ValueError):
            return None
        return model.objects.filter(pk=active_id).first()

    def _target_records_of_path(self):
        """El destino de ``update_path`` — ``reduce(getitem, path[:-1], rec)``.

        La fuente recorre todos los tramos menos el último, que es el campo a
        escribir. Con un solo tramo el destino **es** el registro activo.
        """
        record = self._active_record()
        if record is None:
            return None
        for name in self.update_path.split('.')[:-1]:
            record = getattr(record, name, None)
            if record is None:
                return None
        return record

    def _link_to_active_record(self, new_id):
        """≙ el bloque ``if self.link_field_id`` de los dos modos de creación.

        La fuente distingue el campo relacional múltiple —al que **añade** con
        ``Command.link``— del ``Many2one``, al que **asigna** el id.
        """
        if not self.link_field_id or not new_id:
            return
        record = self._active_record()
        if record is None:
            return
        name = self.link_field_id.name
        if self.link_field_id.ttype in ('one2many', 'many2many'):
            record.write({name: [Command.link(new_id)]})
        else:
            record.write({name: new_id})

    def _get_relation_chain(self, searched_field_name):
        """≙ ``_get_relation_chain`` (``:909-935``).

        Devuelve ``(cadena_de_campos, ruta_legible)``. Rechaza una ruta que
        atraviese un campo no relacional que no sea el último — el mensaje es
        el de la fuente, sin su broma sobre el reino cuántico.
        """
        value = getattr(self, searched_field_name, None)
        if not value or not self.model_name:
            return [], ''
        path = value.split('.')
        try:
            model = apps.get_model(self.model_name)
        except (LookupError, ValueError):
            return [], ''
        chain = []
        for name in path:
            field = model._meta.get_field(name)
            if name != path[-1]:
                if not field.is_relation:
                    raise ValidationError(
                        'La ruta de "%s" contiene un campo no relacional '
                        '(%s) que no es el último. Sólo el último tramo '
                        'puede ser no relacional.'
                        % (searched_field_name, name))
                model = field.related_model
            chain.append(field)
        readable = ' > '.join(
            str(getattr(field, 'verbose_name', field.name)) for field in chain)
        return chain, readable

    def _traverse_path(self):
        """≙ ``_traverse_path`` (``:898-907``) — el ``(modelo, campo)`` final."""
        chain, _readable = self._get_relation_chain('update_path')
        if not chain:
            return None, None
        last = chain[-1]
        label = last.model._meta.label
        model_row = IrModel.objects.filter(model=label).first()
        field_row = IrModelFields.objects.filter(
            model=label, name=last.name).first()
        return model_row, field_row

    def _compute_crud_relations(self):
        """≙ ``_compute_crud_relations`` (``:864-895``).

        Deja ``crud_model_id`` y ``update_field_id`` coherentes con el modo:
        los dos de creación apuntan al modelo de la acción y no tienen ruta;
        ``object_write`` deriva ambos de ``update_path`` cuando la hay.
        """
        if self.model_name and self.state in (
                'object_write', 'object_create', 'object_copy'):
            if self.state in ('object_create', 'object_copy'):
                self.crud_model_id = IrModel.objects.filter(
                    model=self.model_name).first()
                self.update_field_id = None
                self.update_path = ''
            elif self.update_path:
                model_row, field_row = self._traverse_path()
                self.crud_model_id = model_row
                self.update_field_id = field_row
                needs_related = (
                    self.evaluation_type == 'value' and field_row is not None
                    and field_row.relation)
                self.update_related_model_id = (
                    IrModel.objects.filter(model=field_row.relation).first()
                    if needs_related else None)
            else:
                self.crud_model_id = IrModel.objects.filter(
                    model=self.model_name).first()
                self.update_field_id = None
        else:
            self.crud_model_id = None
            self.update_field_id = None
            self.update_path = ''

    def _eval_value(self, eval_context=None):
        """≙ ``_eval_value`` (``:1285-1318``) — sus OCHO ramas.

        Siete resuelven sin evaluar nada: la secuencia, las cuatro operaciones
        de campo relacional múltiple, el booleano, el entero, el flotante y el
        ``html``. La octava —``equation``— evalúa Python almacenado y es la
        divergencia declarada del módulo: **levanta con su motivo** en vez de
        devolver la cadena sin evaluar, que sería escribir el texto del
        programa en el campo y llamarlo éxito.
        """
        expression = self.value
        ttype = self.update_field_id.ttype if self.update_field_id else None
        if self.evaluation_type == 'equation':
            raise NotImplementedError(
                'El modo de valor "equation" evalúa Python almacenado; este '
                'árbol no monta un evaluador sobre entrada guardada sin '
                'decidir explícitamente su contexto (misma decisión que '
                'ir_rule.domain_force). Ver el docstring del módulo.')
        if self.evaluation_type == 'sequence':
            expression = (
                self.sequence_id.next_by_id() if self.sequence_id else False)
        elif ttype in ('one2many', 'many2many'):
            operation = self.update_m2m_operation
            if operation == 'add':
                expression = [Command.link(int(self.value))]
            elif operation == 'remove':
                expression = [Command.unlink(int(self.value))]
            elif operation == 'set':
                expression = [Command.set([int(self.value)])]
            elif operation == 'clear':
                expression = [Command.clear()]
        elif ttype == 'boolean':
            expression = self.update_boolean_value == 'true'
        elif ttype in ('many2one', 'integer'):
            try:
                expression = int(self.value)
                if expression == 0 and ttype == 'many2one':
                    expression = False
            except (TypeError, ValueError):
                # silent OK because la fuente traga la excepción igual
                # (``except Exception: pass``, ``odoo19c: ir_actions.py:1310``)
                # y deja el valor como cadena: un entero mal escrito no debe
                # tumbar la acción, lo rechaza después la validación del campo.
                pass
        elif ttype == 'float':
            try:
                expression = float(self.value)
            except (TypeError, ValueError):
                # silent OK because idéntico al anterior — la fuente lo
                # escribe con ``contextlib.suppress(Exception)`` (``:1313``).
                pass
        elif ttype == 'html':
            expression = self.html_value
        return {self.pk: expression}

    def _get_eval_context(self, action=None):
        """≙ ``_get_eval_context`` (``:1111-1149``).

        El diccionario que la fuente pasa a ``safe_eval``. Se porta **entero**
        aunque aquí ningún corredor lo evalúe: es el contrato que un corredor
        propio recibe, y los cinco que corren lo reciben igual.

        Lo que NO se porta y por qué: ``env``, ``uid`` y ``user`` de la base
        (``:140-153``) son el ``Environment`` de la referencia, que este árbol
        resuelve con ``orm.environments`` y no con un objeto que se pase de
        mano en mano; ``time``/``datetime``/``dateutil`` son los módulos que
        su evaluador restringido necesita exponer, y sin evaluador no tienen
        receptor.
        """
        action = self if action is None else action
        context = get_context()
        model = None
        if action.model_name:
            try:
                model = apps.get_model(action.model_name)
            except (LookupError, ValueError):
                model = None
        record = records = None
        if model is not None and context.get('active_model') == action.model_name:
            if context.get('active_id'):
                record = model.objects.filter(pk=context['active_id']).first()
            if context.get('active_ids'):
                records = model.objects.filter(pk__in=context['active_ids'])

        def log(message, level='info'):
            """≙ el ``log`` de la fuente: una fila en ``ir_logging``."""
            IrLogging = apps.get_model('base', 'IrLogging')
            IrLogging.objects.create(
                type='server', name=__name__, level=level, message=message,
                path='action', line=str(action.pk), func=action.name or '')

        return {
            'model': model,
            'UserError': UserError,
            'record': record,
            'records': records,
            'log': log,
            '_logger': _logger,
        }

    def run(self):
        """≙ ``run`` (``:1151-1181``) — el punto de entrada del motor.

        La fuente itera sobre ``self`` porque allá un recordset puede traer
        varias acciones; aquí ``self`` es **una** instancia y ese bucle
        colapsa. El resto es idéntico: se arma el contexto de evaluación, se
        determinan los registros sobre los que operar y se delega en ``_run``.
        """
        eval_context = self._get_eval_context(self)
        records = eval_context.get('records')
        if records is None and eval_context.get('record') is not None:
            records = type(eval_context['record']).objects.filter(
                pk=eval_context['record'].pk)
        return self._run(records, eval_context)

    def _run(self, records, eval_context):
        """≙ ``_run`` (``:1183-1207``).

        Tres cosas, en este orden: **rehúsa** si la acción trae avisos, elige
        el corredor, y lo invoca — una vez si es ``_multi``, o una vez por
        registro activo si no lo es.
        """
        if self.warning:
            raise ServerActionWithWarningsError(
                'La acción de servidor %s tiene uno o más avisos; resuélvelos '
                'primero.' % self.name)

        runner, multi = self._get_runner()
        result = False
        if runner is not None and multi:
            return runner(self, eval_context=eval_context)
        if runner is not None:
            context = get_context()
            active_id = context.get('active_id')
            active_ids = context.get(
                'active_ids', [active_id] if active_id else [])
            for active_id in active_ids:
                with context_scope(active_ids=[active_id], active_id=active_id):
                    if records is not None:
                        current = records.filter(pk=active_id).first()
                        eval_context['record'] = current
                        eval_context['records'] = records.filter(pk=active_id)
                    result = runner(self, eval_context=eval_context)
            return result
        _logger.warning(
            'No hay manera de ejecutar la acción de servidor %r de tipo %r; '
            'se ignora. Verifica que el tipo sea correcto o añade un método '
            '`_run_action_<tipo>` o `_run_action_<tipo>_multi`.',
            self.name, self.state)
        return result

    # ---- Las dos acciones contextuales ------------------------------------

    def create_action(self):
        """≙ ``create_action`` (``:989-994``) — ancla la acción a su modelo."""
        self.binding_model_name = self.model_name
        self.binding_type = 'action'
        self.save(update_fields=['binding_model_name', 'binding_type'])
        return True

    def unlink_action(self):
        """≙ ``unlink_action`` (``:996-1000``) — retira el anclaje."""
        if self.binding_model_name:
            self.binding_model_name = ''
            self.save(update_fields=['binding_model_name'])
        return True


class IrActionsTodo(TimeStampedModel):
    """Paso pendiente de configuración (``ir.actions.todo``)."""

    STATE_OPEN = 'open'
    STATE_DONE = 'done'
    STATE_CHOICES = [
        (STATE_OPEN, 'Por hacer'),
        (STATE_DONE, 'Hecho'),
    ]

    action = fields.Many2one(
        IrActionsActions, on_delete=models.CASCADE, db_index=True,
        related_name='todos', verbose_name='Acción')
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    state = fields.Selection(
        max_length=8, choices=STATE_CHOICES, default=STATE_OPEN,
        verbose_name='Estado')
    name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Nombre')

    class Meta:
        db_table = 'ir_actions_todo'
        ordering = ['sequence', 'id']
        verbose_name = 'Tarea de configuración'
        verbose_name_plural = 'Tareas de configuración'

    def __str__(self):
        return self.name or f'todo #{self.pk}'
