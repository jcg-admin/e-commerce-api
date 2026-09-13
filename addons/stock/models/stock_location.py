"""``stock.location`` y ``stock.route`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_location.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: la **ubicación** es el nodo del árbol físico del almacén —zona, pasillo,
estante— y también el contraparte virtual de un proveedor, un cliente o una
pérdida de inventario. Todo movimiento sale de una y entra en otra. La **ruta**
es el camino declarado que sigue un producto entre ubicaciones; agrupa reglas
(``stock.rule``) y se selecciona en el producto, la categoría, el almacén o el
tipo de paquete.

Porte símbolo por símbolo — 2 clases, 63 símbolos
==================================================

Medido sobre ``odoo19c: addons/stock/models/stock_location.py`` (595 líneas):
``StockLocation`` con 26 campos, 3 restricciones y 24 métodos; ``StockRoute``
con 14 campos y 8 métodos.

``StockLocation``
-------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``default_get`` (22-27)                          ``default_get`` (classmethod)
``name`` (29)                                    ``name``
``complete_name`` (30)                           ``complete_name`` (almacenado)
``active`` (31)                                  ``active``
``usage`` (32-46)                                ``usage``
``location_id`` (47-49)                          ``location``
``child_ids`` (50)                               reverso ``child_ids``
``child_internal_location_ids`` (51-57)          property ``child_internal_location_ids``
``parent_path`` (58)                             ``parent_path``
``company_id`` (59-62)                           ``company``
``replenish_location`` (63-64)                   ``replenish_location``
``removal_strategy_id`` (65-76)                  ``removal_strategy``
``putaway_rule_ids`` (77)                        reverso ``putaway_rule_ids``
``barcode`` (78)                                 ``barcode``
``quant_ids`` (79)                               reverso ``quant_ids``
``cyclic_inventory_frequency`` (80)              ``cyclic_inventory_frequency``
``last_inventory_date`` (81)                     ``last_inventory_date``
``next_inventory_date`` (82)                     ``next_inventory_date`` (almacenado)
``warehouse_view_ids`` (83)                      reverso ``warehouse_view_ids``
``warehouse_id`` (84)                            ``warehouse`` (almacenado)
``storage_category_id`` (85)                     ``storage_category``
``outgoing_move_line_ids`` (86)                  reverso ``outgoing_move_line_ids``
``incoming_move_line_ids`` (87)                  reverso ``incoming_move_line_ids``
``net_weight`` (88)                              property ``net_weight``
``forecast_weight`` (89)                         property ``forecast_weight``
``is_empty`` (90)                                property ``is_empty``
``_barcode_company_uniq`` (92-95)                ``UniqueConstraint`` homónimo
``_inventory_freq_nonneg`` (96-99)               ``CheckConstraint`` homónimo
``_parent_path_id_idx`` (100)                    ``Index`` homónimo
``_compute_display_name`` (102-112)              ``__str__``
``_compute_weight`` (114-122)                    ``get_weight`` + las 2 properties
``_compute_complete_name`` (124-130)             ``compute_complete_name``
``_compute_is_empty`` (132-139)                  property ``is_empty``
``_compute_next_inventory_date`` (141-158)       ``compute_next_inventory_date``
``_compute_warehouse_id`` (160-172)              ``compute_warehouse``
``_compute_child_internal_location_ids`` (174-178) property homónima
``_compute_replenish_location`` (180-183)        ``compute_replenish_location``
``_check_replenish_location`` (185-192)          ``check_replenish_location``
``_check_scrap_location`` (194-198)              ``check_scrap_location``
``_unlink_except_master_data`` (200-204)         ``check_can_delete``
``_search_is_empty`` (206-217)                   ``search_is_empty`` (classmethod)
``write`` (219-267)                              ``write``
``unlink`` (269-270)                             ``unlink``
``name_create`` (272-284)                        ``name_create`` (classmethod)
``create`` (286-290)                             ``create`` (classmethod)
``copy_data`` (292-298)                          ``copy_data``
``_get_putaway_strategy`` (300-374)              ``_get_putaway_strategy``
``_get_next_inventory_date`` (376-406)           ``get_next_inventory_date``
``should_bypass_reservation`` (408-410)          ``should_bypass_reservation``
``_check_access_putaway`` (412-413)              ``check_access_putaway``
``_check_can_be_used`` (415-461)                 ``check_can_be_used``
``_child_of`` (463-465)                          ``child_of``
``_is_outgoing`` (467-472)                       ``is_outgoing``
``_get_weight`` (474-513)                        ``get_weight`` (classmethod)
===============================================  ======================================

``StockRoute``
----------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``name`` (521)                                   ``name``
``active`` (522)                                 ``active``
``sequence`` (523)                               ``sequence``
``rule_ids`` (524)                               reverso ``rule_ids``
``product_selectable`` (525)                     ``product_selectable``
``product_categ_selectable`` (526)               ``product_categ_selectable``
``warehouse_selectable`` (527)                   ``warehouse_selectable``
``package_type_selectable`` (528)                ``package_type_selectable``
``supplied_wh_id`` (529)                         ``supplied_wh``
``supplier_wh_id`` (530)                         ``supplier_wh``
``company_id`` (531-534)                         ``company``
``product_ids`` (535-537)                        ``product_ids`` (M2M)
``categ_ids`` (538)                              ``categ_ids`` (M2M)
``warehouse_domain_ids`` (539)                   property ``warehouse_domain_ids``
``warehouse_ids`` (540-542)                      ``warehouse_ids`` (M2M)
``copy_data`` (544-550)                          ``copy_data``
``_compute_warehouses`` (552-556)                property ``warehouse_domain_ids``
``_onchange_company`` (558-561)                  ``apply_company_filter``
``_onchange_warehouse_selectable`` (563-566)     ``apply_warehouse_selectable``
``write`` (568-575)                              ``write``
``_check_company_consistency`` (577-590)         ``check_company_consistency``
``_is_valid_resupply_route_for_product`` (592-593) ``_is_valid_resupply_route_for_product``
===============================================  ======================================

Divergencias declaradas
=========================

1. **``parent_path`` se mantiene en ``save()``, no por ``_parent_store``.** La
   referencia declara ``_parent_store = True`` y su ORM materializa la ruta
   ``1/4/9/`` al escribir. Este ORM no tiene ese mecanismo, así que el mismo
   invariante se sostiene en ``save()`` — y con él siguen funcionando
   ``child_of`` y ``compute_warehouse``, que leen la ruta materializada.
   Construirlo como mecanismo del ORM es la tarea **#191**.
2. **Los ``compute`` sin ``store`` son ``property``.** ``net_weight``,
   ``forecast_weight``, ``is_empty``, ``child_internal_location_ids`` y
   ``warehouse_domain_ids`` no tienen columna en la referencia y no la tienen
   aquí. Los tres que **sí** almacena (``complete_name``,
   ``next_inventory_date``, ``warehouse_id``) son columnas, y su recálculo se
   dispara en ``save()``.
3. **Los ``@api.onchange`` son métodos explícitos.** ``_onchange_company`` y
   ``_onchange_warehouse_selectable`` de ``StockRoute`` son reacciones del
   cliente web de Odoo; aquí son métodos que el consumidor llama, con el mismo
   cuerpo. No se pierde la regla, se pierde el disparo automático en un
   formulario que este stack no tiene.
4. **El lado ``stock.warehouse`` de ``@api.depends('warehouse_view_ids',
   'location_id')`` lo dispara** ``StockWarehouse.save()`` **, no este
   archivo** (tarea **#503**, cierra :ref:`h-api-667`). ``compute_warehouse()``
   ya resuelve correctamente el lado ``location_id`` (se recalcula en cada
   ``save()`` propio, y busca el ancestro más profundo **incluyéndose a sí
   misma**, igual que la referencia: su ``[:-1]`` recorta el elemento vacío
   de la barra final, no el ``id`` propio). Lo que faltaba es el lado
   ``warehouse_view_ids``: cuando
   un almacén nuevo apunta su ``view_location`` a un árbol de ubicaciones ya
   existente, ninguna de esas ubicaciones se vuelve a guardar por su cuenta,
   así que su ``warehouse`` queda ``None`` hasta el próximo ``save()`` propio.
   Ver D-4 en ``stock_warehouse.py`` para la medición y el fix — que delega
   de vuelta en ``compute_warehouse()`` de este archivo, sin duplicar la
   regla de «ancestro más profundo».
"""
import calendar
import datetime
from collections import defaultdict

