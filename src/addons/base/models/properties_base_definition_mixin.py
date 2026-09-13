"""``properties.base.definition.mixin`` — propiedades de usuario sin padre.

Adaptación de ``odoo/addons/base/models/properties_base_definition_mixin.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 56 líneas). Un modelo que hereda este
mixin gana un campo ``properties`` —pares clave/valor definidos por el
usuario— cuyo **esquema** vive en una fila de ``properties.base.definition``,
no en el padre del registro.

Archivo propio, como en la referencia
=====================================

La referencia tiene ``image_mixin.py``, ``avatar_mixin.py`` y éste: **un
archivo por mixin**, no un ``mixins.py`` que los agrupe por naturaleza. Este
árbol ya sigue esa forma (``timestamped_mixin.py``, ``append_only_mixin.py``,
``soft_delete_mixin.py``, ``image_mixin.py``, ``avatar_mixin.py``), y este
archivo la completa.

Por qué el vínculo es derivado y no una columna
==============================================

``properties_base_definition_id`` es ``compute`` **sin** ``store`` en la
referencia, y la razón se lee en su propio cómputo: la definición **no
depende del registro**, depende de *(modelo, nombre del campo)*. Todas las
filas de un mismo modelo comparten exactamente la misma definición.

Guardarlo como columna sería replicar el mismo id en cada fila y abrir la
puerta a que dos filas del mismo modelo apunten a definiciones distintas —un
estado que el modelo no admite—. Aquí se declara con el mismo nombre y en el
mismo sitio que la fuente, usando ``fields.Many2one(..., store=False)``: el
despachador de ``orm/fields_relational.py`` devuelve un campo sin columna, que
es lo que un ``compute`` sin ``store`` significa.

Su ``_search_properties_base_definition_id`` lo confirma: no filtra fila por
fila, devuelve ``Domain.TRUE`` o ``Domain.FALSE`` **para todo el modelo**
según si el id buscado es el suyo.

Los cuatro símbolos
===================

Los cuatro métodos de la referencia se portan **con su nombre y su firma**:

.. list-table::
   :header-rows: 1

   * - Referencia
     - Estado aquí
   * - ``_compute_properties_base_definition_id``
     - portado; lo consume el ``default`` del campo sin columna
   * - ``_search_properties_base_definition_id``
     - portado; devuelve ``Domain.TRUE``/``Domain.FALSE``/``NotImplemented``
   * - ``create``
     - portado; siembra la definición antes de insertar, y ``save`` delega
   * - ``_field_to_sql``
     - portado; su rama propia emite el id como constante ``SQL``

``_field_to_sql`` — entero, con su base ya portada
=================================================

La rama propia —emitir el id de la definición como constante para que la
exportación funcione— se porta con ``tools.sql.SQL``; la otra delega en
``super()``, igual que la fuente.

Ese ``super()`` estuvo bloqueado: hasta la tarea **#127**
``BaseModel._field_to_sql`` no existía en ``src/orm`` —medido entonces:
``grep -rn "def _field_to_sql" src/orm/`` → 0— y la mitad de delegación
levantaba ``NotImplementedError`` citando la tarea. Hoy existe como
``orm.models.FieldSqlMixin``, que esta clase adopta, y con él llegaron sus
tres dependencias: ``_traverse_related_sql``, ``_check_field_access`` y el par
``field.to_sql``/``field.property_to_sql`` de ``orm/fields.py``.
"""
import logging

import fields
import api
import models
from tools.sql import SQL

from addons.base.models.properties_base_definition import (
    PropertiesBaseDefinition,
)
from orm.domains import Domain
from orm.utils import COLLECTION_TYPES
from orm.models import FieldSqlMixin

_logger = logging.getLogger(__name__)

#: Nombre del campo de propiedades que este mixin aporta. La definición se
#: resuelve por *(modelo, este nombre)*, no por registro.
PROPERTIES_FIELD_NAME = 'properties'


def _definition_default(record):
    """``default`` del campo sin columna — delega en el cómputo de la fuente."""
    return record._compute_properties_base_definition_id()


