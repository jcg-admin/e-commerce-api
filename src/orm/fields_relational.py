"""Campos relacionales — fiel a ``odoo/orm/fields_relational.py`` (Odoo 19).

``Many2one`` = ``ForeignKey``; ``Many2many`` = ``ManyToManyField``; ``One2many``
es el reverso de un FK en Django (``related_name``), sin clase propia.

``store=False`` — el Many2one sin columna
==========================================

La referencia declara relaciones **calculadas y no almacenadas**::

    properties_base_definition_id = fields.Many2one(
        "properties.base.definition",
        compute="_compute_properties_base_definition_id",
        search="_search_properties_base_definition_id",
    )

(``odoo19c: odoo/addons/base/models/properties_base_definition_mixin.py:21-25``)
— un ``compute`` sin ``store`` **no tiene columna**: el valor se resuelve al
leerlo. Django no lo tiene: todo ``ForeignKey`` es una columna.

Por eso ``Many2one`` deja de ser un alias pelado y pasa a ser una **fachada**,
el mismo patrón que ya tienen ``Char`` (``orm/fields_textual.py``) y ``Float``
(``orm/fields_numeric.py``). El sitio de declaración queda **idéntico al de la
fuente**, que es el punto — la alternativa era colgar una ``property`` fuera de
la clase y repartir en el cableado lo que la referencia declara en el cuerpo.

**La fachada ya no elige clase, y ésa es la corrección de TASK-API-0417.** Hasta
``api@2437373d`` devolvía un ``ForeignKey`` o un ``NonStored`` según el valor de
``store``, que es exactamente lo que la fuente NO hace: ahí ``store`` es un
atributo del campo y nunca un tipo distinto
(``odoo19c: odoo/orm/fields.py:455``, dentro del bloque ``_get_attrs`` de
``:443-465``). Hoy la fachada construye **siempre** el tipo de Django y se
limita a tres cosas — derivar lo que ``compute=``/``related=`` implican
(:func:`~orm.fields_nonstored.apply_source_defaults`), reenviar el vocabulario
de la fuente al constructor, y anotar el resultado. La forma sin columna la
resuelve la **costura** (``orm/fields.py``): ``_field_contribute_to_class``
llama a ``contribute_to_class`` con ``private_only=True``, así que el campo no
entra en ``_meta.concrete_fields``, no genera migración y no tiene columna.

Lo que lo hizo posible: ``_field_init_with_copy`` recoge el vocabulario
declarado en ``_args__`` **antes** de delegar en Django, y retira de ``kwargs``
lo que el constructor de Django no admite. Medido en la sonda
``probe_vocabulary_reaches_args_by_type`` del workbench
``fachadas-construyen-una-vez-20260911T193801``: los **once** tipos que las
fachadas construyen recogen ``store`` y ``related``, incluidos ``ForeignKey`` y
``ManyToManyField``, que tienen ``__init__`` propio.

``join`` — el salto de un camino relacional
===========================================

``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466``) añade a una
consulta el LEFT JOIN que sigue este campo y devuelve el par
``(comodelo, alias)``. Lo consume ``BaseModel._traverse_related_sql``, que
recorre un campo delegado salto a salto.

Se adjunta a ``models.ForeignKey`` —la clase que ``Many2one`` devuelve— por la
misma razón de forma que ``orm/fields.py`` declara para ``to_sql``: la clase es
de Django y no es nuestra para declararla. Medido antes de adjuntar: ``join``
da ``False`` en ``hasattr(models.ForeignKey, 'join')``.

``Many2many`` **no lleva** ``company_dependent``: ``many2many`` no está en la
lista cerrada de tipos que la fuente admite
(``odoo19c: odoo/orm/fields.py:42-44``) — un ``jsonb`` guarda un valor por
empresa, no una tabla intermedia. Su rama sigue siendo un ``ValueError``.

Su ``store=False`` **dejó de ser una rama** con la retirada del enrutado: la
fachada acepta la palabra clave, la deriva igual que las otras ocho y construye
el ``ManyToManyField`` de siempre. Lo que **no** está medido es qué hace la
costura con un muchos-a-muchos bajo ``private_only``: su tabla intermedia no es
una columna del modelo, así que el mecanismo que vacía la columna de un escalar
no tiene contraparte obvia aquí. No se afirma que funcione ni que falle —
**DESCONOCIDO declarado**, y su condición de cierre es que exista un consumidor
que medir: hoy ``grep -rn "Many2many(" `` sobre ``odoo19c:`` no arroja ninguna
declaración ``store=False`` con ``compute`` sin almacenar en la familia
``base``. Sucesor: **TASK-API-0418**, que retira ``NonStored`` como clase y es
donde el eje ``store`` queda medido tipo por tipo.

.. note:: **Corregido.** Esta línea decía *"``Many2many`` **no** lleva el
   despachador"*, y hoy sí lo lleva: es una función, no el alias pelado
   ``Many2many = models.ManyToManyField``. Lo que sigue siendo cierto es la
   razón que el párrafo daba — ninguna de esas **dos** ramas aplica—; lo que
   cambió es que apareció una tercera palabra clave que sí, ``check_company``,
   medida en **19** declaraciones de la referencia dentro de los addons que
   este árbol ya tiene.

``company_dependent`` — el destino que cambia con la empresa (tarea #129)
=========================================================================

``Many2one`` sí lo lleva, y es el tipo que más lo usa en la referencia: **35**
de las 54 declaraciones de producto. Ver la rama en :func:`Many2one`.
"""
import collections.abc
import itertools

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.fields.related import RelatedField

from orm.environments import env as get_environment
from orm.fields_company_dependent import CompanyDependent
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)
from django.db.models.fields.related import lazy_related_operation
from orm.identifiers import NewId
from orm.model_classes import is_transient
from orm.registry import IR_MODELS, model_by_name, name_of, sentinel_label
from orm.utils import display_name_of, model_of, record_ids
from tools.misc import SENTINEL, unique
from tools.sql import SQL

__all__ = ['Many2one', 'One2many', 'Many2many', 'bypass_search_access',
           'PrefetchMany2one', 'PrefetchX2many']