import fields
import api
import models
from django.apps import apps
from django.db.models import Q, Sum

from addons.base.models import TimeStampedModel
from addons.base.models.ir_model import IrModelData
from addons.product.models.product_product import ProductProduct
from exceptions import UserError, ValidationError
from tools.translate import _

USAGE_SUPPLIER = 'supplier'
USAGE_VIEW = 'view'
USAGE_INTERNAL = 'internal'
USAGE_CUSTOMER = 'customer'
USAGE_INVENTORY = 'inventory'
USAGE_PRODUCTION = 'production'
USAGE_TRANSIT = 'transit'

USAGE_CHOICES = [
    (USAGE_SUPPLIER, 'Proveedor'),
    (USAGE_VIEW, 'Virtual'),
    (USAGE_INTERNAL, 'Interna'),
    (USAGE_CUSTOMER, 'Cliente'),
    (USAGE_INVENTORY, 'Pérdida de inventario'),
    (USAGE_PRODUCTION, 'Producción'),
    (USAGE_TRANSIT, 'Tránsito'),
]

#: ≙ el conjunto que ``should_bypass_reservation`` prueba (``odoo19c: :408-410``).
BYPASS_RESERVATION_USAGES = (
    USAGE_SUPPLIER, USAGE_CUSTOMER, USAGE_INVENTORY, USAGE_PRODUCTION,
)

#: ≙ las dos que cuentan como «tiene existencias» (``:132-139``, ``:376-406``).
STOCKED_USAGES = (USAGE_INTERNAL, USAGE_TRANSIT)

#: ≙ el identificador externo que la referencia protege (``:200-204``, ``:467-472``).
INTER_COMPANY_XMLID = 'stock.stock_location_inter_company'


