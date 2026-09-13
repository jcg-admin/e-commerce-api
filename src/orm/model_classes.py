"""Construcción de clases de modelo — fiel a ``odoo/orm/model_classes.py`` (Odoo 19).

En Odoo este módulo es la maquinaria que, al cargar los addons, **fusiona** las
definiciones de un mismo ``_name`` (herencia por ``_inherit``) en una sola clase
registrada, resuelve los campos, y las inserta en el ``Registry``
(``add_to_registry``, ``setup_model_classes``, ``add_field``, ``pop_field``). Es
el corazón del sistema de herencia de Odoo.

Mapeo a Django — **Django ya tiene su propia maquinaria de construcción de
clases**: la metaclase ``ModelBase`` procesa cada ``class X(models.Model)`` al
importarla (resuelve campos, ``Meta``, herencia) y la registra en ``apps``. Por
eso este archivo es un stub delgado documentado:

=====================================  ==================================================
Odoo ``model_classes``                 Equivalente Django
=====================================  ==================================================
metaclase que arma la clase            ``django.db.models.base.ModelBase``
``add_to_registry(...)`` (``:152``)    registro automático de ``ModelBase`` en ``apps``
``setup_model_classes(env)`` (``:301``)  import de ``models/`` + ``apps.populate()``
``_inherit`` = *extensión* (fusiona    intra-app: herencia Python (abstract base /
definiciones del mismo ``_name``,      multi-table); cross-app: **FK RELATED**
o del padre, en una clase por MRO)     (DEC-SALE-01) — no hay fusión por ``_name``
``_inherits`` = *delegación* (Many2one  ``OneToOneField``/FK + delegación por
delegate required, ondelete cascade;   ``property`` (o multi-table inheritance) —
``_check_inherits`` ``:465``)          composición, no fusión de clase
``add_field`` / ``pop_field``          declaración de campos en la clase +
                                       ``contribute_to_class`` de ``ModelBase``
``is_model_class`` / ``is_model_def``  ``issubclass(x, models.Model)`` /
                                       ``not x._meta.abstract``
=====================================  ==================================================

Validación del bloque de comentarios de Odoo (``model_classes.py:32-138``,
PROVEN verbatim en la fuente 19) y su mapeo — los comentarios son **correctos** y
describen el mecanismo real (el código bajo ellos, ``:152+``, lo implementa). Tres
conceptos y por qué en Django divergen:

1. **"model definitions" vs "model classes".** En Odoo la *definición* es la
   clase estática del código del módulo; la *model class* del ``Registry`` se
   construye **dinámicamente al armar el registro**, heredando (en orden inverso,
   para respetar el override) de TODAS las definiciones del mismo ``_name`` — su
   MRO se calcula ahí. En Django **no existe esa dualidad**: ``ModelBase``
   construye la clase **una vez, al importar** (estática), y esa misma clase es la
   del registro (``apps``). No hay "definición" separada de "clase de registro".

2. **Fusión por ``_name`` (A1+A2+A3 → una clase ``a``).** Es la mayor divergencia:
   Django es *una clase = un modelo = una tabla*; no se declara el mismo modelo
   varias veces en módulos distintos para fusionarlo. Por DEC-SALE-01, la
   *extensión* (``_inherit``) se resuelve como herencia Python intra-app y como
   **FK RELATED** cross-app; la *delegación* (``_inherits``, que en Odoo exige un
   Many2one delegate) es composición nativa (``OneToOneField``/FK + delegación).

3. **Model classes por registro (por-DB) + "fields shared across registries".**
   En Odoo el registro es **por base de datos** y la optimización es compartir el
   objeto ``field`` entre registros cuando se puede (por eso los magic fields van
   en las clases-definición, ``:136-138``). En Django las clases son
   **process-global** (una sola vez por proceso), así que esa optimización es
   **irrelevante**: no hay reconstrucción de clase por conexión — el multi-DB es
   un asunto de *router* (``orm/routers.py``), no de rebuild de clases.

Por eso este archivo es un stub delgado documentado: ``ModelBase`` hace el
registro y las migraciones materializan el schema; no hay ``add_to_registry`` ni
MRO-fusion que replicar.


``extend_model`` — el ``_inherit`` por nombre
===============================================

La referencia extiende un modelo **nombrándolo**: ``add_to_registry``
(``odoo19c: odoo/orm/model_classes.py:152-231``) resuelve cada cadena de
``_inherit`` contra ``registry[parent_name]``, y ``add_field`` (``:596``) le
cuelga el campo. Las dos operaciones viven en **este** archivo allá, y por eso
viven aquí — un archivo propio sería la divergencia de forma de
:ref:`h-api-568`.

Django trae el acoplamiento tardío en ``Apps.lazy_model_operation``
(``django/apps/registry.py:388-426``). Lo que este bloque añade es el
adaptador que lo vuelve seguro; el porqué está medido en ``H-API-577`` y sus
pruebas en ``tests/unit/orm/test_extension_tardia_por_nombre.py``.
"""
import copy
import importlib
import inspect
import logging

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models
from django.db.models import CASCADE, ForeignKey, Model, PROTECT
from django.db.models.fields import NOT_PROVIDED
from django.db.models.base import ModelBase
from django.db.models.signals import class_prepared
from django.dispatch import receiver

from django.apps import apps

from orm.method_chain import chain_method, wrap_method
from orm.registry import (MODELS_BY_NAME, clear_marked_methods,
                          field_depends, resolve_model_key)
from tools.misc import discardattr

_logger = logging.getLogger(__name__)

__all__ = [
    'ModelBase', 'is_model_class', 'is_model_definition',
    'extend_model', 'extend_property', 'add_field_if_absent', 'model_key',
    'resolve_rec_name', 'ensure_rec_names',
    'DEFAULT_PARENT_NAME', 'parent_name_of',
    'adopt_access_manager', 'ensure_access_managers',
    'add_field', 'pop_field',
    'is_abstract', 'is_transient', 'check_model_bases',
    'inherits_of', 'inherits_children',
    '_init_model_class_attributes', '_prepare_setup',
    'ensure_model_class_attributes',
]


def is_model_class(cls) -> bool:
    """``True`` si ``cls`` es una clase de modelo (subclase de ``models.Model``).
    Equivale a ``odoo.orm.model_classes.is_model_class`` — sobre ``ModelBase``."""
    return isinstance(cls, ModelBase) and issubclass(cls, Model)


def is_model_definition(cls) -> bool:
    """``True`` si ``cls`` es una definición concreta (no abstracta). Equivale a
    ``odoo.orm.model_classes.is_model_definition`` — sobre ``Model._meta``."""
    return is_model_class(cls) and not cls._meta.abstract


def _is_computed_surface(model_cls, name) -> bool:
    """¿``name`` es un campo **calculado no almacenado** de este modelo?

    La fuente valida ``_rec_name`` contra ``_fields``, y ahí entran también los
    calculados sin columna: ``res.groups`` declara ``_rec_name = 'full_name'``
    y su ``full_name`` es ``Char(compute='_compute_full_name')`` sin ``store``
    (``odoo19c: base/models/res_groups.py:12,29``).

    Aquí un campo así no es un campo de Django —no tiene columna que declarar—
    sino un **descriptor** sobre la clase: una ``property`` o un
    :class:`orm.fields_nonstored.NonStored`. Sin este reconocimiento, portar el
    ``_rec_name`` de la fuente verbatim reventaba el arranque, y la única
    salida habría sido no declararlo — omitir un atributo que la fuente sí
    declara.

    Se mira con ``inspect.getattr_static``, no con ``getattr``: éste
    **ejecutaría** la ``property`` contra la clase y daría ``AttributeError``
    por falta de instancia. Aquél devuelve el descriptor sin invocarlo.

    Un nombre que no está en la clase sigue siendo inválido, que es lo que el
    control tiene que poder rechazar: ``_rec_name = 'no_existe'`` no encuentra
    ni campo ni descriptor y levanta igual que antes.
    """
    attr = inspect.getattr_static(model_cls, name, None)
    return attr is not None and hasattr(type(attr), '__get__')


DEFAULT_PARENT_NAME = 'parent'
"""El campo autorreferente por defecto — ≙ ``_parent_name: str = 'parent_id'``
(``odoo19c: odoo/orm/models.py:435``).

La fuente lo declara como atributo de clase de ``BaseModel``, así que **todo**
modelo lo tiene y ``cls._parent_name`` nunca revienta. Aquí la base es la de
Django y no es nuestra, así que el default vive en esta constante y se lee con
:func:`parent_name_of`.

Vale ``'parent'`` y no ``'parent_id'`` por la convención de sufijo que la
tarea #141 fijó: la relación que allá se llama ``parent_id`` aquí se declara
``parent = fields.Many2one('self', ...)`` y Django le pone ``attname``
``parent_id``. Es el mismo campo por su otra cara — el mismo criterio con que
:func:`resolve_rec_name` acepta las dos formas.
"""


