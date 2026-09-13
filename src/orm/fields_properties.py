"""Campos de propiedades dinámicas — fiel a ``odoo/orm/fields_properties.py``.

Odoo ``Properties``/``PropertiesDefinition`` = propiedades dinámicas por registro
(esquema definido en un padre). En Django el equivalente natural es
``JSONField`` (esquema validado en el serializer/clean). Alias de lectura.

``property_to_sql`` — extraer UNA propiedad del JSON
====================================================

``Field.property_to_sql`` (``orm/fields.py``) rechaza por defecto: sólo un
campo que contenga sub-campos sabe sacar uno. ``Properties`` es ese campo, y
allá lo sobreescribe (``odoo19c: odoo/orm/fields_properties.py:674-676``) con
tres líneas: valida el nombre y emite ``(campo -> 'nombre')``.

Aquí ``Properties`` **es** ``models.JSONField``, así que el método se adjunta a
esa clase — misma divergencia de forma que ``orm/fields.py`` declara para
``to_sql``: la clase es de Django y no es nuestra para declararla.

Consecuencia que conviene saber, y es una diferencia real con la fuente: allá
sólo ``Properties`` lo tiene; aquí el método se adjunta a ``JSONField``, así que
un ``fields.Json`` también responde a ``property_to_sql``. Es un
ensanchamiento, no un defecto: el operador ``->`` de PostgreSQL funciona igual
sobre cualquier ``jsonb``, y ``_field_to_sql`` sólo lo invoca cuando la
expresión trae un punto.

``Properties`` ya NO es un alias
================================

Desde el porte del cargador de datos (tarea #115) es una **clase** con la
tríada de definición de la fuente; ``PropertiesDefinition`` sigue siendo el
alias, porque su papel —guardar el esquema en el contenedor— no necesita
todavía nada más que la columna. Ver el docstring de la clase.
"""
import copy
import json
import functools
import logging
import operator as operator_module
import uuid
from collections import abc, defaultdict

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, models

from exceptions import UserError
from orm import registry
import orm.domains as _domains
import orm.models as _models
from orm.environments import context_scope, get_context, get_current_uid, sudo
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)
from orm.utils import (COLLECTION_TYPES, display_name_of, parse_field_expr,
                       regex_alphanumeric)
from tools.misc import OrderedSet, has_list_types, is_list_of
from tools.sql import SQL
from tools.translate import _

_logger = logging.getLogger(__name__)

#: ≙ el subconjunto de ``SQL_OPERATORS`` que ``condition_to_sql`` alcanza tras
#: descartar ``in``/``not in`` y la familia ``like``. ``orm/utils.py`` omite la
#: tabla entera a propósito —es plumbing del query-builder de la fuente—, así
#: que aquí van sólo los cuatro que este símbolo usa, en su forma de Django.
_COMPARISON_LOOKUP = {'<': 'lt', '>': 'gt', '<=': 'lte', '>=': 'gte'}


def _model_of(model_name):
    """La clase de ese nombre, o ``None`` — ≙ ``env[nombre]`` / ``nombre in env``.

    La fuente indexa el entorno, que conoce todo modelo por su ``_name``, y usa
    ``modelo in env`` como comprobación de existencia. Aquí se consulta el
    registro por nombre de la referencia con respaldo en el de Django, igual
    que ``ir_model._model_class``: un modelo propio del L0 no declara
    ``_name`` y sólo se alcanza por su etiqueta ``app.Modelo``.
    """
    if not model_name:
        return None
    model = registry.model_by_name(model_name)
    if model is not None:
        return model
    try:
        return apps.get_model(model_name)
    except (LookupError, ValueError):
        return None


__all__ = ['Properties', 'PropertiesDefinition', 'check_property_field_value_name']

#: ``NoneType`` — la fuente lo importa de ``types``; aquí se deriva, que es lo
#: mismo y no añade un import por una sola cita.
_NONE_TYPE = type(None)

