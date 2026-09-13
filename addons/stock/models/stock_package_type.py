"""``stock.package.type`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_package_type.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Qué es: el **tipo de paquete** describe el contenedor físico —caja, tarima,
tote— con sus dimensiones, su peso base y su tope. Es lo que permite calcular
el peso de un envío, decidir si un paquete cabe en una ubicación (vía
``stock.storage.category.capacity``) y numerar los paquetes con una secuencia
propia.

Porte símbolo por símbolo — 20 de 20
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_package_type.py``
(131 líneas): 1 clase, 17 campos, 5 restricciones y 9 métodos.

===========================================  ==========================================
Símbolo de la referencia (línea)             Aquí
===========================================  ==========================================
``_get_default_length_uom`` (12-13)          ``get_default_length_uom`` (classmethod)
``_get_default_weight_uom`` (15-16)          ``get_default_weight_uom`` (classmethod)
``name`` (18)                                ``name``
``sequence`` (19)                            ``sequence``
``sequence_id`` (20)                         ``sequence``→ FK ``sequence_ref``
``sequence_code`` (21)                       property + setter ``sequence_code``
``height`` (22)                              ``height``
``width`` (23)                               ``width``
``packaging_length`` (24)                    ``packaging_length``
``base_weight`` (25)                         ``base_weight``
``max_weight`` (26)                          ``max_weight``
``barcode`` (27)                             ``barcode``
``weight_uom_name`` (28)                     property ``weight_uom_name``
``length_uom_name`` (29)                     property ``length_uom_name``
``company_id`` (30)                          ``company``
``package_use`` (31-36)                      ``package_use``
``has_quants`` (37)                          property ``has_quants``
``storage_category_capacity_ids`` (38)       reverso homónimo de la capacidad
``route_ids`` (39)                           ``route_ids`` (M2M)
``_barcode_uniq`` (41-44)                    ``UniqueConstraint`` homónimo
``_positive_height`` (45-48)                 ``CheckConstraint`` homónimo
``_positive_width`` (49-52)                  ``CheckConstraint`` homónimo
``_positive_length`` (53-56)                 ``CheckConstraint`` homónimo
``_positive_max_weight`` (57-60)             ``CheckConstraint`` homónimo
``_compute_display_name`` (62-72)            ``__str__``
``_compute_has_quants`` (74-79)              property ``has_quants``
``_compute_length_uom_name`` (81-83)         property ``length_uom_name``
``_compute_weight_uom_name`` (85-87)         property ``weight_uom_name``
``copy_data`` (89-91)                        ``copy_data``
``create`` (93-103)                          ``create`` (classmethod)
``write`` (105-127)                          ``write``
``_get_next_name_by_sequence`` (129-131)     ``_get_next_name_by_sequence``
===========================================  ==========================================

Divergencias declaradas
=========================

1. **El FK a la secuencia se llama ``sequence_ref``, no ``sequence``.** La
   referencia tiene ``sequence`` (entero de orden) y ``sequence_id`` (FK a
   ``ir.sequence``) como dos campos distintos; el sufijo ``_id`` es su idioma
   para el FK y este árbol lo retira (``picking_id`` → ``picking``). Retirarlo
   aquí colisionaría con el entero, así que el FK toma ``sequence_ref``. Es la
   misma resolución que el árbol ya aplica cuando el nombre corto está tomado.
2. **``sequence_code`` es property + setter, no ``related`` escribible.** La
   referencia lo declara ``related="sequence_id.code", readonly=False``; este
   ORM no cablea el ``related`` escribible sobre un descriptor (tarea
   **#191**), así que el par lectura/escritura se declara explícito. La
   escritura conserva la semántica: crea la secuencia si no existe.
3. **Las cuatro magnitudes son ``Monetary``, no ``Float``.** El árbol usa
   ``DecimalField`` para toda magnitud con redondeo declarado.
4. **``_compute_display_name`` → ``__str__``, no property ``display_name``**
   (:ref:`h-api-680`). ``check_porte_completo.py`` sólo absuelve un
   ``_compute_<campo>`` cuando existe una ``property`` **con el mismo nombre**
   que el campo — ``display_name`` en este puerto es el método especial
   ``__str__`` (:193), no un descriptor con ese nombre exacto, así que el
   gate no lo ve y lo reporta ausente. El cuerpo es el mismo: con las tres
   dimensiones puestas, sufijo ``\t--largo x ancho x alto--``; sin ellas, el
   nombre a secas. La única rama que la referencia no reproduce es
   ``formatted_display_name`` del contexto del cliente web (no hay contexto
   de petición en un método de modelo aquí) — la misma decisión que
   ``stock_package.py::StockPackage._compute_display_name`` declara.
"""
from decimal import Decimal

