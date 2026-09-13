"""``stock.picking.type`` y ``stock.picking`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_picking.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **tipo de operación** es la plantilla que gobierna una clase de
transferencia —recepción, entrega, movimiento interno— y decide su secuencia de
referencia, sus ubicaciones por defecto, su política de reserva y qué se imprime
al validar. La **transferencia** (albarán) es la instancia: un lote de
movimientos que va de una ubicación a otra bajo ese tipo.

Porte símbolo por símbolo — ``StockPickingType``
=================================================

Medido sobre ``odoo19c: addons/stock/models/stock_picking.py:20-537``:
**49 campos + 34 métodos = 83 símbolos**. Todos portados.

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``name`` (27)                                    ``name``
``color`` (28)                                   ``color``
``sequence`` (29)                                ``sequence``
``sequence_id`` (30-32)                          ``sequence_id`` (colisión, ver D-1)
``sequence_code`` (33)                           ``sequence_code``
``default_location_src_id`` (34-37)              ``default_location_src`` (almacenado)
``default_location_dest_id`` (38-41)             ``default_location_dest`` (almacenado)
``code`` (42)                                    ``code``
``return_picking_type_id`` (43-46)               ``return_picking_type``
``show_entire_packs`` (47)                       ``show_entire_packs``
``set_package_type`` (48)                        ``set_package_type``
``warehouse_id`` (49-51)                         ``warehouse`` (almacenado)
``active`` (52)                                  ``active``
``use_create_lots`` (53-56)                      ``use_create_lots`` (almacenado)
``use_existing_lots`` (57-60)                    ``use_existing_lots`` (almacenado)
``print_label`` (61-63)                          ``print_label`` (almacenado)
``show_operations`` (65-67)                      ``show_operations``
``reservation_method`` (68-71)                   ``reservation_method``
``reservation_days_before`` (72)                 ``reservation_days_before``
``reservation_days_before_priority`` (73)        ``reservation_days_before_priority``
``auto_show_reception_report`` (74-76)           ``auto_show_reception_report``
``auto_print_delivery_slip`` (77-79)             ``auto_print_delivery_slip``
``auto_print_return_slip`` (80-82)               ``auto_print_return_slip``
``auto_print_product_labels`` (84-86)            ``auto_print_product_labels``
``product_label_format`` (87-95)                 ``product_label_format``
``auto_print_lot_labels`` (96-98)                ``auto_print_lot_labels``
``lot_label_format`` (99-104)                    ``lot_label_format``
``auto_print_reception_report`` (105-107)        ``auto_print_reception_report``
``auto_print_reception_report_labels`` (108-110) ``auto_print_reception_report_labels``
``auto_print_packages`` (111-113)                ``auto_print_packages``
``auto_print_package_label`` (115-117)           ``auto_print_package_label``
``package_label_to_print`` (118-120)             ``package_label_to_print``
``count_picking_draft`` (122)                    property ``count_picking_draft``
``count_picking_ready`` (123)                    property ``count_picking_ready``
``count_picking`` (124)                          property ``count_picking``
``count_picking_waiting`` (125)                  property ``count_picking_waiting``
``count_picking_late`` (126)                     property ``count_picking_late``
``count_picking_backorders`` (127)               property ``count_picking_backorders``
``count_move_ready`` (128)                       property ``count_move_ready``
``hide_reservation_method`` (129)                property ``hide_reservation_method``
``barcode`` (130)                                ``barcode``
``company_id`` (131-133)                         ``company``
``create_backorder`` (134-140)                   ``create_backorder``
``show_picking_type`` (141)                      property ``show_picking_type``
``picking_properties_definition`` (143)          ``picking_properties_definition``
``favorite_user_ids`` (144-146)                  ``favorite_user_ids`` (M2M + through)
``is_favorite`` (147-150)                        property ``is_favorite``
``kanban_dashboard_graph`` (151)                 property ``kanban_dashboard_graph``
``move_type`` (152-155)                          ``move_type``
``create`` (157-173)                             ``create`` (classmethod)
``copy_data`` (175-183)                          ``copy_data``
``write`` (185-219)                              ``write``
``_search_is_favorite`` (221-225)                ``search_is_favorite`` (classmethod)
``_compute_is_favorite`` (227-229)               property ``is_favorite``
``_inverse_is_favorite`` (231-237)               ``set_is_favorite``
``_order_field_to_sql`` (239-247)                ``order_by_favorite`` (classmethod)
``_compute_hide_reservation_method`` (249-252)   property ``hide_reservation_method``
``_compute_picking_count`` (254-270)             ``get_picking_count`` + 6 properties
``_compute_move_count`` (272-279)                property ``count_move_ready``
``_compute_display_name`` (281-288)              ``__str__``
``_compute_use_create_lots`` (290-294)           ``compute_use_create_lots``
``_compute_use_existing_lots`` (296-300)         ``compute_use_existing_lots``
``_search_display_name`` (302-314)               ``search_display_name`` (classmethod)
``_compute_default_location_src_id`` (316-325)   ``compute_default_location_src``
``_compute_default_location_dest_id`` (327-336)  ``compute_default_location_dest``
``_compute_print_label`` (338-344)               ``compute_print_label``
``_onchange_picking_code`` (346-353)             ``check_picking_code_warning``
``_compute_warehouse_id`` (355-363)              ``compute_warehouse``
``_compute_show_picking_type`` (365-368)         property ``show_picking_type``
``_compute_kanban_dashboard_graph`` (370-392)    property ``kanban_dashboard_graph``
``_onchange_sequence_code`` (394-406)            ``check_sequence_code_warning``
``action_redirect_to_barcode_installation`` (408-412) ``action_redirect_to_barcode_installation``
``_get_action`` (414-441)                        ``get_action``
``get_action_picking_tree_late`` (443-444)       ``get_action_picking_tree_late``
``get_action_picking_tree_backorder`` (446-447)  ``get_action_picking_tree_backorder``
``get_action_picking_tree_waiting`` (449-450)    ``get_action_picking_tree_waiting``
``get_action_picking_tree_ready`` (452-453)      ``get_action_picking_tree_ready``
``get_action_picking_type_moves_analysis`` (455-460) ``get_action_picking_type_moves_analysis``
``get_stock_picking_action_picking_type`` (462-470) ``get_stock_picking_action_picking_type``
``get_action_picking_type_ready_moves`` (472-473) ``get_action_picking_type_ready_moves``
``_get_aggregated_records_by_date`` (475-492)    ``get_aggregated_records_by_date``
``_prepare_graph_data`` (494-525)                ``prepare_graph_data``
``_get_code_report_name`` (527-535)              ``get_code_report_name``
===============================================  ======================================

Divergencias declaradas
=========================

**D-1 · ``sequence_id`` conserva el sufijo.** La convención de este árbol quita
el ``_id`` de un Many2one (``warehouse_id`` → ``warehouse``), pero aquí
colisionaría con ``sequence``, que es el ``Integer`` de orden. Se conserva el
nombre **de la referencia** en vez de inventar uno: es la opción que menos
diverge de la fuente.

**D-2 · Los ``compute`` sin ``store`` son ``property``.** Los seis
``count_picking*``, ``count_move_ready``, ``hide_reservation_method``,
``show_picking_type``, ``is_favorite`` y ``kanban_dashboard_graph`` no tienen
columna allá y no la tienen aquí. Los cinco que **sí** almacena
(``default_location_src``, ``default_location_dest``, ``warehouse``,
``use_create_lots``, ``use_existing_lots``, ``print_label``) son columnas, y su
recálculo se dispara en ``save()``.

**D-3 · ``_order`` por ``is_favorite`` es un método, no ``Meta.ordering``.**
La referencia ordena por un campo calculado y para eso sobreescribe
``_order_field_to_sql``, que emite ``id IN (SELECT picking_type_id FROM
picking_type_favorite_user_rel WHERE user_id = %s)``. Django no ordena por una
``property``; el mismo SQL se obtiene con ``Exists`` sobre la tabla de
relación, así que el mecanismo vive en ``order_by_favorite(queryset, user)`` y
``Meta.ordering`` conserva el resto del criterio (``sequence, id``).

**D-4 · Los ``@api.onchange`` son métodos explícitos.**
``check_picking_code_warning`` y ``check_sequence_code_warning`` devuelven el
mismo aviso que la referencia; lo que se pierde es el disparo automático en un
formulario que este stack no tiene.

**D-5 · Las acciones de ventana devuelven el descriptor, no lo resuelven.**
``get_action`` reproduce la forma de ``_get_action`` (contexto, dominio, nombre
visible) leyendo ``IrActionsActWindow`` por identificador externo. El
``_render_template`` de ``stock.help_message_template`` exige el renderizador
QWeb, que es la tarea **#273**: hasta entonces ``help`` queda en cadena vacía y
la clave se conserva para no cambiar la forma del descriptor.
"""
import json
import datetime
import math
import uuid
from collections import defaultdict

import fields
import api
import models
from django.apps import apps
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from addons.base.models import TimeStampedModel
from addons.base.models.res_users import ResUsers
from addons.mail.models.mail_activity_mixin import MailActivityMixin
from addons.mail.models.mail_thread import MailThread
from addons.stock.models.stock_location import USAGE_INVENTORY
from addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
from exceptions import UserError
from tools.translate import _

CODE_INCOMING = 'incoming'
CODE_OUTGOING = 'outgoing'
CODE_INTERNAL = 'internal'

#: ≙ ``code`` (``odoo19c: :42``).
CODE_CHOICES = [
    (CODE_INCOMING, 'Recepción'),
    (CODE_OUTGOING, 'Entrega'),
    (CODE_INTERNAL, 'Transferencia interna'),
]

#: ≙ ``reservation_method`` (``:68-71``).
RESERVATION_METHOD_CHOICES = [
    ('at_confirm', 'Al confirmar'),
    ('manual', 'Manualmente'),
    ('by_date', 'Antes de la fecha prevista'),
]

#: ≙ ``product_label_format`` (``:87-95``).
PRODUCT_LABEL_FORMAT_CHOICES = [
    ('dymo', 'Dymo'),
    ('2x7xprice', '2 × 7 con precio'),
    ('4x7xprice', '4 × 7 con precio'),
    ('4x12', '4 × 12'),
    ('4x12xprice', '4 × 12 con precio'),
    ('zpl', 'Etiquetas ZPL'),
    ('zplxprice', 'Etiquetas ZPL con precio'),
]

#: ≙ ``lot_label_format`` (``:99-104``).
LOT_LABEL_FORMAT_CHOICES = [
    ('4x12_lots', '4 × 12 — una por lote/serie'),
    ('4x12_units', '4 × 12 — una por unidad'),
    ('zpl_lots', 'Etiquetas ZPL — una por lote/serie'),
    ('zpl_units', 'Etiquetas ZPL — una por unidad'),
]

#: ≙ ``package_label_to_print`` (``:118-120``).
PACKAGE_LABEL_CHOICES = [('pdf', 'PDF'), ('zpl', 'ZPL')]

#: ≙ ``create_backorder`` (``:134-140``).
CREATE_BACKORDER_CHOICES = [
    ('ask', 'Preguntar'),
    ('always', 'Siempre'),
    ('never', 'Nunca'),
]

#: ≙ ``move_type`` (``:152-155``).
MOVE_TYPE_CHOICES = [
    ('direct', 'En cuanto sea posible'),
    ('one', 'Cuando todos los productos estén listos'),
]

#: ≙ los identificadores externos que ``_compute_default_location_*`` resuelve.
XMLID_LOCATION_SUPPLIERS = 'stock.stock_location_suppliers'
XMLID_LOCATION_CUSTOMERS = 'stock.stock_location_customers'