class One2many:
    """El conjunto de registros del comodelo cuyo inverso apunta a este — ≙ ``:843``.

    La fuente lo define en una linea: *"the recordset of all the records in
    ``comodel_name`` such that the field ``inverse_name`` is equal to the
    current record"*. Django tiene ese conjunto —es el reverso de la FK, el
    ``related_name`` del hijo— pero **no tiene donde declararlo en el padre**,
    y ese es exactamente el hueco que esta clase cierra.

    Hasta ``api@596cd2b`` este nombre valia ``None`` y estaba en el ``__all__``
    publico: ``fields.One2many(...)`` daba ``TypeError: 'NoneType' object is
    not callable``. La razon escrita —*"es el reverso de un FK en Django, sin
    clase propia"*— describia el **mecanismo de lectura**, que es correcto, y
    callaba el **sitio de declaracion**, que no lo es::

        # la fuente, en el padre                    (odoo19c: res_partner.py)
        child_ids = fields.One2many('res.partner.category', 'parent_id')

        # Django, en el hijo                        (otro archivo, otra clase)
        parent = models.ForeignKey(..., related_name='child_ids')

    Al portar un modelo padre sus ``One2many`` desaparecian de su cuerpo. Es
    el defecto de forma de :ref:`h-api-350` y del ``store=False``
    (:ref:`h-api-361`): todos los simbolos presentes, la forma cambiada — y el
    conteo, que es lo unico que el gate mide, no lo ve.

    **No reimplementa la lectura: la reusa.** El valor sale del manager que
    Django ya construyo, asi que ``.add()``, ``.create()`` y el resto del
    protocolo del reverso siguen siendo los suyos. Lo que esta clase aporta es
    el sitio de declaracion, ``copy=False`` y el rechazo por nombre.

    Poblacion que lo consume: **730** declaraciones en ``odoo19c``, **37** solo
    en ``base``. No hay que esperar al consumidor real — ya existe y esta
    contado.

    **No persiste.** Sigue el protocolo de ``contribute_to_class`` sin
    registrarse en ``_meta``, igual que la forma sin columna que la costura
    resuelve con ``private_only``: la columna es la FK del hijo, que ya existe. Un ``One2many`` en ``_meta``
    generaria migracion para una columna que nadie tiene.

    Cobertura del porte — 13 simbolos en la fuente
    ==============================================

    ``porte-completo-no-parcial.md`` exige declarar **cuantos, cuales y por
    que** cuando un porte no cierra todos los simbolos. Medido por AST contra
    ``odoo19c: odoo/orm/fields_relational.py:843``:

    ======================================= ===================================
    Simbolo de la fuente                    Desenlace
    ======================================= ===================================
    ``__init__``                            **portado**, con los cuatro
                                            parametros que su docstring
                                            documenta
    ``__get__``                             **portado** — reusa el manager del
                                            reverso de Django
    ``_additional_domain``                  **portado**; su rama polimorfica es
                                            DESCONOCIDO con condicion de
                                            cierre, tarea **#240**
    ``get_comodel_domain``                  **portado** en su composicion; el
                                            tipo de retorno esta bloqueado y
                                            medido, tarea **#241**
    ``_description_relation_field``         **portado** (aqui es ``property``,
                                            alli ``property(attrgetter(...))``)
    ``setup_nonrelated`` · ``update_db``    conducta **portada** en
                                            ``_inverse_field``, con el mensaje
                                            verbatim — pero **perezosa** donde
                                            la fuente es eager. El eje eager es
                                            la tarea **#242**
    ``write_real`` · ``write_new``          su rama ``CLEAR``/``SET`` esta
                                            **portada** en ``__set__``, con la
                                            decision de ``ondelete``. Los otros
                                            cinco comandos no pasan por el
                                            campo: ``Command`` aqui es
                                            ejecutivo (:ref:`h-api-589`, tarea
                                            **#345**)
    ``read``                                **divergencia de mecanismo** — la
                                            fuente llena su cache por lote; aqui
                                            la lectura es el manager del
                                            reverso, y el lote lo da
                                            ``prefetch_related``
    ``setup_inverses``                      **divergencia de mecanismo** — el
                                            mapa existe y lo mantiene Django en
                                            ``remote_field``; la fuente tiene
                                            que construirlo porque su ORM no lo
                                            guarda. Aqui lo deriva
                                            ``registry._TriggerRegistry``.
                                            Cerrado con la capa B de #273
                                            (:ref:`h-api-1032`); era
                                            DESCONOCIDO por *"este arbol no
                                            tiene cache de campos"*, y esa
                                            causa la retiro la capa A
    ``_condition_to_sql_relational``        **trabajo**, no divergencia: el lado
    ``_get_query_for_condition_value``      SQL del campo. Tarea **#243**
    ``_internal_description_domain_raw``    **trabajo**, detras de #241 porque
                                            necesita el tipo ``Domain``
    ======================================= ===================================

    Siete simbolos son propios y no tienen contraparte por nombre:
    ``__set_name__`` y ``contribute_to_class`` son el protocolo de nombre de
    Django; ``_inverse_field``, ``_deletes_the_leftover`` y ``__set__`` son el
    cuerpo de lo que la fuente resuelve dentro de ``setup_nonrelated`` y
    ``write_real``; ``__repr__`` es el que la fuente hereda de ``Field``.
    """

    #: ≙ ``type = 'one2many'`` (``odoo19c: :866``).
    type = 'one2many'

    def __init__(self, comodel_name=None, inverse_name=None, *, copy=False,
                 string=None, domain=None, context=None,
                 bypass_search_access=False, related=None, **_ignored):
        #: Se acepta con nombre para que **no** caiga en ``**_ignored``, que es
        #: como se tragaba antes: la declaración se escribía igual que la de la
        #: fuente (``fields.One2many(related='employee_id.subordinate_ids')``),
        #: pasaba sin error, y no hacía nada. Un parámetro tragado es peor que
        #: uno ausente, que es lo que el comentario de ``domain``/``context``
        #: de este mismo constructor ya decía.
        #:
        #: **Aquí NO se llama a ``apply_source_defaults``**, y es la única de
        #: las nueve fachadas donde no se llama: ``One2many`` no construye un
        #: ``models.Field``, así que no hay constructor de Django al que
        #: reenviar el vocabulario ni ``_args__`` que lo recoja. Su extremo de
        #: cadena es el manager del reverso, que no necesita comodelo ni
        #: inverso declarados — es lo que la referencia declara, sin ellos.
        self.related = related
        self.comodel_name = comodel_name
        self.inverse_name = inverse_name
        #: Los tres que la fuente documenta en su docstring (``:852-860``) y
        #: que este porte tragaba en ``**_ignored``. Un parametro tragado es
        #: peor que uno ausente: la llamada se escribe igual que la de la
        #: fuente, pasa sin error, y no hace nada.
        self.domain = domain
        self.context = context or {}
        #: *"whether access rights are bypassed on the comodel (default:
        #: ``False``)"* — ``:859-860``. El default abierto seria un hueco de
        #: permiso; lo consume ``domains._optimize_any_with_rights``.
        self.bypass_search_access = bool(bypass_search_access)
        #: ≙ ``copy: bool = False`` con su comentario verbatim: *"o2m are not
        #: copied by default"* (``:867``). Lo mira ``BaseModel.copy`` para
        #: decidir si arrastra los hijos; el default contrario duplicaria un
        #: arbol entero al copiar su raiz.
        self.copy = bool(copy)
        self.string = string
        self.name = None

    @property
    def _description_relation_field(self):
        """La columna del hijo por la que cuelga el conjunto — ≙ ``:901``::

            _description_relation_field = property(attrgetter('inverse_name'))

        Es lo que el cliente lee en la descripcion del campo para saber por
        donde esta enlazado.
        """
        return self.inverse_name

    def _additional_domain(self, env=None):
        """El predicado extra del inverso polimorfico — ≙ ``:913-919``.

        La fuente devuelve ``Domain(inverse_field.model_field, '=',
        self.model_name)`` cuando el inverso es un ``many2one_reference``: un
        FK polimorfico guarda modelo e id en dos columnas, y sin acotar el
        modelo el conjunto traeria las filas de todos los demas.

        **DESCONOCIDO declarado, con su condicion de cierre.** Aqui
        ``Many2oneReference`` es el ``GenericForeignKey`` de ``contenttypes``
        (``orm/fields_reference.py:14``), que **no** expone ``model_field``: su
        par de columnas se llama ``ct_field``/``fk_field`` y ningun addon
        portado declara todavia un inverso polimorfico. La rama se cierra
        cuando exista el primero que medir — tarea **#240**. Hasta entonces
        devuelve el predicado vacio, que es lo que la fuente devuelve para los
        otros dos tipos de inverso (``Domain.TRUE``).
        """
        return []

    def get_comodel_domain(self, model=None):
        """El dominio declarado, mas el del inverso — ≙ ``:918-919``.

        La fuente compone ``super().get_comodel_domain(model) &
        self._additional_domain(model.env)`` y devuelve un ``Domain``.

        **El tipo de retorno esta BLOQUEADO por ``orm.domains.Domain``, y el
        bloqueo esta medido dos veces.** ``from orm.domains import Domain`` en
        la cabecera de este archivo no arranca, por dos causas independientes
        que se apilan:

        1. **Ciclo.** ``orm/domains.py:102`` importa ``orm.fields``, y
           ``orm/fields.py:77`` importa este archivo de vuelta. Medido en las
           dos direcciones, que es lo que ``no-lazy-imports.md`` excepcion #3
           exige antes de aceptar nada que no sea un refactor::

               ImportError: cannot import name 'Many2many' from partially
               initialized module 'orm.fields_relational'

        2. **Registro de apps.** Aun rompiendo el ciclo por orden, ``fields.py``
           arrastra ``fields_reference`` -> ``contenttypes`` -> ``ContentType``,
           y este archivo se carga desde ``inherits.py`` **durante**
           ``apps.populate``::

               django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.

        La referencia no tiene ninguno de los dos: su ``odoo/orm/domains.py``
        importa ``.identifiers`` y ``.utils``, y **no** el modulo de campos
        (medido sobre sus 19 imports). La arista de vuelta la pone nuestro
        ``orm/fields.py`` al cargar el papel de fachada que la referencia
        declara en ``odoo/fields.py``.

        **No se resuelve aqui, y no por conveniencia:** retirar
        ``orm/fields.py:77`` tiene dos consumidores medidos —``__all__``, del
        que ``ir_model.FIELD_TYPES`` se deriva (``ir_model.py:213,239``), y
        ``tests/unit/orm/test_fields_facade.py:61``, que ejercita
        ``from orm.fields import *``— asi que cambia el vocabulario de
        ``IrModelFields.ttype``. Separar definidor de fachada es el alcance
        declarado de la tarea **#211**; el cambio de tipo de retorno de este
        metodo es la tarea **#241**, que la sucede.

        Lo que SI esta portado es la **composicion**, que es el contenido del
        metodo: el dominio declarado en el campo mas el del inverso.
        """
        declarado = list(self.domain) if self.domain else []
        return declarado + list(self._additional_domain())

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase en una clase que NO es modelo Django."""
        self.name = name

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class`` — sin tocar ``_meta``."""
        self.name = name
        self.model_name = cls._meta.label
        setattr(cls, name, self)

    # -- protocolo de descriptor -------------------------------------------

    def _inverse_field(self):
        """El ``Many2one`` del comodelo que este campo invierte.

        Rechaza el inverso inexistente **por nombre**, con el mensaje de
        ``setup_nonrelated`` (``odoo19c: :889``)::

            raise ValueError(f"{self.inverse_name!r} declared in {self!r} "
                             f"does not exist on {comodel._name!r}.")

        Un ``FieldDoesNotExist`` pelado de Django no dice cual de los dos
        nombres esta mal: si el del comodelo o el del inverso.
        """
        comodel = apps.get_model(self.comodel_name)
        try:
            return comodel, comodel._meta.get_field(self.inverse_name)
        except FieldDoesNotExist:
            raise ValueError(
                f'{self.inverse_name!r} declared in {self!r} does not exist '
                f'on {self.comodel_name!r}.') from None

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        comodel, inverse = self._inverse_field()
        accessor = inverse.remote_field.get_accessor_name()
        if accessor is not None and hasattr(instance, accessor):
            # El manager del reverso: trae ademas la escritura (``add``,
            # ``create`` con el padre ya puesto), que un ``filter`` no da.
            return getattr(instance, accessor)
        # El inverso apunta a otro modelo, o su reverso esta suprimido con
        # ``related_name='+'``. Queda la definicion literal de la fuente.
        return comodel._default_manager.filter(**{self.inverse_name: instance})

    def _deletes_the_leftover(self, inverse):
        """Que hacer con el hijo que se queda fuera — ≙ ``write_real:975-979``.

        La fuente lo decide por el ``ondelete`` del inverso, no por la
        nulabilidad de la columna::

            if getattr(comodel._fields[inverse], 'ondelete', False) == 'cascade':
                to_delete.extend(lines._ids)
            else:
                lines[inverse] = False

        Django decide por otra cosa: su ``RelatedManager.set()`` existe **si la
        FK admite nulo**, y entonces anula. Sobre una FK ``null=True`` con
        ``on_delete=CASCADE`` las dos politicas discrepan, y el porte impone la
        de la fuente.
        """
        return getattr(inverse.remote_field, 'on_delete', None) is models.CASCADE

    def __set__(self, instance, value):
        """Asignar el conjunto — ≙ el tramo ``CLEAR``/``SET`` de ``write_real``.

        La fuente los trata juntos (``command[0] in (Command.CLEAR,
        Command.SET)``, ``:1027``): el conjunto queda **exactamente** en las
        lineas dadas, y las que sobran pasan por ``unlink``. ``CLEAR`` es el
        mismo camino con la lista vacia.

        Los otros cinco comandos —``CREATE``, ``UPDATE``, ``DELETE``,
        ``UNLINK``, ``LINK``— no pasan por aqui: en este arbol ``Command`` es
        **ejecutivo** (escribe al llamarlo) en vez de ser un valor diferido que
        el ORM interpreta. Esa divergencia es de la clase entera y esta
        registrada en :ref:`h-api-589` (tarea **#345**), no de este metodo.
        """
        comodel, inverse = self._inverse_field()
        nuevos = list(value or ())
        vivos = [obj.pk for obj in nuevos if obj.pk is not None]
        sobrantes = (comodel._default_manager
                     .filter(**{self.inverse_name: instance})
                     .exclude(pk__in=vivos))
        if self._deletes_the_leftover(inverse):
            sobrantes.delete()
        else:
            sobrantes.update(**{inverse.attname: None})
        for obj in nuevos:
            setattr(obj, self.inverse_name, instance)
            obj.save(update_fields=[inverse.attname])

    def __repr__(self):
        return (f'One2many({self.comodel_name!r}, {self.inverse_name!r})')



