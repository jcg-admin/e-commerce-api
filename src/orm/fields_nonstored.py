"""Campo no persistido — ≙ el ``store=False`` de la referencia.

En Odoo un campo puede declararse **sin columna**: ``fields.Char(store=False,
default=_get_algo)`` produce un atributo que se calcula al leerlo y nunca se
escribe a la base (``odoo19c: account/models/res_currency.py:17`` es el caso
canónico). Django no lo tiene: todo ``models.Field`` es una columna.

Este módulo lo construye. No es una comodidad: sin él, portar
``fiscal_country_codes`` obligaba a inventar una forma distinta —una
``property`` colgada desde otro addon— y a repartir en el cableado lo que la
referencia declara **en la clase**. Es la diferencia entre adaptar la conducta
y copiar una restricción ajena.

Qué NO es
==========

- **No es un campo de Django.** No aparece en ``_meta.get_fields()``, no genera
  migración, no se puede filtrar con ``.filter(campo=…)``. Es exactamente lo
  que la referencia promete con ``store=False``: un valor que existe para
  leerse, no para consultarse.
- **No es una ``property``.** Admite asignación —``obj.campo = 'X'`` se guarda
  en la instancia y gana sobre el ``default``—, igual que en la referencia,
  donde un campo no almacenado sigue siendo escribible en memoria.

Cómo se declara
================

Con la misma firma que la fuente, en el cuerpo de la clase o colgado después::

    fiscal_country_codes = fields.Char(store=False,
                                       default=get_fiscal_country_codes)

El ``default`` puede ser un valor o un invocable. Si es invocable se llama con
la instancia cuando acepta un argumento, y sin argumentos cuando no — así
sirven tanto un cómputo que mira sólo la sesión (``env.companies`` en la
referencia) como uno que mira el registro (``record.company_id or …``).

Este archivo NO existe en la referencia, y ``src/orm`` es una raíz espejada
==========================================================================

Medido contra ``odoo19c: odoo/orm/`` — ``find`` por nombre y ``grep`` por
símbolo, los dos a **0**. La referencia no lo necesita: su ``fields.Char(store=False, ...)`` ya declara un campo sin columna. Este mecanismo existe porque en Django todo ``models.Field`` **es** una columna.

Eso lo hace legítimo como **mecanismo construido**
(``porte-completo-no-parcial.md``: *si el stack no trae el mecanismo, se
construye*) y a la vez lo deja **fuera de sitio**: ``src/orm`` es la raíz
espejada de ``odoo/orm``, y ``atributos-de-clase-de-modelo.md`` §2 manda listar
la raíz de la referencia antes de crear un archivo ahí.

``check_porte_completo`` **no puede verlo**: compara símbolos dentro de un par
de archivos, y un archivo que la referencia no tiene no entra en ninguna
comparación. Cinco archivos de ``src/orm`` están en esta situación —
``checks``, ``fields_nonstored``, ``inherits``, ``method_chain``, ``routers``—
y hasta este pase sólo ``checks`` lo declaraba.

El veredicto por archivo —quedarse aquí con la divergencia declarada, o mudarse
a una raíz propia como ``src/core``— es la tarea **#121**.
"""
import inspect
import types
import warnings

from django.db import models

__all__ = ['NonStored', 'non_stored_fields', 'apply_source_defaults',
           'annotate_related', 'derive_source_attrs']


