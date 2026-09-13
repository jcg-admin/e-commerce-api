"""Modelo ``StockMove`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_move.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

El movimiento es la unidad de intención del inventario: dice **qué producto**,
**cuánto**, **de dónde** y **a dónde**, y en qué estado está esa intención. La
ejecución real la llevan sus líneas (``stock.move.line``), que son las que
tocan las existencias; el movimiento agrega, encadena y decide.

Porte en DOS PASES — este archivo es el primero
=================================================

Medido sobre ``odoo19c: addons/stock/models/stock_move.py`` (2825 líneas):
**74 campos y 131 métodos**. El grafo de ``stock`` es un **ciclo** y se rompe
partiéndolo, según el orden que fija :ref:`h-api-601`:

===  =========================  ====================================================
#    Archivo                    Qué aporta
===  =========================  ====================================================
1    ``stock_reference.py``     cerrado — desbloquea ``reference_ids``
2    **este pase**              los **73 campos** declarables (74 menos uno)
3    ``product.py``             los 7 símbolos que el orderpoint consume
4    ``stock_orderpoint.py``    consume el paso 3
5    segundo pase de este       ``orderpoint_id`` + los métodos que lo consumen
===  =========================  ====================================================

**El paso 5 está cerrado (tarea #382).** ``orderpoint`` se declara abajo, junto
a ``next_serial_count``, en la misma posición que la fuente
(``odoo19c: :189``). El campo faltó mientras
``stock.warehouse.orderpoint`` no existía en este árbol: una FK por cadena es
perezosa en el *orden de resolución*, no en la *existencia* del destino —
Django emite ``fields.E300`` cuando el modelo no está instalado, y el commit
``07044d3`` lo midió con 18 errores por exactamente esa causa. Aterrizado el
modelo (tarea **#257**), la FK entra con su migración y su acceso inverso
``stock_moves``, que es lo que hace resoluble el dominio
``Domain('orderpoint_id', 'in', self.ids)`` de
``odoo19c: stock_orderpoint.py:645``.

Los 73 campos de este pase
============================

Convención del árbol: una FK pierde el sufijo ``_id`` (``location_id`` →
``location``); una colección lo conserva (``move_line_ids``). Un campo que la
referencia declara ``compute=`` **sin** ``store=`` se porta como **property** —
su ORM lo recalcula en cada lectura y nunca lo persiste, que es lo que una
property ya hace. Los ``compute=`` **con** ``store=`` sí son columna, y los
invoca ``save()`` (ver :ref:`h-api-591`).

Escalares y relaciones almacenadas (columna real)
---------------------------------------------------

``sequence`` · ``priority`` · ``date`` · ``date_deadline`` · ``company`` ·
``product`` · ``never_product_template_attribute_value_ids`` ·
``description_picking_manual`` · ``product_qty`` · ``product_uom_qty`` ·
``product_uom`` · ``location`` · ``location_dest`` · ``location_final`` ·
``partner`` · ``move_orig_ids`` · ``picking`` · ``state`` · ``picked`` ·
``price_unit`` · ``origin`` · ``procure_method`` · ``scrap`` · ``rule`` ·
``propagate_cancel`` · ``delay_alert_date`` · ``picking_type`` ·
``is_inventory`` · ``inventory_name`` · ``origin_returned_move`` ·
``restrict_partner`` · ``route_ids`` · ``warehouse`` · ``quantity`` ·
``additional`` · ``reference`` · ``next_serial`` · ``next_serial_count`` ·
``reservation_date`` · ``packaging_uom`` · ``packaging_uom_qty``

Derivados (property — ``compute`` sin ``store`` en la fuente)
---------------------------------------------------------------

``product_category`` · ``description_picking`` · ``allowed_uom_ids`` ·
``product_tmpl`` · ``location_usage`` · ``location_dest_usage`` ·
``move_dest_ids`` · ``package_ids`` · ``returned_move_ids`` · ``availability`` ·
``has_tracking`` · ``has_lines_without_result_package`` · ``show_operations`` ·
``picking_code`` · ``show_details_visible`` · ``is_storable`` · ``is_locked`` ·
``is_initial_demand_editable`` · ``is_date_editable`` ·
``is_quantity_done_editable`` · ``move_lines_count`` · ``display_assign_serial``
· ``display_import_lot`` · ``forecast_availability`` ·
``forecast_expected_date`` · ``lot_ids`` · ``show_quant`` · ``show_lots_m2o`` ·
``show_lots_text`` · ``move_line_ids`` (inverso) · ``reference_ids`` (inverso)

Divergencias declaradas en este pase
======================================

**D-1 — ``procurement_values`` no es columna.** La referencia lo declara
``fields.Json(store=False, help="Dummy field to store procurement values to
propagate them to later steps")``. Es un portapapeles entre pasos de una misma
transacción, no un dato del movimiento; aquí es un atributo de instancia con
property, que es lo mismo sin tabla de por medio.

**D-2 — ``move_orig_ids`` renombrado desde ``move_orig``.** El campo existía con
el nombre truncado y su ``related_name`` era ``move_dest``. La referencia los
llama ``move_orig_ids``/``move_dest_ids`` y la convención de este árbol conserva
el sufijo en las colecciones (``move_line_ids``, ``route_ids``). Corregido en
este pase — estado incorrecto heredado, Clausula 2.

**D-3 — ``state`` gana ``partially_available``.** Nuestro Selection tenía seis
valores y la referencia declara **siete** (``odoo19c: :106-113``). El ausente lo
consume la agregación de cantidades del producto
(``('state', 'in', (…, 'partially_available'))``, ``product.py:212``) y lo
escribe ``_recompute_state``; sin él, el paso 3 no puede portarse fiel. La
referencia lo menciona **26** veces en este mismo archivo.

**D-4 — los 131 métodos se portan por olas.** Este archivo es el mayor de la
familia: **2825 líneas** en la referencia contra las nuestras. El porte va por
olas, y cada una declara su cobertura aquí en vez de presentarse como cerrada.

Cobertura de métodos — medida, no estimada
============================================

El instrumento es el conteo por AST **normalizado**: un ``_compute_x`` cuenta
como cubierto si ``x`` existe aquí como property o como columna, porque ésa es
la forma que este árbol le da a un ``compute`` sin ``store`` (precedente en todo
el addon). Sin esa normalización el conteo crudo reporta 126 ausentes y **34 de
ellos son falsos** — es la ceguera que :ref:`h-api-579` registra.

.. list-table::
   :header-rows: 1

   * - Ola
     - Qué entra
     - Métodos
   * - —
     - los cuatro de acción que ya existían
     - 4
   * - —
     - computes portados como property (normalización de arriba)
     - 30
   * - A
     - predicados, ayudantes puros, recorrido de cadena, ``_recompute_state``
     - 40
   * - B
     - persistencia y propagación a reglas de reabastecimiento
     - 9
   * - C
     - reserva y disponibilidad: ``_update_reserved_quantity`` y su familia
     - 10
   * - D
     - fusión, división y reparto en albarán
     - 12
   * - **E** (este pase)
     - lotes y números de serie
     - **8**
   * - F
     - previsión, empuje, abastecimiento y las acciones de ventana
     - 15

**Estado tras la ola E: 116 de 131** — remedido con el instrumento de arriba, no
sumado. La ola F es la tarea **#390**; nada se difiere sin dueño.

> **La estimación de D/E/F estaba mal y se corrigió en la ola D.** La tabla decía
> 18/8/14 = 40, cuando los ausentes reales tras la ola C eran 36 (37 menos el
> falso de entonces). Reparto medido sobre la lista que el instrumento devuelve:
> **D 12 · E 8 · F 15**. La cifra de D no era una omisión de alcance — era una
> estimación escrita antes de contar, que es exactamente lo que
> ``calibration-verified-numbers.md`` prohíbe.

*Métrica:* métodos de **clase** de la referencia (131) presentes aquí por nombre,
tras normalizar el prefijo de ``compute``/``inverse``/``set``/``search`` y el
sufijo ``_id(s)``. Medido con un solo comando contra ``HEAD`` y contra el árbol
de trabajo, para que el delta no mezcle dos instrumentos (la trampa de
:ref:`h-api-350`): **106 → 114 presentes**, +8, exactamente los ocho de la ola E.
*Ciega a:* el porte que además **cambia la raíz** del nombre. De los **17** que
el instrumento reporta ausentes, **dos son falsos**:

- ``_compute_product_availability`` → property ``availability``;
- ``_compute_show_info`` → sus **tres** salidas son las properties
  ``show_quant``, ``show_lots_text`` y ``show_lots_m2o``.

De ahí 116 y no 114. **La cifra anterior (107) estaba un punto baja por esta
misma razón:** declaraba un solo falso cuando ya eran dos — las tres properties
de ``_compute_show_info`` existen desde antes de la ola D. Es la ceguera de
:ref:`h-api-579` mordiendo dos veces al mismo instrumento.

**Y uno que parecía falso y NO lo es:** ``_compute_package_ids``. El árbol tiene
``related_name='package_ids'``, pero en ``StockPackageType`` y ``StockLocation``,
**no** en ``StockMove`` — así que la ausencia es real. Se verificó en vez de
suponerse, que es la diferencia entre este conteo y el anterior.

**Tres de la ola C no entran, y tienen dueño:** ``_trigger_scheduler`` y
``_trigger_assign`` leen su interruptor de ``ir.config_parameter``, que **no
existe en el árbol** (tarea **#387**); ``_match_searched_availability`` depende
de ``forecast_availability``, que es de la ola F. Los tres siguen contados como
ausentes: entran con la ola F o con #387, lo que llegue antes.

**Uno de los 95 está portado a medias, y se dice aquí:** ``write`` tiene sus dos
guardas (cantidad de un cancelado, unidad de un hecho) y la propagación a las
reglas de reabastecimiento, pero **no** el des-reservar/re-asignar de
``product_uom_qty`` (``odoo19c: :851-871``) ni el re-cálculo de almacén
(``:891-899``). Ésos cuelgan de ``_do_unreserve`` y ``_action_assign``, que son
la ola C; portar media mitad ahora dejaría un mecanismo a medio armar sin nadie
que lo note. Es la cobertura declarada que ``porte-completo-no-parcial.md``
exige en vez del silencio.

Qué entró en la ola B
-----------------------

``default_get`` · ``create`` (con ``_normalize_create_values``, la parte pura
separada para poder probarla sin insertar) · ``write`` (parcial, arriba) ·
``unlink`` · ``_set_references`` · ``_compute_display_name`` (como property
``display_name``) · ``_update_orderpoints`` · ``_get_orderpoints_to_update`` ·
``_delay_alert_get_documents`` · ``_propagate_date_log_note``.

Dos piezas que la ola B tuvo que traer de fuera, porque sin ellas el porte
habría necesitado inventar una divergencia:

- ``stock.picking.origin`` (``odoo19c: stock_picking.py:556-558``) — lo lee
  ``_compute_display_name``. Migración ``0012_add_picking_origin``.
- ``stock.picking.reference_ids`` (``related``, ``:590-591``) — lo lee
  ``_set_references``; property, porque allá no tiene columna.

Y una divergencia de mecanismo, declarada: ``_mark_orderpoints_for_recompute``
es el ``add_to_compute`` de la fuente hecho explícito. Allá el ORM difiere el
cálculo hasta la próxima lectura; este ORM no tiene cola de cómputo diferido
(tarea **#191**), así que se ejecuta ya. Misma cifra, distinto cuándo.

Qué entró en la ola C
-----------------------

``_prepare_move_line_vals`` · ``_add_serial_move_line_to_vals_list`` ·
``_update_reserved_quantity_vals`` (la parte que **decide** el reparto, separada
para poder probarla sin escribir) · ``_update_reserved_quantity`` (la que
escribe) · ``_get_available_move_lines_in`` · ``_get_available_move_lines_out`` ·
``_get_available_move_lines`` · ``_set_quantity_done_prepare_vals`` ·
``_set_quantity_done`` · ``_adjust_procure_method``.

Una divergencia de FORMA, declarada: ``_set_quantity_done_prepare_vals`` devuelve
tuplas ``('update'|'delete'|'create', línea, vals)`` donde la fuente devuelve una
lista de ``Command``. El ``Command`` de este árbol es **ejecutivo** —escribe al
llamarlo—, así que una lista de comandos no es un valor que se pueda devolver sin
haber escrito ya. El contenido es el mismo y sus tres salidas se conservan en
orden; lo que cambia es quién aplica. La divergencia de ``Command`` está
registrada en :ref:`h-api-589` (tarea **#345**), y ésta es su consecuencia, no
una decisión nueva.

Dos piezas que la ola C tuvo que traer de fuera:

- ``Command.update`` (``orm/commands.py``) — era el único de los siete que
  faltaba; lo pide el reparto de cantidad entre líneas existentes.
- ``OrderedSet``/``LastOrderedSet``/``groupby`` en ``tools/misc.py`` — el
  ``groupby`` de la fuente agrupa por clave, no por tramo consecutivo como el del
  stdlib; sin él, ``_get_available_move_lines_*`` contaría un grupo varias veces.

Qué entró en la ola D
-----------------------

``_merge_moves_fields`` · ``_merge_move_itemgetter`` · ``_merge_moves`` ·
``_search_picking_for_assignation_domain`` · ``_search_picking_for_assignation`` ·
``_assign_picking`` · ``_assign_picking_values`` · ``_assign_picking_post_process`` ·
``_get_new_picking_values`` · ``_create_backorder`` · ``_prepare_move_split_vals`` ·
``_split``.

Tres divergencias de FORMA, declaradas:

- **La colección es explícita.** Los métodos de conjunto de la fuente operan
  sobre ``self`` como recordset; aquí llevan ``moves=None``, que por defecto es
  ``[self]``. Es la convención que ``_get_relevant_state_among_moves`` ya fijó
  en la ola A, no una decisión nueva.
- **Los contextos son parámetros.** ``merge_extra``, ``force_split_uom_id`` y
  ``source_location_id`` de la fuente entran como argumentos: este ORM no lleva
  contexto de entorno en la llamada.
- **Las relaciones múltiples se enlazan aparte.** ``_merge_moves_fields`` y
  ``_prepare_move_split_vals`` devuelven ``move_dest_ids``/``move_orig_ids``
  dentro del diccionario, igual que la fuente —allá el ORM traduce los comandos
  ``(4, id)``—; aquí ``_apply_merge`` y ``_create_backorder`` las separan antes
  de escribir. Es la misma raíz que la divergencia de ``Command`` de la ola C.

Y dos ayudantes que la referencia no tiene, porque allá no hacen falta:
``_resolve_candidates`` (el conjunto de candidatos mezcla ``attname`` de albarán
con tuplas de movimientos; allá ambas formas son el mismo recordset) y
``_apply_merge`` (separar escalares de relaciones al escribir).

Cinco piezas que la ola D tuvo que traer o arreglar de fuera:

- **Cinco campos de ``stock.picking``** — ``move_type``, ``partner``,
  ``company``, ``user`` y ``printed``, con su migración. Los cinco existen en la
  referencia y los consume el reparto en albarán; ``move_type`` además lo **ya
  leía** ``_get_relevant_state_among_moves`` sobre un modelo que no lo declaraba.
- **``StockMove.save()``** — aplica ``_compute_product_qty``, que la fuente
  declara ``store=True`` y aquí era una columna que nadie calculaba.
- **``StockPicking.save()``** — aplica ``_compute_move_type`` y el ``related`` de
  ``company``, los dos ``store=True`` en la fuente.
- **La lista de campos distintivos** — era la de 18c, con dos atributos que
  ningún modelo declara.
- **La frontera ``Decimal``/``float``** en ``_recompute_state``, que sólo
  funcionaba con un cero de por medio.

Las cinco están en :ref:`h-api-625`.

Qué entró en la ola E
-----------------------

``_compute_lot_ids`` (como la property ``lot_ids``) · ``_set_lot_ids`` (su
setter) · ``_create_lot_ids_from_move_line_vals`` · ``split_lots`` ·
``_generate_serial_move_line_commands`` · ``_generate_serial_numbers`` ·
``_onchange_lot_ids`` · ``action_generate_lot_line_vals``.

Tres divergencias de FORMA, declaradas:

- **``lot_ids`` es property con setter.** La fuente lo declara
  ``fields.Many2many(compute='_compute_lot_ids', inverse='_set_lot_ids')``
  **sin** ``store``, así que aquí es una property — la misma convención que los
  otros treinta computes sin almacenar de este archivo. El getter y el setter
  conservan el cuerpo de cada mitad.
- **Las colecciones son parámetros.** ``_set_lot_ids(lots)`` y
  ``_onchange_lot_ids(lots, previous_lots=None)`` reciben lo que allá leen del
  campo. El segundo además recibe el conjunto **anterior**: la fuente lo saca de
  ``self._origin`` —el registro sin asentar del formulario— y aquí ese búfer no
  existe; por defecto se lee de las líneas, que equivale a ``_origin`` si se
  llama **antes** de ``_set_lot_ids``, que es el orden en que la fuente dispara.
- **Los generadores devuelven tuplas, no ``Command``.** ``('update', línea,
  vals)`` / ``('create', None, vals)`` / ``('delete', línea, None)``, y las
  aplica ``_apply_move_line_commands``. Es la misma raíz que la divergencia de
  la ola C: el ``Command`` de este árbol es ejecutivo (:ref:`h-api-589`, tarea
  **#345**), así que un generador no puede devolver comandos sin haber escrito.

Y una cuarta, de tipo: ``_create_lot_ids_from_move_line_vals`` vacía el
``lot_name`` a ``None`` donde la fuente escribe ``False``. Esos valores acaban en
un ``Char(null=True)``, y un booleano en columna de texto es el defecto que
:ref:`h-api-590` registra (tarea **#346**).

**Lo que la ola E NO cierra, y tiene dueño:** el bloque final de
``action_generate_lot_line_vals`` (``odoo19c: :1193-1206``) rebobina el contador
de la secuencia tras el botón «New» del asistente. Depende de
``_get_current_sequence``, ``get_next_char`` y ``number_next_actual``, que
``ir.sequence`` **no declara en este árbol**. Es completitud de ``ir.sequence``,
no de este archivo. Sucesor: tarea **#394**.

Por qué la ola A va primero, y no las acciones
------------------------------------------------

Los cuarenta símbolos de la ola A **no dependen de ninguna pieza ausente**: son
predicados sobre campos que ya existen, ayudantes puros y el recorrido de la
cadena. Las olas siguientes los consumen —``_recompute_state`` lo llaman cinco
métodos de la ola D, ``_rollup_moves`` lo llaman tres de la F—, así que
portarlos primero evita escribirlos dos veces.

El mismo criterio reordenó el archivo: ``stock_picking.py`` iba antes en el
plan, y su orquestación llama a doce métodos de este archivo. Portarlo primero
habría producido una docena de BLOQUEADOS que la ola siguiente tendría que
retocar de inmediato. Prevalece el análisis actual (Clausula 1).
"""
import re
from collections import defaultdict
from decimal import Decimal

