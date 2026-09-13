"""``stock.move.line`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_move_line.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: la **línea de movimiento** es el detalle ejecutable de un
``stock.move``. El movimiento dice *"hay que mover 10 unidades del producto P"*;
la línea dice *"3 de ellas salen del lote L, en el paquete K, de la ubicación
A"*. Es la única pieza que **toca el quant**: reserva al crearse, mueve
existencia al validarse y libera al borrarse.

Tres verbos que no se confunden en la referencia, y aquí tampoco:

- **reservar** — ``_synchronize_quant(..., action="reserved")``: compromete
  cantidad sin moverla.
- **mover** — ``_synchronize_quant(...)`` sin acción: descuenta del origen y
  suma al destino.
- **liberar** — ``_free_reservation``: le quita la reserva a **otras** líneas
  cuando ésta se llevó existencia que ya estaba comprometida.

Porte símbolo por símbolo — 99 de 99
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_move_line.py`` (1239 líneas):
**5 atributos de clase**, **44 campos** y **50 métodos**.

*Métrica:* atributos y métodos por AST sobre el cuerpo de ``StockMoveLine``,
que es la única clase del archivo. *Ciega a:* las funciones **locales** dentro
de un método — hay dos, ``create_move`` (``:356``) y ``current_picking_first``
(``:820``), portadas como closures igual que en la fuente.

Atributos de clase — 5 de 5
-----------------------------

Los cinco que la referencia declara (``:16-19`` y ``:98-99``), verbatim.
``atributos-de-clase-de-modelo.md``: se portan **todos** los que la fuente
declare, o ninguno. El quinto no es un atributo de ORM sino un **objeto de
tabla** (``models.Index``), y su hogar aquí es ``Meta.indexes`` con el nombre
de la referencia conservado.

Campos — 44 de 44
-------------------

El FK se declara sin el sufijo ``_id`` porque Django ya expone la columna como
``<campo>_id``; así ``line.location_dest_id`` sigue siendo el identificador que
los consumidores ya usan (``stock_location.py``, ``stock_package.py``,
``product_strategy.py``, ``stock_quant.py``).

===============================================  ==========================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ==========================================
``picking_id`` (21-25)                           ``picking``
``move_id`` (26-28)                              ``move``
``company_id`` (29)                              ``company``
``product_id`` (30)                              ``product``
``allowed_uom_ids`` (31, compute)                property ``allowed_uom_ids``
``product_uom_id`` (32-35, compute+store)        ``product_uom`` (almacenado)
``product_category_name`` (36, related)          property ``product_category_name``
``quantity`` (37-39, compute+store)              ``quantity`` (almacenado)
``quantity_product_uom`` (40-42, compute+store)  ``quantity_product_uom`` (almacenado)
``picked`` (43, compute+store)                   ``picked`` (almacenado)
``package_id`` (44-47)                           ``package``
``lot_id`` (48-50)                               ``lot``
``lot_name`` (51)                                ``lot_name``
``result_package_id`` (52-56)                    ``result_package``
``result_package_dest_name`` (57, related)       property ``result_package_dest_name``
``package_history_id`` (58)                      ``package_history``
``is_entire_pack`` (59)                          ``is_entire_pack``
``date`` (60-62)                                 ``date``
``scheduled_date`` (63, related)                 property ``scheduled_date`` — **bloqueado**
``owner_id`` (64-67)                             ``owner``
``location_id`` (68-71, compute+store)           ``location`` (almacenado)
``location_dest_id`` (72, compute+store)         ``location_dest`` (almacenado)
``location_usage`` (73, related)                 property ``location_usage``
``location_dest_usage`` (74, related)            property ``location_dest_usage``
``lots_visible`` (75, compute)                   property ``lots_visible``
``picking_partner_id`` (76, related)             property ``picking_partner`` — **bloqueado**
``move_partner_id`` (77, related)                property ``move_partner`` — **bloqueado**
``picking_code`` (78, related)                   property ``picking_code``
``picking_type_id`` (79-81, compute+search)      property ``picking_type`` + ``_search_picking_type_id``
``picking_type_use_create_lots`` (82, related)   property ``picking_type_use_create_lots``
``picking_type_use_existing_lots`` (83, rel.)    property ``picking_type_use_existing_lots``
``state`` (84, related+store)                    ``state`` (almacenado)
``scrap_id`` (85, related)                       property ``scrap`` — **bloqueado**
``is_inventory`` (86, related)                   property ``is_inventory`` — **bloqueado**
``is_locked`` (87, related)                      property ``is_locked`` — **bloqueado**
``consume_line_ids`` (88, M2M)                   ``consume_line_ids`` (M2M reflexivo)
``produce_line_ids`` (89, M2M)                   property ``produce_line_ids`` (el reverso)
``reference`` (90, related)                      property ``reference`` — **bloqueado**
``tracking`` (91, related)                       property ``tracking``
``origin`` (92, related)                         property ``origin`` — **bloqueado**
``description_picking`` (93, related)            property ``description_picking`` — **bloqueado**
``quant_id`` (94, store=False)                   ``quant`` (``NonStored``)
``picking_location_id`` (95, related)            property ``picking_location``
``picking_location_dest_id`` (96, related)       property ``picking_location_dest``
===============================================  ==========================================

Métodos — 50 de 50
--------------------

**El guion bajo se porta.** Ningún ``_foo`` de la referencia se publica como
``foo`` aquí: la visibilidad es parte del contrato
(``porte-completo-no-parcial.md``, :ref:`h-api-581`). Los tres públicos de la
fuente —``get_move_line_quant_match``, ``action_open_reference``,
``action_put_in_pack``, ``action_revert_inventory``— lo siguen siendo, y los 46
restantes conservan su guion.

**Regla de equivalencia del ``compute``**, una sola y declarada aquí:

- **compute con ``store=True``** → el método conserva su nombre
  ``_compute_<campo>`` y lo llama ``save()``. Cinco casos:
  ``_compute_product_uom_id``, ``_compute_quantity``,
  ``_compute_quantity_product_uom``, ``_compute_picked``,
  ``_compute_location_id``.
- **compute sin almacenar** → el símbolo público es el **campo**, así que el
  método privado se colapsa en la ``property`` que lleva su nombre. Tres casos:
  ``_compute_allowed_uom_ids`` → ``allowed_uom_ids``, ``_compute_lots_visible``
  → ``lots_visible``, ``_compute_picking_type_id`` → ``picking_type``. Es la
  excepción (b) que ``porte-completo-no-parcial.md`` declara: el privado lo es
  *porque* el público es el campo.

Recordset vs registro
-----------------------

La referencia opera sobre *recordsets*: ``self`` puede ser una línea o mil. Aquí
la distinción se hace explícita en la firma:

- método con ``self.ensure_one()`` en la fuente → **método de instancia**;
- método que itera ``for ml in self`` → **``classmethod`` que recibe ``lines``**,
  un iterable de líneas.

No es una libertad: es la única traducción que preserva la semántica sin
inventar un recordset que este ORM no tiene.

Lo que este archivo NO cierra — 10 símbolos bloqueados, todos por la misma raíz
================================================================================

``stock.move`` está en el árbol como **esbozo**: 9 campos y 5 métodos, contra
los 210 métodos de ``odoo19c: addons/stock/models/stock_move.py``. Y
``StockPicking`` es otro esbozo (16 atributos). Nueve de los 44 campos son
``related`` a un atributo que esos dos esbozos aún no declaran, y varios
métodos llaman a métodos de ``stock.move`` que todavía no existen.

Se portan **igual**, navegando el FK como manda la referencia. Un
``AttributeError`` al leerlos es la señal correcta —fuerte y localizada— y
desaparece sola el día que ``stock_move.py`` aterrice; enmascararlo con un
``getattr(..., None)`` produciría un ``None`` silencioso, que es justo lo que
``check_silent_oks`` existe para impedir.

==========================================  ===============================================
Símbolo que falta                           Quién lo espera aquí
==========================================  ===============================================
``stock.move.date``                         ``scheduled_date``
``stock.move.partner_id``                   ``move_partner``
``stock.move.scrap_id``                     ``scrap``
``stock.move.is_inventory``                 ``is_inventory``, ``_exclude_requiring_lot``
``stock.move.is_locked``                    ``is_locked``
``stock.move.reference``                    ``reference``, ``_get_revert_inventory_move_values``
``stock.move.origin``                       ``origin``
``stock.move.description_picking``          ``description_picking``, ``_get_aggregated_properties``
``stock.move.product_uom``                  ``_compute_quantity``, ``_get_aggregated_properties``
``stock.picking.partner_id``                ``picking_partner``
==========================================  ===============================================

Y los métodos de ``stock.move`` que este archivo invoca y aún no existen:
``_should_bypass_reservation``, ``_recompute_state``, ``_action_assign``,
``_do_unreserve``, ``_visible_quantity``, ``_check_quantity``,
``_post_process_created_moves``, ``_action_done``, ``action_open_reference``.

- **Sucesor registrado:** tarea **#330** (*stock completo: los 25 archivos de
  la referencia, sin porte parcial*), cuyo siguiente archivo es justamente
  ``stock_move.py``. Este archivo es su precursor: los 50 símbolos quedan
  escritos y el día que el movimiento se complete no hay que volver aquí.
- **Lo que NO es:** un porte parcial. Los 99 símbolos del archivo están; lo que
  falta pertenece a **otro** archivo de la referencia, y está nombrado uno por
  uno arriba.

Dos divergencias de mecanismo declaradas
==========================================

**D-1 — el registro en el chatter.** ``_log_message`` (``:951-970``) publica en
el hilo del albarán con ``message_post_with_source`` y una plantilla QWeb
(``stock.track_move_template``). Aquí el mensaje se **arma** igual —el diff de
lote, ubicación, paquete y propietario— y se devuelve como diccionario; quién
lo publica es una decisión de la familia ``mail``, no de este modelo. Sucesor:
tarea **#279** (``stock`` no declara ningún ``ReportSpec``/vista propia).

**D-2 — las acciones de ventana.** ``action_open_reference`` (``:1027``),
``_check_destinations`` (``:1057``), ``_pre_put_in_pack_hook`` (``:1040``) y
``action_revert_inventory`` (``:1195``) devuelven ``ir.actions.act_window``
para el cliente Odoo. Se portan devolviendo el **mismo descriptor** —un dict
con ``res_model``/``views``/``res_id``—, que es el contrato de datos; lo que no
existe aquí es el cliente que lo consume. Mismo criterio que
``stock_picking.py`` ya usa con ``_action_by_xmlid``.

**D-3 — ``_compute_picking_type_id`` → property ``picking_type`` (:483)**
(:ref:`h-api-680`). El campo de la referencia es ``picking_type_id``; este
árbol retira el sufijo ``_id`` de todo FK, así que la clave que
``check_porte_completo.py`` deriva de la property (``_compute_picking_type``)
nunca coincide con el nombre real de la referencia
(``_compute_picking_type_id``), y el gate lo reporta ausente aunque el
docstring de ``picking_type`` (:484) ya cite el símbolo. Mismo mecanismo que
``stock_package.py::StockPackage`` y
``stock_orderpoint.py::StockWarehouseOrderpoint`` ya declaran para el mismo
patrón.

Primitivas del proyecto, no Django crudo
==========================================

Donde la referencia usa ``Domain``/``Domain.AND``, aquí va ``osv.expression``
(cuyo tipo de llegada es el ``Q`` de Django). Es el espejo declarado del
proyecto — ver :ref:`h-api-582` y la tarea **#339**.
"""
from collections import Counter, defaultdict
from decimal import Decimal

import fields
import api
import models
from django.apps import apps
from django.db.models import Q
from django.utils import timezone

from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from osv import expression
from tools.translate import _

#: Estados en los que una línea ya no admite edición ni borrado
#: (≙ el ``('done', 'cancel')`` que la referencia repite en seis sitios).
TERMINAL_STATES = ('done', 'cancel')

