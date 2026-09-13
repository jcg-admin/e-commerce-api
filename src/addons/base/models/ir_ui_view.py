"""``ir.ui.view`` — el registro de vistas y su árbol de herencia.

Adaptación de ``odoo/addons/base/models/ir_ui_view.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 3623 líneas — el archivo más grande de
``base``). Una vista es un XML que describe una pantalla; las vistas se
**heredan** entre sí, y el motor las combina aplicando parches ``<xpath/>``
sobre el árbol del padre.

Se porta el **registro y las reglas de herencia**; no el combinador de XML.

Esa divergencia estuvo **sólo en esta prosa** desde que el archivo se portó,
y ningún gate la ve. Desde #76 sus **95 símbolos** están enumerados uno a uno
en ``scripts/divergencias_declaradas.txt`` —70 del combinador, 24 de la API
que sirve el arch, ``NameManager`` entera— cada uno con su motivo. Lo que NO
entró ahí sigue contado como trabajo: ``create``/``write``/``unlink``/
``copy_data``, los cuatro cómputos de ``arch``/``arch_base``, los tres de
``xml_id``/``model_data_id``, los dos de ``model_id``, ``_check_groups`` y
``_check_view_access``.

Esa divergencia cubre también **12 puntos de enganche** que Enterprise 19 usa
sobre este modelo y que aquí no existen —``_get_default_view_domain`` (3),
``_postprocess_attributes``, ``_postprocess_debug``, ``_validate_tag_button``,
``_contains_branded``, ``is_node_branded``, ``_get_x2many_missing_view_archs``,
``_postprocess_access_rights``, ``_is_qweb_based_view``,
``_postprocess_debug_to_cache``—: los diez son del combinador, y operan sobre un
árbol XML que este producto no tiene. No son deuda de porte sino la misma
divergencia vista desde el otro lado. Medido en la tarea #78,
:ref:`h-api-819`.

Qué desbloquea
==============

Cuatro archivos ya portados dejaron anotado que esperaban a éste:

- ``res_groups.py`` — ``view_access``, reverso del M2M de grupos;
- ``res_company.py`` — el diseño de documento externo;
- ``ir_actions.py`` — ``IrActionsActWindowView.view_id``;
- ``ir_model.py`` — ``IrModel.view_ids``;
- ``ir_actions_report.py`` — ``associated_view``.

De esos, **sólo el de ``res_groups`` se cierra solo**: llega por el
``related_name`` del M2M de aquí. Los otros cuatro llevan una columna ``Char``
o una propiedad ausente y su conversión migra su propia tabla; su desenlace es
la tarea **#257**. El criterio que esta frase citaba —``ir_filters.action_id``,
diferido «a su pase»— **ya no existe**: se convirtió en
``base/migrations/0077`` (:ref:`h-api-982`). Sus mediciones sí se corrigen en
este commit (regla de H-API-149).

Las tres reglas de herencia que el registro codifica
====================================================

Sin el combinador, lo que queda es lo que decide **qué vistas se combinan y en
qué orden** — y eso es dato, no XML:

1. **``mode``**: ``extension`` (por defecto) o ``primary``. La diferencia la
   explica la fuente y se conserva verbatim en el ``help_text``: en
   ``extension`` se busca la vista primaria más cercana por ``inherit_id`` y
   se le aplican **todas** las vistas que hereden de ella *con el mismo
   modelo*; en ``primary`` se resuelve la primaria entera —aunque use otro
   modelo— y luego se aplican los parches de ésta.
2. **El orden es ``priority`` y después ``id``**
   (``_get_inheriting_views``). No es cosmético: dos parches sobre el mismo
   nodo se aplican en ese orden y el segundo ve el resultado del primero.
   Cambiarlo produce pantallas distintas sin ningún error.
3. **``active`` filtra antes de combinar**: una vista hija desactivada no
   extiende a su padre, pero sigue existiendo y puede reactivarse. Por eso es
   un booleano y no un borrado.

Y una invariante SQL que **no** es redundante con lo anterior:
``CHECK (mode != 'extension' OR inherit_id IS NOT NULL)``. Una vista en modo
extensión que no extiende a nadie es un parche sin destino — se acepta hoy y
revienta al combinar, lejos de donde se creó.

El combinador — portado en un segundo pase (2026-08-05)
=======================================================

La versión inicial de este módulo NO portaba el combinador, con esta premisa:
*"0 archivos XML en el árbol; las pantallas las declara React"*. La directiva
del ejecutor la supersede (Clausula 1 del principio rector): *"queremos que
nosotros usemos también ``self.env['ir.ui.view']``"* — el registro pasa a ser
el hogar de las **plantillas de reporte** (que emiten el descriptor JSON del
motor de documentos, no HTML), y ``sale_management`` extiende el reporte de
``sale`` **por XPath**, que es exactamente lo que el combinador hace.

Cómo se porta: el motor XPath vive en ``tools/template_inheritance.py``
(espejo de ``odoo/tools/template_inheritance.py``, 346 líneas, lxml puro),
y aquí sólo la **orquestación**: ``get_combined_arch`` / ``_combine`` con el
recorrido en profundidad de la fuente (``ir_ui_view.py:1010-1100``), donde
las extensiones entran por el frente de la cola y las primarias por el final.

Qué NO se porta, con su medición
================================

- **Del combinador**, lo que sirve al editor web y al upgrade de Odoo:
  ``inherit_branding`` (marcado ``data-oe-*``), ``_add_validation_flag``,
  ``NameManager``/``_check_xml`` (validan el XML contra los campos del
  modelo — aquí el arch no describe formularios), ``check_view_ids`` y el
  filtro de vistas cargadas durante upgrade, y ``ir_ui_view_tree_cut_off_view``
  (contexto del editor). El recorrido y la aplicación de specs sí están.
- **``arch`` / ``arch_base`` como campos calculados sobre ``arch_db`` /
  ``arch_fs``**: leen del disco en modo desarrollo y aplican traducción de
  términos XML. Se portan las **columnas** (``arch_db``, ``arch_fs``,
  ``arch_prev``, ``arch_updated``) — que son el dato— y no los cómputos, que
  dependen del lector de archivos y del mecanismo de traducción de Odoo.

  **Portar la columna no basta si nadie la escribe** (#76, :ref:`h-api-836`).
  ``arch_prev`` estuvo aquí como columna y **sin un solo escritor**, mientras
  ``ResetViewArchWizard.source_arch_for(view, 'soft')`` la leía: el reinicio
  suave devolvía siempre la cadena vacía, que se lee como *"no había nada
  previo"*. Ahora la escriben ``save`` —≙ ``create:626`` y ``write:657-658``,
  los dos únicos sitios que la fuente toca— y la limpia ``reset_arch``.
- **``get_view_arch_from_file``** y ``_hasclass``: lectura de la vista desde
  su archivo fuente y una extensión XPath. Ambos son del combinador.
- **``xml_id`` / ``model_data_id``**: dependen de ``ir.model.data``. ``key``
  **sí** se porta: es el identificador estable de una vista QWeb y no pasa por
  esa tabla. (La tabla ya tiene resolutor — ``IrModelData._xmlid_lookup`` y
  hermanos, :ref:`h-api-347` — y la resolución de plantillas de abajo lo usa
  como segundo escalón, igual que la fuente.)

Resolución de plantillas — sin caché, y es una decisión
=======================================================

``_get_template_view`` / ``_get_cached_template_info`` (fuente
``base/models/ir_ui_view.py:1120-1285``) se portan **sin** el
``@tools.ormcache(..., cache='templates')`` de la fuente. Gunicorn corre
prefork síncrono con 4 workers (``setup/gunicorn.conf.py``) y no hay
invalidación compartida entre procesos: un caché por-proceso de contenido
**mutable** (las vistas se editan y se archivan en caliente) serviría vistas
viejas en 3 de 4 workers tras cada edición, sin error que lo delatara. La
fuente puede permitírselo porque su registry invalida el ormcache en cada
``write`` **y lo señala a los demás procesos**; aquí sólo existe la primera
mitad, así que el desenlace correcto es resolver contra la base en cada
llamada.

.. note:: Corregido 2026-08-31 (:ref:`h-api-980`) — esta razón decía *«este
   árbol no tiene ese mecanismo»*, y de las dos mitades sólo una era cierta.

   **La invalidación local SÍ existe**: ``registry.clear_cache(*nombres)``
   (``orm/registry.py:121``), portada de ``Registry.clear_cache``, y
   ``res_groups.py`` la usa en tres sitios como invalidador de su caché
   ``groups``.

   **La señalización entre procesos NO**: ``signal_changes`` /
   ``check_signaling`` (``odoo19c: odoo/orm/registry.py:1076-1140``) escriben
   y leen una secuencia por caché en tablas ``orm_signaling_<nombre>``, y de
   eso hay **0** en este árbol. Medido con un ``grep -rn`` sobre ``src/`` y
   ``addons/`` de los cinco símbolos —``signal_changes``, ``check_signaling``,
   ``orm_signaling``, ``cache_sequences``, ``get_sequences``—, cuyo único
   acierto es la declinación que ``ir_autovacuum.py`` ya declara.

   Con ``workers = 4`` (``setup/gunicorn.conf.py:93``), esa mitad ausente es
   la que hace que un caché de contenido mutable sirva vistas viejas en 3 de 4
   procesos. La conclusión de este bloque **no cambia** por la corrección: sin
   la segunda mitad, no adoptar la caché sigue siendo lo correcto. Lo que
   cambia es que la razón ahora nombra qué falta y qué no, que es lo que
   permite cerrarla — la tarea **#256**.

Consecuencias declaradas:

- ``_get_template_minimal_cache_keys`` **no se porta**: su único consumidor es
  la clave del decorador retirado.
- ``_clear_preload_views_cache_if_needed`` **no se porta**: invalida el memo
  por-cursor (``cr.cache['_compile_batch_']``) que aquí no existe.
- ``_preload_views`` se porta como resolutor puro, sin el memo por-transacción.
- **``warning_info`` / ``invalid_locators``**: diagnósticos que el editor de
  vistas de Odoo muestra al validar el XML; sin combinador no hay qué validar.
- **``ResetViewArchWizard._compute_arch_diff``**: compone un diff HTML entre
  dos versiones del XML. El asistente **sí** se porta —los tres modos de
  reinicio son la decisión, y ésa es dato— sin el generador del diff.
"""
import collections
import logging