class Properties(models.JSONField):
    """``fields.Properties`` — el valor por registro de un esquema del padre.

    ≙ ``odoo19c: odoo/orm/fields_properties.py`` clase ``Properties``, reducida
    a lo que este árbol consume hoy: la **identidad de tipo** y la resolución
    del esquema (``definition`` → ``definition_record`` +
    ``definition_record_field``), que es lo que ``BaseModel._clean_properties``
    necesita para saber qué propiedades siguen existiendo.

    Hasta ``api@0ad922eb`` esto era ``Properties = models.JSONField``, un alias
    pelado. El alias bastaba para la columna —``jsonb`` en los dos— y **no**
    para el cargador de datos: ``_load_records_create`` termina con
    ``records._clean_properties()``, y limpiar exige leer la definición del
    contenedor. Sin la clase, esa mitad del cargador no tenía a quién
    preguntar.

    Qué se porta y qué no
    =====================

    Se porta lo que el cargador ejerce: la tríada de definición, su derivación
    desde ``definition='campo.definicion'``, ``_get_properties_definition``, y
    la conversión de las tres formas de entrada a la forma de almacenamiento
    (``convert_to_cache`` con ``_list_to_dict``, ``_remove_display_name`` y
    ``_add_missing_names``), más su inversa ``_dict_to_list``.

    **NO** se porta todavía el resto del archivo de la fuente —el
    ``compute``/``inverse`` que materializa el campo en lectura, la validación
    de la definición, el saneo HTML por propiedad y la superficie web—. No es
    una divergencia declarada en lugar de portar: es **porte por tramos con
    sucesor registrado**, tarea **#130**, y el tramo que falta no lo toca
    ningún consumidor de este árbol hoy (medido: ninguna de las 11
    declaraciones de ``fields.Properties``/``PropertiesDefinition`` pasa
    ``definition=``, que es la segunda mitad del mismo sucesor).

    El discriminador de tipo es ``isinstance``, no un atributo ``type``
    ====================================================================

    La fuente declara ``type = 'properties'`` y sus consumidores preguntan
    ``field.type != 'properties'``. Aquí el discriminador es
    ``isinstance(field, Properties)``, que es la forma que este árbol ya fijó
    para el mismo problema en ``fields_textual.Html`` (H-API-700): un
    ``models.Field`` de Django no lleva atributo ``type``, y añadírselo
    duplicaría en una cadena lo que la clase ya dice. La clave de tipo que
    ``ir.model.fields`` refleja se sigue derivando del nombre exportado
    (``ir_model._type_key``), no de un atributo — sin cambio.

    La columna no cambia
    ====================

    Como ``Html``, :meth:`deconstruct` devuelve la ruta de
    ``django.db.models.JSONField``: las migraciones generadas cuando esto era
    un alias siguen siendo idénticas y ``makemigrations --check`` queda limpio.
    """

    #: ``'campo_al_contenedor.campo_de_definicion'``, tal cual la fuente.
    definition = None
    #: El campo de ESTE modelo que apunta al contenedor.
    definition_record = None
    #: El campo del contenedor que guarda la definición.
    definition_record_field = None
    #: ≙ el ``_setup_done`` de la fuente — guarda de :meth:`setup`.
    _setup_done = False

    #: ≙ ``ALLOWED_TYPES`` (``odoo19c: fields_properties.py``) — los tipos que
    #: una propiedad puede declarar. Se porta verbatim.
    ALLOWED_TYPES = (
        # standard types
        'boolean', 'integer', 'float', 'text', 'char', 'html', 'date',
        'datetime', 'monetary',
        # relational like types
        'many2one', 'many2many', 'selection', 'tags',
        # UI types
        'separator',
    )

    def __init__(self, *args, definition=None, related=None, store=_UNSET,
                 **kwargs):
        """``definition`` es propio del tipo; ``store`` y ``related`` son el
        vocabulario de la fuente, que se **reenvía** al constructor para que
        ``_args__`` lo recoja (TASK-API-0417)."""
        if store is not _UNSET:
            kwargs['store'] = store
        related_attrs = apply_source_defaults(related, kwargs)
        super().__init__(*args, **kwargs)
        annotate_related(self, related, related_attrs)
        self.definition = definition

    def _setup_definition_attrs(self, model_class=None):
        """≙ ``_setup_definition_attrs`` — parte ``definition`` en sus dos mitades.

        La fuente lo corre desde ``_setup_attrs__``, que su ORM invoca al
        construir la clase de modelo. Aquí lo invoca el mismo símbolo, llamado
        desde :meth:`contribute_to_class` — el momento equivalente de Django.

        La rama de ``compute``/``_depends`` de la fuente sí tiene contraparte
        desde la tarea #130: el receptor es :meth:`pre_save`, que llama a
        :meth:`_compute`. ``_depends`` no viaja porque aquí no hay grafo de
        dependencias que notificar: el enganche se dispara en cada guardado.
        """
        if not self.definition:
            return
        assert self.definition.count('.') == 1, (
            f"definition debe ser 'campo.definicion', no {self.definition!r}")
        self.definition_record, self.definition_record_field = (
            self.definition.rsplit('.', 1))

    def deconstruct(self):
        """Deconstruye como ``django.db.models.JSONField`` — ver el docstring.

        ``definition`` se descarta a propósito: no es un atributo de columna
        sino de resolución en runtime, así que meterlo en la migración pediría
        un ``AlterField`` por cada campo que lo declare sin que la tabla
        cambie.
        """
        name, _path, args, kwargs = super().deconstruct()
        kwargs.pop('definition', None)
        return name, 'django.db.models.JSONField', args, kwargs

    def _get_properties_definition(self, record):
        """≙ ``_get_properties_definition`` (``odoo19c: :401-405``).

        «Return the properties definition of the given record.»

        Devuelve ``None`` cuando el registro no tiene contenedor —igual que la
        fuente, cuyo ``if container:`` deja caer el ``return``— y cuando este
        campo no declara ``definition``, que es el estado de las once
        declaraciones del árbol hoy (tarea #130).

        La elevación de la fuente (``container.sudo()``) se porta con el mismo
        sentido: la definición del contenedor se lee **siempre**, aunque el
        actor no tenga permiso sobre él; lo contrario dejaría a un usuario sin
        acceso al padre viendo propiedades que ya no existen.
        """
        if not self.definition_record:
            return None
        self.setup(type(record))
        container = getattr(record, self.definition_record, None)
        if not container:
            return None
        with sudo():
            return getattr(container, self.definition_record_field, None)

    # -- Conversión entre las formas del valor -------------------------------

    def convert_to_cache(self, value, record, validate=True):
        """≙ ``convert_to_cache`` (``odoo19c: :140-165``).

        «any format -> cache format {name: value} or None». Las cuatro formas
        de entrada de la fuente se portan: vacío, ``dict`` (copia profunda,
        *"avoid accidental side effects from shared mutable data"*), ``str``
        (JSON) y ``list`` (la definición completa que manda el cliente, que se
        reduce a ``{nombre: valor}``).

        La rama ``Property`` de la fuente **no** aplica: ese envoltorio es de
        su capa de lectura, que es el tramo no portado (tarea #130).

        DIVERGENCIA DECLARADA en ``validate``: la fuente sanea con
        ``html_sanitize`` las propiedades cuyo nombre acaba en ``_html``. Aquí
        el saneo de HTML vive en la capa UI (``dompurify``) —la misma decisión
        que ``fields_textual.Html`` ya declara para el campo entero—, así que
        la bandera se acepta y no dispara saneo. No es un hueco silencioso: es
        la misma frontera, aplicada al mismo tipo de dato.
        """
        if not value:
            return None
        if isinstance(value, dict):
            return copy.deepcopy(value)
        if isinstance(value, str):
            value = json.loads(value)
            if not isinstance(value, dict):
                raise ValueError(f"Wrong property value {value!r}")
            return value
        if isinstance(value, list):
            self._remove_display_name(value)
            return self._list_to_dict(value)
        raise TypeError(f"Wrong property type {type(value)!r}")

    @classmethod
    def _add_missing_names(cls, values_list):
        """≙ ``_add_missing_names`` — «Generate new properties name if needed».

        Modifica ``values_list`` en el sitio, como la fuente. El nombre son los
        primeros 64 bits de un UUID4, verbatim.
        """
        for definition in values_list:
            if definition.get('definition_changed') and not definition.get('name'):
                # keep only the first 64 bits
                definition['name'] = str(uuid.uuid4()).replace('-', '')[:16]

    @classmethod
    def _remove_display_name(cls, values_list, value_key='value'):
        """≙ ``_remove_display_name`` — quita la etiqueta que manda el cliente.

        «- many2one: (35, 'Bob') -> 35 · many2many: [(35, 'Bob'), (36, 'Alice')]
        -> [35, 36]». Modifica ``values_list`` en el sitio.
        """
        for property_definition in values_list:
            if not isinstance(property_definition, dict) or not property_definition.get('name'):
                continue

            property_value = property_definition.get(value_key)
            if not property_value:
                continue

            property_type = property_definition.get('type')

            if property_type == 'many2one' and has_list_types(
                    property_value, [int, (str, _NONE_TYPE)]):
                property_definition[value_key] = property_value[0]

            elif property_type == 'many2many':
                if is_list_of(property_value, (list, tuple)):
                    # [(35, 'Admin'), (36, 'Demo')] -> [35, 36]
                    property_definition[value_key] = [
                        many2many_value[0]
                        for many2many_value in property_value
                    ]

    @classmethod
    def _list_to_dict(cls, values_list):
        """≙ ``_list_to_dict`` — la definición completa reducida a ``{nombre: valor}``.

        «To not repeat data in database, we only store the value of each
        property on the child. The properties definition is stored on the
        container.»

        Las tres comprobaciones de forma de la fuente se portan enteras: la
        lista tiene que ser de diccionarios, un ``many2many`` tiene que traer
        enteros y un ``many2one`` un entero. Son las que impiden que llegue a
        la columna un valor que la lectura no sabrá deshacer.
        """
        if not is_list_of(values_list, dict):
            raise ValueError(f'Wrong properties value {values_list!r}')

        cls._add_missing_names(values_list)

        dict_value = {}
        for property_definition in values_list:
            property_value = property_definition.get('value')
            property_type = property_definition.get('type')
            property_model = property_definition.get('comodel')
            if property_value is None:
                # Do not store None key
                continue

            if property_type not in ('integer', 'float') or property_value != 0:
                property_value = property_value or False
            if property_type in ('many2one', 'many2many') and property_model and property_value:
                # check that value are correct before storing them in database
                if property_type == 'many2many' and property_value and not is_list_of(property_value, int):
                    raise ValueError(f"Wrong many2many value {property_value!r}")

                if property_type == 'many2one' and not isinstance(property_value, int):
                    raise ValueError(f"Wrong many2one value {property_value!r}")

            dict_value[property_definition['name']] = property_value

        return dict_value

    @classmethod
    def _dict_to_list(cls, values_dict, properties_definition):
        """≙ ``_dict_to_list`` — la inversa: el valor del hijo sobre la definición.

        «Ignore every values in the child that is not defined on the
        container» — que es exactamente el criterio con que
        ``_clean_properties`` decide qué sobra.
        """
        if not is_list_of(properties_definition, dict):
            raise ValueError(f'Wrong properties value {properties_definition!r}')

        values_list = copy.deepcopy(properties_definition)
        for property_definition in values_list:
            if property_definition['name'] in values_dict:
                property_definition['value'] = values_dict[property_definition['name']]
            else:
                property_definition.pop('value', None)
        return values_list


    # -- Ciclo de vida del campo ---------------------------------------------

    def _setup_attrs__(self, model_class, name):
        """≙ ``_setup_attrs__`` (``odoo19c: :86-88``).

        El enganche que su ORM invoca al construir la clase de modelo. Aquí lo
        invoca :meth:`contribute_to_class`, que es el momento equivalente de
        Django: la clase ya existe y el campo acaba de recibir su nombre.
        """
        self._setup_definition_attrs(model_class)

    def contribute_to_class(self, cls, name, **kwargs):
        """El enganche de Django, que delega en el símbolo de la fuente."""
        super().contribute_to_class(cls, name, **kwargs)
        self._setup_attrs__(cls, name)

    def setup(self, model):
        """≙ ``setup`` (``odoo19c: :102-106``).

        Se anota en el ``properties_fields`` del campo de definición del
        contenedor: la definición necesita saber qué campos la consumen para
        propagarles un cambio de esquema.

        DIVERGENCIA DE MOMENTO, declarada: allá el ORM llama a ``setup`` en su
        etapa de arranque del registro. Aquí no hay esa etapa —Django prepara
        cada modelo por separado y el contenedor puede no estar cargado cuando
        este campo se contribuye—, así que la llamada es **perezosa**: la
        dispara el primer consumidor que necesite la definición, guardada por
        ``_setup_done`` como en la fuente. El efecto es el mismo y el orden de
        carga deja de importar.
        """
        if self._setup_done or not (self.definition_record
                                    and self.definition_record_field):
            return
        self._setup_done = True
        container_field = model._meta.get_field(self.definition_record)
        definition_field = container_field.related_model._meta.get_field(
            self.definition_record_field)
        definition_field.properties_fields += (self,)

    def setup_related(self, model):
        """≙ ``setup_related`` (``odoo19c: :108-112``).

        Un campo heredado por delegación toma la ``definition`` de su original.
        Aquí la delegación es ``orm.inherits``, que copia el campo entero, así
        que el caso sólo se da cuando alguien reasigna ``inherited_field`` a
        mano. Se porta con su nombre y su firma: la rama existe y su condición
        es la misma.
        """
        inherited = getattr(self, 'inherited_field', None)
        if inherited is not None and not self.definition:
            self.definition = inherited.definition
            self._setup_definition_attrs(type(model))

    # -- Cómputo del valor al guardar ----------------------------------------

    def _compute(self, records):
        """≙ ``_compute`` (``odoo19c: :332-338``).

        «Add the default properties value when the container is changed.»

        La fuente lo declara como ``compute`` del campo (``store=True``,
        ``readonly=False``, ``precompute=True``): se dispara al crear o al
        cambiar el contenedor. Aquí el receptor es :meth:`pre_save`, el
        enganche de Django que decide el valor que va a la columna — el mismo
        momento, con otro nombre.
        """
        with sudo():
            for record in records:
                value = self._add_default_values({
                    self.name: getattr(record, self.name, None),
                    self.definition_record: getattr(
                        record, self.definition_record, None),
                }, model=type(record))
                # La fuente escribe ``record[self.name] = <lista>`` y su ORM la
                # pasa por ``convert_to_cache`` al guardarla — de ahí sale la
                # forma ``{nombre: valor}`` de la columna. Aquí el ``setattr``
                # de Django no convierte, así que la conversión va explícita:
                # sin ella la columna guardaría la lista de definiciones.
                setattr(record, self.name,
                        self.convert_to_cache(value, record))

    def pre_save(self, model_instance, add):
        """El enganche de Django que materializa el ``compute`` de la fuente."""
        if self.definition_record:
            self._compute([model_instance])
        return super().pre_save(model_instance, add)

    def _add_default_values(self, values, model=None, using=DEFAULT_DB_ALIAS):
        """≙ ``_add_default_values`` (``odoo19c: :340-396``).

        «Read the properties definition to add default values. Default values
        are defined on the container in the 'default' key of the definition.»

        DIVERGENCIA DE FIRMA, declarada una vez para todo este bloque: la
        fuente recibe ``env`` porque su entorno es un objeto. Aquí el entorno
        es **ambiente** (``orm.environments``), así que lo que viaja es el
        alias de base (``using``) y, cuando hace falta resolver el contenedor
        desde un id pelado, la clase del modelo (``model``). Es la misma
        traducción que ``tools/convert.py`` declara para el cargador.
        """
        properties_values = values.get(self.name) or {}
        if isinstance(properties_values, Property):
            properties_values = properties_values._values

        container = values.get(self.definition_record)
        if not container:
            # container is not given in the value, can not find properties definition
            return {}

        if not isinstance(container, (int, models.Model)):
            raise ValueError(f"Wrong container value {container!r}")

        if isinstance(container, int):
            container_field = model._meta.get_field(self.definition_record)
            with sudo():
                container = container_field.related_model.objects.using(
                    using).filter(pk=container).first()
            if container is None:
                return {}

        with sudo():
            properties_definition = getattr(
                container, self.definition_record_field, None)
        if not (properties_definition or (
            isinstance(properties_values, list)
            and any(d.get('definition_changed') for d in properties_values)
        )):
            # If a parent is set without properties, we might want to change its
            # definition when we create the new record. But if we just set the
            # value without changing the definition, in that case we can just
            # ignored the passed values
            return {}

        assert isinstance(properties_values, (list, dict))
        if isinstance(properties_values, list):
            self._remove_display_name(properties_values)
            properties_list_values = properties_values
        else:
            properties_list_values = self._dict_to_list(
                properties_values, properties_definition)

        context = get_context()
        for properties_value in properties_list_values:
            if properties_value.get('value') is None:
                property_name = properties_value.get('name')
                context_key = f"default_{self.name}.{property_name}"
                if property_name and context_key in context:
                    default = context[context_key]
                else:
                    default = properties_value.get('default')
                if default:
                    properties_value['value'] = default

        return properties_list_values

    # -- Escritura -----------------------------------------------------------

    column_conversion_needs_record = True

    def convert_to_column(self, value, record, values=None, validate=True):
        """≙ ``convert_to_column`` (``odoo19c: :124-129``) — la forma de columna."""
        if not value:
            return None
        value = self.convert_to_cache(value, record, validate=validate)
        return json.dumps(value)

    def get_prep_value(self, value):
        """El enganche de Django, que delega en el símbolo de la fuente.

        ``convert_to_column`` recibe el registro y aquí no llega: Django
        prepara el valor sin él. Se pasa ``None``, que es lo que la fuente
        haría con un campo sin saneo — el único uso del registro en ese cuerpo
        es el saneo HTML, y ese es la divergencia ya declarada.
        """
        if isinstance(value, Property):
            value = value._values
        return super().get_prep_value(value)

    def write(self, records, value):
        """≙ ``write`` (``odoo19c: :291-330``).

        «Check if the properties definition has been changed. To avoid extra
        SQL queries used to detect definition change, we add a flag in the
        properties list. Parent update is done only when this flag is present,
        delegating the check to the caller (generally web client).»

        Es lo que hace que editar el esquema desde el hijo actualice al
        **contenedor**: sin esta rama, una propiedad nueva se guardaría en el
        hijo y ningún otro registro la vería.
        """
        if isinstance(value, str):
            value = json.loads(value)
        if isinstance(value, Property):
            value = value._values

        containers = {getattr(record, self.definition_record, None)
                      for record in records}
        if len(containers) > 1 and value:
            raise UserError(_(
                'Updating records with different property fields definitions '
                'is not supported. Update by separate definition instead.'))

        if isinstance(value, dict):
            # don't need to write on the container definition
            return self._write_cache(records, value)

        definition_changed = any(
            definition.get('definition_changed')
            or definition.get('definition_deleted')
            for definition in (value or [])
        )
        if definition_changed:
            value = [
                definition for definition in value
                if not definition.get('definition_deleted')
            ]
            for definition in value:
                definition.pop('definition_changed', None)

            # update the properties definition on the container
            container = next(iter(containers), None)
            if container:
                properties_definition = copy.deepcopy(value)
                for property_definition in properties_definition:
                    property_definition.pop('value', None)
                setattr(container, self.definition_record_field,
                        properties_definition)
                container.save(update_fields=[self.definition_record_field])
                _logger.info(
                    'Properties field: User #%s changed definition of %r',
                    get_current_uid(), container)

        return self._write_cache(records, value)

    def _write_cache(self, records, value):
        """El ``super().write`` de la fuente — asignar y guardar cada registro.

        Allá ``Field.write`` deja el valor en la caché del ORM y el ``flush``
        lo baja a la columna. Aquí no hay caché: se asigna y se guarda, que es
        el mismo efecto observable.
        """
        for record in records:
            setattr(record, self.name, value)
            record.save(update_fields=[self.name])
        return records

    # -- Lectura -------------------------------------------------------------

    def convert_to_record(self, value, record):
        """≙ ``convert_to_record`` (``odoo19c: :177-178``) — el envoltorio."""
        return Property(value or {}, self, record)

    def convert_to_read(self, value, record, use_display_name=True):
        """≙ ``convert_to_read`` (``odoo19c: :196-197``)."""
        return self.convert_to_read_multi([value], [record], use_display_name)[0]

    def convert_to_read_multi(self, values, records, use_display_name=True,
                              using=DEFAULT_DB_ALIAS):
        """≙ ``convert_to_read_multi`` (``odoo19c: :199-226``).

        La forma de lectura: el valor del hijo **fusionado** con la definición
        del contenedor, con las etiquetas de los relacionales resueltas. Es lo
        que el cliente necesita para pintar el campo sin conocer el esquema.
        """
        records = list(records)
        if not records:
            return values
        assert len(values) == len(records)

        # each value is either False or a dict
        result = []
        for record, value in zip(records, values):
            value = value._values if isinstance(value, Property) else value
            definition = self._get_properties_definition(record)
            if definition:
                value = value or {}
                assert isinstance(value, dict), f"Wrong type {value!r}"
                result.append(self._dict_to_list(value, definition))
            else:
                result.append([])

        res_ids_per_model = self._get_res_ids_per_model(result, using=using)

        # value is in record format
        for value in result:
            self._parse_json_types(value, res_ids_per_model)

        if use_display_name:
            for value in result:
                self._add_display_name(value, using=using)

        return result

    def convert_to_write(self, value, record):
        """≙ ``convert_to_write`` (``odoo19c: :228-230``).

        «If we write a list on the child, update the definition record.» El
        cuerpo de la fuente es un ``return value`` — quien actualiza al
        contenedor es :meth:`write`, no esta conversión.
        """
        return value

    def convert_to_export(self, value, record):
        """≙ ``convert_to_export`` (``odoo19c: :232-236``)."""
        if isinstance(value, Property):
            value = value._values
        return value or ''

    def _get_res_ids_per_model(self, values_list, using=DEFAULT_DB_ALIAS):
        """≙ ``_get_res_ids_per_model`` (``odoo19c: :238-281``).

        «To retrieve relational properties names, or to check their existence,
        we need to do some SQL queries. To reduce the number of queries when we
        read in batch, we prefetch everything needed before calling
        convert_to_record / convert_to_read.»

        Devuelve ``{modelo: ids_existentes}``. La comprobación de existencia de
        la fuente (``browse(ids).exists()``) la hace aquí el propio filtro:
        ``filter(pk__in=ids)`` sólo devuelve las filas que existen.
        """
        ids_per_model = defaultdict(OrderedSet)

        for record_values in values_list:
            for property_definition in record_values:
                comodel = property_definition.get('comodel')
                type_ = property_definition.get('type')
                property_value = property_definition.get('value') or []
                default = property_definition.get('default') or []

                if type_ not in ('many2one', 'many2many') or not _model_of(comodel):
                    continue

                if type_ == 'many2one':
                    default = [default] if default else []
                    property_value = ([property_value]
                                      if isinstance(property_value, int) else [])
                elif not is_list_of(property_value, int):
                    property_value = []

                ids_per_model[comodel].update(default)
                ids_per_model[comodel].update(property_value)

        res_ids_per_model = {}
        for model_name, ids in ids_per_model.items():
            model = _model_of(model_name)
            rows = model.objects.using(using).filter(pk__in=list(ids))
            res_ids_per_model[model_name] = {row.pk for row in rows}

        return res_ids_per_model

    @classmethod
    def _add_display_name(cls, values_list, using=DEFAULT_DB_ALIAS,
                          value_keys=('value', 'default')):
        """≙ ``_add_display_name`` (``odoo19c: :407-448``).

        «Add the "display_name" for each many2one / many2many properties.
        Modify in place "values_list".»

        DIVERGENCIA MEDIDA en la etiqueta: la fuente lee ``record.display_name``,
        que su ``BaseModel`` declara para **todo** modelo. Aquí sólo lo declaran
        13 modelos (medido), así que se cae a ``str(record)`` —el ``__str__`` de
        Django, que es el equivalente natural— cuando el modelo no lo declara.
        Construir el ``display_name`` universal es la tarea **#134**.
        """
        for property_definition in values_list:
            property_type = property_definition.get('type')
            property_model = property_definition.get('comodel')
            if not property_model:
                continue
            model = _model_of(property_model)
            if model is None:
                continue

            for value_key in value_keys:
                property_value = property_definition.get(value_key)

                if (property_type == 'many2one' and property_value
                        and isinstance(property_value, int)):
                    row = model.objects.using(using).filter(
                        pk=property_value).first()
                    if row is None:
                        property_definition[value_key] = False
                    else:
                        property_definition[value_key] = (
                            property_value, display_name_of(row))

                elif (property_type == 'many2many' and property_value
                        and is_list_of(property_value, int)):
                    property_definition[value_key] = []
                    rows = model.objects.using(using).filter(
                        pk__in=property_value)
                    for row in rows:
                        property_definition[value_key].append(
                            (row.pk, display_name_of(row)))

    @classmethod
    def _parse_json_types(cls, values_list, res_ids_per_model):
        """≙ ``_parse_json_types`` (``odoo19c: :491-556``).

        «Parse the value stored in the JSON. Check for records existence, if we
        removed a selection option, ... Modify in place "values_list".»

        Es la mitad que hace la lectura **honesta**: una opción de selección
        retirada del contenedor, o un registro relacional borrado, salen como
        ``False`` en vez de como un id que ya no resuelve.
        """
        for property_definition in values_list:
            property_value = property_definition.get('value')
            property_type = property_definition.get('type')
            res_model = property_definition.get('comodel')

            if property_type not in cls.ALLOWED_TYPES:
                raise ValueError(f'Wrong property type {property_type!r}')

            if property_value is None:
                continue

            if property_type == 'boolean':
                # E.G. convert zero to False
                property_value = bool(property_value)

            elif property_type in ('char', 'text') and not isinstance(property_value, str):
                property_value = False

            elif property_value and property_type == 'selection':
                # check if the selection option still exists
                options = property_definition.get('selection') or []
                options = {option[0] for option in options if option or ()}
                if property_value not in options:
                    # maybe the option has been removed on the container
                    property_value = False

            elif property_value and property_type == 'tags':
                # remove all tags that are not defined on the container
                all_tags = {tag[0] for tag in property_definition.get('tags') or ()}
                property_value = [tag for tag in property_value if tag in all_tags]

            elif property_type == 'many2one':
                if (not isinstance(property_value, int)
                        or res_model not in res_ids_per_model
                        or property_value not in res_ids_per_model[res_model]):
                    property_value = False

            elif property_type == 'many2many':
                if not is_list_of(property_value, int):
                    property_value = []
                elif len(property_value) != len(set(property_value)):
                    # remove duplicated value and preserve order
                    property_value = list(dict.fromkeys(property_value))

                property_value = [
                    id_ for id_ in property_value
                    if id_ in res_ids_per_model[res_model]
                ] if res_model in res_ids_per_model else []

            elif property_type == 'html':
                # field name should end with `_html` to be legit and sanitized,
                # otherwise do not trust the value and force False
                property_value = (property_definition['name'].endswith('_html')
                                  and property_value)

            property_definition['value'] = property_value

    # -- Búsqueda ------------------------------------------------------------

    def property_to_sql(self, field_sql, property_name, model, alias, query):
        """≙ ``property_to_sql`` (``odoo19c: :674-676``) — ``(campo -> 'nombre')``."""
        check_property_field_value_name(property_name)
        return SQL("(%s -> %s)", field_sql, property_name)

    def condition_to_q(self, field_expr, operator, value, model=None):
        """≙ ``condition_to_sql`` (``odoo19c: :678-771``) — la condición de búsqueda.

        DIVERGENCIA DE FORMA, la que ``orm/domains.py`` ya declara para toda
        esta capa: allá el retorno es ``SQL`` porque la fuente compone el
        ``WHERE`` a mano; aquí es ``Q`` porque lo compone Django. El nombre
        sigue al tipo de retorno — ``_to_sql`` es ``_to_q``, y
        ``condition_to_sql`` es ``condition_to_q``.

        **Lo que este símbolo aporta y el compilador genérico NO da.** Sin él,
        ``props.tags in [1, 2]`` compila a ``(campo -> tags) IN (1, 2)``, que
        sólo acierta cuando el valor guardado es **escalar**. La fuente dice
        por qué no basta, verbatim: *"left can be an array or a single value!
        Even if we use the '=' operator, we must check the list subset."* Un
        ``many2many`` guarda una lista, así que la condición necesita además
        la contención ``jsonb``:

        - un solo valor → ``left @> value`` — ``__contains``;
        - varios       → ``left <@ value_list`` — ``__contained_by``.

        Las tres formas que emite (`->`, `@>`, `<@`) son las mismas de la
        fuente; lo que cambia es quién las escribe.
        """
        _fname, property_name = parse_field_expr(field_expr)
        if not property_name:
            raise ValueError(f"Missing property name for {self}")
        # ≙ ``_django_path`` de ``orm/domains.py``, escrito aquí: aquel
        # módulo importa éste, así que importarlo de vuelta cerraría el ciclo.
        key = field_expr.replace('.', '__')

        if operator in ('in', 'not in'):
            assert isinstance(value, COLLECTION_TYPES)
            # ≙ ``:686-699`` — el caso de ``False`` en la colección decide si
            # la fila «sin la propiedad» entra o sale.
            if len(value) == 1 and any(v is True for v in value):
                # inverse the condition
                check_null_op_false = 'not exact'
                value = []
                operator = 'in' if operator == 'not in' else 'not in'
            elif False in value:
                check_null_op_false = ('exact' if operator == 'in'
                                       else 'not exact')
                value = [v for v in value if v]
            else:
                value = list(value)
                check_null_op_false = None

            qs = []
            if check_null_op_false:
                q_false = models.Q(**{key: False})
                if check_null_op_false == 'exact':
                    # check null value too
                    fname = key.split('__')[0]
                    qs.append(q_false
                              | models.Q(**{f'{fname}__isnull': True})
                              | ~models.Q(**{f'{fname}__has_key': property_name}))
                else:
                    qs.append(~q_false)

            # left can be an array or a single value! Even if we use the '='
            # operator, we must check the list subset.
            if len(value) == 1:
                # check single value equality
                q_one = models.Q(**{key: value[0]})
                qs.append(q_one if operator == 'in' else ~q_one)
            if value:
                # hackish operator to search values
                lookup = 'contained_by' if len(value) > 1 else 'contains'
                q_sub = models.Q(**{f'{key}__{lookup}': value})
                qs.append(~q_sub if operator == 'not in' else q_sub)

            assert qs, 'No Q generated for property'
            combine = operator_module.or_ if operator == 'in' else operator_module.and_
            return functools.reduce(combine, qs)

        # ≙ ``:742-771`` — el resto de operadores. La fuente escribe aquí su
        # propio bloque en vez de delegar en el compilador genérico, y este
        # porte hace lo mismo: sobre una clave de JSON no hay columna, así que
        # la semántica de nulos del compilador genérico no aplica.
        if operator.endswith('like'):
            # La fuente usa ``->>`` para el valor de texto y dice por qué:
            # ``->`` devuelve JSON, con sus comillas. Los lookups de texto de
            # Django emiten ``->>`` (medido); los de igualdad, ``->``.
            lookup = {
                'like': 'contains', 'ilike': 'icontains',
                'not like': 'contains', 'not ilike': 'icontains',
                '=like': 'exact', '=ilike': 'iexact',
                'not =like': 'exact', 'not =ilike': 'iexact',
            }[operator]
            q = models.Q(**{f'{key}__{lookup}': str(value)})
            if operator.startswith('not '):
                # ≙ ``:764-765`` — el negativo acepta la fila sin la propiedad
                q = ~q | models.Q(**{f'{key}__isnull': True})
            return q

        lookup = _COMPARISON_LOOKUP.get(operator)
        if lookup is None:
            raise ValueError(f"Invalid operator {operator} for Properties")
        return models.Q(**{f'{key}__{lookup}': value})

    def expression_getter(self, field_expr):
        """≙ ``expression_getter`` (``odoo19c: :634-655``).

        Devuelve el invocable que extrae **una** propiedad de un registro, con
        el tipo que la definición declara: un ``many2one`` sale como registro,
        un ``selection`` como su etiqueta. Es lo que hace que filtrar en
        memoria por una propiedad se comporte como filtrar por un campo.
        """
        _fname, property_name = parse_field_expr(field_expr)
        if not property_name:
            raise ValueError(f"Missing property name for {self}")

        def get_property(record):
            property_value = self.convert_to_record(
                getattr(record, self.name, None), record)
            with context_scope(property_selection_get_key=True):
                value = property_value.get(property_name)
            if value:
                return value
            for definition in self._get_properties_definition(record) or ():
                if definition.get('name') == property_name:
                    break
            else:
                # definition not found
                return value or False

            if not value and definition['type'] in ('many2one', 'many2many'):
                model = _model_of(definition.get('comodel'))
                return model.objects.none() if model is not None else False
            return value

        return get_property

    def filter_function(self, records, field_expr, operator, value):
        """≙ ``filter_function`` (``odoo19c: :657-666``).

        El predicado **en memoria** de una condición sobre una propiedad. Dos
        ramas producen un dominio —el ``any`` explícito y el ``in`` sobre una
        propiedad relacional— y el resto delega en el caso base del campo.

        **Este porte estuvo declinado con una razón que caducó**
        (:ref:`h-api-992`). Decía: *"BLOQUEADO por ``filtered_domain`` … medido:
        ``grep`` da 0"*. El porte de ``ir_default`` construyó ese mecanismo
        —``orm/models.py`` lo declara como función de módulo y como método de
        ``AccessQuerySet``— y con él ``Field.filter_function`` y
        ``Field.expression_getter`` (``orm/fields.py``). La razón dejó de ser
        cierta y nadie editó la prosa.

        **La divergencia que sí queda, medida, es de FORMA del import.** La
        fuente declara este archivo *aguas abajo* de ``domains`` y ``models``
        (``from .domains import Domain``, ``from .models import BaseModel``);
        aquí la dirección está invertida —``domains.py`` y ``models.py``
        importan ``Properties``— así que un ``from orm.domains import Domain``
        cerraría el ciclo. Se resuelve con la forma que Python admite para un
        ciclo: importar el **módulo**, no el símbolo, y resolver el nombre al
        llamar. Enderezar la dirección es la tarea **#260**; hasta entonces
        ``_domains`` y ``_models`` son ese import, declarado arriba y no dentro
        de la función.

        Tres adaptaciones de forma, ninguna de alcance:

        - ``records`` es la **clase** del modelo, no un recordset: es lo que
          ``DomainCondition._as_predicate`` pasa. Por eso el sondeo del tipo de
          la propiedad usa ``records()`` —una instancia sin guardar— donde la
          fuente usa ``records.browse()``.
        - Un valor relacional sale como ``QuerySet`` —``Property.__getitem__``
          devuelve ``model.objects.filter(pk__in=…)``— así que **no** hay que
          envolverlo. Una primera redacción decía «una instancia, no un
          recordset de uno» y la sonda lo desmintió: el guard que eso habría
          justificado era código muerto.
        - ``getter(rec).filtered_domain(domain)`` pasa por la **función** de
          módulo, no por el método: el ``QuerySet`` de un comodelo cualquiera
          no declara ``AccessManager``, así que el método puede no estar.
        - El ``False`` del getter no es un contenedor vacío y no se puede
          filtrar. Distinguir «declarada sin valor» (``QuerySet`` vacío) de
          «no declarada» (``False``) es lo que decide qué caso ejerce la
          guarda; lo destapó el control de neutralización, no la lectura.
        """
        getter = self.expression_getter(field_expr)
        domain = None
        if operator == 'any' or isinstance(value, _domains.Domain):
            domain = _domains.Domain(value).optimize(records)
        elif (operator == 'in' and isinstance(value, COLLECTION_TYPES)
                and isinstance(getter(records()), models.QuerySet)):
            domain = _domains.Domain('id', 'in', value).optimize(records)

        if domain is not None:
            def matches(record):
                corecords = getter(record)
                if not corecords:
                    # El getter devuelve ``False`` —no un contenedor vacío—
                    # cuando el contenedor no declara la propiedad (``:989``).
                    # ``False`` no es iterable: sin esto es un ``TypeError``.
                    return []
                return _models.filtered_domain(corecords, domain)
            return matches

        return super().filter_function(records, field_expr, operator, value)


