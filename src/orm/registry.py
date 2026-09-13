"""``Registry`` — fiel a ``odoo/orm/registry.py`` (Odoo 19).

En Odoo el ``Registry`` es el mapa **por base de datos** de nombre de modelo →
clase de modelo (``registry['res.partner']``). Se construye al cargar los addons
de esa DB, cachea la estructura de modelos/campos y coordina el setup del schema.
Es singleton por ``db_name`` (``Registry(db_name)`` devuelve el existente).

Mapeo a Django — **Django ya provee el registro de modelos**, y por eso el
puerto no lo duplica; lo que sí recrea es todo lo que la fuente cuelga del
registro y Django no tiene (el mapa por nombre punteado, el eje de campos y
disparadores, el de schema, la carga y la señalización entre procesos):

===================================  ===================================================
Odoo ``Registry``                    Equivalente Django
===================================  ===================================================
``Registry(db_name)``                ``django.apps.apps`` (registro global de apps)
``registry['res.partner']``          ``apps.get_model('base', 'ResPartner')``
por-DB (multi-tenant)                ``django.db.connections`` + DB router
                                     (``orm/routers.py``, ya presente: multi-DB
                                     DB-per-company SOL-091)
setup de schema al boot              migraciones Django (``makemigrations`` /
                                     ``migrate``)
caché de estructura modelo/campo     metadata ``Model._meta`` (campos, índices, FKs)
===================================  ===================================================

Recrear ``Registry`` sobre Django duplicaría ``django.apps`` y el manejo de
conexiones. La **dimensión por-DB** (que en Odoo justifica un registry por
tenant) aquí la cubre el router multi-DB de ``orm/routers.py`` + ``connections``.
Un addon portado que leía ``self.env.registry[name]`` se adapta a
``apps.get_model(...)``; el "singleton por DB" a ``connections[alias]``.

``_name`` — el mapa nombre punteado → clase
=============================================

La referencia guarda ese mapa **aquí**: ``Registry.models: dict[str,
type[BaseModel]]`` (``odoo19c: odoo/orm/registry.py:222``), con
``__getitem__``/``__setitem__`` (``:317-323``) como interfaz. Este archivo
recrea esa mitad, que es la única de ``Registry`` sin contraparte directa en
Django: ``apps.get_model`` indexa por ``(app_label, ClassName)``, no por el
nombre punteado de la fuente.

Añadido 2026-08-14 por directiva del ejecutor —*"nosotros queremos hacer
esto"*, sobre un modelo que declara ``_name`` y ``_description``. Vive en
``registry.py`` y no en un archivo propio porque **la referencia no tiene un
archivo propio**: tenerlo sería la divergencia de forma que :ref:`h-api-568`
registra.
"""
import inspect
import logging
import sys
import threading
import time
import warnings
from collections import defaultdict, deque
from contextlib import closing, contextmanager, nullcontext
from functools import partial
from collections.abc import Callable, Collection, Iterator, Mapping

from django.apps import apps
from django.db import DatabaseError, connections, transaction
from django.db.models.signals import class_prepared
from django.db.models.utils import make_model_tuple
from django.dispatch import receiver
from psycopg import sql as pg_sql

# El modulo, no el nombre: ``orm.environments`` importa este modulo (``:98``),
# asi que ligar ``sudo`` aqui daria ImportError segun quien cargue primero.
# Importar el MODULO liga el objeto ya presente en ``sys.modules`` aunque este
# a medio inicializar, y el atributo se resuelve al llamar. Es un import de
# nivel de modulo — no una excepcion a ``no-lazy-imports.md``.
import orm.environments

from modules import db as modules_db
from orm.utils import model_field_registry
from tools.func import locked, reset_cached_properties
from tools.lru import LRU
from tools.misc import Collector, OrderedSet, remove_accents
from tools.sql import (SQL, _CONFDELTYPES, create_index, drop_constraint, drop_index,
                       existing_tables, get_foreign_keys, make_index_name)
from tools.sql import add_foreign_key as sql_add_foreign_key

_logger = logging.getLogger('kaupamex.registry')

#: El registro de cambios de schema — ≙ ``_schema`` de la fuente, que lo abre
#: como ``logging.getLogger('odoo.schema')``.
_schema = logging.getLogger('kaupamex.schema')

__all__ = [
    'apps', 'connections',
    'MODELS_BY_NAME', 'name_of', 'model_by_name', 'model_by_key',
    'resolve_model_key', 'check_table_matches_name',
    'registrants_without_table',
    'clear_cache', 'clear_all_caches', 'cache_of',
    'cache_invalidated_names', 'reset_invalidation_record',
    'signaling_table_names',
    'many2one_company_dependents', 'loaded_xmlids',
    'not_null_fields', 'is_not_null',
    '_unaccent', 'UNACCENT_ENABLED',
    'constraint_methods', 'ondelete_methods', 'onchange_methods',
    'clear_marked_methods',
]

#: ≙ ``Registry.loaded_xmlids`` — los identificadores externos que el cargador
#: de data ha visto en esta carga. Lo puebla ``IrModelData._update_xmlids`` y
#: lo consume ``_process_end``, que borra lo que la data ya no declara: una
#: fila con módulo, sin ``noupdate`` y **ausente** de este conjunto es un
#: registro que su módulo dejó de declarar.
loaded_xmlids = set()


#: Tamaño de cada caché de método de modelo, verbatim de la referencia
#: (``odoo19c: odoo/orm/registry.py:51-59``).
_REGISTRY_CACHES = {
    'default': 8192,
    'assets': 512,
    'stable': 1024,
    'templates': 1024,
    'routing': 1024,  # 2 entradas por sitio web
    'routing.rewrites': 8192,  # entradas de url_rewrite
    'templates.cached_values': 2048,  # arbitrario
    'groups': 64,  # ver res.groups
}

#: Dependencias de invalidación, tal cual la referencia (``:64-71``):
#: ``{ 'clave': ('contenedor_1', 'contenedor_3', ...) }``
_CACHES_BY_KEY = {
    'default': ('default', 'templates.cached_values'),
    'assets': ('assets', 'templates.cached_values'),
    'stable': ('stable', 'default', 'templates.cached_values'),
    'templates': ('templates', 'templates.cached_values'),
    'routing': ('routing', 'routing.rewrites', 'templates.cached_values'),
    # el procesamiento de grupos se guarda en la vista
    'groups': ('groups', 'templates', 'templates.cached_values'),
}

def signaling_table_names():
    """Las siete tablas del eje de señalización, en el orden de la fuente.

    ≙ la expresión que la referencia escribe **dos veces** —en
    ``setup_signaling`` (``odoo19c: odoo/orm/registry.py:1043``) y en
    ``get_sequences`` (``:1067``)—: el registro primero, luego una por clave de
    :data:`_CACHES_BY_KEY`.

    **Divergencia de forma declarada, y su razón.** La fuente la repite; aquí
    es una función porque hay un **tercer** consumidor que allá no existe: la
    migración que crea las tablas (``base/migrations/0085_orm_signaling_tables``),
    ya que en este árbol el DDL lo emiten las migraciones. Tres copias de la
    misma lista serían la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohíbe.

    La migración, aun así, **congela sus siete literales** en vez de llamar a
    esta función: una migración es historia, y derivarla del código vivo haría
    que añadir una clave de caché reescribiera el pasado. Una clave nueva se
    queda sin tabla y :meth:`Registry.setup_signaling` la nombra en voz alta,
    que es para lo que su verificación existe.
    """
    return ('orm_signaling_registry',
            *(f'orm_signaling_{cache_name}' for cache_name in _CACHES_BY_KEY))


#: Los contenedores vivos. La referencia los cuelga de la instancia de
#: ``Registry`` (``self.__caches``, ``:233``) porque allá hay un registry por
#: base de datos; aquí el registry es el módulo —la dimensión por-DB la cubre
#: el router de ``orm/routers.py``, como declara el encabezado— así que los
#: contenedores son estado de módulo. Es la misma estructura, en el único
#: singleton que este árbol tiene.
_CACHES = {name: LRU(size) for name, size in _REGISTRY_CACHES.items()}

#: El registro de invalidación **de este hilo** — ≙ los dos campos que la
#: fuente guarda en ``Registry._invalidation_flags`` (``odoo19c:
#: odoo/orm/registry.py:224``): ``registry`` (bool) y ``cache`` (conjunto de
#: nombres vaciados desde la última señal).
#:
#: Vive en el módulo por la misma razón que :data:`_CACHES`, y es la mitad que
#: faltaba: los contenedores son estado de proceso, así que su registro de
#: invalidación también lo es. Antes de reconciliarlo había **dos estructuras
#: paralelas y disjuntas** — un conjunto de módulo que ``clear_cache`` escribía
#: y nadie leía, y un ``threading.local`` de instancia que la property
#: ``Registry.cache_invalidated`` leía y nadie escribía. El eje de señalización
#: se habría portado entero y habría señalizado siempre cero: un verde que no
#: discrimina (``metrica-decide-la-conclusion.md``, sub-patrón D).
#:
#: **Por hilo, no por proceso**, igual que la fuente: la invalidación es del
#: hilo que la hizo, y ``signal_changes`` corre al cerrar la petición en ese
#: mismo hilo. Propagarla a los demás anunciaría un cambio que ellos no ven.
_invalidation = threading.local()


def cache_invalidated_names():
    """Los nombres de caché que **este hilo** vació desde la última señal.

    ≙ el conjunto que la fuente devuelve en ``Registry.cache_invalidated``
    (``:1026-1033``). Devuelve **el mismo** conjunto en cada llamada del hilo:
    quien lo pide lo hace para añadirle un nombre, y uno nuevo por llamada
    perdería lo anotado.
    """
    try:
        return _invalidation.cache
    except AttributeError:
        # silent OK because la ausencia del atributo ES la respuesta «este hilo
        # aún no ha anotado nada», y el cuerpo que sigue lo crea. La fuente lo
        # escribe igual (``:1030-1032``).
        names = _invalidation.cache = set()
        return names


def reset_invalidation_record():
    """Olvida lo que este hilo hubiera anotado — lo llama ``Registry.init``.

    ≙ ``self._invalidation_flags = threading.local()`` de la fuente (``:279``),
    que al inicializar un registro descarta el registro de invalidación entero.
    Aquí el descarte es del hilo que construye, porque la estructura es de
    proceso: un hilo ajeno conserva lo suyo, que es lo que él necesita
    señalizar.
    """
    _invalidation.registry = False
    _invalidation.cache = set()


#: ¿Envuelve el ``ilike`` sus dos lados en ``unaccent(...)``?
#:
#: ≙ el veredicto que la fuente guarda en ``Registry.has_unaccent``
#: (``odoo19c: odoo/orm/registry.py:286``) midiendo ``pg_proc`` al inicializar.
#: Vive **aqui** y no en ``orm/fields.py`` por la misma razón que allá: el
#: registro es quien lo sabe y el campo quien lo consume
#: (``fields.py:1326-1327`` lee ``model.env.registry.unaccent``). Ponerlo al
#: revés fue lo que produjo el ciclo de import al portar :class:`Registry`.
#:
#: Es ``True`` desde 2026-09-03: la extensión ``unaccent`` la crea
#: ``base/migrations/0084_unaccent_extension.py`` en toda base que el ORM
#: construya. La bandera existe para que las **dos** vías de compilación —el
#: lookup ``SqlILike`` y el predicado en memoria— decidan lo mismo.
UNACCENT_ENABLED = True

#: Los siete modelos del registro que un ``Many2one`` NO puede proteger.
#:
#: ≙ ``IR_MODELS`` (``odoo19c: odoo/orm/fields.py:37``). Su unico consumidor
#: alla es ``fields_relational.py:289``:
#: ``if self.ondelete == 'restrict' and self.comodel_name in IR_MODELS``, que
#: degrada esa politica a ``'cascade'``. La razon es que el propio registro se
#: desmonta al desinstalar un modulo, y una FK que lo proteja convierte esa
#: operacion en un error.
#:
#: **Vive aqui y no en ``orm/fields.py``, que es donde la fuente lo declara.**
#: Es la misma divergencia de SITIO que :data:`UNACCENT_ENABLED`, por la misma
#: causa medida: nuestro ``orm/fields.py`` es a la vez el nucleo de
#: :class:`Field` **y** una fachada que re-exporta diez modulos hermanos, entre
#: ellos ``orm.fields_relational`` (``fields.py:92``). La fuente no tiene esa
#: arista —su ``odoo/orm/fields.py`` no importa ``fields_relational``— asi que
#: alla la constante y su consumidor conviven sin ciclo. Aqui importarla desde
#: ``fields_relational`` cierra un 2-ciclo ``fields <-> fields_relational``.
#:
#: El registro es quien nombra a sus propios modelos, asi que este es su hogar
#: natural. ``orm/fields.py`` la re-exporta para que la superficie publica siga
#: siendo la de la fuente.
IR_MODELS = (
    'ir.model', 'ir.model.data', 'ir.model.fields', 'ir.model.fields.selection',
    'ir.model.relation', 'ir.model.constraint', 'ir.module.module',
)


def _unaccent(x):
    """Envuelve ``x`` en la llamada SQL ``unaccent(...)``, repartiendo por tipo.

    ≙ ``_unaccent`` (``odoo19c: odoo/orm/registry.py:76-81``). La fuente lo
    asigna a ``Registry.unaccent`` cuando la extension esta instalada
    (``:289``) y la identidad cuando no; sus consumidores alla son el indice
    trigram (``:862-864``) y el compilador de ``ilike`` de ``osv/expression``
    (``:449``).

    **Divergencia de mecanismo, no de contrato.** La fuente tipa la tercera
    rama con ``psycopg2.sql.Composable``; este arbol corre **psycopg 3**
    (medido: ``psycopg.__version__`` == ``3.3.4``), cuyo homonimo vive en
    ``psycopg.sql``. Es la misma clase con el mismo nombre en otro paquete,
    asi que la rama se conserva entera apuntada al paquete que este stack
    instala — no se recorta.

    Las tres ramas devuelven tres tipos distintos, igual que la fuente: un
    ``SQL`` compuesto, un ``psycopg.sql.Composed``, y la interpolacion de
    cadena para el resto.

    **Que extension.** La que provee la funcion es ``unaccent``, el contrib de
    PostgreSQL. Se crea en toda base que el ORM construya
    (``base/migrations/0084_unaccent_extension.py``) y tambien la declara el
    provisioner (``db: provisioners/postgresql/db_setup.sh:194-195``); hacen
    falta las dos, porque pytest levanta sus bases desde las migraciones y ahi
    el provisioner no pasa.

    Lo que la fuente pregunta, sin embargo, **no es la extension sino la
    funcion**: ``modules.db.has_unaccent`` mira ``pg_proc``, asi que cualquier
    homonima de un argumento sirve. El ``provolatile`` decide aparte si es
    indexable.

    **Quien lo cablea.** ``orm.fields.UNACCENT_ENABLED`` es ``True`` desde
    2026-09-03, y con el las dos vias de compilacion a la vez: el lookup
    ``SqlILike`` envuelve los dos lados y el predicado en memoria normaliza con
    ``remove_accents``.
    """
    if isinstance(x, SQL):
        return SQL("unaccent(%s)", x)
    if isinstance(x, pg_sql.Composable):
        return pg_sql.SQL('unaccent({})').format(x)
    return f'unaccent({x})'


def cache_of(cache_name):
    """El contenedor vivo de ``cache_name`` ≙ ``Registry.__caches[name]``."""
    return _CACHES[cache_name]


def clear_cache(*cache_names):
    """Vacía las cachés de los métodos decorados con ``tools.ormcache`` cuyo
    nombre esté en ``cache_names`` ≙ ``Registry.clear_cache``
    (``odoo19c: odoo/orm/registry.py:971-987``).
    """
    cache_names = cache_names or ('default',)
    assert not any('.' in cache_name for cache_name in cache_names)
    for cache_name in cache_names:
        for cache in _CACHES_BY_KEY[cache_name]:
            _CACHES[cache].clear()
        cache_invalidated_names().add(cache_name)

    # información sobre la causa de la invalidación
    if _logger.isEnabledFor(logging.DEBUG):
        # podría interesar en info, pero antes hay que minimizar la
        # invalidación, sobre todo en setup de tests y crons
        _logger.debug('Invalidating %s model caches', ','.join(cache_names))


