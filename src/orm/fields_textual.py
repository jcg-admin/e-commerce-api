"""Campos textuales — fiel a ``odoo/orm/fields_textual.py`` (Odoo 19).

``Char``, ``Text`` y ``Html`` (Odoo ``Html``: ≈ ``TextField`` + saneo con
``dompurify`` en UI). Alias de nombre Odoo → clase Django (firma Django).

``store=False`` — el campo sin columna
=======================================

En la referencia un campo puede declararse sin persistencia:
``fields.Char(store=False, default=_get_algo)``
(``odoo19c: account/models/res_currency.py:17``). Django no lo tiene: todo
``models.Field`` es una columna.

Por eso ``Char`` no es un alias pelado sino un **despachador**: recibe el
vocabulario de la fuente, lo deriva y lo anota sobre el campo. El sitio de
declaración queda **idéntico al de la fuente**, que es el punto — la
alternativa era repartir en el cableado de cada addon lo que la referencia
declara en la clase.

Lo que el despachador **ya no hace es elegir clase** (TASK-API-0417): un
``Char`` sin columna sigue siendo un ``CharField``, porque ``store`` es un
atributo del campo y no un tipo (``odoo19c: odoo/orm/fields.py:455``). La
forma sin columna —sin columna en la tabla, sin accessor inverso, leída por
su ``compute`` o su ``default``— la resuelve la costura al contribuir a la
clase, no el constructor. Por la misma razón ``Text`` y ``Html`` reciben hoy
el vocabulario aunque la referencia no declare ninguno sin almacenar
(``grep -rn "Text(store=False"`` sobre ``odoo19c:`` da **0**): no es una rama
que haya que construirles, es la ausencia de rama.

``company_dependent`` — los tres lo llevan (tarea #129)
========================================================

Los tres tipos textuales están en ``COMPANY_DEPENDENT_FIELDS``, así que los
tres despachan: ``Char`` con su rama propia (tiene además ``store`` y
``translate``), ``Text`` con :func:`~orm.fields_company_dependent.make_dispatcher`
y ``Html`` con un ``__new__`` — no puede ser una función porque
``tools/convert.py`` la usa en un ``isinstance`` (H-API-700).

``Html`` — identidad de clase sin cambiar la columna (H-API-700)
=================================================================

Hasta la tarea #554 ``Html`` era un alias pelado de ``TextField``: en runtime un
campo HTML era indistinguible de un ``Text``, y ``Website._get_html_fields``
tenía que rodearlo parseando el fuente por AST. La referencia distingue el tipo
por catálogo — ``ttype = 'html'`` en ``ir.model.fields``
(``odoo19c: addons/website/models/website.py:1883-1908``) — y
:class:`Html` es aquí el equivalente mínimo que habilita ``isinstance``.

Dos invariantes deliberados:

- **La columna no cambia**: la clase no redefine ``db_type`` ni
  ``get_internal_type`` — sigue siendo ``TEXT``, como el alias.
- **La deconstrucción tampoco**: :meth:`Html.deconstruct` devuelve la ruta de
  ``django.db.models.TextField``, así que las migraciones ya generadas con el
  alias siguen siendo idénticas y ``makemigrations --check`` queda limpio.

El **saneo NO va en el campo** — sigue en la capa UI (``dompurify``), igual que
antes; la clase sólo aporta el tipo.
"""
import collections.abc

from django.db import models

from orm.fields_company_dependent import CompanyDependent, make_dispatcher
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)
from tools.misc import SENTINEL

__all__ = ['Char', 'Text', 'Html', 'LangProxyDict']

Text = make_dispatcher('Text', 'text', models.TextField)