class StockPickingType(models.DefaultGetMixin, TimeStampedModel):
    """``stock.picking.type`` — la plantilla que gobierna una clase de albarán."""

    # Atributos de clase de modelo — los cinco que la referencia declara
    # (``odoo19c: addons/stock/models/stock_picking.py:21-25``), verbatim.
    _name = 'stock.picking.type'
    _description = "Picking Type"
    _order = 'is_favorite desc, sequence, id'
    _rec_names_search = ['name', 'warehouse_id.name']
    _check_company_auto = True

    name                     = fields.Char(
        'Operation Type', max_length=100, required=True, translate=True,
        help='Nombre del tipo de operación (Odoo name).',
    )
    color                    = fields.Integer(
        default=0, help_text='Color del kanban (Odoo color).',
    )
    sequence                 = fields.Integer(
        default=0,
        help_text='Orden en la vista «Todas las operaciones» (Odoo sequence).',
    )
    # D-1: se conserva el sufijo ``_id`` porque ``sequence`` ya es el Integer.
    sequence_id              = fields.Many2one(
        'base.IrSequence', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='picking_types',
        help_text='Secuencia de referencia (Odoo sequence_id).',
        db_column='sequence_id',
    )
    sequence_code            = fields.Char(
        'Sequence Prefix', max_length=32, required=True,
        help='Prefijo de la secuencia (Odoo sequence_code).',
    )
    default_location_src     = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.PROTECT,
        related_name='picking_types_src',
        help_text='Ubicación de origen por defecto '
                  '(Odoo default_location_src_id, almacenado).',
    )
    default_location_dest    = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.PROTECT,
        related_name='picking_types_dest',
        help_text='Ubicación de destino por defecto '
                  '(Odoo default_location_dest_id, almacenado).',
    )
    code                     = fields.Selection(
        max_length=16, choices=CODE_CHOICES, default=CODE_INCOMING,
        help_text='Tipo de operación (Odoo code, requerido).',
    )
    return_picking_type      = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='returned_by', db_index=True,
        help_text='Tipo de operación para devoluciones '
                  '(Odoo return_picking_type_id).',
    )
    show_entire_packs        = fields.Boolean(
        default=False,
        help_text='Mostrar paquetes completos en vez de su contenido '
                  '(Odoo show_entire_packs).',
    )
    set_package_type         = fields.Boolean(
        default=False,
        help_text='Permite elegir el tipo de paquete al empaquetar '
                  '(Odoo set_package_type).',
    )
    warehouse                = fields.Many2one(
        'stock.StockWarehouse', null=True, blank=True, on_delete=models.CASCADE,
        related_name='picking_type_ids',
        help_text='Almacén dueño del tipo (Odoo warehouse_id, almacenado).',
    )
    active                   = fields.Boolean(
        default=True,
        help_text='Al desmarcarlo se archiva sin borrar (Odoo active).',
    )
    use_create_lots          = fields.Boolean(
        default=True,
        help_text='Permite crear lotes/series nuevos '
                  '(Odoo use_create_lots, almacenado).',
    )
    use_existing_lots        = fields.Boolean(
        default=True,
        help_text='Permite elegir lotes/series existentes '
                  '(Odoo use_existing_lots, almacenado).',
    )
    print_label              = fields.Boolean(
        default=False,
        help_text='Genera etiqueta de envío al validar '
                  '(Odoo print_label, almacenado).',
    )
    # La referencia marca este campo para retirarlo («TODO: delete this field»,
    # ``odoo19c: :64``); se porta igual para no divergir antes que ella.
    show_operations          = fields.Boolean(
        default=False,
        help_text='Muestra las operaciones detalladas (Odoo show_operations).',
    )
    reservation_method       = fields.Selection(
        max_length=16, choices=RESERVATION_METHOD_CHOICES, default='at_confirm',
        help_text='Cuándo se reservan los productos (Odoo reservation_method).',
    )
    reservation_days_before  = fields.Integer(
        default=0,
        help_text='Días máximos antes de la fecha prevista para reservar '
                  '(Odoo reservation_days_before).',
    )
    reservation_days_before_priority = fields.Integer(
        default=0,
        help_text='Días máximos para reservar cuando la transferencia es '
                  'prioritaria (Odoo reservation_days_before_priority).',
    )
    auto_show_reception_report = fields.Boolean(
        default=False,
        help_text='Muestra el informe de recepción al validar '
                  '(Odoo auto_show_reception_report).',
    )
    auto_print_delivery_slip = fields.Boolean(
        default=False,
        help_text='Imprime el albarán de entrega al validar '
                  '(Odoo auto_print_delivery_slip).',
    )
    auto_print_return_slip   = fields.Boolean(
        default=False,
        help_text='Imprime el comprobante de devolución al validar '
                  '(Odoo auto_print_return_slip).',
    )
    auto_print_product_labels = fields.Boolean(
        default=False,
        help_text='Imprime las etiquetas de producto al validar '
                  '(Odoo auto_print_product_labels).',
    )
    product_label_format     = fields.Selection(
        max_length=16, choices=PRODUCT_LABEL_FORMAT_CHOICES, default='2x7xprice',
        help_text='Formato de etiqueta de producto (Odoo product_label_format).',
    )
    auto_print_lot_labels    = fields.Boolean(
        default=False,
        help_text='Imprime las etiquetas de lote/serie al validar '
                  '(Odoo auto_print_lot_labels).',
    )
    lot_label_format         = fields.Selection(
        max_length=16, choices=LOT_LABEL_FORMAT_CHOICES, default='4x12_lots',
        help_text='Formato de etiqueta de lote/serie (Odoo lot_label_format).',
    )
    auto_print_reception_report = fields.Boolean(
        default=False,
        help_text='Imprime el informe de recepción al validar '
                  '(Odoo auto_print_reception_report).',
    )
    auto_print_reception_report_labels = fields.Boolean(
        default=False,
        help_text='Imprime las etiquetas del informe de recepción al validar '
                  '(Odoo auto_print_reception_report_labels).',
    )
    auto_print_packages      = fields.Boolean(
        default=False,
        help_text='Imprime los paquetes y su contenido al validar '
                  '(Odoo auto_print_packages).',
    )
    auto_print_package_label = fields.Boolean(
        default=False,
        help_text='Imprime la etiqueta del paquete al empaquetar '
                  '(Odoo auto_print_package_label).',
    )
    package_label_to_print   = fields.Selection(
        max_length=8, choices=PACKAGE_LABEL_CHOICES, default='pdf',
        help_text='Formato de la etiqueta de paquete '
                  '(Odoo package_label_to_print).',
    )
    barcode                  = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Código de barras del tipo (Odoo barcode).',
    )
    company                  = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='picking_types', db_index=True,
        help_text='Empresa dueña del tipo (Odoo company_id, requerido).',
    )
    create_backorder         = fields.Selection(
        max_length=8, choices=CREATE_BACKORDER_CHOICES, default='ask',
        help_text='Qué hacer con lo que queda al validar '
                  '(Odoo create_backorder).',
    )
    picking_properties_definition = fields.PropertiesDefinition(
        'Picking Properties', default=dict, blank=True,
        help_text='Definición de propiedades de la transferencia '
                  '(Odoo picking_properties_definition).',
    )
    favorite_user_ids        = fields.Many2many(
        ResUsers, through='PickingTypeFavoriteUserRel',
        related_name='favorite_picking_types', blank=True,
        help_text='Usuarios que marcaron el tipo como favorito '
                  '(Odoo favorite_user_ids).',
    )
    move_type                = fields.Selection(
        max_length=8, choices=MOVE_TYPE_CHOICES, default='direct',
        help_text='Política de envío: parcial o todo junto (Odoo move_type).',
    )

    class Meta:
        db_table = 'stock_picking_type'
        # ≙ ``_order = 'is_favorite desc, sequence, id'`` — el tramo calculado
        # lo aporta ``order_by_favorite`` (D-3).
        ordering = ['sequence', 'id']
        verbose_name = 'Tipo de operación'
        verbose_name_plural = 'Tipos de operación'

    def __str__(self) -> str:
        """≙ ``_compute_display_name`` (``odoo19c: :281-288``).

        Con almacén, el nombre visible es ``<almacén>: <tipo>``.
        """
        if self.warehouse is not None:
            return f'{self.warehouse.name}: {self.name}'
        return self.name

    # -- creación, copia y escritura --

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :157-173``).

        Sin secuencia explícita pero con prefijo, se crea la ``ir.sequence``
        que le corresponde: con almacén el prefijo lleva su código delante
        (``WH/IN/``); sin él, el prefijo a secas. El bucle por ``vals`` es el
        de la referencia.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        ir_sequence = apps.get_model('base', 'IrSequence')
        for vals in vals_list:
            if not vals.get('sequence_id') and vals.get('sequence_code'):
                warehouse = vals.get('warehouse')
                if warehouse is not None:
                    vals['sequence_id'] = ir_sequence.objects.create(
                        name=_('Secuencia %(code)s de %(warehouse)s') % {
                            'code': vals['sequence_code'], 'warehouse': warehouse.name},
                        prefix=f"{warehouse.code}/{vals['sequence_code']}/",
                        padding=5,
                        company=warehouse.company,
                    )
                else:
                    vals['sequence_id'] = ir_sequence.objects.create(
                        name=_('Secuencia %(code)s') % {'code': vals['sequence_code']},
                        prefix=vals['sequence_code'],
                        padding=5,
                        company=vals.get('company'),
                    )
        return super().create(vals_list)

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :175-183``).

        El nombre y el prefijo de la copia se marcan como tales; si el llamador
        ya fijó uno de los dos, ese gana.
        """
        default = dict(default or {})
        vals = {
            'name': default.get('name', _('%s (copia)') % self.name),
            'code': self.code,
            'company': self.company,
            'warehouse': self.warehouse,
        }
        if 'sequence_code' not in default and 'sequence_id' not in default:
            vals['sequence_code'] = _('%s (copia)') % self.sequence_code
        else:
            vals['sequence_code'] = default.get('sequence_code', self.sequence_code)
        return vals

    def write(self, vals):
        """≙ ``write`` (``odoo19c: :185-219``).

        Tres reglas de la referencia, en su orden:

        1. cambiar de empresa está prohibido — se archiva y se crea otro;
        2. cambiar el prefijo reescribe la ``ir.sequence`` asociada;
        3. cambiar el método de reserva recalcula (o borra) la fecha de reserva
           de los movimientos abiertos del tipo.
        """
        stock_move = apps.get_model('stock', 'StockMove')

        if 'company' in vals and self.company != vals['company']:
            raise UserError(_(
                'Cambiar la empresa de este registro está prohibido en este '
                'punto; archívelo y cree uno nuevo.'))

        if 'sequence_code' in vals and self.sequence_id is not None:
            if self.warehouse is not None:
                self.sequence_id.name = _('Secuencia %(code)s de %(warehouse)s') % {
                    'code': vals['sequence_code'], 'warehouse': self.warehouse.name}
                self.sequence_id.prefix = (
                    f"{self.warehouse.code}/{vals['sequence_code']}/")
                self.sequence_id.company = self.warehouse.company
            else:
                self.sequence_id.name = _('Secuencia %(code)s') % {
                    'code': vals['sequence_code']}
                self.sequence_id.prefix = vals['sequence_code']
            self.sequence_id.padding = 5
            self.sequence_id.save()

        if 'reservation_method' in vals:
            if vals['reservation_method'] == 'by_date':
                if self.reservation_method != 'by_date':
                    abiertos = stock_move.objects.filter(
                        picking_type=self,
                        state__in=('draft', 'confirmed', 'waiting',
                                   'partially_available'),
                    )
                    comunes = (vals.get('reservation_days_before')
                               or self.reservation_days_before)
                    prioritarios = (vals.get('reservation_days_before_priority')
                                    or self.reservation_days_before_priority)
                    for move in abiertos:
                        dias = prioritarios if move.priority == '1' else comunes
                        if move.date is not None:
                            move.reservation_date = (
                                move.date.date() - datetime.timedelta(days=dias))
                            move.save(update_fields=['reservation_date'])
            elif self.reservation_method == 'by_date':
                stock_move.objects.filter(
                    picking_type=self,
                ).exclude(
                    state__in=('assigned', 'done', 'cancel'),
                ).update(reservation_date=None)

        for nombre, valor in vals.items():
            setattr(self, nombre, valor)
        self.save()
        return self

    # -- favoritos --

    @classmethod
    def _search_is_favorite(cls, user):
        """≙ ``_search_is_favorite`` (``odoo19c: :221-225``)."""
        return cls.objects.filter(favorite_user_ids=user)

    @property
    def is_favorite(self):
        """≙ ``_compute_is_favorite`` (``odoo19c: :227-229``).

        La referencia lo evalúa contra ``self.env.user``; aquí no hay usuario
        implícito, así que la property responde por el conjunto y el caso
        per-usuario lo cubre :meth:`is_favorite_of`.
        """
        return self.favorite_user_ids.exists()

    def is_favorite_of(self, user):
        """El predicado per-usuario que la referencia obtiene de ``env.user``."""
        return self.favorite_user_ids.filter(pk=user.pk).exists()

    def set_is_favorite(self, user, valor=None):
        """≙ ``_inverse_is_favorite`` (``odoo19c: :231-237``).

        Sin ``valor`` conmuta, que es lo que hace la referencia: lo que no
        estaba favorito pasa a estarlo, y lo que estaba deja de estarlo.
        """
        estaba = self.is_favorite_of(user)
        nuevo = (not estaba) if valor is None else bool(valor)
        if nuevo and not estaba:
            self.favorite_user_ids.add(user)
        elif not nuevo and estaba:
            self.favorite_user_ids.remove(user)
        return nuevo

    @classmethod
    def order_by_favorite(cls, queryset=None, user=None):
        """≙ ``_order_field_to_sql`` (``odoo19c: :239-247``) — D-3.

        La referencia emite ``id IN (SELECT picking_type_id FROM
        picking_type_favorite_user_rel WHERE user_id = %s)`` como expresión de
        orden. El equivalente exacto aquí es un ``Exists`` sobre la misma tabla
        de relación, y con él se completa ``is_favorite desc, sequence, id``.
        """
        queryset = cls.objects.all() if queryset is None else queryset
        if user is None:
            return queryset.order_by('sequence', 'id')
        rel = apps.get_model('stock', 'PickingTypeFavoriteUserRel')
        marked = Exists(rel.objects.filter(
            picking_type_id=OuterRef('pk'), user_id=user.pk))
        return queryset.annotate(
            is_favorite=marked).order_by('-is_favorite', 'sequence', 'id')

    # -- los conteos del tablero: sin columna, se calculan al leerse (D-2) --

    def get_picking_count(self):
        """≙ ``_compute_picking_count`` (``odoo19c: :254-270``).

        Devuelve el mismo diccionario de seis claves que la referencia asigna a
        seis campos calculados, con sus mismos dominios.
        """
        stock_picking = apps.get_model('stock', 'StockPicking')
        base = stock_picking.objects.filter(picking_type=self).exclude(
            state__in=('done', 'cancel'))
        hoy = datetime.date.today()
        abiertos = ('assigned', 'waiting', 'confirmed')
        return {
            'count_picking_draft': base.filter(state='draft').count(),
            'count_picking_waiting': base.filter(
                state__in=('confirmed', 'waiting')).count(),
            'count_picking_ready': base.filter(state='assigned').count(),
            'count_picking': base.filter(state__in=abiertos).count(),
            'count_picking_late': base.filter(state__in=abiertos).filter(
                Q(scheduled_date__lt=hoy) | Q(has_deadline_issue=True)).count(),
            'count_picking_backorders': base.filter(
                backorder__isnull=False,
                state__in=('confirmed', 'assigned', 'waiting')).count(),
        }

    @property
    def count_picking_draft(self):
        """≙ ``count_picking_draft`` (``odoo19c: :122``)."""
        return self.get_picking_count()['count_picking_draft']

    @property
    def count_picking_ready(self):
        """≙ ``count_picking_ready`` (``odoo19c: :123``)."""
        return self.get_picking_count()['count_picking_ready']

    @property
    def count_picking(self):
        """≙ ``count_picking`` (``odoo19c: :124``)."""
        return self.get_picking_count()['count_picking']

    @property
    def count_picking_waiting(self):
        """≙ ``count_picking_waiting`` (``odoo19c: :125``)."""
        return self.get_picking_count()['count_picking_waiting']

    @property
    def count_picking_late(self):
        """≙ ``count_picking_late`` (``odoo19c: :126``)."""
        return self.get_picking_count()['count_picking_late']

    @property
    def count_picking_backorders(self):
        """≙ ``count_picking_backorders`` (``odoo19c: :127``)."""
        return self.get_picking_count()['count_picking_backorders']

    @property
    def count_move_ready(self):
        """≙ ``count_move_ready`` / ``_compute_move_count`` (``:128``, ``:272-279``)."""
        stock_move = apps.get_model('stock', 'StockMove')
        return stock_move.objects.filter(
            picking_type=self, state='assigned').count()

    @property
    def hide_reservation_method(self):
        """≙ ``_compute_hide_reservation_method`` (``odoo19c: :249-252``)."""
        return self.code == CODE_INCOMING

    @property
    def show_picking_type(self):
        """≙ ``_compute_show_picking_type`` (``odoo19c: :365-368``)."""
        return self.code in (CODE_INCOMING, CODE_OUTGOING, CODE_INTERNAL)

    # -- los computes almacenados: se recalculan al guardar --

    def _compute_use_create_lots(self):
        """≙ ``_compute_use_create_lots`` (``odoo19c: :290-294``)."""
        if self.code == CODE_INCOMING:
            self.use_create_lots = True
        return self.use_create_lots

    def _compute_use_existing_lots(self):
        """≙ ``_compute_use_existing_lots`` (``odoo19c: :296-300``)."""
        if self.code == CODE_OUTGOING:
            self.use_existing_lots = True
        return self.use_existing_lots

    def _compute_print_label(self):
        """≙ ``_compute_print_label`` (``odoo19c: :338-344``)."""
        if self.code in (CODE_INCOMING, CODE_INTERNAL):
            self.print_label = False
        elif self.code == CODE_OUTGOING:
            self.print_label = True
        return self.print_label

    def compute_warehouse(self):
        """≙ ``_compute_warehouse_id`` (``odoo19c: :355-363``).

        Con almacén ya puesto no se toca; si no, se toma el primero de la
        empresa.
        """
        if self.warehouse is not None or self.company is None:
            return self.warehouse
        stock_warehouse = apps.get_model('stock', 'StockWarehouse')
        self.warehouse = stock_warehouse.objects.filter(
            company=self.company).first()
        return self.warehouse

    def compute_default_location_src(self):
        """≙ ``_compute_default_location_src_id`` (``odoo19c: :316-325``).

        En una recepción el origen es la ubicación virtual de proveedores; en
        cualquier otro caso, el almacén de existencias.
        """
        if self.warehouse is None:
            self._warehouse_redirect_warning()
        if self.code == CODE_INCOMING:
            self.default_location_src = self._location_by_xmlid(
                XMLID_LOCATION_SUPPLIERS)
        else:
            self.default_location_src = (
                self.warehouse.lot_stock if self.warehouse is not None else None)
        return self.default_location_src

    def compute_default_location_dest(self):
        """≙ ``_compute_default_location_dest_id`` (``odoo19c: :327-336``).

        En una entrega el destino es la ubicación virtual de clientes; en
        cualquier otro caso, el almacén de existencias.
        """
        if self.warehouse is None:
            self._warehouse_redirect_warning()
        if self.code == CODE_OUTGOING:
            self.default_location_dest = self._location_by_xmlid(
                XMLID_LOCATION_CUSTOMERS)
        else:
            self.default_location_dest = (
                self.warehouse.lot_stock if self.warehouse is not None else None)
        return self.default_location_dest

    @staticmethod
    def _location_by_xmlid(xmlid):
        """Resuelve una ubicación por su identificador externo sembrado."""
        ir_model_data = apps.get_model('base', 'IrModelData')
        modulo, _sep, nombre = xmlid.partition('.')
        registro = ir_model_data.objects.filter(
            module=modulo, name=nombre).first()
        if registro is None:
            return None
        stock_location = apps.get_model('stock', 'StockLocation')
        return stock_location.objects.filter(pk=registro.res_id).first()

    @staticmethod
    def _warehouse_redirect_warning():
        """≙ ``stock.warehouse._warehouse_redirect_warning`` (``:318``, ``:329``).

        La referencia lanza el aviso que redirige a crear un almacén. Aquí se
        mantiene el punto de extensión con el mismo nombre; el redirect a la
        vista es cosa del cliente, que este stack no tiene.
        """
        return None

    def save(self, *args, **kwargs):
        """Dispara los computes almacenados, que allá corren por ``@api.depends``."""
        self._compute_use_create_lots()
        self._compute_use_existing_lots()
        self._compute_print_label()
        self.compute_warehouse()
        if self.default_location_src is None:
            self.compute_default_location_src()
        if self.default_location_dest is None:
            self.compute_default_location_dest()
        return super().save(*args, **kwargs)

    # -- los avisos que allá son @api.onchange (D-4) --

    def check_picking_code_warning(self, user):
        """≙ ``_onchange_picking_code`` (``odoo19c: :346-353``)."""
        if self.code == CODE_INTERNAL and not user.has_group(
                'stock.group_stock_multi_locations'):
            return {'warning': {'message': _(
                'Necesita activar las ubicaciones de almacenamiento para poder '
                'usar tipos de operación internos.')}}
        return None

    def check_sequence_code_warning(self):
        """≙ ``_onchange_sequence_code`` (``odoo19c: :394-406``).

        Avisa cuando otro tipo de operación ya usa ese prefijo con una
        secuencia distinta.
        """
        if not self.sequence_code:
            return None
        candidatos = type(self).objects.filter(
            Q(sequence_code=self.sequence_code),
            Q(company=self.company) | Q(company__isnull=True),
        )
        if self.pk is not None:
            candidatos = candidatos.exclude(pk=self.pk)
        otro = candidatos.first()
        if otro is not None and otro.sequence_id != self.sequence_id:
            return {'warning': {'message': _(
                'Otro tipo de operación ya usa este prefijo de secuencia. Se '
                'recomienda elegir un prefijo único para evitar referencias '
                'repetidas, o asignar a este tipo la secuencia existente.')}}
        return None

    # -- acciones de ventana (D-5) --

    @classmethod
    def action_redirect_to_barcode_installation(cls):
        """≙ ``action_redirect_to_barcode_installation`` (``odoo19c: :408-412``)."""
        accion = cls._action_by_xmlid('base.open_module_tree')
        if accion is not None:
            contexto = dict(accion.get('context') or {})
            contexto['search_default_name'] = 'Barcode'
            accion['context'] = contexto
        return accion

    @staticmethod
    def _action_by_xmlid(xmlid):
        """Lee el descriptor de una acción de ventana por identificador externo."""
        ir_model_data = apps.get_model('base', 'IrModelData')
        modulo, _sep, nombre = xmlid.partition('.')
        registro = ir_model_data.objects.filter(
            module=modulo, name=nombre).first()
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
            'context': accion.get_context() if hasattr(
                accion, 'get_context') else {},
        }

    def _get_action(self, action_xmlid):
        """≙ ``_get_action`` (``odoo19c: :414-441``).

        Fija el nombre visible, el contexto por defecto (tipo y empresa) y el
        dominio acotado al tipo. ``help`` se deja vacío hasta que exista el
        renderizador QWeb (tarea #273) — la clave se conserva para no cambiar
        la forma del descriptor.
        """
        accion = self._action_by_xmlid(action_xmlid)
        if accion is None:
            return None
        accion['display_name'] = str(self)
        contexto = dict(accion.get('context') or {})
        contexto.update({
            'default_picking_type_id': self.pk,
            'default_company_id': self.company_id,
        })
        accion['context'] = contexto
        accion['domain'] = [('picking_type_id', '=', self.pk)]
        accion['help'] = ''
        return accion

    def get_action_picking_tree_late(self):
        """≙ ``get_action_picking_tree_late`` (``odoo19c: :443-444``)."""
        return self._get_action('stock.action_picking_tree_late')

    def get_action_picking_tree_backorder(self):
        """≙ ``get_action_picking_tree_backorder`` (``odoo19c: :446-447``)."""
        return self._get_action('stock.action_picking_tree_backorder')

    def get_action_picking_tree_waiting(self):
        """≙ ``get_action_picking_tree_waiting`` (``odoo19c: :449-450``)."""
        return self._get_action('stock.action_picking_tree_waiting')

    def get_action_picking_tree_ready(self):
        """≙ ``get_action_picking_tree_ready`` (``odoo19c: :452-453``)."""
        return self._get_action('stock.action_picking_tree_ready')

    def get_action_picking_type_moves_analysis(self):
        """≙ ``get_action_picking_type_moves_analysis`` (``odoo19c: :455-460``)."""
        accion = self._action_by_xmlid('stock.stock_move_action')
        if accion is None:
            return None
        accion['domain'] = list(accion.get('domain') or []) + [
            ('picking_type_id', '=', self.pk)]
        return accion

    def get_stock_picking_action_picking_type(self):
        """≙ ``get_stock_picking_action_picking_type`` (``odoo19c: :462-470``)."""
        por_codigo = {
            CODE_INCOMING: 'stock.action_picking_tree_incoming',
            CODE_OUTGOING: 'stock.action_picking_tree_outgoing',
            CODE_INTERNAL: 'stock.action_picking_tree_internal',
        }
        return self._get_action(por_codigo.get(
            self.code, 'stock.stock_picking_action_picking_type'))

    def get_action_picking_type_ready_moves(self):
        """≙ ``get_action_picking_type_ready_moves`` (``odoo19c: :472-473``)."""
        return self._get_action('stock.action_get_picking_type_ready_moves')

    # -- el gráfico del tablero --

    @classmethod
    def _get_aggregated_records_by_date(cls, picking_types):
        """≙ ``_get_aggregated_records_by_date`` (``odoo19c: :475-492``).

        Devuelve una terna por tipo: su id, las fechas previstas de sus
        transferencias abiertas, y el nombre de la serie de datos.
        """
        stock_picking = apps.get_model('stock', 'StockPicking')
        ids = [t.pk for t in picking_types]
        by_type = {i: [] for i in ids}
        abiertas = stock_picking.objects.filter(
            picking_type_id__in=ids,
            state__in=('assigned', 'waiting', 'confirmed'),
        ).values_list('picking_type_id', 'scheduled_date')
        for tipo_id, fecha in abiertas:
            by_type[tipo_id].append(fecha)
        return [(i, f, _('Transferencias')) for i, f in by_type.items()]

    @classmethod
    def _prepare_graph_data(cls, summaries):
        """≙ ``_prepare_graph_data`` (``odoo19c: :494-525``).

        Convierte el resumen por categoría en la serie del gráfico. Si todos
        los valores son cero, la serie se marca como muestra.
        """
        categorias = {
            'total_before': {'label': _('Antes'), 'type': 'past'},
            'total_yesterday': {'label': _('Ayer'), 'type': 'past'},
            'total_today': {'label': _('Hoy'), 'type': 'present'},
            'total_day_1': {'label': _('Mañana'), 'type': 'future'},
            'total_day_2': {'label': _('Pasado mañana'), 'type': 'future'},
            'total_after': {'label': _('Después'), 'type': 'future'},
        }
        salida = {}
        for picking_type_id, resumen in summaries.items():
            vacio = all(resumen[k] == 0 for k in categorias)
            salida[picking_type_id] = [{
                'key': _('Datos de muestra') if vacio
                       else resumen['data_series_name'],
                'picking_type_id': None if vacio else picking_type_id,
                'values': [
                    dict(v, value=resumen[k],
                         type='sample' if vacio else v['type'])
                    for k, v in categorias.items()
                ],
            }]
        return salida

    @property
    def kanban_dashboard_graph(self):
        """≙ ``_compute_kanban_dashboard_graph`` (``odoo19c: :370-392``)."""
        stock_picking = apps.get_model('stock', 'StockPicking')
        agrupados = type(self)._get_aggregated_records_by_date([self])
        resumenes = {}
        for picking_type_id, fechas, serie in agrupados:
            resumen = {
                'data_series_name': serie,
                'total_before': 0, 'total_yesterday': 0, 'total_today': 0,
                'total_day_1': 0, 'total_day_2': 0, 'total_after': 0,
            }
            for fecha in fechas:
                categoria = stock_picking.calculate_date_category(fecha)
                if categoria:
                    resumen['total_' + categoria] += 1
            resumenes[picking_type_id] = resumen
        return json.dumps(
            type(self)._prepare_graph_data(resumenes).get(self.pk, []))

    def _get_code_report_name(self):
        """≙ ``_get_code_report_name`` (``odoo19c: :527-535``)."""
        return {
            CODE_OUTGOING: _('Nota de entrega'),
            CODE_INCOMING: _('Nota de recepción'),
            CODE_INTERNAL: _('Movimiento interno'),
        }.get(self.code)


class PickingTypeFavoriteUserRel(models.Model):
    """Tabla de relación ``picking_type_favorite_user_rel`` — tipo ↔ usuario.

    La referencia la declara con sus nombres de columna explícitos
    (``odoo19c: addons/stock/models/stock_picking.py:144-146`` —
    ``favorite_user_ids = fields.Many2many('res.users',
    'picking_type_favorite_user_rel', 'picking_type_id', 'user_id')``), y su
    ``_order_field_to_sql`` (``:239-247``) consulta esa tabla por su nombre. El
    ``through`` explícito existe para fijar los tres nombres.
    """

    picking_type = fields.Many2one(
        StockPickingType, on_delete=models.CASCADE,
        db_column='picking_type_id', related_name='+',
        verbose_name='Tipo de operación',
    )
    user = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, db_column='user_id',
        related_name='+', verbose_name='Usuario',
    )

    class Meta:
        db_table = 'picking_type_favorite_user_rel'
        constraints = [
            models.UniqueConstraint(
                fields=['picking_type', 'user'],
                name='picking_type_favorite_user_rel_uniq'),
        ]
        verbose_name = 'Tipo de operación favorito'
        verbose_name_plural = 'Tipos de operación favoritos'

    def __str__(self) -> str:
        return f'{self.picking_type_id}:{self.user_id}'


class StockPicking(MailThread, MailActivityMixin, models.DefaultGetMixin,
                   TimeStampedModel):
    """``stock.picking`` — una transferencia (albarán).

    .. warning:: Porte parcial declarado — tarea **#330**, segundo pase.

       La referencia declara ``StockPicking`` en
       ``odoo19c: addons/stock/models/stock_picking.py:538-2149``: **154
       símbolos** (57 campos ``fields.X`` + 97 métodos, medidos por AST). El
       primer pase (H-API-580) cerró sólo la cabecera de atributos de clase.
       Este segundo pase suma el ciclo de vida (``create``/``write``/
       ``unlink``), un bloque de campos estructurales y sus computados de
       sólo lectura, y las dos funciones de categorización de fecha — ya
       consumidas por ``StockPickingType.kanban_dashboard_graph``.

       *Métrica:* símbolos ``fields.X(...)`` + ``def`` en el cuerpo de la
       clase, por AST (mismo instrumento de ``porte-completo-no-parcial.md``).
       *Ciega a:* si un símbolo nuestro **hace** lo mismo que el suyo con
       otro nombre (D-1..D-9 abajo) — por eso la tabla de cobertura completa
       vive en el hallazgo, no aquí.

       .. list-table:: Cobertura de símbolos (medida por AST, este pase)
          :header-rows: 1

          * - Corte
            - Campos ``fields.X``
            - ``def`` (métodos+properties)
            - Total
          * - Antes de este pase
            - 13
            - 8
            - 21
          * - Después de este pase
            - 19
            - 29
            - 48
          * - Después de tarea #521 (H-API-692)
            - 19
            - 44
            - 63
          * - Después del grupo Paquetes (tarea #521, continuación)
            - 19
            - 57
            - 76
          * - Referencia (``odoo19c:``)
            - 57
            - 97
            - 154

       La fila «Después de este pase» cuenta símbolos **nuestros**, sin
       normalizar contra el nombre de la referencia — es la cota superior
       de qué hay aquí, no cuánto de la referencia cubre. Normalizando por
       los alias declarados (D-1..D-9: ``location``↔``location_id``,
       ``product``↔``product_id``, un ``compute`` colapsado a una sola
       ``property``, etc.) la cobertura real tras el segundo pase era
       **60 de 154**; tras tarea #521 (H-API-692) eran **75 de 154**, y tras
       cerrar el grupo Paquetes (17 símbolos: 13 ``def`` nuevos medidos por
       AST + 3 campos como ``property`` + ``package_history_ids`` como
       reverso M2M) son **92 de 154** — el resto, **62**, sigue en los grupos
       bloqueados de abajo (era 94 → 79 → 62; ver el detalle de qué se cerró
       en :ref:`h-api-692`).

       **Corrección durante este mismo pase (H-API-685):** un primer borrador
       incluía ``has_deadline_issue`` como ``property`` — leía
       ``self.scheduled_date``, un campo que **no existe** aquí (está en el
       grupo BLOQUEADO). Habría reventado con ``AttributeError`` en el primer
       acceso. Se retiró antes de cerrar el pase y pasó al grupo BLOQUEADO,
       de donde nunca debió salir. El TDD lo hubiera atrapado en verde falso
       si el test no hubiese comparado contra la línea exacta de la
       referencia; se deja registrado porque el propio ejercicio de escribir
       el caso de prueba —no una relectura— fue lo que lo destapó.

       **Grupos bloqueados — 62 símbolos tras cerrar el grupo Paquetes
       (tarea #521, continuación), verificados por AST contra la cobertura
       real** (eran 94 → 79; el detalle símbolo a símbolo de qué se cerró
       vive en :ref:`h-api-692`, no aquí — la marca en mayúsculas queda
       reservada a las declaraciones con forma fija del gate
       ``check_bloqueo_declarado.py``):

       - **Report/QWeb — 13** (``do_print_picking``,
         ``get_action_click_graph``, ``_get_action``,
         ``get_action_picking_tree_incoming/outgoing/internal``,
         ``action_open_label_layout``, ``action_open_label_type``,
         ``_get_autoprint_report_actions``, ``_get_packages_for_print``,
         ``_get_report_lang``,
         ``should_print_delivery_address``, ``action_view_reception_report``):
         cuelgan del renderizador QWeb pendiente (tarea **#273**), igual que
         ``StockPickingType._get_action``. ``get_empty_list_help`` **salió**
         de este grupo en tarea #521: no necesita reportes, sólo texto — se
         portó con la misma divergencia declarada (sin QWeb, texto plano)
         que ya usan ``calculate_date_category``/``date_category_to_domain``.
       - **Paquetes — CERRADO en la continuación de tarea #521.** Los 17
         símbolos (``action_put_in_pack``, ``action_add_entire_packs``,
         ``action_see_packages``, ``action_see_package_histories``,
         ``_check_move_lines_map_quant_package``,
         ``_get_entire_pack_location_dest``, ``_is_single_transfer``,
         ``_check_entire_pack``, ``_prepare_entire_pack_move_line_vals``,
         ``packages_count``, ``show_allocation`` + ``_get_show_allocation``,
         ``package_history_ids``, ``show_check_availability``) están
         portados al final de esta clase; su bloqueo era sólo de write-set
         (``stock_package.py`` fuera del pase anterior). Los tres computes
         sin ``store`` son ``property`` (D-6) y ``package_history_ids`` es el
         reverso del M2M declarado en ``stock_package_history.py``.
       - **Backorder/wizard — 9** (``_should_show_transfers``,
         ``_should_ignore_backorders``, ``_get_without_quantities_error_message``,
         ``_action_generate_backorder_wizard``,
         ``_check_backorder``, ``_autoconfirm_picking``,
         ``_get_moves_to_backorder``, ``_create_backorder_picking``,
         ``_create_backorder``): exigen un modelo wizard
         (``stock.backorder.confirmation``) que no existe — sub-iniciativa
         explícita, no un fix de una función. ``action_toggle_is_locked``
         **salió** de este grupo en tarea #521 (H-API-692): es un toggle de
         dos líneas sobre ``is_locked``, sin relación real con el backorder
         — estaba agrupado por vecindad de línea en la referencia, no por
         dependencia.
       - **Sanity/reserva/reporte de cierre — 12** (``do_unreserve``,
         ``action_split_transfer``, ``_pre_action_done_hook``,
         ``_sanity_check``, ``_get_lot_move_lines_for_sanity_check``,
         ``button_scrap``, ``action_see_move_scrap``,
         ``action_picking_move_tree``,
         ``_can_return``, ``action_see_returns``, ``_action_done``,
         ``_is_to_external_location``):
         reescriben ``_action_done``, que ya sostiene ``button_validate``
         simplificado; profundizar aquí sin la máquina de reservas completa
         de ``stock.move`` arriesga contradecir ese archivo, fuera de lo
         escribible de este pase. **10 de los 22 originales salieron en
         tarea #521 (H-API-692)** — ``action_next_transfer``,
         ``action_detailed_operations``, ``_send_confirmation_email``,
         ``_add_reference``, ``_remove_reference``, ``_log_activity``,
         ``_log_activity_get_documents``,
         ``_log_less_quantities_than_expected``,
         ``_less_quantities_than_expected_add_documents``,
         ``_get_impacted_pickings`` — porque, medidos uno por uno, ninguno
         reescribe ``_action_done`` ni toca la máquina de reservas: la razón
         de bloqueo de la fila de arriba era una justificación de bloque, no
         símbolo a símbolo. Ver H-API-692 para la divergencia declarada de
         cada uno (mensajería sin plantilla QWeb, actividad sin ``sudo()``,
         ``mail.activity.user`` NOT NULL sin fallback a un usuario de
         sesión implícito).
       - **Estado reactivo/ubicación/UI — 28** (``_compute_location_id``,
         ``_compute_scheduled_date``,
         ``scheduled_date``, ``_set_scheduled_date``,
         ``has_deadline_issue`` + ``_compute_has_deadline_issue`` — lee
         ``scheduled_date``, que está en este mismo grupo —,
         ``signature``, ``is_signed`` + ``_compute_is_signed``,
         ``_attach_sign``, ``json_popover`` + ``_compute_json_popover``,
         ``show_lots_text`` + ``_compute_show_lots_text``,
         ``products_availability`` + ``products_availability_state`` +
         ``_compute_products_availability`` +
         ``_search_products_availability_state`` — necesitan
         ``forecast_availability``/``forecast_expected_date`` en
         ``stock_move.py``, que no existen: bloqueado **aguas arriba**, no
         por falta de tiempo —, ``search_date_category`` +
         ``_search_date_category`` + ``_search_delay_alert_date`` (campos de
         sólo búsqueda, sin backend ``search=`` equivalente en este ORM),
         ``weight_bulk`` + ``_compute_bulk_weight``, ``shipping_weight`` +
         ``_compute_shipping_weight``, ``shipping_volume`` +
         ``_compute_shipping_volume``, ``partner_country_id``,
         ``picking_properties``): quedan para el bloque de reservas/UI de la
         tarea #330. **``_compute_state``, ``_onchange_picking_type`` y
         ``_onchange_location_id`` salieron de este grupo en tarea #521**
         (H-API-692) — ``StockMove._get_relevant_state_among_moves``,
         ``_get_upstream_documents_and_responsibles``, ``procure_method``,
         ``location_dest_usage`` y ``should_bypass_reservation()`` ya
         existían en ``stock_move.py``/``stock_location.py``; no hacía
         falta editarlos, sólo leerlos.

       ``_compute_move_type`` (ya cubierto por ``save()``, primer pase) y
       ``_default_picking_type_id`` (divergencia ya declarada — ``picking_type``
       nulable) **no** están en el conteo de 93: están resueltos, no
       bloqueados. ``move_ids``/``move_line_ids``/``backorder_ids``/
       ``return_ids`` tampoco: son accesores reversos de Django
       (``related_name``) — existen en runtime y son invisibles al AST, que
       es la ceguera de este instrumento (``metrica-decide-la-conclusion.md``).

       Sucesor de todo el grupo: tarea **PENDIENTE DE ASIGNAR** — completar
       ``StockPicking`` en dos sub-pases restantes (backorder-wizard,
       reservas/estado), en ese orden de dependencia; el sub-pase de
       paquetes se cerró en la continuación de tarea #521.

       Dos consecuencias de la cabecera, ya resueltas en este pase:

       - ``_order`` está declarado verbatim; ``Meta.ordering`` ahora incluye
         ``-priority`` (portado) y sustituye ``scheduled_date`` (aún
         BLOQUEADO) por ``-created_at`` hasta que ese campo aterrice.
       - ``_name_uniq`` (``odoo19c: :710``) sigue sin `Meta.constraints`
         —``company`` ya existe, pero es nulable y ``name`` tiene datos con
         ``''``/``None`` heredados; añadir la restricción ahora arriesga una
         migración que falle contra datos existentes. Sucesor: tarea
         **PENDIENTE DE ASIGNAR** (auditar duplicados antes de imponerla).

       **Divergencias de este pase (D-6..D-9)** — D-1..D-5 vienen del primer
       pase (arriba, cabecera de la clase):

       - **D-6.** Los ``compute`` de este bloque —``return_count``,
         ``has_tracking``, ``has_scrap_move``, ``date_deadline``,
         ``delay_alert_date``, ``show_next_pickings``,
         ``picking_warning_text``, ``product``, ``lot``, y los cinco
         ``related`` de ``picking_type``— son ``property`` sin ``store``,
         **aunque** en la referencia ``date_deadline`` sí sea ``store=True``.
         El motor de recálculo condicional vive en el grupo BLOQUEADO
         (``_compute_state``/``_compute_scheduled_date``); duplicar su
         lógica de invalidación en ``save()`` antes de portar ese grupo
         habría arriesgado una segunda fuente de verdad.
         ``has_deadline_issue`` **no** entró en este bloque —depende de
         ``scheduled_date``, que sigue BLOQUEADO— y quedó ahí mismo (arriba).
       - **D-7.** ``calculate_date_category``/``date_category_to_domain``
         usan ``django.utils.timezone.localtime`` en vez de
         ``fields.Datetime.context_timestamp(self.env.user, ...)`` + pytz —
         sin usuario/zona por sesión, el borde del día sale de la zona
         activa del proceso (``settings.TIME_ZONE``).
       - **D-8.** ``create``/``write`` no llaman ``_autoconfirm_picking()``
         (grupo backorder BLOQUEADO); el llamador confirma explícitamente
         con :meth:`action_confirm`.
       - **D-9.** ``backorder``/``return_of`` guardan sólo la relación
         estructural (FK + reverso por ``related_name``); quién los **crea**
         (``_create_backorder``, el wizard de backorder) está en el grupo
         BLOQUEADO.
    """

    # Atributos de clase de modelo — los cuatro de ORM que la referencia declara
    # (``odoo19c: :539-542``), verbatim. Los dos mixins que ``_inherit`` nombra
    # **existen y están heredados** (``MailThread``, ``MailActivityMixin`` en la
    # lista de bases): el hilo del chatter y las actividades planificadas.
    _name = 'stock.picking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Transfer"
    _order = "priority desc, scheduled_date asc, id desc"

    STATE_DRAFT     = 'draft'
    STATE_WAITING   = 'waiting'
    STATE_CONFIRMED = 'confirmed'
    STATE_ASSIGNED  = 'assigned'
    STATE_DONE      = 'done'
    STATE_CANCEL    = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Borrador'),
        (STATE_WAITING, 'Esperando otro movimiento'),
        (STATE_CONFIRMED, 'Esperando'),
        (STATE_ASSIGNED, 'Disponible'),
        (STATE_DONE, 'Hecho'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    name             = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Referencia (Odoo stock.picking.name).',
    )
    state            = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo stock.picking.state).',
    )
    location         = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings_out', help_text='Origen (Odoo location_id).',
    )
    location_dest    = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings_in', help_text='Destino (Odoo location_dest_id).',
    )
    # ≙ ``origin`` (``odoo19c: :556-558``, ``index='trigram'``). Entra en este
    # pase porque ``stock_move._compute_display_name`` lo lee: sin el campo, el
    # nombre visible del movimiento no se puede portar sin inventar una
    # divergencia. El índice trigram es la tarea **#95**.
    origin           = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        help_text='Documento de origen (Odoo origin).',
    )
    # Odoo stock.picking.sale_id — el enlace lo añade el módulo sale_stock
    # (stock_picking se inherita en sale_stock/models/stock_picking.py). Aquí el
    # albarán conoce su orden de venta canónica; el sub-estado de preparación
    # (state confirmed/assigned) se proyecta a IN_PREPARATION cuando aún no hay
    # guía de transportista (V5a de analisis-unificar-orders-sale, H-SALE-09).
    sale_order       = fields.Many2one(
        'sale.SaleOrder', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings', help_text='Orden de venta (Odoo stock.picking.sale_id).',
    )
    # ≙ ``is_locked`` (``odoo19c: :658-660``). Entra en este pase porque el
    # movimiento lo consume en tres derivados (``is_locked``,
    # ``is_initial_demand_editable``, ``is_date_editable``) — declararlo aquí es
    # más barato que fabricar una divergencia en ``stock_move``.
    is_locked        = fields.Boolean(
        default=True,
        help_text='Odoo is_locked. Con el albarán sin validar permite cambiar '
                  'la demanda inicial; ya validado, las cantidades hechas.',
    )
    # ≙ ``picking_type_id`` (``odoo19c: :620-623``). La referencia lo declara
    # **requerido** con default por contexto; aquí es nulable porque el default
    # de la fuente (``_default_picking_type_id``) sale del contexto de acción,
    # que este árbol no tiene — un albarán creado por API llegaría sin él y la
    # columna requerida lo haría reventar.
    #
    # Sin este campo, ``StockMoveLine.picking_type`` y ``picking_code``
    # —portados como property que leen ``self.picking.picking_type``— fallaban
    # con ``AttributeError``: la pareja lector/campo estaba rota por el lado
    # del campo. Ver :ref:`h-api-608`.
    picking_type     = fields.Many2one(
        'stock.StockPickingType', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='pickings', db_index=True,
        verbose_name='Tipo de operación',
        help_text='Tipo de operación que gobierna el albarán '
                  '(Odoo picking_type_id).',
    )
    # ≙ ``move_type`` (``odoo19c: :571-574``, ``compute='_compute_move_type'``
    # ``store=True required=True readonly=False precompute=True``). Entra en
    # este pase porque ``stock_move._get_relevant_state_among_moves`` **ya lo
    # leía** —``albaran.move_type == 'one'``— sobre un modelo que no lo
    # declaraba: la pareja lector/campo estaba rota por el lado del campo, y
    # sólo reventaba en ejecución. Ver :ref:`h-api-625`.
    #
    # Su ``compute`` copia el del tipo de operación (``_compute_move_type``:
    # ``record.move_type = record.picking_type_id.move_type``); aquí lo aplica
    # ``save()`` mientras el campo no se haya fijado a mano.
    #
    # **Sin ``default=``, y es deliberado.** El ``default='direct'`` de la
    # referencia está en ``StockPickingType.move_type`` (``:153``), no aquí:
    # en el albarán el valor lo pone el ``compute`` con ``precompute=True``,
    # que en la fuente **cede ante un valor explícito** al crear. Un
    # ``default=`` aquí borra la distinción entre «no lo dieron» y «lo dieron
    # igual al del tipo», que es justo la que ``save()`` necesita para no
    # pisar al llamador. Ver :ref:`h-api-687`.
    move_type        = fields.Selection(
        max_length=8, choices=MOVE_TYPE_CHOICES,
        verbose_name='Política de envío',
        help_text='Parcial o todo junto (Odoo move_type). Sale del tipo de '
                  'operación y se puede sobreescribir por albarán.',
    )
    # ≙ ``partner_id`` (``odoo19c: :631-633``, ``index='btree_not_null'``).
    # El índice parcial de la referencia es la tarea **#95**; aquí un índice
    # normal sobre una columna nulable.
    partner          = fields.Many2one(
        'base.ResPartner', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings', db_index=True, verbose_name='Contacto',
        help_text='Contacto del albarán (Odoo partner_id). Lo borra '
                  '``_assign_picking_values`` cuando el albarán agrupa '
                  'movimientos de contactos distintos.',
    )
    # ≙ ``company_id`` (``odoo19c: :634-636``, ``related='picking_type_id.company_id'``
    # ``store=True readonly=True index=True``). Nulable aquí porque
    # ``picking_type`` lo es (ver arriba): con el tipo ausente no hay empresa
    # de la que derivarla.
    company          = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.PROTECT,
        related_name='stock_pickings', db_index=True,
        help_text='Empresa (Odoo company_id, related del tipo de operación).',
    )
    # ≙ ``user_id`` (``odoo19c: :637-641``, ``tracking=True copy=False``). Su
    # ``domain`` de la referencia acota a los usuarios de ``stock.group_stock_user``;
    # el grupo aún no se siembra, así que la acotación queda declarada y no
    # inventada — la impone quien asigne, no el campo.
    user             = fields.Many2one(
        ResUsers, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='stock_pickings', verbose_name='Responsable',
        help_text='Responsable del albarán (Odoo user_id).',
    )
    # ≙ ``printed`` (``odoo19c: :655``, ``copy=False``). Lo lee
    # ``stock_move._search_picking_for_assignation_domain``: un albarán ya
    # impreso no admite que se le añadan movimientos.
    printed          = fields.Boolean(
        default=False, verbose_name='Impreso',
        help_text='El albarán ya se imprimió (Odoo printed). Un albarán '
                  'impreso no recibe movimientos nuevos por asignación.',
    )
    # ≙ ``note`` (``odoo19c: :559``, ``fields.Html``). Desde #554 ``Html``
    # tiene identidad de clase (misma columna TEXT; el saneo sigue siendo de
    # la capa UI), así que se declara fiel a la fuente.
    note             = fields.Html(
        blank=True, default='', verbose_name='Notas',
        help_text='Notas libres del albarán (Odoo note).',
    )
    # ≙ ``priority`` (``odoo19c: :592-594``). Reusa ``PROCUREMENT_PRIORITIES``
    # de ``stock.move`` — el mismo símbolo, no un duplicado.
    priority         = fields.Selection(
        max_length=1, choices=PROCUREMENT_PRIORITIES, default='0',
        verbose_name='Prioridad',
        help_text='Los productos con prioridad alta se reservan primero '
                  '(Odoo priority).',
    )
    # ≙ ``date_done`` (``odoo19c: :610``).
    date_done        = fields.Datetime(
        null=True, blank=True, verbose_name='Fecha de proceso',
        help_text='Fecha en que el albarán se procesó o canceló '
                  '(Odoo date_done).',
    )
    # ≙ ``backorder_id``/``backorder_ids`` (``odoo19c: :560-565``). D-9: sólo
    # la relación estructural — quién CREA el backorder es
    # ``_create_backorder``, en el grupo bloqueado.
    backorder        = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='backorder_ids', db_index=True,
        verbose_name='Backorder de',
        help_text='Si este albarán se dividió, apunta al albarán que ya se '
                  'procesó (Odoo backorder_id).',
    )
    # ≙ ``return_id``/``return_ids`` (``odoo19c: :566-568``). El nombre
    # cambia de ``return_id`` a ``return_of`` — ``return`` es palabra
    # reservada de Python y no puede ser un atributo de instancia sin
    # comillas; mismo criterio que D-1 en ``StockPickingType.sequence_id``.
    return_of        = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='return_ids', db_index=True,
        verbose_name='Devolución de',
        help_text='Si este albarán se creó como devolución de otro, apunta '
                  'al original (Odoo return_id).',
    )
    # ≙ ``owner_id`` (``odoo19c: :649-651``).
    owner            = fields.Many2one(
        'base.ResPartner', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='owned_pickings', verbose_name='Propietario asignado',
        help_text='Al validar, los productos se asignan a este propietario '
                  '(Odoo owner_id).',
    )

    class Meta:
        db_table = 'stock_picking'
        # ≙ ``_order = "priority desc, scheduled_date asc, id desc"``. Con
        # ``priority`` ya portado y ``scheduled_date`` aún en el grupo
        # BLOQUEADO (``_compute_scheduled_date``), ``created_at`` sustituye al
        # segundo eje hasta que ese campo aterrice.
        ordering = ['-priority', '-created_at', '-id']
        verbose_name = 'Transferencia de inventario'
        verbose_name_plural = 'Transferencias de inventario'

    def __str__(self) -> str:
        return self.name or f'{self.state}:{self.pk}'

    def save(self, *args, **kwargs):
        """Aplica los dos ``compute`` almacenados que dependen del tipo de operación.

        ≙ ``_compute_move_type`` (``odoo19c: :719-721``, ``@api.depends('picking_type_id')``)
        y el ``related='picking_type_id.company_id'`` de ``company_id``
        (``odoo19c: :634-636``). Los dos son ``store=True``, así que su hogar
        aquí es ``save()`` — el mecanismo que este árbol ya usa para los
        ``compute`` con columna (:ref:`h-api-591`).

        **Divergencia declarada:** la fuente los recalcula cuando su
        ``depends`` cambia, sea cual sea el camino. Aquí se aplican al insertar
        y cuando ``picking_type`` viene en ``update_fields`` — que son los dos
        momentos en que este ORM puede saber que el tipo cambió sin releer la
        fila.

        **``move_type`` no se deriva igual que ``company``, y la diferencia es
        de la fuente.** Allá es ``precompute=True`` con ``readonly=False``: el
        ``compute`` sólo **suple** el valor que el llamador no dio, y un valor
        explícito al crear gana. Por eso aquí se deriva al insertar **sólo si
        viene vacío**. ``company`` no tiene esa cláusula —es ``related``, sin
        ``readonly=False``— así que se deriva siempre. Ver :ref:`h-api-687`.
        """
        campos = kwargs.get('update_fields')
        inserting = self._state.adding
        cambio_tipo = campos is not None and 'picking_type' in campos
        if (inserting or cambio_tipo) and self.picking_type_id:
            tocados = ['company']
            self.company = self.picking_type.company
            if cambio_tipo or not self.move_type:
                self.move_type = self.picking_type.move_type
                tocados.append('move_type')
            if campos is not None:
                kwargs['update_fields'] = list(dict.fromkeys([*campos, *tocados]))
        return super().save(*args, **kwargs)

    # -- ciclo de vida: crear, escribir, borrar --

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :1117-1139``).

        Sin nombre explícito (o con el placeholder ``/``), y con un tipo de
        operación que tenga secuencia, el nombre sale de
        ``picking_type.sequence_id.next_by_id()`` — el equivalente de
        ``next_by_id()`` en este ORM (``ir.sequence.get_next``).

        **Divergencia declarada (D-8):** la referencia llama
        ``pickings._autoconfirm_picking()`` al final — auto-confirma un
        albarán cuyos movimientos ya están confirmados. Ese mecanismo vive en
        el grupo BLOQUEADO (backorder/autoconfirm, ver el docstring de la
        clase); aquí el llamador confirma explícitamente con
        :meth:`action_confirm`.
        """
        for vals in vals_list:
            picking_type = vals.get('picking_type')
            if vals.get('name', '') in ('', '/') and picking_type is not None \
                    and picking_type.sequence_id is not None:
                vals['name'] = picking_type.sequence_id.next_by_id()
        return super().create(vals_list)

    def write(self, vals):
        """≙ ``write`` (``odoo19c: :1139-1170``).

        Tres reglas de la referencia, en su orden:

        1. cambiar el tipo de operación de un albarán ya hecho/cancelado está
           prohibido;
        2. cambiar el tipo de operación renumera (nueva secuencia) y
           recalcula las dos ubicaciones por defecto;
        3. ``date_done`` se propaga a los movimientos ya hechos, y un cambio
           de ubicación/contacto se propaga a los movimientos cuyo destino no
           sea una pérdida de inventario.
        """
        if 'picking_type' in vals and self.state in (
                self.STATE_DONE, self.STATE_CANCEL):
            raise UserError(_(
                'Cambiar el tipo de operación de este registro está '
                'prohibido en este punto.'))

        nuevo_tipo = vals.get('picking_type')
        if nuevo_tipo is not None and nuevo_tipo != self.picking_type:
            if nuevo_tipo.sequence_id is not None:
                self.name = nuevo_tipo.sequence_id.next_by_id()
            vals.setdefault('location', nuevo_tipo.default_location_src)
            vals.setdefault(
                'location_dest', nuevo_tipo.default_location_dest)

        for nombre, valor in vals.items():
            setattr(self, nombre, valor)
        self.save()

        stock_move = apps.get_model('stock', 'StockMove')
        if 'date_done' in vals:
            stock_move.objects.filter(
                picking=self, state=self.STATE_DONE,
            ).update(date=vals['date_done'])

        siguientes = {}
        if 'location' in vals:
            siguientes['location'] = vals['location']
        if 'location_dest' in vals:
            siguientes['location_dest'] = vals['location_dest']
        if 'partner' in vals:
            siguientes['partner'] = vals['partner']
        if siguientes:
            stock_move.objects.filter(picking=self).exclude(
                location_dest__usage=USAGE_INVENTORY,
            ).update(**siguientes)

        return self

    def unlink(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: :1170-1175``:
        ``self.move_ids._action_cancel(); self.move_ids.unlink()``).

        Dos fases, en el orden de la fuente — cancelar **todos**, verificar
        **todos**, recién entonces borrar. La guarda real la trae
        ``StockMove._unlink_if_draft_or_cancel`` (``stock_move.py:1458-1466``,
        ≙ ``odoo19c: :2333-2335``): bloquea un movimiento que **no** esté en
        ``draft``/``cancel`` **y además** esté encadenado
        (``move_orig_ids``/``move_dest_ids``). Un movimiento ``done`` aislado
        —sin cadena— sí se cancela y se borra; uno encadenado no, porque
        borrarlo dejaría la cadena rota.

        **Por qué NO es un simple ``for`` cancelar-y-borrar de una pasada:**
        borrar el primer movimiento de una cadena hace que el segundo, al
        revisarse, ya no la vea —``move_dest_ids.exists()`` cambia de valor
        entre movimientos— y el resultado dependería del orden de iteración.
        La referencia no tiene ese problema: en Odoo el ``unlink()`` de un
        recordset verifica la guarda de **todos** los registros contra el
        estado que tenían al invocarse, antes de borrar el primero. Aquí se
        replica con tres pasadas explícitas sobre la misma lista materializada,
        envueltas en una transacción — si la verificación revienta, la
        cancelación tampoco queda a medias.

        **Por qué se borra uno por uno y no con** ``self.move_ids.all().delete()``:
        un ``QuerySet.delete()`` de Django es SQL a granel y **no** pasa por
        ``Model.delete()`` de cada fila — saltaría la guarda entera.
        """
        moves = list(self.move_ids.all())
        with transaction.atomic():
            for move in moves:
                move._action_cancel()
            for move in moves:
                move._unlink_if_draft_or_cancel()
            for move in moves:
                move.delete()
            return super().delete(*args, **kwargs)

    delete = unlink   # el nombre de Django apunta al de la referencia

    @property
    def reference_ids(self):
        """≙ ``reference_ids`` (``related="move_ids.reference_ids"``, ``odoo19c: :590-591``).

        Las referencias de un albarán son las de sus movimientos — no tiene
        ninguna propia. Es ``related`` sin ``store`` allá, así que es property
        aquí (``porte-completo-no-parcial.md``); lo consume
        ``stock_move._set_references``.
        """
        reference = apps.get_model('stock', 'StockReference')
        return reference.objects.filter(move_ids__picking_id=self.pk).distinct()

    @property
    def is_date_editable(self) -> bool:
        """≙ ``_compute_is_date_editable`` (``odoo19c: :749-754``).

        Terminado o cancelado, la fecha sólo se toca si el albarán no está
        bloqueado; en cualquier otro estado siempre se puede.

        Es property y no columna porque la fuente lo declara ``compute=`` sin
        ``store=`` — su ORM lo recalcula en cada lectura.
        """
        if self.state in (self.STATE_DONE, self.STATE_CANCEL):
            return not self.is_locked
        return True

    # -- computados de sólo lectura (D-6: property, sin store) --

    @property
    def return_count(self):
        """≙ ``return_count`` / ``_compute_return_count`` (``:569``, ``:1007-1009``)."""
        return self.return_ids.count()

    @property
    def has_tracking(self):
        """≙ ``has_tracking`` / ``_compute_has_tracking`` (``:680``, ``:715-717``)."""
        return any(m.has_tracking != 'none' for m in self.move_ids.all())

    @property
    def has_scrap_move(self):
        """≙ ``has_scrap_move`` / ``_has_scrap_move`` (``:618-619``, ``:933-940``)."""
        return any(
            m.location_dest_usage == USAGE_INVENTORY
            for m in self.move_ids.all())

    @property
    def date_deadline(self):
        """≙ ``date_deadline`` / ``_compute_date_deadline`` (``:599-600``, ``:917-923``).

        Con envío ``direct`` (parcial en cuanto se pueda), el límite es el más
        temprano de los movimientos abiertos; con ``one`` (todo junto), el
        más tardío.
        """
        fechas = [
            m.date_deadline for m in self.move_ids.all()
            if m.state != self.STATE_CANCEL and m.date_deadline is not None
        ]
        if not fechas:
            return None
        return min(fechas) if self.move_type == 'direct' else max(fechas)

    @property
    def delay_alert_date(self):
        """≙ ``delay_alert_date`` / ``_compute_delay_alert_date`` (``:607``, ``:737-742``)."""
        fechas = [
            m.delay_alert_date for m in self.move_ids.all()
            if m.delay_alert_date is not None
        ]
        return max(fechas) if fechas else None

    def _get_next_transfers(self):
        """≙ ``_get_next_transfers`` (``odoo19c: :1024-1026``).

        Los albaranes que reciben lo que este produce (por
        ``move_dest_ids``), excluyendo las devoluciones de sí mismo.
        """
        stock_picking = apps.get_model('stock', 'StockPicking')
        ids = {
            destino.picking_id
            for m in self.move_ids.all()
            for destino in m.move_dest_ids.all()
            if destino.picking_id is not None
        }
        propios = set(self.return_ids.values_list('pk', flat=True))
        return stock_picking.objects.filter(
            pk__in=[p for p in ids if p not in propios])

    @property
    def show_next_pickings(self) -> bool:
        """≙ ``show_next_pickings`` / ``_compute_show_next_pickings`` (``:693``, ``:1028-1029``)."""
        return self._get_next_transfers().exists()

    @property
    def warehouse_address(self):
        """≙ ``warehouse_address_id`` (``odoo19c: :624``, ``related`` de dos saltos)."""
        if self.picking_type is None or self.picking_type.warehouse is None:
            return None
        return self.picking_type.warehouse.partner

    @property
    def picking_type_code(self):
        """≙ ``picking_type_code`` (``odoo19c: :625-627``, ``related``)."""
        return self.picking_type.code if self.picking_type is not None else None

    @property
    def picking_type_entire_packs(self) -> bool:
        """≙ ``picking_type_entire_packs`` (``odoo19c: :628``, ``related``)."""
        return bool(
            self.picking_type is not None
            and self.picking_type.show_entire_packs)

    @property
    def use_create_lots(self) -> bool:
        """≙ ``use_create_lots`` (``odoo19c: :629``, ``related``).

        ≙ ``_compute_use_create_lots`` (``odoo19c: stock/models/stock_picking.py``).
        """
        return bool(
            self.picking_type is not None and self.picking_type.use_create_lots)

    @property
    def use_existing_lots(self) -> bool:
        """≙ ``use_existing_lots`` (``odoo19c: :630``, ``related``).

        ≙ ``_compute_use_existing_lots`` (``odoo19c: stock/models/stock_picking.py``).
        """
        return bool(
            self.picking_type is not None
            and self.picking_type.use_existing_lots)

    @property
    def show_operations(self) -> bool:
        """≙ ``show_operations`` (``odoo19c: :678``, ``related``)."""
        return bool(
            self.picking_type is not None and self.picking_type.show_operations)

    @property
    def product(self):
        """≙ ``product_id`` (``odoo19c: :675``, ``related='move_ids.product_id'``).

        La referencia relaciona por un one2many — sirve sobre todo para
        búsqueda. Aquí, para lectura, el producto del primer movimiento; sin
        movimientos, ``None``.
        """
        primero = self.move_ids.first()
        return primero.product if primero is not None else None

    @property
    def lot(self):
        """≙ ``lot_id`` (``odoo19c: :676``, ``related='move_line_ids.lot_id'``)."""
        primera = self.move_line_ids.first()
        return primera.lot if primera is not None else None

    @property
    def picking_warning_text(self) -> str:
        """≙ ``picking_warning_text`` / ``_compute_picking_warning_text`` (``:705-708``, ``:1002-1011``).

        Concatena el aviso del contacto y, si tiene empresa matriz, el de
        ella. Sin ``self.env.user.has_group('stock.group_warning_stock')`` —
        ese grupo no existe en este stack — el aviso siempre se calcula; la
        gate de visibilidad queda del lado de quien consuma el campo.
        """
        if self.partner is None:
            return ''
        texto = ''
        if self.partner.picking_warn_msg:
            texto += self.partner.picking_warn_msg + '\n'
        matriz = getattr(self.partner, 'parent', None)
        if matriz is not None and matriz.picking_warn_msg:
            texto += matriz.picking_warn_msg + '\n'
        return texto

    @classmethod
    def calculate_date_category(cls, fecha):
        """≙ ``calculate_date_category`` (``odoo19c: :1799-1836``).

        Clasifica ``fecha`` en ``before``/``yesterday``/``today``/``day_1``
        (mañana)/``day_2``/``after``, según la zona horaria activa del
        proceso.

        **Divergencia declarada (D-7):** la referencia usa
        ``fields.Datetime.context_timestamp(self.env.user, ...)`` + ``pytz``
        — sin usuario ni zona por sesión, el borde del día sale de
        ``django.utils.timezone.localtime``, que ya resuelve la zona activa
        del proceso (``settings.TIME_ZONE``).
        """
        if not fecha:
            return ''
        inicio_hoy = timezone.localtime(timezone.now()).replace(
            hour=0, minute=0, second=0, microsecond=0)
        inicio_ayer = inicio_hoy - datetime.timedelta(days=1)
        inicio_dia_1 = inicio_hoy + datetime.timedelta(days=1)
        inicio_dia_2 = inicio_hoy + datetime.timedelta(days=2)
        inicio_dia_3 = inicio_hoy + datetime.timedelta(days=3)
        fecha = timezone.localtime(fecha) if timezone.is_aware(fecha) else fecha
        if fecha < inicio_ayer:
            return 'before'
        if fecha < inicio_hoy:
            return 'yesterday'
        if fecha < inicio_dia_1:
            return 'today'
        if fecha < inicio_dia_2:
            return 'day_1'
        if fecha < inicio_dia_3:
            return 'day_2'
        return 'after'

    @classmethod
    def date_category_to_domain(cls, field_name, categoria):
        """≙ ``date_category_to_domain`` (``odoo19c: :1842-1885``).

        Devuelve un dict de dos claves ``lt``/``gte`` con los límites de la
        categoría, listo para ``queryset.filter(**{f'{field_name}__lt': ...})``
        — el equivalente Django de la lista de tuplas ``(operador, valor)`` de
        la referencia.
        """
        inicio_hoy = timezone.localtime(timezone.now()).replace(
            hour=0, minute=0, second=0, microsecond=0)
        inicio_ayer = inicio_hoy - datetime.timedelta(days=1)
        inicio_dia_1 = inicio_hoy + datetime.timedelta(days=1)
        inicio_dia_2 = inicio_hoy + datetime.timedelta(days=2)
        inicio_dia_3 = inicio_hoy + datetime.timedelta(days=3)
        by_category = {
            'before': {f'{field_name}__lt': inicio_ayer},
            'yesterday': {
                f'{field_name}__gte': inicio_ayer,
                f'{field_name}__lt': inicio_hoy},
            'today': {
                f'{field_name}__gte': inicio_hoy,
                f'{field_name}__lt': inicio_dia_1},
            'day_1': {
                f'{field_name}__gte': inicio_dia_1,
                f'{field_name}__lt': inicio_dia_2},
            'day_2': {
                f'{field_name}__gte': inicio_dia_2,
                f'{field_name}__lt': inicio_dia_3},
            'after': {f'{field_name}__gte': inicio_dia_3},
        }
        return by_category.get(categoria)

    def action_confirm(self):
        """Confirma la transferencia y sus movimientos (Odoo action_confirm)."""
        if not self.name:
            self.name = f'WH/{uuid.uuid4().hex[:8].upper()}'
        self.state = self.STATE_CONFIRMED
        self.save(update_fields=['name', 'state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_confirm()
        return self

    def action_assign(self):
        """Reserva/asigna la disponibilidad (Odoo action_assign)."""
        self.state = self.STATE_ASSIGNED
        self.save(update_fields=['state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_assign()
        return self

    def button_validate(self):
        """Valida la transferencia → hecho (Odoo button_validate)."""
        for move in self.move_ids.all():
            move._action_done()
        self.state = self.STATE_DONE
        self.save(update_fields=['state', 'updated_at'])
        return self

    def action_cancel(self):
        """Cancela la transferencia (Odoo action_cancel)."""
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_cancel()
        return self

    # -- tarea #521 — grupos C (mensajería) y E (estado reactivo/UI) --
    #
    # Cierra parte de los grupos que ``docstring`` (arriba) etiquetaba
    # "Backorder/wizard — 10" y "Sanity/reserva/reporte de cierre — 22" (el
    # primero es Grupo C de H-API-685; el segundo mezclaba Grupo C y Grupo E)
    # y "Estado reactivo/ubicación/UI — 31" (Grupo E). Divergencia frente a
    # ese bloqueo, declarada aquí y en el hallazgo H-API-692: los símbolos de
    # abajo NO reescriben ``_action_done`` ni tocan la máquina de reservas —
    # son independientes de ella, y su razón de bloqueo original ("reescriben
    # _action_done... arriesga contradecir stock_move.py") no les aplica
    # símbolo a símbolo. ``_action_done`` en sí, ``do_unreserve``,
    # ``_sanity_check``, ``action_split_transfer``, ``_pre_action_done_hook``,
    # ``button_scrap``, ``action_see_move_scrap``, ``action_picking_move_tree``,
    # ``_can_return``, ``action_see_returns``, ``_is_to_external_location`` y
    # todo el clúster de backorder (``_check_backorder``,
    # ``_autoconfirm_picking``, ``_get_moves_to_backorder``,
    # ``_create_backorder_picking``, ``_create_backorder``,
    # ``_action_generate_backorder_wizard``, ``_should_show_transfers``,
    # ``_should_ignore_backorders``, ``_get_without_quantities_error_message``)
    # SIGUEN bloqueados — el primer bloque porque de verdad exige la máquina
    # de reservas completa de ``stock_move.py``; el segundo porque exige el
    # modelo wizard ``stock.backorder.confirmation``, que no existe en este
    # árbol. Ver H-API-692.

    def _compute_state(self):
        """≙ ``_compute_state`` (``odoo19c: :816-848``).

        Deriva el estado del albarán a partir del de sus movimientos y lo
        persiste. Método de RE-derivación explícita — no sustituye las
        asignaciones directas de ``action_confirm``/``action_assign``/
        ``button_validate``/``action_cancel`` (D-8 ya declaró esa forma);
        sirve para resincronizar el estado tras un cambio externo a los
        movimientos (p. ej. tras un ``_onchange_location_id`` o una edición
        en bloque de ``move_ids``).

        **Divergencia declarada:** el vocabulario de estados de la
        referencia distingue más matices de "esperando"/"parcial" de los
        que este ``STATE_CHOICES`` (6 valores) separa; se colapsan al valor
        más cercano, igual que ``StockMove._get_relevant_state_among_moves``
        ya hace para ``assigned``.
        """
        stock_move = apps.get_model('stock', 'StockMove')
        moves = list(self.move_ids.all())
        if not moves or any(m.state == stock_move.STATE_DRAFT for m in moves):
            nuevo_estado = self.STATE_DRAFT
        elif all(m.state == stock_move.STATE_CANCEL for m in moves):
            nuevo_estado = self.STATE_CANCEL
        elif all(m.state in (stock_move.STATE_CANCEL, stock_move.STATE_DONE)
                 for m in moves):
            hechos = [m for m in moves if m.state == stock_move.STATE_DONE]
            todo_hecho_es_merma = all(
                m.location_dest_usage == USAGE_INVENTORY for m in hechos)
            algun_cancelado_no_merma = any(
                m.state == stock_move.STATE_CANCEL
                and m.location_dest_usage != USAGE_INVENTORY
                for m in moves)
            if todo_hecho_es_merma and algun_cancelado_no_merma:
                nuevo_estado = self.STATE_CANCEL
            else:
                nuevo_estado = self.STATE_DONE
        elif (self.location is not None
                and self.location.should_bypass_reservation()
                and all(m.procure_method == stock_move.PROCURE_MAKE_TO_STOCK
                        for m in moves)):
            nuevo_estado = self.STATE_ASSIGNED
        else:
            relevante = moves[0]._get_relevant_state_among_moves(moves)
            nuevo_estado = (
                self.STATE_ASSIGNED if relevante == 'partially_available'
                else relevante)
        self.state = nuevo_estado
        self.save(update_fields=['state', 'updated_at'])
        return nuevo_estado

    def _onchange_picking_type(self):
        """≙ ``_onchange_picking_type`` (``odoo19c: :1093-1099``).

        Sólo en borrador: al fijar/cambiar el tipo de operación, sus
        movimientos existentes se realinean al mismo tipo y empresa — evita
        que un albarán en edición arrastre movimientos de un tipo distinto.
        """
        if self.picking_type is None or self.state != self.STATE_DRAFT:
            return
        stock_move = apps.get_model('stock', 'StockMove')
        stock_move.objects.filter(picking=self).exclude(
            picking_type=self.picking_type,
        ).update(picking_type=self.picking_type)
        stock_move.objects.filter(picking=self).exclude(
            company=self.company,
        ).update(company=self.company)

    def _onchange_location_id(self):
        """≙ ``_onchange_location_id`` (``odoo19c: :1101-1113``).

        Propaga la nueva ubicación origen a los movimientos del albarán, y
        avisa si alguno de los movimientos encadenados (``move_orig_ids``)
        tiene una línea reservada fuera del nuevo árbol de ubicaciones — la
        reserva se perdería al guardar.
        """
        stock_move = apps.get_model('stock', 'StockMove')
        stock_move.objects.filter(picking=self).update(location=self.location)
        for move in self.move_ids.all():
            if not move.move_orig_ids.exists():
                continue
            for ml in move.move_line_ids.all():
                if ml.location is None or not ml.location.parent_path:
                    continue
                ruta = [int(x) for x in ml.location.parent_path.split('/') if x]
                if self.location is not None and self.location.pk not in ruta:
                    return {
                        'warning': {
                            'title': _('Aviso: cambio de ubicación origen'),
                            'message': _(
                                'Actualizar la ubicación de esta '
                                'transferencia liberará la reserva actual. '
                                'Se intentará reservar en la nueva ubicación '
                                'y el enlace con transferencias previas se '
                                'perderá.\n\nPara evitarlo, descarta el '
                                'cambio antes de guardar.'),
                        }
                    }
        return None

    def action_detailed_operations(self):
        """≙ ``action_detailed_operations`` (``odoo19c: :1217-1236``).

        **Divergencia declarada:** sin registro de vistas (``self.env.ref``
        de una vista XML), el descriptor de acción se arma directo — mismo
        contrato de dominio y contexto que la referencia, sin ``view_id``.
        ``show_lots_text`` no entra en el contexto: depende de
        ``_compute_show_lots_text``, que sigue BLOQUEADO (Grupo D).
        """
        return {
            'name': _('Operaciones detalladas'),
            'view_mode': 'list',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move.line',
            'domain': [('picking', '=', self.pk)],
            'context': {
                'sml_specific_default': True,
                'default_picking': self.pk,
                'default_location': self.location_id,
                'default_location_dest': self.location_dest_id,
                'default_company': self.company_id,
                'picking_code': self.picking_type_code,
                'create': self.state not in (self.STATE_DONE, self.STATE_CANCEL),
            },
        }

    def action_next_transfer(self):
        """≙ ``action_next_transfer`` (``odoo19c: :1238-1256``)."""
        siguientes_ids = list(
            self._get_next_transfers().values_list('pk', flat=True))
        if len(siguientes_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'views': [[False, 'form']],
                'res_id': siguientes_ids[0],
            }
        return {
            'name': _('Siguientes transferencias'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', siguientes_ids)],
        }

    def get_empty_list_help(self, help_message=''):
        """≙ ``get_empty_list_help`` (``odoo19c: :1079-1084``).

        **Divergencia declarada:** sin motor QWeb (``ir.ui.view.
        _render_template`` no existe en este stack — ver ``ir_template_expressions.py``), el
        mensaje se arma como texto plano equivalente por tipo de operación.
        """
        if help_message:
            return help_message
        code = self.picking_type_code
        if code == 'incoming':
            return _('Registra una recepción de mercancía.')
        if code == 'outgoing':
            return _('Registra una entrega al cliente.')
        if code == 'internal':
            return _('Registra un movimiento interno de mercancía.')
        return ''

    def action_toggle_is_locked(self):
        """≙ ``action_toggle_is_locked`` (``odoo19c: :1529-1532``)."""
        self.is_locked = not self.is_locked
        self.save(update_fields=['is_locked', 'updated_at'])
        return True

    def _add_reference(self, reference=False):
        """≙ ``_add_reference`` (``odoo19c: :2118-2121``).

        Enlaza cada referencia de ``reference`` a TODOS los movimientos del
        albarán — ``move.reference_ids`` es el M2M real declarado en
        ``stock_reference.py``.
        """
        if not reference:
            return
        for move in self.move_ids.all():
            move.reference_ids.add(*reference)

    def _remove_reference(self, reference):
        """≙ ``_remove_reference`` (``odoo19c: :2124-2127``)."""
        if not reference:
            return
        for move in self.move_ids.all():
            move.reference_ids.remove(*reference)

    def _get_impacted_pickings(self, moves):
        """≙ ``_get_impacted_pickings`` (``odoo19c: :1738-1760``).

        Recorre ``move_dest_ids`` en cascada desde ``moves`` y devuelve los
        albaranes de cada movimiento visitado (directo e indirecto) — lo usa
        ``_log_less_quantities_than_expected`` para avisar de un cambio de
        cantidad en cadena.
        """
        stock_picking = apps.get_model('stock', 'StockPicking')
        visitados = set()
        to_explore = list(moves)
        impactados_ids = set()
        while to_explore:
            move = to_explore.pop()
            if move.pk in visitados:
                continue
            visitados.add(move.pk)
            if move.picking_id is not None:
                impactados_ids.add(move.picking_id)
            to_explore.extend(move.move_dest_ids.all())
        if not impactados_ids:
            return stock_picking.objects.none()
        return stock_picking.objects.filter(pk__in=impactados_ids)

    def _log_activity_get_documents(
            self, orig_obj_changes, stream_field, stream,
            groupby_method=False):
        """≙ ``_log_activity_get_documents`` (``odoo19c: :1605-1673``).

        Agrupa los movimientos alcanzables desde ``orig_obj_changes`` (por
        ``stream_field``, en el sentido ``stream``) en pares
        (documento, responsable) → contexto de renderizado, para que
        ``_log_activity`` publique una nota por grupo.

        **Divergencia declarada:** el flujo ``'UP'`` depende de
        ``StockMove._get_upstream_documents_and_responsibles``, que en este
        árbol todavía no agrega ningún par (documento, responsable) —
        devuelve siempre conjunto vacío (mecanismo preexistente, no se toca
        aquí; ver el propio docstring de ese método). El flujo ``'UP'`` por
        tanto queda funcionalmente inerte (no publica nada) hasta que esa
        pieza se complete; no lanza error.
        """
        if not orig_obj_changes:
            return {}
        move_to_orig = {}
        for orig_obj in orig_obj_changes:
            for move in getattr(orig_obj, stream_field).all():
                move_to_orig.setdefault(move.pk, []).append(orig_obj)

        grouped = {}
        if stream == 'DOWN':
            if not groupby_method:
                raise ValueError(
                    'Hace falta un groupby_method para el flujo DOWN.')
            for orig_obj in orig_obj_changes:
                for move in getattr(orig_obj, stream_field).all():
                    grouped.setdefault(groupby_method(move), []).append(move)
        elif stream == 'UP':
            for orig_obj in orig_obj_changes:
                for move in getattr(orig_obj, stream_field).all():
                    for documento, responsable in (
                            move._get_upstream_documents_and_responsibles()):
                        grouped.setdefault(
                            (documento, responsable), []).append(move)
        else:
            raise ValueError('Flujo desconocido: %r' % stream)

        documentos = {}
        for clave, moves in grouped.items():
            parent, responsable = clave
            if not parent:
                continue
            rendering_context = {
                move: (orig_obj, orig_obj_changes[orig_obj])
                for move in moves
                for orig_obj in move_to_orig.get(move.pk, [])
            }
            documentos[(parent, responsable)] = rendering_context
        return documentos

    def _log_activity(self, render_method, documents):
        """≙ ``_log_activity`` (``odoo19c: :1675-1701``).

        Publica una actividad por (documento, responsable) en ``documents``,
        con la nota que ``render_method`` construye a partir de su contexto.

        **Divergencia declarada (dos):**

        1. Sin mecanismo ``sudo()`` en este stack (no hay elevación de
           privilegios portada), la actividad se planifica con los permisos
           del llamador.
        2. ``mail.activity.user`` es ``NOT NULL`` en este esquema y
           ``MailActivityMixin.activity_schedule`` (``addons/mail/models/
           mail_activity_mixin.py``, fuera de lo escribible de este pase) no
           cae a ``env.user`` cuando ``user`` llega ``None`` — a diferencia
           de la referencia (``user_id or self.env.user.id``), porque este
           stack no tiene un usuario de sesión implícito. Un par
           ``(documento, responsable=None)`` se omite en vez de fallar con
           ``IntegrityError``; se documenta como pendiente aguas arriba, no
           se silencia.
        """
        for (parent, responsable), rendering_context in documents.items():
            if responsable is None:
                continue
            nota = render_method(rendering_context)
            parent.activity_schedule(
                'mail.mail_activity_data_warning',
                date_deadline=datetime.date.today(),
                note=nota,
                user=responsable,
            )

    def _log_less_quantities_than_expected(self, moves):
        """≙ ``_log_less_quantities_than_expected`` (``odoo19c: :1703-1735``).

        Publica una actividad de aviso sobre el albarán que sigue a los
        movimientos cuya cantidad reservada bajó — ``moves`` es un dict
        ``{movimiento: (cantidad_nueva, cantidad_vieja)}``.

        **Divergencia declarada:** el render QWeb de la referencia
        (plantilla ``stock.exception_on_picking``) no existe en este stack
        (sin compilador QWeb activo — ver ``ir_template_expressions.py``); la nota se arma
        como texto plano equivalente.
        """
        def keys_in_groupby(move):
            responsable = move.picking.user if move.picking is not None else None
            return (move.picking, responsable)

        def render_note(rendering_context):
            origin_moves = [orig for (orig, _cambio) in rendering_context.values()]
            origin_pickings = {
                m.picking for m in origin_moves if m.picking is not None}
            move_dest_ids = list(rendering_context.keys())
            destinos_pickings = {
                m.picking for m in move_dest_ids if m.picking is not None}
            impactados = set(
                self._get_impacted_pickings(move_dest_ids)) - destinos_pickings
            lineas = [
                _('La cantidad reservada de %(origin)s bajó a '
                  '%(new)s (esperada: %(old)s).') % {
                    'origin': orig, 'new': nuevo, 'old': viejo}
                for orig in origin_pickings
                for (nuevo, viejo) in [
                    rendering_context[m][1] for m in rendering_context
                    if rendering_context[m][0].picking == orig][:1]
            ]
            if impactados:
                lineas.append(_('Albaranes impactados: %s') % ', '.join(
                    str(p) for p in impactados))
            return '\n'.join(lineas)

        documents = self._log_activity_get_documents(
            moves, 'move_dest_ids', 'DOWN', keys_in_groupby)
        documents = self._less_quantities_than_expected_add_documents(
            moves, documents)
        self._log_activity(render_note, documents)

    def _less_quantities_than_expected_add_documents(self, moves, documents):
        """≙ ``_less_quantities_than_expected_add_documents``
        (``odoo19c: :1735-1736``) — pass-through; puntos de extensión de
        otros addons (venta, compra) que no viven en este árbol.
        """
        return documents

    def _send_confirmation_email(self):
        """≙ ``_send_confirmation_email`` (``odoo19c: :1283-1291``).

        Publica un mensaje de confirmación en el hilo del albarán, usando la
        plantilla de la empresa, cuando ``stock_move_email_validation`` está
        activo y el tipo de operación es de salida.
        """
        if self.company is None or not self.company.stock_move_email_validation:
            return
        if self.picking_type is None or self.picking_type.code != 'outgoing':
            return
        template = self.company.stock_mail_confirmation_template
        if template is not None:
            self.message_post_with_template(template)

    # -- tarea #521 (continuación) — grupo Paquetes, 17 símbolos --
    #
    # El grupo quedó bloqueado en el pase anterior SÓLO por aislamiento de
    # write-set (tocaba ``stock_package.py``); en esta tanda ese archivo es
    # escribible y el grupo se cierra completo. Dos de sus símbolos
    # (``_is_single_transfer`` y ``_check_move_lines_map_quant_package``) ya
    # tenían un llamador vivo en ``stock_move_line.py:2022-2023``
    # (``_get_lines_not_entire_pack``) — la pareja llamador/método estaba rota
    # por el lado del método, la misma clase que :ref:`h-api-608`.

    @property
    def packages_count(self):
        """≙ ``packages_count`` / ``_compute_packages_count`` (``odoo19c:
        addons/stock/models/stock_picking.py:643``, ``:944-962``).

        Con el albarán terminado cuenta las fotografías
        (``stock.package.history``); en curso, los paquetes vivos cuya
        ``picking_ids`` lo incluye. ``compute`` sin ``store`` allá → property
        aquí (D-6). El dominio ``[('picking_ids', 'in', ...)]`` de la fuente
        es exactamente ``StockPackage._search_picking_ids``.
        """
        if self.state == self.STATE_DONE:
            return self.package_history_ids.count()
        StockPackage = apps.get_model('stock', 'StockPackage')
        return StockPackage._search_picking_ids([self]).count()

    @property
    def show_check_availability(self):
        """≙ ``show_check_availability`` / ``_compute_show_check_availability``
        (``odoo19c: addons/stock/models/stock_picking.py:645-647``, ``:964-980``).

        ¿Debe ofrecerse «Comprobar disponibilidad»? Sólo con el albarán en
        confirmado/esperando/disponible, con demanda aún no cubierta, y con
        algún movimiento pendiente de cantidad no nula.
        """
        if self.state not in (self.STATE_CONFIRMED, self.STATE_WAITING,
                              self.STATE_ASSIGNED):
            return False
        moves = list(self.move_ids.all())
        if all(m.picked or m.product_uom_qty == m.quantity for m in moves):
            return False
        return any(
            m.state in ('waiting', 'confirmed', 'partially_available')
            and m.product_uom is not None
            and m.product_uom.compare(m.product_uom_qty, 0) != 0
            for m in moves)

    @property
    def show_allocation(self):
        """≙ ``show_allocation`` / ``_compute_show_allocation`` (``odoo19c:
        addons/stock/models/stock_picking.py:648-650``, ``:982-988``).

        **Divergencia declarada:** la referencia lo apaga si el usuario no
        tiene el grupo ``stock.group_reception_report``; este stack no tiene
        grupos de usuario — se calcula siempre y la gate de visibilidad queda
        del lado de quien consuma el campo (mismo criterio que
        ``picking_warning_text``).
        """
        return bool(self._get_show_allocation(self.picking_type))

    def _get_show_allocation(self, picking_type):
        """≙ ``_get_show_allocation`` (``odoo19c: :1056-1077``).

        Helper separado del compute para que otros modelos (p. ej. batch) lo
        reusen. Hay asignación que ofrecer cuando OTRO albarán espera
        (confirmado/parcial/esperando, y también reservado si éste ya
        terminó) mercancía almacenable de los mismos productos, dentro del
        almacén de este tipo de operación.
        """
        if picking_type is None or picking_type.code == 'outgoing':
            return False
        lines = [m for m in self.move_ids.all()
                 if m.product is not None and m.product.is_storable
                 and m.state != self.STATE_CANCEL]
        if not lines:
            return False
        allowed_states = ['confirmed', 'partially_available', 'waiting']
        if self.state == self.STATE_DONE:
            allowed_states.append('assigned')
        warehouse = picking_type.warehouse
        view_location = warehouse.view_location if warehouse is not None else None
        if view_location is None:
            # ≙ un ``child_of`` sobre un id falsy en la fuente: conjunto vacío.
            return False
        StockMove = apps.get_model('stock', 'StockMove')
        line_ids = [m.pk for m in lines]
        product_ids = {m.product_id for m in lines}
        return StockMove.objects.filter(
            view_location.child_of_domain('location'),
            Q(move_orig_ids__isnull=True) | Q(move_orig_ids__in=line_ids),
            state__in=allowed_states,
            product_qty__gt=0,
            product_id__in=product_ids,
        ).exclude(
            location__usage='supplier',
        ).exclude(picking=self).exists()

    def action_put_in_pack(self, *, package_id=False, package_type_id=False,
                           package_name=False):
        """≙ ``action_put_in_pack`` (``odoo19c: :1761-1766``).

        Delega en las líneas del albarán mientras no esté terminado ni
        cancelado. **Divergencia declarada:** la limpieza de contexto
        (``sml_specific_default`` + ``clean_context``) no aplica — no hay
        ``env.context`` ambiental en este stack; los defaults viajan en el
        descriptor de acción, no en el entorno.
        """
        if self.state in (self.STATE_DONE, self.STATE_CANCEL):
            return None
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        return StockMoveLine.action_put_in_pack(
            list(self.move_line_ids.all()), package_id=package_id,
            package_type_id=package_type_id, package_name=package_name)

    def action_add_entire_packs(self, package_ids):
        """≙ ``action_add_entire_packs`` (``odoo19c: :1904-1917``).

        Añade paquetes COMPLETOS al albarán: borra las líneas que ya tomaban
        parte de esos paquetes (ahora van enteros), crea una línea por quant
        contenido, re-aplica la estrategia de colocación y marca como destino
        los contenedores que quedaron completos. El ``child_of`` de la fuente
        es aquí el prefijo de ``parent_path`` — el árbol de contenedores
        ACTUALES, el mismo que usa ``all_children_package_ids``.
        """
        if self.state in (self.STATE_DONE, self.STATE_CANCEL):
            return False
        StockPackage = apps.get_model('stock', 'StockPackage')
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        tree_domain = Q(pk__in=list(package_ids))
        for root in StockPackage.objects.filter(pk__in=list(package_ids)):
            if root.parent_path:
                tree_domain |= Q(parent_path__startswith=root.parent_path)
        all_packages = StockPackage.objects.filter(tree_domain)
        all_package_ids = set(all_packages.values_list('pk', flat=True))
        self.move_line_ids.filter(package_id__in=all_package_ids).delete()
        move_line_vals = self._prepare_entire_pack_move_line_vals(all_packages)
        pack_move_lines = [
            StockMoveLine.objects.create(**vals) for vals in move_line_vals]
        if pack_move_lines:
            StockMoveLine._apply_putaway_strategy(pack_move_lines)
        for container in {
                l.result_package for l in self.move_line_ids.all()
                if l.result_package_id is not None}:
            container._apply_package_dest_for_entire_packs(
                allowed_package_ids=all_package_ids)
        return True

    def action_see_packages(self):
        """≙ ``action_see_packages`` (``odoo19c: :1927-1942``).

        **Divergencia declarada:** sin registro de vistas (``self.env.ref``)
        el descriptor se arma directo — mismo contrato de dominio y contexto
        que la referencia, sin ``views`` con ids de vista XML (misma forma
        que ``action_detailed_operations``).
        """
        return {
            'name': _('Paquetes'),
            'res_model': 'stock.package',
            'view_mode': 'list,kanban,form',
            'type': 'ir.actions.act_window',
            'domain': [('picking_ids', 'in', [self.pk])],
            'context': {
                'picking_ids': [self.pk],
                'location_id': self.location_id,
                'can_add_entire_packs': self.picking_type_code != 'incoming',
                'search_default_main_packages': True,
            },
        }

    def action_see_package_histories(self):
        """≙ ``action_see_package_histories`` (``odoo19c: :1944-1957``)."""
        return {
            'name': _('Paquetes'),
            'res_model': 'stock.package.history',
            'view_mode': 'list',
            'type': 'ir.actions.act_window',
            'domain': [('picking_ids', '=', self.pk)],
            'context': {
                'search_default_main_packages': 1,
            },
        }

    def _check_move_lines_map_quant_package(self, package):
        """≙ ``_check_move_lines_map_quant_package`` (``odoo19c: :1293-1296``).

        ¿Las líneas de este albarán que tocan ``package`` (o a cualquiera de
        sus descendientes) cubren exactamente su contenido? La comparación en
        sí vive en el paquete (``_check_move_lines_map_quant``).
        """
        descendants = set(
            package.all_children_package_ids.values_list('pk', flat=True))
        lines = [
            l for l in self.move_line_ids.all()
            if l.product is not None and l.product.is_storable
            and (l.package_id == package.pk or l.package_id in descendants)]
        return package._check_move_lines_map_quant(lines)

    def _get_entire_pack_location_dest(self, move_line_ids):
        """≙ ``_get_entire_pack_location_dest`` (``odoo19c: :1298-1302``).

        El destino común de las líneas, o ``False`` si no hay uno solo.
        """
        location_dest_ids = {l.location_dest_id for l in move_line_ids}
        if len(location_dest_ids) != 1:
            return False
        return next(iter(location_dest_ids))

    def _is_single_transfer(self):
        """≙ ``_is_single_transfer`` (``odoo19c: :1304-1306``).

        La fuente responde ``len(self) == 1`` sobre un recordset (y los
        batches la reescriben). Una instancia Django es siempre un solo
        registro, así que aquí es ``True``; la pregunta de conjunto —¿las
        líneas de un paquete caen en UN solo albarán?— la hace
        ``_check_entire_pack`` comparando el conjunto de albaranes.
        """
        return True

    def _check_entire_pack(self):
        """≙ ``_check_entire_pack`` (``odoo19c: :1308-1324``).

        Detecta paquetes movidos COMPLETOS: si todas las líneas de un paquete
        caen en un solo albarán y cubren exactamente su contenido, las líneas
        sin destino heredan el paquete como ``result_package`` — salvo que el
        contenedor sea reutilizable, que por definición se vacía y vuelve. Al
        final, los contenedores completos propagan su propio destino.
        """
        by_package = defaultdict(list)
        for line in self.move_line_ids.all():
            if line.package_id is not None:
                by_package[line.package].append(line)
        for package, package_move_lines in by_package.items():
            transfers = {l.picking for l in package_move_lines
                         if l.picking_id is not None}
            # ≙ ``pickings._is_single_transfer()`` sobre el recordset: aquí el
            # conjunto de albaranes se compara directo (ver el docstring de
            # ``_is_single_transfer``).
            if len(transfers) != 1:
                continue
            transfer = next(iter(transfers))
            if not transfer._check_move_lines_map_quant_package(package):
                continue
            reusable = (package.package_type is not None
                        and package.package_type.package_use == 'reusable')
            if reusable:
                continue
            for line in package_move_lines:
                if (line.result_package_id is None
                        and line.state not in (self.STATE_DONE,
                                               self.STATE_CANCEL)):
                    line.result_package = package
                    line.is_entire_pack = True
                    line.save(
                        update_fields=['result_package', 'is_entire_pack'])
        for container in {
                l.result_package for l in self.move_line_ids.all()
                if l.result_package_id is not None}:
            container._apply_package_dest_for_entire_packs()

    def _prepare_entire_pack_move_line_vals(self, packages):
        """≙ ``_prepare_entire_pack_move_line_vals`` (``odoo19c: :2129-2149``).

        Una línea por quant directamente contenido en cada paquete de
        ``packages`` (los descendientes ya vienen en el conjunto — los trae
        el ``child_of`` de ``action_add_entire_packs``).

        **Divergencia declarada:** la fuente escribe ``'company_id': self.id``
        (``odoo19c: :2143``) — el **id del albarán** en la FK de empresa, un
        defecto aparente de la referencia. Aquí la empresa es la del albarán
        (``self.company``), que es lo que ``save()`` de la línea recalcularía
        de todos modos.
        """
        StockQuant = apps.get_model('stock', 'StockQuant')
        move_line_vals = []
        quants = (StockQuant.objects
                  .filter(package__in=packages)
                  .select_related('product', 'location', 'package',
                                  'lot', 'owner'))
        for package_quant in quants:
            move_line_vals.append({
                'product': package_quant.product,
                'quantity': package_quant.quantity,
                'product_uom': package_quant.product_uom,
                'location': package_quant.location,
                'location_dest': self.location_dest,
                'picking': self,
                'company': self.company,
                'package': package_quant.package,
                'result_package': package_quant.package,
                'lot': package_quant.lot,
                'owner': package_quant.owner,
                'is_entire_pack': True,
            })
        return move_line_vals
