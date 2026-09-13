r"""``stock.warehouse`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_warehouse.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **almacén** no es una ubicación. Es el objeto de configuración que
*genera* toda la topología de un sitio físico — sus ubicaciones internas, sus
tipos de operación con sus secuencias, y las rutas y reglas que mueven la
mercancía entre ellas. Crear un almacén crea entre 5 y 8 ubicaciones, 8 tipos de
operación con sus 8 secuencias, 2 rutas y sus reglas; cambiar su
``reception_steps`` de ``one_step`` a ``three_steps`` reescribe todo eso.

Los dos ejes que gobiernan esa generación, y son ortogonales:

- **``reception_steps``** — cuántos saltos hay entre el proveedor y la
  estantería: ``one_step`` (directo), ``two_steps`` (entrada → stock),
  ``three_steps`` (entrada → control de calidad → stock).
- **``delivery_steps``** — cuántos entre la estantería y el cliente:
  ``ship_only``, ``pick_ship``, ``pick_pack_ship``.

Por qué este archivo desbloquea el árbol
==========================================

**Cinco FK ya portados nombraban este modelo y no existía.** Medido antes de
este pase (:ref:`h-api-583`): ``StockLocation.warehouse``,
``StockPickingType.warehouse``, ``StockRoute.supplied_wh``,
``StockRoute.supplier_wh`` y ``StockRoute.warehouse_ids`` declaraban un FK a
``'stock.StockWarehouse'`` sin declarante, así que Django no resolvía la
relación y **la suite de** ``stock`` **no coleccionaba**: 10 errores de
``ValueError: Related model 'stock.stockwarehouse' cannot be resolved``, cero
tests ejecutados.

Porte símbolo por símbolo — 78 de 78
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_warehouse.py`` (1164 líneas):
**6 atributos de clase**, **28 campos**, **44 métodos**, más el ``namedtuple``
``Routing`` que la referencia declara en el cuerpo de la clase.

*Métrica:* atributos y métodos por AST sobre el cuerpo de ``StockWarehouse``.
*Ciega a:* las funciones locales dentro de un método — aquí no hay ninguna.

**Ojo con el conteo de asignaciones:** el AST devuelve 29 asignaciones no
privadas, pero una es ``Routing = namedtuple(...)``, que no es un campo. Son 28
campos y un ayudante. Es exactamente la mezcla que
``metrica-decide-la-conclusion.md`` describe: un encabezado ("campos") sobre dos
cosas distintas.

Atributos de clase — 6 de 6
-----------------------------

Cuatro de ORM (``:24-27``) y dos **objetos de tabla** (``:92-99``), que en 19 se
declaran igual pero cuyo hogar aquí es ``Meta.constraints``, con el nombre de la
referencia conservado (``atributos-de-clase-de-modelo.md``).

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - Símbolo (línea)
     - Qué es
     - Aquí
   * - ``_name`` (24)
     - atributo de ORM
     - verbatim
   * - ``_description`` (25)
     - atributo de ORM
     - verbatim
   * - ``_order`` (26)
     - atributo de ORM
     - verbatim + ``Meta.ordering``
   * - ``_check_company_auto`` (27)
     - atributo de ORM
     - verbatim + el check en ``save()``
   * - ``_warehouse_name_uniq`` (92-95)
     - objeto de tabla
     - ``Meta.constraints``, mismo nombre
   * - ``_warehouse_code_uniq`` (96-99)
     - objeto de tabla
     - ``Meta.constraints``, mismo nombre

Campos — 28 de 28
-------------------

El FK va sin el sufijo ``_id`` porque Django ya expone la columna como
``<campo>_id``; así los cinco consumidores que ya existen siguen leyendo
``warehouse_id`` sin cambio.

``name`` · ``active`` · ``company`` · ``partner`` · ``view_location`` ·
``lot_stock`` · ``code`` · ``route_ids`` · ``reception_steps`` ·
``delivery_steps`` · ``wh_input_stock_loc`` · ``wh_qc_stock_loc`` ·
``wh_output_stock_loc`` · ``wh_pack_stock_loc`` · ``mto_pull`` · ``pick_type`` ·
``pack_type`` · ``out_type`` · ``in_type`` · ``int_type`` · ``qc_type`` ·
``store_type`` · ``xdock_type`` · ``reception_route`` · ``delivery_route`` ·
``resupply_wh_ids`` · ``sequence``, más ``resupply_route_ids`` como **property**
(la referencia lo declara ``One2many`` sobre ``stock.route.supplied_wh_id``, y
aquí eso es el reverso del FK que ``StockRoute`` ya declara).

Métodos — 44 de 44
--------------------

Todos con su nombre y su visibilidad: los cuatro públicos de la fuente
—``create``, ``write``, ``unlink``, ``copy_data``, ``create_resupply_routes``,
``get_rules_dict``, ``action_view_all_routes``, ``get_current_warehouses``— lo
siguen siendo, y los privados conservan su guion bajo
(``porte-completo-no-parcial.md``, :ref:`h-api-581`).

Igual que en ``stock_move_line.py``: un método que la fuente escribe con
``self.ensure_one()`` es **método de instancia**; uno que itera ``for warehouse
in self`` es **``classmethod`` que recibe ``warehouses``**.

Lo que este archivo NO cierra — las dependencias, nombradas
============================================================

El almacén es un **orquestador**: casi todos sus métodos escriben sobre otros
modelos. Tres de ellos están en el árbol como esbozo, y este archivo los llama
igual —navegando el símbolo que la referencia navega— porque enmascararlo
produciría un ``None`` silencioso.

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Símbolo que falta
     - Quién lo espera aquí
   * - ``stock.rule`` completo (6 campos de 20 portados)
     - ``_create_or_update_global_routes_rules``, ``_find_existing_rule_or_create``,
       ``_get_rule_values``, ``create_resupply_routes``, ``_check_delivery_resupply``
   * - ``res.company.internal_transit_location_id``
     - ``_get_transit_locations``, ``_update_partner_data``
   * - ``res.partner.property_stock_customer/supplier``
     - ``_update_partner_data``
   * - ``res.groups`` con ``implied_ids``
     - ``_check_multiwarehouse_group``, ``_onchange_company_id``
   * - ``ir.model.data`` con los XML ID de ``stock``
     - ``_get_partner_locations``, ``_get_transit_locations``,
       ``_find_or_create_global_route``

- **Sucesor registrado:** tarea **#330** (stock completo, los 25 archivos de la
  referencia), cuyo siguiente archivo tras éste es ``stock_rule.py``.
- **Lo que NO es:** un porte parcial. Los 78 símbolos de **este** archivo están;
  lo que falta pertenece a otros, y está nombrado uno por uno arriba.

Cuatro divergencias de mecanismo declaradas
=============================================

**D-1 — la resolución por XML ID.** La referencia usa ``self.env.ref('stock.…')``
para hallar las ubicaciones de cliente/proveedor y las rutas globales. Aquí el
equivalente es ``IrModelData.ref``, ya portado, con el mismo fallback que la
fuente escribe a mano: si el XML ID no está sembrado, se busca por ``usage`` o
por nombre. No se inventa nada — es el ``or Location.search([...])`` de
``_get_partner_locations`` (``:750-758``).

**D-2 — las acciones de ventana.** ``action_view_all_routes`` (``:1148-1159``) y
``_warehouse_redirect_warning`` (``:165-173``) devuelven descriptores de
``ir.actions.act_window`` para el cliente Odoo. Se portan devolviendo el mismo
descriptor —que es el contrato de datos—; el cliente que lo consume no existe
aquí. Mismo criterio que ``stock_picking.py`` ya usa con ``_action_by_xmlid``.

**D-3 — ``route_ids`` no se declara dos veces.** La referencia declara el MISMO
M2M desde ambos lados sobre la misma tabla, con las columnas invertidas:
``stock.warehouse.route_ids`` (``:51-55``) y ``stock.route.warehouse_ids``
(``odoo19c: stock_location.py:542-544``), ambos sobre ``stock_route_warehouse``.
Su ORM las trata como dos declaraciones de una relación; el de Django las
trataría como **dos relaciones distintas sobre la misma tabla**, y lo dice:
``fields.W344 The field's intermediary table 'stock_route_warehouse' clashes``.

Aquí el M2M lo declara ``StockRoute.warehouse_ids`` con
``related_name='route_ids'``, así que el atributo **existe en este modelo con el
nombre exacto de la referencia** y es un manager normal: ``.all()``, ``.set()``,
``.values_list()`` funcionan igual. No es un símbolo omitido — es una relación
declarada una vez en vez de dos, que es como este ORM expresa lo mismo.

**D-4 — quién dispara el recálculo de** ``StockLocation.warehouse`` **(tarea
#503, cierra** :ref:`h-api-667` **).** La referencia declara ``warehouse_id``
``compute=… store=True`` con ``@api.depends('warehouse_view_ids',
'location_id')`` (``odoo19c: stock_location.py:84-85``) — **almacenado**, no
``property``; :ref:`h-api-667` medía lo contrario y la premisa era falsa (ver
la corrección en el propio hallazgo). El motor de dependencias que dispara ese
recálculo en cada extremo de la relación **no existe en este ORM** —
``src/orm/decorators.py`` deja ``@api.depends`` como anotación no-op, y
construirlo es la tarea **#191**. Sin ese motor, alguien tiene que disparar el
recálculo a mano cuando el lado ``stock.warehouse`` de la relación cambia; el
``save()`` de este modelo lo hace, delegando en
``StockLocation.compute_warehouse()`` para cada ubicación del subárbol de
``view_location`` — el mismo método que ya usa cada ubicación para
autocalcularse, así que no hay una segunda copia de la regla «gana el ancestro
más profundo».

Medido al escribir este ``save()``: el ``create()`` de este archivo (líneas
495-511 antes de este cambio) ya traía un backfill manual equivalente, pero
**nunca se ejecutó en producción** — los siete llamadores reales de este
modelo (``res_company.py:268`` y seis fixtures de test) crean con
``StockWarehouse.objects.create(...)``, el manager de Django, que no pasa por
el ``classmethod create()`` de la referencia (0 ocurrencias de
``StockWarehouse.create(`` en todo el árbol). El ``save()`` nuevo corre en
CUALQUIER camino de persistencia — ``.objects.create()``, ``create()``,
``write()`` — porque todos terminan invocándolo; por eso el backfill manual de
``create()`` se retiró en el mismo cambio: dos mecanismos para la misma regla
divergían además en el resultado (ver el punto siguiente).

El backfill retirado escribía ``view_location.warehouse = self`` a mano. Ese
resultado es **correcto** —la referencia también resuelve la vista a su propio
almacén: ``path = set(int(loc_id) for loc_id in loc.parent_path.split('/')[:-1])``
recorta el elemento **vacío** que deja la barra final de la ruta materializada
(``«1/4/9/»`` → ``['1','4','9','']``), no el ``id`` de la propia ``loc``— pero
la forma no lo era: dos mecanismos para la misma regla, y sólo uno resolvía
«gana el ancestro más profundo». Delegar en ``StockLocation.compute_warehouse()``
deja una sola regla, con el mismo resultado.

Este párrafo afirmaba lo contrario (una «exclusión» de la propia ubicación) en
el primer pase de la tarea #503; se corrigió midiendo la fuente en vez de
razonar sobre el nombre del recorte. Ver :ref:`h-api-676`.

**Lo que este ``save()`` NO cierra — nombrado, no diferido. Ninguno de los tres
tiene ID de tarea verificado** (``calibration-verified-numbers.md`` — el
tablero de tareas leído al escribir este cambio no llega a **#503**, así que
no hay forma de citar un número real sin fabricarlo); quedan **DESCONOCIDO**
con su condición de cierre:

- **``StockWarehouse.create()`` (el ``classmethod`` de arriba, con toda la
  generación de topología) no lo llama nadie.** Medido: **0** ocurrencias de
  ``StockWarehouse.create(`` fuera de su propia definición en todo el árbol
  (``grep -rn "StockWarehouse\.create(" addons/ src/ tests/``). Los **7**
  llamadores reales (``res_company.py:268`` y 6 fixtures de test) usan
  ``.objects.create()``, que corre este ``save()`` pero no la creación de
  ubicaciones/secuencias/tipos de operación/rutas del ``classmethod``. Este
  pase cierra sólo el síntoma que medía :ref:`h-api-667` (``.warehouse``
  stale); que ningún almacén real reciba su topología generada es un defecto
  mayor y arquitectónico —requiere decidir si se llama el ``classmethod``
  desde los 7 sitios o si su lógica se mueve a ``save()``— que excede este
  pase. Condición de cierre: medir cuántos de los 7 llamadores necesitan la
  topología completa (¿``create_missing_warehouse`` sí, los fixtures de test
  tal vez no si ya crean sus propias ubicaciones a mano?) antes de decidir la
  forma del fix.
- **``create_missing_warehouse`` (``res_company.py:255-273``) no puede
  insertar la fila.** Crea con ``warehouse_model.objects.create(name=…,
  code=…, company=…, partner_id=…)`` sin ``view_location_id`` ni
  ``lot_stock_id`` — los dos son ``Many2one`` obligatorios en este archivo
  (``:327-338``, sin ``null=True``). Viola NOT NULL antes de que este
  ``save()`` tenga oportunidad de correr. Mismo origen que el punto anterior
  (no pasa por el ``classmethod create()`` que sí resolvería ambos FK) — es
  plausible que cerrar ése cierre éste también, pero no está medido. Fuera
  del alcance de archivos de este pase (``res_company.py`` no está en la
  lista de archivos tocables). Condición de cierre: reproducir el
  ``IntegrityError`` con un test de integración contra PostgreSQL real antes
  de tocar el archivo.
- **Reparentar una ubicación no propaga a sus descendientes.**
  ``StockLocation.write()`` recalcula ``self.parent_path``/``self.warehouse``
  cuando cambia ``location`` (el padre), pero no toca ``parent_path`` ni
  ``warehouse`` de los hijos de ``self`` — que quedan con la ruta y el almacén
  viejos hasta su propio próximo ``save()``. Mismo defecto de fondo
  (dependencia cruzada sin motor que la dispare), disparador distinto
  (``location_id`` de la propia ubicación, no ``warehouse_view_ids`` de un
  almacén). Condición de cierre: extender ``StockLocation.write()`` con el
  mismo patrón de refresco de subárbol que ``_refresh_descendant_warehouses``
  aplica aquí, cuando ``location`` cambie.
"""
from collections import namedtuple
from decimal import Decimal

