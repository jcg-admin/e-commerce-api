"""Campos del ORM — agregador, fiel a ``odoo/orm/fields.py`` (Odoo 19).

En Odoo 19 los campos se definen por **categoría** en
``odoo/orm/fields_{textual,numeric,temporal,selection,relational,binary,misc,
reference,properties}.py`` y se agregan hacia la superficie pública. Aquí se
replica el split (monolito modular: un archivo por categoría) y este módulo los
**agrega**; ``src/fields/__init__.py`` (≙ ``odoo/fields/__init__.py``) re-exporta
de aquí + ``Command``.

Cada nombre mapea el *nombre* de campo de Odoo → la clase de Django; la *firma*
difiere (alias de lectura con parámetros Django).

Además: ``falsy_value`` y ``condition_to_q``
============================================

La fuente declara en **este mismo archivo** dos piezas que no son un campo sino
el contrato de un campo frente a un dominio:

- ``Field.falsy_value`` (``odoo19c: odoo/orm/fields.py:254``) — el valor que
  cuenta como *no establecido* para las comparaciones.
- ``Field.condition_to_sql`` (``:1249``) — cómo un ``(campo, operador, valor)``
  se convierte en la cláusula que va al ``WHERE``.

Aquí se portan como **funciones sobre el campo de Django**, no como atributos y
métodos de clase. La divergencia es forzada y se declara: nuestros campos NO son
clases propias sino **alias de las de Django** (``Integer = models.IntegerField``,
``fields_numeric.py:11``), así que no hay clase donde colgar ni el atributo ni el
método sin subclasar los veinte campos de Django — un cambio con impacto en
migraciones que ninguna necesidad de hoy justifica.

El **sitio** sí es el de la fuente: los dos símbolos viven donde la referencia
los declara, que es lo que ``atributos-de-clase-de-modelo.md`` exige en su
segunda cláusula.

El campo no persistido es otra categoría del mismo split
========================================================

``orm/fields_nonstored.py`` construye el ``store=False`` de la referencia: un
campo que se calcula al leerlo y nunca escribe columna. Medido: **66**
ocurrencias de ``store`` en ``odoo19c: odoo/orm/fields.py`` — el mecanismo vive
allá **dentro de este mismo archivo**, sin archivo propio.

Aquí es un archivo aparte por la misma razón que las nueve categorías de
arriba: este módulo **agrega**, no define. No se re-exporta desde este
agregador porque no es una clase de campo de Django y no puede aparecer en
``_meta.get_fields()``; se importa por su nombre. Ver :ref:`h-api-855`.
"""
import collections
import inspect
import itertools
import logging
import operator as operator_module
import re
import warnings
import weakref
from decimal import Decimal
from operator import attrgetter
from typing import TypeVar

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import DEFAULT_DB_ALIAS, connections, models
from django.db.models.fields.related import RelatedField
from django.db.models.query_utils import DeferredAttribute
from django.utils.timezone import localtime
from psycopg.types.json import Jsonb

from orm.environments import (env as get_environment, get_current_company,
                             get_transaction, sudo as elevate_privileges)
from tools.constants import PREFETCH_MAX
from tools.misc import SENTINEL, OrderedSet, remove_accents, unique
from tools.translate import _
from orm import registry as orm_registry
from orm.registry import (IR_MODELS, UNACCENT_ENABLED,   # noqa: F401
                          Registry,
                          field_computed as registry_field_computed,
                         field_depends_context, is_not_null)
from tools.sql import (SQL, convert_column, create_column, drop_not_null,
                       pg_varchar, set_not_null, sql_order_by_type)

from orm.model_classes import ensure_field_setup
from orm.fields_binary import Binary, Image                    # noqa: F401
from orm.fields_misc import Boolean, Json                      # noqa: F401
from orm.fields_numeric import Float, Integer, Monetary        # noqa: F401
from orm.fields_nonstored import (                          # noqa: F401
    NonStored,
    annotate_related,
    apply_source_defaults,
)
from orm.fields_properties import (                            # noqa: F401
    Properties,
    PropertiesDefinition,
)
from orm.fields_reference import Many2oneReference, Reference  # noqa: F401
from orm.fields_relational import Many2many, Many2one, One2many  # noqa: F401
from orm.fields_selection import Selection                     # noqa: F401
from orm.fields_temporal import Date, Datetime                 # noqa: F401
from orm.fields_textual import Char, Html, Text                # noqa: F401
from orm.utils import (COLLECTION_TYPES, as_record_list, browse, expand_ids,
                       model_field_registry, model_of, model_of_field,
                       record_ids)

#: La clave del almacén de la instancia donde se anotan los campos escritos
#: cuyo inverso todavía no se ha despachado. Vive en ``__dict__`` y no en una
#: ranura porque es lo que ya hace ``_orm_building`` en este mismo descriptor;
#: la escribe :meth:`ComputedFieldDescriptor._mark_pending_inverse` y la
#: **saca** —no la lee— :meth:`~orm.models.RecordLoaderMixin.save`, que es lo
#: que impide que un segundo ``save()`` de la misma fila vuelva a despacharlo.
PENDING_INVERSE_FIELDS = '_pending_inverse_fields'

#: El **registro de tipos de campo**, no la lista de exportables del módulo.
#:
#: ``base.models.ir_model`` lo consume literalmente: deriva ``FIELD_TYPES`` de
#: esta secuencia (``ir_model.py:147,164``) y con ella puebla las opciones de
#: ``IrModelFields.ttype``. Un nombre que no sea una clase de campo entra al
#: vocabulario de ``ttype`` y ensucia el modelo — y lo hace **en silencio**,
#: porque la única señal es una migración inesperada.
#:
#: Por eso ``falsy_value``, ``condition_to_q``, ``SqlLike`` y ``SqlILike`` NO
#: están aquí: son funciones y ``Lookup``, no tipos de campo. Siguen siendo
#: importables por nombre —que es como los consume ``orm.domains``— porque
#: ``__all__`` sólo gobierna ``from orm.fields import *``. Ver
#: :ref:`h-api-616`.
__all__ = [
    'Char', 'Text', 'Html', 'Integer', 'Float', 'Monetary', 'Date', 'Datetime',
    'Selection', 'Many2one', 'One2many', 'Many2many', 'Binary', 'Image',
    'Boolean', 'Json', 'Reference', 'Many2oneReference', 'Properties',
    'PropertiesDefinition',
]


# === El LIKE crudo que Django no expone ====================================
#
# La referencia emite el patrón **tal cual lo escribió el dominio**:
# ``need_wildcard = '=' not in operator`` y, si hace falta, ``f"%{value}%"``
# (``odoo19c: odoo/orm/fields.py:1319-1325``). Los cuatro operadores ``=like``
# / ``not =like`` / ``=ilike`` / ``not =ilike`` existen justamente para NO
# añadir comodines: el patrón lo pone quien escribe el dominio.
#
# Django no tiene con qué expresarlo. ``__contains`` envuelve en ``%…%`` y
# **escapa** ``%`` y ``_`` del valor (``django/db/models/lookups.py``), así que
# un ``=like`` con comodín propio saldría literal. Por eso se construyen los dos
# lookups —el camino 1 de ``porte-completo-no-parcial.md``: API pública del
# stack antes que rodeo.
#
# El ``::text`` replica el ``sql_left = sql_field if self.is_text else
# SQL("%s::text", sql_field)`` de la fuente (``:1317``): un ``LIKE`` sobre una
# columna no textual necesita el cast en PostgreSQL.


class SqlLike(models.Lookup):
    """``LIKE`` sin envoltura ni escape — el patrón lo pone el dominio."""

    lookup_name = 'sql_like'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f'{lhs}::text LIKE {rhs}', (*lhs_params, *rhs_params)


class SqlILike(models.Lookup):
    """``ILIKE`` sin escape, insensible a mayúsculas **y a acentos**.

    Los dos lados van envueltos en ``unaccent(...)``, que es lo que la fuente
    hace cuando la extensión está presente
    (``odoo19c: odoo/orm/fields.py:1326-1327``)::

        sql_left = model.env.registry.unaccent(sql_left)
        sql_value = model.env.registry.unaccent(sql_value)

    Envolver **los dos** no es simetría cosmética: normalizar sólo la columna
    dejaría el patrón con su acento y «Ácme» no encontraría a «ácme».

    La extensión que provee la función es ``unaccent``, el contrib de
    PostgreSQL; la crea ``base/migrations/0084_unaccent_extension.py`` en toda
    base que el ORM construya. El hermano sensible a mayúsculas
    (:class:`SqlLike`) **no** la usa, igual que en la fuente: allá la
    envoltura está dentro de ``if operator.endswith('ilike')``.
    """

    lookup_name = 'sql_ilike'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        if UNACCENT_ENABLED:
            return (f'unaccent({lhs}::text) ILIKE unaccent({rhs})',
                    (*lhs_params, *rhs_params))
        return f'{lhs}::text ILIKE {rhs}', (*lhs_params, *rhs_params)


models.Field.register_lookup(SqlLike)
models.Field.register_lookup(SqlILike)


# === falsy_value ============================================================
#
# La fuente lo declara por clase de campo. Medido en ``odoo19c``:
#
#   Boolean.falsy_value = False   (fields_misc.py:26)
#   Integer.falsy_value = 0       (fields_numeric.py:21)
#   Float.falsy_value = 0.0       (fields_numeric.py:111)
#   Monetary.falsy_value = 0.0    (fields_numeric.py:197)
#   BaseString.falsy_value = ''   (fields_textual.py:38 — Char, Text, Html)
#
# El resto lo hereda de ``Field.falsy_value = None`` (``fields.py:254``), que
# significa «este campo no tiene valor falsy: sólo NULL cuenta como no
# establecido». ``Json`` entra ahí, y es correcto: la fuente no le asigna
# ninguno.
#
# La clave primaria es la fila que NO se deduce de la tabla de arriba: en
# Django ``BigAutoField`` hereda de ``IntegerField``, así que sin declararla
# valdría ``0``. La fuente dice lo contrario — ``class Id(Field)``
# (``odoo19c: fields_misc.py:89``) **no** es subclase de ``Integer``, y por
# tanto hereda ``Field.falsy_value = None``. Ahí descansa una conducta
# observable: ``_optimize_in_required`` sólo retira el ``False`` de un ``in``
# cuando el campo no tiene valor falsy, y en la fuente
# ``('id', 'in', [1, False])`` sí lo retira.
#
# ``EmailField``/``SlugField``/``URLField`` heredan de ``CharField`` (falsy
# ``''``) por MRO, así que no hace falta nombrarlas.

#: La correspondencia entre la clase de campo de la FUENTE y la de Django.
#:
#: Es conocimiento de **porte**, no un detalle de ``falsy_value``: dice que el
#: ``Boolean`` de allá es ``BooleanField`` aquí, y que su ``Id`` son las tres
#: clases concretas de clave primaria. Vive aquí —y no en el gate que lo
#: consume— porque una segunda copia sería la segunda fuente de verdad que
#: `calibration-verified-numbers.md` prohíbe: el día que se porte un tipo
#: nuevo, el mapa se actualiza en un sitio.
#:
#: Lo consume :data:`_FALSY_VALUE_TARGET_CLASSES` y el gate
#: ``scripts/check_field_class_attributes.py``, que compara lo que cada clase
#: de la fuente declara contra lo que la de Django responde.
#:
#: ``AutoField`` **no** basta: en Django ``BigAutoField`` y ``SmallAutoField``
#: no lo tienen en su MRO —su cadena es ``BigAutoField → AutoFieldMixin →
#: BigIntegerField → IntegerField``— y ``AutoFieldMixin`` no se exporta en
#: ``django.db.models``. Lo que los hace pasar por ``AutoField`` es el
#: ``__subclasscheck__`` de su metaclase, que gobierna ``isinstance`` y **no**
#: la búsqueda de atributos. Medido: con ``IntegerField.x = 0`` y
#: ``AutoField.x = None``, ``BigAutoField.x`` vale ``0``.
#:
#: Por eso las tres clases concretas de clave primaria se nombran una a una.
REFERENCE_CLASS_TO_DJANGO = {
    'Boolean': (models.BooleanField,),
    'Integer': (models.IntegerField,),
    'Float': (models.FloatField,),
    'Monetary': (models.DecimalField,),
    'BaseString': (models.CharField, models.TextField),
    'Id': (models.AutoField, models.BigAutoField, models.SmallAutoField),
    'Json': (models.JSONField,),
    'Binary': (models.BinaryField,),
    'Date': (models.DateField,),
    'Datetime': (models.DateTimeField,),
    'Selection': (models.CharField,),
    'Char': (models.CharField,),
    'Text': (models.TextField,),
    'Html': (Html,),
    '_Relational': (models.ForeignKey, models.ManyToManyField),
    'Many2one': (models.ForeignKey,),
    'Many2many': (models.ManyToManyField,),
    'One2many': (One2many,),
    'Properties': (Properties,),
    'PropertiesDefinition': (PropertiesDefinition,),
    'Many2oneReference': (Many2oneReference,),
}

#: Lo que cada clase concreta de la fuente declara, y que su clase de Django
#: tiene que responder.
#:
#: Las claves salen de :data:`REFERENCE_CLASS_TO_DJANGO`, no de una segunda
#: lista: si mañana ``BaseString`` gana una tercera clase de destino, ésta la
#: hereda sin que nadie se acuerde. Los **valores** sí se declaran aquí — son
#: la declaración portada, y leerlos de la referencia en tiempo de import
#: convertiría un árbol de consulta en una dependencia de arranque. Quien
#: comprueba que coinciden con la fuente es
#: ``scripts/check_field_class_attributes.py``, que la lee por AST.
#:
#: Cada entrada cita la línea de su declaración allá. Lo que **no** cabe aquí
#: —porque la fuente lo declara como ``property`` y depende de la instancia—
#: se instala más abajo: ``Char._column_type`` y ``Float._column_type``.
_CLASS_ATTRIBUTE_OVERRIDES = {
    #: ``Id`` (``fields_misc.py:89-95``). Es el bloque que más mentía: las tres
    #: clases de clave automática de Django cuelgan del ``Field`` base, así que
    #: heredaban su defecto entero. ``AutoFieldMeta.__subclasscheck__`` hace
    #: que ``issubclass(BigAutoField, AutoField)`` sea cierto sin que
    #: ``AutoField`` esté en el MRO; la **resolución de atributo** sigue el
    #: MRO, no la metaclase, así que hay que colgarlo de las tres.
    #:
    #: ``column_type`` va aquí, no ``_column_type``: la fuente lo declara en el
    #: atributo público, saltándose la ``property`` de ``Field``. Un atributo
    #: de clase en la subclase gana a una ``property`` de la clase base porque
    #: la búsqueda para en la primera clase del MRO que lo tenga.
    'Id': {
        'falsy_value': None,
        #: ``aggregator`` NO lo declara ``Id`` allá: lo hereda de ``Field``, que
        #: dice ``None``. Aquí hay que decirlo **explícitamente** porque las
        #: tres clases de clave automática de Django descienden de
        #: ``IntegerField``, que sí recibe el ``'sum'`` de ``Integer``. La
        #: fuente no tiene ese problema: su ``Id`` cuelga de ``Field``, no de
        #: ``Integer``. Es la misma diferencia de árbol que obligó a declarar
        #: ``falsy_value: None`` aquí arriba, y la destapó el gate.
        'aggregator': None,
        'string': 'ID',
        'store': True,
        'readonly': True,
        'prefetch': False,
        'column_type': ('int4', 'int4'),
        #: ``Field._column_type = None`` (``odoo19c: odoo/orm/fields.py:259``)
        #: y ``Id`` cuelga de ``Field``: la clave primaria NO hereda el
        #: ``('int4','int4')`` de ``Integer``. Aquí sí lo heredaría —
        #: ``AutoField(IntegerField)``—, que es la misma divergencia de árbol
        #: de :ref:`h-api-970`. Quien publica el tipo de la columna de la
        #: clave es ``column_type``, la línea de arriba.
        '_column_type': None,
    },
    'Boolean': {                                   # ``fields_misc.py:24-25``
        'falsy_value': False,
        '_column_type': ('bool', 'bool'),
    },
    'Json': {                                      # ``fields_misc.py:65``
        '_column_type': ('jsonb', 'jsonb'),
    },
    'Integer': {                                   # ``fields_numeric.py:20-21``
        'falsy_value': 0,
        'aggregator': 'sum',
        '_column_type': ('int4', 'int4'),
    },
    #: ``Float`` (``fields_numeric.py:107``, ``:125-133``). El agregado es
    #: literal allá; el tipo de columna es una ``property`` que devuelve
    #: ``('numeric','numeric')`` con dígitos declarados y ``('float8','float8')``
    #: sin ellos. **Divergencia de mecanismo declarada:** en este stack la rama
    #: de dígitos es *otra clase* —``DecimalField``, que recibe la declaración
    #: de ``Monetary``—, así que ``FloatField`` sólo puede ser la otra rama. No
    #: se recorta nada: las dos ramas existen, repartidas en dos clases.
    'Float': {
        'falsy_value': 0.0,
        'aggregator': 'sum',
        '_column_type': ('float8', 'float8'),
    },
    'Monetary': {                                  # ``fields_numeric.py:196-197``
        'falsy_value': Decimal('0'),
        'aggregator': 'sum',
        '_column_type': ('numeric', 'numeric'),
    },
    'BaseString': {                                # ``fields_textual.py:33``
        'falsy_value': '',
    },
    'Text': {                                      # ``fields_textual.py:542``
        '_column_type': ('text', 'text'),
    },
    'Many2one': {                                  # ``fields_relational.py:245``
        '_column_type': ('int4', 'int4'),
    },
    'Binary': {                                    # ``fields_binary.py``
        'prefetch': False,
    },
    'Properties': {                                # ``fields_properties.py:53``
        '_column_type': ('jsonb', 'jsonb'),
        'prefetch': False,
        'readonly': False,
    },
    'PropertiesDefinition': {                      # ``fields_properties.py:850``
        '_column_type': ('jsonb', 'jsonb'),
        'readonly': False,
        'prefetch': True,
    },
    #: ``Many2oneReference`` (``fields_reference.py``) hereda de ``Integer``
    #: allá, así que su ``falsy_value`` es el ``0`` de aquél; su ``aggregator``
    #: sí lo declara propio, anulando el ``'sum'`` que heredaría. Aquí no
    #: desciende de ``IntegerField``, de modo que las dos cosas hay que
    #: decirlas: la heredada y la declarada.
    'Many2oneReference': {
        'falsy_value': 0,
        'aggregator': None,
        #: ``Many2oneReference(Integer)`` guarda el id crudo del registro
        #: apuntado, así que hereda la columna del entero. Aquí
        #: ``GenericForeignKey`` no desciende de ``IntegerField``, y sin
        #: declararlo respondía ``None``: la columna que la fuente declara
        #: desaparecía.
        '_column_type': ('int4', 'int4'),
    },
}


def install_class_attribute_overrides():
    """Instala por clase lo que la fuente declara por clase.

    El bucle de :data:`_FIELD_CLASS_ATTRIBUTES` pone el defecto de ``Field`` en
    ``models.Field`` y nada más, así que **toda** clase concreta respondía ese
    defecto. Medido antes de esta función: un ``IntegerField`` decía
    ``falsy_value=None`` donde la fuente dice ``0``; un ``AutoField`` decía
    ``readonly=False`` donde dice ``True``, y su lector ``is_editable``
    declaraba editable la clave primaria de todo modelo.

    Se llama **después** del bucle: el bucle pone el defecto y esto lo pisa
    donde la fuente lo pisa. Invertir el orden no cambia nada —son clases
    distintas— pero leerlo así deja claro cuál es el defecto y cuál la
    excepción.
    """
    for reference_name, overrides in _CLASS_ATTRIBUTE_OVERRIDES.items():
        for field_class in REFERENCE_CLASS_TO_DJANGO[reference_name]:
            for attribute, value in overrides.items():
                setattr(field_class, attribute, value)


def falsy_value(field):
    """El valor que cuenta como *no establecido* — ≙ ``Field.falsy_value``.

    Lee el **atributo**, que es donde la fuente lo declara; la función existe
    para dos cosas que el atributo no da: tolerar ``field is None`` (el caso
    del campo desconocido) y ser el punto único que el resto del ORM importa.

    Devuelve ``None`` cuando el campo no tiene ninguno, que es el defecto de la
    fuente y también lo que se responde ante un campo desconocido: es la
    hipótesis conservadora, porque ``falsy_value is None`` es lo que hace que
    ``_negate`` añada la rama ``OR campo IS NULL``.
    """
    if field is None:
        return None
    return getattr(field, 'falsy_value', None)


# El subconjunto de ``NEGATIVE_CONDITION_OPERATORS`` que la familia ``like``
# usa. La fuente lo lee de ``Domain.NEGATIVE_OPERATORS`` (``:1331``), pero
# importarlo aquí cierra un ciclo —``domains`` ya importa de este módulo—, y un
# import dentro de la función está prohibido (``no-lazy-imports.md``). Unificar
# los dos en un hogar compartido es la tarea **#380**.
_NEGATIVE_LIKE_OPERATORS = frozenset([
    'not like', 'not ilike', 'not =like', 'not =ilike',
])

#: Los nueve operadores de semántica negativa — ≙ ``NEGATIVE_CONDITION_OPERATORS``
#: (``odoo19c: odoo/orm/domains.py``). Es la misma segunda copia que
#: ``_NEGATIVE_LIKE_OPERATORS`` declara arriba y por el mismo motivo: el hogar
#: de la fuente es ``domains``, que ya importa de aquí, y un import dentro de
#: la función está prohibido. Unificar los dos en un hogar compartido es la
#: tarea **#380**; hasta entonces la copia se prueba contra la original en
#: ``tests/unit/orm/test_domains.py`` para que no puedan divergir en silencio.
NEGATIVE_CONDITION_OPERATORS = frozenset([
    'not any', 'not any!', 'not in',
    'not like', 'not ilike', 'not =like', 'not =ilike',
    '!=', '<>',
])

#: ¿El ``ilike`` ignora los acentos? — ≙ ``Registry.unaccent_python``
#: (``odoo19c: odoo/orm/registry.py:290``), que es ``remove_accents`` cuando la
#: extensión ``unaccent`` está instalada y la identidad cuando no.
#:
#: Re-exportado de :data:`orm.registry.UNACCENT_ENABLED`, donde vive.
#:
#: El registro es quien sabe si la función existe y el campo quien la consume
#: — es la dirección de la fuente, que lee ``model.env.registry.unaccent``
#: (``odoo19c: odoo/orm/fields.py:1326-1327``). Estuvo declarado aquí hasta
#: 2026-09-03; moverlo fue lo que destrabó el ciclo de import al portar
#: ``Registry`` como clase.
#:
#: Se re-exporta con su nombre porque sus consumidores lo leen de este módulo.


def convert_to_display_name(field, value, record):
    """El valor de un campo, como etiqueta — ≙ ``Field.convert_to_display_name``.

    ≙ ``odoo19c: odoo/orm/fields.py:1080`` y sus cinco sobrecargas
    (``fields_reference.py:55``, ``fields_relational.py:397`` y ``:715``,
    ``fields_temporal.py:187`` y ``:291``). Es lo que ``_compute_display_name``
    aplica al campo que ``_rec_name`` nombra.

    **Ya NO es la implementación: es la puerta.** El método vive donde la
    fuente lo declara —``models.Field.convert_to_display_name`` y sus cinco
    sobrecargas, adjuntas a la clase de campo que cada una especializa—, y esta
    función **delega** en él. Se conserva por dos consumidores que no pueden
    llamar al método:

    - ``orm/models.py:_compute_display_name``, que resuelve el campo por
      ``_rec_name`` y puede no encontrarlo (``field is None``);
    - una **relación inversa** de Django (``ManyToOneRel``, ``ManyToManyRel``),
      que **no es un** ``Field`` y por tanto no recibe ningún método de campo.
      Darle el vocabulario de campo de la fuente es la tarea **#347**; hasta
      entonces su rama vive aquí.

    Las cinco sobrecargas, y dónde vive cada una:

    - **relacional a uno** (``Many2one``, ``Reference``) → el ``display_name``
      del registro apuntado — ``fields_relational.py``, sobre
      ``models.ForeignKey`` y ``models.OneToOneField``.
    - **relacional a muchos** (``Many2many``, ``One2many``) →
      ``NotImplementedError`` verbatim de la fuente
      (``odoo19c: fields_relational.py:715``): un ``_rec_name`` que nombre una
      colección no tiene etiqueta única, y devolver algo inventado escondería
      el error de declaración.
    - **fecha y fecha-hora** → ``fields_temporal.py:410`` y ``:423``, ya
      adjuntas desde el porte de esa categoría.
    - **el resto** → el método base de este archivo,
      ``str(value) if value else False``, con su ``False`` y no ``None``: es el
      valor que la fuente devuelve para un campo vacío, y
      ``_compute_display_name`` lo distingue.
    """
    if field is not None and hasattr(field, 'convert_to_display_name'):
        return field.convert_to_display_name(value, record)
    if isinstance(field, (models.ManyToOneRel, models.ManyToManyRel)):
        raise NotImplementedError(
            f'convert_to_display_name no aplica a {field!r}: una colección no '
            f'tiene etiqueta única')
    return str(value) if value else False


_INEQUALITY_LOOKUP = {'<': 'lt', '>': 'gt', '<=': 'lte', '>=': 'gte'}



def condition_to_q(field_expr, operator, value, field=None):
    """Un ``(campo, operador, valor)`` a ``Q`` — ≙ ``Field._condition_to_sql``.

    Réplica de ``odoo19c: odoo/orm/fields.py:1262-1366`` **en semántica**, no en
    forma emitida. La diferencia de forma la impone algo que hubo que medir
    antes de escribir esta función, y que corrige la premisa con la que se abrió
    la iniciativa (:ref:`h-api-614`).

    Lo que Django ya hace, medido
    ------------------------------

    La fuente construye el ``WHERE`` a mano y por eso añade la rama de nulos
    explícitamente (``(cond) OR campo IS NULL``). El compilador de Django **ya
    la añade**, con otra forma y el mismo resultado::

        ~Q(user_type__sql_like='%a%')
        -> NOT ("user_type"::text LIKE %a% AND "user_type" IS NOT NULL)

        ~Q(name__sql_like='%a%')      # name es NOT NULL
        -> NOT ("name"::text LIKE %a%)

    Es exactamente la regla de la fuente: con columna nulable la fila sin valor
    **entra**; con columna no nulable no hay nulos que considerar. Así que
    replicar el ``OR campo IS NULL`` encima sería redundante — produciría un
    ``WHERE`` más largo con idéntico conjunto de filas.

    Dónde SÍ diverge, y es al revés de lo que se creía
    --------------------------------------------------

    Dos casos, los dos porque Django es **más** incluyente que la fuente:

    1. ``not in`` con ``False`` en la colección. La fuente emite un
       ``NOT IN`` pelado, y ``NULL NOT IN (x)`` es ``NULL``: la fila sin valor
       **se descarta**, que es lo que «tiene valor y no es x» significa. El
       ``~Q`` de Django la incluiría. Se fuerza con ``isnull=False``.
    2. Las desigualdades. ``Q(campo__lt=v)`` no incluye nulos, y la fuente sí
       cuando el valor *falsy* del campo satisface la comparación
       (``accept_null_value``, ``:1341-1346``). Ahí la rama se añade a mano.

    :param field_expr: ruta de campo ya en notación Django (``a__b``).
    :param field: la instancia de campo de Django, o ``None`` si no se conoce
        el modelo. Sin campo se asume ``can_be_null=True`` y
        ``falsy_value=None``, que son los defectos de la fuente
        (``Field.falsy_value = None``; un campo está en ``not_null_fields``
        sólo si algo lo declara).

    Cómo se pregunta la nulabilidad
    --------------------------------

    ``self not in model.env.registry.not_null_fields`` allá (``:1281``), y aquí
    :func:`~orm.registry.is_not_null`, que es el mismo criterio: columna real
    de un modelo con tabla, y clave primaria o ``null=False``.

    **Decía ``bool(field.null)``**, que es el atajo que :ref:`h-api-971`
    desmontó en el otro consumidor y que aquí seguía vivo. Medido sobre el
    registro entero: **120 de 5170** campos responden distinto, y los 120 en la
    dirección peligrosa —el atajo dice «no puede ser nula» cuando sí puede—,
    de modo que la rama ``IS NULL`` se retiraba y la fila sin valor
    desaparecía del resultado.

    Las 120 son dos familias: **87** ``ManyToManyField``, que declara
    ``null=False`` sin efecto porque la nulabilidad vive en la tabla
    intermedia; y **33** en modelos ``managed=False``, donde este ORM no emite
    el DDL y por tanto no puede afirmar NOT NULL.
    """
    can_be_null = True if field is None else not is_not_null(field)
    null_value = falsy_value(field)

    # --- in / not in (igualdad) --------------------------------------------
    if operator in ('in', 'not in'):
        values = list(value) if isinstance(value, COLLECTION_TYPES) else [value]
        params = [v for v in values if v is not False and v is not None]
        null_in_condition = len(params) < len(values)
        if null_value is not None:
            if null_value in params:
                null_in_condition = True
            elif null_in_condition:
                params = [*params, null_value]

        q = None
        if params:
            q = models.Q(**{f'{field_expr}__in': params})
            if operator == 'not in':
                q = ~q

        if (operator == 'in') == null_in_condition:
            # La fuente quiere aquí la rama de nulos:
            #   campo in {val, False}  => IN vals     OR campo IS NULL
            #   campo not in {val}     => NOT IN vals OR campo IS NULL
            if operator == 'not in':
                # el ``~Q`` de Django ya la trae; con columna no nulable no
                # hace falta y tampoco la pone
                return q if q is not None else models.Q()
            if not can_be_null:
                return q if q is not None else models.Q(pk__in=[])
            q_null = models.Q(**{f'{field_expr}__isnull': True})
            return (q | q_null) if q is not None else q_null

        if operator == 'not in' and null_in_condition:
            # «tiene valor y no está entre estos» — la fila sin valor NO entra
            if not can_be_null:
                return q if q is not None else models.Q()
            q_set = models.Q(**{f'{field_expr}__isnull': False})
            return (q & q_set) if q is not None else q_set

        assert q is not None, f'falta el Q para {operator} {value!r}'
        return q

    # --- like / ilike / =like / =ilike -------------------------------------
    if operator.endswith('like'):
        need_wildcard = '=' not in operator
        pattern = f'%{value}%' if need_wildcard else str(value)
        lookup = 'sql_ilike' if operator.endswith('ilike') else 'sql_like'
        q = models.Q(**{f'{field_expr}__{lookup}': pattern})
        if operator in _NEGATIVE_LIKE_OPERATORS:
            # ``~Q`` ya emite ``NOT (cond AND campo IS NOT NULL)``, que es la
            # regla de ``:1331-1333`` con otra forma
            q = ~q
        return q

    # --- desigualdades ------------------------------------------------------
    if operator in _INEQUALITY_LOOKUP:
        accept_null_value = False
        if null_value is not None and can_be_null:
            # ≙ ``:1341-1346``: la fila sin valor entra si el propio valor
            # falsy satisface la comparación.
            accept_null_value = (
                null_value < value if operator == '<' else
                null_value > value if operator == '>' else
                null_value <= value if operator == '<=' else
                null_value >= value
            )
        q = models.Q(**{f'{field_expr}__{_INEQUALITY_LOOKUP[operator]}': value})
        if accept_null_value:
            q |= models.Q(**{f'{field_expr}__isnull': True})
        return q

    # --- any / not any ------------------------------------------------------
    if operator in ('any', 'not any', 'any!', 'not any!'):
        # La fuente resuelve el subdominio contra el comodelo y lo inyecta como
        # subselect (``:1352-1365``). Aquí el ORM hace el join por la ruta, así
        # que el caso de ruta con punto lo resuelve ``DomainCondition._to_q``
        # traduciendo ``a.b`` a ``a__b`` antes de llegar aquí. Lo que queda es
        # el ``any`` explícito sobre un Queryset o una lista de ids.
        q = models.Q(**{f'{field_expr}__in': value})
        return ~q if operator.startswith('not ') else q

    raise NotImplementedError(
        f'Operador de dominio no soportado: {(field_expr, operator, value)!r}')


