r"""``product.removal`` y ``stock.putaway.rule`` — addon ``stock``.

Adaptación de Odoo ``stock/models/product_strategy.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué son las dos, y por qué van juntas: la **estrategia de retiro** decide de
qué lote se saca (FIFO, LIFO, FEFO…) y la **regla de colocación** decide dónde
se guarda lo que entra. Son las dos mitades de la misma pregunta —qué unidad
concreta se toca— y por eso la referencia las declara en el mismo archivo.

Porte símbolo por símbolo — 2 clases, 22 símbolos
==================================================

Medido sobre ``odoo19c: addons/stock/models/product_strategy.py`` (183 líneas):
``ProductRemoval`` con 2 campos; ``StockPutawayRule`` con 10 campos y 10 métodos.

``ProductRemoval`` — 2 de 2
-----------------------------

``name`` (12) y ``method`` (13), ambos requeridos y traducibles.

``StockPutawayRule`` — 20 de 20
---------------------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``_default_category_id`` (22-24)                 ``_default_category_id`` (classmethod)
``_default_location_id`` (26-32)                 ``_default_location_id`` (classmethod)
``_default_product_id`` (34-40)                  ``_default_product_id`` (classmethod)
``product_id`` (42-48)                           ``product``
``category_id`` (49-50)                          ``category``
``location_in_id`` (51-55)                       ``location_in``
``location_out_id`` (56-59)                      ``location_out``
``sequence`` (60)                                ``sequence``
``company_id`` (61-63)                           ``company``
``package_type_ids`` (64)                        ``package_type_ids`` (M2M)
``storage_category_id`` (65-68)                  ``storage_category``
``active`` (69)                                  ``active``
``sublocation`` (70-74)                          ``sublocation``
``_compute_storage_category`` (76-80)            ``compute_storage_category``
``_onchange_sublocation`` (82-94)                ``_onchange_sublocation``
``_onchange_location_in`` (96-100)               ``_onchange_location_in``
``create`` (102-105)                             ``create`` (classmethod)
``write`` (107-112)                              ``write``
``_get_last_used_search_domain`` (114-124)       ``get_last_used_search_domain``
``_get_last_used_location`` (126-132)            ``get_last_used_location``
``_get_putaway_location`` (134-183)              ``get_putaway_location``
===============================================  ======================================

Divergencias declaradas
=========================

1. **Los tres ``_default_*`` reciben el contexto por parámetro.** La
   referencia los lee de ``self.env.context`` (``active_model``/``active_id``),
   que es lo que su cliente web pone al abrir el formulario desde un producto,
   una categoría o una ubicación. Este stack no tiene ese contexto implícito,
   así que la misma decisión se toma con los dos valores explícitos. El cuerpo
   —qué default corresponde a qué modelo activo— es idéntico. **No se cablean
   como** ``default=`` **de sus campos** (la referencia sí lo hace en
   ``product_id``/``category_id``/``location_in_id``): al recibir el contexto
   por parámetro en vez de leerlo de ``self.env``, no encajan en la firma sin
   argumentos que Django exige para un ``default=`` — quien cree el registro
   los invoca explícitamente con el ``active_model``/``active_id`` que tenga.
   Divergencia declarada, no omisión: :ref:`h-api-680`.
2. **``_onchange_sublocation`` devuelve el aviso, no lo muestra.** La
   referencia retorna un diccionario ``{'warning': …}`` que su cliente
   renderiza. Aquí devuelve el mensaje o ``None``; quien lo llame decide cómo
   presentarlo. La regla —avisar cuando la categoría elegida no existe bajo la
   ubicación destino— se conserva entera.
3. **``get_putaway_location`` es de instancia y de conjunto.** La referencia
   itera ``self`` porque su ``self`` es un recordset; aquí el método vive en el
   manager (``StockPutawayRule.objects``) y también en la instancia, para que
   ``StockLocation._get_putaway_strategy`` pueda llamarlo regla por regla como
   ya hace.

Guion bajo restaurado (2026-08-18, :ref:`h-api-680`)
------------------------------------------------------

Los cinco métodos privados de la referencia
(``_default_category_id``/``_default_location_id``/``_default_product_id``/
``_onchange_sublocation``/``_onchange_location_in``) habían perdido su guion
bajo en el puerto (``default_category``, ``default_location_in``,
``default_product``, ``check_sublocation_category``, ``apply_location_in``) —
el defecto exacto que ``porte-completo-no-parcial.md`` (H-API-581) prohíbe:
quitar el guion bajo promueve el símbolo a API pública. Medido antes de
corregir: **0** referencias a los cinco nombres fuera de este archivo
(``grep -rn`` sobre ``addons/`` y ``tests/``), así que el rename no rompe
ningún llamador. Restaurados verbatim.

**Bug de llamada descubierto al escribir el test de** ``_default_location_id``
**(mismo patrón que H-API-619 en** ``stock_package_type.py``\ **).** El cuerpo
llamaba ``almacen.get_input_output_locations(...)``; el método real de
``StockWarehouse`` es ``_get_input_output_locations`` (privado — verificado
con ``grep -n "def _get_input_output_locations" addons/stock/models/
stock_warehouse.py`` → ``:1301``). ``get_input_output_locations`` sin guion
bajo **no existe en ningún punto del árbol** — fallaba con ``AttributeError``
en tiempo de EJECUCIÓN, sólo alcanzable con ``multi_warehouse=False``, rama
que ningún test previo ejercitaba. Corregido en el mismo pase.
"""
import fields
import api
import models
from django.apps import apps