class NonStored:
    """Descriptor de un campo declarado ``store=False``.

    Sigue el protocolo de ``contribute_to_class`` de Django para que funcione
    en los dos caminos por los que un atributo llega a un modelo: el cuerpo de
    la clase (``ModelBase`` lo invoca) y ``Model.add_to_class`` (el que usan
    las extensiones ``_inherit`` de este puerto). Sin él, el segundo camino
    dejaría el descriptor sin saber su propio nombre.
    """

    def __init__(self, *args, default=None, help_text='', search=None,
                 related=None, verbose_name=None, compute=None, **_ignored):
        self.default = default
        self.help_text = help_text
        #: ≙ ``Field.string`` (``odoo19c: odoo/orm/fields.py:264``) — la
        #: etiqueta. Django la toma del primer posicional, y la fuente la
        #: declara con ``string=``; se conserva por las dos vías para que la
        #: declaración se lea contra la suya sin traducir nada. Un campo sin
        #: columna no la usa para pintar formulario, pero tirarla dejaría al
        #: árbol sin forma de medir cuántos la declaran.
        self.verbose_name = verbose_name if args[:1] == () else args[0]
        #: ≙ ``Field.related`` (``odoo19c: odoo/orm/fields.py:286``) — la ruta
        #: punteada cuyo extremo aporta el valor. Con ella el campo **no lee
        #: su default**: navega la cadena, que es el ``compute`` de la fuente
        #: (``:675`` ``_compute_related``). Es la forma de la gran mayoría de
        #: los ``related=`` que la referencia declara en los addons que este
        #: árbol porta — los que no llevan ``store`` y por tanto no tienen
        #: columna. El reparto lo publica
        #: ``python3 scripts/census_related_fields.py``, que no se transcribe
        #: aquí porque crece con la referencia.
        self.related = related
        #: ≙ ``Field.search`` (``odoo19c: odoo/orm/fields.py:289``): el nombre
        #: de un método o el invocable que sabe traducir una condición sobre
        #: este campo a un dominio sobre campos que sí tienen columna. Sin él
        #: el campo se puede leer y escribir, pero no se puede buscar — que es
        #: exactamente lo que la fuente promete con un campo sin ``search``.
        self.search = search
        #: ≙ ``Field.compute`` (``odoo19c: odoo/orm/fields.py:285``) — «el
        #: nombre de un método o el invocable que calcula el campo». Es la
        #: forma con que la fuente declara la inmensa mayoría de sus campos
        #: sin columna: medido sobre ``addons/*/models/*.py`` y
        #: ``odoo/addons/*/models/*.py`` de ``odoo19c``, **293** declaraciones
        #: de los siete tipos que las fachadas construyen llevan
        #: ``compute=`` y ningún ``store=True``.
        #:
        #: **Lo despacha :meth:`__get__`** desde ``TASK-API-0415``: su
        #: tercera rama llama a ``determine_compute``, que es el cuerpo
        #: efectivo de la rama ``elif self.compute:`` de la fuente para un
        #: campo sin columna. Hasta entonces se guardaba y nadie lo invocaba:
        #: el valor salía de ``related`` o de un ``default`` que envolvía al
        #: cómputo, que es la forma que los dos sitios del árbol declaraban.
        self.compute = compute
        self.name = None

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase en una clase que NO es modelo Django."""
        self.name = name
        _REGISTRY_CACHE.invalidate()

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class``.

        Django llama a este método en vez de ``setattr`` cuando el objeto lo
        declara. Aquí **no** se registra nada en ``_meta``: ese es justamente
        el punto — el campo no tiene columna.
        """
        self.name = name
        setattr(cls, name, self)
        _REGISTRY_CACHE.invalidate()

    # -- protocolo de descriptor -------------------------------------------

    def __get__(self, instance, owner=None):
        """El valor del campo — ≙ ``Field.__get__`` (``odoo19c:
        odoo/orm/fields.py:1642``), en la parte que alcanza a un campo sin
        columna.

        El ORDEN de las cuatro ramas es el de la fuente, no una elección:

        1. **lo escrito gana** — allá ``value = field_cache[record_id]``
           (``:1673``) se intenta antes que cualquier rama de cálculo; aquí el
           ``__dict__`` de la instancia es ese caché;
        2. **``related``** — allá no es una rama aparte: al montar la cadena,
           ``self.compute = self._compute_related`` (``:632``) **sobreescribe**
           el cómputo del autor, así que la cadena gana siempre. Aquí son dos
           ramas porque el descriptor guarda los dos atributos, y el orden
           reproduce esa sobreescritura;
        3. **``compute``** — la rama ``elif self.compute:`` de la fuente
           (``:1736``), cuyo comentario la acota: *"non-stored field or new
           record without origin: compute"*;
        4. **``default``** — el ``else`` final (``:1788-1789``):
           *"non-stored field or stored field on new record: default value"*.

        Las ramas de ``self.store`` de la fuente —traer de la base, traer del
        origen— no se portan **porque no se alcanzan**: un :class:`NonStored`
        es por construcción ``store=False``. No es alcance recortado.
        """
        if instance is None:
            return self
        if self.name in instance.__dict__:
            return instance.__dict__[self.name]
        if self.related:
            return self.resolve_related(instance)
        if self.compute:
            return self.determine_compute(instance)
        return self.resolve_default(instance)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value
        #: ``:632`` — la fuente cablea el inverso **sólo** si el campo no es de
        #: sólo lectura. Un ``related`` sin ``readonly=False`` declarado toma
        #: el defecto de ``:458`` y no propaga: escribirlo se queda en memoria.
        if self.related and not getattr(self, 'readonly', True):
            self.inverse_related(instance, value)

    def inverse_related(self, instance, value):
        """Escribe ``value`` en el extremo de la cadena — ≙
        ``Field._inverse_related`` (``odoo19c: fields.py:724``).

        Este árbol ya tenía ese método portado verbatim, **sobre
        ``models.Field``** (``orm/fields.py:1809``). Un :class:`NonStored` no
        desciende de ``models.Field``, así que nunca lo alcanzaba: un
        ``related`` con ``readonly=False`` aceptaba la escritura y la guardaba
        en sombra sobre el origen. Es la forma de :ref:`h-api-978` otra vez —
        acepta y no hace nada— en el otro sentido de la cadena.

        Dos cosas son verbatim de la fuente, y la segunda no es cosmética:

        - **La guarda de realidad** ``bool(target.id) == bool(record.id)``
          (``:731``), con su comentario: *«update 'target' only if 'record' and
          'target' are both real or both new»*. Un registro sin guardar no
          escribe en uno guardado.
        - **El eslabón vacío no revienta.** Sin destino no hay dónde escribir,
          y eso no es un error — igual que leerlo da vacío.

        Lo que **diverge, y es de mecanismo**: la fuente escribe con
        ``target[field.name] = value``, que en su ORM es un ``write()`` que se
        vacía solo. Aquí hay dos formas según lo que haya al final, porque
        Django las distingue:

        - un **valor**: ``setattr`` + ``save(update_fields=[...])``, la
          escritura mínima;
        - un **manager** del reverso de una FK: Django prohíbe la asignación
          directa y **nombra la salida en su propio error** — ``.set()``. Se
          usa ésa, que es la API que el stack declara para eso.
        """
        target, last_name = self.traverse_related(instance)
        if target is None:
            return
        #: ``:731`` verbatim — ambos reales o ambos nuevos.
        if bool(getattr(target, 'pk', None)) != bool(getattr(instance, 'pk',
                                                             None)):
            return
        held = getattr(type(target), last_name, None)
        if isinstance(held, NonStored):
            #: El extremo es otra proyección: su propio ``__set__`` decide si
            #: la cadena sigue. No se le puede pedir ``update_fields``, que es
            #: cosa de una columna.
            setattr(target, last_name, value)
            return
        current = getattr(target, last_name, None)
        if hasattr(current, 'set'):
            current.set(value)
            return
        setattr(target, last_name, value)
        target.save(update_fields=[last_name])

    def traverse_related(self, instance):
        """El registro anterior al último eslabón, y el nombre de ése — ≙
        ``Field.traverse_related`` (``odoo19c: fields.py:666``).

        Devuelve ``(None, nombre)`` cuando la cadena se corta antes de llegar,
        que es lo que deja al inverso sin destino donde escribir.
        """
        *path, last_name = self.related.split('.')
        target = instance
        for name in path:
            if target is None:
                return None, last_name
            target = getattr(target, name, None)
        return target, last_name

    def __delete__(self, instance):
        instance.__dict__.pop(self.name, None)

    # -- eje de esquema ----------------------------------------------------

    #: ≙ ``Field._column_type`` (``odoo19c: odoo/orm/fields.py:259``), que la
    #: fuente declara ``None`` y expone por la property ``column_type``
    #: (``:781``). Un campo sin columna **no tiene tipo de columna**: es lo
    #: mismo que dice el nombre de esta clase, escrito donde el eje de
    #: esquema lo lee.
    column_type = None

    def update_db(self, model, columns):
        """No hay columna que llevar a la tabla — ≙ el corte de
        ``Field.update_db`` (``odoo19c: odoo/orm/fields.py:1101``).

        La fuente abre con ``if not self.column_type: return False``, así que
        un campo sin columna sale por ahí y **nunca** alcanza los otros cuatro
        del eje (``update_db_column``, ``_convert_db_column``,
        ``update_db_notnull``, ``update_db_related``). Medido sobre todo
        ``odoo19c/odoo``: la única puerta a esa familia es ``update_db``
        (``models.py:3228``); los demás sólo se llaman desde su cuerpo o por
        ``super()`` en una subclase. Por eso aquí se porta **el corte**, no
        los cinco: declararlos sería inventar superficie que la fuente no
        expone por esta vía.

        Se declara en la clase por la misma razón que
        :meth:`inverse_related`: :class:`NonStored` **no desciende de
        ``models.Field``**, así que el enlace que ``orm.fields`` cuelga sobre
        él nunca lo alcanza. Sin este método un campo sin columna respondía
        ``AttributeError`` a una pregunta que la fuente contesta ``False``.
        """
        return False

    # -- protocolo de búsqueda ----------------------------------------------

    #: ``determine_domain`` lo instala :mod:`orm.fields` sobre esta clase, no
    #: se declara aquí: ``orm.fields`` importa a este módulo por la vía de
    #: ``fields_numeric``, así que el import inverso es un ciclo. Es la misma
    #: vía por la que ``type`` y ``relational`` llegan a ``models.Field``, y
    #: por la misma razón: el contrato de la fuente se comparte, la jerarquía
    #: del stack no.

    # -- resolución de la cadena related -----------------------------------

    def resolve_related(self, instance):
        """El valor del extremo de ``self.related``, navegando eslabón a
        eslabón — ≙ ``Field._compute_related`` (``odoo19c: :675``).

        **El eslabón vacío no revienta.** La fuente escribe
        ``next(iter(corecord), corecord)``: sobre un recordset vacío eso
        devuelve el propio vacío y la cadena sigue sin valor. Aquí el análogo
        es que un ``None`` corta el recorrido y el campo lee vacío, que es la
        misma conducta observable — una fila sin país no tiene código de país,
        y eso no es un error.
        """
        value = instance
        for name in self.related.split('.'):
            if value is None:
                return None
            value = getattr(value, name, None)
        return value

    # -- resolución del default --------------------------------------------

    def resolve_default(self, instance):
        """Llama al ``default`` con la instancia sólo si la acepta.

        La referencia pasa siempre ``self`` porque allá el ``default`` es un
        método del modelo. Aquí el mismo cómputo puede ser una función suelta
        que no necesita el registro —el caso de los que sólo miran la sesión—,
        y obligarla a aceptar un parámetro que ignora sería ruido en cada uno.
        Se inspecciona la firma una vez por lectura, que es barato frente a la
        consulta que el propio cómputo hace.
        """
        if not callable(self.default):
            return self.default
        try:
            firma = inspect.signature(self.default)
        except (TypeError, ValueError):
            # Invocable sin firma introspectable (builtin, C-extension): se
            # llama sin argumentos, que es la forma más común de ese caso.
            return self.default()
        if len(firma.parameters) >= 1:
            return self.default(instance)
        return self.default()