# --- Generación de SQL — ≙ "SQL generation methods" de la fuente ------------
#
# ``odoo19c: odoo/orm/fields.py:1205-1247`` agrupa bajo ese encabezado los dos
# métodos con que un campo se convierte en fragmento ``SQL``. Los consume
# ``BaseModel._field_to_sql`` (``orm/models.py``), la puerta del motor de
# consultas: ``sql = field.to_sql(self, alias)``.
#
# LA DIVERGENCIA, Y ES DE FORMA — la misma que ``orm/models.py`` ya declara
# dos veces (permisos y ``_origin``): allá cuelgan de la clase ``Field``, que
# es de la referencia; aquí la clase base de todo campo es
# ``django.db.models.Field``, que **no es nuestra para declararla**. Se le
# adjuntan al importar este módulo, que es el equivalente exacto de declarar
# el método en la clase: todo campo los tiene, como allá, y el sitio de la
# llamada queda **idéntico al de la fuente**.
#
# La alternativa era una función suelta ``to_sql(field, model, alias)``, que
# obliga a reescribir cada llamada y rompe el despacho por tipo de campo —
# ``Properties`` sobreescribe ``property_to_sql``, y una función no se
# sobreescribe.
#
# Medido antes de adjuntar: ``to_sql`` y ``property_to_sql`` dan ``False`` en
# ``hasattr(models.Field, ...)``, así que no pisan nada de Django.


def _field_to_sql_expression(self, model, alias):
    """``to_sql`` — el valor de este campo desde el alias de tabla dado.

    ≙ ``Field.to_sql`` (``odoo19c: odoo/orm/fields.py:1209-1238``).

    Un campo sin columna no se puede convertir, y la fuente lo dice con el
    mismo error: ``store``/``column_type`` allá, ``concrete``/``column`` aquí
    —un ``models.Field`` es concreto cuando tiene columna propia, y las
    relaciones inversas y los ``ManyToMany`` no la tienen—. El ``NonStored``
    de ``orm/fields_nonstored.py`` ni siquiera llega: no es un campo de
    Django, así que ``_field_to_sql`` lo descarta antes.

    La fuente entrecomilla ``self.name`` porque allá el nombre del campo **es**
    el de la columna. Aquí no siempre: un ``db_column`` explícito o una FK
    —cuyo nombre de columna lleva el sufijo ``_id``— los separan. Lo que va en
    SQL es la **columna**, así que es ``self.column`` lo que se entrecomilla.

    La rama ``company_dependent`` (``odoo19c: :1217-1237``) **sí** tiene
    contraparte desde la tarea #111: la columna es ``jsonb`` con
    ``{empresa: valor}``, así que el SQL extrae la entrada de la empresa
    activa y cae al default de ``ir.default`` cuando no la hay. Es el
    ``COALESCE(col->empresa, to_jsonb(fallback::tipo))`` de la fuente.
    """
    if not getattr(self, 'concrete', False) or not getattr(self, 'column', None):
        raise ValueError(f"Cannot convert {self} to SQL because it is not stored")

    sql_field = SQL.identifier(alias, self.column, to_flush=self)
    if not getattr(self, 'company_dependent', False):
        return sql_field

    # ≙ ``:1218-1237``. El `->>` devuelve texto y el CAST lo lleva al tipo del
    # campo base; la fuente hace lo mismo y explica por qué no basta `->`: un
    # `'null'::jsonb` castea a la cadena 'null' en vez de a NULL.
    company_id = get_current_company()
    fallback = self.get_company_dependent_fallback_sql(model)
    return SQL(
        "COALESCE((%(column)s->>%(company_id)s)::%(cast)s, %(fallback)s)",
        column=sql_field,
        company_id=str(company_id) if company_id is not None else None,
        cast=SQL(self.sql_cast_type),
        fallback=fallback,
    )


def _field_property_to_sql(self, field_sql, property_name, model, alias, query):
    """``property_to_sql`` — el valor de una propiedad dentro del campo.

    ≙ ``Field.property_to_sql`` (``odoo19c: odoo/orm/fields.py:1241-1247``).
    El caso base **rechaza**: sólo un campo que contenga sub-campos sabe
    extraer uno, y quien lo sabe lo sobreescribe — ``Properties`` en
    ``orm/fields_properties.py``, igual que allá.
    """
    raise ValueError(f"Invalid field property {property_name!r} on {self}")


models.Field.to_sql = _field_to_sql_expression
models.Field.property_to_sql = _field_property_to_sql


# === La condición de dominio — ≙ "condition_to_sql" de la fuente ============
#
# ``odoo19c: odoo/orm/fields.py:1249-1377`` declara **tres** símbolos, no uno,
# y el reparto es el contrato:
#
# - ``condition_to_sql`` (``:1249-1260``) — la **fachada de dos pasos**: compone
#   el cuerpo de la condición con la optimización de índice del campo
#   dependiente de empresa. Es lo que ``Domain`` llama (``domains.py:1096``), y
#   lo que un tipo de campo sobreescribe cuando necesita otra forma:
#   ``Properties`` lo hace en los dos árboles.
# - ``_condition_to_sql`` (``:1262-1366``) — el **cuerpo**.
# - ``_condition_to_sql_company`` (``:1368-1377``) — la **optimización**.
#
# DIVERGENCIA DE FORMA, la ya declarada para toda esta capa (ver
# ``orm/domains.py``): el retorno es ``Q`` y no ``SQL``, porque el ``WHERE`` lo
# compone Django. El nombre sigue al tipo de retorno —``condition_to_sql`` es
# ``condition_to_q``, ``_condition_to_sql_company`` es
# ``_condition_to_q_company``— y el guion bajo se conserva: es el contrato de
# visibilidad, no decoración (``porte-completo-no-parcial.md``).
#
# El **cuerpo** ya estaba portado como la función de módulo
# :func:`condition_to_q` (arriba), con su divergencia medida. Aquí se le da su
# nombre de método, ``_condition_to_q``, para que el reparto de tres símbolos
# exista también aquí: sin él, un tipo de campo que quisiera sobreescribir sólo
# el cuerpo tendría que reescribir la fachada entera.


def _field_condition_to_q(self, field_expr, operator, value, model=None):
    """La condición ``(campo, operador, valor)`` a ``Q`` — la fachada.

    ≙ ``Field.condition_to_sql`` (``odoo19c: odoo/orm/fields.py:1249-1260``).

    Dos pasos, en el orden de la fuente: el cuerpo, y encima la optimización
    de índice que sólo aplica al campo dependiente de empresa.

    :param model: la clase de modelo, o ``None`` cuando quien llama no la
        conoce. Sin modelo la optimización no se puede decidir —consulta
        ``ir.default`` por el nombre del modelo— y se devuelve el cuerpo tal
        cual, que es el conjunto de filas correcto en todo caso.
    """
    q = self._condition_to_q(field_expr, operator, value, model)
    if self.company_dependent:
        q = self._condition_to_q_company(q, field_expr, operator, value, model)
    return q


def _field_condition_to_q_body(self, field_expr, operator, value, model=None):
    """El cuerpo de la condición — ≙ ``Field._condition_to_sql`` (``:1262-1366``).

    Delega en la función de módulo :func:`condition_to_q`, que es donde el
    cuerpo vive y donde su divergencia frente a la fuente está medida y
    declarada. El ``model`` no se consume aquí: la fuente lo usa para resolver
    el ``SQL`` de la columna (``model._field_to_sql``) y ese trabajo lo hace
    Django al compilar el ``Q``.

    La ruta con punto pasa a la travesía de Django (``a.b`` → ``a__b``). Se
    escribe aquí en vez de importar ``_django_path`` de ``orm/domains.py``
    porque aquel módulo importa éste, y el import de vuelta cerraría el ciclo
    — la misma razón que ``Properties.condition_to_q`` ya declara.
    """
    return condition_to_q(field_expr.replace('.', '__'), operator, value, self)


def _field_condition_to_q_company(self, q, field_expr, operator, value,
                                  model=None):
    """Antepone ``columna IS NOT NULL`` para que el índice parcial sirva.

    ≙ ``Field._condition_to_sql_company`` (``odoo19c: :1368-1377``).

    **Qué hace, y por qué no cambia el conjunto de filas.** Un campo
    dependiente de empresa guarda ``{empresa: valor}`` en una columna
    ``jsonb``; la fila sin entrada propia responde el respaldo de
    ``ir.default``. Cuando ese respaldo **no** satisface la condición, ninguna
    fila con la columna nula la satisface tampoco — así que exigir
    ``IS NOT NULL`` no descarta ninguna fila que debiera entrar, y deja que
    PostgreSQL use el índice parcial ``WHERE columna IS NOT NULL`` que
    ``registry.check_indexes()`` crea para ``index='btree_not_null'``.

    Las cuatro condiciones son las de la fuente, verbatim en su orden:
    ``company_dependent``, el índice parcial declarado, la exclusión de la
    granularidad temporal (una fecha consultada por una parte suya —``:mes``—
    no la admite), y que el respaldo devuelva ``False`` — **no** un valor
    falso: ``None`` significa «no se puede decidir» y ahí la optimización no
    se aplica.

    *Métrica:* campos que declaran ``company_dependent=True`` **y**
    ``index='btree_not_null'``, por recorrido AST sobre ``addons/`` y
    ``odoo/addons/`` de la referencia, y por ``django.apps`` sobre el árbol
    cargado. *Ciega a:* un campo que reciba el índice fuera de su declaración
    —una migración a mano— y a un campo declarado en un addon que el árbol no
    carga.

    **Su población activadora es cero en los dos árboles**, medido: de los
    **69** campos ``company_dependent`` de ``odoo19c`` ninguno declara además
    ese índice, y aquí son **2 y 0**. Se porta porque el contrato de ``Field``
    lo declara, no porque hoy tenga consumidor: declarar divergencia en vez de
    portar es el camino barato que la norma prohíbe.
    """
    if model is None:
        return q
    if not (
        self.company_dependent
        and self.index == 'btree_not_null'
        # la granularidad de agrupación temporal no la soporta
        and not (self.type in ('datetime', 'date') and field_expr != self.name)
    ):
        return q
    IrDefault = apps.get_model('base', 'IrDefault')
    kept = IrDefault._evaluate_condition_with_fallback(
        model_of(model)._meta.label, field_expr, operator, value)
    if kept is False:
        return models.Q(**{f'{self.name}__isnull': False}) & q
    return q


models.Field.condition_to_q = _field_condition_to_q
models.Field._condition_to_q = _field_condition_to_q_body
models.Field._condition_to_q_company = _field_condition_to_q_company


# === expression_getter / filter_function ====================================
#
# El par que evalúa un dominio **en memoria**, sin ir al motor. La fuente los
# declara como métodos de ``Field``
# (``odoo19c: odoo/orm/fields.py:1384-1477``); aquí se cuelgan de
# ``models.Field`` al final del módulo, igual que ``to_sql`` y
# ``property_to_sql`` — un campo de Django no es nuestro para subclasificar,
# pero el nombre y la firma se conservan.
#
# Su consumidor es ``BaseModel.filtered_domain``, y quien lo necesita es
# ``ir.default._evaluate_condition_with_fallback``: preguntar si el valor de
# respaldo de un campo dependiente de empresa satisface una condición no se
# puede resolver en SQL, porque ese valor **no está en ninguna fila** — es el
# que responde el campo cuando la empresa no tiene el suyo.

#: Los cuatro operadores de desigualdad, a su función de Python.
_PYTHON_INEQUALITY_OPERATOR = {
    '<': operator_module.lt,
    '>': operator_module.gt,
    '<=': operator_module.le,
    '>=': operator_module.ge,
}


def _expression_getter(self, field_expr):
    """Un ``field_expr`` de dominio a la función que lo lee de un registro.

    ≙ ``Field.expression_getter`` (``odoo19c: odoo/orm/fields.py:1384-1394``).
    El caso base sólo sabe leer **el campo entero**; cualquier otra expresión
    la resuelve quien la entienda, sobreescribiendo este método.

    La divergencia de forma: allá el getter es ``self.__get__`` —el campo *es*
    su propio descriptor—; aquí el descriptor es otro objeto
    (:class:`FieldDescriptor`, instalado por :func:`_install_field_descriptor`
    sobre todo campo), así que el getter es ``getattr(record, self.name)``, que
    pasa por él. Mismo contrato y mismo cuerpo: dado un registro, devuelve el
    valor leyendo la caché del ORM.
    """
    if field_expr == self.name:
        return lambda record: getattr(record, self.name)
    raise ValueError(f'Expression not supported on {self}: {field_expr!r}')


def _filter_function(self, records, field_expr, operator, value):
    """Un ``(campo, operador, valor)`` a un predicado de un registro.

    ≙ ``Field.filter_function`` (``odoo19c: odoo/orm/fields.py:1396-1477``).
    Es el gemelo en memoria de :func:`condition_to_q`: aquella compila la
    condición a ``Q`` para que la resuelva PostgreSQL, ésta la compila a una
    función de Python para resolverla sobre registros que ya están en mano.

    **Sólo operadores positivos** — la negación la aplica quien llama, igual
    que allá, para no duplicar cada rama.
    """
    if operator in NEGATIVE_CONDITION_OPERATORS:
        raise ValueError(
            f'filter_function espera un operador positivo, no {operator!r}')
    getter = self.expression_getter(field_expr)

    # --- in (igualdad) ------------------------------------------------------
    if operator == 'in':
        if not isinstance(value, COLLECTION_TYPES) or not value:
            raise ValueError(
                f"filter_function con 'in' espera una colección no vacía, "
                f'no {type(value)}')
        values = value if isinstance(value, (set, frozenset)) else set(value)
        if False in values or falsy_value(self) in values:
            # Un campo sin valor cuenta como que lo tiene, si el conjunto
            # incluye el valor *falsy* — la misma regla que ``condition_to_q``
            # aplica al lado SQL.
            if len(values) == 1:
                return lambda record: not getter(record)
            return lambda record: (
                (val := getter(record)) in values or not val)
        return lambda record: getter(record) in values

    # --- familia like -------------------------------------------------------
    if operator.endswith('like'):
        if operator.endswith('ilike'):
            def normalize(x):
                # ``ilike`` compara en minúsculas, y **sin quitar acentos**
                # mientras ``UNACCENT_ENABLED`` sea falso. Ver su declaración:
                # tiene que decidir lo mismo que el lookup ``sql_ilike``, y ése
                # emite un ``ILIKE`` pelado.
                if not x:
                    return ''
                text = str(x).lower()
                return remove_accents(text) if UNACCENT_ENABLED else text
        else:
            def normalize(x):
                return str(x) if x else ''

        pattern = re.compile(
            ''.join(_like_regex_parts(normalize(value), '=' in operator)),
            flags=re.DOTALL)
        return lambda record: bool(pattern.match(normalize(getter(record))))

    # --- desigualdades ------------------------------------------------------
    if python_operator := _PYTHON_INEQUALITY_OPERATOR.get(operator):
        can_be_null = False
        if (null_value := falsy_value(self)) is not None:
            value = value or null_value
            can_be_null = (
                null_value < value if operator == '<' else
                null_value > value if operator == '>' else
                null_value <= value if operator == '<=' else
                null_value >= value)

        def check_inequality(record):
            record_value = getter(record)
            try:
                if record_value is False or record_value is None:
                    return can_be_null
                return python_operator(record_value, value)
            except (ValueError, TypeError):
                # Tipos que no se comparan: la fila no entra, no revienta.
                return False

        return check_inequality

    raise NotImplementedError(f'Operador simple inválido {operator!r}')


def _like_regex_parts(value, exact):
    """El patrón SQL ``LIKE`` a expresión regular, trozo a trozo.

    ≙ el ``build_like_regex`` anidado de la fuente
    (``odoo19c: odoo/orm/fields.py:1428-1445``). Se saca a función de módulo
    porque aquí ``filter_function`` no es un método de clase propia y anidarla
    la reconstruiría en cada llamada.

    ``%`` es ``.*``, ``_`` es un carácter, y ``\\`` escapa al siguiente — las
    tres reglas del ``LIKE`` de SQL.
    """
    yield '^' if exact else '.*'
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            yield re.escape(char)
        elif char == '\\':
            escaped = True
        elif char == '%':
            yield '.*'
        elif char == '_':
            yield '.'
        else:
            yield re.escape(char)
    if exact:
        yield '$'


models.Field.expression_getter = _expression_getter
models.Field.filter_function = _filter_function


# --- El atributo ``copy`` — quién viaja en un duplicado ----------------------
#
# ≙ ``copy: bool = True`` (``odoo19c: odoo/orm/fields.py:281``), con su
# docstring verbatim: *"whether the field is copied over by BaseModel.copy()"*.
# Es el discriminador que ``copy_data`` consulta campo a campo (``:5438``), así
# que sin él el duplicado no puede decidir nada y lo copia todo.
#
# Va aquí y no en cada envoltorio de ``orm/fields_*`` por la misma razón que
# ``to_sql`` y ``expression_getter``: un ``Field`` es una pieza interna del ORM
# que nadie hereda, y los envoltorios son **veinte**. Ponerlo en la clase lo da
# a los veinte de una vez, con la ortografía de la fuente.

#: El default de la fuente: un campo se copia salvo que diga lo contrario.
models.Field.copy = True

_DJANGO_FIELD_INIT = models.Field.__init__

#: Los parámetros que el ``__init__`` de Django declara. Lo que llegue fuera de
#: este conjunto es vocabulario de la fuente —o un parámetro desconocido— y no
#: se le pasa: sería un ``TypeError``. Se deriva de la firma en vez de
#: enumerarse porque la lista cambia entre versiones de Django y una copia
#: sería la segunda fuente de verdad que ``calibration-verified-numbers.md``
#: prohíbe.
_DJANGO_FIELD_KWARGS = frozenset(
    inspect.signature(_DJANGO_FIELD_INIT).parameters) - {'self'}

#: Los mismos parámetros **en orden**, para nombrar lo que llegó por posición.
#:
#: Los veinticinco son ``POSITIONAL_OR_KEYWORD`` (medido sobre la firma), así
#: que ``Char('Etiqueta')`` y ``Char(verbose_name='Etiqueta')`` son la misma
#: declaración escrita de dos maneras. La fuente no tiene el problema —su
#: ``__init__`` recibe ``string`` y el resto por palabra (``odoo19c:
#: odoo/orm/fields.py:314-317``)—; aquí, sin este mapa, ``_args__`` guardaba
#: sólo la mitad por palabra y la fusión reconstruía un campo sin su etiqueta.
_DJANGO_FIELD_POSITIONAL = tuple(
    name for name in inspect.signature(_DJANGO_FIELD_INIT).parameters
    if name != 'self')


def _field_init_with_copy(self, *args, **kwargs):
    """Anota lo que el autor declaró — ≙ ``self._args__`` de la fuente.

    ``odoo19c: odoo/orm/fields.py:414`` lee ``self._args__`` para distinguir
    *"lo declaró el autor"* de *"es el defecto de la clase"*: sin esa
    distinción, :func:`_field_get_attrs` no puede rellenar **sólo** lo no
    declarado y pisaría al autor. Allá el diccionario lo guarda el propio
    ``__init__``; aquí lo guarda este envoltorio, que es el único ``__init__``
    por el que pasan los veinte tipos.

    Los parámetros que Django no conoce se retiran antes de delegar. ``copy``
    es uno de ellos y tiene además su atributo propio, porque el duplicado lo
    consulta campo a campo (``copy_data``, ``:5438``) sin pasar por el setup.

    **Lo posicional se nombra antes de anotarse.** ``_args__`` es lo que la
    fusión de :func:`_field_get_attrs` lee para reconstruir el campo; una
    etiqueta que llegó como primer posicional y no se nombró se pierde en esa
    reconstrucción sin que nada lo delate.
    """
    declared = dict(zip(_DJANGO_FIELD_POSITIONAL, args))
    declared.update(kwargs)
    for key in tuple(kwargs):
        if key not in _DJANGO_FIELD_KWARGS:
            del kwargs[key]
    _DJANGO_FIELD_INIT(self, *args, **kwargs)
    self._args__ = declared
    self.copy = declared.get('copy', True)


models.Field.__init__ = _field_init_with_copy

_DJANGO_FIELD_DECONSTRUCT = models.Field.deconstruct


def _field_deconstruct_without_copy(self):
    """``copy`` NO viaja a la migración, y es deliberado.

    El estado de la migración describe la **columna**; ``copy`` describe la
    conducta del duplicado. Emitirlo cambiaría el estado de todos los campos
    del árbol y ``makemigrations --check`` dejaría de estar limpio, sin que
    ninguna columna hubiera cambiado. Mismo criterio que ``Html.deconstruct``,
    que devuelve la ruta de ``TextField`` para no mover las migraciones ya
    generadas.
    """
    name, path, args, kwargs = _DJANGO_FIELD_DECONSTRUCT(self)
    kwargs.pop('copy', None)
    return name, path, args, kwargs


models.Field.deconstruct = _field_deconstruct_without_copy

_DJANGO_FIELD_CLONE = models.Field.clone


def _field_clone_with_args(self):
    """El duplicado conserva lo que el autor declaró.

    ``Field.clone`` de Django reconstruye el campo desde ``deconstruct()``
    (``django/db/models/fields/__init__.py``), y ``deconstruct`` sólo emite lo
    que **Django** conoce: el vocabulario de la fuente —``compute``,
    ``inverse``, ``related``, ``store``— no viaja. Medido sobre un
    ``CharField('Label', max_length=9, compute='_c')``: ``_args__`` pasa de
    ``['compute', 'max_length']`` a ``['max_length', 'verbose_name']``.

    Importa porque ``clone`` **no es un rodeo**: es la vía por la que un campo
    declarado en una base abstracta de Django llega a cada modelo concreto
    (``ModelBase.__new__`` → ``parent._meta.fields`` → ``field.clone()``). Sin
    esta línea, una base abstracta que declarara ``compute=`` lo perdía en
    silencio en todos sus descendientes: el campo quedaba con columna y sin
    cómputo, que es exactamente la clase de fallo mudo que
    ``metrica-decide-la-conclusion.md`` describe.

    La fuente no tiene contraparte porque no tiene el problema: allá la
    herencia **fusiona** ``_args__`` por la MRO (``:395-411``) en vez de
    duplicar el objeto.
    """
    copy = _DJANGO_FIELD_CLONE(self)
    copy._args__ = dict(self._args__ or {})
    return copy


models.Field.clone = _field_clone_with_args


#
# El bloque de setup del campo — ≙ ``__set_name__`` / ``_get_attrs`` /
# ``_setup_attrs__`` (``odoo19c: odoo/orm/fields.py:382-500``)
#
# **El enganche NO es ``__set_name__``, y es un hecho del stack.**
# ``ModelBase.__new__`` separa en ``contributable_attrs`` todo objeto que
# declare ``contribute_to_class`` y pasa **sólo** ``new_attrs`` a ``super_new``
# (``django/db/models/base.py:116-122``): el campo nunca entra al espacio de
# nombres que ``type.__new__`` recibe, así que Python jamás ejecuta el
# protocolo ``__set_name__`` sobre él. Django se lo entrega después con
# ``add_to_class`` (``:212``) → ``contribute_to_class``. Medido con sonda de
# conducta: un campo con ambos métodos sólo ve el segundo. Portar el cuerpo
# bajo el nombre de la fuente sería código que nunca corre, así que va al
# enganche equivalente vivo — divergencia de mecanismo, no de contrato.
#