#: ≙ ``Domain.NEGATIVE_OPERATORS`` (``odoo19c: odoo/orm/domains.py``). El
#: espejo del proyecto (``osv.expression``) re-exporta ``AND``/``OR``/``NOT``/
#: ``to_q`` pero **no** esta constante, así que se declara aquí con los mismos
#: operadores. Su hogar natural es ``src/orm/domains.py``; llevarla allá es
#: parte de la tarea #339 (usar el espejo, no la primitiva cruda).
NEGATIVE_OPERATORS = ('!=', 'not like', 'not ilike', 'not in', 'not any')

#: ≙ ``_free_reservation_index`` (``odoo19c: :98-99``) — el índice parcial que
#: sostiene la búsqueda de ``_free_reservation``. Es un **objeto de tabla**, no
#: un atributo de ORM: su hogar aquí es ``Meta.indexes``
#: (``atributos-de-clase-de-modelo.md``). Se declara a nivel de módulo para
#: poder colgarlo además de la clase con el nombre de la referencia, y su
#: condición es la misma, expresada como ``Q`` porque es lo que Django acepta
#: en ``condition=``.
FREE_RESERVATION_INDEX = models.Index(
    fields=['id', 'company', 'product', 'lot', 'location', 'owner', 'package'],
    name='free_reservation_index',
    condition=(
        (Q(state__isnull=True) | ~Q(state__in=TERMINAL_STATES))
        & Q(quantity_product_uom__gt=0)
        & ~Q(picked=True)
    ),
)