class StockLocation(models.DefaultGetMixin, TimeStampedModel):
    """``stock.location`` — el nodo del árbol físico y sus contrapartes virtuales."""

    # Alias de clase de las constantes de módulo. NO son atributos de ORM de la
    # referencia —su `usage` es una Selection con los literales en línea— sino
    # una conveniencia de este árbol, y su contrato ya lo fijaron 26 llamadores
    # que las leen como ``StockLocation.USAGE_INTERNAL``. Se alias, no se
    # duplica el valor: la fuente sigue siendo la constante de módulo.
    USAGE_SUPPLIER = USAGE_SUPPLIER
    USAGE_VIEW = USAGE_VIEW
    USAGE_INTERNAL = USAGE_INTERNAL
    USAGE_CUSTOMER = USAGE_CUSTOMER
    USAGE_INVENTORY = USAGE_INVENTORY
    USAGE_PRODUCTION = USAGE_PRODUCTION
    USAGE_TRANSIT = USAGE_TRANSIT
    USAGE_CHOICES = USAGE_CHOICES
    STOCKED_USAGES = STOCKED_USAGES

    name                      = fields.Char(
        max_length=100,
        help_text='Nombre de la ubicación (Odoo name, requerido).',
    )
    complete_name             = fields.Char(
        max_length=512, blank=True, default='',
        help_text='Nombre jerárquico completo (Odoo complete_name, almacenado).',
    )
    active                    = fields.Boolean(
        default=True,
        help_text='Al desmarcarlo se oculta la ubicación sin borrarla (Odoo active).',
    )
    usage                     = fields.Selection(
        max_length=16, choices=USAGE_CHOICES, default=USAGE_INTERNAL, db_index=True,
        help_text='Tipo de ubicación (Odoo usage, requerido).',
    )
    location                  = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='child_ids', db_index=True,
        help_text='Ubicación padre que la contiene (Odoo location_id).',
    )
    parent_path               = fields.Char(
        max_length=512, blank=True, default='', db_index=True,
        help_text='Ruta materializada «1/4/9/» del árbol (Odoo parent_path).',
    )
    company                   = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='stock_locations', db_index=True,
        help_text='Empresa; vacío si la ubicación es compartida (Odoo company_id).',
    )
    replenish_location        = fields.Boolean(
        default=False,
        help_text='Dispara sugerencias de reabastecimiento (Odoo replenish_location).',
    )
    removal_strategy          = fields.Many2one(
        'stock.ProductRemoval', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='location_ids',
        help_text='Estrategia de retiro por defecto: FIFO, LIFO, cercanía, '
                  'menos paquetes o FEFO (Odoo removal_strategy_id).',
    )
    barcode                   = fields.Char(
        max_length=64, blank=True, default='', null=True,
        help_text='Código de barras de la ubicación (Odoo barcode).',
    )
    cyclic_inventory_frequency = fields.Integer(
        default=0,
        help_text='Días entre conteos cíclicos; 0 desactiva '
                  '(Odoo cyclic_inventory_frequency).',
    )
    last_inventory_date       = fields.Date(
        null=True, blank=True,
        help_text='Fecha del último inventario (Odoo last_inventory_date).',
    )
    next_inventory_date       = fields.Date(
        null=True, blank=True,
        help_text='Próximo conteo planeado (Odoo next_inventory_date, almacenado).',
    )
    warehouse                 = fields.Many2one(
        'stock.StockWarehouse', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='descendant_location_ids',
        help_text='Almacén cuya vista contiene esta ubicación '
                  '(Odoo warehouse_id, almacenado).',
    )
    storage_category          = fields.Many2one(
        'stock.StockStorageCategory', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='location_ids', db_index=True,
        help_text='Categoría de almacenamiento (Odoo storage_category_id).',
    )

    class Meta:
        db_table = 'stock_location'
        # ≙ ``_order = 'complete_name, id'``.
        ordering = ['complete_name', 'id']
        verbose_name = 'Ubicación de inventario'
        verbose_name_plural = 'Ubicaciones de inventario'
        constraints = [
            # ≙ ``_barcode_company_uniq`` (``odoo19c: :92-95``).
            models.UniqueConstraint(
                fields=['barcode', 'company'],
                name='stock_location_barcode_company_uniq',
                violation_error_message='El código de barras de una ubicación '
                                        'debe ser único por empresa.',
            ),
            # ≙ ``_inventory_freq_nonneg`` (``:96-99``).
            models.CheckConstraint(
                condition=models.Q(cyclic_inventory_frequency__gte=0),
                name='stock_location_inventory_freq_nonneg',
                violation_error_message='La frecuencia de inventario (días) no '
                                        'puede ser negativa.',
            ),
        ]
        indexes = [
            # ≙ ``_parent_path_id_idx = models.Index("(parent_path, id)")`` (``:100``).
            models.Index(fields=['parent_path', 'id'],
                         name='stock_location_parent_path_id'),
        ]

    def __str__(self) -> str:
        """≙ ``_compute_display_name`` (``odoo19c: :102-112``).

        Con padre y sin ser vista, el nombre visible es
        ``<ruta del padre>/<nombre>``; en otro caso, el nombre a secas.
        """
        if self.location is not None and self.usage != USAGE_VIEW:
            return f'{self.location.complete_name}/{self.name}'
        return self.name

    # -- defaults --

    @classmethod
    def default_get(cls, field_names, values=None):
        """≙ ``default_get`` (``odoo19c: :22-27``).

        Sin código de barras explícito, el nombre completo hace de código —
        que es lo que la referencia copia de ``complete_name`` a ``barcode``.
        """
        resultado = dict(values or {})
        if ('barcode' in field_names and not resultado.get('barcode')
                and resultado.get('complete_name')):
            resultado['barcode'] = resultado['complete_name']
        return resultado

    # -- los computes almacenados: se recalculan al guardar --

    def compute_complete_name(self):
        """≙ ``_compute_complete_name`` (``odoo19c: :124-130``)."""
        if self.location is not None and self.usage != USAGE_VIEW:
            self.complete_name = f'{self.location.complete_name}/{self.name}'
        else:
            self.complete_name = self.name
        return self.complete_name

    def compute_parent_path(self):
        """Materializa ``parent_path`` — ≙ el ``_parent_store`` de la referencia.

        El formato es el suyo: los ids de los ancestros y el propio, separados
        por ``/`` y con ``/`` final, de modo que ``child_of`` sea un
        ``startswith``.
        """
        if self.pk is None:
            return self.parent_path
        if self.location is not None:
            raiz = self.location.parent_path or self.location.compute_parent_path()
            self.parent_path = f'{raiz}{self.pk}/'
        else:
            self.parent_path = f'{self.pk}/'
        return self.parent_path

    def compute_next_inventory_date(self):
        """≙ ``_compute_next_inventory_date`` (``odoo19c: :141-158``).

        Con frecuencia cíclica puesta y ubicación con existencias, la próxima
        fecha sale de la última más la frecuencia; si ese plazo ya venció, es
        mañana. Sin frecuencia, no hay próxima fecha.
        """
        if not (self.company is not None and self.usage in STOCKED_USAGES
                and self.cyclic_inventory_frequency > 0):
            self.next_inventory_date = None
            return None
        hoy = datetime.date.today()
        try:
            if self.last_inventory_date:
                faltan = self.cyclic_inventory_frequency - (hoy - self.last_inventory_date).days
                if faltan <= 0:
                    self.next_inventory_date = hoy + datetime.timedelta(days=1)
                else:
                    self.next_inventory_date = self.last_inventory_date + datetime.timedelta(
                        days=self.cyclic_inventory_frequency)
            else:
                self.next_inventory_date = hoy + datetime.timedelta(
                    days=self.cyclic_inventory_frequency)
        except OverflowError:
            raise UserError(_(
                'La frecuencia de inventario elegida (días) produce una fecha '
                'demasiado lejana en el futuro.'))
        return self.next_inventory_date

    def compute_warehouse(self):
        """≙ ``_compute_warehouse_id`` (``odoo19c: :160-172``).

        El almacén es aquel cuya ubicación-vista es ancestro de ésta. Con
        varios candidatos gana el **más profundo**, que es lo que la referencia
        obtiene ordenando por ``parent_path`` descendente antes de recorrer.

        ``ancestros`` recorta el último elemento de ``parent_path.split('/')``,
        que es la cadena **vacía** que deja la barra final (``«1/4/9/»`` →
        ``['1','4','9','']``): el ``id`` propio SÍ entra en el conjunto, así
        que una ``view_location`` se resuelve a su propio almacén. Es lo
        mismo que hace la referencia (``odoo19c: :171``), cuyo ``parent_path``
        tiene idéntico formato.
        ``StockWarehouse.save()`` es quien vuelve a llamar a este método
        cuando el cambio que invalida el resultado ocurrió del OTRO lado de
        la relación (el almacén), porque este método sólo se dispara con el
        ``save()`` de esta ubicación.
        """
        StockWarehouse = apps.get_model('stock', 'StockWarehouse')
        self.warehouse = None
        if not self.parent_path:
            return None
        ancestros = {int(x) for x in self.parent_path.split('/')[:-1]}
        candidatos = (StockWarehouse.objects
                      .filter(view_location_id__in=ancestros)
                      .select_related('view_location')
                      .order_by('-view_location__parent_path'))
        for almacen in candidatos:
            self.warehouse = almacen
            break
        return self.warehouse

    def compute_replenish_location(self):
        """≙ ``_compute_replenish_location`` (``odoo19c: :180-183``).

        Sólo una ubicación interna puede pedir reabastecimiento.
        """
        if self.usage != USAGE_INTERNAL:
            self.replenish_location = False
        return self.replenish_location

    # -- los computes no almacenados --

    @property
    def child_internal_location_ids(self):
        """≙ ``child_internal_location_ids`` /
        ``_compute_child_internal_location_ids`` (``:51-57``, ``:174-178``).

        Esta ubicación y todas sus descendientes, filtradas a internas.
        """
        return StockLocation.objects.filter(
            parent_path__startswith=self.parent_path, usage=USAGE_INTERNAL)

    @property
    def is_empty(self):
        """≙ ``is_empty`` / ``_compute_is_empty`` (``:90``, ``:132-139``)."""
        if self.usage not in STOCKED_USAGES:
            return True
        total = self.quant_ids.aggregate(total=Sum('quantity'))['total']
        return (total or 0) <= 0

    @property
    def net_weight(self):
        """≙ ``net_weight`` (``:88``, compute ``:114-122``)."""
        return self.get_weight()[self.pk]['net_weight']

    @property
    def forecast_weight(self):
        """≙ ``forecast_weight`` (``:89``, compute ``:114-122``)."""
        return self.get_weight()[self.pk]['forecast_weight']

    # -- las tres restricciones de Python --

    def check_replenish_location(self):
        """≙ ``_check_replenish_location`` (``odoo19c: :185-192``).

        Dos ubicaciones de la misma rama no pueden pedir reabastecimiento a la
        vez: la sugerencia se duplicaría.
        """
        if not self.replenish_location:
            return
        rama = StockLocation.objects.filter(replenish_location=True).exclude(pk=self.pk)
        conflicto = rama.filter(
            models.Q(location__parent_path__startswith=self.parent_path)
            | models.Q(parent_path__startswith=self.parent_path)
        ).first()
        if conflicto is not None:
            raise ValidationError(_(
                'Ya existe otra ubicación de reabastecimiento padre/hija (%s); '
                'para cambiarla, desmárcala primero.') % conflicto.name)

    def check_scrap_location(self):
        """≙ ``_check_scrap_location`` (``odoo19c: :194-198``).

        Una ubicación no puede ser de chatarra si además es el destino de un
        tipo de operación de fabricación.
        """
        if self.usage != USAGE_INVENTORY:
            return
        StockPickingType = apps.get_model('stock', 'StockPickingType')
        if StockPickingType.objects.filter(
                code='mrp_operation', default_location_dest=self).exists():
            raise ValidationError(_(
                'No se puede marcar una ubicación como de chatarra cuando está '
                'asignada como destino de un tipo de operación de fabricación.'))

    def check_can_delete(self):
        """≙ ``_unlink_except_master_data`` (``odoo19c: :200-204``).

        La ubicación entre-empresas la necesita el módulo de inventario: se
        archiva, no se borra.
        """
        entre_empresas = IrModelData.ref(INTER_COMPANY_XMLID, raise_if_not_found=False)
        if entre_empresas is not None and entre_empresas.pk == self.pk:
            raise ValidationError(_(
                'La ubicación %s la requiere la aplicación de Inventario y no '
                'se puede borrar, pero sí archivar.') % self.name)

    def clean(self):
        """Corre las restricciones de la referencia en el gancho de Django."""
        super().clean()
        self.check_replenish_location()
        self.check_scrap_location()

    # -- búsqueda --

    @classmethod
    def search_is_empty(cls, value=True):
        """≙ ``_search_is_empty`` (``odoo19c: :206-217``).

        Vacía = sin ningún quant con cantidad positiva. Se calcula por el
        complemento, igual que la referencia.
        """
        StockQuant = apps.get_model('stock', 'StockQuant')
        con_stock = (StockQuant.objects
                     .filter(location__usage__in=STOCKED_USAGES)
                     .values('location_id')
                     .annotate(total=Sum('quantity'))
                     .filter(total__gt=0)
                     .values_list('location_id', flat=True))
        if value:
            return cls.objects.exclude(pk__in=con_stock)
        return cls.objects.filter(pk__in=con_stock)

    # -- create / write / unlink / copy --

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :286-290``).

        Tras crear, la referencia invalida ``warehouse_id`` para que se
        recalcule; aquí el recálculo se hace en el acto, que es lo que la
        invalidación produce en la siguiente lectura.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        locations = super().create(vals_list)
        for location in locations:
            location.refresh_computed_fields()
        return locations

    def save(self, *args, **kwargs):
        """Los ``compute … store=True`` se disparan en CADA escritura.

        En la referencia los recalcula el ORM, así que da igual por dónde entre
        el registro. Aquí sólo los disparaba el ``create`` portado, y
        ``objects.create(...)`` —el camino de Django, el que usan los tests y
        buena parte del árbol— dejaba ``complete_name``, ``parent_path`` y
        ``warehouse`` vacíos. Se detectó con ``complete_name == ''`` donde la
        jerarquía decía ``WH/Stock``.

        El recálculo va **después** del ``INSERT`` porque ``parent_path``
        incluye el propio ``id``, y persiste con ``update_fields`` para no
        reescribir el resto. No hay recursión: ``refresh_computed_fields`` llama
        a ``super().save()``, que es el de ``TimeStampedModel``, no éste.
        """
        super().save(*args, **kwargs)
        self.refresh_computed_fields()

    def refresh_computed_fields(self):
        """Recalcula y persiste los cinco campos almacenados de la referencia."""
        self.compute_parent_path()
        self.compute_complete_name()
        self.compute_replenish_location()
        self.compute_next_inventory_date()
        self.compute_warehouse()
        super().save(update_fields=[
            'parent_path', 'complete_name', 'replenish_location',
            'next_inventory_date', 'warehouse',
        ])

    def write(self, **vals):
        """≙ ``write`` (``odoo19c: :219-267``).

        Cinco guardas de la referencia, en su orden:

        1. cambiar de empresa está prohibido — se archiva y se crea otra;
        2. no se convierte en vista una ubicación con productos;
        3. no se convierte una interna que tenga existencias;
        4. no se archiva una ubicación que un almacén usa como vista o stock;
        5. no se archiva una rama cuyas hijas internas tengan existencias — y
           si se puede, el archivado **se propaga** a las hijas.
        """
        StockQuant = apps.get_model('stock', 'StockQuant')
        StockWarehouse = apps.get_model('stock', 'StockWarehouse')

        if 'company' in vals and self.company is not None:
            if getattr(vals['company'], 'pk', vals['company']) != self.company_id:
                raise UserError(_(
                    'Cambiar la empresa de este registro está prohibido en este '
                    'punto; archívalo y crea uno nuevo.'))

        if vals.get('usage') == USAGE_VIEW and self.quant_ids.exists():
            raise UserError(_(
                'El uso de esta ubicación no puede pasar a vista porque '
                'contiene productos.'))

        if 'usage' in vals and vals['usage'] != self.usage:
            if StockQuant.objects.filter(location=self, quantity__gt=0).exists():
                raise UserError(_(
                    'Una ubicación interna con existencias no se puede convertir.'))

        if 'active' in vals and not vals['active']:
            usado = StockWarehouse.objects.filter(
                active=True).filter(
                models.Q(lot_stock=self) | models.Q(view_location=self)).first()
            if usado is not None:
                raise UserError(_(
                    'No se puede archivar la ubicación %(location)s porque la '
                    'usa el almacén %(warehouse)s.') % {
                        'location': self, 'warehouse': usado})

            descendientes = StockLocation.objects.filter(
                parent_path__startswith=self.parent_path).exclude(pk=self.pk)
            internas = descendientes.filter(usage=USAGE_INTERNAL)
            con_stock = StockQuant.objects.filter(
                location__in=internas).filter(
                models.Q(quantity__gt=0) | models.Q(reserved_quantity__gt=0))
            if con_stock.exists():
                nombres = ', '.join(str(q.location) for q in con_stock)
                raise UserError(_(
                    'No se pueden desactivar las ubicaciones %s porque aún '
                    'contienen productos.') % nombres)
            descendientes.update(active=False)

        for clave, valor in vals.items():
            setattr(self, clave, valor)
        self.save()
        self.refresh_computed_fields()
        return self

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: :269-270``) — borra la rama entera."""
        self.check_can_delete()
        return StockLocation.objects.filter(
            parent_path__startswith=self.parent_path).delete()

    @classmethod
    def name_create(cls, name):
        """≙ ``name_create`` (``odoo19c: :272-284``).

        Un nombre con barras crea la hoja bajo el padre que la ruta designa,
        si ese padre ya existe.
        """
        if not name:
            return None
        partes = name.split('/')
        padre = cls.objects.filter(complete_name='/'.join(partes[:-1])).first()
        nueva, = cls.create([{'name': partes[-1], 'location': padre}])
        return nueva.pk, str(nueva)

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :292-298``) — el duplicado lleva «(copia)»."""
        valores = dict(default or {})
        valores.setdefault('name', f'{self.name} (copia)')
        for campo in ('usage', 'location', 'company', 'storage_category',
                      'removal_strategy', 'cyclic_inventory_frequency'):
            valores.setdefault(campo, getattr(self, campo))
        return valores

    # -- estrategia de colocación --

    def _get_putaway_strategy(self, product, quantity=0, package=None,
                              packaging=None, additional_qty=None,
                              products=None, locations=None, exclude_sml_ids=None):
        """≙ ``_get_putaway_strategy`` (``odoo19c: :300-374``).

        Devuelve la ubicación donde colocar el producto según las reglas de
        colocación aplicables, o ``self`` si ninguna aplica.

        El orden de preferencia entre reglas es el de la referencia, y no es
        cosmético: gana la que fija tipo de paquete, luego la que fija
        producto, luego la de la **misma** categoría (no la de un ancestro), y
        por último la que fija cualquier categoría.
        """
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        StockQuant = apps.get_model('stock', 'StockQuant')

        self.check_access_putaway()
        universo = set(products or ())
        universo.add(product)

        tipo_paquete = None
        if package is not None:
            tipo_paquete = package.package_type
        elif packaging is not None:
            tipo_paquete = packaging.package_type

        categorias = []
        categs = {p.categ for p in universo if getattr(p, 'categ', None) is not None}
        categ = next(iter(categs)) if len(categs) == 1 else None
        propia = categ
        while categ is not None:
            categorias.append(categ)
            categ = categ.parent

        reglas = [
            r for r in self.putaway_rule_ids.all()
            if (r.product is None or r.product in universo)
            and (r.category is None or r.category in categorias)
            and (not r.package_type_ids.exists() or tipo_paquete in r.package_type_ids.all())
        ]
        reglas.sort(key=lambda r: (
            r.package_type_ids.exists(),
            r.product is not None,
            r.category is not None and r.category == propia,
            r.category is not None,
        ), reverse=True)

        destinos = locations if locations is not None else self.child_internal_location_ids
        if not reglas:
            return self

        excluidas = set(exclude_sml_ids or ())
        cantidad_por_ubicacion = defaultdict(lambda: 0)
        if destinos.filter(storage_category__isnull=False).exists():
            if package is not None and tipo_paquete is not None:
                lineas = (StockMoveLine.objects
                          .exclude(pk__in=excluidas)
                          .filter(result_package__package_type=tipo_paquete)
                          .exclude(state__in=['draft', 'cancel', 'done'])
                          .values('location_dest_id')
                          .annotate(n=models.Count('result_package', distinct=True)))
                for fila in lineas:
                    cantidad_por_ubicacion[fila['location_dest_id']] += fila['n']
                quants = (StockQuant.objects
                          .filter(package__package_type=tipo_paquete,
                                  location__in=destinos)
                          .values('location_id')
                          .annotate(n=models.Count('package', distinct=True)))
                for fila in quants:
                    cantidad_por_ubicacion[fila['location_id']] += fila['n']
            else:
                quants = (StockQuant.objects
                          .filter(product=product, location__in=destinos)
                          .values('location_id')
                          .annotate(total=Sum('quantity')))
                for fila in quants:
                    cantidad_por_ubicacion[fila['location_id']] += fila['total'] or 0
                lineas = (StockMoveLine.objects
                          .exclude(pk__in=excluidas)
                          .filter(product=product, location_dest__in=destinos)
                          .exclude(state__in=['draft', 'done', 'cancel']))
                for linea in lineas:
                    cantidad_por_ubicacion[linea.location_dest_id] += (
                        linea.quantity_product_uom or 0)

        for ubicacion_id, cantidad in (additional_qty or {}).items():
            cantidad_por_ubicacion[ubicacion_id] += cantidad

        for regla in reglas:
            destino = regla.get_putaway_location(
                product, quantity, package, packaging, cantidad_por_ubicacion)
            if destino is not None:
                return destino

        primera = destinos.first()
        if primera is not None and self.usage == USAGE_VIEW:
            return primera
        return self

    def check_access_putaway(self):
        """≙ ``_check_access_putaway`` (``odoo19c: :412-413``).

        Punto de extensión: la referencia lo deja como identidad y lo
        reescriben los addons que elevan privilegio para leer reglas ajenas.
        """
        return self

    def check_can_be_used(self, product=None, quantity=0, package=None,
                          location_qty=0, products=None, exclude_sml_ids=None):
        """≙ ``_check_can_be_used`` (``odoo19c: :415-461``).

        Decide si el producto o el paquete cabe aquí. Sin categoría de
        almacenamiento no hay límite y siempre cabe; con ella se prueban, en
        este orden: mezcla permitida, peso previsto y capacidad declarada.
        """
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')

        categoria = self.storage_category
        if categoria is None:
            return True

        positivos = [q for q in self.quant_ids.all() if (q.quantity or 0) > 0]

        if categoria.allow_new_product == 'empty' and positivos:
            return False

        if categoria.allow_new_product == 'same':
            universo = set(products or ())
            if product is not None:
                universo.add(product)
            if len(universo) > 1:
                return False
            if positivos and any(q.product not in universo for q in positivos):
                return False
            if product is not None and StockMoveLine.objects.filter(
                    location_dest=self).exclude(
                    product=product).exclude(
                    state__in=('done', 'cancel')).exists():
                return False

        previsto = self.get_weight(exclude_sml_ids)[self.pk]['forecast_weight']

        if package is not None and package.package_type is not None:
            lineas = StockMoveLine.objects.filter(
                result_package=package).exclude(state__in=['done', 'cancel'])
            peso_paquete = sum((l.quantity_product_uom or 0) * (l.product.weight or 0)
                               for l in lineas)
            if categoria.max_weight < previsto + peso_paquete:
                return False
            capacidad = categoria.package_capacity_ids.filter(
                package_type=package.package_type).first()
            if capacidad is not None and location_qty >= capacidad.quantity:
                return False
            return True

        peso_producto = (product.weight or 0) * quantity if product is not None else 0
        if categoria.max_weight < previsto + peso_producto:
            return False
        capacidad = categoria.product_capacity_ids.filter(product=product).first()
        if capacidad is not None:
            if location_qty >= capacidad.quantity:
                return False
            if quantity + location_qty > capacidad.quantity:
                return False
        return True

    # -- utilidades de árbol y peso --

    def get_next_inventory_date(self):
        """≙ ``_get_next_inventory_date`` (``odoo19c: :376-406``).

        La fecha del quant de esta ubicación sale de tres reglas, en orden:
        el ciclo propio; si no, el inventario anual de la empresa; si no,
        ninguna. Con ambos, gana el más próximo.

        **Divergencia — "sin fecha" es ``None``, no ``False``.** La fuente
        devuelve ``False`` en las tres salidas negativas (``:379``, ``:405``):
        en Odoo ``False`` es el nulo universal de todo campo. Aquí el nulo de un
        ``DateField`` es ``None``, y ``False`` no lo es: el consumidor lo
        escribe tal cual y Django revienta al preparar el valor
        (``parse_date(False)`` → ``TypeError: fromisoformat: argument must be
        str``), que es como se detectó — ``StockQuant._compute_inventory_date``
        asignándolo a ``inventory_date``. Se traduce **en el productor** para
        que ningún consumidor tenga que acordarse.
        """
        if self.usage not in STOCKED_USAGES:
            return None
        date_company = None
        empresa = self.company
        mes = getattr(empresa, 'annual_inventory_month', None) if empresa else None
        if mes:
            hoy = datetime.date.today()
            mes = int(mes)
            dia = max(getattr(empresa, 'annual_inventory_day', 1) or 1, 1)
            dia = min(dia, calendar.monthrange(hoy.year, mes)[1])
            date_company = hoy.replace(month=mes, day=dia)
            if date_company <= hoy:
                dia = min(dia, calendar.monthrange(hoy.year + 1, mes)[1])
                date_company = date_company.replace(day=dia, year=hoy.year + 1)
        if self.next_inventory_date:
            if date_company:
                return min(self.next_inventory_date, date_company)
            return self.next_inventory_date
        return date_company

    def should_bypass_reservation(self) -> bool:
        """≙ ``should_bypass_reservation`` (``odoo19c: :408-410``).

        Una ubicación no interna no reserva: su existencia no es física.
        """
        return self.usage in BYPASS_RESERVATION_USAGES

    def child_of(self, other_location) -> bool:
        """≙ ``_child_of`` (``odoo19c: :463-465``).

        Es un ``startswith`` sobre la ruta materializada — por eso
        ``parent_path`` se mantiene aunque este ORM no traiga ``_parent_store``.
        """
        if not self.parent_path or other_location is None:
            return False
        return self.parent_path.startswith(other_location.parent_path)

    def child_of_domain(self, field_path='location'):
        """≙ el **operador de dominio** ``child_of``, no el predicado ``_child_of``.

        Son dos cosas distintas y confundirlas costó cuatro tests: ``_child_of``
        (arriba) responde *sí/no* sobre **una** ubicación; ``('location_id',
        'child_of', id)`` selecciona **todas** las descendientes, y en la
        referencia lo implementa el ORM, no el modelo
        (``odoo19c: odoo/orm/domains.py:1780-1791``): para un modelo
        ``_parent_store`` se reduce a ``parent_path =like <ruta>%``.

        Aquí no hay motor de dominios que lo provea, así que el mecanismo vive
        en el modelo que lo tiene —el que mantiene ``parent_path``— en vez de
        repetirse en cada consumidor, que es como nació el defecto: ``stock_quant``
        llamaba a ``location.child_of()`` esperando un conjunto y recibía la
        firma del predicado.

        :param field_path: prefijo del lookup desde el modelo que consulta
            (``'location'`` para ``StockQuant``, que declara ese FK).
        :return: un ``Q`` con el mismo alcance que el ``=like`` de la fuente.
        """
        return Q(**{f'{field_path}__parent_path__startswith': self.parent_path or ''})

    def is_outgoing(self) -> bool:
        """≙ ``_is_outgoing`` (``odoo19c: :467-472``).

        Sale del sistema si es de cliente, o si cuelga de la ubicación de
        tránsito entre empresas.
        """
        if self.usage == USAGE_CUSTOMER:
            return True
        entre_empresas = IrModelData.ref(INTER_COMPANY_XMLID, raise_if_not_found=False)
        return self.child_of(entre_empresas) if entre_empresas is not None else False

    def get_weight(self, excluded_sml_ids=None):
        """≙ ``_get_weight`` (``odoo19c: :474-513``).

        Peso neto (lo que hay) y previsto (lo que habrá tras las salidas y
        entradas pendientes), por ubicación. Devuelve el mismo diccionario
        anidado que la referencia, indexado por pk.
        """
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        StockQuant = apps.get_model('stock', 'StockQuant')

        excluidas = set(excluded_sml_ids or ())
        resultado = defaultdict(lambda: defaultdict(float))

        quants = (StockQuant.objects
                  .filter(location=self)
                  .values('location_id', 'product_id')
                  .annotate(total=Sum('quantity')))
        pendientes = (StockMoveLine.objects
                      .exclude(state__in=['draft', 'done', 'cancel'])
                      .exclude(pk__in=excluidas))
        salidas = (pendientes.filter(location=self)
                   .values('location_id', 'product_id')
                   .annotate(total=Sum('quantity_product_uom')))
        entradas = (pendientes.filter(location_dest=self)
                    .values('location_dest_id', 'product_id')
                    .annotate(total=Sum('quantity_product_uom')))

        pesos = self._weights_by_product(
            {f['product_id'] for f in list(quants) + list(salidas) + list(entradas)})

        for fila in quants:
            peso = float(fila['total'] or 0) * pesos.get(fila['product_id'], 0.0)
            resultado[fila['location_id']]['net_weight'] += peso
            resultado[fila['location_id']]['forecast_weight'] += peso
        for fila in salidas:
            resultado[fila['location_id']]['forecast_weight'] -= (
                float(fila['total'] or 0) * pesos.get(fila['product_id'], 0.0))
        for fila in entradas:
            resultado[fila['location_dest_id']]['forecast_weight'] += (
                float(fila['total'] or 0) * pesos.get(fila['product_id'], 0.0))

        # ≙ el ``defaultdict`` de la referencia: una ubicación sin filas pesa 0.
        resultado[self.pk]
        return resultado

    @staticmethod
    def _weights_by_product(product_ids):
        """El ``products.fetch(['weight'])`` de la referencia, en una consulta."""
        if not product_ids:
            return {}
        return {
            fila['pk']: float(fila['weight'] or 0)
            for fila in ProductProduct.objects.filter(
                pk__in=product_ids).values('pk', 'weight')
        }


