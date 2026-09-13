"""Base del ORM — fiel a ``odoo/orm/models.py`` (Odoo 19).

En Odoo 19 la clase base ``BaseModel``/``Model`` se define en
``odoo/orm/models.py`` y ``odoo/models/__init__.py`` la re-exporta. Aquí, con el
prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``), esta es la **definición**;
``src/models.py`` (top-level, ≙ ``odoo/models/__init__.py``) la re-exporta para
que un addon escriba ``import models`` / ``class X(models.Model)``.

Respaldo: ``models`` ES la ORM de Django — se re-exporta ``django.db.models``
completo (``Model``, ``Manager``, ``UniqueConstraint``, ``Index``, ``CASCADE``/
``SET_NULL``/``PROTECT``, ``Q``, ``Sum``, ``F``…). No se interpone una capa;
sólo se expone bajo el nombre Odoo para que el addon lea igual que su fuente.

La resolución de permiso vive aquí, como allá
==============================================

``_check_access`` y sus tres formas públicas (``check_access``, ``has_access``,
``_filtered_access``) se declaran en **este archivo** en la referencia
(``odoo19c: odoo/orm/models.py:4099-4158``), sobre ``BaseModel``. Por eso están
aquí y no en un archivo nuevo: ``odoo/orm/`` no tiene ningún ``access.py``
—verificado con ``ls``—, y crear uno repetiría :ref:`h-api-578`.

**La divergencia, y es de forma:** allá ``self`` es un *recordset*, así que los
cuatro símbolos son métodos de todo modelo. Aquí el recordset es un
``QuerySet``, y **``models.Model`` de Django no es nuestro** para colgarle
métodos. Cuelgan de un ``QuerySet`` — que es el mismo objeto, con otro nombre —
y un modelo los adopta declarando ``objects = AccessManager()``.

Consecuencia que conviene saber: en la fuente **todo** modelo los tiene; aquí
sólo los que adopten el manager. Qué modelos lo adoptan, y en qué orden, es
trabajo aparte — tarea **#96**.

Dos mecanismos de este archivo viven en un módulo hermano
==========================================================

La referencia declara los dos **aquí dentro**; aquí se extrajeron a su propio
archivo y este hogar los apunta, para que se lleguen navegando desde donde la
fuente los pone y no por casualidad:

- ``orm/inherits.py`` — ``_inherits``, la delegación por Many2one nombrado.
  Medido en la referencia: **8** ocurrencias en ``odoo19c: odoo/orm/models.py``
  y presencia en otros cuatro módulos de ``odoo/orm/`` (``fields.py``,
  ``fields_relational.py``, ``model_classes.py``, ``registry.py``). Es decir:
  el mecanismo **sí** existe allá y **no** tiene archivo propio.
- ``orm/method_chain.py`` — ``chain_method``, el relevo entre overrides que
  cuelgan por ``setattr`` desde ``AppConfig.ready()``. Éste **no** tiene
  contraparte: la referencia no lo necesita porque ``_inherit`` le construye
  una MRO real y cada override llama a ``super()``.

La forma es la misma que ``service/model.py`` ya usa para ``service/retry.py``.
Ver :ref:`h-api-855` para el veredicto por archivo de las raíces espejadas.
"""
import collections
import collections.abc
import functools
import itertools
import logging
import re
import warnings
from operator import itemgetter

from django.apps import apps
from django.db.models import *          # noqa: F401,F403  (re-export ORM completo)
from django.db.models import (  # noqa: F401
    ForeignKey, Manager, Model, QuerySet,
)
from django.db.models.base import ModelState
from django.db.models.signals import (class_prepared, post_init,
                                      pre_delete, pre_init, pre_save)
from django.dispatch import receiver

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import DatabaseError
from django.db import DEFAULT_DB_ALIAS, connections

import api

from exceptions import AccessError, UserError
from orm.environments import (
    context_scope, env, get_context, get_current_company, get_current_uid,
    get_current_user, get_transaction, is_su, sudo as elevate_privileges,
)
from orm.commands import ManyToManyLink, ManyToManySet, One2manyChild
from orm import registry
from orm.domains import Domain, to_q
from orm.fields import convert_to_display_name
from orm.identifiers import NewId
from orm.fields_nonstored import NonStored, non_stored_fields
from orm.fields_properties import Properties, check_property_field_value_name
from orm.utils import (FieldRegistryDescriptor, OriginIds, as_record_list,
                       check_object_name, model_field_registry,
                       parse_field_expr, record_ids)
from service.db import Savepoint
from tools.cache import ormcache
from tools.constants import PREFETCH_MAX
from tools.misc import OrderedSet, ReadonlyDict, partition, split_every
from tools.sql import SQL

_logger = logging.getLogger(__name__)


#: Las tres claves que **referencian** a un registro en vez de nombrar un
#: campo — ≙ ``REFERENCING_FIELDS`` de ``odoo19c:
#: addons/base/models/ir_fields.py:16``. Se declaran aquí además de allá
#: porque ``_extract_records`` las necesita para validar la cabecera del
#: archivo, y este módulo no puede importar ``ir_fields`` sin cerrar ciclo.
REFERENCING_FIELD_NAMES = frozenset({None, 'id', '.id'})


def fix_import_export_id_paths(fieldname):
    """≙ ``fix_import_export_id_paths`` (``odoo19c: odoo/orm/models.py:145-156``).

    «Fixes the id fields in import and exports, and splits field paths on
    ``/``.»

    Las dos sustituciones no son cosmética: la cabecera de un CSV escribe
    ``partner_id/.id`` o ``partner_id:id`` según de dónde venga, y ambas
    significan lo mismo — el subcampo que referencia. Se normalizan a la forma
    con barra antes de partir, así que el resto del cargador ve una sola forma.
    """
    fixed_db_id = re.sub(r'([^/])\.id', r'\1/.id', fieldname)
    fixed_external_id = re.sub(r'([^/]):id', r'\1/id', fixed_db_id)
    return fixed_external_id.split('/')


def to_record_ids(arg) -> list:
    """≙ ``to_record_ids`` (``odoo19c: odoo/orm/models.py:159-166``).

    «Return the record ids of ``arg``, which may be a recordset, an integer or
    a list of integers.»

    Las tres formas se normalizan a una lista de ids reales, y las tres
    descartan el id falso — pero **no por el mismo camino**, y la diferencia es
    de la fuente, no de este puerto:

    ================== ============================ =========================
    Forma              La fuente                     Aquí
    ================== ============================ =========================
    recordset          ``arg.ids``                   ``OriginIds(record_ids(…))``
    entero             ``[arg] if arg else []``      igual
    iterable           ``[i for i in arg if i]``     igual
    ================== ============================ =========================

    **Divergencia de mecanismo en la primera fila, no de contrato.** Aquí no
    hay recordset: un conjunto de filas es una instancia de modelo o un
    ``QuerySet``, así que ``arg.ids`` no existe y su equivalente es
    :func:`~orm.utils.record_ids`. Lo que ``.ids`` hace en la fuente
    (``odoo19c: odoo/orm/models.py:5905-5909``) es envolver sus ids en
    :class:`~orm.utils.OriginIds`, y por eso el puerto también lo envuelve: sin
    esa envoltura una fila sin guardar aportaría ``None`` a la lista.

    **La asimetría que esto deja es la de la fuente y se conserva.** Un
    :class:`~orm.identifiers.NewId` **con origen** dentro de una fila se
    resuelve a su origen; el mismo ``NewId`` dentro de una lista suelta se
    descarta, porque la rama del iterable filtra por verdad y ``NewId`` es
    falso. No se corrige: quien pasa una lista pasa ids, no registros.
    """
    if isinstance(arg, (Model, QuerySet)):
        return list(OriginIds(record_ids(arg)))
    if isinstance(arg, int):
        return [arg] if arg else []
    return [id_ for id_ in arg if id_]


def itemgetter_tuple(items):
    """≙ ``itemgetter_tuple`` (``odoo19c: odoo/orm/models.py:7097-7105``).

    «Fixes itemgetter inconsistency (useful in some cases) of not returning a
    tuple if ``len(items) == 1``: always returns an n-tuple where
    ``n = len(items)``.»
    """
    if len(items) == 0:
        return lambda a: ()
    if len(items) == 1:
        return lambda gettable: (gettable[items[0]],)
    return itemgetter(*items)