class Html(models.TextField):
    """``fields.Html`` — un ``TextField`` con identidad de tipo (H-API-700).

    ≙ ``odoo/orm/fields_textual.py`` clase ``Html`` de la referencia, reducida
    a lo que este árbol necesita: que ``isinstance(campo, Html)`` distinga un
    campo HTML de un ``Text`` en runtime. Sin saneo (capa UI) y sin columna
    propia (sigue ``TEXT``).
    """

    def __new__(cls, *args, company_dependent=False, related=None, **kwargs):
        """Despacha a ``CompanyDependent`` sin dejar de ser una clase.

        ``Html`` no puede ser una función como los otros ocho despachadores:
        ``tools/convert.py:969`` hace ``isinstance(campo, Html)`` para
        distinguir un campo HTML de un ``Text`` en runtime (H-API-700), y una
        función no es un tipo. La bifurcación va en ``__new__``, que sí la
        admite: cuando devuelve una instancia que **no** es de ``cls``, Python
        no llama a ``__init__`` — así el ``CompanyDependent`` queda construido
        por su propio constructor y no por el de ``TextField``.

        **La única rama que queda es ``company_dependent``.** ``store`` ya no
        elige clase: un ``Html`` sin columna sigue siendo un ``Html``
        (``odoo19c: odoo/orm/fields.py:455``). Por eso la derivación vive en
        :meth:`__init__`, que es el camino de la rama llana; aquí sólo se
        deriva la que no pasa por él, porque Python no llama a ``__init__``
        cuando ``__new__`` devuelve algo que no es de ``cls``.
        """
        if company_dependent:
            attrs = apply_source_defaults(related, kwargs,
                                          company_dependent=True)
            return annotate_related(
                CompanyDependent(*args, base_type='html', **kwargs),
                related, attrs)
        return super().__new__(cls)

    def __init__(self, *args, company_dependent=False, related=None,
                 store=_UNSET, **kwargs):
        """Deriva el vocabulario de la fuente y lo reenvía al constructor.

        **Reenvía en vez de tragar.** La versión anterior nombraba ``store`` y
        ``related`` sólo para que no llegaran al constructor de Django —y con
        eso nunca aterrizaban en ``_args__``, así que la costura veía un campo
        que no declaraba nada y le dejaba los defaults de clase. Hoy los
        reenvía: ``_field_init_with_copy`` los recoge y los retira él mismo
        (``orm/fields.py``), medido sobre los once tipos en la sonda
        ``probe_vocabulary_reaches_args_by_type``.
        """
        if store is not _UNSET:
            kwargs['store'] = store
        related_attrs = apply_source_defaults(related, kwargs)
        super().__init__(*args, **kwargs)
        annotate_related(self, related, related_attrs)

    def deconstruct(self):
        """Deconstruye como ``django.db.models.TextField``.

        Las migraciones existentes se generaron cuando ``Html`` era un alias de
        ``TextField``; conservar esa ruta evita que ``makemigrations`` proponga
        un ``AlterField`` por cada campo HTML del árbol (verificado con
        ``makemigrations --check --dry-run`` → *No changes detected*).
        """
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.db.models.TextField', args, kwargs