#: Centinela de «el declarante no dijo nada». Lo usan las fachadas en la firma
#: de su parámetro ``store=``: un ``store=None`` declarado y un ``store``
#: ausente tienen que distinguirse, y un default literal no los separa.
_UNSET = object()


#: Las claves del vocabulario de la fuente que un declarante puede pasar por
#: ``kwargs``. Se enumeran para saber CUÁLES declaró: la derivación añade
#: defaults, y sin la lista no habría cómo distinguir «el autor lo escribió»
#: de «el bloque lo dedujo» — que es lo que :func:`annotate_related` necesita
#: para no colgar un atributo de instancia por cada clave sobre un campo llano.
SOURCE_VOCABULARY_KEYS = frozenset({
    'compute', 'inverse', 'recursive', 'precompute', 'compute_sudo',
    'related_sudo', 'readonly', 'store', 'copy', 'related',
})


def derive_source_attrs(attrs, many_to_many=False, field_label=''):
    """Los tres bloques de derivación de la fuente, sobre ``attrs``, en su orden.

    ≙ ``odoo19c: odoo/orm/fields.py:443-465``. Es **una sola copia**, y ése es
    el punto: la tenían duplicada :func:`apply_source_defaults` —que deriva en
    el sitio de declaración— y ``_field_get_attrs`` de :mod:`orm.fields` —que
    deriva tras fusionar la cadena de la MRO—. Los dos momentos hacen falta:
    un campo suelto responde ``field.store`` antes de contribuir a ninguna
    clase, y una redeclaración sólo se puede corregir después de fusionar. Lo
    que no hacía falta eran dos cuerpos que se pudieran separar.

    Vive en este módulo, y no en :mod:`orm.fields` donde la fuente lo pone,
    porque la dirección de import ya está fijada: ``fields`` importa de aquí
    (``orm/fields.py:85``) y la vuelta sería un ciclo. Es la misma divergencia
    de sitio que este archivo entero declara (tarea **#291**).

    :param attrs: el diccionario con **lo que el declarante escribió**. Se
        muta en el sitio, igual que allá.
    :param many_to_many: el tercer caso de ``precompute``, que es nuestro y es
        de stack.
    :param field_label: qué campo nombra el aviso; vacío en el sitio de
        declaración, donde el campo aún no tiene nombre.
    """
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
        suffix = f' {field_label}' if field_label else ''
        if not attrs.get('compute') and not attrs.get('related'):
            warnings.warn(
                f"precompute attribute doesn't make any sense on non computed "
                f"field{suffix}", stacklevel=2)
            attrs['precompute'] = False
        elif not attrs.get('store'):
            warnings.warn(
                f"precompute attribute has no impact on non stored "
                f"field{suffix}", stacklevel=2)
            attrs['precompute'] = False
        elif many_to_many:
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
                f"yet{suffix}", stacklevel=2)
            attrs['precompute'] = False
    return attrs


