"""``stock.quant`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_quant.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **quant** es la existencia de un producto en una ubicación, con sus
características (lote, paquete, propietario). Es la única tabla que sabe cuánto
hay y cuánto está comprometido; todo lo demás —reserva, ajuste de inventario,
FEFO— se apoya en ella.

Tres ejes que conviene no confundir, porque la referencia los mantiene
separados a propósito:

- ``quantity`` — lo que hay físicamente.
- ``reserved_quantity`` — lo que ya está comprometido a un movimiento.
- ``inventory_quantity`` — lo que alguien **contó**; sólo existe durante un
  ajuste de inventario y no es un tercer saldo.

Porte símbolo por símbolo — 109 de 109
========================================

Medido sobre ``odoo19c: addons/stock/models/stock_quant.py`` (1563 líneas):
4 atributos de clase, 29 campos y **76 métodos**.

*Métrica:* nombres de método por AST, con ``ast.walk`` — que ve también las
clases anidadas. *Ciega a:* las funciones **locales** de un método (closures),
que se cuentan aparte abajo.

Los 76 no son 72: cuatro pertenecen a ``PriorityQueue``, la clase anidada
dentro de ``_run_least_packages_removal_strategy_astar`` (``odoo19c: :659-669``).
Un primer conteo de este mismo puerto dijo 72 porque midió sólo el cuerpo de
``StockQuant`` — la ceguera que ``metrica-decide-la-conclusion.md`` describe,
detectada al re-medir con el instrumento correcto antes de commitear.

Atributos de clase — 4 de 4
-----------------------------

Los cuatro que la referencia declara (``:20-23``), verbatim.
``atributos-de-clase-de-modelo.md``: se portan todos los que la fuente
declare, o ninguno.

Campos — 29 de 29
-------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``product_id`` (45-48)                           ``product``
``product_tmpl_id`` (49-51, related)             property ``product_tmpl``
``product_uom_id`` (52-54, related)              property ``product_uom``
``is_favorite`` (55, related)                    property ``is_favorite``
``company_id`` (56, related+store)               ``company`` (almacenado)
``location_id`` (57-60)                          ``location``
``warehouse_id`` (61, related)                   property ``warehouse``
``storage_category_id`` (62, related)            property ``storage_category``
``cyclic_inventory_frequency`` (63, related)     property ``cyclic_inventory_frequency``
``lot_id`` (64-67)                               ``lot``
``lot_properties`` (68, related)                 property ``lot_properties``
``sn_duplicated`` (69, compute)                  property ``sn_duplicated``
``package_id`` (70-73)                           ``package``
``owner_id`` (74-77)                             ``owner``
``quantity`` (78-81)                             ``quantity``
``reserved_quantity`` (82-86)                    ``reserved_quantity``
``available_quantity`` (87-90, compute)          property ``available_quantity``
``in_date`` (91)                                 ``in_date``
``tracking`` (92, related)                       property ``tracking``
``on_hand`` (93, store=False + search)           property ``on_hand`` + ``_search_on_hand``
``product_categ_id`` (94, related)               property ``product_categ``
``inventory_quantity`` (97-99)                   ``inventory_quantity``
``inventory_quantity_auto_apply`` (100-104)      property + setter (compute+inverse)
``inventory_diff_quantity`` (105-108, store)     ``inventory_diff_quantity`` (almacenado)
``inventory_date`` (109-111, store)              ``inventory_date`` (almacenado)
``last_count_date`` (112, compute)               property ``last_count_date``
``inventory_quantity_set`` (113, store)          ``inventory_quantity_set`` (almacenado)
``is_outdated`` (114, compute + search)          property + ``_search_is_outdated``
``user_id`` (115-117)                            ``user``
===============================================  ======================================

Métodos — 76 de 76
--------------------

Todos conservan el **nombre y la visibilidad** de la referencia: un ``_foo``
allá es un ``_foo`` aquí (``porte-completo-no-parcial.md``, sección del guion
bajo — :ref:`h-api-581`). Los que la referencia declara ``@api.model`` son
``classmethod``; los de instancia son métodos de instancia.

===============================================  ======================================
Símbolo de la referencia (línea)                 Forma aquí
===============================================  ======================================
``_domain_location_id`` (25-28)                  ``_domain_location_id`` (classmethod)
``_domain_lot_id`` (30-36)                       ``_domain_lot_id`` (classmethod)
``_domain_product_id`` (38-42)                   ``_domain_product_id`` (classmethod)
``_compute_available_quantity`` (119-122)        property ``available_quantity``
``_compute_inventory_date`` (124-129)            ``_compute_inventory_date``
``_compute_last_count_date`` (131-177)           ``_compute_last_count_date``
``_search`` (179-184)                            ``_search`` (classmethod)
``_compute_inventory_diff_quantity`` (185-192)   ``_compute_inventory_diff_quantity``
``_compute_inventory_quantity_set`` (194-196)    ``_compute_inventory_quantity_set``
``_compute_is_outdated`` (198-202)               property ``is_outdated``
``_search_is_outdated`` (204-210)                ``_search_is_outdated`` (classmethod)
``_compute_inventory_quantity_auto_apply`` (212) property ``inventory_quantity_auto_apply``
``_compute_sn_duplicated`` (217-223)             property ``sn_duplicated``
``_set_inventory_quantity`` (225-237)            setter de ``inventory_quantity_auto_apply``
``_search_on_hand`` (239-243)                    ``_search_on_hand`` (classmethod)
``copy`` (245-246)                               ``copy``
``name_create`` (248-250)                        ``name_create`` (classmethod)
``create`` (252-312)                             ``create`` (classmethod)
``_load_records_create`` (315-322)               ``_load_records_create`` (classmethod)
``_load_records_write`` (324-326)                ``_load_records_write`` (classmethod)
``_read_group_select`` (328-338)                 ``_read_group_select`` (classmethod)
``get_import_templates`` (340-345)               ``get_import_templates`` (classmethod)
``_get_forbidden_fields_write`` (347-349)        ``_get_forbidden_fields_write``
``write`` (351-361)                              ``write``
``_unlink_except_wrong_permission`` (363-369)    ``_unlink_except_wrong_permission``
``action_view_stock_moves`` (371-388)            ``action_view_stock_moves``
``action_view_orderpoints`` (390-394)            ``action_view_orderpoints``
``action_view_quants`` (396-400)                 ``action_view_quants`` (classmethod)
``action_view_inventory`` (402-431)              ``action_view_inventory`` (classmethod)
``action_apply_inventory`` (433-450)             ``action_apply_inventory``
``action_stock_quant_relocate`` (452-466)        ``action_stock_quant_relocate`` (cls)
``action_inventory_history`` (468-495)           ``action_inventory_history``
``action_set_inventory_quantity`` (497-516)      ``action_set_inventory_quantity`` (cls)
``action_apply_all`` (518-529)                   ``action_apply_all`` (classmethod)
``action_reset`` (531-543)                       ``action_reset`` (classmethod)
``action_clear_inventory_quantity`` (545-549)    ``action_clear_inventory_quantity`` (cls)
``action_set_inventory_quantity_zero`` (551-556) ``action_set_inventory_quantity_zero``
``_compute_display_name`` (558-580)              ``__str__`` + ``display_name``
``check_product_id`` (582-585)                   ``check_product_id``
``check_quantity`` (587-604)                     ``check_quantity`` (classmethod)
``check_location_id`` (606-610)                  ``check_location_id``
``check_lot_id`` (612-616)                       ``check_lot_id``
``_get_removal_strategy`` (618-628)              ``_get_removal_strategy`` (classmethod)
``_run_least_packages_removal_strategy_astar``   ídem, con sus 6 anidados
``PriorityQueue.__init__`` (660-661)             ídem (anidada)
``PriorityQueue.empty`` (662-663)                ídem (anidada)
``PriorityQueue.put`` (665-666)                  ídem (anidada)
``PriorityQueue.get`` (668-669)                  ídem (anidada)
``_get_removal_strategy_order`` (741-748)        ``_get_removal_strategy_order`` (cls)
``_get_gather_domain`` (750-769)                 ``_get_gather_domain`` (classmethod)
``_gather`` (771-791)                            ``_gather`` (classmethod)
``_get_available_quantity`` (793-832)            ``_get_available_quantity`` (classmethod)
``_get_reserve_quantity`` (834-914)              ``_get_reserve_quantity`` (classmethod)
``_get_quants_by_products_locations`` (916-933)  ``_get_quants_by_products_locations`` (cls)
``_onchange_location_or_product_id`` (935-957)   ``_onchange_location_or_product_id``
``_onchange_inventory_quantity`` (959-970)       ``_onchange_inventory_quantity``
``_onchange_serial_number`` (972-979)            ``_onchange_serial_number``
``_onchange_product_id`` (981-994)               ``_onchange_product_id``
``_apply_inventory`` (996-1036)                  ``_apply_inventory``
``_update_available_quantity`` (1038-1106)       ``_update_available_quantity`` (classmethod)
``_update_reserved_quantity`` (1108-1121)        ``_update_reserved_quantity`` (classmethod)
``_unlink_zero_quants`` (1123-1140)              ``_unlink_zero_quants`` (classmethod)
``_clean_reservations`` (1142-1176)              ``_clean_reservations`` (classmethod)
``_merge_quants`` (1178-1223)                    ``_merge_quants`` (classmethod)
``_quant_tasks`` (1225-1229)                     ``_quant_tasks`` (classmethod)
``_is_inventory_mode`` (1231-1237)               ``_is_inventory_mode`` (classmethod)
``_get_inventory_fields_create`` (1239-1243)     ``_get_inventory_fields_create`` (cls)
``_get_inventory_fields_write`` (1245-1251)      ``_get_inventory_fields_write`` (cls)
``_get_inventory_move_values`` (1253-1292)       ``_get_inventory_move_values``
``_set_view_context`` (1294-1306)                ``_set_view_context`` (classmethod)
``_get_quants_action`` (1308-1347)               ``_get_quants_action`` (classmethod)
``_get_gs1_barcode`` (1349-1388)                 ``_get_gs1_barcode``
``get_aggregate_barcodes`` (1390-1453)           ``get_aggregate_barcodes`` (classmethod)
``_check_serial_number`` (1455-1525)             ``_check_serial_number`` (classmethod)
``move_quants`` (1527-1560)                      ``move_quants``
``_should_bypass_product`` (1562-1563)           ``_should_bypass_product`` (classmethod)
===============================================  ======================================

Divergencias declaradas
=========================

Ninguna es una omisión: cada una nombra el mecanismo que este árbol resuelve
de otra forma, y por qué.

D-1 · ``compute`` no almacenado → ``property``
------------------------------------------------

La referencia declara ``available_quantity``, ``sn_duplicated``,
``last_count_date`` e ``is_outdated`` como ``compute`` sin ``store=True``: no
son columnas, se calculan al leer. Aquí son ``property`` — misma semántica y
mismo valor, sin motor de invalidación. Los ``related`` sin ``store`` reciben
el mismo trato (property que navega el FK), que es el idioma ya fijado en
``stock_package.py`` y ``product_expiry/models/stock_quant.py``.

Los que **sí** llevan ``store=True`` (``company_id``,
``inventory_diff_quantity``, ``inventory_date``, ``inventory_quantity_set``)
son columnas, y su recálculo vive en ``save()`` — igual que en
``stock_location.py``.

D-2 · ``_search_*`` → ``classmethod`` que devuelve un ``Q``
------------------------------------------------------------

La referencia declara ``search='_search_on_hand'`` sobre un campo no
almacenado: el ORM llama al método para traducir el filtro a dominio. Aquí no
hay ese cableado, así que ``_search_on_hand``, ``_search_is_outdated`` y
``_search`` son **classmethods invocables** que devuelven el filtro. Conservan
su nombre y su visibilidad; lo que falta es el registro automático, no el
símbolo.

D-3 · ``@api.onchange`` → método explícito
--------------------------------------------

Los cuatro ``_onchange_*`` son reacciones del cliente Odoo a un cambio de
campo antes de guardar. Aquí no hay esa capa, así que son métodos que devuelven
el ``dict`` de cambios/aviso y los llama quien edite el quant. Mismo criterio
que ``stock_picking.py``.

D-4 · acciones de ventana → descriptor por identificador externo
------------------------------------------------------------------

Los diez ``action_*`` de la referencia devuelven un ``ir.actions.act_window``
que su cliente interpreta. Aquí devuelven el **mismo descriptor** leído por
``_action_by_xmlid``, o construido a mano cuando la referencia lo construye a
mano. Las vistas que citan (``stock.view_stock_quant_tree_editable``…) aún no
existen: el descriptor las nombra igual y el ``view_id`` queda en ``None``
hasta que se siembren (tarea **#273**).

D-5 · ``_run_least_packages_removal_strategy_astar`` — A* completo, sin el SQL
--------------------------------------------------------------------------------

La referencia arma el conjunto candidato con ``query.groupby``/``having`` sobre
``Query``, y sobre él corre una búsqueda A* con ``heapq``. **El A* se porta
entero**; lo que cambia es cómo se obtiene el agregado por paquete: aquí es un
``values('package').annotate(Sum(...))``, que produce exactamente la misma
población. La heurística, la cola de prioridad y el criterio de corte son los
de la referencia, línea por línea.

D-6 · qué primitiva se usa para cada cosa — los espejos, no Django crudo
-------------------------------------------------------------------------

La referencia usa tres primitivas de consulta, y **las tres tienen espejo en
este árbol**. Se importan de ahí, no de ``django.db`` directamente:

===========================  ==============================  =====================
La referencia usa            Espejo del proyecto             Respaldo real
===========================  ==============================  =====================
``Domain`` / ``Domain.AND``  ``osv.expression`` (AND/OR/NOT) ``django.db.models.Q``
``SQL("…")``                 ``tools.sql.SQL``               ``RawSQL``
``Query``                    ``QuerySet`` (ver abajo)        ``QuerySet``
===========================  ==============================  =====================

``Query`` es la fila que NO usa su espejo, y es deliberado: el parámetro de
``_run_least_packages_removal_strategy_astar`` recibe el agregado de
``values(...).annotate(...)``, que **es** un ``QuerySet``. ``tools.query.Query``
existe desde ``api`` #127 como la clase propia de la fuente —el constructor
de SELECT crudo con ``make_alias``/``add_join``— y anotarlo aquí sería
nombrar un tipo que este método nunca recibe.

``Q`` **no es un puente por fuera del ORM**: es el tipo de llegada del espejo —
``src/orm/domains.py`` convierte un dominio de Odoo a ``Q`` con ``to_q``, y
``expression.AND([...])`` opera sobre ``Q``. Lo que sí sería drift es escribir
la conjunción a mano donde la referencia llama a ``Domain.AND``; por eso
``_get_gather_domain`` y ``_get_quants_by_products_locations`` la llaman.

**El único que no tiene espejo es el cursor.** ``_merge_quants`` y
``_unlink_zero_quants`` ejecutan SQL crudo con ``self.env.cr.execute``, y de
``env.cr`` no hay contraparte: aquí es ``django.db.connection.cursor()``.

Y ese SQL **se copia verbatim gracias a la migración de motor** (ADR-028,
tarea #93). No es una casualidad de estilo:

- ``round(quantity::numeric, %s)`` — el *cast* ``::numeric`` es sintaxis de
  PostgreSQL; bajo MariaDB había que reescribirlo.
- ``array_agg(id ORDER BY id)``, ``unnest(...)`` y el CTE con ``UPDATE`` dentro
  de ``WITH`` no existen en MariaDB en esa forma.

Es exactamente lo que ``T-014`` fija como procedimiento —«LATERAL y DISTINCT ON
se copian, no se traducen»— y la primera vez que este archivo lo puede cumplir.

D-6-bis · las dos closures que NO tienen contraparte
-----------------------------------------------------

Aparte de los 76, la referencia declara **dos funciones locales** dentro de
sendos métodos. Ninguna se porta, y las dos lo dicen aquí en vez de
desaparecer en silencio:

- ``_add_to_cache`` (dentro de ``create``, ``:257-262``) — puebla
  ``env.context['quants_cache']``, el índice que ``_gather`` consulta para no
  volver a la base. Ese caché vive en el **contexto del entorno**, que este
  stack no tiene; su equivalente aquí es
  ``_get_quants_by_products_locations``, que sí está portado y produce el
  mismo índice, sólo que el llamador lo sostiene en vez del entorno.
- ``_update_dict`` (dentro de ``_compute_last_count_date``, ``:153-156``) —
  queda máximo por clave en el agrupamiento de siete ejes. Aquí
  ``last_count_date`` resuelve con un solo ``aggregate(Max)``, porque el ORM
  admite el ``OR`` sobre origen y destino sin desdoblar el grupo; sin
  desdoblar el grupo no hay claves que fusionar, y la closure sobra.

Ambas son **detalle de implementación de un método portado**, no símbolos que
alguien pueda llamar: no aparecen en ningún ``_inherit`` ni en ninguna llamada
externa de la referencia (medido: ``grep -rn '_add_to_cache|_update_dict' -E``
sobre ``odoo19c: addons/`` → sólo sus dos definiciones y sus usos locales).

D-7 · ``available_qty`` / ``apply_move`` / ``set_on_hand`` — adaptadores del L0
--------------------------------------------------------------------------------

Tres helpers **propios**, no de la referencia, que ya existían en este archivo
y tienen 15 llamadores vivos (``stock.move``, ``stock.services``,
``product_expiry``, la suite). Se conservan y se declaran como lo que son:
adaptadores de firma sobre los métodos portados.

- ``available_qty(product, location)`` **no** es ``_get_available_quantity``:
  devuelve un tope alto para las ubicaciones que puentean la reserva. Allá esa
  decisión vive en ``stock.move._action_assign``, no en el quant. Aquí queda
  aquí, declarado, hasta que ``stock.move`` porte su ``_action_assign``
  completo — sucesor: tarea **#330** (``stock`` completo, este archivo es su
  primer lote).
- ``gather`` **se retiró**: era la despromoción de ``_gather`` con una firma
  recortada. Su único encadenador —``product_expiry``— ahora encadena sobre
  ``_get_removal_strategy_order``, que es **el símbolo que la referencia
  extiende**. Es un cierre de :ref:`h-api-581` y de la divergencia que el
  propio ``product_expiry`` declaraba.

D-8 · ``_set_inventory_quantity`` — ya portado; el gate es ciego a los ``inverse``
------------------------------------------------------------------------------------

``check_porte_completo.py`` lo reporta ausente, y **no lo está**
(:ref:`h-api-680`). ``_set_inventory_quantity`` (``odoo19c: :225-237``) es el
``inverse='_set_inventory_quantity'`` del campo
``inventory_quantity_auto_apply``; aquí es el **setter** de la property
homónima (:613-625), citado en su propio docstring. La absolución del gate
(``equivalencias_declaradas()``) sólo deriva claves ``_compute_<campo>`` a
partir de una property **getter**; declara explícitamente en su propio
docstring que es ciega a los ``_inverse_x``/``_search_x`` — «el lado seguro».
El cuerpo es el mismo: si la cantidad no cambió no hay ajuste; si cambió,
escribe ``inventory_quantity`` y aplica el inventario.
"""
import datetime
import heapq
from collections import defaultdict, namedtuple
from decimal import Decimal