from addons.base.models import TimeStampedModel
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate
from exceptions import UserError
from tools.translate import _

SUBLOCATION_NO = 'no'
SUBLOCATION_LAST_USED = 'last_used'
SUBLOCATION_CLOSEST = 'closest_location'

SUBLOCATION_CHOICES = [
    (SUBLOCATION_NO, 'No'),
    (SUBLOCATION_LAST_USED, 'Última usada'),
    (SUBLOCATION_CLOSEST, 'Ubicación más cercana'),
]


class ProductRemoval(TimeStampedModel):
    """``product.removal`` — la estrategia que decide de qué lote se saca.

    Primer modelo del árbol con ``_name`` y ``_description`` declarados
    (directiva del ejecutor 2026-08-14). La cabecera se lee ahora contra la de
    ``odoo19c: stock/models/product_strategy.py:8-13`` sin traducir nada:

    .. code-block:: python

       class ProductRemoval(models.Model):
           _name = 'product.removal'
           _description = 'Removal Strategy'

           name = fields.Char('Name', required=True, translate=True)
           method = fields.Char("Method", required=True, translate=True,
                                help="FIFO, LIFO...")

    ``_description`` conserva la cadena **inglesa** de la fuente —es el origen
    de traducción allá— y no sustituye a ``Meta.verbose_name``, que es la
    etiqueta ya en español que este árbol muestra. Ver
    ``orm/model_naming.py``.
    """

    _name = 'product.removal'
    _description = 'Removal Strategy'

    name   = fields.Char(
        'Name', max_length=120, required=True, translate=True,
        help='Nombre de la estrategia (Odoo name).',
    )
    method = fields.Char(
        'Method', max_length=32, required=True, translate=True,
        help='FIFO, LIFO... — aquí además FEFO, closest y least_packages '
             '(Odoo method).',
    )

    class Meta:
        db_table = 'product_removal'
        ordering = ['name']
        verbose_name = 'Estrategia de retiro'
        verbose_name_plural = 'Estrategias de retiro'

    def __str__(self) -> str:
        return self.name