def apply_source_defaults(related, kwargs, many_to_many=False,
                          company_dependent=False):
    """Lo que ``compute=`` y ``related=`` implican, resuelto al declarar.

    Deriva con :func:`derive_source_attrs` —la única copia de los tres bloques
    de la fuente— y añade las dos consecuencias que sólo se pueden resolver en
    el sitio de declaración, porque son argumentos del constructor de Django o
    contradicciones de la propia declaración.

    **Ya no retira nada de ``kwargs``.** Lo hacía porque el constructor de
    Django rechazaba las claves de la fuente; desde que
    ``_field_init_with_copy`` las recoge en ``_args__`` y las retira él mismo
    (``orm/fields.py``), retirarlas aquí sólo conseguía que la costura no las
    viera y tuviera que derivar de nuevo sobre un ``_args__`` mutilado. Medido
    en la sonda ``probe_vocabulary_reaches_args_by_type``: los **once** tipos
    de Django que las fachadas construyen —``CharField`` … ``ManyToManyField``,
    incluidos los dos relacionales, que tienen ``__init__`` propio— recogen
    ``store`` y ``related`` en ``_args__`` sin rechazarlos.

    **Se llamaba ``apply_related_defaults``.** El nombre describía la mitad que
    portaba; con las tres, mentiría.
    """
    declared_keys = SOURCE_VOCABULARY_KEYS & frozenset(kwargs)
    attrs = {key: kwargs[key] for key in declared_keys}
    if related:
        attrs['related'] = related
        #: Viaja también en ``kwargs`` para que ``_args__`` lo recoja: es lo
        #: que hace que la costura derive lo mismo tras fusionar la MRO, en vez
        #: de ver un campo sin ``related`` y dejar los defaults de clase.
        kwargs['related'] = related

    derive_source_attrs(attrs, many_to_many=many_to_many)
    attrs.setdefault('store', True)

    #: La exclusión vive en el sitio de declaración porque es una contradicción
    #: de lo declarado, no una decisión de rama: un campo sin columna no tiene
    #: ``jsonb`` donde repartir el valor por empresa. Resolverla más tarde la
    #: convertiría en un fallo de arranque en vez de un error donde se escribe.
    if company_dependent and not attrs['store']:
        raise ValueError(
            'store=False y company_dependent=True son excluyentes: un '
            'campo sin columna no tiene jsonb donde repartir el valor.')

    #: ``editable=False`` es la forma NATIVA de Django de decir «esto no lo
    #: escribe el cliente», y es la que DRF ya consume: ``get_field_kwargs``
    #: (``rest_framework/utils/field_mapping.py:124-128``) hace
    #: ``if ... or not model_field.editable: kwargs['read_only'] = True``. Se
    #: pasa como argumento del constructor y no como atributo derivado porque
    #: Django lo lee al construir —``Field.__init__`` lo guarda y las
    #: migraciones lo deconstruyen—; la costura lo vuelve a derivar para el
    #: campo que llegue sin pasar por una fachada.
    if attrs.get('readonly') and attrs['store'] and 'editable' not in kwargs:
        kwargs['editable'] = False

    attrs['declared_keys'] = declared_keys
    return attrs