#: El permiso del comodelo no se aplica al atravesar este campo — ≙
#: ``_Relational.bypass_search_access`` (``odoo19c:
#: odoo/orm/fields_relational.py:39``), con su comentario verbatim: *"whether
#: access rights are bypassed on the comodel"*.
#:
#: Lo consume ``domains._optimize_any_with_rights``: un ``any`` sobre un campo
#: que lo declara se reescribe a ``any!``, la forma que salta el permiso, y de
#: ahí cuelga el resto de la cadena — ``_optimize_m2o_bypass_comodel_id_lookup``
#: sólo actúa sobre los que llevan ``!``.
#:
#: **Se declara sobre las clases de campo de Django y no se consulta con un
#: ``getattr`` de respaldo.** Es la misma decisión que la fuente toma al
#: ponerlo en ``_Relational`` y no en ``Field``: un campo escalar **no** lo
#: tiene, y preguntárselo tiene que ser un error y no un ``False`` silencioso.
#: Un respaldo haría indistinguible *"este campo no lo concede"* de *"a este
#: campo la pregunta no le aplica"*.
#:
#: Va sobre la clase porque **759** declaraciones del árbol lo necesitarían:
#: 690 pasan por la fábrica ``fields.Many2one`` y 69 son ``models.ForeignKey``
#: directas (medido con ``grep -rhoP`` sobre ``src/`` y ``addons/``). Marcarlo
#: sólo en la fábrica dejaría a esas 69 sin el atributo, que es justo el
#: agujero que el párrafo anterior prohíbe. Es un atributo **nuevo**: no
#: sobreescribe nada de Django, así que no puede alterar su comportamiento.
models.ForeignKey.bypass_search_access = False
models.ManyToManyField.bypass_search_access = False


def bypass_search_access(field, flag=True):
    """Declara que el permiso del comodelo no aplica al atravesar ``field``.

    La fuente lo recibe como palabra clave del constructor; aquí se cuelga del
    campo ya construido por la misma razón de forma que ``check_company``: la
    clase del campo es de Django y su constructor no conoce la palabra.

    Es público —sin guion bajo— porque lo llama ``orm.inherits``, que está
    fuera de este módulo: la delegación lo implica (``:257-259`` de la fuente,
    con su comentario *"self.delegate implies self.bypass_search_access"*).
    """
    field.bypass_search_access = bool(flag)
    return field


def _mark_check_company(field, check_company):
    """Marca el campo para que ``BaseModel._check_company`` lo mire.

    ≙ ``_Relational.check_company`` (``odoo19c:
    odoo/orm/fields_relational.py:40``), que allá es un atributo de clase con
    ``False`` por defecto y aquí es un atributo de instancia por la misma
    razón de forma que ``join``: la clase del campo es de Django y no es
    nuestra para declararla.

    El valor **no** llega al constructor de Django — ``ForeignKey`` no lo
    conoce y reventaría—; se cuelga del campo ya construido, que es donde
    ``_check_company`` lo lee al recorrer ``_meta.get_fields()``.
    """
    field.check_company = bool(check_company)
    return field


