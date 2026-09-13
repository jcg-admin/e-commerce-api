"""Campos numéricos — fiel a ``odoo/orm/fields_numeric.py`` (Odoo 19).

``Integer``, ``Float``, ``Monetary`` (Odoo Monetary = importe con moneda; alias
de ``DecimalField`` que en el proyecto sale como string por
``COERCE_DECIMAL_TO_STRING``).

``Monetary`` no es un alias pelado sino un **despachador** de ``store=``, igual
que ``Char`` (ver ``fields_textual.py``): recibe el vocabulario de la fuente,
lo deriva y lo anota sobre el campo. Lo que **ya no hace** es elegir clase —
``store`` es un atributo, no un tipo (``odoo19c: odoo/orm/fields.py:455``), y
la forma sin columna la resuelve la costura al contribuir a la clase
(TASK-API-0417). Precedente de ``Monetary`` sin columna:
``account/models/account_analytic_distribution_model.py`` (campo
``prefix_placeholder``) y ``account/models/digest.py`` (los KPI
``kpi_account_*_value``, que en la fuente son ``compute`` no almacenados).
``Integer`` y ``Float`` reciben el mismo trato por el molde de
:func:`~orm.fields_company_dependent.make_dispatcher`. Primer consumidor de
``Integer(store=False)``: ``hr_recruitment/models/digest.py`` (tarea #159),
cuyo KPI la fuente declara ``fields.Integer(compute=…)``, sin columna.

``company_dependent`` — ``Integer`` y ``Float`` sí lo llevan (tarea #129)
=========================================================================

Los dos están en ``COMPANY_DEPENDENT_FIELDS``, y los dos tienen consumidor en
la referencia: ``purchase/models/res_partner.py:43``
(``reminder_date_before_receipt``, ``Integer``) y
``product/models/product_product.py:62`` (``standard_price``, ``Float``). Por
eso dejan de ser alias pelados y pasan a ser despachadores fabricados con
:func:`~orm.fields_company_dependent.make_dispatcher`.

``Monetary`` **no** lo lleva, y no por olvido: ``monetary`` no está en la lista
cerrada de tipos que la fuente admite
(``odoo19c: odoo/orm/fields.py:42-44``). El ``standard_price`` que aquí es
``Monetary`` y allá es ``Float`` company_dependent es una decisión propia —
tarea **#135**.
"""
import decimal

from django.db import models

from orm.fields_company_dependent import make_dispatcher
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)

__all__ = ['Integer', 'Float', 'Monetary']

Integer = make_dispatcher('Integer', 'integer', models.IntegerField)
Float = make_dispatcher('Float', 'float', models.FloatField)


def Monetary(*args, store=_UNSET, help=None, related=None, **kwargs):
    """``fields.Monetary`` — ≙ el de la referencia, con y sin columna.

    ``help=`` es el alias de firma de la fuente para ``help_text=`` (misma
    tabla de alias que ``Char``).
    """
    if help is not None:
        kwargs.setdefault('help_text', help)
    #: ``:452-458`` — el centinela, por el mismo motivo que en ``Char``: el
    #: defecto de ``store`` depende de si hay ``related``.
    if store is not _UNSET:
        kwargs['store'] = store
    related_attrs = apply_source_defaults(related, kwargs)
    #: El ``DecimalField`` se construye con columna y sin ella: ``store`` es
    #: atributo, no tipo (``odoo19c: odoo/orm/fields.py:455``).
    field = models.DecimalField(*args, **kwargs)
    return annotate_related(field, related, related_attrs)


def _integer_convert_to_column(self, value, record, values=None, validate=True):
    """``Integer.convert_to_column`` — ≙ ``odoo19c: odoo/orm/fields_numeric.py:32-33``.

    ``int(value or 0)``: el vocabulario de ausencia de un entero es el cero, no
    el ``NULL``. Es la sobrecarga que impide que la base lleve ``False`` a
    ``NULL`` sobre una columna que la fuente declara siempre poblada.

    **El cuerpo es verbatim y NO consulta ``null``.** Una primera versión
    añadió una rama ``if self.null: return None``, razonando que la fuente
    declara su ``Integer`` NOT NULL. Medido, eso es falso:
    ``odoo19c: odoo/orm/fields.py:298`` declara ``required: bool = False`` —
    «whether the field is required (NOT NULL in database)»—, así que la columna
    de un ``Integer`` admite ``NULL`` como cualquier otra. Lo que la fuente
    declara es ``falsy_value = 0`` (``fields_numeric.py:21``) y **tres**
    conversores que colapsan la ausencia al cero —éste, ``convert_to_cache`` y
    ``convert_to_record``—: el ORM nunca escribe ``NULL`` ni devuelve ``None``,
    y un ``NULL`` heredado en la columna se lee como ``0``.

    Cuando una restricción de tabla necesita el ``NULL``, la fuente lo resuelve
    **en el modelo**, no aquí: ``ir_filters`` declara su ``CHECK`` y borra la
    clave cuando vale cero antes de escribir
    (``odoo19c: odoo/addons/base/models/ir_filters.py:33-34`` y ``:54-57``).
    """
    return int(value or 0)


models.IntegerField.convert_to_column = _integer_convert_to_column


def _float_convert_to_column(self, value, record, values=None, validate=True):
    """``Float.convert_to_column`` — ≙ ``:155-163``.

    Redondea al número de decimales declarado antes de escribir, que es el
    punto entero del cuerpo de la fuente: sin ese paso el valor de la columna y
    el de la caché divergen en el último dígito y las comparaciones dejan de
    coincidir.

    La fuente lee la precisión de ``self.get_digits(record.env)`` —un ajuste por
    empresa— y aquí la declara el propio campo (``decimal_places``), que es
    donde este stack la pone. El registro no hace falta: por eso la firma lo
    acepta y el cuerpo no lo consulta.
    """
    value = float(value or 0.0)
    scale = getattr(self, 'decimal_places', None)
    return round(value, scale) if scale is not None else value


models.FloatField.convert_to_column = _float_convert_to_column


def _decimal_convert_to_column(self, value, record, values=None, validate=True):
    """``Monetary.convert_to_column`` — ≙ el mismo reparto que ``Float``.

    ``DecimalField`` es el tipo con que este árbol declara el dinero, y su
    valor **no** pasa por ``float``: cuantizarlo en ``Decimal`` es lo que
    conserva la representación exacta que la columna guarda. Un ``0`` o un
    ``False`` entran como cero, no como ``NULL`` — mismo criterio que el
    entero.
    """
    if value is None or value is False or value == '':
        return decimal.Decimal(0)
    if not isinstance(value, decimal.Decimal):
        value = decimal.Decimal(str(value))
    scale = getattr(self, 'decimal_places', None)
    if scale is None:
        return value
    return value.quantize(decimal.Decimal(1).scaleb(-scale),
                          rounding=decimal.ROUND_HALF_UP)


models.DecimalField.convert_to_column = _decimal_convert_to_column