from lxml import etree

import fields
import models
from django.apps import apps
from django.core.exceptions import ValidationError
from exceptions import MissingError
from orm.environments import get_context
from tools.template_inheritance import apply_inheritance_specs

from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)

#: Atributos de marcado que el editor en línea mueve con el nodo — verbatim.
MOVABLE_BRANDING = [
    'data-oe-model', 'data-oe-id', 'data-oe-field', 'data-oe-xpath',
    'data-oe-source-id',
]

#: Los cuatro modificadores que una vista puede declarar sobre un campo.
VIEW_MODIFIERS = ('column_invisible', 'invisible', 'readonly', 'required')

#: El octavo tipo de vista **NO copia el valor de la fuente**, y es la única
#: divergencia de los ocho: donde ``odoo19c: base/models/ir_ui_view.py:120``
#: escribe ``('qweb', 'QWeb')``, aquí se escribe
#: ``('template', 'Plantilla')`` (DEC-FW-05, pieza 5 de 8).
#:
#: **Por qué diverge.** Los otros siete nombran *qué es* la vista —lista,
#: formulario, gráfica, tabla dinámica, calendario, kanban, búsqueda—. El
#: octavo nombraba *su intérprete*. Es el mismo par (intérprete, cosa) que
#: ``report_type`` ya resolvió en ``ir_actions_report.py:146-152``: allí el
#: prefijo ``qweb-`` se retiró porque *"afirmaría un sustrato que este árbol
#: no tiene"*. Aquí el par no tiene segundo término: el valor **era** el
#: intérprete y nada más.
#:
#: **Por qué ``template`` y no otra palabra — no se inventa.** Es el nombre
#: que la propia referencia usa en la superficie que un humano escribe: su
#: azúcar XML es ``<template id="...">``, con manejador ``_tag_template``
#: (``odoo19c: odoo/tools/convert.py:469,655``), y sólo el valor almacenado
#: dice ``qweb``. Nuestro ``tools/convert.py`` hace la misma sustitución. El
#: renombre no cambia el concepto: alinea el dato con el nombre que la fuente
#: ya le da donde se escribe.
#:
#: **Qué es este tipo, medido por sus tres consumidores** — es el único que:
#: (a) el registro de vistas del cliente **excluye** (``addons/web``, porque
#: no es una vista que el cliente dibuje); (b) **exige clave**, porque se
#: resuelve por clave y no por (modelo, tipo) — la restricción de abajo; y
#: (c) puede llevar contraseña de visibilidad en ``addons/website``, porque
#: es una página servida. Los tres describen lo mismo: una **plantilla de
#: documento**, no una disposición de interfaz.
#:
#: **Lo que el stack aporta para hacerlo** (criterio de las dos categorías):
#: TRAE el mecanismo entero y no hay nada que construir — ``choices`` del
#: ``CharField``, ``AlterField`` y ``RunPython`` para renombrar el dato ya
#: guardado, y ``CheckConstraint`` para la restricción. El renombre es
#: cableado, no construcción; por eso su costo no es argumento para
#: conservar el valor viejo.
VIEW_TYPE_TEMPLATE = 'template'
VIEW_TYPE_CHOICES = [
    ('list', 'Lista'),
    ('form', 'Formulario'),
    ('graph', 'Gráfica'),
    ('pivot', 'Tabla dinámica'),
    ('calendar', 'Calendario'),
    ('kanban', 'Kanban'),
    ('search', 'Búsqueda'),
    (VIEW_TYPE_TEMPLATE, 'Plantilla'),
]