def clear_all_caches():
    """Vacía todas las cachés de los métodos decorados con ``tools.ormcache``
    ≙ ``Registry.clear_all_caches`` (``odoo19c: odoo/orm/registry.py:989-1001``).
    """
    for cache_name, caches in _CACHES_BY_KEY.items():
        for cache in caches:
            _CACHES[cache].clear()
        cache_invalidated_names().add(cache_name)

    _logger.debug('Invalidating all model caches')


#: ``'product.removal' -> <class ProductRemoval>``. Ver :func:`_ensure_seeded`
#: sobre por qué se puebla por dos vías y no por una.
MODELS_BY_NAME = {}


def _register(model):
    """Anota el modelo bajo su ``_name``, rechazando el nombre duplicado.

    El paso hermano —resolver ``_rec_name``— vive en ``orm/model_classes.py``,
    que es donde la fuente lo declara, y **no** se llama desde aquí: este
    módulo es el que ``model_classes`` importa, así que la llamada inversa
    cerraría el ciclo. Cada uno cuelga de la señal por su lado.
    """
    name = model.__dict__.get('_name')
    if not name:
        return
    previous = MODELS_BY_NAME.get(name)
    if previous is not None and previous is not model:
        label = lambda cls: getattr(getattr(cls, '_meta', None), 'label',
                                    cls.__name__)
        raise ValueError(
            f'Dos modelos declaran _name={name!r}: '
            f'{label(previous)} y {label(model)}. '
            f'El nombre punteado identifica un modelo, no una familia.'
        )
    MODELS_BY_NAME[name] = model


#: El ``app_label`` bajo el que viaja el asa opaca que sustituye a un ``_name``
#: punteado. Medido antes de elegirlo: ninguno de los 137 ``app_label``
#: instalados se llama ``orm``, y ninguno de los 224 ``_name`` del árbol
#: colisiona con otro al colapsar sus puntos en guiones bajos.
SENTINEL_APP_LABEL = 'orm'


def sentinel_label(name):
    """La etiqueta legal de Django que sustituye al ``_name`` punteado.

    La fuente **no deriva ninguna clave**: ``comodel_name`` es una cadena
    (``odoo19c: odoo/orm/fields_relational.py:36``) y la existencia del
    destinatario se afirma contra un registro cuya clave *es* el nombre
    punteado (``odoo/orm/registry.py:84``, ``__getitem__`` en ``:317``).

    Django hace lo contrario: ``make_model_tuple``
    (``django/db/models/utils.py:5-25``) parte la cadena por el punto, y con
    dos o más puntos levanta ``ValueError`` **en el cuerpo de la clase**, antes
    de que exista entrada pendiente que arreglar. Por eso el porte no le
    entrega el nombre: le entrega esta etiqueta, y el nombre de la fuente
    sobrevive en ``field.comodel_name``, que es el atributo que la fuente
    declara.
    """
    return f'{SENTINEL_APP_LABEL}.{name.replace(".", "_").lower()}'


def sentinel_key(name):
    """La clave con que Django indexa la etiqueta de :func:`sentinel_label`.

    Coincide por construcción con lo que ``make_model_tuple`` derivaría de esa
    etiqueta; el test del puerto lo afirma contra el símbolo real de Django en
    vez de replicar su aritmética aquí.
    """
    return (SENTINEL_APP_LABEL, name.replace('.', '_').lower())


def _flush_sentinels(model):
    """Vacía las claves centinela a las que el modelo responde. Son **dos**.

    El árbol usa los dos vocabularios: el ``_name`` de la fuente
    (``'report.paperformat'``) y la etiqueta de Django en minúsculas
    (``'base.reportpaperformat'``), que es como una **migración** tiene que
    nombrarlo — el estado de una migración rechaza la referencia a la clase
    (*"Model fields in ModelState.fields cannot refer to a model class"*), así
    que ahí la cadena en minúsculas no es un descuido sino el único camino. Un
    modelo sin ``_name`` sólo responde a la segunda.
    """
    name = model.__dict__.get('_name')
    if name:
        flush_sentinel(name, model)
    flush_sentinel(model._meta.label_lower, model)


def flush_sentinel(name, model):
    """Aplica las operaciones que Django dejó pendientes bajo la clave centinela.

    Es el porte mínimo de ``Apps.do_pending_operations``
    (``django/apps/registry.py:428-435``), que sólo sabe vaciar la clave real
    del modelo. Cada función pendiente es el ``partial`` que
    ``lazy_related_operation`` encoló (``related.py:80-86``) y que termina en
    ``resolve_related_class`` (``:392-394``), donde se fija
    ``remote_field.model`` y se llama a ``do_related_class``.

    Corre desde ``class_prepared``, que ``ModelBase.__new__`` emite **antes**
    de ``register_model`` (``base.py:387`` contra ``:388``): el modelo ya tiene
    su ``_meta`` poblado, que es todo lo que la función pendiente necesita.

    **El registro es el del modelo, no el global.** Django encola el pendiente
    en ``model._meta.apps`` —``lazy_related_operation`` lo fija verbatim en
    ``related.py:85``— y lo vacía en ese mismo, porque ``ModelBase.__new__``
    llama a ``new_class._meta.apps.register_model`` (``base.py:388``) y
    ``do_pending_operations`` recorre su propio ``_pending_operations``
    (``apps/registry.py:433``). Un modelo bajo ``isolate_apps`` o renderizado
    por el ``StateApps`` de una migración tiene OTRO ``Apps``: apuntar al
    global deja la entrada sin vaciar para siempre, y los system checks la
    reportan como referencia perezosa colgada (``models.E022``).
    """
    for function in model._meta.apps._pending_operations.pop(
            sentinel_key(name), []):
        function(model)


def register_abstract(cls):
    """Anota bajo su ``_name`` una clase que **no** es modelo de Django.

    ≙ lo que la referencia obtiene gratis: allá ``ir.fields.converter`` es un
    ``AbstractModel``, así que su registro lo conoce y ``env['ir.fields.converter']``
    lo devuelve. Aquí una clase sin columnas no pasa por ``ModelBase``, así que
    la señal ``class_prepared`` nunca dispara para ella y hay que anotarla a
    mano — es la misma tabla y el mismo nombre punteado, sólo que por la puerta
    que este stack deja abierta.

    Se usa donde la referencia usa ``env[...]`` sobre un modelo abstracto: un
    consumidor que no puede importar la clase (porque cerraría ciclo) la
    resuelve por nombre, igual que allá.
    """
    _register(cls)
    return cls


@receiver(class_prepared, dispatch_uid='orm.registry.register_name')
def _register_name(sender, **kwargs):
    """Registra el ``_name`` del modelo recién construido, si lo declara.

    ``class_prepared`` dispara al final de ``ModelBase.__new__``, así que el
    modelo ya tiene ``_meta`` poblado. Un modelo sin ``_name`` no se registra —
    no es un error: los 290 del árbol están así hasta que se toquen.

    Y vacía las claves centinela a las que este modelo responde. Son **dos**
    vocabularios, no uno, y el árbol usa los dos: su ``_name`` de la fuente
    (``'report.paperformat'``) y su etiqueta de Django en minúsculas
    (``'base.reportpaperformat'``), que es como una **migración** tiene que
    nombrarlo — el estado de una migración rechaza la referencia a la clase
    (*"Model fields in ModelState.fields cannot refer to a model class"*), así
    que ahí la cadena en minúsculas no es un descuido sino el único camino.
    Un modelo sin ``_name`` sólo responde a la segunda.
    """
    _register(sender)
    # El vaciado NO puede correr aqui, y el orden lo dice ``ModelBase.__new__``:
    # ``_prepare()`` emite esta senal en ``base.py:387`` y ``register_model``
    # ocurre en ``:388``. Django encadena el pendiente —``lazy_related_operation``
    # espera PRIMERO al modelo que declara el campo y solo despues encola la
    # clave del destino (``apps/registry.py:400-426``)—, asi que al llegar aqui
    # la clave centinela todavia no existe: medido, quedaba viva tras el pase.
    # Se difiere con la misma primitiva de Django, encolando detras de la suya.
    #
    # Y se encola en el registro DEL MODELO, no en el global: es el que Django
    # usa para encolar (``related.py:85``) y para vaciar (``base.py:388`` ->
    # ``apps/registry.py:433``). Con el global, un modelo desechable bajo
    # ``isolate_apps`` o uno del ``StateApps`` de una migracion registra en
    # otro ``Apps`` y la entrada queda colgada: medido, dos ``models.E022``
    # —``migrations.migration`` y un modelo de prueba de ``stock``— que el
    # arbol no tenia antes de este porte.
    sender._meta.apps.lazy_model_operation(
        _flush_sentinels, make_model_tuple(sender))


def _ensure_seeded():
    """Barre el registro de Django si la señal llegó tarde.

    **La señal sola no basta, y la razón es la misma de** ``H-API-577``: sólo
    dispara para los modelos preparados **después** de importar este módulo. Si
    algo lo importa tras ``django.setup()`` —un test, un guion, un ``ready()``
    tardío— la tabla queda vacía y el nombre punteado no resuelve, sin error
    que lo delate.

    Medido: con el módulo importado al final de un guion, el registro daba
    ``[]`` con ``ProductRemoval`` ya cargado y declarando su ``_name``.

    Por eso hay dos vías, y ninguna sobra: la señal cubre lo que llega después,
    este barrido cubre lo que ya estaba. Corre una sola vez por proceso porque
    ``apps.get_models()`` es barato pero no gratis, y se salta si el registro de
    apps aún no está listo — en ese caso la señal es la única vía y es correcta.
    """
    if _ensure_seeded.hecho or not apps.ready:
        return
    for model in apps.get_models(include_auto_created=True):
        _register(model)
    _ensure_seeded.hecho = True


_ensure_seeded.hecho = False


def name_of(model):
    """El ``_name`` declarado del modelo, o ``None``.

    Se lee de ``__dict__`` y no con ``getattr`` a propósito: con ``getattr``
    una subclase heredaría el ``_name`` de su padre y diría ser el mismo modelo.
    """
    return model.__dict__.get('_name')


def model_by_name(name):
    """La clase que declara ese ``_name``, o ``None`` si no está cargada."""
    _ensure_seeded()
    return MODELS_BY_NAME.get(name)


def model_by_key(key):
    """La clase de un modelo nombrado en **cualquiera** de las dos formas.

    Puente que nuestra divergencia de almacenamiento necesita, y que la fuente
    no necesita: allá ``self.env[name]`` sólo admite el nombre punteado porque
    es el único que existe. Aquí conviven dos:

    - ``'res.partner'`` — el ``_name`` de la referencia, que es la clave de
      :data:`MODELS_BY_NAME`;
    - ``'base.ResPartner'`` — el *label* de Django, que es lo que guardan las
      columnas de texto que apuntan a un modelo (``ir_model.model``,
      ``ir_actions_server.model_name``, ``ir_rule.model_name``).

    Devuelve ``None`` si ninguna de las dos resuelve, en vez de levantar: sus
    consumidores leen una **columna**, y una fila puede sobrevivir al modelo
    que nombraba (módulo desinstalado, clase renombrada). Es el mismo criterio
    con que ``IrModel.django_model`` devuelve ``None``.

    :func:`resolve_model_key` es la hermana que **sí** levanta, porque su
    consumidor —``extend_model``— nombra un destino que el programador escribió
    y cuya ausencia es un error de programa, no un dato viejo.
    """
    if not key:
        return None
    _ensure_seeded()
    model = MODELS_BY_NAME.get(key)
    if model is not None:
        return model
    try:
        app_label, model_name = key.split('.', 1)
    except ValueError:
        return None
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def resolve_model_key(*args):
    """Normaliza las dos formas de nombrar un modelo a la clave de Django.

    Acepta:

    - ``resolve_model_key('product.removal')`` — el nombre de la referencia,
      **si** el modelo ya está registrado;
    - ``resolve_model_key('stock', 'ProductRemoval')`` — el par de Django, que
      no exige que el modelo exista todavía.

    Devuelve siempre ``(app_label, model_name_en_minúscula)``, que es la clave
    que ``Apps.do_pending_operations`` reconstruye (ver ``H-API-577``).

    El nombre punteado **sólo** resuelve si el modelo está cargado: la tabla la
    puebla la señal, y antes de que el módulo se importe no hay nada que
    consultar. Para el caso tardío —extender algo aún no cargado— hay que dar el
    par de Django. Es la única asimetría entre las dos formas, y es inherente:
    la referencia no la tiene porque su registro conoce todos los nombres antes
    de construir ninguna clase.
    """
    if len(args) == 2:
        label, name = args
        return (label, name.lower())
    if len(args) != 1:
        raise TypeError(
            'resolve_model_key acepta "app.Modelo" (dos argumentos) o '
            'el nombre punteado de la referencia (uno), no %d' % len(args))

    dotted_name = args[0]
    _ensure_seeded()
    model = MODELS_BY_NAME.get(dotted_name)
    if model is None:
        raise LookupError(
            f'Ningún modelo cargado declara _name={dotted_name!r}. '
            f'Si el destino todavía no se ha importado, nómbralo con el par '
            f'de Django: extend_model("app", "Modelo", …).'
        )
    return (model._meta.app_label, model._meta.model_name)


def check_table_matches_name(models_found=None):
    """¿Coincide ``db_table`` con lo que la referencia derivaría de ``_name``?

    La referencia obtiene la tabla por sustitución; aquí es una declaración
    humana, así que las dos pueden divergir sin que nada avise. Devuelve la
    lista de ``(label, _name, db_table_esperado, db_table_real)`` que NO
    coinciden — vacía si todo cuadra.

    Sólo mira los modelos que declaran ``_name``: el resto no tiene con qué
    comparar, y contarlos como divergencia sería medir su ausencia, no su
    forma.

    **Un registrante sin tabla no es una divergencia — es otra población.**
    El registro por nombre admite clases que no son modelos de Django: el
    equivalente del ``AbstractModel`` de la fuente, que declara ``_name`` y no
    tiene tabla (``IrFieldsConverter`` es uno). Preguntarle su ``db_table``
    reventaba con ``AttributeError``, así que este check moría en vez de dar
    veredicto. Ahora se apartan, **y se pueden contar** con
    :func:`registrants_without_table` — un salto silencioso dejaría el verde
    sin discriminar «no hay divergencias» de «no pude comparar».

    **``_table`` gana sobre la sustitución**, como en la fuente: allá
    ``model_cls._table = model_cls._name.replace('.', '_')``
    (``odoo19c: odoo/orm/model_classes.py:266``) es sólo el **default**, y una
    clase que declara ``_table`` lo sobreescribe. Nueve de los diez modelos de
    ``ir_actions.py`` lo hacen (``ir.actions.act_window`` → ``ir_act_window``),
    así que sin honrarlo este check reportaría como divergencia la forma que la
    referencia declara a propósito.
    """
    if models_found is None:
        _ensure_seeded()
        models_found = list(MODELS_BY_NAME.values())
    divergences = []
    for model in models_found:
        name = name_of(model)
        if not name:
            continue
        meta = getattr(model, '_meta', None)
        if meta is None:
            continue                      # sin tabla: lo cuenta el hermano
        expected = model.__dict__.get('_table') or name.replace('.', '_')
        actual = meta.db_table
        if expected != actual:
            divergences.append((meta.label, name, expected, actual))
    return divergences


