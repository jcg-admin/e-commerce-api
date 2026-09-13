"""Decoradores del ORM — fiel a ``odoo/orm/decorators.py`` (Odoo 19).

En Odoo 19 los decoradores ``@api.depends``/``@api.constrains``/``@api.model``…
se **definen** en ``odoo/orm/decorators.py`` y ``odoo/api/__init__.py`` los
re-exporta. Aquí, con el prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``),
esta es la **definición**; ``src/api/__init__.py`` (≙ ``odoo/api/__init__.py``)
la re-exporta como el namespace ``api``.

Django no tiene el motor de dependencias del ORM de Odoo: el cómputo se ejecuta
en ``save()`` y la validación en ``clean()``. Estos decoradores **no cambian el
comportamiento** (devuelven la función tal cual) y anotan el metadato ``_odoo_*``
con los campos declarados; permiten conservar el decorador sobre el método
portado para expresar la intención Odoo — el ``save()``/``clean()`` del modelo
es quien realmente los llama.
"""

import collections.abc
import functools

__all__ = [
    'attrsetter', 'depends', 'depends_context', 'constrains', 'onchange',
    'ondelete', 'model', 'model_create_multi', 'returns', 'autovacuum',
]


def attrsetter(attr, value):
    """Devuelve una función que fija ``attr`` en su argumento y lo devuelve.

    ≙ ``attrsetter`` (``odoo19c: odoo/orm/decorators.py:73-79``). Docstring de
    la fuente, verbatim: *"Return a function that sets ``attr`` on its argument
    and returns it"*.

    Devolver el argumento es lo que la hace componible: dos ``attrsetter``
    apilados sobre el mismo método dejan las dos marcas, porque el de dentro
    entrega al de fuera lo mismo que recibió.
    """
    def setter(method):
        setattr(method, attr, value)
        return method

    return setter


def depends(*args):
    """Declara de qué campos depende un método ``compute``.

    ≙ ``depends`` (``odoo19c: odoo/orm/decorators.py:248-270``). Cada argumento
    es una cadena de nombres de campo separados por punto::

        pname = fields.Char(compute='_compute_pname')

        @api.depends('partner_id.name', 'partner_id.is_company')
        def _compute_pname(self):
            ...

    **La forma de un solo invocable** (``:265-266`` de la fuente: *"One may
    also pass a single function as argument. In that case, the dependencies are
    given by calling the function with the field's model"*) se guarda tal cual;
    quien la resuelve es el lector — :class:`~orm.registry._DerivedCollector`,
    igual que ``odoo19c: odoo/orm/fields.py:595`` hace ``deps(model) if
    callable(deps) else deps``.

    **La guarda de ``id``** reparte por ``split('.')``, no por subcadena: cae
    ``'partner_id.id'`` y no cae ``'partner_id'``. Un ``'id' in arg`` rechazaría
    los dos.
    """
    if args and callable(args[0]):
        args = args[0]
    elif any('id' in arg.split('.') for arg in args):
        raise NotImplementedError("Compute method cannot depend on field 'id'.")
    return attrsetter('_depends', args)


def constrains(*args):
    """Declara sobre qué campos dispara una restricción de Python.

    ≙ ``constrains`` (``odoo19c: odoo/orm/decorators.py:92-128``). Admite la
    misma forma de un solo invocable que :func:`depends`, y por el mismo
    motivo: los nombres se dan llamando a la función con el modelo.

    Sólo admite nombres simples — una cadena punteada se ignora, como avisa la
    fuente. Esa parte es contrato del consumidor, no del decorador.
    """
    if args and callable(args[0]):
        args = args[0]
    return attrsetter('_constrains', args)


def onchange(*args):
    """Declara a qué campos del formulario reacciona el método.

    ≙ ``onchange`` (``odoo19c: odoo/orm/decorators.py:189-235``). No tiene la
    forma invocable: la fuente tampoco se la da.
    """
    return attrsetter('_onchange', args)