import fields
import api
import models
from django.apps import apps
from django.db.models import Q

from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from osv import expression
from tools.translate import _

#: ≙ ``ROUTE_NAMES`` (``odoo19c: :13-20``) — el nombre legible de cada modo de
#: recepción y de entrega. Vive a nivel de módulo, igual que en la fuente.
ROUTE_NAMES = {
    'one_step': _('Receive in 1 step (stock)'),
    'two_steps': _('Receive in 2 steps (input + stock)'),
    'three_steps': _('Receive in 3 steps (input + quality + stock)'),
    'ship_only': _('Deliver in 1 step (ship)'),
    'pick_ship': _('Deliver in 2 steps (pick + ship)'),
    'pick_pack_ship': _('Deliver in 3 steps (pick + pack + ship)'),
}

#: ≙ ``StockWarehouse.Routing`` (``odoo19c: :29``) — «namedtuple used in helper
#: methods generating values for routes». La referencia lo declara en el cuerpo
#: de la clase; aquí se declara a nivel de módulo **y** se cuelga de la clase con
#: su nombre, para que ambas formas de citarlo resuelvan.
Routing = namedtuple('Routing', ['from_loc', 'dest_loc', 'picking_type', 'action'])

#: Los ocho tipos de operación que un almacén genera, en el orden en que la
#: referencia los numera con ``max_sequence + N`` (``:1005-1078``).
PICKING_TYPE_FIELDS = (
    'in_type', 'qc_type', 'store_type', 'int_type',
    'pick_type', 'pack_type', 'out_type', 'xdock_type',
)