def registrants_without_table(models_found=None):
    """Los registrantes por ``_name`` que NO tienen tabla que comparar.

    Es el denominador que :func:`check_table_matches_name` aparta. Devuelve
    ``(nombre_de_clase, _name)`` de cada clase que declara ``_name`` sin ser un
    modelo de Django — el equivalente aquí del ``AbstractModel`` de la fuente,
    que en el registro existe y en el catálogo de tablas no.

    Se exporta para que el salto sea **medible** y no silencioso: sin esta
    función, un cero de divergencias no distinguiría «todo cuadra» de «no había
    nada que comparar».
    """
    if models_found is None:
        _ensure_seeded()
        models_found = list(MODELS_BY_NAME.values())
    return [
        (model.__name__, name_of(model))
        for model in models_found
        if name_of(model) and getattr(model, '_meta', None) is None
    ]



def many2one_company_dependents(model_label):
    """Los ``Many2one`` dependientes de empresa que apuntan a este modelo.

    ≙ ``Registry.many2one_company_dependents``
    (``odoo19c: odoo/orm/registry.py``), el mapa que la fuente indexa por
    ``_name`` del modelo apuntado. Lo consume ``base_partner_merge``: al
    fusionar dos contactos hay que repuntar también los valores por empresa
    que guardan su id dentro de un ``jsonb``, y una FK del catálogo no los ve.

    DIVERGENCIA DE MECANISMO, declarada: allá es un atributo memorizado del
    ``Registry``, que se puebla al cargar el registro; aquí se deriva de
    ``apps.get_models()`` en la llamada. El coste es el recorrido de los
    modelos instalados, que su único llamador paga una vez por fusión — no un
    bucle caliente. Memorizarlo exigiría invalidarlo, y no hay evento que lo
    dispare: el conjunto de campos no cambia en caliente.

    **Devuelve vacío por dato, no por construcción.** Hoy ningún ``Many2one``
    se declara ``company_dependent`` porque su despachador todavía no lo
    cablea (tarea **#129**); el día que uno lo haga, aparece aquí solo.

    :param model_label: la etiqueta del modelo apuntado (``app.Modelo``).
    :returns: lista de ``(modelo, campo)`` — el par que el llamador necesita
        para nombrar tabla y columna.
    """
    encontrados = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not getattr(field, 'company_dependent', False):
                continue
            if getattr(field, 'base_type', None) != 'many2one':
                continue
            related = getattr(field, 'company_dependent_comodel', None)
            if related == model_label:
                encontrados.append((model, field))
    return encontrados


# ═══════════════════════════════════════════════════════════════════════════
# ``field_depends`` — ≙ ``odoo19c: odoo/orm/registry.py:252-253``
# ═══════════════════════════════════════════════════════════════════════════
#
# Allá son dos ``Collector`` que el setup del registro **puebla** al cargar los
# addons (``:410-474``): ``field_depends[campo]`` da los nombres punteados de
# los que ese campo depende, y ``field_depends_context[campo]`` las claves de
# contexto. El consumidor directo es ``Field._description_depends``
# (``odoo/orm/fields.py:902``), que los publica al cliente.
#
# Aquí no hay fase de setup que poblar: Django carga los modelos y termina. Así
# que el mapa se **deriva** de lo ya declarado, y se deriva una sola vez —
# ``@api.depends`` deja su tupla en ``func._depends`` (``orm/decorators.py:23``),
# y un campo calculado nombra su método en ``compute``.
#
# La derivación es la misma información por otro camino: allá el decorador la
# entrega al setup, aquí el mapa va a buscarla al método. Lo que NO se hereda
# es la invalidación parcial de ``:474``, que existe porque allá el registro se
# reconstruye por base; aquí se vacía entero con :func:`clear_field_depends`.


class _DerivedCollector:
    """Mapa campo → tupla, derivado de lo declarado y cacheado entero.

    ≙ ``Collector`` (``odoo19c: odoo/tools/misc.py``) en su lado de lectura:
    un campo sin entrada devuelve la tupla vacía, nunca ``KeyError``. Esa
    parte del contrato importa — ``_description_depends`` lo consulta para
    todo campo, tenga o no dependencias declaradas.
    """

    #: Cual de los dos elementos del par de ``get_depends`` consume este
    #: colector: 0 las dependencias, 1 las de contexto.
    INDEX = 0

    def __init__(self, marker):
        self.marker = marker
        self._table = None

    @staticmethod
    def _resolve(declared, model):
        """La tupla de lo declarado, resolviendo la forma invocable.

        ``@api.depends`` y ``@api.constrains`` admiten **un solo argumento
        invocable** en vez de nombres (``odoo19c: odoo/orm/decorators.py:265``
        — *"One may also pass a single function as argument. In that case, the
        dependencies are given by calling the function with the field's
        model"*). La fuente lo resuelve al leerlo, en
        ``odoo19c: odoo/orm/fields.py:595``::

            depends.extend(deps(model) if callable(deps) else deps)

        Aquí el lector es este colector, así que la resolución vive aquí. Sin
        ella un ``_depends`` invocable reventaba con ``TypeError`` al pasar por
        ``tuple()`` — la forma existía en el decorador y no tenía quien la
        leyera.
        """
        if callable(declared):
            declared = declared(model)
        return tuple(declared)

    def _declared_by_the_field(self, field, model):
        """Lo que ``Field.get_depends`` produce, o ``None`` si no lo publica.

        El productor es ``get_depends`` (``odoo19c: odoo/orm/fields.py:561``),
        que decide las tres ramas —``_depends`` explicito, ``related`` y el
        recorrido del MRO sobre la funcion de calculo—. Leer el atributo en
        crudo, que es lo que este colector hacia, veia solo la primera y media:
        el ``related`` no aportaba nada y del computo tomaba una sola funcion.

        Devuelve ``None`` —y no la tupla vacia— cuando el campo no lleva el
        metodo, para que el respaldo de :meth:`_build` distinga «el productor
        dice que no hay» de «este objeto no es un campo nuestro». La relacion
        inversa de Django entra por ahi: ``_meta.get_fields()`` la incluye y no
        hereda de ``models.Field`` (tarea **#347**).
        """
        producer = getattr(field, 'get_depends', None)
        if producer is None:
            return None
        return producer(model)[self.INDEX]

    def _build(self):
        table = {}
        for model in apps.get_models():
            for field in model._meta.get_fields():
                declared = self._declared_by_the_field(field, model)
                if declared is None:
                    declared = getattr(field, self.marker, None)
                    if declared is None:
                        compute = getattr(field, 'compute', None)
                        method = getattr(model, compute, None) if compute else None
                        declared = getattr(method, self.marker, None)
                if declared:
                    table[field] = self._resolve(declared, model)
        return table

    def __getitem__(self, field):
        if self._table is None:
            self._table = self._build()
        return self._table.get(field, ())

    def __contains__(self, field):
        return bool(self[field])

    def pop(self, field, default=None):
        """Retira la entrada de ``field``, o devuelve ``default`` si no estaba.

        ≙ el ``self.field_depends.pop(f, None)`` de ``Registry._discard_fields``
        (``odoo19c: odoo/orm/registry.py:577``). Alla ``field_depends`` es un
        ``dict`` y hereda ``pop``; aqui el mapa se deriva y hay que exponerlo.
        Fuerza la derivacion antes de retirar: sin eso, retirar de un mapa aun
        no construido no quitaria nada y la siguiente consulta lo volveria a
        traer.
        """
        if self._table is None:
            self._table = self._build()
        return self._table.pop(field, default)

    def clear(self):
        """≙ ``Collector.clear`` (``:421-422``) — el mapa se vuelve a derivar
        en la siguiente consulta."""
        self._table = None


#: ≙ ``Registry.field_depends`` (``:252``).
field_depends = _DerivedCollector('_depends')

class _DerivedContextCollector(_DerivedCollector):
    """El hermano de :class:`_DerivedCollector` para el segundo elemento.

    ``get_depends`` devuelve el par entero; los dos colectores consumen el mismo
    productor y se reparten por :attr:`INDEX`, en vez de derivar cada uno por su
    cuenta y arriesgar que discrepen.
    """

    INDEX = 1


#: ≙ ``Registry.field_depends_context`` (``:253``).
field_depends_context = _DerivedContextCollector('_depends_context')


class _MarkedMethodCollector:
    """Metodos de un modelo que llevan un marcador, derivados y cacheados.

    Es el hermano de :class:`_DerivedCollector` para el otro eje: aquel recorre
    los CAMPOS de cada modelo buscando un marcador; este recorre los METODOS de
    un modelo dado. Los dos derivan de lo declarado y los dos se invalidan
    enteros.

    **Donde vive el memo, y por que no en la clase.** La fuente declara los
    tres como ``@property`` sobre ``BaseModel`` y memoiza el resultado EN LA
    CLASE del modelo (``odoo19c: odoo/orm/models.py:544``, ``:556``, ``:592``:
    *"optimization: memoize result on cls, it will not be recomputed"*). Aqui
    ``BaseModel`` es el ``Model`` de Django: colgarle una ``property`` nuestra
    alcanzaria a ``auth``, ``contenttypes`` y a todo modelo de tercero — la
    colision que barre la tarea **#98**. El memo vive en este mapa, y el reset
    que ``_prepare_setup`` hace reasignando la property (``model_classes.py:
    344-346``) es aqui :func:`clear_marked_methods`.

    **``getattr_static``, no ``getmembers``, y no es preferencia.** La fuente
    usa ``inspect.getmembers``, que LEE cada atributo — alla eso es inocuo. Un
    modelo de Django declara descriptores que se resuelven al leerlos
    (``orm.fields_nonstored.NonStored`` calcula su default consultando el
    registro), asi que recorrer la clase con ``getattr`` los ejecutaria.
    ``getattr_static`` devuelve el objeto sin dispararlos. Es la misma razon
    por la que ``addons/web/models/models.py`` ya lo hacia en su copia local.

    *Metrica:* atributos de la clase, resueltos sin ejecutar descriptores, que
    declaren el marcador.
    *Ciega a:* un metodo que el modelo resuelva en un ``__getattr__`` propio —
    no aparece en ``dir()``. Es la misma ceguera que ``_delegable_field_names``
    declara para su eje.
    """

    def __init__(self, marker):
        self.marker = marker
        self._table = {}

    def _marked(self, model_cls):
        """Los metodos de ``model_cls`` que declaran el marcador.

        ≙ el ``getmembers(cls, is_constraint)`` de la fuente (``:534``), cuyo
        predicado es ``callable(func) and hasattr(func, '_constrains')``.
        """
        found = []
        for name in dir(model_cls):
            if name.startswith('__'):
                continue
            try:
                attr = inspect.getattr_static(model_cls, name)
            except AttributeError:
                continue
            func = getattr(attr, '__func__', attr)
            if callable(func) and getattr(func, self.marker, None) is not None:
                found.append((name, func))
        found.sort()
        return found

    def __call__(self, model_cls):
        if model_cls not in self._table:
            self._table[model_cls] = self._build(model_cls)
        return self._table[model_cls]

    def clear(self):
        """El reset de ``_prepare_setup`` (``model_classes.py:344-346``)."""
        self._table = {}


class _ConstraintMethods(_MarkedMethodCollector):
    """≙ ``BaseModel._constraint_methods`` (``odoo19c: odoo/orm/models.py:
    519-546``) — «Return a list of methods implementing Python constraints».

    Devuelve una **tupla**, no la lista de la fuente: ningun consumidor la
    muta, y es la forma que los colectores de este modulo ya tienen. Los
    nombres declarados siguen en ``func._constrains``, que es donde
    :func:`~orm.models._validate_fields` los lee.

    **La forma invocable se envuelve, no se sobreescribe.** La fuente admite
    ``@api.constrains(lambda self: self._get_plan_fnames())`` y resuelve la
    llamada en un **proxy** con los nombres ya fijos (``:526-532``), dejando
    intacto el ``_constrains`` invocable del metodo original. Medido en
    ``odoo19c``: **5** declarantes, uno de ellos en ``base``
    (``res_company.py:426``); aqui **0** todavia.

    Reescribir el atributo sobre el propio metodo —que es lo que esta clase
    hacia hasta la tarea **#334**— parece equivalente y no lo es: **destruye
    el invocable en la primera lectura**. Tras un
    :func:`clear_marked_methods` el metodo ya solo tendria la tupla de aquella
    vez, asi que un ``lambda`` cuyo resultado dependa del estado —los cinco de
    la fuente llaman a un metodo del modelo— quedaria congelado en su primera
    respuesta. La fuente re-resuelve en cada reconstruccion porque nunca toca
    el original.

    **A quien se le pasa el invocable** es la unica divergencia: la fuente lo
    llama con ``self.sudo()``, un recordset vacio y elevado. Aqui el analogo
    de un recordset vacio es una **instancia sin guardar**, y la elevacion es
    un gestor de contexto (``orm.environments.sudo``) en vez de un receptor
    distinto — la misma asimetria que :func:`~orm.models._validate_fields`
    declara para su eje.

    **Los dos avisos se portan** (``:539-542``): un nombre que no es campo, y
    un campo que no se puede escribir. Sin ellos un ``@api.constrains`` con
    una errata queda mudo, que es justo lo que la fuente evita.
    """

    def __init__(self):
        super().__init__('_constrains')

    def _build(self, model_cls):
        methods = []
        for name, func in self._marked(model_cls):
            if callable(func._constrains):
                func = self._wrap(func, model_cls)
            self._warn_about_declared_names(model_cls, name, func)
            methods.append(func)
        return tuple(methods)

    @staticmethod
    def _wrap(func, model_cls):
        """El proxy de la fuente (``:526-532``), con los nombres ya resueltos.

        Deja ``func._constrains`` invocable donde estaba: el proxy es otro
        objeto, y el original sigue disponible para la proxima reconstruccion.
        """
        with orm.environments.sudo():
            names = tuple(func._constrains(model_cls()))

        def wrapper(self):
            return func(self)

        wrapper._constrains = names
        wrapper.__name__ = getattr(func, '__name__', 'wrapper')
        wrapper.__doc__ = func.__doc__
        return wrapper

    @staticmethod
    def _warn_about_declared_names(model_cls, attr, func):
        """≙ los dos avisos de la fuente (``odoo19c: odoo/orm/models.py:
        539-542``), verbatim en su texto.

        Lee el mapa con ``model_field_registry``, que es lo que ``_fields``
        devuelve (``orm/models.py:1449``), y lo lee **de la clase**: aquel es
        una property de instancia y fabricar una fila solo para leer su
        registro seria trabajo por nada.

        *Ciega a:* un nombre que el modelo resuelva fuera de ``_fields`` —
        misma ceguera que ``_fields`` ya declara para su propio contrato— y a
        una clase sin ``_meta``, que no es un modelo y por tanto no declara
        campo alguno contra el que comparar.
        """
        if not hasattr(model_cls, '_meta'):
            return
        fields = model_field_registry(model_cls)
        for name in func._constrains:
            field = fields.get(name)
            if not field:
                _logger.warning(
                    "method %s.%s: @constrains parameter %r is not a field name",
                    getattr(model_cls, '_name', model_cls.__name__), attr, name)
            elif not (getattr(field, 'store', False)
                      or getattr(field, 'inverse', None)
                      or getattr(field, 'inherited', False)):
                _logger.warning(
                    "method %s.%s: @constrains parameter %r is not writeable",
                    getattr(model_cls, '_name', model_cls.__name__), attr, name)


class _OndeleteMethods(_MarkedMethodCollector):
    """≙ ``BaseModel._ondelete_methods`` (``models.py:548-558``) — «Return a
    list of methods implementing checks before unlinking».

    El valor del marcador **no es un booleano de presencia**: es el
    ``at_uninstall`` que el decorador guarda, y ``unlink`` lo lee para decidir
    si el metodo corre tambien al desinstalar el modulo (``:4207``: *"func.
    _ondelete is True if it should be called during uninstallation"*). Por eso
    el colector no puede filtrar por verdad — un ``at_uninstall=False`` es
    ``False`` y sigue siendo un metodo marcado.
    """

    def __init__(self):
        super().__init__('_ondelete')

    def _build(self, model_cls):
        return tuple(func for _name, func in self._marked(model_cls))