def depends_context(*args):
    """Declara de qué claves de contexto depende un ``compute`` no almacenado.

    ≙ ``depends_context`` (``odoo19c: odoo/orm/decorators.py:273-296``). Cada
    argumento es una clave del contexto::

        price = fields.Float(compute='_compute_product_price')

        @api.depends_context('pricelist')
        def _compute_product_price(self):
            ...

    Todas las dependencias tienen que ser hashables. La fuente da soporte
    especial a tres claves: ``company`` (la del contexto o la empresa activa),
    ``uid`` (el usuario actual y su bandera de elevación) y ``active_test`` (la
    del contexto del entorno o la del campo).

    Su lector aquí ya existe: ``orm.registry.field_depends_context`` recoge el
    marcador y ``Environment._field_depends_context`` lo consulta (tarea #324);
    ``Binary`` lo declara con ``('bin_size',)``.
    """
    return attrsetter('_depends_context', args)


def ondelete(*, at_uninstall):
    """Marca un método para ejecutarse durante el borrado del registro.

    ≙ ``ondelete`` (``odoo19c: odoo/orm/decorators.py:130-186``). Permite
    rechazar el borrado desde el punto de vista del negocio —una orden de venta
    validada no se borra— sin sobreescribir ``unlink``, que es lo que rompería
    la desinstalación del módulo: al desinstalar, la sobreescritura seguiría
    lanzando errores de usuario cuando lo correcto es borrar todo.

    Por convención el método se llama ``_unlink_if_<condicion>`` o
    ``_unlink_except_<condicion_contraria>``::

        @api.ondelete(at_uninstall=False)
        def _unlink_if_user_inactive(self):
            if any(user.active for user in self):
                raise UserError("Can't delete an active user!")

    ``at_uninstall`` es **keyword-only**, como en la fuente, y casi siempre
    ``False``: sólo va en ``True`` cuando la comprobación también aplica al
    desinstalar —el ejemplo de la fuente es no dejar borrar el idioma por
    defecto si no queda otro instalado—.

    Su consumidor es :func:`~orm.models._run_ondelete_checks`, que la
    senal ``pre_delete`` dispara — el equivalente del bloque que la fuente
    corre dentro de ``unlink`` (``odoo19c: odoo/orm/models.py:4205-4208``).
    Los metodos marcados los reune ``orm.registry.ondelete_methods``.

    **No confundirlo con ``_process_ondelete``** (la tarea **#205**), que
    esta linea nombraba como consumidor hasta la **#334** y es otro
    mecanismo: aquel aplica la politica de borrado de un valor de
    ``ir.model.fields.selection`` cuando el valor desaparece del catalogo.
    Comparten la palabra ``ondelete`` y nada mas.
    """
    return attrsetter('_ondelete', at_uninstall)


def _mark(method, attr):
    """Deja ``attr`` en la función, atravesando ``classmethod``/``staticmethod``.

    Un objeto ``classmethod`` no admite atributos arbitrarios, pero su
    ``__func__`` sí — y ``getattr`` sobre el método ligado delega en él, así que
    el marcador se lee igual desde la clase. Hace falta porque en este árbol un
    método de nivel de modelo se escribe ``@api.model`` sobre un ``classmethod``
    (``addons/product/models/product_template.py:400``), forma que la referencia
    no tiene.

    El cuerpo es :func:`attrsetter` con el valor fijo en ``True``; lo único
    propio es **sobre qué** lo aplica. Escribir el ``setattr`` aquí otra vez
    sería la segunda fuente de verdad que ``calibration-verified-numbers.md``
    prohíbe, y divergiría el día que la fuente cambie el suyo.
    """
    attrsetter(attr, True)(getattr(method, '__func__', method))
    return method


