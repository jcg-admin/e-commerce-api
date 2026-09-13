"""``stock.package`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_package.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **paquete** es el contenedor físico con contenido — existencias
sueltas (``quant_ids``) y/o otros paquetes anidados. Tiene **dos jerarquías
distintas**, y confundirlas es el error más fácil de este modelo:

- ``parent_package_id`` — el contenedor **actual**, dónde está ahora;
- ``package_dest_id`` — el contenedor **destino**, dónde quedará al validar.

La referencia sólo puede materializar una de las dos (``_parent_store`` admite
un único padre), por eso la segunda se recorre a mano en
``_get_all_children_package_dest_ids`` y ``_get_all_package_dest_ids``. Este
puerto conserva esa asimetría tal cual: no es un descuido de la referencia, es
la consecuencia de tener dos árboles sobre la misma tabla.

Porte símbolo por símbolo — 57 de 57
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_package.py`` (558 líneas):
24 campos y 33 métodos.

Campos — 24 de 24
-------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``name`` (25)                                    ``name``
``complete_name`` (26)                           ``complete_name`` (almacenado)
``dest_complete_name`` (27)                      property ``dest_complete_name``
``quant_ids`` (28-29)                            reverso ``quant_ids``
``contained_quant_ids`` (30)                     property ``contained_quant_ids``
``content_description`` (31)                     property ``content_description``
``package_type_id`` (32-33)                      ``package_type``
``location_id`` (34-36)                          ``location`` (almacenado)
``location_dest_id`` (37)                        property ``location_dest``
``company_id`` (38-40)                           ``company`` (almacenado)
``owner_id`` (41-43)                             property ``owner``
``parent_package_id`` (44)                       ``parent_package``
``child_package_ids`` (45)                       reverso ``child_package_ids``
``all_children_package_ids`` (46)                property ``all_children_package_ids``
``package_dest_id`` (47)                         ``package_dest``
``outermost_package_id`` (48)                    property ``outermost_package``
``child_package_dest_ids`` (49)                  reverso ``child_package_dest_ids``
``move_line_ids`` (50)                           property ``move_line_ids``
``picking_ids`` (51)                             property ``picking_ids``
``shipping_weight`` (52)                         ``shipping_weight``
``valid_sscc`` (53)                              property ``valid_sscc``
``pack_date`` (54)                               ``pack_date``
``parent_path`` (55)                             ``parent_path``
``json_popover`` (56)                            property ``json_popover``
===============================================  ======================================

Métodos — 33 de 33
--------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``_compute_all_children_package_ids`` (59-70)    property ``all_children_package_ids``
``_compute_display_name`` (72-90)                ``__str__`` + ``display_name``
``_compute_complete_name`` (92-98)               ``compute_complete_name``
``_compute_dest_complete_name`` (100-106)        property ``dest_complete_name``
``_compute_contained_quant_ids`` (108-111)       property ``contained_quant_ids``
``_compute_content_description`` (113-122)       property ``content_description``
``_compute_json_popover`` (124-136)              property ``json_popover``
``_compute_location_dest_id`` (138-141)          property ``location_dest``
``_compute_move_line_ids`` (143-155)             property ``move_line_ids``
``_compute_package_info`` (157-170)              ``compute_package_info``
``_compute_picking_ids`` (172-183)               property ``picking_ids``
``_compute_owner_id`` (185-192)                  property ``owner``
``_compute_outermost_package_id`` (194-200)      property ``outermost_package``
``_compute_valid_sscc`` (202-206)                property ``valid_sscc``
``_search_all_children_package_ids`` (208-210)   ``_search_all_children_package_ids``
``_search_contained_quant_ids`` (212-217)        ``_search_contained_quant_ids``
``_search_location_dest_id`` (219-228)           ``_search_location_dest_id``
``_search_move_line_ids`` (230-248)              ``_search_move_line_ids``
``_search_outermost_package_id`` (250-259)       ``_search_outermost_package_id``
``_search_owner`` (261-264)                      ``_search_owner``
``_search_picking_ids`` (266-276)                ``_search_picking_ids``
``create`` (278-287)                             ``create`` (classmethod)
``write`` (289-314)                              ``write``
``unpack`` (316-325)                             ``unpack``
``action_add_to_picking`` (327-330)              ``action_add_to_picking``
``_pre_put_in_pack_hook`` (332-341)              ``pre_put_in_pack_hook``
``_post_put_in_pack_hook`` (343-345)             ``post_put_in_pack_hook``
``action_put_in_pack`` (347-367)                 ``action_put_in_pack``
``action_remove_package`` (369-405)              ``action_remove_package``
``action_view_picking`` (407-412)                ``action_view_picking``
``_check_move_lines_map_quant`` (414-433)        ``_check_move_lines_map_quant``
``_get_weight`` (435-470)                        ``get_weight``
``_has_issues`` (472-474)                        ``has_issues``
``_apply_dest_to_package`` (476-509)             ``apply_dest_to_package``
``_get_all_children_package_dest_ids`` (511-531) ``get_all_children_package_dest_ids``
``_get_all_package_dest_ids`` (533-544)          ``get_all_package_dest_ids``
``_apply_package_dest_for_entire_packs`` (546-558) ``_apply_package_dest_for_entire_packs``
===============================================  ======================================

Divergencias declaradas
=========================

1. **Los ``search=`` devuelven un queryset, no un dominio.** La referencia los
   declara como método de búsqueda del campo computado y retorna una lista de
   tuplas que su ORM traduce a SQL. Aquí devuelven el ``QuerySet`` ya resuelto:
   es el mismo conjunto, sin la capa de traducción que este ORM no necesita.
2. **``_pre_put_in_pack_hook`` devuelve el asistente como descriptor, no como
   acción.** La referencia retorna un ``ir.actions.act_window`` que su cliente
   web abre. Sin capa de vistas, aquí retorna el diccionario con el mismo
   contenido (``default_package_ids``, ``default_location_dest_id``) para que
   el consumidor —hoy, la API REST— decida cómo presentarlo. El **gate** es
   idéntico: si ``should_display_put_in_pack_wizard`` dice que sí, no se
   empaqueta directo. Registrado en la tarea **#279** (``stock`` sin capa de
   reportes/vistas propia).
3. **``json_popover`` emite el diccionario, no su serialización.** La
   referencia hace ``json.dumps`` porque su widget lo consume como cadena;
   aquí el consumidor es DRF, que serializa él mismo. El contenido —título,
   mensaje con las ubicaciones, color e icono— es el mismo.

Cuatro computes que el gate de porte reporta ausentes, y por qué no lo están
(:ref:`h-api-680`)
--------------------------------------------------------------------------------

``check_porte_completo.py`` absuelve un ``_compute_<campo>`` cuando existe una
``property`` **con el mismo nombre exacto** que el campo de la referencia y su
docstring cita el símbolo — ``equivalencias_declaradas()``,
``scripts/check_porte_completo.py:289-340``. Los cuatro casos siguientes fallan
esa condición por una razón *distinta* cada vez, verificada leyendo ambos
archivos línea a línea, no asumida:

4. **``_compute_location_dest_id`` → property ``location_dest`` (:377).** El
   campo de la referencia es ``location_dest_id``; este árbol retira el
   sufijo ``_id`` de todo FK (convención del proyecto, no de este archivo:
   ``picking_id`` → ``picking``, ``package_dest_id`` → ``package_dest``, ya
   arriba en este mismo docstring). La property se llama ``location_dest``,
   así que la clave que el gate deriva es ``_compute_location_dest`` —no
   ``_compute_location_dest_id``— y nunca coincide con el nombre real de la
   referencia. El cuerpo (``:378-384``) es el mismo: la ubicación destino de
   la **primera** línea en curso, con el conflicto multi-destino reportado
   por ``has_issues``/``json_popover``.
5. **``_compute_outermost_package_id`` → property ``outermost_package``
   (:423).** Mismo mecanismo — el campo es ``outermost_package_id`` allá,
   ``outermost_package`` aquí. Cuerpo idéntico: recursión por
   ``package_dest`` hasta la raíz.
6. **``_compute_owner_id`` → property ``owner`` (:409).** Mismo mecanismo —
   ``owner_id`` → ``owner``. Cuerpo idéntico: sólo hay dueño si todos los
   quants coinciden.
7. **``_compute_display_name`` — portado, y la divergencia se cerró.** Esta
   entrada declaraba que el stack «no tiene ese contexto implícito de
   petición», así que las cuatro claves de la referencia
   (``is_done``/``show_dest_package``/``show_src_package``/
   ``formatted_display_name``) viajaban como **parámetros** de un
   ``display_name(self, is_done=False, …)``. **La premisa caducó:** el
   contexto existe —``orm.environments.get_context``— y ya lo consumen
   ``ResPartner._compute_display_name`` y
   ``ProductSupplierinfo._compute_display_name``. El método toma el nombre y
   la firma de la fuente, lee el contexto, y ``__str__`` conserva la rama por
   defecto para el ``str()`` de Python.

Deuda saldada al tocar el archivo (2026-08-18)
================================================

``_check_move_lines_map_quant`` y ``_apply_package_dest_for_entire_packs``
estaban despromovidos (H-API-581) — la referencia los declara privados y el
puerto los había publicado. Restaurados con su guion bajo al consumirlos el
grupo «Paquetes» de ``stock.picking`` (tarea #521); medido antes del cambio,
**0 llamadores** con el nombre público fuera de este archivo (``grep -rn``
sobre ``addons/``, ``src/`` y ``tests/``). Los demás despromovidos de este
archivo (``get_weight``, ``has_issues``, ``apply_dest_to_package``,
``get_all_children_package_dest_ids``, ``get_all_package_dest_ids``,
``pre_put_in_pack_hook``, ``post_put_in_pack_hook``) siguen en el barrido de
la tarea **#337** — dos de ellos tienen llamadores externos medidos
(``apply_dest_to_package`` y ``get_all_package_dest_ids``, en
``stock_move_line.py``) y ninguno lo consume el grupo Paquetes de este pase.
"""
import datetime
from collections import defaultdict