def _field_get_attrs(self, model_class, name):
    """Los atributos de parámetro del campo, ya normalizados.

    ≙ ``Field._get_attrs`` (``:414-486``). Recibe lo declarado en ``_args__``
    y devuelve el diccionario con lo que la fuente **deriva** de ello.

    **Los tres bloques de derivación viven aquí, que es donde la fuente los
    pone.** Estuvieron portados en
    :func:`~orm.fields_nonstored.apply_source_defaults`, que los aplica en el
    **sitio de declaración** — y ése es justo el orden invertido: allá
    ``store`` se deriva antes de que exista la cadena de la MRO, así que una
    redeclaración no puede corregirlo. La fuente deriva **después** de fusionar,
    dentro de esta misma función (``:443-465``), y por eso el porte los trae.

    Mientras las fachadas de ``fields_textual``/``fields_nonstored`` sigan
    enrutando al construir, ``apply_source_defaults`` conserva su copia: es la
    duplicación que ``TASK-API-0417`` cierra al retirar el enrutado. No se
    retira en este pase porque hoy es lo único que decide qué clase se
    construye.
    """
    attrs = {}
    modules = []
    for field in self._args__.get('_base_fields__', ()):
        if not isinstance(self, type(field)):
            # 'self' pisa a 'field' y sus tipos no son compatibles; se
            # descarta todo lo acumulado hasta aquí.
            attrs.clear()
            modules.clear()
            continue
        attrs.update(field._args__)
        if field._module:
            modules.append(field._module)
    attrs.update(self._args__)
    if self._module:
        modules.append(self._module)

    attrs['model_name'] = getattr(model_class, '_name', '')
    attrs['name'] = name
    attrs['_module'] = modules[-1] if modules else None
    attrs['_modules'] = tuple(unique(modules) if len(modules) > 1 else modules)

    if name == 'state':
        # Un campo de estado se reinicia al duplicar: el duplicado empieza de
        # cero, no en el estado del original.
        attrs['copy'] = attrs.get('copy', False)
    if attrs.get('compute'):
        # ``:443-451`` — un calculado no se almacena, se calcula elevado si
        # tiene columna, no se copia (salvo que tenga columna y sea escribible)
        # y es de sólo lectura (salvo que tenga inversa).
        attrs['store'] = store = attrs.get('store', False)
        attrs['compute_sudo'] = attrs.get('compute_sudo', store)
        if not (attrs['store'] and not attrs.get('readonly', True)):
            attrs['copy'] = attrs.get('copy', False)
        attrs['readonly'] = attrs.get('readonly', not attrs.get('inverse'))
    if attrs.get('related'):
        # ``:452-458`` — un related no se almacena, se calcula elevado, no se
        # copia y es de sólo lectura. Va DESPUÉS del bloque de ``compute`` y
        # lo pisa: un ``related=`` con ``compute=`` acaba con forma de related.
        attrs['store'] = store = attrs.get('store', False)
        attrs['compute_sudo'] = attrs.get('compute_sudo',
                                          attrs.get('related_sudo', True))
        attrs['copy'] = attrs.get('copy', False)
        attrs['readonly'] = attrs.get('readonly', True)
    if attrs.get('precompute'):
        # ``:459-465`` — avisa y apaga. ``precompute`` sólo tiene efecto sobre
        # un calculado (o un related, que es un calculado con otro nombre) y
        # con columna. Fuera de ahí la fuente lo dice en vez de tragárselo.
        if not attrs.get('compute') and not attrs.get('related'):
            warnings.warn(
                f"precompute attribute doesn't make any sense on non computed "
                f"field {self}", stacklevel=1)
            attrs['precompute'] = False
        elif not attrs.get('store'):
            warnings.warn(
                f"precompute attribute has no impact on non stored field "
                f"{self}", stacklevel=1)
            attrs['precompute'] = False
        elif self.many_to_many:
            # El tercer caso es NUESTRO, y es de stack. Un muchos-a-muchos no
            # se puede adelantar al ``INSERT``: su valor no vive en una columna
            # de la fila sino en una tabla intermedia que necesita el ``pk``
            # para tener a quién apuntar. La fuente no lo tiene porque su ORM
            # asigna el id antes de ejecutar la cola de recálculo, y por eso
            # declara ``tag_ids`` con ``precompute=True``
            # (``odoo19c: account_account.py:107``).
            warnings.warn(
                f"precompute attribute has no impact on a many2many field: "
                f"its join table needs the pk of a row that does not exist "
                f"yet {self}", stacklevel=1)
            attrs['precompute'] = False
    if (attrs.get('readonly') and attrs.get('store')
            and 'editable' not in attrs):
        # ``editable=False`` es la forma NATIVA de Django de decir «esto no lo
        # escribe el cliente», y es la que DRF ya consume: ``get_field_kwargs``
        # (``rest_framework/utils/field_mapping.py:124-128``) hace
        # ``if ... or not model_field.editable: kwargs['read_only'] = True`` y
        # retorna. El contrato del endpoint sale del riel del anfitrión, sin
        # override en ningún serializer — el stack lo trae hecho.
        #
        # Aplica al calculado **y al related**, que es lo que la fuente declara
        # para los dos (``:451`` y ``:458``, ambos ``readonly``). La guarda de
        # ``store`` es lo que la hace correcta: sin columna no hay contrato de
        # escritura que proteger, y con ella el campo ya está publicado.
        #
        # **Vivía en ``apply_source_defaults``**, que la aplicaba como kwarg del
        # constructor. Aquí es un atributo derivado como los demás, y por eso
        # llega igual a un campo que declaró ``store``/``readonly`` sin pasar
        # por una fachada.
        attrs['editable'] = False
    if attrs.get('company_dependent',
                 getattr(self, 'company_dependent', False)):
        # El respaldo sobre la instancia es la divergencia de mecanismo: allá
        # ``company_dependent`` es un parámetro y viaja en ``_args__``; aquí es
        # una **clase** (:class:`~orm.fields_company_dependent.CompanyDependent`)
        # cuyo despachador consume la palabra antes de llegar a este
        # ``__init__``. La derivación tiene que dispararse por la naturaleza
        # real del campo, no por cómo se escribió; lo declarado —``copy``,
        # ``index``, ``prefetch``— sigue saliendo de ``_args__`` y sigue
        # ganando.
        #
        # El valor vive en un mapa por empresa, así que no viaja en la copia,
        # se busca por el índice parcial que ``registry.check_indexes()`` crea
        # para ``btree_not_null``, se prelee en su propio grupo, y depende de
        # la empresa activa.
        #
        # Los tres avisos de la fuente (``:467-472``) NO se portan como aviso:
        # aquí son **errores** en el constructor de
        # :class:`~orm.fields_company_dependent.CompanyDependent` —``required``
        # y ``translate`` levantan ``ValueError``, y el tipo base se valida
        # contra ``COMPANY_DEPENDENT_FIELDS``—. Un error en el sitio de
        # declaración cubre lo que el aviso cubría, y antes.
        attrs['copy'] = attrs.get('copy', False)
        attrs['index'] = attrs.get('index', 'btree_not_null')
        attrs['prefetch'] = attrs.get('prefetch', 'company_dependent')
        attrs['_depends_context'] = ('company',)
    if 'depends' in attrs:
        attrs['_depends'] = tuple(attrs.pop('depends'))
    if 'depends_context' in attrs:
        attrs['_depends_context'] = tuple(attrs.pop('depends_context'))

    if 'group_operator' in attrs:
        warnings.warn(
            "Since Odoo 18, 'group_operator' is deprecated, use 'aggregator' "
            "instead", DeprecationWarning, stacklevel=2)
        attrs['aggregator'] = attrs.pop('group_operator')

    return attrs


def _field_setup_attrs(self, model_class, name):
    """Escribe en el campo lo que :func:`_field_get_attrs` derivó.

    ≙ ``Field._setup_attrs__`` (``:491-500``). ``_extra_keys__`` censa los
    parámetros que la clase no conoce: la fuente los admite sin error —un campo
    suyo no tiene juego fijo de parámetros— y los deja greppeables en vez de
    silenciarlos.
    """
    attrs = self._get_attrs(model_class, name)

    extra_keys = tuple(key for key in attrs if not hasattr(self, key))
    if extra_keys:
        attrs['_extra_keys__'] = extra_keys

    self.__dict__.update(attrs)


models.Field._get_attrs = _field_get_attrs
models.Field._setup_attrs__ = _field_setup_attrs

_DJANGO_FIELD_CONTRIBUTE = models.Field.contribute_to_class
_DJANGO_SET_ATTRIBUTES_FROM_NAME = models.Field.set_attributes_from_name


def _field_set_attributes_from_name(self, name):
    """Un campo sin ``store`` no tiene columna, y por tanto no es concreto.

    ≙ la consecuencia de ``store`` en la fuente: allá un campo con
    ``store=False`` no declara ``column_type``, así que el motor no le crea
    columna ni lo pide en un ``SELECT`` (``odoo19c: odoo/orm/fields.py:455``).
    Aquí el equivalente son las dos banderas que este método deja puestas.

    **El sitio del parche es éste y no ``get_attname_column``**, y no es
    indiferente: ``ForeignKey`` sobrescribe ``get_attname_column`` y
    **ninguna** de las dos relacionales sobrescribe este método (medido sobre
    ``vars(models.ForeignKey)`` y ``vars(models.OneToOneField)``). Parchear el
    otro dejaría fuera justo a la familia que más barato es equivocarse.

    Django ya deriva ``concrete`` de la columna —``self.concrete = self.column
    is not None``—, así que basta con anular la columna; las dos líneas se
    escriben juntas porque el orden del método original no garantiza que la
    derivación quede después.
    """
    _DJANGO_SET_ATTRIBUTES_FROM_NAME(self, name)
    if self.store is False:
        self.column = None
        self.concrete = False


models.Field.set_attributes_from_name = _field_set_attributes_from_name


#: Marca de «esta instancia se está construyendo».
#:
#: **Construir un registro NO es asignarle sus campos.** En la fuente un
#: recordset se construye con ``browse``, que no toca ``Field.__set__``: el
#: valor de la base entra por la CACHÉ, en la rama de lectura. Aquí quien
#: construye es ``Model.__init__`` de Django, que asigna **cada campo concreto
#: por posición** —``cls(*values)`` en ``Model.from_db``—, así que con el
#: descriptor puesto una simple lectura de la base entraba por ``__set__`` y se
#: comportaba como una escritura de negocio.
#:
#: Medido, y el efecto no era cosmético: ``_recompute_field`` materializa sus
#: filas con ``model.objects.filter(pk__in=...)``; cada instancia así creada
#: escribía sus campos calculados, ``Field.write`` llamaba a
#: ``remove_to_compute`` y **borraba la marca de recálculo pendiente** justo
#: antes de que ``recompute`` la leyera. El resultado era un ``recompute`` con
#: ``pendientes=OrderedSet([])`` que no computaba nada y un volcado que escribía
#: el valor viejo en la columna — 3 casos de ``tests/unit/orm/``.
#:
#: El envoltorio marca la instancia mientras ``__init__`` corre; ``__set__`` lo
#: consulta y en ese tramo escribe **sólo** el almacén, que es exactamente lo
#: que Django hacía antes del descriptor y lo que la fuente hace al construir.
_DJANGO_MODEL_INIT = models.Model.__init__


def _model_init_marking_the_load(self, *args, **kwargs):
    """Envuelve ``Model.__init__`` para marcar el tramo de construcción."""
    object.__setattr__(self, '_orm_building', True)
    try:
        _DJANGO_MODEL_INIT(self, *args, **kwargs)
    finally:
        object.__setattr__(self, '_orm_building', False)


models.Model.__init__ = _model_init_marking_the_load


class FieldDescriptor(DeferredAttribute):
    """El cuerpo de ``Field.__get__`` y ``Field.__set__``, en el enganche vivo.

    ≙ ``Field.__get__`` (``odoo19c: odoo/orm/fields.py:1642-1804``) y
    ``Field.__set__`` (``:1807-1841``).

    **El descriptor NO es el campo, y por eso el cuerpo no cuelga de
    ``models.Field``.** La fuente hace del propio ``Field`` su descriptor: el
    objeto que vive en el atributo de clase *es* el campo. Django coloca ahí un
    objeto distinto, que el campo instala por ``descriptor_class``
    (= ``DeferredAttribute``). Medido sobre ``res.partner``: ``name`` y
    ``active`` llevan un ``DeferredAttribute``, ``barcode`` un
    ``_CompanyDependentAttribute`` y ``parent_id`` un
    ``ForeignKeyDeferredAttribute``. Colgar ``__get__`` de ``models.Field``
    sería código muerto — nadie lo consultaría —, igual que lo era
    ``__set_name__`` antes de portarse a ``contribute_to_class``
    (:ref:`h-api-1067`). El cuerpo se porta al descriptor; el sitio cambia, el
    comportamiento no.

    **Se instala sobre TODO campo, y por eso aquí no hay ``__set__``.** La
    fuente consulta ``env.cache`` para todo campo (``:1667``); un puerto que
    instale el descriptor sólo sobre el calculado tiene dos cachés y un lector
    que consulta la que no es. ``DeferredAttribute`` no declara ``__set__``: es
    un descriptor de NO datos, así que ``instance.__dict__`` gana y este
    ``__get__`` sólo se consulta cuando el valor falta — que es exactamente
    cuando el recordset, cuyo ``__dict__`` está vacío, necesita la caché del
    ORM. Medido sobre 300 000 lecturas: el de NO datos cuesta **1.00×** lo que
    el atributo llano, porque en el camino caliente no se le consulta. La
    escritura, que sí cuesta **3.24×**, vive en :class:`ComputedFieldDescriptor`.

    Precedente propio del árbol: ``_CompanyDependentAttribute``
    (``orm/fields_company_dependent.py:167``) ya porta comportamiento de campo a
    un descriptor, y se instala por campo en ``contribute_to_class``.
    """

    def __get__(self, instance, cls=None):
        """≙ ``Field.__get__`` (``:1642``) — el valor del campo sobre la fila."""
        if instance is None:
            # ``:1644-1645`` — acceso por la clase: devuelve el descriptor.
            return self

        # El primer consumidor tras ``apps.ready`` dispara la fase de setup
        # que la fuente corre desde su cargador (``ensure_field_setup``): sin
        # ella un ``related=`` sobre un campo de Django no tiene ``compute``.
        if ensure_field_setup.pending:
            ensure_field_setup()

        field = self.field
        environment = get_environment()

        # ``:1647-1651`` — el control de acceso por campo. La guarda por
        # ``hasattr`` es la que el árbol ya usa en ``models.py:1454``: el
        # contrato vive en los modelos que heredan el mixin de acceso, no en
        # ``django.db.models.Model``.
        if not environment.su and hasattr(instance, '_has_field_access'):
            if not instance._has_field_access(field, 'read'):
                instance._check_field_access(field, 'read')

        # ``:1653-1661`` — la rama de tamaño, y SÍ tiene receptor. Un recordset
        # ES una instancia del modelo de Django, y desde TASK-API-0402 toda
        # fila de :class:`~orm.models.BaseModel` lleva la terna: la instala
        # ``_from_ids`` con N ids, y ``__init__``/``from_db`` con ``(pk,)``.
        # La terna es una ranura de ``__slots__`` (``models.py:362`` de la
        # fuente), así que NO vive en ``__dict__``: un ``__dict__.get('_ids')``
        # devuelve ``None`` siempre y esta rama quedaría muerta — el control
        # que no discrimina (H-API-1106). ``None`` sólo lo da una fila de
        # ``django.db.models.Model`` fuera de ``BaseModel``, que es una fila y
        # sobre la que la rama no aplica.
        own_ids = getattr(instance, '_ids', None)
        if own_ids is not None and len(own_ids) != 1:
            if own_ids:
                # ``:1656-1658`` — que ``ensure_one`` levante la excepción.
                instance.ensure_one()
                raise AssertionError('unreachable')
            # ``:1659-1661`` — recordset vacío: el valor nulo del campo.
            return field.convert_to_record(
                field.convert_to_cache(False, instance, validate=False),
                instance)

        if field.compute and getattr(field, 'store', False):
            # ``:1664-1666`` — procesa los cómputos pendientes.
            field.recompute(instance)

        record_id = instance.pk
        field_cache = field._get_cache(environment)
        try:
            # ``:1668-1673`` — acierto de caché.
            return field.convert_to_record(field_cache[record_id], instance)
        except KeyError:
            # silent OK because el fallo de cache NO es un error: es la
            # bifurcacion del cuerpo. La fuente lo escribe igual
            # (``try: value = field_cache[record.id] / except KeyError: pass``,
            # ``:1668-1691``) porque ``KeyError`` es como el cache dice "no lo
            # tengo", y las ramas de abajo son exactamente su respuesta.
            pass

        # **Aquí hay DOS cachés, no una — y la segunda es el ``__dict__``.**
        # La fuente tiene una sola (``env.cache``) y su acierto es la rama de
        # arriba. En este stack, Django mantiene además el almacén de la
        # instancia, y ES el analogo de esa misma rama: es donde
        # ``Model.__init__`` deja la fila leida, donde ``save()`` lee la
        # columna y donde el metodo de computo asigna (:ref:`h-api-1067`).
        # Consultar solo la caché del ORM deja fuera al almacén, y entonces
        # una fila recien construida —sin ``pk``, con su valor ya puesto— cae
        # en la rama de computo. Medido: ``pre_save`` disparaba
        # ``_compute_amounts`` sobre una ``SaleOrder`` sin ``pk`` y su
        # ``order_line`` reventaba con *'SaleOrder' instance needs to have a
        # primary key* — 443 casos de la suite.
        #
        # El recalculo pendiente ya se proceso arriba (``field.recompute``),
        # asi que un valor en el almacén es un valor vigente, no uno viejo.
        if field.attname in instance.__dict__:
            # **El valor del almacén se devuelve TAL CUAL.** La rama de arriba
            # aplica ``convert_to_record`` porque lo que guarda ``env.cache``
            # está en forma de caché; el almacén de Django guarda la forma de
            # registro —es lo que ``Model.__init__`` puso y lo que ``pre_save``
            # espera leer—, así que pasarlo por ``convert_to_cache`` y volver
            # NO es la identidad. Medido: un ``DateField`` salía de ese viaje
            # como algo que ``parse_date`` rechazaba con *fromisoformat:
            # argument must be str* — 443 casos de la suite.
            value = instance.__dict__[field.attname]
            if record_id:
                # Sembrar la caché del ORM sólo con ``pk``: es su clave. Una
                # fila en vuelo dentro de ``_do_insert`` no la tiene todavía.
                field._update_cache(
                    instance,
                    field.convert_to_cache(value, instance, validate=False))
            # **Se traduce, igual que la rama de arriba.** Las dos ramas
            # son el mismo acierto de caché de la fuente —una sola en su
            # cuerpo— y por tanto tienen que responder lo mismo:
            # ``convert_to_record`` (``odoo19c: odoo/orm/fields.py:1053``,
            # ``return False if value is None else value``) lleva el ``None``
            # al vocabulario de la fuente para «sin valor», que es ``False``.
            # Sin esto el MISMO campo de la MISMA fila respondía ``False`` o
            # ``None`` según cuál de los dos planos contestara.
            #
            # La vuelta la cierra ``convert_to_column`` en el camino de la
            # columna (ver :func:`_field_get_prep_value`): sin ella ese
            # ``False`` viajaba al ``parse_date`` de Django y lo rechazaba.
            return field.convert_to_record(value, instance)

        # ``:1694-1804`` — las ramas de fallo de caché.
        if getattr(field, 'store', False) and record_id:
            # ``:1697-1713`` — fila real y persistida: se lee de la base. Quien
            # lo hace es el ``DeferredAttribute`` de Django, que devuelve
            # ``instance.__dict__[attname]`` si la fila se cargó, y si no emite
            # el ``refresh_from_db`` de la columna. Es el equivalente medido de
            # ``_fetch_field``, que este árbol no declara.
            #
            # **Divergencia de mecanismo declarada:** la fuente prelecta la
            # ventana de ``_to_prefetch`` en una consulta; aquí la unidad es la
            # fila, así que la ventana no ahorraría ninguna. Es la misma
            # divergencia 1 de :func:`recompute`, con el mismo sucesor: **#306**.
            value = super().__get__(instance, cls)
            field._update_cache(
                instance, field.convert_to_cache(value, instance, validate=False))

        elif getattr(field, 'store', False) and getattr(instance, '_origin', None) \
                and not (field.compute and getattr(field, 'readonly', False)):
            # ``:1716-1734`` — fila nueva con origen: el valor se toma de la
            # fila guardada que la origina.
            origin = instance._origin
            value = field.convert_to_cache(
                getattr(origin, field.name), instance, validate=False)
            field._update_cache(instance, value)

        elif field.compute:
            # ``:1736-1763`` — sin columna, o fila nueva sin origen: se computa.
            if environment.is_protected(field, record_id):
                field._update_cache(
                    instance,
                    field.convert_to_cache(False, instance, validate=False))
            else:
                field.compute_value(instance)
                if record_id in tuple(field._cache_missing_ids(instance)):
                    if field.attname in instance.__dict__:
                        # **El cómputo SÍ asignó — al almacén, no a la caché
                        # del ORM.** ``__set__`` escribe siempre
                        # ``instance.__dict__[attname]`` y sólo siembra
                        # ``env.cache`` con ``pk``; sobre una fila nueva la
                        # clave es ``None`` y la caché nunca la recibe, así
                        # que ``_cache_missing_ids`` la sigue reportando
                        # ausente. Es el mismo acierto que la rama del
                        # almacén de arriba, y responde igual: la forma de
                        # registro, traducida. Medido en la sonda E del
                        # workbench ``fachadas-construyen-una-vez``: la
                        # primera lectura levantaba *Compute method failed to
                        # assign* con el valor ya en ``after_dict``; la
                        # segunda lo devolvía por el almacén.
                        return field.convert_to_record(
                            instance.__dict__[field.attname], instance)
                    if getattr(field, 'readonly', False) and not field.store:
                        raise ValueError(
                            f'Compute method failed to assign '
                            f'{instance}.{field.name}')
                    # ``:1753-1757`` — el cómputo no asignó: valor nulo.
                    field._update_cache(
                        instance,
                        field.convert_to_cache(False, instance, validate=False))

        # ``:1765-1783`` — la rama del ``many2one`` delegado sobre fila nueva NO
        # tiene receptor aquí: el descriptor no se instala sobre una FK, que
        # conserva el ``ForeignKeyDeferredAttribute`` de Django con su propio
        # camino de escritura (ver :func:`_field_contribute_to_class`).

        else:
            # ``:1786-1801`` — ni almacenado ni calculado: el valor por omisión.
            field._update_cache(
                instance, field.convert_to_cache(False, instance, validate=False))
            defaults = instance.default_get([field.name])
            if field.name in defaults:
                field._update_cache(
                    instance,
                    field.convert_to_cache(defaults[field.name], instance))

        # La caché pudo invalidarse entera dentro del cómputo (``:1759-1761``),
        # así que se vuelve a pedir en vez de reusar la referencia de arriba.
        field_cache = field._get_cache(environment)
        return field.convert_to_record(field_cache[record_id], instance)


class ComputedFieldDescriptor(FieldDescriptor):
    """El mismo ``__get__``, más ``__set__`` — ≙ ``Field.__set__`` (``:1807``).

    **Por qué la escritura vive en una subclase y no en la base.**
    ``DeferredAttribute`` no declara ``__set__``: es un descriptor de NO datos,
    así que ``instance.__dict__`` gana y su ``__get__`` sólo se consulta cuando
    el valor falta. Declarar ``__set__`` lo convierte en descriptor de datos, y
    entonces **toda** lectura de **todo** campo pasa por Python. Medido sobre
    300 000 lecturas con un cuerpo vacío
    (``scripts/workbench/two-caches-descriptor-20260911T053450/outputs/``
    ``descriptor_cost.txt``): el descriptor de NO datos cuesta **1.00×** lo que
    el atributo llano —22.8 ns contra 22.8 ns, porque nunca se le consulta— y
    el de datos **3.24×** (73.9 ns). El coste no lo trae el descriptor: lo trae
    ``__set__``.

    Por eso el reparto es por **capacidad**, no por comodidad: la lectura la
    necesitan todos los campos —es donde vive la caché del ORM— y la escritura
    en tres cubos sólo tiene receptor donde el campo declara ``compute``. Ahí el
    3.24× es despreciable frente a la llamada al método de cómputo.
    """

    def _mark_pending_inverse(self, instance):
        """Anota que este campo quedó escrito y su inverso no se ha despachado.

        **Es la segunda mitad de la divergencia que el docstring de**
        :meth:`__set__` **ya declara**, no una razón nueva. La fuente manda la
        fila persistida a ``records.write({name: value})`` (``:1841``), y su
        ``write`` despacha el inverso al final del mismo cuerpo —
        ``fields[0].determine_inverse(real_recs)``
        (``odoo19c: odoo/orm/models.py:4493``)—. Aquí la asignación **no**
        entra en ``write`` —emitiría un UPDATE donde la de Django no emite
        ninguno—, así que el despacho se queda sin sitio: se anota al asignar
        y lo recoge :meth:`~orm.models.RecordLoaderMixin.save`, que es el
        momento en que la fila llega a la base.

        No se anota en los otros dos cubos, y el motivo lo da la fuente:
        ``is_protected`` es *"records being computed: no business logic, no
        recomputation"* (``:1822``) y ``_orm_building`` es la carga de caché.
        Un inverso ES lógica de negocio.
        """
        field = self.field
        if not getattr(field, 'inverse', None):
            return
        instance.__dict__.setdefault(PENDING_INVERSE_FIELDS, set()).add(
            field.name)

    def __set__(self, instance, value):
        """≙ ``Field.__set__`` (``:1807-1841``) — el reparto en tres cubos.

        **Divergencia de mecanismo declarada, y es la del cubo real.** La fuente
        manda la fila persistida a ``records.write({name: value})``, que en este
        árbol es ``BaseModel.write`` (``orm/models.py:2057``) — y ése llama a
        ``self.save(update_fields=…)``, o sea emite SQL. Portarlo literal haría
        que ``partner.campo = x`` lanzara un UPDATE, cuando la asignación de
        Django emite **cero** consultas (medido en
        ``test_a_real_record_does_not_emit_sql_on_assignment``). Se porta lo que
        ``Field.write`` hace —descartar el recálculo pendiente, filtrar la fila
        cuyo valor ya coincide, marcar la caché sucia— más ``modified()``, que
        es la mitad de disparo; el volcado sigue siendo ``save()``.
        """
        field = self.field
        # El atributo de instancia se escribe SIEMPRE: es de donde ``save()``
        # de Django lee la columna, y de donde la lee ``_cache_computed_values``
        # tras el cómputo.
        instance.__dict__[field.attname] = value

        if instance.__dict__.get('_orm_building'):
            # **Construir NO es asignar, y esto lo decide la fuente.**
            #
            # Su camino de lectura es ``BaseModel._fetch_query``
            # (``odoo19c: odoo/orm/models.py:3879-3933``), que **no pasa por
            # ``Field.__set__``**: lee las columnas y puebla la caché con
            # ``field._insert_cache(fetched, values)``. El comentario de la
            # fuente dice por qué es ``insert`` y no ``update``: *"If we assume
            # that the value of a pending update is in cache, we can avoid
            # flushing pending updates if the fetched values do not overwrite
            # values in cache"* — *"store values in cache, but without
            # overwriting"*.
            #
            # Aquí el ``_fetch_query`` es el cargador de Django: ``from_db``
            # construye con ``cls(*values)`` y ``Model.__init__`` asigna cada
            # campo concreto por posición. Ése es el enganche equivalente, así
            # que este tramo hace lo mismo que la fuente y nada más: poblar sin
            # pisar. Sin ``remove_to_compute``, sin marca de sucio y sin
            # ``modified()`` — son la lógica de negocio de una escritura, y
            # cancelaban el recálculo pendiente de la fila recién cargada.
            #
            # El ``setdefault`` de ``_insert_cache`` subsume la guarda del
            # valor sucio: una escritura pendiente ES lo que la fuente se niega
            # a sobreescribir, con esas palabras.
            if instance.pk:
                field._insert_cache(
                    instance,
                    [field.convert_to_cache(value, instance, validate=False)])
            if not getattr(field, 'concrete', True):
                # **Un campo SIN COLUMNA no puede venir de la fila.** El
                # cargador de Django puebla por ``opts.concrete_fields``, así
                # que un campo sin columna sólo llega hasta aquí por el bucle
                # de sobrantes de ``Model.__init__`` — es decir, porque quien
                # construyó lo pasó como argumento. Ése es exactamente el
                # ``vals`` del que la fuente saca sus ``determine_inverses`` en
                # ``create`` (``odoo19c: odoo/orm/models.py:4682``), y por eso
                # la marca sí corresponde: el tramo sigue sin ser una
                # escritura —ni ``modified()``, ni marca de sucio— pero el
                # inverso que ``create`` despacha (``:4717-4733``) necesita
                # saber qué campos trajo el llamador.
                self._mark_pending_inverse(instance)
            return

        environment = get_environment()
        record_id = instance.pk

        if environment.is_protected(field, record_id):
            # ``:1819-1822`` — fila en cómputo: sin lógica de negocio y sin
            # recálculo. Sin este cubo, escribir el resultado de un cómputo
            # dispararía el recálculo del propio campo: recursión infinita.
            field.write(instance, value)
            return

        if not record_id:
            # ``:1824-1836`` — fila nueva: sin lógica de negocio, pero con
            # protección y con aviso de modificación.
            # ``.get(self) or [self]`` de la fuente. El agrupador de este
            # árbol NO expone ``.get`` a propósito —un campo sin ``compute``
            # ahí es un error de programación, no un caso (``registry.py:979``)
            # — así que la consulta va por ``in`` + ``[]``, que es la misma
            # semántica sin esconder el error.
            protected = (registry_field_computed[field]
                         if field in registry_field_computed else [field])
            with environment.protecting(protected, instance):
                if getattr(field, 'relational', False):
                    instance.modified([field.name], before=True)
                field.write(instance, value)
                instance.modified([field.name])

            if getattr(field, 'inherited', False):
                # ``:1833-1836`` — el campo delegado también se asigna sobre el
                # padre cuando el padre es nuevo.
                parent = getattr(instance, field.related.split('.')[0], None)
                if parent is not None and not parent.pk:
                    setattr(parent, field.name, value)
            self._mark_pending_inverse(instance)
            return

        # ``:1838-1841`` — fila real. Ver la divergencia del docstring.
        field.write(instance, field.convert_to_write(value, instance))
        instance.modified([field.name])
        self._mark_pending_inverse(instance)