def model(method):
    """≙ ``odoo19c: odoo/orm/decorators.py:313`` — ``method._api_model = True``.

    Marca el método como de **nivel de modelo**: opera sobre el modelo, no sobre
    registros concretos. El dispatcher ``/json/2`` lo lee para rechazar con 422
    una llamada que además traiga ``ids``.

    Era ``return func`` —un no-op con el nombre de la referencia— hasta
    :ref:`h-api-639`.
    """
    return _mark(method, '_api_model')


def model_create_multi(method):
    """≙ ``odoo19c: odoo/orm/decorators.py:357-371`` — envuelve ``create``.

    La referencia devuelve un **wrapper**, no el método marcado: convierte un
    ``Mapping`` en ``[vals]`` antes de delegar, y fija ``_api_model`` en el
    wrapper. Hasta :ref:`h-api-1108` este decorador sólo marcaba —``return
    _mark(method, '_api_model')``—, así que un ``create({...})`` llegaba al
    cuerpo como diccionario y cada override lo desdoblaba a mano.

    Dos adaptaciones, declaradas:

    - **Se apila bajo o sobre ``classmethod``.** La fuente decora un método de
      instancia; aquí ``create`` es ``classmethod`` (``DefaultGetMixin.create``)
      y el árbol escribe el decorador en los dos órdenes. Si llega un objeto
      ``classmethod`` se envuelve su ``__func__`` y se devuelve otro
      ``classmethod``; si llega la función, se devuelve la función.
    - **``*args``/``**kwargs`` pasan.** La fuente no tiene ``using=`` porque el
      cursor viaja en ``self.env.cr``; aquí tres overrides lo reciben
      (``grep -rn "def create(cls, vals_list, using" src addons``). El wrapper
      no los toca — el contrato de la fuente es sobre ``vals_list``, no sobre
      el resto de la firma.
    """
    inner = getattr(method, '__func__', method)

    @functools.wraps(inner)
    def create(self, vals_list, *args, **kwargs):
        if isinstance(vals_list, collections.abc.Mapping):
            vals_list = [vals_list]
        return inner(self, vals_list, *args, **kwargs)

    create._api_model = True
    return classmethod(create) if isinstance(method, classmethod) else create


def returns(*args, **kwargs):
    def deco(func):
        return func
    return deco


def autovacuum(method):
    """Marca un método para que lo llame el barrido de ``ir.autovacuum``.

    Fiel a ``odoo/orm/decorators.py:299-310`` (``odoo19c:``), incluida la
    aserción de que el nombre sea privado: allá el mensaje es *"autovacuum
    methods must be private"*. Sirve para tareas de recolección que no ameritan
    un cron propio.

    El valor de retorno puede ser la tupla ``(hechos, restantes)``; si
    ``restantes`` es verdadero, el colector vuelve a encolar el método.
    """
    assert method.__name__.startswith('_'), (
        '%s: los métodos de autovacuum deben ser privados' % method.__name__
    )
    method._autovacuum = True
    return method


def private(method):
    """Marca un método público como **no invocable remotamente**.

    ≙ ``odoo19c: odoo/orm/decorators.py:private``. Su docstring lo encuadra: si
    un método de negocio no debe llamarse por RPC, lo natural es prefijarlo con
    ``_``; este decorador existe para los que **ya son públicos** y pasan a no
    serlo, y para los métodos del propio ORM.

    Lo consulta ``service.model.get_public_method`` recorriendo el MRO: un
    ancestro puede volver privado un nombre que la subclase redefine.
    """
    method._api_private = True
    return method


def readonly(method):
    """Declara que el método puede correr con un cursor de sólo lectura.

    ≙ ``odoo19c: odoo/orm/decorators.py:readonly``. Lo consulta el selector de
    cursor del despacho genérico (``_web_json_2_rpc_readonly`` en la
    referencia), que recorre el MRO buscando el primer ``_readonly`` declarado.
    """
    method._readonly = True
    return method