MODE_PRIMARY = 'primary'
MODE_EXTENSION = 'extension'
#: ``mode`` — ver el docstring del módulo sobre la diferencia entre los dos.
MODE_CHOICES = [
    (MODE_PRIMARY, 'Vista base'),
    (MODE_EXTENSION, 'Vista de extensión'),
]

RESET_SOFT = 'soft'
RESET_HARD = 'hard'
RESET_OTHER_VIEW = 'other_view'
#: Los tres modos de reinicio del asistente, verbatim.
RESET_MODE_CHOICES = [
    (RESET_SOFT, 'Restaurar la versión anterior (reinicio suave).'),
    (RESET_HARD, 'Reiniciar a la versión del archivo (reinicio duro).'),
    (RESET_OTHER_VIEW, 'Reiniciar a partir de otra vista.'),
]


class IrUiView(models.DefaultGetMixin, TimeStampedModel):
    """``ir.ui.view`` — una vista y su lugar en el árbol de herencia."""

    _name = 'ir.ui.view'
    _description = 'View'
    _order = "priority,name,id"
    _allow_sudo_commands = False

    name = fields.Char(max_length=255, verbose_name='Nombre de la vista')
    model = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Modelo',
        help_text='Modelo técnico que la vista muestra. Char plano, mismo '
                  'criterio que ir_rule.model_name.',
    )
    key = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Clave',
        help_text='Identificador estable de una vista QWeb. NO pasa por '
                  'ir.model.data, por eso sí se porta.',
    )
    priority = fields.Integer(
        default=16, verbose_name='Secuencia',
        help_text='Orden de aplicación entre vistas hermanas. Menor = antes. '
                  'Ver el docstring del módulo: el orden cambia el resultado.',
    )
    type = fields.Selection(
        max_length=16, choices=VIEW_TYPE_CHOICES, blank=True, default='',
        verbose_name='Tipo de vista')
    arch_db = fields.Text(
        blank=True, default='', verbose_name='Arquitectura',
        help_text='El XML de la vista. Este archivo NO lo interpreta.')
    arch_fs = fields.Char(
        max_length=512, blank=True, default='',
        verbose_name='Archivo de origen',
        help_text='Archivo del que procede la vista; sirve para el reinicio '
                  'duro.',
    )
    arch_updated = fields.Boolean(
        default=False, verbose_name='Arquitectura modificada',
        help_text='Marcado, la vista se editó tras cargarse del archivo.')
    arch_prev = fields.Text(
        blank=True, default='', verbose_name='Arquitectura anterior',
        help_text='Copia del arch_db antes de la última escritura; sirve para '
                  'el reinicio suave.',
    )
    inherit_id = fields.Many2one(
        'self', on_delete=models.PROTECT, null=True, blank=True, db_index=True,
        related_name='inherit_children_ids', verbose_name='Vista heredada',
        help_text='ondelete restrict de la fuente: no se borra una vista de '
                  'la que otras heredan.',
        db_column='inherit_id',
    )
    groups = fields.Many2many(
        ResGroups, blank=True, db_table='ir_ui_view_group_rel',
        related_name='view_access', verbose_name='Grupos',
        help_text='Vacío = la vista aplica a todos. Con valor, sólo a los '
                  'usuarios de esos grupos. Este related_name es el '
                  'view_access que res_groups.py dejó anotado como pendiente.',
    )
    mode = fields.Selection(
        max_length=16, choices=MODE_CHOICES, default=MODE_PRIMARY,
        verbose_name='Modo de herencia',
        help_text='Sólo aplica si la vista hereda de otra. En extensión se '
                  'busca la primaria más cercana y se le aplican todas las '
                  'vistas que hereden de ella con el mismo modelo; en '
                  'primaria se resuelve la primaria entera —aunque use otro '
                  'modelo— y luego se aplican los parches de ésta.',
    )
    active = fields.Boolean(
        default=True, verbose_name='Activa',
        help_text='Si la vista es heredada: activa extiende siempre a su '
                  'padre; inactiva no lo extiende hoy pero puede reactivarse.',
    )

    class Meta:
        db_table = 'ir_ui_view'
        ordering = ['priority', 'name', 'id']
        verbose_name = 'Vista'
        verbose_name_plural = 'Vistas'
        constraints = [
            # ``_inheritance_mode``: una vista en modo extensión tiene que
            # extender a alguien, o es un parche sin destino.
            models.CheckConstraint(
                condition=(
                    ~models.Q(mode=MODE_EXTENSION)
                    | models.Q(inherit_id__isnull=False)
                ),
                name='ir_ui_view_inheritance_mode',
            ),
            # ``_qweb_required_key``: una vista de plantilla necesita su
            # clave — es el único tipo que se resuelve por clave.
            models.CheckConstraint(
                condition=~models.Q(type=VIEW_TYPE_TEMPLATE) | ~models.Q(key=''),
                name='ir_ui_view_template_required_key',
            ),
        ]
        indexes = [
            # ``_model_type_inherit_id``.
            models.Index(fields=['model', 'inherit_id'],
                         name='ir_ui_view_model_inherit'),
        ]

    def _check_groups(self):
        """Una vista heredada no declara grupos en el registro.

        ≙ ``_check_groups`` (``odoo19c: ir_ui_view.py:537-543``), su
        ``@api.constrains('group_ids')`` — que aquí es el campo ``groups``,
        el nombre que este árbol le dio al M2M. Los grupos de una vista **de
        extensión** van dentro del propio arch, en el atributo ``groups=`` del
        nodo: declararlos en el registro los aplicaría a la vista entera, no al
        fragmento que la extensión aporta, que es lo contrario de lo que quien
        los escribe pretende.

        DIVERGENCIA DE ENLACE, la del archivo: allá es un ``@api.constrains``
        que el ORM dispara al escribir; aquí lo llama
        ``ResGroups._check_inherited_view_groups`` —su otro llamador en la
        fuente— y se puede invocar a mano.
        """
        if self.groups.exists() and self.inherit_id_id and self.mode != 'primary':
            raise ValidationError(
                "Una vista heredada no puede declarar 'groups' en el registro. "
                "Use el atributo 'groups' dentro de la definición de la vista.")

    def __str__(self):
        return self.name

    def clean(self):
        """``_check_000_inheritance`` — no se admiten herencias recursivas.

        La fuente comenta que este chequeo va **antes** que los demás para no
        entrar en bucle infinito al combinar; aquí el orden lo da que sea lo
        primero de ``clean``.
        """
        super().clean()
        seen = set()
        node = self.inherit_id
        while node is not None:
            if node.pk == self.pk or node.pk in seen:
                raise ValidationError(
                    'No se pueden crear vistas heredadas recursivas.')
            seen.add(node.pk)
            node = node.inherit_id

    def save(self, *args, from_file=False, save_prev=True, **kwargs):
        """≙ ``create:626`` + ``write:640-658`` — el ciclo de vida del arch.

        La fuente reparte en dos metodos lo que aqui hace uno, y lo que hacen
        son tres cosas:

        #. **La copia previa** — ``arch_prev`` guarda el ``arch_db`` que habia
           antes de esta escritura. Al crear, la fuente la fija al arch que
           entra (``:626``); al escribir, al que estaba en la base
           (``:657-658``).
        #. **La marca de editado** — ``arch_updated`` distingue *"lo edito una
           persona"* de *"lo trajo el archivo"*. La fuente lo decide por la
           presencia de ``install_filename`` en su contexto; aqui por el
           argumento ``from_file``, que es el mismo dato sin contexto global.
        #. **La limpieza** — las personalizaciones de ``ir.ui.view.custom``
           mueren con cada escritura, *"otherwise not all users would see the
           updated views"* (``:650-653``, comentario verbatim).

        ``save_prev=False`` ≙ ``no_save_prev`` de la fuente: se usa al
        reiniciar, donde el arch que se descarta esta roto y guardarlo como
        copia lo dejaria como unico destino del proximo reinicio.

        **Por que hacia falta.** ``arch_prev`` era una columna que nadie
        escribia, y ``ResetViewArchWizard.source_arch_for(view, 'soft')`` la
        leia: el reinicio suave devolvia siempre la cadena vacia, que se lee
        como *"no habia nada previous"*. Misma forma que :ref:`h-api-833`.

        **Divergencia declarada:** la fuente escribe ``arch_prev`` tambien
        desde ``arch`` y ``arch_base``, sus dos campos calculados con
        traduccion. Aqui el unico dato es ``arch_db`` —la traduccion por campo
        no se porta, ver el docstring del modulo—, asi que la copia se toma de
        el.
        """
        is_new = self.pk is None
        previous = None
        if not is_new:
            previous = (type(self).objects.filter(pk=self.pk)
                        .values_list('arch_db', flat=True).first())

        the_arch_changes = is_new or (previous is not None
                                      and previous != self.arch_db)

        if is_new:
            self.arch_prev = self.arch_db or ''
        elif the_arch_changes and save_prev:
            self.arch_prev = previous or ''

        if the_arch_changes and not is_new and not from_file:
            self.arch_updated = True

        result = super().save(*args, **kwargs)
        # La fuente las borra en CADA write, no solo cuando cambia el arch.
        IrUiViewCustom.objects.filter(ref_id=self.pk).delete()
        return result

    def reset_arch(self, mode=RESET_SOFT, arch=None):
        """≙ ``reset_arch`` (``:281-293``) — vuelve al arch anterior o al del archivo.

        - ``soft`` — de ``arch_prev``. Si esta vacio no hace nada, como la
          fuente: su ``if arch:`` protege de reiniciar a la nada.
        - ``hard`` — del archivo de origen. **La lectura del disco no vive
          aqui**: este arbol no tiene el cargador de addons de la referencia,
          asi que el arch leido entra por el argumento ``arch`` y la
          **decision** —que columnas se tocan— se conserva verbatim:
          ``arch_prev`` a vacio y ``arch_updated`` a falso. Es la misma
          frontera que ``ResetViewArchWizard.source_arch_for``, que para el
          modo duro devuelve la RUTA y no el contenido.

        Devuelve ``True`` si hubo reinicio y ``False`` si no habia a que
        volver — la fuente no devuelve nada y decide por el mismo ``if``.
        """
        if mode == RESET_SOFT:
            if not self.arch_prev:
                return False
            self.arch_db = self.arch_prev
        elif mode == RESET_HARD:
            if not (self.arch_fs and arch):
                return False
            self.arch_db = arch
            self.arch_prev = ''
            self.arch_updated = False
        else:
            raise ValidationError(f'Modo de reinicio desconocido: {mode!r}.')
        self.save(save_prev=False, from_file=(mode == RESET_HARD))
        return True

    @classmethod
    def default_view(cls, model, view_type):
        """≙ ``default_view`` — la primaria de menor prioridad del par.

        Su docstring de la fuente, verbatim: *"Fetches the default view for the
        provided (model, view_type) pair: primary view with the lowest
        priority"*.

        El filtro ``mode='primary'`` de ``_get_default_view_domain`` es lo que
        hace la funcion: sin el, una vista de **extension** con prioridad menor
        ganaria, y una extension no es una pantalla — es un parche sobre otra.

        Devuelve el ``pk``, o ``None`` si no hay ninguna. La fuente devuelve
        ``False``; aqui el ausente de una consulta es ``None``, que es lo que
        el resto del arbol comprueba.
        """
        return (cls.objects
                .filter(model=model, type=view_type, mode=MODE_PRIMARY)
                .order_by('priority', 'name', 'id')
                .values_list('pk', flat=True).first())

    @property
    def root_view(self):
        """La vista primaria más cercana subiendo por ``inherit_id``.

        Es el punto de partida de la combinación en modo ``extension``.
        Devuelve ``self`` si ya es primaria.
        """
        node = self
        while node.mode == MODE_EXTENSION and node.inherit_id is not None:
            node = node.inherit_id
        return node

    def inheriting_views(self, include_inactive=False):
        """``_get_inheriting_views`` — las vistas que extienden a ésta.

        Recorrido transitivo, **ordenado por ``priority`` y luego ``id``** —
        ver el docstring del módulo: ese orden decide el resultado de la
        combinación, no sólo su presentación.

        Las condiciones de la fuente que se conservan: sólo hereda quien
        declara ``mode='extension'``, y sólo si su ``model`` **coincide** con
        el del padre (``coalesce(model,'') = coalesce(parent.model,'')``); una
        extensión sobre otro modelo no entra en esta rama.
        """
        collected = []
        seen = {self.pk}
        frontier = [self]
        manager = type(self).objects
        while frontier:
            parent_ids = [view.pk for view in frontier]
            children = manager.filter(
                inherit_id__in=parent_ids, mode=MODE_EXTENSION,
            ).order_by('priority', 'id')
            if not include_inactive:
                children = children.filter(active=True)
            frontier = []
            for child in children:
                if child.pk in seen:
                    continue
                # ``coalesce(model,'') = coalesce(parent.model,'')`` — un
                # ``model`` vacío casa con otro vacío, no con cualquiera.
                if (child.model or '') != (child.inherit_id.model or ''):
                    continue
                seen.add(child.pk)
                collected.append(child)
                frontier.append(child)
        return collected

    # ------------------------------------------------------------------ #
    #  El combinador — ``get_combined_arch`` (fuente ``:1010-1100``)      #
    # ------------------------------------------------------------------ #

    def apply_inheritance_specs(self, source, specs_tree, pre_locate=None):
        """``apply_inheritance_specs`` (fuente ``:944``) — delega en el motor.

        El trabajo real vive en ``tools/template_inheritance`` (lxml puro);
        aquí sólo se le pone nombre de vista al error, que es lo que la
        fuente hace con ``_raise_view_error``.
        """
        try:
            return apply_inheritance_specs(source, specs_tree,
                                           pre_locate=pre_locate)
        except ValueError as e:
            raise ValidationError(
                f'Error al aplicar la herencia de la vista {self.name!r}: {e}'
            ) from e

    def _get_hierarchy(self):
        """Mapa ``pk del padre -> [vistas hijas]`` del árbol de ``self``.

        Réplica de ``get_hierarchy`` (fuente ``:1086-1092``) sin la parte de
        upgrade: se recorren las heredantes activas (misma condición de
        modelo que ``inheriting_views``) y una hija **primaria** corta la
        rama — sus parches se aplican al resolverla a ella, no al padre.
        """
        hierarchy = collections.defaultdict(list)
        for view in self.inheriting_views():
            hierarchy[view.inherit_id_id].append(view)
        return hierarchy

    def _combine(self, hierarchy):
        """``_combine`` (fuente ``:971-1041``) — recorrido en profundidad.

        La cola se recorre de izquierda a derecha; tras procesar una vista,
        sus hijas entran por la **izquierda** (así se recorren en orden — la
        cola funciona casi como pila). La excepción son las vistas
        *primarias*, que entran por la derecha: se aplican después de todas
        las extensiones. Verbatim de la fuente, sin branding ni flags de
        validación (ver el docstring del módulo).
        """
        assert self.mode == MODE_PRIMARY
        combined_arch = etree.fromstring(self.arch_db)

        # ``sorted(..., key=mode)``: 'extension' < 'primary' — las
        # extensiones directas se procesan antes que las primarias hijas.
        queue = collections.deque(
            sorted(hierarchy.get(self.pk, []), key=lambda v: v.mode))
        while queue:
            view = queue.popleft()
            arch = etree.fromstring(view.arch_db or '<data/>')
            combined_arch = view.apply_inheritance_specs(combined_arch, arch)

            for child_view in reversed(hierarchy.get(view.pk, [])):
                if child_view.mode == MODE_PRIMARY:
                    queue.append(child_view)
                else:
                    queue.appendleft(child_view)

        return combined_arch

    def _get_combined_arch(self):
        """La arquitectura de ``self`` (etree) combinada con sus heredantes.

        En modo ``extension`` la combinación parte de la primaria más
        cercana (``root_view``) — fuente ``:1051-1060``, el ascenso por
        ``inherit_id``.
        """
        return self.root_view._combine(self.root_view._get_hierarchy())

    def get_combined_arch(self):
        """La arquitectura combinada, como string (fuente ``:1043``)."""
        return etree.tostring(self._get_combined_arch(), encoding='unicode')

    # ------------------------------------------------------------------ #
    #  Resolución de plantillas (fuente ``:1120-1285``) — sin caché,     #
    #  ver el docstring del módulo por qué.                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_cached_template_prefetched_keys(cls):
        """Campos que ``_get_cached_template_info`` publica (fuente ``:1122``).

        La extensión de ``website`` en la fuente suma ``visibility`` y
        ``track``; aquí se conserva como punto de extensión por ``super()``.
        """
        return ['id', 'key', 'active']

    @classmethod
    def _get_template_domain(cls, xmlids):
        """``_get_template_domain`` (fuente ``:1169``) — vistas por ``key``.

        Devuelve un ``Q`` en lugar del ``Domain`` de la fuente; la extensión
        de ``website`` lo estrecha con ``website_id`` vía ``super()``.
        """
        return models.Q(key__in=list(xmlids))

    @classmethod
    def _get_template_order(cls):
        """``_get_template_order`` (fuente ``:1173``) — ``"priority, id"``.

        Divergencia de forma declarada: la fuente devuelve la cadena SQL del
        ``order`` y aquí se devuelve la tupla que consume ``order_by``.
        """
        return ('priority', 'id')

    @classmethod
    def _fetch_template_views(cls, ids_or_xmlids):
        """``_fetch_template_views`` (fuente ``:1177-1240``).

        Resuelve cada referencia —id entero o ``xmlid``/``key``— a su vista, y
        las ausentes a un ``MissingError``. Dos escalones, como la fuente:

        1. Búsqueda por ``key`` (o id) ordenada por ``_get_template_order``;
           entre vistas con la misma ``key`` gana la primera del orden — la de
           menor ``priority``.
        2. Las ``xmlid`` con punto que no aparecieron se buscan en
           ``ir.model.data``. La fuente consulta ``model = 'ir.ui.view'``;
           aquí la tabla guarda la etiqueta de Django (es lo que escribe
           ``IrModelData.set_xmlid``), así que se consulta por
           ``cls._meta.label``.

        Divergencias declaradas:

        - La fuente empuja cada resultado al ormcache
          (``_get_cached_template_info(key, _view=view)``); sin caché ese
          bucle no tiene efecto y no se porta.
        - El ``try/except MissingError`` alrededor de ``view.key`` protege a
          su ``browse`` perezoso de ids borrados; ``filter`` sólo devuelve
          filas existentes y no lo necesita.
        - ``ir.model.data`` se importa por el registro de apps, no por
          ``import``: ``ir_model.py:144`` ya importa este módulo (ciclo real
          medido — excepción 3 de ``no-lazy-imports.md``).
        """
        ids = [ref for ref in ids_or_xmlids if isinstance(ref, int)]
        xmlids = [ref for ref in ids_or_xmlids if not isinstance(ref, int)]

        view_by_id = {}
        if xmlids:
            domain = models.Q(id__in=ids) | cls._get_template_domain(xmlids)
            views = cls.objects.filter(domain).order_by(
                *cls._get_template_order())
            # ``search`` de la fuente respeta ``active_test`` del contexto:
            # con el valor por defecto las archivadas no se resuelven por
            # ``key``; ``viewref``/``is_view_active`` entran con
            # ``active_test=False`` para verlas.
            if get_context().get('active_test', True):
                views = views.filter(active=True)
        else:
            views = cls.objects.filter(id__in=ids)

        for view in views:
            if view.key in view_by_id:
                # Conserva las vistas según su orden de prioridad.
                continue
            view_by_id[view.id] = view
            if view.key:
                view_by_id[view.key] = view

        # Segundo escalón: ``xmlid`` ausentes, vía ``ir.model.data``.
        missing_xmlid_views = [
            xmlid for xmlid in xmlids
            if '.' in xmlid and xmlid not in view_by_id]
        if missing_xmlid_views:
            data_model = apps.get_model('base', 'IrModelData')
            domain = models.Q(pk__in=[])
            for xmlid in missing_xmlid_views:
                module, _, name = xmlid.partition('.')
                domain |= models.Q(module=module, name=name)
            rows = data_model.objects.filter(domain, model=cls._meta.label)
            for model_data in rows:
                view = cls.objects.filter(pk=model_data.res_id).first()
                if view is not None:
                    view_by_id[view.id] = view
                    xmlid = f'{model_data.module}.{model_data.name}'
                    view_by_id[xmlid] = view
                    if view.key:
                        view_by_id[view.key] = view

        # Lo que no se resolvió sale como error, no como hueco silencioso.
        for view_id in ids:
            if view_id not in view_by_id:
                view_by_id[view_id] = MissingError(
                    'La plantilla no existe o fue eliminada: %s' % view_id)
        for xmlid in xmlids:
            if xmlid not in view_by_id:
                view_by_id[xmlid] = MissingError(
                    "Plantilla no encontrada: '%s'" % xmlid)
        return view_by_id

    @classmethod
    def _preload_views(cls, refs):
        """``_preload_views`` (fuente ``:1247-1285``), sin el memo.

        La fuente memoiza por transacción en
        ``cr.cache['_compile_batch_']`` (y lo invalida con
        ``_clear_preload_views_cache_if_needed``); aquí no hay caché de
        cursor y el memo no se porta — cada llamada resuelve contra la base.
        La forma del resultado se conserva verbatim:
        ``{ref: {'xmlid', 'ref', 'view', 'error'}}``.
        """
        refs = [
            int(ref) if isinstance(ref, int) or ref.isdigit() else ref
            for ref in refs]
        batch = {}
        wanted = [ref for ref in refs if ref]
        if not wanted:
            return batch

        unknown_views = cls._fetch_template_views(wanted)

        for id_or_xmlid, view in unknown_views.items():
            if isinstance(view, models.Model):
                batch[view.id] = batch[id_or_xmlid] = {
                    'xmlid': view.key or id_or_xmlid,
                    'ref': view.id,
                    'view': view,
                    'error': False,
                }
            else:
                batch[id_or_xmlid] = {
                    'xmlid': id_or_xmlid,
                    'view': None,
                    'ref': None,
                    'error': view,  # MissingError
                }
        return batch

    @classmethod
    def _get_cached_template_info(cls, id_or_xmlid, _view=None):
        """``_get_cached_template_info`` (fuente ``:1130-1160``).

        Devuelve el dict ``{'id', 'key', 'active', 'error'}`` de la vista que
        la referencia designa. A pesar del nombre —que se conserva por
        fidelidad— **aquí no cachea**: ver el docstring del módulo.

        ``_view`` es el atajo de la fuente para poblar el resultado con una
        vista ya resuelta (``_view=False`` marca "ausente conocida": campos
        ``None`` y ``error`` falso, verbatim de la fuente).

        Divergencia declarada: la rama entera de la fuente atrapa además
        ``UserError`` del control de acceso de su ``browse``; la consulta
        directa por pk de este árbol no pasa por record rules y esa rama no
        tiene equivalente.
        """
        view = None
        error = False
        if _view is not None:
            view = _view
        elif isinstance(id_or_xmlid, int):
            view = cls.objects.filter(pk=id_or_xmlid).first()
            if view is None:
                error = MissingError(
                    "Plantilla no encontrada: '%s'" % id_or_xmlid)
        else:
            preload = cls._preload_views([id_or_xmlid])
            if id_or_xmlid in preload:
                info = preload[id_or_xmlid]
                view = info['view']
                error = info['error']
            else:
                # Verbatim de la fuente — cubre la referencia vacía y la
                # cadena de dígitos, que el preload reindexa como entero.
                error = SyntaxError('Error compiling template')
        info = {
            f: getattr(view, f) if view else None
            for f in cls._get_cached_template_prefetched_keys()}
        info['error'] = error
        return info

    @classmethod
    def _get_template_view(cls, id_or_xmlid, raise_if_not_found=True):
        """``_get_template_view`` (fuente ``:1162-1166``).

        La vista que designa ``id_or_xmlid`` (id entero, ``key`` o ``xmlid``).
        Divergencia declarada: la fuente devuelve un recordset —vacío cuando
        no hay vista y no se pide levantar—; aquí ese vacío es ``None``.
        """
        info = cls._get_cached_template_info(id_or_xmlid)
        if info['error'] and raise_if_not_found:
            raise info['error']
        if info['id'] is None:
            return None
        return cls.objects.filter(pk=info['id']).first()