class StockWarehouse(TimeStampedModel):
    """``stock.warehouse`` — el sitio físico y la topología que genera."""

    # Atributos de clase de modelo — los cuatro de ORM que la referencia
    # declara (``odoo19c: addons/stock/models/stock_warehouse.py:24-27``),
    # verbatim. Los dos objetos de tabla viven en ``Meta.constraints``.
    _name = 'stock.warehouse'
    _description = "Warehouse"
    _order = 'sequence,id'
    _check_company_auto = True
    #: ≙ ``Routing`` (``:29``) — el mismo namedtuple del módulo, colgado aquí
    #: para que ``self.Routing(...)`` resuelva como en la fuente.
    Routing = Routing

    name                 = fields.Char(
        max_length=255,
        help_text='Nombre del almacén (Odoo name; su default es el nombre de '
                  'la empresa — ver _default_name).',
    )
    active               = fields.Boolean(
        default=True, help_text='Almacén activo (Odoo active).',
    )
    company              = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='warehouses',
        help_text='Empresa (Odoo company_id, readonly+required: se toma de las '
                  'preferencias del usuario y no se cambia después).',
    )
    partner              = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses',
        help_text='Dirección del almacén (Odoo partner_id).',
    )
    view_location        = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, db_index=True,
        related_name='warehouses_as_view',
        help_text='Ubicación raíz de tipo vista que cuelga de este almacén '
                  '(Odoo view_location_id).',
    )
    lot_stock            = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT,
        related_name='warehouses_as_stock',
        help_text='La estantería: ubicación interna donde vive la existencia '
                  '(Odoo lot_stock_id).',
    )
    code                 = fields.Char(
        max_length=5,
        help_text='Nombre corto que identifica el almacén; prefija los códigos '
                  'de barras y las secuencias (Odoo code, size=5).',
    )
    # ``route_ids`` NO se declara aquí — ver "Divergencia D-3" en el docstring.
    # ``StockRoute.warehouse_ids`` ya declara este M2M sobre la misma tabla
    # ``stock_route_warehouse`` con ``related_name='route_ids'``, así que el
    # atributo existe con el nombre de la referencia y es un manager normal.
    reception_steps      = fields.Selection(
        choices=[
            ('one_step', 'Receive and Store (1 step)'),
            ('two_steps', 'Receive then Store (2 steps)'),
            ('three_steps', 'Receive, Quality Control, then Store (3 steps)'),
        ],
        max_length=16, default='one_step',
        help_text='Ruta de entrada por defecto (Odoo reception_steps).',
    )
    delivery_steps       = fields.Selection(
        choices=[
            ('ship_only', 'Deliver (1 step)'),
            ('pick_ship', 'Pick then Deliver (2 steps)'),
            ('pick_pack_ship', 'Pick, Pack, then Deliver (3 steps)'),
        ],
        max_length=16, default='ship_only',
        help_text='Ruta de salida por defecto (Odoo delivery_steps).',
    )
    wh_input_stock_loc   = fields.Many2one(
        'stock.StockLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_input',
        help_text='Ubicación de entrada (Odoo wh_input_stock_loc_id); activa '
                  'sólo si reception_steps != one_step.',
    )
    wh_qc_stock_loc      = fields.Many2one(
        'stock.StockLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_qc',
        help_text='Ubicación de control de calidad (Odoo wh_qc_stock_loc_id); '
                  'activa sólo con reception_steps == three_steps.',
    )
    wh_output_stock_loc  = fields.Many2one(
        'stock.StockLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_output',
        help_text='Ubicación de salida (Odoo wh_output_stock_loc_id); activa '
                  'sólo si delivery_steps != ship_only.',
    )
    wh_pack_stock_loc    = fields.Many2one(
        'stock.StockLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_pack',
        help_text='Zona de empaque (Odoo wh_pack_stock_loc_id); activa sólo con '
                  'delivery_steps == pick_pack_ship.',
    )
    mto_pull             = fields.Many2one(
        'stock.StockRule', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_mto',
        help_text='Regla MTO del almacén dentro de la ruta global «Replenish on '
                  'Order» (Odoo mto_pull_id).',
    )
    pick_type            = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_pick', help_text='Odoo pick_type_id.',
    )
    pack_type            = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_pack_type', help_text='Odoo pack_type_id.',
    )
    out_type             = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_out', help_text='Odoo out_type_id.',
    )
    in_type              = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_in', help_text='Odoo in_type_id.',
    )
    int_type             = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_int', help_text='Odoo int_type_id.',
    )
    qc_type              = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_qc_type', help_text='Odoo qc_type_id.',
    )
    store_type           = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_store', help_text='Odoo store_type_id.',
    )
    xdock_type           = fields.Many2one(
        'stock.StockPickingType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouses_as_xdock', help_text='Odoo xdock_type_id.',
    )
    reception_route      = fields.Many2one(
        'stock.StockRoute', on_delete=models.RESTRICT, null=True, blank=True,
        related_name='warehouses_as_reception',
        help_text='Ruta de recepción generada por reception_steps '
                  '(Odoo reception_route_id).',
    )
    delivery_route       = fields.Many2one(
        'stock.StockRoute', on_delete=models.RESTRICT, null=True, blank=True,
        related_name='warehouses_as_delivery',
        help_text='Ruta de entrega generada por delivery_steps '
                  '(Odoo delivery_route_id).',
    )
    resupply_wh_ids      = fields.Many2many(
        'self', through='stock.StockWarehouseResupply', symmetrical=False,
        through_fields=('supplied_wh', 'supplier_wh'),
        related_name='+', blank=True,
        help_text='Almacenes desde los que éste se reabastece; marcar uno crea '
                  'su ruta inter-almacén (Odoo resupply_wh_ids).',
    )
    sequence             = fields.Integer(
        default=10, help_text='Orden de despliegue del almacén (Odoo sequence).',
    )

    class Meta:
        db_table = 'stock_warehouse'
        # ≙ ``_order = 'sequence,id'`` (``odoo19c: :26``).
        ordering = ['sequence', 'id']
        constraints = [
            # ≙ ``_warehouse_name_uniq`` (``odoo19c: :92-95``).
            models.UniqueConstraint(
                fields=['name', 'company'], name='warehouse_name_uniq',
                violation_error_message='The name of the warehouse must be '
                                        'unique per company!',
            ),
            # ≙ ``_warehouse_code_uniq`` (``odoo19c: :96-99``).
            models.UniqueConstraint(
                fields=['code', 'company'], name='warehouse_code_uniq',
                violation_error_message='The short name of the warehouse must '
                                        'be unique per company!',
            ),
        ]
        verbose_name = 'Almacén'
        verbose_name_plural = 'Almacenes'

    def __str__(self):
        return self.name or f'stock.warehouse#{self.pk}'

    # ------------------------------------------------------------------ #
    # Defaults y avisos (≙ :31-33, 101-113, 165-173)                       #
    # ------------------------------------------------------------------ #

    @classmethod
    def _default_name(cls, company=None):
        """≙ ``_default_name`` (``odoo19c: :31-33``).

        El primer almacén de una empresa se llama como ella; a partir del
        segundo lleva sufijo numerado. La referencia cuenta **con los
        archivados** (``active_test=False``), para que el número no se repita
        al archivar uno.
        """
        if company is None:
            return ''
        cuenta = cls.objects.filter(company=company).count()
        return f'{company.name} - warehouse # {cuenta + 1}' if cuenta else company.name

    def _onchange_company_id(self):
        """≙ ``_onchange_company_id`` (``odoo19c: :101-113``).

        Avisa de que crear un almacén activará el ajuste de ubicaciones
        múltiples. Devuelve el aviso en vez de mutar el formulario: aquí no hay
        cliente que lo consuma (divergencia D-2).
        """
        grupos = self._implied_groups_of_base_user()
        if ('stock.group_stock_multi_warehouses' not in grupos
                and 'stock.group_stock_multi_locations' not in grupos):
            return {'warning': {
                'title': _('Warning'),
                'message': _('Creating a new warehouse will automatically '
                             'activate the Storage Locations setting'),
            }}
        return {}

    @classmethod
    def _warehouse_redirect_warning(cls, company=None, user=None):
        """≙ ``_warehouse_redirect_warning`` (``odoo19c: :165-173``).

        La empresa no tiene almacén y algo lo necesita. Al gestor se le manda a
        crearlo; a quien no lo es se le dice que hable con su administrador.
        Divergencia D-2: se devuelve el descriptor en vez de lanzar el
        ``RedirectWarning`` del cliente Odoo.
        """
        if user is not None and not cls._user_has_group(user, 'stock.group_stock_manager'):
            raise UserError(_('Please contact your administrator to configure '
                              'your warehouse.'))
        return {
            'type': 'ir.actions.act_window',
            'xml_id': 'stock.action_warehouse_form',
            'name': _('Go to Warehouses'),
            'message': _('Please create a warehouse for company %s.',
                         getattr(company, 'name', '')),
        }

    # ------------------------------------------------------------------ #
    # CRUD (≙ :115-315)                                                    #
    # ------------------------------------------------------------------ #

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :115-163``).

        Crear un almacén no es insertar una fila: es **generar la topología**.
        En el orden de la referencia, que no es arbitrario:

        1. se completan nombre, código y dirección desde la empresa;
        2. se crea la ubicación **vista** que será la raíz del almacén, y bajo
           ella las cinco sub-ubicaciones (stock, entrada, calidad, salida,
           empaque) con el ``active`` que sus dos ejes dicten;
        3. **entonces** se inserta el almacén — antes no se puede, porque
           ``view_location_id`` es obligatorio;
        4. se crean secuencias y tipos de operación, y se escriben de vuelta;
        5. se crean las rutas y sus reglas, y se escriben de vuelta;
        6. se actualizan las reglas de las rutas **globales** (MTO);
        7. se crean las rutas de reabastecimiento desde otros almacenes;
        8. se marca el almacén en las ubicaciones — que no lo conocían al
           crearse, porque el almacén aún no existía.
        """
        location_model = apps.get_model('stock', 'StockLocation')
        company_model = apps.get_model('base', 'ResCompany')

        for vals in vals_list:
            if vals.get('company_id'):
                empresa = company_model.objects.get(pk=vals['company_id'])
                vals.setdefault('name', empresa.name)
                vals.setdefault('code', empresa.name[:5])
                if 'partner_id' not in vals:
                    vals['partner_id'] = getattr(empresa, 'partner_id', None)

            loc_vals = {'name': vals.get('code'), 'usage': 'view'}
            if vals.get('company_id'):
                loc_vals['company_id'] = vals['company_id']
            vals['view_location_id'] = location_model.objects.create(**loc_vals).pk

            for campo, valores in cls._get_locations_values(vals).items():
                valores['location_id'] = vals['view_location_id']
                if vals.get('company_id'):
                    valores['company_id'] = vals['company_id']
                vals[campo] = location_model.objects.create(**valores).pk

        warehouses = [cls.objects.create(**vals) for vals in vals_list]

        for warehouse, vals in zip(warehouses, vals_list):
            cls.write([warehouse],
                      warehouse._create_or_update_sequences_and_picking_types())
            cls.write([warehouse], warehouse._create_or_update_route())
            warehouse._create_or_update_global_routes_rules()
            warehouse.create_resupply_routes(list(warehouse.resupply_wh_ids.all()))

            if vals.get('partner_id'):
                cls._update_partner_data(vals['partner_id'], vals.get('company_id'))

            # El almacén no existía cuando se crearon sus ubicaciones — pero
            # `cls.objects.create(**vals)` (línea de arriba) ya disparó
            # `save()`, que ya recalculó `warehouse` en todo el subárbol de
            # `view_location` (ver `save()`/D-4). No hace falta repetirlo aquí.

        cls._check_multiwarehouse_group()
        return warehouses

    def save(self, *args, **kwargs):
        """Dispara el recálculo de ``StockLocation.warehouse`` en el subárbol.

        No es un símbolo de la referencia — Odoo no tiene ``save()`` de
        Django. Existe porque ``@api.depends`` no dispara nada en este ORM
        (``src/orm/decorators.py``; el motor real es la tarea **#191**), así
        que el lado ``stock.warehouse`` de la dependencia
        ``@api.depends('warehouse_view_ids', 'location_id')`` de la referencia
        (``odoo19c: stock_location.py:159-160``) necesita disparar el
        recálculo a mano cuando cambia. Ver D-4 en el docstring del módulo
        para la medición completa y por qué reemplaza al backfill manual que
        tenía ``create()``.

        Corre en CUALQUIER camino de persistencia — ``.objects.create()``
        (el que usan los siete llamadores reales de este modelo, ninguno pasa
        por el ``classmethod create()``), el propio ``create()``, y
        ``write()`` (que llama ``warehouse.save()`` en su línea de guardado) —
        porque los tres terminan en este método.
        """
        super().save(*args, **kwargs)
        self._refresh_descendant_warehouses()

    def _refresh_descendant_warehouses(self):
        """Recalcula ``.warehouse`` en ``view_location`` y todo su subárbol.

        Delega en ``StockLocation.compute_warehouse()`` por ubicación —no
        escribe ``warehouse = self`` a mano— porque ese método ya resuelve
        «gana el ancestro más profundo» (varios almacenes anidados), que es la
        parte que el backfill manual NO hacía. La propia ``view_location``
        entra en el conjunto de candidatos: ``parent_path.split('/')[:-1]``
        recorta el elemento vacío de la barra final, no el ``id`` propio —
        igual que la referencia en ``_compute_warehouse_id`` (D-4). Sólo
        escribe cuando el
        valor calculado difiere del guardado, para no generar un ``UPDATE``
        por ubicación en cada ``save()`` del almacén cuando nada cambió.
        """
        if self.view_location_id is None:
            return
        location_model = apps.get_model('stock', 'StockLocation')
        view = self.view_location
        affected = location_model.objects.filter(
            parent_path__startswith=view.parent_path)
        for location in affected:
            previous = location.warehouse_id
            location.compute_warehouse()
            if location.warehouse_id != previous:
                location_model.objects.filter(pk=location.pk).update(
                    warehouse=location.warehouse)

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :175-183``).

        Nombre y código llevan sufijo de copia: los dos tienen restricción de
        unicidad por empresa, así que duplicarlos tal cual reventaría.
        """
        default = dict(default or {})
        vals = {}
        if 'name' not in default:
            vals['name'] = _("%s (copy)", self.name)
        if 'code' not in default:
            vals['code'] = _("COPY")
        vals.update(default)
        return vals

    @classmethod
    def write(cls, warehouses, vals):
        """≙ ``write`` (``odoo19c: :185-303``).

        El método más largo del archivo, y su trabajo es **propagar**: cambiar
        un eje del almacén reescribe ubicaciones, tipos de operación, rutas y
        reglas. Sigue el orden de la referencia:

        1. la empresa no se cambia — se archiva el almacén y se crea otro;
        2. se reponen las ubicaciones que falten (un módulo instalado después
           pudo añadir alguna, o alguien pudo borrarla);
        3. se activan/archivan las ubicaciones según los dos ejes nuevos;
        4. se escribe;
        5. **después** se recrean tipos de operación y rutas, pero sólo si
           cambió algo de lo que declaran depender — ese ``depends`` viaja en
           los propios diccionarios de ``_get_routes_values``;
        6. archivar un almacén con operaciones en curso está prohibido, y el
           mensaje nombra cuáles.
        """
        warehouses = list(warehouses)
        if not warehouses:
            return warehouses
        route_model = apps.get_model('stock', 'StockRoute')

        if 'company_id' in vals:
            for warehouse in warehouses:
                if warehouse.company_id != vals['company_id']:
                    raise UserError(_(
                        "Changing the company of this record is forbidden at this "
                        "point, you should rather archive it and create a new one."))

        cls._create_missing_locations(warehouses, vals)
        if vals.get('reception_steps'):
            cls._update_location_reception(warehouses, vals['reception_steps'])
        if vals.get('delivery_steps'):
            cls._update_location_delivery(warehouses, vals['delivery_steps'])
        if vals.get('reception_steps') or vals.get('delivery_steps'):
            cls._update_reception_delivery_resupply(
                warehouses, vals.get('reception_steps'), vals.get('delivery_steps'))

        resupply_previos = {}
        if vals.get('resupply_wh_ids') and not vals.get('resupply_route_ids'):
            resupply_previos = {
                w.pk: set(w.resupply_wh_ids.values_list('pk', flat=True))
                for w in warehouses
            }

        if vals.get('partner_id'):
            for warehouse in warehouses:
                cls._update_partner_data(
                    vals['partner_id'], vals.get('company_id') or warehouse.company_id)

        if vals.get('code') or vals.get('name'):
            cls._update_name_and_code(warehouses, vals.get('name'), vals.get('code'))

        for warehouse in warehouses:
            for clave, valor in vals.items():
                atributo = clave.removesuffix('_id')
                if hasattr(warehouse, atributo) and atributo != clave:
                    setattr(warehouse, f'{atributo}_id', valor)
                elif hasattr(warehouse, clave):
                    setattr(warehouse, clave, valor)
            warehouse.save()

        for warehouse in warehouses:
            depends = [d
                       for valor in warehouse._get_routes_values().values()
                       for d in valor.get('depends', [])]
            if 'code' in vals or any(d in vals for d in depends):
                tipos = warehouse._create_or_update_sequences_and_picking_types()
                if tipos:
                    cls.write([warehouse], tipos)
            if any(d in vals for d in depends):
                rutas = warehouse._create_or_update_route()
                if rutas:
                    cls.write([warehouse], rutas)

            globales = warehouse._get_global_route_rules_values()
            depends_globales = [d
                                for valor in globales.values()
                                for d in valor.get('depends', [])]
            if (any(r in vals for r in globales)
                    or any(d in vals for d in depends_globales)):
                warehouse._create_or_update_global_routes_rules()

            if 'active' in vals:
                warehouse._apply_active_to_topology(vals['active'])

        if resupply_previos:
            for warehouse in warehouses:
                nuevos = set(warehouse.resupply_wh_ids.values_list('pk', flat=True))
                previos = resupply_previos[warehouse.pk]
                a_agregar, a_quitar = nuevos - previos, previos - nuevos
                if a_agregar:
                    existentes = route_model.objects.filter(
                        supplied_wh=warehouse, supplier_wh__in=a_agregar, active=False)
                    ya = set(existentes.values_list('supplier_wh_id', flat=True))
                    existentes.update(active=True)
                    faltan = a_agregar - ya
                    if faltan:
                        warehouse.create_resupply_routes(
                            list(cls.objects.filter(pk__in=faltan)))
                if a_quitar:
                    route_model.objects.filter(
                        supplied_wh=warehouse, supplier_wh__in=a_quitar, active=True
                    ).update(active=False)

        if 'active' in vals:
            cls._check_multiwarehouse_group()
        return warehouses

    def _apply_active_to_topology(self, activo):
        """Propaga ``active`` a la topología generada (≙ el bloque ``:273-303``).

        No es un símbolo de la referencia: es el cuerpo del ``if 'active' in
        vals`` de ``write``, extraído porque ese método ya es el más largo del
        archivo y este bloque tiene su propia condición de error. Se declara
        aquí para que la extracción sea visible y no se lea como un símbolo
        inventado.
        """
        picking_type_model = apps.get_model('stock', 'StockPickingType')
        location_model = apps.get_model('stock', 'StockLocation')
        move_model = apps.get_model('stock', 'StockMove')
        rule_model = apps.get_model('stock', 'StockRule')

        tipos = picking_type_model.objects.filter(warehouse=self)
        en_curso = move_model.objects.filter(picking_type__in=tipos).exclude(
            state__in=('done', 'cancel'))
        if en_curso.exists():
            raise UserError(_(
                'You still have ongoing operations for operation types '
                '%(operations)s in warehouse %(warehouse)s',
                operations=[str(m.picking_type) for m in en_curso],
                warehouse=self.name))
        tipos.update(active=activo)

        ubicaciones = location_model.objects.filter(
            location__in=location_model.objects.filter(pk=self.view_location_id))
        ajenos = picking_type_model.objects.filter(
            default_location_src__in=ubicaciones,
            default_location_dest__in=ubicaciones,
        ).exclude(pk__in=tipos.values_list('pk', flat=True))
        if ajenos.exists():
            raise UserError(_(
                '%(operations)s have default source or destination locations '
                'within warehouse %(warehouse)s, therefore you cannot archive it.',
                operations=[str(t) for t in ajenos], warehouse=self.name))

        location_model.objects.filter(pk=self.view_location_id).update(active=activo)
        rule_model.objects.filter(warehouse=self).update(active=activo)
        # Sólo las rutas que aplican **sólo** a este almacén.
        for ruta in self.route_ids.all():
            if ruta.warehouse_ids.count() == 1:
                ruta.active = activo
                ruta.save()

    @classmethod
    def unlink(cls, warehouses):
        """≙ ``unlink`` (``odoo19c: :305-308``)."""
        res = cls.objects.filter(pk__in=[w.pk for w in warehouses]).delete()
        cls._check_multiwarehouse_group()
        return res

    @classmethod
    def _check_multiwarehouse_group(cls):
        """≙ ``_check_multiwarehouse_group`` (``odoo19c: :310-325``).

        El grupo «varios almacenes» se enciende y se apaga solo: con un almacén
        activo por empresa sobra, con dos hace falta. La referencia lo implica
        sobre ``base.group_user``, no lo asigna usuario por usuario, para que
        valga también para los que se creen después.
        """
        por_empresa = (cls.objects.filter(active=True)
                       .values('company').annotate(n=models.Count('pk')))
        if not por_empresa:
            return
        maximo = max(fila['n'] for fila in por_empresa)
        implicados = cls._implied_groups_of_base_user()
        multi_wh = 'stock.group_stock_multi_warehouses'
        multi_loc = 'stock.group_stock_multi_locations'

        if maximo <= 1 and multi_wh in implicados:
            cls._set_implied_group(multi_wh, False)
        if maximo > 1 and multi_wh not in implicados:
            cls._set_implied_group(multi_loc, True)
            cls._set_implied_group(multi_wh, True)

    @classmethod
    def _update_partner_data(cls, partner_id, company_id):
        """≙ ``_update_partner_data`` (``odoo19c: :327-337``).

        La dirección del almacén hereda la ubicación de tránsito de la empresa
        como su ubicación de cliente y de proveedor — sin eso, un movimiento
        hacia ese contacto no sabría por dónde salir.
        """
        if not partner_id:
            return
        partner_model = apps.get_model('base', 'ResPartner')
        company_model = apps.get_model('base', 'ResCompany')
        empresa = (company_model.objects.filter(pk=company_id).first()
                   if company_id else None)
        if empresa is None:
            return
        transito = empresa.internal_transit_location
        partner_model.objects.filter(pk=getattr(partner_id, 'pk', partner_id)).update(
            property_stock_customer=transito, property_stock_supplier=transito)

    # ------------------------------------------------------------------ #
    # Generación de tipos de operación y secuencias (≙ :339-388)           #
    # ------------------------------------------------------------------ #

    def _create_or_update_sequences_and_picking_types(self):
        """≙ ``_create_or_update_sequences_and_picking_types`` (``odoo19c: :339-388``).

        Crea o actualiza los ocho tipos de operación del almacén. El que ya
        existe se actualiza con ``_get_picking_type_update_values``; el que no,
        se crea con su **secuencia propia** y el siguiente color libre — la
        referencia elige el primero de 0..11 que ningún otro almacén use, para
        que dos almacenes no se vean iguales en el tablero.

        Al final enlaza recepción y entrega como devolución mutua: lo que entra
        por ``in_type`` se devuelve por ``out_type`` y viceversa.
        """
        picking_type_model = apps.get_model('stock', 'StockPickingType')
        sequence_model = apps.get_model('base', 'IrSequence')

        usados = set(picking_type_model.objects.filter(
            warehouse__isnull=False, color__isnull=False
        ).values_list('color', flat=True))
        libres = [c for c in range(0, 12) if c not in usados]
        color = libres[0] if libres else 0

        sequence_data = self._get_sequence_values()
        max_sequence = (picking_type_model.objects.exclude(sequence=None)
                        .order_by('-sequence').values_list('sequence', flat=True)
                        .first() or 0)

        actualizar = self._get_picking_type_update_values()
        crear, _max = self._get_picking_type_create_values(max_sequence)

        resultado = {}
        for campo, valores in actualizar.items():
            existente = getattr(self, campo, None)
            if existente is not None:
                for clave, valor in valores.items():
                    setattr(existente, clave.removesuffix('_id'), valor)
                existente.save()
                continue
            valores = dict(valores, **crear[campo])
            secuencia = sequence_model.objects.create(**sequence_data[campo])
            valores.update(warehouse=self, color=color, sequence_id=secuencia.pk)
            resultado[campo] = picking_type_model.objects.create(**valores).pk

        if 'out_type' in resultado:
            picking_type_model.objects.filter(pk=resultado['out_type']).update(
                return_picking_type_id=resultado.get('in_type'))
        if 'in_type' in resultado:
            picking_type_model.objects.filter(pk=resultado['in_type']).update(
                return_picking_type_id=resultado.get('out_type'))
        return resultado

    # ------------------------------------------------------------------ #
    # Rutas globales (≙ :390-470)                                          #
    # ------------------------------------------------------------------ #

    def _create_or_update_global_routes_rules(self):
        """≙ ``_create_or_update_global_routes_rules`` (``odoo19c: :390-404``).

        Las rutas globales (MTO, Comprar…) no son de un almacén, pero contienen
        **una regla por almacén**. Este método crea o actualiza esa regla para
        que apunte a las ubicaciones que los ejes actuales dictan.
        """
        rule_model = apps.get_model('stock', 'StockRule')
        for campo, detalle in self._get_global_route_rules_values().items():
            valores = dict(detalle.get('update_values', {}))
            regla = getattr(self, campo, None)
            if regla is not None:
                for clave, valor in valores.items():
                    setattr(regla, clave.removesuffix('_id'), valor)
                regla.save()
                continue
            valores.update(detalle['create_values'])
            valores['warehouse_id'] = self.pk
            setattr(self, campo, rule_model.objects.create(**valores))
            self.save()
        return True

    def _find_or_create_global_route(self, xml_id, route_name, create=True,
                                     raise_if_not_found=False):
        """≙ ``_find_or_create_global_route`` (``odoo19c: :406-425``).

        Busca la ruta por su XML ID; si no existe o pertenece a otra empresa, la
        busca por nombre; y si tampoco, la **copia** de la plantilla del XML ID.
        Divergencia D-1: el ``env.ref`` es ``IrModelData.ref``.
        """
        route_model = apps.get_model('stock', 'StockRoute')
        data_model = apps.get_model('base', 'IrModelData')
        ruta_plantilla = data_model.ref(xml_id, raise_if_not_found=False)
        ruta = ruta_plantilla
        empresa = self.company

        if ruta is None or (ruta.company_id and ruta.company_id != self.company_id):
            ruta = route_model.objects.filter(
                expression.AND([
                    Q(name__contains=route_name),
                    Q(company__isnull=True) | Q(company=empresa),
                ])).order_by('company').first()

        if ruta is None:
            if raise_if_not_found:
                raise UserError(_("Can't find any generic route %s.", route_name))
            if ruta_plantilla is not None and create:
                ruta = route_model.objects.create(
                    name=route_name, company=empresa)
        return ruta

    def _get_global_route_rules_values(self):
        """≙ ``_get_global_route_rules_values`` (``odoo19c: :427-442``).

        Filtra del generador las reglas cuya ruta el usuario borró: sin ruta la
        regla no se puede crear, y la referencia elige ignorarla en vez de
        reventar.
        """
        vals = self._generate_global_route_rules_values()
        return {
            k: v for k, v in vals.items()
            if v.get('create_values', {}).get('route_id', True)
            and v.get('update_values', {}).get('route_id', True)
        }

    def _generate_global_route_rules_values(self):
        """≙ ``_generate_global_route_rules_values`` (``odoo19c: :444-470``).

        Genera la regla MTO. El comentario de la referencia explica por qué toma
        la regla cuyo origen es ``lot_stock_id`` y no la primera de la lista:
        *"routing are order from stock to cust; if the routing order is modify,
        the mto rule will be wrong"*.
        """
        reglas = self.get_rules_dict()[self.pk][self.delivery_steps]
        regla = [r for r in reglas if r.from_loc == self.lot_stock][0]
        return {
            'mto_pull': {
                'depends': ['delivery_steps'],
                'create_values': {
                    'active': True,
                    'procure_method': 'make_to_order',
                    'company_id': self.company_id,
                    'action': 'pull',
                    'auto': 'manual',
                    'propagate_carrier': True,
                    'route_id': getattr(self._find_or_create_global_route(
                        'stock.route_warehouse0_mto',
                        _('Replenish on Order (MTO)')), 'pk', None),
                },
                'update_values': {
                    'name': self._format_rulename(regla.from_loc, regla.dest_loc, 'MTO'),
                    'location_dest_id': getattr(regla.dest_loc, 'pk', None),
                    'location_src_id': getattr(regla.from_loc, 'pk', None),
                    'picking_type_id': getattr(regla.picking_type, 'pk', None),
                },
            }
        }

    # ------------------------------------------------------------------ #
    # Rutas del almacén (≙ :472-618)                                       #
    # ------------------------------------------------------------------ #

    def _create_or_update_route(self):
        """≙ ``_create_or_update_route`` (``odoo19c: :472-522``).

        Crea o actualiza las dos rutas del almacén. La secuencia importa:
        primero se **archivan todas las reglas** de la ruta existente, y luego
        se recrean o reactivan sólo las que los ejes actuales necesitan. Así un
        cambio de tres pasos a uno no deja reglas huérfanas activas.
        """
        route_model = apps.get_model('stock', 'StockRoute')
        rutas = []
        reglas_por_paso = self.get_rules_dict()

        for campo, datos in self._get_routes_values().items():
            ruta = getattr(self, campo, None)
            if ruta is not None:
                for clave, valor in datos.get('route_update_values', {}).items():
                    setattr(ruta, clave, valor)
                ruta.save()
                ruta.rule_ids.update(active=False)
            else:
                crear = dict(datos['route_create_values'])
                crear.update(datos.get('route_update_values', {}))
                ruta = route_model.objects.create(**crear)
                setattr(self, campo, ruta)
                self.save()

            reglas = reglas_por_paso[self.pk][datos.get('routing_key')]
            valores = dict(datos.get('rules_values', {}), route_id=ruta.pk)
            self._find_existing_rule_or_create(
                self._get_rule_values(reglas, values=valores))

            if (datos['route_create_values'].get('warehouse_selectable')
                    or datos.get('route_update_values', {}).get('warehouse_selectable')):
                rutas.append(ruta)
        return {'route_ids': [r.pk for r in rutas]}

    def _get_routes_values(self):
        """≙ ``_get_routes_values`` (``odoo19c: :524-580``).

        El contrato de las dos rutas del almacén. Cada entrada declara su
        ``depends`` —el campo cuyo cambio obliga a regenerarla—, cómo crearla y
        cómo actualizarla. Ese ``depends`` es lo que ``write`` lee para no
        reconstruir rutas que nadie tocó.
        """
        return {
            'reception_route': {
                'routing_key': self.reception_steps,
                'depends': ['reception_steps'],
                'route_update_values': {
                    'name': self._format_routename(route_type=self.reception_steps),
                    'active': self.active,
                },
                'route_create_values': {
                    'product_categ_selectable': True,
                    'warehouse_selectable': True,
                    'product_selectable': False,
                    'company_id': self.company_id,
                    'sequence': 50,
                },
                'rules_values': {'active': True, 'propagate_cancel': True},
            },
            'delivery_route': {
                'routing_key': self.delivery_steps,
                'depends': ['delivery_steps'],
                'route_update_values': {
                    'name': self._format_routename(route_type=self.delivery_steps),
                    'active': self.active,
                },
                'route_create_values': {
                    'product_categ_selectable': True,
                    'warehouse_selectable': True,
                    'product_selectable': False,
                    'company_id': self.company_id,
                    'sequence': 60,
                },
                'rules_values': {'active': True, 'propagate_carrier': True},
            },
        }

    def _get_receive_routes_values(self, installed_depends):
        """≙ ``_get_receive_routes_values`` (``odoo19c: :582-616``).

        La misma ruta de recepción pero con ``procure_method: make_to_order``.
        Es un punto de extensión: lo consumen los addons que añaden acciones
        capaces de disparar la recepción bajo pedido, para que ninguna regla
        generada caiga por defecto en ``make_to_stock``.
        """
        return {
            'reception_route': {
                'routing_key': self.reception_steps,
                'depends': ['reception_steps', installed_depends],
                'route_update_values': {
                    'name': self._format_routename(route_type=self.reception_steps),
                    'active': self.active,
                },
                'route_create_values': {
                    'product_categ_selectable': True,
                    'warehouse_selectable': True,
                    'product_selectable': False,
                    'company_id': self.company_id,
                    'sequence': 9,
                },
                'rules_values': {
                    'active': True,
                    'propagate_cancel': True,
                    'procure_method': 'make_to_order',
                },
            }
        }

    def _find_existing_rule_or_create(self, rules_list):
        """≙ ``_find_existing_rule_or_create`` (``odoo19c: :618-632``).

        Busca la regla **archivada** con las mismas cinco coordenadas y la
        reactiva; si no existe, la crea. Reactivar en vez de duplicar es lo que
        permite ir y volver entre modos sin acumular reglas muertas.
        """
        rule_model = apps.get_model('stock', 'StockRule')
        for vals in rules_list:
            existente = rule_model.objects.filter(
                picking_type_id=vals['picking_type_id'],
                location_src_id=vals['location_src_id'],
                location_dest_id=vals['location_dest_id'],
                route_id=vals['route_id'],
                action=vals['action'],
                active=False,
            ).first()
            if existente is None:
                rule_model.objects.create(**vals)
            else:
                existente.active = True
                existente.save()

    # ------------------------------------------------------------------ #
    # Ubicaciones (≙ :634-690)                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_locations_values(cls, vals, code=False):
        """≙ ``_get_locations_values`` (``odoo19c: :634-680``).

        Las cinco sub-ubicaciones con su ``active`` derivado de los dos ejes:
        la entrada sólo existe si la recepción no es de un paso, la de calidad
        sólo con tres pasos, la salida sólo si la entrega no es directa, y la de
        empaque sólo con tres pasos de entrega.
        """
        reception_steps = vals.get('reception_steps', 'one_step')
        delivery_steps = vals.get('delivery_steps', 'ship_only')
        codigo = (vals.get('code') or code or '').replace(' ', '').upper()
        company_id = vals.get('company_id')
        return {
            'lot_stock_id': {
                'name': _('Stock'), 'active': True, 'usage': 'internal',
                'replenish_location': True,
                'barcode': cls._valid_barcode(codigo + 'STOCK', company_id),
            },
            'wh_input_stock_loc_id': {
                'name': _('Input'), 'active': reception_steps != 'one_step',
                'usage': 'internal',
                'barcode': cls._valid_barcode(codigo + 'INPUT', company_id),
            },
            'wh_qc_stock_loc_id': {
                'name': _('Quality Control'),
                'active': reception_steps == 'three_steps', 'usage': 'internal',
                'barcode': cls._valid_barcode(codigo + 'QUALITY', company_id),
            },
            'wh_output_stock_loc_id': {
                'name': _('Output'), 'active': delivery_steps != 'ship_only',
                'usage': 'internal',
                'barcode': cls._valid_barcode(codigo + 'OUTPUT', company_id),
            },
            'wh_pack_stock_loc_id': {
                'name': _('Packing Zone'),
                'active': delivery_steps == 'pick_pack_ship', 'usage': 'internal',
                'barcode': cls._valid_barcode(codigo + 'PACKING', company_id),
            },
        }

    @classmethod
    def _valid_barcode(cls, barcode, company_id):
        """≙ ``_valid_barcode`` (``odoo19c: :682-687``).

        Devuelve el código sólo si nadie de la misma empresa lo usa; si ya está
        tomado devuelve falso, y la ubicación nace sin código de barras en vez
        de romper la restricción de unicidad.
        """
        location_model = apps.get_model('stock', 'StockLocation')
        tomado = location_model.objects.filter(
            barcode=barcode, company_id=company_id).exists()
        return not tomado and barcode

    @classmethod
    def _create_missing_locations(cls, warehouses, vals):
        """≙ ``_create_missing_locations`` (``odoo19c: :689-705``).

        Repone la ubicación que el usuario borró o que un módulo instalado
        después necesita. Sin ella, la creación de tipos de operación y reglas
        fallaría a mitad y dejaría el almacén a medias.
        """
        location_model = apps.get_model('stock', 'StockLocation')
        for warehouse in warehouses:
            company_id = vals.get('company_id', warehouse.company_id)
            sub = cls._get_locations_values(
                dict(vals, company_id=company_id), warehouse.code)
            faltantes = {}
            for campo, valores in sub.items():
                if getattr(warehouse, campo.removesuffix('_id'), None) is None \
                        and campo not in vals:
                    valores['location_id'] = vals.get(
                        'view_location_id', warehouse.view_location_id)
                    valores['company_id'] = company_id
                    faltantes[campo] = location_model.objects.create(**valores).pk
            if faltantes:
                cls.write([warehouse], faltantes)

    def create_resupply_routes(self, supplier_warehouses):
        """≙ ``create_resupply_routes`` (``odoo19c: :707-738``).

        Crea la ruta que trae mercancía de otro almacén. Pasa siempre por una
        ubicación de **tránsito** —interna si los dos almacenes son de la misma
        empresa, externa si no—, y esa distinción es lo que permite que el
        movimiento entre empresas tenga dos patas contables.

        El caso ``ship_only`` del proveedor necesita además una regla MTO
        propia: en los otros modos ya existe.
        """
        route_model = apps.get_model('stock', 'StockRoute')
        rule_model = apps.get_model('stock', 'StockRule')
        transito_interno, transito_externo = self._get_transit_locations()

        for supplier_wh in supplier_warehouses:
            transito = (transito_interno
                        if supplier_wh.company_id == self.company_id
                        else transito_externo)
            if transito is None:
                continue
            transito.active = True
            transito.save()
            salida = (supplier_wh.lot_stock
                      if supplier_wh.delivery_steps == 'ship_only'
                      else supplier_wh.wh_output_stock_loc)

            if supplier_wh.delivery_steps == 'ship_only':
                ruteo = [Routing(salida, transito, supplier_wh.out_type, 'pull')]
                mto = supplier_wh._get_global_route_rules_values().get('mto_pull')
                vals = supplier_wh._get_rule_values(
                    ruteo, mto['create_values'], name_suffix='MTO')
                rule_model.objects.create(**vals[0])

            inter_wh = route_model.objects.create(
                **self._get_inter_warehouse_route_values(supplier_wh))

            reglas = supplier_wh._get_supply_pull_rules_values(
                [Routing(salida, transito, supplier_wh.out_type, 'pull')],
                values={'route_id': inter_wh.pk, 'location_dest_from_rule': True})
            if supplier_wh.delivery_steps != 'ship_only':
                reglas += supplier_wh._get_supply_pull_rules_values(
                    [Routing(supplier_wh.lot_stock, salida,
                             supplier_wh.pick_type, 'pull')],
                    values={'route_id': inter_wh.pk})
            reglas += self._get_supply_pull_rules_values(
                [Routing(transito, self.lot_stock, self.in_type, 'pull')],
                values={'route_id': inter_wh.pk})
            for vals in reglas:
                rule_model.objects.create(**vals)

    # ------------------------------------------------------------------ #
    # Herramientas de ruteo (≙ :740-812)                                   #
    # ------------------------------------------------------------------ #

    def _get_input_output_locations(self, reception_steps, delivery_steps):
        """≙ ``_get_input_output_locations`` (``odoo19c: :742-744``).

        Con un solo paso, la entrada y la salida **son la estantería**: no hay
        ubicación intermedia. Es la regla que hace que cambiar de modo mueva
        todos los tipos de operación de golpe.
        """
        return (
            self.lot_stock if reception_steps == 'one_step' else self.wh_input_stock_loc,
            self.lot_stock if delivery_steps == 'ship_only' else self.wh_output_stock_loc,
        )

    def _get_transit_locations(self):
        """≙ ``_get_transit_locations`` (``odoo19c: :746-747``).

        La interna la aporta la empresa; la de entre-empresas es una ubicación
        sembrada por XML ID. Divergencia D-1 para la segunda.
        """
        data_model = apps.get_model('base', 'IrModelData')
        interna = getattr(self.company, 'internal_transit_location', None)
        externa = data_model.ref('stock.stock_location_inter_company',
                                 raise_if_not_found=False)
        return interna, externa

    @classmethod
    def _get_partner_locations(cls):
        """≙ ``_get_partner_locations`` (``odoo19c: :749-761``).

        Las ubicaciones virtuales de cliente y proveedor. Se buscan por XML ID y,
        si no están sembradas, **por su ``usage``** — el mismo fallback que la
        referencia escribe a mano (divergencia D-1). Si no hay ninguna de las
        dos, revienta: sin ellas no hay ruta que generar.
        """
        location_model = apps.get_model('stock', 'StockLocation')
        data_model = apps.get_model('base', 'IrModelData')
        cliente = data_model.ref('stock.stock_location_customers',
                                 raise_if_not_found=False)
        proveedor = data_model.ref('stock.stock_location_suppliers',
                                   raise_if_not_found=False)
        if cliente is None:
            cliente = location_model.objects.filter(usage='customer').first()
        if proveedor is None:
            proveedor = location_model.objects.filter(usage='supplier').first()
        if cliente is None and proveedor is None:
            raise UserError(_("Can't find any customer or supplier location."))
        return cliente, proveedor

    def _get_route_name(self, route_type):
        """≙ ``_get_route_name`` (``odoo19c: :763-764``)."""
        return ROUTE_NAMES[route_type]

    def get_rules_dict(self):
        """≙ ``get_rules_dict`` (``odoo19c: :766-791``).

        **El corazón del archivo.** Para cada uno de los seis modos declara la
        cadena de saltos: origen, destino, tipo de operación y si la regla es de
        arrastre (``pull``) o de empuje (``push``).

        La distinción no es decorativa. El primer salto de una recepción es
        ``pull`` porque lo dispara la necesidad; los siguientes son ``push``
        porque los dispara la llegada de la mercancía al paso anterior.
        """
        cliente, proveedor = self._get_partner_locations()
        return {
            w.pk: {
                'one_step': [Routing(proveedor, w.lot_stock, w.in_type, 'pull')],
                'two_steps': [
                    Routing(proveedor, w.lot_stock, w.in_type, 'pull'),
                    Routing(w.wh_input_stock_loc, w.lot_stock, w.store_type, 'push')],
                'three_steps': [
                    Routing(proveedor, w.lot_stock, w.in_type, 'pull'),
                    Routing(w.wh_input_stock_loc, w.wh_qc_stock_loc, w.qc_type, 'push'),
                    Routing(w.wh_qc_stock_loc, w.lot_stock, w.store_type, 'push')],
                'ship_only': [Routing(w.lot_stock, cliente, w.out_type, 'pull')],
                'pick_ship': [
                    Routing(w.lot_stock, cliente, w.pick_type, 'pull'),
                    Routing(w.wh_output_stock_loc, cliente, w.out_type, 'push')],
                'pick_pack_ship': [
                    Routing(w.lot_stock, cliente, w.pick_type, 'pull'),
                    Routing(w.wh_pack_stock_loc, w.wh_output_stock_loc,
                            w.pack_type, 'push'),
                    Routing(w.wh_output_stock_loc, cliente, w.out_type, 'push')],
                'company_id': w.company_id,
            }
            for w in [self]
        }

    def _get_receive_rules_dict(self):
        """≙ ``_get_receive_rules_dict`` (``odoo19c: :793-806``).

        Las mismas reglas de recepción **sin el primer arrastre**. Punto de
        extensión hermano de ``_get_receive_routes_values``: los addons que
        disparan la recepción bajo pedido no quieren que la ruta arrastre por
        su cuenta.
        """
        return {
            'one_step': [],
            'two_steps': [Routing(self.wh_input_stock_loc, self.lot_stock,
                                  self.store_type, 'push')],
            'three_steps': [
                Routing(self.wh_input_stock_loc, self.wh_qc_stock_loc,
                        self.qc_type, 'push'),
                Routing(self.wh_qc_stock_loc, self.lot_stock,
                        self.store_type, 'push')],
        }

    def _get_inter_warehouse_route_values(self, supplier_warehouse):
        """≙ ``_get_inter_warehouse_route_values`` (``odoo19c: :808-817``).

        La empresa de la ruta es la **intersección** de las dos: si los almacenes
        son de empresas distintas, la ruta queda global.
        """
        misma = (self.company if self.company_id == supplier_warehouse.company_id
                 else None)
        return {
            'name': _('%(warehouse)s: Supply Product from %(supplier)s',
                      warehouse=self.name, supplier=supplier_warehouse.name),
            'warehouse_selectable': True,
            'product_selectable': True,
            'product_categ_selectable': True,
            'supplied_wh_id': self.pk,
            'supplier_wh_id': supplier_warehouse.pk,
            'company_id': getattr(misma, 'pk', None),
        }

    # ------------------------------------------------------------------ #
    # Herramientas de arrastre/empuje (≙ :819-880)                         #
    # ------------------------------------------------------------------ #

    def _get_rule_values(self, route_values, values=None, name_suffix=''):
        """≙ ``_get_rule_values`` (``odoo19c: :822-856``).

        Convierte la cadena de ``Routing`` en valores de regla. Dos detalles que
        la referencia comenta y conviene no perder:

        - **sólo la primera regla es ``make_to_stock``**; las siguientes son
          ``make_to_order``, porque encadenan sobre la anterior;
        - **la última regla NO propaga la cancelación**. Su comentario da el
          caso: en ``Input → QC → Stock → Cliente``, cancelar ``I→QC`` debe
          cancelar ``QC→S`` pero no ``S→C``.
        """
        primera = True
        rules_list = []
        for routing in route_values:
            vals = {
                'name': self._format_rulename(routing.from_loc, routing.dest_loc,
                                              name_suffix),
                'location_src_id': getattr(routing.from_loc, 'pk', None),
                'location_dest_id': getattr(routing.dest_loc, 'pk', None),
                'action': routing.action,
                'auto': 'manual',
                'picking_type_id': getattr(routing.picking_type, 'pk', None),
                'procure_method': 'make_to_stock' if primera else 'make_to_order',
                'warehouse_id': self.pk,
                'company_id': self.company_id,
            }
            vals.update(values or {})
            rules_list.append(vals)
            primera = False
        if values and values.get('propagate_cancel') and rules_list:
            rules_list[-1]['propagate_cancel'] = False
        return rules_list

    def _get_supply_pull_rules_values(self, route_values, values=None):
        """≙ ``_get_supply_pull_rules_values`` (``odoo19c: :858-865``).

        El primer tramo de una ruta de reabastecimiento sale de la estantería y
        es ``make_to_stock``; los demás son ``make_to_order``. Es la regla que
        evita que el almacén proveedor fabrique bajo pedido lo que ya tiene.
        """
        pull_values = dict(values or {})
        pull_values['active'] = True
        rules_list = self._get_rule_values(route_values, values=pull_values)
        for vals in rules_list:
            vals['procure_method'] = (
                'make_to_order' if self.lot_stock_id != vals['location_src_id']
                else 'make_to_stock')
        return rules_list

    @classmethod
    def _update_reception_delivery_resupply(cls, warehouses, reception_new, delivery_new):
        """≙ ``_update_reception_delivery_resupply`` (``odoo19c: :867-873``).

        Sólo actúa cuando la entrega **cruza** el umbral de ``ship_only``: es el
        único cambio que altera por dónde salen las rutas de reabastecimiento.
        """
        for warehouse in warehouses:
            _entrada, salida = warehouse._get_input_output_locations(
                reception_new, delivery_new)
            if (delivery_new and warehouse.delivery_steps != delivery_new
                    and (warehouse.delivery_steps == 'ship_only'
                         or delivery_new == 'ship_only')):
                a_varios = warehouse.delivery_steps == 'ship_only'
                warehouse._check_delivery_resupply(salida, a_varios)

    def _check_delivery_resupply(self, new_location, change_to_multiple):
        """≙ ``_check_delivery_resupply`` (``odoo19c: :875-921``).

        Reapunta las reglas que abastecen a otros almacenes cuando este cambia
        de número de pasos de entrega. Los dos sentidos son asimétricos:

        - **hacia un solo paso**: se archiva la regla extra que abastecía la
          salida desde la estantería y se crean las reglas MTO que la
          sustituyen;
        - **hacia varios pasos**: se reactivan (o crean) esas reglas extra, y se
          **archivan las MTO** que quedarían compitiendo con ellas.
        """
        rule_model = apps.get_model('stock', 'StockRule')
        route_model = apps.get_model('stock', 'StockRoute')
        rutas = route_model.objects.filter(supplier_wh=self)
        reglas = rule_model.objects.filter(
            route__in=rutas, location_dest__usage='transit').exclude(action='push')
        destinos = [r.location_dest for r in reglas]
        reglas.update(
            location_src=new_location,
            procure_method='make_to_order' if change_to_multiple else 'make_to_stock')

        if not change_to_multiple:
            rule_model.objects.filter(
                route__in=rutas, location_dest_id=self.wh_output_stock_loc_id,
                picking_type_id=self.pick_type_id,
            ).exclude(action='push').update(active=False)

            ruteos = [Routing(self.lot_stock, destino, self.out_type, 'pull')
                      for destino in destinos]
            mto = self._get_global_route_rules_values().get('mto_pull')
            for vals in self._get_rule_values(ruteos, mto['create_values'],
                                              name_suffix='MTO'):
                rule_model.objects.create(**vals)
            return

        a_reactivar = rule_model.objects.filter(
            route__in=rutas, location_dest_id=self.wh_output_stock_loc_id,
            picking_type_id=self.pick_type_id).exclude(action='push')
        encontradas = set(a_reactivar.values_list('route_id', flat=True))
        a_reactivar.update(active=True)

        for ruta in rutas.exclude(pk__in=encontradas):
            for vals in self._get_supply_pull_rules_values(
                    [Routing(self.lot_stock, new_location, self.pick_type, 'pull')],
                    values={'route_id': ruta.pk}):
                rule_model.objects.create(**vals)

        mto_route = self._find_or_create_global_route(
            'stock.route_warehouse0_mto', _('Replenish on Order (MTO)'), create=False)
        rule_model.objects.filter(
            route=mto_route, location_dest__usage='transit',
            location_src_id=self.lot_stock_id,
        ).exclude(action='push').update(active=False)

    @classmethod
    def _update_name_and_code(cls, warehouses, new_name=False, new_code=False):
        """≙ ``_update_name_and_code`` (``odoo19c: :923-947``).

        Renombrar el almacén reescribe el nombre de sus rutas, sus reglas y sus
        ocho secuencias. La referencia lo hace por **reemplazo del prefijo**
        (``replace(old, new, 1)``) y su propio comentario duda de ello —*"not
        better to re-generate the route naming?"*—; se conserva tal cual, porque
        regenerar perdería los sufijos que otros addons hayan añadido.
        """
        location_model = apps.get_model('stock', 'StockLocation')
        for warehouse in warehouses:
            if new_code:
                location_model.objects.filter(
                    pk__in=location_model.objects.filter(
                        pk=warehouse.lot_stock_id).values_list('location_id', flat=True)
                ).update(name=new_code)
            if new_name:
                for ruta in warehouse.route_ids.all():
                    ruta.name = ruta.name.replace(warehouse.name, new_name, 1)
                    ruta.save()
                    for regla in ruta.rule_ids.all():
                        regla.name = regla.name.replace(warehouse.name, new_name, 1)
                        regla.save()
                if warehouse.mto_pull is not None:
                    warehouse.mto_pull.name = warehouse.mto_pull.name.replace(
                        warehouse.name, new_name, 1)
                    warehouse.mto_pull.save()

            datos = warehouse._get_sequence_values(name=new_name, code=new_code)
            for campo in PICKING_TYPE_FIELDS:
                tipo = getattr(warehouse, campo, None)
                if tipo is None or tipo.sequence_id is None:
                    continue
                sequence_model = apps.get_model('base', 'IrSequence')
                sequence_model.objects.filter(pk=tipo.sequence_id).update(**datos[campo])

    @classmethod
    def _update_location_reception(cls, warehouses, new_reception_step):
        """≙ ``_update_location_reception`` (``odoo19c: :949-951``)."""
        location_model = apps.get_model('stock', 'StockLocation')
        location_model.objects.filter(
            pk__in=[w.wh_qc_stock_loc_id for w in warehouses if w.wh_qc_stock_loc_id]
        ).update(active=new_reception_step == 'three_steps')
        location_model.objects.filter(
            pk__in=[w.wh_input_stock_loc_id for w in warehouses if w.wh_input_stock_loc_id]
        ).update(active=new_reception_step != 'one_step')

    @classmethod
    def _update_location_delivery(cls, warehouses, new_delivery_step):
        """≙ ``_update_location_delivery`` (``odoo19c: :953-955``)."""
        location_model = apps.get_model('stock', 'StockLocation')
        location_model.objects.filter(
            pk__in=[w.wh_pack_stock_loc_id for w in warehouses if w.wh_pack_stock_loc_id]
        ).update(active=new_delivery_step == 'pick_pack_ship')
        location_model.objects.filter(
            pk__in=[w.wh_output_stock_loc_id for w in warehouses if w.wh_output_stock_loc_id]
        ).update(active=new_delivery_step != 'ship_only')

    # ------------------------------------------------------------------ #
    # Valores de los tipos de operación y sus secuencias (≙ :957-1128)     #
    # ------------------------------------------------------------------ #

    def _get_picking_type_update_values(self):
        """≙ ``_get_picking_type_update_values`` (``odoo19c: :960-1000``).

        Qué cambia en cada tipo de operación cuando se mueven los ejes. Lo
        importante es el ``active``: el tipo no se borra al bajar de tres pasos
        a uno — se archiva, y vuelve intacto al subir otra vez.
        """
        entrada, salida = self._get_input_output_locations(
            self.reception_steps, self.delivery_steps)
        codigo = (self.code or '').replace(' ', '').upper()
        return {
            'in_type': {
                'default_location_dest_id': getattr(entrada, 'pk', None),
                'barcode': codigo + 'IN',
            },
            'out_type': {
                'default_location_src_id': getattr(salida, 'pk', None),
                'barcode': codigo + 'OUT',
            },
            'pick_type': {
                'active': self.delivery_steps != 'ship_only' and self.active,
                'default_location_dest_id': (
                    getattr(salida, 'pk', None) if self.delivery_steps == 'pick_ship'
                    else self.wh_pack_stock_loc_id),
                'barcode': codigo + 'PICK',
            },
            'pack_type': {
                'active': self.delivery_steps == 'pick_pack_ship' and self.active,
                'default_location_dest_id': getattr(salida, 'pk', None),
                'barcode': codigo + 'PACK',
            },
            'qc_type': {
                'active': self.reception_steps == 'three_steps' and self.active,
                'barcode': codigo + 'QC',
            },
            'store_type': {
                'active': self.reception_steps != 'one_step' and self.active,
                'default_location_src_id': (
                    getattr(entrada, 'pk', None)
                    if self.reception_steps == 'two_steps'
                    else self.wh_qc_stock_loc_id),
                'barcode': codigo + 'STOR',
            },
            'int_type': {'barcode': codigo + 'INT'},
            'xdock_type': {
                'active': (self.reception_steps != 'one_step'
                           and self.delivery_steps != 'ship_only' and self.active),
                'barcode': codigo + 'XD',
            },
        }

    def _get_picking_type_create_values(self, max_sequence):
        """≙ ``_get_picking_type_create_values`` (``odoo19c: :1002-1080``).

        Los ocho tipos se crean **todos a la vez**, con el almacén, y luego se
        activan o archivan según los ejes. Su orden en el tablero lo fija el
        ``max_sequence + N`` de la referencia: recepción 1, calidad 2, almacenaje
        3, internas 4, pick 5, pack 6, entrega 7, cross-dock 8.

        Devuelve la tupla ``(valores, siguiente max_sequence)`` que la fuente
        devuelve.
        """
        entrada, salida = self._get_input_output_locations(
            self.reception_steps, self.delivery_steps)
        empresa = self.company_id
        return {
            'in_type': {
                'name': _('Receipts'), 'code': 'incoming',
                'use_existing_lots': False, 'sequence': max_sequence + 1,
                'sequence_code': 'IN', 'company_id': empresa,
            },
            'out_type': {
                'name': _('Delivery Orders'), 'code': 'outgoing',
                'use_create_lots': False, 'sequence': max_sequence + 7,
                'sequence_code': 'OUT', 'print_label': True, 'company_id': empresa,
            },
            'pack_type': {
                'name': _('Pack'), 'code': 'internal',
                'use_create_lots': False, 'use_existing_lots': True,
                'default_location_src_id': self.wh_pack_stock_loc_id,
                'default_location_dest_id': getattr(salida, 'pk', None),
                'sequence': max_sequence + 6, 'sequence_code': 'PACK',
                'company_id': empresa,
            },
            'pick_type': {
                'name': _('Pick'), 'code': 'internal',
                'use_create_lots': False, 'use_existing_lots': True,
                'default_location_src_id': self.lot_stock_id,
                'sequence': max_sequence + 5, 'sequence_code': 'PICK',
                'company_id': empresa,
            },
            'qc_type': {
                'name': _('Quality Control'), 'code': 'internal',
                'use_create_lots': False, 'use_existing_lots': True,
                'default_location_src_id': self.wh_input_stock_loc_id,
                'default_location_dest_id': self.wh_qc_stock_loc_id,
                'sequence': max_sequence + 2, 'sequence_code': 'QC',
                'company_id': empresa,
            },
            'store_type': {
                'name': _('Storage'), 'code': 'internal',
                'use_create_lots': False, 'use_existing_lots': True,
                'default_location_dest_id': self.lot_stock_id,
                'sequence': max_sequence + 3, 'sequence_code': 'STOR',
                'company_id': empresa,
            },
            'int_type': {
                'name': _('Internal Transfers'), 'code': 'internal',
                'use_create_lots': False, 'use_existing_lots': True,
                'default_location_src_id': self.lot_stock_id,
                'default_location_dest_id': self.lot_stock_id,
                'active': 'stock.group_stock_multi_locations'
                          in self._implied_groups_of_base_user(),
                'sequence': max_sequence + 4, 'sequence_code': 'INT',
                'company_id': empresa,
            },
            'xdock_type': {
                'name': _('Cross Dock'), 'code': 'internal',
                'use_create_lots': False, 'use_existing_lots': True,
                'default_location_src_id': self.wh_input_stock_loc_id,
                'default_location_dest_id': self.wh_output_stock_loc_id,
                'sequence': max_sequence + 8, 'sequence_code': 'XD',
                'company_id': empresa,
            },
        }, max_sequence + 9

    def _get_sequence_values(self, name=False, code=False):
        """≙ ``_get_sequence_values`` (``odoo19c: :1082-1128``).

        Cada tipo de operación lleva su propia secuencia, con prefijo
        ``<código>/<sequence_code>/`` y relleno a cinco dígitos. El
        ``sequence_code`` del tipo gana sobre el literal — así un addon que lo
        cambie no queda con un prefijo que ya no le corresponde.
        """
        nombre = name or self.name
        codigo = code or self.code
        empresa = self.company_id
        etiquetas = {
            'in_type': ('in', 'IN'), 'out_type': ('out', 'OUT'),
            'pack_type': ('packing', 'PACK'), 'pick_type': ('picking', 'PICK'),
            'qc_type': ('quality control', 'QC'), 'store_type': ('storage', 'STOR'),
            'int_type': ('internal', 'INT'), 'xdock_type': ('cross dock', 'XD'),
        }
        valores = {}
        for campo, (sufijo, por_defecto) in etiquetas.items():
            tipo = getattr(self, campo, None)
            valores[campo] = {
                'name': _('%(name)s Sequence ' + sufijo, name=nombre),
                'prefix': f'{codigo}/{getattr(tipo, "sequence_code", None) or por_defecto}/',
                'padding': 5,
                'company_id': empresa,
            }
        return valores

    def _format_rulename(self, from_loc, dest_loc, suffix):
        """≙ ``_format_rulename`` (``odoo19c: :1130-1136``)."""
        nombre = f'{self.code}: {getattr(from_loc, "name", "")}'
        if dest_loc is not None:
            nombre += f' → {dest_loc.name}'
        if suffix:
            nombre += f' ({suffix})'
        return nombre

    def _format_routename(self, name=None, route_type=None):
        """≙ ``_format_routename`` (``odoo19c: :1138-1141``)."""
        if route_type:
            name = self._get_route_name(route_type)
        return f'{self.name}: {name}'

    def _get_all_routes(self):
        """≙ ``_get_all_routes`` (``odoo19c: :1143-1146``).

        Las del almacén, la de su regla MTO, y las que lo abastecen —incluidas
        las archivadas, porque la vista de rutas las muestra.
        """
        route_model = apps.get_model('stock', 'StockRoute')
        ids = set(self.route_ids.values_list('pk', flat=True))
        if self.mto_pull is not None and self.mto_pull.route_id:
            ids.add(self.mto_pull.route_id)
        ids.update(route_model.objects.filter(supplied_wh=self)
                   .values_list('pk', flat=True))
        return route_model.objects.filter(pk__in=ids)

    def action_view_all_routes(self):
        """≙ ``action_view_all_routes`` (``odoo19c: :1148-1159``). Divergencia D-2."""
        rutas = self._get_all_routes()
        return {
            'name': _("Warehouse's Routes"),
            'domain': [('id', 'in', list(rutas.values_list('pk', flat=True)))],
            'res_model': 'stock.route',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'list,form',
            'limit': 20,
            'context': {'default_warehouse_selectable': True,
                        'default_warehouse_ids': [self.pk]},
        }

    @classmethod
    def get_current_warehouses(cls):
        """≙ ``get_current_warehouses`` (``odoo19c: :1161-1162``)."""
        return list(cls.objects.values('id', 'name', 'code'))

    # ------------------------------------------------------------------ #
    # Ayudantes de grupo (no son símbolos de la referencia)                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _implied_groups_of_base_user(cls):
        """Los XML ID de los grupos implicados por ``base.group_user``.

        **No es un símbolo de la referencia.** Allá esto es
        ``self.env.ref('base.group_user').implied_ids``, una navegación de una
        línea; aquí hace falta resolver el XML ID y leer la relación, y eso lo
        usan tres métodos. Se declara aparte para no repetirlo tres veces, y se
        nombra aquí para que no se lea como un símbolo inventado.
        """
        data_model = apps.get_model('base', 'IrModelData')
        grupo = data_model.ref('base.group_user', raise_if_not_found=False)
        if grupo is None:
            return set()
        return {
            data_model.xmlid_of(g) for g in grupo.implied_ids.all()
        } - {None}

    @classmethod
    def _set_implied_group(cls, xml_id, activo):
        """Enciende o apaga un grupo implicado por ``base.group_user``.

        **No es un símbolo de la referencia** — es el
        ``group_user.write({'implied_ids': [(4|3, …)]})`` de
        ``_check_multiwarehouse_group``, extraído por la misma razón que el
        ayudante de arriba.
        """
        data_model = apps.get_model('base', 'IrModelData')
        base_user = data_model.ref('base.group_user', raise_if_not_found=False)
        grupo = data_model.ref(xml_id, raise_if_not_found=False)
        if base_user is None or grupo is None:
            return
        if activo:
            base_user.implied_ids.add(grupo)
        else:
            base_user.implied_ids.remove(grupo)

    @classmethod
    def _user_has_group(cls, user, xml_id):
        """¿El usuario pertenece al grupo del XML ID? — ≙ ``user.has_group``.

        **No es un símbolo de la referencia**: allá ``has_group`` vive en
        ``res.users``. Aquí se resuelve por ``IrModelData`` hasta que ese método
        exista en el puerto de ``res.users``.
        """
        data_model = apps.get_model('base', 'IrModelData')
        grupo = data_model.ref(xml_id, raise_if_not_found=False)
        if grupo is None or user is None:
            return False
        return grupo.user_ids.filter(pk=user.pk).exists()


class StockWarehouseResupply(models.Model):
    """Tabla intermedia de ``resupply_wh_ids`` (≙ ``stock_wh_resupply_table``, ``:84-86``)."""

    supplied_wh = fields.Many2one(
        'stock.StockWarehouse', on_delete=models.CASCADE, related_name='+',
        help_text='Almacén abastecido (Odoo supplied_wh_id).',
    )
    supplier_wh = fields.Many2one(
        'stock.StockWarehouse', on_delete=models.CASCADE, related_name='+',
        help_text='Almacén que abastece (Odoo supplier_wh_id).',
    )

    class Meta:
        db_table = 'stock_wh_resupply_table'
        constraints = [
            models.UniqueConstraint(fields=['supplied_wh', 'supplier_wh'],
                                    name='unique_stock_wh_resupply'),
        ]
        verbose_name = 'Reabastecimiento entre almacenes'
        verbose_name_plural = 'Reabastecimientos entre almacenes'

    def __str__(self):
        return f'{self.supplied_wh_id} ← {self.supplier_wh_id}'


__all__ = [
    'PICKING_TYPE_FIELDS',
    'ROUTE_NAMES',
    'Routing',
    'StockWarehouse',
    'StockWarehouseResupply',
]