def Many2many(*args, check_company=False, store=_UNSET, related=None,
              **kwargs):
    """``fields.Many2many`` — el ``ManyToManyField`` de Django, marcable.

    Era un alias pelado (``Many2many = models.ManyToManyField``) y pasa a ser
    despachador por un solo motivo medido: **19** declaraciones de la
    referencia en los addons que este árbol ya tiene la marcan
    ``check_company=True`` (contra 282 ``Many2one`` y 5 ``One2many``), y el
    alias no tenía dónde recibir la palabra clave.

    No lleva ``store=False`` ni ``company_dependent`` — ver el bloque del
    docstring del módulo, que mide por qué ninguno de los dos aplica aquí.
    """
    #: ``:452-458`` — igual que en ``Many2one``: la referencia declara
    #: ``fields.Many2many(related="lead_id.tag_ids", readonly=True)`` sin
    #: comodelo, porque el extremo de la cadena lo determina.
    if store is not _UNSET:
        kwargs['store'] = store
    #: ``compute=`` en un M2M — #313. El bloque de la fuente se aplica igual
    #: que en cualquier otro tipo; lo que cambia es el VOLCADO, no la
    #: declaración: ``orm.models._flush_m2m`` entrega el valor calculado al
    #: manager relacional en vez de asignarlo, porque Django prohíbe el
    #: ``setattr`` sobre el lado directo de un muchos-a-muchos.
    #:
    #: La bandera viaja hasta el bloque de ``precompute``: un M2M no se puede
    #: adelantar al ``INSERT`` —su tabla intermedia necesita el ``pk``—, así
    #: que ahí se apaga con aviso. ``many_to_many=True`` es lo que lo lleva al
    #: derivador, que es la única copia de los tres bloques de la fuente.
    related_attrs = apply_source_defaults(related, kwargs, many_to_many=True)
    #: El tipo se construye SIEMPRE: ``store`` es un atributo del campo, no una
    #: clase distinta (``odoo19c: odoo/orm/fields.py:455``). La forma sin
    #: columna la resuelve la costura —``contribute_to_class`` con
    #: ``private_only``— y no el enrutado de esta fachada.
    args, source_name = _translate_comodel(args)
    field = _mark_check_company(models.ManyToManyField(*args, **kwargs),
                                check_company)
    if source_name is not None:
        field.comodel_name = source_name
    return annotate_related(field, related, related_attrs)


def _comodel_label(to):
    """La etiqueta ``app.Modelo`` del destino de una FK, venga como venga.

    ``registry.many2one_company_dependents`` indexa por ``_meta.label``, así
    que el comodelo hay que guardarlo con esa forma. Django admite el destino
    como cadena (``'base.ResPartner'``), como clase, o como
    ``'self'``; los tres se normalizan aquí para que el catálogo no tenga que
    saber cuál se usó en la declaración.

    ``'self'`` se conserva verbatim: en el momento de construir el campo la
    clase todavía no existe, y quien lo resuelve es la carga del modelo.
    """
    if to is None or isinstance(to, str):
        return to
    return to._meta.label



#: ≙ ``OnDelete`` (``odoo19c: odoo/orm/fields_relational.py:28``) — los tres
#: valores que la fuente admite, y su política en el vocabulario del stack.
#:
#: ``'restrict'`` va a ``models.RESTRICT`` y no a ``models.PROTECT``, y la
#: diferencia no es de estilo: ``RESTRICT`` emite el ``ON DELETE RESTRICT`` de
#: SQL —que es literalmente lo que la palabra de la fuente nombra— mientras que
#: ``PROTECT`` es una guarda de Django en el plano de Python. La fuente vive en
#: el catálogo de PostgreSQL (``:318`` compone su ``ON DELETE`` con este mismo
#: valor), así que la contraparte fiel es la del motor.
ON_DELETE_POLICY = {
    'cascade': models.CASCADE,
    'set null': models.SET_NULL,
    'restrict': models.RESTRICT,
}


def _apply_ondelete(args, kwargs):
    """Resuelve el ``ondelete`` de la fuente: su politica Y su atributo.

    ≙ ``Many2one.setup_nonrelated`` (``odoo19c: :268-295``), con sus tres casos
    portados verbatim:

    1. sin ``ondelete`` declarado → ``'restrict' if required else 'set null'``
       (``:282``);
    2. ``'set null'`` sobre un campo requerido → ``ValueError`` (``:283-288``);
    3. ``'restrict'`` hacia un modelo de :data:`~orm.fields.IR_MODELS` →
       ``ValueError`` (``:289-294``).

    **El MOMENTO diverge, y la divergencia es del stack.** La fuente resuelve en
    ``setup_nonrelated``, una fase de preparación que Django no tiene; su
    ``ForeignKey.__init__`` exige ``on_delete`` posicional, así que aquí la
    resolución ocurre al construir el campo. La política es la misma; lo que
    cambia es cuándo se aplica.

    **La rama de ``is_transient()`` NO se simula.** La fuente la consulta en
    ``:275`` —``if model.is_transient() and not comodel.is_transient()``— y
    necesita el MODELO, que en ``__init__`` todavía no existe: el campo aún no
    se ha asociado a ninguna clase. Un ``Many2one`` declarado en un modelo
    transitorio recibe por tanto el default de la rama no transitoria. Queda
    declarado aquí en vez de inventado, y su cierre es TASK-API-0405.

    Sin ``ondelete`` en ``kwargs`` la función es transparente: los 1868
    ``on_delete=`` del árbol pasan intactos.
    """
    required = not kwargs.get('null', False)
    if 'ondelete' not in kwargs:
        # La fuente resuelve la politica para TODO Many2one en
        # `setup_nonrelated` (`:274-282`), lo declare quien lo declare, y la
        # usa para componer el `ON DELETE` de la FK (`:306`). Asi que el
        # default se aplica tambien aqui — no solo el atributo.
        declared = 'restrict' if required else 'set null'
        if 'on_delete' in kwargs or (len(args) > 1
                                     and not isinstance(args[1], str)):
            # El llamador ya trajo la politica en el vocabulario del stack: son
            # las 1868 declaraciones que el arbol ya tiene, y el segundo
            # posicional de `ForeignKey` es ese mismo `on_delete`. No se pisa;
            # lo que se resuelve es el ATRIBUTO, que allá tambien existiria.
            # El llamador fijo la politica; NO es provisional.
            return args, kwargs, declared, False
        kwargs['on_delete'] = ON_DELETE_POLICY[declared]
        # Provisional: la fuente lo decide en `setup_nonrelated`, donde ya
        # tiene el modelo Y el comodelo. Aqui no hay ninguno de los dos.
        return args, kwargs, declared, True

    declared = kwargs.pop('ondelete')
    from_default = not declared
    if from_default:
        #: ``:282`` — la rama que este momento alcanza. La tercera, la
        #: transitoria de ``:276``, la decide :func:`_setup_nonrelated`
        #: cuando ambas clases existen.
        declared = 'restrict' if required else 'set null'

    if declared == 'set null' and required:
        raise ValueError(
            "The m2o field %s of model %s is required but declares its ondelete "
            "policy as being 'set null'. Only 'restrict' and 'cascade' make "
            "sense." % (kwargs.get('name', '<sin nombre>'),
                        _comodel_label(args[0]) if args else '<sin comodelo>')
        )

    #: ``:289`` verbatim — la fuente compara la CADENA declarada contra
    #: :data:`~orm.registry.IR_MODELS`, sin resolver el modelo: ``comodel_name``
    #: allá es siempre el ``_name`` punteado, porque es el único vocabulario que
    #: existe. Aquí el destino llega como esa misma cadena o como la clase ya
    #: cargada, así que la clase se reduce a su ``_name`` con
    #: :func:`~orm.registry.name_of`, que lee ``__dict__['_name']`` — un solo
    #: vocabulario, como la fuente.
    comodel = args[0] if args else None
    if comodel is None or isinstance(comodel, str):
        comodel_name = comodel
    else:
        comodel_name = name_of(comodel)
    if declared == 'restrict' and comodel_name in IR_MODELS:
        raise ValueError(
            f"Field is defined as ondelete='restrict' while having "
            f"{comodel_name} as comodel, the 'restrict' mode is not supported "
            f"for this type of field as comodel."
        )

    try:
        kwargs['on_delete'] = ON_DELETE_POLICY[declared]
    except KeyError:
        raise ValueError(
            f"ondelete={declared!r} no es uno de los tres valores que la "
            f"fuente admite: {sorted(ON_DELETE_POLICY)}"
        ) from None
    return args, kwargs, declared, from_default