def check_property_field_value_name(property_name):
    """≙ ``check_property_field_value_name`` (``odoo19c: :27-29``).

    El nombre de una propiedad va **interpolado en el SQL**, así que se acota
    antes: hasta 512 caracteres y sólo minúsculas, dígitos y guion bajo.
    """
    if not (0 < len(property_name) <= 512) or not regex_alphanumeric.match(property_name):
        raise ValueError(f"Wrong property field value name {property_name!r}.")


# ``property_to_sql`` era una función de módulo adjuntada a ``models.JSONField``
# porque ``Properties`` era un alias de esa clase. Desde la tarea #130 es un
# **método de** ``Properties``, como en la fuente: el despacho por tipo de campo
# vuelve a ser el de la referencia, y un ``fields.Json`` cualquiera deja de
# responder a él — que es también lo que allá ocurre, porque el caso base de
# ``Field.property_to_sql`` rechaza.


class Property(abc.Mapping):
    """≙ ``Property`` (``odoo19c: fields_properties.py:775-841``).

    «Represent a collection of properties of a record. […] The value behaves as
    a ``dict``, and individual properties are returned in their expected type,
    according to ORM conventions. For instance, the value of a many2one
    property is returned as a recordset.»

    Es la forma de **registro** del valor: lo que se obtiene al leer
    ``record.propiedades``. Un ``many2one`` sale como registro, un
    ``selection`` como su etiqueta —o como su clave, si el contexto trae
    ``property_selection_get_key``—, y una clave sin definición en el
    contenedor levanta ``KeyError`` en vez de devolver un valor huérfano.
    """

    def __init__(self, values, field, record):
        self._values = values
        self.record = record
        self.field = field

    def __iter__(self):
        for key in self._values:
            try:
                self[key]
            except KeyError:
                continue
            yield key

    def __len__(self):
        return len(self._values)

    def __eq__(self, other):
        return self._values == (
            other._values if isinstance(other, Property) else other)

    def __getitem__(self, property_name):
        """Will make the verification."""
        if not self.record:
            return False

        values = self.field.convert_to_read(
            self._values, self.record, use_display_name=False)
        prop = next((p for p in values if p['name'] == property_name), False)
        if not prop:
            raise KeyError(property_name)

        if prop.get('type') in ('many2one', 'many2many') and prop.get('comodel'):
            model = _model_of(prop.get('comodel'))
            if model is None:
                return False
            value = prop.get('value')
            pks = ([value] if prop['type'] == 'many2one' and value
                   else (value or []))
            return model.objects.filter(pk__in=pks)

        if prop.get('type') == 'selection' and prop.get('value'):
            if get_context().get('property_selection_get_key'):
                return next((sel[0] for sel in prop.get('selection')
                             if sel[0] == prop['value']), False)
            return next((sel[1] for sel in prop.get('selection')
                         if sel[0] == prop['value']), False)

        if prop.get('type') == 'tags' and prop.get('value'):
            return ', '.join(tag[1] for tag in prop.get('tags')
                             if tag[0] in prop['value'])

        return prop.get('value') or False

    def __hash__(self):
        """La fuente congela con ``frozendict``; aquí basta el JSON canónico.

        ``frozendict`` de la fuente existe para hacer *hashable* un dict que su
        caché de ORM comparte. Aquí el valor no vive en una caché compartida, y
        el JSON con claves ordenadas da el mismo invariante —dos valores
        iguales tienen el mismo hash— sin arrastrar el tipo.
        """
        return hash(json.dumps(self._values, sort_keys=True, default=str))