import fields
import api
import models
from orm.environments import sudo
from orm.utils import browse
from django.apps import apps
from django.db import connection
from django.db.models import (
    Case, F, IntegerField, Q, QuerySet, Sum, Value, When,
)
from django.utils import timezone

from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from osv import expression
from tools.sql import SQL
from tools.translate import _

#: ≙ ``PackageLevel`` — el nodo del A* de ``_run_least_packages_removal_strategy_astar``
#: (``odoo19c: :630-739``): un paquete con su cantidad disponible.
PackageQty = namedtuple('PackageQty', ['package_id', 'available_qty'])

#: Tope que ``available_qty`` devuelve para una ubicación que puentea la
#: reserva — ver D-7 del docstring. No es un valor de la referencia.
UNBOUNDED_QTY = Decimal('999999999.00')


class StockQuant(models.DefaultGetMixin, TimeStampedModel):
    """``stock.quant`` — existencia de un producto en una ubicación."""

    # Atributos de clase de modelo — los cuatro que la referencia declara
    # (``odoo19c: addons/stock/models/stock_quant.py:20-23``), verbatim.
    _name = 'stock.quant'
    _description = 'Quants'
    _rec_name = 'product_id'
    _rec_names_search = ['location_id', 'lot_id', 'package_id', 'owner_id']

    product           = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE, related_name='quants',
        help_text='Producto (Odoo product_id).',
    )
    company           = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='stock_quants',
        help_text='Empresa (Odoo company_id, related a location_id.company_id '
                  'con store=True; se recalcula en save()).',
    )
    location          = fields.Many2one(
        'stock.StockLocation', on_delete=models.CASCADE, related_name='quants',
        help_text='Ubicación (Odoo location_id).',
    )
    lot               = fields.Many2one(
        'stock.StockLot', on_delete=models.CASCADE, related_name='quants',
        null=True, blank=True,
        help_text='Lote / número de serie (Odoo lot_id). NULL = sin lote.',
    )
    package           = fields.Many2one(
        'stock.StockPackage', on_delete=models.RESTRICT, related_name='quant_ids',
        null=True, blank=True,
        help_text='Paquete que contiene esta existencia (Odoo package_id).',
    )
    owner             = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_quants',
        help_text='Propietario de la existencia (Odoo owner_id).',
    )
    quantity          = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad a la mano (Odoo stock.quant.quantity).',
    )
    reserved_quantity = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad reservada (Odoo reserved_quantity).',
    )
    in_date           = fields.Datetime(
        default=timezone.now,
        help_text='Fecha de entrada al quant (Odoo stock.quant.in_date; '
                  'clave de orden de la estrategia FIFO).',
    )

    # -- campos de ajuste de inventario (≙ el bloque "Inventory Fields", :95-117) --

    inventory_quantity      = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad contada (Odoo inventory_quantity).',
    )
    inventory_diff_quantity = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Diferencia contada − teórica (Odoo inventory_diff_quantity, '
                  'almacenado; lo recalcula compute_inventory_diff_quantity).',
    )
    inventory_date          = fields.Date(
        null=True, blank=True,
        help_text='Próximo conteo planeado (Odoo inventory_date, almacenado y '
                  'editable: readonly=False en la referencia).',
    )
    inventory_quantity_set  = fields.Boolean(
        default=False,
        help_text='Marca que alguien ya fijó la cantidad contada (Odoo '
                  'inventory_quantity_set, almacenado y editable).',
    )
    user                    = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_quants',
        help_text='Usuario asignado al conteo (Odoo user_id).',
    )

    class Meta:
        db_table = 'stock_quant'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'location', 'lot'],
                name='unique_quant_product_location_lot',
            ),
        ]
        # ≙ el orden que _get_removal_strategy_order devuelve para 'fifo', que
        # es el default de _get_removal_strategy (``:628``).
        ordering = ['in_date', 'id']
        verbose_name = 'Existencia de inventario'
        verbose_name_plural = 'Existencias de inventario'

    # ------------------------------------------------------------------ #
    # Dominios de los campos (≙ :25-42)                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def _domain_location_id(cls, user=None):
        """≙ ``_domain_location_id`` (``odoo19c: :25-28``).

        Devuelve el filtro que acota las ubicaciones seleccionables en modo
        inventario: sólo internas y de tránsito.
        """
        return Q(usage__in=['internal', 'transit'])

    @classmethod
    def _domain_lot_id(cls, product=None):
        """≙ ``_domain_lot_id`` (``odoo19c: :30-36``).

        La referencia devuelve una cadena de dominio evaluada por el cliente,
        con tres ramas según el modelo activo. Aquí sólo sobrevive la rama que
        no depende del contexto del cliente: los lotes del producto dado.
        """
        if product is None:
            return Q()
        return Q(product=product)

    @classmethod
    def _domain_product_id(cls, product_tmpl_ids=None):
        """≙ ``_domain_product_id`` (``odoo19c: :38-42``).

        Sólo productos almacenables, opcionalmente acotados a unas plantillas.
        ``is_storable`` aún no está portado (``addons/stock/models/product.py``
        lo declara como alcance de la tarea **#330**); mientras tanto el filtro
        se queda en las plantillas, que es la mitad que sí se puede expresar.
        """
        if product_tmpl_ids:
            return Q(product_tmpl__in=product_tmpl_ids)
        return Q()

    # ------------------------------------------------------------------ #
    # Los `related` de la referencia — properties (D-1)                    #
    # ------------------------------------------------------------------ #

    @property
    def product_tmpl(self):
        """≙ ``product_tmpl_id`` (related a ``product_id``, ``:49-51``)."""
        return self.product.product_tmpl if self.product is not None else None

    @property
    def product_uom(self):
        """≙ ``product_uom_id`` (related a ``product_id.uom_id``, ``:52-54``)."""
        return self.product.uom if self.product is not None else None

    @property
    def is_favorite(self):
        """≙ ``is_favorite`` (related a ``product_tmpl_id``, ``:55``)."""
        plantilla = self.product_tmpl
        return bool(plantilla is not None and plantilla.is_favorite)

    @property
    def warehouse(self):
        """≙ ``warehouse_id`` (related a ``location_id``, ``:61``)."""
        return self.location.warehouse if self.location is not None else None

    @property
    def storage_category(self):
        """≙ ``storage_category_id`` (related a ``location_id``, ``:62``)."""
        return self.location.storage_category if self.location is not None else None

    @property
    def cyclic_inventory_frequency(self):
        """≙ ``cyclic_inventory_frequency`` (related a ``location_id``, ``:63``)."""
        if self.location is None:
            return 0
        return self.location.cyclic_inventory_frequency

    @property
    def lot_properties(self):
        """≙ ``lot_properties`` (related a ``lot_id``, ``:68``).

        ``fields.Properties`` no tiene contraparte en este ORM: la referencia
        guarda un diccionario cuya definición vive en el producto. Aquí se
        expone lo que el lote tenga bajo ese nombre, o ``{}``.
        """
        return getattr(self.lot, 'lot_properties', None) or {}

    @property
    def tracking(self):
        """≙ ``tracking`` (related a ``product_id``, ``:92``)."""
        return getattr(self.product, 'tracking', 'none')

    @property
    def product_categ(self):
        """≙ ``product_categ_id`` (related a ``product_tmpl_id.categ_id``, ``:94``)."""
        plantilla = self.product_tmpl
        return plantilla.categ if plantilla is not None else None

    # ------------------------------------------------------------------ #
    # Los `compute` no almacenados — properties (D-1)                      #
    # ------------------------------------------------------------------ #

    @property
    def available_quantity(self):
        """≙ ``available_quantity`` / ``_compute_available_quantity`` (``:87-90``, ``:119-122``).

        La resta cruda, sin acotar en cero y sin trato de ubicación — que es
        exactamente lo que hace la referencia. El acotamiento vive en
        ``_get_available_quantity``, y el trato de ubicación en ``available_qty``
        (D-7).
        """
        return self.quantity - self.reserved_quantity

    @property
    def sn_duplicated(self):
        """≙ ``sn_duplicated`` / ``_compute_sn_duplicated`` (``:69``, ``:216-223``).

        ``True`` si el mismo número de serie está en otro quant con existencia
        positiva en una ubicación interna o de tránsito.
        """
        if self.lot is None or self.tracking != 'serial':
            return False
        return (
            type(self).objects
            .filter(lot=self.lot, quantity__gt=0,
                    location__usage__in=['internal', 'transit'])
            .exclude(pk=self.pk)
            .exists()
        )

    @property
    def last_count_date(self):
        """≙ ``last_count_date`` / ``_compute_last_count_date`` (``:112``, ``:131-177``).

        La fecha del último movimiento de inventario hecho que tocó esta
        combinación. La referencia agrupa por siete ejes y cruza origen y
        destino; aquí es la misma consulta expresada en una sola pasada, porque
        el ORM permite el ``OR`` sobre los dos extremos sin desdoblar el grupo.
        """
        move_line = apps.get_model('stock', 'StockMoveLine')
        if move_line is None or self.product is None:
            return None
        filtro = (
            Q(state='done') & Q(is_inventory=True) & Q(product=self.product)
            & (Q(lot=self.lot) | Q(lot__isnull=True))
            & (Q(owner=self.owner) | Q(owner__isnull=True))
            & (Q(location=self.location) | Q(location_dest=self.location))
        )
        agregado = move_line.objects.filter(filtro).aggregate(ultima=models.Max('date'))
        return agregado['ultima']

    @property
    def is_outdated(self):
        """≙ ``is_outdated`` / ``_compute_is_outdated`` (``:114``, ``:197-202``).

        La cantidad se movió desde el último conteo: lo contado menos la
        diferencia registrada ya no coincide con lo que hay.
        """
        if self.product is None or not self.inventory_quantity_set:
            return False
        uom = self.product_uom
        izquierda = self.inventory_quantity - self.inventory_diff_quantity
        if uom is None:
            return izquierda != self.quantity
        return bool(uom.compare(float(izquierda), float(self.quantity)))

    @property
    def on_hand(self):
        """≙ ``on_hand`` (``:93``, ``store=False``, sólo filtro).

        En la referencia es un campo de búsqueda puro: no se lee, se filtra.
        Aquí se expone además como lectura —existencia positiva— porque un
        campo que no se puede leer es más confuso que útil, y el filtro sigue
        siendo ``_search_on_hand``.
        """
        return self.quantity > 0

    @property
    def inventory_quantity_auto_apply(self):
        """≙ ``inventory_quantity_auto_apply`` /
        ``_compute_inventory_quantity_auto_apply`` (``:100-104``, ``:211-215``).

        Lee la cantidad a la mano; al **escribirla** dispara el ajuste, que es
        lo que hace el ``inverse='_set_inventory_quantity'`` de la referencia.
        """
        return self.quantity

    @inventory_quantity_auto_apply.setter
    def inventory_quantity_auto_apply(self, value):
        """≙ ``_set_inventory_quantity`` (``odoo19c: :225-237``).

        Docstring de la referencia: *"Inverse method to create stock move when
        `inventory_quantity` is set"*. Si el valor no cambia, no hay ajuste.
        """
        if not self._is_inventory_mode():
            return
        if self.quantity == Decimal(value):
            return
        self.inventory_quantity = Decimal(value)
        self.action_apply_inventory()

    # ------------------------------------------------------------------ #
    # Los `compute` almacenados — se recalculan en save() (D-1)             #
    # ------------------------------------------------------------------ #

    def compute_company(self):
        """≙ ``company_id`` (related a ``location_id.company_id``, ``store=True``)."""
        self.company = self.location.company if self.location is not None else None

    def _compute_inventory_date(self):
        """≙ ``_compute_inventory_date`` (``odoo19c: :124-129``).

        Sólo para quants sin fecha planeada en ubicación interna o de tránsito;
        la fecha la produce la ubicación.
        """
        if self.inventory_date is not None:
            return
        if self.location is None or self.location.usage not in ('internal', 'transit'):
            return
        self.inventory_date = self.location.get_next_inventory_date()

    def _compute_inventory_diff_quantity(self):
        """≙ ``_compute_inventory_diff_quantity`` (``odoo19c: :185-192``)."""
        if self.inventory_quantity_set:
            self.inventory_diff_quantity = self.inventory_quantity - self.quantity
        else:
            self.inventory_diff_quantity = Decimal('0.00')

    def _compute_inventory_quantity_set(self):
        """≙ ``_compute_inventory_quantity_set`` (``odoo19c: :194-196``).

        La referencia lo pone en ``True`` en cuanto ``inventory_quantity``
        cambia; el campo es ``readonly=False``, así que un ``False`` explícito
        sobrevive hasta el siguiente cambio.
        """
        self.inventory_quantity_set = True

    def save(self, *args, **kwargs):
        """Recalcula los cuatro campos almacenados antes de escribir."""
        self.compute_company()
        self._compute_inventory_date()
        self._compute_inventory_diff_quantity()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Los `search` de campos no almacenados (D-2)                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def _search(cls, domain=None, **kwargs):
        """≙ ``_search`` (``odoo19c: :179-184``).

        La referencia reescribe las condiciones sobre ``lot_properties.*`` para
        que viajen al lote. Aquí el equivalente es traducir el prefijo del
        nombre de campo al recorrido del FK.
        """
        filtro = domain if domain is not None else Q()
        traducidos = {
            clave.replace('lot_properties.', 'lot__lot_properties__', 1): valor
            for clave, valor in kwargs.items()
        }
        return cls.objects.filter(filtro, **traducidos)

    @classmethod
    def _search_on_hand(cls, operator='in', value=True):
        """≙ ``_search_on_hand`` (``odoo19c: :239-243``).

        La referencia delega en ``product.product._get_domain_locations()``,
        que acota a las ubicaciones visibles del usuario. Aquí el filtro
        equivalente es la existencia positiva en ubicación interna o de
        tránsito, que es lo que ese dominio produce.
        """
        if operator != 'in':
            return NotImplemented
        return Q(quantity__gt=0, location__usage__in=['internal', 'transit'])

    @classmethod
    def _search_is_outdated(cls, operator='in', value=True):
        """≙ ``_search_is_outdated`` (``odoo19c: :204-210``).

        La referencia filtra en Python sobre los quants con conteo fijado,
        porque el predicado depende del redondeo de la unidad. Aquí igual:
        se devuelve el filtro por ``pk``, no una expresión SQL.
        """
        if operator != 'in':
            return NotImplemented
        candidatos = cls.objects.filter(inventory_quantity_set=True)
        desfasados = [quant.pk for quant in candidatos if quant.is_outdated]
        return Q(pk__in=desfasados)

    # ------------------------------------------------------------------ #
    # Ciclo de vida del registro                                          #
    # ------------------------------------------------------------------ #

    def copy(self, default=None):
        """≙ ``copy`` (``odoo19c: :245-246``) — duplicar un quant está prohibido."""
        raise UserError(_('No se puede duplicar una existencia de inventario.'))

    @classmethod
    def name_create(cls, name):
        """≙ ``name_create`` (``odoo19c: :248-250``) — crear por nombre no aplica."""
        return False

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :252-312``).

        Docstring de la referencia: *"Override to handle the 'inventory mode'
        and create a quant as superuser the conditions are met"*.

        En modo inventario la creación se restringe a los campos permitidos y,
        si ya existe un quant con las mismas características, **se escribe
        sobre él** en vez de crear uno nuevo. Es lo que evita que un conteo
        duplique la existencia. El bucle por ``vals`` y la unión de lo creado
        con lo reescrito (``quants |= ...``) son los de la referencia.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        modo_inventario = cls._is_inventory_mode()
        permitidos = cls._get_inventory_fields_create()
        quants = []
        for vals in vals_list:
            trae_conteo = any(
                campo in vals
                for campo in ('inventory_quantity', 'inventory_quantity_auto_apply')
            )
            if not (modo_inventario and trae_conteo):
                if 'inventory_quantity' not in vals:
                    vals.setdefault('inventory_quantity_set', False)
                quant, = super().create([vals])
                quants.append(quant)
                continue

            invasores = [c for c in vals if not c.startswith('x_') and c not in permitidos]
            if invasores:
                raise UserError(
                    _('La creación de existencias está restringida; no se puede '
                      'realizar esta operación.'))

            auto_aplicar = 'inventory_quantity_auto_apply' in vals
            contado = (vals.pop('inventory_quantity_auto_apply', None)
                       or vals.pop('inventory_quantity', None)
                       or Decimal('0.00'))

            quant = cls._gather(
                vals.get('product'), vals.get('location'), lot=vals.get('lot'),
                package=vals.get('package'), owner=vals.get('owner'), strict=True,
            ).first()
            if quant is None:
                with sudo():  # ``self.sudo().create(vals)`` (``odoo19c: :295``)
                    quant, = super().create([vals])
            if auto_aplicar:
                quant.inventory_quantity_auto_apply = contado
            else:
                quant.inventory_quantity = Decimal(contado)
                quant.user = vals.get('user')
                quant.inventory_date = timezone.now().date()
                quant.save(update_fields=['inventory_quantity', 'user',
                                          'inventory_date', 'inventory_diff_quantity',
                                          'updated_at'])
            quants.append(quant)
        return browse(cls, [quant.pk for quant in quants])

    @classmethod
    def _load_records_create(cls, values):
        """≙ ``_load_records_create`` (``odoo19c: :315-322``).

        Docstring de la referencia: *"Add default location if import file did
        not fill it"*. La ubicación por defecto es el almacén de la empresa.
        """
        warehouse_model = apps.get_model('stock', 'StockWarehouse')
        almacen = warehouse_model.objects.first() if warehouse_model else None
        for value in values:
            if 'location' not in value and almacen is not None:
                value['location'] = almacen.lot_stock
        return list(cls.create(values))

    @classmethod
    def _load_records_write(cls, values):
        """≙ ``_load_records_write`` (``odoo19c: :324-326``).

        Docstring de la referencia: *"Only allowed fields should be
        modified"*. La restricción la aplica ``write``; aquí sólo se enruta.
        """
        resultados = []
        for quant, vals in values:
            resultados.append(quant.write(**vals))
        return resultados

    @classmethod
    def _read_group_select(cls, aggregate_spec, queryset=None,
                           inventory_report_mode=False):
        """≙ ``_read_group_select`` (``odoo19c: :328-338``).

        Traduce tres agregados que no tienen columna propia:
        ``available_quantity:sum`` es la resta de dos sumas, y
        ``inventory_quantity_auto_apply:sum`` es la suma de ``quantity``.
        """
        if aggregate_spec == 'inventory_quantity:sum' and inventory_report_mode:
            # ≙ ``return SQL("NULL")`` (``odoo19c: :330``).
            return SQL('NULL', output_field=models.DecimalField())
        if aggregate_spec == 'available_quantity:sum':
            # ≙ ``SQL("%s - %s", sql_quantity, sql_reserved_quantity)`` (``:335``).
            return SQL('SUM(quantity) - SUM(reserved_quantity)',
                       output_field=models.DecimalField())
        if aggregate_spec == 'inventory_quantity_auto_apply:sum':
            return cls._read_group_select('quantity:sum', queryset)
        campo, _sep, funcion = aggregate_spec.partition(':')
        if funcion == 'sum':
            return Sum(campo)
        return None

    @classmethod
    def get_import_templates(cls):
        """≙ ``get_import_templates`` (``odoo19c: :340-345``)."""
        return [{
            'label': _('Plantilla de importación para ajustes de inventario'),
            'template': '/stock/static/xlsx/stock_quant.xlsx',
        }]

    @classmethod
    def _get_forbidden_fields_write(cls):
        """≙ ``_get_forbidden_fields_write`` (``odoo19c: :347-349``).

        Docstring de la referencia: *"Returns a list of fields user can't edit
        when he want to edit a quant in `inventory_mode`"*.
        """
        return ['product', 'location', 'lot', 'package', 'owner']

    def write(self, **vals):
        """≙ ``write`` (``odoo19c: :351-361``).

        En modo inventario las características del quant son inmutables: quien
        cuenta ajusta la cantidad, no mueve la existencia de sitio.
        """
        prohibidos = self._get_forbidden_fields_write()
        if self._is_inventory_mode() and any(c in vals for c in prohibidos):
            if self.location is not None and self.location.usage == 'inventory':
                # La referencia no hace nada cuando se intenta editar a mano
                # una pérdida de inventario.
                return None
            raise UserError(
                _('La edición de existencias está restringida; no se puede '
                  'realizar esta operación.'))
        for clave, valor in vals.items():
            setattr(self, clave, valor)
        self.save()
        return self

    def _unlink_except_wrong_permission(self):
        """≙ ``_unlink_except_wrong_permission`` (``odoo19c: :363-369``).

        Los quants se borran solos cuando toca. El borrado manual pasa por un
        ajuste a cero, no por un ``DELETE``.
        """
        self.inventory_quantity = Decimal('0.00')
        self._apply_inventory()

    # ------------------------------------------------------------------ #
    # Acciones de ventana (D-4)                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _action_by_xmlid(xmlid):
        """Lee el descriptor de una acción de ventana por identificador externo.

        Mismo ayudante que ``stock_picking.py``; se repite aquí porque es el
        puente al registro de acciones y no un símbolo de la referencia.
        """
        ir_model_data = apps.get_model('base', 'IrModelData')
        modulo, _sep, nombre = xmlid.partition('.')
        registro = ir_model_data.objects.filter(module=modulo, name=nombre).first()
        if registro is None:
            return None
        act_window = apps.get_model('base', 'IrActionsActWindow')
        accion = act_window.objects.filter(pk=registro.res_id).first()
        if accion is None:
            return None
        return {
            'type': 'ir.actions.act_window',
            'name': accion.name,
            'res_model': accion.res_model,
            'view_mode': accion.view_mode,
            'domain': accion.domain or [],
            'context': {},
        }

    def action_view_stock_moves(self):
        """≙ ``action_view_stock_moves`` (``odoo19c: :371-388``)."""
        accion = self._action_by_xmlid('stock.stock_move_line_action') or {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move.line',
            'view_mode': 'list,form',
        }
        dominio = (Q(location=self.location) | Q(location_dest=self.location))
        if self.lot is not None:
            dominio &= Q(lot=self.lot)
        if self.package is not None:
            dominio &= (Q(package=self.package) | Q(result_package=self.package))
        accion['domain'] = dominio
        contexto = dict(accion.get('context') or {})
        contexto['search_default_product_id'] = self.product_id
        accion['context'] = contexto
        return accion

    def action_view_orderpoints(self):
        """≙ ``action_view_orderpoints`` (``odoo19c: :390-394``)."""
        accion = self._action_by_xmlid('stock.action_orderpoint') or {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.warehouse.orderpoint',
            'view_mode': 'list,form',
        }
        accion['domain'] = Q(product=self.product)
        return accion

    @classmethod
    def action_view_quants(cls):
        """≙ ``action_view_quants`` (``odoo19c: :396-400``)."""
        contexto = cls._set_view_context({'search_default_internal_loc': 1})
        accion = cls._get_quants_action(extend=True)
        accion['context'] = {**accion.get('context', {}), **contexto}
        return accion

    @classmethod
    def action_view_inventory(cls):
        """≙ ``action_view_inventory`` (``odoo19c: :402-431``).

        Docstring de la referencia: *"Similar to _get_quants_action except
        specific for inventory adjustments (i.e. inventory counts)"*.
        """
        contexto = cls._set_view_context({'no_at_date': True})
        cls._quant_tasks()
        return {
            'name': _('Inventario físico'),
            'view_mode': 'list',
            'res_model': 'stock.quant',
            'type': 'ir.actions.act_window',
            'context': contexto,
            'domain': Q(location__usage__in=['internal', 'transit']),
            'help': _('Tu inventario está vacío. Define la cantidad de un '
                      'producto o impórtala desde una hoja de cálculo.'),
        }

    def action_apply_inventory(self, date=None):
        """≙ ``action_apply_inventory`` (``odoo19c: :433-450``).

        Si el quant está desfasado —se movió desde el conteo— la referencia
        abre el asistente de conflicto en vez de aplicar. Aquí se devuelve ese
        mismo descriptor; el asistente ``stock.inventory.conflict`` aún no está
        portado (alcance de la tarea **#330**).
        """
        if self.is_outdated:
            return {
                'name': _('Conflicto en el ajuste de inventario'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'stock.inventory.conflict',
                'target': 'new',
                'context': {'default_quant_ids': [self.pk],
                            'default_quant_to_fix_ids': [self.pk]},
            }
        self._apply_inventory(date)
        self.inventory_quantity_set = False
        self.save(update_fields=['inventory_quantity_set', 'updated_at'])
        return None

    @classmethod
    def action_stock_quant_relocate(cls, quants, lot=None, single_product=False):
        """≙ ``action_stock_quant_relocate`` (``odoo19c: :452-466``).

        Sólo se reubica cantidad positiva de una sola empresa; la referencia lo
        exige porque el asistente crea un movimiento por empresa.
        """
        empresas = {q.company_id for q in quants}
        if len(empresas) > 1 or None in empresas or any(q.quantity <= 0 for q in quants):
            raise UserError(
                _('Sólo se pueden mover cantidades positivas almacenadas en '
                  'ubicaciones de una única empresa por reubicación.'))
        return {
            'res_model': 'stock.quant.relocate',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {
                'default_quant_ids': [q.pk for q in quants],
                'default_lot_id': lot.pk if lot is not None else False,
                'single_product': single_product,
            },
        }

    def action_inventory_history(self):
        """≙ ``action_inventory_history`` (``odoo19c: :468-495``)."""
        contexto = {
            'search_default_inventory': 1,
            'search_default_done': 1,
            'search_default_product_id': self.product_id,
        }
        if self.lot is not None:
            contexto['search_default_lot_id'] = self.lot_id
        if self.package is not None:
            contexto['search_default_package_id'] = self.package_id
            contexto['search_default_result_package_id'] = self.package_id
        if self.owner is not None:
            contexto['search_default_owner_id'] = self.owner_id
        return {
            'name': _('Historial'),
            'view_mode': 'list,form',
            'res_model': 'stock.move.line',
            'type': 'ir.actions.act_window',
            'context': contexto,
            'domain': (Q(company=self.company)
                       & (Q(location=self.location) | Q(location_dest=self.location))),
        }

    @classmethod
    def action_set_inventory_quantity(cls, quants, user=None, from_request_count=False):
        """≙ ``action_set_inventory_quantity`` (``odoo19c: :497-516``).

        Si alguno ya tiene conteo fijado, la referencia pide confirmación antes
        de pisarlo; aquí se devuelve ese descriptor de aviso.
        """
        ya_fijados = [q for q in quants if q.inventory_quantity_set]
        if ya_fijados:
            return {
                'name': _('Cantidades ya fijadas'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'stock.inventory.warning',
                'target': 'new',
                'context': {'default_quant_ids': [q.pk for q in quants]},
            }
        for quant in quants:
            if not from_request_count:
                quant.inventory_quantity = quant.quantity
            quant.user = user
            quant.inventory_quantity_set = True
            quant.save(update_fields=['inventory_quantity', 'user',
                                      'inventory_quantity_set',
                                      'inventory_diff_quantity', 'updated_at'])
        return None

    @classmethod
    def action_apply_all(cls, active_domain=None):
        """≙ ``action_apply_all`` (``odoo19c: :518-529``)."""
        quants = cls.objects.filter(active_domain or Q())
        return {
            'name': _('Ajuste de inventario'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.inventory.adjustment.name',
            'target': 'new',
            'context': {'default_quant_ids': list(quants.values_list('pk', flat=True))},
        }

    @classmethod
    def action_reset(cls, quants):
        """≙ ``action_reset`` (``odoo19c: :531-543``)."""
        return {
            'name': _('Cantidades por restablecer'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock.inventory.warning',
            'target': 'new',
            'context': {'default_quant_ids': [q.pk for q in quants]},
        }

    @classmethod
    def action_clear_inventory_quantity(cls, quants):
        """≙ ``action_clear_inventory_quantity`` (``odoo19c: :545-549``)."""
        for quant in quants:
            quant.inventory_quantity = Decimal('0.00')
            quant.inventory_diff_quantity = Decimal('0.00')
            quant.inventory_quantity_set = False
            quant.user = None
            models.Model.save(
                quant, update_fields=['inventory_quantity',
                                      'inventory_diff_quantity',
                                      'inventory_quantity_set', 'user',
                                      'updated_at'])

    def action_set_inventory_quantity_zero(self, user=None, inventory_report_mode=False):
        """≙ ``action_set_inventory_quantity_zero`` (``odoo19c: :551-556``)."""
        self.inventory_quantity = Decimal('0.00')
        if inventory_report_mode:
            self._apply_inventory()
        else:
            self.user = user
            self.save(update_fields=['inventory_quantity', 'user',
                                     'inventory_diff_quantity', 'updated_at'])

    # ------------------------------------------------------------------ #
    # Nombre para mostrar y restricciones                                 #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        return self.display_name

    def _compute_display_name(self) -> str:
        """≙ ``_compute_display_name`` (``odoo19c: :558-580``).

        Docstring de la referencia: *"name that will be displayed in the
        detailed operation"*. Ubicación, lote, paquete y propietario, unidos
        por guion — el orden es el de la referencia.
        """
        partes = [str(self.location)]
        if self.lot is not None:
            partes.append(self.lot.name)
        if self.package is not None:
            partes.append(str(self.package))
        if self.owner is not None:
            partes.append(str(self.owner))
        return ' - '.join(partes)

    def check_product_id(self):
        """≙ ``check_product_id`` (``odoo19c: :582-585``, ``@api.constrains``).

        Divergencia declarada: la referencia exige ``product_id.is_storable``.
        Ese campo aún no está portado (``addons/stock/models/product.py`` lo
        declara como alcance de la tarea **#330**), así que el check verifica
        lo que sí se puede verificar —que haya producto— y se completará con
        él en el mismo lote. No es una omisión silenciosa.
        """
        if self.product is None:
            raise ValidationError(
                _('No se pueden crear existencias sin producto.'))
        almacenable = getattr(self.product, 'is_storable', None)
        if almacenable is False:
            raise ValidationError(
                _('No se pueden crear existencias de consumibles ni servicios.'))

    @classmethod
    def check_quantity(cls, quants):
        """≙ ``check_quantity`` (``odoo19c: :587-604``).

        Un número de serie no puede estar en dos sitios a la vez: la suma de
        existencias del mismo lote serial debe ser 1 como máximo.
        """
        seriales = [
            q for q in quants
            if q.tracking == 'serial'
            and q.lot is not None
            and (q.location is None or q.location.usage != 'inventory')
        ]
        if not seriales:
            return
        grupos = (
            cls.objects
            .filter(product__in=[q.product_id for q in seriales],
                    lot__in=[q.lot_id for q in seriales])
            .values('product', 'location', 'lot')
            .annotate(total=Sum('quantity'))
        )
        for grupo in grupos:
            if abs(grupo['total'] or Decimal('0.00')) > Decimal('1'):
                lote = apps.get_model('stock', 'StockLot').objects.get(pk=grupo['lot'])
                raise ValidationError(
                    _('El número de serie ya está asignado: '
                      'producto %(product)s, número de serie %(serial_number)s')
                    % {'product': lote.product, 'serial_number': lote.name})

    def check_location_id(self):
        """≙ ``check_location_id`` (``odoo19c: :606-610``, ``@api.constrains``)."""
        if self.location is not None and self.location.usage == 'view':
            raise ValidationError(
                _('No se pueden tomar ni entregar productos en una ubicación '
                  'de tipo «vista» (%s).') % self.location.name)

    def check_lot_id(self):
        """≙ ``check_lot_id`` (``odoo19c: :612-616``, ``@api.constrains``)."""
        if self.lot is not None and self.lot.product is not None \
                and self.lot.product != self.product:
            raise ValidationError(
                _('El lote / número de serie (%s) está ligado a otro producto.')
                % self.lot.name)

    # ------------------------------------------------------------------ #
    # Estrategia de retiro y recolección                                  #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_removal_strategy(cls, product, location):
        """≙ ``_get_removal_strategy`` (``odoo19c: :618-628``).

        La categoría del producto manda; si no declara estrategia, se sube por
        la cadena de ubicaciones hasta encontrar una. El default es ``fifo``.
        """
        categoria = getattr(product, 'categ', None)
        estrategia = getattr(categoria, 'removal_strategy', None)
        if estrategia is not None:
            return estrategia.method
        actual = location
        while actual is not None:
            propia = getattr(actual, 'removal_strategy', None)
            if propia is not None:
                return propia.method
            actual = actual.location
        return 'fifo'

    @classmethod
    def _run_least_packages_removal_strategy_astar(cls, queryset: QuerySet, qty):
        """≙ ``_run_least_packages_removal_strategy_astar`` (``odoo19c: :630-739``).

        Elige el **menor número de paquetes** que cubre ``qty``, con una
        búsqueda A* sobre el conjunto de paquetes disponibles.

        Lo único que cambia respecto de la referencia es de dónde sale el
        agregado por paquete: allá de ``query.groupby``/``having`` sobre
        ``Query``, aquí de ``values('package').annotate(Sum(...))``. Misma
        población (D-5). **El algoritmo se porta entero**, incluidos los
        cuatro detalles que lo hacen correcto y que es fácil perder al
        resumirlo:

        1. los quants **sin paquete** se explotan en unidades sueltas de 1 —
           un artículo suelto es su propio «paquete» de tamaño 1 (``:645-647``);
        2. las ramas con la **misma cantidad** se saltan (``last_count``), o el
           árbol se multiplica sin explorar nada nuevo (``:711-714``);
        3. hay dos casos de fallo con memoria del **mejor intento**
           (``best_leaf``): pasarse (``:723-727``) y no alcanzar (``:729-733``);
        4. el ``MemoryError`` se atrapa y se devuelve el dominio sin acotar
           (``:736-738``) — quedarse sin memoria no debe romper la reserva.
        """
        por_paquete = (
            queryset
            .values('package')
            .annotate(disponible=Sum(F('quantity') - F('reserved_quantity')))
            .filter(disponible__gt=0)
            .order_by('-disponible')
        )
        qty_by_package = [
            PackageQty(fila['package'], fila['disponible']) for fila in por_paquete
        ]

        # ≙ ``:641-653``: los sueltos se explotan en unidades de 1 y van al
        # final; un paquete con cantidad cero se descarta.
        pkg_found = False
        new_qty_by_package = []
        none_elements = []
        for elem in qty_by_package:
            if elem.package_id is None:
                none_elements.extend(
                    PackageQty(None, Decimal('1')) for _ in range(int(elem.available_qty)))
            elif elem.available_qty != 0:
                new_qty_by_package.append(elem)
                pkg_found = True
        new_qty_by_package.extend(none_elements)
        qty_by_package = new_qty_by_package

        if not pkg_found:
            return queryset
        size = len(qty_by_package)

        class PriorityQueue:
            """≙ ``PriorityQueue`` (``odoo19c: :659-669``) — la frontera del A*."""

            def __init__(self):
                self.elements = []
                self._contador = 0

            def empty(self) -> bool:
                """≙ ``empty`` (``:662-663``)."""
                return not self.elements

            def put(self, item, priority):
                """≙ ``put`` (``:665-666``).

                Divergencia mínima: la referencia empuja ``(priority, item)`` y
                se apoya en que su ``Node`` sea comparable. Aquí se intercala un
                contador monótono para que ``heapq`` nunca tenga que comparar
                dos ``Node`` con la misma prioridad — el desempate es de llegada,
                igual que allá en la práctica.
                """
                self._contador += 1
                heapq.heappush(self.elements, (priority, self._contador, item))

            def get(self):
                """≙ ``get`` (``:668-669``)."""
                return heapq.heappop(self.elements)[2]

        def heuristic(node):
            """≙ ``heuristic`` (``odoo19c: :671-674``).

            Paquetes ya tomados más lo que faltaría suponiendo que el resto
            fueran del tamaño del siguiente candidato. Es admisible porque la
            lista viene ordenada de mayor a menor.
            """
            if node.next_index < size:
                siguiente = qty_by_package[node.next_index].available_qty
                return (len(node.taken_packages)
                        + float(node.count_remaining) / float(siguiente))
            return len(node.taken_packages)

        def generate_domain(node):
            """≙ ``generate_domain`` (``odoo19c: :676-690``).

            Los paquetes elegidos por id; los sueltos se resuelven a ids
            concretos —uno por unidad tomada— sólo si el nodo tomó alguno.
            """
            selected_single_items = []
            single_item_ids = None
            for pkg in node.taken_packages:
                if pkg.package_id is None:
                    if single_item_ids is None:
                        single_item_ids = list(
                            queryset.filter(package__isnull=True)
                            .values_list('pk', flat=True))
                    if single_item_ids:
                        selected_single_items.append(single_item_ids.pop())
            filtro = Q(package__in=[e.package_id for e in node.taken_packages
                                    if e.package_id is not None])
            if selected_single_items:
                filtro |= Q(pk__in=selected_single_items)
            return queryset.filter(filtro)

        #: ≙ ``Node = namedtuple("Node", "count_remaining taken_packages next_index")``
        #: (``odoo19c: :692``).
        Node = namedtuple('Node', 'count_remaining taken_packages next_index')

        frontier = PriorityQueue()
        frontier.put(Node(Decimal(qty), (), 0), 0)
        best_leaf = Node(Decimal(qty), (), 0)

        try:
            while not frontier.empty():
                current = frontier.get()
                if current.count_remaining <= 0:
                    return generate_domain(current)

                # ≙ ``:711-714``: una sola rama por cantidad repetida.
                last_count = None
                i = current.next_index
                while i < size:
                    pkg = qty_by_package[i]
                    i += 1
                    if pkg.available_qty == last_count:
                        continue
                    last_count = pkg.available_qty

                    count = current.count_remaining - pkg.available_qty
                    taken = current.taken_packages + (pkg,)
                    node = Node(count, taken, i)

                    if count < 0:
                        # ≙ ``:722-727``: se pasó. Se guarda si mejora al mejor
                        # intento — menos paquetes, o el mismo número dejando
                        # menos sobrante.
                        if (best_leaf.count_remaining > 0
                                or len(node.taken_packages) < len(best_leaf.taken_packages)
                                or (len(node.taken_packages) == len(best_leaf.taken_packages)
                                    and node.count_remaining > best_leaf.count_remaining)):
                            best_leaf = node
                        continue

                    if i >= size and count != 0:
                        # ≙ ``:729-733``: no alcanza ni tomándolo todo.
                        if node.count_remaining < best_leaf.count_remaining:
                            best_leaf = node
                        continue

                    frontier.put(node, heuristic(node))
        except MemoryError:
            # ≙ ``:736-738``: sin memoria se devuelve el conjunto sin acotar.
            return queryset

        return generate_domain(best_leaf)

    @classmethod
    def _get_removal_strategy_order(cls, removal_strategy):
        """≙ ``_get_removal_strategy_order`` (``odoo19c: :741-748``).

        El orden de retiro traducido al vocabulario de ``order_by``. Es el
        símbolo que ``product_expiry`` extiende para añadir ``fefo`` — la
        referencia lo hace con ``super()``, aquí con ``chain_method``.
        """
        if removal_strategy in ('fifo', 'least_packages'):
            return ('in_date', 'id')
        if removal_strategy == 'lifo':
            return ('-in_date', '-id')
        if removal_strategy == 'closest':
            return None
        raise UserError(
            _('La estrategia de retiro %s no está implementada.') % removal_strategy)

    @classmethod
    def _get_gather_domain(cls, product, location, lot=None, package=None,
                           owner=None, strict=False, with_expiration=None):
        """≙ ``_get_gather_domain`` (``odoo19c: :750-769``).

        ``strict`` es la distinción que gobierna todo el módulo: sin él la
        búsqueda baja por el árbol de ubicaciones y admite quants sin lote; con
        él exige la coincidencia exacta de las cinco características.
        """
        dominios = [Q(product=product)]
        if not strict:
            if lot is not None:
                dominios.append(expression.OR([Q(lot=lot), Q(lot__isnull=True)]))
            if package is not None:
                dominios.append(Q(package=package))
            if owner is not None:
                dominios.append(Q(owner=owner))
            if location is not None:
                # ≙ ``Domain('location_id', 'child_of', location_id.id)``
                # (``odoo19c: :759``) — el OPERADOR, no el predicado.
                dominios.append(location.child_of_domain())
        else:
            dominios.extend((
                Q(lot=lot) if lot is not None else Q(lot__isnull=True),
                Q(package=package) if package is not None else Q(package__isnull=True),
                Q(owner=owner) if owner is not None else Q(owner__isnull=True),
                Q(location=location),
            ))
        if with_expiration is not None:
            dominios.append(expression.OR([
                Q(lot__removal_date__gte=with_expiration),
                Q(lot__removal_date__isnull=True),
            ]))
        # ≙ ``Domain.AND(domains)`` (``odoo19c: :769``) — el espejo del proyecto
        # de ``odoo.fields.Domain`` es ``osv.expression``, cuyo tipo de llegada
        # es el ``Q`` de Django (``src/orm/domains.py``).
        return expression.AND(dominios)

    @classmethod
    def _gather(cls, product, location, lot=None, package=None, owner=None,
                strict=False, qty=0, with_expiration=None):
        """≙ ``_gather`` (``odoo19c: :771-791``).

        Docstring de la referencia: *"if records in self, the records are
        filtered based on the wanted characteristics passed to this function;
        if not, a search is done with all the characteristics passed"*.

        Devuelve los quants candidatos **en el orden de la estrategia de
        retiro** — que es lo que hace que la reserva consuma primero lo que
        toca.
        """
        estrategia = cls._get_removal_strategy(product, location)
        filtro = cls._get_gather_domain(product, location, lot, package, owner,
                                        strict, with_expiration)
        queryset = cls.objects.filter(filtro)
        if estrategia == 'least_packages' and qty:
            queryset = cls._run_least_packages_removal_strategy_astar(queryset, qty)
        orden = cls._get_removal_strategy_order(estrategia)
        if orden:
            orden_final = orden
        elif estrategia == 'closest':
            orden_final = ('location__complete_name', '-id')
        else:
            orden_final = ('id',)
        # ≙ ``res.sorted(lambda q: not q.lot_id)`` (``:791``): los quants CON
        # lote van primero, y dentro de cada grupo manda la estrategia — el
        # ``sorted`` de la fuente es estable, así que no reordena lo ya ordenado.
        #
        # Dos cuidados que costaron el orden FIFO:
        #
        # - ``order_by`` de Django **reemplaza**, no acumula: encadenar uno por
        #   rama y otro al final descartaba el de la estrategia (y con él las
        #   ramas ``least_packages`` y ``closest``). Va una sola llamada.
        # - la clave es «¿tiene lote?», un booleano, **no** el valor del lote:
        #   ``F('lot').desc(nulls_last=True)`` ordena por id de lote descendente,
        #   que es otra cosa y pisaba el ``in_date``.
        return (queryset
                .annotate(without_lot=Case(
                    When(lot__isnull=True, then=Value(1)),
                    default=Value(0), output_field=IntegerField()))
                .order_by('without_lot', *orden_final))

    @classmethod
    def _get_available_quantity(cls, product, location, lot=None, package=None,
                                owner=None, strict=False, allow_negative=False):
        """≙ ``_get_available_quantity`` (``odoo19c: :793-832``).

        Docstring de la referencia: *"Return the available quantity, i.e. the
        sum of `quantity` minus the sum of `reserved_quantity`"*.

        Con ``allow_negative=False`` —el default— un saldo negativo se lee como
        cero: no se puede reservar de un déficit. Para producto con
        trazabilidad la suma se hace **por lote**, porque un lote en déficit no
        debe consumir el disponible de otro.
        """
        with sudo():  # ``self = self.sudo()`` de la referencia (``odoo19c: :812``)
            quants = cls._gather(product, location, lot=lot, package=package,
                                 owner=owner, strict=strict)
            cero = Decimal('0.00')
            if getattr(product, 'tracking', 'none') == 'none':
                agregado = quants.aggregate(
                    q=Sum('quantity'), r=Sum('reserved_quantity'))
                disponible = ((agregado['q'] or cero) - (agregado['r'] or cero))
                if allow_negative:
                    return disponible
                return disponible if disponible >= cero else cero

            por_lote = defaultdict(lambda: cero)
            for quant in quants:
                if quant.lot is None and strict and lot is not None:
                    continue
                clave = quant.lot_id if quant.lot is not None else 'untracked'
                por_lote[clave] += quant.quantity - quant.reserved_quantity
            if allow_negative:
                return sum(por_lote.values(), start=cero)
            return sum((v for v in por_lote.values() if v > cero), start=cero)

    @classmethod
    def _get_reserve_quantity(cls, product, location, quantity, uom=None, lot=None,
                              package=None, owner=None, strict=False):
        """≙ ``_get_reserve_quantity`` (``odoo19c: :834-914``).

        Docstring de la referencia: *"return: a list of tuples (quant,
        quantity_reserved) showing on which quant the reservation could be done
        and how much the system is able to reserve on it"*.

        No escribe nada: decide el reparto. Tres reglas de la referencia que se
        conservan tal cual —y que son la parte difícil—:

        1. un quant con saldo negativo **descuenta** del disponible de su misma
           combinación antes de repartir (``negative_reserved_quantity``);
        2. un producto con número de serie no admite fracción;
        3. una cantidad negativa es una **liberación**, y no puede liberar más
           de lo reservado.
        """
        with sudo():  # ``self = self.sudo()`` de la referencia (``odoo19c: :844``)
            cero = Decimal('0.00')
            quants = list(cls._gather(product, location, lot=lot, package=package,
                                      owner=owner, strict=strict, qty=quantity))
            disponible = cls._get_available_quantity(
                product, location, lot, package, owner, strict)
            cantidad = min(Decimal(quantity), disponible)

            if getattr(product, 'tracking', 'none') == 'serial' and cantidad != int(cantidad):
                cantidad = cero

            reservados = []
            if cantidad > cero:
                disponible = (
                    sum((q.quantity for q in quants if q.quantity > cero), start=cero)
                    - sum((q.reserved_quantity for q in quants), start=cero)
                )
            elif cantidad < cero:
                disponible = sum((q.reserved_quantity for q in quants), start=cero)
                if abs(cantidad) > disponible:
                    raise UserError(
                        _('No es posible liberar más productos de %s de los que hay '
                          'en existencia.') % product)
            else:
                return reservados

            negativos = defaultdict(lambda: cero)
            for quant in quants:
                saldo = quant.quantity - quant.reserved_quantity
                if saldo < cero:
                    negativos[(quant.location_id, quant.lot_id,
                               quant.package_id, quant.owner_id)] += saldo

            for quant in quants:
                clave = (quant.location_id, quant.lot_id, quant.package_id, quant.owner_id)
                if cantidad > cero:
                    tope = quant.quantity - quant.reserved_quantity
                    if tope <= cero:
                        continue
                    negativo = negativos[clave]
                    if negativo:
                        a_descontar = min(abs(negativo), tope)
                        negativos[clave] += a_descontar
                        tope -= a_descontar
                    if tope <= cero:
                        continue
                    tope = min(tope, cantidad)
                    reservados.append((quant, tope))
                    cantidad -= tope
                    disponible -= tope
                else:
                    tope = min(quant.reserved_quantity, abs(cantidad))
                    reservados.append((quant, -tope))
                    cantidad += tope
                    disponible += tope
                if cantidad == cero or disponible == cero:
                    break
            return reservados

    @classmethod
    def _get_quants_by_products_locations(cls, products, locations, extra_domain=None):
        """≙ ``_get_quants_by_products_locations`` (``odoo19c: :916-933``).

        Índice de quants por las cinco características, para no golpear la base
        una vez por combinación. Es el que puebla ``quants_cache``.
        """
        resultado = defaultdict(list)
        if not products or not locations:
            return resultado
        # ≙ ``('location_id', 'child_of', locations.ids)`` — el operador de
        # dominio, que sobre varias raíces es la unión de sus descendencias.
        filtro = expression.AND([
            Q(product__in=products),
            expression.OR([location.child_of_domain() for location in locations]),
        ])
        if extra_domain is not None:
            # ≙ ``domain &= Domain(extra_domain)`` (``odoo19c: :925``).
            filtro = expression.AND([filtro, extra_domain])
        for quant in cls.objects.filter(filtro).order_by('lot'):
            clave = (quant.product_id, quant.location_id, quant.lot_id,
                     quant.package_id, quant.owner_id)
            resultado[clave].append(quant)
        return resultado

    # ------------------------------------------------------------------ #
    # Reacciones a la edición (D-3)                                       #
    # ------------------------------------------------------------------ #

    def _onchange_location_or_product_id(self):
        """≙ ``_onchange_location_or_product_id`` (``odoo19c: :935-957``).

        Al completar la línea se traen los valores teóricos. Si el lote no
        corresponde al producto se limpia; si el producto es serial, el conteo
        arranca en 1.
        """
        cambios = {}
        if self.product is None or self.location is None:
            return cambios
        if self.lot is not None:
            if self.tracking == 'none' or self.product != self.lot.product:
                cambios['lot'] = None
        quants = self._gather(self.product, self.location, lot=self.lot,
                              package=self.package, owner=self.owner, strict=True)
        self.quantity = sum(
            (q.quantity for q in quants if q.lot_id == self.lot_id),
            start=Decimal('0.00'))
        if self.lot is not None and self.tracking == 'serial':
            cambios['inventory_quantity'] = Decimal('1')
            cambios['inventory_quantity_auto_apply'] = Decimal('1')
        return cambios

    def _onchange_inventory_quantity(self):
        """≙ ``_onchange_inventory_quantity`` (``odoo19c: :959-970``)."""
        if self.location is not None and self.location.usage == 'inventory':
            return {'warning': {
                'title': _('No se puede modificar la cantidad de pérdida de inventario'),
                'message': _('Editar cantidades en una ubicación de ajuste de '
                             'inventario está prohibido: esas ubicaciones son la '
                             'contrapartida al corregir las cantidades.'),
            }}
        return None

    def _onchange_serial_number(self):
        """≙ ``_onchange_serial_number`` (``odoo19c: :972-979``)."""
        if self.lot is not None and self.tracking == 'serial':
            mensaje, _location = self._check_serial_number(
                self.product, self.lot, self.company)
            if mensaje:
                return {'warning': {'title': _('Advertencia'), 'message': mensaje}}
        return None

    def _onchange_product_id(self):
        """≙ ``_onchange_product_id`` (``odoo19c: :981-994``).

        Propone la ubicación: la del último quant del producto si tiene
        trazabilidad, o el almacén de la empresa.
        """
        if self.location is not None:
            return None
        if self.tracking in ('lot', 'serial'):
            previo = (
                type(self).objects
                .filter(product=self.product,
                        location__usage__in=['internal', 'transit'])
                .order_by('-created_at')
                .first()
            )
            if previo is not None:
                self.location = previo.location
        if self.location is None:
            warehouse_model = apps.get_model('stock', 'StockWarehouse')
            almacen = (warehouse_model.objects.filter(company=self.company).first()
                       if warehouse_model else None)
            if almacen is not None:
                self.location = almacen.lot_stock
        return None

    # ------------------------------------------------------------------ #
    # Ajuste de inventario y actualización de saldos                      #
    # ------------------------------------------------------------------ #

    def _apply_inventory(self, date=None):
        """≙ ``_apply_inventory`` (``odoo19c: :996-1036``).

        Crea y valida el movimiento que hace que el quant coincida con lo
        contado. La contrapartida es la ubicación de pérdida de inventario del
        producto: si sobra, entra desde ahí; si falta, sale hacia ahí.
        """
        self.inventory_quantity_set = True
        self._compute_inventory_diff_quantity()
        move_model = apps.get_model('stock', 'StockMove')
        location_model = apps.get_model('stock', 'StockLocation')
        perdida = location_model.objects.filter(usage='inventory').first()
        cero = Decimal('0.00')
        if self.inventory_diff_quantity != cero and move_model is not None:
            if self.inventory_diff_quantity > cero:
                vals = self._get_inventory_move_values(
                    self.inventory_diff_quantity, perdida, self.location,
                    package_dest=self.package)
            else:
                vals = self._get_inventory_move_values(
                    -self.inventory_diff_quantity, self.location, perdida,
                    package=self.package)
            movimiento = move_model.objects.create(**vals)
            movimiento.action_done()
            if date is not None:
                movimiento.date = date
                movimiento.save(update_fields=['date', 'updated_at'])
        if self.location is not None:
            self.location.last_inventory_date = timezone.now().date()
            self.location.save(update_fields=['last_inventory_date', 'updated_at'])
            self.inventory_date = self.location.get_next_inventory_date()
        type(self).action_clear_inventory_quantity([self])

    @classmethod
    def _update_available_quantity(cls, product, location, quantity=None,
                                   reserved_quantity=None, lot=None, package=None,
                                   owner=None, in_date=None):
        """≙ ``_update_available_quantity`` (``odoo19c: :1038-1106``).

        Docstring de la referencia: *"Increase or decrease `quantity` or
        'reserved quantity' of a set of quants"*. Devuelve la tupla
        ``(disponible, in_date)``.

        La ``in_date`` que sobrevive es **la más antigua** de las que
        concurren: es la clave de orden de FIFO, y tomar la nueva rompería el
        orden de consumo.
        """
        with sudo():  # ``self = self.sudo()`` de la referencia (``odoo19c: :1055``)
            if not (quantity or reserved_quantity):
                raise ValidationError(
                    _('Se debe indicar la cantidad o la cantidad reservada.'))
            cero = Decimal('0.00')
            quants = list(cls._gather(product, location, lot=lot, package=package,
                                      owner=owner, strict=True))
            if lot is not None:
                if Decimal(quantity or cero) > cero:
                    quants = [q for q in quants if q.lot is not None]
                else:
                    # No se descuenta de un quant negativo sin lote.
                    quants = [q for q in quants if q.quantity > cero or q.lot is not None]

            if location is not None and location.should_bypass_reservation():
                fechas = []
            else:
                fechas = [q.in_date for q in quants if q.in_date and q.quantity > cero]
            if in_date is not None:
                fechas.append(in_date)
            in_date = min(fechas) if fechas else timezone.now()

            quant = quants[0] if quants else None
            if quant is not None:
                # ≙ ``try_lock_for_update(limit=1)`` (``:1085``): la referencia
                # bloquea el primer quant disponible para que dos transacciones no
                # repartan el mismo saldo.
                quant = (cls.objects.select_for_update()
                         .filter(pk=quant.pk).first()) or quant
                quant.in_date = in_date
                if quantity:
                    quant.quantity = quant.quantity + Decimal(quantity)
                if reserved_quantity:
                    nueva = quant.reserved_quantity + Decimal(reserved_quantity)
                    quant.reserved_quantity = nueva if nueva > cero else cero
                quant.save(update_fields=['in_date', 'quantity', 'reserved_quantity',
                                          'inventory_diff_quantity', 'updated_at'])
            else:
                vals = {'product': product, 'location': location, 'lot': lot,
                        'package': package, 'owner': owner, 'in_date': in_date}
                if quantity:
                    vals['quantity'] = Decimal(quantity)
                if reserved_quantity:
                    vals['reserved_quantity'] = Decimal(reserved_quantity)
                cls.create([vals])
            return cls._get_available_quantity(
                product, location, lot=lot, package=package, owner=owner,
                strict=True, allow_negative=True), in_date

    @classmethod
    def _update_reserved_quantity(cls, product, location, quantity, lot=None,
                                  package=None, owner=None, strict=True):
        """≙ ``_update_reserved_quantity`` (``odoo19c: :1108-1121``).

        Docstring de la referencia: *"Increase or decrease `reserved_quantity`
        of a set of quants"*. Es un delegado a ``_update_available_quantity``,
        igual que allá.
        """
        return cls._update_available_quantity(
            product, location, reserved_quantity=quantity, lot=lot,
            package=package, owner=owner)

    @classmethod
    def _unlink_zero_quants(cls):
        """≙ ``_unlink_zero_quants`` (``odoo19c: :1123-1140``).

        Docstring de la referencia: *"It used to directly unlink these zero
        quants but this proved to hurt the performance … We defer the calls to
        unlink in this method"*. El SQL se copia (D-6): el redondeo por
        ``round(numeric, N)`` es del motor.
        """
        digitos = 6
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id FROM stock_quant
                    WHERE (round(quantity::numeric, %s) = 0 OR quantity IS NULL)
                      AND round(reserved_quantity::numeric, %s) = 0
                      AND (round(inventory_quantity::numeric, %s) = 0
                           OR inventory_quantity IS NULL)
                      AND user_id IS NULL""",
                [digitos, digitos, digitos])
            ids = [fila[0] for fila in cursor.fetchall()]
        if ids:
            with sudo():  # ``quants.sudo().unlink()`` (``odoo19c: :1139``)
                cls.objects.filter(pk__in=ids).delete()

    @classmethod
    def _clean_reservations(cls):
        """≙ ``_clean_reservations`` (``odoo19c: :1142-1176``).

        Reconcilia lo reservado en los quants contra lo que las líneas de
        movimiento dicen tener reservado. Una ubicación que puentea la reserva
        se limpia entera; el resto se ajusta por la diferencia.
        """
        move_line = apps.get_model('stock', 'StockMoveLine')
        cero = Decimal('0.00')
        reservado_quants = (
            cls.objects.exclude(reserved_quantity=cero)
            .values('product', 'location', 'lot', 'package', 'owner')
            .annotate(total=Sum('reserved_quantity'))
        )
        reservado_lineas = {}
        if move_line is not None:
            for fila in (move_line.objects
                         .filter(state__in=['assigned', 'partially_available',
                                            'waiting', 'confirmed'])
                         .exclude(quantity_product_uom=cero)
                         .values('product', 'location', 'lot', 'package', 'owner')
                         .annotate(total=Sum('quantity_product_uom'))):
                clave = (fila['product'], fila['location'], fila['lot'],
                         fila['package'], fila['owner'])
                reservado_lineas[clave] = fila['total'] or cero

        location_model = apps.get_model('stock', 'StockLocation')
        product_model = apps.get_model('product', 'ProductProduct')
        for fila in reservado_quants:
            clave = (fila['product'], fila['location'], fila['lot'],
                     fila['package'], fila['owner'])
            en_lineas = reservado_lineas.pop(clave, cero)
            location = location_model.objects.filter(pk=fila['location']).first()
            product = product_model.objects.filter(pk=fila['product']).first()
            if location is not None and location.should_bypass_reservation():
                delta = -(fila['total'] or cero)
            elif (fila['total'] or cero) != en_lineas:
                delta = en_lineas - (fila['total'] or cero)
            else:
                continue
            cls._update_reserved_quantity(
                product, location, delta, lot=cls._by_pk('stock', 'StockLot', fila['lot']),
                package=cls._by_pk('stock', 'StockPackage', fila['package']),
                owner=cls._by_pk('base', 'ResPartner', fila['owner']))

        for clave, cantidad in reservado_lineas.items():
            product_pk, location_pk, lot_pk, package_pk, owner_pk = clave
            location = location_model.objects.filter(pk=location_pk).first()
            product = product_model.objects.filter(pk=product_pk).first()
            if location is None or location.should_bypass_reservation():
                continue
            if cls._should_bypass_product(product, location, cantidad):
                continue
            cls._update_reserved_quantity(
                product, location, cantidad,
                lot=cls._by_pk('stock', 'StockLot', lot_pk),
                package=cls._by_pk('stock', 'StockPackage', package_pk),
                owner=cls._by_pk('base', 'ResPartner', owner_pk))

    @staticmethod
    def _by_pk(app_label, model_name, pk):
        """Resuelve un FK opcional desde su clave — ayudante local, no de la referencia.

        En la referencia el ``_read_group`` ya devuelve recordsets; aquí
        ``values()`` devuelve claves, así que hace falta el paso de vuelta.
        """
        if pk is None:
            return None
        modelo = apps.get_model(app_label, model_name)
        return modelo.objects.filter(pk=pk).first() if modelo else None

    @classmethod
    def _merge_quants(cls):
        """≙ ``_merge_quants`` (``odoo19c: :1178-1223``).

        Docstring de la referencia: *"In a situation where one transaction is
        updating a quant via `_update_available_quantity` and another
        concurrent one calls this function with the same argument, we'll create
        a new quant in order for these transactions to not rollback. This
        method will find and deduplicate these quants"*.

        El CTE se copia verbatim (D-6): es un ``UPDATE`` + ``DELETE`` en una
        sola sentencia, y traducirlo al ORM lo partiría en dos —que es
        exactamente la carrera que este método existe para cerrar.
        """
        consulta = """
            WITH dupes AS (
                SELECT min(id) AS to_update_quant_id,
                       (array_agg(id ORDER BY id))[2:array_length(array_agg(id), 1)]
                           AS to_delete_quant_ids,
                       GREATEST(0, SUM(reserved_quantity)) AS reserved_quantity,
                       SUM(inventory_quantity) AS inventory_quantity,
                       SUM(quantity) AS quantity,
                       MIN(in_date) AS in_date
                  FROM stock_quant
                 GROUP BY product_id, company_id, location_id, lot_id,
                          package_id, owner_id
                HAVING count(id) > 1
            ),
            _up AS (
                UPDATE stock_quant q
                   SET quantity = d.quantity,
                       reserved_quantity = d.reserved_quantity,
                       inventory_quantity = d.inventory_quantity,
                       in_date = d.in_date
                  FROM dupes d
                 WHERE d.to_update_quant_id = q.id
            )
            DELETE FROM stock_quant
             WHERE id IN (SELECT unnest(to_delete_quant_ids) FROM dupes)
        """
        with connection.cursor() as cursor:
            cursor.execute(consulta)

    @classmethod
    def _quant_tasks(cls):
        """≙ ``_quant_tasks`` (``odoo19c: :1225-1229``) — las tres, en orden."""
        cls._merge_quants()
        cls._clean_reservations()
        cls._unlink_zero_quants()

    @classmethod
    def _is_inventory_mode(cls, inventory_mode=None):
        """≙ ``_is_inventory_mode`` (``odoo19c: :1231-1237``).

        Docstring de la referencia: *"Used to control whether a quant was
        written on or created during an 'inventory session'"*.

        Allá lo decide el contexto del entorno más el grupo del usuario; aquí
        el contexto se pasa explícito, porque este stack no tiene ``env.context``
        (misma divergencia que ``stock_picking.py`` declara).
        """
        return bool(inventory_mode)

    @classmethod
    def _get_inventory_fields_create(cls):
        """≙ ``_get_inventory_fields_create`` (``odoo19c: :1239-1243``)."""
        return ['product', 'owner'] + cls._get_inventory_fields_write()

    @classmethod
    def _get_inventory_fields_write(cls):
        """≙ ``_get_inventory_fields_write`` (``odoo19c: :1245-1251``)."""
        return ['inventory_quantity', 'inventory_quantity_auto_apply',
                'inventory_diff_quantity', 'inventory_date', 'user',
                'inventory_quantity_set', 'is_outdated', 'lot', 'location',
                'package']

    def _get_inventory_move_values(self, qty, location, location_dest,
                                   package=None, package_dest=None,
                                   inventory_name=None):
        """≙ ``_get_inventory_move_values`` (``odoo19c: :1253-1292``).

        Docstring de la referencia: *"Called when user manually set a new
        quantity (via `inventory_quantity`) just before creating the
        corresponding stock move"*.
        """
        vals = {
            'product': self.product,
            'product_uom': self.product_uom,
            'product_uom_qty': qty,
            'company': self.company,
            'state': 'confirmed',
            'location': location,
            'location_dest': location_dest,
            'restrict_partner': self.owner,
            'is_inventory': True,
            'picked': True,
            'move_line_vals': [{
                'product': self.product,
                'product_uom': self.product_uom,
                'quantity': qty,
                'location': location,
                'location_dest': location_dest,
                'company': self.company,
                'lot': self.lot,
                'package': package,
                'result_package': package_dest,
                'owner': self.owner,
            }],
        }
        if inventory_name:
            vals['inventory_name'] = inventory_name
        return vals

    @classmethod
    def _set_view_context(cls, base_context=None):
        """≙ ``_set_view_context`` (``odoo19c: :1294-1306``).

        Docstring de la referencia: *"Adds context when opening quants related
        views"*. Sin multi-ubicación se fija la ubicación por defecto del
        almacén; con permiso de escritura se entra en modo inventario.
        """
        contexto = dict(base_context or {})
        warehouse_model = apps.get_model('stock', 'StockWarehouse')
        almacen = warehouse_model.objects.first() if warehouse_model else None
        if almacen is not None:
            contexto.setdefault('default_location_id', almacen.lot_stock_id)
            contexto.setdefault('hide_location', not contexto.get('always_show_loc'))
        contexto['inventory_mode'] = True
        return contexto

    @classmethod
    def _get_quants_action(cls, extend=False):
        """≙ ``_get_quants_action`` (``odoo19c: :1308-1347``).

        Docstring de la referencia: *"Returns an action to open (non-inventory
        adjustment) quant view"*.
        """
        cls._quant_tasks()
        accion = cls._action_by_xmlid('stock.stock_quant_action') or {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
        }
        accion['context'] = {'inventory_report_mode': True}
        accion['view_mode'] = 'list,form,pivot,graph' if extend else 'list,form'
        accion['path'] = 'stock-locations'
        return accion

    # ------------------------------------------------------------------ #
    # Códigos de barras                                                   #
    # ------------------------------------------------------------------ #

    def _get_gs1_barcode(self, gs1_quantity_rules_ai_by_uom=None):
        """≙ ``_get_gs1_barcode`` (``odoo19c: :1349-1388``).

        Docstring de la referencia: *"Generates a GS1 barcode for the quant's
        properties (product, quantity and LN/SN.)"*.

        Concatena el AI del producto, el de la cantidad y el del lote/serie.
        ``product_expiry`` lo extiende para anteponer los AI ``17``/``15``.
        """
        gs1_quantity_rules_ai_by_uom = gs1_quantity_rules_ai_by_uom or {}
        barcode = ''
        codigo = getattr(self.product, 'barcode', None)
        if codigo:
            barcode += f'01{str(codigo).rjust(14, "0")}'
        uom = self.product_uom
        ai_cantidad = gs1_quantity_rules_ai_by_uom.get(
            uom.pk if uom is not None else None, '30')
        cantidad = int(self.quantity)
        if cantidad:
            barcode += f'{ai_cantidad}{str(cantidad).rjust(8, "0")}'
        if self.lot is not None:
            ai_lote = '21' if self.tracking == 'serial' else '10'
            barcode += f'{ai_lote}{self.lot.name}'
        return barcode

    @classmethod
    def get_aggregate_barcodes(cls, quants, gs1_quantity_rules_ai_by_uom=None):
        """≙ ``get_aggregate_barcodes`` (``odoo19c: :1390-1453``).

        Agrega los quants que comparten producto y lote antes de generar su
        código: un código por combinación, no uno por fila.
        """
        agregados = {}
        for quant in quants:
            clave = (quant.product_id, quant.lot_id)
            if clave in agregados:
                agregados[clave].quantity += quant.quantity
            else:
                copia = cls(product=quant.product, location=quant.location,
                            lot=quant.lot, quantity=quant.quantity)
                agregados[clave] = copia
        return [q._get_gs1_barcode(gs1_quantity_rules_ai_by_uom)
                for q in agregados.values()]

    @classmethod
    def _check_serial_number(cls, product, lot, company, source_location=None):
        """≙ ``_check_serial_number`` (``odoo19c: :1455-1525``).

        Devuelve ``(mensaje, ubicacion_recomendada)``. Avisa de dos cosas: que
        el número de serie ya existe en otra empresa, y que ya está en otra
        ubicación —en cuyo caso propone esa ubicación como origen.
        """
        mensaje = None
        recomendada = None
        if product is None or lot is None:
            return mensaje, recomendada
        if getattr(product, 'tracking', 'none') != 'serial':
            return mensaje, recomendada

        lot_model = apps.get_model('stock', 'StockLot')
        duplicado = (lot_model.objects
                     .filter(name=lot.name, product=product)
                     .exclude(pk=lot.pk)
                     .exists())
        if duplicado:
            mensaje = (
                _('El número de serie %s ya existe en otra empresa.') % lot.name)
            return mensaje, recomendada

        quants = cls.objects.filter(lot=lot, quantity__gt=0,
                                    location__usage__in=['internal', 'transit'])
        if source_location is not None:
            quants = quants.exclude(location=source_location)
        ubicaciones = [q.location for q in quants]
        if ubicaciones:
            if len(ubicaciones) == 1:
                recomendada = ubicaciones[0]
                mensaje = (
                    _('El número de serie %(serial_number)s está en '
                      '%(other_locations)s, no en %(source_location)s.')
                    % {'serial_number': lot.name,
                       'other_locations': recomendada,
                       'source_location': source_location})
            else:
                mensaje = (
                    _('El número de serie %(serial_number)s está en varias '
                      'ubicaciones (%(other_locations)s). Corrígelo para evitar '
                      'datos inconsistentes.')
                    % {'serial_number': lot.name,
                       'other_locations': ', '.join(str(u) for u in ubicaciones)})
        return mensaje, recomendada

    # ------------------------------------------------------------------ #
    # Movimiento directo                                                  #
    # ------------------------------------------------------------------ #

    def move_quants(self, location_dest=None, package_dest=None, message=None,
                    unpack=False, up_to_parent_packages=None):
        """≙ ``move_quants`` (``odoo19c: :1527-1560``).

        Docstring de la referencia: *"Directly move a stock.quant to another
        location and/or package by creating a stock.move"*.

        La recursión ``set_parent_package`` de la referencia se conserva: el
        contenedor padre se mueve sólo si **todo** su contenido se mueve, y se
        detiene en los paquetes que ``up_to_parent_packages`` marca como tope.
        """
        message = message or _('Cantidad reubicada')
        topes = {p.pk for p in (up_to_parent_packages or [])}

        def set_parent_package(package):
            padre = getattr(package, 'parent_package', None)
            if padre is None or (topes and package.pk in topes):
                return
            contenido = padre.contained_quant_ids
            if any(q.pk != self.pk for q in contenido):
                # Sólo se mueve el contenedor si todo su contenido va con él.
                return
            package.package_dest = padre
            package.save(update_fields=['package_dest', 'updated_at'])
            set_parent_package(padre)

        resultado = package_dest
        if not unpack and package_dest is None:
            resultado = self.package
            if resultado is not None:
                set_parent_package(resultado)

        move_model = apps.get_model('stock', 'StockMove')
        if move_model is None:
            return None
        vals = self._get_inventory_move_values(
            self.quantity, self.location, location_dest or self.location,
            package=self.package, package_dest=resultado,
            inventory_name=message)
        movimiento = move_model.objects.create(**vals)
        movimiento.action_done()
        return movimiento

    @classmethod
    def _should_bypass_product(cls, product=None, location=None, reserved_quantity=0,
                               lot=None, package=None, owner=None):
        """≙ ``_should_bypass_product`` (``odoo19c: :1562-1563``).

        Devuelve ``False`` en la base — es el punto de extensión que los
        satélites sobrescriben, no una decisión de este addon.
        """
        return False

    # ------------------------------------------------------------------ #
    # Adaptadores del L0 (D-7) — no son símbolos de la referencia          #
    # ------------------------------------------------------------------ #

    @classmethod
    def available_qty(cls, product, location) -> Decimal:
        """Cantidad disponible con el trato de ubicación puenteada.

        **No es** ``_get_available_quantity``: añade que una ubicación no
        interna (proveedor, cliente, producción, inventario) tiene
        disponibilidad ilimitada. Allá esa decisión vive en
        ``stock.move._action_assign``; aquí queda declarada hasta que ese
        método se porte entero — sucesor: tarea **#330**.

        Lo encadena ``product_expiry`` para descontar la existencia caducada.
        """
        if location.should_bypass_reservation():
            return UNBOUNDED_QTY
        return cls._get_available_quantity(product, location)

    @classmethod
    def apply_move(cls, product, location_src, location_dest, qty) -> None:
        """Aplica un movimiento hecho: resta del origen, suma al destino.

        Adaptador de firma sobre ``_update_available_quantity``: los llamadores
        de este árbol pasan instancias sueltas, no un recordset con
        características. Las ubicaciones no internas no llevan contabilidad de
        quant (son sumideros/fuentes), igual que en la referencia.
        """
        qty = Decimal(qty)
        if not location_src.should_bypass_reservation():
            cls._update_available_quantity(product, location_src, quantity=-qty)
        if not location_dest.should_bypass_reservation():
            cls._update_available_quantity(product, location_dest, quantity=qty)

    @classmethod
    def set_on_hand(cls, product, location, qty, lot=None):
        """Ajuste directo: fija la cantidad a la mano.

        Atajo del L0 para sembrar existencia en pruebas y en la carga inicial;
        el camino de la referencia para un ajuste es
        ``inventory_quantity`` + ``action_apply_inventory``, que crea el
        movimiento de contrapartida. Este atajo **no** lo crea, y por eso no
        sustituye al ajuste: sólo siembra.
        """
        quant, _creado = cls.objects.get_or_create(
            product=product, location=location, lot=lot)
        quant.quantity = Decimal(qty)
        quant.save(update_fields=['quantity', 'inventory_diff_quantity', 'updated_at'])
        return quant