def _setup_nonrelated(field, model):
    """El tercer caso del default de ``ondelete`` — ≙ ``setup_nonrelated``
    (``odoo19c: odoo/orm/fields_relational.py:267-282``).

    La fuente decide la politica de borrado en una FASE, no en el sitio de
    declaracion, y por eso puede preguntar por las dos clases::

        if model.is_transient() and not comodel.is_transient():
            # "Many2one relations from TransientModel Model are annoying
            #  because they can block deletion due to foreign keys. So unless
            #  stated otherwise, we default them to ondelete='cascade'."
            self.ondelete = 'cascade' if self.required else 'set null'
        else:
            self.ondelete = 'restrict' if self.required else 'set null'

    Solo corre cuando la politica salio del DEFAULT. Con ``ondelete``
    declarado —o con el ``on_delete`` de Django en la llamada— la fuente
    tampoco entra: su guarda es ``if not self.ondelete`` (``:273``).
    """
    if not is_transient(model) or model._meta.abstract:
        #: ``:276`` pregunta por el modelo ANTES que por el comodelo, asi que
        #: un modelo persistente no paga ninguna resolucion. Y un abstracto no
        #: tiene tabla: su politica la decide la concreta que lo herede.
        return
    comodel = field.remote_field.model
    if isinstance(comodel, str):
        #: Comodelo diferido. El stack trae hecha la fase que hace falta:
        #: ``lazy_related_operation`` agenda la funcion *"once `model` and all
        #: `related_models` have been imported and registered with the app
        #: registry"* (``django/db/models/fields/related.py``), que es lo que
        #: ``setup_nonrelated`` garantiza alla. No se construye nada.
        lazy_related_operation(
            lambda _model, _comodel, field=field: _decide_transient_ondelete(
                field, _comodel),
            model, comodel)
        return
    _decide_transient_ondelete(field, comodel)


def _decide_transient_ondelete(field, comodel):
    """La rama ``:276-279``, ya con las dos clases resueltas."""
    if is_transient(comodel):
        #: El ``else`` de ``:282``: wizard hacia wizard no es el caso molesto
        #: que el comentario de la fuente describe. La politica que dejo el
        #: default al construir ya es la correcta.
        return
    required = not field.null
    declared = 'cascade' if required else 'set null'
    field.ondelete = declared
    field.remote_field.on_delete = ON_DELETE_POLICY[declared]


def _is_source_name(value):
    """¿La cadena es un ``_name`` de la fuente, y no una etiqueta de Django?

    El discriminador es la caja, y está medido, no supuesto: los **224**
    ``_name`` del árbol son todos minúsculas, y **549** de las **580** llamadas
    con cadena literal declaran la etiqueta de Django con mayúscula en su
    segmento de modelo (``base.ResPartner``, ``account.AccountAccount``). Un
    nombre sin punto —``'self'``, el constante recursivo de Django— no es
    ninguno de los dos y sale por aquí sin tocarse.

    *Ciega a:* una etiqueta de Django escrita en forma ``label_lower``
    (``'base.respartner'``), que es legal para Django y este discriminador
    leería como ``_name``. **NO es hipotética, y no es una: son 41** — medidas
    por AST sobre ``src/``, resolubles con ``apps.get_model``, repartidas en
    **31 archivos de migración** y 3 fuera. Son legítimas: el estado de una
    migración rechaza la referencia a la clase (*"Model fields in
    ModelState.fields cannot refer to a model class"*), así que la cadena en
    minúsculas es el único camino que le queda. Por eso el discriminador de
    caja no decide solo: :func:`_deferred_comodel` pregunta después si Django
    puede resolver la cadena, y si puede la devuelve intacta.

    Los dos vocabularios **no se solapan hoy**: de las 41, **0** son además un
    ``_name`` de la fuente, así que el orden de las dos consultas de
    :func:`_deferred_comodel` no desempata nada. El día que una cadena sea las
    dos cosas, el orden pasa a ser una decisión y no un detalle.

    *Métrica:* llamadas a ``Many2one`` con primer argumento constante de
    cadena, recorridas por AST sobre ``src/`` y ``addons/`` — **549** etiquetas
    con mayúscula, **27** ``'self'``, **4** en minúsculas con un punto, **0**
    en minúsculas con dos o más. El censo por línea que precedió a este medía
    14 valores y no vio la de la migración (M20 del banco).
    """
    return '.' in value and value == value.lower()


def _translate_comodel(args):
    """Sustituye el ``_name`` punteado del primer posicional, si lo es.

    Comparten mecanismo ``Many2one`` y ``Many2many``: los dos acaban en un
    campo relacional de Django que resuelve su destino por
    ``lazy_related_operation`` (``related.py:80-86``), así que el nombre
    punteado les rompe igual y el asa los arregla igual. **No** lo comparte
    ``One2many``, que resuelve con ``apps.get_model(self.comodel_name)``
    (:func:`_one2many_comodel`) — otro mecanismo, otro puerto, sucesor
    declarado.

    Devuelve ``(args, source_name)``; ``source_name`` es ``None`` cuando no
    había nada que traducir.
    """
    if args and isinstance(args[0], str) and _is_source_name(args[0]):
        return (_deferred_comodel(args[0]),) + args[1:], args[0]
    return args, None


def _deferred_comodel(comodel):
    """Lo que se le entrega a Django en lugar del ``_name`` punteado.

    Dos caminos, uno por orden de declaración, y cada uno con su anulación:

    - **destino-primero** — el ``_name`` ya está en el registro, así que se
      entrega su **etiqueta** de Django y éste resuelve en el acto
      (``apps/registry.py:417-426``, rama ``else``). Nada queda pendiente.

    Siempre se devuelve una **cadena**, nunca la clase, y no es cosmético: el
    estado de una migración la rechaza — *"Model fields in ModelState.fields
    cannot refer to a model class"* (``django/db/migrations/state.py``) —, y
    una migración de este árbol declara sus dos campos por cadena justo por
    eso.
    - **referente-primero y auto-referencia** — el destino todavía no existe,
      así que se entrega la etiqueta centinela; la resolución la hace
      :func:`~orm.registry.flush_sentinel` cuando el destino emita
      ``class_prepared``.

    Una clase registrada con ``register_abstract`` no tiene ``_meta`` y no
    puede ser destinataria de una clave foránea: para ella también vale el
    centinela, que nunca resolverá — es el caso que el check de existencia
    porta como sucesor, no un silencio.
    """
    registered = model_by_name(comodel)
    if registered is not None and getattr(registered, '_meta', None) is not None:
        return registered._meta.label_lower
    if comodel.count('.') == 1:
        # Segunda vía del destino-primero: la cadena puede ser ya la etiqueta
        # de Django de un modelo cargado —que es como una **migración** tiene
        # que nombrarlo— y entonces no hay nada que traducir.
        # ``require_ready=False`` porque en Fase 2 ``models_ready`` aún es
        # False y el modelo ya está registrado.
        try:
            apps.get_model(comodel, require_ready=False)
        except (LookupError, ValueError):
            # silent OK because la excepcion ES la respuesta: no hay modelo de
            # Django con esa etiqueta, asi que la cadena es un ``_name`` de la
            # fuente y sigue al centinela. Propagarla convertiria una pregunta
            # en un fallo.
            pass
        else:
            return comodel
    return sentinel_label(comodel)