def _collect_field_definitions(field, cls, name):
    """Las definiciones de ``name`` a lo largo de la MRO, de la base al hijo.

    ≙ ``_init_model_class_fields`` (``odoo19c: odoo/orm/model_classes.py:
    366-374``), que recoge ``cls._field_definitions`` recorriendo
    ``reversed(model_cls._model_classes__)`` y acumula en ``definitions[name]``
    una lista por nombre. Allá el recorrido lo hace el cargador del registro;
    aquí lo hace este enganche, que es el único momento en que existen a la vez
    la clase completa y el campo que se está montando.

    **Qué se salta, y por qué son dos razones distintas:**

    - una base que **es** modelo de Django: su campo ya pasó por
      ``contribute_to_class`` y vive en ``_meta``, no en ``vars(base)`` —lo que
      queda ahí es un ``DeferredAttribute``—, y Django además **prohíbe**
      redeclararlo en la subclase (``FieldError: Local field 'x' … clashes``).
      El recorrido no puede verlo y no hay nada que fusionar;
    - el propio ``field``: ``ModelBase.__new__`` lo separó de ``new_attrs``
      antes de crear la clase, así que no está en ``vars(cls)``; la guarda es
      contra el caso en que sí lo esté.

    Medido en consecuencia: hoy la rama de fusión es **inalcanzable** —cero
    bases llanas del árbol declaran un ``models.Field``—. Se vuelve alcanzable
    exactamente cuando ``TASK-API-0418`` retire :class:`NonStored`, que es una
    clase suelta y por eso hoy no cuenta como definición de campo.
    """
    if '_base_fields__' in (field._args__ or {}):
        # Ya es el campo fusionado: volver a recoger daría una cadena de
        # cadenas. ≙ la rama ``_direct`` de la fuente, que no reentra.
        return (field,)
    chain = []
    for base in reversed(cls.__mro__):
        if issubclass(base, models.Model):
            continue
        declared = vars(base).get(name)
        if isinstance(declared, models.Field) and declared is not field:
            chain.append(declared)
    chain.append(field)
    return tuple(chain)


def _merge_field_definitions(chain):
    """Un campo nuevo con la unión de lo declarado — ≙ ``:378-381``.

    La fuente construye ``Field(_base_fields__=tuple(fields_))`` con la clase
    del **último** eslabón y deja que ``_get_attrs`` fusione los ``_args__`` al
    montar. La clase la fija el último y no el ``store``: la fuente no enruta
    por almacenamiento en ningún punto del flujo (``api@0734b906``).

    **La divergencia es que aquí la unión viaja también en el ``__init__``.**
    Allá basta con ``_base_fields__`` porque el constructor de un campo son
    tres líneas y no deriva nada. Aquí ``CharField.__init__`` materializa
    ``MaxLengthValidator`` sobre la ``cached_property`` ``validators``, así que
    un campo construido vacío y rellenado con ``__dict__.update`` queda con
    ``max_length=9`` y ``validators=[]`` — medido, y por eso el porte pasa los
    parámetros de Django por donde Django los espera.

    Lo que el envoltorio de ``__init__`` no conozca lo retira antes de delegar,
    de modo que el vocabulario de la fuente llega a ``_args__`` sin llegar a
    Django.

    **Cota declarada:** la reconstrucción sale de ``_args__``, que sólo tiene lo
    que llegó a ``Field.__init__``. Una relacional pasa ``to`` y ``on_delete``
    a **su** ``__init__`` y nunca al de ``Field``, así que su reconstrucción
    falla. No se alcanza hoy —la rama entera es inalcanzable— y su desenlace es
    ``TASK-API-0419``.
    """
    merged = {}
    for declared in chain:
        merged.update(declared._args__ or {})
    merged['_base_fields__'] = chain
    return type(chain[-1])(**merged)


def _field_contribute_to_class(self, cls, name, private_only=False):
    """El cuerpo de ``__set_name__``, en el enganche que este ORM sí ejecuta.

    El orden es el de la fuente —recoger por la MRO, fusionar, derivar
    ``store``, enrutar una vez— y **no** el que este puerto tenía. La versión
    anterior llamaba a ``super()`` primero, con la razón de que
    ``set_attributes_from_name`` fija ``self.name``. La razón no se sostiene:
    :func:`_field_setup_attrs` no lee ``self.name``, ``self.model``,
    ``self.attname`` ni ``self.column`` — recibe el ``name`` por parámetro.
    Y el orden invertido **costaba** el campo: ``get_attname_column`` decide la
    columna leyendo un ``store`` que todavía era el defecto de clase, así que
    un ``compute=`` acababa con columna y pidiéndose en cada ``SELECT``.

    ``private_only`` se refuerza con el ``store`` derivado. Sin él, un campo sin
    columna sigue en ``_meta.local_fields`` y el ORM lo pide a la base:
    ``ProgrammingError``. La forma —``private_only=True`` **y** ``column=None``—
    es la que el propio stack usa en ``GenericForeignKey``, que declara las dos.
    """
    chain = _collect_field_definitions(self, cls, name)
    if len(chain) > 1:
        _merge_field_definitions(chain).contribute_to_class(
            cls, name, private_only=private_only)
        return

    #: La rama de un solo eslabón ≙ el atajo ``_direct`` de la fuente
    #: (``:375-377``), con una divergencia declarada: allá un ``related=`` no
    #: es ``_direct`` (``:404``) y baja por la rama de fusión aunque se declare
    #: una sola vez. Aquí, con un eslabón, fusionar sería construir un campo
    #: idéntico al que ya se tiene; la diferencia observable es nula porque
    #: :func:`_field_get_attrs` deriva lo mismo en los dos caminos.
    self._setup_attrs__(cls, name)
    _DJANGO_FIELD_CONTRIBUTE(
        self, cls, name, private_only=private_only or self.store is False)
    _install_field_descriptor(self, cls)
    phase = getattr(self, 'setup_nonrelated__', None)
    if phase is not None:
        #: ``setup_nonrelated`` (``odoo19c: odoo/orm/fields.py:1043``) es la
        #: FASE de la fuente: corre con la clase ya construida, que es lo que
        #: la decision de ``ondelete`` necesita y el sitio de declaracion no
        #: tiene. Lo cuelga quien lo necesita —hoy ``Many2one``— porque este
        #: modulo es la base que aquel importa, y al reves seria un ciclo.
        phase(self, cls)


def _install_field_descriptor(field, cls):
    """Cuelga el descriptor de la fuente sobre el campo, y elige cuál.

    **Todo campo lee por el descriptor; sólo el calculado escribe por él.** La
    fuente tiene UNA caché (``env.cache``) y ``Field.__get__`` la consulta
    siempre, para todo campo (``odoo19c: odoo/orm/fields.py:1667``). Instalarlo
    sólo sobre el calculado dejaba al puerto con **dos** cachés y un lector que
    consultaba la que no era: ``_insert_cache`` escribía en la del ORM y una
    lectura llana caía al ``DeferredAttribute`` de Django, que emite
    ``refresh_from_db``. Medido sobre un recordset con la caché sembrada
    (``scripts/workbench/two-caches-descriptor-20260911T053450/outputs/``
    ``id_resolution_on_recordset.txt``): ``rs.label`` iba a la base y reventaba,
    mientras ``rs.id`` —que sí tiene descriptor propio, :class:`IdFromIds`—
    respondía ``7``.

    Las dos guardas que quedan, y ninguna es de comodidad:

    1. **Quién escribe.** ``compute`` declarado → :class:`ComputedFieldDescriptor`
       (con ``__set__``, descriptor de datos); si no → :class:`FieldDescriptor`
       (sin ``__set__``, de NO datos, coste medido **1.00×**). El reparto lo
       justifica el docstring de la subclase.
    2. **El atributo de clase es un ``DeferredAttribute`` PELADO, o no hay
       ninguno.** Un ``ForeignKeyDeferredAttribute`` o un
       ``_CompanyDependentAttribute`` ya son descriptores de datos con su
       propio camino de lectura y escritura portado; sustituirlos rompería la
       relación o el eje por empresa. Por eso la condición es de tipo exacto,
       no ``isinstance``. El campo relacional sobre recordset lo cierra su
       propio sucesor, **TASK-API-0402**.

       El ``None`` es el caso del campo **sin columna**, y no es un hueco: el
       ``contribute_to_class`` de Django cuelga su descriptor sólo ``if
       self.column`` (verbatim en el paquete instalado), así que un
       ``store=False`` sale de ahí sin nada. Sin esta rama el atributo se
       resolvía por la MRO al objeto ``Field`` crudo de la base y una lectura
       nunca despachaba el cómputo — el campo respondía con el descriptor en
       vez de con su valor.
    """
    current = cls.__dict__.get(field.attname)
    # Re-invocable desde ``Field.setup``: un campo ``related=`` no tiene
    # ``compute`` en ``contribute_to_class`` —se lo cuelga ``setup_related``
    # (``:632``) en la fase de setup—, así que aquí recibía el descriptor
    # base, que NO define ``__set__``: la asignación del cómputo caía al
    # ``__dict__`` y la caché nunca se enteraba (medido en
    # ``probe_plain_row_assignment_lands_in_cache.py``: ``_model_setitem``
    # trazado, ``_field_write`` nunca). La fuente no distingue: allá el
    # descriptor es el propio ``Field`` y ``compute`` llega antes del primer
    # acceso. Aquí el equivalente es promoverlo cuando el setup lo declara.
    if type(current) is FieldDescriptor and getattr(field, 'compute', None):
        setattr(cls, field.attname, ComputedFieldDescriptor(field))
        return
    if current is not None and type(current) is not DeferredAttribute:
        return
    descriptor = (ComputedFieldDescriptor if getattr(field, 'compute', None)
                  else FieldDescriptor)
    setattr(cls, field.attname, descriptor(field))


models.Field.contribute_to_class = _field_contribute_to_class


# ---------------------------------------------------------------------------
# La compuerta relacional de ``store`` — ≙ ``if self.store:`` en
# ``odoo19c: odoo/orm/fields_relational.py:1279`` (``Many2many.setup_nonrelated``
# crea la tabla de relación SÓLO si el campo está almacenado; ``:1517`` y
# ``:1554`` la tocan al escribir sólo bajo la misma guarda). La fuente no tiene
# accessor inverso: un relacional sin ``store`` es un campo calculado que
# devuelve registros del comodelo y nada más.
#
# En Django el mismo contenido se construye con dos piezas que el stack ya
# trae —«con qué construirlo», sin dependencia de fuera—:
#
# 1. ``remote_field.related_name = '+'`` — la relación queda ``hidden``
#    (``related.py:hidden``), y ``contribute_to_related_class`` no instala
#    accessor ni nombre de consulta inversa en el comodelo.
# 2. Para ``ManyToManyField``, enrutar al ``contribute_to_class`` de
#    ``RelatedField`` (el abuelo): ``ManyToManyField.contribute_to_class``
#    crea la tabla intermedia y el ``ManyToManyDescriptor`` DESPUÉS de
#    ``super()`` (``related.py:1961-2008``), así que nuestro parche sobre
#    ``Field`` no alcanza a impedirlo — hay que decidir antes de entrar.
#
# ``store`` se deriva ANTES con ``_setup_attrs__`` (idempotente: vuelve a
# correr dentro de ``_field_contribute_to_class`` con el mismo resultado),
# porque el orden de la MRO obliga a conocerlo antes de que Django lea
# ``related_name``.
# ---------------------------------------------------------------------------
_DJANGO_RELATED_CONTRIBUTE = RelatedField.contribute_to_class
_DJANGO_M2M_CONTRIBUTE = models.ManyToManyField.contribute_to_class


def _hidden_reverse_name(cls, name):
    """El nombre oculto que el propio stack genera para un ``related_name='+'``
    de M2M (``related.py:1977-1981``): distingue dos relacionales ocultos del
    mismo modelo sin exponer ninguno."""
    return '_%s_%s_%s_+' % (cls._meta.app_label, cls.__name__.lower(), name)


def _related_contribute_to_class(self, cls, name, private_only=False, **kwargs):
    """``RelatedField.contribute_to_class`` con la compuerta de ``store``."""
    self._setup_attrs__(cls, name)
    if self.store is False and not cls._meta.abstract:
        self.remote_field.related_name = '+'
    _DJANGO_RELATED_CONTRIBUTE(
        self, cls, name, private_only=private_only, **kwargs)


def _m2m_contribute_to_class(self, cls, name, **kwargs):
    """``ManyToManyField.contribute_to_class`` con la compuerta de ``store``:
    sin ``store`` no nace la tabla de relación ni el descriptor de M2M."""
    self._setup_attrs__(cls, name)
    if self.store is False and not cls._meta.abstract:
        self.remote_field.related_name = _hidden_reverse_name(cls, name)
        _DJANGO_RELATED_CONTRIBUTE(self, cls, name, **kwargs)
        return
    _DJANGO_M2M_CONTRIBUTE(self, cls, name, **kwargs)


RelatedField.contribute_to_class = _related_contribute_to_class
models.ManyToManyField.contribute_to_class = _m2m_contribute_to_class


# === Los seis del censo de ``odoo/orm/fields.py`` (tarea #209) ==============
#
# La referencia declara **9** símbolos de nivel superior; dos ya viven aquí en
# otro archivo (``COMPANY_DEPENDENT_FIELDS`` en ``fields_company_dependent``,
# ``_logger`` en ``environments``). Los seis restantes se portan **en este
# archivo**, que es donde la fuente los declara — segunda cláusula de
# ``atributos-de-clase-de-modelo.md``.
#
# Ninguno cae en EXCLUIDO: los seis son TRAE o CONSTRUYE. El veredicto por
# símbolo, con su consumidor medido, está en
# ``docs: …/analisis-censo-orm-referencia-trae-o-construye.rst``.

#: ≙ ``T = typing.TypeVar("T")`` (``odoo19c: odoo/orm/fields.py:35``) — el
#: parámetro del genérico ``Field[T]``. TRAE: biblioteca estándar.
T = TypeVar('T')

#: ≙ ``IR_MODELS`` (``:37``) — los siete modelos del registro que un
#: ``Many2one`` NO puede proteger con ``on_delete=PROTECT``.
#:
#: Re-exportado de :data:`orm.registry.IR_MODELS`, donde vive. La fuente lo
#: declara aquí y lo consume desde ``fields_relational.py:289``; aquí esa
#: arista cerraría un 2-ciclo, porque este módulo es además la fachada que
#: re-exporta ``orm.fields_relational`` (``:92``) y la fuente no tiene esa
#: arista. Mismo traslado y misma causa que :data:`UNACCENT_ENABLED`.

#: ≙ ``PYTHON_INEQUALITY_OPERATOR`` (``:45``) — la comparación **en memoria**.
#:
#: NO es lo mismo que ``_INEQUALITY_LOOKUP``, que traduce el mismo operador al
#: nombre de lookup de Django para que la comparación la haga PostgreSQL. La
#: fuente declara los dos porque tiene los dos caminos, y aquí igual: éste lo
#: consume :func:`condition_matches_in_memory`, aquél :func:`condition_to_q`.
PYTHON_INEQUALITY_OPERATOR = {
    '<': operator_module.lt,
    '>': operator_module.gt,
    '<=': operator_module.le,
    '>=': operator_module.ge,
}

#: ≙ ``_global_seq = itertools.count()`` (``:89``) — el orden de declaración.
#:
#: DIVERGENCIA DE MECANISMO, y es que el stack ya lo TRAE: Django numera cada
#: campo al construirlo con ``models.Field.creation_counter``, con el mismo
#: propósito —ordenar los campos por el orden en que se escribieron— y ya
#: consumido por ``_meta.get_fields()``. Declarar un segundo contador daría dos
#: numeraciones para una sola pregunta. El nombre se conserva como alias para
#: que la lectura contra la fuente no exija traducir.
def global_seq():
    """El siguiente número de orden de declaración — ≙ ``next(_global_seq)``."""
    value = models.Field.creation_counter
    models.Field.creation_counter += 1
    return value


def resolve_mro(model, name, predicate):
    """Los valores sucesivamente sobreescritos de ``name`` en el MRO.

    Docstring de la fuente, verbatim: *"Return the list of successively
    overridden values of attribute ``name`` in mro order on ``model`` that
    satisfy ``predicate``. Model registry classes are ignored."*
    (``odoo19c: odoo/orm/fields.py:50-64``).

    CONSTRUYE: el ``__mro__`` de Python basta. La fuente recorre
    ``model._model_classes__`` —su lista de clases de módulo, que excluye las
    que su registro fabrica— y aquí el equivalente es el ``__mro__`` de la
    clase saltando ``object``: Django no fabrica clases intermedias, así que
    todo lo que hay en el MRO lo escribió alguien.

    Se detiene en el primer valor que **no** cumple ``predicate``, no lo salta.
    Esa diferencia es el contrato: la lista describe una cadena de
    sobreescrituras contigua, y un eslabón de otra naturaleza la corta.

    :param model: la clase (o instancia) cuyo MRO se recorre.
    :param name: el atributo a buscar en cada clase de la cadena.
    :param predicate: qué valores cuentan; el primero que falle corta.
    :returns: los valores en orden de MRO — el más derivado primero.
    """
    cls = model if isinstance(model, type) else type(model)
    result = []
    for klass in cls.__mro__:
        if klass is object:
            continue
        value = klass.__dict__.get(name, _MRO_SENTINEL)
        if value is _MRO_SENTINEL:
            continue
        if not predicate(value):
            break
        result.append(value)
    return result


#: Centinela propio de :func:`resolve_mro`: distingue *"la clase no declara el
#: atributo"* de *"lo declara con valor ``None``"*. La fuente usa su ``SENTINEL``
#: de ``odoo.tools``.
_MRO_SENTINEL = object()


def determine(needle, records, *args):
    """Llama un método dado como cadena o como invocable — ≙ ``determine``.

    Docstring de la fuente, verbatim: *"Simple helper for calling a method
    given as a string or a function."* (``odoo19c: odoo/orm/fields.py:66-87``).

    CONSTRUYE: ``getattr`` y ``callable`` de la estándar.

    DIVERGENCIA DE MECANISMO: la fuente exige que ``records`` sea un recordset
    (``isinstance(records, BaseModel)``) porque allá todo método de modelo
    opera sobre un conjunto. Aquí el sujeto es una **instancia de modelo o un
    queryset**, y la comprobación se relaja a *"no es None"*: exigir una clase
    concreta obligaría a importar ``models`` desde este archivo, que es su
    dependiente.

    :raises TypeError: si ``needle`` no es invocable ni nombra un método.
    """
    if records is None:
        raise TypeError('La determinación necesita un sujeto sobre el que '
                        'llamar; se recibió None.')
    if isinstance(needle, str):
        method = getattr(records, needle, None)
        if method is None:
            raise TypeError(
                f'{type(records).__name__} no declara el método {needle!r}.')
        return method(*args)
    if callable(needle):
        return needle(records, *args)
    raise TypeError('La determinación necesita un invocable o el nombre de un '
                    f'método; se recibió {needle!r}.')


# === El registro de tipos de campo — ``Field._by_type__`` ===================
#
# La fuente lo puebla en ``__init_subclass__``: cada subclase de ``Field`` se
# inscribe con su ``type`` (``odoo19c: odoo/orm/fields.py:312,327``). Aquí las
# subclases son de Django y su ``__init_subclass__`` es de Django, así que el
# registro se **deriva** de ``__all__`` — el mismo criterio con que
# ``ir_model.FIELD_TYPES`` ya se derivaba de él.
#
# Vive aquí y no en ``ir_model.py`` porque aquí es donde la referencia lo
# declara, y porque tenerlo en los dos sitios sería la segunda fuente de
# verdad que ``calibration-verified-numbers.md`` prohíbe: ``ir_model`` lo
# importa de este módulo.

#: Separa el ``CamelCase`` del nombre exportado para reconstruir la clave del
#: tipo: ``Many2oneReference`` → ``many2one_reference``.
_CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


def _type_key(exported_name):
    """Nombre de clase exportado → clave de tipo al estilo de la referencia."""
    return _CAMEL_BOUNDARY.sub('_', exported_name).lower()


#: ≙ ``Field._by_type__`` (``odoo19c: odoo/orm/fields.py:312``) — «mapping from
#: type name to field type». Derivado de :data:`__all__`, no declarado: una
#: lista escrita a mano se desincroniza con el módulo en el primer campo nuevo.
_by_type__ = {_type_key(name): globals()[name] for name in __all__}

#: Tipo interno de Django → clave de tipo de la referencia, para el recorrido
#: **inverso**: dado un campo ya construido, qué ``type`` declara.
#:
#: Declarado y no derivado, y la razón es que el mapa de alias es
#: muchos-a-uno: ``Char``, ``Text`` y ``Html`` comparten familia en Django, así
#: que ``_by_type__`` no se puede invertir sin perder información. ``html``
#: no se recupera nunca —colapsa en ``text``—; ``selection`` sí, porque
#: ``choices`` lo delata.
DJANGO_TYPE_TO_TTYPE = {
    'AutoField': 'integer',
    'BigAutoField': 'integer',
    'BigIntegerField': 'integer',
    'BinaryField': 'binary',
    'BooleanField': 'boolean',
    'CharField': 'char',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'monetary',
    'EmailField': 'char',
    'FileField': 'binary',
    'FloatField': 'float',
    'ForeignKey': 'many2one',
    'ImageField': 'image',
    'IntegerField': 'integer',
    'JSONField': 'json',
    'ManyToManyField': 'many2many',
    'OneToOneField': 'many2one',
    'PositiveIntegerField': 'integer',
    'PositiveSmallIntegerField': 'integer',
    'SlugField': 'char',
    'SmallIntegerField': 'integer',
    'TextField': 'text',
    'URLField': 'char',
    'UUIDField': 'char',
}


def type_for(field):
    """El ``type`` de la referencia que le corresponde a un campo de Django.

    Es la función que puebla :attr:`Field.type`. ``ir.model.fields.ttype_for``
    delega aquí desde el 2026-08-30: el mapa tenía dos dueños y el de la
    referencia es éste.
    """
    #: Lo que la FACHADA declaró gana sobre lo que el campo construido
    #: aparenta: ``make_dispatcher`` anota ``declared_type`` con el
    #: ``base_type`` del tipo de la fuente, que es el porte del atributo de
    #: clase ``type`` de la referencia. Sin esta rama un
    #: ``Selection(related=…)`` —``CharField`` sin ``choices`` todavía—
    #: publicaba ``char`` y rompía la comparación de ``setup_related``.
    declared = getattr(field, 'declared_type', None)
    if declared:
        return declared
    internal = field.get_internal_type()
    if internal == 'CharField' and getattr(field, 'choices', None):
        return 'selection'
    return DJANGO_TYPE_TO_TTYPE.get(internal, 'char')


# ===========================================================================
# ``Field`` — el contrato del campo, instalado sobre la base de Django
# ===========================================================================
#
# ``odoo19c: odoo/orm/fields.py:92-1932`` declara ``Field`` como la clase base
# de la que cuelga todo campo del ORM: 68 atributos de clase y 72 métodos.
#
# Aquí ``Field`` **es** ``django.db.models.Field``, y no una clase paralela.
# Es la lectura fiel: allá ``Field`` es la base de la que hereda todo campo, y
# aquí la base de la que hereda todo campo es la de Django —``Integer =
# models.IntegerField``, ``fields_numeric.py``—. Un ``Field`` propio dejaría
# ``isinstance(campo, Field)`` en falso para los veinte tipos del árbol, que es
# exactamente lo contrario de lo que la fuente garantiza.
#
# Las cinco mediciones que fijan la forma
# =======================================
#
# Reproducibles con ``uv run python scripts/census_field_contract.py``:
#
# 1. **140 símbolos** declara la fuente (68 atributos + 72 métodos).
# 2. **4 colisionan** con ``django.db.models.Field``: ``__init__``, ``__str__``,
#    ``__repr__`` y ``__init_subclass__``. Los cuatro son de Django y se
#    respetan — instalar los de la fuente encima rompería el ORM anfitrión.
#    Los otros **136** se instalan sin pisar nada.
# 3. **2 de 68** atributos los fija una instancia de Django en su ``__init__``
#    (``default`` y ``name``), así que su default de clase nunca se consulta.
#    Los otros **66** quedan vivos, que es lo que la fuente quiere.
# 4. **13 nombres se ASIGNAN** en este árbol y **5 en Django**. Ésos no pueden
#    portarse como ``property`` de solo lectura —la asignación levantaría
#    ``AttributeError``—, así que van como atributo llano que la instancia
#    pisa. Es la medición que decide, una por una, entre las dos formas.
#
#    Su **raíz importa tanto como su regla**: acotada a ``django/db/models``
#    publicaba 0 asignaciones de ``base_field``, se portó como ``property``, y
#    el arranque de Django reventó — ``ArrayField.__init__`` lo asigna desde
#    ``django/contrib/postgres/fields/array.py:27``. Hoy la raíz es el paquete
#    entero. De ahí sale :class:`_ComputedUnlessAssigned`, el descriptor NO de
#    datos que deja ganar a quien asigne.
# 5. **La conducta** — a qué responde ``models.Field`` con este módulo ya
#    cargado. Es el único eje que no mide el NOMBRE, y hace falta porque la
#    medición 1 busca el nombre en TODO ``src/``: una mención en un docstring
#    de otro archivo la satisface. ``get_description`` figuraba presente por
#    una línea de prosa que decía que NO existía.
#
# El veredicto por grupo — TRAE / CONSTRUYE
# ==========================================
#
# ==================================  ==========  ============================
# Mecanismo                           Veredicto   Con qué
# ==================================  ==========  ============================
# la base de todo campo               **TRAE**    ``models.Field``
# etiqueta, ayuda y edición           **TRAE**    ``verbose_name``,
#                                                 ``help_text``, ``editable``
# la columna y si se almacena         **TRAE**    ``db_column``, ``db_type``,
#                                                 ``concrete``
# la relación y su modelo             **TRAE**    ``is_relation``,
#                                                 ``related_model``
# crear y alterar la columna          **TRAE**    ``SchemaEditor`` — el DDL
#                                                 que las migraciones emiten
# el orden de declaración             **TRAE**    ``creation_counter``
# ligar el campo a su modelo          **TRAE**    ``contribute_to_class``,
#                                                 el ``__set_name__`` de Django
# la caché de campo por transacción   CONSTRUYE   ``orm.environments``
#                                                 :class:`Transaction`
# el orden de columna por tipo        CONSTRUYE   ``tools.sql``
#                                                 ``sql_order_by_type``
# la descripción del campo al cliente CONSTRUYE   los ``_description_*`` sobre
#                                                 lo que ya se deriva
# el campo relacionado (``related=``) CONSTRUYE   recorrido por ``getattr``
# el cómputo diferido y su inversa    CONSTRUYE   :func:`determine` sobre
#                                                 ``tocompute``
# ==================================  ==========  ============================
#
# Ninguno queda EXCLUIDO: los 140 símbolos tienen su desenlace.

_logger = logging.getLogger(__name__)

#: ≙ ``Field`` (``odoo19c: odoo/orm/fields.py:92``). El nombre de la fuente,
#: ligado a la base real de este árbol. ``isinstance(campo, Field)`` es cierto
#: para los veinte tipos exportados, igual que allá.
Field = models.Field


#: Los 66 atributos de clase cuyo default de la fuente queda **vivo** aquí —
#: los dos que faltan del total de 68 son ``default`` y ``name``, que toda
#: instancia de Django fija en su ``__init__`` (medición 3 del censo).
#:
#: Se instalan como atributos llanos y no como ``property`` porque la medición
#: 4 encontró que trece de ellos se asignan en este árbol; distinguir cuáles
#: uno por uno partiría el grupo sin ganancia, y un atributo llano se
#: comporta igual que el default de clase de la fuente: la instancia lo pisa
#: cuando quiere, y cuando no, gobierna el de aquí.
_FIELD_CLASS_ATTRIBUTES = {
    # --- identidad y naturaleza del campo -------------------------------
    'translate': False,             # si el campo se traduce
    'is_text': False,               # si en la base es un tipo textual
    'falsy_value': None,            # el valor que cuenta como no establecido
    'write_sequence': 0,            # orden del campo dentro de un ``write()``
    '_column_type': None,           # (ident, spec) de la columna
    # --- procedencia y montaje ------------------------------------------
    '_args__': None,                # los parámetros que recibió ``__init__``
    '_module': None,                # el módulo que declara el campo
    '_modules': (),                 # los módulos que lo definen
    '_setup_done': True,            # si el montaje del campo terminó
    '_base_fields__': (),           # los campos que definen a éste, en orden
    '_extra_keys__': (),            # los parámetros desconocidos que recibió
    '_direct': False,               # si se puede usar directamente (compartido)
    '_toplevel': False,             # si está en la clase de registro del modelo
    # --- herencia por delegación (``_inherits``) -------------------------
    'inherited': False,             # si el campo es heredado
    'inherited_field': None,        # el campo heredado correspondiente
    # --- nombres ----------------------------------------------------------
    'model_name': '',               # el modelo de este campo
    'comodel_name': None,           # el modelo de los valores, si es relacional
    # --- almacenamiento ---------------------------------------------------
    'store': True,                  # si se almacena en la base
    'index': None,                  # cómo se indexa en la base
    'manual': False,                # si es un campo a medida
    'copy': True,                   # si se copia al duplicar el registro
    # --- cómputo, inversa y búsqueda --------------------------------------
    '_depends': None,               # las dependencias declaradas
    '_depends_context': None,       # las claves de contexto de las que depende
    'recursive': False,             # si el campo depende de sí mismo
    'compute': None,                # compute(recs) calcula el campo
    'compute_sudo': False,          # si el cómputo corre elevado
    'precompute': False,            # si se calcula antes de crear la fila
    'inverse': None,                # inverse(recs) invierte el campo
    'search': None,                 # search(recs, operador, valor)
    'related': None,                # la ruta de campos, si es relacionado
    'related_field': None,          # el campo relacionado correspondiente
    'company_dependent': False,     # si el valor depende de la empresa activa
    # --- presentación -----------------------------------------------------
    'string': None,                 # la etiqueta del campo
    'export_string_translation': True,  # si su etiqueta se exporta traducida
    'help': None,                   # el texto de ayuda
    'readonly': False,              # si es de solo lectura en la interfaz
    'required': False,              # si el valor es obligatorio
    'groups': None,                 # los grupos que pueden verlo
    'change_default': False,        # si puede disparar un "user-onchange"
    'aggregator': None,             # el operador con que se agrega
    'group_expand': None,           # el método que expande los grupos
    'falsy_value_label': None,      # qué mostrar cuando no está establecido
    'prefetch': True,               # el grupo de prelectura
    'default_export_compatible': False,  # si se exporta por defecto
    'exportable': True,             # si el campo es exportable
}