class _OnchangeMethods(_MarkedMethodCollector):
    """≙ ``BaseModel._onchange_methods`` (``models.py:560-593``) — «Return a
    dictionary mapping field names to onchange methods».

    Devuelve un ``dict`` de tuplas donde la fuente devuelve un
    ``defaultdict(list)``. La diferencia es observable en un solo punto y a
    favor: ``_has_onchange`` pregunta ``field.name in self._onchange_methods``
    (``:6970``), y sobre un ``defaultdict`` una lectura previa por ``[]``
    habria creado la clave. Con un ``dict`` la ausencia se mantiene ausente.

    **La mitad de ``change_default`` no se porta todavia.** La fuente anade un
    metodo sintetico por cada campo con ``change_default`` (``:583-589``), que
    lee los valores por defecto de ``ir.default`` para la condicion
    ``campo=valor``. Medido: **0** campos declaran ``change_default`` en este
    arbol, asi que el bucle no tendria sobre que iterar. Queda como DESCONOCIDO
    con condicion de cierre — se porta en cuanto el primer campo lo declare, y
    su sucesor es la tarea **#335**.
    """

    def __init__(self):
        super().__init__('_onchange')

    def _build(self, model_cls):
        methods = defaultdict(list)
        for _name, func in self._marked(model_cls):
            for field_name in func._onchange:
                methods[field_name].append(func)
        return {name: tuple(funcs) for name, funcs in methods.items()}


#: ≙ ``BaseModel._constraint_methods`` (``odoo19c: odoo/orm/models.py:519``).
constraint_methods = _ConstraintMethods()

#: ≙ ``BaseModel._ondelete_methods`` (``:548``).
ondelete_methods = _OndeleteMethods()

#: ≙ ``BaseModel._onchange_methods`` (``:560``).
onchange_methods = _OnchangeMethods()


def clear_marked_methods():
    """Vacia los tres mapas de metodo marcado.

    ≙ el bloque de ``_prepare_setup`` que reasigna las tres propiedades
    memoizadas (``odoo19c: odoo/orm/model_classes.py:343-346``: *"reset
    properties memoized on model_cls"*). Alla el reset es por modelo porque el
    memo vive en su clase; aqui el mapa es de modulo y se vacia entero, con el
    mismo criterio que :func:`clear_field_depends` ya declara para su eje.
    """
    constraint_methods.clear()
    ondelete_methods.clear()
    onchange_methods.clear()


class _ComputedGrouper:
    """Mapa campo → los campos que calcula el MISMO método.

    ≙ ``Registry.field_computed`` (``odoo19c: odoo/orm/registry.py:515``). Su
    contrato tiene dos mitades y las dos importan:

    - un campo calculado devuelve la lista de **todos** los campos de su
      modelo que declaran ese mismo ``compute``, incluido él. Es lo que
      ``Field.compute_value`` recorre para desmarcar el cómputo pendiente de
      todo el grupo, no sólo del campo por el que se entró;
    - un campo **sin** ``compute`` no está en el mapa. La fuente lo consulta
      con ``[]`` y deja que reviente, porque llamarlo sobre un campo no
      calculado es un error de programación, no un caso.

    Por eso NO hereda de :class:`_DerivedCollector`: aquél devuelve la tupla
    vacía ante lo ausente, que aquí escondería justo ese error.

    La **tercera** mitad son las comprobaciones de consistencia (``:526-550``):
    cuando dos campos comparten método de cálculo, la fuente avisa si no
    comparten ``compute_sudo``, ``precompute`` o ``store``. Estaban ausentes
    hasta 2026-09-03 — el agrupamiento se había portado y los avisos no, que es
    el porte parcial silencioso que ``porte-completo-no-parcial.md`` prohíbe.
    Ver :meth:`_warn_inconsistencies`.
    """

    def __init__(self):
        self._table = None

    def _build(self, models=None):
        """El mapa, y de paso las tres comprobaciones de consistencia.

        ``models`` acota la poblacion; por omision es ``apps.get_models()``.
        El parametro existe porque las tres comprobaciones de abajo no se
        pueden ejercer sobre un arbol coherente: un control que solo mida el
        caso positivo no distingue *"avisa cuando toca"* de *"avisa siempre"*
        (``metrica-decide-la-conclusion.md``, sub-patron D).
        """
        table = {}
        for model in apps.get_models() if models is None else models:
            model_name = getattr(model, '_name', None) or model.__name__
            groups = defaultdict(list)
            for field in model._meta.get_fields():
                compute = getattr(field, 'compute', None)
                if compute:
                    table[field] = group = groups[compute]
                    group.append(field)
            for fields in groups.values():
                if len(fields) > 1:
                    self._warn_inconsistencies(model_name, fields)
        return table

    @staticmethod
    def _warn_inconsistencies(model_name, fields):
        """Avisa cuando el grupo no comparte las tres banderas — ≙ ``:526-550``.

        Son tres avisos distintos porque cada bandera rompe una cosa distinta:
        ``compute_sudo`` decide con que privilegio corre el metodo, y mezclarlo
        deja la mitad del grupo elevada por accidente; ``precompute`` decide si
        el valor se calcula antes del ``INSERT``, y mezclarlo hace que un campo
        se pierda esa ventana; ``store`` es el mas insidioso — leer un campo no
        guardado dispara el calculo y **escribe** los guardados del mismo
        grupo, asi que una lectura acaba mutando filas.

        La fuente los emite con ``warnings.warn`` y ``stacklevel=1``: el aviso
        senala esta linea a proposito, porque el defecto esta en la declaracion
        de los campos y no en quien los consulta.
        """
        if len({field.compute_sudo for field in fields}) > 1:
            fnames = ", ".join(field.name for field in fields)
            warnings.warn(
                f"{model_name}: inconsistent 'compute_sudo' for computed fields "
                f"{fnames}. Either set 'compute_sudo' to the same value on all "
                f"those fields, or use distinct compute methods for sudoed and "
                f"non-sudoed fields.",
                stacklevel=1,
            )
        if len({field.precompute for field in fields}) > 1:
            fnames = ", ".join(field.name for field in fields)
            warnings.warn(
                f"{model_name}: inconsistent 'precompute' for computed fields "
                f"{fnames}. Either set all fields as precompute=True (if "
                f"possible), or use distinct compute methods for precomputed "
                f"and non-precomputed fields.",
                stacklevel=1,
            )
        if len({field.store for field in fields}) > 1:
            fnames1 = ", ".join(field.name for field in fields if not field.store)
            fnames2 = ", ".join(field.name for field in fields if field.store)
            warnings.warn(
                f"{model_name}: inconsistent 'store' for computed fields, "
                f"accessing {fnames1} may recompute and update {fnames2}. "
                f"Use distinct compute methods for stored and non-stored fields.",
                stacklevel=1,
            )

    def __getitem__(self, field):
        if self._table is None:
            self._table = self._build()
        return self._table[field]

    def __contains__(self, field):
        if self._table is None:
            self._table = self._build()
        return field in self._table

    def clear(self):
        self._table = None


#: ≙ ``Registry.field_computed`` (``:515``).
field_computed = _ComputedGrouper()


class _TriggerRegistry:
    """El grafo de disparo: qué recalcular cuando un campo cambia.

    ≙ el bloque de ``Registry`` que va de ``field_inverses`` (``:506``) a
    ``is_modifying_relations`` (``:670``). Es la **inversa** de la capa A:
    aquélla sabe recalcular un campo; esto sabe QUÉ campos hay que recalcular
    y por qué camino llegar a las filas afectadas.

    Es una clase y no seis funciones sueltas porque los tres mapas
    —``field_inverses``, los disparadores y el caché de árboles— se derivan del
    mismo recorrido y se vacían juntos. Separarlos dejaría tres invalidaciones
    que alguien tendría que acordarse de llamar en orden.

    La inversa la trae el stack, y por eso ``setup_inverses`` no se porta
    =====================================================================

    La fuente construye ``field_inverses`` llamando a un ``setup_inverses``
    **por clase de campo** (``One2many`` liga con su ``inverse_name``,
    ``Many2many`` con su tabla de relación) porque su ORM no guarda la vuelta.
    Django sí: ``field.remote_field`` es la relación inversa, y
    ``_meta.get_fields()`` la publica como un objeto propio junto a los campos
    concretos. Aquí el mapa se **deriva** de eso.

    Es divergencia de mecanismo, no de alcance: el contenido del mapa es el
    mismo —cada lado de una relación apunta al otro— y se obtiene sin la
    ceremonia que la fuente necesita. Cierra el DESCONOCIDO que
    ``fields_relational.py`` declaró sobre ``setup_inverses`` (tarea **#244**),
    cuya razón era que este árbol no tenía caché de campos; desde la capa A la
    tiene.
    """

    def __init__(self):
        self._inverses = None
        self._triggers = None
        self._trees = {}
        self._modifying = {}

    # --- la relación inversa, derivada de Django ---------------------------

    @property
    def field_inverses(self):
        """≙ ``Registry.field_inverses`` (``:506``) — cada lado de una
        relación apunta al otro."""
        if self._inverses is None:
            self._inverses = self._build_inverses()
        return self._inverses

    @staticmethod
    def _build_inverses():
        inverses = Collector()
        for model in apps.get_models():
            for field in model._meta.get_fields():
                remote = getattr(field, 'remote_field', None)
                if remote is None:
                    continue
                # ``remote_field`` del concreto es el objeto de relación
                # inversa, y el de éste es el concreto: la vuelta es simétrica
                # y basta con anotar las dos direcciones de cada par.
                inverses.add(field, remote)
                inverses.add(remote, field)
        return inverses

    # --- los disparadores, invirtiendo lo declarado ------------------------

    def field_triggers(self):
        """La inversa de las dependencias: ``{campo: {ruta: campos}}``.

        ≙ ``Registry._field_triggers`` (``:645``). Docstring de la fuente,
        verbatim: *"the inverse of field dependencies, as a dictionary like
        ``{field: {path: fields}}``, where ``field`` is a dependency, ``path``
        is a sequence of fields to inverse and ``fields`` is a collection of
        fields that depend on ``field``"*.

        Es un método y no una propiedad porque la fuente lo declara con guion
        bajo —es interno— y aquí un atributo de módulo con el mismo nombre
        chocaría con el mapa público. El guion bajo se conserva en el nombre
        del atributo, no en el del método (``porte-completo-no-parcial.md``:
        el guion bajo es contrato, y este símbolo es el que el motor llama).
        """
        if self._triggers is None:
            self._triggers = self._build_triggers()
        return self._triggers

    @staticmethod
    def _build_triggers():
        triggers = defaultdict(lambda: defaultdict(OrderedSet))
        for model in apps.get_models():
            # Un modelo abstracto de Django no está en ``get_models()``, así
            # que el ``if Model._abstract: continue`` de la fuente no tiene
            # nada que saltarse aquí.
            for field in model._meta.get_fields():
                resolve = getattr(field, 'resolve_depends', None)
                if resolve is None:
                    continue
                for dependency in resolve(sys.modules[__name__]):
                    *path, dep_field = dependency
                    triggers[dep_field][tuple(reversed(path))].add(field)
        return triggers

    # --- el árbol y sus lectores -------------------------------------------

    def get_field_trigger_tree(self, field):
        """El árbol de disparo de un campo, por cierre transitivo.

        ≙ ``Registry.get_field_trigger_tree`` (``:594``).
        """
        try:
            return self._trees[field]
        except KeyError:
            # silent OK because es el fallo del memo, no un error: la ausencia
            # de la clave ES la respuesta «todavía no está calculado», y el
            # cuerpo que sigue lo calcula. La fuente lo escribe igual
            # (``odoo19c: odoo/orm/registry.py:598-601``).
            pass

        triggers = self.field_triggers()
        if field not in triggers:
            return TriggerTree()

        def transitive_triggers(field, prefix=(), seen=()):
            if field in seen or field not in triggers:
                return
            for path, targets in triggers[field].items():
                full_path = concat(prefix, path)
                yield full_path, targets
                for target in targets:
                    yield from transitive_triggers(
                        target, full_path, seen + (field,))

        def concat(seq1, seq2):
            """Cancela el par ida-vuelta: bajar por un ``many2one`` y subir
            por su ``one2many`` deja el recorrido donde estaba."""
            if seq1 and seq2:
                first, second = seq1[-1], seq2[0]
                if _is_round_trip(first, second):
                    return concat(seq1[:-1], seq2[1:])
            return seq1 + seq2

        tree = TriggerTree()
        for path, targets in transitive_triggers(field):
            current = tree
            for label in path:
                current = current.increase(label)
            if current.root:
                current.root.update(targets)
            else:
                current.root = OrderedSet(targets)

        self._trees[field] = tree
        return tree

    def get_trigger_tree(self, fields_changed, select=bool):
        """El árbol a recorrer cuando ``fields_changed`` han cambiado.

        ≙ ``Registry.get_trigger_tree`` (``:554``). ``select`` decide qué
        campos se conservan en los nodos, para descartar los que no interesan.
        """
        triggers = self.field_triggers()
        trees = [self.get_field_trigger_tree(field)
                 for field in fields_changed if field in triggers]
        return TriggerTree.merge(trees, select)

    def get_dependent_fields(self, field):
        """Los campos que dependen de ``field`` — ≙ ``:567``."""
        if field not in self.field_triggers():
            return
        for tree in self.get_field_trigger_tree(field).depth_first():
            yield from tree.root

    def is_modifying_relations(self, field):
        """Si tocar ``field`` puede cambiar QUÉ filas dependen de él.

        ≙ ``Registry.is_modifying_relations`` (``:670``). Docstring de la
        fuente, verbatim: *"Return whether ``field`` has dependent fields on
        some records, and that modifying ``field`` might change the dependent
        records"*.
        """
        try:
            return self._modifying[field]
        except KeyError:
            inverses = self.field_inverses
            result = field in self.field_triggers() and bool(
                _is_relational(field) or inverses[field] or any(
                    _is_relational(dep) or inverses[dep]
                    for dep in self.get_dependent_fields(field)))
            self._modifying[field] = result
            return result

    # --- invalidación ------------------------------------------------------

    def has_inverses(self):
        """Si el mapa de inversas ya está materializado.

        ≙ la pregunta ``if 'field_inverses' in vars(self)`` que
        ``Registry._discard_fields`` hace antes de descartar (``:585``). Allá
        interroga al ``__dict__`` de la instancia porque el mapa es una
        ``cached_property``; aquí lo sabe el propio colector. La pregunta
        importa igual en los dos: forzar la derivación para borrar de ella es
        trabajo que nadie pidió.
        """
        return self._inverses is not None

    def discard_triggers(self):
        """Descarta los disparadores y sus dos memos, conservando las inversas.

        ≙ el tramo de ``Registry._discard_fields`` que hace
        ``self.__dict__.pop('_field_triggers', None)`` seguido de vaciar
        ``_field_trigger_trees`` y ``_is_modifying_relations`` (``:580-583``).

        **Los tres juntos**: el caché de árboles guarda instancias derivadas de
        los disparadores, así que vaciar uno y no el otro serviría un árbol
        construido sobre un grafo que ya no existe — el mismo defecto que el
        memo de ``_get_cache`` tenía frente a ``invalidate_field_data``.

        Los dos memos se vacían **en el sitio** y no se reasignan: un registro
        construido los toma prestados en :meth:`Registry.init`, y reasignarlos
        aquí dejaría a ese registro leyendo el diccionario viejo.
        """
        self._triggers = None
        self._trees.clear()
        self._modifying.clear()

    def clear(self):
        """Vacía los cuatro mapas derivados — los disparadores y las inversas.

        Es :meth:`discard_triggers` más el mapa de inversas, que sobrevive a un
        descarte por campo pero no a un cambio de lo declarado.
        """
        self._inverses = None
        self.discard_triggers()