def Many2one(*args, store=_UNSET, company_dependent=False,
             check_company=False, related=None, **kwargs):
    """``fields.Many2one`` — ≙ el de la referencia: con columna, sin ella o por empresa.

    ``store=True`` (el defecto, y el de todos los usos previos del árbol)
    devuelve un ``models.ForeignKey`` con la firma de Django, exactamente como
    antes: el alias sigue siendo transparente para quien no nombra ``store``.

    ``store=False`` construye **el mismo** ``models.ForeignKey``: ``store`` es un
    atributo del campo, no un tipo distinto. Quien lo deja sin columna es la
    costura, que lo contribuye con ``private_only=True`` — no genera migración
    ni aparece en ``_meta.concrete_fields``, que es lo que la referencia promete
    con un ``compute`` sin ``store``.

    Y **sin comodelo declarado** —la forma que la referencia usa con
    ``related=``— el campo se construye contra su propio modelo con
    ``DO_NOTHING``, y ``_field_setup_related`` lo reapunta al destino real al
    cerrar el ``setup``. Ver el comentario de esa rama, con la sonda que la
    mide.

    ``company_dependent=True`` — el destino depende de la empresa
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tercera rama, con la firma de la fuente::

        property_account_payable_id = fields.Many2one(
            'account.account', company_dependent=True)

    Es **el tipo más usado** de la referencia con esa palabra clave: 35 de las
    54 declaraciones de producto (``odoo19c``, medido por AST). Devuelve un
    :class:`~orm.fields_company_dependent.CompanyDependent` de
    ``base_type='many2one'``, cuya columna guarda ``{empresa: id}``.

    **Deja de haber FK real, y eso es del mecanismo, no de la adaptación.**
    Allá pasa igual: el valor vive dentro del ``jsonb``, así que el catálogo de
    claves foráneas de PostgreSQL no ve la referencia y nadie la protege con
    ``ON DELETE``. Por eso la fuente lleva un índice propio —
    ``Registry.many2one_company_dependents``, portado en
    ``orm/registry.py``— y por eso el comodelo se guarda en el campo: es lo
    único que queda para responder *"¿quién apunta a este modelo?"*.

    Los argumentos que sólo tienen sentido en una FK real —``on_delete``,
    ``related_name``— se descartan aquí: sin FK no hay nada que cascadear ni
    accesor inverso que nombrar. Descartarlos en silencio sería el defecto que
    ``porte-completo-no-parcial.md`` prohíbe, así que quedan declarados.
    """
    #: ``:452-458`` — con ``related=`` y sin columna, el comodelo sobra: el
    #: extremo de la cadena lo determina, y así lo declara la referencia
    #: (``fields.Many2one(related='product_id.categ_id')``, sin comodelo).
    #: El centinela distingue «no declaró store» de «lo declaró True», que un
    #: default literal no puede.
    if store is not _UNSET:
        kwargs['store'] = store
    related_attrs = apply_source_defaults(related, kwargs,
                                         company_dependent=company_dependent)
    has_column = related_attrs['store']

    if company_dependent:
        to = args[0] if args else kwargs.pop('to', None)
        resto = args[1:]                       # el ``on_delete`` posicional
        if to is None:
            raise ValueError(
                'un Many2one dependiente de empresa necesita su modelo '
                'destino: es lo único que queda para indexarlo, porque el '
                'jsonb no deja FK que el catálogo pueda seguir.')
        for solo_fk in ('on_delete', 'related_name', 'limit_choices_to',
                        'to_field', 'db_constraint'):
            kwargs.pop(solo_fk, None)
        if resto:
            # ``Many2one('x', models.CASCADE)`` — el segundo posicional es el
            # ``on_delete`` de Django, que aquí tampoco tiene destinatario.
            resto = ()
        return _mark_check_company(
            CompanyDependent(*resto, base_type='many2one',
                             comodel=_comodel_label(to), **kwargs),
            check_company)
    args, kwargs, resolved_ondelete, ondelete_from_default = \
        _apply_ondelete(args, kwargs)
    # DESPUES de ``_apply_ondelete``, y no antes: su guarda de ``:289`` compara
    # la CADENA declarada contra ``IR_MODELS``, que lleva los ``_name`` de la
    # fuente. Traducir primero la dejaria sin nada que comparar.
    args, source_name = _translate_comodel(args)
    if not has_column:
        #: **Sin columna NO hay clave foránea, así que NO hay política que
        #: aplicar** — y la que el campo hereda de :func:`_apply_ondelete` no es
        #: inocua: es ``SET_NULL`` para todo ``null=True``, y el recolector de
        #: ``delete()`` de Django sólo omite ``DO_NOTHING``
        #: (``django/db/models/deletion.py``: la rama que salta el campo es
        #: ``if field.remote_field.on_delete is DO_NOTHING``). Con cualquier
        #: otra política el recolector recorre el campo y manda a emitir un
        #: ``UPDATE`` sobre una columna que no existe.
        #:
        #: Medido, y el par discrimina: con ``SET_NULL`` borrar un ``res.country``
        #: aborta con ``FieldError: Cannot update model field <ForeignKey:
        #: country> (only concrete fields are permitted)``
        #: (``deletion.py:489 delete`` → ``query.py:1274 update``); con
        #: ``DO_NOTHING`` el mismo borrado sobrevive. Sondas
        #: ``probe_column_less_fk_with_set_null_breaks_country_delete`` y
        #: ``probe_column_less_fk_with_do_nothing_survives_country_delete``,
        #: evidencia ``scripts/evidence/ranuras2-2026-09-12T08-12-46-00{2,3}.log``.
        #:
        #: La política DECLARADA no se pierde: ``field.ondelete`` conserva el
        #: ``resolved_ondelete`` unas líneas más abajo, que es el atributo que la
        #: fuente expone y que leen ``ir.model.fields``, ``_check_inherits`` y el
        #: One2many inverso. Lo que cambia es sólo el recorrido del recolector de
        #: Django, que es un mecanismo que la fuente no tiene.
        #:
        #: ``related=`` sin destino añade su propio marcador: la referencia lo
        #: declara así —``fields.Many2one(related='product_id.categ_id')``—
        #: porque el extremo de la cadena determina el comodelo. Django exige
        #: ``to`` posicional, así que el campo se construye apuntando a su propio
        #: modelo y ``_field_setup_related`` lo reapunta al destino real al
        #: cerrar el ``setup``. Medido en ``probe_relational_related_without_to``.
        if not args and 'to' not in kwargs:
            args = ('self',)
        elif len(args) > 1:
            # ``Many2one('x', models.CASCADE)`` — el segundo posicional ES el
            # ``on_delete`` de Django, y se descarta para que el kwarg mande.
            args = args[:1]
        kwargs['on_delete'] = models.DO_NOTHING
    field = _mark_check_company(models.ForeignKey(*args, **kwargs),
                                check_company)
    # El atributo SOBREVIVE a la construccion, y no es cosmetico: la fuente lo
    # LEE desde cuatro sitios ademas de la FK — `ir.model.fields` lo refleja a
    # su columna `on_delete` (`odoo19c: ir_model.py:1164`), `_check_inherits`
    # exige `cascade` en un campo `delegate` (`model_classes.py:465`), un
    # One2many consulta el de su inverso (`fields_relational.py:987`), y la
    # suite del ORM afirma sobre el directamente
    # (`test_orm/tests/test_fields.py:4230-4256`, cuatro casos). Un porte que
    # solo tradujera el kwarg dejaria ciegos a los cuatro.
    field.ondelete = resolved_ondelete
    if ondelete_from_default:
        #: El gancho que :func:`~orm.fields._field_contribute_to_class` invoca
        #: cuando la clase ya existe. Se cuelga SOLO si la politica salio del
        #: default: su presencia ES la guarda ``if not self.ondelete`` de
        #: ``:273``, que aqui no se puede expresar dejando el atributo vacio
        #: porque Django exige ``on_delete`` posicional al construir la FK.
        field.setup_nonrelated__ = _setup_nonrelated
    if source_name is not None:
        # ``comodel_name`` es el atributo que la fuente declara
        # (``odoo19c: odoo/orm/fields_relational.py:36``) y el unico sitio donde
        # el nombre punteado sobrevive: lo que Django guarda en
        # ``remote_field.model`` es el asa, hasta que se resuelve a la clase.
        field.comodel_name = source_name
    return annotate_related(field, related, related_attrs)