for _name_attr, _default_value in _FIELD_CLASS_ATTRIBUTES.items():
    if not hasattr(models.Field, _name_attr):
        setattr(models.Field, _name_attr, _default_value)

#: El mismo contrato sobre :class:`~orm.fields_nonstored.NonStored`, con UNA
#: excepción: ``store``.
#:
#: En la fuente no hay dos clases. Un campo sin columna **es** un ``Field`` con
#: ``store=False`` (``odoo19c: odoo/orm/fields.py:455``), así que responde a
#: los mismos cuarenta y tantos atributos que cualquier otro. Aquí la jerarquía
#: del stack los separa —``NonStored`` no desciende de ``models.Field``, y no
#: puede: no tiene columna que declarar—, y el bucle de arriba sólo alcanzaba a
#: la clase de Django. El resultado era que un campo sin columna levantaba
#: ``AttributeError`` ante ``_description_searchable``, que es justo lo que
#: ``_field_setup_related`` pregunta a **cada eslabón** de una cadena
#: ``related=`` antes de cablear su búsqueda (:ref:`h-api-1027`).
#:
#: ``store`` va a ``False`` y no al defecto de ``Field``: es lo que la clase
#: significa, y de él depende ``_description_searchable`` —``bool(self.store or
#: self.search)``—, que con ``True`` daría buscable a todos y no discriminaría
#: nada.
for _name_attr, _default_value in _FIELD_CLASS_ATTRIBUTES.items():
    if not hasattr(NonStored, _name_attr):
        setattr(NonStored, _name_attr,
                False if _name_attr == 'store' else _default_value)

#: Las sobrescrituras por clase concreta van DESPUÉS del bucle: el bucle pone
#: el defecto de ``Field`` y éstas lo pisan donde la fuente lo pisa. Invertir
#: el orden no cambia nada —son clases distintas— pero leerlo así deja claro
#: cuál es el defecto y cuál la excepción.
install_class_attribute_overrides()


def _char_column_type(self):
    """≙ ``Char._column_type`` (``odoo19c: odoo/orm/fields_textual.py:494-496``).

    Allá es ``('varchar', pg_varchar(self.size))`` y aquí ``size`` es el
    ``max_length`` de Django. Es una ``property`` y no una entrada de
    :data:`_CLASS_ATTRIBUTE_OVERRIDES` porque **depende de la instancia**: dos
    ``CharField`` de la misma clase declaran columnas distintas.

    La misma ``property`` sirve a ``Selection`` (``fields_selection.py:63``),
    que declara ``('varchar', pg_varchar())`` — el caso de ``size`` ausente.
    Las dos clases de la fuente comparten aquí una sola clase de Django, así
    que compartir el descriptor no es una simplificación: es la única forma en
    que ``CharField`` puede responder por ambas.
    """
    return ('varchar', pg_varchar(self.max_length or 0))


models.CharField._column_type = property(_char_column_type)


#: ``type`` — el vocabulario de la fuente sobre un campo de Django.
#:
#: Es el único de los 68 atributos de clase que **no** puede ser un valor
#: llano: allá cada clase concreta declara el suyo (``Boolean.type =
#: 'boolean'``), y aquí la clase concreta es la de Django, compartida entre
#: tipos que la fuente separa. Un ``CharField`` con ``choices`` **es** la
#: ``Selection`` de la fuente, y sin ``choices`` es su ``Char``: dos
#: instancias de la misma clase con tipos distintos, que ningún atributo de
#: clase puede expresar.
#:
#: Por eso delega en :func:`type_for`, que ya sabía el mapa completo y no
#: estaba cableado a nada: hasta este porte ``type`` valía ``''`` en toda
#: familia salvo ``date`` y ``datetime`` —las dos que ``fields_temporal``
#: declara en su clase concreta, como la fuente—. El despacho por tipo de
#: campo del registro de optimizadores (``orm/domains.py``) buscaba esa cadena
#: vacía y no casaba con ninguna familia registrada.
#:
#: Un atributo llano de la subclase gana sobre esta ``property`` por
#: resolución de atributo, así que las dos declaraciones de
#: ``fields_temporal`` siguen gobernando su clase.
models.Field.type = property(type_for)


#: ``relational`` — hermano de ``type``, y con el mismo defecto de origen.
#:
#: La fuente lo declara **una vez**, en la base abstracta de los tres campos
#: de relación: ``_Relational.relational: typing.Literal[True] = True``
#: (``odoo19c: odoo/orm/fields_relational.py:35``). Aquí esa base es la de
#: Django, que ya publica el mismo predicado con otro nombre —``is_relation``,
#: verdadero para ``ForeignKey``, ``OneToOneField`` y ``ManyToManyField``—.
#:
#: Instalado como valor llano valía ``False`` incluso en un ``ForeignKey``,
#: que es lo contrario de lo que la fuente garantiza. Su consumidor inmediato
#: es ``_optimize_like_str``, que ramifica por él: un campo relacional con un
#: patrón vacío devuelve una condición sobre el campo, y uno escalar devuelve
#: un booleano. Con ``False`` universal el escalar se aplicaba a los dos.
models.Field.relational = property(lambda self: self.is_relation)

#: ``comodel_name`` — el modelo de los valores de un campo de relacion.
#:
#: La fuente lo declara en la base abstracta de los tres campos de relacion
#: (``odoo19c: odoo/orm/fields_relational.py:36`` — ``comodel_name: str``) y
#: lo puebla ``_setup_attrs`` al resolver la cadena que el programador escribe
#: en ``Many2one('res.partner')``.
#:
#: Instalado como valor llano por :data:`_CLASS_ATTRIBUTE_DEFAULTS` valia
#: ``None`` **incluso en un ForeignKey**, que es lo contrario de lo que la
#: fuente garantiza — medido sobre ``ResUsers._fields['partner']``:
#: ``type='many2one'``, ``relational=True``, ``comodel_name=None``.
#:
#: Aqui el destino lo trae el stack hecho: ``Field.related_model`` es el
#: modelo apuntado, resuelto por Django cuando la app esta lista. Lo unico que
#: falta es TRADUCIRLO al vocabulario de la fuente, y eso lo sabe el registro
#: por nombre: ``registry.name_of`` devuelve el ``_name`` del modelo cuando lo
#: declara. Sin ``_name`` cae a la etiqueta de Django, que es lo mas cercano a
#: un identificador estable de modelo que este arbol tiene.
#:
#: **La derivacion se queda; el ser de solo lectura se retira** (H-API-1094).
#: La fuente declara ``comodel_name: str`` como ANOTACION sin valor, asi que
#: alla no hay descriptor: el nombre lo escribe el ``__init__`` del campo y
#: vive en el ``__dict__`` de la instancia. Un ``property`` es descriptor de
#: DATOS —tiene ``__set__``— y por eso ganaba sobre el ``__dict__`` y rehusaba
#: la asignacion con ``property … has no setter``. Eso rompia la mitad de
#: escritura de ``setup_related`` (``:645-649``), que asigna los cinco
#: ``related_attrs`` con ``setattr``.
#:
#: Un descriptor NO de datos —solo ``__get__``— reproduce la semantica de la
#: fuente sin una sola linea de sincronizacion: Python consulta primero el
#: ``__dict__`` de la instancia, de modo que un valor asignado gana por el
#: orden de busqueda del lenguaje y la derivacion solo corre cuando no hay
#: ninguno. La alternativa —``property`` con ``fset`` que escribe ``__dict__``
#: y ``fget`` que lo lee primero— exige dos sitios que no pueden discrepar.
class _ComodelName:
    """El nombre del comodelo, derivado del destino que Django ya resuelve."""

    __slots__ = ()

    def __get__(self, field, owner=None):
        if field is None:
            return self
        if not field.is_relation:
            return None
        remote = getattr(field, 'related_model', None)
        if remote is None or isinstance(remote, str):
            # Referencia perezosa sin resolver todavia: la cadena que se escribio.
            return remote
        return orm_registry.name_of(remote) or remote._meta.label


models.Field.comodel_name = _ComodelName()

#: ≙ ``Field._by_type__`` colgado de la clase, como en la fuente.
models.Field._by_type__ = _by_type__


# ═══════════════════════════════════════════════════════════════════════════
# El protocolo de descripción — ≙ ``odoo19c: odoo/orm/fields.py:872-975``
# ═══════════════════════════════════════════════════════════════════════════
#
# Es el bloque con el que un campo se **describe a su cliente**: qué nombre
# lleva, de qué tipo es, si se puede ordenar, agrupar o agregar por él. La
# fuente lo resuelve con un convenio de nombres —todo atributo que empieza por
# ``_description_`` publica la clave que sigue al prefijo— y una tabla
# ``description_attrs`` que su ``__init_subclass__`` deriva con ``dir(cls)``.
#
# Aquí ``__init_subclass__`` es una de las cuatro colisiones medidas: es de
# Django y se respeta. La derivación se construye con la misma regla y el
# mismo momento efectivo —la primera vez que alguien la pide, por clase— con
# el descriptor :class:`_DerivedFromPrefix`, que cachea el resultado en el
# ``__dict__`` de la clase que lo pidió. La diferencia con la fuente es
# **cuándo** se deriva, no **qué** deriva: allá al crear la subclase, aquí al
# primer acceso. Una subclase que añada su propio ``_description_*`` obtiene
# su tabla igual que allá, porque ``dir()`` la ve.


class _DerivedFromPrefix:
    """Deriva una tabla ``(clave, atributo)`` de los nombres con un prefijo.

    ≙ el cuerpo de ``__init_subclass__`` (``odoo19c: :336-344``), que hace lo
    mismo con ``dir(cls)`` al crear cada subclase. Aquí es un descriptor de
    clase porque ``__init_subclass__`` colisiona con el de Django.

    Cachea **por clase**, así que la derivación corre una vez por cada una —
    igual que allá, donde corre una vez por creación de subclase.

    El caché va en un mapa propio y NO con ``setattr`` sobre la clase, y la
    razón se midió: al pedir la tabla sobre ``models.Field`` —la clase que
    aloja el descriptor— el ``setattr`` lo sustituía por la tupla, y a partir
    de ahí toda subclase heredaba la tabla de la base en vez de derivar la
    suya. El caché se comía al mecanismo que cachea.

    El mapa es débil en su clave para no retener una clase que ya nadie usa.
    """

    def __init__(self, prefix, attribute_name):
        self.prefix = prefix
        self.attribute_name = attribute_name
        self._by_class = weakref.WeakKeyDictionary()

    def __get__(self, instance, owner=None):
        owner = owner if owner is not None else type(instance)
        cached = self._by_class.get(owner)
        if cached is not None:
            return cached
        cut = len(self.prefix)
        table = tuple((name[cut:], name) for name in dir(owner)
                      if name.startswith(self.prefix))
        self._by_class[owner] = table
        return table


#: ≙ ``Field.related_attrs`` / ``Field.description_attrs`` (``:336-344``).
models.Field.related_attrs = _DerivedFromPrefix('_related_', 'related_attrs')
models.Field.description_attrs = _DerivedFromPrefix('_description_',
                                                    'description_attrs')


def _field_get_description(self, env, attributes=None):
    """≙ ``Field.get_description`` (``:872``) — «return a dictionary that
    describes the field ``self``».

    El convenio es el de la fuente verbatim: se recorre ``description_attrs``,
    se descarta lo que no empiece por ``_description_``, se llama al valor si
    es invocable —los que necesitan el entorno lo son— y se omite el ``None``.

    Omitir el ``None`` no es cosmético: la clave ausente y la clave con
    ``None`` significan cosas distintas para el cliente, y la fuente elige la
    primera.
    """
    description = {}
    for key, attribute in self.description_attrs:
        if attributes is not None and key not in attributes:
            continue
        if not attribute.startswith('_description_'):
            continue
        value = getattr(self, attribute)
        if callable(value):
            value = value(env)
        if value is not None:
            description[key] = value
    return description


models.Field.get_description = _field_get_description

#: Los doce que la fuente declara como ``property(attrgetter(...))``
#: (``:889-900``): la clave publicada es el nombre del atributo que leen.
#: Se instalan con la misma forma —``property``— porque ninguno de los doce
#: aparece en la medición 4 del censo como asignado.
for _key, _source_attribute in (
        ('name', 'name'),
        ('type', 'type'),
        ('store', 'store'),
        ('manual', 'manual'),
        ('related', 'related'),
        ('company_dependent', 'company_dependent'),
        ('readonly', 'readonly'),
        ('required', 'required'),
        ('groups', 'groups'),
        ('change_default', 'change_default'),
        ('default_export_compatible', 'default_export_compatible'),
        ('exportable', 'exportable'),
):
    setattr(models.Field, f'_description_{_key}', property(attrgetter(_source_attribute)))


def _field_description_depends(self, env):
    """≙ ``Field._description_depends`` (``:902``) — las dependencias que el
    registro tiene anotadas para este campo."""
    return env.registry.field_depends[self]


models.Field._description_depends = _field_description_depends


@property
def _field_description_searchable(self):
    """≙ ``Field._description_searchable`` (``:906``) — ``bool(self.store or
    self.search)``, verbatim.

    Un campo con columna se busca por SQL; uno sin columna se busca sólo si
    declara su ``search=``. La disyunción es la misma que allá porque el
    fenómeno es el mismo: hay o no hay por dónde buscar.
    """
    return bool(self.store or self.search)


models.Field._description_searchable = _field_description_searchable
#: Y sobre el campo sin columna, por la misma razón que ``determine_domain`` se
#: instala en las dos clases: es una ``property``, así que el bucle de
#: :data:`_FIELD_CLASS_ATTRIBUTES` —que copia valores— no la alcanza.
NonStored._description_searchable = _field_description_searchable


def _field_description_sortable(self, env):
    """≙ ``Field._description_sortable`` (``:909``).

    **Divergencia de mecanismo, no de contrato.** La fuente responde
    construyendo la consulta y viendo si revienta: llama a
    ``model._order_field_to_sql(...)`` dentro de un ``try`` y devuelve
    ``False`` ante ``ValueError``/``AccessError``. Es su forma de preguntarle
    al motor, porque allá el motor de consultas es suyo.

    Aquí el motor es el de Django, y la misma pregunta se responde **sin
    construir nada**: un campo es ordenable si tiene columna. ``concrete`` es
    el atributo con que Django lo declara, y es exacto — un campo no concreto
    no tiene por dónde ordenarse en SQL.

    El atajo de la fuente y su herencia se conservan verbatim: el campo
    heredado responde por el suyo para no recomputar.
    """
    if self.column_type and self.store:
        return True
    inherited = self.inherited_field
    if inherited is not None and inherited._description_sortable(env):
        return True
    return bool(getattr(self, 'concrete', False))


models.Field._description_sortable = _field_description_sortable


def _field_description_groupable(self, env):
    """≙ ``Field._description_groupable`` (``:924``).

    Misma divergencia de mecanismo que :func:`_field_description_sortable`, y
    por la misma razón. La fuente distingue el caso temporal —agrupa por
    ``<campo>:month``, no por el valor crudo— y esa distinción se conserva
    porque es de contrato, no de motor: un ``date`` se agrupa por tramo.
    """
    if self.column_type and self.store:
        return True
    inherited = self.inherited_field
    if inherited is not None and inherited._description_groupable(env):
        return True
    return bool(getattr(self, 'concrete', False))


models.Field._description_groupable = _field_description_groupable


def _field_description_aggregator(self, env):
    """≙ ``Field._description_aggregator`` (``:940``).

    Devuelve el operador con que el campo se agrega, o ``None`` si no lo
    admite. La primera guarda es la de la fuente verbatim: sin ``aggregator``
    declarado no hay nada que devolver, y con columna almacenada se devuelve
    sin más comprobación.
    """
    if not self.aggregator or (self.column_type and self.store):
        return self.aggregator
    inherited = self.inherited_field
    if inherited is not None and inherited._description_aggregator(env):
        return inherited.aggregator
    return self.aggregator if getattr(self, 'concrete', False) else None


models.Field._description_aggregator = _field_description_aggregator


def _field_description_string(self, env):
    """≙ ``Field._description_string`` (``:955``) — la etiqueta, traducida al
    idioma del entorno cuando lo hay.

    Delega en ``ir.model.fields.get_field_string``, que es quien guarda el
    mapa. Sin idioma en el entorno devuelve la etiqueta declarada, igual que
    allá: no hay a qué traducir.
    """
    if self.string and env.lang:
        model_name = self.base_field.model_name
        field_string = env['ir.model.fields'].get_field_string(model_name)
        return field_string.get(self.name) or self.string
    return self.string


models.Field._description_string = _field_description_string


def _field_description_help(self, env):
    """≙ ``Field._description_help`` (``:962``) — el hermano de
    :func:`_field_description_string` para el texto de ayuda."""
    if self.help and env.lang:
        model_name = self.base_field.model_name
        field_help = env['ir.model.fields'].get_field_help(model_name)
        return field_help.get(self.name) or self.help
    return self.help


models.Field._description_help = _field_description_help


def _field_description_falsy_value_label(self, env):
    """≙ ``Field._description_falsy_value_label`` (``:969``) — qué mostrar
    cuando el valor no está establecido, traducido."""
    return _(self.falsy_value_label) if self.falsy_value_label else None


models.Field._description_falsy_value_label = _field_description_falsy_value_label


def _field_is_editable(self):
    """≙ ``Field.is_editable`` (``:972``) — «return whether the field can be
    editable in a view». Verbatim: ``not self.readonly``.

    NO es el ``editable`` de Django, aunque suene igual: aquél gobierna si el
    campo aparece en un ``ModelForm``; éste, si la vista lo deja editar. El
    nombre de la fuente se conserva justamente para que los dos no se
    confundan.
    """
    return not self.readonly


models.Field.is_editable = _field_is_editable


############################################################################
#
# Conversion of values — ≙ ``odoo19c: odoo/orm/fields.py:975-1081``
#
# El nombre de la sección es el de la fuente. Son nueve métodos y un contrato
# de tres formatos que Django no separa: el suyo tiene ``to_python`` y
# ``get_prep_value``, dos pasos entre «lo que escribió el usuario» y «lo que
# va al placeholder». La fuente distingue cinco —columna, caché, registro,
# lectura y exportación— porque un campo suyo puede guardar un mapa donde
# expone un escalar (traducible, dependiente de empresa), y ahí los formatos
# dejan de coincidir.
#
# Veredicto por el criterio de las dos categorías:
#
# - **el stack lo trae hecho**: el adaptador de ``jsonb``.
#   ``psycopg.types.json.Jsonb`` es el ``PsycopgJson`` de la fuente traído a
#   psycopg 3 —allá es ``from psycopg2.extras import Json as PsycopgJson``—, y
#   la tabla de orden de columna, que ``tools/sql.py`` ya porta como
#   :func:`~tools.sql.sql_order_by_type`.
# - **el stack tiene con qué construirlo**: el contrato en sí, sobre el
#   almacén que ``Transaction.field_data`` ya provee.
#
# Cuatro adaptaciones de firma, cada una con su causa, y valen para toda la
# sección:
#
# 1. ``record.env.transaction.field_data`` → :func:`~orm.environments.get_transaction`
#    y :func:`~orm.environments.env`. No hay ``env`` colgado de la fila: aquí
#    una fila es una instancia de Django y el entorno es ambiente.
# 2. ``record.env.company.id`` → :func:`~orm.environments.get_current_company`,
#    la misma adaptación que ``CompanyDependent.value_for_current_company``.
# 3. ``record._name`` → ``model_of(record)._meta.label``, la llave con que
#    ``ir.default`` guarda sus filas en este árbol. **No** ``type(record)``:
#    el receptor no siempre es una fila. El eje de esquema lo llama desde
#    ``_init_column``, que pasa la CLASE del modelo —allá es un recordset
#    vacío, que responde ``_name`` igual—, y ``type(clase)`` da ``ModelBase``,
#    que no tiene ``_meta``. Medido: el caso reventaba con
#    ``AttributeError: type object 'ModelBase' has no attribute '_meta'`` antes
#    de la corrección. :func:`~orm.utils.model_of` acepta las tres formas que
#    este árbol produce —instancia, ``QuerySet`` y clase— y rehúsa el resto.
# 4. ``self in record.env._field_depends_context`` →
#    :func:`_has_context_buckets`, que ya responde lo mismo desde el mapa
#    derivado del registro.
#
############################################################################


def _field_convert_to_column(self, value, record, values=None, validate=True):
    """≙ ``Field.convert_to_column`` (``:981``) — del formato de ``write`` al
    parámetro SQL de una condición.

    Cuerpo verbatim de la fuente, y sus cuatro ramas importan en ese orden:
    ``None`` y ``False`` se descartan **por identidad**, así que la cadena
    vacía y el ``0`` sobreviven; luego ``str`` pasa tal cual, ``bytes`` se
    decodifica, y el resto se lleva a texto.

    La comparación por identidad no es un detalle de estilo: con ``not value``
    el cero de un ``Integer`` y la cadena vacía de un ``Char`` se guardarían
    como ``NULL``, que es otro valor.
    """
    if value is None or value is False:
        return None
    if isinstance(value, str):
        return value
    elif isinstance(value, bytes):
        return value.decode()
    else:
        return str(value)


models.Field.convert_to_column = _field_convert_to_column


def _field_convert_to_column_insert(self, value, record, values=None, validate=True):
    """≙ ``Field.convert_to_column_insert`` (``:994``) — el parámetro de un
    ``INSERT``, que es donde el campo dependiente de empresa se separa.

    Sin ``company_dependent`` delega en :func:`_field_convert_to_column` y ahí
    termina. Con él, el valor de la empresa activa se envuelve en un mapa
    ``{empresa: valor}`` para la columna ``jsonb`` — **salvo** que coincida con
    el default de ``ir.default``, en cuyo caso devuelve ``None`` y la fila
    hereda el fallback en vez de repetirlo.

    El default se lee **crudo**, sin pasarlo por ninguna conversión, y luego se
    compara ya convertido. Es lo que la fuente hace, y por eso NO delega en
    :meth:`~orm.fields_company_dependent.CompanyDependent.get_company_dependent_fallback`,
    que sí aplica ``convert_to_cache``/``convert_to_record``
    (``odoo19c: :794-801``): comparar un valor convertido contra otro
    convertido dos veces daría falsos negativos en los tipos cuya conversión no
    es idempotente.
    """
    value = self.convert_to_column(value, record, values, validate)
    if not self.company_dependent:
        return value
    IrDefault = apps.get_model('base', 'IrDefault')
    fallback = IrDefault._get_model_defaults(
        model_of(record)._meta.label,
        company_id=get_current_company()).get(self.name)
    if value == self.convert_to_column(fallback, record):
        return None
    return Jsonb({get_current_company(): value})


models.Field.convert_to_column_insert = _field_convert_to_column_insert


_DJANGO_FIELD_GET_DB_PREP_SAVE = models.Field.get_db_prep_save


def _field_get_db_prep_save(self, value, connection):
    """El cableado de ``convert_to_column`` al camino de escritura del stack.

    **Dónde encaja, y es ``get_db_prep_save`` y no ``get_prep_value``.** En la
    fuente ``convert_to_column`` es el último paso hacia el parámetro SQL **de
    una escritura**: quien guarda una columna pasa por él, y de ahí sale el
    vocabulario de «sin valor» traducido. Una **condición** de búsqueda no pasa
    por ahí — la arma ``_condition_to_sql``, que es otro camino. Django separa
    los dos igual: ``get_prep_value`` lo consultan la escritura **y** el
    ``lookup``; ``get_db_prep_save`` sólo la escritura (lo llama ``pre_save``).

    Cablearlo al primero fue un defecto medido: el recorte a ``max_length`` que
    ``Char`` aplica al guardar (``odoo19c: odoo/orm/fields_textual.py:110``:
    ``value = s[:self.size]``) se aplicaba también al parámetro de un
    ``code__iexact='nope'``, que quedaba en ``'no'`` y encontraba Noruega. El
    recorte es correcto; el sitio no lo era.

    **Por qué sólo cuando el tipo la declara.** El cuerpo base
    (:func:`_field_convert_to_column`) lleva a texto todo lo que no sea
    ``str``/``bytes``, que es correcto para la familia textual de la fuente y
    no para un tipo que este stack convierte a su manera. La fuente reparte esa
    decisión **por clase**: declara la sobrecarga donde el tipo tiene
    vocabulario propio —``Boolean`` conserva ``False`` (``fields_misc.py:28``),
    ``Integer`` lo lleva a ``0`` (``fields_numeric.py:32``), ``Many2one`` a
    ``None`` (``fields_relational.py:326``), ``Char`` delega en su caché
    (``fields_textual.py:84``)— y hereda la base donde no. Aquí se lee ese
    mismo reparto: el tipo que la declaró la usa; el que no, conserva la
    conversión de Django intacta.

    ``validate=False`` y sin registro: la validación pertenece a la escritura
    del ORM —que llama a ``convert_to_column_insert`` con el registro— y no a
    este último metro hacia el motor, donde el valor ya está decidido.

    **``None`` sobre una columna que admite el nulo NO se convierte, y ésa es
    la traducción de «la clave no venía en ``vals``».** La fuente construye la
    columna sólo para los campos **presentes** en el diccionario de escritura
    (``convert_to_column_insert`` por clave); el que no viene toma el default
    de la columna, que sin ``required`` es ``NULL``. Django no tiene esa
    distinción —escribe todas las columnas siempre— y lo que lleva en su lugar
    es el ``None`` del atributo. Así que ``None`` sobre columna nulable es el
    caso *ausente* y pasa sin tocar; un ``False``, un ``0`` o una cadena vacía
    son un valor **dado** y sí pasan por el conversor, que los lleva al
    vocabulario del tipo —``0`` para un entero, ``None`` para el resto—.

    Sin esta lectura, ``int(value or 0)`` convertía el «no establecido» de una
    columna nulable en un cero real: medido, ``ir_filters.embedded_parent_res_id``
    dejó de ser ``NULL`` y su ``CHECK`` lo rechazó, y un contador de uso vacío
    pasó a leerse como agotado. La fuente no tiene ese problema porque la clave
    sencillamente no llega hasta aquí.

    **Lo que trae su propio SQL no es un valor y no se convierte.** El
    discriminador no se inventa: lo declara la propia función envuelta
    (``django/db/models/fields/__init__.py:1009`` — ``if hasattr(value,
    "as_sql"): return value``). En un ``UPDATE`` con ``F()`` el compilador
    resuelve la expresión y se la pasa al campo
    (``django/db/models/sql/compiler.py:2035-2065``); el cableado corría
    **por delante** de esa guarda y ``int(value or 0)`` recibía un
    ``CombinedExpression``. La fuente coincide en el fondo: sus dos únicos
    llamadores de ``convert_to_column`` (``odoo19c: odoo/orm/models.py:3145``
    y ``:4870``) le pasan un valor del formato de caché, y sus fragmentos de
    SQL viajan como ``SQL()`` sin entrar por aquí.

    **Y hay cuerpos que sí necesitan el registro**, así que se excluyen por
    declaración y no por descarte silencioso:
    :attr:`~models.Field.column_conversion_needs_record`. Es el caso de
    ``Properties`` (``odoo19c: odoo/orm/fields_properties.py:124`` y ``:871``),
    cuya forma de columna se resuelve contra la definición que cuelga del
    registro. Para ésos el camino sigue siendo el del ORM, que sí lo tiene.
    """
    if not (hasattr(value, 'as_sql') or (value is None and self.null)
            or self.column_conversion_needs_record
            or type(self).convert_to_column is models.Field.convert_to_column):
        value = self.convert_to_column(value, None, validate=False)
    return _DJANGO_FIELD_GET_DB_PREP_SAVE(self, value, connection)


models.Field.get_db_prep_save = _field_get_db_prep_save

#: Si el cuerpo de ``convert_to_column`` del campo consulta el registro.
#:
#: Por omisión no: los cuerpos de la fuente para ``Boolean``, ``Integer``,
#: ``Many2one``, ``Char`` y la propia base deciden con el valor y nada más. Lo
#: declara en ``True`` el tipo cuya forma de columna se resuelve contra el
#: registro —``Properties``—, y con eso queda fuera del cableado a
#: ``get_prep_value``, que no tiene registro que pasar.
models.Field.column_conversion_needs_record = False