def parent_name_of(model_cls):
    """El ``_parent_name`` del modelo, o el default si no lo declara.

    ≙ la lectura de ``comodel._parent_name`` que hace ``_operator_hierarchy``
    (``odoo19c: odoo/orm/domains.py:1741``). Se escribe como función y no como
    un ``getattr`` en el sitio porque son **tres** los sitios que lo leen —el
    optimizador y sus dos constructores de dominio— y un default repetido tres
    veces es tres sitios donde puede divergir.
    """
    return getattr(model_cls, '_parent_name', DEFAULT_PARENT_NAME)


def resolve_rec_name(model_cls):
    """Fija ``_rec_name`` cuando el modelo no lo declara y tiene ``name``.

    ≙ el paso 5 de ``_init_model_class_attributes``
    (``odoo19c: odoo/orm/model_classes.py:433-441``), verbatim en su lógica:
    si el modelo declara ``_rec_name`` se valida que sea un campo suyo; si no
    lo declara y tiene un campo ``name``, ``_rec_name`` pasa a ser ``'name'``.

    Por qué hace falta resolverlo y no basta con leerlo: la referencia declara
    ``_rec_name`` **sólo cuando difiere del default**, y por eso
    ``ResPartner`` no lo declara y aun así ``name_create`` escribe
    ``{self._rec_name: ...}`` (``odoo19c: res_partner.py:1088``). Sin este
    paso ese acceso revienta con ``AttributeError`` — y declararlo a mano en
    cada modelo sería inventar un atributo que la fuente no tiene, que es lo
    que ``atributos-de-clase-de-modelo.md`` prohíbe.

    La rama ``_custom`` con ``x_name`` de la fuente **no se porta**: los
    modelos a medida en tiempo de ejecución son su mecanismo de estudio, y
    aquí un modelo es una clase Python. Es divergencia de mecanismo, no un
    hueco: sin modelos a medida no hay campo ``x_name`` que resolver.

    :returns: el ``_rec_name`` resuelto, o ``None`` si el modelo no tiene
        campo que lo respalde.
    """
    declared = model_cls.__dict__.get('_rec_name')
    # ``fields`` y ``many_to_many``, NO ``get_fields()``: este ultimo trae las
    # inversas, y para eso recorre el grafo de relaciones, que exige el
    # registro de apps poblado. Esta funcion corre desde ``class_prepared``,
    # cuando aun no lo esta — medido: revienta con ``AppRegistryNotReady`` en
    # el primer modelo de ``contenttypes``. La fuente tampoco las mira:
    # ``_fields`` son los campos del modelo, no lo que apunta a el.
    campos = [*model_cls._meta.fields, *model_cls._meta.many_to_many]
    # El nombre Y el ``attname``. La fuente compara contra ``_fields``, donde
    # una Many2one se llama ``user_id``; aqui esa misma relacion se declara
    # ``user = fields.Many2one(...)`` y Django le pone ``attname='user_id'``.
    # Un ``_rec_name = 'user_id'`` portado verbatim —``ir.ui.view.custom`` lo
    # trae asi— nombra el mismo campo por su otra cara, y ``getattr`` responde
    # con las dos. Aceptar solo ``name`` convertiria el porte fiel en un error.
    field_names = {f.name for f in campos} | {f.attname for f in campos}
    if declared:
        if declared not in field_names and not _is_computed_surface(model_cls, declared):
            raise ValueError(
                f'Invalid _rec_name={declared!r} for model '
                f'{model_cls._meta.label}'
            )
        return declared
    if getattr(model_cls, '_rec_name', None):
        return model_cls._rec_name
    if 'name' in field_names:
        model_cls._rec_name = 'name'
        return 'name'
    # El default de la fuente, explicito: ``BaseModel`` los declara
    # ``_rec_name: str | None = None`` y ``_rec_names_search = None``
    # (``odoo19c: odoo/orm/models.py:431-433``), asi que **todo** modelo los
    # tiene y ``cls._rec_name`` nunca revienta. Aqui la base es la de Django y
    # no es nuestra, asi que el default se pone al resolver. Sin esto,
    # ``IrCron`` —que llama a su campo ``cron_name``— daba ``AttributeError``.
    if '_rec_name' not in model_cls.__dict__:
        model_cls._rec_name = None
    if not hasattr(model_cls, '_rec_names_search'):
        model_cls._rec_names_search = None
    return None


#: Los prefijos de módulo que NO son nuestros. El discriminador es el módulo y
#: no la etiqueta de app: ``auth``, ``sessions`` o ``token_blacklist`` son
#: nombres cortos que un addon nuestro podría reusar, mientras que el módulo
#: de origen no se puede confundir.
THIRD_PARTY_MODULE_PREFIXES = ('django.', 'rest_framework')


def adopt_access_manager(model_cls):
    """Le da al modelo las cuatro formas de permiso, si no las tiene ya.

    ≙ que ``check_access``, ``has_access``, ``_check_access`` y
    ``_filtered_access`` cuelguen de ``BaseModel``
    (``odoo19c: odoo/orm/models.py:4100-4135``): allá **todo** modelo las
    tiene, sin declarar nada.

    Aquí las lleva un ``Manager``, y la universalidad se recupera en el
    momento en que Django termina de construir la clase. El discriminador de
    *"no declaró manager propio"* es de Django, no nuestro:
    ``manager.auto_created`` lo marca el propio ``ModelBase._prepare`` cuando
    pone el ``objects`` por defecto (``django/db/models/base.py:434-441``).
    Un modelo que sí declara el suyo se respeta — los siete del árbol derivan
    de ``AccessManager``, que es lo que ``RuleScopedManager`` ya hacía desde la
    tarea #93.

    Por qué una señal y no 90 declaraciones a mano: la alternativa se olvida
    en la primera, y **el olvido no falla** — deja el modelo sin las cuatro
    formas y nada lo delata hasta que alguien las llama.

    :returns: ``True`` si se lo puso; ``False`` si ya lo tenía, es de terceros
        o es abstracto — para que el llamador pueda medir en vez de suponer.

    .. note:: ``orm.models`` se resuelve con ``importlib``, no con un ``import``
       al top, y es la **excepción #4** de ``no-lazy-imports.md`` aplicada a su
       causa hermana. Aquel módulo importa ``orm.environments``, que toca el
       registro de apps; importarlo desde aquí al cargar da
       ``AppRegistryNotReady``, medido. La resolución sancionada es una
       **llamada**, no un statement ``import``: el gate AST da exit 0 y el
       arranque se preserva.
    """
    # Las guardas van ANTES de resolver ``orm.models``, y el orden importa: la
    # señal dispara mientras ``contenttypes`` se está importando, y resolver
    # ``orm.models`` ahí lo arrastra de vuelta —``orm/fields_reference`` pide
    # ``ContentType``— con un ``ImportError`` de módulo parcialmente
    # inicializado. Medido. Descartar al ajeno primero cierra el ciclo.
    if model_cls._meta.abstract or model_cls._meta.proxy:
        return False
    if model_cls.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
        return False
    manager = model_cls._meta.managers_map.get('objects')
    if manager is None or not getattr(manager, 'auto_created', False):
        return False

    orm_models = importlib.import_module('orm.models')
    AccessManager = orm_models.AccessManager
    AccessQuerySet = orm_models.AccessQuerySet
    if isinstance(manager.get_queryset(), AccessQuerySet):
        return False
    # Retirar el viejo ANTES de colgar el nuevo, y no es opcional:
    # ``Options.managers`` recorre ``local_managers`` en orden de inserción y
    # se queda con el **primero** de cada nombre (``seen_managers``). Sin esta
    # línea el ``objects`` auto-creado sigue ganando y ``add_to_class`` no
    # cambia nada — medido: 159 adopciones reportadas y 0 efectivas.
    model_cls._meta.local_managers = [
        m for m in model_cls._meta.local_managers if m.name != 'objects']
    model_cls._meta._expire_cache()
    nuevo = AccessManager()
    nuevo.auto_created = True
    model_cls.add_to_class('objects', nuevo)
    return True


@receiver(class_prepared, dispatch_uid='orm.model_classes.adopt_access_manager')
def _adopt_access_manager_on_prepared(sender, **kwargs):
    """Adopta el manager de permisos en cuanto la clase queda construida."""
    adopt_access_manager(sender)


def ensure_access_managers():
    """Barre el registro por si la señal llegó tarde.

    Dos vías por la misma razón de ``H-API-577``, igual que
    :func:`ensure_rec_names`: la señal cubre lo que llega después de importar
    este módulo; el barrido, lo que ya estaba.

    :returns: cuántos modelos lo adoptaron en el barrido.
    """
    return sum(1 for model in apps.get_models(include_auto_created=True)
               if adopt_access_manager(model))