import fields
import api
import models
from django.apps import apps
from django.db.models import Sum

from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from orm.environments import get_context
from tools.barcode import check_barcode_encoding
from tools.translate import _

#: ≙ los estados que la referencia excluye al mirar líneas «en curso»
#: (``odoo19c: :147``, ``:177``, ``:224``, ``:271``).
ONGOING_EXCLUDED_STATES = ('done', 'cancel')


class StockPackage(models.DefaultGetMixin, TimeStampedModel):
    """``stock.package`` — contenedor de existencias y/o de otros paquetes."""

    # Atributos de clase de modelo — los seis que la referencia declara
    # (``odoo19c: stock/models/stock_package.py:18-23``), verbatim
    # (:ref:`h-api-680`). ``_parent_store``/``_parent_name`` describen el
    # árbol de contenedores ACTUALES (``parent_package``); el segundo árbol
    # de DESTINOS (``package_dest``) no se materializa con ``parent_path`` —
    # ver la nota de cabecera sobre las dos jerarquías.
    _name = 'stock.package'
    _description = 'Package'
    _order = 'name, id'
    _parent_name = 'parent_package'
    _parent_store = True
    _rec_name = 'complete_name'

    name              = fields.Char(
        max_length=120, db_index=True,
        help_text='Referencia del paquete (Odoo name, requerido).',
    )
    complete_name     = fields.Char(
        max_length=512, blank=True, default='',
        help_text='Nombre jerárquico «A > B > C» (Odoo complete_name, almacenado).',
    )
    package_type      = fields.Many2one(
        'stock.StockPackageType', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='package_ids', db_index=True,
        help_text='Tipo de paquete (Odoo package_type_id).',
    )
    location          = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='package_ids', db_index=True,
        help_text='Ubicación actual, derivada de su contenido '
                  '(Odoo location_id, computado y almacenado).',
    )
    company           = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='stock_packages', db_index=True,
        help_text='Empresa, derivada de su contenido '
                  '(Odoo company_id, computado y almacenado).',
    )
    parent_package    = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='child_package_ids', db_index=True,
        help_text='Contenedor ACTUAL (Odoo parent_package_id).',
    )
    package_dest      = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='child_package_dest_ids', db_index=True,
        help_text='Contenedor DESTINO al validar (Odoo package_dest_id).',
    )
    shipping_weight   = fields.Monetary(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text='Peso total declarado del paquete (Odoo shipping_weight).',
    )
    pack_date         = fields.Date(
        default=datetime.date.today,
        help_text='Fecha de empaquetado (Odoo pack_date).',
    )
    parent_path       = fields.Char(
        max_length=512, blank=True, default='', db_index=True,
        help_text='Ruta materializada del árbol de contenedores ACTUALES '
                  '(Odoo parent_path).',
    )

    class Meta:
        db_table = 'stock_package'
        ordering = ['name', 'id']          # ≙ ``_order = 'name, id'``
        verbose_name = 'Paquete'
        verbose_name_plural = 'Paquetes'

    def __str__(self) -> str:
        """≙ ``_compute_display_name`` (``odoo19c: :72-90``), rama por defecto.

        La referencia elige entre ``name``, ``complete_name`` y
        ``dest_complete_name`` según tres claves de contexto que pone su
        cliente web (``is_done``, ``show_src_package``, ``show_dest_package``).
        Sin ese contexto, la rama por defecto es ``name`` — y las otras tres
        se piden explícitamente con ``display_name``.
        """
        return self.name

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``odoo19c: stock_package.py:71-89``).

        Las cuatro claves de contexto de la referencia, leídas del contexto —
        ``is_done``, ``show_dest_package``, ``show_src_package`` y
        ``formatted_display_name``—, no como parámetros: el mecanismo de
        contexto ya existe (``orm.environments.get_context``) y es el mismo que
        consumen ``ResPartner._compute_display_name`` y
        ``ProductSupplierinfo._compute_display_name``.

        El orden de las ramas es el de la fuente y no es intercambiable: un
        albarán validado (``is_done``) muestra el nombre corto aunque la vista
        pida el contenedor de destino.
        """
        contexto = get_context()
        if contexto.get('is_done'):
            nombre = self.name
        elif contexto.get('show_dest_package'):
            nombre = self.dest_complete_name
        elif contexto.get('show_src_package'):
            nombre = self.complete_name
        else:
            nombre = self.name
        tipo = self.package_type
        if (contexto.get('formatted_display_name') and tipo is not None
                and tipo.packaging_length and tipo.width and tipo.height):
            return (f'{nombre}\t--{tipo.packaging_length} x '
                    f'{tipo.width} x {tipo.height}--')
        return nombre

    # -- los computes almacenados --

    def compute_complete_name(self):
        """≙ ``_compute_complete_name`` (``odoo19c: :92-98``)."""
        if self.parent_package is not None:
            self.complete_name = f'{self.parent_package.complete_name} > {self.name}'
        else:
            self.complete_name = self.name
        return self.complete_name

    def compute_parent_path(self):
        """Materializa ``parent_path`` — ≙ el ``_parent_store`` de la referencia.

        Sólo del árbol de contenedores **actuales**: el de destino no se puede
        materializar (un solo campo padre por modelo), y por eso la referencia
        lo recorre a mano en ``_get_all_children_package_dest_ids``.
        """
        if self.pk is None:
            return self.parent_path
        if self.parent_package is not None:
            raiz = self.parent_package.parent_path or self.parent_package.compute_parent_path()
            self.parent_path = f'{raiz}{self.pk}/'
        else:
            self.parent_path = f'{self.pk}/'
        return self.parent_path

    def compute_package_info(self):
        """≙ ``_compute_package_info`` (``odoo19c: :157-170``).

        Ubicación y empresa se **derivan del contenido**: de los quants con
        cantidad positiva si los hay, y si no, del primer paquete hijo. La
        empresa sólo se fija cuando **todos** coinciden — con contenido de dos
        empresas el paquete no es de ninguna, que es lo que la referencia
        expresa con su ``all(...)``.
        """
        self.location = None
        self.company = None
        positivos = [q for q in self.quant_ids.all() if (q.quantity or 0) > 0]
        if positivos:
            self.location = positivos[0].location
            todos = list(self.quant_ids.all())
            if all(q.company_id == todos[0].company_id for q in todos):
                self.company = todos[0].company
            return
        hijos = list(self.child_package_ids.all())
        if hijos:
            self.location = hijos[0].location
            if all(p.company_id == hijos[0].company_id for p in hijos):
                self.company = hijos[0].company

    def save(self, *args, **kwargs):
        """Los ``compute … store=True`` se disparan en CADA escritura.

        Mismo defecto y mismo remedio que ``StockLocation.save``
        (``stock_location.py:545``): la clase declara ``_parent_store``, pero
        sin este disparo ``objects.create(...)`` —el camino de Django, el que
        usan los tests y buena parte del árbol— dejaba ``parent_path`` vacío.
        Con la ruta vacía, ``_search_all_children_package_ids`` y
        ``_search_contained_quant_ids`` devolvían el conjunto vacío para
        jerarquías que sí existían: el silencio del campo se leía como
        ausencia de ancestros.

        El recálculo va **después** del ``INSERT`` porque ``parent_path``
        incluye el propio ``id``, y persiste con ``update_fields`` para no
        reescribir el resto. No hay recursión: ``refresh_computed_fields``
        llama a ``super().save()``, que es el de ``TimeStampedModel``.
        """
        super().save(*args, **kwargs)
        self.refresh_computed_fields()

    def refresh_computed_fields(self):
        """Recalcula y persiste los cuatro campos almacenados de la referencia."""
        self.compute_parent_path()
        self.compute_complete_name()
        self.compute_package_info()
        super().save(update_fields=[
            'parent_path', 'complete_name', 'location', 'company'])

    # -- los computes no almacenados --

    @property
    def dest_complete_name(self):
        """≙ ``dest_complete_name`` / ``_compute_dest_complete_name`` (``:27``, ``:100-106``).

        El mismo nombre jerárquico, pero sobre el árbol de **destino**.
        """
        if self.package_dest is not None:
            return f'{self.package_dest.dest_complete_name} > {self.name}'
        return self.name

    @property
    def all_children_package_ids(self):
        """≙ ``all_children_package_ids`` /
        ``_compute_all_children_package_ids`` (``:46``, ``:59-70``).

        Todos los descendientes del árbol **actual**, a cualquier profundidad.
        La referencia los recoge con una recursión sobre el agrupado; aquí
        basta el prefijo de la ruta materializada.
        """
        return StockPackage.objects.filter(
            parent_path__startswith=self.parent_path).exclude(pk=self.pk)

    @property
    def contained_quant_ids(self):
        """≙ ``contained_quant_ids`` / ``_compute_contained_quant_ids`` (``:30``, ``:108-111``).

        Los quants propios más los de todos los descendientes.
        """
        StockQuant = apps.get_model('stock', 'StockQuant')
        descendientes = self.all_children_package_ids.values_list('pk', flat=True)
        return StockQuant.objects.filter(
            models.Q(package=self) | models.Q(package__in=descendientes))

    @property
    def content_description(self):
        """≙ ``content_description`` / ``_compute_content_description`` (``:31``, ``:113-122``).

        «2 Unidades Camiseta, 3 kg Café» — la cantidad se imprime sin decimales
        cuando es entera, que es lo que hace el ``int(qty) if qty == int(qty)``
        de la referencia.
        """
        agrupado = defaultdict(lambda: 0)
        unidades = {}
        for quant in self.contained_quant_ids.select_related('product', 'product_uom'):
            clave = (quant.product_uom_id, quant.product_id)
            agrupado[clave] += quant.quantity or 0
            unidades[clave] = (quant.product_uom, quant.product)
        partes = []
        for clave, cantidad in agrupado.items():
            unidad, producto = unidades[clave]
            numero = int(cantidad) if cantidad == int(cantidad) else cantidad
            partes.append(f'{numero} {unidad} {producto}')
        return ', '.join(partes)

    @property
    def json_popover(self):
        """≙ ``json_popover`` / ``_compute_json_popover`` (``:56``, ``:124-136``).

        El aviso de destinos múltiples, o ``None`` si no hay conflicto.
        """
        if not self.has_issues():
            return None
        destinos = sorted({str(l.location_dest) for l in self.move_line_ids})
        return {
            'title': _('Destinos múltiples'),
            'msg': _('Este paquete está configurado para enviarse a %s.')
                   % ', '.join(destinos),
            'color': 'text-warning',
            'icon': 'fa-exclamation-triangle',
        }

    @property
    def location_dest(self):
        """≙ ``location_dest_id`` (``:37``, compute ``:138-141``).

        La ubicación destino de su **primera** línea en curso. Con más de una
        el paquete tiene conflicto, y eso lo reporta ``has_issues``.
        """
        primera = next(iter(self.move_line_ids), None)
        return primera.location_dest if primera is not None else None

    @property
    def move_line_ids(self):
        """≙ ``move_line_ids`` / ``_compute_move_line_ids`` (``:50``, ``:143-155``).

        Las líneas en curso que apuntan a este paquete como destino, más las
        de todos sus contenedores-hijos de destino.
        """
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        _por_paquete, todos = self.get_all_children_package_dest_ids()
        return StockMoveLine.objects.filter(
            result_package_id__in=todos).exclude(state__in=ONGOING_EXCLUDED_STATES)

    @property
    def picking_ids(self):
        """≙ ``picking_ids`` / ``_compute_picking_ids`` (``:51``, ``:172-183``).

        Las transferencias donde este paquete es el destino.
        """
        StockPicking = apps.get_model('stock', 'StockPicking')
        ids = {l.picking_id for l in self.move_line_ids if l.picking_id}
        return StockPicking.objects.filter(pk__in=ids)

    @property
    def owner(self):
        """≙ ``owner_id`` (``:41-43``, compute ``:185-192``).

        Sólo hay dueño si **todos** los quants coinciden — mismo criterio que
        la empresa en ``compute_package_info``.
        """
        quants = list(self.quant_ids.all())
        if not quants:
            return None
        if all(q.owner_id == quants[0].owner_id for q in quants):
            return quants[0].owner
        return None

    @property
    def outermost_package(self):
        """≙ ``outermost_package_id`` (``:48``, compute ``:194-200``).

        La raíz del árbol de **destino**; si no tiene destino, es él mismo.
        """
        if self.package_dest is not None:
            return self.package_dest.outermost_package
        return self

    @property
    def valid_sscc(self):
        """≙ ``valid_sscc`` / ``_compute_valid_sscc`` (``:53``, ``:202-206``)."""
        return bool(self.name) and check_barcode_encoding(self.name, 'sscc')

    # -- las siete búsquedas --
    #
    # Los siete métodos de esta sección restauran su guion bajo
    # (:ref:`h-api-680`, porte-completo-no-parcial.md/H-API-581): la
    # referencia los declara privados (``_search_x``) y el puerto los había
    # publicado sin él. Medido antes de corregir: 0 llamadores fuera de este
    # archivo (``grep -rn`` sobre ``addons/`` y ``tests/``).

    @classmethod
    def _search_all_children_package_ids(cls, packages):
        """≙ ``_search_all_children_package_ids`` (``odoo19c: :208-210``).

        Los ancestros de los paquetes dados — ``parent_of`` en su idioma.
        """
        rutas = [p.parent_path for p in packages if p.parent_path]
        if not rutas:
            return cls.objects.none()
        pks = {int(x) for ruta in rutas for x in ruta.split('/') if x}
        return cls.objects.filter(pk__in=pks)

    @classmethod
    def _search_contained_quant_ids(cls, quants):
        """≙ ``_search_contained_quant_ids`` (``odoo19c: :212-217``).

        Los paquetes que contienen esos quants, y sus ancestros.
        """
        directos = cls.objects.filter(quant_ids__in=quants).distinct()
        if not directos.exists():
            return cls.objects.none()
        return cls._search_all_children_package_ids(directos)

    @classmethod
    def _search_location_dest_id(cls, locations):
        """≙ ``_search_location_dest_id`` (``odoo19c: :219-228``)."""
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        lineas = (StockMoveLine.objects
                  .exclude(state__in=ONGOING_EXCLUDED_STATES)
                  .filter(location_dest__in=locations)
                  .exclude(result_package__isnull=True)
                  .select_related('result_package'))
        pks = set()
        for linea in lineas:
            pks.update(linea.result_package.get_all_package_dest_ids())
        return cls.objects.filter(pk__in=pks)

    @classmethod
    def _search_move_line_ids(cls, move_lines=None, unassigned=False):
        """≙ ``_search_move_line_ids`` (``odoo19c: :230-248``).

        Con ``unassigned=True`` devuelve los paquetes **sin** ninguna línea en
        curso — la rama que la referencia activa cuando el valor buscado es
        ``(False,)``.
        """
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        consulta = StockMoveLine.objects.exclude(state__in=ONGOING_EXCLUDED_STATES)
        if not unassigned and move_lines is not None:
            consulta = consulta.filter(pk__in=[l.pk for l in move_lines])
        pks = set()
        for linea in consulta.exclude(result_package__isnull=True).select_related(
                'result_package'):
            pks.update(linea.result_package.get_all_package_dest_ids())
        if unassigned:
            return cls.objects.exclude(pk__in=pks)
        return cls.objects.filter(pk__in=pks)

    @classmethod
    def _search_outermost_package_id(cls, packages):
        """≙ ``_search_outermost_package_id`` (``odoo19c: :250-259``)."""
        directos = cls.objects.filter(package_dest__in=packages)
        _por_paquete, todos = cls.get_all_children_package_dest_ids_for(directos)
        return cls.objects.filter(pk__in=todos)

    @classmethod
    def _search_owner(cls, partners):
        """≙ ``_search_owner`` (``odoo19c: :261-264``)."""
        return cls.objects.filter(quant_ids__owner__in=partners).distinct()

    @classmethod
    def _search_picking_ids(cls, pickings):
        """≙ ``_search_picking_ids`` (``odoo19c: :266-276``)."""
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        lineas = (StockMoveLine.objects
                  .exclude(state__in=ONGOING_EXCLUDED_STATES)
                  .filter(picking__in=pickings)
                  .exclude(result_package__isnull=True)
                  .select_related('result_package'))
        pks = set()
        for linea in lineas:
            pks.update(linea.result_package.get_all_package_dest_ids())
        return cls.objects.filter(pk__in=pks)

    # -- create / write --

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: :278-287``).

        Dos normalizaciones de la referencia: ``complete_name`` recibido se
        interpreta como ``name`` (lo escribe el escáner de códigos), y sin
        nombre se pide el siguiente a la secuencia del tipo de paquete.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        for vals in vals_list:
            if vals.get('complete_name'):
                vals['name'] = vals.pop('complete_name')
            if not vals.get('name'):
                tipo = vals.get('package_type')
                if tipo is not None:
                    vals['name'] = tipo._get_next_name_by_sequence()
        packages = super().create(vals_list)
        for package in packages:
            package.refresh_computed_fields()
        return packages

    def write(self, **vals):
        """≙ ``write`` (``odoo19c: :289-314``).

        Tres guardas de la referencia:

        1. vaciar el nombre lo **recalcula** desde la secuencia del tipo;
        2. cambiar la ubicación **mueve los quants** (no reetiqueta): quitarla
           de un paquete no vacío o mover uno vacío son ambos errores;
        3. un paquete no puede tener como destino a uno de sus contenidos —
           sería una recursión, y el ``parent_path`` no la detecta porque
           materializa el **otro** árbol.
        """
        if 'name' in vals and not vals['name']:
            tipo = vals.get('package_type', self.package_type)
            vals['name'] = tipo._get_next_name_by_sequence() if tipo is not None else ''

        if 'location' in vals:
            vacio = not self.contained_quant_ids.exists()
            if not vals['location'] and not vacio:
                raise UserError(_(
                    'No se puede quitar la ubicación de un paquete no vacío.'))
            if vals['location']:
                if vacio:
                    raise UserError(_('No se puede mover un paquete vacío.'))
                a_mover = self.contained_quant_ids.filter(quantity__gt=0)
                for quant in a_mover:
                    quant.move_quants(
                        vals['location'],
                        message=_('Paquete reubicado manualmente'),
                        up_to_parent_packages=[self])

        if vals.get('package_dest'):
            _por_paquete, contenidos = self.get_all_children_package_dest_ids()
            destino = getattr(vals['package_dest'], 'pk', vals['package_dest'])
            if destino in contenidos:
                raise ValidationError(_(
                    'Un paquete no puede tener como contenedor destino a uno '
                    'de los paquetes que contiene.'))

        for clave, valor in vals.items():
            setattr(self, clave, valor)
        self.save()
        self.refresh_computed_fields()
        return self

    # -- acciones --

    def unpack(self):
        """≙ ``unpack`` (``odoo19c: :316-325``).

        Saca los quants del contenedor y desliga los paquetes hijos. La
        consolidación posterior (``_quant_tasks``) no es cosmética: sin ella
        quedan dos quants del mismo producto y una reserva de 100 sobre dos
        paquetes de 50 crea un quant de −50 al validar.
        """
        self.child_package_ids.update(parent_package=None)
        quants = list(self.quant_ids.all())
        if quants:
            for quant in quants:
                quant.move_quants(message=_('Cantidades desempaquetadas'),
                                  unpack=True)
            StockQuant = apps.get_model('stock', 'StockQuant')
            StockQuant._quant_tasks()

    def action_add_to_picking(self, picking):
        """≙ ``action_add_to_picking`` (``odoo19c: :327-330``)."""
        if picking is not None:
            picking.action_add_entire_packs([self.pk])

    def pre_put_in_pack_hook(self, package=None, package_type=None,
                             package_name=None, from_package_wizard=False):
        """≙ ``_pre_put_in_pack_hook`` (``odoo19c: :332-341``).

        Si hace falta preguntar al usuario, devuelve el descriptor del
        asistente; si no, ``None`` y el empaquetado sigue directo.
        """
        lineas = self.move_line_ids
        if not lineas.exists():
            return None
        primera = lineas.first()
        if not primera.should_display_put_in_pack_wizard(
                package, package_type, package_name, from_package_wizard):
            return None
        destino = self.location_dest
        return {
            'wizard': 'stock.action_put_in_pack_wizard',
            'context': {
                'default_package_ids': [self.pk],
                'default_location_dest_id': destino.pk if destino is not None else None,
            },
        }

    def post_put_in_pack_hook(self):
        """≙ ``_post_put_in_pack_hook`` (``odoo19c: :343-345``).

        Punto de extensión: la referencia devuelve ``self`` y lo reescriben los
        addons de transporte para calcular el peso del envío.
        """
        return self

    def action_put_in_pack(self, package=None, package_type=None,
                           package_name=None, from_package_wizard=False):
        """≙ ``action_put_in_pack`` (``odoo19c: :347-367``).

        Mete este paquete dentro de otro. Lo delicado son los dos pasos
        finales, y ninguno es opcional: los contenedores que quedaron sin
        líneas se liberan (si no, apuntan a una cadena rota), y la estrategia
        de colocación se re-aplica porque el contenedor exterior cambió y con
        él, la regla que decide dónde va.
        """
        asistente = self.pre_put_in_pack_hook(
            package, package_type, package_name, from_package_wizard)
        if asistente:
            return asistente

        if package is None:
            package = StockPackage.create(
                package_type=package_type, name=package_name)

        previos = StockPackage.objects.filter(pk__in=self.get_all_package_dest_ids())
        self.package_dest = package
        self.save(update_fields=['package_dest'])

        for previo in previos:
            if not previo.move_line_ids.exists():
                previo.package_dest = None
                previo.save(update_fields=['package_dest'])

        lineas = package.move_line_ids
        if lineas.exists():
            lineas.first().apply_putaway_strategy(lineas)
        return package.post_put_in_pack_hook()

    def action_remove_package(self, picking_ids=None):
        """≙ ``action_remove_package`` (``odoo19c: :369-405``).

        Saca el paquete del árbol de destino. La distinción que gobierna el
        método: una línea que movía el **paquete entero** se borra (ya no hay
        paquete que mover); una que movía parte, sólo pierde su destino.
        """
        StockMove = apps.get_model('stock', 'StockMove')
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')

        todos_destinos = self.get_all_package_dest_ids()
        todas_lineas = {l.pk for l in self.move_line_ids}
        a_borrar, a_actualizar, movimientos = set(), set(), set()

        for linea in self.move_line_ids:
            if picking_ids and linea.picking_id not in picking_ids:
                continue
            if linea.result_package_id == self.pk:
                if linea.is_entire_pack:
                    a_borrar.add(linea.pk)
                    movimientos.add(linea.move_id)
                else:
                    a_actualizar.add(linea.pk)

        StockMoveLine.objects.filter(pk__in=a_borrar).delete()
        StockMoveLine.objects.filter(pk__in=a_actualizar).update(result_package=None)
        StockMove.objects.filter(
            pk__in=movimientos, product_uom_qty=0, move_line_ids__isnull=True).delete()

        self.child_package_dest_ids.update(package_dest=None)
        self.package_dest = None
        self.save(update_fields=['package_dest'])

        for paquete in StockPackage.objects.filter(pk__in=todos_destinos):
            if not paquete.move_line_ids.exists():
                paquete.package_dest = None
                paquete.save(update_fields=['package_dest'])

        restantes = StockMoveLine.objects.filter(pk__in=todas_lineas - a_borrar)
        if restantes.exists():
            restantes.first().apply_putaway_strategy(restantes)
        return True

    def action_view_picking(self):
        """≙ ``action_view_picking`` (``odoo19c: :407-412``).

        Devuelve las transferencias donde el paquete aparece como origen o
        como destino.
        """
        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        StockPicking = apps.get_model('stock', 'StockPicking')
        lineas = StockMoveLine.objects.filter(
            models.Q(result_package=self) | models.Q(package=self))
        return StockPicking.objects.filter(
            pk__in=lineas.values_list('picking_id', flat=True))

    # -- verificación y peso --

    def _check_move_lines_map_quant(self, move_lines):
        """≙ ``_check_move_lines_map_quant`` (``odoo19c: :414-433``).

        ¿Las líneas cubren exactamente lo que el paquete contiene? Se agrupa
        por (producto, lote) en ambos lados y se comparan los dos sentidos —
        la referencia hace las dos comprobaciones a propósito: que no falte y
        que no sobre no son la misma pregunta.
        """
        if not move_lines:
            return True

        del_paquete = defaultdict(lambda: 0)
        for quant in self.contained_quant_ids:
            del_paquete[(quant.product_id, quant.lot_id)] += quant.quantity or 0

        de_lineas = defaultdict(lambda: 0)
        for linea in move_lines:
            de_lineas[(linea.product_id, linea.lot_id)] += linea.quantity_product_uom or 0

        return (all(del_paquete[k] == de_lineas.get(k, 0) for k in del_paquete)
                and all(de_lineas[k] == del_paquete.get(k, 0) for k in de_lineas))

    def get_weight(self, picking=None):
        """≙ ``_get_weight`` (``odoo19c: :435-470``).

        Sin transferencia, el peso es el declarado del embalaje más el de todo
        lo que contiene (incluidos los embalajes de los paquetes anidados).
        Con transferencia, el contenido son las **líneas de esa** transferencia
        —no los quants—, porque el paquete todavía no está formado.
        """
        peso = float(self.package_type.base_weight or 0) if self.package_type else 0.0

        if picking is None:
            for hijo in self.all_children_package_ids.select_related('package_type'):
                if hijo.package_type is not None:
                    peso += float(hijo.package_type.base_weight or 0)
            for quant in self.contained_quant_ids.select_related('product'):
                peso += float(quant.quantity or 0) * float(quant.product.weight or 0)
            return peso

        StockMoveLine = apps.get_model('stock', 'StockMoveLine')
        _por_paquete, todos = self.get_all_children_package_dest_ids()
        for hijo in StockPackage.objects.filter(
                pk__in=todos).exclude(pk=self.pk).select_related('package_type'):
            if hijo.package_type is not None:
                peso += float(hijo.package_type.base_weight or 0)
        lineas = (StockMoveLine.objects
                  .filter(result_package_id__in=todos, picking=picking)
                  .exclude(product__isnull=True)
                  .select_related('product'))
        for linea in lineas:
            peso += float(linea.quantity_product_uom or 0) * float(linea.product.weight or 0)
        return peso

    def has_issues(self) -> bool:
        """≙ ``_has_issues`` (``odoo19c: :472-474``).

        Hay conflicto si sus líneas apuntan a más de una ubicación destino.
        """
        destinos = {l.location_dest_id for l in self.move_line_ids}
        return len(destinos) > 1

    # -- el árbol de destino, recorrido a mano --

    def apply_dest_to_package(self, processed_package_ids=None):
        """≙ ``_apply_dest_to_package`` (``odoo19c: :476-509``).

        Materializa el destino: lo que era ``package_dest`` pasa a ser
        ``parent_package``. Las dos validaciones son de coherencia física —
        un contenedor no puede tener partes en dos ubicaciones, ni recibir
        contenido en una ubicación distinta de la que ya ocupa.
        """
        procesados = set(processed_package_ids or ())
        pendientes = [self] if self.pk not in procesados else []
        if not pendientes:
            return

        contenedor = self.package_dest
        if contenedor is None:
            self.parent_package = None
            self.save(update_fields=['parent_package'])
            procesados.add(self.pk)
        else:
            nueva = self.location
            contenidos = [q for q in contenedor.contained_quant_ids
                          if (q.quantity or 0) != 0]
            ubicaciones = {q.location_id for q in contenidos}
            if contenidos and ubicaciones != {nueva.pk if nueva else None}:
                anteriores = ', '.join(
                    str(q.location) for q in contenidos
                    if q.location_id != (nueva.pk if nueva else None))
                raise UserError(_(
                    'No se puede mover un contenedor con paquetes en otra '
                    'ubicación (%(old_location)s) a una distinta '
                    '(%(new_location)s).') % {
                        'old_location': anteriores, 'new_location': nueva})
            self.parent_package = contenedor
            self.package_dest = None
            self.save(update_fields=['parent_package', 'package_dest'])
            procesados.add(self.pk)

        padre = self.parent_package
        if padre is not None and (padre.package_dest is not None
                                  or padre.parent_package is not None):
            padre.apply_dest_to_package(procesados)

    def get_all_children_package_dest_ids(self):
        """≙ ``_get_all_children_package_dest_ids`` (``odoo19c: :511-531``).

        Todos los paquetes que tienen a éste como destino, recursivamente. Se
        recorre a mano porque el modelo sólo puede materializar **un** árbol,
        y ése lo ocupa ``parent_package``.
        """
        return StockPackage.get_all_children_package_dest_ids_for([self])

    @classmethod
    def get_all_children_package_dest_ids_for(cls, packages):
        """La forma de conjunto — ≙ el mismo método sobre un recordset."""
        def siguientes(actuales):
            ids = {p.pk for p in actuales}
            hijos = list(cls.objects.filter(package_dest__in=actuales))
            if hijos:
                ids |= siguientes(hijos)
            return ids

        todos = {p.pk for p in packages}
        por_paquete = defaultdict(list)
        for paquete in packages:
            hijos = list(cls.objects.filter(package_dest=paquete))
            if hijos:
                descendientes = list(siguientes(hijos))
                todos.update(descendientes)
                por_paquete[paquete.pk] = descendientes
        return por_paquete, todos

    def get_all_package_dest_ids(self):
        """≙ ``_get_all_package_dest_ids`` (``odoo19c: :533-544``).

        Todos los contenedores destino hacia arriba, recursivamente.
        """
        ids = {self.pk}
        actual = self.package_dest
        while actual is not None and actual.pk not in ids:
            ids.add(actual.pk)
            actual = actual.package_dest
        return list(ids)

    def _apply_package_dest_for_entire_packs(self, allowed_package_ids=None):
        """≙ ``_apply_package_dest_for_entire_packs`` (``odoo19c: :546-558``).

        Si al asignar paquetes se añadió un contenedor **completo**, el
        contenedor mismo cuenta como añadido — salvo que sea reutilizable, que
        por definición se vacía y vuelve.
        """
        contenedor = self.parent_package
        if contenedor is not None:
            hermanos = set(contenedor.child_package_ids.values_list('pk', flat=True))
            if hermanos == {self.pk} or hermanos <= {self.pk}:
                permitido = (not allowed_package_ids
                             or contenedor.pk in allowed_package_ids)
                reutilizable = (contenedor.package_type is not None
                                and contenedor.package_type.package_use == 'reusable')
                if permitido and not reutilizable:
                    self.package_dest = contenedor
                    self.save(update_fields=['package_dest'])
        if self.package_dest is not None:
            self.package_dest._apply_package_dest_for_entire_packs(allowed_package_ids)