def _field_get_column_update(self, record):
    """≙ ``Field.get_column_update`` (``:1008``) — el valor **de la caché**
    como parámetro de un ``UPDATE``.

    Lee ``field_data``, no el atributo de la instancia: lo que se escribe es lo
    que el ORM tiene por bueno, y esos dos pueden diferir mientras haya un
    cómputo pendiente. Tres caminos, los de la fuente:

    - **dependiente de empresa** — recorre los cubos por clave de contexto y
      arma el mapa ``{empresa: valor}`` con los que tengan valor; sin ninguno,
      ``None``.
    - **con contexto** — toma el **primer** valor establecido. La fuente lo
      justifica en su comentario: más de uno es un error de diseño del modelo,
      y como la columna sólo admite uno, elige al azar en vez de callar. Sin
      ninguno levanta ``AssertionError``.
    - **el caso común** — ``field_cache[record_id]``, con corchete y no
      ``.get``: la ausencia es un ``KeyError``, no un ``None``. Un campo sin
      valor en caché no sabe qué escribir, y decirlo es lo que impide que un
      ``UPDATE`` ponga ``NULL`` donde había un valor.
    """
    field_cache = get_transaction().field_data[self]
    record_id = record.pk
    if self.company_dependent:
        values = {}
        for ctx_key, cache in field_cache.items():
            if (value := cache.get(record_id, SENTINEL)) is not SENTINEL:
                values[ctx_key[0]] = self.convert_to_column(value, record)
        return Jsonb(values) if values else None
    if _has_context_buckets(self):
        for ctx_key, cache in field_cache.items():
            if (value := cache.get(record_id, SENTINEL)) is not SENTINEL:
                break
        else:
            raise AssertionError(
                f"Value not in cache for field {self} and id={record_id}")
    else:
        value = field_cache[record_id]
    return self.convert_to_column_insert(value, record, validate=False)


models.Field.get_column_update = _field_get_column_update


# ═══════════════════════════════════════════════════════════════════════════
# El EJE DE ESQUEMA — cómo un campo lleva su forma a la tabla
#     ≙ ``Field.update_db`` y su familia (``odoo19c: odoo/orm/fields.py:
#     1094-1202``)
# ═══════════════════════════════════════════════════════════════════════════
#
# Cinco métodos que ``BaseModel._auto_init`` recorre por campo: crear la
# columna, convertirla si su tipo divergió, poner o quitar el ``NOT NULL``, y
# —cuando el campo es un ``related`` simple— llenarla de una vez en SQL en vez
# de recomputarla fila a fila.
#
# **Ocho adaptaciones, todas medidas, ninguna recorta el contrato:**
#
# 1. ``model._table`` **existe** y vale lo mismo que ``Meta.db_table``, así que
#    se usa directo — sin adaptación.
# 2. ``model._fields`` no resuelve en toda clase de este árbol; el mapa lo da
#    :func:`~orm.utils.model_field_registry`, que fusiona los campos de Django
#    con los no persistidos.
# 3. **El cursor.** La fuente escribe ``model.env.cr``; aquí ``env().cr`` es la
#    *conexión* de Django, no un cursor, y el modelo es una clase sin entorno.
#    Cada método abre el suyo desde el alias por omisión. Misma puerta que
#    ``registry.Registry.is_an_ordinary_table`` ya declaró, y por eso la firma
#    **no** gana un parámetro ``cr``: quien llama sigue pasando lo que la
#    fuente pasa.
# 4. ``model.pool`` no existe; el registro es :class:`~orm.registry.Registry`,
#    que ya lleva ``post_init``, ``post_constraint`` y sus dos colas.
# 5. **``self.name`` no es ``self.column``.** En la fuente el campo se llama
#    igual que su columna, así que ambas formas coinciden y su DDL escribe el
#    nombre. Aquí no: medido con ``django.apps`` sobre el árbol cargado, **747
#    de 4291** campos con columna la declaran distinta (17.4 %) — todo
#    ``ForeignKey`` la sufija ``_id``, entre otros. Por eso el DDL y el lookup
#    en el mapa ``columns`` usan ``self.column``, y las búsquedas en el
#    registro de campos siguen usando ``self.name``. Confundirlas crea una
#    columna paralela con el nombre del campo y deja la real intacta, sin que
#    nada falle.
#    *Métrica:* ``column != name`` sobre ``_meta.get_fields()`` de
#    ``apps.get_models()``.
#    *Ciega a:* un campo cuya columna la fije una migración a mano divergiendo
#    de ``db_column``.
# 6. **El campo sin columna corta antes.** ``:1101`` corta con
#    ``if not self.column_type: return False``, y ese corte llega por herencia
#    a todo campo de la fuente. Aquí :class:`~orm.fields_nonstored.NonStored`
#    **no desciende de** ``models.Field``, así que el enlace de estos cinco
#    métodos no lo alcanza: declara su propio ``column_type = None`` y su
#    propio ``update_db``, siguiendo el precedente que ese archivo ya
#    documenta para ``inverse_related``. Se porta **el corte**, no los cinco:
#    medido sobre todo ``$ODOO19C/odoo``, el único llamador externo de la
#    familia es ``models.py:3228`` → ``update_db``; los otros cinco métodos
#    sólo se alcanzan desde dentro de ``update_db`` o por ``super()``.
# 7. **El receptor de ``flush_model`` va explícito.** ``models.Model`` recibe
#    el método por asignación (``orm/models.py``), así que se liga como método
#    de *instancia*: ``model.flush_model([...])`` sobre una CLASE devuelve la
#    función sin ligar y pasa la lista como ``self``. Los dos métodos propios
#    de esta familia —``_init_column`` y ``_table_has_rows``— lo resuelven
#    declarándose ``classmethod``; en uno ajeno no se puede cambiar el enlace,
#    así que se nombra el receptor: ``models.Model.flush_model(model, [...])``.
#    En el mismo pase, ``_model_of_records`` ganó su rama de CLASE: sus dos
#    consumidores ya escribían la guarda ``self if isinstance(self, type)``, o
#    sea que **declaraban** admitirla, y la función reventaba antes de
#    devolverla.
# 8. **El contrato del default es el de Django, no la falsedad.** ``:3141``
#    escribe ``if field.default:`` porque allá el default, cuando existe, es
#    SIEMPRE un invocable. Aquí es un valor **o** un invocable, y el centinela
#    de «sin default» no es la falsedad sino ``NOT_PROVIDED``: con
#    ``default=''`` —un ``TextField`` obligatorio— la guarda de la fuente daría
#    falso y la columna nueva quedaría sin sembrar, que es lo contrario de lo
#    que ella hace. El par que el stack declara resuelve las dos formas:
#    ``has_default()`` (``fields/__init__.py:1013``) y ``get_default()``
#    (``:1021``, que envuelve el valor en un ``lambda`` cuando no es
#    invocable).


def _field_update_db(self, model, columns):
    """≙ ``Field.update_db`` (``:1094``) — lleva el campo al esquema.

    Docstring de la fuente, verbatim: *"Update the database schema to implement
    this field"*; devuelve *"``True`` if the field must be recomputed on
    existing rows"*.

    El índice **no** se toca aquí: lo gobierna ``registry.check_indexes()``,
    igual que allá.

    La rama larga es la **optimización del related simple** (``foo_id.bar``):
    cuando la columna nace y el campo es un related de un solo salto sobre un
    ``many2one`` almacenado y sin cómputo, el valor se copia con un ``UPDATE
    ... FROM`` diferido a ``post_init`` en vez de recomputarse registro a
    registro. Por eso devuelve ``False``: el cómputo clásico se descarta.
    """
    if not self.column_type:
        return False

    column = columns.get(self.column)

    # crea/actualiza la columna y su restricción de no-nulo; el índice lo
    # gobierna registry.check_indexes()
    self.update_db_column(model, column)
    self.update_db_notnull(model, column)

    # optimización para calcular related simples del tipo 'foo_id.bar'
    if (
        not column
        and self.related and self.related.count('.') == 1
        and self.related_field.store and not self.related_field.compute
        and not (self.related_field.type == 'binary' and self.related_field.attachment)
        and self.related_field.type not in ('one2many', 'many2many')
    ):
        join_field = model_field_registry(model)[self.related.split('.')[0]]
        if (
            join_field.type == 'many2one'
            and join_field.store and not join_field.compute
        ):
            Registry(DEFAULT_DB_ALIAS).post_init(self.update_db_related, model)
            # descarta el cálculo «clásico»
            return False

    return not column


models.Field.update_db = _field_update_db


def _field_update_db_column(self, model, column):
    """≙ ``Field.update_db_column`` (``:1129``) — crea o actualiza la columna.

    Docstring de la fuente, verbatim: *"Create/update the column corresponding
    to ``self``"*. El parámetro ``column`` es la configuración de la columna
    tal como la base la reporta, o ``None`` si aún no existe.

    La comparación es contra ``column_type[0]`` —el ``udt_name`` de PostgreSQL,
    no la declaración DDL— porque es lo que ``information_schema`` devuelve. Un
    ``varchar(64)`` y un ``varchar`` comparten ``udt_name`` a propósito: lo que
    esta rama vigila es el cambio de **tipo**, no el de longitud.
    """
    if not column:
        # la columna no existe, se crea
        with connections[DEFAULT_DB_ALIAS].cursor() as cr:
            create_column(cr, model._table, self.column,
                          self.column_type[1], self.string)
        return
    if column['udt_name'] == self.column_type[0]:
        return
    self._convert_db_column(model, column)


models.Field.update_db_column = _field_update_db_column


def _field_convert_db_column(self, model, column):
    """≙ ``Field._convert_db_column`` (``:1143``).

    Docstring de la fuente, verbatim: *"Convert the given database column to
    the type of the field"*. Delega en :func:`~tools.sql.convert_column`, que
    es quien retira las vistas dependientes cuando PostgreSQL rechaza el
    ``ALTER``.
    """
    with connections[DEFAULT_DB_ALIAS].cursor() as cr:
        convert_column(cr, model._table, self.column, self.column_type[1])


models.Field._convert_db_column = _field_convert_db_column


def _field_update_db_notnull(self, model, column):
    """≙ ``Field.update_db_notnull`` (``:1147``) — pone o quita el ``NOT NULL``.

    Docstring de la fuente, verbatim: *"Add or remove the NOT NULL constraint
    on ``self``"*.

    Tres caminos, los de la fuente:

    - **la columna nace, o el campo pasa a obligatorio** — si la tabla ya tiene
      filas, se les siembra el default con ``_init_column``; sin ese paso, las
      filas viejas quedarían en ``NULL`` y la restricción las rechazaría.
    - **el campo es obligatorio y la columna aún admite nulos** — la restricción
      **no** se aplica en el acto: se difiere a ``post_init``. La razón es de la
      fuente y está en su comentario: ``_init_column`` puede haber diferido
      cómputos, así que el ``NOT NULL`` tiene que esperar a que se vacíen. El
      cierre re-lee el campo del registro porque *"the model's ``_fields`` may
      have been reset"* entre encolar y ejecutar.
    - **el campo dejó de ser obligatorio** — se quita, y ahí termina.
    """
    has_notnull = column and column['is_nullable'] == 'NO'

    if not column or (self.required and not has_notnull):
        # la columna es nueva o pasa a obligatoria; se inicializan sus valores
        if model._table_has_rows():
            model._init_column(self.name)

    if self.required and not has_notnull:
        # _init_column puede diferir cómputos a la fase post-init
        @Registry(DEFAULT_DB_ALIAS).post_init
        def add_not_null():
            # Cuando esta función se llama, los _fields del modelo pueden
            # haberse reiniciado aunque la clase sea la misma. Se recupera el
            # campo para ver si la restricción sigue aplicando.
            field = model_field_registry(model)[self.name]
            if not field.required or not field.store:
                return
            if field.compute:
                query = SQL(
                    "SELECT id FROM %s AS t WHERE %s IS NULL",
                    SQL.identifier(model._table),
                    SQL.identifier(field.column),
                )
                with connections[DEFAULT_DB_ALIAS].cursor() as cr:
                    cr.execute(query.code, query.params)
                    pending = [row[0] for row in cr.fetchall()]
                get_environment().add_to_compute(field, pending)
            # vacía los valores antes de añadir la restricción NOT NULL.
            # El receptor va explícito: ``flush_model`` se cuelga de ``Model``
            # como método de instancia (``orm/models.py:3549``) y su cuerpo ya
            # contempla recibir la clase (``self if isinstance(self, type)``),
            # pero ``model.flush_model([...])`` sobre una CLASE devuelve la
            # función sin ligar y pasa la lista como ``self``. Es el mismo
            # defecto de binding que ``_init_column`` y ``_table_has_rows``
            # resuelven declarándose ``classmethod``; aquí no se puede cambiar
            # el binding ajeno, así que se nombra el receptor.
            models.Model.flush_model(model, [field.name])
            registry = Registry(DEFAULT_DB_ALIAS)
            with connections[DEFAULT_DB_ALIAS].cursor() as cr:
                registry.post_constraint(
                    cr,
                    lambda cursor: set_not_null(cursor, model._table, field.column),
                    key=f"add_not_null:{model._table}:{field.column}",
                )

    elif not self.required and has_notnull:
        with connections[DEFAULT_DB_ALIAS].cursor() as cr:
            drop_not_null(cr, model._table, self.column)


models.Field.update_db_notnull = _field_update_db_notnull


def _field_update_db_related(self, model):
    """≙ ``Field.update_db_related`` (``:1190``).

    Docstring de la fuente, verbatim: *"Compute a stored related field directly
    in SQL"*. Un solo ``UPDATE ... FROM`` en vez de N lecturas: es la mitad que
    justifica la rama de optimización de :func:`_field_update_db`.
    """
    comodel = model_of_field(self.related_field, orm_registry)
    join_field, comodel_field = self.related.split('.')
    query = SQL(
        """ UPDATE %(model_table)s AS x
            SET %(model_field)s = y.%(comodel_field)s
            FROM %(comodel_table)s AS y
            WHERE x.%(join_field)s = y.id """,
        model_table=SQL.identifier(model._table),
        model_field=SQL.identifier(self.column),
        comodel_table=SQL.identifier(comodel._table),
        comodel_field=SQL.identifier(
            model_field_registry(comodel)[comodel_field].column),
        join_field=SQL.identifier(model_field_registry(model)[join_field].column),
    )
    with connections[DEFAULT_DB_ALIAS].cursor() as cr:
        cr.execute(query.code, query.params)


models.Field.update_db_related = _field_update_db_related


def _field_convert_to_cache(self, value, record, validate=True):
    """≙ ``Field.convert_to_cache`` (``:1034``) — al formato de caché.

    El ``Field`` base no transforma nada; son sus subclases las que dan
    contenido a este método. Existe igual porque es el primer eslabón de
    :func:`_field_convert_to_write`, y sin él la cadena no se puede escribir de
    forma uniforme.
    """
    return value


models.Field.convert_to_cache = _field_convert_to_cache


def _field_convert_to_record(self, value, record):
    """≙ ``Field.convert_to_record`` (``:1046``) — de la caché al registro.

    ``False if value is None else value``: el vocabulario de la fuente para
    «no establecido» es ``False``, no ``None``. Quien lee un campo vacío recibe
    ``False``, y ``_compute_display_name`` y las condiciones de dominio
    distinguen los dos.
    """
    return False if value is None else value


models.Field.convert_to_record = _field_convert_to_record


def _field_convert_to_read(self, value, record, use_display_name=True):
    """≙ ``Field.convert_to_read`` (``:1053``) — del registro al formato de
    ``read``.

    ``use_display_name`` se conserva en la firma aunque el cuerpo base no lo
    consulte: es el parámetro con que las sobrecargas relacionales deciden si
    resuelven la etiqueta del registro apuntado, y quitarlo de la base rompería
    la llamada polimórfica.
    """
    return False if value is None else value


models.Field.convert_to_read = _field_convert_to_read


def _field_convert_to_write(self, value, record):
    """≙ ``Field.convert_to_write`` (``:1065``) — de cualquier formato al de
    ``write``, encadenando los tres anteriores en ese orden."""
    cache_value = self.convert_to_cache(value, record, validate=False)
    record_value = self.convert_to_record(cache_value, record)
    return self.convert_to_read(record_value, record)


models.Field.convert_to_write = _field_convert_to_write


def _field_convert_to_export(self, value, record):
    """≙ ``Field.convert_to_export`` (``:1073``) — al formato de exportación.

    Todo lo falso sale como cadena vacía, no como ``False``: el destino es una
    celda de CSV o de hoja de cálculo, donde ``False`` se leería como el texto
    ``False``.
    """
    if not value:
        return ''
    return value


models.Field.convert_to_export = _field_convert_to_export


def _field_convert_to_display_name(self, value, record):
    """≙ ``Field.convert_to_display_name`` (``:1080``) — el valor como
    etiqueta. ``str(value) if value else False``.

    **Era sólo una función de módulo** (:func:`convert_to_display_name`, arriba
    en este archivo) con despacho por ``isinstance``. La fuente lo declara
    método de la clase del campo y sus cinco sobrecargas son métodos de su
    clase; dos de ellas —las temporales— ya se adjuntaban así
    (``fields_temporal.py:410`` y ``:423``), así que la base y las relacionales
    eran las que faltaban. La función se conserva y **delega**: sigue siendo la
    puerta para una relación inversa de Django, que no es un ``Field`` y no
    puede recibir el método (tarea **#347**).
    """
    return str(value) if value else False


models.Field.convert_to_display_name = _field_convert_to_display_name


# ═══════════════════════════════════════════════════════════════════════════
# El campo relacionado y la columna — ≙ ``odoo19c: :774-792``
# ═══════════════════════════════════════════════════════════════════════════

#: ≙ los cinco ``_related_*`` (``:774-778``). Publican, con el mismo convenio
#: de prefijo que los ``_description_*``, qué atributo hereda un campo
#: ``related=`` de aquél al que apunta. Los lee ``related_attrs``.
for _key, _source_attribute in (
        ('comodel_name', 'comodel_name'),
        ('string', 'string'),
        ('help', 'help'),
        ('groups', 'groups'),
        ('aggregator', 'aggregator'),
):
    setattr(models.Field, f'_related_{_key}', property(attrgetter(_source_attribute)))


@property
def _field_column_type(self):
    """≙ ``Field.column_type`` (``:781``) — «return the actual column type for
    this field, if stored as a column».

    La rama de la fuente se conserva verbatim: un campo dependiente de empresa
    o traducible guarda un mapa, no un escalar, así que su columna es
    ``jsonb`` sea cual sea su tipo declarado. El resto devuelve su
    ``_column_type``.

    Allá es ``functools.cached_property``; aquí es ``property`` sin caché
    porque ``_column_type`` es un atributo de clase que ninguna instancia
    reescribe —medición 4 del censo: **1** asignación en todo el árbol, la de
    ``fields_temporal._attach_base_date``, que corre al declarar la clase—.
    Cachear un valor que no cambia no compra nada y añade una entrada por
    instancia.
    """
    if self.company_dependent or self.translate:
        return ('jsonb', 'jsonb')
    return self._column_type


models.Field.column_type = _field_column_type

#: ``column_type`` tambien en el campo sin columna, por el mismo motivo que
#: ``_description_searchable``: en la fuente **no hay dos clases**, asi que un
#: ``store=False`` responde a ``column_type`` como cualquier otro campo. El
#: bucle de ``_FIELD_CLASS_ATTRIBUTES`` ya le puso ``_column_type = None``, que
#: es lo que el cuerpo lee; lo que faltaba era el lector publico.
#:
#: Lo destapo ``Registry.check_indexes`` (tarea #342), que recorre
#: ``model._fields.values()`` y filtra por ``field.column_type and field.store``
#: —``odoo19c: odoo/orm/registry.py:814`` verbatim—. Sin esta linea el recorrido
#: reventaba en el primer campo sin columna del modelo.
#: Se adjunta **el objeto ya decorado**, no ``property(_field_column_type)``:
#: la funcion de arriba lleva su propio ``@property``, asi que envolverla otra
#: vez daba una property cuyo ``fget`` es otra property — y leerla reventaba
#: con ``TypeError: 'property' object is not callable``. Ver :ref:`h-api-1062`.
NonStored.column_type = _field_column_type


@property
def _field_column_order(self):
    """≙ ``Field.column_order`` (``:1090``) — *"prescribed column order in
    table"*. ``0`` si el campo no tiene columna; si la tiene, lo que la tabla
    de la fuente diga de su tipo.

    Ordena las columnas al crear la tabla para minimizar el relleno de
    alineación de la fila: PostgreSQL alinea cada valor a su frontera natural,
    así que un ``bool`` entre dos ``int8`` desperdicia siete bytes por fila.
    La tabla vive en ``odoo19c: odoo/tools/sql.py:261`` y aquí la porta
    :func:`~tools.sql.sql_order_by_type`, que resuelve el tipo desconocido al
    mismo 16 de la fuente en vez de reventar con ``KeyError``.

    **Sitio:** la fuente lo declara abriendo su sección «Update database
    schema»; aquí va junto a ``column_type``, que es de quien depende y que en
    este árbol se declara en esta sección. Un lector que busque «cómo se
    resuelve la columna de un campo» encuentra los dos juntos.
    """
    return 0 if self.column_type is None else sql_order_by_type(self.column_type[0])


models.Field.column_order = _field_column_order

#: ``column_order`` también en el campo sin columna, por la misma razón que
#: ``column_type`` una línea más arriba: en la fuente no hay dos clases, así
#: que un ``store=False`` responde a ``column_order`` como cualquier otro
#: campo — con el ``0`` que su propio cuerpo devuelve al ver ``column_type``
#: en ``None``.
NonStored.column_order = _field_column_order

#: ``concrete`` es el nombre de Django para lo mismo que la fuente llama tener
#: columna, y la equivalencia ya esta declarada arriba: *"``store``/
#: ``column_type`` alla, ``concrete``/``column`` aqui"*. Un ``NonStored`` no la
#: tiene, y decirlo permite que un consumidor filtre con el vocabulario del
#: stack sin preguntar con ``getattr`` — que taparia por igual un campo sin
#: columna y un atributo mal escrito.
NonStored.concrete = False


class _ComputedUnlessAssigned:
    """Un valor derivado que la instancia puede pisar — descriptor NO de datos.

    Una ``property`` es descriptor **de datos**: define ``__set__``, así que
    gana sobre el ``__dict__`` de la instancia y una asignación revienta con
    ``property of X has no setter``. Un descriptor que declara sólo ``__get__``
    es **no** de datos: Python consulta primero el ``__dict__``, de modo que
    quien asigne el atributo gana y quien no, obtiene el valor derivado.

    Es el mecanismo exacto que el porte de ``base_field`` necesita, y la razón
    está medida, no supuesta: ``ArrayField.__init__`` **asigna**
    ``self.base_field`` (``django/contrib/postgres/fields/array.py:27``) con
    otro significado —el campo de los elementos del arreglo—, y ``ArrayField``
    hereda de ``models.Field``. Instalarlo como ``property`` aborta el
    arranque de Django entero.
    """

    def __init__(self, function):
        self.function = function
        self.__doc__ = function.__doc__

    def __set_name__(self, owner, name):
        self.attribute_name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return self.function(instance)


def _field_base_field(self):
    """≙ ``Field.base_field`` (``:786``) — «return the base field of an
    inherited field, or ``self``». Verbatim, recursivo por
    ``inherited_field``.
    """
    inherited = self.inherited_field
    return inherited.base_field if inherited is not None else self


#: NO es ``property``: ver :class:`_ComputedUnlessAssigned`. La forma la fija
#: la medición 4 del censo, con la raíz de Django ya ensanchada al paquete
#: entero — con la raíz estrecha publicaba 0 asignaciones y el porte reventó.
models.Field.base_field = _ComputedUnlessAssigned(_field_base_field)


# ═══════════════════════════════════════════════════════════════════════════
# El campo relacionado — ≙ ``odoo19c: :557-772``
# ═══════════════════════════════════════════════════════════════════════════
#
# ``related='partner_id.country_id.name'`` declara un campo cuyo valor no vive
# en su propia fila: se lee recorriendo una cadena punteada hasta el campo del
# extremo. La fuente lo resuelve dándole al campo un ``compute`` y un
# ``inverse`` propios, que son estos métodos.
#
# **Qué desbloqueó este porte, y por qué se hizo en este orden.** El recorrido
# escribe ``record[self.name] = ...`` y lee ``record[name]``: sin el acceso por
# clave (``orm/models.py``, ``api@35012013``) sería código que no puede correr.
# Y ``setup_related`` recorre ``model._fields[name]`` por una cadena que puede
# atravesar un ``One2many``, que no es concreto: con el mapa filtrado por
# ``concrete`` esa cadena no se podía recorrer (``api@b7856a6b``, tarea #215).
# Los dos son primitivas, y las dos se construyeron antes que este bloque.


def _field_prepare_setup(self):
    """≙ ``Field.prepare_setup`` (``:523``) — verbatim."""
    self._setup_done = False


models.Field.prepare_setup = _field_prepare_setup


def _field_setup_nonrelated(self, model):
    """≙ ``Field.setup_nonrelated`` (``:557``) — «determine the dependencies
    and inverse field(s)».

    Verbatim: la fuente no hace nada aquí. Es el gancho que sus subclases
    relacionales sobreescriben, y se porta con su cuerpo vacío porque el
    símbolo ES el contrato — quitarlo obligaría a cada subclase a saber si su
    base lo declara.
    """


models.Field.setup_nonrelated = _field_setup_nonrelated


def _first_record(corecord):
    """El primer registro de un eslabón, o el eslabón vacío.

    ≙ ``next(iter(corecord), corecord)`` de ``traverse_related`` (``:670``) y
    ``_compute_related`` (``:692``): al atravesar una relación de varios se
    toma el primero, y si no hay ninguno se conserva el contenedor vacío.

    **Divergencia de mecanismo, medida:** allá ``record[name]`` sobre un
    ``Many2one`` devuelve un recordset —iterable, de cero o un elemento—.
    Aquí lo devuelve la ``ForeignKey`` de Django: la **fila** cuando hay una,
    ``None`` cuando la columna es ``NULL``. Una fila corriente de Django no es
    iterable (``TypeError`` en ``iter``), y un ``None`` tampoco; en los dos
    casos el eslabón YA es «el primero o el vacío», que es lo que la fuente
    obtiene con el ``next``. Un recordset nuestro (``orm.models.BaseModel``)
    sí itera, y para él el ``next`` es el de la fuente.
    """
    try:
        return next(iter(corecord), corecord)
    except TypeError:
        return corecord


def _end_of_chain(value, related_field):
    """Lee el último campo de la cadena sobre el eslabón final.

    ≙ ``value[self.related_field.name]`` (``:696``). Allá un eslabón vacío es
    un recordset vacío y leerle un campo devuelve el valor falso del campo
    (``Field.falsy_value``). Aquí el eslabón vacío es ``None`` —lo que la FK
    devuelve— y leerle con ``[]`` sería ``TypeError``: se traduce al mismo
    valor falso que la fuente produce.
    """
    if value is None:
        return getattr(related_field, 'falsy_value', None)
    return value[related_field.name]


def _field_traverse_related(self, record):
    """≙ ``Field.traverse_related`` (``:666``) — «traverse the fields of the
    related field ``self`` except for the last one, and return it as a pair
    ``(last_record, last_field)``».

    Verbatim, incluido el ``next(iter(corecord), corecord)``: al atravesar una
    relación de varios se toma el primero, y si no hay ninguno se conserva el
    contenedor vacío para que el llamador distinga «no hay» de «no se
    recorrió».
    """
    for name in self.related.split('.')[:-1]:
        corecord = record[name]
        record = _first_record(corecord)
    return record, self.related_field


models.Field.traverse_related = _field_traverse_related


def _field_process_related(self, value, env):
    """≙ ``Field._process_related`` (``:720``) — «no transformation by default,
    but allows override».

    Se porta aunque no transforme nada: es el punto de extensión que las
    subclases usan, y el docstring de la fuente lo dice de sí mismo.
    """
    return value


models.Field._process_related = _field_process_related


def _field_compute_related(self, records):
    """≙ ``Field._compute_related`` (``:675``) — «compute the related field
    ``self`` on ``records``».

    **El orden del recorrido es el contrato, no un detalle.** La fuente
    atraviesa TODOS los registros en un campo antes de pasar al siguiente
    campo, no cada registro en todos sus campos, y dedica veinte líneas de
    comentario a explicar por qué: recorrer campo a campo deja que la
    prelectura resuelva el campo para todo el lote de una vez, y recorrer
    registro a registro lo pide de uno en uno. Su comentario lo llama *«a
    major impact on performance»*.

    Se conserva ese orden aunque aquí la prelectura la haga
    ``select_related``/``prefetch_related`` de Django y no el ORM: el orden es
    lo que la deja funcionar, y invertirlo la anularía en silencio — el N+1
    no rompe nada, sólo cuesta.
    """
    records = as_record_list(records)
    values = list(records)
    for name in self.related.split('.')[:-1]:
        values = [_first_record(element[name]) for element in values]
    for record, value in zip(records, values):
        record[self.name] = self._process_related(
            _end_of_chain(value, self.related_field), get_environment())


models.Field._compute_related = _field_compute_related