def Char(*args, store=_UNSET, required=None, translate=None, help=None,
         size=None, company_dependent=False, related=None, **kwargs):
    r"""``fields.Char`` — ≙ el de la referencia, con y sin columna.

    ``store=True`` (el defecto, y el de los 432 usos del árbol) devuelve un
    ``models.CharField`` con la firma de Django, exactamente como antes.

    ``store=False`` devuelve un campo **no persistido** cuyo valor sale de
    ``default`` al leerlo. No genera migración ni aparece en ``_meta``, que es
    lo que la referencia promete con esa bandera.

    Los tres alias de firma
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Añadidos 2026-08-14 para que el sitio de declaración se lea contra el de la
    fuente sin traducir nada (directiva del ejecutor sobre
    ``odoo19c: stock/models/product_strategy.py:12-13``)::

        name = fields.Char('Name', required=True, translate=True)

    ==============  =====================================================
    De la fuente    Aquí
    ==============  =====================================================
    ``required=``   ``blank=False``/``blank=True`` — el vacío de formulario
    ``help=``       ``help_text=``
    ``size=``       ``max_length=`` — la longitud de la columna ``varchar``
    ``translate=``  se **anota** en el campo; ver el aviso de abajo
    ==============  =====================================================

    ``size=`` es el cuarto alias, y no es cosmético: la referencia lo declara
    en **33** sitios (medido con ``grep -rhoP 'fields\.Char\([^)]*size\s*='``
    sobre ``odoo19c: addons`` y ``odoo``), y sin él cada uno de esos portes
    revienta con ``TypeError`` al construir el campo. Es el mismo nombre que
    ``_char_column_type`` ya traduce en el otro sentido
    (``orm/fields.py:1332``): allá ``('varchar', pg_varchar(self.size))``, aquí
    ``pg_varchar(self.max_length)``. Declararlo en la firma cierra el viaje de
    ida, que era el que faltaba.

    El primer argumento posicional ya coincidía: es ``verbose_name`` en Django
    y la etiqueta en la referencia.

    .. warning:: ``translate=True`` todavía no traduce nada.

       La referencia almacena el campo traducible como **columna ``jsonb``**
       ``{lang: valor}`` y resuelve el idioma en el ORM
       (``odoo19c: odoo/orm/fields_textual.py:53`` — ``if self.store and
       self.translate``; ``:66`` — ``column['udt_name'] == 'jsonb'``). Aquí la
       bandera **se conserva en el campo** (``field.translate``, el mismo
       nombre que la fuente le da en ``odoo19c: odoo/orm/fields.py:288``) para
       que la declaración sea fiel y greppeable, pero el almacenamiento por
       idioma no está construido: hoy la columna sigue siendo ``varchar`` y
       guarda un solo idioma.

       Anotarla en vez de aceptarla y tirarla es deliberado: un ``**kwargs``
       que se traga la bandera deja el árbol sin forma de medir cuántos campos
       esperan traducción. Con la anota, el barrido es un ``grep``.

       Almacenamiento ``jsonb`` + resolución por idioma: tarea **#333**.

    ``company_dependent=True`` — una fila, un valor por empresa
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Tercera rama del despachador, con la firma de la fuente::

        barcode = fields.Char(company_dependent=True, max_length=64)

    Devuelve un :class:`~orm.fields_company_dependent.CompanyDependent`: la
    columna es ``jsonb`` con ``{empresa: valor}`` y leer el atributo da el
    valor de la empresa activa, o el default de ``ir.default``. Es lo que la
    referencia hace con el atributo homónimo de ``Field``
    (``odoo19c: odoo/orm/fields.py:291``, ``:783``).

    ``store=False`` y ``company_dependent=True`` son excluyentes, y la fuente
    también: un campo sin columna no tiene ``jsonb`` donde repartir el valor.
    """
    if required is not None:
        kwargs.setdefault('blank', not required)
    if help is not None:
        kwargs.setdefault('help_text', help)

    #: ``:452-458`` — un related NO se guarda por defecto, y un campo normal
    #: sí. El centinela distingue «no lo declaró» de «lo declaró ``True``»,
    #: que es lo que un default literal no puede: con ``store=True`` fijo,
    #: todo related habría salido con columna, y la forma de la gran mayoría
    #: se habría perdido: el reparto lo publica
    #: ``python3 scripts/census_related_fields.py``.
    if size is not None:
        kwargs['max_length'] = size
    if store is not _UNSET:
        kwargs['store'] = store
    related_attrs = apply_source_defaults(related, kwargs,
                                         company_dependent=company_dependent)
    store = related_attrs['store']

    if company_dependent:
        #: La exclusión ``store=False`` + ``company_dependent`` la levanta
        #: :func:`~orm.fields_nonstored.apply_source_defaults`, que es donde
        #: vive su única copia. Aquí quedan las dos que son de ``Char``.
        if translate:
            raise ValueError('company_dependent field cannot be translated')
        # La guarda de ``required`` va AQUI y no en ``CompanyDependent``: para
        # cuando el campo se construye, ``required`` ya se tradujo a ``blank``
        # arriba y el parametro no llega. Lo destapo su propio test —el
        # constructor tenia la comprobacion y nunca disparaba—.
        if required:
            raise ValueError('company_dependent field cannot be required')
        campo = CompanyDependent(*args, base_type='char', **kwargs)
    else:
        #: El ``CharField`` se construye con columna y sin ella. ``store`` es
        #: atributo del campo, no una clase distinta: la forma sin columna la
        #: resuelve la costura al contribuir a la clase (TASK-API-0417).
        campo = models.CharField(*args, **kwargs)
    campo.translate = bool(translate)
    return annotate_related(campo, related, related_attrs)