import fields
import api
import models

from addons.base.models import TimeStampedModel
from addons.base.models.ir_sequence import IrSequence
from addons.product.models.product_template import ProductTemplate

PACKAGE_USE_DISPOSABLE = 'disposable'
PACKAGE_USE_REUSABLE = 'reusable'

PACKAGE_USE_CHOICES = [
    (PACKAGE_USE_DISPOSABLE, 'Caja desechable'),
    (PACKAGE_USE_REUSABLE, 'Caja reutilizable (tote)'),
]

#: ≙ el ``padding=7`` que la referencia fija al crear la secuencia
#: (``odoo19c: :98``, ``:118``).
SEQUENCE_PADDING = 7


class StockPackageType(models.DefaultGetMixin, TimeStampedModel):
    """``stock.package.type`` — el contenedor físico y sus límites."""

    # Atributos de clase de modelo — los tres que la referencia declara
    # (``odoo19c: stock/models/stock_package_type.py:8-10``), verbatim
    # (:ref:`h-api-680`).
    _name = 'stock.package.type'
    _description = 'Stock package type'
    _order = 'sequence, id'

    name                = fields.Char(
        max_length=120,
        help_text='Nombre del tipo de paquete (Odoo name, requerido).',
    )
    sequence            = fields.Integer(
        default=1,
        help_text='Orden; el primero es el tipo por defecto (Odoo sequence).',
    )
    sequence_ref        = fields.Many2one(
        'base.IrSequence', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='package_types',
        help_text='Secuencia de numeración de los paquetes de este tipo '
                  '(Odoo sequence_id).',
    )
    height              = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Alto del embalaje (Odoo height).',
    )
    width               = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Ancho del embalaje (Odoo width).',
    )
    packaging_length    = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Largo del embalaje (Odoo packaging_length).',
    )
    base_weight         = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Peso del propio embalaje vacío (Odoo base_weight).',
    )
    max_weight          = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Peso máximo embarcable en este embalaje (Odoo max_weight).',
    )
    barcode             = fields.Char(
        max_length=64, blank=True, default='', null=True,
        help_text='Código de barras del tipo de paquete (Odoo barcode).',
    )
    company             = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='package_types', db_index=True,
        help_text='Empresa (Odoo company_id).',
    )
    package_use         = fields.Selection(
        max_length=12, choices=PACKAGE_USE_CHOICES, default=PACKAGE_USE_DISPOSABLE,
        help_text='Las cajas reutilizables se usan en preparación por lotes y '
                  'se vacían después; al escanear una desechable, sus productos '
                  'se añaden a la transferencia (Odoo package_use).',
    )
    route_ids           = fields.Many2many(
        'stock.StockRoute', blank=True, related_name='package_type_ids',
        help_text='Rutas aplicables a este tipo de paquete (Odoo route_ids).',
    )

    class Meta:
        db_table = 'stock_package_type'
        ordering = ['sequence', 'id']      # ≙ ``_order = "sequence, id"``
        verbose_name = 'Tipo de paquete'
        verbose_name_plural = 'Tipos de paquete'
        constraints = [
            # ≙ ``_barcode_uniq`` (``odoo19c: :41-44``). ``nulls_distinct`` no
            # hace falta: PostgreSQL ya trata cada NULL como distinto, que es
            # lo que la referencia obtiene con su ``unique(barcode)``.
            models.UniqueConstraint(
                fields=['barcode'],
                name='stock_package_type_barcode_uniq',
                violation_error_message='Un código de barras sólo puede '
                                        'asignarse a un tipo de paquete.',
            ),
            # ≙ ``_positive_height`` (``:45-48``).
            models.CheckConstraint(
                condition=models.Q(height__gte=0),
                name='stock_package_type_positive_height',
                violation_error_message='El alto debe ser positivo.',
            ),
            # ≙ ``_positive_width`` (``:49-52``).
            models.CheckConstraint(
                condition=models.Q(width__gte=0),
                name='stock_package_type_positive_width',
                violation_error_message='El ancho debe ser positivo.',
            ),
            # ≙ ``_positive_length`` (``:53-56``).
            models.CheckConstraint(
                condition=models.Q(packaging_length__gte=0),
                name='stock_package_type_positive_length',
                violation_error_message='El largo debe ser positivo.',
            ),
            # ≙ ``_positive_max_weight`` (``:57-60``).
            models.CheckConstraint(
                condition=models.Q(max_weight__gte=0),
                name='stock_package_type_positive_max_weight',
                violation_error_message='El peso máximo debe ser positivo.',
            ),
        ]

    def __str__(self) -> str:
        """≙ ``_compute_display_name`` (``odoo19c: :62-72``).

        Con las tres dimensiones puestas, la referencia añade el formato
        ``nombre\t--largo x ancho x alto--``; sin ellas, cae al nombre. El
        ``formatted_display_name`` del contexto es una decisión de la vista
        del cliente Odoo, que este stack no tiene: aquí el formato largo se
        emite siempre que haya dimensiones, que es la mitad observable.
        """
        if self.packaging_length and self.width and self.height:
            return (f'{self.name}\t--{self.packaging_length} x '
                    f'{self.width} x {self.height}--')
        return self.name

    # -- los dos defaults de unidad --

    @classmethod
    def get_default_length_uom(cls):
        """≙ ``_get_default_length_uom`` (``odoo19c: :12-13``)."""
        return ProductTemplate.get_length_uom_name_from_ir_config_parameter()

    @classmethod
    def get_default_weight_uom(cls):
        """≙ ``_get_default_weight_uom`` (``odoo19c: :15-16``)."""
        return ProductTemplate.get_weight_uom_name_from_ir_config_parameter()

    # -- los tres compute --

    @property
    def weight_uom_name(self):
        """≙ ``weight_uom_name`` / ``_compute_weight_uom_name`` (``:28``, ``:85-87``)."""
        return self.get_default_weight_uom()

    @property
    def length_uom_name(self):
        """≙ ``length_uom_name`` / ``_compute_length_uom_name`` (``:29``, ``:81-83``)."""
        return self.get_default_length_uom()

    @property
    def has_quants(self):
        """≙ ``has_quants`` / ``_compute_has_quants`` (``:37``, ``:74-79``).

        ``True`` si algún paquete de este tipo tiene existencias dentro. La
        referencia lo resuelve con un ``_read_group`` agrupado por tipo porque
        computa el lote entero de una vez; aquí la property responde por
        instancia con la misma pregunta.
        """
        return self.package_ids.filter(quant_ids__isnull=False).exists()

    # -- el par lectura/escritura del código de secuencia --

    @property
    def sequence_code(self):
        """≙ ``sequence_code`` (``related="sequence_id.code"``, ``:21``)."""
        return self.sequence_ref.code if self.sequence_ref is not None else ''

    @sequence_code.setter
    def sequence_code(self, value):
        """El lado escribible del ``related`` (``readonly=False``).

        Reproduce lo que ``write`` hace con la clave (``:105-127``): si no hay
        secuencia, la crea; si la hay, le reescribe nombre y prefijo.
        """
        self.apply_sequence_code(value)

    def apply_sequence_code(self, code, company=None):
        """Crea o reescribe la secuencia asociada — cuerpo común de ``write``.

        ``odoo19c: :105-127`` hace exactamente esto: arma ``seq_vals`` con
        nombre y prefijo, y según haya o no ``sequence_id`` crea la secuencia
        (con ``padding=7``) o reescribe la existente.
        """
        valores = {
            'name': f'Secuencia de tipo de paquete {code}',
            'prefix': code,
        }
        empresa = company if company is not None else self.company
        if self.sequence_ref is None:
            self.sequence_ref = IrSequence.objects.create(
                padding=SEQUENCE_PADDING, company=empresa, **valores)
        else:
            for clave, valor in valores.items():
                setattr(self.sequence_ref, clave, valor)
            if company is not None:
                self.sequence_ref.company = company
            self.sequence_ref.save()

    # -- create / write / copy --

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :93-103``).

        Si llega ``sequence_code`` sin ``sequence_ref``, la secuencia se crea
        antes del registro — dentro del bucle sobre ``vals_list``, como la
        referencia, que deja su id en ``vals['sequence_id']``.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        for vals in vals_list:
            code = vals.pop('sequence_code', None)
            if code and not vals.get('sequence_ref'):
                vals['sequence_ref'] = IrSequence.objects.create(
                    name=f'Secuencia de tipo de paquete {code}',
                    prefix=code,
                    padding=SEQUENCE_PADDING,
                    company=vals.get('company'),
                )
        return super().create(vals_list)

    def write(self, **vals):
        """≙ ``write`` (``odoo19c: :105-127``).

        Cambiar ``sequence_code`` o ``company`` propaga a la secuencia: la
        referencia arma ``seq_vals`` con lo que cambió y lo aplica creando o
        reescribiendo. Aquí es el mismo orden — primero la secuencia, luego el
        propio registro.
        """
        code = vals.pop('sequence_code', None)
        company = vals.get('company')
        if code is not None:
            self.apply_sequence_code(code, company=company)
        elif company is not None and self.sequence_ref is not None:
            self.sequence_ref.company = company
            self.sequence_ref.save(update_fields=['company'])
        for clave, valor in vals.items():
            setattr(self, clave, valor)
        self.save()
        return self

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :89-91``) — el duplicado lleva «(copia)»."""
        valores = dict(default or {})
        valores.setdefault('name', f'{self.name} (copia)')
        for campo in ('sequence', 'height', 'width', 'packaging_length',
                      'base_weight', 'max_weight', 'package_use', 'company'):
            valores.setdefault(campo, getattr(self, campo))
        return valores

    def _get_next_name_by_sequence(self):
        """≙ ``_get_next_name_by_sequence`` (``odoo19c: :129-131``).

        Con secuencia propia, el siguiente nombre sale de ella; sin ella, del
        código global ``stock.package``.

        **Dos correcciones en el mismo pase** (ver :ref:`h-api-619`):

        1. El cuerpo llamaba ``self.sequence_ref.next_by_id()``, y ese método
           **no existe en ningún punto del árbol** — medido:
           ``grep -rn "def next_by_id" addons/ src/`` → 0. El equivalente
           nuestro de ``_next()``/``next_by_id()`` es ``next_by_id()``
           (``src/addons/base/models/ir_sequence.py:94``), y lo dice el propio
           docstring de ``account_check_printing/models/ir_sequence.py:17``.
           Fallaba con ``AttributeError`` en tiempo de EJECUCIÓN, no de import,
           así que ni el gate de porte ni la suite lo veían.
        2. El nombre había perdido su guion bajo, que en la fuente es el
           contrato (``porte-completo-no-parcial.md``, H-API-581). Se restaura
           aquí porque este pase toca el archivo.
        """
        if self.sequence_ref is not None:
            return self.sequence_ref.next_by_id()
        return IrSequence.next_by_code('stock.package')
