"""Campos binarios — fiel a ``odoo/orm/fields_binary.py`` (Odoo 19).

Adaptado de Odoo Community (LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Cobertura del porte
===================

La fuente declara **2 clases, 17 métodos y 8 atributos de clase** en 365
líneas. Aquí están los **atributos de clase** de ambas, que son el contrato
que el resto del ORM lee, y no los métodos, que son el mecanismo de
almacenamiento en ``ir.attachment`` y el procesamiento de imagen.

===================================  =========================================
Símbolo de la fuente                 Desenlace aquí
===================================  =========================================
``Binary.type``                      portado
``Binary.prefetch``                  portado
``Binary._depends_context``          portado
``Binary.attachment``                portado, con **otro default** (ver abajo)
``Binary._description_attachment``   portado
``Image.max_width`` / ``max_height`` portado
``Image.verify_resolution``          portado
los 17 métodos                       bloqueo medido, sucesor en el tablero
===================================  =========================================

**Por qué el default de** ``attachment`` **es** ``False`` **y allá es**
``True``. No es una preferencia: es lo que nuestros campos hacen hoy. La
fuente declara ``column_type`` = ``None`` cuando ``attachment`` es cierto
(``odoo19c: :43``) — el valor **no vive en una columna**, vive en una fila de
``ir.attachment``. Aquí las 16 declaraciones de ``fields.Binary`` del árbol son
``BinaryField`` con su columna ``bytea``. Declarar ``True`` por default
describiría un almacenamiento que ninguna de las 16 usa, y haría que
``domains._optimize_type_binary_attachment`` rechazara toda condición sobre
datos que **sí** están en una columna.

El día que se porte el almacenamiento en adjunto, un campo lo pide con
``fields.Binary(attachment=True)`` — el kwarg ya existe y el atributo ya se
lee. Lo que falta es el mecanismo detrás, no la declaración.
"""
from operator import attrgetter

from django.db import models

from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)

__all__ = ['Binary', 'Image']


class Binary(models.BinaryField):
    """≙ ``class Binary(Field)`` (``odoo19c: :29``).

    Docstring de la fuente, verbatim: *"Encapsulates a binary content (e.g. a
    file)"*, con el parámetro *"attachment: whether the field should be stored
    as `ir_attachment` or in a column of the model's table"*.
    """

    type = 'binary'

    #: ≙ ``:38`` — *"not prefetched by default"*.
    prefetch = False

    #: ≙ ``:37`` — el valor depende de si se pide el contenido o su tamaño.
    _depends_context = ('bin_size',)

    def __init__(self, *args, attachment=False, related=None, store=_UNSET,
                 **kwargs):
        """≙ ``:39``. El default de ``attachment`` diverge — la razón, en el
        docstring del módulo.

        ``store`` y ``related`` se **reenvían**, no se tragan: el enrutado de
        ``__new__`` se retiró (TASK-API-0417) y el vocabulario tiene que llegar
        a ``_args__`` para que la costura lo vea tras fusionar la MRO.
        """
        self.attachment = bool(attachment)
        if store is not _UNSET:
            kwargs['store'] = store
        related_attrs = apply_source_defaults(related, kwargs)
        super().__init__(*args, **kwargs)
        annotate_related(self, related, related_attrs)

    #: ≙ ``:51`` — lo que el cliente lee para saber dónde vive el valor.
    _description_attachment = property(attrgetter('attachment'))

    def deconstruct(self):
        """La ruta que la migración registra sigue siendo la de Django.

        Mientras ``attachment`` es falso el campo **es** un ``BinaryField``: la
        misma columna ``bytea``, el mismo DDL. Emitir aquí la ruta de esta
        subclase generaría un ``AlterField`` por cada una de las 16
        declaraciones del árbol sin que ninguna columna cambie.

        Con ``attachment=True`` la ruta sí es la propia: ahí el campo deja de
        ser un ``BinaryField`` y la migración tiene que poder reconstruirlo.
        """
        name, path, args, kwargs = super().deconstruct()
        if self.attachment:
            kwargs['attachment'] = True
        else:
            path = 'django.db.models.BinaryField'
        return name, path, args, kwargs


class Image(models.ImageField):
    """≙ ``class Image(Binary)`` (``odoo19c: :243``).

    Los tres atributos que la fuente declara para acotar y validar la imagen.
    El procesamiento (``_image_process``, 46 líneas) es el mecanismo, y va con
    el resto de los métodos en el sucesor.
    """

    type = 'binary'

    #: ≙ ``:250-252`` — el recorte máximo, y si se verifica la resolución.
    max_width = 0
    max_height = 0
    verify_resolution = True

    def __init__(self, *args, max_width=0, max_height=0, related=None,
                 store=_UNSET, verify_resolution=True, **kwargs):
        """Los tres atributos de recorte, y el vocabulario de la fuente
        reenviado — mismo criterio que :class:`Binary`."""
        self.max_width = max_width
        self.max_height = max_height
        self.verify_resolution = verify_resolution
        if store is not _UNSET:
            kwargs['store'] = store
        related_attrs = apply_source_defaults(related, kwargs)
        super().__init__(*args, **kwargs)
        annotate_related(self, related, related_attrs)

    def deconstruct(self):
        """Mismo criterio que :meth:`Binary.deconstruct` — ver allí."""
        name, path, args, kwargs = super().deconstruct()
        propios = {'max_width': self.max_width, 'max_height': self.max_height}
        if not self.verify_resolution:
            propios['verify_resolution'] = False
        if any(propios.values()) or not self.verify_resolution:
            kwargs.update({k: v for k, v in propios.items() if v})
        else:
            path = 'django.db.models.ImageField'
        return name, path, args, kwargs