from django.apps import apps
from django.db.models import Q
from django.utils import timezone

import fields
import api
import models

from orm.environments import get_current_company, get_current_user
from tools.float_utils import float_compare, float_round
from tools.misc import OrderedSet, groupby
from tools.translate import _
from exceptions import UserError, ValidationError

from addons.stock.models.stock_quant import StockQuant
from addons.stock.models.stock_move_line import StockMoveLine
from addons.stock.models.stock_rule import StockRule
from addons.base.models.decimal_precision import DecimalPrecision
from addons.base.models import TimeStampedModel

#: ≙ ``PROCUREMENT_PRIORITIES`` (``odoo19c: stock_move.py:15``).
PROCUREMENT_PRIORITIES = [('0', 'Normal'), ('1', 'Urgent')]

#: ≙ ``_product_location_index`` (``:200``) — objeto de tabla, no atributo de
#: ORM: su hogar aquí es ``Meta.indexes``. La fuente no fija nombre (lo deriva
#: su ORM); el anterior ``stock_move_product_location_idx`` (31 ch) violaba el
#: límite de 30 de ``models.E034`` y bloqueaba ``manage.py migrate``.
PRODUCT_LOCATION_INDEX = models.Index(
    fields=['product', 'location', 'location_dest', 'company', 'state'],
    name='stock_move_product_loc_idx',
)