class StockRoute(TimeStampedModel):
    """``stock.route`` — el camino declarado que sigue un producto."""

    name                      = fields.Char(
        max_length=120,
        help_text='Nombre de la ruta (Odoo name, requerido, traducible).',
    )
    active                    = fields.Boolean(
        default=True,
        help_text='Al desmarcarlo se oculta la ruta sin borrarla (Odoo active).',
    )
    sequence                  = fields.Integer(
        default=0, help_text='Orden de evaluación (Odoo sequence).',
    )
    product_selectable        = fields.Boolean(
        default=True,
        help_text='Seleccionable en la pestaña Inventario del producto '
                  '(Odoo product_selectable).',
    )
    product_categ_selectable  = fields.Boolean(
        default=False,
        help_text='Seleccionable en la categoría de producto '
                  '(Odoo product_categ_selectable).',
    )
    warehouse_selectable      = fields.Boolean(
        default=False,
        help_text='Seleccionable en el almacén; al elegirlo, es la ruta por '
                  'defecto de lo que pase por él (Odoo warehouse_selectable).',
    )
    package_type_selectable   = fields.Boolean(
        default=False,
        help_text='Seleccionable en el tipo de paquete '
                  '(Odoo package_type_selectable).',
    )
    supplied_wh               = fields.Many2one(
        'stock.StockWarehouse', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='supplied_route_ids', db_index=True,
        help_text='Almacén abastecido (Odoo supplied_wh_id).',
    )
    supplier_wh               = fields.Many2one(
        'stock.StockWarehouse', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='supplier_route_ids',
        help_text='Almacén que abastece (Odoo supplier_wh_id).',
    )
    company                   = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='stock_routes', db_index=True,
        help_text='Empresa; vacío si la ruta es compartida (Odoo company_id).',
    )
    product_ids               = fields.Many2many(
        'product.ProductTemplate', blank=True, related_name='route_ids',
        db_table='stock_route_product',
        help_text='Productos que declaran esta ruta (Odoo product_ids).',
    )
    categ_ids                 = fields.Many2many(
        'product.ProductCategory', blank=True, related_name='route_ids',
        db_table='stock_route_categ',
        help_text='Categorías que declaran esta ruta (Odoo categ_ids).',
    )
    warehouse_ids             = fields.Many2many(
        'stock.StockWarehouse', blank=True, related_name='route_ids',
        db_table='stock_route_warehouse',
        help_text='Almacenes que declaran esta ruta (Odoo warehouse_ids).',
    )

    class Meta:
        db_table = 'stock_route'
        ordering = ['sequence']            # ≙ ``_order = 'sequence'``
        verbose_name = 'Ruta de inventario'
        verbose_name_plural = 'Rutas de inventario'

    def __str__(self) -> str:
        return self.name

    @property
    def warehouse_domain_ids(self):
        """≙ ``warehouse_domain_ids`` (``:539``, compute ``:552-556``).

        Los almacenes elegibles: los de la empresa de la ruta, o todos si la
        ruta es compartida.
        """
        StockWarehouse = apps.get_model('stock', 'StockWarehouse')
        if self.company is not None:
            return StockWarehouse.objects.filter(company=self.company)
        return StockWarehouse.objects.all()

    def apply_company_filter(self):
        """≙ ``_onchange_company`` (``odoo19c: :558-561``).

        Al fijar empresa, los almacenes de otra empresa dejan de aplicar.
        """
        if self.company is None:
            return
        self.warehouse_ids.set(self.warehouse_ids.filter(company=self.company))

    def apply_warehouse_selectable(self):
        """≙ ``_onchange_warehouse_selectable`` (``odoo19c: :563-566``).

        Si la ruta deja de ser seleccionable por almacén, se vacía la lista —
        ``[(5, 0, 0)]`` en el idioma de comandos de la referencia.
        """
        if not self.warehouse_selectable:
            self.warehouse_ids.clear()

    def write(self, **vals):
        """≙ ``write`` (``odoo19c: :568-575``).

        Archivar la ruta archiva sus reglas, y desarchivarla las devuelve —
        pero sólo las que apuntan a una ubicación destino viva, que es la
        condición que la referencia filtra antes de propagar.
        """
        if 'active' in vals:
            reglas = self.rule_ids.filter(location_dest__active=True)
            reglas.update(active=bool(vals['active']))
        for clave, valor in vals.items():
            setattr(self, clave, valor)
        self.save()
        return self

    def check_company_consistency(self):
        """≙ ``_check_company_consistency`` (``odoo19c: :577-590``).

        Una regla de otra empresa dentro de la ruta rompe el aislamiento.
        """
        if self.company is None:
            return
        for regla in self.rule_ids.all():
            if regla.company_id != self.company_id:
                raise ValidationError(_(
                    'La regla %(rule)s pertenece a %(rule_company)s mientras '
                    'que la ruta pertenece a %(route_company)s.') % {
                        'rule': regla, 'rule_company': regla.company,
                        'route_company': self.company})

    def clean(self):
        """Corre el ``@api.constrains`` de la referencia en el gancho de Django."""
        super().clean()
        self.check_company_consistency()

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :544-550``) — el duplicado lleva «(copia)»."""
        valores = dict(default or {})
        valores.setdefault('name', f'{self.name} (copia)')
        for campo in ('sequence', 'product_selectable', 'product_categ_selectable',
                      'warehouse_selectable', 'package_type_selectable', 'company'):
            valores.setdefault(campo, getattr(self, campo))
        return valores

    def _is_valid_resupply_route_for_product(self, product) -> bool:
        """≙ ``_is_valid_resupply_route_for_product`` (``odoo19c: :592-593``).

        Punto de extensión: la referencia devuelve ``False`` y lo reescriben
        los addons de reabastecimiento entre almacenes.
        """
        return False