class LangProxyDict(collections.abc.MutableMapping):
    """Una vista de un idioma sobre la caché de un campo traducible.

    ≙ ``LangProxyDict`` (``odoo19c: odoo/orm/fields_textual.py:706-777``).
    Docstring de la fuente: *"A view on a dict[id, dict[lang, value]] that maps
    id to value given a fixed language."*

    El almacén real es ``{id: {idioma: valor}}``; esta clase lo presenta como
    ``{id: valor}`` para un idioma fijo, así que el resto del ORM lee y escribe
    la caché de un campo traducible sin saber que hay un nivel más.

    La regla de respaldo, que es su única lógica
    =============================================

    Cuando el valor **no está en base ni se calcula** —campo sin columna, o
    registro nuevo sin origen— el idioma pedido puede no existir en el mapa, y
    la fuente cae a ``en_US``. Cuando **sí** está en base, no cae: pedir un
    idioma ausente es un ``KeyError``, porque ahí el respaldo lo resuelve la
    consulta y no la caché.

    La fuente escribe esa condición **tres veces inline** —en :meth:`get`, en
    :meth:`__getitem__` y en :meth:`__setitem__`—; aquí sale una vez a
    :meth:`_falls_back`. Es la única diferencia de forma con la fuente, y la
    pide ``calibration-verified-numbers.md``: tres copias de la misma regla son
    tres fuentes de verdad que nadie sincroniza.

    ``key or key.origin`` distingue el registro guardado del recién creado: un
    id real es verdadero; un :class:`~orm.identifiers.NewId` sin origen es
    falso y no tiene fila que consultar.

    **Todavía no tiene consumidor en este árbol.** La columna ``jsonb`` por
    idioma que la fuente usa para un campo ``translate=True`` no está
    construida —hoy la columna es ``varchar`` y guarda un solo idioma, ver el
    aviso de :func:`Char`—; construirla es la tarea **#333**, y el eje completo
    de traducción del ORM la **#184**. La clase se porta entera contra su
    contrato para que ese trabajo la encuentre hecha.
    """

    __slots__ = ('_cache', '_field', '_lang')

    def __init__(self, field, cache, lang):
        super().__init__()
        self._field = field
        self._cache = cache
        self._lang = lang

    def _falls_back(self, key):
        """¿Cae a ``en_US`` este id? — la condición que la fuente repite tres
        veces: el valor no se calcula y no está en base."""
        return not (self._field.compute
                    or (self._field.store and (key or key.origin)))

    def get(self, key, default=None):
        # sólo por rendimiento, como la fuente
        vals = self._cache.get(key, SENTINEL)
        if vals is SENTINEL:
            return default
        if vals is None:
            return None
        if self._falls_back(key):
            return vals.get(self._lang, vals.get('en_US', default))
        return vals.get(self._lang, default)

    def __getitem__(self, key):
        vals = self._cache[key]
        if vals is None:
            return None
        if self._falls_back(key):
            return vals.get(self._lang, vals.get('en_US'))
        return vals[self._lang]

    def __setitem__(self, key, value):
        if value is None:
            self._cache[key] = None
            return
        vals = self._cache.get(key)
        if vals is None:
            # el id no está en caché, o lo está como ``{id: None}``
            self._cache[key] = vals = {self._lang: value}
        else:
            vals[self._lang] = value
        if self._falls_back(key):
            # sin fila que consultar, la caché tiene que llevar el valor de
            # respaldo para los demás idiomas
            vals.setdefault('en_US', value)

    def __delitem__(self, key):
        vals = self._cache.get(key)
        if vals:
            vals.pop(self._lang, None)

    def __iter__(self):
        for key, vals in self._cache.items():
            if vals is None or self._lang in vals:
                yield key

    def __len__(self):
        return sum(1 for _ in self)

    def clear(self):
        for vals in self._cache.values():
            if vals:
                vals.pop(self._lang, None)

    def __repr__(self):
        return (f"<LangProxyDict lang={self._lang!r} "
                f"size={len(self._cache)} at {hex(id(self))}>")


def _textual_convert_to_column(self, value, record, values=None, validate=True):
    """``Char.convert_to_column`` — ≙ ``odoo19c: odoo/orm/fields_textual.py:84-85``.

    Delega en ``convert_to_cache``, que es donde la fuente pone el recorte a
    ``size`` y el descarte del valor vacío. Cubre también ``Selection``: la
    fuente las declara como dos clases (``:84`` y
    ``fields_selection.py:223-226``) y este stack lleva ambas al mismo
    ``models.CharField``, así que una sola sobrecarga porta las dos — sus
    cuerpos terminan en el mismo sitio, ``convert_to_cache`` y luego la base.
    """
    return self.convert_to_cache(value, record, validate)


def _textual_convert_to_cache(self, value, record, validate=True):
    """``Char.convert_to_cache`` — ≙ ``odoo19c: odoo/orm/fields_textual.py:102-113``.

    Cuatro pasos, en el orden de la fuente: ``None`` y ``False`` se descartan
    **por identidad** —la cadena vacía sobrevive, y es un valor distinto de la
    ausencia—; ``bytes`` se decodifica; lo demás se lleva a texto; y el
    resultado se recorta al tamaño declarado.

    El tamaño lo declara ``max_length`` en este stack, que es donde la fuente
    pone ``self.size``. Un ``TextField`` no lo declara y entonces no recorta,
    igual que el ``Text`` de la fuente.
    """
    if value is None or value is False:
        return None
    text = value.decode() if isinstance(value, bytes) else str(value)
    size = getattr(self, 'max_length', None)
    return text[:size] if size else text


models.CharField.convert_to_cache = _textual_convert_to_cache
models.TextField.convert_to_cache = _textual_convert_to_cache


models.CharField.convert_to_column = _textual_convert_to_column
models.TextField.convert_to_column = _textual_convert_to_column