class PropertiesDefinition(models.JSONField):
    """≙ ``PropertiesDefinition`` (``odoo19c: fields_properties.py:844-1063``).

    «Field used to define the properties definition. This field is used on the
    container record to define the structure of expected properties on
    subrecords. It is used to check the properties definition.»

    Hasta ``api@43fb9385`` esto era ``PropertiesDefinition = models.JSONField``,
    un alias pelado, y el alias **no validaba nada**: una definición con una
    clave inventada, un tipo desconocido o dos propiedades con el mismo nombre
    entraba a la columna y sólo se notaba al leerla. Es lo que este porte
    cierra (tarea #130).

    Como ``Properties`` y ``Html``, :meth:`deconstruct` devuelve la ruta de
    ``django.db.models.JSONField``: las migraciones generadas cuando era un
    alias siguen siendo idénticas.
    """

    def __init__(self, *args, related=None, store=_UNSET, **kwargs):
        """Recibe el vocabulario de la fuente y lo reenvía al constructor.

        ``fields.PropertiesDefinition(store=False)`` llegó a levantar
        ``TypeError``, y la ausencia no era una divergencia declarada: en la
        fuente es un ``Field`` como los demás
        (``odoo19c: odoo/orm/fields_properties.py:844``) y todo ``Field``
        admite ``store`` (``odoo/orm/fields.py:278``). Que hoy ninguna
        declaración de la referencia lo pida (**0** medidas en
        ``addons/*/models/*.py``) no autoriza a portar menos: el molde es el
        del tipo, no el de sus consumidores de hoy.
        """
        if store is not _UNSET:
            kwargs['store'] = store
        related_attrs = apply_source_defaults(related, kwargs)
        super().__init__(*args, **kwargs)
        annotate_related(self, related, related_attrs)

    #: Los campos ``Properties`` que consumen esta definición. Lo puebla
    #: ``Properties.setup``, igual que la fuente.
    properties_fields = ()

    REQUIRED_KEYS = ('name', 'type')
    ALLOWED_KEYS = (
        'name', 'string', 'type', 'comodel', 'default', 'suffix',
        'selection', 'tags', 'domain', 'view_in_cards', 'fold_by_default',
        'currency_field',
    )
    #: those keys will be removed if the types does not match
    PROPERTY_PARAMETERS_MAP = {
        'comodel': {'many2one', 'many2many'},
        'currency_field': {'monetary'},
        'domain': {'many2one', 'many2many'},
        'selection': {'selection'},
        'tags': {'tags'},
    }

    def deconstruct(self):
        """Deconstruye como ``django.db.models.JSONField`` — ver el docstring."""
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.JSONField', args, kwargs

    column_conversion_needs_record = True

    def convert_to_column(self, value, record, values=None, validate=True):
        """≙ ``convert_to_column`` (``odoo19c: :871-908``) — la forma de columna."""
        if not value:
            return None
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, list):
            raise TypeError(f'Wrong properties definition type {type(value)!r}')

        if validate:
            Properties._remove_display_name(value, value_key='default')
            self._validate_properties_definition(value, record)

        return json.dumps(
            record._convert_to_cache_properties_definition(value))

    def convert_to_cache(self, value, record, validate=True):
        """≙ ``convert_to_cache`` (``odoo19c: :910-929``).

        «any format -> cache format (list of dicts or None)». El rodeo por
        ``json.dumps``/``loads`` de la fuente se porta con su razón verbatim:
        *"avoid accidental side effects from shared mutable data, and make the
        value strict with respect to JSON (tuple -> list, etc)"*.
        """
        if not value:
            return None

        if isinstance(value, list):
            value = json.dumps(value)
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, list):
            raise TypeError(f'Wrong properties definition type {type(value)!r}')

        if validate:
            Properties._remove_display_name(value, value_key='default')
            self._validate_properties_definition(value, record)

        return record._convert_to_column_properties_definition(value)

    def convert_to_record(self, value, record):
        """≙ ``convert_to_record`` (``odoo19c: :931-975``).

        Limpia la definición **al leerla**: una propiedad sin sus claves
        obligatorias se ignora, un comodelo cuyo módulo se desinstaló pasa a
        ``False``, y un ``selection``/``tags`` sin opciones sale con lista
        vacía en vez de con la clave ausente.
        """
        if not value:
            return []

        result = []
        for property_definition in value:
            if not all(property_definition.get(key)
                       for key in self.REQUIRED_KEYS):
                # some required keys are missing, ignore this property definition
                continue

            # don't modify the value in cache
            property_definition = copy.deepcopy(property_definition)
            type_ = property_definition.get('type')

            if type_ in ('many2one', 'many2many'):
                # check if the model still exists, the module of the model
                # might have been uninstalled
                property_model = property_definition.get('comodel')
                if _model_of(property_model) is None:
                    property_definition['comodel'] = False
                    property_definition.pop('domain', None)

            elif type_ in ('selection', 'tags'):
                # always set at least an empty array if there's no option
                property_definition[type_] = property_definition.get(type_) or []

            result.append(property_definition)

        return result

    def convert_to_read(self, value, record, use_display_name=True):
        """≙ ``convert_to_read`` (``odoo19c: :977-985``)."""
        if not value:
            return value
        if use_display_name:
            Properties._add_display_name(value, value_keys=('default',))
        return value

    def convert_to_write(self, value, record):
        """≙ ``convert_to_write`` (``odoo19c: :987-988``)."""
        return value

    def _validate_properties_definition(self, properties_definition, record):
        """≙ ``_validate_properties_definition`` (``odoo19c: :990-1063``).

        «Raise an error if the property definition is not valid.» Es el símbolo
        que el alias no tenía, y el que impide que llegue a la columna un
        esquema que la lectura no sabrá deshacer: clave no permitida, clave
        obligatoria ausente, nombre duplicado, tipo desconocido, sufijo
        ``_html`` sin tipo ``html``, comodelo inexistente, opciones o etiquetas
        mal formadas o duplicadas.

        DIVERGENCIA DE FIRMA, la misma del bloque de arriba: la fuente recibe
        ``env`` y pide los dos enganches de extensión a ``env["base"]``, que es
        «cualquier modelo» — los declara ``BaseModel``. Aquí el entorno es
        ambiente, así que el receptor es el **registro** que ya llega a los dos
        llamadores; los enganches viven en ``orm.models.RecordLoaderMixin``,
        junto a ``_clean_properties``, igual que la fuente los declara junto al
        suyo (``odoo19c: odoo/orm/models.py:5070-5084``).
        """
        allowed_keys = self.ALLOWED_KEYS + tuple(
            record._additional_allowed_keys_properties_definition())
        record._validate_properties_definition(properties_definition, self)

        properties_names = set()

        for property_definition in properties_definition:
            for property_parameter, allowed_types in self.PROPERTY_PARAMETERS_MAP.items():
                if (property_definition.get('type') not in allowed_types
                        and property_parameter in property_definition):
                    raise ValueError(
                        f'Invalid property parameter {property_parameter!r}')

            property_definition_keys = set(property_definition.keys())

            invalid_keys = property_definition_keys - set(allowed_keys)
            if invalid_keys:
                raise ValueError(
                    'Some key are not allowed for a properties definition [%s].'
                    % ', '.join(invalid_keys))

            check_property_field_value_name(property_definition['name'])

            required_keys = set(self.REQUIRED_KEYS) - property_definition_keys
            if required_keys:
                raise ValueError(
                    'Some key are missing for a properties definition [%s].'
                    % ', '.join(required_keys))

            property_type = property_definition.get('type')
            property_name = property_definition.get('name')
            if not property_name or property_name in properties_names:
                raise ValueError(
                    f'The property name {property_name!r} is not set or duplicated.')
            properties_names.add(property_name)

            if property_type == 'html' and not property_name.endswith('_html'):
                raise ValueError("HTML property name should end with `_html`.")

            if property_type != 'html' and property_name.endswith('_html'):
                raise ValueError("Only HTML properties can have the `_html` suffix.")

            if property_type and property_type not in Properties.ALLOWED_TYPES:
                raise ValueError(f'Wrong property type {property_type!r}.')

            model_name = property_definition.get('comodel')
            if model_name and _model_of(model_name) is None:
                raise ValueError(f'Invalid model name {model_name!r}')

            property_selection = property_definition.get('selection')
            if property_selection:
                if (not is_list_of(property_selection, (list, tuple))
                        or not all(len(selection) == 2
                                   for selection in property_selection)):
                    raise ValueError(f'Wrong options {property_selection!r}.')

                all_options = [option[0] for option in property_selection]
                if len(all_options) != len(set(all_options)):
                    duplicated = set(filter(
                        lambda x: all_options.count(x) > 1, all_options))
                    raise ValueError(
                        f'Some options are duplicated: {", ".join(duplicated)}.')

            property_tags = property_definition.get('tags')
            if property_tags:
                if (not is_list_of(property_tags, (list, tuple))
                        or not all(len(tag) == 3 and isinstance(tag[2], int)
                                   for tag in property_tags)):
                    raise ValueError(
                        f'Wrong tags definition {property_tags!r}.')

                all_tags = [tag[0] for tag in property_tags]
                if len(all_tags) != len(set(all_tags)):
                    duplicated = set(filter(
                        lambda x: all_tags.count(x) > 1, all_tags))
                    raise ValueError(
                        f'Some tags are duplicated: {", ".join(duplicated)}.')