def annotate_related(field, related, attrs):
    """Deja en el campo lo que la declaración dijo, para que sea greppeable.

    Los cuatro atributos son del vocabulario de la fuente y Django no los
    conoce, así que no viajan en su constructor: se anotan aquí. Sin la
    anotación el árbol no tendría con qué medir cuántos campos son una
    proyección — el mismo criterio con que ``translate`` se anota en vez de
    tragarse (``orm/fields_textual.py``).
    """
    field.related = related
    #: ≙ ``odoo19c: odoo/orm/fields.py:500`` — ``self.__dict__.update(attrs)``,
    #: **incondicional**: la fuente no pregunta si el campo es ``related`` ni
    #: si es calculado, aplica todo lo que el autor declaró. Aquí vivía una
    #: salida temprana para la rama llana que la fuente no tiene, y con ella se
    #: perdían en silencio ``readonly`` (645 declaraciones en la referencia),
    #: ``inverse`` (35), ``recursive`` (3) y ``compute_sudo`` (1) — el default
    #: de clase (``orm/fields.py:1915-1945``) devolvía justo el valor que el
    #: autor quiso cambiar. Ver :ref:`h-api-1103`.
    #:
    #: Lo que SÍ se conserva de aquel razonamiento es su restricción, no su
    #: filtro: un campo que no declara nada no gana un atributo de instancia
    #: por cada clave del vocabulario. La fuente tampoco lo hace — su ``attrs``
    #: sale de ``_get_attrs`` (``:414-430``), que arranca con
    #: ``attrs.update(self._args__)``: **sólo lo que el autor pasó**, y los
    #: bloques de ``compute``/``related`` añaden defaults únicamente en esas
    #: dos ramas. ``declared_keys`` es el porte de esa asimetría.
    #:
    #: Un calculado entra entero: su vocabulario es lo que
    #: :class:`~orm.registry._DerivedCollector` lee para unir el campo con el
    #: ``_depends`` de su método. Sin la anotación, ``field.compute`` sería
    #: ``None`` y el mapa saldría vacío — que es lo que el censo midió antes de
    #: este porte (44 métodos, 0 campos, 0 aristas).
    declared_keys = attrs.get('declared_keys', frozenset())
    landing = (attrs if (related or attrs.get('compute'))
               else {key: value for key, value in attrs.items()
                     if key in declared_keys})
    for attribute, value in landing.items():
        #: Contabilidad del mecanismo, no vocabulario de la fuente: viaja en el
        #: diccionario para que esta función sepa qué declaró el autor, y no
        #: aterriza en el campo.
        if attribute == 'declared_keys':
            continue
        setattr(field, attribute, value)
    #: El campo queda buscable por su cadena, que es lo que navegar la FK a
    #: mano no da — la razón por la que este mecanismo se porta en vez de
    #: declinarse (:ref:`h-api-974`). ``_search_related`` lo instala
    #: :mod:`orm.domains`; aquí se liga a esta instancia. Con ``store`` la
    #: búsqueda va por la columna propia, así que no se cablea (``:635``).
    if related and not attrs['store']:
        field.search = _bind_search_related(field)
    return field