class IrUiViewCustom(TimeStampedModel):
    """``ir.ui.view.custom`` — la personalización de una vista por un usuario.

    ``_order = 'create_date desc, id desc'`` en la fuente, con el comentario
    que explica por qué: *"search(limit=1) should return the last
    customization"*. Se conserva el orden descendente por creación, porque un
    orden ascendente devolvería la personalización **más vieja** al pedir una
    sola — un fallo silencioso en el que la vista guardada nunca se ve.
    """

    _name = 'ir.ui.view.custom'
    _description = 'Custom View'
    _order = 'create_date desc, id desc'  # search(limit=1) should return the last customization
    _rec_name = 'user_id'
    _allow_sudo_commands = False

    ref_id = fields.Many2one(
        IrUiView, on_delete=models.CASCADE, db_index=True,
        related_name='custom_ids', verbose_name='Vista original',
        db_column='ref_id',
    )
    user = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, db_index=True,
        related_name='custom_views', verbose_name='Usuario')
    arch = fields.Text(verbose_name='Arquitectura de la vista')

    class Meta:
        db_table = 'ir_ui_view_custom'
        ordering = ['-created_at', '-id']
        verbose_name = 'Vista personalizada'
        verbose_name_plural = 'Vistas personalizadas'
        indexes = [
            # ``_user_id_ref_id``.
            models.Index(fields=['user', 'ref_id'],
                         name='ir_ui_view_custom_user_ref'),
        ]

    def __str__(self):
        return f'{self.ref_id_id} / {self.user_id}'