def _field_inverse_related(self, records):
    """≙ ``Field._inverse_related`` (``:724``) — «inverse the related field
    ``self`` on ``records``».

    La primera línea guarda los valores antes de tocar nada, y la fuente
    explica por qué en su comentario: *«store record values, otherwise they
    may be lost by cache invalidation»*. Escribir en el extremo de la cadena
    invalida la caché del origen, así que leer después de escribir devolvería
    otra cosa.

    La guarda ``bool(target.id) == bool(record.id)`` también es verbatim: sólo
    se propaga entre dos registros que sean ambos reales o ambos nuevos. Un
    registro sin guardar no puede escribir en uno guardado.
    """
    record_value = {record: record[self.name] for record in records}
    for record in records:
        target, field = self.traverse_related(record)
        if target and bool(target.id) == bool(record.id):
            target[field.name] = record_value[record]


models.Field._inverse_related = _field_inverse_related


# ═══════════════════════════════════════════════════════════════════════════
# ``related=`` — el campo que proyecta el valor del extremo de una cadena
# ═══════════════════════════════════════════════════════════════════════════
#
# ≙ ``Field.setup_related`` (``odoo19c: :604-660``) y ``Field._search_related``
# (``:735-772``), más las cinco properties ``_related_*`` (``:774-778``).
#
# **Por qué se construye y no se declina.** Sobre los 120 addons que este
# árbol porta la referencia declara centenares de campos ``related=``, y la
# inmensa mayoría **sin ``store``**. No es un puñado de casos aislados — es un
# mecanismo. Dos bloques de prosa de este árbol lo declinaban dando como razón
# que un ``related`` es «una copia que puede divergir», y eso describe
# ``store=True``, que casi ninguno lleva.
#
# El reparto **no se transcribe aquí**: crece con la referencia, y una cifra
# copiada a prosa es la segunda fuente de verdad que
# ``calibration-verified-numbers.md`` prohíbe. Lo publica
# ``python3 scripts/census_related_fields.py``; la forma se ejerce en
# ``tests/unit/orm/test_related_shape_in_the_reference.py``.
#
# **Qué diverge, y es de mecanismo.** El ``setup_related`` de la fuente usa su
# registro por base (``model.pool``, ``field._setup_done`` + ``field.setup()``,
# ``field_setup_dependents``) para asegurar que cada eslabón esté listo antes
# de recorrerlo. Aquí quien liga los campos es Django, al construir la clase:
# cuando este código corre, la cadena ya está resuelta. Por eso el recorrido es
# directo y no hay fase de espera que replicar. Los ``_extra_keys__`` y
# ``_modules`` de ``:650-663`` son del cargador de módulos de la fuente, que
# este árbol no tiene: su desenlace es divergencia de mecanismo declarada.


def walk_related_chain(field, model):
    """Los campos que ``field.related`` atraviesa, de origen a destino.

    ≙ el recorrido de ``setup_related`` (``:608-617``), que allá lee
    ``model.pool[model_name]._fields[name]``.

    **La referencia no declara este símbolo**: inlinea el mismo recorrido dos
    veces, en ``setup_related`` (``:608-617``) y en ``_search_related``
    (``:757-762``). Aquí es uno solo, y **público** porque
    :mod:`orm.domains` lo importa — no hay contrato de visibilidad de la
    fuente que preservar, y un ``_nombre`` importado entre módulos sería el
    defecto que PEP 8 nombra.

    **Divergencia de mecanismo, medida:** allá ``_fields`` es un atributo de la
    clase de registro, y este recorrido corre sobre la **clase** — Django liga
    los campos al construirla, así que no hay fase de espera que replicar. El
    registro se consulta con :func:`~orm.utils.model_field_registry`, que es el
    cuerpo que ``BaseModel._fields`` invoca: **el mismo** mapa, alcanzado desde
    la clase.

    > **Corregido (TASK-API-0417).** Este recorrido construía su propio mapa con
    > ``{f.name: f for f in current._meta.get_fields()}``. La primera redacción
    > de esta nota decía que ese mapa era «estrictamente más estrecho porque un
    > campo sin columna se contribuye con ``private_only=True`` y no aparece
    > ahí», y **eso es falso**: medido sobre ``TestOrmCategory``,
    > ``_meta.private_fields`` da ``['depth', 'root_categ', 'display_name',
    > 'dummy']`` y los cuatro salen en ``get_fields()`` con ``hidden=False``.
    > ``Options.get_fields()`` **sí** devuelve los campos privados.
    >
    > Lo que el mapa propio no alcanzaba es la otra población que
    > :func:`~orm.utils.model_field_registry` une: los ``NonStored`` que viven
    > en el ``vars()`` de una clase del MRO y que **ningún** ``_meta`` ve,
    > porque no son campos de Django. Mientras las fachadas enrutaban, un
    > ``related=`` devolvía justo uno de ésos. El cambio se conserva por esa
    > razón —y caduca con TASK-API-0418, que retira ``NonStored`` como clase—;
    > la ceguera de :ref:`h-api-1025` **no** tiene aquí un tercer sitio.

    Lanza ``KeyError`` nombrando el eslabón que falta, como la fuente
    (``:611-615``).
    """
    field_seq, current = [], model
    for name in field.related.split('.'):
        link = model_field_registry(current).get(name)
        if link is None:
            raise KeyError(
                f'El campo {name} de la definición related de {field.name} '
                f'no existe en {current.__name__}.')
        field_seq.append(link)
        current = getattr(link, 'related_model', None) or current
    return field_seq


def _field_setup_related(self, model):
    """≙ ``Field.setup_related`` (``:604-660``) — «setup the attributes of a
    related field».

    Deja instaladas las tres funciones que hacen del campo una proyección:
    ``compute`` para leerlo, ``inverse`` para escribirlo, y ``search`` para
    **buscarlo** — que es la que se perdía al navegar la cadena por la FK a
    mano.
    """
    if not isinstance(self.related, str):
        raise TypeError(f'related debe ser una ruta punteada, no {self.related!r}')

    field_seq = walk_related_chain(self, model)

    #: ``:622-624`` — el related y su destino son del mismo tipo, o la
    #: proyección miente. Aquí el tipo lo publica la ``property`` ``type``
    #: (``:1327``), que despacha por conducta y no por clase: un ``CharField``
    #: con ``choices`` es ``selection`` y sin ellas ``char``, distinción que
    #: la clase de Django no expresa por sí sola.
    if self.type != field_seq[-1].type:
        raise TypeError(
            f'El tipo del campo related {self.name} ({self.type}) no coincide '
            f'con el de su destino {field_seq[-1].name} '
            f'({field_seq[-1].type}).')

    self.related_field = field_seq[-1]

    self.compute = self._compute_related
    #: ``:632`` — sin inverso si el campo o su destino son de sólo lectura.
    #: ``inherited`` y ``readonly`` se leen directos, sin ``getattr`` con
    #: defecto: los instala :data:`_FIELD_CLASS_ATTRIBUTES` sobre
    #: ``models.Field``, así que existen siempre. Un ``getattr`` defensivo
    #: aquí escondería su desaparición en vez de delatarla.
    if self.inherited or not (self.readonly or field_seq[-1].readonly):
        self.inverse = self._inverse_related
    #: ``:634-636`` — buscable sólo si NO se guarda (con columna propia se
    #: busca por ella) y si cada eslabón lo es. El defecto de ``store`` es
    #: ``True``, así que un campo que quiera la búsqueda por cadena declara
    #: ``store=False`` — que es la forma de casi todos los ``related=`` de la
    #: referencia (reparto: ``python3 scripts/census_related_fields.py``).
    if not self.store and all(f._description_searchable for f in field_seq):
        self.search = self._search_related

    #: ``:640-641`` — un related de sólo lectura y sin inverso no puede
    #: honrar un default: nadie escribiría ese valor. La fuente avisa en vez
    #: de reventar, y aquí igual. El centinela de «sin default» en Django es
    #: ``NOT_PROVIDED``, no ``None``: un ``default=None`` declarado es un
    #: default real.
    if (self.default is not models.NOT_PROVIDED
            and self.readonly and not self.inverse):
        _logger.warning('Default redundante en %s', self.name)

    #: ``:643-647`` — copiar del destino lo que el related no declare por sí.
    for attribute, prop in self.related_attrs:
        if attribute not in self.__dict__ and prop.startswith('_related_'):
            setattr(self, attribute, getattr(field_seq[-1], prop, None))

    _retarget_related_relation(self, field_seq[-1])


#: Las ``cached_property`` de Django que derivan de ``remote_field.model``
#: (``related.py:111,790-802,891,911``). Se vacían al reapuntar la relación:
#: un valor cacheado contra el placeholder describiría al modelo equivocado.
_RELATION_CACHED_PROPERTIES = (
    'related_model', 'related_fields', 'reverse_related_fields',
    'local_related_fields', 'foreign_related_fields', 'path_infos',
    'reverse_path_infos', 'cached_col',
)


def _retarget_related_relation(field, end_of_chain):
    """Reapunta una relación ``related=`` sin ``to`` al comodelo de la cadena.

    En la fuente el comodelo de un ``Many2one(related=...)`` viene de
    ``_related_comodel_name`` (``:643-647``): la fachada no exige ``to``. En
    este stack ``ForeignKey`` exige un destino al construirse, y el que se
    declara sin él lleva un **placeholder** que Django ya resolvió y cacheó
    —``remote_field.model``, ``related_model`` y sus derivadas— antes de que
    ``setup_related`` corra. Copiar ``comodel_name`` (el bucle de arriba) deja
    el nombre bien y el descriptor mal: ``ForwardManyToOneDescriptor.__set__``
    comprueba contra ``remote_field.model._meta.concrete_model``
    (``related_descriptors.py:285``) y rechaza la fila del comodelo real.

    Medido en la sonda C del workbench ``fachadas-construyen-una-vez``:
    ``comodel_name`` copiado correcto y ``remote_model`` en el placeholder,
    con *Cannot assign ... must be a ... instance* al leer.
    """
    if not (field.is_relation and getattr(end_of_chain, 'is_relation', False)):
        return
    target = getattr(end_of_chain, 'related_model', None)
    if target is None or isinstance(target, str):
        return
    remote = getattr(field, 'remote_field', None)
    if remote is None or remote.model is target:
        return
    remote.model = target
    #: ``ForeignKey.contribute_to_related_class`` fijó el nombre de la clave
    #: del placeholder (``related.py:1196``); el del comodelo real puede
    #: diferir.
    if getattr(remote, 'field_name', None) is not None:
        remote.field_name = target._meta.pk.name
    for cached in _RELATION_CACHED_PROPERTIES:
        field.__dict__.pop(cached, None)
    remote.__dict__.pop('related_model', None)


models.Field.setup_related = _field_setup_related


#: ``_search_related`` (``:735-772``) **se instala desde**
#: :mod:`orm.domains`, no aquí, y la razón es una divergencia medida de
#: **dirección de import**, no una preferencia:
#:
#: ==================  ==========================================
#: La referencia       ``fields`` → ``domains`` (``odoo/orm/fields.py:24``),
#:                     y la vuelta sólo bajo ``TYPE_CHECKING``
#:                     (``odoo/orm/domains.py:73``).
#: Aquí                al revés — ``domains`` importa de ``fields``
#:                     ``condition_to_q``, ``falsy_value`` y
#:                     ``NEGATIVE_CONDITION_OPERATORS``.
#: ==================  ==========================================
#:
#: La inversión la causan esos tres símbolos, que la fuente **no tiene como
#: función de módulo**: allá ``falsy_value`` es un atributo del campo y el
#: compilador de hojas vive en ``Domain._to_q``. Con la dirección invertida,
#: un cuerpo que construya ``Domain`` no cabe en este archivo, y un import
#: dentro de la función está prohibido (``no-lazy-imports.md``).
#:
#: Enderezarla es la tarea **#380**, la misma que ``_NEGATIVE_LIKE_OPERATORS``
#: ya citaba: unificar los tres en un hogar compartido devuelve la dirección
#: de la fuente y trae este cuerpo a su archivo. Hasta entonces la instalación
#: cruzada es la misma vía por la que ``determine_domain`` llega a
#: ``NonStored``. :func:`_field_setup_related` lo referencia por ``self``, así
#: que el orden de instalación no importa: cuando el campo se configura, el
#: método ya está colgado.


#: ``:774-778`` — los cinco ``_related_*`` los instala el bucle de la seccion
#: «El campo relacionado y la columna», con ``property(attrgetter(...))``, que
#: es la forma literal de la fuente. Aqui vivia una SEGUNDA declaracion de los
#: cinco con lambdas defensivas, que pisaba la primera en silencio: dos fuentes
#: de verdad para un mismo simbolo, y la que ganaba no era la fiel. Retirada en
#: H-API-1094; medido antes de retirarla: los cinco atributos de origen existen
#: siempre en ``models.Field``, asi que el ``attrgetter`` no puede levantar.


def _field_setup(self, model):
    """≙ ``Field.setup`` (``:526-542``) — el despachador de las dos ramas.

    La fuente valida antes sus ``_extra_keys__`` contra
    ``_valid_field_parameter``; aquí no hay cargador de módulos que los
    aporte, así que esa mitad es divergencia de mecanismo declarada. Lo que sí
    se porta es la bifurcación, que es el contrato: un campo con ``related``
    va por un camino y el resto por el otro.
    """
    if getattr(self, '_setup_done', False):
        return
    if self.related:
        self.setup_related(model)
    else:
        self.setup_nonrelated(model)
    # ``setup_related`` acaba de declarar ``compute``
    # (``odoo19c: odoo/orm/fields.py:632``, ``self.compute = self._compute_related``).
    # En la fuente el campo ES su propio descriptor, así que ese ``compute``
    # rige desde el instante en que se asigna; aquí el descriptor se eligió en
    # ``contribute_to_class``, antes de que ``compute`` existiera, y se vuelve a
    # elegir con el campo ya armado.
    _install_field_descriptor(self, model)
    self._setup_done = True


models.Field.setup = _field_setup


#: La resolucion vive en ``orm/utils.py`` desde la tarea #324: la comparte con
#: ``Environment._recompute_all`` y ``flush_all``, que no pueden importar este
#: archivo porque este importa ``orm.environments``. El alias conserva el nombre
#: con que lo citan los consumidores de aqui.
_model_of = model_of_field


def _comodel_of(field, registry_module):
    """El modelo al que ``field`` lleva, o ``None`` si no lleva a ninguno.

    ≙ el ``model_name = field.comodel_name`` con que la fuente avanza el
    recorrido (``:865``). Django ya publica la clase en ``related_model``, asi
    que no hace falta pasar por el nombre; ``comodel_name`` queda de respaldo
    para un campo portado que lo declare y no sea relacion de Django.
    """
    related = getattr(field, 'related_model', None)
    if related is not None:
        return related
    comodel = getattr(field, 'comodel_name', None)
    return registry_module.MODELS_BY_NAME.get(comodel) if comodel else None


def _is_one_to_many(field):
    """Si ``field`` es el lado «muchos» de una relacion — ≙ ``type ==
    'one2many'``.

    Se pregunta por ``one_to_many`` de Django, que es donde este stack lo
    declara, **y** por el ``type`` que :class:`~orm.fields_relational.One2many`
    declara (``fields_relational.py:179``): el primero cubre el reverso de una
    FK, el segundo el campo portado que se declara explicitamente.
    """
    return bool(getattr(field, 'one_to_many', False)
                or getattr(field, 'type', None) == 'one2many')


def _is_many_to_one(field):
    """Si ``field`` lleva a UN registro — ≙ ``type == 'many2one'``.

    Mismo criterio doble que :func:`_is_one_to_many`, por la misma razon.
    """
    return bool(getattr(field, 'many_to_one', False)
                or getattr(field, 'type', None) == 'many2one')


def _field_resolve_depends(self, registry_module):
    """≙ ``Field.resolve_depends`` (``:807-865``) — «return the dependencies of
    ``self`` as a collection of field tuples».

    Cada dependencia declarada es un nombre punteado; esto la resuelve a las
    tuplas de campos que la recorren, para que quien invalide sepa que tocar.

    El parametro se llama ``registry_module`` y no ``registry`` porque aqui el
    registro es un **modulo** (``orm.registry``) y no la instancia por base de
    la fuente — la divergencia esta declarada en la cabecera de ese archivo.

    > **Completado (tarea #273, capa B).** La version anterior emitia **solo la
    > tupla completa**, en el ``else`` del ``for``. La fuente emite **cada
    > prefijo** dentro del bucle, y ese es el contrato que el registro de
    > disparadores consume: sin los prefijos, un ``@api.depends('owner.label')``
    > nunca registra a ``owner`` como clave, asi que
    > ``is_modifying_relations(owner)`` responde ``False`` sobre un campo que
    > **si** cambia que filas dependen de el. Con la tupla completa como unica
    > salida el mecanismo entero queda medio construido y su verde no lo
    > delata.
    >
    > Se portan ademas los cinco comportamientos que faltaban y que la fuente
    > declara en el mismo cuerpo: el corte por transitorio, el aviso de
    > recursion, el aviso de precomputo con su corte en ``many2one``, el aviso
    > de no-buscable, y la emision extra por el inverso de un ``one2many``.
    > Esta ultima **no se podia portar antes**: necesita ``field_inverses``,
    > que la capa B es la que construye.

    Cuatro divergencias de mecanismo, todas declaradas:

    - el mapa de campos del modelo lo da :func:`~orm.utils.model_field_registry`
      —el cuerpo de ``BaseModel._fields``— y no ``_meta.get_field``, que es
      ciego al campo sin columna (:ref:`h-api-1025`);
    - ``_transient`` se lee con ``getattr``: aqui lo declara
      ``orm.models_transient`` sobre los modelos que lo son, y los demas no
      llevan el atributo;
    - ``one2many`` y ``many2one`` se reconocen por los marcadores de Django
      (``one_to_many`` / ``many_to_one``) ademas del ``type`` portado;
    - el comodelo sale de ``related_model``, no del nombre.
    """
    model_zero = _model_of(self, registry_module)
    if model_zero is None:
        return
    zero_transient = bool(getattr(model_zero, '_transient', False))

    for dotnames in registry_module.field_depends[self]:
        field_sequence = []
        current = model_zero
        check_precompute = bool(getattr(self, 'precompute', False))

        for index, fname in enumerate(dotnames.split('.')):
            if current is None:
                break
            #: Tocar un campo de un modelo normal no debe disparar el
            #: recalculo de un campo de un modelo transitorio — ≙ ``:820-824``.
            if zero_transient and not getattr(current, '_transient', False):
                break

            registry = model_field_registry(current)
            try:
                field = registry[fname]
            except KeyError:
                raise ValueError(
                    f"Wrong @depends on '{self.compute}' (compute method of "
                    f"field {self}). Dependency field '{fname}' not found in "
                    f"model {current.__name__}."
                ) from None

            if field is self and index and not self.recursive:
                self.recursive = True
                warnings.warn(
                    f'Field {self} should be declared with recursive=True',
                    stacklevel=1)

            #: Un campo precomputado puede depender de uno que no lo sea, pero
            #: solo si se llega a el atravesando al menos un ``many2one``
            #: — ≙ ``:834-838``.
            #: Los tres atributos se leen con ``getattr``: el objeto de
            #: relacion inversa de Django (``ForeignObjectRel``) **no** es un
            #: ``models.Field``, asi que el bucle de
            #: :data:`_FIELD_CLASS_ATTRIBUTES` no lo alcanza. Un lado inverso
            #: no tiene columna propia ni computo, que es justo el default.
            if (check_precompute and getattr(field, 'store', False)
                    and getattr(field, 'compute', None)
                    and not getattr(field, 'precompute', False)):
                warnings.warn(
                    f'Field {self} cannot be precomputed as it depends on '
                    f'non-precomputed field {field}', stacklevel=1)
                self.precompute = False

            #: ``True`` por defecto por la misma razon: un lado inverso de
            #: Django SI es atravesable en una consulta (``probes__source``),
            #: que es lo que este aviso mide — «hay por donde llegar a las
            #: filas que recalcular».
            if field_sequence and not getattr(
                    field_sequence[-1], '_description_searchable', True):
                warnings.warn(
                    f'Field {field_sequence[-1]!r} in dependency of {self} '
                    f'should be searchable. This is necessary to determine '
                    f'which records to recompute when {field} is modified. '
                    f'You should either make the field searchable, or simplify '
                    f'the field dependency.', stacklevel=1)

            field_sequence.append(field)

            #: Un campo no se dispara a si mismo: un ``one2many`` con dominio
            #: sobre ``foo`` declara ``line_ids.foo``, y el primer paso de esa
            #: ruta es el propio campo — ≙ ``:853-856``.
            if not (field is self and not index):
                yield tuple(field_sequence)

            if _is_one_to_many(field):
                for inverse in registry_module.field_inverses[field]:
                    yield tuple(field_sequence) + (inverse,)

            if check_precompute and _is_many_to_one(field):
                check_precompute = False

            current = _comodel_of(field, registry_module)


models.Field.resolve_depends = _field_resolve_depends


def get_depends(self, model):
    """Las dependencias del campo y las de contexto — ≙ ``Field.get_depends``
    (``odoo19c: odoo/orm/fields.py:561-598``), *"Return the field's
    dependencies and cache dependencies"*.

    Es el **productor** del par que :func:`_field_resolve_depends` consume: aquel
    expande cada nombre punteado a las tuplas de campos que lo recorren, y este
    decide **cuales son esos nombres** a partir de lo que la clase declara. Sin
    el, el mapa ``registry.field_depends`` se derivaba del atributo ``_depends``
    en crudo y dos de las tres ramas de la fuente no existian: la de ``related``
    y la del recorrido del MRO sobre la funcion de calculo.

    Las tres ramas, en el orden en que la fuente las evalua:

    1. ``_depends`` explicito — *"the parameter 'depends' has priority over
       'depends' on compute"* (``:563``).
    2. ``related`` — la dependencia **es** la ruta; el contexto sale de recorrer
       la cadena punteada eslabon por eslabon, acumulando el de cada campo.
    3. ``compute`` — el ``_depends`` de **todas** las funciones sobreescritas
       (``resolve_mro``), no solo el de la mas derivada.

    Dos divergencias de mecanismo, ambas declaradas:

    - el modelo de cada eslabon lo da :func:`_comodel_of` —que lee el
      ``related_model`` de Django y cae a ``comodel_name``— en vez del
      ``model.env[nombre]`` de la fuente, porque aqui el registro es un modulo;
    - el mapa de campos lo da :func:`~orm.utils.model_field_registry`, el cuerpo
      de ``BaseModel._fields``, y no ``model._fields`` directo.

    :param model: la clase de modelo que declara el campo.
    :returns: el par ``(depends, depends_context)``.
    """
    if self._depends is not None:
        # ``:563-565`` — lo declarado en el campo gana sobre lo del computo.
        return self._depends, self._depends_context or ()

    if self.related:
        if self._depends_context is not None:
            depends_context = self._depends_context
        else:
            depends_context = []
            field_model = model
            for field_name in self.related.split('.'):
                if field_model is None:
                    raise ValueError(
                        f'{model.__name__}.{self.name}: la ruta related '
                        f'{self.related!r} atraviesa un campo que no lleva a '
                        f'ningun modelo')
                registry_of_model = model_field_registry(field_model)
                if field_name not in registry_of_model:
                    # **El eslabón ausente se NOMBRA.** Antes salía como un
                    # ``KeyError`` pelado con sólo el segmento —diez mil veces
                    # ``KeyError: 'company_id'``— y no decía ni qué campo
                    # declara la cadena ni sobre qué modelo se rompió. La
                    # fuente no necesita el mensaje porque su ``_fields``
                    # siempre tiene el nombre; aquí la cadena viaja portada
                    # verbatim y el eslabón puede faltar de verdad.
                    raise ValueError(
                        f'{model.__name__}.{self.name}: la ruta related '
                        f'{self.related!r} pide {field_name!r} sobre '
                        f'{field_model.__name__}, que no lo declara')
                field = registry_of_model[field_name]
                depends_context.extend(field.get_depends(field_model)[1])
                field_model = _comodel_of(field, orm_registry)
            depends_context = tuple(unique(depends_context))
        return [self.related], depends_context

    if not self.compute:
        return (), self._depends_context or ()

    # ``:588-591`` — el ``compute`` declarado por nombre recorre el MRO; el que
    # ya es funcion se usa tal cual.
    if isinstance(self.compute, str):
        funcs = resolve_mro(model, self.compute, callable)
    else:
        funcs = [self.compute]

    depends = []
    depends_context = list(self._depends_context or ())
    for func in funcs:
        # DIVERGENCIA DE STACK: ``resolve_mro`` lee el ``__dict__`` de cada
        # clase en crudo, asi que un computo declarado ``@staticmethod`` o
        # ``@classmethod`` llega aqui como el DESCRIPTOR, no como la funcion —
        # y el marcador que ``@api.depends`` puso vive en la funcion. La fuente
        # no lo necesita porque sus computos son funciones llanas; aqui se
        # desenvuelve, que es lo que ``getattr(model, compute)`` hacia gratis.
        func = getattr(func, '__func__', func)
        deps = getattr(func, '_depends', ())
        depends.extend(deps(model) if callable(deps) else deps)
        depends_context.extend(getattr(func, '_depends_context', ()))

    return depends, depends_context


models.Field.get_depends = get_depends


# ═══════════════════════════════════════════════════════════════════════════
# ``determine_domain`` — la condición que un campo traduce por sí mismo
# ═══════════════════════════════════════════════════════════════════════════
#
# ≙ ``Field.determine_domain`` (``odoo19c: odoo/orm/fields.py:1926-1928``),
# cuyo cuerpo entero es ``determine(self.search, records, operator, value)``.
#
# Es la puerta del camino ``search=``: un campo que declara ``search`` no se
# compila a SQL, porque puede no tener columna; en su lugar **devuelve un
# dominio** que sustituye a la condición y se compone con el resto igual que
# cualquier otro. Un ``QuerySet`` no puede hacerlo — no se puede meter dentro
# de un ``any`` ni negar sin materializar—, y ésa es la razón por la que la
# forma de retorno importa y no es un detalle de estilo.
#
# Se instala sobre DOS clases, y la duplicación es del stack, no del contrato:
#
# - ``models.Field`` — los campos con columna, que hoy no declaran ``search``
#   pero heredan el protocolo para cuando lo declaren.
# - ``NonStored`` — los campos sin columna, que son quienes lo necesitan hoy
#   (``display_name`` es el primero). No es un ``models.Field``, así que
#   heredar no lo alcanza.
#
# La instalación va aquí y no en ``fields_nonstored`` porque este módulo lo
# importa por la vía de ``fields_numeric``: el import inverso sería un ciclo.
# Es la misma vía por la que ``type`` y ``relational`` llegan a
# ``models.Field``.


def determine_inverse(field, records):
    """Ejecuta el inverso declarado del campo — ≙ ``Field.determine_inverse``.

    Docstring de la fuente, verbatim: *"Given the value of ``self`` on
    ``records``, inverse the computation."* Su cuerpo entero es
    ``determine(self.inverse, records)`` (``odoo19c: odoo/orm/fields.py:1921``),
    y aqui es el mismo: el despacho ya lo resuelve :func:`determine`, que sabe
    llamar tanto una cadena como un invocable.

    Se declara CONSTRUYE por el criterio de las dos categorias: no hay simbolo
    hecho —Django no conoce la nocion de un metodo inverso sobre un campo— pero
    las primitivas estan y no hace falta nada de fuera.

    **Sin guarda, a proposito.** La fuente tampoco la tiene: sus dos llamadas
    —``write`` (``odoo19c: odoo/orm/models.py:4493``) y el descriptor— agrupan
    antes por ``field.inverse``, asi que solo llega aqui un campo que lo
    declara. Un campo sin inverso levanta ``TypeError`` desde
    :func:`determine`, que es exactamente lo que la fuente hace y lo que
    distingue *"no lo declara"* de *"lo declara y no corrio"*.
    """
    return determine(field.inverse, records)


def determine_domain(field, records, operator, value):
    """El dominio que sustituye a una condición sobre ``field``.

    Devuelve ``NotImplemented`` cuando el campo no declara ``search``: es la
    misma señal con que la fuente dice *"este operador no lo soporto"* y deja
    al despachador probar sus respaldos, en vez de un error que cortaría la
    escalera antes del primer peldaño.
    """
    search = getattr(field, 'search', None)
    if search is None:
        return NotImplemented
    return determine(search, records, operator, value)


models.Field.determine_domain = determine_domain


# ═══════════════════════════════════════════════════════════════════════════
# El ciclo de vida del campo — leer, crear, escribir, prelectar
# ═══════════════════════════════════════════════════════════════════════════
#
# Los cinco de esta sección más ``get_company_dependent_fallback`` son el
# bloque que la referencia declara sobre ``Field`` y que este puerto no tenía.
# Los seis son CONSTRUYE por el criterio de las dos categorías: Django no
# concibe un campo que sepa leerse, escribirse y prelectar por sí mismo —su
# ``Field`` describe una columna y delega en el ``QuerySet``—, pero ninguna
# pieza viene de fuera: las primitivas (``convert_to_cache``,
# ``_filter_not_equal``, ``_update_cache``, ``_get_cache``, ``expand_ids``,
# ``PREFETCH_MAX``, ``determine``) ya están todas en el árbol.