class StockPutawayRule(models.DefaultGetMixin, TimeStampedModel):
    """``stock.putaway.rule`` — dónde se guarda lo que entra."""

    # Atributos de clase de modelo — los cuatro que la referencia declara
    # (``odoo19c: stock/models/product_strategy.py:17-20``), verbatim.
    _name = 'stock.putaway.rule'
    _order = 'sequence,product_id'
    _description = 'Putaway Rule'
    _check_company_auto = True

    product            = fields.Many2one(
        'product.ProductProduct', null=True, blank=True, on_delete=models.CASCADE,
        related_name='putaway_rule_ids', db_index=True,
        help_text='Producto al que aplica la regla (Odoo product_id).',
    )
    category           = fields.Many2one(
        'product.ProductCategory', null=True, blank=True, on_delete=models.CASCADE,
        related_name='putaway_rule_ids', db_index=True,
        help_text='Categoría de producto a la que aplica (Odoo category_id).',
    )
    location_in        = fields.Many2one(
        'stock.StockLocation', on_delete=models.CASCADE,
        related_name='putaway_rule_ids', db_index=True,
        help_text='Ubicación donde llega el producto '
                  '(Odoo location_in_id, requerido).',
    )
    location_out       = fields.Many2one(
        'stock.StockLocation', on_delete=models.CASCADE,
        related_name='putaway_destination_ids',
        help_text='Sububicación donde se almacena '
                  '(Odoo location_out_id, requerido).',
    )
    sequence           = fields.Integer(
        default=0,
        help_text='Prioridad; mayor para la categoría más específica '
                  '(Odoo sequence).',
    )
    company            = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        related_name='putaway_rules', db_index=True,
        help_text='Empresa (Odoo company_id, requerido).',
    )
    package_type_ids   = fields.Many2many(
        'stock.StockPackageType', blank=True, related_name='putaway_rule_ids',
        help_text='Tipos de paquete a los que aplica (Odoo package_type_ids).',
    )
    storage_category   = fields.Many2one(
        'stock.StockStorageCategory', null=True, blank=True, on_delete=models.CASCADE,
        related_name='putaway_rule_ids',
        help_text='Categoría de almacenamiento exigida a la sububicación '
                  '(Odoo storage_category_id, computado y almacenado).',
    )
    active             = fields.Boolean(
        default=True, help_text='Regla activa (Odoo active).',
    )
    sublocation        = fields.Selection(
        max_length=20, choices=SUBLOCATION_CHOICES, default=SUBLOCATION_NO,
        help_text='Cómo elegir la sububicación concreta (Odoo sublocation).',
    )

    class Meta:
        db_table = 'stock_putaway_rule'
        # ≙ ``_order = 'sequence,product_id'``.
        ordering = ['sequence', 'product_id']
        verbose_name = 'Regla de colocación'
        verbose_name_plural = 'Reglas de colocación'

    def __str__(self) -> str:
        objetivo = self.product or self.category or self.location_in
        return f'{objetivo} → {self.location_out}'

    # -- los tres defaults --

    @classmethod
    def _default_category_id(cls, active_model=None, active_id=None):
        """≙ ``_default_category_id`` (``odoo19c: :22-24``).

        Abriendo la regla desde una categoría, la categoría viene puesta.
        """
        if active_model == 'product.category':
            return active_id
        return None

    @classmethod
    def _default_location_id(cls, active_model=None, active_id=None, company=None,
                             multi_warehouse=True):
        """≙ ``_default_location_id`` (``odoo19c: :26-32``).

        Desde una ubicación, esa ubicación. Sin permiso de multi-almacén, la
        ubicación de entrada del único almacén de la empresa — porque con un
        solo almacén no hay ambigüedad que resolver.
        """
        if active_model == 'stock.location':
            return active_id
        if multi_warehouse:
            return None
        StockWarehouse = apps.get_model('stock', 'StockWarehouse')
        almacen = StockWarehouse.objects.filter(company=company).first()
        if almacen is None:
            return None
        entrada, _salida = almacen._get_input_output_locations(
            almacen.reception_steps, almacen.delivery_steps)
        return entrada

    @classmethod
    def _default_product_id(cls, active_model=None, active_id=None):
        """≙ ``_default_product_id`` (``odoo19c: :34-40``).

        Desde una plantilla con **una sola** variante, esa variante; desde una
        variante, ella misma. Con varias variantes no hay default: elegir una
        sería inventar.
        """
        if active_model == 'product.product':
            return active_id
        if active_model == 'product.template' and active_id:
            plantilla = ProductTemplate.objects.filter(pk=active_id).first()
            if plantilla is not None and plantilla.product_variant_count == 1:
                return plantilla.product_variant_id
        return None

    # -- compute y onchange --

    def compute_storage_category(self):
        """≙ ``_compute_storage_category`` (``odoo19c: :76-80``).

        La categoría de almacenamiento sólo tiene sentido con
        ``sublocation='closest_location'``: en los otros dos modos la regla no
        la consulta, así que dejarla puesta engañaría al lector.
        """
        if self.sublocation != SUBLOCATION_CLOSEST:
            self.storage_category = None
        return self.storage_category

    def _onchange_sublocation(self):
        """≙ ``_onchange_sublocation`` (``odoo19c: :82-94``).

        Devuelve el mensaje de aviso, o ``None`` si no hay nada que avisar.
        """
        if self.sublocation != SUBLOCATION_CLOSEST:
            return None
        StockLocation = apps.get_model('stock', 'StockLocation')
        hijas = StockLocation.objects.filter(
            parent_path__startswith=self.location_out.parent_path,
            storage_category=self.storage_category)
        if hijas.exists():
            return None
        return _('La categoría de almacenamiento elegida no existe en la '
                 'ubicación destino ni en ninguna de sus sububicaciones.')

    def _onchange_location_in(self):
        """≙ ``_onchange_location_in`` (``odoo19c: :96-100``).

        Si el destino no cuelga del origen, deja de ser válido: se iguala al
        origen, que siempre lo es.

        Se leen los **attname** (``location_out_id``/``location_in_id``), no
        los objetos, porque los dos campos son FK no nulables: leer
        ``self.location_out`` con la relación sin fijar levanta
        ``RelatedObjectDoesNotExist`` en vez de devolver ``None``. La fuente
        hace exactamente esto —``loc_in, loc_out = self.location_in_id,
        self.location_out_id`` (``odoo19c: :98``)— porque en su ORM el sufijo
        ``_id`` ES el campo; aquí es el atributo crudo de Django, y la
        traducción fiel del `falsy` de la fuente pasa por él.
        """
        source_id, destination_id = self.location_in_id, self.location_out_id
        if not destination_id or (
                source_id
                and not self.location_out.child_of(self.location_in)):
            self.location_out_id = source_id
        return self.location_out if self.location_out_id else None

    # -- create / write --

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :102-105``).

        La referencia sólo delega en ``super()``; el punto de extensión existe
        para que los addons de almacén lo reescriban, y aquí se conserva por
        la misma razón.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        rules = super().create(vals_list)
        for rule in rules:
            rule.compute_storage_category()
            rule.save(update_fields=['storage_category'])
        return rules

    def write(self, **vals):
        """≙ ``write`` (``odoo19c: :107-112``).

        Cambiar de empresa está prohibido: se archiva y se crea otra.
        """
        if 'company' in vals and self.company is not None:
            if getattr(vals['company'], 'pk', vals['company']) != self.company_id:
                raise UserError(_(
                    'Cambiar la empresa de este registro está prohibido en este '
                    'punto; archívalo y crea uno nuevo.'))
        for clave, valor in vals.items():
            setattr(self, clave, valor)
        self.compute_storage_category()
        self.save()
        return self

    # -- la última ubicación usada --

    def get_last_used_search_domain(self, product):
        """≙ ``_get_last_used_search_domain`` (``odoo19c: :114-124``).

        Devuelve el ``Q`` de las líneas ya validadas que dejaron este producto
        bajo la ubicación destino; con tipos de paquete declarados, además
        acota a esos tipos.
        """
        dominio = models.Q(
            state='done',
            location_dest__parent_path__startswith=self.location_out.parent_path,
            product=product,
        )
        if self.package_type_ids.exists():
            dominio &= models.Q(
                result_package__package_type__in=self.package_type_ids.all())
        return dominio

    def get_last_used_location(self, product):
        """≙ ``_get_last_used_location`` (``odoo19c: :126-132``).

        La ubicación de la última entrada de este producto — «última» por
        fecha descendente, igual que la referencia.
        """
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        linea = (StockMoveLine.objects
                 .filter(self.get_last_used_search_domain(product))
                 .order_by('-date')
                 .first())
        return linea.location_dest if linea is not None else None

    # -- el resolutor --

    def get_putaway_location(self, product, quantity=0, package=None,
                             packaging=None, qty_by_location=None):
        """≙ ``_get_putaway_location`` (``odoo19c: :134-183``).

        Devuelve la ubicación donde colocar, o ``None`` si esta regla no
        resuelve. El orden de prueba es el de la referencia y tiene un porqué:

        1. sin categoría de almacenamiento, se prueba el destino directo;
        2. con ella, primero las sububicaciones que **ya tienen** este producto
           o este tipo de paquete —agrupar es mejor que dispersar—;
        3. y sólo después, cualquier sububicación de la categoría.

        ``checked_locations`` evita volver a probar una que ya se descartó, que
        es lo que hace barato el tercer paso.
        """
        cantidades = qty_by_location if qty_by_location is not None else {}
        tipo_paquete = None
        if package is not None:
            tipo_paquete = package.package_type
        elif packaging is not None:
            tipo_paquete = packaging.package_type

        descartadas = set()
        destino = self.location_out
        if self.sublocation == SUBLOCATION_LAST_USED:
            ultima = self.get_last_used_location(product)
            destino = ultima or destino

        if self.storage_category is None:
            if destino.pk in descartadas:
                return None
            if destino.check_can_be_used(
                    product, quantity, package, cantidades.get(destino.pk, 0)):
                return destino
            return None

        hijas = [loc for loc in destino.child_internal_location_ids
                 if loc.storage_category_id == self.storage_category_id]

        # (2) las que ya albergan este producto o este tipo de paquete
        for ubicacion in hijas:
            if ubicacion.pk in descartadas:
                continue
            if tipo_paquete is not None:
                ya_tiene = ubicacion.quant_ids.filter(
                    package__isnull=False,
                    package__package_type=tipo_paquete).exists()
                if not ya_tiene:
                    continue
                if ubicacion.check_can_be_used(
                        product, quantity, package=package,
                        location_qty=cantidades.get(ubicacion.pk, 0)):
                    return ubicacion
                descartadas.add(ubicacion.pk)
            elif cantidades.get(ubicacion.pk, 0) > 0:
                if ubicacion.check_can_be_used(
                        product, quantity,
                        location_qty=cantidades.get(ubicacion.pk, 0)):
                    return ubicacion
                descartadas.add(ubicacion.pk)

        # (3) cualquiera de la categoría
        for ubicacion in hijas:
            if ubicacion.pk in descartadas:
                continue
            if ubicacion.check_can_be_used(
                    product, quantity, package, cantidades.get(ubicacion.pk, 0)):
                return ubicacion
            descartadas.add(ubicacion.pk)

        return None