class StockMove(models.DefaultGetMixin, TimeStampedModel):
    """``stock.move`` — un movimiento de inventario."""

    # Atributos de clase de modelo — los cuatro de ORM que la referencia
    # declara (``odoo19c: addons/stock/models/stock_move.py:19-22``), verbatim.
    # El quinto (``_product_location_index``) es un objeto de tabla y vive en
    # ``Meta.indexes``, que apunta al mismo objeto.
    _name = 'stock.move'
    _description = "Stock Move"
    _order = 'sequence, id'
    _rec_name = 'reference'
    _product_location_index = PRODUCT_LOCATION_INDEX

    PRIORITY_CHOICES = PROCUREMENT_PRIORITIES

    PROCURE_MAKE_TO_STOCK = 'make_to_stock'
    PROCURE_MAKE_TO_ORDER = 'make_to_order'
    PROCURE_METHOD_CHOICES = [
        (PROCURE_MAKE_TO_STOCK, 'Default: Take From Stock'),
        (PROCURE_MAKE_TO_ORDER, 'Advanced: Apply Procurement Rules'),
    ]

    # Los SIETE estados de la referencia (``:106-113``). ``partially_available``
    # faltaba: lo consume la agregación de cantidades del producto y lo escribe
    # ``_recompute_state`` (D-3 del docstring).
    STATE_DRAFT               = 'draft'
    STATE_WAITING             = 'waiting'
    STATE_CONFIRMED           = 'confirmed'
    STATE_PARTIALLY_AVAILABLE = 'partially_available'
    STATE_ASSIGNED            = 'assigned'
    STATE_DONE                = 'done'
    STATE_CANCEL              = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Nuevo'),
        (STATE_WAITING, 'Esperando otro movimiento'),
        (STATE_CONFIRMED, 'Esperando disponibilidad'),
        (STATE_PARTIALLY_AVAILABLE, 'Parcialmente disponible'),
        (STATE_ASSIGNED, 'Disponible'),
        (STATE_DONE, 'Hecho'),
        (STATE_CANCEL, 'Cancelado'),
    ]

    # --- identificación y agenda -------------------------------------------

    sequence        = fields.Integer(
        default=10, help_text='Orden dentro del albarán (Odoo sequence).',
    )
    priority        = fields.Selection(
        max_length=1, choices=PRIORITY_CHOICES, default='0',
        help_text='Prioridad (Odoo priority, compute+store desde el albarán).',
    )
    date            = fields.Datetime(
        db_index=True, default=timezone.now,
        help_text='Fecha planificada hasta que se hace; después, la real '
                  '(Odoo date, requerido, default=Datetime.now).',
    )
    date_deadline   = fields.Datetime(
        null=True, blank=True,
        help_text='Fecha límite propagada por la cadena (Odoo date_deadline, '
                  'readonly; lo escribe _set_date_deadline).',
    )
    reservation_date = fields.Date(
        null=True, blank=True,
        help_text='Fecha a partir de la cual reservar (Odoo reservation_date, '
                  'compute+store desde el tipo de operación).',
    )
    delay_alert_date = fields.Datetime(
        null=True, blank=True,
        help_text='Fecha de alerta por retraso de un movimiento origen '
                  '(Odoo delay_alert_date, compute+store).',
    )

    # --- qué se mueve --------------------------------------------------------

    company         = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT, db_index=True,
        related_name='stock_moves', default=get_current_company,
        help_text='Empresa (Odoo company_id, requerido, '
                  'default=lambda self: self.env.company).',
    )
    product         = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT, related_name='stock_moves',
        db_index=True, help_text='Producto (Odoo product_id; el dominio excluye servicios).',
    )
    never_product_template_attribute_value_ids = fields.Many2many(
        'product.ProductTemplateAttributeValue', blank=True,
        related_name='stock_moves',
        db_table='template_attribute_value_stock_move_rel',
        help_text='Valores de atributo excluidos (Odoo '
                  'never_product_template_attribute_value_ids).',
    )
    product_uom     = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_moves',
        help_text='Unidad del movimiento (Odoo product_uom, compute+store con '
                  'readonly=False; la recalcula compute_product_uom).',
    )
    product_uom_qty = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='Cantidad demandada, en la unidad del movimiento (Odoo '
                  'product_uom_qty). Bajarla NO genera pedido pendiente.',
    )
    product_qty     = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='La misma demanda en la unidad del PRODUCTO (Odoo '
                  'product_qty, compute+store; su inverso lanza error a '
                  'propósito — se escribe product_uom_qty).',
    )
    quantity        = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='Suma de las cantidades de las líneas (Odoo quantity, '
                  'compute+store con inverso).',
    )
    packaging_uom   = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_moves_packaging',
        help_text='Unidad de empaque de la orden de origen (Odoo '
                  'packaging_uom_id, compute+store precompute).',
    )
    packaging_uom_qty = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='La demanda en la unidad de empaque (Odoo '
                  'packaging_uom_qty, compute+store).',
    )
    price_unit      = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='Coste unitario fijado al confirmar, en la divisa de la '
                  'empresa (Odoo price_unit; campo técnico, sin digits).',
    )

    # --- de dónde a dónde ----------------------------------------------------

    location        = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='moves_out',
        db_index=True, help_text='Ubicación origen (Odoo location_id, compute+store).',
    )
    location_dest   = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='moves_in',
        db_index=True,
        help_text='Ubicación destino INTERMEDIA (Odoo location_dest_id, '
                  'compute+store con inverso).',
    )
    location_final  = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, null=True, blank=True,
        related_name='moves_final', db_index=True,
        help_text='Ubicación destino FINAL de la cadena (Odoo '
                  'location_final_id). El destino intermedio es el siguiente '
                  'salto; éste es el fin del encargo.',
    )
    warehouse       = fields.Many2one(
        'stock.StockWarehouse', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_moves',
        help_text='Almacén a considerar al elegir ruta en el siguiente '
                  'aprovisionamiento (Odoo warehouse_id).',
    )
    route_ids       = fields.Many2many(
        'stock.StockRoute', blank=True, related_name='stock_moves',
        db_table='stock_route_move',
        help_text='Rutas de destino preferidas (Odoo route_ids).',
    )
    partner         = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_moves',
        help_text='Dirección de entrega opcional (Odoo partner_id, '
                  'compute+store desde el albarán).',
    )
    restrict_partner = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_moves_restricted',
        help_text='Propietario cuyos quants son los únicos considerables al '
                  'marcar hecho (Odoo restrict_partner_id).',
    )

    # --- documentos y encadenamiento -----------------------------------------

    picking         = fields.Many2one(
        'stock.StockPicking', null=True, blank=True, on_delete=models.CASCADE,
        related_name='move_ids', db_index=True,
        help_text='Transferencia (Odoo picking_id).',
    )
    picking_type    = fields.Many2one(
        'stock.StockPickingType', null=True, blank=True, on_delete=models.PROTECT,
        related_name='stock_moves',
        help_text='Tipo de operación (Odoo picking_type_id, compute+store con '
                  'readonly=False).',
    )
    rule            = fields.Many2one(
        'stock.StockRule', null=True, blank=True, on_delete=models.PROTECT,
        related_name='stock_moves',
        help_text='Regla que creó el movimiento (Odoo rule_id, '
                  "ondelete='restrict').",
    )
    move_orig_ids   = fields.Many2many(
        'self', symmetrical=False, blank=True, related_name='move_dest_ids',
        db_table='stock_move_move_rel',
        help_text='Movimientos origen que abastecen a éste (Odoo '
                  'move_orig_ids). El inverso es move_dest_ids, el nombre que '
                  'la referencia le da a la otra mitad.',
    )
    origin_returned_move = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='returned_move_ids', db_index=True,
        help_text='Movimiento que originó esta devolución (Odoo '
                  'origin_returned_move_id).',
    )
    scrap           = fields.Many2one(
        'stock.StockScrap', null=True, blank=True, on_delete=models.CASCADE,
        related_name='move_ids',
        help_text='Desecho que originó el movimiento (Odoo scrap_id). Es el '
                  'inverso que ``stock.scrap.move_ids`` declara '
                  '(odoo19c: stock/models/stock_scrap.py:37).',
    )
    origin          = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Documento de origen, en texto (Odoo origin).',
    )
    reference       = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta del movimiento (Odoo reference, compute+store). '
                  'Es el _rec_name: sale del albarán, del desecho o del '
                  'nombre de inventario, en ese orden.',
    )

    # --- estado y banderas ---------------------------------------------------

    state           = fields.Selection(
        max_length=20, choices=STATE_CHOICES, default=STATE_DRAFT, db_index=True,
        help_text='Estado (Odoo state, readonly). Los SIETE de la referencia.',
    )
    picked          = fields.Boolean(
        default=False,
        help_text='Marca indicativa de recogido (Odoo picked, compute+store '
                  'con inverso). No valida ni genera movimientos por sí sola.',
    )
    procure_method  = fields.Selection(
        max_length=16, choices=PROCURE_METHOD_CHOICES, default=PROCURE_MAKE_TO_STOCK,
        help_text='Método de suministro (Odoo procure_method). make_to_stock '
                  'espera disponibilidad; make_to_order dispara una regla.',
    )
    propagate_cancel = fields.Boolean(
        default=True,
        help_text='Si al cancelar éste se cancela el movimiento enlazado '
                  '(Odoo propagate_cancel).',
    )
    is_inventory    = fields.Boolean(
        default=False,
        help_text='El movimiento es un ajuste de inventario (Odoo is_inventory).',
    )
    inventory_name  = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Nombre del ajuste (Odoo inventory_name, readonly).',
    )
    additional      = fields.Boolean(
        default=False,
        help_text='El movimiento se añadió DESPUÉS de confirmar el albarán '
                  '(Odoo additional).',
    )
    description_picking_manual = fields.Text(
        blank=True, default='',
        help_text='Descripción escrita a mano (Odoo '
                  'description_picking_manual, readonly). Cuando está, gana '
                  'sobre la derivada del producto.',
    )
    next_serial     = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Primer número de serie a generar (Odoo next_serial).',
    )
    next_serial_count = fields.Integer(
        default=0,
        help_text='Cuántos números de serie generar (Odoo next_serial_count).',
    )
    orderpoint      = fields.Many2one(
        'stock.StockWarehouseOrderpoint', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_moves', db_index=True,
        help_text='La regla de reabastecimiento que originó el movimiento '
                  '(Odoo orderpoint_id, «Original Reordering Rule», index).',
    )

    class Meta:
        db_table = 'stock_move'
        ordering = ['sequence', 'id']
        verbose_name = 'Movimiento de inventario'
        verbose_name_plural = 'Movimientos de inventario'
        indexes = [PRODUCT_LOCATION_INDEX]

    def __str__(self) -> str:
        return f'{self.product} {self.product_uom_qty} [{self.state}]'

    # --- derivados: los ``compute`` sin ``store`` de la referencia -----------

    @property
    def product_category(self):
        """Categoría del producto (≙ ``product_category_id``, related)."""
        return self.product.categ if self.product_id else None

    @property
    def product_tmpl(self):
        """Plantilla del producto (≙ ``product_tmpl_id``, related)."""
        return self.product.product_tmpl if self.product_id else None

    @property
    def location_usage(self):
        """Tipo de la ubicación origen (≙ ``location_usage``, related)."""
        return self.location.usage if self.location_id else None

    @property
    def location_dest_usage(self):
        """Tipo de la ubicación destino (≙ ``location_dest_usage``, related)."""
        return self.location_dest.usage if self.location_dest_id else None

    @property
    def has_tracking(self):
        """Trazabilidad del producto (≙ ``has_tracking``, related)."""
        return self.product.tracking if self.product_id else None

    @property
    def is_storable(self):
        """¿El producto lleva existencias? (≙ ``is_storable``, related)."""
        return bool(self.product.is_storable) if self.product_id else False

    @property
    def picking_code(self):
        """Código del tipo de operación (≙ ``picking_code``, related)."""
        return self.picking_type.code if self.picking_type_id else None

    @property
    def show_operations(self):
        """≙ ``show_operations`` (related del tipo de operación del albarán)."""
        return bool(self.picking_type.show_operations) if self.picking_type_id else False

    @property
    def allowed_uom_ids(self):
        """Unidades admisibles para este movimiento (≙ ``_compute_allowed_uom_ids``).

        La fuente une tres conjuntos: la unidad del producto, sus empaquetados
        y las unidades de sus proveedores. Los tres los declara
        ``product.template``, así que se leen por el delegado (``product_tmpl``)
        — la variante no los tiene propios.
        """
        if not self.product_id:
            return apps.get_model('uom', 'Uom').objects.none()
        Uom = apps.get_model('uom', 'Uom')
        tmpl = self.product.product_tmpl
        ids = {tmpl.uom_id} if tmpl.uom_id else set()   # FK sin traer la fila
        ids |= set(tmpl.uom_ids.values_list('pk', flat=True))
        ids |= set(tmpl.seller_ids.exclude(product_uom__isnull=True)
                   .values_list('product_uom', flat=True))
        return Uom.objects.filter(pk__in=ids)

    @property
    def move_lines_count(self) -> int:
        """Número de líneas (≙ ``_compute_move_lines_count``)."""
        return self.move_line_ids.count()

    @property
    def is_initial_demand_editable(self) -> bool:
        """≙ ``_compute_is_initial_demand_editable``."""
        return (not self.picking.is_locked if self.picking_id else True) \
            or self.state == self.STATE_DRAFT

    @property
    def is_date_editable(self) -> bool:
        """≙ ``_compute_is_date_editable``."""
        return self.picking.is_date_editable if self.picking_id else True

    @property
    def is_quantity_done_editable(self) -> bool:
        """≙ ``_compute_is_quantity_done_editable``."""
        return bool(self.product_id)

    @property
    def is_locked(self) -> bool:
        """≙ ``_compute_is_locked`` — sin albarán, nunca bloqueado."""
        return bool(self.picking.is_locked) if self.picking_id else False

    @property
    def has_lines_without_result_package(self) -> bool:
        """≙ ``_compute_has_lines_without_result_package``.

        Cierto sólo si **alguna** línea ya tiene paquete de destino y **otra**
        no — un movimiento sin ningún paquete no cuenta.
        """
        lineas = list(self.move_line_ids.all())
        return any(l.result_package_id for l in lineas) and \
            any(not l.result_package_id for l in lineas)

    @property
    def display_import_lot(self) -> bool:
        """≙ ``_compute_display_assign_serial`` (la primera de las dos salidas)."""
        return bool(
            self.has_tracking and self.has_tracking != 'none'
            and self.product_id
            and self.picking_type_id and self.picking_type.use_create_lots
            and not self.origin_returned_move_id
            and self.state not in (self.STATE_DONE, self.STATE_CANCEL)
        )

    @property
    def display_assign_serial(self) -> bool:
        """≙ ``_compute_display_assign_serial`` — la fuente iguala ambas."""
        return self.display_import_lot

    @property
    def show_quant(self) -> bool:
        """≙ ``_compute_show_info`` (primera de sus tres salidas)."""
        return self.picking_code != 'incoming' and self.is_storable

    @property
    def show_lots_text(self) -> bool:
        """≙ ``_compute_show_info`` (segunda salida)."""
        return bool(
            self.has_tracking and self.has_tracking != 'none'
            and self.picking_type_id and self.picking_type.use_create_lots
            and not self.picking_type.use_existing_lots
            and self.state != self.STATE_DONE
            and not self.origin_returned_move_id
        )

    @property
    def show_lots_m2o(self) -> bool:
        """≙ ``_compute_show_info`` (tercera salida)."""
        return bool(
            not self.show_quant and not self.show_lots_text
            and self.has_tracking and self.has_tracking != 'none'
            and ((self.picking_type_id and self.picking_type.use_existing_lots)
                 or self.state == self.STATE_DONE
                 or self.origin_returned_move_id)
        )

    @property
    def availability(self):
        """Cantidad aún reservable (≙ ``_compute_product_availability``).

        Hecho el movimiento, es lo que movió de verdad; antes, el mínimo entre
        la demanda y lo disponible en la ubicación origen.
        """
        if self.state == self.STATE_DONE:
            return self.product_qty
        if not self.product_id:
            return Decimal('0.0000')
        return min(self.product_qty,
                   StockQuant.available_qty(self.product, self.location))

    @property
    def procurement_values(self):
        """Portapapeles entre pasos del aprovisionamiento (≙ ``procurement_values``).

        La referencia lo declara ``fields.Json(store=False)`` y su propio
        ``help`` lo llama *dummy field*: no es un dato del movimiento, es un
        valor que viaja entre pasos de la misma transacción. Aquí es atributo de
        instancia — lo mismo, sin columna (D-1 del docstring).
        """
        return getattr(self, '_procurement_values', None)

    @procurement_values.setter
    def procurement_values(self, value):
        self._procurement_values = value

    @property
    def description_picking(self):
        """Descripción para el albarán (≙ ``_compute_description_picking``).

        La manual gana; si no la hay, se deriva del producto. El inverso de la
        fuente (``_inverse_description_picking``) es el setter.
        """
        if self.description_picking_manual:
            return self.description_picking_manual
        if not self.product_id:
            return ''
        return self.product._get_picking_description(self.picking_type) \
            or self._get_description()

    @description_picking.setter
    def description_picking(self, value):
        self.description_picking_manual = value

    def _get_description(self) -> str:
        """≙ ``_get_description`` — la descripción del producto para este tipo."""
        return self.product._get_description(self.picking_type) if self.product_id else ''

    # --- máquina de estados (los cuatro con consumidores vivos) --------------

    # --- Ola A: predicados, ayudantes puros y recorrido de cadena ---------
    #
    # Los cuarenta símbolos de este bloque comparten una propiedad: **no
    # dependen de ninguna pieza ausente**. Se portan verbatim de la referencia
    # y quedan disponibles para las olas siguientes, que sí orquestan.

    def _quantity_sml(self):
        """≙ ``_quantity_sml`` (``odoo19c: :401-406``).

        La suma de las cantidades de las líneas, convertida a la unidad del
        movimiento. Sin redondear — la fuente pasa ``round=False`` a propósito:
        redondear aquí perdería el resto que la comparación posterior necesita.
        """
        cantidad = Decimal('0')
        for linea in self.move_line_ids.all():
            cantidad += linea.product_uom._compute_quantity(
                linea.quantity, self.product_uom, round=False)
        return cantidad

    def _visible_quantity(self):
        """≙ ``_visible_quantity`` (``odoo19c: :2811-2813``)."""
        return self.quantity

    def _is_incoming(self):
        """≙ ``_is_incoming`` (``odoo19c: :2815-2819``).

        Entra mercancía cuando el origen es externo: cliente, proveedor, o un
        tránsito **sin empresa** (el tránsito de una empresa nuestra es
        interno, no una entrada).
        """
        origen = self.location
        if origen is None:
            return False
        return origen.usage in ('customer', 'supplier') or (
            origen.usage == 'transit' and origen.company_id is None
        )

    def _is_outgoing(self):
        """≙ ``_is_outgoing`` (``odoo19c: :2821-2825``) — el simétrico."""
        destino = self.location_dest
        if destino is None:
            return False
        return destino.usage in ('customer', 'supplier') or (
            destino.usage == 'transit' and destino.company_id is None
        )

    def _is_consuming(self):
        """≙ ``_is_consuming`` (``odoo19c: :2433-2437``).

        Consume existencias si es interno/salida, o si cruza de un almacén a
        otro distinto.
        """
        wh_origen = self.location.warehouse if self.location_id else None
        wh_destino = self.location_dest.warehouse if self.location_dest_id else None
        if self.picking_code in ('internal', 'outgoing'):
            return True
        return bool(wh_origen and wh_destino and wh_origen != wh_destino)

    def _should_bypass_reservation(self, forced_location=None):
        """≙ ``_should_bypass_reservation`` (``odoo19c: :1962-1965``).

        Se salta la reserva si la ubicación lo permite (proveedor, cliente,
        inventario…) o si el producto no lleva existencias.
        """
        ubicacion = forced_location or self.location
        if ubicacion is not None and ubicacion.should_bypass_reservation():
            return True
        return not self.is_storable

    def _should_assign_at_confirm(self):
        """≙ ``_should_assign_at_confirm`` (``odoo19c: :1967-1968``)."""
        if self._should_bypass_reservation():
            return True
        if self.picking_type_id and self.picking_type.reservation_method == 'at_confirm':
            return True
        return bool(self.reservation_date
                    and self.reservation_date <= timezone.now().date())

    def _should_be_assigned(self):
        """≙ ``_should_be_assigned`` (``odoo19c: :1679-1681``).

        Un movimiento sin albarán pero con tipo de operación es candidato a
        que se le asigne uno.
        """
        return bool(self.picking_id is None and self.picking_type_id)

    def _can_create_lot(self):
        """≙ ``_can_create_lot`` (``odoo19c: :1046-1047``)."""
        return bool(self.picking_type_id and self.picking_type.use_existing_lots)

    def _skip_push(self):
        """≙ ``_skip_push`` (``odoo19c: :2226-2232``).

        No se aplica regla de empuje a un ajuste de inventario, ni cuando ya
        hay un destino encadenado cuya ubicación solapa con la nuestra: empujar
        ahí duplicaría el tramo.
        """
        if self.is_inventory:
            return True
        destinos = list(self.move_dest_ids.all())
        if not destinos:
            return False
        return any(
            m.location.is_child_of(self.location_dest)
            or self.location_dest.is_child_of(m.location)
            for m in destinos if m.location_id and self.location_dest_id
        )

    def _check_quantity(self):
        """≙ ``_check_quantity`` (``odoo19c: :2234-2239``).

        Delega en el quant: reúne los de este producto bajo la ubicación
        destino y su lote, y le pide la verificación.
        """
        Quant = apps.get_model('stock', 'StockQuant')
        quants = Quant.objects.filter(
            product=self.product,
            location__in=self.location_dest.child_ids_recursive()
            if self.location_dest_id else [],
        )
        return Quant.check_quantity(quants)

    def _get_picked_quantity(self):
        """≙ ``_get_picked_quantity`` (``odoo19c: :1970-1980``).

        Cuando el movimiento está marcado como recogido pero **alguna** de sus
        líneas no lo está, la cantidad recogida es la suma sólo de las que sí
        —no ``quantity``, que incluiría las no recogidas—.
        """
        lineas = list(self.move_line_ids.all())
        if self.picked and any(not ml.picked for ml in lineas):
            recogida = Decimal('0')
            for ml in lineas:
                if not ml.picked:
                    continue
                recogida += ml.product_uom._compute_quantity(
                    ml.quantity, self.product_uom, round=False)
            return recogida
        return self.quantity

    def _get_available_quantity(self, location, lot=None, package=None,
                                owner=None, strict=False, allow_negative=False):
        """≙ ``_get_available_quantity`` (``odoo19c: :1983-1987``).

        Si la ubicación se salta la reserva, todo está disponible por
        definición; en otro caso decide el quant.
        """
        if location is not None and location.should_bypass_reservation():
            return self.product_qty
        return StockQuant._get_available_quantity(
            self.product, location, lot=lot, package=package, owner=owner,
            strict=strict, allow_negative=allow_negative)

    def _get_lang(self):
        """≙ ``_get_lang`` (``odoo19c: :2439-2441``).

        El idioma de la descripción traducida: el del contacto del albarán, el
        del contacto del movimiento, o el del usuario.
        """
        if self.picking_id and self.picking.partner_id:
            if self.picking.partner.lang:
                return self.picking.partner.lang
        if self.partner_id and self.partner.lang:
            return self.partner.lang
        usuario = get_current_user()
        return getattr(usuario, 'lang', None)

    def _get_source_document(self):
        """≙ ``_get_source_document`` (``odoo19c: :2443-2448``).

        El documento del movimiento. La fuente declara el método como punto de
        extensión para que otros addons añadan su tipo de documento.
        """
        return self.picking if self.picking_id else None

    def _get_report_description_picking(self):
        """≙ ``_get_report_description_picking`` (``odoo19c: :2461-2466``).

        La descripción para el reporte, sin repetir el nombre del producto al
        principio — en el reporte el producto ya está en su propia columna.
        """
        descripcion = self.description_picking or ''
        nombre = str(self.product) if self.product_id else ''
        if nombre and descripcion.startswith(nombre):
            descripcion = descripcion[len(nombre):].strip()
        return descripcion

    def _get_partner_id(self):
        """≙ ``_get_partner_id`` (``odoo19c: :1818-1822``)."""
        if self.picking_id and self.picking.partner_id:
            return self.picking.partner
        return self.partner if self.partner_id else None

    def _get_mto_procurement_date(self):
        """≙ ``_get_mto_procurement_date`` (``odoo19c: :1864-1865``)."""
        return self.date

    def _prepare_procurement_origin(self):
        """≙ ``_prepare_procurement_origin`` (``odoo19c: :1780-1782``)."""
        return self.origin or (self.picking.name if self.picking_id else '')

    def _get_formating_options(self):
        """≙ ``_get_formating_options`` (``odoo19c: :1648-1649``).

        El nombre con la errata está **en la referencia** (``formating``, con
        una sola ``t``). Se conserva: renombrarlo rompería la correspondencia
        símbolo a símbolo por una mejora cosmética.
        """
        return {}

    def _key_assign_picking(self):
        """≙ ``_key_assign_picking`` (``odoo19c: :1522-1527``).

        La clave por la que dos movimientos comparten albarán. El albarán de
        los movimientos origen entra en la clave **sólo** si el movimiento no
        trae referencias propias: con referencia, ésta manda.
        """
        key_of = (tuple(self.reference_ids.values_list('pk', flat=True)),
                 self.location_id, self.location_dest_id, self.picking_type_id)
        if not self.reference_ids.exists():
            origen_pickings = tuple(sorted(
                self.move_orig_ids.exclude(picking__isnull=True)
                .values_list('picking', flat=True)))
            if origen_pickings:
                key_of += (origen_pickings,)
        return key_of

    def _prepare_merge_moves_distinct_fields(self, merge_extra=False):
        """≙ ``_prepare_merge_moves_distinct_fields`` (``odoo19c: :1275-1288``).

        Los campos que **impiden** fusionar dos movimientos: si difieren en
        alguno, son movimientos distintos.

        > **Corregido en el pase de la ola D.** Esta lista era la de **18c**
        > (``odoo18c: addons/stock/models/stock_move.py``): traía ``scrapped`` y
        > ``package_level``, que 19 retiró del modelo y **este árbol nunca
        > declaró** —dos atributos fantasma—, y omitía
        > ``never_product_template_attribute_value_ids``, que sí existe. Nada lo
        > delataba porque la ola D es su primer consumidor. Ver
        > :ref:`h-api-625`.

        ``merge_extra`` es el contexto homónimo de la fuente, aquí parámetro
        explícito: al absorber un movimiento extra, el método de
        abastecimiento deja de separar.

        **Bloqueado, con dueño:** las dos ramas que la fuente condiciona a
        ``ir.config_parameter`` —``stock.merge_only_same_date`` (añadiría
        ``date``) y ``stock.merge_ignore_date_deadline`` (retiraría
        ``date_deadline``)— quedan fijas en su valor por defecto: el modelo
        ``ir.config_parameter`` no existe en el árbol (tarea **#387**). El
        comportamiento resultante es el de la fuente sin configurar, así que el
        método es funcional; lo que se difiere es su configurabilidad.
        """
        campos = [
            'product', 'price_unit', 'procure_method', 'location', 'location_dest',
            'location_final', 'product_uom', 'restrict_partner',
            'origin_returned_move', 'propagate_cancel', 'description_picking',
            'never_product_template_attribute_value_ids',
        ]
        if merge_extra:
            campos.remove('procure_method')
        campos.append('date_deadline')
        return campos

    def _prepare_merge_negative_moves_excluded_distinct_fields(self):
        """≙ ``_prepare_merge_negative_moves_excluded_distinct_fields``
        (``odoo19c: :1291-1292``).

        De la lista de arriba, el único campo que **no** cuenta al fusionar un
        movimiento negativo con su positivo.
        """
        return ['description_picking']

    def _clean_merged(self):
        """≙ ``_clean_merged`` (``odoo19c: :1294-1296``)."""
        self.move_ids_to_clean().update(propagate_cancel=False)

    def move_ids_to_clean(self):
        """El conjunto sobre el que ``_clean_merged`` escribe.

        Divergencia de mecanismo: la fuente llama ``self.write(...)`` sobre el
        recordset; aquí un modelo suelto no es un conjunto, así que el hogar de
        esa distinción es explícito. Sobre una instancia devuelve su propio
        queryset de un elemento.
        """
        return type(self).objects.filter(pk=self.pk)

    def _update_candidate_moves_list(self, candidate_moves_set):
        """≙ ``_update_candidate_moves_list`` (``odoo19c: :1298-1300``).

        Añade al conjunto de candidatos todos los movimientos de cada albarán
        implicado — la fusión mira el albarán entero, no sólo el movimiento.
        """
        if self.picking_id:
            candidate_moves_set.add(self.picking_id)
        return candidate_moves_set

    def _log_cancel_activity(self):
        """≙ ``_log_cancel_activity`` (``odoo19c: :2223-2225``).

        Vacío en la referencia: es el punto de extensión que otros addons
        sobreescriben para dejar la actividad al cancelar.
        """
        return

    def _action_synch_order(self):
        """≙ ``_action_synch_order`` (``odoo19c: :2311-2312``) — punto de extensión."""
        return True

    def _post_process_created_moves(self):
        """≙ ``_post_process_created_moves`` (``odoo19c: :2405-2409``).

        Punto de extensión de la referencia: acciones posteriores a la creación
        para movimientos que nunca se van a confirmar.
        """
        return None

    def _break_mto_link(self, parent_move):
        """≙ ``_break_mto_link`` (``odoo19c: :2786-2789``).

        Rompe el encadenamiento con el movimiento padre y devuelve este
        movimiento a fabricar-contra-existencias.
        """
        self.move_orig_ids.remove(parent_move)
        self.procure_method = self.PROCURE_MAKE_TO_STOCK
        self.save(update_fields=['procure_method', 'updated_at'])
        self._recompute_state()

    @staticmethod
    def _convert_string_into_field_data(string, options=None):
        """≙ ``_convert_string_into_field_data`` (``odoo19c: :2739-2743``).

        Interpreta lo escrito en el lector de código de barras: si es un
        número, es una cantidad. La coma se normaliza a punto porque
        ``float()`` sólo entiende el punto.
        """
        string = (string or '').replace(',', '.')
        if re.fullmatch(r'([0-9]+\.?[0-9]*|\.[0-9]+)', string):
            return {'quantity': float(string)}
        return False

    # -- ola B · persistencia: lo que pasa al crear, escribir y borrar --

    def save(self, *args, **kwargs):
        """Aplica ``_compute_product_qty``, que es ``store=True`` en la fuente.

        ≙ ``_compute_product_qty`` (``odoo19c: :791-794``,
        ``@api.depends('product_uom_qty', 'product_uom')``): la cantidad pedida
        expresada en la **unidad del producto**, no en la del movimiento. La
        fuente la declara ``store=True``, así que su hogar aquí es ``save()``
        (:ref:`h-api-591`).

        > **Añadido en el pase de la ola D.** La columna existía desde el
        > primer pase y **nadie la calculaba**: quedaba en cero, y todo lo que
        > la lee —la absorción de negativos y el resto de una división, ambos
        > de esta ola— operaba sobre cero sin error visible. Ver
        > :ref:`h-api-625`.

        La conversión trabaja en coma flotante (es el algoritmo de la fuente) y
        la columna es ``Decimal``: la frontera se cruza aquí (H-API-588,
        tarea **#344**).
        """
        campos = kwargs.get('update_fields')
        toca_cantidad = campos is None or bool(
            {'product_uom_qty', 'product_uom', 'product'} & set(campos))
        if toca_cantidad and self.product_uom_id and self.product_id:
            in_product = self.product_uom.compute_quantity(
                float(self.product_uom_qty or 0), self.product.uom,
                rounding_method='HALF-UP')
            self.product_qty = Decimal(str(in_product))
            if campos is not None:
                kwargs['update_fields'] = list(
                    dict.fromkeys([*campos, 'product_qty']))
        return super().save(*args, **kwargs)

    @classmethod
    def default_get(cls, field_names, values=None, default_picking=None):
        """≙ ``default_get`` (``odoo19c: :770-784``).

        El albarán de destino decide con qué estado nace el movimiento. La
        fuente lo lee del contexto (``default_picking_id``); aquí es un
        argumento explícito, igual que en ``stock_rule.default_get`` — este ORM
        no lleva contexto de entorno en la llamada.

        ``additional`` no es cosmético: es lo que hace que
        ``_autoconfirm_picking`` recoja el movimiento. Sin la marca, una línea
        añadida a un albarán ya en marcha se quedaría en borrador dentro de una
        transferencia que ya avanzó.
        """
        defaults = dict(values or {})
        if default_picking is None:
            return defaults
        if default_picking.state == 'done':
            defaults['state'] = cls.STATE_DONE
            defaults['additional'] = True
        elif default_picking.state not in ('cancel', 'draft', 'done'):
            defaults['additional'] = True    # dispara `_autoconfirm_picking`
        return defaults

    @staticmethod
    def _normalize_create_values(values):
        """≙ el bucle de normalización de ``create`` (``odoo19c: :819-826``).

        Se separa del ``create`` porque es la parte **pura**: sólo transforma
        el diccionario, sin tocar la base. Así se prueba sin insertar nada, y
        ``create`` queda con lo que sí es persistencia.

        Las tres reglas de la fuente, en su orden:

        1. Con cantidad (o con líneas), ``lot_ids`` sobra y se descarta —
           dejar ambos permitiría dos verdades sobre lo mismo.
        2. Un movimiento que nace dentro de un albarán hecho nace hecho.
        3. Todo movimiento hecho está recogido, por definición.
        """
        values = dict(values)
        if (values.get('quantity') or values.get('move_line_ids')) and 'lot_ids' in values:
            values.pop('lot_ids')
        albaran = values.get('picking')
        if albaran is not None and albaran.state == 'done' \
                and values.get('state') != StockMove.STATE_DONE:
            values['state'] = StockMove.STATE_DONE
        if values.get('state') == StockMove.STATE_DONE:
            values['picked'] = True
        return values

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :818-830``).

        Normaliza, inserta, y **luego** propaga: las reglas de reabastecimiento
        que este producto toca quedan marcadas para recalcularse, y el
        movimiento hereda las referencias de su albarán.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        moves = super().create([cls._normalize_create_values(vals) for vals in vals_list])
        for move in moves:
            move._update_orderpoints()
            move._set_references()
        return moves

    def write(self, vals, skip_uom_conversion=False):
        """≙ ``write`` (``odoo19c: :833-905``) — la mitad de guardas.

        Dos prohibiciones de la fuente, con su razón:

        - **Cantidad de un cancelado.** El cancelado es un hecho histórico;
          reescribirlo borraría por qué se canceló. La fuente pide una línea
          nueva en su lugar.
        - **Unidad de un hecho.** Cambiarla reinterpreta una cantidad ya
          asentada: cinco cajas pasarían a ser cinco piezas sin que ningún
          quant se mueva. ``skip_uom_conversion`` es la puerta que la fuente
          deja abierta para quien sí sabe lo que hace.

        Divergencia declarada — **la mitad de reserva no está aquí.** La fuente
        encadena, tras las guardas, el des-reservar/re-asignar de
        ``product_uom_qty`` (``:851-871``), el aviso de fecha límite
        (``:872-873``) y el re-cálculo de almacén (``:891-899``). Esos cuelgan
        de ``_do_unreserve`` y ``_action_assign``, que son la **ola C**; se
        portan ahí y no antes, para no dejar medio mecanismo en pie. Cobertura
        declarada en el docstring del módulo.
        """
        for campo, valor in vals.items():
            if campo == 'quantity' and self.state == self.STATE_CANCEL:
                raise UserError(_(
                    'No puede cambiar un movimiento cancelado; cree una línea nueva.'))
            if (campo == 'product_uom' and self.state == self.STATE_DONE
                    and not skip_uom_conversion):
                raise UserError(_(
                    "No puede cambiar la unidad de un movimiento en estado 'Hecho'."))
            setattr(self, campo, valor)
        if {'product', 'location', 'location_dest'} & set(vals):
            self._update_orderpoints()
        self.save()
        if {'product', 'state', 'date', 'product_uom_qty',
                'location', 'location_dest'} & set(vals):
            self._update_orderpoints()
        if 'picking' in vals:
            self._set_references()
        return True

    def unlink(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: :2337-2343``).

        El orden importa y es el de la fuente: primero las líneas, después la
        fila. Y antes de todo, la guarda de cadena — que la fuente declara
        aparte, con ``@api.ondelete``, y aquí se invoca explícitamente porque
        este ORM no tiene ese decorador.

        Las reglas de reabastecimiento se capturan **antes** de borrar: después
        el movimiento ya no está para decir a cuáles tocaba.
        """
        self._unlink_if_draft_or_cancel()
        self.move_line_ids.all().delete()
        reglas = list(self._get_orderpoints_to_update())
        resultado = super().delete(*args, **kwargs)
        type(self)._mark_orderpoints_for_recompute(reglas)
        return resultado

    delete = unlink   # el nombre de Django apunta al de la referencia

    def _set_references(self):
        """≙ ``_set_references`` (``odoo19c: :793-796``).

        Un movimiento sin referencias propias adopta las de su albarán: es lo
        que hace que los documentos de un mismo encargo compartan nombre.
        """
        if not self.reference_ids.exists() and self.picking_id:
            self.reference_ids.set(self.picking.reference_ids)

    def _compute_display_name(self):
        """≙ ``display_name`` / ``_compute_display_name`` (``odoo19c: :786-792``).

        ``origen/código: ubicación>destino``, con los dos primeros tramos
        opcionales — la fuente los omite cuando están vacíos en vez de dejar
        separadores huérfanos.
        """
        origen = self.picking.origin if self.picking_id else ''
        codigo = self.product.code_for(None) if self.product_id else ''
        return '%s%s%s>%s' % (
            f'{origen}/' if origen else '',
            f'{codigo}: ' if codigo else '',
            self.location.name if self.location_id else '',
            self.location_dest.name if self.location_dest_id else '')

    # -- ola B · propagación a las reglas de reabastecimiento --

    def _update_orderpoints(self):
        """≙ ``_update_orderpoints`` (``odoo19c: :908-916``).

        Marca para recálculo **sólo** las reglas del almacén afectado, no todas
        las del producto. La fuente lo dice explícito: *"instead of all the
        orderpoints linked to the product"*.
        """
        if self.pk is None:
            return
        type(self)._mark_orderpoints_for_recompute(self._get_orderpoints_to_update())

    def _get_orderpoints_to_update(self):
        """≙ ``_get_orderpoints_to_update`` (``odoo19c: :918-927``).

        Las reglas de este producto, acotadas a los almacenes que el movimiento
        toca — origen y destino. Sin almacén en ninguno de los dos extremos, el
        acotamiento no aplica y quedan todas las del producto.
        """
        orderpoint = apps.get_model('stock', 'StockWarehouseOrderpoint')
        if self.product_id is None:
            return orderpoint.objects.none()
        almacenes = [
            a for a in (
                self.location.warehouse_id if self.location_id else None,
                self.location_dest.warehouse_id if self.location_dest_id else None,
            ) if a is not None
        ]
        reglas = orderpoint.objects.filter(product_id=self.product_id)
        if almacenes:
            reglas = reglas.filter(warehouse_id__in=almacenes)
        return reglas.order_by('id')

    @classmethod
    def _mark_orderpoints_for_recompute(cls, orderpoints):
        """El ``add_to_compute`` de la fuente (``odoo19c: :916``), explícito.

        Divergencia declarada: allá el ORM difiere el cálculo hasta la próxima
        lectura del campo. Este ORM no tiene cola de cómputo diferido —
        construirla es la tarea **#191**— así que el recálculo se ejecuta ya.
        Es la misma cifra; cambia cuándo se paga.
        """
        reglas = list(orderpoints)
        if reglas:
            type(reglas[0])._compute_qty_to_order_computed(reglas)

    # -- ola B · el aviso de retraso --

    def _delay_alert_get_documents(self):
        """≙ ``_delay_alert_get_documents`` (``odoo19c: :929-938``).

        Los documentos sobre los que se publica el aviso de retraso. La fuente
        lo declara para que otros módulos lo extiendan añadiendo su propio tipo
        de documento (la orden de compra, la de fabricación); aquí sólo está el
        albarán, que es lo que ``stock`` conoce.
        """
        return [self.picking] if self.picking_id else []

    def _propagate_date_log_note(self, move_orig):
        """≙ ``_propagate_date_log_note`` (``odoo19c: :940-957``).

        Publica en los documentos de este movimiento que su fecha límite se
        movió por un retraso aguas arriba. La guarda contra el duplicado es de
        la fuente: si el último mensaje ya dice lo mismo, no se repite.
        """
        docs_origen = move_orig._delay_alert_get_documents()
        documentos = self._delay_alert_get_documents()
        if not documentos or not docs_origen:
            return
        cuerpo = _('La fecha límite se actualizó por un retraso en %s.') % docs_origen[0]
        asunto = _('Fecha límite actualizada por retraso en %s') % docs_origen[0]
        for doc in documentos:
            ultimo = doc.message_ids.order_by('-id').first()
            if ultimo is not None and ultimo.subject == asunto:
                continue
            doc.message_post(body=cuerpo, subject=asunto)

    def _unlink_if_draft_or_cancel(self):
        """≙ ``_unlink_if_draft_or_cancel`` (``odoo19c: :2333-2335``).

        Un movimiento encadenado sólo se borra si está en borrador o
        cancelado: borrar uno intermedio dejaría la cadena rota.
        """
        if self.state not in (self.STATE_DRAFT, self.STATE_CANCEL) and (
                self.move_orig_ids.exists() or self.move_dest_ids.exists()):
            raise UserError(_('No puede eliminar movimientos enlazados a otra operación'))

    def _get_relevant_state_among_moves(self, moves=None):
        """≙ ``_get_relevant_state_among_moves`` (``odoo19c: :1406-1446``).

        El estado que representa a un conjunto de movimientos — lo consume el
        albarán para derivar el suyo. El orden de importancia lo fija la
        referencia: asignado > esperando > parcial > confirmado.

        Con política «todo junto» (``move_type == 'one'``) manda el movimiento
        **más** importante, porque basta uno sin resolver para frenar el envío
        completo; con «lo antes posible» manda el **menos** importante, porque
        cualquiera resuelto ya permite enviar.
        """
        orden = {'assigned': 4, 'waiting': 3, 'partially_available': 2, 'confirmed': 1}
        candidatos = [
            m for m in (moves if moves is not None else [self])
            if m.state not in (self.STATE_CANCEL, self.STATE_DONE)
            and not (m.state == self.STATE_ASSIGNED and not m.product_uom_qty)
        ]
        if not candidatos:
            return self.STATE_ASSIGNED
        candidatos.sort(key=lambda m: (orden.get(m.state, 0), m.product_uom_qty))
        primero = candidatos[0]
        albaran = primero.picking if primero.picking_id else None
        if albaran is not None and albaran.move_type == 'one':
            if all(not m.product_uom_qty for m in candidatos):
                return self.STATE_ASSIGNED
            if primero.state in (self.STATE_CONFIRMED, 'partially_available'):
                return self.STATE_CONFIRMED
            return primero.state or self.STATE_DRAFT
        if primero.state != self.STATE_ASSIGNED and any(
                m.state in (self.STATE_ASSIGNED, 'partially_available')
                for m in candidatos):
            return 'partially_available'
        ultimo = candidatos[-1]
        if ultimo.state == self.STATE_CONFIRMED and not ultimo.product_uom_qty:
            return self.STATE_ASSIGNED
        return ultimo.state or self.STATE_DRAFT

    def _recompute_state(self):
        """≙ ``_recompute_state`` (``odoo19c: :2411-2431``).

        Deriva el estado de la relación entre lo reservado y lo pedido. El
        contexto ``preserve_state`` de la fuente es un parámetro explícito
        aquí: este ORM no lleva contexto de entorno en la llamada.
        """
        if self.state in (self.STATE_CANCEL, self.STATE_DONE):
            return
        if self.state == self.STATE_DRAFT and not self.quantity:
            return
        # ``float_compare`` es el algoritmo de la fuente y trabaja en coma
        # flotante; las columnas son ``Decimal``. Sin la conversión sólo
        # funcionaba con un cero de por medio —el corto-circuito de
        # ``float_round``—, y con dos cantidades reales levantaba ``TypeError``
        # en ejecución. Ver :ref:`h-api-625` (H-API-588, tarea **#344**).
        redondeo = float(self.product_uom.rounding) if self.product_uom_id else 0.01
        if float_compare(float(self.quantity), float(self.product_uom_qty),
                         precision_rounding=redondeo) >= 0:
            nuevo = self.STATE_ASSIGNED
        elif self.quantity and float_compare(
                float(self.quantity), float(self.product_uom_qty),
                precision_rounding=redondeo) <= 0:
            nuevo = 'partially_available'
        elif (self.procure_method == self.PROCURE_MAKE_TO_ORDER
              and not self.move_orig_ids.exists()) or any(
                orig.product_uom_qty > 0
                and orig.state not in (self.STATE_DONE, self.STATE_CANCEL)
                for orig in self.move_orig_ids.all()):
            nuevo = self.STATE_WAITING
        else:
            nuevo = self.STATE_CONFIRMED
        if self.state != nuevo:
            self.state = nuevo
            self.save(update_fields=['state', 'updated_at'])

    # -- el recorrido de la cadena de movimientos --

    def _rollup_moves(self, origin=True, seen=None):
        """≙ ``_rollup_moves`` (``odoo19c: :2674-2688``).

        Recorre la cadena en la dirección pedida y devuelve **los ids** de todo
        lo visitado. ``seen`` corta el ciclo: una cadena puede volver sobre sí
        misma y sin el acumulador el recorrido no termina.

        Divergencia declarada: la fuente devuelve ``OrderedSet``; aquí un
        ``dict`` vacío hace de conjunto ordenado — Python garantiza el orden de
        inserción desde 3.7, que es exactamente la propiedad que ``OrderedSet``
        aporta, y el acumulador se consulta por pertenencia, no se compone con
        otros conjuntos. (``tools.misc.OrderedSet`` **sí** está portado desde
        ``api@e6aff38``; la nota anterior lo daba por ausente.)
        """
        campo = 'move_orig_ids' if origin else 'move_dest_ids'
        if seen is None:
            seen = {}
        if self.pk in seen:
            return seen
        seen[self.pk] = None
        for siguiente in getattr(self, campo).all():
            siguiente._rollup_moves(origin, seen)
        return seen

    def _rollup_move_dests(self, seen=None):
        """≙ ``_rollup_move_dests`` (``odoo19c: :2668-2669``)."""
        return self._rollup_moves(origin=False, seen=seen)

    def _rollup_move_origs(self, seen=None):
        """≙ ``_rollup_move_origs`` (``odoo19c: :2671-2672``)."""
        return self._rollup_moves(origin=True, seen=seen)

    def _rollup_move_dests_fetch(self):
        """≙ ``_rollup_move_dests_fetch`` (``odoo19c: :2648-2656``).

        En la referencia precarga la cadena para no pagar una consulta por
        salto. Aquí el equivalente es materializar el recorrido: el ORM de
        Django no tiene ``fetch()`` de campo suelto, y ``prefetch_related``
        no atraviesa profundidad arbitraria.
        """
        return list(self._rollup_move_dests())

    def _rollup_move_origs_fetch(self):
        """≙ ``_rollup_move_origs_fetch`` (``odoo19c: :2658-2666``)."""
        return list(self._rollup_move_origs())

    def _get_upstream_documents_and_responsibles(self, visited=None):
        """≙ ``_get_upstream_documents_and_responsibles`` (``odoo19c: :2450-2459``).

        Asciende por la cadena hasta el documento vivo más alto y devuelve los
        pares (documento, responsable). Un movimiento sin origen vivo es la
        cima: ahí la fuente devuelve lista vacía y el descendiente decide.
        """
        if visited is None:
            visited = set()
        if self.pk in visited:
            return set()
        origenes = [m for m in self.move_orig_ids.all()
                    if m.state not in (self.STATE_DONE, self.STATE_CANCEL)]
        if not origenes:
            return set()
        visited.add(self.pk)
        salida = set()
        for movimiento in origenes:
            salida |= movimiento._get_upstream_documents_and_responsibles(visited)
        return salida

    # -- ola C · reserva y disponibilidad --

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """≙ ``_prepare_move_line_vals`` (``odoo19c: :1867-1897``).

        El diccionario con que nace una línea de movimiento. Su parte
        interesante es el **ida y vuelta de unidad**: convierte la cantidad a
        la unidad del movimiento, la redondea, y la vuelve a convertir a la del
        producto. Si el resultado no coincide con lo pedido, la conversión
        perdió precisión y la fuente prefiere **guardar en la unidad del
        producto** antes que asentar una cifra redondeada — un movimiento de
        tres piezas en cajas de doce no se guarda como 0.25 cajas.
        """
        vals = {
            'move': self,
            'product': self.product,
            'product_uom': self.product_uom,
            'location': self.location,
            'location_dest': self.location_dest,
            'picking': self.picking,
            'company': self.company,
        }
        if quantity:
            redondeo = DecimalPrecision.precision_get('Product Unit')
            in_uom = self.product.uom.compute_quantity(
                quantity, self.product_uom, rounding_method='HALF-UP')
            in_uom = float_round(in_uom, precision_digits=redondeo)
            de_vuelta = self.product_uom.compute_quantity(
                in_uom, self.product.uom, rounding_method='HALF-UP')
            if float_compare(quantity, de_vuelta, precision_digits=redondeo) == 0:
                vals = dict(vals, quantity=in_uom)
            else:
                vals = dict(vals, quantity=quantity, product_uom=self.product.uom)
        if reserved_quant is not None:
            vals = dict(
                vals,
                location=reserved_quant.location,
                lot=reserved_quant.lot,
                package=reserved_quant.package,
                owner=reserved_quant.owner,
            )
        return vals

    def _add_serial_move_line_to_vals_list(self, reserved_quant, quantity):
        """≙ ``_add_serial_move_line_to_vals_list`` (``odoo19c: :1958-1959``).

        Un producto con número de serie no admite fracción: **una línea por
        unidad**, cada una con su lote.
        """
        return [self._prepare_move_line_vals(quantity=1, reserved_quant=reserved_quant)
                for _ in range(int(quantity))]

    def _update_reserved_quantity_vals(self, need, location, lot=None, package=None,
                                       owner=None, strict=True):
        """≙ ``_update_reserved_quantity_vals`` (``odoo19c: :1912-1956``).

        Decide **el reparto** sin escribirlo: qué línea existente crece y qué
        líneas nuevas hacen falta. Devuelve ``(valores, tomado)``.

        Dos pasos de la fuente que no son adorno:

        1. **Se agrupan los quants duplicados** por su combinación
           (ubicación, lote, paquete, dueño) antes de repartir. Sin eso, dos
           quants de la misma combinación crearían dos líneas donde debe haber
           una.
        2. **Sólo se acumula sobre una línea candidata si la conversión de
           unidad es exacta** — el mismo ida y vuelta de
           ``_prepare_move_line_vals``. Si no lo es, se crea línea nueva en vez
           de asentar un redondeo sobre una cantidad que ya estaba.

        Las líneas con paquete de resultado o con serie quedan fuera de las
        candidatas: la fuente no acumula sobre ellas.
        """
        quants = StockQuant._get_reserve_quantity(
            self.product, location, need, uom=self.product_uom,
            lot=lot, package=package, owner=owner, strict=strict)

        tomado = 0
        redondeo = DecimalPrecision.precision_get('Product Unit')
        candidatas = {}
        for linea in self.move_line_ids.all():
            if linea.result_package_id or linea.product.tracking == 'serial':
                continue
            candidatas[(linea.location_id, linea.lot_id,
                        linea.package_id, linea.owner_id)] = linea

        valores = []
        agrupados = {}
        for quant, cantidad in quants:
            key_of = (quant.location_id, quant.lot_id, quant.package_id, quant.owner_id)
            if key_of not in agrupados:
                agrupados[key_of] = [quant, cantidad]
            else:
                agrupados[key_of][1] += cantidad

        for quant, cantidad in agrupados.values():
            tomado += cantidad
            actualizable = candidatas.get(
                (quant.location_id, quant.lot_id, quant.package_id, quant.owner_id))
            exacta = False
            if actualizable is not None:
                in_uom = self.product.uom.compute_quantity(
                    cantidad, actualizable.product_uom, rounding_method='HALF-UP')
                in_uom = float_round(in_uom, precision_digits=redondeo)
                de_vuelta = actualizable.product_uom.compute_quantity(
                    in_uom, self.product.uom, rounding_method='HALF-UP')
                exacta = float_compare(cantidad, de_vuelta,
                                       precision_digits=redondeo) == 0
            if actualizable is not None and exacta:
                actualizable.quantity += Decimal(str(in_uom))
                actualizable.save(update_fields=['quantity', 'updated_at'])
            elif (self.product.tracking == 'serial' and self.picking_type_id
                  and (self.picking_type.use_create_lots
                       or self.picking_type.use_existing_lots)):
                valores += self._add_serial_move_line_to_vals_list(quant, cantidad)
            else:
                valores.append(
                    self._prepare_move_line_vals(quantity=cantidad, reserved_quant=quant))
        return valores, tomado

    def _update_reserved_quantity(self, need, location, lot=None, package=None,
                                  owner=None, strict=True):
        """≙ ``_update_reserved_quantity`` (``odoo19c: :1900-1910``).

        «Create or update move lines and reserves quantity from quants.» Es la
        mitad que **escribe**; el reparto lo decide el método de arriba.
        """
        valores, tomado = self._update_reserved_quantity_vals(
            need, location, lot, package, owner, strict)
        for vals in valores:
            StockMoveLine.objects.create(**vals)
        return tomado

    def _get_available_move_lines_in(self):
        """≙ ``_get_available_move_lines_in`` (``odoo19c: :1989-2002``).

        Lo que **entró** por los hermanos de esta cadena, agrupado por su
        combinación de destino. Se recorre ``move_orig_ids.move_dest_ids
        .move_orig_ids`` —el rodeo es de la fuente— porque un mismo origen
        puede abastecer a varios destinos y hay que ver todo lo que llegó.
        """
        lineas = [
            linea
            for origen in self.move_orig_ids.all()
            for destino in origen.move_dest_ids.all()
            for hermano in destino.move_orig_ids.all()
            if hermano.state == self.STATE_DONE
            for linea in hermano.move_line_ids.all()
        ]

        def key_of(line):
            return (line.location_dest_id, line.lot_id,
                    line.result_package_id, line.owner_id)

        agrupado = {}
        for k, grupo in groupby(lineas, key=key_of):
            agrupado[k] = sum(
                ml.product_uom.compute_quantity(float(ml.quantity), ml.product.uom)
                for ml in grupo)
        return agrupado

    def _get_available_move_lines_out(self, assigned_moves_ids, partially_available_moves_ids):
        """≙ ``_get_available_move_lines_out`` (``odoo19c: :2004-2028``).

        Lo que los **hermanos ya se llevaron**, por la misma combinación. Suma
        dos poblaciones distintas, y la fuente explica por qué la segunda:
        *"As we defer the write on the stock.move's state at the end of the
        loop, there could be moves to consider in what our siblings already
        took"* — es decir, hermanos cuyo estado aún no se ha escrito.
        """
        hermanos = [m for origen in self.move_orig_ids.all()
                    for m in origen.move_dest_ids.all() if m.pk != self.pk]
        hechos = [linea for m in hermanos if m.state == self.STATE_DONE
                  for linea in m.move_line_ids.all()]
        en_vuelo = set(assigned_moves_ids) | set(partially_available_moves_ids)
        reservados = [
            linea for m in hermanos
            if m.state in (self.STATE_ASSIGNED, 'partially_available') or m.pk in en_vuelo
            for linea in m.move_line_ids.all()
        ]

        def key_of(line):
            return (line.location_id, line.lot_id, line.package_id, line.owner_id)

        agrupado = {}
        for k, grupo in groupby(hechos, key=key_of):
            agrupado[k] = sum(
                ml.product_uom.compute_quantity(float(ml.quantity), ml.product.uom)
                for ml in grupo)
        for k, grupo in groupby(reservados, key=key_of):
            agrupado[k] = sum(float(ml.quantity_product_uom) for ml in grupo)
        return agrupado

    def _get_available_move_lines(self, assigned_moves_ids, partially_available_moves_ids):
        """≙ ``_get_available_move_lines`` (``odoo19c: :2030-2036``).

        Lo que entró menos lo que se llevaron. Las combinaciones que quedan en
        cero **se descartan**: la fuente sólo devuelve las que aún tienen algo,
        y quien la consume itera el diccionario esperando que cada entrada sea
        reservable.
        """
        entradas = self._get_available_move_lines_in()
        salidas = self._get_available_move_lines_out(
            assigned_moves_ids, partially_available_moves_ids)
        disponible = {k: entradas[k] - salidas.get(k, 0) for k in entradas}
        redondeo = self.product.uom.rounding if self.product_id else 0.01
        return {k: v for k, v in disponible.items()
                if float_compare(v, 0, precision_rounding=redondeo) > 0}

    def _set_quantity_done_prepare_vals(self, qty):
        """≙ ``_set_quantity_done_prepare_vals`` (``odoo19c: :2468-2549``).

        Reparte ``qty`` entre las líneas existentes y devuelve **el plan**: qué
        línea se actualiza, cuál se borra y cuál falta crear.

        Divergencia declarada de FORMA, no de contenido: la fuente devuelve
        una lista de ``Command``, que su ORM aplica al asignar. El ``Command``
        de este árbol es **ejecutivo** —escribe al llamarlo— así que una lista
        de comandos no es un valor que se pueda devolver sin haber escrito ya.
        El plan viaja como tuplas ``('update'|'delete'|'create', línea, vals)``
        y lo aplica ``_set_quantity_done``. La divergencia de ``Command`` está
        registrada en :ref:`h-api-589` (tarea **#345**); ésta es una de sus
        consecuencias, no una decisión nueva.

        El recorrido conserva las tres salidas de la fuente, en su orden:
        agotada la cantidad, la línea sobra y se borra; si la línea tiene más
        de lo que queda, se recorta; si tiene menos, se consume entera y se
        sigue. Las líneas con paquete de resultado **descuentan pero no se
        tocan** — ya están empaquetadas.
        """
        def en_uom_del_movimiento(quantity):
            return self.product.uom.compute_quantity(
                quantity, self.product_uom, round=False)

        plan = []
        qty = self.product_uom.compute_quantity(qty, self.product.uom, round=False)
        for linea in self.move_line_ids.all():
            cantidad_linea = float(linea.quantity)
            if linea.product_uom.compare(cantidad_linea, 0) < 0:
                continue
            if linea.product_uom != self.product.uom:
                cantidad_linea = linea.product_uom.compute_quantity(
                    cantidad_linea, self.product.uom, round=False)

            if self.product_uom.is_zero(en_uom_del_movimiento(qty)):
                plan.append(('delete', linea, {}))
                continue

            if self.product.uom.compare(cantidad_linea, qty) > 0:
                recorte = qty
                if linea.product_uom != self.product.uom:
                    recorte = self.product.uom.compute_quantity(
                        qty, linea.product_uom, round=False)
                plan.append(('update', linea, {'quantity': Decimal(str(recorte))}))
                qty = 0
                continue

            if linea.result_package_id:
                qty -= cantidad_linea
                continue

            plan.append(('update', linea, {'quantity': Decimal(str(
                en_uom_del_movimiento(cantidad_linea)))}))
            qty -= cantidad_linea

        if self.product.uom.compare(qty, 0) > 0:
            plan.append(('create', None,
                         self._prepare_move_line_vals(quantity=qty)))
        return plan

    def _set_quantity_done(self, qty):
        """≙ ``_set_quantity_done`` (``odoo19c: :2551-2562``).

        «Set the given quantity as quantity done on the move through the move
        lines.» Aplica el plan y **redirige las líneas nuevas** por la
        estrategia de ubicación — que es la única razón por la que la fuente
        distingue las nuevas de las que ya estaban.
        """
        nuevas = []
        for accion, linea, vals in self._set_quantity_done_prepare_vals(qty):
            if accion == 'delete':
                fields.Command.delete(linea)
            elif accion == 'update':
                fields.Command.update(linea, **vals)
            else:
                nuevas.append(StockMoveLine.objects.create(**vals))
        if nuevas:
            StockMoveLine._apply_putaway_strategy(nuevas)

    def _adjust_procure_method(self, picking_type_code=False):
        """≙ ``_adjust_procure_method`` (``odoo19c: :2564-2599``).

        «This method will try to apply the procure method MTO on some moves if
        a compatible MTO route is found. Else the procure method will be set to
        MTS.»

        El bucle asciende por el árbol de ubicaciones buscando una regla que
        cubra el trayecto: sin regla, el movimiento se abastece de existencias.
        El ``while`` de la fuente se conserva porque una ubicación hija puede
        no tener regla propia y heredar la de su padre.
        """
        regla = None
        ubicacion = self.location
        while ubicacion is not None:
            criterio = (Q(location_src=ubicacion)
                        & Q(location_dest=self.location_dest)
                        & ~Q(action='push'))
            if picking_type_code:
                criterio &= Q(picking_type__code=picking_type_code)
            regla = StockRule._search_rule(
                None, self.packaging_uom, self.product,
                self.warehouse or (self.picking_type.warehouse
                                   if self.picking_type_id else None),
                criterio)
            if regla is not None:
                break
            ubicacion = ubicacion.location

        if regla is None:
            self.procure_method = self.PROCURE_MAKE_TO_STOCK
            self.save(update_fields=['procure_method', 'updated_at'])
            return

        self.rule = regla
        self.procure_method = (
            regla.procure_method
            if regla.procure_method in (self.PROCURE_MAKE_TO_STOCK,
                                        self.PROCURE_MAKE_TO_ORDER)
            else self.PROCURE_MAKE_TO_STOCK)
        self.save(update_fields=['rule', 'procure_method', 'updated_at'])

    def _do_unreserve(self):
        """≙ ``_do_unreserve`` (``odoo19c: :1018-1044``).

        Suelta la reserva borrando las líneas no recogidas. Tres casos que la
        fuente salta en silencio y aquí también: cancelado, hecho hacia
        inventario (un desecho), y ya recogido.

        Un movimiento **hecho** sí revienta: soltar la reserva de algo ya
        entregado no tiene sentido y la fuente lo declara error.
        """
        if self.state == self.STATE_CANCEL:
            return True
        if self.state == self.STATE_DONE:
            if self.location_dest_usage == 'inventory':
                return True
            raise UserError(
                _('No puede quitar la reserva de un movimiento ya hecho.'))
        if self.picked:
            return True
        lineas = list(self.move_line_ids.all())
        recogida_alguna = any(ml.picked for ml in lineas)
        for ml in lineas:
            if not ml.picked:
                ml.delete()
        # ``write`` sobre la línea no dispara ``_recompute_state`` (a diferencia
        # de ``unlink``), así que hay que llamarlo donde no se borró ninguna.
        if recogida_alguna:
            self._recompute_state()
        return True

    # -- ola D · fusión, reparto en albarán y división --

    def _merge_moves_fields(self, moves=None, merge_extra=False):
        """≙ ``_merge_moves_fields`` (``odoo19c: :1260-1273``).

        Los valores del movimiento **superviviente** cuando varios se funden en
        uno. La cantidad se suma —salvo que se absorba un extra, donde manda la
        del primero— y la fecha depende de la política de envío: con «lo antes
        posible» gana la **más temprana**, porque el primer envío parcial ya
        sale; con «todo junto» gana la **más tardía**, porque nada sale hasta
        que todo esté.
        """
        conjunto = list(moves) if moves is not None else [self]
        estado = self._get_relevant_state_among_moves(moves=conjunto)
        origenes = {m.origin for m in conjunto if m.origin}
        albaranes = [m.picking for m in conjunto if m.picking_id]
        todos_directos = all(p.move_type == 'direct' for p in albaranes)
        fechas = [m.date for m in conjunto if m.date]
        return {
            'product_uom_qty': (conjunto[0].product_uom_qty if merge_extra
                                else sum(m.product_uom_qty for m in conjunto)),
            'date': (min(fechas) if todos_directos else max(fechas)) if fechas else None,
            'move_dest_ids': [d for m in conjunto for d in m.move_dest_ids.all()],
            'move_orig_ids': [o for m in conjunto for o in m.move_orig_ids.all()],
            'state': estado,
            'origin': '/'.join(origenes),
        }

    def _merge_move_itemgetter(self, distinct_fields, excluded_fields=None):
        """≙ ``_merge_move_itemgetter`` (``odoo19c: :1302-1321``).

        Devuelve la **función clave** por la que se agrupa: dos movimientos con
        la misma clave son fusionables. Su parte delicada es el campo decimal:
        se formatea a cadena con la precisión que corresponde, para que un
        error de redondeo no impida una fusión legítima.

        ``price_unit`` toma la menor precisión entre la de ``Product Price`` y
        la de la divisa de la empresa, igual que la fuente.

        **Divergencia declarada:** la fuente usa ``operator.itemgetter`` sobre
        el recordset, que indexa por nombre de campo. Aquí un modelo Django se
        lee con ``getattr``, así que la clave la arma un ``tuple(...)`` — misma
        semántica, distinto acceso. Y una relación múltiple
        (``never_product_template_attribute_value_ids``) entra como **tupla de
        claves primarias ordenada**: su gestor no es comparable ni hashable.
        """
        campos = [c for c in (distinct_fields or [])
                  if c not in set(excluded_fields or [])]
        decimales = {c for c in campos if c in ('price_unit',)}
        precision = {}
        if 'price_unit' in decimales:
            of_price = DecimalPrecision.precision_get('Product Price')
            divisas = [m.company.currency for m in [self]
                       if m.company_id and m.company.currency_id]
            de_divisa = min((d.decimal_places for d in divisas), default=None)
            precision['price_unit'] = (min(de_divisa, of_price)
                                       if de_divisa is not None else of_price)

        def valor(move, campo):
            leido = getattr(move, campo, None)
            if campo in decimales:
                digitos = precision[campo]
                # ``float_round`` es el algoritmo de la fuente y trabaja en
                # coma flotante; la columna es ``Decimal``. La conversión va en
                # el llamador, que es donde la frontera se conoce (H-API-588,
                # tarea **#344**).
                redondeado = float_round(float(leido or 0), precision_digits=digitos)
                return f'{redondeado:.{digitos}f}'
            if hasattr(leido, 'all'):          # relación múltiple
                return tuple(sorted(leido.values_list('pk', flat=True)))
            return leido

        return lambda move: tuple(valor(move, c) for c in campos)

    def _merge_moves(self, moves=None, merge_into=None, merge_extra=False):
        """≙ ``_merge_moves`` (``odoo19c: :1323-1404``).

        Funde los movimientos equivalentes de un mismo albarán en uno solo, y
        absorbe los **negativos** contra su positivo correspondiente. Devuelve
        los movimientos que sobreviven.

        La absorción de negativos es lo que no se puede simplificar: un
        movimiento de cantidad negativa (una devolución dentro de la misma
        transferencia) se resta del positivo que comparte su clave *limitada*
        —la clave sin ``description_picking``—, y el precio unitario se
        recalcula sobre el **valor total** resultante, no sobre la media de los
        dos precios. Si el positivo no alcanza a cubrirlo, se agota y el
        negativo sigue buscando en el siguiente.

        **Divergencia declarada:** la fuente separa los borrados
        (``unlink``) de los cancelados (``_action_cancel``) y llama a ambos
        sobre el recordset. Aquí se hace por instancia, en el mismo orden.
        """
        conjunto = list(moves) if moves is not None else [self]
        candidatos = set()
        if merge_into is None:
            for move in conjunto:
                move._update_candidate_moves_list(candidatos)
        else:
            candidatos.add(tuple(dict.fromkeys([*merge_into, *conjunto])))

        distintos = self._prepare_merge_moves_distinct_fields(merge_extra=merge_extra)
        excluidos = self._prepare_merge_negative_moves_excluded_distinct_fields()
        key_of = self._merge_move_itemgetter(distintos)
        clave_limitada = self._merge_move_itemgetter(distintos, excluidos)
        of_price = DecimalPrecision.precision_get('Product Price')

        por_borrar, fusionados, por_cancelar = [], [], []
        negativos = [m for m in conjunto if m.product_uom_qty < 0]
        for negativo in negativos:
            # Se le suelta el albarán: o lo absorbe un positivo, o abre un
            # pedido pendiente. En ninguno de los dos casos deja rastro aquí.
            negativo.picking = None
            negativo.save(update_fields=['picking', 'updated_at'])

        por_clave_limitada = defaultdict(list)
        for grupo in candidatos:
            vivos = [m for m in self._resolve_candidates(grupo)
                     if m.state not in (self.STATE_DONE, self.STATE_CANCEL,
                                        self.STATE_DRAFT)
                     and m.pk not in {n.pk for n in negativos}]
            for _k, iguales in groupby(sorted(vivos, key=key_of), key=key_of):
                iguales = list(iguales)
                if len(iguales) > 1:
                    superviviente = iguales[0]
                    for sobrante in iguales[1:]:
                        sobrante.move_line_ids.update(move=superviviente)
                    valores = superviviente._merge_moves_fields(
                        moves=iguales, merge_extra=merge_extra)
                    superviviente._apply_merge(valores)
                    por_borrar.extend(iguales[1:])
                    fusionados.append(superviviente)
                if iguales:
                    por_clave_limitada[clave_limitada(iguales[0])].append(iguales[0])

        for negativo in negativos:
            for positivo in por_clave_limitada.get(clave_limitada(negativo), []):
                total_value = (positivo.product_qty * positivo.price_unit
                               + negativo.product_qty * negativo.price_unit)
                if positivo.product_uom_qty >= abs(negativo.product_uom_qty):
                    positivo.product_uom_qty += negativo.product_uom_qty
                    positivo.price_unit = (
                        float_round(total_value / positivo.product_qty,
                                    precision_digits=of_price)
                        if positivo.product_qty else Decimal('0'))
                    positivo.move_dest_ids.add(*[
                        d for d in negativo.move_dest_ids.all()
                        if d.location_id == positivo.location_dest_id])
                    positivo.move_orig_ids.add(*[
                        o for o in negativo.move_orig_ids.all()
                        if o.location_dest_id == positivo.location_id])
                    positivo.save(update_fields=['product_uom_qty', 'price_unit',
                                                 'updated_at'])
                    fusionados.append(positivo)
                    por_borrar.append(negativo)
                    if not positivo.product_uom_qty:
                        por_cancelar.append(positivo)
                    break
                negativo.product_uom_qty += positivo.product_uom_qty
                negativo.price_unit = float_round(
                    total_value / negativo.product_qty, precision_digits=of_price)
                negativo.save(update_fields=['product_uom_qty', 'price_unit',
                                             'updated_at'])
                positivo.product_uom_qty = Decimal('0')
                positivo.save(update_fields=['product_uom_qty', 'updated_at'])
                por_cancelar.append(positivo)

        # El conjunto de borrados se toma ANTES de borrar: ``Model.delete()``
        # de Django pone ``pk = None`` sobre la instancia, así que leerlo
        # después devuelve un conjunto de ``None`` y el filtro de abajo deja
        # pasar lo que acaba de desaparecer.
        borrados = {m.pk for m in por_borrar}
        for move in [*por_borrar, *por_cancelar]:
            move._clean_merged()
        for move in por_borrar:
            move._action_cancel()
            move.delete()
        for move in por_cancelar:
            if not move.picked:
                move._action_cancel()

        vivos = [m for m in [*conjunto, *fusionados] if m.pk not in borrados]
        return list({m.pk: m for m in vivos}.values())

    def _resolve_candidates(self, group):
        """Los movimientos de una entrada del conjunto de candidatos.

        ``_update_candidate_moves_list`` mete **albaranes** en el conjunto (es
        lo que la fuente hace con ``picking.move_ids``); ``_merge_moves`` con
        ``merge_into`` mete una tupla de movimientos ya resueltos. Este ayudante
        es el punto donde las dos formas se vuelven una lista de movimientos —
        la fuente no lo necesita porque allá ambas son el mismo recordset.
        """
        if isinstance(group, tuple):
            return list(group)
        if isinstance(group, int):
            # ``_update_candidate_moves_list`` mete el ``attname`` del albarán
            # (un entero), no el objeto: es lo que hace hashable al conjunto.
            return list(type(self).objects.filter(picking=group))
        return list(group.move_ids.all())

    def _apply_merge(self, values):
        """Escribe sobre el superviviente los valores que la fusión calculó.

        Separa las relaciones múltiples de los escalares: en la fuente
        ``write`` acepta las dos cosas en el mismo diccionario porque el ORM
        traduce los comandos ``(4, id)``; aquí el gestor de la relación se
        toca aparte.
        """
        destinos = values.pop('move_dest_ids', [])
        origenes = values.pop('move_orig_ids', [])
        for campo, valor in values.items():
            setattr(self, campo, valor)
        self.save(update_fields=[*values, 'updated_at'])
        if destinos:
            self.move_dest_ids.add(*destinos)
        if origenes:
            self.move_orig_ids.add(*origenes)
        return self

    def _search_picking_for_assignation_domain(self):
        """≙ ``_search_picking_for_assignation_domain`` (``odoo19c: :1529-1537``).

        El filtro del albarán al que este movimiento se puede sumar. Un albarán
        ya **impreso** queda fuera: se entregó al operario en papel y añadirle
        líneas invisibles es lo que la condición evita.

        Devuelve un diccionario de filtros de Django, que es la forma que este
        árbol da al ``domain`` de la fuente.

        **Divergencia declarada:** la fuente filtra por ``reference_ids``
        directamente sobre el albarán, que allá es un ``related`` almacenable.
        Aquí ``StockPicking.reference_ids`` es una **property** —la referencia
        lo declara ``related`` sin ``store``— así que no se puede filtrar por
        ella: el filtro atraviesa la misma relación a mano
        (``move_ids__reference_ids``), que es lo que la property calcula.
        """
        destino = (self.location_dest_id
                   or (self.picking_type.default_location_dest_id
                       if self.picking_type_id else None))
        return {
            'move_ids__reference_ids__in': list(self.reference_ids.all()),
            'location': self.location_id,
            'location_dest': destino,
            'picking_type': self.picking_type_id,
            'printed': False,
            'state__in': ['draft', 'confirmed', 'waiting',
                          'partially_available', 'assigned'],
        }

    def _search_picking_for_assignation(self):
        """≙ ``_search_picking_for_assignation`` (``odoo19c: :1539-1545``).

        Sin referencias no hay albarán al que sumarse: la referencia es lo que
        identifica al grupo de aprovisionamiento.
        """
        if not self.reference_ids.exists():
            return None
        picking = apps.get_model('stock', 'StockPicking')
        return picking.objects.filter(
            **self._search_picking_for_assignation_domain()).distinct().first()

    def _assign_picking(self, moves=None):
        """≙ ``_assign_picking`` (``odoo19c: :1547-1578``).

        Reparte los movimientos en albaranes: busca uno existente que los
        admita y, si no lo hay, crea uno nuevo. Los movimientos **negativos**
        no estrenan albarán — se van a revertir y a asignar a otro.
        """
        conjunto = list(moves) if moves is not None else [self]
        picking = apps.get_model('stock', 'StockPicking')
        for _k, grupo in groupby(sorted(conjunto, key=lambda m: str(m._key_assign_picking())),
                                 key=lambda m: m._key_assign_picking()):
            grupo = list(grupo)
            nuevo = False
            albaran = grupo[0]._search_picking_for_assignation()
            if albaran is not None:
                valores = grupo[0]._assign_picking_values(albaran, moves=grupo)
                if valores:
                    for campo, valor in valores.items():
                        setattr(albaran, campo, valor)
                    albaran.save(update_fields=[*valores, 'updated_at'])
            else:
                grupo = [m for m in grupo if m.product_uom_qty >= 0]
                if not grupo:
                    continue
                nuevo = True
                albaran = picking.objects.create(
                    **grupo[0]._get_new_picking_values(moves=grupo))
            for move in grupo:
                move.picking = albaran
                move.save(update_fields=['picking', 'updated_at'])
                move._assign_picking_post_process(new=nuevo)
        return True

    def _assign_picking_values(self, picking, moves=None):
        """≙ ``_assign_picking_values`` (``odoo19c: :1580-1590``).

        Qué cambia en el albarán al recibir movimientos nuevos. Si los
        movimientos traen contactos distintos del suyo, el albarán **pierde**
        el contacto: pasa a referirse a varios y ninguno es el correcto. Los
        orígenes, en cambio, se acumulan sin repetir.
        """
        conjunto = list(moves) if moves is not None else [self]
        valores = {}
        if any(picking.partner_id != m.partner_id for m in conjunto):
            valores['partner'] = None
        if any(picking.origin != m.origin for m in conjunto):
            actuales = picking.origin.split(',') if picking.origin else []
            nuevo = ','.join(OrderedSet(
                [*actuales, *[m.origin for m in conjunto if m.origin]]))
            if picking.origin != nuevo:
                valores['origin'] = nuevo
        return valores

    def _assign_picking_post_process(self, new=False):
        """≙ ``_assign_picking_post_process`` (``odoo19c: :1592-1593``).

        Vacío en la referencia: es el punto de extensión que otros addons
        sobreescriben para actuar tras el reparto.
        """
        return

    def _get_new_picking_values(self, moves=None):
        """≙ ``_get_new_picking_values`` (``odoo19c: :1651-1677``).

        Los valores del albarán que se crea para un grupo de movimientos. El
        origen concatena hasta **cinco** documentos distintos y añade puntos
        suspensivos si hay más — el campo es una etiqueta para leer, no un
        índice. El contacto sólo entra si es el mismo para todo el grupo.
        """
        conjunto = list(moves) if moves is not None else [self]
        origenes = list(dict.fromkeys(m.origin for m in conjunto if m.origin))
        if not origenes:
            origen = ''
        else:
            origen = ','.join(origenes[:5])
            if len(origenes) > 5:
                origen += '...'
        contactos = {m.partner_id for m in conjunto if m.partner_id}
        valores = {
            'origin': origen,
            'company': conjunto[0].company,
            'user': None,
            'partner': (conjunto[0].partner if len(contactos) == 1 else None),
            'picking_type': conjunto[0].picking_type,
            'location': conjunto[0].location,
        }
        if conjunto[0].location_dest_id:
            valores['location_dest'] = conjunto[0].location_dest
        return valores

    def _create_backorder(self, moves=None):
        """≙ ``_create_backorder`` (``odoo19c: :2314-2330``).

        Cuando se entrega menos de lo pedido, lo que falta no se pierde: se
        parte en un movimiento nuevo que queda pendiente. La comparación usa la
        precisión **del producto**, no la de la unidad del movimiento — una
        diferencia por debajo de esa precisión no justifica un pendiente.
        """
        conjunto = list(moves) if moves is not None else [self]
        redondeo = DecimalPrecision.precision_get('Product Unit')
        valores = []
        for move in conjunto:
            if float_compare(float(move.quantity), float(move.product_uom_qty),
                             precision_digits=redondeo) < 0:
                por_partir = move.product_uom.compute_quantity(
                    float(move.product_uom_qty - move.quantity), move.product.uom,
                    rounding_method='HALF-UP')
                valores += move._split(Decimal(str(por_partir)))
        # ``_split`` devuelve las relaciones múltiples dentro del diccionario,
        # igual que la fuente —allá el ORM traduce los comandos ``(4, id)``—;
        # aquí ``objects.create`` no las admite, así que se enlazan después.
        pendientes = []
        for vals in valores:
            destinos = vals.pop('move_dest_ids', [])
            origenes = vals.pop('move_orig_ids', [])
            move = type(self).objects.create(**vals)
            if destinos:
                move.move_dest_ids.add(*destinos)
            if origenes:
                move.move_orig_ids.add(*origenes)
            pendientes.append(move)
        for move in pendientes:
            move._action_confirm()
        return pendientes

    def _prepare_move_split_vals(self, qty, force_split_uom=None):
        """≙ ``_prepare_move_split_vals`` (``odoo19c: :2345-2357``).

        Los valores del movimiento que nace de una división. Hereda la cadena
        —origen y destino— **salvo** los destinos ya hechos o cancelados: ésos
        no esperan nada del pendiente.

        ``force_split_uom`` es el contexto homónimo de la fuente, aquí
        parámetro explícito: este ORM no lleva contexto de entorno en la
        llamada (mismo criterio que ``merge_extra``).
        """
        valores = {
            'product': self.product,
            'product_uom_qty': qty,
            'procure_method': self.procure_method,
            'location': self.location,
            'location_dest': self.location_dest,
            'company': self.company,
            'picking_type': self.picking_type,
            'origin': self.origin,
            'state': self.state,
            'move_dest_ids': [d for d in self.move_dest_ids.all()
                              if d.state not in (self.STATE_DONE, self.STATE_CANCEL)],
            'move_orig_ids': list(self.move_orig_ids.all()),
            'origin_returned_move': self.origin_returned_move,
            'price_unit': self.price_unit,
            'date_deadline': self.date_deadline,
            'product_uom': force_split_uom or self.product_uom,
        }
        return valores

    def _split(self, qty, restrict_partner=None, force_split_uom=None,
               source_location=None):
        """≙ ``_split`` (``odoo19c: :2359-2403``).

        Parte la cantidad y devuelve los **valores** del movimiento nuevo — no
        lo crea: quien llama decide cuándo. ``qty`` viene en la unidad del
        producto.

        Lo que decide la unidad del pendiente es un **ida y vuelta**: si
        convertir a la unidad del movimiento y volver da la cantidad original,
        el pendiente conserva esa unidad; si no, se crea en la del producto
        para no arrastrar el error de redondeo. Es el mismo criterio que
        ``_prepare_move_line_vals`` aplica a la línea.

        Un movimiento **hecho** o **cancelado** no se parte, y uno en borrador
        tampoco: sin confirmar puede sustituirse por otros (una lista de
        materiales fantasma), y partirlo antes complica esa sustitución.
        """
        if self.state in (self.STATE_DONE, self.STATE_CANCEL):
            raise UserError(
                _("No puede dividir un movimiento en estado 'Hecho' o 'Cancelado'."))
        if self.state == self.STATE_DRAFT:
            raise UserError(
                _('No puede dividir un movimiento en borrador. Debe confirmarse primero.'))
        if not qty:
            return []

        # ``compute_quantity`` y ``float_compare`` son el algoritmo de la
        # fuente y trabajan en coma flotante; las columnas son ``Decimal``. La
        # conversión va aquí, en la frontera (H-API-588, tarea **#344**).
        redondeo = DecimalPrecision.precision_get('Product Unit')
        in_uom = self.product.uom.compute_quantity(
            float(qty), self.product_uom, rounding_method='HALF-UP')
        de_vuelta = self.product_uom.compute_quantity(
            in_uom, self.product.uom, rounding_method='HALF-UP')
        if float_compare(float(qty), de_vuelta, precision_digits=redondeo) == 0:
            valores = self._prepare_move_split_vals(Decimal(str(in_uom)))
        else:
            valores = self._prepare_move_split_vals(
                qty, force_split_uom=self.product.uom)

        if restrict_partner is not None:
            valores['restrict_partner'] = restrict_partner
        if source_location is not None:
            valores['location'] = source_location

        # La cantidad del original baja en lo que se llevó el pendiente.
        restante = self.product.uom.compute_quantity(
            float(max(Decimal('0'), self.product_qty - qty)), self.product_uom,
            round=False)
        self.product_uom_qty = Decimal(str(
            float_round(restante, precision_digits=redondeo)))
        self.save(update_fields=['product_uom_qty', 'updated_at'])
        self._recompute_state()
        return [valores]

    # -- ola E · lotes y números de serie --

    @property
    def lot_ids(self):
        """≙ ``_compute_lot_ids`` (``odoo19c: :601-610``).

        Los lotes que este movimiento lleva puestos son los de sus líneas **con
        cantidad**: el dominio de la fuente exige ``lot_id != False`` y
        ``quantity != 0``, así que una línea a cero no aporta su lote aunque lo
        tenga asignado.
        """
        return [linea.lot for linea in self.move_line_ids.all()
                if linea.lot_id and linea.quantity]

    @lot_ids.setter
    def lot_ids(self, lots):
        """La fuente declara el campo ``inverse='_set_lot_ids'`` (``:192``)."""
        self._set_lot_ids(lots)

    def _set_lot_ids(self, lots):
        """≙ ``_set_lot_ids`` (``odoo19c: :612-720``).

        Fijar los lotes de un movimiento **adapta la reserva**, y su docstring
        declara las dos reglas: quitar un lote retira su referencia de la línea
        pero no la cantidad reservada; añadir lotes se resuelve en orden,
        asignando a cada uno el máximo entre la demanda restante y lo
        disponible.

        Cada lote necesita su propia línea, así que la reserva base es **una
        unidad por lote** y el sobrante (``extra_uom_qty``) se reparte después.

        **DIVERGENCIA de FORMA declarada:** la colección llega como parámetro.
        Allá ``lot_ids`` es un campo y el ``inverse`` lo lee de ``self``; aquí
        es una property, así que el valor nuevo viaja en la llamada. Es la misma
        convención explícita que fijó ``_get_relevant_state_among_moves``.
        """
        if not self.product_id or self.product.tracking == 'none':
            return self
        lots = list(lots or [])
        lineas = list(self.move_line_ids.all())
        if (self.state == self.STATE_ASSIGNED
                and all(l.lot_id for l in lineas)
                and {l.lot_id for l in lineas} == {lot.pk for lot in lots}):
            # Ya reservado con exactamente esos lotes: no hay nada que rehacer.
            return self

        product = self.product
        uom = product.uom if product.tracking == 'serial' else self.product_uom
        ordenes = []
        lote_por_nombre = {lot.name: lot for lot in lots}
        libres = []
        free_uom_qty = self.product_uom.compute_quantity(
            float(max(self.quantity or Decimal('0'), self.product_uom_qty or Decimal('0'))),
            product.uom)
        asignados = set()
        for linea in lineas:
            nombre = linea.lot.name if linea.lot_id else linea.lot_name
            if linea.product_uom.is_zero(float(linea.quantity or 0)):
                continue
            elif not linea.lot_id and not linea.lot_name:
                libres.append(linea)
            elif nombre in lote_por_nombre:
                lote = lote_por_nombre[nombre]
                asignados.add(lote.pk)
                free_uom_qty -= linea.product_uom.compute_quantity(
                    float(linea.quantity or 0), product.uom)
                ordenes.append(('update', linea, {'lot': lote}))
            else:
                ordenes.append(('delete', linea, None))

        sin_reserva = self._should_bypass_reservation()
        # Una línea por lote: la reserva base es 1 y lo que sobre se reparte.
        extra_uom_qty = free_uom_qty - len({lot.pk for lot in lots} - asignados)
        quants_by_lot = {}
        if not sin_reserva:
            for quant in StockQuant._gather(product, self.location):
                quants_by_lot.setdefault(quant.lot_id, []).append(quant)

        for lote in lots:
            if lote.pk in asignados:
                continue
            if sin_reserva:
                if libres:
                    linea = libres.pop(0)
                    cantidad = (Decimal('1') if product.tracking == 'serial'
                                else linea.quantity)
                    ordenes.append(('update', linea, {
                        'lot': lote, 'lot_name': lote.name,
                        'product_uom': uom, 'quantity': cantidad}))
                    extra_uom_qty -= uom.compute_quantity(
                        float(cantidad), product.uom) - 1
                else:
                    reservar = 1.0
                    if (product.tracking == 'lot'
                            and product.uom.compare(extra_uom_qty, 0.0) > 0):
                        reservar += extra_uom_qty
                        extra_uom_qty = 0
                    vals = self._prepare_move_line_vals(quantity=reservar)
                    vals.update({'lot': lote, 'lot_name': lote.name})
                    if product.tracking == 'serial':
                        vals.update({'quantity': Decimal('1'),
                                     'product_uom': product.uom})
                    ordenes.append(('create', None, vals))
            else:
                reservado = False
                for quant in quants_by_lot.get(lote.pk, []):
                    if reservado and product.uom.compare(extra_uom_qty, 0.0) <= 0:
                        break
                    disponible = float(quant.available_quantity or 0)
                    if not quant.lot_id or product.uom.compare(disponible, 0.0) <= 0:
                        continue
                    reservar = min(
                        disponible,
                        max(extra_uom_qty if reservado else extra_uom_qty + 1, 1))
                    if product.uom.compare(reservar, 0.0) > 0:
                        vals = self._prepare_move_line_vals(
                            quantity=reservar, reserved_quant=quant)
                        vals.update({'lot': lote, 'lot_name': lote.name})
                        if product.tracking == 'serial':
                            reservar = 1
                            vals.update({'quantity': Decimal('1'),
                                         'product_uom': product.uom})
                        ordenes.append(('create', None, vals))
                        extra_uom_qty -= reservar if reservado else reservar - 1
                        reservado = True
                if not reservado:
                    # Sin quant que reservar, se toma una unidad del producto.
                    vals = self._prepare_move_line_vals(quantity=1.0)
                    vals.update({'lot': lote, 'lot_name': lote.name})
                    if product.tracking == 'serial':
                        vals.update({'quantity': Decimal('1'),
                                     'product_uom': product.uom})
                    ordenes.append(('create', None, vals))

        if not sin_reserva and libres:
            # Se recrean las líneas vacías para alterar el orden de reserva: la
            # des-reserva consume por orden, y las líneas con lote deben quedar
            # por delante (``odoo19c: :706-718``).
            for linea in libres:
                ordenes.append(('delete', linea, None))
            for linea in libres:
                if product.uom.compare(extra_uom_qty, 0.0) <= 0:
                    break
                in_product = linea.product_uom.compute_quantity(
                    float(linea.quantity or 0), product.uom)
                reservar = min(in_product, extra_uom_qty)
                ordenes.append(('create', None, {
                    'move': self, 'product': linea.product,
                    'product_uom': linea.product_uom,
                    'location': linea.location, 'location_dest': linea.location_dest,
                    'company': linea.company, 'picking': linea.picking,
                    'picked': linea.picked,
                    'quantity': Decimal(str(product.uom.compute_quantity(
                        reservar, linea.product_uom))),
                }))
                extra_uom_qty -= reservar

        self._apply_move_line_commands(ordenes)
        return self

    def _apply_move_line_commands(self, commands):
        """Ejecuta las órdenes que los generadores de línea calcularon.

        **DIVERGENCIA de FORMA declarada, la misma de la ola C:** la fuente
        acumula ``Command.update``/``create``/``delete`` y los entrega al ORM,
        que los traduce al escribir. El ``Command`` de este árbol es
        **ejecutivo** —escribe al llamarlo—, así que un generador no puede
        devolver una lista de comandos sin haber escrito ya. Devuelve tuplas y
        este ayudante las aplica. Ver :ref:`h-api-589` (tarea **#345**).
        """
        creadas = []
        for orden in commands:
            accion, linea, vals = orden
            if accion == 'delete':
                linea.delete()
            elif accion == 'update':
                for campo, valor in vals.items():
                    setattr(linea, campo, valor)
                linea.save(update_fields=[*vals, 'updated_at'])
            elif accion == 'create':
                creadas.append(StockMoveLine.objects.create(**vals))
        return creadas

    @classmethod
    def _create_lot_ids_from_move_line_vals(cls, vals_list, product_id,
                                            company_id=None):
        """≙ ``_create_lot_ids_from_move_line_vals`` (``odoo19c: :1067-1091``).

        Resuelve cada ``lot_name`` a un lote: el que ya exista para ese producto
        (de la empresa o sin empresa), y si no existe lo crea. Una vez resuelto,
        el nombre sobra y se vacía — el dato vive en la relación.

        **DIVERGENCIA declarada:** la fuente escribe ``lot_name = False``; aquí
        ``None``, porque estos valores acaban en un ``Char(null=True)`` y un
        booleano en columna de texto es el defecto de :ref:`h-api-590`.
        """
        nombres = [v['lot_name'] for v in vals_list if v.get('lot_name')]
        if not nombres:
            return vals_list
        StockLot = apps.get_model('stock', 'StockLot')
        existentes = list(StockLot.objects.filter(
            Q(company=company_id) | Q(company__isnull=True),
            product=product_id, name__in=nombres))
        ya = {lot.name for lot in existentes}
        existentes += [StockLot.objects.create(product_id=product_id, name=nombre)
                       for nombre in dict.fromkeys(nombres) if nombre not in ya]

        por_nombre = {lot.name: lot.pk for lot in existentes}
        for vals in vals_list:
            nombre = vals.get('lot_name', None)
            if not nombre:
                continue
            vals['lot_id'] = por_nombre[nombre]
            vals['lot_name'] = None
        return vals_list

    @classmethod
    def split_lots(cls, lots):
        """≙ ``split_lots`` (``odoo19c: :1093-1129``).

        Interpreta lo que el usuario pega en el campo de lotes: un nombre por
        renglón, y —por comodidad— el punto y coma se normaliza a tabulador
        para que el separador de la cantidad sea uno solo. Si la parte extra no
        se puede interpretar, **no se adivina**: el renglón entero pasa a ser el
        nombre del lote.
        """
        salto, separator = '\n', '\t'
        opciones = False
        if not lots:
            return []

        renglones = [r for r in lots.split(salto) if r]
        valores = []
        for texto in renglones:
            vals = {'lot_name': texto, 'quantity': 1}
            partes = texto.replace(';', separator).split(separator)
            opciones = opciones or cls._get_formating_options(partes[1:])
            for extra in partes[1:]:
                datos = cls._convert_string_into_field_data(extra, opciones)
                if datos:
                    texto = partes[0]
                    if datos == 'ignore':
                        vals.update(lot_name=texto)
                    else:
                        vals.update(**datos, lot_name=texto)
                else:
                    vals['lot_name'] = texto
                    break
            valores.append(vals)
        return valores

    def _generate_serial_move_line_commands(self, field_data, location_dest=None,
                                            origin_move_line=None):
        """≙ ``_generate_serial_move_line_commands`` (``odoo19c: :1595-1645``).

        Traduce una lista de ``{lot_name, quantity}`` a las órdenes que crean o
        actualizan líneas. Su regla es el **reuso**: primero se llenan las
        líneas que aún no tienen lote ni nombre, y sólo cuando se agotan nace
        una línea nueva, cuyo destino lo decide la estrategia de ubicación
        acumulando lo ya colocado en cada una.
        """
        destino = None
        base = {
            'move': self,
            'picking': self.picking,
            'location': self.location,
            'product': self.product,
            'product_uom': self.product.uom,
            'company': self.company,
        }
        if origin_move_line is not None:
            destino = origin_move_line.location_dest
            base.update({'owner': origin_move_line.owner,
                         'package': origin_move_line.package})
        destino = destino or location_dest

        libres = [l for l in self.move_line_ids.all()
                  if not l.lot_id and not l.lot_name]
        ordenes = []
        by_location = defaultdict(float)
        for vals in field_data:
            cantidad = vals['quantity']
            if libres:
                linea = libres.pop(0)
                ordenes.append(('update', linea, dict(vals)))
                by_location[linea.location_dest_id] += cantidad
            else:
                donde = destino or self.location_dest._get_putaway_strategy(
                    self.product, quantity=cantidad,
                    additional_qty=by_location)
                ordenes.append(('create', {**base, **vals, 'location_dest': donde}))
                by_location[donde.pk if donde is not None else None] += cantidad
        return ordenes

    def _generate_serial_numbers(self, next_serial, next_serial_count=False,
                                 location=None):
        """≙ ``_generate_serial_numbers`` (``odoo19c: :1049-1065``).

        Genera los nombres de serie a partir del primero y crea **una línea por
        unidad**. Si el tipo de albarán reutiliza lotes existentes, los nombres
        se resuelven a lote antes de escribir las líneas.
        """
        StockLot = apps.get_model('stock', 'StockLot')
        if location is None:
            location = self.location_dest
        count = next_serial_count or self.next_serial_count
        if not count:
            raise ValidationError(
                _('The number of Serial Numbers to generate must be greater '
                  'than zero.'))
        nombres = StockLot.generate_lot_names(next_serial, count)
        field_data = [{'lot_name': n['lot_name'], 'quantity': 1} for n in nombres]
        if self._can_create_lot():
            self._create_lot_ids_from_move_line_vals(
                field_data, self.product_id, self.company_id)
        ordenes = self._generate_serial_move_line_commands(
            field_data, location_dest=location)
        self._apply_move_line_commands(
            [o if len(o) == 3 else (o[0], None, o[1]) for o in ordenes])
        return True

    def _onchange_lot_ids(self, lots, previous_lots=None):
        """≙ ``_onchange_lot_ids`` (``odoo19c: :1449-1520``).

        Ajusta la cantidad del movimiento a la que resulta de fijar esos lotes:
        lo que las líneas sin lote pueden absorber, más lo ya asignado a los
        lotes que siguen en el conjunto. Los lotes **nuevos** —los que no
        estaban antes— exigen cada uno su propia línea, así que suben la
        cantidad al menos en una unidad mínima.

        Devuelve el aviso de la fuente cuando un número de serie del conjunto
        existe **fuera** de la ubicación de origen, y ``None`` si no hay nada
        que advertir.

        **DIVERGENCIA de FORMA declarada, doble:** la colección nueva llega como
        parámetro (``lot_ids`` es property, no campo) y la **anterior** también.
        Allá el ORM compara contra ``self._origin``, el registro tal como está
        en la base mientras el formulario aún no se guarda; aquí no hay ese
        búfer sin asentar, así que por defecto se lee de las líneas actuales —
        lo que equivale a ``_origin`` **si se llama antes** de ``_set_lot_ids``,
        que es el orden en que la fuente lo dispara.
        """
        product = self.product if self.product_id else None
        if product is None or product.tracking == 'none':
            return None

        asignada = 0.0
        asignable = 0.0
        sin_lote = 0
        nuevos = OrderedSet(lot.name for lot in lots if lot.name)
        for linea in self.move_line_ids.all():
            in_uom = linea.product_uom.compute_quantity(
                float(linea.quantity or 0), self.product_uom)
            nombre = linea.lot.name if linea.lot_id else linea.lot_name
            if not nombre:
                asignable += in_uom
                sin_lote += 1
            elif nombre in nuevos:
                asignada += in_uom

        if previous_lots is None:
            previous_lots = self.lot_ids
        anteriores = OrderedSet(lot.name for lot in previous_lots if lot.name)
        extra = [n for n in nuevos if n not in anteriores]
        cantidad = asignada + asignable
        if not extra:
            # Sin lotes nuevos no hay reserva que ampliar: la cantidad es la
            # que ya sostienen las líneas.
            self.quantity = Decimal(str(cantidad))
            self.save(update_fields=['quantity', 'updated_at'])
            return None

        base = self.picking.location if self.picking_id else self.location
        uom = self.product_uom
        minima = product.uom.compute_quantity(1.0, uom)
        candidatos = StockQuant.objects.filter(
            product=product, lot__name__in=extra,
            lot__isnull=False,
        ).exclude(quantity=0).filter(
            Q(location__usage__in=('internal', 'transit', 'customer')),
            Q(company__isnull=True) | Q(company=self.company_id),
        )

        if self._should_bypass_reservation():
            # Cada lote nuevo necesita su línea: los que exceden a las líneas
            # disponibles suben la cantidad en una unidad mínima cada uno.
            exceden = max(len(extra) - sin_lote, 0)
            if exceden > 0:
                cantidad = max(float(self.product_uom_qty or 0),
                               cantidad + exceden * minima)
        else:
            libre = float(self.product_uom_qty or 0) - asignada
            disponible_por_lote = defaultdict(float)
            for quant in candidatos.filter(base.child_of_domain('location')):
                disponible_por_lote[quant.lot.name] += product.uom.compute_quantity(
                    float((quant.quantity or 0) - (quant.reserved_quantity or 0)), uom)
            # Cada lote se representa con una línea, así que de entrada se
            # reserva la unidad mínima por lote; el resto se reparte después.
            libre -= len(extra) * minima
            nueva_asignada = len(extra) * minima
            for nombre in extra:
                if uom.compare(libre, 0.0) > 0:
                    de_mas = min(disponible_por_lote[nombre],
                                 libre + minima) - minima
                    if uom.compare(de_mas, 0) > 0:
                        nueva_asignada += de_mas
                        libre -= de_mas
            cantidad += max(0.0, nueva_asignada - asignable)

        self.quantity = Decimal(str(cantidad))
        self.save(update_fields=['quantity', 'updated_at'])

        if product.tracking == 'serial':
            problematicos = candidatos.exclude(base.child_of_domain('location'))
            if problematicos.exists():
                detalle = ''.join(
                    _('\n(%(serial_number)s) exists in location %(location)s',
                      serial_number=str(quant.lot), location=str(quant.location))
                    for quant in problematicos)
                return {'warning': {
                    'title': _('Warning'),
                    'message': _('Unavailable Serial numbers. Please correct '
                                 'the serial numbers encoded: '
                                 '%(serial_numbers_to_locations)s',
                                 serial_numbers_to_locations=detalle)}}
        return None

    @classmethod
    def action_generate_lot_line_vals(cls, context_data, mode, first_lot, count,
                                      lot_text):
        """≙ ``action_generate_lot_line_vals`` (``odoo19c: :1131-1207``).

        Los valores con que el cliente pinta las líneas de lote/serie antes de
        escribirlas. En modo ``generate`` los nombres salen de la secuencia; en
        modo ``import``, del texto pegado. Con seguimiento **por lote** la
        demanda se reparte en tramos de ``count`` y el residuo va en la última
        fila; con seguimiento por serie cada fila vale una unidad.

        **Lo que este método NO porta, y por qué:** el bloque final de la fuente
        (``:1193-1206``) rebobina el contador de la secuencia tras el botón
        «New» del asistente. Depende de ``_get_current_sequence``,
        ``get_next_char`` y ``number_next_actual``, que ``ir.sequence`` **no
        declara en este árbol** — medido sobre ``src/addons/base/models/
        ir_sequence.py``. Es completitud de ``ir.sequence``, no de este archivo,
        y corrige un pre-incremento que sólo causa un asistente que aquí no
        existe. Sucesor: tarea **#394**.
        """
        if not context_data.get('default_product_id'):
            raise UserError(_('No product found to generate Serials/Lots for.'))
        assert mode in ('generate', 'import')
        StockLot = apps.get_model('stock', 'StockLot')
        StockLocation = apps.get_model('stock', 'StockLocation')
        ProductProduct = apps.get_model('product', 'ProductProduct')

        def reparto(quantity, qty_per_lot):
            if qty_per_lot <= 0:
                raise UserError(
                    _('The quantity per lot should always be a positive value.'))
            tramos = [qty_per_lot] * int(quantity // qty_per_lot)
            residuo = quantity % qty_per_lot
            if residuo:
                tramos.append(residuo)
            return tramos

        por_defecto = {k[len('default_'):]: v for k, v in context_data.items()
                       if k.startswith('default_')}

        if por_defecto.get('tracking') == 'lot' and mode == 'generate':
            cantidades = reparto(por_defecto['quantity'], count)
        else:
            cantidades = [1] * count

        if mode == 'generate':
            nombres = StockLot.generate_lot_names(first_lot, len(cantidades))
        else:
            nombres = cls.split_lots(lot_text)
            cantidades = [1] * len(nombres)

        valores = []
        destino = StockLocation.objects.filter(
            pk=por_defecto.get('location_dest_id')).first()
        product = ProductProduct.objects.get(pk=por_defecto['product_id'])
        for lote, qty in zip(nombres, cantidades):
            if not lote.get('quantity'):
                lote['quantity'] = qty
            donde = (destino._get_putaway_strategy(product, quantity=lote['quantity'])
                     if destino is not None else None)
            valores.append({
                **por_defecto, **lote,
                'location_dest_id': donde.pk if donde is not None else None,
                'product_uom_id': por_defecto.get('uom_id', product.uom.pk),
            })
        tipo_id = por_defecto.get('picking_type_id')
        if tipo_id:
            StockPickingType = apps.get_model('stock', 'StockPickingType')
            tipo = StockPickingType.objects.filter(pk=tipo_id).first()
            if tipo is not None and (tipo.use_existing_lots
                                     or context_data.get('force_lot_m2o')):
                cls._create_lot_ids_from_move_line_vals(
                    valores, por_defecto['product_id'],
                    por_defecto.get('company_id'))
        return valores

    def _action_confirm(self):
        """Confirma el movimiento (≙ ``_action_confirm``).

        Con orígenes pendientes → ``waiting`` (MTO); sin ellos → ``confirmed``.
        """
        if self.state in (self.STATE_DONE, self.STATE_CANCEL):
            return self
        has_pending_orig = self.move_orig_ids.exclude(state=self.STATE_DONE).exists()
        self.state = self.STATE_WAITING if has_pending_orig else self.STATE_CONFIRMED
        self.save(update_fields=['state', 'updated_at'])
        return self

    def _action_assign(self):
        """Reserva la disponibilidad (≙ ``_action_assign``).

        Reserva desde el stock disponible en la ubicación origen (``StockQuant``):
        ``quantity`` = min(demanda, disponible). Si cubre la demanda →
        ``assigned``; si cubre una parte → ``partially_available``, el séptimo
        estado que este pase repone (D-3).
        """
        if self.state not in (self.STATE_CONFIRMED, self.STATE_WAITING,
                              self.STATE_PARTIALLY_AVAILABLE, self.STATE_ASSIGNED):
            return self
        available = StockQuant.available_qty(self.product, self.location)
        self.quantity = min(self.product_uom_qty, available)
        if self.product_uom_qty > 0:
            if self.quantity >= self.product_uom_qty:
                self.state = self.STATE_ASSIGNED
            elif self.quantity > 0:
                self.state = self.STATE_PARTIALLY_AVAILABLE
        self.save(update_fields=['quantity', 'state', 'updated_at'])
        return self

    def _action_done(self):
        """Ejecuta el movimiento (≙ ``_action_done``): aplica los quants."""
        if self.state == self.STATE_CANCEL:
            return self
        done_qty = self.quantity or self.product_uom_qty
        StockQuant.apply_move(self.product, self.location, self.location_dest, done_qty)
        self.quantity = done_qty
        self.state = self.STATE_DONE
        self.save(update_fields=['quantity', 'state', 'updated_at'])
        return self

    def _action_cancel(self):
        """Cancela el movimiento (≙ ``_action_cancel``)."""
        if self.state == self.STATE_DONE:
            return self
        self.state = self.STATE_CANCEL
        self.quantity = Decimal('0.0000')
        self.save(update_fields=['state', 'quantity', 'updated_at'])
        return self