#: Los cinco símbolos del bloque ``display_name`` de la fuente
#: (``odoo19c: odoo/orm/models.py:473,1425,1442,1493,1512``). Se enumeran aquí
#: y no se derivan del ``__dict__`` del mixin: un ayudante privado que se
#: añadiera allá entraría al barrido sin que nadie lo decidiera.
DISPLAY_NAME_SYMBOLS = (
    'display_name', '_compute_display_name', '_search_display_name',
    'name_create', 'name_search',
)

#: El único de los cinco que es un CAMPO y no un método. Se separa porque su
#: entrega es distinta: un método se cuelga con ``setattr`` y ya resuelve por
#: MRO; un campo de Django **no existe** para el modelo hasta que alguien lo
#: contribuye (``add_to_class`` -> ``contribute_to_class``).
DISPLAY_NAME_FIELD = 'display_name'


def _lacks_contributed_display_name(model_cls):
    """Si al modelo le falta un ``display_name`` que de verdad funcione.

    El discriminador es **de contenido**, no de presencia por MRO, y los cuatro
    desenlaces son los que el árbol tiene:

    =========================================  ==========================
    Lo que el modelo resuelve hoy              Veredicto
    =========================================  ==========================
    está en ``_meta`` (contribuido)            ya lo tiene
    una ``property`` propia                    ya lo tiene — gana por MRO,
                                               que es lo que la fuente hace
                                               con un ``compute`` reescrito
    un ``models.Field`` pelado                 **le falta** — es el objeto
                                               del mixin llano, que Django
                                               nunca contribuyó
    nada                                       **le falta**
    =========================================  ==========================

    La tercera fila es la que ``getattr(...) is None`` no podía ver: un
    ``CharField`` colgado de una clase llana **resuelve** por MRO y por eso se
    leía como «presente», aunque leer ``record.display_name`` devolviera el
    objeto campo en vez de la etiqueta.

    **Por qué las tres listas locales y no ``_meta.get_fields()``.** Esta
    función corre en ``class_prepared``, o sea **mientras** el registro de apps
    se puebla. ``get_fields()`` incluye las relaciones inversas, y para
    resolverlas Django llama a ``_populate_directed_relation_graph`` ->
    ``apps.get_models()`` -> ``check_models_ready()``, que aborta con
    ``AppRegistryNotReady: Models aren't loaded yet`` (medido). Las tres listas
    locales bastan: ``ModelBase`` **copia** a la clase hija los campos que
    hereda de un modelo abstracto, así que un ``display_name`` contribuido por
    la vía que sea ya está en una de ellas.
    """
    meta = model_cls._meta
    declared = (tuple(meta.local_fields) + tuple(meta.private_fields)
                + tuple(meta.local_many_to_many))
    if any(f.name == DISPLAY_NAME_FIELD for f in declared):
        return False
    current = getattr(model_cls, DISPLAY_NAME_FIELD, None)
    return current is None or isinstance(current, models.Field)


def adopt_display_name(model_cls):
    """Le da al modelo su etiqueta y su búsqueda por etiqueta, si no las tiene.

    ≙ que ``display_name``, ``_compute_display_name``,
    ``_search_display_name``, ``name_create`` y ``name_search`` cuelguen de
    ``BaseModel`` (``odoo19c: odoo/orm/models.py:473,1421-1543``): allá **todo**
    modelo los tiene sin declarar nada.

    Aquí los lleva :class:`orm.models.DisplayNameMixin`, que ``TimeStampedModel``
    adopta — **284 de los 374 modelos concretos nuestros** lo heredan (medido).
    Esta función cubre a los **90** que no: los que declaran su propia base,
    como toda la familia ``account``.

    **Los cuatro métodos y el campo se entregan distinto, y ésa es la mitad que
    esta función tuvo mal.** Un método se cuelga con ``setattr`` y resuelve por
    MRO; su discriminador sigue siendo ``getattr``, porque un modelo que hereda
    su ``_compute_display_name`` de una base propia lo tiene tan resuelto como
    el que lo declara. Un **campo de Django no existe** para el modelo hasta
    que alguien lo contribuye: se entrega con ``add_to_class`` sobre una
    ``copy.deepcopy`` —que es lo que ``ModelBase`` hace con los campos que
    hereda de un abstracto; ``clone()`` no sirve, porque reconstruye desde
    ``deconstruct()`` y pierde ``compute``, ``search`` y ``store``— y su
    discriminador es :func:`_lacks_contributed_display_name`, que mira el
    contenido.

    > **Corregido (TASK-API-0417).** El discriminador era ``getattr(...) is
    > None`` para los cinco, y la entrega ``setattr`` para los cinco. Los dos
    > fallaban sobre el campo, y sólo se destapó al retirar el enrutado de las
    > fachadas: con ``Char(compute=...)`` construyendo un ``CharField`` real en
    > vez de un descriptor, el campo que :class:`orm.models.DisplayNameMixin`
    > declara dejó de llegar a ningún ``_meta`` —Django **no contribuye** los
    > campos de una clase llana, sólo los del ``attrs`` que construye y los
    > heredados de modelos **abstractos**— y ``record.display_name`` devolvía
    > el objeto campo. ``getattr`` lo leía como presente (resuelve por MRO) y
    > ``setattr`` no habría podido arreglarlo (no contribuye nada). Medido:
    > **398 de 399** modelos sin ``display_name`` en el registro; el único
    > superviviente era ``addons.test_orm.models.test_orm.TestOrmCategory``,
    > que lo declara él mismo.

    :returns: cuántos de los cinco símbolos se instalaron — 0 si ya los tenía,
        es de terceros o es abstracto, para que el llamador pueda medir en vez
        de suponer.

    .. note:: ``orm.models`` se resuelve con ``importlib`` por la misma causa
       que :func:`adopt_access_manager` documenta: importarlo al top arrastra
       ``orm.environments`` y da ``AppRegistryNotReady``.
    """
    if model_cls._meta.abstract or model_cls._meta.proxy:
        return 0
    if model_cls.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
        return 0

    mixin = importlib.import_module('orm.models').DisplayNameMixin
    adopted = 0

    if _lacks_contributed_display_name(model_cls):
        model_cls.add_to_class(
            DISPLAY_NAME_FIELD,
            copy.deepcopy(mixin.__dict__[DISPLAY_NAME_FIELD]))
        adopted += 1

    for name in DISPLAY_NAME_SYMBOLS:
        if name == DISPLAY_NAME_FIELD:
            continue
        if getattr(model_cls, name, None) is None:
            setattr(model_cls, name, mixin.__dict__[name])
            adopted += 1
    return adopted


def adopt_base_url(model_cls):
    """Le da al modelo la URL raíz desde la que se sirve, si no la tiene.

    ≙ que ``get_base_url`` cuelgue de ``BaseModel``
    (``odoo19c: odoo/orm/models.py:3985``): allá **todo** modelo la tiene sin
    declarar nada.

    Aquí la lleva :class:`orm.models.BaseUrlMixin`, que ``TimeStampedModel``
    adopta — **291 de los 389 modelos concretos** lo heredan (medido). Esta
    función cubre a los **98** que no: los que declaran su propia base, como
    ``IrAttachment``, más los de Django y los de terceros.

    Lo destapó un test del bloque B de ``ir.actions.report`` que pedía la URL
    a un modelo cualquiera, no al reporte: sin él, el porte habría sido del
    **método** y no del **mecanismo**, que es la distinción que
    :ref:`h-api-350` registró.

    Un modelo que ya lo resuelve **no se toca**, y el discriminador es
    ``getattr`` sobre el MRO, igual que en :func:`adopt_display_name`: un
    modelo que sobreescriba ``get_base_url`` en una base propia gana, que es
    lo que la fuente permite con cualquier método de ``BaseModel``.

    :returns: 1 si se instaló, 0 si ya lo tenía, es de terceros o es
        abstracto — para que el llamador pueda medir en vez de suponer.
    """
    if model_cls._meta.abstract or model_cls._meta.proxy:
        return 0
    if model_cls.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES):
        return 0
    if getattr(model_cls, 'get_base_url', None) is not None:
        return 0

    mixin = importlib.import_module('orm.models').BaseUrlMixin
    model_cls.get_base_url = mixin.__dict__['get_base_url']
    return 1


@receiver(class_prepared, dispatch_uid='orm.model_classes.adopt_base_url')
def _adopt_base_url_on_prepared(sender, **kwargs):
    """Adopta la URL raíz en cuanto la clase queda construida."""
    adopt_base_url(sender)


def ensure_base_urls():
    """Barre el registro por si la señal llegó tarde.

    Dos vías por la razón de ``H-API-577``, igual que
    :func:`ensure_display_names`.

    :returns: cuántos modelos adoptaron el método en el barrido.
    """
    return sum(1 for model in apps.get_models(include_auto_created=True)
               if adopt_base_url(model))


@receiver(class_prepared, dispatch_uid='orm.model_classes.adopt_display_name')
def _adopt_display_name_on_prepared(sender, **kwargs):
    """Adopta el bloque de etiqueta en cuanto la clase queda construida."""
    adopt_display_name(sender)