class StockMoveLine(TimeStampedModel):
    """``stock.move.line`` — el detalle ejecutable de un movimiento."""

    # Atributos de clase de modelo — los cuatro de ORM que la referencia
    # declara (``odoo19c: addons/stock/models/stock_move_line.py:16-19``),
    # verbatim. El quinto (``_free_reservation_index``) es un objeto de tabla
    # y vive en ``Meta.indexes``.
    _name = 'stock.move.line'
    _description = "Product Moves (Stock Move Line)"
    _rec_name = "product_id"
    _order = "result_package_id desc, id"
    #: El quinto atributo de clase de la referencia (``:98-99``): un objeto de
    #: tabla, no de ORM. Se conserva su nombre y su hogar real es
    #: ``Meta.indexes``, que apunta al mismo objeto.
    _free_reservation_index = FREE_RESERVATION_INDEX

    picking          = fields.Many2one(
        'stock.StockPicking', on_delete=models.CASCADE, null=True, blank=True,
        related_name='move_line_ids', db_index=True,
        help_text='Transferencia donde se hizo el empaque (Odoo picking_id).',
    )
    move             = fields.Many2one(
        'stock.StockMove', on_delete=models.CASCADE, null=True, blank=True,
        related_name='move_line_ids', db_index=True,
        help_text='Movimiento de inventario al que pertenece (Odoo move_id).',
    )
    company          = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, db_index=True,
        related_name='stock_move_lines',
        help_text='Empresa (Odoo company_id, readonly+required; se recalcula '
                  'en save() desde el movimiento o el albarán).',
    )
    product          = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE, db_index=True,
        related_name='stock_move_lines',
        help_text='Producto (Odoo product_id; el dominio excluye servicios).',
    )
    product_uom      = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_move_lines',
        help_text='Unidad de la línea (Odoo product_uom_id, compute+store; '
                  'la recalcula _compute_product_uom_id).',
    )
    quantity         = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='Cantidad en la unidad de la línea (Odoo quantity, '
                  'compute+store con readonly=False).',
    )
    quantity_product_uom = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='La misma cantidad en la unidad del producto (Odoo '
                  'quantity_product_uom, compute+store).',
    )
    picked           = fields.Boolean(
        default=False,
        help_text='La línea ya fue tomada (Odoo picked, compute+store con '
                  'readonly=False).',
    )
    package          = fields.Many2one(
        'stock.StockPackage', on_delete=models.RESTRICT, null=True, blank=True,
        related_name='source_move_line_ids',
        help_text='Paquete de origen (Odoo package_id).',
    )
    lot              = fields.Many2one(
        'stock.StockLot', on_delete=models.CASCADE, null=True, blank=True,
        related_name='move_line_ids', db_index=True,
        help_text='Lote / número de serie (Odoo lot_id).',
    )
    lot_name         = fields.Char(
        max_length=255, null=True, blank=True,
        help_text='Nombre del lote cuando aún no existe el registro (Odoo '
                  'lot_name); lo materializa _create_and_assign_production_lot.',
    )
    result_package   = fields.Many2one(
        'stock.StockPackage', on_delete=models.RESTRICT, null=True, blank=True,
        related_name='move_line_ids',
        help_text='Paquete de destino (Odoo result_package_id).',
    )
    package_history  = fields.Many2one(
        'stock.StockPackageHistory', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='move_line_ids',
        help_text='Instantánea del paquete al momento del movimiento (Odoo '
                  'package_history_id).',
    )
    is_entire_pack   = fields.Boolean(
        default=False,
        help_text='La línea entró por un paquete completo (Odoo is_entire_pack).',
    )
    date             = fields.Datetime(
        default=timezone.now,
        help_text='Fecha de creación, actualizada al aumentar cantidad, al '
                  'marcarse tomada o al terminar (Odoo date).',
    )
    owner            = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_move_lines',
        help_text='Propietario de la mercancía en origen (Odoo owner_id).',
    )
    location         = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, db_index=True,
        related_name='move_line_ids',
        help_text='Ubicación de origen (Odoo location_id, compute+store).',
    )
    location_dest    = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, db_index=True,
        related_name='dest_move_line_ids',
        help_text='Ubicación de destino (Odoo location_dest_id, compute+store).',
    )
    state            = fields.Char(
        max_length=32, null=True, blank=True,
        help_text='Estado heredado del movimiento (Odoo state, related+store; '
                  'lo recalcula save()).',
    )
    consume_line_ids = fields.Many2many(
        'self', through='stock.StockMoveLineConsumeRel', symmetrical=False,
        through_fields=('consume_line', 'produce_line'),
        related_name='+', blank=True,
        help_text='Líneas consumidas por ésta (Odoo consume_line_ids).',
    )

    #: ≙ ``quant_id`` (``:94``) — «Dummy field for the detailed operation
    #: view». La referencia lo declara ``store=False``: existe para leerse y
    #: escribirse en memoria, nunca para consultarse. Aquí es el mismo
    #: mecanismo (``orm/fields_nonstored.py``), no una ``property``: la
    #: referencia **le asigna** valor (``vals.get('quant_id')`` en ``create``).
    quant = fields.NonStored(help_text='Existencia de la que se toma (Odoo quant_id).')

    class Meta:
        db_table = 'stock_move_line'
        # ≙ ``_order = "result_package_id desc, id"`` (``odoo19c: :19``).
        ordering = ['-result_package', 'id']
        indexes = [FREE_RESERVATION_INDEX]
        verbose_name = 'Línea de movimiento de inventario'
        verbose_name_plural = 'Líneas de movimiento de inventario'

    def __str__(self):
        # ≙ ``_rec_name = "product_id"`` (``odoo19c: :18``).
        return str(self.product) if self.product_id else f'stock.move.line#{self.pk}'

    # ------------------------------------------------------------------ #
    # Campos calculados sin almacenar (≙ los tres `compute` no-store)      #
    # ------------------------------------------------------------------ #

    @property
    def allowed_uom_ids(self):
        """≙ el campo ``allowed_uom_ids`` / ``_compute_allowed_uom_ids`` (``:101-104``).

        Las unidades admisibles son la del producto, las suyas alternas y las
        que declaran sus proveedores. La referencia lo resuelve con la unión de
        recordsets; aquí es la unión de los tres conjuntos de identificadores.
        """
        producto = self.product
        if producto is None:
            return []
        uom_model = apps.get_model('uom', 'Uom')
        permitidas = set()
        unidad = getattr(producto, 'uom', None)
        if unidad is not None:
            permitidas.add(unidad.pk)
        permitidas.update(
            uom.pk for uom in getattr(producto, 'uom_ids', uom_model.objects.none())
        )
        for proveedor in getattr(producto, 'seller_ids', []):
            if getattr(proveedor, 'product_uom', None) is not None:
                permitidas.add(proveedor.product_uom.pk)
        return list(uom_model.objects.filter(pk__in=permitidas))

    @property
    def product_category_name(self):
        """≙ ``product_category_name`` (``related='product_id.categ_id.complete_name'``, ``:36``)."""
        producto = self.product
        categoria = getattr(producto, 'categ', None) if producto is not None else None
        return getattr(categoria, 'complete_name', '')

    @property
    def result_package_dest_name(self):
        """≙ ``result_package_dest_name`` (related, ``:57``)."""
        paquete = self.result_package
        return paquete.dest_complete_name if paquete is not None else ''

    @property
    def scheduled_date(self):
        """≙ ``scheduled_date`` (``related='move_id.date'``, ``:63``).

        **Bloqueado:** ``stock.move`` aún no declara ``date`` — ver la tabla de
        símbolos bloqueados del docstring del módulo (tarea #330).
        """
        return self.move.date if self.move is not None else None

    @property
    def location_usage(self):
        """≙ ``location_usage`` (``related='location_id.usage'``, ``:73``)."""
        return self.location.usage if self.location is not None else None

    @property
    def location_dest_usage(self):
        """≙ ``location_dest_usage`` (related, ``:74``)."""
        return self.location_dest.usage if self.location_dest is not None else None

    @property
    def lots_visible(self):
        """≙ el campo ``lots_visible`` / ``_compute_lots_visible`` (``:114-121``).

        El lote se muestra si el producto se rastrea; y cuando hay tipo de
        operación, además decide el tipo: sólo si admite crear o usar lotes.
        """
        producto = self.product
        rastreado = getattr(producto, 'tracking', 'none') != 'none'
        albaran = self.picking
        tipo = getattr(albaran, 'picking_type', None) if albaran is not None else None
        if tipo is not None and rastreado:
            return bool(tipo.use_existing_lots or tipo.use_create_lots)
        return rastreado

    @property
    def picking_partner(self):
        """≙ ``picking_partner_id`` (``related='picking_id.partner_id'``, ``:76``).

        **Bloqueado:** ``StockPicking`` aún no declara ``partner`` (tarea #330).
        """
        return self.picking.partner if self.picking is not None else None

    @property
    def move_partner(self):
        """≙ ``move_partner_id`` (``related='move_id.partner_id'``, ``:77``).

        **Bloqueado:** ``stock.move`` aún no declara ``partner`` (tarea #330).
        """
        return self.move.partner if self.move is not None else None

    @property
    def picking_code(self):
        """≙ ``picking_code`` (``related='picking_type_id.code'``, ``:78``)."""
        tipo = self.picking_type
        return tipo.code if tipo is not None else None

    @property
    def picking_type(self):
        """≙ el campo ``picking_type_id`` / ``_compute_picking_type_id`` (``:136-141``).

        El tipo lo aporta el albarán; sin albarán la referencia deja el campo
        en falso.
        """
        albaran = self.picking
        return albaran.picking_type if albaran is not None else None

    @classmethod
    def _search_picking_type_id(cls, operator, value):
        """≙ ``_search_picking_type_id`` (``odoo19c: :150-153``).

        El campo no se almacena, así que la búsqueda se traduce al recorrido
        del FK. La referencia rehúsa los operadores negativos devolviendo
        ``NotImplemented``; se conserva verbatim, porque ese ``NotImplemented``
        es lo que hace que el ORM caiga a su ruta genérica.
        """
        if operator in NEGATIVE_OPERATORS:
            return NotImplemented
        return expression.to_q([('picking_id.picking_type_id', operator, value)])

    @property
    def picking_type_use_create_lots(self):
        """≙ ``picking_type_use_create_lots`` (related, ``:82``)."""
        tipo = self.picking_type
        return bool(tipo is not None and tipo.use_create_lots)

    @property
    def picking_type_use_existing_lots(self):
        """≙ ``picking_type_use_existing_lots`` (related, ``:83``)."""
        tipo = self.picking_type
        return bool(tipo is not None and tipo.use_existing_lots)

    @property
    def scrap(self):
        """≙ ``scrap_id`` (``related='move_id.scrap_id'``, ``:85``). **Bloqueado** (#330)."""
        return self.move.scrap if self.move is not None else None

    @property
    def is_inventory(self):
        """≙ ``is_inventory`` (``related='move_id.is_inventory'``, ``:86``). **Bloqueado** (#330)."""
        return bool(self.move is not None and self.move.is_inventory)

    @property
    def is_locked(self):
        """≙ ``is_locked`` (``related='move_id.is_locked'``, ``:87``). **Bloqueado** (#330)."""
        return bool(self.move is not None and self.move.is_locked)

    @property
    def produce_line_ids(self):
        """≙ ``produce_line_ids`` (``:89``) — el reverso del M2M reflexivo.

        La referencia declara los dos lados sobre la misma tabla
        ``stock_move_line_consume_rel`` con las columnas invertidas. Django lo
        resuelve navegando la relación al revés, así que aquí es el reverso y
        no una segunda tabla.
        """
        return type(self).objects.filter(consume_line_ids=self)

    @property
    def reference(self):
        """≙ ``reference`` (``related='move_id.reference'``, ``:90``). **Bloqueado** (#330)."""
        return self.move.reference if self.move is not None else None

    @property
    def tracking(self):
        """≙ ``tracking`` (``related='product_id.tracking'``, ``:91``)."""
        return getattr(self.product, 'tracking', 'none')

    @property
    def origin(self):
        """≙ ``origin`` (``related='move_id.origin'``, ``:92``). **Bloqueado** (#330)."""
        return self.move.origin if self.move is not None else None

    @property
    def description_picking(self):
        """≙ ``description_picking`` (``related='move_id.description_picking'``, ``:93``). **Bloqueado** (#330)."""
        return self.move.description_picking if self.move is not None else None

    @property
    def picking_location(self):
        """≙ ``picking_location_id`` (``related='picking_id.location_id'``, ``:95``)."""
        return self.picking.location if self.picking is not None else None

    @property
    def picking_location_dest(self):
        """≙ ``picking_location_dest_id`` (related, ``:96``)."""
        return self.picking.location_dest if self.picking is not None else None

    # ------------------------------------------------------------------ #
    # Campos calculados y almacenados (≙ los cinco `compute` con store)    #
    # ------------------------------------------------------------------ #

    def _compute_product_uom_id(self):
        """≙ ``_compute_product_uom_id`` (``odoo19c: :106-112``).

        Sólo llena la unidad si está vacía: la del movimiento si existe, la del
        producto si no. La referencia declara ``readonly=False``, así que un
        valor puesto a mano sobrevive.
        """
        if self.product_uom_id:
            return
        del_movimiento = getattr(self.move, 'product_uom', None) if self.move is not None else None
        if del_movimiento is not None:
            self.product_uom = del_movimiento
        elif self.product is not None:
            self.product_uom = self.product.uom

    def _compute_quantity(self):
        """≙ ``_compute_quantity`` (``odoo19c: :155-171``).

        Sólo actúa cuando la línea nace de un quant y aún no tiene cantidad:
        propone lo disponible del quant, acotado por lo que al movimiento le
        falta. Si al movimiento no le falta nada, propone todo lo disponible.
        """
        quant = self.quant
        if quant is None or self.quantity:
            return
        uom_producto = self.product.uom
        uom_linea = self.product_uom
        movimiento = self.move
        visible = movimiento._visible_quantity() if movimiento is not None else 0.0

        demanda = movimiento.product_uom.compute_quantity(
            movimiento.product_uom_qty, uom_linea, rounding_method='HALF-UP')
        hecho = movimiento.product_uom.compute_quantity(
            visible, uom_linea, rounding_method='HALF-UP')
        of_quant = uom_producto.compute_quantity(
            quant.available_qty(quant.product, quant.location), uom_linea,
            rounding_method='HALF-UP')

        if uom_linea.compare(demanda, hecho) > 0:
            self.quantity = max(0, min(of_quant, demanda - hecho))
        else:
            self.quantity = max(0, of_quant)

    def _compute_quantity_product_uom(self):
        """≙ ``_compute_quantity_product_uom`` (``odoo19c: :173-176``)."""
        if self.product_uom is None or self.product is None:
            self.quantity_product_uom = self.quantity
            return
        self.quantity_product_uom = Decimal(str(self.product_uom.compute_quantity(
            float(self.quantity), self.product.uom, rounding_method='HALF-UP')))

    def _compute_picked(self):
        """≙ ``_compute_picked`` (``odoo19c: :123-127``).

        La marca sólo se **pone**: la referencia nunca la quita desde aquí
        (``readonly=False``), así que un ``False`` explícito sobrevive salvo
        que el movimiento termine.
        """
        if self.move is not None and self.move.state == 'done':
            self.picked = True

    def _compute_location_id(self):
        """≙ ``_compute_location_id`` (``odoo19c: :143-148``).

        Origen y destino se heredan del movimiento, y del albarán si el
        movimiento no los fija. Se recalculan en dos casos: cuando están
        vacíos, y cuando **el albarán cambió de ubicación bajo la línea** — que
        es lo que la referencia detecta comparando contra ``_origin``, el
        registro tal como está en la base.

        Aquí ``_origin`` es la fila persistida: se lee sólo si la línea ya
        existe, porque una línea nueva no tiene contra qué comparar.
        """
        movimiento, albaran = self.move, self.picking
        del_movimiento = getattr(movimiento, 'location_id', None)
        del_albaran = getattr(albaran, 'location_id', None)
        dest_movimiento = getattr(movimiento, 'location_dest_id', None)
        dest_albaran = getattr(albaran, 'location_dest_id', None)

        origen = None
        if self.pk:
            origen = type(self).objects.filter(pk=self.pk).select_related(
                'picking').first()
        albaran_previo = origen.picking if origen is not None else None

        # La rama "el albarán cambió" sólo aplica a líneas EXISTENTES: en una
        # nueva no hay ``_origin`` y dispararía siempre, pisando el valor que
        # el llamador fijó explícitamente — la fuente sólo rellena lo no
        # provisto (precompute) y resincroniza al cambiar el albarán.
        if (self.location_id is None
                or (origen is not None
                    and getattr(albaran_previo, 'location_id', None) != del_albaran)):
            nueva = del_movimiento or del_albaran
            if nueva is not None:
                self.location_id = nueva
        if (self.location_dest_id is None
                or (origen is not None
                    and getattr(albaran_previo, 'location_dest_id', None) != dest_albaran)):
            nueva = dest_movimiento or dest_albaran
            if nueva is not None:
                self.location_dest_id = nueva

    def save(self, *args, **kwargs):
        """Recalcula los campos almacenados antes de escribir.

        El orden importa y es el de la referencia: la unidad antes que las dos
        cantidades (la conversión la necesita), y el estado al final porque
        ``picked`` lo consulta.
        """
        self._compute_product_uom_id()
        self._compute_location_id()
        self._compute_quantity()
        self._compute_quantity_product_uom()
        if self.move is not None:
            # ≙ ``state = fields.Selection(related='move_id.state', store=True)``
            self.state = self.move.state
        self._compute_picked()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Restricciones (≙ los dos `@api.constrains`)                          #
    # ------------------------------------------------------------------ #

    def _check_lot_product(self):
        """≙ ``_check_lot_product`` (``odoo19c: :178-186``)."""
        if self.lot is not None and self.product_id != self.lot.product_id:
            raise ValidationError(_(
                'This lot %(lot_name)s is incompatible with this product %(product_name)s',
                lot_name=self.lot.name,
                product_name=str(self.product),
            ))

    def _check_positive_quantity(self):
        """≙ ``_check_positive_quantity`` (``odoo19c: :188-191``)."""
        if self.quantity < 0:
            raise ValidationError(_('You can not enter negative quantities.'))

    def clean(self):
        """Ejecuta las dos restricciones declaradas (≙ ``@api.constrains``)."""
        super().clean()
        self._check_lot_product()
        self._check_positive_quantity()

    # ------------------------------------------------------------------ #
    # Onchange (≙ los cuatro `@api.onchange`)                              #
    # ------------------------------------------------------------------ #

    def _onchange_product_id(self):
        """≙ ``_onchange_product_id`` (``odoo19c: :193-196``).

        En la referencia el onchange fija ``lots_visible``, que aquí es una
        ``property`` derivada — así que devuelve el valor en vez de asignarlo.
        """
        if self.product is None:
            return {}
        return {'lots_visible': self.tracking != 'none'}

    def _onchange_serial_number(self):
        """≙ ``_onchange_serial_number`` (``odoo19c: :198-241``).

        Tres ayudas para el capturista de un producto con número de serie:
        pone la cantidad en 1, avisa si el número ya se usó en esta operación,
        y avisa (corrigiendo la ubicación) si la serie está en otro sitio.
        """
        res = {}
        if self.tracking != 'serial':
            return res
        if not self.quantity:
            self.quantity = Decimal('1.0000')

        mensaje = None
        if self.lot_name or self.lot is not None:
            otras = [l for l in self._get_similar_move_lines() if l.pk != self.pk]
            if self.lot_name:
                cuenta = Counter([l.lot_name for l in otras])
                if cuenta.get(self.lot_name, 0) > 1:
                    mensaje = _('You cannot use the same serial number twice. '
                                'Please correct the serial numbers encoded.')
                elif self.lot is None:
                    lot_model = apps.get_model('stock', 'StockLot')
                    quant_model = apps.get_model('stock', 'StockQuant')
                    lotes = lot_model.objects.filter(
                        expression.AND([
                            Q(product=self.product, name=self.lot_name),
                            Q(company__isnull=True) | Q(company=self.company),
                        ]))
                    quants = quant_model.objects.filter(
                        lot__in=lotes,
                        location__usage__in=['customer', 'internal', 'transit'],
                    ).exclude(quantity=0)
                    if quants.exists():
                        mensaje = _(
                            'Serial number (%(serial_number)s) already exists in '
                            'location(s): %(location_list)s. Please correct the '
                            'serial number encoded.',
                            serial_number=self.lot_name,
                            location_list=[str(q.location) for q in quants],
                        )
            elif self.lot is not None:
                cuenta = Counter([l.lot_id for l in otras])
                if cuenta.get(self.lot_id, 0) > 1:
                    mensaje = _('You cannot use the same serial number twice. '
                                'Please correct the serial numbers encoded.')
                else:
                    quant_model = apps.get_model('stock', 'StockQuant')
                    mensaje, recomendada = quant_model._check_serial_number(
                        self.product, self.lot, self.company, self.location,
                        self.picking.location if self.picking is not None else None)
                    if recomendada is not None:
                        self.location = recomendada
        if mensaje:
            res['warning'] = {'title': _('Warning'), 'message': mensaje}
        return res

    def _onchange_quantity(self):
        """≙ ``_onchange_quantity`` (``odoo19c: :243-251``).

        Un producto con número de serie sólo admite 1.0 — o 0, que es la forma
        de vaciar la línea.
        """
        if not self.quantity or self.tracking != 'serial':
            return {}
        uom = self.product.uom
        cantidad = float(self.quantity_product_uom)
        if uom.compare(cantidad, 1.0) != 0 and not uom.is_zero(cantidad):
            raise UserError(_(
                'You can only process 1.0 %s of products with unique serial number.',
                uom.name))
        return {}

    def _onchange_putaway_location(self):
        """≙ ``_onchange_putaway_location`` (``odoo19c: :253-260``).

        Propone el destino de la estrategia de colocación, pero sólo mientras
        la línea no exista y el destino siga siendo el de por defecto — si
        alguien ya lo cambió a mano, no lo pisa.
        """
        destino = self._get_default_dest_location()
        if self.pk or self.product is None or not self.quantity_product_uom:
            return
        if self.location_dest_id != getattr(destino, 'pk', None):
            return
        self.location_dest = destino._get_putaway_strategy(
            self.product, quantity=self.quantity_product_uom,
            package=self.result_package)

    # ------------------------------------------------------------------ #
    # Estrategia de colocación (≙ :262-311)                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _apply_putaway_strategy(cls, lines):
        """≙ ``_apply_putaway_strategy`` (``odoo19c: :262-292``).

        Tres caminos, y la referencia los mantiene separados a propósito:

        - **paquete con tipo** — todas las líneas van al sitio que la
          estrategia elige para *el paquete*, no para cada producto;
        - **paquete sin tipo** — se coloca producto por producto, pero si el
          reparto termina en más de una ubicación se deshace: un paquete no se
          parte entre sitios;
        - **sin paquete** — cada línea a donde su producto corresponda.
        """
        por_paquete = defaultdict(list)
        for line in lines:
            paquete = line.result_package
            raiz = paquete.outermost_package if paquete is not None else None
            por_paquete[getattr(raiz, 'pk', None)].append(line)

        for paquete_id, grupo in por_paquete.items():
            paquete = None
            if paquete_id is not None:
                paquete = apps.get_model('stock', 'StockPackage').objects.get(pk=paquete_id)
            excluidas = {l.pk for l in grupo if l.pk}

            if paquete is not None and paquete.package_type_id:
                base = grupo[0].move.location_dest if grupo[0].move is not None else None
                if base is None:
                    continue
                mejor = base._get_putaway_strategy(None, package=paquete,
                                                   exclude_sml_ids=excluidas)
                for line in grupo:
                    line.location_dest = mejor
                continue

            if paquete is not None:
                usadas = set()
                for line in grupo:
                    if len(usadas) > 1:
                        break
                    base = line.move.location_dest if line.move is not None else None
                    if base is None:
                        continue
                    propuesta = base._get_putaway_strategy(
                        line.product, quantity=line.quantity,
                        exclude_sml_ids=excluidas)
                    if propuesta is not None and propuesta.pk != line.location_dest_id:
                        line.location_dest = propuesta
                    excluidas.discard(line.pk)
                    usadas.add(line.location_dest_id)
                if len(usadas) > 1:
                    # El paquete no se parte: todas vuelven al destino del movimiento.
                    for line in grupo:
                        if line.move is not None:
                            line.location_dest = line.move.location_dest
                continue

            for line in grupo:
                base = line.move.location_dest if line.move is not None else None
                if base is None:
                    continue
                propuesta = base._get_putaway_strategy(
                    line.product, quantity=line.quantity,
                    exclude_sml_ids=excluidas)
                if propuesta is not None and propuesta.pk != line.location_dest_id:
                    line.location_dest = propuesta
                excluidas.discard(line.pk)

    def _get_default_dest_location(self):
        """≙ ``_get_default_dest_location`` (``odoo19c: :294-299``).

        Sin multi-ubicación la respuesta es el propio destino de la línea; con
        multi-ubicación gana el del movimiento, luego el del albarán.
        """
        movimiento, albaran = self.move, self.picking
        return (
            (getattr(movimiento, 'location_dest', None) if movimiento is not None else None)
            or (getattr(albaran, 'location_dest', None) if albaran is not None else None)
            or self.location_dest
        )

    @classmethod
    def _get_putaway_additional_qty(cls, lines):
        """≙ ``_get_putaway_additional_qty`` (``odoo19c: :301-306``).

        Devuelve, por ubicación de destino, la cantidad que estas líneas ya
        comprometieron — **en negativo**, porque la estrategia la resta del
        espacio libre que calcula.
        """
        adicional = {}
        for line in lines:
            if line.product_uom is None or line.product is None:
                continue
            cantidad = line.product_uom.compute_quantity(
                float(line.quantity), line.product.uom)
            clave = line.location_dest_id
            adicional[clave] = adicional.get(clave, 0) - cantidad
        return adicional

    # ------------------------------------------------------------------ #
    # Emparejamiento línea ↔ quant (≙ :308-341)                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def get_move_line_quant_match(cls, move_id, dirty_move_line_ids, dirty_quant_ids):
        """≙ ``get_move_line_quant_match`` (``odoo19c: :308-341``).

        ``quant_id`` no se almacena ni se calcula, así que el cliente necesita
        que alguien le diga qué quant corresponde a cada línea editada. Este
        método lo resuelve del lado del servidor: busca los quants que casan
        con las cinco características de cada línea sucia y devuelve las dos
        listas que el cliente refresca.
        """
        move_model = apps.get_model('stock', 'StockMove')
        quant_model = apps.get_model('stock', 'StockQuant')
        movimiento = move_model.objects.get(pk=move_id)
        sucias = list(cls.objects.filter(pk__in=dirty_move_line_ids))
        vivas_ids = {l.pk for l in cls.objects.filter(move=movimiento)}
        borradas = list(cls.objects.filter(
            pk__in=vivas_ids - set(dirty_move_line_ids)))

        # ≙ ``Domain("id","in",…) | Domain.OR(…)`` (``:315-324``) — el espejo
        # del proyecto es ``osv.expression``.
        ramas = [
            Q(product_id=l.product_id, lot_id=l.lot_id, location_id=l.location_id,
              package_id=l.package_id, owner_id=l.owner_id)
            for l in (sucias + borradas)
        ]
        filtro = Q(pk__in=list(dirty_quant_ids))
        if ramas:
            filtro = expression.OR([filtro, expression.OR(ramas)])

        quants_data, move_lines_data = [], []
        for quant in quant_model.objects.filter(filtro):
            def _casa(linea):
                return (linea.product_id == quant.product_id
                        and linea.lot_id == quant.lot_id
                        and linea.location_id == quant.location_id
                        and linea.package_id == quant.package_id
                        and linea.owner_id == quant.owner_id)

            de_sucias = [l for l in sucias if _casa(l)]
            de_borradas = [l for l in borradas if _casa(l)]
            disponible = quant.available_qty(quant.product, quant.location)
            quants_data.append((quant.pk, {
                'available_quantity': disponible + sum(
                    l.quantity_product_uom for l in de_borradas),
                'move_line_ids': [l.pk for l in de_sucias],
            }))
            move_lines_data += [
                (l.pk, {'quantity': l.quantity, 'quant_id': quant.pk})
                for l in de_sucias
            ]
        return [quants_data, move_lines_data]

    # ------------------------------------------------------------------ #
    # CRUD (≙ :343-559)                                                    #
    # ------------------------------------------------------------------ #

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :343-419``).

        Cuatro trabajos, en el orden de la referencia:

        1. hereda empresa y ``picked`` del movimiento o del albarán;
        2. si la línea nació suelta sobre un albarán, la engancha a un
           movimiento existente — o crea uno (``create_move``);
        3. reserva la existencia de las líneas que no puentean la reserva;
        4. si la línea nace ya terminada, **mueve** el quant en vez de
           reservarlo, y reasigna los movimientos encadenados.
        """
        move_model = apps.get_model('stock', 'StockMove')
        quant_model = apps.get_model('stock', 'StockQuant')

        for vals in vals_list:
            if vals.get('move_id'):
                movimiento = move_model.objects.get(pk=vals['move_id'])
                vals['company_id'] = movimiento.company_id
                if 'picked' not in vals:
                    vals['picked'] = movimiento.picked
            elif vals.get('picking_id'):
                albaran = apps.get_model('stock', 'StockPicking').objects.get(
                    pk=vals['picking_id'])
                vals['company_id'] = albaran.company_id
            if vals.get('quant_id'):
                vals.update(cls._copy_quant_info(vals))

        mls = [cls.objects.create(**vals) for vals in vals_list]
        created_moves = set()

        def create_move(move_line):
            """≙ la closure ``create_move`` (``odoo19c: :356-359``)."""
            nuevo = move_model.objects.create(**move_line._prepare_stock_move_vals())
            move_line.move = nuevo
            move_line.save()
            created_moves.add(nuevo.pk)

        for move_line in mls:
            if move_line.move_id or not move_line.picking_id:
                continue
            if move_line.picking.state != 'done':
                candidatos = move_line._get_linkable_moves()
                if candidatos:
                    move_line.move = candidatos[0]
                    move_line.picking = candidatos[0].picking
                    if candidatos[0].picked:
                        move_line.picked = True
                    move_line.save()
                else:
                    create_move(move_line)
            else:
                create_move(move_line)

        move_to_recompute_state = set()
        for move_line in mls:
            if move_line.state == 'done':
                continue
            movimiento = move_line.move
            if movimiento is not None:
                reserva = not movimiento._should_bypass_reservation()
            else:
                reserva = (getattr(move_line.product, 'is_storable', True)
                           and not move_line.location.should_bypass_reservation())
            if move_line.quantity_product_uom and reserva:
                quant_model._update_reserved_quantity(
                    move_line.product, move_line.location,
                    move_line.quantity_product_uom, lot_id=move_line.lot,
                    package_id=move_line.package, owner_id=move_line.owner)
                if movimiento is not None:
                    move_to_recompute_state.add(movimiento.pk)

        for movimiento in move_model.objects.filter(pk__in=move_to_recompute_state):
            movimiento._recompute_state()
        for movimiento in move_model.objects.filter(pk__in=created_moves):
            movimiento._post_process_created_moves()

        for ml in mls:
            if ml.state != 'done':
                continue
            if getattr(ml.product, 'is_storable', True):
                cantidad = Decimal(str(ml.product_uom.compute_quantity(
                    float(ml.quantity), ml.product.uom, rounding_method='HALF-UP')))
                disponible, in_date = quant_model._update_available_quantity(
                    ml.product, ml.location, -cantidad, lot_id=ml.lot,
                    package_id=ml.package, owner_id=ml.owner)
                if disponible < 0 and ml.lot is not None:
                    # Compensar el quant negativo con existencia sin lote.
                    sin_lote = quant_model._get_available_quantity(
                        ml.product, ml.location, lot_id=None,
                        package_id=ml.package, owner_id=ml.owner, strict=True)
                    if sin_lote:
                        tomado = min(sin_lote, abs(cantidad))
                        quant_model._update_available_quantity(
                            ml.product, ml.location, -tomado, lot_id=None,
                            package_id=ml.package, owner_id=ml.owner)
                        quant_model._update_available_quantity(
                            ml.product, ml.location, tomado, lot_id=ml.lot,
                            package_id=ml.package, owner_id=ml.owner)
                quant_model._update_available_quantity(
                    ml.product, ml.location_dest, cantidad, lot_id=ml.lot,
                    package_id=ml.result_package, owner_id=ml.owner, in_date=in_date)
            siguientes = [
                m for m in ml.move.move_dest_ids.all()
                if m.state not in TERMINAL_STATES
            ] if ml.move is not None else []
            for m in siguientes:
                m._do_unreserve()
                m._action_assign()

        terminadas = {ml.move for ml in mls if ml.state == 'done' and ml.move is not None}
        for movimiento in terminadas:
            movimiento._check_quantity()
        return mls

    @classmethod
    def write(cls, lines, vals):
        """≙ ``write`` (``odoo19c: :421-546``).

        El trabajo real no es escribir los campos: es **mantener los quants en
        sincronía**. Tocar origen, lote, paquete, propietario o cantidad de una
        línea reservada obliga a devolver la reserva vieja y tomar la nueva; y
        editar una línea ya terminada obliga a deshacer el movimiento del quant
        y rehacerlo, además de reasignar lo que venía encadenado.
        """
        lines = list(lines)
        if 'product_id' in vals and any(
                vals.get('state', l.state) != 'draft'
                and vals['product_id'] != l.product_id for l in lines):
            raise UserError(_("Changing the product is only allowed in 'Draft' state."))
        if ('lot_id' in vals or 'quant_id' in vals) and len({l.product_id for l in lines}) > 1:
            raise UserError(_("Changing the Lot/Serial number for move lines with "
                              "different products is not allowed."))

        package_model = apps.get_model('stock', 'StockPackage')
        paquetes_a_revisar = []
        if 'result_package_id' in vals:
            ids = set()
            for l in lines:
                if l.result_package is not None:
                    ids.update(l.result_package.get_all_package_dest_ids())
            paquetes_a_revisar = list(package_model.objects.filter(pk__in=ids))

        triggers = [
            ('location_id', ('stock', 'StockLocation'), 'location'),
            ('location_dest_id', ('stock', 'StockLocation'), 'location_dest'),
            ('lot_id', ('stock', 'StockLot'), 'lot'),
            ('package_id', ('stock', 'StockPackage'), 'package'),
            ('result_package_id', ('stock', 'StockPackage'), 'result_package'),
            ('owner_id', ('base', 'ResPartner'), 'owner'),
            ('product_uom_id', ('uom', 'Uom'), 'product_uom'),
        ]
        if vals.get('quant_id'):
            vals.update(cls._copy_quant_info(vals))

        updates = {}
        for clave, (app_label, modelo), atributo in triggers:
            if clave in vals:
                valor = vals[clave]
                updates[atributo] = (
                    valor if isinstance(valor, models.Model)
                    else apps.get_model(app_label, modelo).objects.get(pk=valor)
                )

        moves_to_recompute_state = set()
        # Reservar de nuevo con las características nuevas.
        if (updates and {'result_package'}.difference(updates.keys())) or 'quantity' in vals:
            for ml in lines:
                if not getattr(ml.product, 'is_storable', True) or ml.state == 'done':
                    continue
                if 'quantity' in vals or 'product_uom_id' in vals:
                    nueva_uom = updates.get('product_uom', ml.product_uom)
                    nueva_reserva = Decimal(str(nueva_uom.compute_quantity(
                        float(vals.get('quantity', ml.quantity)), ml.product.uom,
                        rounding_method='HALF-UP')))
                    if ml.product.uom.compare(float(nueva_reserva), 0) < 0:
                        raise UserError(_('Reserving a negative quantity is not allowed.'))
                else:
                    nueva_reserva = ml.quantity_product_uom

                if not ml.product_uom.is_zero(float(ml.quantity_product_uom)):
                    ml._synchronize_quant(-ml.quantity_product_uom, ml.location,
                                          action='reserved')
                origen = updates.get('location', ml.location)
                if ml.move is None or not ml.move._should_bypass_reservation(origen):
                    ml._synchronize_quant(
                        nueva_reserva, origen, action='reserved',
                        lot=updates.get('lot', ml.lot),
                        package=updates.get('package', ml.package),
                        owner=updates.get('owner', ml.owner))
                if (('quantity' in vals and vals['quantity'] != ml.quantity)
                        or 'product_uom_id' in vals):
                    if ml.move is not None:
                        moves_to_recompute_state.add(ml.move.pk)

        # Editar una línea terminada: deshacer y rehacer el movimiento del quant.
        mls = []
        siguientes = set()
        if updates or 'quantity' in vals:
            mls = [l for l in lines
                   if l.move is not None and l.move.state == 'done'
                   and getattr(l.product, 'is_storable', True)]
            if not updates:
                mls = [l for l in mls
                       if not l.product_uom.is_zero(float(l.quantity - vals['quantity']))]
            for ml in mls:
                in_date = ml._synchronize_quant(
                    -ml.quantity_product_uom, ml.location_dest,
                    package=ml.result_package)[1]
                ml._synchronize_quant(ml.quantity_product_uom, ml.location,
                                      in_date=in_date)
                siguientes.update(
                    m.pk for m in ml.move.move_dest_ids.all()
                    if m.state not in TERMINAL_STATES)
                if ml.picking is not None:
                    ml._log_message(ml.picking, ml, 'stock.track_move_template', vals)
            for movimiento in {l.move for l in mls}:
                movimiento._check_quantity()

        # La fecha se refresca cuando la cantidad sube o la línea se toma.
        if 'date' not in vals and ('product_uom_id' in vals or 'quantity' in vals
                                   or vals.get('picked', False)):
            a_refrescar = set()
            for ml in lines:
                if ml.state in ('draft', 'cancel', 'done'):
                    continue
                if vals.get('picked', False) and not ml.picked:
                    a_refrescar.add(ml.pk)
                    continue
                if ('quantity' in vals or 'product_uom_id' in vals) and ml.picked:
                    uom = updates.get('product_uom', ml.product_uom)
                    nueva = uom.compute_quantity(
                        float(vals.get('quantity', ml.quantity)), ml.product.uom,
                        rounding_method='HALF-UP')
                    vieja = ml.product_uom.compute_quantity(
                        float(ml.quantity), ml.product.uom, rounding_method='HALF-UP')
                    if ml.product_uom.compare(vieja, nueva) < 0:
                        a_refrescar.add(ml.pk)
            cls.objects.filter(pk__in=a_refrescar).update(date=timezone.now())

        for ml in lines:
            for clave, valor in vals.items():
                atributo = clave.removesuffix('_id')
                if atributo in updates:
                    # El FK ya se resolvió a instancia en `triggers`.
                    setattr(ml, atributo, updates[atributo])
                elif hasattr(ml, clave):
                    setattr(ml, clave, valor)
            ml.save()

        for ml in mls:
            disponible, _sin_uso = ml._synchronize_quant(
                -ml.quantity_product_uom, ml.location)
            ml._synchronize_quant(ml.quantity_product_uom, ml.location_dest,
                                  package=ml.result_package)
            if disponible < 0:
                ml._free_reservation(
                    ml.product, ml.location, abs(disponible), lot_id=ml.lot,
                    package_id=ml.package, owner_id=ml.owner)

        for paquete in paquetes_a_revisar:
            if paquete.package_dest_id and not paquete.picking_ids:
                paquete.package_dest = None
                paquete.save()

        if updates or 'quantity' in vals:
            fuera_de_pack = cls._get_lines_not_entire_pack(lines)
            if fuera_de_pack:
                cls.objects.filter(pk__in=[l.pk for l in fuera_de_pack]).update(
                    is_entire_pack=False)
            move_model = apps.get_model('stock', 'StockMove')
            for movimiento in move_model.objects.filter(pk__in=siguientes):
                movimiento._do_unreserve()
                movimiento._action_assign()

        if moves_to_recompute_state:
            move_model = apps.get_model('stock', 'StockMove')
            for movimiento in move_model.objects.filter(pk__in=moves_to_recompute_state):
                movimiento._recompute_state()
        return lines

    @classmethod
    def _unlink_except_done_or_cancel(cls, lines):
        """≙ ``_unlink_except_done_or_cancel`` (``odoo19c: :548-555``)."""
        for ml in lines:
            if ml.state in TERMINAL_STATES:
                raise UserError(_(
                    "Deleting product moves after the transfer is done?\n\n"
                    "That would be like going back in time to revert all operations "
                    "triggered after this move. Who knows what the end result would "
                    "be, So let's not do it.\n\n"
                    "Try changing the “done” quantity to 0 instead."))

    @classmethod
    def unlink(cls, lines):
        """≙ ``unlink`` (``odoo19c: :557-575``).

        Borrar una línea **libera su reserva**: si no lo hiciera, la existencia
        quedaría comprometida con una línea que ya no existe.
        """
        lines = list(lines)
        cls._unlink_except_done_or_cancel(lines)
        quant_model = apps.get_model('stock', 'StockQuant')
        package_model = apps.get_model('stock', 'StockPackage')

        for ml in lines:
            if (ml.quantity_product_uom and ml.move is not None
                    and not ml.move._should_bypass_reservation(ml.location)):
                quant_model._update_reserved_quantity(
                    ml.product, ml.location, -ml.quantity_product_uom,
                    lot_id=ml.lot, package_id=ml.package, owner_id=ml.owner,
                    strict=True)

        movimientos = {l.move for l in lines if l.move is not None}
        ids_paquete = set()
        for l in lines:
            if l.result_package is not None:
                ids_paquete.update(l.result_package.get_all_package_dest_ids())
        paquetes = list(package_model.objects.filter(pk__in=ids_paquete))

        res = cls.objects.filter(pk__in=[l.pk for l in lines]).delete()

        for movimiento in movimientos:
            movimiento._recompute_state()
        for paquete in paquetes:
            if paquete.package_dest_id and not paquete.picking_ids:
                paquete.package_dest = None
                paquete.save()
        return res

    # ------------------------------------------------------------------ #
    # Validación del movimiento (≙ :577-905)                               #
    # ------------------------------------------------------------------ #

    def _exclude_requiring_lot(self):
        """≙ ``_exclude_requiring_lot`` (``odoo19c: :577-579``).

        Cuatro situaciones eximen a una línea rastreada de exigir lote: viene
        de un tipo de operación, es un ajuste de inventario, ya lo tiene, o es
        un desecho.
        """
        movimiento = self.move
        if movimiento is None:
            return False
        return bool(getattr(movimiento, 'picking_type_id', None)
                    or self.is_inventory
                    or self.lot_id
                    or getattr(movimiento, 'scrap_id', None))

    @classmethod
    def _action_done(cls, lines, ignore_dest_packages=False):
        """≙ ``_action_done`` (``odoo19c: :581-887``).

        Es el método que **mueve la existencia**. Dos mitades:

        1. **Chequeo previo** — la cantidad respeta el redondeo de su unidad,
           no es negativa, y el producto rastreado tiene lote (creándolo si el
           tipo de operación lo permite). Las líneas en cero se borran: sin eso
           su reserva quedaría colgada.
        2. **El movimiento del quant** — por cada línea: devuelve la reserva
           del origen, descuenta del origen, suma al destino. Si al descontar
           el saldo queda negativo, se llevó existencia que otra línea tenía
           reservada, y hay que liberársela (``_free_reservation``).
        """
        lines = list(lines)
        quant_model = apps.get_model('stock', 'StockQuant')
        lot_model = apps.get_model('stock', 'StockLot')

        sin_lote, a_borrar, a_crear_lote = [], [], []
        a_revisar = defaultdict(list)

        uom_model = apps.get_model('uom', 'Uom')
        for ml in lines:
            # Dos redondeos distintos, y ahí está el chequeo: el de la unidad
            # de la línea contra el de la precisión decimal 'Product Unit'. Si
            # discrepan, la cantidad no cabe en la unidad que se declaró.
            uom_qty = ml.product_uom.round(float(ml.quantity), rounding_method='HALF-UP')
            digitos = uom_model._precision_digits()
            cantidad = round(float(ml.quantity), digitos)
            if ml.product_uom.compare(uom_qty, cantidad) != 0:
                raise UserError(_(
                    'The quantity done for the product "%(product)s" doesn\'t respect '
                    'the rounding precision defined on the unit of measure "%(unit)s". '
                    'Please change the quantity done or the rounding precision of your '
                    'unit of measure.',
                    product=str(ml.product), unit=ml.product_uom.name))

            comparada = ml.product_uom.compare(float(ml.quantity), 0)
            if comparada > 0:
                if ml.tracking == 'none':
                    continue
                tipo = getattr(ml.move, 'picking_type', None) if ml.move is not None else None
                if not ml._exclude_requiring_lot():
                    sin_lote.append(ml)
                    continue
                if (tipo is None or ml.lot_id
                        or (not tipo.use_create_lots and not tipo.use_existing_lots)):
                    # El tipo desactivó las dos casillas: se admite sin lote.
                    continue
                if tipo.use_create_lots:
                    a_revisar[(ml.product_id, ml.company_id)].append(ml)
                else:
                    sin_lote.append(ml)
            elif comparada < 0:
                raise UserError(_('No negative quantities allowed'))
            elif not ml.is_inventory:
                a_borrar.append(ml)

        for (product_id, company_id), grupo in a_revisar.items():
            lotes = {
                lote.name: lote
                for lote in lot_model.objects.filter(
                    expression.AND([
                        Q(product_id=product_id,
                          name__in=[l.lot_name for l in grupo if l.lot_name]),
                        Q(company__isnull=True) | Q(company_id=company_id),
                    ]))
            }
            for ml in grupo:
                lote = lotes.get(ml.lot_name)
                if lote is not None:
                    ml.lot = lote
                    ml.save()
                elif ml.lot_name:
                    a_crear_lote.append(ml)
                else:
                    sin_lote.append(ml)

        if sin_lote:
            productos = "\n".join(f"- {ml.product}" for ml in sin_lote)
            raise UserError(_(
                "You need to supply a Lot/Serial Number for product:\n%(products)s",
                products=productos))
        if a_crear_lote:
            cls._create_and_assign_production_lot(a_crear_lote)

        if a_borrar:
            cls.unlink(a_borrar)
        pendientes = [l for l in lines if l not in a_borrar]

        ids_a_ignorar = set()
        if not ignore_dest_packages:
            vals_historial = cls._prepare_package_history_vals(pendientes)
            if vals_historial:
                historial_model = apps.get_model('stock', 'StockPackageHistory')
                for vals in vals_historial:
                    historial_model.objects.create(**vals)

        for ml in pendientes:
            # Si la línea se forzó, hay que des-reservar en otro sitio.
            ml._synchronize_quant(-ml.quantity_product_uom, ml.location,
                                  action='reserved')
            disponible, in_date = ml._synchronize_quant(
                -ml.quantity_product_uom, ml.location)
            ml._synchronize_quant(ml.quantity_product_uom, ml.location_dest,
                                  package=ml.result_package, in_date=in_date)
            if disponible < 0:
                ml._free_reservation(
                    ml.product, ml.location, abs(disponible), lot_id=ml.lot,
                    package_id=ml.package, owner_id=ml.owner,
                    ml_ids_to_ignore=ids_a_ignorar)
            ids_a_ignorar.add(ml.pk)

        if not ignore_dest_packages:
            for ml in pendientes:
                if ml.result_package is not None:
                    ml.result_package.apply_dest_to_package()

        cls.objects.filter(pk__in=[l.pk for l in pendientes]).update(date=timezone.now())
        return pendientes

    def _synchronize_quant(self, quantity, location, action='available',
                           in_date=None, **quants_value):
        """≙ ``_synchronize_quant`` (``odoo19c: :889-910``).

        ``quantity`` viene **en la unidad del producto**, no en la de la línea
        — es la única precondición del método y la referencia la deja escrita
        en su docstring de una línea.

        Dos acciones: ``available`` mueve la existencia; ``reserved`` sólo
        compromete, y se salta si la ubicación puentea la reserva. Cuando el
        saldo del lote queda negativo, compensa con la existencia sin lote de
        la misma ubicación — sin eso el negativo quedaría anclado al lote.
        """
        quant_model = apps.get_model('stock', 'StockQuant')
        lote = quants_value.get('lot', self.lot)
        paquete = quants_value.get('package', self.package)
        propietario = quants_value.get('owner', self.owner)
        disponible = 0

        if not getattr(self.product, 'is_storable', True):
            return 0, False
        if self.product_uom.is_zero(float(quantity)):
            return 0, False

        if action == 'available':
            disponible, in_date = quant_model._update_available_quantity(
                self.product, location, quantity, lot_id=lote,
                package_id=paquete, owner_id=propietario, in_date=in_date)
        elif action == 'reserved':
            if self.move is None or not self.move._should_bypass_reservation(location):
                quant_model._update_reserved_quantity(
                    self.product, location, quantity, lot_id=lote,
                    package_id=paquete, owner_id=propietario)

        if disponible < 0 and lote is not None:
            sin_lote = quant_model._get_available_quantity(
                self.product, location, lot_id=None, package_id=paquete,
                owner_id=propietario, strict=True)
            if not sin_lote:
                return disponible, in_date
            tomado = min(sin_lote, abs(quantity))
            quant_model._update_available_quantity(
                self.product, location, -tomado, lot_id=None,
                package_id=paquete, owner_id=propietario, in_date=in_date)
            quant_model._update_available_quantity(
                self.product, location, tomado, lot_id=lote,
                package_id=paquete, owner_id=propietario, in_date=in_date)
        return disponible, in_date

    def _get_similar_move_lines(self):
        """≙ ``_get_similar_move_lines`` (``odoo19c: :912-918``).

        Las líneas del mismo albarán con el mismo producto y algún lote — el
        conjunto sobre el que se detecta un número de serie repetido.
        """
        albaran = (self.move.picking if self.move is not None else None) or self.picking
        if albaran is None:
            return type(self).objects.none()
        return type(self).objects.filter(
            picking=albaran, product_id=self.product_id,
        ).filter(Q(lot__isnull=False) | ~Q(lot_name=''))

    def _prepare_new_lot_vals(self):
        """≙ ``_prepare_new_lot_vals`` (``odoo19c: :920-928``).

        El lote sólo lleva empresa cuando el producto es de una empresa y la
        línea pertenece a ella o a una hija — si no, queda global.
        """
        vals = {'name': self.lot_name, 'product_id': self.product_id}
        product_company = getattr(self.product, 'company', None)
        if product_company is not None:
            hijas = {product_company.pk}
            hijas.update(getattr(product_company, 'all_child_ids', []) or [])
            if self.company_id in hijas:
                vals['company_id'] = self.company_id
        return vals

    @classmethod
    def _create_and_assign_production_lot(cls, lines):
        """≙ ``_create_and_assign_production_lot`` (``odoo19c: :930-949``).

        Un mismo ``lot_name`` puede repetirse en varias líneas. Para un lote se
        crea **uno** y se comparte; para una serie se crea uno por línea —
        que es exactamente lo que distingue el ``if ml.tracking != 'lot'`` de
        la referencia.
        """
        lot_model = apps.get_model('stock', 'StockLot')
        indice_por_clave = {}
        lineas_por_clave = defaultdict(list)
        lots_vals = []

        for ml in lines:
            clave = (ml.product_id, ml.lot_name)
            lineas_por_clave[clave].append(ml)
            if ml.tracking != 'lot' or clave not in indice_por_clave:
                indice_por_clave[clave] = len(lots_vals)
                lots_vals.append(ml._prepare_new_lot_vals())

        lotes = [lot_model.objects.create(**vals) for vals in lots_vals]
        for clave, grupo in lineas_por_clave.items():
            lote = lotes[indice_por_clave[clave]]
            cls.objects.filter(pk__in=[l.pk for l in grupo]).update(lot=lote)
        return lotes

    def _log_message(self, record, move, template, vals):
        """≙ ``_log_message`` (``odoo19c: :951-970``).

        **Divergencia D-1 declarada** (ver el docstring del módulo): el mensaje
        se arma con el mismo diff que la referencia —lote, ubicaciones, los dos
        paquetes y propietario, sólo cuando cambian— y se **devuelve**; quién
        lo publica es de la familia ``mail``, no de este modelo.
        """
        data = dict(vals)
        if 'lot_id' in vals and vals['lot_id'] != move.lot_id:
            lote = apps.get_model('stock', 'StockLot').objects.filter(
                pk=vals.get('lot_id')).first()
            data['lot_name'] = getattr(lote, 'name', None)
        location_model = apps.get_model('stock', 'StockLocation')
        if 'location_id' in vals:
            origen = location_model.objects.filter(pk=vals.get('location_id')).first()
            data['location_name'] = str(origen) if origen is not None else None
        if 'location_dest_id' in vals:
            destino = location_model.objects.filter(pk=vals.get('location_dest_id')).first()
            data['location_dest_name'] = str(destino) if destino is not None else None
        package_model = apps.get_model('stock', 'StockPackage')
        if 'package_id' in vals and vals['package_id'] != move.package_id:
            paquete = package_model.objects.filter(pk=vals.get('package_id')).first()
            data['package_name'] = getattr(paquete, 'name', None)
        if ('package_result_id' in vals
                and vals['package_result_id'] != move.result_package_id):
            paquete = package_model.objects.filter(
                pk=vals.get('result_package_id')).first()
            data['result_package_dest_name'] = getattr(paquete, 'name', None)
        if 'owner_id' in vals and vals['owner_id'] != move.owner_id:
            propietario = apps.get_model('base', 'ResPartner').objects.filter(
                pk=vals.get('owner_id')).first()
            data['owner_name'] = str(propietario) if propietario is not None else None
        return {
            'record': record,
            'template': template,
            'render_values': {'move': move, 'vals': data},
            'subtype_xmlid': 'mail.mt_note',
        }

    def _free_reservation(self, product_id, location_id, quantity, lot_id=None,
                          package_id=None, owner_id=None, ml_ids_to_ignore=None):
        """≙ ``_free_reservation`` (``odoo19c: :972-1043``).

        Al editar o validar una línea con cantidad forzada se puede tocar
        existencia que **otra** línea tenía reservada. Este método le quita esa
        reserva a las líneas afectadas — recortándoles la cantidad, o
        borrándolas si se quedan sin nada.

        El orden importa y la referencia lo fija: primero el albarán en curso,
        luego los de fecha planeada más lejana. Así el recorte cae sobre lo que
        se entrega más tarde.
        """
        if ml_ids_to_ignore is None:
            ml_ids_to_ignore = set()
        ml_ids_to_ignore = set(ml_ids_to_ignore) | {self.pk}

        if self.move is not None and self.move._should_bypass_reservation(location_id):
            return

        candidatos = type(self).objects.filter(
            expression.AND([
                ~Q(state__in=TERMINAL_STATES),
                Q(product_id=getattr(product_id, 'pk', product_id)),
                Q(lot_id=getattr(lot_id, 'pk', None)),
                Q(location_id=getattr(location_id, 'pk', location_id)),
                Q(owner_id=getattr(owner_id, 'pk', None)),
                Q(package_id=getattr(package_id, 'pk', None)),
                Q(quantity_product_uom__gt=0),
                Q(picked=False),
                ~Q(pk__in=tuple(ml_ids_to_ignore)),
            ]))

        mi_albaran = self.move.picking if self.move is not None else None

        def current_picking_first(cand):
            """≙ la closure ``current_picking_first`` (``odoo19c: :1012-1018``)."""
            fecha = None
            if cand.picking is not None:
                fecha = getattr(cand.picking, 'scheduled_date', None)
            if fecha is None and cand.move is not None:
                fecha = getattr(cand.move, 'date', None)
            return (
                cand.picking != mi_albaran,
                -fecha.timestamp() if fecha is not None else 0,
                -cand.pk,
            )

        move_model = apps.get_model('stock', 'StockMove')
        a_reasignar = set()
        a_borrar = set()

        for candidato in sorted(candidatos, key=current_picking_first):
            if candidato.move is not None:
                a_reasignar.add(candidato.move.pk)
            if self.product_uom.compare(
                    float(candidato.quantity_product_uom), float(quantity)) <= 0:
                quantity -= candidato.quantity_product_uom
                a_borrar.add(candidato.pk)
                if self.product_uom.is_zero(float(quantity)):
                    break
            else:
                candidato.quantity -= Decimal(str(
                    candidato.product.uom.compute_quantity(
                        float(quantity), candidato.product_uom,
                        rounding_method='HALF-UP')))
                candidato.save()
                break

        a_desatar = list(type(self).objects.filter(pk__in=a_borrar))
        movimientos = {l.move.pk for l in a_desatar if l.move is not None} | a_reasignar
        for movimiento in move_model.objects.filter(pk__in=movimientos):
            movimiento.procure_method = 'make_to_stock'
            # ≙ ``'move_orig_ids': [Command.clear()]`` (``odoo19c: :1038``).
            fields.Command.clear(movimiento.move_orig_ids)
            movimiento.save()
        if a_desatar:
            type(self).unlink(a_desatar)
        for movimiento in reversed(list(move_model.objects.filter(pk__in=movimientos))):
            movimiento._action_assign()

    # ------------------------------------------------------------------ #
    # Agregación para reportes (≙ :1045-1170)                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_aggregated_properties(cls, move_line=False, move=False):
        """≙ ``_get_aggregated_properties`` (``odoo19c: :1045-1069``).

        Construye la **clave de agrupación** de una línea. La descripción se
        recorta cuando repite el nombre del producto, para que dos líneas
        equivalentes no caigan en grupos distintos por un prefijo redundante.
        """
        movimiento = move or (move_line.move if move_line else None)
        uom = (getattr(movimiento, 'product_uom', None)
               or (move_line.product_uom if move_line else None))
        packaging_uom = getattr(movimiento, 'packaging_uom', None)
        producto = movimiento.product if movimiento is not None else move_line.product
        nombre = str(producto)
        descripcion = getattr(movimiento, 'description_picking', '') or ''
        if descripcion.startswith(nombre):
            descripcion = descripcion.removeprefix(nombre).strip()
        elif descripcion.startswith(producto.name):
            descripcion = descripcion.removeprefix(producto.name).strip()

        line_key = (f'{producto.pk}_{nombre}_{descripcion or ""}_'
                    f'{getattr(uom, "pk", 0)}_{getattr(packaging_uom, "pk", 0)}')
        propiedades = {
            'line_key': line_key,
            'name': nombre,
            'description': descripcion,
            'product_uom': uom,
            'packaging_uom_id': packaging_uom,
            'move': movimiento,
        }
        if move_line and move_line.result_package is not None:
            propiedades['package'] = move_line.result_package
            propiedades['package_history'] = move_line.package_history
            propiedades['line_key'] += f'_{move_line.result_package_id}'
        return propiedades

    @classmethod
    def _get_aggregated_product_quantities(cls, lines, **kwargs):
        """≙ ``_get_aggregated_product_quantities`` (``odoo19c: :1071-1160``).

        Agrupa por producto+descripción+unidad para el albarán de entrega.
        Ignora lotes a propósito —ya vienen agrupados por línea— y suma a la
        cantidad *pedida* lo que se difirió a los pedidos pendientes, para que
        el documento muestre el pedido original y no el trozo entregado.
        """
        lines = list(lines)
        agregadas = {}
        picking_model = apps.get_model('stock', 'StockPicking')

        pendientes = set()
        actuales = {l.picking for l in lines if l.picking is not None}
        while actuales:
            siguientes = set()
            for albaran in actuales:
                for atrasado in getattr(albaran, 'backorder_ids', picking_model.objects.none()):
                    siguientes.add(atrasado)
            pendientes |= siguientes
            actuales = siguientes

        for move_line in lines:
            if kwargs.get('except_package') and move_line.result_package is not None:
                continue
            propiedades = cls._get_aggregated_properties(move_line=move_line)
            line_key, uom = propiedades['line_key'], propiedades['product_uom']
            cantidad = move_line.product_uom.compute_quantity(float(move_line.quantity), uom)
            packaging_uom = getattr(move_line.move, 'packaging_uom', None)
            cantidad_pack = uom.compute_quantity(cantidad, packaging_uom) if packaging_uom else 0

            if line_key not in agregadas:
                pedida = None
                pedida_pack = None
                if not kwargs.get('strict'):
                    pedida = move_line.move.product_uom_qty
                    if pendientes:
                        posteriores = cls.objects.filter(picking__in=pendientes)
                        pedida += sum(
                            l.move.product_uom_qty for l in posteriores
                            if line_key.startswith(
                                cls._get_aggregated_properties(move=l.move)['line_key']))
                    previas = cls.objects.filter(move=move_line.move).exclude(pk=move_line.pk)
                    pedida -= sum(
                        Decimal(str(l.product_uom.compute_quantity(float(l.quantity), uom)))
                        for l in previas
                        if line_key.startswith(
                            cls._get_aggregated_properties(move=l.move)['line_key']))
                    if packaging_uom:
                        pedida_pack = uom.compute_quantity(float(pedida), packaging_uom)
                agregadas[line_key] = {
                    **propiedades,
                    'quantity': cantidad,
                    'packaging_quantity': cantidad_pack,
                    'qty_ordered': pedida if pedida is not None else cantidad,
                    'packaging_qty_ordered': (
                        pedida_pack if pedida_pack is not None else cantidad_pack),
                    'product': move_line.product,
                }
            else:
                agregadas[line_key]['qty_ordered'] += cantidad
                agregadas[line_key]['packaging_qty_ordered'] += cantidad_pack
                agregadas[line_key]['quantity'] += cantidad
                agregadas[line_key]['packaging_quantity'] += cantidad_pack

        if kwargs.get('strict'):
            return agregadas

        # Los movimientos vacíos también aportan su cantidad pedida: al
        # validar parcialmente se parten y el trozo pendiente queda sin líneas.
        move_model = apps.get_model('stock', 'StockMove')
        albaranes = {l.picking for l in lines if l.picking is not None} | pendientes
        for empty_move in move_model.objects.filter(picking__in=albaranes):
            saltar = False
            if not (empty_move.product_uom_qty
                    and empty_move.product_uom.is_zero(float(empty_move.quantity))):
                continue
            if empty_move.state != 'cancel':
                if empty_move.state != 'confirmed' or empty_move.move_line_ids.exists():
                    continue
                saltar = True
            propiedades = cls._get_aggregated_properties(move=empty_move)
            line_key = propiedades['line_key']

            if not any(k.startswith(line_key) for k in agregadas) and not saltar:
                agregadas[line_key] = {
                    **propiedades,
                    'quantity': False,
                    'packaging_quantity': 0,
                    'packaging_qty_ordered': 0,
                    'qty_ordered': empty_move.product_uom_qty,
                    'product': empty_move.product,
                }
            elif line_key in agregadas:
                agregadas[line_key]['qty_ordered'] += empty_move.product_uom_qty
            else:
                coincidencias = [k for k in agregadas if k.startswith(line_key)]
                if coincidencias:
                    agregadas[coincidencias[0]]['qty_ordered'] += empty_move.product_uom_qty
        return agregadas

    def _compute_sale_price(self):
        """≙ ``_compute_sale_price`` (``odoo19c: :1162-1164``).

        «To Override» en la fuente: el precio de venta lo aporta ``sale_stock``,
        no ``stock``. Se porta como el punto de extensión que es.
        """
        return None

    # ------------------------------------------------------------------ #
    # Preparación de valores (≙ :1166-1025)                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _prepare_package_history_vals(cls, lines):
        """≙ ``_prepare_package_history_vals`` (``odoo19c: :1166-1187``).

        La instantánea se toma **antes** de mover nada: guarda dónde estaba
        cada paquete de destino y bajo qué padre, para que el historial no
        describa el estado posterior.
        """
        package_model = apps.get_model('stock', 'StockPackage')
        ids = set()
        for line in lines:
            if line.result_package is not None:
                ids.update(line.result_package.get_all_package_dest_ids())

        vals = []
        for paquete in package_model.objects.filter(pk__in=ids):
            propias = [l for l in lines if l.result_package_id == paquete.pk]
            vals.append({
                'location_id': paquete.location_id,
                'location_dest_id': getattr(paquete.location_dest, 'pk', None),
                # ≙ ``[Command.set(ids)]`` (``odoo19c: :1173-1174``). Aquí el
                # comando se aplica sobre un manager vivo, y estos son vals de
                # creación: se entregan los identificadores y el creador los
                # asigna tras insertar la fila.
                'move_line_ids': [l.pk for l in propias],
                'picking_ids': [p.pk for p in paquete.picking_ids],
                'package_id': paquete.pk,
                'package_name': paquete.complete_name,
                'parent_orig_id': paquete.parent_package_id,
                'parent_orig_name': getattr(paquete.parent_package, 'complete_name', None),
                'parent_dest_id': paquete.package_dest_id,
                'parent_dest_name': getattr(paquete.package_dest, 'dest_complete_name', None),
                'outermost_dest_id': getattr(paquete.outermost_package, 'pk', None),
            })
        return vals

    def _prepare_stock_move_vals(self):
        """≙ ``_prepare_stock_move_vals`` (``odoo19c: :1189-1204``).

        Los valores del movimiento que se crea cuando alguien captura una línea
        suelta sobre un albarán. La demanda va en **cero** salvo que el albarán
        ya esté terminado: la línea es el hecho, no el plan.
        """
        albaran = self.picking
        return {
            'product_id': self.product_id,
            'product_uom_qty': (
                0 if albaran is not None and albaran.state != 'done' else self.quantity),
            'product_uom': self.product_uom_id,
            'location_id': getattr(albaran, 'location_id', None),
            'location_dest_id': getattr(albaran, 'location_dest_id', None),
            'picked': self.picked,
            'picking_id': self.picking_id,
            'state': getattr(albaran, 'state', None),
            'picking_type_id': getattr(albaran, 'picking_type_id', None),
            'restrict_partner_id': getattr(albaran, 'owner_id', None),
            'company_id': getattr(albaran, 'company_id', None),
            'partner_id': getattr(albaran, 'partner_id', None),
        }

    @classmethod
    def _copy_quant_info(cls, vals):
        """≙ ``_copy_quant_info`` (``odoo19c: :1206-1215``).

        Elegir un quant fija las cinco características de la línea de golpe —
        producto, lote, paquete, ubicación y propietario.
        """
        quant_model = apps.get_model('stock', 'StockQuant')
        quant = quant_model.objects.filter(pk=vals.get('quant_id', 0)).first()
        if quant is None:
            return {}
        return {
            'product_id': quant.product_id,
            'lot_id': quant.lot_id,
            'package_id': quant.package_id,
            'location_id': quant.location_id,
            'owner_id': quant.owner_id,
        }

    def action_open_reference(self):
        """≙ ``action_open_reference`` (``odoo19c: :1217-1228``).

        **Divergencia D-2 declarada:** devuelve el descriptor de ventana, que
        es el contrato de datos; el cliente que lo consume no existe aquí.
        """
        if self.move is not None:
            accion = self.move.action_open_reference()
            if accion.get('res_model') != 'stock.move':
                return accion
        return {
            'res_model': self._name,
            'type': 'ir.actions.act_window',
            'views': [[False, 'form']],
            'res_id': self.pk,
        }

    # ------------------------------------------------------------------ #
    # Empaquetado (≙ :1230-1400)                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def _pre_put_in_pack_hook(cls, lines, all_lines=False, package_id=False,
                              package_type_id=False, package_name=False,
                              from_package_wizard=False):
        """≙ ``_pre_put_in_pack_hook`` (``odoo19c: :1230-1244``).

        Dos preguntas antes de empacar: ¿las líneas van a destinos distintos?
        (entonces hay que elegir uno) y ¿hace falta preguntar el tipo de
        paquete? Cualquiera de las dos devuelve un descriptor de ventana y
        aborta el empaque — divergencia D-2.
        """
        move_lines = all_lines if all_lines else lines
        accion = cls._check_destinations(move_lines)
        if accion:
            return accion
        if cls._should_display_put_in_pack_wizard(lines, package_id, package_type_id,
                                                  package_name, from_package_wizard):
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.package.destination',
                'xml_id': 'stock.action_put_in_pack_wizard',
                'context': {
                    'all_move_line_ids': [l.pk for l in move_lines],
                    'default_move_line_ids': [l.pk for l in lines],
                    'default_location_dest_id': lines[0].location_dest_id if lines else None,
                    'picking_ids': list({l.picking_id for l in move_lines
                                         if l.picking_id}),
                },
            }
        return None

    @classmethod
    def _check_destinations(cls, lines):
        """≙ ``_check_destinations`` (``odoo19c: :1246-1262``).

        Si las líneas apuntan a más de un destino no se puede empacar sin
        decidir cuál — la referencia abre el asistente
        ``stock.package.destination``. Divergencia D-2: se devuelve el
        descriptor.
        """
        lines = list(lines)
        destinos = {l.location_dest_id for l in lines}
        if len(destinos) <= 1:
            return None
        return {
            'name': _('Choose destination location'),
            'view_mode': 'form',
            'res_model': 'stock.package.destination',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_move_line_ids': [l.pk for l in lines],
                'default_location_dest_id': lines[0].location_dest_id,
            },
        }

    @classmethod
    def _get_lines_not_entire_pack(cls, lines):
        """≙ ``_get_lines_not_entire_pack`` (``odoo19c: :1264-1278``).

        Una línea deja de ser «paquete completo» si su paquete de destino ya no
        es el de origen, o si el albarán dejó de contener el paquete entero.
        """
        lines = list(lines)
        relevantes = [l for l in lines if l.is_entire_pack]
        if not relevantes:
            return False

        a_actualizar = {l.pk for l in relevantes
                        if l.package_id != l.result_package_id}
        por_paquete = defaultdict(list)
        for l in relevantes:
            por_paquete[l.package_id].append(l)

        for package_id, grupo in por_paquete.items():
            albaranes = {l.picking for l in grupo if l.picking is not None}
            for albaran in albaranes:
                paquete = grupo[0].package
                completo = (albaran._is_single_transfer()
                            and albaran._check_move_lines_map_quant_package(paquete))
                if not completo:
                    a_actualizar.update(
                        l.pk for l in cls.objects.filter(
                            picking=albaran, package_id=package_id))
        return list(cls.objects.filter(pk__in=a_actualizar))

    @classmethod
    def _put_in_pack(cls, lines, package_id=False, package_type_id=False,
                     package_name=False):
        """≙ ``_put_in_pack`` (``odoo19c: :1280-1301``).

        Crea (o reutiliza) el paquete y le asigna las líneas. Con una sola
        línea además recalcula el destino: la estrategia de colocación puede
        preferir otro sitio ahora que la mercancía va empacada.
        """
        lines = list(lines)
        package_model = apps.get_model('stock', 'StockPackage')
        if package_id:
            paquete = package_model.objects.get(pk=package_id)
        elif package_type_id:
            paquete = package_model.objects.create(
                name=package_name, package_type_id=package_type_id)
        else:
            vals = {'name': package_name}
            tipos = {getattr(l.move, 'packaging_uom', None) for l in lines}
            tipos = {getattr(t, 'package_type_id', None) for t in tipos if t is not None}
            tipos.discard(None)
            if len(tipos) == 1:
                vals['package_type_id'] = tipos.pop()
            paquete = package_model.objects.create(**vals)

        if len(lines) == 1:
            linea = lines[0]
            destino = linea._get_default_dest_location()
            linea.location_dest = destino._get_putaway_strategy(
                product=linea.product, quantity=linea.quantity, package=paquete)
            linea.save()

        cls.objects.filter(pk__in=[l.pk for l in lines]).update(result_package=paquete)
        return paquete

    @classmethod
    def _post_put_in_pack_hook(cls, lines, package):
        """≙ ``_post_put_in_pack_hook`` (``odoo19c: :1303-1314``).

        Si el tipo de operación pide imprimir la etiqueta del paquete, devuelve
        el descriptor del reporte (PDF o ZPL). Divergencia D-2.
        """
        lines = list(lines)
        tipo = lines[0].picking_type if lines else None
        if package is None or tipo is None or not tipo.auto_print_package_label:
            return package
        xml_id = {
            'pdf': 'stock.action_report_package_barcode_small',
            'zpl': 'stock.label_package_template',
        }.get(tipo.package_label_to_print)
        if not xml_id:
            return package
        return {
            'type': 'ir.actions.report',
            'xml_id': xml_id,
            'res_id': package.pk,
            'close_on_report_download': True,
        }

    @classmethod
    def action_put_in_pack(cls, lines, *, package_id=False, package_type_id=False,
                           package_name=False, all_move_line_ids=None,
                           force_move_lines=False, from_package_wizard=False):
        """≙ ``action_put_in_pack`` (``odoo19c: :1316-1338``).

        El orquestador del empaque. Empaca primero las líneas sueltas; los
        paquetes ya formados que quedan se anidan dentro del que se acaba de
        crear, con una llamada recursiva — que es como la referencia construye
        el paquete de paquetes.
        """
        lines = list(lines)
        if all_move_line_ids:
            lines = list(cls.objects.filter(pk__in=all_move_line_ids))

        a_empacar, paquetes = cls._get_lines_and_packages_to_pack(
            lines, picked_first=not force_move_lines)
        hecho = False
        if a_empacar:
            accion = cls._pre_put_in_pack_hook(
                a_empacar, lines, package_id, package_type_id, package_name,
                from_package_wizard)
            if accion:
                return accion
            paquete = cls._put_in_pack(a_empacar, package_id, package_type_id,
                                       package_name)
            hecho = cls._post_put_in_pack_hook(a_empacar, paquete)

        if hecho and not force_move_lines:
            return hecho
        if paquetes:
            if hecho is not False and hasattr(hecho, 'pk'):
                paquetes = [p for p in paquetes if p.pk != hecho.pk]
                package_id = hecho.pk
            if paquetes:
                return paquetes[0].action_put_in_pack(
                    package_id=package_id, package_type_id=package_type_id,
                    package_name=package_name)
        return None

    @classmethod
    def _get_lines_and_packages_to_pack(cls, lines, picked_first=True):
        """≙ ``_get_lines_and_packages_to_pack`` (``odoo19c: :1340-1360``).

        Separa lo que se empaca en dos: las líneas sin paquete y los paquetes
        ya formados. Con ``picked_first``, en cuanto haya una línea tomada se
        ignoran las no tomadas — el capturista ya declaró qué va.
        """
        lines = list(lines)
        tipos = {l.picking_type.pk for l in lines if l.picking_type is not None}
        if len(tipos) > 1:
            raise UserError(_('You cannot pack products into the same package when '
                              'they are from different transfers with different '
                              'operation types'))

        con_cantidad = [l for l in lines
                        if l.state not in TERMINAL_STATES
                        and l.product_uom.compare(float(l.quantity), 0.0) > 0]
        if picked_first:
            tomadas = [l for l in con_cantidad if l.picked]
            if tomadas:
                con_cantidad = tomadas

        a_empacar = [l for l in con_cantidad if l.result_package is None]
        paquetes = []
        for l in con_cantidad:
            if l.result_package is not None and l.result_package.outermost_package is not None:
                paquetes.append(l.result_package.outermost_package)
        return a_empacar, list({p.pk: p for p in paquetes}.values())

    # ------------------------------------------------------------------ #
    # Reversión de ajuste de inventario (≙ :1362-1430)                     #
    # ------------------------------------------------------------------ #

    def _get_revert_inventory_move_values(self):
        """≙ ``_get_revert_inventory_move_values`` (``odoo19c: :1362-1389``).

        El movimiento inverso: mismo producto y cantidad, origen y destino
        cruzados, y los dos paquetes también cruzados — revertir un ajuste es
        devolver la mercancía por donde vino.
        """
        return {
            'inventory_name': _('%s [reverted]', self.reference),
            'product_id': self.product_id,
            'product_uom': self.product_uom_id,
            'product_uom_qty': self.quantity,
            'company_id': self.company_id,
            'state': 'confirmed',
            'location_id': self.location_dest_id,
            'location_dest_id': self.location_id,
            'is_inventory': True,
            'picked': True,
            'move_line_ids': [(0, 0, {
                'product_id': self.product_id,
                'product_uom_id': self.product_uom_id,
                'quantity': self.quantity,
                'location_id': self.location_dest_id,
                'location_dest_id': self.location_id,
                'company_id': self.company_id,
                'lot_id': self.lot_id,
                'package_id': self.result_package_id,
                'result_package_id': self.package_id,
                'owner_id': self.owner_id,
            })],
        }

    @classmethod
    def action_revert_inventory(cls, lines):
        """≙ ``action_revert_inventory`` (``odoo19c: :1391-1417``).

        Sólo revierte líneas de ajuste con cantidad; si no hay ninguna devuelve
        la notificación de la referencia en vez de crear movimientos vacíos.
        """
        lines = list(lines)
        move_model = apps.get_model('stock', 'StockMove')
        vals, procesadas = [], []
        for move_line in lines:
            if (move_line.is_inventory
                    and not move_line.product_uom.is_zero(float(move_line.quantity))):
                procesadas.append(move_line)
                vals.append(move_line._get_revert_inventory_move_values())

        if not procesadas:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': _("There are no inventory adjustments to revert."),
                },
            }

        movimientos = [move_model.objects.create(**v) for v in vals]
        for movimiento in movimientos:
            movimiento._action_done()
        nuevas = list(cls.objects.filter(move__in=movimientos).values_list('pk', flat=True))
        return {
            'name': _('Reverted Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move.line',
            'view_mode': 'list',
            'domain': [('id', 'in', nuevas + [l.pk for l in lines])],
        }

    def _get_linkable_moves(self):
        """≙ ``_get_linkable_moves`` (``odoo19c: :1419-1422``).

        Los movimientos del albarán con el mismo producto, **primero los que
        aún no cubren su demanda** — para que la línea nueva se enganche donde
        hace falta y no donde ya sobra.
        """
        albaran = self.picking
        if albaran is None:
            return []
        move_model = apps.get_model('stock', 'StockMove')
        candidatos = list(move_model.objects.filter(
            picking=albaran, product_id=self.product_id))
        return sorted(candidatos,
                      key=lambda m: m.quantity < m.product_uom_qty, reverse=True)

    @classmethod
    def _should_display_put_in_pack_wizard(cls, lines, package_id, package_type_id,
                                           package_name, from_package_wizard):
        """≙ ``_should_display_put_in_pack_wizard`` (``odoo19c: :1424-1426``).

        Sólo se pregunta si el tipo de operación pide fijar el tipo de paquete
        **y** no viene ya un paquete, tipo o nombre decidido.
        """
        return (cls._should_set_package(lines)
                and not from_package_wizard
                and not package_id and not package_type_id and not package_name)

    @classmethod
    def _should_set_package(cls, lines):
        """≙ ``_should_set_package`` (``odoo19c: :1428-1430``).

        Con más de un tipo de operación en juego no hay respuesta única, así
        que la referencia responde que no.
        """
        tipos = {l.picking_type.pk for l in lines if l.picking_type is not None}
        if len(tipos) != 1:
            return False
        tipo = next(l.picking_type for l in lines if l.picking_type is not None)
        return bool(tipo.set_package_type)


class StockMoveLineConsumeRel(models.Model):
    """Tabla intermedia de ``consume_line_ids`` / ``produce_line_ids``.

    ≙ ``stock_move_line_consume_rel`` (``odoo19c: :88-89``) — la referencia
    declara los dos M2M sobre **la misma** tabla con las columnas invertidas,
    así que aquí es una sola tabla explícita y el segundo lado se navega al
    revés (ver la property ``produce_line_ids``).
    """

    consume_line = fields.Many2one(
        'stock.StockMoveLine', on_delete=models.CASCADE,
        related_name='+', help_text='Línea consumida (Odoo consume_line_id).',
    )
    produce_line = fields.Many2one(
        'stock.StockMoveLine', on_delete=models.CASCADE,
        related_name='+', help_text='Línea producida (Odoo produce_line_id).',
    )

    class Meta:
        db_table = 'stock_move_line_consume_rel'
        constraints = [
            models.UniqueConstraint(
                fields=['consume_line', 'produce_line'],
                name='unique_stock_move_line_consume_rel',
            ),
        ]
        verbose_name = 'Relación consumo/producción de líneas'
        verbose_name_plural = 'Relaciones consumo/producción de líneas'

    def __str__(self):
        return f'{self.consume_line_id} → {self.produce_line_id}'


__all__ = [
    'FREE_RESERVATION_INDEX',
    'NEGATIVE_OPERATORS',
    'StockMoveLine',
    'StockMoveLineConsumeRel',
    'TERMINAL_STATES',
]