class PropertiesBaseDefinitionMixin(FieldSqlMixin, models.Model):
    """Mixin que añade propiedades **sin padre** a un modelo."""

    _name = 'properties.base.definition.mixin'
    _description = 'Properties Base Definition Mixin'

    properties = fields.Properties(
        default=dict, blank=True, verbose_name='Propiedades',
        definition='properties_base_definition_id.properties_definition',
        help_text='Pares clave/valor definidos por el usuario. Su esquema vive '
                  'en properties.base.definition, resuelto por (modelo, '
                  'campo) — no por registro.',
    )
    properties_base_definition_id = fields.Many2one(
        PropertiesBaseDefinition, store=False, default=_definition_default,
        help_text='Derivado de (modelo, campo), no del registro: todas las '
                  'filas de este modelo comparten la misma definición.',
    )

    class Meta:
        abstract = True

    @classmethod
    def properties_model_label(cls):
        """El nombre técnico del modelo, tal como lo guarda ``ir.model.fields``.

        La fuente usa ``self._name``; aquí el nombre del modelo en el catálogo
        es la etiqueta de Django, que es la que ``ir.model.fields`` almacena.
        """
        return f'{cls._meta.app_label}.{cls._meta.object_name}'

    def _compute_properties_base_definition_id(self):
        """``_compute_properties_base_definition_id`` — derivado, no columna.

        ≙ ``odoo19c: properties_base_definition_mixin.py:27-29``. La definición
        depende de *(modelo, campo)*, no del registro: todas las filas de este
        modelo comparten la misma. Ver el docstring del módulo sobre por qué
        guardarla sería un error.
        """
        return PropertiesBaseDefinition._get_definition_for_property_field(
            type(self).properties_model_label(), PROPERTIES_FIELD_NAME)

    @classmethod
    def _search_properties_base_definition_id(cls, operator, value):
        """``_search_properties_base_definition_id`` — para todo el modelo.

        ≙ ``odoo19c: properties_base_definition_mixin.py:31-40``. No filtra
        fila por fila: devuelve si la definición de **este modelo** está entre
        las buscadas. Con un operador que no sea ``in`` devuelve
        ``NotImplemented``, igual que la fuente.
        """
        if operator != 'in':
            return NotImplemented

        properties_base_definition_id = (
            PropertiesBaseDefinition._get_definition_id_for_property_field(
                cls.properties_model_label(), PROPERTIES_FIELD_NAME))

        if not isinstance(value, COLLECTION_TYPES):
            value = (value,)
        return (Domain.TRUE if properties_base_definition_id in value
                else Domain.FALSE)

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """``create`` — siembra la definición antes de insertar.

        ≙ ``odoo19c: properties_base_definition_mixin.py:42-48``. La fuente
        inyecta ``properties_base_definition_id`` en cada ``vals`` para que el
        ORM aplique los valores por defecto de las propiedades. Aquí el
        vínculo es derivado, así que lo que la inyección garantiza —que la
        fila de definición **exista**— se hace llamando al mismo método que
        ella llama.
        """
        parent = PropertiesBaseDefinition._get_definition_id_for_property_field(
            cls.properties_model_label(), PROPERTIES_FIELD_NAME)
        created = []
        for vals in vals_list:
            record = cls.objects.create(**vals)
            record.properties_base_definition_id = parent
            created.append(record)
        return created

    def save(self, *args, **kwargs):
        """Enganche de Django — garantiza la definición al insertar.

        Es lo que ``create`` de la fuente asegura; se pone en ``save`` para
        que también lo cumpla quien inserte por la vía del ORM de Django.
        """
        if self._state.adding:
            PropertiesBaseDefinition._get_definition_id_for_property_field(
                type(self).properties_model_label(), PROPERTIES_FIELD_NAME)
        return super().save(*args, **kwargs)

    def _field_to_sql(self, alias, fname, query=None):
        """``_field_to_sql`` — el id de la definición como constante.

        ≙ ``odoo19c: properties_base_definition_mixin.py:50-56``. Permite que
        la exportación funcione: el campo no tiene columna, así que el motor
        de consultas necesita un valor literal en su lugar.

        El ``super()`` es ``FieldSqlMixin._field_to_sql`` (``orm/models.py``),
        el porte de ``BaseModel._field_to_sql`` de la fuente (``odoo19c:
        odoo/orm/models.py:2910-2932``). Estuvo bloqueado hasta la tarea #127;
        desde entonces la delegación es la de la fuente, palabra por palabra.
        """
        if fname == 'properties_base_definition_id':
            parent = (
                PropertiesBaseDefinition._get_definition_id_for_property_field(
                    type(self).properties_model_label(),
                    PROPERTIES_FIELD_NAME))
            return SQL("%s", parent)

        return super()._field_to_sql(alias, fname, query)