def _bind_search_related(field):
    """``_search_related`` ligado a ``field`` — el invocable que ``search``
    espera: ``(records, operator, value) -> Domain``."""
    def search(records, operator, value):
        return models.Field._search_related(field, records, operator, value)
    return search


class _RegistryCache:
    """Memoria del recorrido del MRO, por clase, con invalidación exacta.

    El recorrido cuesta lo suyo y :meth:`~orm.models.FieldSqlMixin._fields` lo
    hace en cada acceso, incluido el camino de composición de SQL. Medido sobre
    ``ResPartner`` —16 clases en el MRO, 17 campos sin columna— el recorrido son
    **20.9 us** contra **4.6 us** del mapa de ``_meta``: sin memoria, el
    registro del modelo pasa de 4.6 a 26.4 us por lectura.

    La invalidación es por **generación** y no por clase: un descriptor puede
    aterrizar en una clase base y cambiar el resultado de todas sus derivadas,
    así que la única invalidación correcta es tirar el mapa entero. Ocurre sólo
    mientras los addons instalan sus extensiones —``AppConfig.ready()``—, no en
    caliente.

    Con memoria el recorrido baja a **0.1 us** y el registro completo a
    **6.1 us**: lo que queda sobre los 4.6 del mapa de ``_meta`` es la unión de
    los 17, que es el precio de tener el registro de la fuente y no el de las
    columnas.

    *Métrica:* ``timeit`` con 2000 repeticiones sobre ``ResPartner``, con las
    apps ya cargadas.
    *Ciega a:* un descriptor que alguien cuelgue con ``setattr`` pelado, sin
    pasar por ``contribute_to_class`` ni por ``__set_name__``. Esa vía no
    invalida nada, y por eso la instalación de un campo sin columna se hace
    siempre por una de las dos.
    """

    def __init__(self):
        self._generation = 0
        self._by_class = {}

    def invalidate(self):
        self._generation += 1
        self._by_class.clear()

    def get(self, cls):
        cached = self._by_class.get(cls)
        if cached is not None and cached[0] == self._generation:
            return cached[1]
        return None

    def put(self, cls, mapping):
        self._by_class[cls] = (self._generation, mapping)