def ensure_display_names():
    """Barre el registro por si la señal llegó tarde.

    Dos vías por la razón de ``H-API-577``, igual que :func:`ensure_rec_names`
    y :func:`ensure_access_managers`.

    :returns: cuántos modelos adoptaron al menos un símbolo en el barrido.
    """
    return sum(1 for model in apps.get_models(include_auto_created=True)
               if adopt_display_name(model))


@receiver(class_prepared, dispatch_uid='orm.model_classes.resolve_rec_name')
def _resolve_rec_name_on_prepared(sender, **kwargs):
    """Resuelve el ``_rec_name`` del modelo recién construido.

    ``class_prepared`` dispara al final de ``ModelBase.__new__``, así que
    ``_meta`` ya está poblado y los campos se pueden enumerar.
    """
    resolve_rec_name(sender)


def ensure_rec_names():
    """Barre el registro de Django por si la señal llegó tarde.

    **Dos vías y ninguna sobra**, por la misma razón que ``H-API-577`` dejó
    escrita para ``MODELS_BY_NAME``: la señal sólo cubre los modelos
    preparados **después** de importar este módulo. Si algo lo importa tras
    ``django.setup()``, los que ya estaban se quedan sin resolver y el
    ``_rec_name`` no existe, **sin error que lo delate** hasta que alguien lo
    lea.

    :returns: cuántos modelos quedaron con ``_rec_name`` resuelto — para que
        el llamador pueda medir en vez de suponer.
    """
    resueltos = 0
    for model in apps.get_models(include_auto_created=True):
        if resolve_rec_name(model):
            resueltos += 1
    return resueltos


def model_key(app_label, model_name):
    """La clave que ``do_pending_operations`` va a reconstruir.

    ``Model._meta.label`` da ``stock.StockLocation``; la cola se indexa por
    ``_meta.model_name``, que Django guarda en minúscula. Normalizar aquí es lo
    que impide el cuelgue silencioso descrito en el docstring del módulo.
    """
    return (app_label, model_name.lower())