def _is_relational(field):
    """Si el campo lleva a otro modelo — ≙ ``Field.relational`` de la fuente.

    Se lee de ``is_relation`` de Django, que es donde este stack lo declara,
    y no de un atributo ``relational`` que habría que instalar en cada clase.
    """
    return bool(getattr(field, 'is_relation', False))


def _is_round_trip(first, second):
    """Si ``second`` deshace el paso que ``first`` dio.

    ≙ la comprobación que ``concat`` hace en la fuente
    (``many2one`` seguido del ``one2many`` que lo invierte). Aquí la decide la
    propia relación inversa de Django en vez de comparar cuatro nombres a
    mano: ``second`` deshace a ``first`` cuando es exactamente su
    ``remote_field``, en cualquiera de los dos sentidos.
    """
    return (getattr(first, 'remote_field', None) is second
            or getattr(second, 'remote_field', None) is first)


#: La instancia única del grafo — el registro aquí es un módulo, no una
#: instancia por base (divergencia declarada en la cabecera de este archivo).
_triggers = _TriggerRegistry()


def field_triggers():
    """≙ ``Registry._field_triggers`` — ver :meth:`_TriggerRegistry.field_triggers`."""
    return _triggers.field_triggers()


def get_field_trigger_tree(field):
    """≙ ``Registry.get_field_trigger_tree``."""
    return _triggers.get_field_trigger_tree(field)


def get_trigger_tree(fields_changed, select=bool):
    """≙ ``Registry.get_trigger_tree``."""
    return _triggers.get_trigger_tree(fields_changed, select)


def get_dependent_fields(field):
    """≙ ``Registry.get_dependent_fields``."""
    return _triggers.get_dependent_fields(field)


def is_modifying_relations(field):
    """≙ ``Registry.is_modifying_relations``."""
    return _triggers.is_modifying_relations(field)


class _FieldInversesProxy:
    """``registry.field_inverses`` como el mapa que la fuente expone.

    La fuente lo declara ``cached_property``, así que se lee como atributo. Un
    módulo no tiene propiedades, y una función obligaría a escribir
    ``field_inverses()[campo]`` — que es otra firma. El proxy conserva la de la
    fuente delegando en la instancia.
    """

    def __getitem__(self, field):
        return _triggers.field_inverses[field]

    def __contains__(self, field):
        return field in _triggers.field_inverses

    def __iter__(self):
        return iter(_triggers.field_inverses)

    def __len__(self):
        return len(_triggers.field_inverses)


#: ≙ ``Registry.field_inverses`` (``:506``).
field_inverses = _FieldInversesProxy()


def clear_field_depends():
    """Vacía los mapas derivados de lo declarado.

    Se llama cuando cambia lo declarado — un modelo nuevo registrado, un campo
    extendido. NO hay invalidación parcial como en ``:474``: allá el registro
    se reconstruye por base y merece el detalle; aquí la derivación entera
    cuesta un recorrido de ``apps.get_models()``.
    """
    field_depends.clear()
    field_depends_context.clear()
    field_computed.clear()
    _triggers.clear()


class DummyRLock:
    """≙ ``DummyRLock`` (``odoo19c: odoo/orm/registry.py:1189-1198``).

    Docstring de la fuente, verbatim: *"Dummy reentrant lock, to be used while
    running rpc and js tests"*.

    Es un **objeto nulo**: cumple el protocolo de ``threading.RLock`` sin
    tomar nada. La fuente lo sustituye en ``Registry._lock`` mientras corren
    las pruebas de RPC y de JS, donde el cerrojo real serializaría peticiones
    que la prueba necesita concurrentes.

    ``__exit__`` devuelve ``None`` a propósito, así que la excepción del
    bloque **se propaga**: un cerrojo nulo no es un ``try`` mudo.
    """

    def acquire(self):
        pass

    def release(self):
        pass

    def __enter__(self):
        self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()