class ResetViewArchWizard(models.Model):
    """``reset.view.arch.wizard`` — comparar y reiniciar la vista.

    Transitorio en la fuente; abstracto aquí, como el resto de asistentes que
    este árbol porta. Lo que aporta es la **decisión de los tres modos**, que
    es dato; el diff HTML entre versiones no se porta (ver el docstring del
    módulo).
    """

    _name = 'reset.view.arch.wizard'
    _description = "Reset View Architecture Wizard"

    class Meta:
        abstract = True

    @staticmethod
    def source_arch_for(view, reset_mode, compare_view=None):
        """De dónde sale el XML con el que se reinicia, según el modo.

        - ``soft``: de ``arch_prev``, la copia previa a la última escritura;
        - ``hard``: del archivo de origen (``arch_fs``) — **no** se lee aquí,
          se devuelve la ruta para que lo haga quien tenga el disco;
        - ``other_view``: del ``arch_db`` de la vista con la que se compara.

        Devuelve ``(origen, valor)`` para que el llamador sepa **qué** recibió
        y no tenga que adivinarlo por el contenido.
        """
        if reset_mode == RESET_SOFT:
            return ('arch_prev', view.arch_prev)
        if reset_mode == RESET_HARD:
            return ('arch_fs', view.arch_fs)
        if reset_mode == RESET_OTHER_VIEW:
            if compare_view is None:
                raise ValidationError(
                    'El modo "otra vista" requiere una vista de comparación.')
            return ('arch_db', compare_view.arch_db)
        raise ValidationError(f'Modo de reinicio desconocido: {reset_mode!r}.')

    @staticmethod
    def check_comparable(views):
        """``default_get`` — no se comparan más de dos vistas."""
        if len(views) > 2:
            raise ValidationError('No se pueden comparar más de dos vistas.')
        return True