def get_columns_from_sql_diagnostics(connection, diagnostics, *,
                                     check_registry=False):
    """≙ ``get_columns_from_sql_diagnostics`` (``odoo19c: :7108-7130``).

    «Given the diagnostics of an error, return the affected column names by the
    constraint. Return an empty list if we cannot determine the columns.»

    Sirve para atribuir un error de restricción a **su** columna en el informe
    de importación. Cuando el diagnóstico no la nombra, la saca del catálogo de
    PostgreSQL —``pg_constraint`` cruzado con ``pg_attribute``—, que es donde
    vive la lista de columnas de una restricción compuesta.

    :param connection: la conexión sobre la que consultar el catálogo; ≙ el
        ``cr`` de la fuente.
    """
    if column := diagnostics.column_name:
        return [column]
    if not check_registry:
        return []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                ARRAY(
                    SELECT attname FROM pg_attribute
                    WHERE attrelid = conrelid
                    AND attnum = ANY(conkey)
                ) as "columns"
            FROM pg_constraint
            JOIN pg_class t ON t.oid = conrelid
            WHERE conname = %s
                AND t.relname = %s
                AND t.relnamespace = current_schema::regnamespace
        """, [diagnostics.constraint_name, diagnostics.table_name])
        columns = cursor.fetchone()
    return columns[0] if columns else []


def _acting_user(user):
    """El usuario que actúa — ``self.env.user`` de la referencia."""
    return get_current_user() if user is None else user


class AccessQuerySet(QuerySet):
    """Un recordset que sabe resolver su propio permiso.

    Las cuatro formas de la fuente, con la misma semántica y el mismo orden:
    primero la ACL del **modelo** (``ir.model.access``), y sólo si pasa, las
    reglas de **fila** (``ir.rule``).
    """

    def _check_access(self, operation, user=None):
        """``None`` si puede; si no, ``(prohibidos, fábrica de error)``.

        Fiel a ``odoo19c: odoo/orm/models.py:4135``. Las dos mitades y su
        orden:

        1. ``ir.model.access.check(model, operation)`` — sin permiso de modelo
           los prohibidos son **todos**, y las reglas **ni se evalúan**. La
           fuente hace ``return`` ahí mismo.
        2. Sólo entonces, ``ir.rule`` acota las filas; los prohibidos son los
           que el dominio combinado no devuelve.

        El orden no es cosmético: una regla permisiva sobre un modelo cuya ACL
        deniega devolvería "nada prohibido" si se evaluara primero.
        """
        Access = apps.get_model('base', 'IrModelAccess')
        label = self.model._meta.label
        actor = _acting_user(user)
        if not Access.check(label, operation, raise_exception=False,
                            user=actor):
            return self, functools.partial(
                Access._make_access_error, label, operation)

        Rule = apps.get_model('base', 'IrRule')
        group_ids = list(actor._get_group_ids()) if actor is not None else []
        forbidden = Rule._get_failing(
            self, mode=operation, group_ids=tuple(group_ids), user=actor)
        if forbidden.exists():
            return forbidden, functools.partial(
                Rule._make_access_error, operation, forbidden,
                group_ids=tuple(group_ids), user=actor)
        return None

    def check_access(self, operation, user=None):
        """Levanta ``AccessError`` si no puede — ``check_access``.

        ``odoo19c: odoo/orm/models.py:4100``. Bajo elevación no comprueba nada:
        ``if not self.env.su and (result := self._check_access(operation))``.
        """
        if is_su():
            return None
        result = self._check_access(operation, user=user)
        if result:
            raise result[1]()
        return None

    def has_access(self, operation, user=None):
        """Lo mismo, como booleano — ``has_access`` (``:4117``)."""
        return is_su() or not self._check_access(operation, user=user)

    def _filtered_access(self, operation, user=None):
        """El subconjunto permitido — ``_filtered_access`` (``:4123``).

        La fuente hace ``self - result[0]``; aquí la resta de recordsets es un
        ``exclude`` por PK, que es la misma operación sobre el mismo conjunto.
        """
        if not self or is_su():
            return self
        result = self._check_access(operation, user=user)
        if result:
            return self.exclude(pk__in=result[0].values_list('pk', flat=True))
        return self


    def _get_redirect_suggested_company(self, user=None):
        """La empresa que sugerir al redirigir a estos registros — ``:5825-5839``.

        La fuente lo declara en ``BaseModel`` y lo usa
        ``ir.rule._make_access_error`` para distinguir *"no tienes permiso"* de
        *"tienes permiso pero con otra empresa activa"*, que es la diferencia
        entre un 403 opaco y uno accionable. Su cuerpo es un ``if`` de tres
        ramas sobre qué campo declara el modelo:

        .. code-block:: python

           if 'company_id' in self:      return self.company_id
           elif 'company_ids' in self:   return (self.company_ids & self.env.user.company_ids)[:1]
           return False

        Aquí vive en el queryset, que es lo que en este árbol hace de
        recordset. La fuente devuelve un recordset —vacío, de uno, o la unión
        de las empresas de varias filas— y aquí una **lista**: ``company_ids``
        es un M2M inverso y su intersección con las del usuario no es un
        queryset de la misma tabla.

        ``'company_id' in self`` pregunta por el **campo**, no por el valor.
        Aquí se pregunta por los dos nombres —``company`` y su ``attname``
        ``company_id``— porque este árbol declara la FK con el nombre corto
        (:ref:`h-api-874` midió la misma distinción en ``_add_missing_default_values``).
        """
        nombres = {f.name for f in self.model._meta.get_fields()}
        nombres |= {f.attname for f in self.model._meta.fields}
        if 'company_id' in nombres:
            field_name = 'company' if 'company' in nombres else 'company_id'
            companies = []
            for record in self:
                company = getattr(record, field_name, None)
                if company is not None and company not in companies:
                    companies.append(company)
            return companies
        if 'company_ids' in nombres:
            actor = _acting_user(user)
            if actor is None:
                return []
            suyas = set(actor.company_ids.values_list('pk', flat=True))
            for record in self:
                for company in record.company_ids.all():
                    if company.pk in suyas:
                        return [company]
            return []
        return []

    def filtered_domain(self, domain):
        """Las filas de ``self`` que cumplen el dominio, en el mismo orden.

        ≙ ``BaseModel.filtered_domain``
        (``odoo19c: odoo/orm/models.py:6252-6260``). Evalúa **en memoria**: no
        emite ``WHERE``, recorre los registros que ya están en mano. Es la
        contraparte de ``filter()``, que compila el dominio a ``Q`` y deja que
        lo resuelva PostgreSQL.

        Devuelve una **lista**, no un ``QuerySet``: filtrar en Python rompe la
        pereza por construcción, y devolver algo que parece un ``QuerySet``
        invitaría a encadenarle un ``.filter()`` que volvería al motor con el
        conjunto entero. La fuente devuelve un recordset porque allá el
        recordset ya es una lista de ids en memoria.
        """
        return filtered_domain(self, domain)

    def _get_external_ids(self):
        """Los identificadores externos de cada fila — ``{pk: ['modulo.nombre']}``.

        ≙ ``BaseModel._get_external_ids``
        (``odoo19c: odoo/orm/models.py:5695-5714``). Lista vacía cuando la fila
        no tiene ninguno, y **todos** los que tenga cuando tiene varios: la
        fuente los acumula en un ``defaultdict(list)`` y ordena por ``id`` de
        ``ir.model.data``, que es lo que fija cuál queda primero.

        **La divergencia es de VÍA, no de alcance**, y es la de la sección de
        permisos de este archivo: allá cuelga de ``BaseModel``, así que todo
        modelo lo tiene; aquí el **recordset** es el ``QuerySet``, y su hogar
        es esta clase, que ya aloja las cuatro formas de permiso y
        ``filtered_domain``.

        Dos precisiones de forma, ambas medidas:

        - La fuente indexa el resultado por ``record._origin.id`` porque un
          recordset puede contener registros **sin fila** (los del formulario).
          Un ``QuerySet`` no: sólo entrega filas guardadas, así que
          ``record._origin.pk == record.pk`` para todo lo que devuelve. Se
          indexa por ``pk``.
        - La columna ``model`` de ``ir.model.data`` guarda aquí la **etiqueta
          de Django** (``base.ResGroups``), no el nombre con puntos: es lo que
          escribe ``IrModelData._update_xmlids``, que es el único escritor.
        """
        Data = apps.get_model('base', 'IrModelData')
        records = list(self)
        result = collections.defaultdict(list)
        rows = Data.objects.filter(
            model=self.model._meta.label,
            res_id__in=[record.pk for record in records],
        ).order_by('pk').values_list('module', 'name', 'res_id')
        for module, name, res_id in rows:
            result[res_id].append('%s.%s' % (module, name))
        return {record.pk: result[record.pk] for record in records}

    def get_external_id(self):
        """Un identificador externo por fila — ``{pk: 'modulo.nombre'}``.

        ≙ ``BaseModel.get_external_id``
        (``odoo19c: odoo/orm/models.py:5716-5735``). Cuando una fila tiene
        varios devuelve **uno** de ellos, y cuando no tiene ninguno devuelve
        la **cadena vacía** —no ``None``—: la fuente lo dice explícitamente,
        *"to be usable as a function field"*, y quien la consume distingue el
        caso comparando contra un falsy, no contra un centinela.
        """
        results = self._get_external_ids()
        return {key: val[0] if val else ''
                for key, val in results.items()}


#: Manager que expone las cuatro formas. Un modelo las adopta con
#: ``objects = AccessManager()``; ``RuleScopedManager`` hereda de él, así que
#: los modelos que ya declaran ``scoped`` las tienen sin cambiar nada.
AccessManager = Manager.from_queryset(AccessQuerySet)


def filtered_domain(records, domain):
    """Los registros que cumplen el dominio, en el mismo orden.

    ≙ ``BaseModel.filtered_domain``
    (``odoo19c: odoo/orm/models.py:6252-6260``), como **función de módulo**
    además de método de ``AccessQuerySet``.

    **Por qué las dos superficies y no sólo el método.** Allá ``self`` es un
    recordset y un registro suelto ya es un recordset de uno, así que un solo
    método cubre los dos casos. Aquí no: un registro **sin guardar**
    —``Model(**valores)``, que es lo que ``model.new()`` construye allá— no es
    un ``QuerySet`` y no lo puede ser. Y ese caso no es marginal: es
    exactamente el de ``ir.default._evaluate_condition_with_fallback``, que
    pregunta si el valor de respaldo de un campo dependiente de empresa cumple
    una condición. Ese valor **no está en ninguna fila**, así que no hay
    ``QuerySet`` del que partir.

    La función es el mecanismo; el método de ``AccessQuerySet`` delega en ella.

    :param records: iterable de instancias del **mismo** modelo.
    :param domain: un dominio (``Domain`` o su forma de lista).
    """
    records = list(records)
    if not records or not domain:
        return records
    model = type(records[0])
    predicate = Domain(domain)._as_predicate(model)
    return [record for record in records if predicate(record)]


class OriginMixin:
    """``_origin`` — el registro **guardado** del que este proviene.

    ≙ ``BaseModel._origin`` (``odoo19c: odoo/orm/models.py:6462-6469``). Allá un
    registro en formulario lleva un ``NewId`` cuyo ``.origin`` apunta a la fila
    persistida; sobre registros ya reales el atributo devuelve ``self`` ("already
    real records"). Es lo que permite a un ``@api.onchange`` comparar el valor
    que el usuario acaba de teclear con el que hay en base.

    **La divergencia, y es de forma** —la misma que declara la sección de
    permisos de este archivo—: allá ``self`` es un recordset y el atributo
    cuelga de ``BaseModel``, así que todo modelo lo tiene. Aquí ``models.Model``
    es el de Django y no es nuestro para colgarle nada, así que el mecanismo es
    un mixin que el modelo adopta —igual que ``objects = AccessManager()``— y
    el eje que distingue "en formulario" de "guardado" no es el tipo del id
    sino el estado de la instancia: los atributos en memoria frente a la fila.

    Quién lo adopta, medido 2026-08-28: ``ResPartner`` —el consumidor que
    registró la tarea #112, y que hasta entonces hacía la lectura a mano— y
    ``DecimalPrecision``. Quedan **ocho** sitios más con la misma lectura
    escrita a mano; decidir uno a uno cuál de ellos ES ``_origin`` y cuál es
    otra cosa es la tarea **#136**.
    """

    @property
    def _origin(self):
        """El registro tal como está en base, o ``self`` si no hay fila.

        Sin ``pk`` no hay origen que traer —es el caso "already real records"
        invertido: la fuente devuelve ``self`` cuando no hay nada que resolver,
        y aquí tampoco lo hay—. Con ``pk``, la lectura va a la base y **no** se
        memoriza: el sentido del atributo es justamente ver lo guardado, no lo
        que esta instancia recuerda.
        """
        if self.pk is None:
            return self
        return type(self)._base_manager.using(self._state.db).get(pk=self.pk)


class DefaultGetMixin:
    """``default_get`` — los valores por defecto de un alta.

    ≙ ``BaseModel.default_get`` (``odoo19c: odoo/orm/models.py:1271-1338``).
    Responde, para los campos que se le piden, el valor con que un alta
    debería empezar. Su consumidor natural es el formulario, y aquí el
    serializer o el comando que crea el registro.

    **La divergencia de forma es la de siempre en este archivo** (ver la
    sección de permisos y ``OriginMixin``): allá cuelga de ``BaseModel`` y
    todo modelo lo tiene; aquí ``models.Model`` es el de Django y no es
    nuestro, así que es un mixin que el modelo adopta.

    Por qué hacía falta la base, habiendo ya overrides
    ==================================================

    ``IrCron`` e ``IrSequenceDateRange`` ya declaraban su ``default_get``, y
    los dos **no podían llamar a ``super()``** porque no había base a la que
    llamar. Allá los dos empiezan por ``super().default_get(fields)`` y
    encima ponen lo suyo: sin la base, cada override era la respuesta
    completa, y los cuatro primeros orígenes de valor —contexto,
    ``ir.default``, el ``default`` del campo, el respaldo por empresa— no los
    veía nadie.
    """

    #: Los cinco orígenes, en el orden de la fuente, más el paso de
    #: normalización y la delegación al padre. El orden **es** el contrato:
    #: el contexto gana sobre ``ir.default``, y el ``default`` del campo gana
    #: sobre el respaldo por empresa pero no sobre el default de usuario.
    #: Reordenarlos cambia qué valor ve el alta.
    @classmethod
    def default_get(cls, fields):
        """Los valores por defecto de los campos pedidos.

        :param fields: nombres de los campos cuyo default se quiere.
        :returns: dict ``campo -> valor``, sólo con los que tengan uno.

        Un campo que no esté en ``fields`` no se considera — la nota de la
        fuente, verbatim: *"Unrequested defaults won't be considered"*.
        """
        IrDefault = apps.get_model('base', 'IrDefault')
        defaults = {}
        parent_fields = collections.defaultdict(list)
        context = get_context()
        ir_defaults = IrDefault._get_model_defaults(
            cls._meta.label, company_id=get_current_company())

        for name in fields:
            # 1. el contexto manda sobre todo lo demás
            key = 'default_' + name
            if key in context:
                defaults[name] = context[key]
                continue

            try:
                field = cls._meta.get_field(name)
            except FieldDoesNotExist:
                continue

            company_dependent = getattr(field, 'company_dependent', False)

            # 2. el default de usuario/empresa, para el campo normal
            if not company_dependent and name in ir_defaults:
                defaults[name] = ir_defaults[name]
                continue

            # 3. el ``default`` declarado en el campo
            #
            # Allá ``field.default`` es un invocable que recibe el recordset;
            # aquí Django distingue tener default de calcularlo, y su
            # ``get_default()`` ya resuelve el invocable. ``has_default()`` es
            # el discriminador correcto: un ``default=False`` o ``default=0``
            # es un default declarado, y un ``if field.default:`` lo perdería.
            if field.has_default() and not _is_plumbing_default(field):
                defaults[name] = field.get_default()
                continue

            # 4. el respaldo, para el campo dependiente de empresa
            if company_dependent and name in ir_defaults:
                defaults[name] = ir_defaults[name]
                continue

            # 5. delegar en el modelo padre, para el campo heredado
            delegated = _delegated_origin(cls, name)
            if delegated is not None:
                parent_model, parent_name = delegated
                parent_fields[parent_model].append(parent_name)

        # 6. normalizar el valor pasandolo por el campo
        #
        # La fuente lo hace para TODO campo: ``convert_to_cache`` y luego
        # ``convert_to_write``, con el comentario de que el paso existe para
        # que un x2many salga como ``[(SET, 0, [2, 3])]`` y no como una lista
        # de ``LINK``. Aqui el par de conversion lo declaran los campos que lo
        # necesitan —``Properties`` y ``PropertiesDefinition``
        # (``orm/fields_properties.py``)—, y el motivo x2many no se puede dar:
        # nuestro ``Command`` es **ejecutivo**, escribe al llamarlo en vez de
        # devolver una tupla, asi que un default de x2many nunca es una lista
        # de comandos. Esa divergencia es de la clase entera y ya tiene su
        # registro (:ref:`h-api-589`, tarea **#345**), no se abre aqui.
        instance = cls()
        for name, value in list(defaults.items()):
            try:
                field = cls._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            if not (hasattr(field, 'convert_to_cache')
                    and hasattr(field, 'convert_to_write')):
                continue
            cached = field.convert_to_cache(value, instance, validate=False)
            defaults[name] = field.convert_to_write(cached, instance)

        # 7. los defaults del padre, por el mismo camino
        for parent_model, names in parent_fields.items():
            if hasattr(parent_model, 'default_get'):
                defaults.update(parent_model.default_get(names))

        return defaults

    @classmethod
    def _add_missing_default_values(cls, values):
        """Completa ``values`` con el default de los campos que no trae.

        ≙ ``_add_missing_default_values``
        (``odoo19c: odoo/orm/models.py:1546-1596``). Es el consumidor real de
        :meth:`default_get`: sin él, ``default_get`` responde bien y nadie le
        pregunta — que es exactamente el estado en que estaba el árbol antes
        de la tarea **#113**.

        Los valores dados **siempre** ganan al default; el comentario de la
        fuente lo dice verbatim: *"override defaults with the provided
        values, never allow the other way around"*.

        :param values: el dict del alta, tal como llega.
        :returns: un dict nuevo con los defaults que faltaban ya puestos.
        """
        avoid_models = set()

        def collect_models_to_avoid(model):
            """No pisar el valor heredado cuando el padre ya viene puesto.

            El conjunto guarda **la clase**, no el nombre punteado que la
            fuente usa como llave de ``_inherits``: aquí quien responde
            :func:`_delegated_origin` es la clase, y comparar la llave contra
            ``_meta.label`` no casa nunca — ``'res.partner'`` frente a
            ``'base.ResPartner'``. Medido: el filtro no excluía nada.

            Y el FK se busca por sus **dos** nombres. ``ResUsers`` declara
            ``partner = fields.Many2one(...)``, así que ``_inherits`` dice
            ``'partner'`` y Django le pone ``attname='partner_id'``; un alta
            puede traer cualquiera de los dos y las dos formas nombran al
            mismo padre.
            """
            for _parent_name, fk_name in getattr(model, '_inherits', {}).items():
                parent = _inherits_parent(model, fk_name)
                if parent is None:
                    continue
                try:
                    fk_field = model._meta.get_field(fk_name)
                except FieldDoesNotExist:
                    continue
                if fk_field.name in values or fk_field.attname in values:
                    avoid_models.add(parent)
                else:
                    collect_models_to_avoid(parent)

        collect_models_to_avoid(cls)

        def avoid(name):
            """¿El campo llega heredado de un padre que ya viene puesto?"""
            if not avoid_models:
                return False
            delegated = _delegated_origin(cls, name)
            if delegated is None:
                return False
            parent_model, _ = delegated
            return parent_model in avoid_models

        missing_defaults = [
            name
            for name in _field_names(cls)
            if name not in values
            if not avoid(name)
        ]

        if missing_defaults:
            defaults = cls.default_get(missing_defaults)
            defaults.update(values)
        else:
            defaults = dict(values)

        # Delegar el default de las propiedades en el propio campo.
        for field in cls._meta.get_fields():
            if hasattr(field, '_add_default_values'):
                defaults[field.name] = field._add_default_values(defaults)

        return defaults

    @classmethod
    def create(cls, **values):
        """Alta que aplica los defaults que faltan, como la fuente.

        ≙ la llamada ``vals = self._add_missing_default_values(vals)`` que
        ``BaseModel.create`` hace en ``odoo19c: odoo/orm/models.py:4796``.

        **La divergencia de forma, declarada:** allá ``create`` recibe una
        lista de dicts y devuelve un recordset; aquí recibe kwargs y devuelve
        una instancia, que es la firma que ya usan los seis ``create`` de
        clase del árbol (``ir_config_parameter``, ``res_currency``,
        ``ir_default``, …). Lo que se porta es **el paso**, no la firma.

        El **muchos-a-muchos se asigna después del alta**, no dentro: Django
        exige la fila antes de poblar la tabla intermedia. Allá el mismo caso
        se resuelve convirtiendo la lista de ids en ``[Command.set(value)]``
        (``:1580-1581``); aquí el equivalente es ``manager.set(...)``, porque
        nuestro ``Command`` es ejecutivo (:ref:`h-api-589`, tarea **#345**).
        """
        values = cls._add_missing_default_values(values)
        deferred = {}
        for field in cls._meta.many_to_many:
            if field.name in values:
                deferred[field.name] = values.pop(field.name)
        record = cls.objects.create(**values)
        for name, value in deferred.items():
            getattr(record, name).set(value)
        return record


#: ≙ ``LOG_ACCESS_COLUMNS`` (``odoo19c: odoo/orm/models.py:296``). Allá son
#: ``create_uid``, ``create_date``, ``write_uid`` y ``write_date``; aquí el
#: mecanismo es ``TimeStampedModel``, que declara dos —``created_at`` y
#: ``updated_at``, ambas ``auto_now``— y ninguna de autoría. La divergencia es
#: del mixin, no de este archivo: quién escribió la fila no se guarda.
LOG_ACCESS_COLUMNS = ['created_at', 'updated_at']

#: ≙ ``MAGIC_COLUMNS`` (``odoo19c: odoo/orm/models.py:297``).
MAGIC_COLUMNS = ['id'] + LOG_ACCESS_COLUMNS

#: ≙ ``regex_order`` (``odoo19c: odoo/orm/models.py:93-104``), verbatim.
#: Acota la cláusula ``_order`` entera: una lista de campos separados por coma,
#: cada uno con su dirección y su tratamiento de nulos opcionales. Es lo que
#: :meth:`BaseModel._check_qorder` mide antes de dejar pasar un orden.
regex_order = re.compile(r"""
    ^
    (\s*
        (?P<term>((?P<field>[a-z0-9_]+)(\.(?P<property>[a-z0-9_]+))?(:(?P<func>[a-z_]+))?))
        (\s+(?P<direction>desc|asc))?
        (\s+(?P<nulls>nulls\ first|nulls\ last))?
        \s*
        (,|$)
    )+
    (?<!,)
    $
""", re.IGNORECASE | re.VERBOSE)


#: ≙ el nombre que la referencia usa para la empresa de un registro. Aquí la
#: convención renombró la FK: ``company`` en 76 declaraciones y ``company_id``
#: en 6 (medido sobre ``addons/`` y ``src/``), así que la búsqueda mira las
#: dos formas antes de rendirse. El orden es el de frecuencia, no el de gusto.
COMPANY_FIELD_NAMES = ('company', 'company_id')

#: Su hermano plural — ≙ ``company_ids`` de la fuente. ``ResUsers`` ya lo
#: consume en su ``_check_company_domain`` propio (``res_users.py:1387``).
COMPANIES_FIELD_NAMES = ('companies', 'company_ids')


def _first_field_name(model, candidates):
    """El primero de ``candidates`` que el modelo declara, o ``None``.

    Ni la referencia ni Django ofrecen esto: allá la pregunta es
    ``'company_id' in self``, que sobre un recordset consulta ``_fields``.
    Aquí el equivalente es ``_meta.get_field``, y hace falta el bucle porque
    el nombre no es uno solo (ver :data:`COMPANY_FIELD_NAMES`).
    """
    for name in candidates:
        try:
            model._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        return name
    return None


class BaseUrlMixin:
    """La URL raíz desde la que se sirve un registro.

    ≙ ``BaseModel.get_base_url`` (``odoo19c: odoo/orm/models.py:3985-3995``),
    que la fuente declara justo antes de ``_check_company_domain`` — de ahí
    que aquí viva pegado a :class:`CheckCompanyMixin`, en el mismo archivo
    espejado.

    **Quién la consume.** ``ir.actions.report._get_report_url``, que arma la
    URL con que el motor resuelve los recursos de una plantilla (hojas de
    estilo, imágenes) mientras la renderiza. Sin ella el porte de ese método
    no tiene de dónde sacar la raíz.

    **La divergencia de forma es la de siempre en este archivo**: allá cuelga
    de ``BaseModel`` y todo modelo la tiene; aquí ``models.Model`` es el de
    Django, así que viaja por ``TimeStampedModel``, la base común del
    proyecto. Es un mixin sin campos ni manager a propósito — uno con manager
    eclipsaría el de toda base declarada más abajo, que es el defecto medido
    en :ref:`h-api-876`.
    """

    def get_base_url(self):
        """Devuelve la URL raíz de este registro.

        Por defecto devuelve el parámetro ``web.base.url``, pero un modelo
        puede sobreescribirla.

        ≙ ``get_base_url`` (``odoo19c: models.py:3985``). Tres notas de
        forma, ninguna recorta el contrato:

        - La fuente valida ``len(self) > 1`` porque allá el receptor es un
          conjunto de registros; aquí es una instancia y esa rama no tiene
          forma que tomar.
        - El ``sudo()`` de la fuente tampoco: ``get_param`` es un
          ``classmethod`` que lee sin pasar por reglas de fila.
        - El ``self.env['ir.config_parameter']`` de la fuente es una consulta
          al registro, tardía a propósito; aquí es
          ``registry.model_by_name('ir.config_parameter')``, que es como este
          mismo archivo ya alcanza a ``ir.fields.converter``. Importarlo al
          top invertiría la capa: ``orm`` no depende de ``addons``.

        :return: la URL base de este registro
        """
        parameters = registry.model_by_name('ir.config_parameter')
        return parameters.get_param('web.base.url') if parameters else None


class CheckCompanyMixin:
    """Coherencia de empresa entre un registro y aquello a lo que apunta.

    ≙ ``BaseModel._check_company_auto`` / ``_check_company_domain`` /
    ``_check_company`` (``odoo19c: odoo/orm/models.py:451, 3997, 4009``), más
    sus dos llamadas desde ``write`` (``:4516``) y ``create`` (``:4744``).

    **El problema que cierra.** ``check_company=True`` marca un campo
    relacional para que el ORM verifique que el registro apuntado pertenece a
    la misma empresa que el registro que apunta —o a ninguna, que en este
    modelo significa «compartido»—. Sin el mecanismo, la palabra clave es
    decoración: se declara y nadie la lee. Medido en la referencia sobre los
    addons que este árbol ya tiene: **282** ``Many2one``, **19** ``Many2many``
    y **5** ``One2many`` la llevan, y seis archivos nuestros la declaraban
    como bloqueo explícito (``account/models/res_company.py:47``,
    ``hr/models/hr_work_location.py:20``,
    ``certificate/models/certificate.py:218``, …).

    **La divergencia de forma es la de siempre en este archivo**: allá cuelga
    de ``BaseModel`` y todo modelo lo tiene con ``_check_company_auto = False``;
    aquí ``models.Model`` es el de Django y no es nuestro, así que viaja por
    ``TimeStampedModel`` —la base común del proyecto— con el mismo valor por
    defecto. Un modelo lo enciende declarando ``_check_company_auto = True``,
    exactamente como la fuente.

    **Qué NO se porta, y no es olvido.** ``_description_domain``
    (``odoo19c: odoo/orm/fields_relational.py:131-157``) usa la misma marca
    para acotar el *selector* del widget: construye una cadena de dominio que
    consume ``fields_get`` y la interpreta el cliente web. Este stack no tiene
    esa capa (DEC-FW-01: API DRF + UI propia, sin vistas XML), así que no hay
    destinatario para esa cadena. El acotamiento del selector, donde importa,
    se declara con ``limit_choices_to`` en el campo — que es el constructor de
    Django para el mismo papel y ya se usa así en el árbol.

    ``check_company`` sobre un ``One2many`` (5 en la referencia) tampoco tiene
    sitio de declaración: aquí un One2many es el reverso de una FK
    (``related_name``) y no un campo propio, así que la marca vive en la FK
    del otro lado, que es donde el registro apuntado guarda su empresa.
    """

    #: ≙ ``_check_company_auto: bool = False`` (``odoo19c: models.py:451``).
    #: Al guardar, ``save()`` llama a ``_check_company`` sólo si está en
    #: ``True``. El defecto es ``False`` allá y aquí: encenderlo es una
    #: decisión por modelo, y la fuente la toma en 76 clases.
    _check_company_auto = False

    @classmethod
    def _check_company_domain(cls, companies):
        """El predicado con que ESTE modelo se valida contra unas empresas.

        ≙ ``_check_company_domain`` (``odoo19c: models.py:3997-4007``). La
        fuente devuelve ``Domain('company_id','in', ids + [False])``: el
        registro vale si es de alguna de esas empresas **o si no es de
        ninguna**, que es como se expresa «compartido entre todas».

        Se devuelve un ``Q`` en vez de un ``Domain`` porque el consumidor es
        un ``QuerySet``. ``ResUsers`` ya redefine este método con esa misma
        firma (``src/addons/base/models/res_users.py:1369``), que es el
        precedente de forma; allá lo redefine por el mismo motivo — para un
        usuario la pregunta correcta es por sus empresas permitidas, no por
        su empresa por defecto.

        Un modelo sin campo de empresa no tiene con qué discriminar: devuelve
        ``None``, y quien llama lo lee como «este comodelo no participa».
        """
        name = _first_field_name(cls, COMPANY_FIELD_NAMES)
        if name is None:
            return None
        ids = _company_ids(companies)
        if not ids:
            return Q(**{f'{name}__isnull': True})
        return Q(**{f'{name}__in': ids}) | Q(**{f'{name}__isnull': True})

    def _check_company(self, fnames=None):
        """Verifica la empresa de lo que apuntan los campos marcados.

        ≙ ``_check_company`` (``odoo19c: models.py:4009-4090``). Recorre los
        campos relacionales con ``check_company`` y, para cada valor apuntado,
        exige que su empresa sea la del registro o ninguna. Acumula las
        incoherencias y lanza **una** ``UserError`` con hasta cinco, como la
        fuente — no una por campo: quien corrige un formulario quiere ver
        todo lo que está mal de una vez.

        ``fnames`` acota el recorrido a los campos escritos. Igual que allá,
        si entre ellos va el propio campo de empresa se revisan **todos**: al
        cambiar de empresa, un valor que antes era coherente puede dejar de
        serlo aunque nadie lo haya tocado.

        La segunda mitad de la fuente —los campos ``company_dependent``, que
        se validan contra la empresa del entorno y no contra la del
        registro— se porta con :func:`~orm.environments.get_current_company`,
        que es el equivalente de ``self.env.company``.
        """
        regular, dependent = self._check_company_fields(fnames)
        if not regular and not dependent:
            return

        inconsistencies = []
        own_name = _first_field_name(type(self), COMPANY_FIELD_NAMES)
        many_name = _first_field_name(type(self), COMPANIES_FIELD_NAMES)

        if regular:
            if type(self)._meta.label_lower == 'base.rescompany':
                # ≙ ``if self._name == 'res.company': companies = record``
                # (:4051). La empresa de una empresa es ella misma.
                companies = [self]
            elif own_name is not None:
                companies = [getattr(self, own_name, None)]
            elif many_name is not None:
                companies = list(getattr(self, many_name).all())
            else:
                _logger.warning(
                    'Se omite la verificación de empresa de %s: sus campos %s '
                    'están marcados check_company pero el modelo no declara '
                    'ni %s ni %s.',
                    type(self)._meta.label, sorted(regular),
                    ' / '.join(COMPANY_FIELD_NAMES),
                    ' / '.join(COMPANIES_FIELD_NAMES),
                )
                companies = None
            if companies is not None:
                companies = [c for c in companies if c is not None]
                inconsistencies += self._company_inconsistencies(regular, companies)

        if dependent:
            inconsistencies += self._company_inconsistencies(
                dependent, [c for c in [get_current_company()] if c is not None])

        if inconsistencies:
            raise UserError(self._company_inconsistency_message(inconsistencies))

    @classmethod
    def _check_company_fields(cls, fnames=None):
        """Los nombres de campo marcados, partidos en regulares y por empresa.

        ≙ el primer bloque de ``_check_company`` (``odoo19c: models.py:4029-
        4040``), extraído a su propio método porque aquí lo consumen dos
        sitios: la verificación y su prueba, que necesita poder preguntar qué
        va a mirar sin escribir nada.
        """
        campos = {f.name: f for f in cls._meta.get_fields()
                  if getattr(f, 'check_company', False)}
        if fnames is not None and not (set(COMPANY_FIELD_NAMES) |
                                       set(COMPANIES_FIELD_NAMES)) & set(fnames):
            campos = {n: f for n, f in campos.items() if n in set(fnames)}
        regular, dependent = [], []
        for name, field in campos.items():
            (dependent if getattr(field, 'company_dependent', False)
             else regular).append(name)
        return regular, dependent

    def _company_inconsistencies(self, fnames, companies):
        """Las ternas ``(registro, campo, apuntado)`` que no cuadran.

        ≙ el bucle interior de ``_check_company`` (``:4055-4078``). Un campo
        vacío no se mira; uno cuyo comodelo no tiene empresa tampoco, porque
        su ``_check_company_domain`` devuelve ``None`` y no hay con qué
        discriminar.
        """
        fuera = []
        for name in fnames:
            corecords = _corecords(self, name)
            if not corecords:
                continue
            comodel = type(corecords[0])
            domain = comodel._check_company_domain(companies)
            if domain is None:
                continue
            validos = set(comodel._base_manager.filter(
                domain, pk__in=[c.pk for c in corecords],
            ).values_list('pk', flat=True))
            if any(c.pk not in validos for c in corecords):
                fuera.append((self, name, corecords))
        return fuera

    @staticmethod
    def _company_inconsistency_message(inconsistencies):
        """El texto del rechazo — ≙ ``:4080-4090``, con sus cinco primeras.

        La fuente distingue tres redacciones (empresa, registro, empresa
        raíz); aquí se conserva la del registro, que es la que aplica a los
        casos medidos. Sin ``_()``: este archivo no importa ``tools.translate``
        —medido, 0 usos— y su única ``UserError`` (``:1931``) también escribe
        el texto directo.
        """
        lines = ['Hay incoherencias de empresa:']
        for record, name, corecords in inconsistencies[:5]:
            values = ', '.join(str(c) for c in corecords)
            lines.append(
                f'- «{record}» pertenece a una empresa y «{name}» '
                f'({values}) pertenece a otra.'
            )
        return '\n'.join(lines)

    def save(self, *args, **kwargs):
        """≙ las dos llamadas de la fuente, que van **después** del escribir.

        ``write`` (``odoo19c: models.py:4516``) y ``create`` (``:4744``)
        llaman a ``_check_company`` una vez completada la escritura, no antes:
        la verificación mira el estado final del registro, incluido lo que
        hayan puesto los ``compute`` y los inversos. Aquí pasa lo mismo con
        ``save()``, y por eso la excepción llega con la fila ya escrita — como
        allá, donde la transacción es la que deshace.

        ``update_fields`` hace de ``list(vals)``: acota el recorrido a lo que
        se escribió. Sin él se revisan todos los campos marcados, que es lo
        que la fuente hace en ``create``.
        """
        super().save(*args, **kwargs)
        if self._check_company_auto:
            update_fields = kwargs.get('update_fields')
            self._check_company(
                None if update_fields is None else list(update_fields))


def _company_ids(companies):
    """Las claves primarias de ``companies``, venga como venga.

    ≙ ``to_record_ids`` (``odoo19c: odoo/orm/models.py:159-166``), que acepta
    un recordset, un entero o una lista. Aquí lo que llega es una instancia,
    un ``QuerySet``, una lista de instancias o una lista de enteros; los
    cuatro se normalizan a una lista de ``pk``, y los falsos se descartan
    igual que allá.
    """
    if companies is None:
        return []
    if hasattr(companies, 'values_list'):
        return [pk for pk in companies.values_list('pk', flat=True) if pk]
    if not isinstance(companies, (list, tuple, set)):
        companies = [companies]
    ids = []
    for c in companies:
        pk = getattr(c, 'pk', c)
        if pk:
            ids.append(pk)
    return ids


def _ancestor_company_ids(companies):
    """Los ids de ``companies`` **y de todos sus ancestros**.

    ≙ el cuerpo comun de los dos ``*_parent_of`` de la fuente
    (``odoo19c: odoo/orm/models.py:180-184`` y ``:196-200``), que recorre
    ``rec.parent_path.split('/')[:-1]`` de cada empresa.

    ``parent_path`` es la ruta materializada (``'1/4/9/'``) que
    ``ResCompany._compute_parent_path`` mantiene: la lista de ancestros mas la
    propia empresa, con separador final. El ``[:-1]`` de la fuente descarta el
    hueco que deja ese separador, no un ancestro.

    Una empresa sin ``parent_path`` poblado cae a su propio id: es la
    respuesta correcta —una raiz es su unico ancestro— y evita que una fila
    sin calcular desaparezca del dominio en silencio.
    """
    company_model = registry.MODELS_BY_NAME.get('res.company')
    ids = _company_ids(companies)
    if company_model is None or not ids:
        return ids
    ancestors = []
    for company in company_model.objects.filter(pk__in=ids):
        path = company.parent_path or ''
        segments = [seg for seg in path.split('/')[:-1] if seg]
        ancestors.extend(int(seg) for seg in segments) if segments \
            else ancestors.append(company.pk)
    return ancestors


def check_company_domain_parent_of(cls, companies):
    """Predicado de coherencia de empresa que admite a los **ancestros**.

    ≙ ``check_company_domain_parent_of``
    (``odoo19c: odoo/orm/models.py:169-184``). Docstring de la fuente,
    verbatim: *"A `_check_company_domain` function that lets a record be used
    if either: record.company_id = False (which implies that it is shared
    between all companies), or record.company_id is a parent of any of the
    given companies."*

    Es la variante **jerarquica** de
    :meth:`CheckCompanyMixin._check_company_domain`: aquella exige que la
    empresa del registro este entre las dadas; esta admite ademas cualquier
    ancestro suyo, que es como una matriz comparte catalogos con sus filiales.

    Se declara como funcion de modulo —no como metodo— porque asi la declara
    la fuente y asi la consumen los modelos:
    ``_check_company_domain = models.check_company_domain_parent_of`` es una
    **asignacion de atributo de clase**, no una sobreescritura. El primer
    parametro se llama ``cls`` y no ``self`` porque en este arbol el consumidor
    (:meth:`CheckCompanyMixin._check_company`) lo invoca sobre la clase.

    Devuelve un ``Q`` y no un ``Domain`` por la misma razon que su hermano de
    clase: el consumidor es un ``QuerySet``.

    La rama ``isinstance(companies, str)`` de la fuente —el dominio simbolico
    ``('company_id', 'parent_of', companies)``— **no se porta**: aqui el
    operador ``parent_of`` sobre un nombre de campo es la tarea **#235**, y
    hasta que exista un ``Q`` no puede expresarlo. Un ``str`` levanta
    ``TypeError`` en vez de devolver un predicado que no discrimina.
    """
    if isinstance(companies, str):
        raise TypeError(
            'check_company_domain_parent_of no acepta un dominio simbolico: '
            'el operador parent_of sobre un nombre de campo es la tarea #235'
        )
    name = _first_field_name(cls, COMPANY_FIELD_NAMES)
    if name is None:
        return None
    ids = _ancestor_company_ids(companies)
    if not ids:
        return Q(**{f'{name}__isnull': True})
    return Q(**{f'{name}__in': ids}) | Q(**{f'{name}__isnull': True})


def check_companies_domain_parent_of(cls, companies):
    """Su hermano plural, sobre el M2M de empresas.

    ≙ ``check_companies_domain_parent_of``
    (``odoo19c: odoo/orm/models.py:188-200``). Docstring de la fuente,
    verbatim: *"A `_check_company_domain` function that lets a record be used
    if any company in record.company_ids is a parent of any of the given
    companies."*

    **La diferencia con el singular no es cosmetica**: aqui NO hay rama de
    «compartido entre todas». La fuente devuelve ``[]`` —dominio vacio, todo
    pasa— cuando no se dan empresas, y un registro sin ninguna empresa en su
    M2M no entra en el dominio. Se conserva: ``None`` significa «este modelo no
    participa», que es otra cosa.
    """
    if isinstance(companies, str):
        raise TypeError(
            'check_companies_domain_parent_of no acepta un dominio simbolico: '
            'el operador parent_of sobre un nombre de campo es la tarea #235'
        )
    name = _first_field_name(cls, COMPANIES_FIELD_NAMES)
    if name is None:
        return None
    ids = _ancestor_company_ids(companies)
    if not ids:
        return Q()
    return Q(**{f'{name}__in': ids})


def _corecords(record, name):
    """Los registros que ``record.<name>`` apunta, siempre como lista.

    Un Many2one da uno o ninguno; un Many2many, los que haya. La fuente no
    necesita distinguirlos porque allá todo es recordset; aquí sí, y la
    distinción se hace por el descriptor, no por el nombre del campo.
    """
    value = getattr(record, name, None)
    if value is None:
        return []
    if hasattr(value, 'all'):
        return list(value.all())
    return [value]


class CopyMixin:
    """``copy`` y su cadena — duplicar un registro con sus hijos.

    ≙ los tres métodos que ``BaseModel`` declara seguidos:
    ``copy_data`` (``odoo19c: odoo/orm/models.py:5406``),
    ``copy_translations`` (``:5465``) y ``copy`` (``:5530``). Van juntos
    porque el último llama a los otros dos.

    **La divergencia de forma es la de siempre en este archivo** (ver
    ``OriginMixin``, ``FieldSqlMixin`` y ``DefaultGetMixin``): allá cuelgan de
    ``BaseModel`` y todo modelo los tiene; aquí ``models.Model`` es el de
    Django y no es nuestro, así que es un mixin que el modelo adopta.

    Qué decide qué se copia
    =======================

    El discriminador es ``field.copy``, que este árbol acaba de construir en
    ``orm/fields.py`` con la ortografía de la fuente. Sobre él van las dos
    listas de la fuente: la **negra** —:data:`MAGIC_COLUMNS` más
    ``parent_path`` y los FK de delegación— y la **blanca**, que son los
    campos propios frente a los que llegan heredados.
    """

    @classmethod
    def _copy_blacklist(cls, default):
        """Los campos que un duplicado NO lleva, con su razón.

        ≙ el bloque ``blacklist``/``whitelist``/``blacklist_given_fields``
        (``odoo19c: odoo/orm/models.py:5419-5434``). Se saca a un método
        propio porque :meth:`copy_data` lo usa una vez y el test lo mide
        aparte — allá es una clausura y no se puede interrogar.
        """
        blacklist = set(MAGIC_COLUMNS) | {'parent_path'}
        whitelist = {name for name in _field_names(cls)
                     if _delegated_origin(cls, name) is None}

        def blacklist_given_fields(model):
            """Lo que llega por delegación lo pone el padre, no la copia."""
            for _parent_name, fk_name in getattr(model, '_inherits', {}).items():
                parent = _inherits_parent(model, fk_name)
                if parent is None:
                    continue
                try:
                    fk_field = model._meta.get_field(fk_name)
                except FieldDoesNotExist:
                    continue
                blacklist.add(fk_field.name)
                blacklist.add(fk_field.attname)
                if fk_field.name in default or fk_field.attname in default:
                    # El registro trae el padre entero: todos sus campos los
                    # da él, salvo los que el hijo redefina.
                    blacklist.update(set(_field_names(parent)) - whitelist)
                else:
                    blacklist_given_fields(parent)

        blacklist_given_fields(cls)
        return blacklist

    def copy_data(self, default=None, seen=None):
        """Los valores con que se daría de alta un duplicado de este registro.

        ≙ ``copy_data`` (``odoo19c: odoo/orm/models.py:5406-5462``).

        Docstring de la fuente, verbatim: *"Copy given record's data with all
        its fields values"*.

        :param default: valores que pisan a los del original.
        :param seen: los ya visitados, por modelo — la guarda contra la
            recursión de una relación circular. Allá viaja en el contexto
            (``__copy_data_seen``); aquí es un parámetro, porque el contexto
            de este árbol es de **sólo lectura** por diseño
            (``orm/environments.py``) y un ``defaultdict`` que se muta dentro
            no cabe en él. Es la misma guarda con otro vehículo.
        :returns: el dict de valores, o ``None`` si el registro ya se visitó.

        **Devuelve un dict, no una lista.** Allá ``self`` es un recordset y el
        método responde uno por registro; aquí es una instancia. La forma
        plural la recupera quien la necesite iterando, que es lo que
        :meth:`copy` hace.
        """
        cls = type(self)
        default = dict(default or {})
        seen = collections.defaultdict(set) if seen is None else seen

        if self.pk in seen[cls._meta.label]:
            return None
        seen[cls._meta.label].add(self.pk)

        blacklist = cls._copy_blacklist(default)
        values = default.copy()

        for field in cls._meta.concrete_fields:
            if not getattr(field, 'copy', True):
                continue
            if field.name in default or field.name in blacklist:
                continue
            if field.attname in default or field.attname in blacklist:
                continue
            if field.is_relation:
                # El id, no la instancia: es lo que ``objects.create`` toma, y
                # evita releer la fila apuntada.
                values[field.attname] = getattr(self, field.attname)
            else:
                values[field.name] = getattr(self, field.name)

        return values

    def copy_children(self, new, seen=None):
        """Duplica los hijos ``one2many`` del original bajo el nuevo registro.

        ≙ la rama ``if field.type == 'one2many'`` de ``copy_data``
        (``odoo19c: :5450-5455``), que allá vive **dentro** del mismo método
        porque su ``Command.create`` es una tupla que el ORM aplica después.

        Aquí no puede vivir dentro: nuestro ``Command`` es **ejecutivo**
        —escribe al llamarlo (:ref:`h-api-589`, tarea **#345**)— y Django
        exige la fila del padre antes de poder colgarle un hijo. Así que el
        paso se separa y corre **después** del alta, con el padre ya con ``pk``.
        El efecto es el mismo que el de la fuente: los hijos se duplican *"using
        the wrong (old) parent, but then are reassigned to the correct one"*.

        El orden **por id** no es cosmético; el comentario de la fuente lo dice:
        *"duplicate following the order of the ids because we'll rely on it
        later for copying translations"*.
        """
        cls = type(self)
        seen = collections.defaultdict(set) if seen is None else seen
        for relation in cls._meta.related_objects:
            if not relation.one_to_many:
                continue
            accessor = relation.get_accessor_name()
            if accessor is None or not hasattr(self, accessor):
                continue
            child_model = relation.related_model
            if not issubclass(child_model, CopyMixin):
                continue
            fk_name = relation.field.name
            for child in getattr(self, accessor).order_by('id'):
                child_values = child.copy_data({fk_name: new}, seen=seen)
                if child_values is None:
                    continue
                child_values.pop(relation.field.attname, None)
                child_values[fk_name] = new
                nuevo_hijo = child_model.create(**child_values)
                child.copy_children(nuevo_hijo, seen=seen)

    def copy_translations(self, new, excluded=()):
        """BLOQUEADO por ``translate`` — el almacenamiento por idioma.

        ≙ ``copy_translations`` (``odoo19c: odoo/orm/models.py:5465-5528``).

        No es una divergencia de mecanismo ni una omisión: **no hay
        traducciones que copiar**. La referencia guarda el campo traducible
        como columna ``jsonb`` ``{lang: valor}``; aquí ``translate=True`` se
        **anota** en el campo (``field.translate``, ``orm/fields_textual``)
        y la columna sigue siendo ``varchar`` con un solo idioma. Los tres
        símbolos que el cuerpo consume —``_get_stored_translations``,
        ``update_field_translations``, ``get_translation_dictionary``— están
        medidos en **0** definiciones bajo ``src/``.

        El método existe con su firma para que :meth:`copy` lo llame donde la
        fuente lo llama: cuando #333 construya el almacenamiento, el cuerpo se
        escribe aquí y ``copy`` no cambia. Sucesor: tarea **#333**.
        """
        return None

    def copy(self, default=None):
        """Duplica el registro, con sus hijos, aplicando ``default``.

        ≙ ``copy`` (``odoo19c: odoo/orm/models.py:5530-5542``).

        Docstring de la fuente, verbatim: *"Duplicate record ``self`` updating
        it with default values."*

        :param default: valores que pisan a los del original.
        :returns: el registro nuevo.

        Los tres pasos de la fuente, en su orden: ``copy_data``, el alta, y
        ``copy_translations``. El alta va por :meth:`DefaultGetMixin.create`
        cuando el modelo lo adopta —así el duplicado recibe los defaults que
        un alta normal recibiría, como allá— y por ``objects.create`` si no.

        El ``with_context(active_test=False)`` de la fuente **no** tiene
        contraparte: ese filtro implícito por ``active`` es de su ORM, y aquí
        un ``QuerySet`` no lo lleva. Sin filtro que desactivar, no hay
        contexto que poner.
        """
        cls = type(self)
        seen = collections.defaultdict(set)
        values = self.copy_data(default, seen=seen)
        if values is None:
            return None
        alta = cls.create if hasattr(cls, '_add_missing_default_values') \
            else cls.objects.create
        new = alta(**values)
        self.copy_children(new, seen=seen)
        self.copy_translations(new, excluded=default or ())
        return new


def _is_plumbing_default(field):
    """¿El ``default`` del campo es fontanería de columna y no un default real?

    NO tiene contraparte: allá ``field.default`` es lo que el desarrollador
    escribió y nada más, así que ``if field.default:`` distingue solo. Aquí un
    ``CompanyDependent`` guarda un ``jsonb`` y su constructor pone
    ``kwargs.setdefault('default', dict)``
    (``orm/fields_company_dependent.py:286``) para que la columna arranque con
    el mapa vacío — eso **no** es un valor por defecto del campo.

    Sin este discriminador el paso 3 se comería al 4 en **todo** campo
    dependiente de empresa: ``default_get`` respondía ``{}`` y el respaldo de
    ``ir.default`` no se veía nunca. Medido con ``barcode`` de ``res.partner``.

    El ``setdefault`` es lo que hace posible distinguirlos: un default que el
    desarrollador sí escribió sobrevive y no es ``dict``.
    """
    return (getattr(field, 'company_dependent', False)
            and field.default is dict)


def _inherits_parent(model, fk_name):
    """El modelo al que apunta el FK de delegación ``fk_name``, o ``None``.

    NO tiene contraparte con este nombre: allá el padre se resuelve con
    ``self.env[parent_mname]``, porque el nombre del modelo **es** la llave
    del registro. Aquí la llave es la clase, así que se llega por el FK.
    """
    try:
        fk_field = model._meta.get_field(fk_name)
    except FieldDoesNotExist:
        return None
    return getattr(fk_field, 'related_model', None)


def _field_names(model):
    """Los nombres de campo que un alta puede recibir, incluidos los del padre.

    ≙ el recorrido de ``self._fields`` de la fuente
    (``odoo19c: odoo/orm/models.py:1571-1575``). Allá ``_fields`` ya trae los
    campos que ``_inherits`` refleja en el hijo; aquí ``_meta`` sólo conoce los
    propios, así que los del padre se añaden por el mapa de delegación —el
    mismo camino que :func:`_delegated_origin` recorre en sentido inverso.

    Se excluyen las relaciones inversas: no son valores que un alta reciba.
    """
    names = []
    seen = set()
    for field in [*model._meta.concrete_fields, *model._meta.many_to_many]:
        if field.name not in seen:
            seen.add(field.name)
            names.append(field.name)
    for parent_name, fk_name in getattr(model, '_inherits', {}).items():
        parent = _inherits_parent(model, fk_name)
        if parent is None:
            continue
        for field in [*parent._meta.concrete_fields, *parent._meta.many_to_many]:
            if field.name not in seen:
                seen.add(field.name)
                names.append(field.name)
    return names


def _delegated_origin(model, name):
    """El ``(modelo padre, campo)`` del que ``name`` se hereda, o ``None``.

    NO tiene contraparte con este nombre: allá el campo heredado lo declara
    él mismo (``field.inherited`` y ``field.related_field``), porque el ORM
    construye un campo espejo en el hijo. Aquí ``_inherits`` cuelga los
    campos del padre por ``property`` (``orm/inherits.py``), así que la
    pregunta se responde mirando el mapa de delegación.

    La fuente además exige ``_has_field_access(field, 'write')`` antes de
    delegar. Aquí ese check vive en ``FieldSqlMixin``, que no todo modelo
    adopta todavía (tarea **#96**); cuando el modelo lo tenga, se aplica.
    """
    for parent_name, fk_name in getattr(model, '_inherits', {}).items():
        try:
            fk_field = model._meta.get_field(fk_name)
        except FieldDoesNotExist:
            continue
        parent_model = fk_field.related_model
        if parent_model is None:
            continue
        try:
            parent_model._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        if hasattr(model, '_has_field_access'):
            if not model()._has_field_access(fk_field, 'write'):
                continue
        return parent_model, name
    return None


#: ≙ ``NO_ACCESS`` (``odoo19c: odoo/orm/models.py:122``). Valor sentinela de
#: ``field.groups`` que prohíbe el campo a todo el mundo, elevación aparte.
NO_ACCESS = '.'


#: ≙ ``regex_read_group_spec`` (``odoo19c: odoo/orm/models.py:113``), verbatim.
#: Parte una especificación de agrupamiento en sus tres piezas: el campo, el
#: nombre de propiedad opcional tras el punto, y el agregado o granularidad
#: opcional tras los dos puntos.
regex_read_group_spec = re.compile(r'(\w+)(\.([\w\.]+))?(?::(\w+))?$')


def parse_read_group_spec(spec):
    """El triplete ``(campo, propiedad, agregado)`` de ``spec``.

    ≙ ``parse_read_group_spec`` (``odoo19c: odoo/orm/models.py:125-136``).
    Docstring de la fuente: *"Return a triplet corresponding to the given
    field/property_name/aggregate specification."*

    El patrón captura cuatro grupos y la fuente devuelve el 0, el 2 y el 3 —
    el 1 es el punto con su contenido, que sólo existe para delimitar al 2.

    La guarda **no es cosmética**: sin ella un ``spec`` que no parsea deja
    ``res_match`` en ``None`` y el acceso a ``.groups()`` revienta con
    ``AttributeError`` en vez del ``ValueError`` explicado que la fuente
    promete a quien escribió el agrupamiento.
    """
    res_match = regex_read_group_spec.match(spec)
    if not res_match:
        raise ValueError(
            f'Invalid aggregate/groupby specification {spec!r}.\n'
            '- Valid aggregate specification looks like "<field_name>:<agg>" '
            'example: "quantity:sum".\n'
            '- Valid groupby specification looks like "<no_datish_field_name>" '
            'or "<datish_field_name>:<granularity>" example: "date:month" or '
            '"<properties_field_name>.<property>:<granularity>".'
        )

    groups = res_match.groups()
    return groups[0], groups[2], groups[3]


def raise_on_invalid_object_name(name):
    """La mitad que lanza de :func:`~orm.utils.check_object_name`.

    ≙ ``raise_on_invalid_object_name`` (``odoo19c: odoo/orm/models.py:139-142``).
    El hermano devuelve un booleano y éste lo convierte en el rechazo que el
    cargador de modelos necesita: un ``_name`` inválido no puede seguir adelante
    en silencio.
    """
    if not check_object_name(name):
        msg = "The _name attribute %s is not valid." % name
        raise ValueError(msg)


class FieldSqlMixin:
    """``_field_to_sql`` y su cadena — la puerta del motor de consultas.

    ≙ los cuatro métodos que ``BaseModel`` declara en ``odoo19c:
    odoo/orm/models.py``: ``_field_to_sql`` (``:2910``),
    ``_traverse_related_sql`` (``:2889``), ``_check_field_access`` (``:3384``)
    y ``_has_field_access`` (``:3370``). Los cuatro van juntos porque el
    primero llama a los otros tres.

    **La divergencia, y es la que este archivo ya declara dos veces** (la
    sección de permisos y ``OriginMixin``): allá cuelgan de ``BaseModel``, así
    que todo modelo los tiene; aquí ``models.Model`` es el de Django y no es
    nuestro para colgarle nada, así que el mecanismo es un mixin que el modelo
    adopta. Qué modelos lo adoptan, y en qué orden, es el mismo trabajo
    abierto que la adopción de ``AccessManager`` — tarea **#96**.

    Por qué no se adjunta a ``models.Model`` como ``to_sql`` a ``Field``
    ===================================================================

    ``orm/fields.py`` sí adjunta a la clase de Django, y aquí no: la asimetría
    es deliberada. Un ``Field`` es una pieza interna del ORM que nadie hereda;
    ``models.Model`` es la base que **toda** la aplicación hereda, incluidos
    los modelos de Django (``auth``, ``contenttypes``, ``sessions``) y los de
    cualquier paquete de terceros. Colgarle cuatro métodos con guion bajo
    cambia la superficie de clases que no son del proyecto — que es
    exactamente la colisión que la tarea **#98** barre. El mixin da lo mismo
    donde se pide y nada donde no.

    Qué resuelve, en una línea
    ==========================

    Una expresión de campo —``'name'`` o ``'properties.color'``— contra un
    alias de tabla, devuelta como ``SQL`` y con la lectura del campo
    comprobada. Es el punto por el que pasa todo lo que compone SQL crudo: el
    ORDER BY de un ``_order_field_to_sql``, la condición de un dominio, la
    exportación de un campo sin columna.
    """

    #: Los campos del modelo por nombre — ≙ ``BaseModel._fields``.
    #:
    #: Allá es el registro que el ORM construye al cargar la clase; aquí lo
    #: provee ``_meta``, que es el registro equivalente de Django. Entran
    #: **todos**, como allá: el mapa es el registro del modelo, no el de sus
    #: columnas.
    #:
    #: > **Ensanchado (tarea #215, H-API-953).** Hasta hoy filtraba por
    #: > ``concrete``, y ese filtro era un contrato **más estrecho** que el de
    #: > la fuente sin que nadie hubiera comparado los dos alcances. Lo
    #: > destapó ``setup_related`` (``odoo19c: :604``), que recorre
    #: > ``model._fields[name]`` por una cadena punteada que puede atravesar
    #: > un ``One2many`` — que no es concreto. Con el mapa estrecho esa cadena
    #: > no se puede recorrer.
    #: >
    #: > Medido sobre ``ResPartner``: **107** campos en total, **66**
    #: > concretos, **41** no. El filtro escondía el 38 %.
    #: >
    #: > Los cinco consumidores se midieron uno a uno antes de ensanchar.
    #: > Cuatro filtran por su cuenta —dos exigen ``ForeignKey``, dos exigen
    #: > ``Properties``— así que el filtro no era suyo. El quinto,
    #: > ``_field_to_sql``, SÍ lo usaba: un nombre no concreto quedaba fuera
    #: > del mapa y producía su ``ValueError`` limpio. Ese rechazo se conserva
    #: > **en su sitio**, que es donde pertenece — quien compone SQL es quien
    #: > sabe qué puede convertir.
    #:
    #: > **Ensanchado otra vez (tarea #301, :ref:`h-api-1025`).** La ceguera
    #: > que la versión anterior declaraba abajo —*"ciega al ``NonStored``"*—
    #: > no era una nota al pie: era la mitad que faltaba. El campo sin
    #: > columna **es un campo del modelo** en la fuente, y dejarlo fuera
    #: > volvía a hacer el mapa más estrecho que allá, sólo que por otro eje.
    #: > Lo destapó ``_address_fields()``, que desde ``base_address_extended``
    #: > devuelve ``city_id`` —sin columna aquí, DEC-SALE-01— y hacía reventar
    #: > a ``_convert_fields_to_values`` sobre 35 casos de
    #: > ``tests/integration/base``.
    #: >
    #: > Los seis consumidores se re-midieron uno a uno antes de ensanchar, y
    #: > ninguno cambia de conducta: cuatro filtran por ``Properties`` o
    #: > ``ForeignKey``, uno lee ``ondelete`` con ``getattr`` y el sexto
    #: > —``_field_to_sql``— exige ``concrete``, que un ``NonStored`` no
    #: > declara. Ahí el nombre pasa de dar ``None`` a dar el descriptor, y el
    #: > mismo ``ValueError`` sale por la misma rama.
    #:
    #: *Métrica:* ``_meta.get_fields()`` unido a los descriptores
    #: :class:`~orm.fields_nonstored.NonStored` que el MRO de la clase
    #: declara.
    #: *Ciega a:* un campo de la fuente que aquí no se declare ni como campo
    #: de Django ni como ``NonStored`` — una ``property`` pelada, por ejemplo.
    #: Esa forma existe en el árbol y su barrido es la tarea **#302**.
    #:
    #: **Es un descriptor y no una ``property`` (tarea #342).** La fuente
    #: declara ``_fields`` en la clase de registro, asi que ``Model._fields``
    #: y ``record._fields`` devuelven el mismo mapa; ``check_indexes``
    #: (``odoo19c: odoo/orm/registry.py:813``) lo lee por la clase. Una
    #: ``property`` sobre la clase devuelve el objeto descriptor, no el mapa,
    #: y ese hueco lo tapaba :func:`~orm.utils.model_field_registry` llamada a
    #: mano en once sitios. El protocolo de descriptor de CPython ya distingue
    #: los dos accesos, asi que el mecanismo no se trae de fuera: se usa.
    _fields = FieldRegistryDescriptor()

    def _has_field_access(self, field, operation) -> bool:
        """Si el usuario puede leer o escribir este campo.

        ≙ ``_has_field_access`` (``odoo19c: odoo/orm/models.py:3370-3382``).
        Un campo sin ``groups`` es accesible; bajo elevación, también.
        ``NO_ACCESS`` lo prohíbe siempre.

        ``field.groups`` se lee con ``getattr``: los campos de Django no lo
        declaran, así que hoy la respuesta es ``True`` para todos salvo que
        alguien lo asigne. No es una laxitud inventada — es el mismo
        ``if not field.groups`` de la fuente, que allá también deja pasar todo
        campo que no declare grupos.
        """
        groups = getattr(field, 'groups', None)
        if not groups or is_su():
            return True
        if groups == NO_ACCESS:
            return False
        user = get_current_user()
        return user is not None and user.has_groups(groups)

    def _check_field_access(self, field, operation) -> None:
        """Levanta ``AccessError`` si el usuario no puede — ≙ ``:3384-3424``.

        Cuatro piezas, como la fuente: campo, descripción del modelo, operación
        y —sólo para quien pueda verlo— **qué grupos lo abrirían**. Esa cuarta
        es la que convierte un 403 opaco en accionable, y va condicionada a
        ``base.group_no_one`` igual que allá: el nombre de un grupo que
        concede acceso a un campo es en sí mismo información.

        Las tres ramas del tramo de grupos son las de la fuente (``:3411-3418``)
        y no son intercambiables: ``NO_ACCESS`` significa *prohibido siempre* y
        no *«pide el grupo»*; un campo sin ``groups`` que aun así se denegó
        sólo puede deberse a una regla a medida.
        """
        if self._has_field_access(field, operation):
            return

        _logger.info(
            'Access Denied by ACLs for operation: %s, uid: %s, model: %s, field: %s',
            operation, get_current_uid(), self._meta.label, field.name)

        description = self._model_description()
        message = (
            f'No tiene permisos suficientes para acceder al campo '
            f'"{field.name}" en {description} '
            f'({self._meta.label}). Contacte a su administrador.'
            f'\n\nOperación: {operation}'
        )
        user = get_current_user()
        if user is not None and user.has_group('base.group_no_one'):
            message += (f'\nUsuario: {get_current_uid()}'
                        f'\nGrupos: {self._allowed_groups_message(field)}')
        raise AccessError(message)

    def _model_description(self):
        """El nombre informal del modelo — ≙ ``self.env['ir.model']._get(name).name``.

        La fuente lo lee de ``ir.model`` y cae al nombre técnico si no hay
        fila; aquí igual, con el ``verbose_name`` de Django como último
        respaldo — que es lo que este árbol declara siempre y ``ir.model`` no
        necesariamente tiene sembrado.
        """
        IrModel = apps.get_model('base', 'IrModel')
        return (IrModel.objects.filter(model=self._meta.label)
                .values_list('name', flat=True).first()
                or self._meta.verbose_name or self._meta.label)

    @staticmethod
    def _allowed_groups_message(field):
        """El tramo *"Groups: …"* del error de campo — ≙ ``:3411-3418``."""
        groups = getattr(field, 'groups', None)
        if groups == NO_ACCESS:
            return 'prohibido siempre'
        if not groups:
            return 'reglas de acceso de campo a medida'
        # ≙ ``[self.env.ref(g) for g in field.groups.split(',')]`` ordenado
        # por id: el identificador externo se resuelve por ``ir.model.data``,
        # que es el mismo canal que ``has_group``. Un xmlid que no resuelve se
        # deja verbatim en vez de desaparecer — si el campo lo declara, quien
        # lea el error necesita verlo aunque el grupo no esté sembrado.
        IrModelData = apps.get_model('base', 'IrModelData')
        ResGroups = apps.get_model('base', 'ResGroups')
        resueltos = []
        for xmlid in (g.strip() for g in groups.split(',')):
            group = IrModelData.ref(xmlid, raise_if_not_found=False)
            if isinstance(group, ResGroups):
                resueltos.append((group.pk, str(group)))
            else:
                resueltos.append((None, xmlid))
        resueltos.sort(key=lambda par: (par[0] is None, par[0]))
        return 'permitido a los grupos %s' % ', '.join(
            repr(name) for _pk, name in resueltos)

    def _traverse_related_sql(self, alias, field, query):
        """Recorre el campo delegado y añade a ``query`` los JOIN que hagan falta.

        ≙ ``_traverse_related_sql`` (``odoo19c: odoo/orm/models.py:2889-2908``).

        :returns: la terna ``(model, field, alias)``, donde ``field`` es el
            último campo de la secuencia, ``model`` el modelo de ese campo y
            ``alias`` el alias de su tabla.

        El ``related`` de la fuente es una ruta con puntos —``partner_id.name``—
        y aquí el mecanismo equivalente es ``orm/inherits.py``: ``_inherits``
        instala la delegación y el camino es un solo salto, el de su FK. Por
        eso el bucle recorre ``field.related.split('.')`` igual que allá: la
        ruta de un salto es el caso que hoy existe, y la de varios funciona sin
        tocar nada el día que un campo la declare.
        """
        # `related`/`store` se leen con `getattr`: son atributos de la clase
        # `Field` de la referencia, y un campo de Django no los declara. Sin
        # el `getattr` la aserción no rechaza — revienta con AttributeError,
        # que no es lo mismo y esconde el motivo.
        assert (getattr(field, 'related', None)
                and not getattr(field, 'store', True))
        *path_fnames, last_fname = field.related.split('.')
        model = type(self)
        for path_fname in path_fnames:
            path_field = model._fields[path_fname]
            if not isinstance(path_field, ForeignKey):
                raise ValueError(
                    f'Cannot convert {field} (related={field.related}) to SQL '
                    f'because {path_fname} is not a Many2one')
            model, alias = path_field.join(model, alias, query)

        return model, model._fields[last_fname], alias

    def _field_to_sql(self, alias, field_expr, query=None):
        """El valor del campo dado desde el alias dado, como ``SQL``.

        ≙ ``_field_to_sql`` (``odoo19c: odoo/orm/models.py:2910-2932``).
        Comprueba además que el campo sea legible.

        El objeto ``query`` es necesario para los campos delegados y los
        Many2one: es donde se añaden los JOIN.
        """
        fname, property_name = parse_field_expr(field_expr)
        field = self._fields.get(fname)
        if not field or not getattr(field, 'concrete', False):
            # El rechazo del campo sin columna vive AQUÍ y no en ``_fields``:
            # quien compone SQL es quien sabe qué puede convertir. Antes lo
            # hacía el mapa, filtrando por ``concrete``, y con eso el registro
            # del modelo quedaba más estrecho que el de la fuente para todos
            # sus consumidores — no sólo para éste (tarea #215).
            raise ValueError(
                f"Invalid field {fname!r} on model {self._meta.label!r}")

        if getattr(field, 'related', None) and not getattr(field, 'store', True):
            model, field, alias = self._traverse_related_sql(alias, field, query)
            related_expr = (field.name if not property_name
                            else f"{field.name}.{property_name}")
            return model._field_to_sql(alias, related_expr, query)

        self._check_field_access(field, 'read')

        sql = field.to_sql(self, alias)
        if property_name:
            sql = field.property_to_sql(sql, property_name, self, alias, query)
        return sql


class RecordLoaderMixin(FieldSqlMixin):
    """``_load_records`` y su cadena — el lado ORM del cargador de datos.

    ≙ los cuatro métodos que ``BaseModel`` declara en ``odoo19c:
    odoo/orm/models.py``: ``_clean_properties`` (``:5054``),
    ``_load_records_write`` (``:5085``), ``_load_records_create`` (``:5102``) y
    ``_load_records`` (``:5108``). Van juntos porque el último llama a los
    otros tres.

    **La divergencia es de VÍA, no de alcance.** Allá cuelgan de ``BaseModel``,
    así que todo modelo los tiene; aquí ``models.Model`` es el de Django y no
    es nuestro para colgarle nada. La universalidad se recupera adoptando este
    mixin en ``addons.base.models.timestamped_mixin.TimeStampedModel``, que es
    la base común del proyecto ("usar en TODOS los modelos concretos", dice su
    propio docstring) — así todo modelo concreto tiene ``_load_records`` sin
    declararlo, igual que en la fuente.

    No es lo mismo que ``FieldSqlMixin`` ni que ``AccessManager``, que siguen
    adoptándose modelo a modelo (tarea **#96**): aquéllos cambian **cómo se
    consulta** un modelo concreto, y el cargador de datos no admite esa
    gradualidad — un archivo de datos de la referencia nombra veinticuatro
    modelos distintos sólo en ``base``, y el cargador falla con
    ``AttributeError`` en el primero que no lo declare.

    Qué resuelve, en una línea
    ==========================

    Un archivo de datos declara registros con su identificador externo; este
    mixin decide, por cada uno, si **crear**, **actualizar** o **saltar**, y
    deja el identificador asignado. Es lo que ``tools/convert.py`` llama al
    leer un ``<record>``, y por tanto lo que estaba bloqueando a
    ``ResPartner._load_records_create``.

    Las tres decisiones, y de dónde salen
    =====================================

    La partición de la fuente se porta entera y en su orden:

    - **Sin ``xml_id``**: con ``values['id']`` se actualiza ese registro; sin
      él, se crea — salvo que sea una actualización de módulo, donde no hay
      forma de saber a qué registro se refiere y se rechaza.
    - **Con ``xml_id`` sin fila**: se crea.
    - **Con ``xml_id`` y fila viva** (``r_id``): se actualiza, salvo que sea
      actualización de módulo **y** la fila lleve ``noupdate`` — la bandera que
      protege el dato que alguien tocó a mano.
    - **Con ``xml_id`` y fila huérfana** (el registro ya no está): la fila se
      borra y el registro se crea de nuevo.

    El modelo de la fila tiene que coincidir con el de este mixin; si no, se
    rechaza con el mensaje de la fuente. Es la guarda que impide que un
    ``xml_id`` reutilizado entre módulos apunte a la tabla equivocada.

    DIVERGENCIA DE FORMA, declarada: la fuente es método de recordset y aquí de
    clase
    =====================================================================

    ``_load_records`` y ``_load_records_create`` son **classmethods**: allá
    ``self`` es un recordset vacío que sólo aporta el modelo (``self.browse()``
    en la primera línea), y aquí ese papel lo cumple la clase. ``self.create``
    pasa a ser ``cls.objects.create``, ``self.browse(id)`` a un ``filter(pk=)``,
    y el ``original_self.concat(...)`` del final a la lista de registros en el
    orden de ``data_list``, que es lo que la fuente promete devolver.

    ``_load_records_write`` y ``_clean_properties`` sí son de instancia: la
    fuente empieza con ``self.ensure_one()``, es decir, opera sobre **un**
    registro.

    Por qué hereda de ``FieldSqlMixin``
    ===================================

    Los dos métodos de instancia recorren ``self._fields``, que allá es un
    atributo de ``BaseModel`` y aquí lo porta ``FieldSqlMixin``. Heredarlo
    reproduce el hecho de la fuente —los ocho símbolos cuelgan del **mismo**
    objeto— en vez de pedirle al modelo que adopte dos mixins y recuerde el
    orden. Un modelo que adopte éste obtiene los dos, que es lo que allá
    obtiene por herencia de ``BaseModel``.
    """

    # -- Propiedades ---------------------------------------------------------

    def get_property_definition(self, full_name):
        """≙ ``get_property_definition`` (``odoo19c: odoo/orm/models.py:3043``).

        Docstring de la fuente, verbatim: *"Return the definition of the given
        property"*, con ``full_name`` = *"Name of the field / property (e.g.
        'property.integer')"*.

        Su consumidor es ``domains._optimize_properties_date_datetime``, que
        necesita saber de qué **tipo** es una propiedad para convertir el valor
        de la condición antes de compilarla: sin el tipo no puede distinguir
        una propiedad de fecha de una de texto, y la comparación se haría
        contra la cadena cruda.

        **La divergencia de mecanismo, declarada.** La fuente arma un ``SELECT``
        con ``jsonb_array_elements`` sobre la tabla del registro de definición y
        filtra en SQL por ``definition->>'name'`` (``:3060-3067``). Aquí la
        lista ya la resuelve ``Properties._get_properties_definition(record)``
        —el mismo camino que ``_clean_properties`` usa—, así que la selección
        por nombre se hace sobre esa lista en vez de emitir una segunda
        consulta. El resultado es el mismo: la definición que coincide, o
        ``{}`` cuando no hay ninguna, que es el ``LIMIT 1`` sin filas de allá.

        Se conserva de la fuente: la comprobación de lectura sobre el recordset
        vacío, el ``ValueError`` cuando el campo no existe, y la validación del
        nombre de la propiedad con
        :func:`~orm.fields_properties.check_property_field_value_name` **antes**
        de interpolarlo en el SQL.

        **Es independiente del registro, como la fuente.** Su primera versión
        leía la definición con ``field._get_properties_definition(self)`` —el
        camino que usa :meth:`_clean_properties`— y eso NO es lo mismo: aquel
        camino resuelve el contenedor **de un registro concreto**, y aquí no
        hay ninguno. El único consumidor es
        ``domains._optimize_properties_date_datetime``, que llama sobre el
        **modelo**: con la versión por registro no habría podido resolver nada.
        Es el sub-patrón D de ``metrica-decide-la-conclusion.md`` aplicado a un
        mecanismo — construido, sin control que lo midiera contra su
        consumidor.

        **La divergencia de mecanismo, declarada:** allá el recordset vacío
        llega por ``self.browse()``; aquí se construye el ``AccessQuerySet``
        explícitamente, porque su adopción por modelo aún está en curso
        (tarea #96) y el manager por omisión puede no traerlo. La comprobación
        se hace igual — no se omite por no estar adoptada.
        """
        AccessQuerySet(model=type(self)).none().check_access('read')
        field_name, property_name = parse_field_expr(full_name)
        field = self._fields.get(field_name)
        if not field:
            raise ValueError(
                f'Campo inválido {field_name!r} en el modelo '
                f'{getattr(self, "_name", type(self).__name__)!r}')
        check_property_field_value_name(property_name)

        if not isinstance(field, Properties):
            return {}
        target_model = self._meta.get_field(field.definition_record).related_model
        column = target_model._meta.get_field(
            field.definition_record_field).column
        result = env().execute_query_dict(SQL(
            """ SELECT definition
                  FROM %(table)s, jsonb_array_elements(%(field)s) definition
                 WHERE %(field)s IS NOT NULL AND definition->>'name' = %(name)s
                 LIMIT 1 """,
            table=SQL.identifier(target_model._meta.db_table),
            field=SQL.identifier(column),
            name=property_name,
        ))
        return result[0]['definition'] if result else {}

    def _clean_properties(self):
        """≙ ``_clean_properties`` (``odoo19c: odoo/orm/models.py:5054-5068``).

        «Remove all properties of ``self`` that are no longer in the related
        definition.»

        El discriminador de tipo es ``isinstance(field, Properties)`` y no
        ``field.type != 'properties'`` — la forma que este árbol fijó para el
        mismo problema en ``fields_textual.Html`` (H-API-700); ver el docstring
        de ``orm/fields_properties.Properties``.

        La fuente itera ``for record in self`` porque su ``self`` es un
        recordset; aquí es un registro, así que el bucle exterior desaparece y
        queda el cuerpo. Escribe con ``save(update_fields=...)`` para no tocar
        columnas que no cambiaron.
        """
        changed = []
        for fname, field in self._fields.items():
            if not isinstance(field, Properties):
                continue
            old_value = getattr(self, fname, None)
            if not old_value:
                continue

            definitions = field._get_properties_definition(self)
            if not definitions:
                continue
            all_names = {definition['name'] for definition in definitions}
            new_values = {name: value for name, value in old_value.items()
                          if name in all_names}
            if len(new_values) != len(old_value):
                setattr(self, fname, new_values)
                changed.append(fname)
        if changed:
            self.save(update_fields=changed)

    # -- Enganches de extensión de la definición de propiedades --------------
    #
    # ≙ los cuatro que ``BaseModel`` declara junto a ``_clean_properties``
    # (``odoo19c: odoo/orm/models.py:5070-5084``). Los cuatro cuerpos son los
    # de la fuente: existen para que un addon los sobreescriba, no para hacer
    # nada por sí mismos. Su llamador es ``PropertiesDefinition`` en
    # ``orm/fields_properties.py``, que allá los pide a ``env["base"]`` y aquí
    # al registro — ver su docstring.

    def _validate_properties_definition(self, properties_definition, field):
        """Allow to validate additional properties attributes."""

    def _additional_allowed_keys_properties_definition(self):
        """Allow to add more allowed key for properties."""
        return ()

    def _convert_to_cache_properties_definition(self, value):
        """Allow to patch `convert_to_cache` of the properties definition."""
        return value

    def _convert_to_column_properties_definition(self, value):
        """Allow to patch `convert_to_column` of the properties definition."""
        return value

    # -- Escritura y creación ------------------------------------------------

    @classmethod
    def _load_records_coerce_vals(cls, values):
        """El id de un ``Many2one`` entra por su columna, no por el atributo.

        **Divergencia de stack, no de mecanismo.** En la referencia un
        ``Many2one`` se escribe con el id y ya: ``{'parent_id': 42}`` es lo que
        el archivo de datos produce y lo que ``create``/``write`` aceptan.
        Django separa las dos caras de una FK — ``parent`` quiere la
        **instancia** y ``parent_id`` (su ``attname``) quiere la **clave**—, y
        asignar un entero al primero levanta ``ValueError: Cannot assign
        "42": "ResPartner.parent" must be a "ResPartner" instance``.

        Aquí se traduce el nombre del campo a su ``attname`` cuando el valor no
        es ya una instancia. El sitio es el mixin del cargador y no
        ``tools/convert.py`` porque el que decide es el ORM: es la frontera
        ``create``/``write``, la misma que en la fuente acepta el id.

        Un nombre que el modelo no declara se deja pasar tal cual — quien
        levante el error es Django, con su mensaje, y no un ``KeyError`` de
        aquí que oculte cuál era el campo.
        """
        coerced = {}
        for fname, value in values.items():
            try:
                field = cls._meta.get_field(fname)
            except FieldDoesNotExist:
                coerced[fname] = value
                continue
            attname = getattr(field, 'attname', None)
            if (field.is_relation and field.many_to_one and attname
                    and attname != fname and not isinstance(value, Model)):
                coerced[attname] = value
            else:
                coerced[fname] = value
        return coerced

    def _load_records_write(self, values):
        """≙ ``_load_records_write`` (``odoo19c: :5085-5100``).

        Escribe los valores de un registro que ya existe. Los campos de
        propiedades se **difieren**: se sacan del lote, se escribe el resto, y
        sólo entonces se escriben mezclados con lo que ya había. El comentario
        de la fuente dice por qué —*"Deferred the write to avoid using the old
        definition if it changed"*—: si en el mismo lote viene una definición
        nueva, mezclar antes usaría la vieja.

        Tras escribirlos se limpia, con la razón de la fuente verbatim:
        *"Because we don't know which properties was linked to which
        definition, we can know clean properties"*.
        """
        to_write = {}  # Deferred the write to avoid using the old definition if it changed
        for fname in list(values):
            field = self._fields.get(fname)
            if not isinstance(field, Properties):
                continue
            field_converter = field.convert_to_cache
            to_write[fname] = dict(
                getattr(self, fname, None) or {},
                **(field_converter(values.pop(fname), self, validate=False) or {}))

        self.write(values)
        if to_write:
            self.write(to_write)
            # Because we don't know which properties was linked to which
            # definition, we can know clean properties (note that it is not
            # mandatory, we can wait that client change the record in a Form
            # view)
            self._clean_properties()

    def write(self, values):
        """Escribe los valores y guarda — el ``write`` que la fuente supone.

        La referencia lo tiene en ``BaseModel``; aquí ``models.Model`` es el de
        Django, así que el mixin lo aporta para el modelo que lo adopte. Un
        modelo que ya declare su propio ``write`` —``ir_config_parameter``,
        ``properties_base_definition``— gana el suyo por MRO y éste no
        interfiere.

        La clave primaria se **descarta**, y es lo que la fuente hace de hecho:
        ``_load_records`` le pasa ``data['values']`` entero, ``'id'`` incluido,
        porque ese ``id`` es lo que acaba de **seleccionar** el registro.
        Reescribirlo es un no-op allá y aquí un ``ValueError`` de Django, así
        que se filtra en un solo sitio en vez de en cada llamador.
        """
        pk_name = self._meta.pk.name
        values = {fname: value for fname, value in values.items()
                  if fname not in (pk_name, 'id')}
        if not values:
            return self
        determine_inverses = self._group_written_inverses(values)
        values, relational = self._load_records_split_relational(values)
        values = self._load_records_coerce_vals(values)
        if values:
            for fname, value in values.items():
                setattr(self, fname, value)
            self.save(update_fields=list(values))
        if relational:
            self._load_records_apply_relational(relational)
        for fields in determine_inverses.values():
            fields[0].determine_inverse(self)
        return self

    def _group_written_inverses(self, values):
        """Los campos escritos que declaran inverso, agrupados POR METODO.

        ≙ ``determine_inverses = defaultdict(list)  # {inverse: fields}``
        (``odoo19c: odoo/orm/models.py:4399``), poblado en ``:4416`` con
        ``determine_inverses[field.inverse].append(field)``.

        La agrupacion no es cosmetica: la fuente llama al inverso **una vez por
        grupo** —``fields[0].determine_inverse(real_recs)`` (``:4493``)— porque
        un mismo metodo puede invertir varios campos a la vez y llamarlo N veces
        repetiria su efecto. Escribir ``email_from`` y ``phone`` en la misma
        llamada da dos grupos y dos invocaciones; si ambos declararan el mismo
        metodo, daria una.

        Se calcula **antes** de partir los valores en columna y relacion, porque
        la fuente recorre ``vals`` entero: un campo relacional con inverso
        cuenta igual que uno con columna.

        DIVERGENCIA DE MECANISMO declarada: la fuente lee ``self._fields``; aqui
        el registro equivalente es :func:`~orm.utils.model_field_registry`, que
        ya cubre el campo con columna y el que no la tiene. Y donde ella lanza
        ``ValueError`` ante un nombre desconocido, aqui se ignora: ``write`` de
        este arbol acepta nombres que ``save``/``_load_records_apply_relational``
        resuelven por otras vias, y adelantar ese rechazo cambiaria el contrato
        de un metodo que no es el de esta tarea.
        """
        fields_of = model_field_registry(type(self))
        determine_inverses = collections.defaultdict(list)
        for fname in values:
            field = fields_of.get(fname)
            if field is not None and getattr(field, 'inverse', None):
                determine_inverses[field.inverse].append(field)
        return determine_inverses

    @classmethod
    def _write_rows_skipping_save(cls, queryset, values):
        """Escribe ``values`` sobre las filas de ``queryset`` sin pasar por
        ``save()`` — ≙ el ``super().write(vals)`` de la fuente.

        Por qué existe, y por qué no basta ``QuerySet.update()``
        =======================================================

        La fuente usa ``super().write(...)`` cuando quiere escribir **sin**
        re-entrar en el ``write`` sobrecargado que volvería a sincronizar
        (``odoo19c: res_partner.py:677-683`` es el caso de manual). Su análogo
        en este stack es ``QuerySet.update()``: no invoca ``save()`` ni emite
        señales.

        Pero ``update()`` compone un ``UPDATE`` y por tanto **sólo sabe de
        columnas**: un campo sin columna —el ``store=False`` de la fuente, aquí
        :class:`~orm.fields_nonstored.NonStored`— le levanta
        ``FieldDoesNotExist``. Allá no hay tal frontera: ``write`` acepta todo
        campo del modelo, tenga columna o no. Sin esta separación, cualquier
        addon que añada un campo sin columna a una lista que luego se escribe
        en bloque revienta a su consumidor — que es lo que ``city_id`` de
        ``base_address_extended`` hizo sobre 35 casos (:ref:`h-api-1025`).

        El reparto es por registro, no por SQL: el descriptor de un campo sin
        columna sabe dónde vive su valor, y escribirlo por ``setattr`` es
        llamarlo. Eso no re-entra en ``save()`` del modelo que se está
        escribiendo, así que la garantía de la fuente —no volver a
        sincronizar— se conserva.
        """
        without_column = non_stored_fields(cls)
        columns = {name: value for name, value in values.items()
                   if name not in without_column}
        projected = {name: value for name, value in values.items()
                     if name in without_column}
        if columns:
            queryset.update(**columns)
        if projected:
            for record in queryset:
                for name, value in projected.items():
                    setattr(record, name, value)

    @classmethod
    def _create_row_from_values(cls, values, using=DEFAULT_DB_ALIAS):
        """Crea la fila aceptando **todo** campo del modelo — ≙ ``create(vals)``.

        Es la cara de alta de la misma frontera que
        :meth:`_write_rows_skipping_save` cubre en la escritura. El
        ``Model.__init__`` de Django rechaza con ``TypeError`` cualquier
        argumento que no sea una columna suya, y allá ``create`` acepta todo
        campo declarado — un ``store=False`` incluido. Sin esta separación,
        pasarle a ``objects.create`` un diccionario derivado de una lista de
        campos —``_address_fields()``, por ejemplo— revienta en cuanto un addon
        mete en esa lista un campo que aquí no tiene columna
        (:ref:`h-api-1025`).

        El orden importa y es el de la fuente: la fila se crea primero con lo
        que tiene columna, y el campo sin columna se escribe **después**, con
        la fila ya real. Su descriptor puede necesitar la clave para colgar de
        ella lo que respalda su valor, igual que un ``One2many`` necesita el
        padre guardado.
        """
        without_column = non_stored_fields(cls)
        columns = {name: value for name, value in values.items()
                   if name not in without_column}
        projected = {name: value for name, value in values.items()
                     if name in without_column}
        record = cls.objects.using(using).create(**columns)
        for name, value in projected.items():
            setattr(record, name, value)
        return record

    @classmethod
    def _load_records_split_relational(cls, values):
        """Separa lo que se escribe en la fila de lo que se escribe **después**.

        Es la contraparte de la divergencia que ``ir_fields`` declara: la
        fuente devuelve ``Command`` diferidos y su ``write`` los interpreta; el
        ``Command`` de este árbol es ejecutivo (:ref:`h-api-589`, tarea
        **#345**), así que el valor viaja en
        :class:`~orm.commands.ManyToManySet`,
        :class:`~orm.commands.ManyToManyLink` y
        :class:`~orm.commands.One2manyChild`, y es aquí donde se aparta.

        El aparte no es una comodidad: Django **exige** que la fila exista
        antes de tocar una relación de muchos (``Direct assignment to the
        forward side of a many-to-many set is prohibited``). Lo mismo vale para
        el hijo de un ``One2many``, que necesita la clave del padre.
        """
        scalar, relational = {}, {}
        for fname, value in values.items():
            if isinstance(value, (ManyToManySet, ManyToManyLink)):
                relational[fname] = value
            elif (isinstance(value, list) and value
                    and all(isinstance(item, One2manyChild) for item in value)):
                relational[fname] = value
            else:
                scalar[fname] = value
        return scalar, relational

    def _load_records_apply_relational(self, relational):
        """Aplica lo que la fila ya existente admite: el conjunto y los hijos.

        Los tres verbos son los de ``Command`` en la fuente, con el del ORM de
        este lado: ``set`` reemplaza el conjunto, ``add`` lo amplía, y un hijo
        con id se **actualiza** mientras que uno sin id se **crea** apuntando al
        padre.
        """
        for fname, value in relational.items():
            manager = getattr(self, fname)
            if isinstance(value, ManyToManySet):
                manager.set([id for id in value if id])
            elif isinstance(value, ManyToManyLink):
                manager.add(*[id for id in value if id])
            else:
                for child in value:
                    if child.id:
                        existing = manager.get(pk=child.id)
                        existing.write(child.values)
                    else:
                        manager.create(**manager.model._load_records_coerce_vals(
                            child.values))

    @classmethod
    def _load_records_create(cls, vals_list, using=DEFAULT_DB_ALIAS):
        """≙ ``_load_records_create`` (``odoo19c: :5102-5106``).

        Crea los registros y, si el modelo tiene algún campo de propiedades,
        los limpia. La guarda ``any(...)`` de la fuente se conserva: recorrer
        los campos una vez es más barato que llamar a ``_clean_properties`` por
        registro cuando el modelo no tiene ninguno.

        Es el símbolo que ``ResPartner._load_records_create`` sobreescribe
        (``odoo19c: res_partner.py:988``): el enganche que el cargador ofrece
        para que un modelo intervenga en la creación desde datos.
        """
        records = []
        for vals in vals_list:
            scalar, relational = cls._load_records_split_relational(vals)
            record = cls.objects.using(using).create(
                **cls._load_records_coerce_vals(scalar))
            if relational:
                record._load_records_apply_relational(relational)
            records.append(record)
        if any(isinstance(field, Properties)
               for field in cls._meta.get_fields()):
            for record in records:
                record._clean_properties()
        return records

    # -- El cargador de archivos ---------------------------------------------

    @classmethod
    def _sql_error_to_message(cls, exc):
        """≙ ``_sql_error_to_message`` (``odoo19c: :3270-3285``).

        «Convert a database exception to a user error message depending on the
        model.»

        La restricción violada tiene un mensaje declarado en
        ``ir.model.constraint``; si lo hay, ése es el que ve quien importa, y
        no el texto de PostgreSQL. Sin él, se cae al mensaje genérico.
        """
        IrModelConstraint = apps.get_model('base', 'IrModelConstraint')
        constraint_name = getattr(getattr(exc, 'diag', None),
                                  'constraint_name', None)
        if constraint_name:
            row = IrModelConstraint.objects.filter(
                name=constraint_name).values_list('message', flat=True).first()
            if row:
                return row
        return str(exc)

    @classmethod
    def _extract_records(cls, field_paths, data, log=lambda a: None,
                         limit=float('inf')):
        """≙ ``_extract_records`` (``odoo19c: :1075-1195``).

        «Generates record dicts from the data sequence.»

        Recorre la matriz **por filas** y devuelve un dict por registro. Lo que
        hace no trivial este método es que un registro puede ocupar **varias
        filas**: las que siguen a la suya con valores sólo en columnas
        ``One2many`` le pertenecen. Esa es la regla que ``only_o2m_values``
        codifica y por la que el avance del índice es ``len(record_span)`` y no
        uno.

        Las tres claves especiales de la fuente se conservan: ``None`` es la
        etiqueta visible del registro, ``id`` su identificador externo y
        ``.id`` su id de base.
        """
        fields = {field.name: field for field in cls._meta.get_fields()
                  if hasattr(field, 'name')}

        def is_one2many(fname):
            field = fields.get(fname)
            return field is not None and getattr(field, 'one_to_many', False)

        get_o2m_values = itemgetter_tuple([
            index
            for index, fnames in enumerate(field_paths)
            if is_one2many(fnames[0])
        ])
        get_nono2m_values = itemgetter_tuple([
            index
            for index, fnames in enumerate(field_paths)
            if not is_one2many(fnames[0])
        ])

        # Checks if the provided row has any non-empty one2many fields
        def only_o2m_values(row):
            return any(get_o2m_values(row)) and not any(get_nono2m_values(row))

        for fname, *__ in field_paths:
            if not fname or '.' in fname:
                continue
            if fname not in fields and fname not in REFERENCING_FIELD_NAMES:
                raise ValueError(f'Invalid field name {fname!r}')

        # m2o fields can't be on multiple lines so don't take it in account
        # for only_o2m_values rows filter, but special-case it later on to
        # be handled with relational fields (as it can have subfields).
        def is_relational(fname):
            field = fields.get(fname)
            return field is not None and field.is_relation

        index = 0
        while index < len(data) and index < limit:
            row = data[index]

            # copy non-relational fields to record dict
            record = {
                fnames[0]: value
                for fnames, value in zip(field_paths, row)
                if not is_relational(fnames[0])
            }

            # Get all following rows which have relational values attached to
            # the current record (no non-relational values)
            record_span = itertools.takewhile(
                only_o2m_values,
                (data[j] for j in range(index + 1, len(data))),
            )
            # stitch record row back on for relational fields
            record_span = list(itertools.chain([row], record_span))

            for relfield, *__ in field_paths:
                if not is_relational(relfield):
                    continue

                comodel = fields[relfield].related_model

                # get only cells for this sub-field, should be strictly
                # non-empty, field path [None] is for display_name field
                indices, subfields = zip(*(
                    (position, fnames[1:] or [None])
                    for position, fnames in enumerate(field_paths)
                    if fnames[0] == relfield))

                # return all rows which have at least one value for the
                # subfields of relfield
                relfield_data = [it for it
                                 in map(itemgetter_tuple(indices), record_span)
                                 if any(it)]
                record[relfield] = [
                    subrecord
                    for subrecord, _subinfo
                    in comodel._extract_records(subfields, relfield_data,
                                                log=log)
                ]

            yield record, {'rows': {
                'from': index,
                'to': index + len(record_span) - 1,
            }}
            index += len(record_span)

    @classmethod
    def _convert_records(cls, records, *, log=lambda a: None, savepoint):
        """≙ ``_convert_records`` (``odoo19c: :1198-1251``).

        «Converts records from the source iterable (recursive dicts of strings)
        into forms which can be written to the database.»

        :returns: una tupla ``(dbid, xid, convertido, info)`` por registro.

        El ``.id`` se valida **contra la base** antes de aceptarlo: la fuente
        registra un error y lo descarta si el registro no existe, en vez de
        dejar que el fallo salga como violación de clave ajena tres pasos más
        tarde.
        """
        converter_cls = registry.model_by_name('ir.fields.converter')
        field_names = {field.name: str(getattr(field, 'verbose_name', field.name))
                       for field in cls._meta.get_fields()
                       if hasattr(field, 'name')}

        convert = converter_cls.for_model(cls, savepoint=savepoint)

        def _log(base, record, field, exception):
            type = 'warning' if isinstance(exception, Warning) else 'error'
            # logs the logical (not human-readable) field name for automated
            # processing of response, but injects human readable in message
            field_name = field_names.get(field, field)
            exc_vals = dict(base, record=record, field=field_name)
            record = dict(base, type=type, record=record, field=field,
                          message=str(exception.args[0]) % exc_vals)
            if len(exception.args) > 1:
                info = {}
                if exception.args[1] and isinstance(exception.args[1], dict):
                    info = exception.args[1]
                # ensure field_name is added to the exception. Used in import to
                # concatenate multiple errors in the same block
                info['field_name'] = field_name
                record.update(info)
            log(record)

        for stream_index, (record, extras) in enumerate(records):
            # xid
            xid = record.get('id', False)
            # dbid
            dbid = False
            if record.get('.id'):
                try:
                    dbid = int(record['.id'])
                except ValueError:
                    # in case of overridden id column
                    dbid = record['.id']
                if not cls.objects.filter(pk=dbid).exists():
                    log(dict(extras,
                             type='error',
                             record=stream_index,
                             field='.id',
                             message="Identificador de base desconocido '%s'"
                                     % dbid))
                    dbid = False

            converted = convert(record,
                                functools.partial(_log, extras, stream_index))

            yield dbid, xid, converted, dict(extras, record=stream_index)

    @classmethod
    def load(cls, fields, data, using=DEFAULT_DB_ALIAS):
        """≙ ``load`` (``odoo19c: :895-1073``).

        «Attempts to load the data matrix, and returns a list of ids (or
        ``False`` if there was an error and no id could be generated) and a
        list of messages.»

        :param fields: los campos a importar, en el orden de las columnas.
        :param data: la matriz de datos, por filas.
        :returns: ``{'ids': [...] | False, 'messages': [...], 'nextrow': int}``.

        Las tres decisiones de la fuente que definen su comportamiento:

        - **Se intenta en lote y, si falla, uno por uno.** El lote es el camino
          rápido; el recorrido fila a fila es el que puede decir *cuál* falló.
          El error del lote se guarda y se antepone al informe si el segundo
          intento tampoco crea nada, porque a veces sólo el conjunto es
          inválido.
        - **Cada fallo vuelve al punto de retorno.** Sin eso la transacción
          queda abortada en PostgreSQL y el resto del archivo ya no se puede
          importar — es lo que :class:`service.db.Savepoint` existe para dar.
        - **El recorrido se corta a los diez errores** si además hay más de uno
          por cada diez filas, con el aviso de la fuente: un archivo con el
          formato equivocado produciría un informe ilegible.

        Si hubo **algún** error, se deshace todo y ``ids`` es ``False``: una
        importación es completa o no es.
        """
        converter_cls = registry.model_by_name('ir.fields.converter')
        converter_cls._selection_translation_cache.clear()

        context = get_context()
        # determine values of mode, current_module and noupdate
        mode = context.get('mode', 'init')
        current_module = context.get('module', '__import__')
        noupdate = context.get('noupdate', False)

        connection = connections[using]
        savepoint = Savepoint(connection)

        fields = [fix_import_export_id_paths(f) for f in fields]

        ids = []
        messages = []

        # list of (xid, vals, info) for records to be created in batch
        batch = []
        batch_xml_ids = set()
        # models in which we may have created / modified data, therefore might
        # require flushing in order to name_search: the root model and any o2m
        creatable_models = {cls}
        for field_path in fields:
            if field_path[0] in (None, 'id', '.id'):
                continue
            model = cls
            for field_name in field_path:
                if field_name in (None, 'id', '.id'):
                    break
                try:
                    field = model._meta.get_field(field_name)
                except (FieldDoesNotExist, AttributeError):
                    break
                if getattr(field, 'one_to_many', False):
                    model = field.related_model
                    creatable_models.add(model)

        def flush(*, xml_id=None, model=None):
            if not batch:
                return

            assert not (xml_id and model), \
                'flush can specify *either* an external id or a model, not both'

            if model and model not in creatable_models:
                return

            data_list = [
                dict(xml_id=xid, values=vals, info=info, noupdate=noupdate)
                for xid, vals, info in batch
            ]
            batch.clear()
            batch_xml_ids.clear()

            # try to create in batch
            global_error_message = None
            try:
                with Savepoint(connection):
                    recs = cls._load_records(data_list, mode == 'update',
                                              using=using)
                    ids.extend(record.pk for record in recs)
                return
            except UserError as exc:
                global_error_message = dict(data_list[0]['info'], type='error',
                                            message=str(exc))
            except Exception:  # noqa: BLE001
                # silent OK because el lote es el camino rápido y su fallo NO
                # es el resultado: el recorrido fila a fila de abajo vuelve a
                # intentarlo y es el que puede decir CUÁL falló. Tragarlo aquí
                # es lo que la fuente hace, y por eso mismo
                # (``odoo19c: odoo/orm/models.py:980-981``).
                pass

            errors = 0
            # try again, this time record by record
            for i, rec_data in enumerate(data_list, 1):
                try:
                    [rec] = cls._load_records([rec_data], mode == 'update',
                                               using=using)
                    ids.append(rec.pk)
                except DatabaseError as exc:
                    savepoint.rollback()
                    info = rec_data['info']
                    pg_error_info = {'message': cls._sql_error_to_message(exc)}
                    diag = getattr(exc.__cause__, 'diag', None)
                    if diag is not None and diag.table_name == cls._meta.db_table:
                        e_fields = get_columns_from_sql_diagnostics(
                            connection, diag, check_registry=True)
                        if len(e_fields) == 1:
                            pg_error_info['field'] = e_fields[0]
                    messages.append(dict(info, type='error', **pg_error_info))
                    # Failed to write, log to messages, rollback savepoint (to
                    # avoid broken transaction) and keep going
                    errors += 1
                except UserError as exc:
                    savepoint.rollback()
                    messages.append(dict(rec_data['info'], type='error',
                                         message=str(exc)))
                    errors += 1
                except Exception as exc:  # noqa: BLE001
                    savepoint.rollback()
                    _logger.debug('Error while loading record', exc_info=True)
                    messages.append(dict(
                        rec_data['info'], type='error',
                        message='Error desconocido durante la importación: '
                                '%s: %s' % (exc.__class__, exc),
                        moreinfo='Resuelve los otros errores primero'))
                    # Failed for some reason, perhaps due to invalid data
                    # supplied, rollback savepoint and keep going
                    errors += 1
                if errors >= 10 and (errors >= i / 10):
                    messages.append({
                        'type': 'warning',
                        'message': 'Más de 10 errores y más de uno por cada 10 '
                                   'registros: se interrumpe para no mostrar '
                                   'demasiados errores.',
                    })
                    break
            if errors > 0 and global_error_message \
                    and global_error_message not in messages:
                # If we cannot create the records 1 by 1, we display the error
                # raised when we created the records simultaneously
                messages.insert(0, global_error_message)

        # make 'flush' available to the methods below, in the case where XMLID
        # resolution fails, for instance
        limit = context.get('_import_limit')
        if limit is None:
            limit = float('inf')

        with context_scope(_import_current_module=current_module,
                           import_flush=flush, import_cache={}):
            extracted = cls._extract_records(fields, data,
                                              log=messages.append, limit=limit)
            converted = list(cls._convert_records(
                extracted, log=messages.append, savepoint=savepoint))

            info = {'rows': {'to': -1}}
            for id, xid, record, info in converted:
                if xid:
                    xid = xid if '.' in xid else '%s.%s' % (current_module, xid)
                    batch_xml_ids.add(xid)
                elif id:
                    record['id'] = id
                batch.append((xid, record, info))

            flush()

        if any(message['type'] == 'error' for message in messages):
            savepoint.rollback()
            ids = False
        savepoint.close(rollback=False)

        nextrow = info['rows']['to'] + 1
        if nextrow < limit:
            nextrow = 0
        return {
            'ids': ids,
            'messages': messages,
            'nextrow': nextrow,
        }

    # -- El cargador ---------------------------------------------------------

    @classmethod
    def _load_records(cls, data_list, update=False, using=DEFAULT_DB_ALIAS):
        """≙ ``_load_records`` (``odoo19c: :5108-5213``).

        Docstring de la fuente, verbatim: *"Create or update records of this
        model, and assign XMLIDs."*

        :param data_list: lista de dicts con ``xml_id`` (el identificador a
            asignar), ``noupdate`` (su bandera) y ``values`` (los valores).
        :param update: ``True`` al **actualizar** un módulo.
        :return: los registros correspondientes a ``data_list``.

        Los dos avisos de contexto de la fuente se portan y siguen leyendo del
        contexto, que aquí es ``tools.misc``/``orm.environments`` en vez del
        ``env.context``: ``install_module`` (avisa de un ``xml_id`` de otro
        módulo) e ``import_file`` (rechaza un prefijo que coincida con un
        módulo instalado, porque la próxima actualización borraría el
        registro).
        """
        IrModelData = apps.get_model('base', 'IrModelData')

        # determine existing xml_ids
        xml_ids = [data['xml_id'] for data in data_list if data.get('xml_id')]
        existing = {
            ('%s.%s' % row[1:3]): row
            for row in IrModelData._lookup_xmlids(xml_ids, cls, using=using)
        }

        # determine which records to create and update
        to_create = []                  # list of data
        to_update = []                  # list of data
        imd_data_list = []              # list of data for _update_xmlids()

        for data in data_list:
            xml_id = data.get('xml_id')
            if not xml_id:
                vals = data['values']
                if vals.get('id'):
                    data['record'] = cls.objects.using(using).get(pk=vals['id'])
                    to_update.append(data)
                elif not update:
                    to_create.append(data)
                else:
                    raise ValidationError(
                        'Cannot update a record without specifying its id or '
                        'xml_id')
                continue
            row = existing.get(xml_id)
            if not row:
                to_create.append(data)
                continue
            d_id, _d_module, _d_name, d_model, d_res_id, d_noupdate, r_id = row
            if cls._meta.label != d_model:
                raise ValidationError(
                    f'For external id {xml_id} '
                    f'when trying to create/update a record of model '
                    f'{cls._meta.label} '
                    f'found record of different model {d_model} ({d_id})')
            if r_id:
                data['record'] = cls.objects.using(using).get(pk=d_res_id)
                imd_data_list.append(data)
                if not (update and d_noupdate):
                    to_update.append(data)
            else:
                IrModelData.objects.using(using).filter(pk=d_id).delete()
                to_create.append(data)

        # update existing records
        for data in to_update:
            data['record']._load_records_write(data['values'])

        # check for records to create with an XMLID from another module
        context = get_context()
        module = context.get('install_module')
        if module:
            prefix = module + '.'
            for data in to_create:
                if (data.get('xml_id') and not data['xml_id'].startswith(prefix)
                        and not context.get('foreign_record_to_create')):
                    _logger.warning('Creating record %s in module %s.',
                                    data['xml_id'], module)

        if context.get('import_file'):
            IrModule = apps.get_model('base', 'IrModule')
            existing_modules = set(IrModule.objects.using(using).values_list(
                'name', flat=True))
            for data in to_create:
                xml_id = data.get('xml_id')
                if xml_id and not data.get('noupdate'):
                    module_name, sep, record_id = xml_id.partition('.')
                    if sep and module_name in existing_modules:
                        raise UserError(
                            f'The record {xml_id} has the module prefix '
                            f'{module_name}. This is the part before the "." '
                            f'in the external id. Because the prefix refers to '
                            f'an existing module, the record would be deleted '
                            f'when the module is upgraded. Use either no '
                            f'prefix and no dot or a prefix that is not an '
                            f'existing module. For example, __import__, '
                            f'resulting in the external id '
                            f'__import__.{record_id}.')

        # create records
        if to_create:
            records = cls._load_records_create(
                [data['values'] for data in to_create], using=using)
            for data, record in zip(to_create, records):
                data['record'] = record
                if data.get('xml_id'):
                    # add XML ids for parent records that have just been created
                    # ``_inherits`` se lee del atributo de clase, que es donde
                    # la referencia lo declara y donde este árbol lo porta
                    # verbatim (tarea #385).
                    for parent_model, parent_field in getattr(
                            cls, '_inherits', {}).items():
                        if not data['values'].get(parent_field):
                            imd_data_list.append({
                                'xml_id': f"{data['xml_id']}_"
                                          f"{parent_model.replace('.', '_')}",
                                'record': getattr(record, parent_field),
                                'noupdate': data.get('noupdate', False),
                            })
                    imd_data_list.append(data)

        # create or update XMLIDs
        IrModelData._update_xmlids(imd_data_list, update, using=using)

        return [data['record'] for data in data_list]



def search_display_name(model_cls, operator, value):
    """La implementación base de ``_search_display_name``, como función.

    Existe por una divergencia **de vía**, no de alcance. En la fuente el
    método cuelga de ``BaseModel``, así que una sobrescritura delega con
    ``super()`` y siempre lo encuentra. Aquí el bloque ``display_name`` llega
    por dos caminos distintos —herencia de :class:`DisplayNameMixin` para la
    mayoría, e inyección de :func:`orm.model_classes.adopt_display_name` para
    los que declaran su propia base— y en el segundo **``super()`` no lo ve**:
    el mixin no está en el MRO.

    Medido: de los tres modelos que sobrescriben este método en ``base``, dos
    —``ResBank`` y ``ResCurrencyRate``— tienen el bloque inyectado y sólo uno
    lo hereda. Una delegación con ``super()`` funcionaría en un tercio de los
    casos, que es peor que no funcionar en ninguno: falla sólo para algunos
    operadores de algunos modelos.

    Por eso la implementación base es una función y el ``classmethod`` la
    invoca. Una sobrescritura que quiera delegar la llama por su nombre, y
    funciona por los dos caminos.
    """
    cls = model_cls
    search_fnames = (getattr(cls, '_rec_names_search', None)
                     or ([cls._rec_name] if getattr(cls, '_rec_name', None)
                         else []))
    if not search_fnames:
        _logger.warning(
            'No se puede buscar por display_name: %s no declara _rec_name '
            'ni _rec_names_search', cls._meta.label)
        return Domain.TRUE
    negative = operator in NEGATIVE_DISPLAY_NAME_OPERATORS
    if operator.endswith('like') and not value and '=' not in operator:
        return Domain.FALSE if negative else Domain.TRUE

    combine = Domain.AND if negative else Domain.OR
    return combine([Domain(field_expr, operator, value)
                    for field_expr in search_fnames])


def _display_name_default(record):
    """El ``default`` del descriptor: delega en ``_compute_display_name``."""
    return record._compute_display_name()


class OrderMixin:
    """``_check_qorder`` — la cláusula de orden se valida antes de usarse.

    ≙ ``BaseModel._check_qorder`` (``odoo19c: odoo/orm/models.py:5215-5222``).
    Su única razón de existir es que un ``_order`` llega como **texto** —de una
    fila de ``ir.model``, de un contexto, de un parámetro— y acaba interpolado
    en un ``ORDER BY``. La comprobación es lo que separa un nombre de campo de
    una inyección.

    **La divergencia es de VÍA, no de alcance**, y es la misma que
    :class:`DisplayNameMixin` y :class:`FieldSqlMixin` ya declaran: allá cuelga
    de ``BaseModel``, así que todo modelo lo tiene; aquí ``models.Model`` es el
    de Django y no es nuestro para colgarle nada. Lo adopta
    ``TimeStampedModel``, que es la base común del proyecto.
    """

    def _check_qorder(self, word):
        """Levanta ``UserError`` si ``word`` no es una cláusula de orden válida.

        Cuerpo verbatim de la fuente, con su mensaje: *"Invalid 'order'
        specified (%s). A valid 'order' specification is a comma-separated list
        of valid field names (optionally followed by asc/desc for the
        direction)"*.
        """
        if not regex_order.match(word):
            raise UserError(
                'Orden inválido (%s). Un orden válido es una lista de nombres '
                'de campo separados por coma, cada uno seguido opcionalmente '
                'de asc o desc.' % word)


class DisplayNameMixin:
    """``display_name`` y su bloque — la etiqueta de un registro, universal.

    ≙ el bloque que ``BaseModel`` declara bajo el comentario
    *"display_name, name_create, name_search"* (``odoo19c:
    odoo/orm/models.py:1421-1543``): el campo ``display_name`` (``:473``), su
    ``_compute_display_name`` (``:1425``), su ``_search_display_name``
    (``:1442``), ``name_create`` (``:1493``) y ``name_search`` (``:1512``).

    **La divergencia es de VÍA, no de alcance**, y es la misma que
    :class:`RecordLoaderMixin` declara: allá cuelgan de ``BaseModel``, así que
    **todo** modelo los tiene sin declarar nada; aquí ``models.Model`` es el de
    Django y no es nuestro. La universalidad se recupera por dos caminos, que
    son los de ``H-API-577``:

    - este mixin lo adopta ``TimeStampedModel``, la base común del proyecto —
      **284 de los 374 modelos concretos nuestros** lo heredan (medido);
    - los **90** restantes lo reciben de :func:`orm.model_classes.adopt_display_name`,
      que corre en ``class_prepared`` y en un barrido, igual que el manager de
      permisos.

    Por qué no basta con la base común: 90 modelos no la heredan, y **el olvido
    no falla** — un modelo sin ``display_name`` cae al ``__str__`` de Django y
    nada lo delata. Es la misma clase de defecto silencioso que ``H-API-876``
    registró para el manager.

    Tres divergencias de FORMA, todas heredadas del árbol y ninguna nueva
    ======================================================================

    Las tres ya las ejercían los cinco modelos que declaraban su
    ``_compute_display_name`` antes de esta tarea (``res_bank``, ``res_partner``,
    ``ir_model``, ``properties_base_definition``, ``res_currency``), así que
    cambiarlas ahora rompería lo que ya funciona:

    1. **``_compute_display_name`` DEVUELVE la etiqueta**; la fuente la
       **asigna** (``record.display_name = convert(...)``). Aquí el campo no es
       un campo del ORM con cache de cómputo, así que el valor tiene que
       volver al descriptor por el retorno.
    2. **``name_create`` y ``name_search`` reciben y devuelven lo de Django.**
       ``name_search`` acota con un ``Q`` y no con un dominio extra, que es la
       forma que sus llamadores de este árbol ya usaban.
    3. **``name_create`` y ``name_search`` son ``classmethod``**: allá son
       ``@api.model``, es decir métodos sobre un recordset vacío que sólo
       aporta el modelo. Ese papel lo cumple la clase.

    Lo que DEJÓ de ser divergencia: la forma de ``_search_display_name``
    ======================================================================

    Hasta ``api@4f898d9e`` este bloque declaraba una tercera divergencia —
    ``_search_display_name`` devolvía un ``QuerySet``— con el argumento de que
    era *"lo que el llamador de este árbol sabe consumir"*. El argumento era
    medible y quedó falso al llegar el segundo llamador: el optimizador de
    dominios necesita un ``Domain``, y la diferencia no es de estilo. Un
    dominio **se compone** —cabe dentro de un ``any``, se niega sin
    materializar, se optimiza con el resto—; un ``QuerySet`` no. Ahora
    devuelve ``Domain``, como la fuente, y ``name_search`` lo convierte con
    ``to_q`` para seguir acotando en Django.

    Lo que NO es divergencia: la asignación sigue permitida
    ======================================================

    ``display_name`` es un :class:`orm.fields_nonstored.NonStored`, no una
    ``property``, y la diferencia es deliberada: la fuente declara un campo, y
    un campo de la fuente **se puede escribir en memoria** aunque no tenga
    columna. ``record.display_name = 'X'`` gana sobre el cómputo hasta que se
    borre, igual que allá.
    """

    #: ≙ ``display_name = Char(string='Display Name', compute=..., search=...)``
    #: (``odoo19c: odoo/orm/models.py:473``). El ``compute`` y el ``search`` de
    #: la fuente son los dos métodos de abajo; aquí el primero lo cablea el
    #: ``default`` del descriptor y el segundo lo llama ``name_search``.
    display_name = NonStored(default=_display_name_default,
                             search='_search_display_name',
                             help_text='Display Name')

    def _compute_display_name(self):
        """La etiqueta del registro — ≙ ``_compute_display_name`` (``:1425``).

        Con ``_rec_name`` resuelto, el valor de ese campo pasado por
        :func:`orm.fields.convert_to_display_name`; sin él, ``modelo,id``,
        verbatim el ``f"{record._name},{record.id}"`` de la fuente.

        El ``@api.depends(lambda self: (self._rec_name,) ...)`` de la fuente no
        se porta: declara de qué depende el cómputo para invalidar su cache, y
        aquí no hay cache que invalidar — el descriptor computa en cada
        lectura. Es divergencia de mecanismo, no un hueco.
        """
        rec_name = getattr(type(self), '_rec_name', None)
        if not rec_name:
            name = getattr(type(self), '_name', None) or self._meta.label
            return f'{name},{self.pk}'
        try:
            field = self._meta.get_field(rec_name)
        except FieldDoesNotExist:
            field = None
        etiqueta = convert_to_display_name(field, getattr(self, rec_name), self)
        # El ``False`` del default de la fuente para un campo vacío: aquí la
        # etiqueta tiene que ser texto, así que se cae al par ``modelo,id`` —
        # que es lo que la fuente da cuando NO hay ``_rec_name`` en absoluto, y
        # el único texto que identifica al registro sin inventar nada.
        if not etiqueta:
            name = getattr(type(self), '_name', None) or self._meta.label
            return f'{name},{self.pk}'
        return etiqueta

    @classmethod
    def _search_display_name(cls, operator, value):
        """Los registros cuya etiqueta coincide — ≙ ``:1442``.

        Busca sobre ``_rec_names_search`` o, en su defecto, sobre
        ``_rec_name``: la misma preferencia y el mismo orden de la fuente.
        Sin ninguno de los dos **avisa y no restringe** — ``Domain.TRUE`` allá,
        ``objects.all()`` aquí—, que es la conducta de la fuente y no un
        atajo: restringir a cero sería inventar una negativa que la fuente no
        da.

        ``_rec_names_search`` admite rutas con punto (``partner_id.name``); se
        traducen al ``__`` de Django, que es el mismo recorrido de relación.
        Un campo relacional busca sobre el ``display_name`` del otro lado en la
        fuente; aquí sobre su ``_rec_name``, que es de donde ese
        ``display_name`` sale.

        El corto-circuito del ``like ''`` de la fuente se porta: con valor
        vacío y operador positivo devuelve todo, y con uno negativo, nada.
        """
        return search_display_name(cls, operator, value)

    @classmethod
    def name_create(cls, name):
        """Crea el registro a partir de su sola etiqueta — ≙ ``:1493``.

        Escribe ``name`` en el campo que ``_rec_name`` nombra y devuelve el par
        ``(id, display_name)``. Sin ``_rec_name`` avisa y devuelve ``False``,
        verbatim — con su ``TODO`` incluido: la fuente misma anota que debería
        lanzar un error en vez de devolver un falso.
        """
        rec_name = getattr(cls, '_rec_name', None)
        if not rec_name:
            _logger.warning(
                'No se puede ejecutar name_create: %s no declara _rec_name',
                cls._meta.label)
            return False
        record = cls.objects.create(**{rec_name: name})
        return record.pk, record.display_name

    @classmethod
    def name_search(cls, name='', domain=None, operator='ilike', limit=100):
        """Los pares ``(id, etiqueta)`` que coinciden — ≙ ``:1512``.

        Es :meth:`_search_display_name` acotado por el ``domain`` extra y por
        ``limit``. El ``domain`` se recibe como ``Q`` de Django o ``None``,
        que es la forma que ``website_rewrite.name_search`` ya usaba en este
        árbol.

        El ``.sudo()`` del final de la fuente no se porta: allá levanta el
        permiso para poder leer la etiqueta de lo que la búsqueda ya
        seleccionó. Aquí la selección la hace un ``QuerySet`` de Django, que no
        filtra por permiso — el acotamiento por fila lo aplica
        ``AccessQuerySet`` cuando el llamador lo pide, y elevarlo aquí sería
        conceder un permiso que nadie otorgó.
        """
        queryset = cls.objects.filter(
            to_q(Domain('display_name', operator, name), cls))
        if domain is not None:
            queryset = queryset.filter(domain)
        return [(record.pk, record.display_name) for record in queryset[:limit]]


#: Los operadores de semántica negativa que :meth:`_search_display_name`
#: atiende — ≙ el ``Domain.NEGATIVE_OPERATORS`` que la fuente consulta
#: (``odoo19c: odoo/orm/models.py:1462``). Es la tercera copia del mismo
#: conjunto en este árbol; unificar las tres en un hogar compartido es la
#: tarea **#380**, que ``orm/fields.py`` ya declara para las suyas.
NEGATIVE_DISPLAY_NAME_OPERATORS = frozenset([
    'not like', 'not ilike', 'not =like', 'not =ilike', '!=', '<>',
])


# ═══════════════════════════════════════════════════════════════════════════
# El acceso por clave — ≙ ``odoo19c: odoo/orm/models.py:6669-6698``
# ═══════════════════════════════════════════════════════════════════════════
#
# Es la primitiva de la que cuelga la familia ``related=`` de ``Field``:
# ``_compute_related`` escribe ``record[self.name] = ...`` e
# ``_inverse_related`` lo lee. Sin ella el porte de esa familia sería código
# que no puede correr.
#
# Medido antes de construir: ``django.db.models.Model`` no responde a
# ``__getitem__`` ni a ``__setitem__``. No hay colisión que respetar.
#
# **Se porta SÓLO su rama de cadena.** La fuente sobrecarga ``__getitem__``
# con tres significados —``inst[3]`` da el cuarto registro, ``inst[10:20]`` un
# subconjunto, ``rs['name']`` un valor— porque allá un recordset ES un
# contenedor de filas. Aquí una instancia de modelo es UNA fila, y el
# contenedor es el ``QuerySet``, que ya responde a ``[3]`` y a ``[10:20]`` con
# la semántica de Django. Portar esas dos ramas sobre la instancia inventaría
# un significado que el contenedor ya tiene en otro sitio; la rama de cadena,
# en cambio, no existe en ninguno de los dos.
#
# **Por qué NO consulta ``_fields``.** El árbol ya declara un ``_fields``
# (``FieldToSqlMixin``, arriba) y su contrato es más estrecho que el de la
# fuente: filtra por ``concrete``, porque quien lo consume compone SQL. La
# fuente incluye TODOS los campos. Instalar un segundo ``_fields`` con la
# semántica ancha crearía dos fuentes de verdad del mismo mapa —el defecto que
# ``calibration-verified-numbers.md`` prohíbe—, y ensancharlo en el sitio
# cambiaría el alcance de todo consumidor de ``_field_to_sql``. Así que el
# acceso por clave pregunta a ``_meta``, que es el registro que todo modelo
# tiene, y la reconciliación de los dos contratos queda como decisión con su
# medición: tarea **#215**.


def _model_getitem(self, key):
    """≙ ``BaseModel.__getitem__``, rama de cadena (``:6674``) — «read the
    field ``key``».

    La fuente llama al **getter del campo**, no a ``getattr`` a secas, y su
    comentario lo subraya: *«important: one must call the field's getter»*.
    Aquí el getter del campo ES el descriptor que Django instaló, así que
    ``getattr`` lo invoca — la indirección es la misma, sólo que quien aloja
    el descriptor es Django.

    Un nombre que el modelo no declara levanta ``KeyError`` y no
    ``AttributeError``: es acceso por clave, y quien lo escribe espera el
    error del mapa.
    """
    if not isinstance(key, str):
        raise TypeError(
            f'{type(self).__name__}[{key!r}]: sólo se accede por nombre de '
            'campo. El contenedor de filas es el QuerySet, no la instancia.')
    try:
        self._meta.get_field(key)
    except FieldDoesNotExist:
        raise KeyError(key) from None
    return getattr(self, key)


def _model_setitem(self, key, value):
    """≙ ``BaseModel.__setitem__`` (``:6694``) — «assign the field ``key`` to
    ``value``». Mismo criterio que el getter, con el setter del descriptor."""
    try:
        self._meta.get_field(key)
    except FieldDoesNotExist:
        raise KeyError(key) from None
    setattr(self, key, value)


Model.__getitem__ = _model_getitem
Model.__setitem__ = _model_setitem


# ═══════════════════════════════════════════════════════════════════════════
# Capa C de #273 — ``modified()``: quien recorre el grafo y marca el recalculo
# ═══════════════════════════════════════════════════════════════════════════
#
# ≙ ``BaseModel.modified``, ``_modified``, ``_modified_triggers``,
# ``_recompute_model``, ``_recompute_recordset`` y ``_recompute_field``
# (``odoo19c: odoo/orm/models.py:6756-6959``).
#
# Las tres capas de #273, en una linea cada una:
#
# - **A** (``orm/fields.py``) — el campo sabe recalcularse y cachear su valor.
# - **B** (``orm/registry.py``) — el grafo sabe QUE campos dependen de cual, y
#   por que camino llegar a las filas afectadas.
# - **C** (aqui) — alguien recorre ese grafo cuando un valor cambia, y marca.
#
# **Divergencia de mecanismo transversal, declarada una vez:** la fuente opera
# sobre *recordsets* y aqui la unidad es la **instancia** o el ``QuerySet``.
# Donde ella escribe ``records.browse(ids)`` para rehacer un conjunto, aqui se
# lleva una **lista de instancias**: no hay recordset que rehacer, y filtrar la
# lista es la misma operacion sin la indireccion. Es la misma adaptacion que
# ``orm.utils.record_ids`` y ``orm.utils.as_record_list`` ya declaran.


def _model_of_records(records):
    """La clase de modelo de ``records`` — clase, instancia, lista o ``QuerySet``.

    La rama de la CLASE existe porque la fuente llama a esta familia sobre un
    recordset vacio del modelo (``self.env[nombre]``), que allá lleva su modelo
    consigo. Aqui el equivalente que llega desde el eje de esquema es la propia
    clase, y ``as_record_list`` no la puede recorrer: ``list(ModelBase)`` es un
    ``TypeError``. Sus dos consumidores —``flush_model`` y
    ``_recompute_model``— ya escribian la guarda
    ``or (self if isinstance(self, type) else None)``, asi que **declaraban**
    admitir la clase; lo que faltaba era que esta funcion llegara a devolverla
    en vez de reventar antes.
    """
    if isinstance(records, type):
        return records
    if isinstance(records, QuerySet):
        return records.model
    rows = as_record_list(records)
    return type(rows[0]) if rows else None


def _new_records(rows):
    """Las filas aun sin persistir — ≙ el ``NewId`` de la fuente.

    Alla un registro sin guardar lleva un id-falso y ``bool(NewId)`` es
    ``False``; aqui Django deja ``pk is None`` hasta el ``save()``. Es el mismo
    predicado con otro portador (``orm/identifiers.py`` lo declara).
    """
    return [row for row in rows if row.pk is None]


def _inverse_accessor(inverse):
    """El nombre por el que se navega ``inverse`` desde una instancia.

    **No es ``inverse.name``**, y la diferencia es medible: en un
    ``ManyToOneRel`` sin ``related_name`` el ``name`` es el del modelo en
    minusculas y el atributo real es ``<modelo>_set``. La fuente no tiene esta
    distincion porque su lado inverso es un campo declarado con su nombre; aqui
    Django separa el nombre del registro del nombre del atributo, asi que se
    pregunta por el segundo.
    """
    accessor = getattr(inverse, 'get_accessor_name', None)
    return accessor() if accessor is not None else inverse.name


def _traverse_inverse(rows, inverse):
    """Las filas a las que ``rows`` llega por ``inverse``.

    ≙ ``self[invf.name]`` de la fuente (``:6892``). El acceso a un lado inverso
    en Django devuelve un *related manager*, no el conjunto: se materializa
    aqui, y un lado directo devuelve la instancia o ``None``.
    """
    name = _inverse_accessor(inverse)
    reached = []
    seen = set()
    for row in rows:
        value = getattr(row, name, None)
        if value is None:
            continue
        found = list(value.all()) if hasattr(value, 'all') else [value]
        for item in found:
            key = (type(item), item.pk) if item.pk is not None else id(item)
            if key not in seen:
                seen.add(key)
                reached.append(item)
    return reached


def _records_pointing_at(model, field, rows):
    """Las filas de ``model`` cuyo ``field`` apunta a alguna de ``rows``.

    ≙ el ``else`` del ``for`` de ``:6903-6913``: cuando ningun inverso sirve,
    la fuente busca por dominio. Aqui la busqueda es un ``filter`` con
    ``__in``, y las filas aun sin persistir se resuelven por el cache del
    campo — que es donde su valor vive hasta el ``save()``.
    """
    new_rows = _new_records(rows)
    real_ids = [row.pk for row in rows if row.pk is not None]
    found = []
    if real_ids:
        found = list(model.objects.filter(
            **{f'{field.name}__in': real_ids}).order_by('pk'))
    if new_rows:
        cached_ids = field._get_cache(env())
        new_keys = {id(row) for row in new_rows}
        for candidate in model.objects.filter(pk__in=list(cached_ids)):
            value = getattr(candidate, field.name, None)
            if value is not None and id(value) in new_keys:
                found.append(candidate)
    return found


def _modified_triggers(self, tree, create=False):
    """Recorre el arbol de disparo hacia atras, cediendo que recalcular.

    ≙ ``BaseModel._modified_triggers`` (``:6862-6918``). Cede tuplas
    ``(campo, filas, creado)``.
    """
    rows = as_record_list(self)
    if not rows:
        return

    #: Primero lo que hay que calcular sobre estas mismas filas.
    for field in tree.root:
        yield field, rows, create

    #: Luego se baja por cada dependencia, invirtiendola.
    for field, subtree in tree.items():
        #: Al crear, ninguna otra fila puede tener todavia una referencia a
        #: estas — ≙ ``:6884-6886``.
        if create and (getattr(field, 'many_to_one', False)
                       or getattr(field, 'type', None) in ('many2one',
                                                           'many2one_reference')):
            continue

        model = getattr(field, 'model', None)
        if model is None:
            continue

        records = None
        for inverse in registry.field_inverses[field]:
            #: Un inverso con dominio no sirve para la vuelta: su conjunto no
            #: es el de todas las filas que apuntan aqui — ≙ ``:6889``.
            if getattr(inverse, 'domain', None) and (
                    getattr(inverse, 'one_to_many', False)
                    or getattr(inverse, 'many_to_many', False)):
                continue
            records = _traverse_inverse(rows, inverse)
            break

        if records is None:
            records = _records_pointing_at(model, field, rows)

        if records:
            yield from _modified_triggers(records, subtree)


def _modified(self, fields, create):
    """Los disparos que ``fields`` provoca sobre ``self``.

    ≙ ``BaseModel._modified`` (``:6840-6860``). El ``select`` descarta del
    arbol fusionado las ramas que solo contienen campos sin columna y sin nada
    en cache: recorrerlas costaria consultas para no invalidar nada.
    """
    environment = env()

    def select(field):
        return bool((field.compute and field.store)
                    or field._get_all_cache_ids(environment))

    tree = registry.get_trigger_tree(fields, select=select)
    if not tree:
        return ()

    #: La fuente eleva y desactiva el filtro por activo para el recorrido; aqui
    #: la elevacion es un bloque de contexto, no un metodo del recordset, asi
    #: que se abre alrededor de la construccion del iterador. Materializar es
    #: deliberado: un generador perezoso saldria del bloque antes de recorrer.
    with elevate_privileges(), context_scope(active_test=False):
        return list(_modified_triggers(self, tree, create))


def modified(self, fnames, create=False, before=False):
    """Anuncia que ``fnames`` va a cambiar o cambio sobre ``self``.

    ≙ ``BaseModel.modified`` (``:6756-6838``). Invalida el cache donde toca y
    prepara el recalculo de los campos almacenados que dependan.

    Docstring de la fuente, verbatim: *"Notify that fields will be or have been
    modified on ``self``. This invalidates the cache where necessary, and
    prepares the recomputation of dependent stored fields"*.

    :param fnames: nombres de campo modificados sobre ``self``
    :param create: si se llama en el contexto de una creacion
    :param before: si se llama ANTES de modificar

    El arbol de disparo de un campo F contiene los campos que dependen de F,
    junto con los campos a invertir para saber que filas recalcular. Si G
    depende de F, H de X.F, I de W.X.F y J de Y.F, el arbol de F es::

                                  [G]
                                X/   \\Y
                              [H]     [J]
                            W/
                          [I]

    y al modificar F sobre unas filas se marca G sobre ellas, H sobre
    ``inverso(X, filas)``, I sobre ``inverso(W, inverso(X, filas))`` y J sobre
    ``inverso(Y, filas)``.
    """
    rows = as_record_list(self)
    if not rows or not fnames:
        return

    transaction = get_transaction()
    if before:
        #: Antes de modificar hay que ver que depende de ``self`` **ahora**, y
        #: eso no debe recalcularse antes del cambio: solo se acumula.
        marked = transaction.tocompute
        tomark = collections.defaultdict(OrderedSet)
    else:
        #: Despues, el recorrido hacia atras tiene que contar con todo lo que
        #: ya se sabe pendiente, asi que se marca cuanto antes.
        marked = {}
        tomark = transaction.tocompute

    registry_of_model = model_field_registry(type(rows[0]))
    fields = [registry_of_model[fname] for fname in fnames]
    todo = [_modified(rows, fields, create)]

    environment = env()
    for field, records, created in itertools.chain.from_iterable(todo):
        protected_ids = environment.protected(field)
        records = [row for row in records if row.pk not in protected_ids]
        if not records:
            continue

        if field.recursive:
            #: Descarta lo ya procesado, para no entrar en ciclo — ``:6813``.
            if field.compute and field.store:
                seen = set(marked.get(field) or ()) | set(tomark.get(field) or ())
                records = [row for row in records if row.pk not in seen]
            else:
                #: Sin columna solo interesan las filas con valor en cache: las
                #: demas no tienen nada que invalidar.
                in_cache = field._get_all_cache_ids(environment)
                records = [row for row in records if row.pk in in_cache]
            if not records:
                continue
            todo.append(_modified(records, [field], created))

        if field.compute and field.store:
            tomark[field].update(record_ids(records))
        else:
            #: Un calculado sin columna no se fuerza a recalcular: basta con
            #: retirar su valor del cache — ``:6828-6831``.
            field._invalidate_cache(environment, record_ids(records))

    if before:
        for field, ids in tomark.items():
            environment.add_to_compute(field, ids)


def _recompute_field(self, field, ids=None):
    """Procesa el recalculo pendiente de ``field``.

    ≙ ``BaseModel._recompute_field`` (``:6948-6959``).
    """
    pending = get_transaction().tocompute.get(field) or ()
    ids = pending if ids is None else [i for i in ids if i in pending]
    if not ids:
        return
    #: No se fuerza sobre las filas aun sin persistir: esas se recalculan al
    #: leer el campo — ``:6955-6957``.
    model = _model_of_records(self) or getattr(field, 'model', None)
    if model is None:
        return
    field.recompute(list(model.objects.filter(pk__in=[i for i in ids if i])))


def _recompute_model(self, fnames=None):
    """Procesa los calculos pendientes de los campos del MODELO de ``self``.

    ≙ ``BaseModel._recompute_model`` (``:6920-6932``). Sin acotar por fila: se
    procesa todo lo pendiente de cada campo.
    """
    model = _model_of_records(self) or (self if isinstance(self, type) else None)
    if model is None:
        return
    registry_of_model = model_field_registry(model)
    fields = (registry_of_model.values() if fnames is None
              else [registry_of_model[fname] for fname in fnames])
    for field in fields:
        if getattr(field, 'compute', None) and getattr(field, 'store', False):
            _recompute_field(self, field)


def _recompute_recordset(self, fnames=None):
    """Procesa los calculos pendientes de las FILAS de ``self``.

    ≙ ``BaseModel._recompute_recordset`` (``:6934-6946``). La diferencia con
    ``_recompute_model`` es el alcance: aqui solo estas filas.
    """
    rows = as_record_list(self)
    if not rows:
        return
    registry_of_model = model_field_registry(type(rows[0]))
    fields = (registry_of_model.values() if fnames is None
              else [registry_of_model[fname] for fname in fnames])
    for field in fields:
        if getattr(field, 'compute', None) and getattr(field, 'store', False):
            _recompute_field(self, field, record_ids(rows))


def _flush(self):
    """Escribe a la base lo que el calculo dejo sucio en el cache.

    ≙ ``BaseModel._flush`` (``odoo19c: odoo/orm/models.py:6386-6400``). La
    fuente saca del cache los campos sucios con sus ids y compone el
    ``UPDATE``; aqui el ``UPDATE`` lo pone Django con
    ``save(update_fields=...)``, que escribe **solo** esas columnas.

    El cache lo puebla ``orm.fields._cache_computed_values``, que corre al
    final de cada ``compute_value``: sin el, ``field_dirty`` estaria siempre
    vacio y este metodo no tendria de donde saber que columna escribir.

    **El alcance es el MODELO, no las filas de ``self``** — corregido con la
    tarea #324. La version anterior arrancaba con ``rows = as_record_list(self)``
    y ``if not rows: return``, asi que sobre un recordset vacio no escribia
    nada; y ``flush_model``, que es quien lo llama sin filas, se volvia un
    verde que no discrimina: corria, no volcaba, y nadie lo notaba. La fuente
    recorre ``self._fields.values()`` y **saca** (``pop``) los ids sucios de
    cada uno, sin mirar ``self._ids``: por eso su ``flush_model`` sobre un
    recordset vacio si vuelca el modelo entero.

    La firma tambien vuelve a la de la fuente: ``_flush(self)``, sin
    ``fnames``. Quien acota por nombre es el llamador —``flush_model`` decide
    si vale la pena volcar— y allá el volcado, una vez decidido, es completo.
    """
    model = _model_of_records(self) or (self if isinstance(self, type) else None)
    if model is None:
        return
    dirty = get_transaction().field_dirty
    dirty_field_ids = {}
    for field in model_field_registry(model).values():
        ids = dirty.pop(field, None)
        if ids:
            dirty_field_ids[field] = ids
    if not dirty_field_ids:
        return

    #: Solo las filas ya persistidas: un id que no es entero es una fila
    #: virtual, que se recalcula al leerla y no tiene columna que escribir.
    wanted_ids = OrderedSet(record_id for ids in dirty_field_ids.values()
                            for record_id in ids if isinstance(record_id, int))
    rows = {row.pk: row for row in model.objects.filter(pk__in=list(wanted_ids))}

    for record_id in wanted_ids:
        row = rows.get(record_id)
        if row is None:
            # silent OK because la fila se borro entre el calculo y el volcado:
            # su id salio del cache sucio arriba, asi que no queda pendiente, y
            # escribir sobre una fila inexistente es el error, no el silencio.
            continue
        names = []
        for field, ids in dirty_field_ids.items():
            if record_id not in ids:
                continue
            cached = field._get_cache(env())
            if record_id not in cached:
                continue
            if getattr(field, 'many_to_many', False):
                _flush_m2m(row, field, cached[record_id])
                continue
            attname = getattr(field, 'attname', field.name)
            setattr(row, attname, cached[record_id])
            names.append(attname)
        if names:
            row.save(update_fields=names)


def _flush_m2m(row, field, value):
    """Vuelca un campo muchos-a-muchos calculado — la rama que #313 anade.

    Un M2M no es una columna y no admite ``setattr``: Django lanza
    ``TypeError: Direct assignment to the forward side of a many-to-many set
    is prohibited``. Tampoco cabe en ``update_fields``, que nombra columnas.
    Por eso la rama existe: el mismo valor calculado se entrega al manager
    relacional, que resuelve el diff contra la tabla intermedia.

    ``.set()`` y no un ``bulk_create`` sobre un ``through`` propio: las
    relaciones que hoy declaran computo son de **configuracion** —etiquetas de
    una cuenta, campos que disparan una regla—, de cardinalidad baja y
    escritura rara. Ahi lo caro es la superficie, no la ida a la base; y
    ``.set()`` emite ``m2m_changed``, que es donde vive el control de acceso
    de la relacion. La rama mira el CAMPO, no el modelo, asi que una relacion
    de operacion que manana pida otro mecanismo no queda cerrada por esto.

    Una fila sin ``pk`` no llega aqui: :func:`_flush` solo recorre las que el
    registro de sucios nombra por id, y una fila nueva no tiene ninguno.
    """
    manager = getattr(row, field.name)
    manager.set([] if value is None else value)


def flush_model(self, fnames=None):
    """Procesa los calculos y las escrituras pendientes del MODELO de ``self``.

    ≙ ``BaseModel.flush_model`` (``:6353-6365``). Docstring de la fuente,
    verbatim: *"Process the pending computations and database updates on
    ``self``'s model. When the parameter is given, the method guarantees that
    at least the given fields are flushed to the database. More fields can be
    flushed, though"*.
    """
    _recompute_model(self, fnames)
    model = _model_of_records(self) or (self if isinstance(self, type) else None)
    if model is None:
        return
    if fnames is None:
        _flush(self)
        return
    dirty = get_transaction().field_dirty
    registry_of_model = model_field_registry(model)
    if any(registry_of_model[fname] in dirty for fname in fnames):
        _flush(self)


def flush_recordset(self, fnames=None):
    """Procesa los calculos y las escrituras pendientes de las FILAS de ``self``.

    ≙ ``BaseModel.flush_recordset`` (``:6367-6384``). La diferencia con
    ``flush_model`` es el alcance: aqui solo estas filas.
    """
    rows = as_record_list(self)
    if not rows:
        return
    _recompute_recordset(rows, fnames)
    registry_of_model = model_field_registry(type(rows[0]))
    fields = (registry_of_model.values() if fnames is None
              else [registry_of_model[fname] for fname in fnames])
    ids = set(record_ids(rows))
    dirty = get_transaction().field_dirty
    if not all(ids.isdisjoint(dirty.get(field) or ()) for field in fields):
        _flush(rows)


for _engine_method in (modified, _modified, _modified_triggers,
                       _recompute_model, _recompute_recordset,
                       _recompute_field, _flush, flush_model,
                       flush_recordset):
    setattr(Model, _engine_method.__name__, _engine_method)
    setattr(QuerySet, _engine_method.__name__, _engine_method)


# ═══════════════════════════════════════════════════════════════════════════
# ``precompute`` — el cálculo que se adelanta al INSERT
#     ≙ ``BaseModel._prepare_create_values`` (``odoo19c: odoo/orm/models.py:
#     4786-4791``) y ``BaseModel._add_precomputed_values`` (``:4814-4846``)
# ═══════════════════════════════════════════════════════════════════════════
#
# Hasta aquí ``precompute`` sólo se **validaba**: ``resolve_depends`` avisa y
# lo apaga cuando la cadena de dependencia no lo sostiene
# (``orm/fields.py:2181-2189``), y ``_apply_precompute_block`` rechaza el
# atributo sobre un campo que no es calculado, no es almacenado o es un M2M
# (``orm/fields_nonstored.py:369-406``). Nadie lo **corría**: los nueve campos
# vivos que lo declaran se computaban a mano desde el ``save()`` de su modelo.
#
# Qué hace la fuente, y en qué se traduce aquí
# --------------------------------------------
#
# ``_prepare_create_values`` descarta de ``vals`` los precompute **readonly**
# —para forzar su cómputo aunque el llamador haya pasado un valor— y
# ``_add_precomputed_values`` computa todo precompute cuyo nombre ``fname not
# in vals``, leyéndolo con ``record[fname]`` sobre un ``self.new(vals)``.
#
# Las dos mitades exigen saber **qué nombres dio el llamador**, y ahí está la
# diferencia de este stack: la fuente tiene el diccionario ``vals`` delante;
# una instancia de Django llega al ``pre_save`` con TODOS sus campos poblados
# —los dados y los que tomaron su ``default``— y ya no distingue unos de
# otros. El dato existe un instante antes: ``Model.__init__`` emite
# ``pre_init`` con los ``args`` y ``kwargs`` del llamador **verbatim**
# (``django/db/models/base.py:491``). Eso es ``vals``.
#
# Veredicto por el criterio de las dos categorías: **el stack tiene con qué
# construirlo**. No hay símbolo hecho —Django no tiene la noción de un campo
# que se calcule antes del INSERT— pero las tres primitivas son nativas y
# ninguna viene de fuera del INVENTORY: ``pre_init``/``post_init`` capturan lo
# que el llamador nombró y ``pre_save`` corre antes de ``_do_insert``, las tres
# en ``('django', 'evaluación y control de flujo')``.


#: Los nombres que el llamador pasó a ``__init__``, apilados mientras el
#: constructor corre. Es una **pila** y no una casilla porque ``__init__``
#: anida: un ``default`` que construye otra instancia mete la suya en medio, y
#: con una sola casilla la de fuera se perdería.
#:
#: Si un ``__init__`` revienta entre las dos señales, su entrada se queda en la
#: pila. Eso NO corrompe a la siguiente instancia —``post_init`` saca la
#: **última**, que es la suya— sino que deja una entrada huérfana al fondo: una
#: fuga acotada a un ``frozenset`` por constructor fallido.
_EXPLICIT_VALUES = []


def _explicit_value_names(sender, args, kwargs):
    """Los campos que el llamador nombró al construir la fila.

    Es la traducción de ``fname not in vals`` (``odoo19c: :4842``) al
    constructor de Django, que admite las dos formas de pasar un valor:

    - por palabra clave, que es el caso corriente y el que da ``kwargs``;
    - por **posición**, que Django resuelve contra ``_meta.concrete_fields`` en
      orden (``django/db/models/base.py:496``). Sin esta mitad, una fila
      construida posicionalmente llegaría con el conjunto vacío y todo
      precompute se recalcularía encima del valor que el llamador sí dio.

    Se registran el ``name`` y el ``attname`` porque una FK responde a los dos
    (``company`` y ``company_id``) y el llamador elige cuál usa.
    """
    names = set(kwargs)
    if args:
        for field, _value in zip(sender._meta.concrete_fields, args):
            names.add(field.name)
            names.add(field.attname)
    return frozenset(names)


@receiver(pre_init, dispatch_uid='orm.models.stack_explicit_values')
def _stack_explicit_values(sender, args, kwargs, **_ignored):
    """Apila lo que el llamador nombró, antes de que ``__init__`` lo mezcle."""
    _EXPLICIT_VALUES.append(_explicit_value_names(sender, args, kwargs))


@receiver(post_init, dispatch_uid='orm.models.attach_explicit_values')
def _attach_explicit_values(sender, instance, **_ignored):
    """Cuelga de la instancia lo que su constructor apiló."""
    instance._explicit_values = (
        _EXPLICIT_VALUES.pop() if _EXPLICIT_VALUES else frozenset())


def _precomputable_fields(instance):
    """Los precompute de este modelo que hay que calcular en esta fila.

    ≙ el ``precomputable`` de ``_add_precomputed_values`` (``:4820``) ya
    cruzado con las dos exclusiones que la fuente reparte en dos sitios:

    - el precompute **readonly** se computa siempre, porque la fuente lo saca
      de ``vals`` antes de mirarlo (``:4786-4791``);
    - el precompute **escribible** respeta el valor que el llamador dio, que es
      el ``fname not in vals`` de ``:4842``.
    """
    given = getattr(instance, '_explicit_values', None) or frozenset()
    pending = {}
    for name, field in model_field_registry(type(instance)).items():
        if not getattr(field, 'precompute', False):
            continue
        if not getattr(field, 'readonly', False):
            if name in given or getattr(field, 'attname', name) in given:
                continue
        pending[name] = field
    return pending


def _run_precompute_field(instance, name, pending, done, chain):
    """Corre el cómputo de ``name``, y antes el de los precompute que lee.

    **Esto es la mitad que la fuente obtiene gratis y aquí hay que construir.**
    Allá el pase es perezoso: ``record[fname]`` sobre un registro virtual
    dispara el cómputo *al leerlo*, así que un cómputo que lee otro precompute
    lo resuelve por el camino y el orden de declaración da igual.

    Aquí el cómputo se invoca, no se lee, y el orden de declaración **no** es el
    de dependencia. Medido en el árbol: ``SaleOrderLine`` declara
    ``price_reduce_taxexcl`` (``:309``) y ``price_reduce_taxinc`` (``:317``)
    ANTES de ``price_subtotal`` (``:417``), ``price_tax`` (``:425``) y
    ``price_total`` (``:433``), y sus dos cómputos leen justamente lo que
    ``_compute_amount`` escribe. Un pase en orden de declaración los calcularía
    contra el ``default``.

    Así que la pereza se hace explícita: antes de correr el cómputo de un campo
    se corren los de los precompute del **mismo modelo** que su ``@api.depends``
    nombra. ``chain`` corta el ciclo —un campo recursivo se nombra a sí mismo— y
    ``done`` lleva los **métodos** ya invocados, no los campos: ``_compute_amount``
    escribe tres y correrlo tres veces repetiría su efecto.
    """
    field = pending[name]
    if field.compute in done:
        return
    chain = chain + (name,)
    for dotted in registry.field_depends[field]:
        head = dotted.split('.')[0]
        other = pending.get(head)
        if other is not None and head not in chain and other.compute not in done:
            _run_precompute_field(instance, head, pending, done, chain)
    done.add(field.compute)
    getattr(instance, field.compute)()


def _add_precomputed_values(self):
    """Calcula los precompute que faltan, antes de que la fila se inserte.

    ≙ ``BaseModel._add_precomputed_values`` (``odoo19c: :4814-4846``).

    **Tres divergencias de mecanismo, las tres con el mismo resultado
    observable:**

    1. *El valor no se copia a un diccionario.* La fuente escribe
       ``vals[fname] = field.convert_to_write(record[fname], self)`` porque su
       INSERT se arma desde ``vals``. Aquí el cómputo asigna sobre la propia
       instancia, que es de donde Django arma el INSERT: el paso de copia no
       tiene destino.
    2. *Sin registro virtual.* La fuente computa sobre un ``self.new(vals)``
       —un registro sin fila— para no ensuciar el caché con el valor de un
       registro que aún no existe. Aquí el cómputo se invoca **directamente**
       sobre la instancia, no por ``compute_value``, por la misma razón medida
       al revés: ``record_ids`` de una fila sin guardar da ``None``, y
       ``_update_cache`` escribiría ``field_cache[None]``, que la siguiente
       fila sin guardar leería como suyo.
    3. *Sin* ``__precomputed__``. La fuente marca los campos que precomputó
       para que ``create`` **no dispare su** ``inverse`` (``:4664`` y
       ``:4681``): el valor lo puso el cómputo, no el llamador, así que
       invertirlo sería escribir hacia atrás algo que nadie pidió. Aquí ese
       riesgo no existe por construcción — el único que llama a
       ``determine_inverse`` es :meth:`write`, sobre los nombres que el llamador
       le pasó (:meth:`_group_written_inverses`), y este pase no pasa por ahí.
    """
    pending = _precomputable_fields(self)
    if not pending:
        return
    done = set()
    for name in list(pending):
        _run_precompute_field(self, name, pending, done, ())


@receiver(pre_save, dispatch_uid='orm.models.run_precompute')
def _run_precompute(sender, instance, raw=False, **_ignored):
    """Dispara el pase de precompute justo antes del INSERT.

    ``pre_save`` corre antes de ``_save_table`` —y por tanto antes de
    ``_do_insert``— así que el valor calculado viaja en la MISMA sentencia
    (``django/db/models/base.py:946``). Ése es el punto entero de
    ``precompute``, y la fuente lo dice: *"computed stored fields with a column
    have to be computed before create s.t. required and constraints can be
    applied on those fields"* (``:4841``).

    Dos salidas tempranas: ``raw`` es el cargador de fixtures, que escribe la
    fila tal cual viene; y una fila que ya existe es un UPDATE, donde el
    recálculo lo gobierna el motor de ``modified()``, no este pase.
    """
    if raw or not instance._state.adding:
        return
    _add_precomputed_values(instance)


def _validate_fields(self, field_names, excluded_names=()):
    """Corre las restricciones que nombran alguno de los campos tocados.

    ≙ ``_validate_fields`` (``odoo19c: odoo/orm/models.py:1252-1268``).
    Docstring de la fuente, verbatim: *"Invoke the constraint methods for which
    at least one field name is in ``field_names`` and none is in
    ``excluded_names``"*.

    **Los dos filtros son de la fuente y los dos importan.** El primero acota:
    una restriccion que no nombra ningun campo tocado no tiene por que correr.
    El segundo veta: basta con que UNO de los nombres que la restriccion
    declara este excluido para que no corra — el llamador excluye lo que sabe
    que esta a medio escribir, y una restriccion que lo mire daria un falso
    negativo.

    **Divergencia de mecanismo, no de contrato.** Alla el mapa de metodos es
    una ``@property`` memoizada en la clase (``:519-546``) y aqui es el
    colector :data:`~orm.registry.constraint_methods`, por la razon que su
    docstring declara. Y ``self.sudo()`` es alla un recordset elevado; aqui la
    elevacion es un bloque de contexto (``orm.environments.sudo``), asi que se
    envuelve la corrida en vez de recibir otro receptor.

    El comentario de la fuente sobre por que se eleva se conserva porque es la
    razon y no el como: *"run constrains just as sudoed computed-stored fields
    — see Field.compute_value()"*.
    """
    methods = registry.constraint_methods(type(self))
    if not methods:
        return
    field_names = set(field_names)
    excluded_names = set(excluded_names)
    with elevate_privileges():
        for check in methods:
            declared = check._constrains
            if (not field_names.isdisjoint(declared)
                    and excluded_names.isdisjoint(declared)):
                check(self)


def _run_ondelete_checks(self, at_uninstall=False):
    """Corre las comprobaciones marcadas antes de borrar la fila.

    ≙ el bloque de ``unlink`` que recorre ``self._ondelete_methods``
    (``odoo19c: odoo/orm/models.py:4205-4208``), con su comentario verbatim:
    *"func._ondelete is True if it should be called during uninstallation"*.

    El marcador NO es una bandera de presencia: guarda el ``at_uninstall`` que
    el decorador recibio. Un metodo con ``at_uninstall=False`` corre en el
    borrado normal y **se salta** cuando quien borra es la desinstalacion de un
    modulo — porque entonces todo lo que el modulo declaro se va de todas
    formas, y un ``UserError`` de negocio ahi solo dejaria la base a medias.
    Ese razonamiento es el del docstring de ``@api.ondelete``
    (``odoo19c: odoo/orm/decorators.py:139-149``).

    **Divergencia de mecanismo:** alla la bandera de desinstalacion viaja en el
    contexto (``MODULE_UNINSTALL_FLAG``); aqui es el argumento de esta llamada,
    porque quien borra es ``Model.delete()`` de Django y no hay contexto de
    recordset que consultar.
    """
    for check in registry.ondelete_methods(type(self)):
        if check._ondelete or not at_uninstall:
            check(self)


@receiver(pre_delete, dispatch_uid='orm.models.run_ondelete_checks')
def _run_ondelete_on_delete(sender, instance, **_ignored):
    """Dispara las comprobaciones marcadas justo antes del DELETE.

    ``pre_delete`` corre dentro de la transaccion del borrado y antes de la
    sentencia, que es donde la fuente las corre: un ``UserError`` levantado
    aqui deja la fila intacta.

    Su equivalente de ``MODULE_UNINSTALL_FLAG`` es la clave de contexto
    ``module_uninstall``, que el desinstalador activa. Con el contexto vacio
    —el caso normal— vale ``False`` y corren todas.
    """
    if not registry.ondelete_methods(sender):
        return
    _run_ondelete_checks(
        instance, at_uninstall=bool(get_context().get('module_uninstall')))


Model._add_precomputed_values = _add_precomputed_values
Model._validate_fields = _validate_fields
Model._run_ondelete_checks = _run_ondelete_checks


class RecordCache(collections.abc.Mapping):
    """Los campos de una fila que están en caché, por nombre.

    ≙ ``RecordCache`` (``odoo19c: odoo/orm/models.py:7012-7043``). Docstring de
    la fuente: *"A mapping from field names to values, to read the cache of a
    record."* Es la vista que ``record._cache`` devuelve allá.

    **Dos divergencias de mecanismo, ninguna de contrato.**

    1. *El entorno es ambiente.* La fuente lee ``record.env`` —un ``__slots__``
       del recordset (``:362``)—; aquí una fila es una instancia de Django y no
       lleva entorno, así que se toma el de la transacción en curso con
       :func:`~orm.environments.env`. Es la misma adaptación que hace el resto
       de ``src/orm``.
    2. *La fila ya es una sola.* La fuente abre con ``assert len(record) == 1``
       porque allá recibe un recordset que podría traer N. Aquí el tipo del
       argumento **es** el registro único, así que ese assert no tiene qué
       comprobar; se conserva su intención comprobando que no llegue una
       colección.

    ``_fields`` sí existe con el contrato de la fuente —el registro completo
    del modelo, no sólo sus columnas (tareas #215 y #301)—, así que el
    recorrido de :meth:`__iter__` es el mismo.
    """

    __slots__ = ['_record']

    def __init__(self, record):
        assert not isinstance(record, (list, tuple, set, QuerySet)), (
            "Unexpected RecordCache(%s)" % (record,))
        self._record = record

    def __contains__(self, name):
        """¿Tiene la fila un valor en caché para el campo ``name``?"""
        record = self._record
        field = record._fields[name]
        return record.id in field._get_cache(env())

    def __getitem__(self, name):
        """El valor en caché del campo ``name`` para la fila."""
        record = self._record
        field = record._fields[name]
        return field._get_cache(env())[record.id]

    def __iter__(self):
        """Los nombres de campo que tienen valor en caché.

        **La guarda de ``_get_cache`` es la tercera divergencia**, y es del
        contrato de ``_fields``, no de esta clase. Allá el mapa sólo contiene
        objetos ``Field``, y todos tienen caché. Aquí lo provee ``_meta``, que
        incluye además los descriptores de relación **inversa** de Django
        —``ManyToOneRel``, ``OneToOneRel``, ``ManyToManyRel``—, que no son
        campos y no tienen dónde cachear: la fuente los modela como
        ``One2many``, que allá sí es un ``Field``.

        *Métrica:* atributos de ``res.partner`` en ``_fields`` con
        ``_get_cache``: **86 de 128**; los 42 restantes son 36 ``ManyToOneRel``,
        4 ``OneToOneRel`` y 2 ``ManyToManyRel``.
        *Ciega a:* un campo que tuviera caché y no la expusiera con ese nombre.
        La guarda se retira cuando el uno-a-muchos sea un campo propio con su
        caché — tareas **#243** y **#244**.
        """
        record = self._record
        id_ = record.id
        environment = env()
        for name, field in record._fields.items():
            if not hasattr(field, '_get_cache'):
                continue
            if id_ in field._get_cache(environment):
                yield name

    def __len__(self):
        """Cuántos campos tienen valor en caché."""
        return sum(1 for name in self)


class BaseModel(Model):
    """El recordset — ≙ ``BaseModel`` (``odoo19c: odoo/orm/models.py:334-7004``).

    Docstring de la fuente, verbatim en lo que gobierna: *"Every model instance
    is a 'recordset', i.e., an ordered collection of records of the model.
    Recordsets are returned by methods like* :meth:`~.browse`, :meth:`~.search`
    *, or field accesses. Records have no explicit representation: a record is
    represented as a recordset of one record."*

    **Es una base abstracta de Django, y los modelos portados DERIVAN de ella**
    (decisión del ejecutor sobre las tres formas candidatas de
    :ref:`h-api-1083`). Eso fija tres cosas que no son elección de estilo:

    1. ``__slots__`` se declara **verbatim**. Medido
       (``scripts/workbench/basemodel-id-access-20260911T035612/outputs/abstract_base.txt``):
       ``ModelBase`` lo admite sobre una base abstracta, el modelo concreto
       conserva su ``__dict__`` —así que los tres nombres quedan como
       descriptores de ranura sobre la base y las instancias siguen admitiendo
       atributos— y una ranura sin asignar levanta ``AttributeError``, que es
       la conducta que distingue una fila de Django de un recordset.
    2. ``_abstract = True`` lo **hereda** el modelo concreto. En la fuente nadie
       deriva de ``BaseModel`` directamente: ``Model(AbstractModel)``
       (``odoo19c: :7049``) invierte ``_abstract``/``_auto``/``_register``. Aquí
       el registrante sin tabla es :class:`AbstractModel` de este mismo módulo,
       que **no se toca** (su objeción de ``registrants_without_table`` está
       medida y la gobierna la tarea **#329**).
    3. El recordset **no se construye con** ``Model.__init__``. Ver
       :meth:`_from_ids`.
    4. **Una fila que construye Django NO lleva la terna, y seis de los ocho
       dunder portados revientan sobre ella.** Medido sobre
       ``RecordsetProbe(id=7, label='x')``: ``hasattr(row, '_ids')`` es
       ``False``, y ``bool`` · ``len`` · ``repr`` · ``hash`` · ``str`` ·
       ``iter`` levantan ``AttributeError: … has no attribute '_ids'``. Sólo
       ``int`` y ``id`` sobreviven, los dos por el relevo de
       :class:`IdFromIds` al descriptor original. Es la consecuencia más
       afilada de **TASK-API-0402**: mientras no aterrice, derivar de esta base
       es nominal para todo lo que no venga de :meth:`browse`.

    **Cobertura del porte, re-derivada contra el banco** — la medición vive en
    ``scripts/workbench/basemodel-contract-20260911T030334/outputs/coverage_derived.txt``.
    Son **dos ejes**, y mezclarlos fue el defecto de la primera redacción:

    *Métodos.* El censo del banco cuenta **194 declaraciones**, no 194 nombres:
    ``__getitem__``, ``grouped`` y ``mapped`` van declarados dos veces
    (``@overload``), así que el contrato son **188 nombres únicos**. Este pase
    porta **33 de esos 188**, y declara **3 fuera del contrato**:
    :meth:`__str__` (divergencia forzada), :meth:`_from_ids` (divergencia de
    mecanismo) y :meth:`_read_field` (la guarda de tamaño, extraída).

    Los **155 sin portar**, por familia —el desglose **suma**, que es lo que la
    primera redacción no hacía—: ``read_group`` 16 · ``cache/recompute`` 16 ·
    ``CRUD`` 16 · ``schema/SQL`` 14 · ``access/check`` 11 · ``search/fetch`` 9 ·
    ``parent_store`` 8 · ``import/export`` 8 · ``constraints`` 7 ·
    ``properties`` 6 · ``traducción`` 5 · ``name_search`` 5 · ``onchange`` 4 ·
    ``otros`` 30. Dos que este núcleo SÍ necesita están bloqueados y con sucesor
    acuñado: :meth:`fetch` (**TASK-API-0399**) y ``_sorted_order_to_function``
    (**TASK-API-0400**).

    *Atributos de clase.* La referencia declara **31** (3 ``ast.Assign`` + 28
    ``ast.AnnAssign``); aquí van **29 verbatim**. Los dos ausentes están
    declarados, no omitidos: ``id`` se porta como el descriptor
    :class:`IdFromIds` que instala ``class_prepared``, y ``display_name`` es un
    campo, fuera del alcance de este pase. El censo del banco publica
    ``atributos de clase: 1`` porque su recorrido sólo visita ``ast.Assign`` —
    ceguera medida, con sucesor en el board **#320**.

    Licencia de la fuente: **LGPL-3** (``odoo19c``), así que el mecanismo es
    copia + adaptación con atribución — no reimplementación.
    """

    __slots__ = ['env', '_ids', '_prefetch_ids']

    #: **Divergencia de mecanismo.** La fuente cuelga el registro completo de la
    #: clase (``pool: Registry``, ``:362``) porque su metaclase lo construye.
    #: Aquí el registro de Django vive en ``_meta.apps`` y el nuestro en
    #: :mod:`orm.registry`; la anotación se conserva para que el nombre exista
    #: en la cabecera, sin valor que la falsee.
    pool: 'registry.Registry'

    _fields__: dict
    #: ≙ ``BaseModel._fields`` (``:368``). **No se duplica el mecanismo**: es el
    #: mismo :class:`~orm.utils.FieldRegistryDescriptor` que
    #: :class:`FieldSqlMixin` ya declara en ``:1612``, respaldado por
    #: :func:`~orm.utils.model_field_registry`. Aquí es además el sitio fiel:
    #: la fuente lo declara en ``BaseModel``, no en un mixin.
    _fields = FieldRegistryDescriptor()

    _auto: bool = False
    """Whether a database table should be created."""
    _register: bool = False           #: registry visibility
    _abstract: bool = True
    """ Whether the model is *abstract*. """
    _transient: bool = False
    """ Whether the model is *transient*. """

    _name: str = None                   #: the model name (in dot-notation, module namespace)
    _description: str | None = None     #: the model's informal name
    _module: str | None = None          #: the model's module (in the Odoo sense)
    _custom: bool = False               #: should be True for custom models only

    _inherit: str | list | tuple = ()
    """Python-inherited models."""
    _inherits: ReadonlyDict = ReadonlyDict({})
    """dictionary {'parent_model': 'm2o_field'}; ``frozendict`` allá, ≙ :class:`~tools.misc.ReadonlyDict`."""
    _table: str = ''                 #: SQL table name used by model if :attr:`_auto`
    _table_query: SQL | str | None = None  #: SQL expression of the table's content (optional)
    _table_objects: ReadonlyDict = ReadonlyDict({})  #: SQL/Table objects
    _inherit_children: OrderedSet

    _rec_name: str | None = None                  #: field to use for labeling records, default: ``name``
    _rec_names_search: list | None = None          #: fields to consider in ``name_search``
    _order: str = 'id'                            #: default order field for searching results
    _parent_name: str = 'parent_id'               #: the many2one field used as parent field
    _parent_store: bool = False
    """set to True to compute parent_path field."""
    _active_name: str | None = None
    """field to use for active records."""
    _fold_name: str = 'fold'         #: field to determine folded groups in kanban views

    _translate: bool = True           # False disables translations export for this model
    _check_company_auto: bool = False
    """On write and create, call ``_check_company``."""
    _allow_sudo_commands: bool = True
    """Allow One2many and Many2many Commands targeting this model under ``sudo()``."""
    _depends: ReadonlyDict = ReadonlyDict({})
    """dependencies of models backed up by SQL views ``{model_name: field_names}``."""

    #: ``id = Id()`` (``:472``) **se porta como descriptor instalado en la clase
    #: concreta**, no como asignación en este cuerpo: ``ModelBase`` pone su
    #: propio ``DeferredAttribute`` sobre ``id`` al preparar la subclase y
    #: sombrea cualquier descriptor de la base — medido en
    #: ``outputs/id_descriptor.txt``. El porte es :class:`IdFromIds` más el
    #: receptor de ``class_prepared`` de más abajo, que lo instala DESPUÉS.
    #: Contraparte: ``odoo19c: odoo/orm/fields_misc.py:102-114``.
    #:
    #: ``display_name = Char(..., compute='_compute_display_name')`` (``:473``)
    #: es un **campo**, no parte de este núcleo: entra con el porte de campos
    #: calculados.

    class Meta:
        abstract = True

    # === construcción =====================================================

    @classmethod
    def _from_ids(cls, env, ids, prefetch_ids):
        """Instala la terna del recordset — ≙ ``BaseModel.__init__`` (``:5871``).

        **Divergencia de mecanismo, medida y forzada.** La fuente construye con
        ``self.__class__(self.env, ids, ids)`` (``browse``, ``:5897``) y **no
        tiene** ``_browse``: medido, 0 declaraciones y 0 llamadas en ``odoo19c``
        y ``odoo18c``. Aquí ``__init__`` está ocupado posicionalmente por
        Django, que construye una fila con ``new = cls(*values)``
        (``django/db/models/base.py:604``); usar la firma de la fuente
        rompería la construcción de filas.

        Por eso el recordset se construye **sin pasar por** ``Model.__init__``:
        ``object.__new__`` más las tres ranuras, y ``_state`` a mano porque es
        lo único que ``Model.__init__`` deja y que el resto de Django lee.
        """
        record = object.__new__(cls)
        record._state = ModelState()
        record.env = env
        record._ids = ids
        record._prefetch_ids = prefetch_ids
        return record

    @api.private
    def browse(self, ids=()):
        """Return a recordset for the ids provided as parameter in the current
        environment.

        ≙ ``:5882``. El ``self.__class__(self.env, ids, ids)`` de la fuente es
        aquí :meth:`_from_ids` por la divergencia declarada en ese método.
        """
        if not ids:
            ids = ()
        elif ids.__class__ is int:
            ids = (ids,)
        else:
            ids = tuple(ids)
        return self._from_ids(self.env, ids, ids)

    # === identidad y tamaño ===============================================

    @property
    def ids(self):
        """ Return the list of actual record ids corresponding to ``self``. — ≙ ``:5904`` """
        if all(self._ids):
            return list(self._ids)  # already real records
        return list(OriginIds(self._ids))

    @api.private
    def ensure_one(self):
        """Verify that the current recordset holds a single record. — ≙ ``:5930``

        :raise ValueError: ``len(self) != 1``
        """
        try:
            # unpack to ensure there is only one value is faster than len when true and
            # has a significant impact as this check is largely called
            _id, = self._ids
            return self
        except ValueError:
            raise ValueError("Expected singleton: %s" % self)

    def __bool__(self):
        """ Test whether ``self`` is nonempty. — ≙ ``:6475`` """
        return True if self._ids else False  # fast version of bool(self._ids)

    def __len__(self):
        """ Return the size of ``self``. — ≙ ``:6479`` """
        return len(self._ids)

    def __int__(self):
        """ ≙ ``:6656`` """
        return self.id or 0

    def __repr__(self):
        """ ≙ ``:6659`` """
        return f"{self._name}{self._ids!r}"

    def __str__(self):
        """Rutea a :meth:`__repr__`.

        **Divergencia forzada por Django, no elección.** La fuente no declara
        ``__str__``: ahí ``str()`` cae en ``__repr__`` por el default de
        ``object``. Aquí ``Model.__str__`` existe y devuelve
        ``'%s object (%s)' % (self.__class__.__name__, self.pk)``, que lee
        ``self.pk`` → el descriptor :class:`IdFromIds` → ``ValueError`` sobre un
        recordset de N. Sin este override, ``ensure_one`` no puede interpolar
        ``%s`` de su propio mensaje.
        """
        return self.__repr__()

    def __hash__(self):
        """ ≙ ``:6662`` """
        return hash((self._name, frozenset(self._ids)))

    def __eq__(self, other):
        """ Test whether two recordsets are equivalent (up to reordering). — ≙ ``:6608`` """
        try:
            return self._name == other._name and set(self._ids) == set(other._ids)
        except AttributeError:
            if other:
                warnings.warn(
                    f"unsupported operand type(s) for \"==\": '{self._name}()' == '{other!r}'",
                    stacklevel=2)
        return NotImplemented

    def __lt__(self, other):
        """ ≙ ``:6617`` """
        try:
            if self._name == other._name:
                return set(self._ids) < set(other._ids)
        except AttributeError:
            # silent OK because el operando no es un recordset: la fuente cae
            # deliberadamente a ``NotImplemented`` para que Python pruebe el
            # reflejado y levante ``TypeError`` con su mensaje propio.
            pass
        return NotImplemented




    # === recorrido y lectura ==============================================

    def __iter__(self):
        """ Return an iterator over ``self``. — ≙ ``:6483`` """
        ids = self._ids
        size = len(ids)
        if size <= 1:
            # detect and handle small recordsets (single `1f`)
            # early return if no records and avoid allocation if we have a one
            if size == 1:
                yield self
            return
        env_ = self.env
        prefetch_ids = self._prefetch_ids
        if size > PREFETCH_MAX and prefetch_ids is ids:
            for sub_ids in split_every(PREFETCH_MAX, ids):
                for id_ in sub_ids:
                    yield self._from_ids(env_, (id_,), sub_ids)
        else:
            for id_ in ids:
                yield self._from_ids(env_, (id_,), prefetch_ids)

    def __contains__(self, item):
        """ Test whether ``item`` (record or field name) is an element of ``self``. — ≙ ``:6525`` """
        try:
            if self._name == item._name:
                return len(item) == 1 and item.id in self._ids
            raise TypeError(f"inconsistent models in: {item} in {self}")
        except AttributeError:
            if isinstance(item, str):
                return item in self._fields
            raise TypeError(f"unsupported operand types in: {item!r} in {self}")

    def __getitem__(self, key):
        """ If ``key`` is an integer or a slice, return the corresponding record
            selection as an instance (attached to ``self.env``).
            Otherwise read the field ``key`` of the first record in ``self``. — ≙ ``:6674``
        """
        if isinstance(key, str):
            # important: one must call the field's getter
            return self._read_field(self._fields[key])
        elif isinstance(key, slice):
            return self.browse(self._ids[key])
        else:
            return self.browse((self._ids[key],))

    def _read_field(self, field):
        """Lee ``field`` sobre ``self`` aplicando la guarda de tamaño de la fuente.

        **Es el porte de la guarda de** ``Field.__get__``
        (``odoo19c: odoo/orm/fields.py:1641-1661``), verbatim en su decisión::

            record_len = len(record._ids)
            if record_len != 1:
                if record_len:
                    record.ensure_one()
                    assert False, "unreachable"
                value = self.convert_to_cache(False, record, validate=False)
                return self.convert_to_record(value, record)

        **Divergencia de mecanismo, medida.** La fuente escribe
        ``self._fields[key].__get__(self)`` porque allá el mapa contiene objetos
        ``Field`` **suyos**, que son descriptores. Aquí ``_fields`` devuelve
        ``Field`` de Django, que **no tiene** ``__get__``, y
        :class:`~orm.fields.FieldDescriptor` sólo se instala donde el campo
        declara ``compute`` —medido 42.6 ns contra 132.9 ns (**3.12×**) si se
        hiciera descriptor de datos en todos—. Así que el campo se resuelve a su
        descriptor por el nombre de atributo y se le pide su ``__get__``.

        El valor del recordset vacío es ``falsy_value`` del campo, que es
        exactamente lo que ``convert_to_cache(False, …)`` produce allá; su
        instalación por clase de campo está en ``orm/fields.py:186-211``.

        **Lo que este método no cierra:** la guarda sólo actúa por esta vía y
        por :meth:`__getitem__`. El acceso llano ``rs.label`` sobre un recordset
        de N sigue cayendo en el ``DeferredAttribute`` de Django, que ignora
        ``_ids``. Extenderlo cuesta los 3.12× medidos, así que es decisión del
        ejecutor: tarea **TASK-API-0401**. El docstring de
        ``orm/fields.py:1236`` declara hoy que la rama ``record_len != 1`` *"no
        tiene receptor"*; con este núcleo sí lo tiene, y esa nota queda rancia
        (misma tarea).
        """
        size = len(self._ids)
        if size != 1:
            if size:
                self.ensure_one()
                raise AssertionError("unreachable")
            return getattr(field, 'falsy_value', None)
        name = getattr(field, 'attname', None) or field.name
        descriptor = getattr(type(self), name, None)
        if descriptor is None or not hasattr(descriptor, '__get__'):
            return getattr(self, name)
        return descriptor.__get__(self, type(self))

    @property
    def _cache(self):
        """ Return the cache of ``self``, mapping field names to values. — ≙ ``:6703`` """
        return RecordCache(self)

    @property
    def _origin(self):
        """ Return the actual records corresponding to ``self``. — ≙ ``:6462`` """
        if all(self._ids):
            return self  # already real records
        ids = tuple(OriginIds(self._ids))
        prefetch_ids = OriginIds(self._prefetch_ids)
        return self._from_ids(self.env, ids, prefetch_ids)

    # === derivación de entorno ============================================

    @api.private
    def with_env(self, env):
        """Return a new version of this recordset attached to the provided environment.

        ≙ ``:5944``. The returned recordset has the same prefetch object as ``self``.
        """
        return self._from_ids(env, self._ids, self._prefetch_ids)

    @api.private
    def sudo(self, flag=True):
        """ Return a new version of this recordset with superuser mode enabled or
        disabled, depending on `flag`. — ≙ ``:5953``
        """
        assert isinstance(flag, bool)
        if flag == self.env.su:
            return self
        return self.with_env(self.env(su=flag))

    @api.private
    def with_user(self, user):
        """ Return a new version of this recordset attached to the given user. — ≙ ``:5980`` """
        if not user:
            return self
        return self.with_env(self.env(user=user, su=False))

    @api.private
    def with_company(self, company):
        """ Return a new version of this recordset with a modified context. — ≙ ``:5990`` """
        if not company:
            # With company = None/False/0/[]/empty recordset: keep current environment
            return self

        company_id = int(company)
        allowed_company_ids = self.env.context.get('allowed_company_ids') or []
        if allowed_company_ids and company_id == allowed_company_ids[0]:
            return self
        # Copy the allowed_company_ids list
        # to avoid modifying the context of the current environment.
        allowed_company_ids = list(allowed_company_ids)
        if company_id in allowed_company_ids:
            allowed_company_ids.remove(company_id)
        allowed_company_ids.insert(0, company_id)

        return self.with_context(allowed_company_ids=allowed_company_ids)

    @api.private
    def with_context(self, ctx=None, /, **overrides):
        """ Return a new version of this recordset attached to an extended context. — ≙ ``:6020``

        La fuente avisa aquí de dos claves de contexto retiradas en 19
        (``force_company``, ``company``); se portan los dos avisos verbatim.
        """
        context = dict(ctx if ctx is not None else self.env.context, **overrides)
        if 'force_company' in context:
            warnings.warn(
                "Since 19.0, context key 'force_company' is no longer supported. "
                "Use with_company(company) instead.",
                DeprecationWarning,
            )
        if 'company' in context:
            warnings.warn(
                "Context key 'company' is not recommended, because "
                "of its special meaning in @depends_context.",
            )
        if 'allowed_company_ids' not in context and 'allowed_company_ids' in self.env.context:
            # Force 'allowed_company_ids' to be kept when context is overridden
            # without 'allowed_company_ids'
            context['allowed_company_ids'] = self.env.context['allowed_company_ids']
        return self.with_env(self.env(context=context))

    @api.private
    def with_prefetch(self, prefetch_ids=None):
        """ Return a new version of this recordset that uses the given prefetch ids,
        or ``self``'s ids if not given. — ≙ ``:6057``
        """
        if prefetch_ids is None:
            prefetch_ids = self._ids
        return self._from_ids(self.env, self._ids, prefetch_ids)

    # === operaciones de conjunto ==========================================

    def __add__(self, other):
        """ Return the concatenation of two recordsets. — ≙ ``:6544`` """
        return self.concat(other)

    @api.private
    def concat(self, *args):
        """ Return the concatenation of ``self`` with all the arguments (in
            linear time complexity). — ≙ ``:6548``
        """
        ids = list(self._ids)
        for arg in args:
            try:
                if arg._name != self._name:
                    raise TypeError(f"inconsistent models in: {self} + {arg}")
                ids.extend(arg._ids)
            except AttributeError:
                raise TypeError(f"unsupported operand types in: {self} + {arg!r}")
        return self.browse(ids)

    def __sub__(self, other):
        """ Return the recordset of all the records in ``self`` that are not in
            ``other``. Note that recordset order is preserved. — ≙ ``:6563``
        """
        try:
            if self._name != other._name:
                raise TypeError(f"inconsistent models in: {self} - {other}")
            other_ids = set(other._ids)
            return self.browse(id_ for id_ in self._ids if id_ not in other_ids)
        except AttributeError:
            raise TypeError(f"unsupported operand types in: {self} - {other!r}")

    def __and__(self, other):
        """ Return the intersection of two recordsets.
            Note that first occurrence order is preserved. — ≙ ``:6575``
        """
        try:
            if self._name != other._name:
                raise TypeError(f"inconsistent models in: {self} & {other}")
            other_ids = set(other._ids)
            return self.browse(OrderedSet(id_ for id_ in self._ids if id_ in other_ids))
        except AttributeError:
            raise TypeError(f"unsupported operand types in: {self} & {other!r}")

    def __or__(self, other):
        """ Return the union of two recordsets.
            Note that first occurrence order is preserved. — ≙ ``:6587``
        """
        return self.union(other)

    @api.private
    def union(self, *args):
        """ Return the union of ``self`` with all the arguments (in linear time
            complexity, with first occurrence order preserved). — ≙ ``:6593``
        """
        ids = list(self._ids)
        for arg in args:
            try:
                if arg._name != self._name:
                    raise TypeError(f"inconsistent models in: {self} | {arg}")
                ids.extend(arg._ids)
            except AttributeError:
                raise TypeError(f"unsupported operand types in: {self} | {arg!r}")
        return self.browse(OrderedSet(ids))

    # === proyección =======================================================

    @api.private
    def mapped(self, func):
        """Apply ``func`` on all records in ``self``, and return the result as a
        list or a recordset (if ``func`` return recordsets). — ≙ ``:6127``

        Dos divergencias, las dos con sucesor acuñado y ninguna de contrato:

        * ``records.fetch([field_name])`` sobre ``PREFETCH_MAX`` — ``fetch`` no
          está portado (``odoo19c: :3775-3818``). Tarea **TASK-API-0399**.
        * la rama **relacional** devuelve allá ``getter(records)`` con el
          recordset de N, que ``_Relational.__get__``
          (``odoo19c: odoo/orm/fields_relational.py:42``) resuelve por su cuenta
          — no cae en la guarda de tamaño. Aquí el comodelo sólo puede dar un
          recordset si él mismo deriva de :class:`BaseModel`; mientras las filas
          que Django construye no lleven la terna, la unión no se puede
          expresar. Tarea **TASK-API-0402**.
        """
        if not func:
            return self                 # support for an empty path of fields

        if isinstance(func, str):
            # special case: sequence of field names
            *rel_field_names, field_name = func.split('.')
            records = self
            for rel_field_name in rel_field_names:
                records = records[rel_field_name]
            if len(records) > PREFETCH_MAX:
                raise NotImplementedError(
                    "mapped() sobre PREFETCH_MAX exige BaseModel.fetch, sin portar "
                    "(odoo19c: odoo/orm/models.py:3775-3818) — TASK-API-0399")
            field = records._fields[field_name]
            if field.relational:
                # La guarda NO puede ser ``issubclass(comodel, BaseModel)``: mide
                # la CLASE y el defecto esta en la INSTANCIA. El descriptor de
                # clave foranea de Django devuelve una fila construida por
                # ``Model.from_db``, que no lleva ``_ids`` ni aunque su clase
                # derive de esta base — asi que ``value._ids`` daria
                # ``AttributeError`` en vez de este rechazo. Se rehusa sin
                # condicion hasta que TASK-API-0402 haga que esas filas lleven
                # la terna.
                raise NotImplementedError(
                    f"mapped() relacional sobre {field.name!r} exige que la fila que "
                    "Django construye lleve la terna del recordset — tarea "
                    "TASK-API-0402")
            return [record._read_field(field) for record in records]

        if self:
            vals = [func(rec) for rec in self]
            if isinstance(vals[0], BaseModel):
                return vals[0].union(*vals)
            return vals
        else:
            # we want to follow-up the comodel from the function
            # so we pass an empty recordset
            vals = func(self)
            return vals if isinstance(vals, BaseModel) else []

    @api.private
    def filtered(self, func):
        """Return the records in ``self`` satisfying ``func``. — ≙ ``:6185``

        La rama de nombre de campo suelto lee con :meth:`_read_field` en vez de
        ``self._fields[func].__get__``, por la divergencia declarada allí.
        """
        if not func:
            # align with mapped()
            return self
        if callable(func):
            # normal function
            pass
        elif isinstance(func, str):
            if '.' in func:
                return self.browse(rec_id for rec_id, rec in zip(self._ids, self) if any(rec.mapped(func)))
            # avoid costly mapped
            field = self._fields[func]
            return self.browse(rec_id for rec_id, rec in zip(self._ids, self)
                               if rec._read_field(field))
        elif isinstance(func, Domain):
            return self.filtered_domain(func)
        else:
            raise TypeError(f"Invalid function {func!r} to filter on {self._name}")
        return self.browse(rec_id for rec_id, rec in zip(self._ids, self) if func(rec))

    @api.private
    def filtered_domain(self, domain):
        """Return the records in ``self`` satisfying the domain and keeping the same order. — ≙ ``:6251`` """
        if not self or not domain:
            return self
        predicate = Domain(domain)._as_predicate(self)
        return self.browse(rec_id for rec_id, rec in zip(self._ids, self) if predicate(rec))

    @api.private
    def grouped(self, key):
        """Eagerly groups the records of ``self`` by the ``key``, returning a
        dict from the ``key``'s result to recordsets. All the resulting
        recordsets are guaranteed to be part of the same prefetch-set. — ≙ ``:6225``
        """
        if isinstance(key, str):
            key = itemgetter(key)

        collator = collections.defaultdict(list)
        for record in self:
            collator[key(record)].extend(record._ids)

        browse = functools.partial(type(self)._from_ids, self.env,
                                   prefetch_ids=self._prefetch_ids)
        return {key: browse(tuple(ids)) for key, ids in collator.items()}

    @api.private
    def sorted(self, key=None, reverse=False):
        """Return the recordset ``self`` ordered by ``key``. — ≙ ``:6262``

        La rama de cadena y la de ``None`` exigen ``_sorted_order_to_function``
        (``odoo19c: :6294-6344``), sin portar — tarea **TASK-API-0400**.
        """
        if len(self) < 2:
            return self
        if key is None or isinstance(key, str):
            raise NotImplementedError(
                "sorted() por cadena o por _order exige _sorted_order_to_function, "
                "sin portar (odoo19c: odoo/orm/models.py:6294-6344) — TASK-API-0400")
        ids = tuple(item.id for item in sorted(self, key=key, reverse=reverse))
        return self._from_ids(self.env, ids, self._prefetch_ids)

    # === existencia =======================================================

    @api.private
    def exists(self):
        """ The subset of records in ``self`` that exist. — ≙ ``:5544``

        By convention, new records are returned as existing.

        **Divergencia de mecanismo.** La fuente arma ``Query(self.env,
        self._table, self._table_sql)`` y ejecuta el ``SELECT``;
        ``_table_sql`` no tiene contraparte aquí (declarado en
        ``orm/environments.py:1831``). El stack trae el mecanismo: el manager
        por defecto del modelo emite el mismo ``id IN (…)`` y devuelve los ids
        reales, sin SQL a mano.
        """
        new_ids, ids = partition(lambda i: isinstance(i, NewId), self._ids)
        if not ids:
            return self
        real_ids = (type(self)._default_manager
                    .filter(pk__in=tuple(ids))
                    .values_list('pk', flat=True))
        valid_ids = {*real_ids, *new_ids}
        return self.browse(i for i in self._ids if i in valid_ids)


class IdFromIds:
    """El porte de ``Id.__get__`` — ≙ ``odoo19c: odoo/orm/fields_misc.py:102-114``.

    La fuente declara ``id = Id()`` en el cuerpo de ``BaseModel``. Aquí eso no
    basta: ``ModelBase`` instala su propio ``DeferredAttribute`` sobre la clave
    primaria al preparar **cada** subclase concreta, y sombrea el descriptor de
    la base — medido en
    ``scripts/workbench/basemodel-id-access-20260911T035612/outputs/id_descriptor.txt``.
    Por eso el descriptor se instala con :func:`_install_id_descriptor`, que
    corre en ``class_prepared`` y por tanto DESPUÉS de ``ModelBase``.

    **``__set__`` NO se porta, y está medido** (``outputs/id_setter.txt``):
    declararlo convierte al descriptor en *descriptor de datos*, que precede al
    ``__dict__`` de la instancia; ``Model.__init__`` asigna la clave primaria
    con ``setattr``, así que ``Sujeto(id=99)`` levanta
    ``TypeError: field 'id' cannot be assigned``. Sin ``__set__`` la misma fila
    da ``.id = 99``. Es divergencia forzada por el stack, no recorte de alcance.

    El relevo al descriptor original es lo que mantiene viva la construcción de
    filas de Django: una instancia sin ``_ids`` no es un recordset.
    """

    __slots__ = ['fallback']

    def __init__(self, fallback):
        self.fallback = fallback

    def __get__(self, record, owner=None):
        if record is None:
            return self
        ids = getattr(record, '_ids', None)
        if ids is None:
            return self.fallback.__get__(record, owner)
        size = len(ids)
        if size == 0:
            return False
        if size == 1:
            return ids[0]
        # El mensaje NO interpola el registro: el ``__repr__``/``__str__`` de un
        # modelo de Django lee ``self.pk``, que vuelve a este descriptor y
        # recursa. La fuente no lo sufre porque su ``__repr__`` es
        # ``f'{self._name}{self._ids!r}'`` y no toca ``id``.
        raise ValueError(f'Expected singleton: ids={ids!r}')


@receiver(class_prepared)
def _install_id_descriptor(sender, **kwargs):
    """Instala :class:`IdFromIds` sobre la clave primaria de cada subclase.

    El receptor vive DESPUÉS de :class:`BaseModel` porque ``class_prepared`` no
    dispara para la base abstracta —``ModelBase`` sólo lo emite al preparar un
    modelo concreto—, así que el nombre ya está definido cuando llega la
    primera señal.

    **Divergencia declarada:** la fuente nombra siempre ``id``; aquí la clave
    primaria puede llamarse de otro modo, así que el descriptor se instala
    sobre ``_meta.pk.attname`` y, si ése no es ``id``, también bajo ``id`` para
    conservar el nombre del contrato.
    """
    if not issubclass(sender, BaseModel):
        return
    attname = sender._meta.pk.attname
    actual = sender.__dict__.get(attname)
    if actual is not None and not isinstance(actual, IdFromIds):
        descriptor = IdFromIds(actual)
        setattr(sender, attname, descriptor)
        if attname != 'id':
            setattr(sender, 'id', descriptor)



class AbstractModel:
    """La base del registrante **sin tabla** — ≙ ``AbstractModel``.

    La fuente lo declara como alias de su base (``AbstractModel = BaseModel``,
    ``odoo19c: odoo/orm/models.py:7047``), que trae ``_auto = False``
    (``:370``), ``_register = False`` (``:380``), ``_abstract = True``
    (``:381``) y ``_name = None`` (``:392``). Los cuatro se declaran aquí
    verbatim.

    **Por qué no hereda de Django, que es lo que lo hace útil.** Un registrante
    sin tabla es exactamente lo que
    :func:`~orm.registry.registrants_without_table` aparta al comparar
    ``_name`` con ``db_table``: clases que declaran nombre punteado y no tienen
    ``_meta``. Heredar de ``models.Model`` les daría uno —con ``db_table``
    derivado del ``app_label``— y las sacaría de esa cuenta, que es el
    denominador que impide que un cero de divergencias se lea como «todo
    cuadra» cuando en realidad no había nada que comparar.

    **Sus dos consumidores están medidos** y hoy no lo adoptan:
    ``IrFieldsConverter`` (``ir.fields.converter``) e ``IrTemplateExpressions``
    (``ir.qweb``). Que pasen a heredar de aquí —y con ello dejen de repetir los
    cuatro atributos por su cuenta— es la tarea **#329**.
    """

    _name = None            #: el nombre del modelo, en notación de punto
    _auto = False           #: no crea tabla en la base
    _register = False       #: no visible en el registro por nombre
    _abstract = True        #: es abstracto


#: ``Model`` — ≙ ``class Model(AbstractModel)`` (``odoo19c: odoo/orm/models.py:7049``).
#:
#: **Ya existe, y es el de Django**: este módulo re-exporta el ORM completo
#: (``from django.db.models import *``, arriba), así que ``orm.models.Model``
#: es ``django.db.models.Model`` — *"main super-class for regular
#: database-persisted models"*, que es palabra por palabra lo que la fuente
#: dice del suyo. Lo hereda todo el árbol, y ``orm/models_transient.py:36`` lo
#: importa de aquí por su nombre.
#:
#: **Los tres atributos de clase que la fuente le declara NO se le cuelgan**, y
#: la razón está medida, no supuesta:
#:
#: - ``_auto = True`` — su equivalente es ``Meta.managed``, que Django ya
#:   declara por modelo (``atributos-de-clase-de-modelo.md``).
#: - ``_abstract = False`` — su equivalente es ``Meta.abstract``, y colgarlo
#:   como constante en la base **mentiría** sobre todo modelo que sí declara
#:   ``abstract = True``: lo heredaría en ``False``.
#: - ``_register = False`` — su equivalente es el registro por nombre
#:   ``orm.registry.MODELS_BY_NAME``, que se puebla por ``_name`` declarado.
#:
#: Y colgarle atributos a ``models.Model`` alcanza a **toda** clase que lo
#: hereda, incluidas las de Django (``auth``, ``contenttypes``, ``sessions``) y
#: las de terceros — la misma colisión que :class:`FieldSqlMixin` ya declara al
#: elegir mixin en vez de adjuntar, y que la tarea **#98** barre.


@functools.total_ordering
class ReversibleComparator:
    """Clave de orden con dirección y política de nulos **en la clave**.

    ≙ ``ReversibleComparator`` (``odoo19c: odoo/orm/models.py:7066-7094``).

    Los dos ejes son independientes, y ahí está su razón de ser: ``reverse``
    invierte la comparación entre dos valores presentes, y ``none_first``
    decide dónde va el ausente **sin** invertirse con el anterior. Un
    ``sorted(reverse=True)`` no puede expresarlo —invierte la lista entera,
    nulos incluidos— ni permite mezclar columnas ascendentes y descendentes en
    un mismo orden, que es para lo que la fuente lo usa.

    ``@functools.total_ordering`` deriva ``<=``, ``>`` y ``>=`` de
    :meth:`__lt__` y :meth:`__eq__`; la fuente cuenta con ello.
    """

    __slots__ = ('__item', '__none_first', '__reverse')

    def __init__(self, item, reverse, none_first):
        self.__item = item
        self.__reverse = reverse
        self.__none_first = none_first

    def __lt__(self, other):
        item = self.__item
        item_cmp = other.__item
        if item == item_cmp:
            return False
        if item is None:
            return self.__none_first
        if item_cmp is None:
            return not self.__none_first
        if self.__reverse:
            item, item_cmp = item_cmp, item
        return item < item_cmp

    def __eq__(self, other):
        return self.__item == other.__item

    def __hash__(self):
        return hash(self.__item)

    def __repr__(self):
        return (f"<ReversibleComparator {self.__item!r}"
                f"{' reverse' if self.__reverse else ''}>")


# ═══════════════════════════════════════════════════════════════════════════
# El esquema de una columna sobre filas que ya existen
#     ≙ ``BaseModel._init_column`` (``odoo19c: odoo/orm/models.py:3137-3161``)
#     y ``BaseModel._table_has_rows`` (``:3163-3168``)
# ═══════════════════════════════════════════════════════════════════════════
#
# Los dos son consumidores de ``Field.update_db_notnull``: cuando una columna
# nace, o cuando un campo pasa a ser obligatorio, las filas que ya estaban ahí
# tienen ``NULL`` y la restricción no las admite. La fuente resuelve eso en dos
# pasos —¿hay filas? y, si las hay, siémbrales el default— y aquí igual.
#
# **Divergencia de enlace, declarada.** La fuente los declara métodos de
# instancia porque allá un «modelo» es un recordset. Aquí el modelo es una
# clase de Django, y quien los llama —``Field.update_db``— tiene la clase, no
# una fila. Se enlazan como ``classmethod``: el contrato es el mismo y el
# receptor es el que el llamador tiene. Es la misma puerta que
# ``registry.Registry.is_an_ordinary_table`` ya declaró para el cursor.


def _init_column(cls, column_name):
    """Siembra el valor por defecto de una columna en las filas existentes.

    Docstring de la fuente, verbatim: *"Initialize the value of the given
    column for existing rows"*.

    El default se obtiene del campo y **no** de ``default_get``: la fuente lo
    explica en su comentario —*"ideally, we should use default_get(), but it
    fails due to ir.default not being ready"*— y aquí vale igual, porque este
    camino corre mientras el esquema se está construyendo.

    La guarda de ``necessary`` es de la fuente y no es cosmética: un booleano
    no obligatorio trata ``False`` y ``NULL`` como lo mismo, así que sembrarlo
    costaría un ``UPDATE`` sobre toda la tabla sin cambiar nada observable. Si
    es obligatorio sí se escribe, porque ahí el ``NOT NULL`` sí distingue.
    """
    field = model_field_registry(cls)[column_name]
    #: **Divergencia de mecanismo, no de conducta.** La fuente escribe
    #: ``if field.default: value = field.default(self)`` porque en su ORM el
    #: default, cuando existe, es SIEMPRE un invocable. En Django es un valor
    #: **o** un invocable, y el centinela de «sin default» no es la falsedad
    #: sino ``NOT_PROVIDED``: con ``default=''`` —el caso de un ``TextField``
    #: obligatorio— la guarda de la fuente daria falso y la columna nueva
    #: quedaria sin sembrar, que es justo lo contrario de lo que ella hace.
    #: El par que el stack declara para esto resuelve las dos formas:
    #: ``has_default()`` (``fields/__init__.py:1013``) y ``get_default()``
    #: (``:1021``, que envuelve el valor en un ``lambda`` cuando no es
    #: invocable).
    if field.has_default():
        value = field.get_default()
        value = field.convert_to_write(value, cls)
        value = field.convert_to_column_insert(value, cls)
    else:
        value = None
    necessary = (value is not None) if field.type != 'boolean' or field.required else value
    if not necessary:
        return
    _logger.debug("Tabla '%s': valor por defecto de la columna nueva %s a %r",
                  cls._table, column_name, value)
    query = SQL(
        "UPDATE %(table)s SET %(field)s = %(value)s WHERE %(field)s IS NULL",
        table=SQL.identifier(cls._table),
        field=SQL.identifier(field.column),
        value=value,
    )
    with connections[DEFAULT_DB_ALIAS].cursor() as cr:
        cr.execute(query.code, query.params)


def _table_has_rows(cls) -> bool:
    """Si la tabla del modelo tiene alguna fila.

    Docstring de la fuente, verbatim: *"Return whether the model's table has
    rows. This method should only be used when updating the database schema"*.

    Memorizado con :class:`~tools.cache.ormcache` como allá: durante la
    construcción del esquema se pregunta una vez por campo y la respuesta no
    cambia dentro de ese pase. Quien siembre filas después invalida con
    ``orm.registry.clear_cache()``.
    """
    with connections[DEFAULT_DB_ALIAS].cursor() as cr:
        cr.execute(f'SELECT 1 FROM {cls._table} LIMIT 1')
        return bool(cr.fetchone())


Model._init_column = classmethod(_init_column)
Model._table_has_rows = classmethod(ormcache()(_table_has_rows))