class TriggerTree(dict):
    """≙ ``TriggerTree`` (``odoo19c: odoo/orm/registry.py:1201-1269``).

    Docstring de la fuente, verbatim: *"The triggers of a field F is a tree
    that contains the fields that depend on F, together with the fields to
    inverse to find out which records to recompute"*.

    El árbol que la fuente dibuja: G depende de F, H de ``X.F``, I de
    ``W.X.F``, y J de ``Y.F``::

                                 [G]
                               X/   \\Y
                             [H]     [J]
                           W/
                         [I]

    Y para qué sirve, verbatim: *"when F is modified on records, mark G to
    recompute on records, mark H to recompute on ``inverse(X, records)``, mark
    I to recompute on ``inverse(W, inverse(X, records))``, mark J to recompute
    on ``inverse(Y, records)``"*.

    La **clave** de cada nodo es el campo a invertir; la **raíz** de cada nodo
    son los campos a recalcular en ese punto del recorrido.

    Divergencia de anotación, no de mecanismo
    =========================================

    La fuente declara ``dict['Field', 'TriggerTree']``. Aquí la clase hereda de
    ``dict`` a secas y la anotación viaja en el docstring: ``Field`` es el ciclo
    duro de siete que el orden de porte midió, y **la clave no crea dependencia
    real** — el árbol nunca invoca nada del campo, sólo lo usa como clave
    hasheable y lo guarda en su raíz. Esperar a ``Field`` para portar esto sería
    confundir una anotación con un acoplamiento.
    """

    __slots__ = ['root']

    # pylint: disable=keyword-arg-before-vararg
    def __init__(self, root: Collection = (), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = root

    def __bool__(self) -> bool:
        return bool(self.root or len(self))

    def __repr__(self) -> str:
        return f"TriggerTree(root={self.root!r}, {super().__repr__()})"

    def increase(self, key) -> 'TriggerTree':
        """El subárbol de ``key``, creándolo vacío si aún no existe."""
        try:
            return self[key]
        except KeyError:
            subtree = self[key] = TriggerTree()
            return subtree

    def depth_first(self) -> Iterator['TriggerTree']:
        """Cada nodo del árbol, el padre antes que sus hijos."""
        yield self
        for subtree in self.values():
            yield from subtree.depth_first()

    @classmethod
    def merge(cls, trees: list, select: Callable = bool) -> 'TriggerTree':
        """≙ ``merge`` (``odoo19c: :1249-1269``).

        Docstring de la fuente, verbatim: *"Merge trigger trees into a single
        tree. The function ``select`` is called on every field to determine
        which fields should be kept in the tree nodes. This enables to discard
        some fields from the tree nodes"*.

        Un subárbol que ``select`` deja vacío **no se conserva**: su
        ``__bool__`` es falso y la rama desaparece del resultado.
        """
        root_fields = OrderedSet()             # los campos del nodo raíz
        subtrees_to_merge = defaultdict(list)  # subárboles a fundir, por clave

        for tree in trees:
            root_fields.update(tree.root)
            for label, subtree in tree.items():
                subtrees_to_merge[label].append(subtree)

        # El nodo raíz se queda con los campos para los que ``select`` es cierto.
        result = cls([field for field in root_fields if select(field)])
        for label, subtrees in subtrees_to_merge.items():
            subtree = cls.merge(subtrees, select)
            if subtree:
                result[label] = subtree

        return result


def not_null_fields(model=None):
    """≙ ``Registry.not_null_fields`` (``odoo19c: odoo/orm/registry.py:267``).

    El conjunto de campos cuya **columna** rechaza el nulo. Su consumidor en
    la fuente son tres sitios que deciden si una condición tiene que contemplar
    la fila sin valor: ``domains._optimize_in_required``,
    ``fields.Field.condition_to_sql`` (``:1279``) y el lado relacional
    (``fields_relational.py:487,1156``).

    **La divergencia de mecanismo, declarada.** La fuente lo puebla en
    ``check_null_constraints`` (``:786-801``): consulta ``pg_attribute`` por
    ``attnotnull`` y lo cruza con lo que el campo *declara*
    (``field.required and field.store``), avisando cuando el esquema y la
    declaración no coinciden. Ese cruce existe porque allá el DDL lo emite el
    propio ORM y puede quedar atrás de la declaración.

    Aquí el DDL lo emiten las migraciones de Django, que derivan la restricción
    de ``null=False`` — declaración y esquema no pueden divergir sin que una
    migración lo registre. Por eso el conjunto se deriva de ``field.null``, y
    el cruce contra ``pg_attribute`` sería medir dos veces la misma fuente.

    Se conserva de la fuente: la **pk siempre entra** (``:795-797``, la rama
    ``field_name == 'id'`` que no consulta el esquema), y sólo se miran los
    modelos con tabla — el ``Model._auto and not Model._abstract`` de allá es
    aquí el modelo concreto de Django.

    :param model: si se da, sólo sus campos; si no, los de todo el registro.
    :returns: ``set`` de instancias de campo.
    """
    candidates = [model] if model is not None else apps.get_models(include_auto_created=True)
    result = set()
    for candidate in candidates:
        meta = getattr(candidate, '_meta', None)
        if meta is None or meta.abstract or meta.proxy or not meta.managed:
            continue
        for field in meta.concrete_fields:
            if field.primary_key or not field.null:
                result.add(field)
    return result


def is_not_null(field):
    """Si la columna de este campo rechaza el nulo — el uso puntual.

    ``not_null_fields()`` recorre el registro entero; un optimizador de dominio
    pregunta por **un** campo y no necesita pagar ese recorrido.

    **Las dos vías tienen que dar la misma respuesta**, y la primera versión de
    este atajo no lo hacía: leía ``field.null`` sin exigir que el campo tuviera
    columna. Un ``ManyToManyField`` declara ``null=False`` —Django avisa de que
    ahí el atributo *no tiene efecto*, porque la nulabilidad vive en la tabla
    intermedia— así que el atajo lo daba por NOT NULL y el conjunto no.

    Medido sobre el registro: **88 de 5345** campos discrepaban (87
    ``ManyToManyField`` y 1 ``GenericForeignKey``). El coste no era teórico:
    ``_optimize_in_required`` recortaba el ``False`` de un dominio sobre un
    M2M, y ``Domain('groups', 'like', '')`` sobre ``ir.rule`` colapsaba a
    ``TRUE`` en vez de quedarse como comparación contra la columna.

    Por eso las dos condiciones que ``not_null_fields`` aplica al recorrer
    —campo **concreto**, modelo con tabla— se aplican aquí una a una. Con
    ellas, las dos vías coinciden en los 5407 campos medidos.
    """
    if not getattr(field, 'concrete', False):
        return False
    meta = getattr(getattr(field, 'model', None), '_meta', None)
    if meta is None or meta.abstract or meta.proxy or not meta.managed:
        return False
    return bool(getattr(field, 'primary_key', False)) or not getattr(field, 'null', True)


# Este import va AQUI y no arriba, y la posicion es el mecanismo: ``orm.
# model_classes`` importa ``MODELS_BY_NAME`` de este archivo (``:95``), asi que
# arriba —antes de que la asignacion exista— el ciclo revienta. Aqui ya esta
# definido, y el modulo se liga entero para resolver el atributo al llamar. Es
# un import de nivel de modulo, no una excepcion a ``no-lazy-imports.md``;
# mismo criterio que ``orm.environments`` de arriba.
import orm.model_classes                                          # noqa: E402


class Registry(Mapping):
    """El registro de modelos de **una** base — ≙ ``odoo19c: odoo/orm/registry.py:84``.

    Docstring de la fuente, verbatim: *"Model registry for a particular
    database. The registry is essentially a mapping between model names and
    model classes. There is one registry instance per database."*

    Hasta 2026-09-03 este archivo llevaba el registro como **funciones de
    modulo** y su docstring lo justificaba: *"por eso este archivo es un stub
    delgado documentado, no una reimplementacion"*, con el argumento de que
    recrear ``Registry`` duplicaria ``django.apps``. Eso es declarar
    divergencia en vez de portar, que ``porte-completo-no-parcial.md``
    prohibe: la clase se porta, y las funciones de modulo siguen siendo el eje
    de proceso sobre el que se apoya.

    **Que es una «base» aqui.** La fuente indexa por el nombre de base que le
    pasa a psycopg. En este stack lo que designa una base es el **alias** de
    ``django.db.connections``, y su nombre vive en ``settings.DATABASES``. La
    clase acepta cualquiera de los dos: quien resuelve el alias es
    :meth:`_alias`, no el indice, asi que ``Registry('default')`` y
    ``Registry('kaupamex_core')`` conviven sin que el llamador tenga que saber
    cual le toca.

    **Por que ``models`` no es ``MODELS_BY_NAME`` directamente.** En Django la
    clase de modelo pertenece al **proceso**, y cual base lee lo decide el
    router por consulta; en la fuente pertenece a la base, porque cada base
    tiene sus modulos instalados. El equivalente honesto es que cada registro
    arranque con una **vista propia** del mapa de proceso y pueda estrecharla:
    es lo que la fuente hace al cargar su grafo de modulos. Por eso
    ``__setitem__`` y ``__delitem__`` escriben en el diccionario del registro y
    no en el del proceso — dos registros no se pisan.

    Este es el **tramo 1** del porte (tarea #342): el singleton por base, el
    ciclo de vida y la mitad ``Mapping``. Los otros cuatro tramos —campos y
    disparadores, carga y setup, schema, y senalizacion con cursor— estan
    declarados ahi con sus simbolos. ``new`` porta su estructura y delega la
    carga de modulos en :func:`_ensure_seeded`, que es lo que este arbol tiene;
    el grafo de modulos de la fuente es el tramo 3.

    Vive al final del archivo y no al principio como en la fuente porque su
    cuerpo referencia a :class:`DummyRLock` y a :class:`TriggerTree`, que se
    declaran arriba. La fuente puede ponerla primero porque abre con
    ``from __future__ import annotations``.
    """

    #: El cerrojo de clase. Es **reentrante** a proposito: ``new`` lo toma y
    #: llama a ``delete``, que tambien lo toma. Con un ``threading.Lock`` la
    #: segunda toma se bloquearia contra si misma.
    _lock: 'threading.RLock | DummyRLock' = threading.RLock()

    #: Lo guarda la fuente para restaurarlo tras sustituir ``_lock`` por un
    #: :class:`DummyRLock` mientras corren sus pruebas de RPC y de JS.
    _saved_lock: 'threading.RLock | DummyRLock | None' = None

    #: ≙ ``Registry.registries`` (``:94``). Docstring de la fuente, verbatim:
    #: *"A mapping from database names to registries"*. El tamano —42, que la
    #: fuente comenta como ``random default value``— se conserva.
    registries = LRU(42)

    _init: bool
    ready: bool
    loaded: bool
    models: dict

    def __new__(cls, db_name):
        """El registro de ``db_name``, creandolo si no existe — ≙ ``:97-104``.

        Docstring de la fuente, verbatim: *"Return the registry for the given
        database name"*. El nombre vacio se rechaza con ``assert``, como alla:
        un registro sin base no designa nada.
        """
        assert db_name, "Missing database name"
        with cls._lock:
            try:
                return cls.registries[db_name]
            except KeyError:
                return cls.new(db_name)

    @classmethod
    @locked
    def new(cls, db_name, *, update_module=False, install_modules=(),
            upgrade_modules=(), reinit_modules=(), new_db_demo=None,
            models_to_check=None):
        """Construye y registra un registro nuevo para ``db_name`` — ≙ ``:113-215``.

        Los siete parametros de la fuente se conservan con su significado:
        ``update_module`` actualiza modulos al cargar; ``install_modules``,
        ``upgrade_modules`` y ``reinit_modules`` nombran los modulos a
        instalar, actualizar y reinicializar; ``new_db_demo`` decide la data de
        demostracion; ``models_to_check`` acota la verificacion.

        **Que hace aqui y que no.** La estructura es la de la fuente: crea la
        instancia sin pasar por ``__new__``, la inicializa, anula en ella los
        tres puntos de entrada de clase, la registra ANTES de cargar —porque la
        carga vuelve a pedir ``Registry(db_name)`` y tiene que encontrarla— y la
        descarta si algo revienta. La **carga de modulos** delega en
        :func:`_ensure_seeded`; el grafo de modulos de la fuente
        (``load_modules``, ``reset_modules_state``) es el tramo 3 de la tarea
        **#342**, y hasta entonces los cinco parametros de modulo se guardan en
        la instancia sin consumirse. Se guardan y no se ignoran: el tramo 3 los
        lee de ahi.
        """
        t0 = time.time()
        registry = object.__new__(cls)
        registry.init(db_name)
        # Anular los tres en la instancia es de la fuente (``:147``), y no es
        # limpieza: llamarlos desde un registro ya construido es siempre un
        # error, y asi revienta ahi en vez de hacer algo raro.
        registry.new = registry.init = registry.registries = None

        registry._update_module = bool(
            update_module or install_modules or upgrade_modules or reinit_modules)
        registry._install_modules = tuple(install_modules)
        registry._upgrade_modules = tuple(upgrade_modules)
        registry._reinit_modules = set(reinit_modules)
        registry._new_db_demo = new_db_demo
        registry._models_to_check = models_to_check

        cls.delete(db_name)
        cls.registries[db_name] = registry
        try:
            _ensure_seeded()
        except Exception:
            _logger.error('Failed to load registry')
            del cls.registries[db_name]
            raise

        registry._init = False
        registry.ready = True
        _logger.debug("Registry loaded in %.3fs", time.time() - t0)
        return registry

    def init(self, db_name):
        """Deja el registro en su estado inicial — ≙ ``:217-291``.

        Los ejes derivados —dependencias de campo, colectores de metodo
        marcado, disparadores— **se comparten con el proceso**: son propiedad
        de las clases de modelo, que en Django son del proceso y no de la base.
        Colgarlos como atributos de instancia aqui es lo que hace que
        ``registry.field_depends`` se lea igual que en la fuente sin que haya
        dos mapas que sincronizar.
        """
        self._init = True
        self.loaded = False
        self.ready = False
        self.db_name = db_name

        #: Vista propia del mapa de proceso — ver el docstring de la clase.
        self.models = dict(MODELS_BY_NAME)

        self._sql_constraints = set()
        self._database_translated_fields = {}
        self._database_company_dependent_fields = set()
        self._ordinary_tables = None
        self._constraint_queue = {}

        self._force_upgrade_scripts = set()
        self._reinit_modules = set()
        self._init_modules = set()
        self.updated_modules = []
        self.loaded_xmlids = loaded_xmlids

        # Ejes derivados, compartidos con el proceso (ver el docstring).
        self.field_depends = field_depends
        self.field_depends_context = field_depends_context
        self.many2many_relations = defaultdict(OrderedSet)
        self.field_setup_dependents = Collector()
        self.many2one_company_dependents = many2one_company_dependents
        self.not_null_fields = not_null_fields()

        # Los dos memos del eje de disparadores son **los del proceso**, no
        # copias por registro. El grafo se deriva de ``apps.get_models()``, que
        # es del proceso: dos registros con memos propios recalcularian lo
        # mismo dos veces, y ``_discard_fields`` sobre uno dejaria al otro
        # sirviendo un arbol construido sobre un grafo que ya no existe.
        self._field_trigger_trees = _triggers._trees
        self._is_modifying_relations = _triggers._modifying

        self.registry_sequence = -1
        self.cache_sequences = {}
        reset_invalidation_record()

        #: ≙ ``Registry._assertion_report`` (``:227-231``). Alla guarda un
        #: ``OdooTestResult`` de su propio corredor de pruebas; aqui el
        #: corredor es pytest y su resultado no pasa por el registro. Queda en
        #: ``None`` y su desenlace es el tramo 3 de la tarea **#342**.
        self._assertion_report = None

    @property
    def unaccent(self):
        """El envoltorio ``unaccent(...)``, o la identidad — ≙ ``:289``.

        La fuente lo decide al inicializar, con un cursor abierto. Aqui se
        decide al leerlo: construir un registro no tiene por que tocar la base,
        y el veredicto es el mismo. Lo gobierna
        :data:`orm.fields.UNACCENT_ENABLED`, que es la bandera que las dos vias
        de compilacion comparten.
        """
        return _unaccent if self.has_unaccent else lambda x: x

    @property
    def unaccent_python(self):
        """La normalizacion en memoria, hermana de :meth:`unaccent` — ≙ ``:290``."""
        return remove_accents if self.has_unaccent else lambda x: x

    @property
    def has_unaccent(self):
        """¿Existe la funcion ``unaccent``? — ≙ ``Registry.has_unaccent`` (``:286``).

        Lee la bandera compartida en vez de preguntarle a la base en cada
        lectura. Quien la fija midiendo es el arranque; medir aqui abriria un
        cursor por consulta.
        """
        return UNACCENT_ENABLED

    @property
    def has_trigram(self):
        """¿Existe ``word_similarity``? — ≙ ``Registry.has_trigram`` (``:287``)."""
        with connections[self._alias()].cursor() as cr:
            return modules_db.has_trigram(cr)

    def _alias(self):
        """El alias de ``connections`` que designa esta base.

        La fuente no lo necesita: su ``db_name`` **es** lo que psycopg recibe.
        Aqui abrir un cursor exige el alias, asi que se acepta cualquiera de
        los dos y se resuelve al usarlo — ver el docstring de la clase.
        """
        if self.db_name in connections:
            return self.db_name
        for alias in connections:
            if connections[alias].settings_dict.get('NAME') == self.db_name:
                return alias
        return 'default'

    # -- El eje de campos y disparadores -------------------------------------
    #
    # ≙ ``:506-682``. Los ocho simbolos que la fuente declara entre
    # ``field_inverses`` e ``is_modifying_relations``. Delegan en
    # :data:`_triggers` y en los mapas derivados del modulo por la razon que la
    # cabecera de este archivo declara: el grafo se deriva de
    # ``apps.get_models()``, que es del proceso, mientras que en la fuente es
    # de la base. El contrato que ve el llamador es el de la fuente — misma
    # firma, mismo valor de vuelta.
    #
    # Su reparto entre «el stack lo trae hecho» y «el stack tiene con que
    # construirlo» esta medido, con su control, en
    # ``scripts/workbench/registry-field-axis-support-20260903T053330/``:
    # 1 READY (``field_inverses``, porque Django guarda la relacion inversa y
    # la fuente tiene que construirla), 7 BUILDABLE, 0 BLOCKED.

    @property
    def field_inverses(self):
        """Cada lado de una relacion apunta al otro — ≙ ``:505-512``.

        La fuente lo declara ``cached_property`` y lo construye llamando a
        ``setup_inverses`` por clase de campo, porque su ORM no guarda la
        vuelta. Django si: la relacion inversa es un objeto propio que
        ``_meta.get_fields()`` publica, y el mapa se deriva de ahi. Divergencia
        de mecanismo, mismo contenido — ver :class:`_TriggerRegistry`.
        """
        return _triggers.field_inverses

    @property
    def field_computed(self):
        """Campo → los campos que calcula el MISMO metodo — ≙ ``:514-551``.

        Incluye las tres comprobaciones de consistencia de la fuente; las emite
        :meth:`_ComputedGrouper._warn_inconsistencies` al derivar el mapa.
        """
        return field_computed

    @property
    def _field_triggers(self):
        """La inversa de las dependencias de campo — ≙ ``:642-667``.

        Docstring de la fuente, verbatim: *"Return the field triggers, i.e.,
        the inverse of field dependencies, as a dictionary like ``{field:
        {path: fields}}``, where ``field`` is a dependency, ``path`` is a
        sequence of fields to inverse and ``fields`` is a collection of fields
        that depend on ``field``"*.

        El guion bajo se conserva: la fuente lo declara interno y quitarlo
        promoveria el simbolo a API publica (``porte-completo-no-parcial.md``).
        """
        return _triggers.field_triggers()

    def get_trigger_tree(self, fields, select=bool):
        """El arbol a recorrer cuando ``fields`` han cambiado — ≙ ``:552-564``.

        Docstring de la fuente, verbatim: *"Return the trigger tree to traverse
        when ``fields`` have been modified. The function ``select`` is called
        on every field to determine which fields should be kept in the tree
        nodes. This enables to discard some unnecessary fields from the tree
        nodes"*.
        """
        return _triggers.get_trigger_tree(fields, select)

    def get_dependent_fields(self, field):
        """Los campos que dependen de ``field`` — ≙ ``:565-571``.

        Docstring de la fuente, verbatim: *"Return an iterable on the fields
        that depend on ``field``"*.
        """
        return _triggers.get_dependent_fields(field)

    def get_field_trigger_tree(self, field):
        """El arbol de disparo de un campo — ≙ ``:592-641``.

        Docstring de la fuente, verbatim: *"Return the trigger tree of a field
        by computing it from the transitive closure of field triggers"*.
        """
        return _triggers.get_field_trigger_tree(field)

    def is_modifying_relations(self, field):
        """Si tocar ``field`` puede cambiar QUE filas dependen de el — ≙ ``:669-682``.

        Docstring de la fuente, verbatim: *"Return whether ``field`` has
        dependent fields on some records, and that modifying ``field`` might
        change the dependent records"*.
        """
        return _triggers.is_modifying_relations(field)

    def _discard_fields(self, fields):
        """Retira los campos dados de las estructuras derivadas — ≙ ``:573-590``.

        Docstring de la fuente, verbatim: *"Discard the given fields from the
        registry's internal data structures"*.

        Las cinco de la fuente, en su orden, y **todas juntas**: descartar el
        campo de los disparadores y dejarlo en el cache de arboles serviria un
        arbol construido sobre un grafo que ya no existe.

        El ``pop(f, None)`` del primer tramo es de la fuente y su comentario
        explica por que: *"tests usually don't reload the registry, so when they
        create custom fields those may not have the entire dependency setup, and
        may be missing from these maps"*. Un campo ausente no es un error.

        La fuente descarta ``field_inverses`` solo si esta materializado
        (``if 'field_inverses' in vars(self)``) para no forzar su derivacion al
        borrar; aqui la pregunta equivalente es si el colector ya se construyo,
        y la responde el propio :class:`_TriggerRegistry`.
        """
        for field in fields:
            field_depends.pop(field, None)
            field_depends_context.pop(field, None)

        # Los disparadores y sus dos memos se rehacen enteros: la derivacion
        # cuesta un recorrido de ``apps.get_models()``, y una invalidacion
        # parcial tendria que saber que arboles tocaban al campo retirado.
        _triggers.discard_triggers()

        if _triggers.has_inverses():
            _triggers.field_inverses.discard_keys_and_values(fields)

        self.field_setup_dependents.discard_keys_and_values(fields)

    # -- Las dos banderas de invalidacion ------------------------------------
    #
    # ≙ ``:1017-1033``. Son del tramo 5, y entran aqui porque
    # ``_setup_models__`` **escribe** la primera: sin ellas ese metodo no se
    # puede portar entero. Viven en un ``threading.local`` a proposito — la
    # invalidacion es del hilo que la hizo, y propagarla a los demas anunciaria
    # un cambio que ellos no ven.

    @property
    def registry_invalidated(self):
        """Si este hilo ha modificado el registro — ≙ ``:1017-1021``.

        Docstring de la fuente, verbatim: *"Determine whether the current
        thread has modified the registry"*.
        """
        return getattr(_invalidation, 'registry', False)

    @registry_invalidated.setter
    def registry_invalidated(self, value):
        _invalidation.registry = value

    @property
    def cache_invalidated(self):
        """Que caches ha modificado este hilo — ≙ ``:1026-1033``.

        Docstring de la fuente, verbatim: *"Determine whether the current
        thread has modified the cache"*.

        Es **el mismo** registro que escribe :func:`clear_cache`, y ahi esta
        el trabajo del tramo 5: antes eran dos estructuras disjuntas y el eje
        de senalizacion habria leido siempre un conjunto vacio. Ver el
        docstring de :data:`_invalidation`.
        """
        return cache_invalidated_names()

    # -- Carga y setup -------------------------------------------------------
    #
    # ≙ ``:350-380`` y ``:686-777``. El tramo 3 de la tarea #342.
    #
    # La divergencia de mecanismo que gobierna los tres primeros: alla el
    # registro **instancia** las clases de modelo de cada modulo al cargarlo
    # (``model_classes.add_to_registry``), porque una clase pertenece a la base
    # y cada base tiene sus modulos instalados. Aqui las clases las construye
    # Django al importar el modulo, una vez por proceso, y el registro las
    # **recoge**. Lo que estos metodos conservan es lo demas: que caches se
    # vacian, que memos se descartan y en que orden.

    def load(self, module):
        """Carga un modulo en el registro y nombra sus modelos — ≙ ``:350-380``.

        Docstring de la fuente, verbatim: *"Load a given module in the
        registry, and return the names of the directly modified models"*, y
        sigue: *"At the Python level, the modules are already loaded, but not
        yet on a per-registry level"*.

        Esa segunda frase es justo lo que aqui no aplica: en Django la clase se
        registra al importar y **no hay un segundo nivel** por base. Asi que la
        instanciacion desaparece y queda lo que si tiene receptor: vaciar los
        caches, descartar las propiedades derivadas y los memos del eje de
        disparadores, y devolver los nombres.

        Acepta el nodo de grafo de la fuente —cualquier objeto con ``.name``—
        o el nombre a secas, que es lo que este arbol tiene: el ``app_label``
        de Django.
        """
        name = getattr(module, 'name', module)

        # vacia el cache para dejarlo consistente, sin senalizarlo
        for cache in _CACHES.values():
            cache.clear()

        reset_cached_properties(self)
        self._field_trigger_trees.clear()
        self._is_modifying_relations.clear()

        model_names = []
        for model in apps.get_models(include_auto_created=True):
            if model._meta.app_label != name:
                continue
            model_name = getattr(model, '_name', None)
            if model_name:
                model_names.append(model_name)
                self.models[model_name] = model
        return model_names

    @locked
    def _setup_models__(self, cr, model_names=None):
        """Prepara los modelos para usarse — ≙ ``:382-...``.

        Docstring de la fuente, verbatim: *"Perform the setup of models. This
        must be called after loading modules and before using the ORM"*, y
        sobre el segundo parametro: *"When given ``model_names``, it performs
        an incremental setup: only the models impacted by the given
        ``model_names`` and all the already-marked models will be set up.
        Otherwise, all models are set up"*.

        El **marcado** de la fuente —``model_cls._setup_done__ = False`` y la
        reconstruccion de cada campo— no tiene receptor aqui: la clase de
        Django se construye una vez al importar y sus campos no se rehacen.
        Lo que si tiene receptor, y es lo que este metodo hace, es la
        invalidacion: vaciar los caches, descartar lo derivado y anunciar que
        el registro cambio.

        ``model_names`` acota el descarte a los descendientes nombrados por los
        dos ejes, como alla; sin el, se descarta todo.
        """
        for cache in _CACHES.values():
            cache.clear()

        reset_cached_properties(self)
        self._field_trigger_trees.clear()
        self._is_modifying_relations.clear()
        self.registry_invalidated = True

        if model_names is None:
            self.many2many_relations.clear()
            self.field_setup_dependents.clear()
            clear_field_depends()
        else:
            impacted = self.descendants(model_names, '_inherit', '_inherits')
            for fields in self.many2many_relations.values():
                for pair in list(fields):
                    if pair[0] in impacted:
                        fields.discard(pair)

    def post_init(self, func, *args, **kwargs):
        """Encola una llamada para el final de ``init_models`` — ≙ ``:686-688``.

        Docstring de la fuente, verbatim: *"Register a function to call at the
        end of :meth:`~.init_models`"*.
        """
        self._post_init_queue.append(partial(func, *args, **kwargs))

    def post_constraint(self, cr, func, key):
        """Aplica la restriccion, y la difiere si falla — ≙ ``:690-709``.

        Docstring de la fuente, verbatim: *"Call the given function, and delay
        it if it fails during an upgrade"*.

        El comentario de la fuente explica por que una clave ya encolada NO se
        vuelve a aplicar: *"Module A may try to apply a constraint and fail but
        another module B inheriting from Module A may try to reapply the same
        constraint and succeed, however the constraint would already be in the
        _constraint_queue and would be executed again at the end of the
        registry cycle, this would fail (already-existing constraint)"*.

        El punto de guardado de la fuente —``cr.savepoint(flush=False)``— es
        aqui ``transaction.atomic``, que es lo que en Django abre un savepoint
        anidado. Sin el, una restriccion que falla aborta la transaccion entera
        y el siguiente ``cr.execute`` revienta con ``InFailedSqlTransaction``.
        """
        try:
            if key not in self._constraint_queue:
                with transaction.atomic(using=self._alias()):
                    func(cr)
            else:
                self._constraint_queue[key] = func
        except Exception as error:
            if self._is_install:
                _schema.error(*(error.args or (error,)))
            else:
                _schema.info(*(error.args or (error,)))
                self._constraint_queue[key] = func

    def finalize_constraints(self, cr):
        """Aplica lo que quedo diferido — ≙ ``:711-721``.

        Docstring de la fuente, verbatim: *"Call the delayed functions from
        above"*.

        Un fallo aqui **solo avisa**, y la fuente dice por que: *"warn only,
        this is not a deployment showstopper, and can sometimes be a transient
        error"*.
        """
        for func in self._constraint_queue.values():
            try:
                with transaction.atomic(using=self._alias()):
                    func(cr)
            except Exception as error:
                _schema.warning(*(error.args or (error,)))
        self._constraint_queue.clear()

    def init_models(self, cr, model_names, context, install=True):
        """Lleva los modelos nombrados a la base — ≙ ``:723-777``.

        Docstring de la fuente, verbatim: *"Initialize a list of models (given
        by their name). Call methods ``_auto_init`` and ``init`` on each model
        to create or update the database tables supporting the models"*. El
        ``context`` admite ``module`` —el modulo que se instala o actualiza— y
        ``update_custom_fields``.

        **``_auto_init`` e ``init`` no tienen receptor aqui**, y es la misma
        divergencia que declara :meth:`check_tables_exist`: el DDL lo emiten
        las migraciones de Django. Lo que este metodo conserva es todo lo
        demas, que si lo tiene: la cola diferida, el reflejo del registro, el
        descarte del memo de tablas y las tres verificaciones de schema, en el
        orden de la fuente.

        Los tres atributos temporales —``_post_init_queue``, ``_foreign_keys``
        e ``_is_install``— se crean al entrar y se borran en el ``finally``,
        como alla (``:775-777``). Son estado de UNA llamada: si se quedaran, la
        siguiente heredaria la cola de la anterior.
        """
        if not model_names:
            return

        if 'module' in context:
            _logger.info('module %s: creating or updating database tables',
                         context['module'])
        elif context.get('models_to_check', False):
            _logger.info("verifying fields for every extended model")

        try:
            self._post_init_queue = deque()
            # (tabla1, columna1) -> (tabla2, columna2, ondelete, modelo, modulo)
            self._foreign_keys = {}
            self._is_install = install

            self._reflect_all(model_names, context)

            self._ordinary_tables = None

            while self._post_init_queue:
                func = self._post_init_queue.popleft()
                func()

            self.check_indexes(cr, model_names)
            self.check_foreign_keys(cr)
            self.check_tables_exist(cr)
        finally:
            del self._post_init_queue
            del self._foreign_keys
            del self._is_install

    def _reflect_all(self, model_names, context):
        """Refleja el registro en las cinco tablas de ``ir.model``.

        ≙ las cinco llamadas que ``init_models`` hace seguidas (``:749-753``):
        ``_reflect_models``, ``_reflect_fields``, ``_reflect_selections``,
        ``_reflect_constraints`` y ``_reflect_inherits``.

        Sale a su propio metodo por dos razones. La primera es que aqui las
        firmas no son las de alla: ``_reflect_models`` recibe **etiquetas de
        app** y devuelve conteos, mientras ``_reflect_fields`` y
        ``_reflect_inherits`` reciben la **fila** de ``ir.model`` de un modelo,
        no una lista de nombres — asi que hace falta un puente que las una. La
        segunda es que el modelo se resuelve por el registro
        (``self.models['ir.model']``) y no por un import: ``orm`` no importa
        addons.
        """
        model_classes = [self.models[name] for name in model_names
                         if name in self.models]
        if not model_classes:
            return

        ir_model = self.models.get('ir.model')
        if ir_model is None:
            _logger.info("Skipping reflection: ir.model is not in the registry yet")
            return

        app_labels = {model._meta.app_label for model in model_classes}
        ir_model._reflect_models(app_labels)

        wanted = {model._meta.label for model in model_classes}
        for row in ir_model.objects.filter(model__in=[m._name for m in model_classes]):
            if row.django_model is not None and row.django_model._meta.label in wanted:
                ir_model._reflect_fields(row)
                ir_model._reflect_inherits(row)

        selection = self.models.get('ir.model.fields.selection')
        if selection is not None:
            selection._reflect_selections(model_classes)
        constraint = self.models.get('ir.model.constraint')
        if constraint is not None:
            constraint._reflect_constraints(model_classes)

    # -- El eje de senalizacion entre procesos --------------------------------
    #
    # ≙ ``:1036-1186``. Los siete simbolos con que la fuente entera un proceso
    # de lo que invalido OTRO. Con ``workers = 4``
    # (``setup/gunicorn.conf.py:93``) sin este eje una invalidacion local deja
    # a los otros tres sirviendo contenido viejo — la mitad que
    # :ref:`h-api-980` declaro ausente y que la tarea **#256** cierra.
    #
    # Su reparto entre «el stack lo trae hecho» y «el stack tiene con que
    # construirlo» esta medido, con su control, en
    # ``scripts/workbench/registry-signaling-axis-support-20260903T063526/``:
    # 1 READY (``cursor``, porque ``connections[alias].cursor()`` ya es el
    # cursor con su gestor de contexto), 6 BUILDABLE, 0 BLOCKED.
    #
    # La UNICA divergencia de mecanismo del tramo es quien emite el DDL: alla
    # ``setup_signaling`` crea la tabla que falte; aqui la crea
    # ``base/migrations/0085_orm_signaling_tables`` y el metodo conserva la
    # mitad con receptor —la verificacion, que **nombra** la ausente—. Mismo
    # reparto que ``check_tables_exist`` (:ref:`h-api-1057`).

    def setup_signaling(self):
        """Prepara la senalizacion entre procesos — ≙ ``:1036-1064``.

        Docstring de la fuente, verbatim: *"Setup the inter-process signaling
        on this registry"*, y su comentario explica el mecanismo: la secuencia
        de ``orm_signaling_registry`` indica cuando hay que recargar el
        registro, y las de ``orm_signaling_...`` cuando hay que vaciar cada
        cache. Son tablas insert-only y no secuencias porque *"signaling was
        previously using sequence but this doesn't work with replication"*.

        **Verifica en vez de crear** — la divergencia que la cabecera de la
        seccion declara. Una tabla ausente levanta ``RuntimeError`` con su
        nombre; crearla es trabajo de la migracion.
        """
        with self.cursor() as cr:
            tables = tuple(signaling_table_names())
            cr.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_name = ANY(%s) AND table_schema = current_schema",
                [list(tables)])
            existing_sig_tables = {row[0] for row in cr.fetchall()}
            missing = [name for name in tables if name not in existing_sig_tables]
            if missing:
                raise RuntimeError(
                    "Faltan las tablas de senalizacion %s: las crea la "
                    "migracion base.0085_orm_signaling_tables, que no se ha "
                    "aplicado en esta base." % ', '.join(missing))

            db_registry_sequence, db_cache_sequences = self.get_sequences(cr)
            self.registry_sequence = db_registry_sequence
            self.cache_sequences.update(db_cache_sequences)

            _logger.debug(
                "Multiprocess load registry signaling: [Registry: %s] %s",
                self.registry_sequence,
                ' '.join('[Cache %s: %s]' % cs
                         for cs in self.cache_sequences.items()))

    def get_sequences(self, cr):
        """La secuencia del registro y la de cada cache — ≙ ``:1066-1074``.

        Un solo ``SELECT`` con un subquery ``max(id)`` por tabla, como la
        fuente: leer siete tablas en siete viajes costaria siete veces mas por
        peticion, que es donde este eje se consume.
        """
        tables = tuple(signaling_table_names())
        selects = SQL(', ').join([SQL('(SELECT max(id) FROM %s)',
                                      SQL.identifier(table))
                                  for table in tables])
        query = SQL("SELECT %s", selects)
        cr.execute(query.code, query.params)
        row = cr.fetchone()
        assert row is not None, "No result when reading signaling sequences"
        registry_sequence, *cache_sequences_values = row
        cache_sequences = dict(zip(_CACHES_BY_KEY, cache_sequences_values))
        return registry_sequence, cache_sequences

    def check_signaling(self, cr=None):
        """Se entera de lo que otro proceso senalizo — ≙ ``:1076-1108``.

        Docstring de la fuente, verbatim: *"Check whether the registry has
        changed, and performs all necessary operations to update the registry.
        Return an up-to-date registry"*.

        Devuelve un registro al dia: **el mismo** si nada cambio, o uno
        reconstruido si la secuencia del registro se movio. Los caches cuya
        secuencia se movio se vacian **sin** llamar a :func:`clear_cache` —
        comentario de la fuente: *"don't call clear_cache to avoid signal
        loop"*—, porque anotar la invalidacion la reenviaria a los demas
        procesos y el ciclo no pararia.
        """
        with nullcontext(cr) if cr is not None else closing(self.cursor(readonly=True)) as cr:
            assert cr is not None
            db_registry_sequence, db_cache_sequences = self.get_sequences(cr)
            changes = ''
            # ¿hay que recargar el registro de modelos?
            if self.registry_sequence != db_registry_sequence:
                _logger.info("Reloading the model registry after database signaling.")
                self = Registry.new(self.db_name)
                self.registry_sequence = db_registry_sequence
                if _logger.isEnabledFor(logging.DEBUG):
                    changes += "[Registry - %s -> %s]" % (
                        self.registry_sequence, db_registry_sequence)
            # ¿hay que invalidar los caches de modelo?
            else:
                invalidated = []
                for cache_name, cache_sequence in self.cache_sequences.items():
                    expected_sequence = db_cache_sequences[cache_name]
                    if cache_sequence != expected_sequence:
                        for cache in _CACHES_BY_KEY[cache_name]:
                            if cache not in invalidated:
                                invalidated.append(cache)
                                cache_of(cache).clear()
                        self.cache_sequences[cache_name] = expected_sequence
                        if _logger.isEnabledFor(logging.DEBUG):
                            changes += "[Cache %s - %s -> %s]" % (
                                cache_name, cache_sequence, expected_sequence)
                if invalidated:
                    _logger.info("Invalidating caches after database signaling: %s",
                                 sorted(invalidated))
            if changes:
                _logger.debug("Multiprocess signaling check: %s", changes)
        return self

    def signal_changes(self):
        """Avisa a los demas procesos de lo invalidado — ≙ ``:1110-1140``.

        Docstring de la fuente, verbatim: *"Notifies other processes if
        registry or cache has been invalidated"*.

        El ``elif`` es de la fuente y su comentario dice por que: *"no need to
        notify cache invalidation in case of registry invalidation, because
        reloading the registry implies starting with an empty cache"*.

        Incrementa **ademas** su propio contador en memoria. Si otro proceso
        escribio a la vez, el contador queda por detras y el siguiente
        ``check_signaling`` lo detecta — que es el desenlace correcto, no una
        carrera perdida.
        """
        if not self.ready:
            _logger.warning(
                'Calling signal_changes when registry is not ready is not suported')
            return

        if self.registry_invalidated:
            _logger.info("Registry changed, signaling through the database")
            with self.cursor() as cr:
                cr.execute("INSERT INTO orm_signaling_registry DEFAULT VALUES")
                self.registry_sequence += 1

        elif self.cache_invalidated:
            _logger.info("Caches invalidated, signaling through the database: %s",
                         sorted(self.cache_invalidated))
            with self.cursor() as cr:
                for cache_name in self.cache_invalidated:
                    query = SQL("INSERT INTO %s DEFAULT VALUES",
                                SQL.identifier(f'orm_signaling_{cache_name}'))
                    cr.execute(query.code, query.params)
                    self.cache_sequences[cache_name] += 1

        self.registry_invalidated = False
        self.cache_invalidated.clear()

    def reset_changes(self):
        """Deshace la invalidacion en vez de anunciarla — ≙ ``:1142-1153``.

        Docstring de la fuente, verbatim: *"Reset the registry and cancel all
        invalidations"*. Es la contraparte de :meth:`signal_changes` cuando el
        trabajo que invalido fallo: se rehace el setup y se vacian los caches
        anotados, **sin** escribir en la base.
        """
        if self.registry_invalidated:
            with closing(self.cursor()) as cr:
                self._setup_models__(cr)
                self.registry_invalidated = False
        if self.cache_invalidated:
            for cache_name in self.cache_invalidated:
                for cache in _CACHES_BY_KEY[cache_name]:
                    cache_of(cache).clear()
            self.cache_invalidated.clear()

    @contextmanager
    def manage_changes(self):
        """Senaliza al salir bien, deshace al fallar — ≙ ``:1155-1163``.

        Docstring de la fuente, verbatim: *"Context manager to signal/discard
        registry and cache invalidations"*. La fuente lo declara **deprecado**
        desde 19.0 en favor de llamar a los dos metodos directamente, y el
        aviso se porta con el simbolo: quitarlo publicaria como vigente lo que
        la fuente marca de salida.
        """
        warnings.warn(
            "Since 19.0, use signal_changes() and reset_changes() directly",
            DeprecationWarning, stacklevel=2)
        try:
            yield self
            self.signal_changes()
        except Exception:
            self.reset_changes()
            raise

    def cursor(self, /, readonly=False):
        """Un cursor nuevo sobre la base — ≙ ``:1165-1186``.

        Docstring de la fuente, verbatim: *"Return a new cursor for the
        database. The cursor itself may be used as a context manager to
        commit/rollback and close automatically"*, y sobre el parametro:
        *"Attempt to acquire a cursor on a replica database. Acquire a
        read/write cursor on the primary database in case no replica exists or
        that no readonly cursor could be acquired"*.

        **La replica se busca por alias, no por atributo.** La fuente guarda
        dos conexiones (``self._db`` y ``self._db_readonly``); aqui las
        conexiones las declara ``DATABASES``, asi que la replica es el alias
        ``<alias>_readonly`` si esta declarado. Sin el, el fallback de la
        fuente es el camino unico — que es lo que este arbol tiene hoy, y por
        eso ``readonly=True`` devuelve el cursor de escritura.
        """
        alias = self._alias()
        if readonly:
            replica = f'{alias}_readonly'
            if replica in connections:
                try:
                    return connections[replica].cursor()
                except DatabaseError:
                    _logger.warning(
                        "Failed to open a readonly cursor, falling back to "
                        "read-write cursor")
        return connections[alias].cursor()

    # -- El eje de schema ----------------------------------------------------
    #
    # ≙ ``:779-1016``. Los seis simbolos con que la fuente compara lo declarado
    # contra lo que la base tiene. Ninguno existia aqui: ``init`` declaraba
    # ``_ordinary_tables`` y ``_sql_constraints`` y **nadie los leia**.
    #
    # Aqui el DDL lo emiten las migraciones de Django y no el ORM, asi que
    # estos seis **verifican** en vez de construir el schema entero. Eso NO los
    # hace redundantes: una migracion editada a mano, una tabla creada por el
    # provisioner o un indice retirado desde psql dejan al esquema por detras
    # de la declaracion, y el aviso de la fuente es justo lo que lo delata.

    def check_null_constraints(self, cr):
        """Comprueba que las restricciones de no-nulo estan puestas — ≙ ``:779-803``.

        Docstring de la fuente, verbatim: *"Check that all not-null constraints
        are set"*.

        Cruza ``pg_attribute`` contra lo que cada campo declara y **avisa**
        cuando no coinciden. La ``id`` entra sin preguntarle al esquema, como
        alla (``:795-797``): es la clave primaria y su no-nulo lo garantiza la
        propia definicion de la tabla.

        Repuebla :attr:`not_null_fields`, que hasta ahora sólo se derivaba de
        ``field.null`` al inicializar. Las dos vias conviven a proposito: la
        derivacion no necesita cursor y sirve al arranque; ésta necesita uno y
        es la que puede ver la divergencia.
        """
        cr.execute("""
            SELECT c.relname, a.attname
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE c.relnamespace = current_schema::regnamespace
            AND a.attnotnull = true
            AND a.attnum > 0
            AND a.attname != 'id'
        """)
        not_null_columns = set(cr.fetchall())

        self.not_null_fields.clear()
        for model in self.models.values():
            if not self._has_ordinary_schema(model):
                continue
            for field_name, field in model._fields.items():
                if field_name == 'id':
                    self.not_null_fields.add(field)
                    continue
                if field.column_type and field.store and field.required:
                    if (model._table, field_name) in not_null_columns:
                        self.not_null_fields.add(field)
                    else:
                        _schema.warning("Missing not-null constraint on %s", field)

    def check_indexes(self, cr, model_names):
        """Crea o retira los indices de columna de los modelos dados — ≙ ``:805-892``.

        Docstring de la fuente, verbatim: *"Create or drop column indexes for
        the given models"*.

        El valor de ``field.index`` decide: ``'btree'``, ``'btree_not_null'``,
        ``'trigram'``, o lo falso. Un indice que existe con **otro metodo de
        acceso** del esperado esta obsoleto y se rehace; uno que existe con el
        metodo correcto se deja en paz.

        **El filtro lleva un tercer termino que la fuente no necesita.** Alla
        el registro de campos contiene ``Field`` y nada mas, asi que
        ``field.column_type and field.store`` (``:814``) alcanza. Aqui
        ``_fields`` incluye tambien los objetos de relacion inversa de Django
        —``ManyToOneRel``, ``OneToOneRel``, ``ManyToManyRel``—, que no son
        campos y no declaran ninguno de los dos atributos. ``field.concrete``
        va delante porque es el que **si** declaran, y su ``False`` los deja
        fuera por cortocircuito. Es el mismo veredicto que da la fuente a su
        ``One2many``, dicho con el vocabulario del stack.
        """
        expected = [
            (make_index_name(model._table, field.name), model._table, field)
            for model_name in model_names
            for model in [self.models[model_name]]
            if self._has_ordinary_schema(model)
            for field in model._fields.values()
            if field.concrete and field.column_type and field.store
        ]
        if not expected:
            return

        cr.execute("""
            SELECT idx.relname, tbl.relname, am.amname
              FROM pg_index ix
              JOIN pg_class idx ON idx.oid = ix.indexrelid
              JOIN pg_class tbl ON tbl.oid = ix.indrelid
              JOIN pg_am am ON am.oid = idx.relam
             WHERE idx.relname = ANY(%s)
               AND idx.relnamespace = current_schema::regnamespace
        """, [[row[0] for row in expected]])
        existing = {name: (table, method) for name, table, method in cr.fetchall()}

        for indexname, tablename, field in expected:
            index = field.index
            assert index in ('btree', 'btree_not_null', 'trigram', True, False, None)

            if index and field.translate and index != 'trigram':
                _schema.warning(
                    "Index attribute on %r ignored, only trigram index is "
                    "supported for translated fields", field)
                continue

            # si el campo debe llevar indice, y con que metodo de acceso: gin
            # para el trigram, btree para el resto.
            will_index = bool(index) and (
                (not field.translate and index != 'trigram')
                or (index == 'trigram' and self.has_trigram))
            if indexname in existing:
                expected_method = 'gin' if index == 'trigram' else 'btree'
                stale = existing[indexname][1] != expected_method
                will_index &= stale     # se crea sólo cuando el que hay esta obsoleto
            else:
                stale = False

            if will_index:
                expression, method, where = self._index_shape(field, index)
                try:
                    with transaction.atomic(using=self._alias()):
                        if stale:
                            drop_index(cr, indexname, tablename)
                        create_index(cr, indexname, tablename, [expression],
                                     method, where)
                except DatabaseError:
                    _schema.error("Unable to add index %r for %s", indexname, self)

            elif not index and tablename == existing.get(indexname, (None, None))[0]:
                _schema.info("Keep unexpected index %s on table %s", indexname, tablename)

    def _index_shape(self, field, index):
        """La expresion, el metodo y la condicion del indice de un campo.

        ≙ el cuerpo del ``if will_index`` de la fuente (``:853-881``). Sale a
        su propio metodo porque decide tres valores a la vez y su llamador ya
        lleva dos niveles de anidamiento; la fuente puede permitirselo en linea
        porque no tiene que resolver el alias de conexion.
        """
        column = f'"{field.name}"'
        if index == 'trigram':
            if field.translate:
                column = f"""(jsonb_path_query_array({column}, '$.*')::text)"""
            # el ``unaccent`` va sólo en el indice trigram: es el unico que
            # sirve al ``ilike`` insensible a acentos, que es donde se usa.
            if self.has_unaccent == modules_db.FunctionStatus.INDEXABLE:
                column = self.unaccent(column)
            elif self.has_unaccent:
                warnings.warn(
                    "PostgreSQL function 'unaccent' is present but not immutable, "
                    "therefore trigram indexes may not be effective.",
                    stacklevel=1)
            return f'{column} gin_trgm_ops', 'gin', ''
        if index == 'btree_not_null' and field.company_dependent:
            # la condicion por empresa usa un ``AND col IS NOT NULL`` extra
            # para poder aprovechar el indice.
            return f'({column} IS NOT NULL)', 'btree', f'{column} IS NOT NULL'
        where = f'{column} IS NOT NULL' if index == 'btree_not_null' else ''
        return column, 'btree', where

    @staticmethod
    def _has_ordinary_schema(model):
        """Si el modelo tiene tabla propia que el schema deba verificar.

        ≙ el ``Model._auto and not Model._abstract`` de la fuente. Aqui esos
        dos atributos son ``Meta.managed`` y ``Meta.abstract``, que es donde
        Django los declara: un modelo no gestionado es exactamente aquel cuya
        tabla el ORM no toca, y uno abstracto no tiene tabla.
        """
        meta = getattr(model, '_meta', None)
        return bool(meta is not None and meta.managed and not meta.abstract)

    def add_foreign_key(self, table1, column1, table2, column2, ondelete,
                        model, module, force=True):
        """Declara una clave foranea esperada — ≙ ``:894-905``.

        Docstring de la fuente, verbatim: *"Specify an expected foreign key"*.

        ``force=False`` es un ``setdefault``: quien declara primero gana. La
        distincion importa porque dos modulos pueden declarar la misma columna
        y el segundo no debe pisar la politica de borrado del primero salvo que
        lo pida.
        """
        key = (table1, column1)
        val = (table2, column2, ondelete, model, module)
        if force:
            self._foreign_keys[key] = val
        else:
            self._foreign_keys.setdefault(key, val)

    def check_foreign_keys(self, cr):
        """Crea o actualiza las claves foraneas esperadas — ≙ ``:907-943``.

        Docstring de la fuente, verbatim: *"Create or update the expected
        foreign keys"*.

        Cada clave nueva o rehecha se refleja en ``ir.model.constraint``, que
        es lo que permite retirarla al desinstalar su modulo. El modelo se
        resuelve por el propio registro —``self['ir.model.constraint']``— y no
        por un import: ``orm`` no importa addons, y la mitad ``Mapping`` de esta
        clase existe justamente para esto.
        """
        if not self._foreign_keys:
            return

        cr.execute("""
            SELECT fk.conname, c1.relname, a1.attname, c2.relname, a2.attname, fk.confdeltype
            FROM pg_constraint AS fk
            JOIN pg_class AS c1 ON fk.conrelid = c1.oid
            JOIN pg_class AS c2 ON fk.confrelid = c2.oid
            JOIN pg_attribute AS a1 ON a1.attrelid = c1.oid AND fk.conkey[1] = a1.attnum
            JOIN pg_attribute AS a2 ON a2.attrelid = c2.oid AND fk.confkey[1] = a2.attnum
            WHERE fk.contype = 'f' AND c1.relname = ANY(%s)
            AND c1.relnamespace = current_schema::regnamespace
        """, [[table for table, column in self._foreign_keys]])
        existing = {
            (table1, column1): (name, table2, column2, deltype)
            for name, table1, column1, table2, column2, deltype in cr.fetchall()
        }

        for key, val in self._foreign_keys.items():
            table1, column1 = key
            table2, column2, ondelete, model, module = val
            deltype = _CONFDELTYPES[ondelete.upper()]
            spec = existing.get(key)
            if spec is None:
                sql_add_foreign_key(cr, table1, column1, table2, column2, ondelete)
            elif (spec[1], spec[2], spec[3]) != (table2, column2, deltype):
                drop_constraint(cr, table1, spec[0])
                sql_add_foreign_key(cr, table1, column1, table2, column2, ondelete)
            else:
                continue
            conname = get_foreign_keys(cr, table1, column1, table2, column2, ondelete)[0]
            self._reflect_foreign_key(model, conname, module)

    def _reflect_foreign_key(self, model, conname, module):
        """Anota la clave foranea en ``ir.model.constraint``.

        ≙ la llamada ``model.env['ir.model.constraint']._reflect_constraint(
        model, conname, 'f', None, module)`` que la fuente hace dos veces en
        ``check_foreign_keys``. Sale a su propio metodo porque aqui el modelo
        se resuelve por el registro y esa resolucion puede no estar disponible
        —durante el arranque, antes de que ``ir.model.constraint`` se registre—
        y esa condicion se comprueba una vez y no dos.
        """
        constraint_model = self.models.get('ir.model.constraint')
        if constraint_model is None or model is None:
            _schema.info("Foreign key %r not reflected: ir.model.constraint "
                         "is not in the registry yet", conname)
            return
        constraint_model._reflect_constraint(model, conname, 'f', None, module)

    def check_tables_exist(self, cr):
        """Verifica que todas las tablas estan presentes — ≙ ``:945-...``.

        Docstring de la fuente, verbatim: *"Verify that all tables are present
        and try to initialize those that are missing"*.

        Aqui **no** las inicializa, y la divergencia es del mecanismo entero:
        la tabla la crea una migracion de Django, no el ORM. Lo que este metodo
        conserva es el aviso, que es la mitad que sirve para detectar una
        migracion que falta.
        """
        table2model = {
            model._table: name
            for name, model in self.models.items()
            if self._has_ordinary_schema(model)
            and not getattr(model, '_table_query', None)
        }
        if not table2model:
            return
        missing_tables = set(table2model).difference(existing_tables(cr, table2model))

        if missing_tables:
            missing = {table2model[table] for table in missing_tables}
            _logger.info("Models have no table: %s.", ", ".join(sorted(missing)))

    def is_an_ordinary_table(self, model):
        """Si el modelo tiene una tabla ordinaria — ≙ ``:1001-1016``.

        Docstring de la fuente, verbatim: *"Return whether the given model has
        an ordinary table"*.

        **Ordinaria** es ``relkind = 'r'``: existir no basta. Una vista existe
        —y :func:`~tools.sql.existing_tables` la cuenta— y no admite las
        operaciones que su llamador va a intentar.

        La fuente abre el cursor por ``model.env.cr``; aqui el modelo es una
        clase de Django y no lleva entorno, asi que el cursor sale del alias de
        este registro. Mismo contrato, otra puerta.
        """
        if self._ordinary_tables is None:
            tables = [m._table for m in self.models.values()
                      if getattr(m, '_table', None)]
            with connections[self._alias()].cursor() as cr:
                cr.execute("""
                    SELECT c.relname
                      FROM pg_class c
                     WHERE c.relname = ANY(%s)
                       AND c.relkind = 'r'
                       AND c.relnamespace = current_schema::regnamespace
                """, [tables])
                self._ordinary_tables = {row[0] for row in cr.fetchall()}

        return model._table in self._ordinary_tables

    @classmethod
    @locked
    def delete(cls, db_name):
        """Borra el registro de una base — ≙ ``:294-297``.

        Docstring de la fuente, verbatim: *"Delete the registry linked to a
        given database"*. Pregunta antes de borrar, como alla: borrar una base
        que no esta registrada no es un error.
        """
        if db_name in cls.registries:
            del cls.registries[db_name]

    @classmethod
    @locked
    def delete_all(cls):
        """Borra todos los registros — ≙ ``:301-303``.

        Docstring de la fuente, verbatim: *"Delete all the registries"*.
        """
        cls.registries.clear()

    # -- La mitad Mapping ----------------------------------------------------
    #
    # ≙ ``:305-330``. Los cinco abstractos; el mixin de ``Mapping`` aporta
    # ``keys``, ``items``, ``values``, ``get``, ``__eq__`` y ``__ne__``.

    def __len__(self):
        """El tamano del registro — ≙ ``:309-311``."""
        return len(self.models)

    def __iter__(self):
        """Un iterador sobre los nombres de modelo — ≙ ``:313-315``."""
        return iter(self.models)

    def __getitem__(self, model_name):
        """El modelo de ese nombre, o ``KeyError`` — ≙ ``:317-319``."""
        return self.models[model_name]

    def __setitem__(self, model_name, model):
        """Anade o reemplaza un modelo — ≙ ``:321-323``."""
        self.models[model_name] = model

    def __delitem__(self, model_name):
        """Retira un modelo a medida — ≙ ``:325-330``.

        Ademas lo olvida en los padres: el comentario de la fuente lo explica
        —*"the custom model can inherit from mixins ('mail.thread', ...)"*—, y
        sin eso el conjunto del padre quedaria nombrando un modelo que ya no
        existe.
        """
        del self.models[model_name]
        for model in self.models.values():
            hijos = getattr(model, '_inherit_children', None)
            if hijos is not None:
                hijos.discard(model_name)

    def descendants(self, model_names, *kinds):
        """Los modelos dados y todos los que heredan de ellos — ≙ ``:332-348``.

        Docstring de la fuente, verbatim: *"Return the models corresponding to
        ``model_names`` and all those that inherit/inherits from them"*.

        Recorre en anchura con una cola, y un modelo ya visto no se vuelve a
        encolar: por eso admite un grafo con ciclos y no repite. Un nombre que
        el registro no conoce se **salta**, no levanta — es lo que la fuente
        hace con su ``self.get``.

        **El eje ``_inherits`` se deriva aqui, no se mantiene.** La fuente
        escribe ``registry[padre]._inherits_children`` en cada
        ``_init_model_class_attributes``; este arbol lo calcula con
        :func:`orm.model_classes.inherits_children`, por la razon que ese
        archivo declara: un mapa mantenido a mano puede quedar nombrando un
        modelo que ya no delega y nadie lo nota. Es divergencia de mecanismo,
        no de contrato — el atributo se lee igual, y si la clase lo declara se
        respeta el declarado.
        """
        assert all(kind in ('_inherit', '_inherits') for kind in kinds)

        models = OrderedSet()
        queue = deque(model_names)
        while queue:
            model = self.get(queue.popleft())
            if model is None or model._name in models:
                continue
            models.add(model._name)
            for kind in kinds:
                queue.extend(self._children_of(model, kind))
        return models

    @staticmethod
    def _children_of(model, kind):
        """Los hijos de ``model`` por el eje ``kind``.

        Lee el atributo que la fuente mantiene si la clase lo declara; si no,
        deriva el eje ``_inherits`` del registro. Ver :meth:`descendants`.
        """
        declarado = getattr(model, kind + '_children', None)
        if declarado is not None:
            return declarado
        if kind == '_inherits':
            return orm.model_classes.inherits_children(model._name)
        return ()