_REGISTRY_CACHE = _RegistryCache()


def non_stored_fields(cls):
    """Los campos sin columna que ``cls`` declara, por nombre.

    Es la mitad que le faltaba a ``BaseModel._fields`` para ser el registro de
    la fuente y no el de las columnas. Allá ``_fields`` es el mapa que el ORM
    construye al cargar la clase, y en él entra **todo** campo declarado, tenga
    columna o no: un ``related`` sin ``store`` está ahí igual que un ``Char``.
    Aquí las columnas las publica ``_meta`` y los campos sin columna no — por
    diseño, porque un :class:`NonStored` no se registra en ``_meta``
    (:meth:`NonStored.contribute_to_class` lo dice explícitamente). Sin este
    recorrido el registro del modelo queda estrictamente más estrecho que el de
    la fuente, y quien lo consulte por un nombre que sí existe recibe un fallo
    en vez del campo (:ref:`h-api-1025`).

    Se recorre el **MRO entero** y no sólo el ``__dict__`` de ``cls``: un campo
    sin columna puede venir de una clase base o de la extensión que un addon
    cuelga con ``_inherit``, igual que allá. El recorrido va de la base a la
    derivada, así que la declaración más derivada gana — que es la resolución
    de atributo de Python, no un orden inventado aquí.

    Se lee ``vars(klass)`` y no ``getattr``: sobre la clase, un ``getattr``
    invoca ``NonStored.__get__``, que devuelve el descriptor sólo por
    convención del propio descriptor. El ``__dict__`` no depende de esa
    convención y ve también a un descriptor que no la siga.

    **Dos poblaciones, un solo registro (TASK-API-0417).** Desde que las nueve
    fachadas dejaron de enrutar por ``store``, la forma sin columna dominante ya
    no es :class:`NonStored` sino un ``models.Field`` corriente que la costura
    contribuyó con ``private_only=True`` — ``_field_contribute_to_class``
    (``orm/fields.py``) lo refuerza con ``private_only or self.store is False``,
    así que aterriza en ``_meta.private_fields`` y no en ``local_fields``. Este
    recorrido las junta porque el registro que publica es el de la FUENTE, donde
    ``store`` es un atributo y nunca un tipo distinto
    (``odoo19c: odoo/orm/fields.py:455``). Mirar sólo una de las dos dejaría al
    registro estrictamente más estrecho que el de la referencia, que es el
    defecto que :ref:`h-api-1025` ya registró una vez.

    El filtro sobre ``private_fields`` es ``store is False`` y no la mera
    pertenencia: Django también contribuye ahí ``GenericForeignKey`` y los
    campos de contenido genérico, que sí tienen columna asociada y no son campos
    sin almacenamiento de la fuente. Preguntar por la pertenencia mediría la
    tubería de Django y concluiría sobre el vocabulario de la referencia.

    :class:`NonStored` sigue recorriéndose porque la clase todavía existe y
    ``display_name`` la usa; su retirada es **TASK-API-0418**, y ahí esta
    función se queda con una sola de las dos ramas.
    """
    cached = _REGISTRY_CACHE.get(cls)
    if cached is not None:
        return cached
    found = {}
    for klass in reversed(getattr(cls, '__mro__', (cls,))):
        for name, held in vars(klass).items():
            if isinstance(held, NonStored):
                found[name] = held
    meta = getattr(cls, '_meta', None)
    for field in getattr(meta, 'private_fields', ()) or ():
        if getattr(field, 'store', True) is False:
            found[field.name] = field
    #: De sólo lectura a propósito: el mapa se comparte entre lecturas, y un
    #: consumidor que lo mutara corrompería el registro de todos los demás.
    mapping = types.MappingProxyType(found)
    _REGISTRY_CACHE.put(cls, mapping)
    return mapping