def _many2one_join(self, model, alias, query):
    """``join`` — añade el LEFT JOIN de este Many2one y devuelve (modelo, alias).

    ≙ ``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466-478``).
    Es lo que ``BaseModel._traverse_related_sql`` invoca en cada salto de un
    camino relacional: sin él, un campo delegado no se puede resolver a SQL.

    La condición ON se compone con ``model._field_to_sql(alias, self.name,
    query)`` —el mismo punto de entrada que la fuente usa— para que la columna
    del lado izquierdo salga del mismo sitio que cualquier otra, con su
    comprobación de acceso incluida.

    Divergencias de nombre, las dos mecánicas: el comodelo se obtiene de
    ``self.related_model`` en vez de ``model.env[self.comodel_name]`` —Django
    ya lo tiene resuelto en el campo—, y su tabla de ``_meta.db_table`` en vez
    de ``_table``.
    """
    comodel = self.related_model
    coalias = query.make_alias(alias, self.name)
    query.add_join('LEFT JOIN', coalias, comodel._meta.db_table, SQL(
        "%s = %s",
        model._field_to_sql(alias, self.name, query),
        SQL.identifier(coalias, 'id'),
    ))
    return (comodel, coalias)


models.ForeignKey.join = _many2one_join



############################################################################
#
# El inverso en caché — ≙ ``odoo19c: odoo/orm/fields_relational.py:81,322,564``
#
# Cuando se escribe un lado de una relación, el **otro** lado que ya está en
# caché queda obsoleto. ``_update_inverse`` es quien lo pone al día, y lo
# consume ``Cache.patch`` (``orm/environments.py``). Vive aquí y no en
# ``orm/fields.py`` porque su base es ``_Relational`` — la fuente sólo lo
# declara para campos relacionales, y el genérico levanta ``NotImplementedError``.
#
# Divergencia de mecanismo, la misma de toda esta familia y por tanto declarada
# una vez: el entorno es **ambiental** (``orm.environments.env()``) en vez de
# ``records.env``; no hay recordset, así que ``records._ids`` es
# :func:`~orm.utils.record_ids` y ``record.id`` es :func:`single_record_id`.
#
############################################################################


def single_record_id(records):
    """El id de una fila única — la adaptación de ``BaseModel.id``.

    ≙ ``Id.__get__`` (``odoo19c: odoo/orm/fields_misc.py:103-114``): vacío
    devuelve ``False``, uno devuelve su id, y más de uno es un error de
    programación (*"Expected singleton"*). Se porta ese contrato tal cual.

    Admite además un id **suelto** —entero o :class:`~orm.identifiers.NewId`—
    y es una divergencia que hay que declarar, no un atajo. La fuente envuelve
    el id en un recordset (``comodel.browse(new_id)``) sólo para tener algo con
    ``.id``, y eso allá no consulta nada. Aquí :func:`~orm.utils.browse` **es
    una consulta**, y un ``NewId`` no tiene fila que traer: el envoltorio
    volvería vacío y el id se perdería en silencio. Por eso el id viaja crudo
    desde ``Cache.patch`` y se normaliza en este punto.
    """
    if isinstance(records, (int, NewId)):
        return records
    ids = record_ids(records)
    if not ids:
        return False
    if len(ids) == 1:
        return ids[0]
    raise ValueError("Expected singleton: %s" % (records,))


def _relational_update_inverse(self, records, value):
    """≙ ``_Relational._update_inverse`` (``:81``).

    Docstring de la fuente: *"Update the cached value of ``self`` for
    ``records`` with ``value``."* El genérico no sabe hacerlo — cada forma de
    relación guarda su caché distinta— así que declara el contrato y delega en
    la subclase. Se porta el ``raise`` verbatim: es lo que hace observable que
    a un tipo relacional nuevo le falta su implementación, en vez de que herede
    la del uno-a-muchos y corrompa la caché en silencio.
    """
    raise NotImplementedError


def _many2one_convert_to_cache(self, value, record, validate=True):
    """``Many2one.convert_to_cache`` — ≙ ``:328-351``. Formato: id o ``None``.

    Las cinco ramas de la fuente, con una divergencia de forma y un bloqueo
    medido:

    - ``isinstance(value, BaseModel)`` se abre aquí a **instancia o
      ``QuerySet``**, que son las dos formas en que este árbol representa un
      conjunto de filas, y el modelo se compara con
      :func:`~orm.utils.model_of` en vez de con ``value._name``.
    - la rama de ``dict`` **no se porta**: la fuente construye un registro
      virtual con ``comodel.new(value, origin=…)`` y ``BaseModel.new`` no
      existe todavía en este árbol (``src/orm/models.py:376`` declara que su
      equivalente es ``Model(**valores)``, sin registro que devuelva la fila
      por su ``NewId``). Emitir sólo el ``NewId`` y descartar las demás claves
      del ``dict`` sería un porte generoso —el método existiría sin hacer lo
      que hace el de la fuente—, así que levanta ``NotImplementedError`` y su
      sucesor está registrado como la tarea **#327**.

    La guarda final es la que da sentido a ``delegate``: si **todas** las filas
    son nuevas, el padre al que delegan también lo es, y su id se envuelve en
    un :class:`~orm.identifiers.NewId`.
    """
    if type(value) is int or type(value) is NewId:
        id_ = value
    elif isinstance(value, (models.Model, models.QuerySet)):
        ids = record_ids(value)
        if validate and (model_of(value) is not self.related_model or len(ids) > 1):
            raise ValueError("Wrong value for %s: %r" % (self, value))
        id_ = ids[0] if ids else None
    elif isinstance(value, tuple):
        # el valor es un par (id, nombre), o una tupla de ids
        id_ = value[0] if value else None
    elif isinstance(value, dict):
        raise NotImplementedError(
            "%s.convert_to_cache no admite un dict: la fuente construye el "
            "registro virtual con comodel.new(), que este arbol todavia no "
            "tiene (tarea #327)" % (self.name,)
        )
    else:
        id_ = None

    if self.delegate and record and not any(record_ids(record)):
        # si todas las filas son nuevas, el padre tambien lo es
        id_ = id_ and NewId(id_)

    return id_


def _many2one_convert_to_display_name(self, value, record):
    """``Many2one.convert_to_display_name`` — ≙ ``:397-398``.

    La fuente escribe ``return value.display_name`` sin guarda, porque allá un
    ``Many2one`` vacío es un **conjunto vacío** y su ``display_name`` ya vale
    ``False``. Aquí una FK vacía es ``None``, que no tiene atributo alguno: la
    guarda ``if value else False`` es la traducción de esa semántica, no un
    añadido — devuelve el mismo ``False`` que la fuente para el campo vacío, y
    ``_compute_display_name`` lo distingue.

    ``Reference`` comparte cuerpo en la fuente (``:1101``); aquí lo hereda por
    la adjunción a ``models.ForeignKey``, de la que ``OneToOneField`` desciende.
    """
    return display_name_of(value) if value else False


def _relational_multi_convert_to_display_name(self, value, record):
    """``_RelationalMulti.convert_to_display_name`` — ≙ ``:714-715``.

    Verbatim de la fuente, ``raise NotImplementedError()``: un ``_rec_name``
    que nombre una colección no tiene etiqueta única, y devolver algo inventado
    escondería el error de declaración. El mensaje se añade porque el nuestro
    no tiene el ``repr`` del campo en el traceback de la fuente.
    """
    raise NotImplementedError(
        f'convert_to_display_name no aplica a {self!r}: una coleccion no '
        f'tiene etiqueta unica')