def _field_read(self, records):
    """Lee el valor del campo sobre ``records`` y lo deja en caché.

    ≙ ``Field.read`` (``odoo19c: odoo/orm/fields.py:1486-1489``). Docstring de
    la fuente, verbatim: *"Read the value of ``self`` on ``records``, and store
    it in cache."*

    El cuerpo de la fuente **es** la guarda: un campo sin columna no sabe
    leerse y lo dice con ``NotImplementedError``, en vez de devolver ``None``
    y dejar que el consumidor lo confunda con un valor. Los subtipos que sí
    tienen forma propia de leerse la sobreescriben.
    """
    if not self.column_type:
        raise NotImplementedError("Method read() undefined on %s" % self)


def _field_write(self, records, value):
    """Escribe el valor del campo sobre ``records``.

    ≙ ``Field.write`` (``:1501-1518``). Docstring de la fuente: *"Write the
    value of ``self`` on ``records``. This method must update the cache and
    prepare database updates."*

    Los tres pasos son los de la fuente, en su orden: descartar el recálculo
    pendiente, filtrar las filas cuyo valor ya coincide, y actualizar la
    caché marcándola sucia.

    **Divergencia de mecanismo, declarada.** ``Environment.remove_to_compute``
    toma aquí ``(field, record_ids)`` —una colección de pk— mientras la fuente
    le pasa el recordset. Se traduce con :func:`~orm.utils.record_ids`, que es
    la misma traducción que toda esta familia aplica: lo descartado es lo
    mismo, cambia por dónde se nombra.

    El filtro no es una optimización: sin él, una escritura del valor que la
    fila ya tiene la marcaría sucia y forzaría un UPDATE que no cambia nada.
    Se pide en su forma de **ids** (:meth:`_filter_not_equal_ids`) y no de
    filas: allí está la razón medida de por qué el símbolo existe.
    """
    ids = record_ids(records)
    get_environment().remove_to_compute(self, ids)

    cache_value = self.convert_to_cache(value, records)
    surviving = self._filter_not_equal_ids(records, cache_value)
    if not surviving:
        return

    self._update_cache(surviving, cache_value, dirty=True)


def _field_create(self, record_values):
    """Escribe el campo sobre filas recién creadas.

    ≙ ``Field.create`` (``:1491-1499``). Docstring de la fuente: *"Write the
    value of ``self`` on the given records, which have just been created.
    :param record_values: a list of pairs ``(record, value)``, where ``value``
    is in the format of method :meth:`BaseModel.write`"*

    Sin lógica propia: delega en :func:`_field_write` par a par, igual que la
    fuente. Existe como símbolo aparte porque los subtipos que necesitan un
    camino distinto al crear —una tabla intermedia, un adjunto— lo
    sobreescriben sin tocar ``write``.
    """
    for record, value in record_values:
        self.write(record, value)


def _field_to_prefetch(self, record):
    """La ventana de filas que acompañan a ``record`` al leer este campo.

    ≙ ``Field._to_prefetch`` (``:1588-1593``). Docstring de la fuente: *"Return
    a recordset including ``record`` to prefetch the field."*

    Devuelve ``record`` y las filas de su lote de prelectura que **no** están
    ya en la caché del campo, acotadas a ``PREFETCH_MAX``. Que la fila pedida
    vaya primero es del contrato: ``expand_ids`` la emite antes que ninguna,
    así que el recorte por el tope nunca la deja fuera.
    """
    ids = expand_ids(record.pk, getattr(record, '_prefetch_ids', ()) or ())
    field_cache = self._get_cache(get_environment())
    pending = (id_ for id_ in ids if id_ not in field_cache)
    return browse(model_of(record), list(itertools.islice(pending, PREFETCH_MAX)))


def _field_determine_group_expand(self, records, values, domain):
    """El expansor de grupos declarado del campo.

    ≙ ``Field.determine_group_expand`` (``:1930-1932``), cuyo cuerpo entero es
    ``determine(self.group_expand, records, values, domain)``.

    **Sin guarda, a propósito** — igual que :func:`determine_inverse`. La
    fuente tampoco la tiene: sus llamadas agrupan antes por
    ``field.group_expand``, así que sólo llega aquí un campo que lo declara.
    Un campo sin expansor levanta ``TypeError`` desde :func:`determine`, que es
    lo que distingue *"no lo declara"* de *"lo declara y no corrió"*.
    """
    return determine(self.group_expand, records, values, domain)


def _field_get_company_dependent_fallback(self, records):
    """El respaldo de ``ir.default`` para un campo dependiente de empresa.

    ≙ ``Field.get_company_dependent_fallback`` (``:794-801``). Un campo
    dependiente de empresa vive en una columna ``jsonb`` con
    ``{empresa: valor}``; la fila sin entrada propia responde este respaldo.

    La aserción es la de la fuente y no es ceremonia: llamar a este método
    sobre un campo llano devolvería el default de otro mecanismo y lo haría
    pasar por el de empresa.

    **Divergencia de mecanismo.** La fuente encadena
    ``records.env['ir.default'].with_user(SUPERUSER_ID).with_company(...)``;
    aquí ``_get_model_defaults`` es un ``classmethod`` que recibe el modelo y
    la empresa como argumentos, así que el encadenado se traduce a la llamada
    directa. Lo consultado es lo mismo: el default de mayor prioridad para
    ``self.name`` sobre el modelo de ``records``.
    """
    assert self.company_dependent
    env = get_environment()
    company = getattr(env, 'company', None)
    defaults = orm_registry.MODELS_BY_NAME['ir.default']._get_model_defaults(
        model_of(records)._name,
        company_id=getattr(company, 'pk', None),
    )
    fallback = defaults.get(self.name)
    fallback = self.convert_to_cache(fallback, records, validate=False)
    return self.convert_to_record(fallback, records)


models.Field.read = _field_read
models.Field.write = _field_write
models.Field.create = _field_create
models.Field._to_prefetch = _field_to_prefetch
models.Field.determine_group_expand = _field_determine_group_expand
models.Field.get_company_dependent_fallback = _field_get_company_dependent_fallback
NonStored.determine_domain = determine_domain
models.Field.determine_inverse = determine_inverse
NonStored.determine_inverse = determine_inverse


def determine_compute(field, records):
    """Ejecuta el cómputo declarado del campo y devuelve lo que produce.

    Es el cuerpo EFECTIVO de la rama ``elif self.compute:`` del descriptor de
    la fuente (``odoo19c: odoo/orm/fields.py:1736-1737``, con su comentario
    *"non-stored field or new record without origin: compute"*) **para un campo
    sin columna**. Allá esa rama llama ``self.compute_value(recs)`` (``:1744``),
    que termina en ``records._compute_field_value(self)``, cuyo cuerpo entero es
    (``odoo19c: odoo/orm/models.py:4953-4959``)::

        determine(field.compute, self)

        if field.store and any(self._ids):
            ...

    Con ``store=False`` el segundo bloque no se alcanza, así que lo que queda es
    la llamada a :func:`determine` — la misma forma que :func:`determine_inverse`
    (``odoo19c: odoo/orm/fields.py:1921``).

    Se declara **CONSTRUYE** por el criterio de las dos categorías: no hay
    símbolo hecho —Django no conoce la noción de un método de cómputo sobre un
    campo— pero las primitivas están (``getattr`` y ``callable``, que es lo que
    :func:`determine` ya usa) y no hace falta ninguna dependencia de fuera.

    POR QUÉ NO SE LLAMA ``compute_value``: ese nombre ya está tomado en este
    módulo (``:4179``) por el porte de ``Field.compute_value``, que sí hace la
    ceremonia completa —desmarcar de la cola, ``protecting``, llevar al caché—
    y por tanto sólo aplica a un campo CON columna. Un :class:`NonStored` no
    tiene ni cola ni caché que tocar: llamar a aquél desde aquí ejecutaría un
    mecanismo que no le corresponde.

    DIVERGENCIA DE MECANISMO, ya declarada: el cómputo de la fuente **asigna**
    sobre el recordset y el descriptor relee el caché; aquí **devuelve**, y ese
    retorno es el canal. Es la divergencia 1 de
    :class:`~orm.models.DisplayNameMixin`, que precede a esta función y que los
    cinco modelos que declaraban su ``_compute_display_name`` ya ejercían.
    """
    return determine(field.compute, records)


#: Se instala desde AQUÍ y no desde ``fields_nonstored`` por la misma razón que
#: ``determine_domain`` y ``determine_inverse``: este módulo importa aquél
#: (``:83``), así que el import inverso sería un ciclo. Sólo sobre
#: :class:`NonStored`: el campo con columna ya tiene la ceremonia completa en
#: :func:`compute_value`, que es lo que la fuente le da.
NonStored.determine_compute = determine_compute


############################################################################
#
# Cache management methods — ≙ ``odoo19c: odoo/orm/fields.py:1520-1630``
#
# El almacén es ``Transaction.field_data``, que existía desde el porte de
# ``environments.py`` y hasta aquí no tenía **ningún** consumidor: medido,
# 0 lecturas fuera de su propio módulo. Esta sección es quien lo estrena.
#
# Veredicto por el criterio de las dos categorías:
#
# - **el stack lo trae hecho**: ``collections.deque(maxlen=0)`` para drenar
#   un ``map`` en C, ``collections.ChainMap`` para fusionar los cubos de un
#   campo con contexto, y ``defaultdict`` para el mapa por campo. Los tres
#   de ``cpython``; se llaman y ya.
# - **el stack tiene con qué construirlo**: la caché en sí. Django no tiene
#   almacén de valor por campo y por transacción —el suyo es por instancia,
#   en ``_state.fields_cache``, y muere con el objeto—, pero las primitivas
#   están y no hace falta ninguna dependencia de fuera.
#
# La adaptación de firma es UNA y se declara aquí para no repetirla en cada
# método: donde la fuente escribe ``records._ids``, aquí va
# ``record_ids(records)``. No hay recordset en este stack — ver el docstring
# de :func:`~orm.utils.record_ids` —; el resto del cuerpo es el de la fuente.
############################################################################


def _has_context_buckets(field):
    """Si el campo separa su caché por clave de contexto.

    ≙ ``self in env._field_depends_context`` de la fuente. Allá el registro
    guarda el conjunto; aquí lo responde el mismo mapa derivado que ya
    existía, ``registry.field_depends_context``.
    """
    return field in field_depends_context


def _get_cache(self, env):
    """La caché del campo: un mapa mutable de id a valor.

    ≙ ``Field._get_cache`` (``:1525``). Docstring de la fuente: *"Calling
    this function multiple times, always returns the same mapping instance
    for a given environment, unless the transaction was entirely
    invalidated."* Esa promesa sostiene el resto — quien recibe el mapa
    escribe en él y espera que la escritura se vea.
    """
    transaction = env.transaction
    memo_key = (self, env.cache_key(self) if _has_context_buckets(self) else None)
    try:
        return transaction.field_cache_memo[memo_key]
    except KeyError:
        field_cache = self._get_cache_impl(env)
        transaction.field_cache_memo[memo_key] = field_cache
        return field_cache


def _get_cache_impl(self, env):
    """≙ ``Field._get_cache_impl`` (``:1541``) — puede dar una vista del
    almacén real, según lo que el campo necesite."""
    cache = env.transaction.field_data[self]
    if _has_context_buckets(self):
        cache = cache.setdefault(env.cache_key(self), {})
    return cache


def _invalidate_cache(self, env, ids=None):
    """≙ ``Field._invalidate_cache`` (``:1550``) — invalida los ids dados, o
    todos si ``ids`` es ``None``.

    Lee ``field_data.get`` y no el corchete a propósito: sobre un
    ``defaultdict`` el corchete **crea** la entrada, y un campo que nadie ha
    tocado quedaría con un cubo vacío por el mero hecho de invalidarlo.
    """
    cache = env.transaction.field_data.get(self)
    if not cache:
        return

    caches = cache.values() if _has_context_buckets(self) else (cache,)
    for field_cache in caches:
        if ids is None:
            field_cache.clear()
            continue
        for id_ in ids:
            field_cache.pop(id_, None)


def _get_all_cache_ids(self, env):
    """Todos los ids con valor en caché, en cualquier entorno.

    ≙ ``Field._get_all_cache_ids`` (``:1564``). El ``ChainMap`` es el truco
    de la fuente para *"cheaply merge"* las claves de los cubos sin copiar
    ninguno.
    """
    cache = env.transaction.field_data[self]
    if _has_context_buckets(self):
        return collections.ChainMap(*cache.values())
    return cache


def _cache_missing_ids(self, records):
    """≙ ``Field._cache_missing_ids`` (``:1572``) — los ids sin valor en
    caché."""
    field_cache = self._get_cache(get_environment())
    return (id_ for id_ in record_ids(records) if id_ not in field_cache)


def _filter_not_equal(self, records, cache_value):
    """Las filas cuyo valor en caché falta o difiere de ``cache_value``.

    ≙ ``Field._filter_not_equal`` (``:1577``). Docstring de la fuente:
    *"Return the subset of ``records`` for which the value of ``self`` is
    either not in cache, or different from ``cache_value``."*

    El centinela hace el trabajo: ``field_cache.get(id_, SENTINEL)`` no
    distingue *"no está en caché"* de *"está y vale ``None``"* si el valor
    por omisión fuera ``None`` — y ``None`` es un valor legítimo de casi
    todos los campos. Con ``SENTINEL``, la ausencia siempre difiere.

    Divergencia de mecanismo, la misma de toda esta familia: el entorno es
    ambiental (``orm.environments.env()``) en vez de ``records.env``, los
    ids salen de :func:`~orm.utils.record_ids` en vez de ``records._ids``, y
    el conjunto de vuelta se arma con :func:`~orm.utils.browse` sobre
    :func:`~orm.utils.model_of` en vez de ``records.browse``.
    """
    return browse(model_of(records),
                  self._filter_not_equal_ids(records, cache_value))


def _filter_not_equal_ids(self, records, cache_value):
    """Los **ids** de las filas cuyo valor en caché falta o difiere.

    No tiene contraparte en la fuente, y la razón es de mecanismo: allí un
    recordset **lleva** sus ids en una tupla, así que
    ``self._filter_not_equal(...)._ids`` es gratis y su ``if not records``
    no consulta nada. Aquí :func:`~orm.utils.browse` devuelve un
    ``QuerySet`` —una consulta, no una lista— y volver a pedirle los ids
    con :func:`~orm.utils.record_ids` los lee de la base.

    Medido: sin este símbolo, ``Field.write`` sobre una fila en cómputo
    ejecuta un ``SELECT`` por escritura, y en un test unitario sin la marca
    ``django_db`` levanta *"Database access not allowed"* — 7 casos de
    ``tests/unit/orm/``. La fuente no toca la base en ese punto, así que el
    ``SELECT`` era nuestro, no suyo.

    :meth:`_filter_not_equal` conserva su contrato —devuelve el conjunto de
    filas— y se construye sobre éste; quien sólo necesita los ids los pide
    aquí y no paga la vuelta. **El invariante que liga a los dos** es que
    esto devuelve exactamente los ids de aquello:

        ``record_ids(f._filter_not_equal(r, v)) == f._filter_not_equal_ids(r, v)``

    De ahí sale la guarda por ``id_``, que no es un descarte arbitrario:
    :func:`~orm.utils.browse` no lleva una fila sin ``pk``, así que un
    ``None`` en esta tupla rompería la igualdad. Y la caché del ORM está
    **indexada por pk** —es su clave—, de modo que sembrarla con ``None``
    haría que ese valor le contestara a la siguiente fila en vuelo, que
    también tiene ``pk`` nulo. Medido: con el ``None`` dentro, el
    ``pre_save`` de un ``DateField`` leía la forma de caché de otra fila y
    ``parse_date`` la rechazaba con *fromisoformat: argument must be str*.

    La fuente no necesita la guarda porque su fila nueva lleva un
    ``NewId``, que sí es una clave de caché válida. Construir ese
    identificador virtual es la tarea **#327**; hasta entonces la fila en
    vuelo vive sólo en el almacén de instancia de Django.
    """
    field_cache = self._get_cache(get_environment())
    return tuple(
        id_ for id_ in record_ids(records)
        if id_ and field_cache.get(id_, SENTINEL) != cache_value
    )


def _insert_cache(self, records, values):
    """Rellena la caché SIN pisar lo que ya hay.

    ≙ ``Field._insert_cache`` (``:1595``). El ``setdefault`` no es un
    detalle: la fuente lo explica —*"this enables to keep the pending
    updates of records, and flush them later"*—. Una asignación borraría una
    escritura pendiente y la fila se guardaría con el valor leído de la base.

    El ``deque(maxlen=0)`` es el drenaje en C que la fuente mide un 15 % más
    rápido que el bucle equivalente; se porta igual, porque es el stack quien
    lo trae hecho.
    """
    field_cache = self._get_cache(get_environment())
    collections.deque(
        map(field_cache.setdefault, record_ids(records), values), maxlen=0)


def _is_persisted(field):
    """¿El valor de este campo sobrevive a la transacción?

    La respuesta **no** es ``column_type``: un muchos-a-muchos persiste —en su
    tabla intermedia— y no tiene columna en la fila. Con el predicado viejo el
    M2M calculado quedaba fuera del caché y de la marca de sucio, así que el
    volcado no tenía de dónde saber que había algo que escribir (#313).

    El predicado vive aquí y no repetido en sus dos consumidores por lo mismo
    que ``calibration-verified-numbers.md`` prohíbe la segunda copia de una
    cifra: dos condiciones que dicen lo mismo divergen en cuanto una se toca.
    """
    return bool(getattr(field, 'store', False)
                and (field.column_type
                     or getattr(field, 'many_to_many', False)))


def _update_cache(self, records, cache_value, dirty=False):
    """Escribe el valor en caché y, si se pide, marca el campo sucio.

    ≙ ``Field._update_cache`` (``:1609``). Docstring de la fuente: *"One can
    normally make a clean field dirty but not the other way around. Updating
    a dirty field without ``dirty=True`` is a programming error and logs an
    error."* Se porta el **registro**, no una excepción: la fuente elige no
    lanzar, y lanzar aquí cambiaría el contrato de todo escritor.
    """
    env = get_environment()
    field_cache = self._get_cache(env)
    ids = record_ids(records)
    for id_ in ids:
        field_cache[id_] = cache_value

    # ``dirty`` sólo tiene sentido para un campo PERSISTIDO — con columna, o
    # con tabla intermedia si es un muchos-a-muchos (ver :func:`_is_persisted`).
    if _is_persisted(self):
        if dirty:
            env.transaction.field_dirty[self].update(id_ for id_ in ids if id_)
        else:
            dirty_ids = env.transaction.field_dirty.get(self)
            if dirty_ids and not dirty_ids.isdisjoint(ids):
                _logger.error(
                    "Field._update_cache() updating the value on %s.%s where "
                    "dirty flag is already set",
                    records, self.name, stack_info=True,
                )


############################################################################
#
# Computation of field values — ≙ ``odoo19c: odoo/orm/fields.py:1845-1918``
#
############################################################################


def _invoke_compute_method(field, records):
    """Despacha ``field.compute`` sobre cada fila — por :func:`determine`.

    ≙ ``BaseModel._compute_field_value`` (``odoo19c: odoo/orm/models.py:4953``),
    cuyo cuerpo es ``determine(field.compute, self)``. El despacho va por
    :func:`determine` y no por ``getattr`` porque ``compute`` tiene DOS formas
    en la fuente y las dos llegan aquí: el **nombre** de un método del modelo
    (``compute='_compute_total'``) y un **invocable** — ``setup_related``
    instala ``self.compute = self._compute_related`` (``:632``), un método
    ligado al campo. Medido antes de este cambio
    (``scripts/workbench/fachadas-construyen-una-vez-*/``
    ``probe_related_setup_phase_when_reachable.py``): con ``getattr`` la
    lectura de un ``related=`` moría con ``TypeError: attribute name must be
    string, not 'method'``.

    La fuente lo invoca sobre el *recordset* entero y el método itera por
    dentro con ``for record in self``; aquí la unidad es la instancia, así
    que el bucle vive de este lado y el método recibe una fila. Es la misma
    adaptación de :func:`~orm.utils.record_ids`, vista desde el otro lado.
    """
    for record in as_record_list(records):
        determine(field.compute, record)


def recompute(self, records):
    """Procesa los cómputos pendientes de este campo sobre ``records``.

    ≙ ``Field.recompute`` (``:1850``). Sólo se llama si el campo es calculado
    y almacenado.

    **Dos divergencias de mecanismo, las dos con su motivo medido y su
    sucesor** — ninguna recorta el comportamiento observable del campo:

    1. *Sin lote de prelectura.* La fuente agrupa los pendientes en ventanas
       de ``PREFETCH_MAX`` con ``expand_ids`` y computa la ventana entera de
       una vez. Aquí el cómputo se invoca por fila (ver
       :func:`_invoke_compute_method`), así que la ventana no ahorraría ni
       una consulta: agruparla sería ceremonia. Vuelve a tener sentido el día
       que el cómputo reciba un ``QuerySet``, que es la tarea **#306**.
    2. *Sin reintento por fila ausente.* La fuente envuelve cada cómputo en
       ``apply_except_missing``: ante un ``MissingError`` reintenta sobre
       ``records.exists()`` y desmarca los que ya no existen *"otherwise they
       remain to compute forever, which may lead to an infinite loop"*. Aquí
       no hay ``MissingError`` — una fila borrada no se detecta al tocarla,
       sino al consultarla — y el equivalente exige el lado de lectura del
       motor, que es la capa C. Sucesor: tarea **#307**.
    """
    to_compute_ids = get_environment().transaction.tocompute.get(self)
    if not to_compute_ids:
        return

    pending = [record for record in as_record_list(records)
               if record.pk in to_compute_ids]
    if not pending:
        return

    if self.recursive:
        # Un calculado recursivo se computa fila a fila, para que sus
        # dependencias internas se resuelvan en orden. Aquí el no-recursivo
        # también va fila a fila (divergencia 1 del docstring), así que las
        # dos ramas coinciden; la condición se conserva porque es donde
        # aterriza el lote cuando #306 lo construya.
        for record in pending:
            self.compute_value(record)
        return

    for record in pending:
        self.compute_value(record)


def compute_value(self, records):
    """Invoca el método de cómputo; el resultado queda en caché.

    ≙ ``Field.compute_value`` (``:1897``).

    El orden importa, y la fuente lo razona: desmarca el cómputo **antes** de
    correrlo *"just in case the compute method does not assign a value"* y
    porque el propio método puede leer el valor viejo, lo que dispararía una
    lectura que volvería a computar el campo — recursión infinita. Si el
    cómputo revienta, se vuelve a marcar y se relanza.

    ``compute_sudo`` no eleva aquí con ``records.sudo()`` —no hay recordset
    que elevar— sino con el alcance de elevación del entorno, que es el
    mecanismo equivalente de este stack (``orm.environments.sudo``).
    """
    env = get_environment()
    ids = record_ids(records)
    fields = registry_field_computed[self]

    for field in fields:
        if field.store:
            env.remove_to_compute(field, ids)

    try:
        with env.protecting(fields, ids):
            if self.compute_sudo:
                with elevate_privileges():
                    _invoke_compute_method(self, records)
            else:
                _invoke_compute_method(self, records)
    except Exception:
        for field in fields:
            if field.store:
                env.add_to_compute(field, ids)
        raise

    _cache_computed_values(fields, records)


def _cache_computed_values(fields, records):
    """Lleva al caché lo que el cómputo dejó en la fila, marcándolo sucio.

    Es la mitad de :func:`compute_value` que este stack tiene que escribir. La
    fuente no la necesita: allá el método de cómputo **asigna sobre el
    recordset**, y esa asignación ya pasa por ``_update_cache`` —el caché es el
    canal de escritura del ORM—. Aquí el método asigna sobre la **instancia de
    Django**, que es un objeto normal: el valor queda en el atributo y el caché
    no se entera.

    Sin este paso, ``field_dirty`` no se puebla nunca, y el ``_flush`` de la
    capa C no tendría de dónde saber qué columna escribir: el cómputo correría,
    el valor viviría en memoria, y la fila de la base seguiría con el valor
    viejo. Es exactamente la mitad silenciosa que ``store=True`` promete.

    Sólo para los campos **persistidos**: un calculado sin columna no se
    guarda, y ``_update_cache`` ya acota ahí su marca de sucio.

    **El muchos-a-muchos entra, y por eso la condición no es** ``column_type``
    (#313). Un M2M persiste —en su tabla intermedia— y no tiene columna en la
    fila, así que la condición vieja lo dejaba fuera: el campo se calculaba, el
    caché no se enteraba, ``field_dirty`` seguía vacío y la rama de
    ``_flush_m2m`` no se ejecutaba nunca. Lo destapó el control discriminante
    de #313: anular esa rama dejaba el módulo **en verde**, que es la señal de
    que medía código muerto.

    Su valor se lee del **manager**, no del atributo: ``getattr`` sobre un M2M
    devuelve el manager, no lo que contiene. ``list(...)`` lo materializa a lo
    que ``.set()`` espera al volcarlo.
    """
    rows = as_record_list(records)
    for field in fields:
        if not _is_persisted(field):
            continue
        many_to_many = getattr(field, 'many_to_many', False)
        for row in rows:
            if many_to_many:
                if row.pk is None:
                    continue
                value = list(getattr(row, field.name).all())
            else:
                value = _value_left_by_compute(row, field)
            field._update_cache([row], value, dirty=True)


def _value_left_by_compute(row, field):
    """Lo que el cómputo dejó en la fila, SIN volver a pasar por el descriptor.

    Este read-back leía con ``getattr``, y eso era correcto mientras el
    atributo de clase fuese un descriptor que sólo consulta el ``__dict__``.
    Desde :class:`FieldDescriptor` (#211) ya no lo es: sobre una fila sin ``pk``
    —el caso de ``pre_save`` en el INSERT— el ``getattr`` vuelve a entrar por
    la rama de cómputo, que llama otra vez a ``compute_value``, que vuelve a
    llamar aquí. Medido: ``RecursionError`` al crear cualquier fila con un
    campo calculado y persistido.

    La fuente no tiene el problema porque no tiene este paso: allá el método de
    cómputo asigna **sobre el recordset** y esa asignación ya es
    ``_update_cache``. Aquí asigna sobre la instancia de Django, así que lo que
    hay que leer es **el almacén de la instancia**, no el campo.

    El caso aplazado —el atributo ausente del ``__dict__``— conserva el camino
    de Django llamando al ``__get__`` del padre, que es literalmente lo que el
    ``getattr`` hacía antes. No puede reentrar: ese camino no computa.
    """
    attname = getattr(field, 'attname', field.name)
    if attname in row.__dict__:
        return row.__dict__[attname]
    descriptor = getattr(type(row), attname, None)
    if isinstance(descriptor, FieldDescriptor):
        return DeferredAttribute.__get__(descriptor, row, type(row))
    return getattr(row, attname, None)


for _cache_method in (_get_cache, _get_cache_impl, _invalidate_cache,
                      _get_all_cache_ids, _cache_missing_ids,
                      _filter_not_equal, _filter_not_equal_ids,
                      _insert_cache,
                      _update_cache, recompute, compute_value):
    setattr(models.Field, _cache_method.__name__, _cache_method)


#: El campo SIN columna recibe la misma familia de caché, y no es un extra: es
#: el que más depende de ella. En la fuente no hay dos clases —``display_name``
#: es un ``Field`` con ``compute`` y sin ``store``— y su valor **sólo** vive en
#: la caché de la transacción, porque no hay columna de donde releerlo. Partir
#: ``Field`` en ``models.Field`` (Django) y :class:`NonStored` (descriptor) es
#: divergencia de stack, así que el contrato se instala sobre las dos.
#:
#: Sin esto ``Cache.get_fields`` reventaba con ``AttributeError`` en el primer
#: modelo que declarara uno — o sea en **todos**, porque ``display_name`` es
#: universal en este árbol desde la tarea #134.
#:
#: ``_is_persisted`` corta solo: exige ``store`` **y** columna o tabla
#: intermedia, y un ``NonStored`` no declara ninguna de las tres. Por eso la
#: marca de sucio nunca prende sobre él y el volcado no intenta escribir una
#: columna que no existe.
#:
#: ``recompute`` y ``compute_value`` **no** se instalan aquí, y la ausencia se
#: declara: son el motor de recálculo, que la fuente dispara desde
#: ``modified()`` y que este árbol construye en la tarea **#273**. Ambos leen
#: ``field.store``, ``self.compute_sudo`` y ``self.recursive`` —tres atributos
#: que ``NonStored`` no declara— así que colgarlos hoy entregaría media
#: mecánica en vez de la de la fuente.
for _cache_method in (_get_cache, _get_cache_impl, _invalidate_cache,
                      _get_all_cache_ids, _cache_missing_ids,
                      _filter_not_equal, _filter_not_equal_ids,
                      _insert_cache, _update_cache):
    setattr(NonStored, _cache_method.__name__, _cache_method)