def add_field_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idéntico al ``_add_if_absent`` que ya repiten ``account``,
    ``account_fleet``, ``l10n_mx`` y ``product_expiry``: el idioma de extensión
    por ``add_to_class`` no tiene MRO, así que dos addons que cuelguen el mismo
    campo duplicarían la columna.

    Devuelve ``True`` si lo añadió — para que el llamador pueda medir en vez de
    suponer.
    """
    if any(f.name == name for f in model._meta.get_fields()):
        return False
    model.add_to_class(name, field)
    return True


#: Las políticas de borrado que la delegación admite — ≙ ``('cascade',
#: 'restrict')`` de ``_check_inherits`` (``odoo19c:
#: odoo/orm/model_classes.py:473``). El mapeo es uno a uno con el ``on_delete``
#: de Django: ``cascade`` borra en cadena, ``restrict`` impide borrar el padre
#: mientras quede un hijo, que es lo que ``PROTECT`` hace.
INHERITS_DELETE_POLICIES = (CASCADE, PROTECT)


def inherits_of(model_cls):
    """Las delegaciones declaradas por ``model_cls``, vacias si no declara.

    **Divergencia de mecanismo, no de contrato.** La fuente declara el default
    ``_inherits = {}`` en ``BaseModel`` (``odoo19c: odoo/orm/models.py:412``),
    asi que todo modelo lo tiene y se lee sin preguntar. Aqui la clase base es
    la de Django y no admite atributos nuestros: colgarselo alcanzaria tambien
    a ``auth``, ``contenttypes`` y a todo modelo de tercero — la colision que
    barre la tarea **#98**. El default vive en esta lectura.
    """
    return getattr(model_cls, '_inherits', {})


def inherits_children(comodel_name):
    """Los modelos que delegan EN ``comodel_name`` — la arista de vuelta.

    ≙ ``registry[parent]._inherits_children`` (``odoo19c: odoo/orm/
    model_classes.py:293-294``), que alla se mantiene **por escritura**: cada
    ``_init_model_class_attributes`` anade el hijo al conjunto del padre.

    Aqui se **deriva** del registro, con el mismo criterio que
    ``orm.registry.field_depends`` ya toma para su eje: un mapa mantenido a
    mano puede quedar con una entrada de un modelo que ya no delega, y no hay
    quien lo note. Derivarlo no puede envejecer.

    Lee por :func:`inherits_of`, que es el unico lector de ``_inherits`` del
    arbol — un segundo lector seria la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohibe.

    *Ciega a:* un modelo que declare ``_inherits`` y no llegue a
    ``MODELS_BY_NAME`` por no declarar ``_name``; y al transitorio de
    ``account`` que hoy declara delegacion y esta ausente del registro, que es
    la tarea **#333**.
    """
    return frozenset(
        model._name for model in MODELS_BY_NAME.values()
        if comodel_name in inherits_of(model)
    )


def _inherits_field(model_cls, field_name):
    """El campo delegado, o ``None`` si el modelo no lo declara.

    ≙ ``model_cls._fields.get(field_name)`` de la fuente. Aquí ``_fields`` es
    una ``property`` de instancia —se apoya en ``_meta``—, así que sobre la
    **clase** devuelve el descriptor y no el mapa. El registro equivalente a
    nivel de clase es ``_meta``, y su ``get_field`` levanta en vez de devolver
    ``None``; esta envoltura restituye la forma de la fuente.
    """
    try:
        return model_cls._meta.get_field(field_name)
    except FieldDoesNotExist:
        return None


def _check_inherits(model_cls):
    """Valida el campo de cada delegación declarada en ``_inherits``.

    ≙ ``_check_inherits`` (``odoo19c: odoo/orm/model_classes.py:465-477``).
    Mide **cuatro** propiedades del campo, y las cuatro tienen que darse: que
    exista y sea una relación a uno, que delegue, que sea obligatorio y que su
    política de borrado sea de las dos admitidas.

    ================== ============================== =========================
    La fuente exige    Cómo se lee allá                Cómo se lee aquí
    ================== ============================== =========================
    relación a uno     ``field.type != 'many2one'``    ``isinstance(…, ForeignKey)``
    delegación         ``field.delegate``              ídem — lo pone ``apply_inherits``
    obligatorio        ``field.required``              ``not field.null``
    borrado admitido   ``ondelete in (cascade,         ``remote_field.on_delete in
                       restrict)``                     INHERITS_DELETE_POLICIES``
    ================== ============================== =========================

    **La clave de ``_inherits`` nombra el campo de ESTE árbol.** La fuente
    escribe ``{'res.partner': 'partner_id'}``; aquí la FK no lleva el sufijo
    (decisión #141) y la clave la sigue: ``{'res.partner': 'partner'}``. El
    criterio está declarado en ``addons/website/models/website_page.py:26-30``
    y lo cumplen los tres declarantes del árbol.

    El mensaje de las dos ramas se conserva verbatim de la fuente: quien lo lea
    en un traceback tiene que poder buscarlo allá.
    """
    for comodel_name, field_name in inherits_of(model_cls).items():
        field = _inherits_field(model_cls, field_name)
        if not field or not isinstance(field, ForeignKey):
            raise TypeError(
                f"Missing many2one field definition for _inherits reference "
                f"{field_name!r} in model {model_cls._name!r}. Add a field "
                f"like: {field_name} = fields.Many2one({comodel_name!r}, "
                f"required=True, ondelete='cascade')"
            )
        delegates = getattr(field, 'delegate', False)
        policy = getattr(field.remote_field, 'on_delete', None)
        if not (delegates and not field.null
                and policy in INHERITS_DELETE_POLICIES):
            raise TypeError(
                f"Field definition for _inherits reference {field_name!r} in "
                f"{model_cls._name!r} must be marked as 'delegate', 'required' "
                f"with ondelete='cascade' or 'restrict'"
            )


def add_field(model_cls, name, field):
    """Cuelga ``field`` bajo ``name`` en la clase de modelo ya construida.

    ≙ ``add_field`` (``odoo19c: odoo/orm/model_classes.py:596-619``). «Add the
    given ``field`` under the given ``name`` on the model class of the given
    ``model``.»

    Es el hermano **estricto** de :func:`add_field_if_absent`: aquél existe
    para que dos addons no dupliquen la columna y calla si ya está; éste valida
    y levanta. Las dos validaciones de la fuente se portan enteras:

    1. **El nombre tiene que estar autorizado** — o lo declara la clase Python
       (propia o de un delegado por ``_inherits``), o es personalizado y
       empieza por ``x_``. Sin esto, un nombre inventado crearía una columna
       que ningún código conoce.
    2. **El valor tiene que ser un campo.** La fuente pide un ``fields.Field``;
       aquí, un ``models.Field`` de Django, que es la misma pieza.

    Y el aviso de la tercera rama —sobreescribir algo que no era un campo— se
    conserva: no impide la operación, la deja en el log.

    **Divergencia de mecanismo, no de contrato:** la fuente cierra apuntando el
    campo en ``model_cls._fields__``, su registro por nombre. Aquí ese registro
    es ``_meta``, y quien lo puebla es ``add_to_class`` — que además invoca
    ``contribute_to_class`` y con él el ``__set_name__`` que la fuente llama a
    mano. Una sola llamada hace las tres cosas.

    De ahi sale la unica linea sin contraparte literal: la fuente **reemplaza**
    con ``_fields__[name] = field``, y un ``dict`` reemplaza solo. ``_meta``
    guarda sus campos en una lista, asi que colgar encima de uno que ya esta
    dejaria los dos. :func:`pop_field` retira el anterior primero, que es lo
    que hace del reemplazo un reemplazo.
    """
    delegated = [MODELS_BY_NAME[inherit] for inherit in inherits_of(model_cls)
                 if inherit in MODELS_BY_NAME]
    is_class_field = any(
        isinstance(_inherits_field(cls, name), models.Field)
        for cls in [model_cls] + delegated
    )
    if not (is_class_field
            or MODELS_BY_NAME['ir.model.fields']._is_manual_name(name)):
        raise ValidationError(
            f"The field `{name}` is not defined in the `{model_cls._name}` "
            f"Python class and does not start with 'x_'"
        )

    if not isinstance(field, models.Field):
        raise ValidationError(
            "You can only add `fields.Field` objects to a model fields")

    previous = getattr(model_cls, name, None)
    if previous is not None and isinstance(previous, models.Field):
        _logger.warning("In model %r, field %r overriding existing value",
                        model_cls._name, name)
    pop_field(model_cls, name)
    model_cls.add_to_class(name, field)
    field._toplevel = True


def pop_field(model_cls, name):
    """Retira el campo ``name`` de la clase de modelo, y lo devuelve.

    ≙ ``pop_field`` (``odoo19c: odoo/orm/model_classes.py:622-633``). «Remove
    the field with the given ``name`` from the model class of ``model``.»

    Las **dos** mitades importan, y la segunda es la que un ``delattr`` pelado
    no hace: si el campo que se va era el ``_rec_name``, el modelo se queda
    apuntando a una columna inexistente, y ``display_name`` seguiría
    declarándolo entre sus dependencias. La fuente arregla las dos cosas aquí
    mismo, y el puerto también.

    **Divergencia de mecanismo, no de contrato.** La fuente saca el campo de
    ``model_cls._fields__``; aquí el registro es ``_meta``, que no expone una
    baja pública — así que se retira de la lista local que corresponda a su
    forma y se caduca el cache derivado, que es lo que ``add_to_class`` hace al
    poner. ``discardattr`` (``odoo19c: odoo/tools/misc.py:700``) quita el
    descriptor sin preguntar si estaba.
    """
    field = _inherits_field(model_cls, name)
    if field is not None:
        meta = model_cls._meta
        for bucket in (meta.local_fields, meta.local_many_to_many):
            if field in bucket:
                bucket.remove(field)
        meta._expire_cache()
        discardattr(model_cls, name)
        discardattr(model_cls, getattr(field, 'attname', name))

    if model_cls._rec_name == name:
        # Arreglo de ``_rec_name`` y de las dependencias de ``display_name``.
        model_cls._rec_name = None
        field_depends.clear()
    return field


def add_meta_index(model, index):
    """Cuelga un ``models.Index`` del ``Meta`` de un model ajeno.

    Es lo que ``extend_model(campos=…)`` no alcanza: ``add_to_class`` instala
    la columna y no toca ``_meta.indexes``. La referencia sí lo alcanza, porque
    allá el índice es un atributo del propio campo (``index='btree_not_null'``),
    y aquí es una entrada del ``Meta`` del model — que pertenece a otro addon.

    **Las DOS escrituras son necesarias, y la segunda no es opcional.**
    ``ModelState.from_model`` sólo lee ``model._meta.indexes`` si el nombre
    ``indexes`` figura en ``model._meta.original_attrs``
    (``django/db/migrations/state.py:839``), que es el registro de qué opciones
    declaró el ``class Meta`` del model. Un model cuyo ``Meta`` nunca declaró
    ``indexes`` no lo tiene, así que el autodetector leería una lista vacía y
    **propondría borrar el índice en cada `makemigrations`** — un rojo perpetuo
    que además no cuesta nada evitar. Declararlo en ``original_attrs`` es
    exactamente lo que habría hecho escribir ``indexes = [...]`` en el ``Meta``.

    Idempotente por nombre: ``ready()`` puede correr más de una vez en tests que
    recargan el registro de apps, y un índice repetido saldría dos veces en la
    migración propuesta.

    Devuelve ``True`` si lo añadió — para que el llamador pueda medir.
    """
    if any(i.name == index.name for i in model._meta.indexes):
        return False
    model._meta.indexes = list(model._meta.indexes) + [index]
    model._meta.original_attrs['indexes'] = model._meta.indexes
    return True


#: Las cinco politicas de borrado de un valor de seleccion, verbatim de la
#: fuente (``odoo19c: odoo/orm/fields_selection.py:45-57``). ``'set VALUE'``
#: no cabe en un conjunto —el valor es libre— y se reconoce por prefijo.
ONDELETE_POLICIES = ('set null', 'set default', 'cascade')

#: La politica que la fuente pone por defecto a todo valor nuevo que el
#: ``selection_add`` no nombre (``:131-133``).
ONDELETE_DEFAULT = 'set null'


def check_ondelete_policies(field, ondelete, new_values, values):
    """Valida el mapa ``{valor: politica}`` — ≙ el bloque de la fuente.

    ≙ ``odoo19c: odoo/orm/fields_selection.py:129-163``, con sus cuatro
    comprobaciones y sus cuatro mensajes. Se saca a funcion propia porque
    :func:`extend_selection_choices` la usa una vez y el test la interroga
    aparte; alla es un tramo del cuerpo de ``_setup_attrs__`` y no se puede
    llamar sola.

    :param field: el campo de Django cuyo vocabulario se amplia.
    :param ondelete: el mapa declarado, ya con los defectos rellenos.
    :param new_values: los valores que este ``selection_add`` **agrega** —
        son los unicos a los que la politica aplica.
    :param values: el vocabulario completo tras la ampliacion, para validar
        el destino de un ``'set VALUE'``.
    :raises ValueError: con el mensaje de la fuente, adaptado al espanol.
    """
    # La INTENCION declarada, no el defecto de Django. ``null`` y ``blank``
    # nacen en ``False``, asi que deducir de ellos daria "requerido" en los
    # 181 campos ``Selection`` del arbol que no declaran ninguno de los dos —
    # el instrumento mediria la forma del ORM anfitrion y la conclusion seria
    # sobre la intencion de la fuente. ``fields.Selection`` anota
    # ``field.required`` cuando la declaracion lo dice, y su ausencia vale
    # ``False``, que es el defecto de la fuente.
    required = bool(getattr(field, 'required', False))
    if required and new_values and ONDELETE_DEFAULT in ondelete.values():
        raise ValueError(
            f'{field.name!r}: un campo de seleccion requerido debe declarar '
            f'una politica de borrado que limpie sus registros al '
            f'desinstalar el modulo. Use una o mas de estas: '
            f"'set default' (si el campo declara uno), 'cascade', o un "
            f'invocable de un solo argumento, que recibe el conjunto de '
            f'registros con el valor.')

    for key, policy in ondelete.items():
        if callable(policy) or policy in ('set null', 'cascade'):
            continue
        if policy == 'set default':
            if field.default is NOT_PROVIDED:
                raise ValueError(
                    f"{field.name!r}: la politica 'set default' no vale para "
                    f'este campo porque no declara un valor por defecto. '
                    f'Declare uno en el campo base, o cambie la politica.')
        elif isinstance(policy, str) and policy.startswith('set '):
            if policy[4:] not in values:
                raise ValueError(
                    f"{field.name!r}: la politica 'set %' debe ser "
                    f"'set null', 'set default', o 'set VALOR' donde VALOR "
                    f'es un valor valido de la seleccion.')
        else:
            raise ValueError(
                f'{field.name!r}: la politica de borrado {policy!r} para el '
                f'valor {key!r} no es valida; elija una de '
                f"'set null', 'set default', 'set [valor]', 'cascade' o un "
                f'invocable.')


def extend_selection_choices(model, field_name, extra, ondelete=None):
    """Amplia en sitio los ``choices`` de un campo ya declarado — ≙ ``selection_add``.

    ``extra`` es la lista de pares ``(valor, etiqueta)`` que el addon suma al
    vocabulario que otro ya declaro. Es exactamente lo que la referencia
    expresa redeclarando el campo con ``selection_add=``: **amplia**, no
    sustituye, y por eso preserva los valores del declarante original.

    ``ondelete`` es el ``{valor: politica}`` que la fuente declara **junto** a
    ``selection_add``, y por la misma razon: la politica dice que hacer con
    las filas que guardaban un valor cuando ese valor desaparece. Se guarda en
    el atributo ``ondelete`` del propio campo —el mismo nombre que la fuente
    le da (``odoo19c: fields_selection.py:67``)— porque es ahi donde
    :meth:`~addons.base.models.ir_model.IrModelFieldsSelection._process_ondelete`
    lo lee. Todo valor nuevo que el mapa no nombre recibe
    :data:`ONDELETE_DEFAULT`, igual que alla (``:131-133``).

    No genera migracion. ``choices`` no es DDL: PostgreSQL guarda el valor en
    la misma columna de texto, y ``Field.validate()`` consulta la lista viva en
    cada llamada, asi que la ampliacion es efectiva desde el momento en que
    corre. Lo unico que puede necesitar migracion es el ``max_length`` del
    campo, si el valor nuevo no cupiera — quien amplie lo comprueba.

    Idempotente por pertenencia: ``ready()`` puede correr mas de una vez en
    tests que recargan el registro de apps, y un valor repetido en ``choices``
    sale duplicado en todo selector que lo lea. El mapa de politicas se
    **acumula** por la misma razon que alla (``self.ondelete.update``): dos
    addons pueden ampliar el mismo campo, y el segundo no borra al primero.

    Devuelve los valores realmente agregados, para que el llamador pueda medir
    en vez de suponer.
    """
    field = model._meta.get_field(field_name)
    present = {value for value, _label in field.choices}
    added = []
    for value, label in extra:
        if value in present:
            continue
        field.choices = list(field.choices) + [(value, label)]
        present.add(value)
        added.append(value)

    policies = dict(ondelete or {})
    for value in added:
        policies.setdefault(value, ONDELETE_DEFAULT)
    if policies:
        check_ondelete_policies(field, policies, added, present)
        combined = dict(getattr(field, 'ondelete', None) or {})
        combined.update(policies)
        field.ondelete = combined
    return added


def is_abstract(model_cls):
    """El modelo no tiene tabla — ≙ ``_abstract`` (``odoo19c: odoo/orm/
    models.py:381``).

    Es un **lector**, no un atributo, y la razon esta medida: colgar
    ``_abstract`` de ``models.Model`` alcanzaria a ``auth``, ``contenttypes``
    y a todo modelo de tercero —la colision de la tarea **#98**— y ademas
    **mentiria** sobre el modelo que si declara ``Meta.abstract = True``, que
    lo heredaria en ``False`` (``orm/models.py:3846-3862``).

    Lee las **dos** formas que este arbol si tiene: el ``Meta.abstract`` de
    Django, que es el mecanismo del stack, y el ``_abstract`` declarado, que
    es el de :class:`~orm.models.AbstractModel` para el registrante sin tabla.
    """
    meta = getattr(model_cls, '_meta', None)
    if meta is not None and getattr(meta, 'abstract', False):
        return True
    return bool(getattr(model_cls, '_abstract', False))


def is_transient(model_cls):
    """El modelo se vacia solo — ≙ ``_transient`` (``odoo19c: odoo/orm/
    models.py:382``).

    Aqui **si** es un atributo de clase, porque su declarante es nuestro:
    ``orm/models_transient.py:70``. El lector existe igual para que el check
    de abajo lea las dos especies por la misma puerta, y para que el default
    —``False``— viva en un solo sitio.
    """
    return bool(getattr(model_cls, '_transient', False))


def _check_model_extension(model_cls, model_def):
    """≙ ``_check_model_extension`` (``odoo19c: odoo/orm/model_classes.py:
    233-250``) — «Check whether ``model_cls`` can be extended with
    ``model_def``».

    **De sus dos mitades, aqui solo tiene superficie la transitoria**, y no
    por recorte: allá la mitad de ``_abstract`` existe porque ``_inherit``
    FUNDE dos clases bajo un mismo ``_name``, y la segunda puede cambiarle la
    especie a la primera. Aqui ``orm.registry._register`` **rechaza** el
    ``_name`` duplicado (``registry.py:216-224``) — *"El nombre punteado
    identifica un modelo, no una familia"*—, asi que esa fusion no ocurre y la
    transformacion no tiene por donde entrar. Es una guarda mas estricta que
    la de la fuente, no un hueco.

    Los dos mensajes se portan **verbatim**: son lo que quien los lee busca
    en la documentacion de la referencia.
    """
    if is_transient(model_cls) != is_transient(model_def):
        if is_transient(model_cls):
            raise TypeError(
                f"{model_def} transforms the transient model "
                f"{model_cls._name!r} into a non-transient model. "
                "That class should either inherit from TransientModel, or set "
                "a different '_name'."
            )
        raise TypeError(
            f"{model_def} transforms the model {model_cls._name!r} into a "
            "transient model. That class should either inherit from Model, or "
            "set a different '_name'."
        )


def _check_model_parent_extension(model_cls, model_def, parent_cls):
    """≙ ``_check_model_parent_extension`` (``:253-258``) — «Check whether
    ``model_cls`` can inherit from ``parent_cls``».

    Verbatim, mensaje incluido. Aqui el ``model_def`` de la firma es la propia
    clase: no hay clase de definicion separada de la registrada, porque
    ``ModelBase`` de Django ya construyo una sola.
    """
    if is_abstract(model_cls) and not is_abstract(parent_cls):
        raise TypeError(
            f"In {model_def}, abstract model {model_cls._name!r} cannot "
            f"inherit from non-abstract model {parent_cls._name!r}."
        )


def check_model_bases(model_cls):
    """Aplica los dos checks de la fuente sobre cada padre con ``_name``.

    **Es lo unico nuestro de este bloque**, y cubre el hueco que deja la
    ausencia de ``_base_classes__``: alla el recorrido lo hace
    ``add_to_registry`` al fundir cada clase de definicion en la registrada
    (``:225-229``), y aqui no hay fusion que recorrer — la jerarquia es la
    MRO de Python, que ``ModelBase`` ya resolvio.

    **Solo mide padres que declaren ``_name``**, como la fuente, que recorre
    clases de definicion y no toda la cadena: un mixin sin nombre no es un
    modelo y no tiene especie que contradecir.
    """
    for parent_cls in model_cls.__mro__[1:]:
        if not getattr(parent_cls, '_name', None):
            continue
        _check_model_parent_extension(model_cls, model_cls, parent_cls)
        _check_model_extension(parent_cls, model_cls)


def _init_model_class_attributes(model_cls):
    """≙ ``_init_model_class_attributes`` (``odoo19c: odoo/orm/model_classes.
    py:261-298``) — «Initialize model class attributes».

    Rellena los defaults que la fuente deriva del ``_name`` y funde el
    ``_inherits`` declarado a lo largo de las bases.

    **Tres divergencias, las tres medidas:**

    - ``_log_access = _auto`` de la fuente no se cuelga: su equivalente aqui
      es ``TimeStampedModel``, que declara las columnas de auditoria como
      campos y no como una bandera (``atributos-de-clase-de-modelo.md``).
    - ``_table`` se deja en el default derivado del ``_name``; quien manda
      sobre la tabla real es ``Meta.db_table``, y que los dos coincidan lo
      verifica ``orm.registry.check_table_matches_name()``.
    - el recorrido es la **MRO**, no ``_base_classes__``. En orden inverso,
      como la fuente, para que la declaracion propia gane sobre la de la base.

    La fuente evita asignar un dict vacio *"to save memory"* (``:289-292``);
    aqui el efecto observable es que la clase no gana un atributo que no
    declaro, que es lo que :func:`inherits_of` lee.
    """
    # El ``_name`` DECLARADO, no el heredado: ``getattr`` recorre la MRO, y
    # medido en el arbol hay un modelo —``addons/website/models/static_page.py:
    # 30``, ``StaticPage``— que hereda el ``_name`` de un mixin sin declarar el
    # suyo. Con ``getattr`` se le habrian escrito el ``_description`` y el
    # ``_table`` del mixin. Es la misma lectura que ``orm.registry._register``
    # ya hace (``registry.py:214``), y por la misma razon.
    name = model_cls.__dict__.get('_name')
    if not name:
        return

    if not model_cls.__dict__.get('_description'):
        # El aviso de la fuente (``:271-272``), verbatim. Medido al portarlo:
        # 0 de los 140 modelos registrados lo dispara — el arbol ya declara
        # ``_description`` en todos, asi que entra sobre un baseline limpio.
        _logger.warning("The model %s has no _description", name)
        model_cls._description = name
    if not model_cls.__dict__.get('_table'):
        model_cls._table = name.replace('.', '_')

    inherits = {}
    for base in reversed(model_cls.__mro__):
        inherits.update(base.__dict__.get('_inherits') or {})
    if inherits:
        model_cls._inherits = inherits


def _prepare_setup(model_cls):
    """≙ ``_prepare_setup`` (``odoo19c: odoo/orm/model_classes.py:329-346``) —
    «Prepare the setup of the model».

    Su unico trabajo es **olvidar** lo que el setup vuelve a calcular: los dos
    atributos resueltos y los tres mapas de metodo marcado.

    **Sin ``_setup_done__`` ni el cambio de bases** de la fuente (``:330-337``):
    aquel guarda ``_base_classes__`` para poder reconstruir la clase, y aqui
    ``ModelBase`` construyo una sola cuya MRO no se reescribe. Lo que queda es
    el olvido, que es la mitad con consumidor.

    Es el llamador que :func:`~orm.registry.clear_marked_methods` esperaba
    desde la tarea **#334**: un colector que no se vacia hace invisible un
    metodo anadido despues, y eso ya se midio
    (``tests/unit/web/test_models_onchange.py``).
    """
    for attr in ('_rec_name', '_active_name'):
        discardattr(model_cls, attr)
    clear_marked_methods()


@receiver(class_prepared, dispatch_uid='orm.model_classes.init_class_attributes')
def _init_class_attributes_on_prepared(sender, **kwargs):
    """Valida la especie heredada y rellena los defaults, clase por clase.

    ``class_prepared`` dispara al final de ``ModelBase.__new__``, que es donde
    la fuente corre los dos checks y ``_init_model_class_attributes``: al
    fundir cada clase de definicion en la registrada
    (``odoo19c: odoo/orm/model_classes.py:216-229``).

    El orden importa y es el de la fuente: **primero se valida**, y solo
    entonces se rellena. Rellenar una clase cuya especie contradice a su padre
    seria dejar consistente un estado que no deberia existir.
    """
    check_model_bases(sender)
    _init_model_class_attributes(sender)


def ensure_model_class_attributes():
    """Barrido para las clases preparadas ANTES de conectar el receptor.

    Mismo hermano que :func:`ensure_rec_names` y :func:`ensure_access_managers`
    ya tienen, y por la misma razon: ``class_prepared`` no dispara hacia atras,
    asi que una clase construida antes de que este modulo se importara nunca
    pasaria por el receptor. Corre desde ``AppConfig.ready()``.

    Devuelve los nombres tocados, para que quien lo llame pueda medirlo.
    """
    tocados = []
    for model_cls in list(MODELS_BY_NAME.values()):
        check_model_bases(model_cls)
        _init_model_class_attributes(model_cls)
        tocados.append(model_cls._name)
    return tocados


def _fields_with_setup(model_cls):
    """Los campos del modelo que tienen fase de setup — ≙ ``model_cls._fields``.

    Allá ese universo sólo contiene ``Field`` (``odoo19c: odoo/orm/models.py``,
    ``_fields: dict[str, Field]``). Aquí son las tres listas hacia adelante de
    ``_meta`` —concretos con los heredados, ``many_to_many`` y ``private_fields``—
    y NO ``get_fields()``: ésa además enumera las relaciones inversas
    (``ManyToOneRel``…), que no son campos de la fuente, y para listarlas
    construye ``_relation_tree`` sobre TODOS los modelos del registro. Medido
    (``probe_which_test_module_breaks_a_fk.py``): con ``get_fields()`` la
    fase reventaba con ``'NoneType' object has no attribute '_meta'`` al
    correr sobre el modelo *through* de un M2M, que Django registra a mitad
    de la construcción de su dueño — un árbol de relaciones con un modelo a
    medias. Las tres listas no tocan ese árbol
    (``options.py:_get_fields(reverse=False)``).
    """
    opts = model_cls._meta
    return [f for f in (*opts.fields, *opts.many_to_many, *opts.private_fields)
            if isinstance(f, models.Field)]


def _is_setup_done(model_cls):
    """El marcado de la fuente, leído en la clase y no por la MRO.

    ``_setup_done__`` vive en ``vars(model_cls)``: un hijo concreto de un
    modelo concreto no hereda el «hecho» del padre, igual que allá cada
    ``model_cls`` del registro lleva el suyo. Sin entrada = no hecho, que es
    el estado con que ``add_to_registry`` deja al modelo (``:228``).
    """
    return vars(model_cls).get('_setup_done__', False)


def mark_model_for_setup(model_cls):
    """≙ ``registry[model_name]._setup_done__ = False`` (``:228``).

    Es lo que ``add_to_registry`` hace al cargar un modelo y lo que
    ``_setup_models__`` hace con los descendientes por ``_inherit`` de un
    módulo cargado (``odoo19c: odoo/orm/registry.py:426-433``). Aquí lo
    disparan ``class_prepared`` (el modelo nuevo) y :func:`extend_model` (el
    ``_inherit``). El barrido perezoso lo recoge.
    """
    model_cls._setup_done__ = False
    ensure_field_setup.pending = True


def prepare_field_setup(model_cls):
    """Reabre la fase de setup de cada campo — ≙ ``_setup`` paso 4 (``:432``).

    La fuente, tras fijar ``_setup_done__ = True`` en el modelo, recorre
    ``for field in model_cls._fields.values(): field.prepare_setup()``. Es lo
    que pone ``_setup_done = False`` en el campo, cuyo defecto de clase es
    ``True`` (``odoo19c: odoo/orm/fields.py:264``): sin esta pasada,
    ``field.setup(model)`` retorna en su primera línea y no instala nada.
    Medido por conducta antes de portarla
    (``probe_related_setup_phase_resolves.py``: ``setup_done=True``,
    ``compute=None`` tras la llamada).

    Un modelo ya hecho retorna en la primera línea, como ``_prepare_setup``
    (``:331``): la fase es incremental, y un campo ya instalado no se reabre
    hasta que alguien vuelva a marcar su modelo.

    :returns: cuántos campos quedaron reabiertos.
    """
    if _is_setup_done(model_cls):
        return 0
    fields_ = _fields_with_setup(model_cls)
    for field in fields_:
        field.prepare_setup()
    return len(fields_)


def setup_fields(model_cls):
    """La fase que completa cada campo — ≙ ``_setup_fields`` (``:511-528``).

    Docstring de la fuente, verbatim: *"Setup the fields, except for
    recomputation triggers."* Allá construye ``model = model_cls(env, (), ())``
    y llama ``field.setup(model)`` por campo; aquí ``setup`` lee la clase
    (``walk_related_chain`` recorre ``_meta``), así que se le pasa la clase.

    Lo que la fase deja instalado en un ``related=``: ``compute`` (la
    proyección), ``inverse`` si es escribible y ``search`` si no tiene columna
    (``setup_related``, ``:604-660``). Sin ella un ``related`` declarado sobre
    un campo de Django tenía ``compute=None`` y la lectura caía a
    ``default_get`` (medido: ``probe_related_on_django_field_at_read.py``).

    La rama de la fuente que traga el error de un campo **manual** (``:517-527``,
    ``pop_field`` sobre ``bad_fields``) no tiene receptor: no hay campos
    manuales en este árbol. Un ``related`` cuya cadena no resuelve levanta,
    como allá para un campo declarado en código.

    Cierra con ``_setup_done__ = True`` (``:429``): el modelo queda hecho hasta
    que :func:`mark_model_for_setup` lo reabra.

    :returns: cuántos campos pasaron por ``setup``.
    """
    if _is_setup_done(model_cls):
        return 0
    fields_ = _fields_with_setup(model_cls)
    for field in fields_:
        field.setup(model_cls)
    model_cls._setup_done__ = True
    return len(fields_)


@receiver(class_prepared, dispatch_uid='orm.model_classes.setup_fields')
def _setup_fields_on_prepared(sender, **kwargs):
    """Marca el modelo recién construido — ≙ ``add_to_registry`` (``:228``).

    Antes del arranque sólo marca: la fase de la fuente corre cuando TODOS
    los modelos de un módulo están (``_setup_models__`` tras
    ``registry.load``, ``loading.py:187-193``), y un ``related`` cruza
    modelos. El equivalente aquí es el barrido perezoso de
    :func:`ensure_field_setup`, que recoge lo marcado en cuanto
    ``apps.ready``.

    Un modelo construido DESPUÉS del arranque —un test, ``isolate_apps``—
    también SÓLO se marca, y lo completa el mismo barrido perezoso en su
    primer acceso a campo. Una versión anterior lo encolaba con
    ``lazy_model_operation`` para completarlo en ``register_model``; medido
    (``probe_which_test_module_breaks_a_fk.py``), ese momento cae **dentro**
    de ``ModelBase.__new__`` del dueño cuando el modelo es el *through*
    auto-creado de un M2M (``related.py:2000`` → ``register_model`` →
    ``do_pending_operations``): la fase corría sobre un modelo a medias. La
    fuente no tiene ese problema porque nunca hace setup por clase — lo hace
    el cargador, después del módulo (``loading.py:193``) — y el barrido
    perezoso es ese «después».
    """
    mark_model_for_setup(sender)


def ensure_field_setup():
    """El barrido — ≙ ``_setup_models__`` sobre los modelos marcados.

    La fuente lo corre desde el CARGADOR: incremental tras cada módulo
    (``odoo19c: odoo/modules/loading.py:173,184,193,285``) y completo al
    terminar (``:488``, tras ``registry.loaded = True``). El cargador de aquí
    es ``apps.populate``, y Django no expone el momento «tras el último
    ``ready()``»: el ``ready()`` de ``base`` corre ANTES de que ``crm``
    aplique sus ``extend_model`` (medido: ``FieldDoesNotExist: CrmTeam has
    no field named 'lead_properties_definition'`` al barrer desde ahí). Por
    eso el barrido es **perezoso**: lo dispara el primer consumidor de un
    campo —el descriptor— cuando ``apps.ready``, que es el mismo criterio con
    que :func:`orm.registry._ensure_seeded` cubre lo que llegó tarde.

    Orden de la fuente, conservado (``setup_model_classes``, ``:318-323``):
    primero reabrir TODOS los marcados, sólo después completarlos — un
    ``related`` de A puede cruzar a B, y B tiene que estar reabierto antes.

    Idempotente y barato cuando no hay nada marcado: ``pending`` es la
    bandera que los marcadores levantan y este barrido baja.

    :returns: cuántos campos pasaron por ``setup`` — para medir, no suponer.
    """
    if not apps.ready:
        return 0
    ensure_field_setup.pending = False
    models_ = [m for m in apps.get_models(include_auto_created=True)
               if not _is_setup_done(m)]
    for model_cls in models_:
        prepare_field_setup(model_cls)
    return sum(setup_fields(model_cls) for model_cls in models_)


#: Levantada por :func:`mark_model_for_setup`; bajada por el barrido. Nace en
#: ``True`` porque todo modelo cargado antes de importar este módulo está sin
#: hacer y sin marca en su ``__dict__`` (la clase de ``H-API-577``).
ensure_field_setup.pending = True


def extend_model(*destino, campos=None, metodos=None, overrides=None,
                 propiedades=None, selection_add=None, ondelete=None,
                 indexes=None, luego=None):
    """Extiende un modelo cuando exista — ≙ ``_inherit``.

    El destino se nombra de una de las dos formas, y la primera es la de la
    referencia::

        extend_model('product.removal', campos={...})       # el _name portado
        extend_model('stock', 'ProductRemoval', campos={})  # el par de Django

    El nombre punteado exige que el modelo **ya esté cargado** (lo registra la
    señal ``class_prepared``); el par de Django no, y es por tanto el único que
    sirve para el caso genuinamente tardío. Ver
    :func:`orm.model_naming.resolve_model_key`.

    Ninguno de los cuatro bloques es obligatorio; se aplican en este orden
    sobre la clase destino:

    ``campos``
        ``{nombre: field}`` — vía :func:`add_field_if_absent`.
    ``metodos``
        ``{nombre: función}`` — vía ``chain_method``: el mecanismo decide
        cuándo invocar la previa (relevo por ``None``, o ``combine``), y la
        nueva corre primero.
    ``overrides``
        ``{nombre: función}`` — vía :func:`~orm.method_chain.wrap_method`: la
        previa llega **en la mano**, ligada al receptor, como segundo
        argumento de ``func``. Es la forma del override que necesita el
        resultado de ``super()`` como insumo, o que hace su trabajo **antes**
        de delegar. La referencia usa las dos en el mismo archivo
        (``odoo19c: sale/models/ir_config_parameter.py`` — ``create`` delega
        primero, ``unlink`` delega último), así que ningún mecanismo que fije
        el orden las cubre.

        Su nombre va en inglés porque es un identificador nuevo
        (``identificadores-en-ingles.md``). Los cinco hermanos están en
        español como deuda heredada congelada: renombrarlos toca 135 sitios de
        llamada y es el barrido de la tarea **#147**, no un pago al tocar.
    ``propiedades``
        ``{nombre: función}`` — instaladas como ``property``, para los
        ``compute`` sin ``store`` de la referencia. No pisa una existente.
    ``selection_add``
        ``{nombre_campo: [(valor, etiqueta), …]}`` — ≙ el ``selection_add=``
        de la referencia, vía :func:`extend_selection_choices`. Amplía el
        vocabulario de un ``fields.Selection`` ya declarado sin redeclararlo,
        que es lo que preserva los valores de quien lo declaró primero.
    ``ondelete``
        ``{nombre_campo: {valor: política}}`` — ≙ el ``ondelete=`` que la
        fuente declara **junto** al ``selection_add`` en la misma
        redeclaración, y por eso viaja aquí como su hermano y no como un
        parámetro de ``fields.Selection``. Dice qué hacer con las filas que
        guardaban un valor cuando ese valor desaparece; lo consume
        ``IrModelFieldsSelection._process_ondelete``. Todo valor nuevo que el
        mapa no nombre recibe ``'set null'``, como allá.
    ``indexes``
        ``[models.Index(…), …]`` — ≙ el ``index=`` que la referencia declara
        como atributo del campo, vía :func:`add_meta_index`. Es lo que hay que
        usar cuando el addon aporta la columna y el ``Meta`` es de otro addon.
    ``luego``
        ``f(modelo)`` — escotilla para lo que no cae en los cuatro anteriores
        (constraints, receptores de señal).

    **No devuelve el modelo**: en el caso interesante todavía no existe. Quien
    necesite la clase la pide dentro de ``luego``, que la recibe como argumento.
    """
    def aplicar(modelo):
        for nombre, field in (campos or {}).items():
            add_field_if_absent(modelo, nombre, field)
        for nombre, funcion in (metodos or {}).items():
            chain_method(modelo, nombre, funcion)
        for nombre, funcion in (overrides or {}).items():
            wrap_method(modelo, nombre, funcion)
        for nombre, funcion in (propiedades or {}).items():
            if not hasattr(modelo, nombre):
                setattr(modelo, nombre, property(funcion))
        for nombre, extra in (selection_add or {}).items():
            extend_selection_choices(modelo, nombre, extra,
                                     (ondelete or {}).get(nombre))
        for indice in (indexes or ()):
            add_meta_index(modelo, indice)
        if luego is not None:
            luego(modelo)
        # ≙ ``_setup_models__`` marca a los descendientes del módulo cargado
        # (``registry.py:426-433``): el destino de un ``_inherit`` se vuelve a
        # marcar —un campo colgado aquí no pasó por ``class_prepared``— y lo
        # completa el barrido perezoso, que es el «tras el módulo» de
        # ``loading.py:193``. No se completa aquí: ``aplicar`` corre dentro
        # de ``lazy_model_operation``, que puede caer a mitad de la
        # construcción de otro modelo (ver ``_setup_fields_on_prepared``).
        mark_model_for_setup(modelo)

    apps.lazy_model_operation(aplicar, resolve_model_key(*destino))


def extend_property(modelo, nombre, funcion):
    """Extiende una ``property`` que YA existe — ≙ ``super().PROP + [...]``.

    Es el hermano de ``extend_model(propiedades=…)``, y la frontera entre los
    dos es exactamente la que su nombre dice:

    - ``propiedades=`` **declara** una property que no existía. No pisa una
      existente, a propósito: pisarla borraría la aportación de quien la
      declaró antes.
    - ``extend_property`` **suma a** la que existe. Envuelve el ``fget``
      instalado en ese momento y le pasa su valor a ``funcion``, que devuelve
      el valor ampliado.

    ``funcion(self, anterior)`` recibe el valor del eslabón previo ya
    calculado, que es lo que el ``super().PROP`` de la fuente entrega. Si la
    property no existía todavía, ``anterior`` llega como ``None`` — el mismo
    desenlace que ``super()`` sobre un atributo ausente.

    **Por qué existe.** Sin él, un addon que quisiera sumar a una property
    tenía dos salidas y las dos estaban mal: ``propiedades=``, que el guard de
    ``extend_model`` **descarta en silencio**, o un ``setattr`` a mano
    duplicado por addon. La primera se ejerció y falló sin ruido — ``hr``
    declaraba sus 32 campos de ``SELF_READABLE_FIELDS`` y ninguno llegaba al
    modelo (:ref:`h-api-834`).

    Es idempotente: reinstalar la misma ``funcion`` es un no-op, igual que
    ``chain_method``.
    """
    previo = getattr(modelo, nombre, None)
    if isinstance(previo, property):
        fget_previo = previo.fget
        if getattr(fget_previo, '_extendida_por', None) is funcion:
            return          # ya está en la cadena
    else:
        fget_previo = None

    def fget(self):
        anterior = fget_previo(self) if fget_previo is not None else None
        return funcion(self, anterior)

    fget.__name__ = nombre
    fget._extendida_por = funcion
    setattr(modelo, nombre, property(fget))