def _many2one_update_inverse(self, records, value):
    """``Many2one._update_inverse`` — ≙ ``:322-324``.

    El uno-a-uno del lado muchos: el valor se convierte al formato de caché
    **por fila**, porque :meth:`convert_to_cache` consulta la propia fila para
    decidir si el id del padre delegado es nuevo.
    """
    for record in records:
        self._update_cache(
            record, self.convert_to_cache(value, record, validate=False))


def _relational_multi_update_inverse(self, records, value):
    """``_RelationalMulti._update_inverse`` — ≙ ``:564-573``.

    Suma ``value`` al valor en caché de cada fila. Las dos aserciones de la
    fuente se portan verbatim porque son el contrato del método: sólo opera
    sobre **ids nuevos** sobre **filas nuevas** — un id real se escribe por la
    vía normal, no parcheando la caché.

    Cuando la fila todavía no tiene valor en caché, el id no se puede sumar a
    nada: se apunta en ``field_data_patches`` de la transacción y lo aplicará
    :func:`_relational_multi_update_cache` cuando el valor llegue.
    """
    new_id = single_record_id(value)
    assert not new_id, "Field._update_inverse solo admite un id nuevo"
    env = get_environment()
    field_cache = self._get_cache(env)
    for record_id in record_ids(records):
        assert not record_id, "Field._update_inverse solo admite filas nuevas"
        cache_value = field_cache.get(record_id, SENTINEL)
        if cache_value is SENTINEL:
            env.transaction.field_data_patches[self][record_id].append(new_id)
        else:
            field_cache[record_id] = tuple(unique(cache_value + (new_id,)))


def _relational_multi_update_cache(self, records, cache_value, dirty=False):
    """``_RelationalMulti._update_cache`` — ≙ ``:576-586``.

    Drena los parches que :func:`_relational_multi_update_inverse` dejó
    pendientes: los ids apuntados se suman al valor que se está escribiendo,
    en ese orden y sin repetir.

    ``models.Field._update_cache`` se resuelve **en tiempo de llamada**, no al
    importar: ``orm/fields.py`` instala el método base al final de su propio
    módulo y es él quien importa a éste (``orm/fields.py:84``), así que al
    ejecutarse estas líneas de módulo el atributo todavía no existe. Es el
    ``super()`` de la fuente escrito de la única forma que el orden de carga
    admite.
    """
    field_patches = get_environment().transaction.field_data_patches.get(self)
    if field_patches and records is not None:
        for record in records:
            ids = field_patches.pop(record.pk, ())
            if ids:
                value = tuple(unique(itertools.chain(cache_value, ids)))
            else:
                value = cache_value
            models.Field._update_cache(self, record, value, dirty)
        return
    models.Field._update_cache(self, records, cache_value, dirty)


#: ``delegate`` — ≙ ``Many2one.delegate`` (``:248``), *"whether self implements
#: delegation"*. Va sobre la clase por la misma razón que
#: ``bypass_search_access``: el atributo tiene que existir en las 759
#: declaraciones del árbol, pasen o no por la fábrica. Lo enciende
#: ``orm.inherits.apply_inherits`` sobre el campo concreto, que es el
#: equivalente del ``_setup_attrs__`` de la fuente (``:255-259``).
models.ForeignKey.delegate = False

RelatedField._update_inverse = _relational_update_inverse
models.ForeignKey.convert_to_cache = _many2one_convert_to_cache
models.ForeignKey.convert_to_display_name = _many2one_convert_to_display_name
models.ForeignKey._update_inverse = _many2one_update_inverse
models.ManyToManyField._update_inverse = _relational_multi_update_inverse
models.ManyToManyField._update_cache = _relational_multi_update_cache
models.ManyToManyField.convert_to_display_name = (
    _relational_multi_convert_to_display_name)

#: ``One2many`` **no recibe estos métodos**, y es una ausencia declarada, no un
#: olvido: aquí es una clase plana (:class:`One2many`, arriba) que describe el
#: reverso de una FK, no un ``models.Field``, así que no participa de la caché
#: de campo ni tiene dónde colgarlos. En la fuente sí es un ``_RelationalMulti``
#: y los hereda. Su desenlace va con el porte del lado SQL del uno-a-muchos —
#: tareas **#243** y **#244**.


class PrefetchMany2one(collections.abc.Reversible):
    """Los valores de un ``Many2one`` sobre el conjunto de prelectura.

    ≙ ``PrefetchMany2one`` (``odoo19c: odoo/orm/fields_relational.py:1734-1754``).
    Docstring de la fuente: *"Iterable for the values of a many2one field on
    the prefetch set of a given record."*

    Recorre los ids del conjunto de prelectura del registro, toma de la caché
    del campo el id relacionado de cada uno, **descarta** el que no tenga valor
    cacheado y **deduplica** conservando el orden — eso último lo aporta
    :func:`~tools.misc.unique`.

    **Divergencia de mecanismo:** la fuente pide la caché con
    ``self.field._get_cache(self.record.env)``, donde ``env`` es un
    ``__slots__`` del recordset; aquí una fila es una instancia de Django y el
    entorno es ambiente, así que se toma con
    :func:`~orm.environments.env`. Es la misma adaptación de
    :class:`~orm.models.RecordCache`.

    **Su consumidor real todavía no existe, y está medido.** ``_prefetch_ids``
    es el tercer ``__slots__`` del recordset de la fuente
    (``odoo19c: odoo/orm/models.py:362``), y este árbol no tiene recordset: 0
    apariciones del nombre en ``src/``. La clase se porta entera contra ese
    protocolo —lo único que consulta del registro es ese atributo— y el lote de
    prelectura que lo poblará es la tarea **#306**.
    """

    __slots__ = ('field', 'record')

    def __init__(self, record, field):
        self.record = record
        self.field = field

    def __iter__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid for id_ in self.record._prefetch_ids
            if (coid := field_cache.get(id_)) is not None
        )

    def __reversed__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid for id_ in reversed(self.record._prefetch_ids)
            if (coid := field_cache.get(id_)) is not None
        )


class PrefetchX2many(collections.abc.Reversible):
    """Los valores de un campo x2many sobre el conjunto de prelectura.

    ≙ ``PrefetchX2many`` (``odoo19c: odoo/orm/fields_relational.py:1757-1779``).
    Docstring de la fuente: *"Iterable for the values of an x2many field on the
    prefetch set of a given record."*

    Es la hermana de :class:`PrefetchMany2one` con una diferencia: la caché de
    un campo múltiple guarda una **colección** por id, así que el recorrido la
    aplana. El id que no está en caché no aporta nada —``field_cache.get(id_,
    ())``—, y :func:`~tools.misc.unique` deduplica **a través** de las
    colecciones, no dentro de cada una.

    Su divergencia de mecanismo y su bloqueo son los mismos que los de la
    hermana: entorno ambiente, y ``_prefetch_ids`` sin receptor hasta la tarea
    **#306**.
    """

    __slots__ = ('field', 'record')

    def __init__(self, record, field):
        self.record = record
        self.field = field

    def __iter__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid
            for id_ in self.record._prefetch_ids
            for coid in field_cache.get(id_, ())
        )

    def __reversed__(self):
        field_cache = self.field._get_cache(get_environment())
        return unique(
            coid
            for id_ in reversed(self.record._prefetch_ids)
            for coid in field_cache.get(id_, ())
        )


def _many2one_convert_to_column(self, value, record, values=None, validate=True):
    """``Many2one.convert_to_column`` — ≙ ``odoo19c: odoo/orm/fields_relational.py:326-327``.

    ``value or None``: el cero y la cadena vacía de una clave foránea son la
    ausencia de relación, no una fila con ese identificador. La base los
    conservaría —descarta por identidad— y la columna guardaría un ``0`` que no
    apunta a nada.
    """
    return value or None


models.ForeignKey.convert_to_column = _many2one_convert_to_column
