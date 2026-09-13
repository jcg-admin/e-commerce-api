"""SystemParameter (L2) — config runtime global key/value (app ``addons.base``).

Portación **fiel** de Odoo ``ir.config_parameter``
(``scratchpad/odoo19x/odoo/addons/base/models/ir_config_parameter.py`` y
``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_config_parameter.py`` —
arquitectura idéntica en v19 y v18). Diseño: capa L2 de
``analisis-estrategia-configuracion-capas``. Hallazgos de la portación:
``hallazgos-implementar-systemparameter-l2``.

Correspondencia Odoo -> Django (adaptación sin azúcar sintáctica):

- ``_name='ir.config_parameter'`` / ``_description='System Parameter'`` ->
  modelo ``SystemParameter`` (``verbose_name='System Parameter'``).
- ``key = Char(required=True)`` + ``unique (key)`` -> ``CharField(unique=True)``.
  Odoo ``Char`` no fija longitud; en MariaDB un índice único requiere longitud,
  así que se fija ``max_length=255`` (adaptación de motor, H-CFG-IMPL-05).
- ``value = Text(required=True)`` -> ``TextField``.
- ``_order='key'`` -> ``Meta.ordering=['key']``; ``_rec_name='key'`` ->
  ``__str__`` devuelve ``key``.
- ``_default_parameters`` (dict clave->callable) -> ``_DEFAULT_PARAMETERS``
  módulo-nivel. **Fuente de verdad de la protección**: NO existe una columna
  ``is_system`` en Odoo (H-CFG-IMPL-01 corrige el análisis, que la había
  especulado). Una clave está protegida ssi pertenece a este dict.
- ``get_param``/``set_param``/``init`` (``@api.model``) -> ``classmethod`` s
  (``seed`` == ``init``).
- ``@ormcache('key', cache='stable')`` + ``clear_cache('stable')`` -> los
  MISMOS (H-API-864). Hasta ``api@c636e68c`` este archivo construía un
  ``_PARAM_CACHE`` de módulo con su propio ``_clear_cache()``, y lo declaraba
  como el equivalente del decorador «porque el stack no lo trae». Esa razón
  dejó de ser cierta: ``tools/cache.py``, ``tools/lru.py`` y los contenedores
  de ``orm/registry.py`` existen, así que se adopta el mecanismo y la
  invalidación deja de ser global para ser la de la familia ``stable``.
- ``write`` rechaza renombrar una clave protegida; ``unlink_default_parameters``
  (``@api.ondelete``) rechaza borrar una clave protegida. Los dos se portan con
  su nombre, y los enganches de Django (``save``/``delete``) delegan en ellos:
  así la guarda protege también a quien escriba por la vía del ORM de Django.

DIVERGENCIA DE CLAVE, declarada: la referencia decora con
``@ormcache('key', cache='stable')`` y **no** nombra la base, porque su
``Registry`` es por base de datos y esa dimensión va implícita en él. Aquí el
registry es el módulo (divergencia de enlace declarada en ``tools/cache.py``),
así que el alias entra en la clave: ``@ormcache('key', 'using', ...)``. Sin él
dos bases compartirían entrada, que es un defecto que la fuente no tiene.
"""
import api
import uuid

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, models

from orm import registry
from tools.cache import ormcache

# Parámetros sembrados al inicializar la instancia (Odoo ``_default_parameters``,
# líneas 18-25 de ir_config_parameter.py, v19/v18 idénticas). Pertenecer a este
# dict == estar protegido contra borrado y renombrado. El valor es un callable
# perezoso (se evalúa al sembrar), fiel a Odoo.
#
# ``authz.reauth_ttl`` y ``backup.alert_email`` migran aquí desde
# ``config.settings.base`` (slice 2 de ``implementar-systemparameter-l2`,
# cierra el drift H-API-CFG-01/02 de
# :ref:`hallazgos-estrategia-configuracion-kaupamex`): eran tunables globales
# con ``default=`` cableado en código (el de ``backup.alert_email`` además
# stale — ``kaupamex.com`` tras el rename L0 a Kaupamex, SOL-087). Se
# preserva el valor operativo previo (900 s) y se corrige el dominio del
# email a ``kaupamex.com``.
_DEFAULT_PARAMETERS = {
    'database.uuid': lambda: str(uuid.uuid1()),
    'database.secret': lambda: str(uuid.uuid4()),
    'authz.reauth_ttl': lambda: '900',
    'backup.alert_email': lambda: 'admin@kaupamex.com',
}

class SystemParameter(models.Model):
    """Almacén per-instancia de pares clave/valor de configuración (L2 global).

    Equivalente a ``ir.config_parameter``. Vive en el plano de control
    (``default``); no es per-empresa (eso es L3).

    Cabecera — los 5 atributos de clase que la referencia declara
    (``odoo19c: odoo/addons/base/models/ir_config_parameter.py:28-34``),
    portados verbatim junto a su forma Django derivada
    (``atributos-de-clase-de-modelo.md``, H-API-580):

    - ``_name`` -> en la referencia, ``Meta.db_table`` se derivaria de él
      (``_name.replace('.', '_')`` = ``'ir_config_parameter'``). Aquí
      **diverge**: la tabla es ``'system_parameter'`` (el nombre de la
      clase Django, ya migrado en ``0001_initial``). Divergencia
      **declarada**, no símbolo omitido — renombrar la tabla excede el
      alcance de esta tarea (T-387 sólo admite migración nueva para
      campo/índice agregado, no para renombrar una tabla ya migrada).
      Ver ``test_table_diverges_from_name_dot_replaced_by_declared_naming``.
    - ``_description`` -> convive con ``Meta.verbose_name`` (no lo
      sustituye).
    - ``_rec_name`` -> el campo que etiqueta el registro; lo consume
      ``__str__``.
    - ``_order`` -> convive con ``Meta.ordering``.
    - ``_allow_sudo_commands`` -> Odoo lo usa para permitir comandos con
      privilegio elevado sobre este modelo incluso en contexto ``sudo``
      restringido; se declara verbatim como documentación del contrato de
      la referencia. Este puerto no tiene un mecanismo de sudo-restringido
      equivalente al de Odoo (no hay ``env.su`` ni un modo "sudo command"
      separado del superusuario de Django) — divergencia de mecanismo, no
      símbolo omitido.

    Divergencia declarada (NO ausente): ``_key_uniq`` (Odoo
    ``models.Constraint('unique (key)', ...)``, un **objeto de tabla**, no
    un atributo de ORM per ``atributos-de-clase-de-modelo.md``) ya está
    cubierto por ``key = CharField(unique=True)`` abajo — unicidad
    funcionalmente equivalente, sin el nombre de la referencia preservado
    en un ``Meta.constraints`` explícito porque no requiere migración
    nueva para un mecanismo ya presente.
    """

    _name = 'ir.config_parameter'
    _description = 'System Parameter'
    _rec_name = 'key'
    _order = 'key'
    _allow_sudo_commands = False

    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()

    class Meta:
        db_table = 'system_parameter'
        ordering = ['key']
        verbose_name = 'System Parameter'
        verbose_name_plural = 'System Parameters'

    def __str__(self):
        return self.key

    # -- Lectura (Odoo get_param / _get_param) ------------------------------

    @classmethod
    def get_param(cls, key, default=None, using=DEFAULT_DB_ALIAS):
        """Devuelve el valor de ``key``, o ``default`` si no existe.

        Fiel a Odoo ``get_param`` (línea 60): ``return self._get_param(key) or
        default``. El ``or default`` implica que un valor almacenado *falsy*
        (cadena vacía) también devuelve ``default`` — quirk heredado de Odoo
        (H-CFG-IMPL-03), documentado y preservado por fidelidad.
        """
        return cls._get_param(key, using=using) or default

    @classmethod
    @ormcache('key', 'using', cache='stable')
    def _get_param(cls, key, using=DEFAULT_DB_ALIAS):
        """Lee el valor crudo, memorizado en la familia ``stable``.

        ≙ ``odoo19c: ir_config_parameter.py:68-77``. Odoo bypassa el ORM con SQL
        directo porque ``get_param`` se usa en ``@api.depends`` con el ORM a
        medio inicializar; Django no tiene esa restricción, así que se usa el
        ORM normal (H-CFG-IMPL-04). Cachea también la ausencia (``None``), igual
        que la fuente cachea el resultado del SELECT incluyendo el vacío.

        El decorador nombra ``using`` además de ``key`` — ver la divergencia de
        clave declarada en la cabecera del módulo.
        """
        return (cls.objects.using(using)
                .filter(key=key)
                .values_list('value', flat=True)
                .first())

    # -- Escritura (Odoo set_param) -----------------------------------------

    @classmethod
    def set_param(cls, key, value, using=DEFAULT_DB_ALIAS):
        """Fija el valor de ``key``; devuelve el valor previo (o ``None``).

        ≙ ``odoo19c: ir_config_parameter.py:79-99``: si la clave existe y el
        valor es *None/False* -> borra; si cambió -> actualiza; devuelve el
        valor previo. Si no existe y el valor no es *None/False* -> crea;
        devuelve ``None`` (la fuente devuelve ``False``).

        No invalida por su cuenta: delega en ``write``/``unlink``/``create``,
        que son quienes vacían la familia — igual que la fuente.
        """
        param = cls.objects.using(using).filter(key=key).first()
        if param is not None:
            old = param.value
            if value is not None and value is not False:
                if str(value) != old:
                    param.write({'value': str(value)}, using=using)
            else:
                param.unlink(using=using)
            return old
        if value is not None and value is not False:
            cls.create({'key': key, 'value': str(value)}, using=using)
        return None

    # -- Los cuatro enganches de mutación de la referencia -------------------

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list, using=DEFAULT_DB_ALIAS):
        """≙ ``odoo19c: ir_config_parameter.py:101-104`` (``@api.model_create_multi``).

        Vacía la familia ``stable`` y delega. Un dict suelto lo envuelve el
        decorador, como en la fuente; devuelve la lista de instancias.
        """
        registry.clear_cache('stable')
        return [cls.objects.using(using).create(**vals) for vals in vals_list]

    def write(self, vals, using=None):
        """≙ ``odoo19c: ir_config_parameter.py:106-112``.

        Si ``vals`` cambia ``key`` y la clave actual está protegida, rechaza
        nombrándola. Después vacía la familia ``stable`` y persiste.
        """
        using = using or self._state.db or DEFAULT_DB_ALIAS
        if 'key' in vals:
            illegal = _DEFAULT_PARAMETERS.keys() & {self.key}
            if illegal:
                raise ValidationError(
                    'No se pueden renombrar los parámetros de configuración '
                    'con claves %s.' % ', '.join(sorted(illegal)))
        for field, value in vals.items():
            setattr(self, field, value)
        # ``save`` es quien vacía la familia; no se duplica aquí ni se bypassa
        # el enganche, para que un mixin futuro siga entrando en la cadena.
        return self.save(using=using)

    def unlink(self, using=None):
        """≙ ``odoo19c: ir_config_parameter.py:114-116``.

        Corre la guarda de ``@api.ondelete``, vacía la familia y borra.
        """
        using = using or self._state.db or DEFAULT_DB_ALIAS
        # ``delete`` corre la guarda y vacía la familia; aquí sólo se delega.
        return self.delete(using=using)

    def unlink_default_parameters(self):
        """≙ ``odoo19c: ir_config_parameter.py:118-121`` (``@api.ondelete``).

        Una clave de ``_DEFAULT_PARAMETERS`` no se puede eliminar.
        """
        if self.key in _DEFAULT_PARAMETERS:
            raise ValidationError(
                'No se puede eliminar el registro %s.' % self.key)

    # -- Sembrado (Odoo init) -----------------------------------------------

    @classmethod
    def init(cls, force=False, using=DEFAULT_DB_ALIAS):
        """Siembra ``_DEFAULT_PARAMETERS`` ≙ ``odoo19c: ir_config_parameter.py:43-56``.

        Idempotente: sólo crea las claves ausentes; ``force=True`` sobreescribe
        las existentes.
        """
        for key, func in _DEFAULT_PARAMETERS.items():
            exists = cls.objects.using(using).filter(key=key).exists()
            if force or not exists:
                cls.set_param(key, func(), using=using)

    #: Alias histórico de :meth:`init`. El nombre de la referencia es ``init``;
    #: ``seed`` es como se llamó al portarlo y lo consumen la sembradora de
    #: ``conftest`` y las migraciones de datos. Se conserva como alias en vez de
    #: renombrar sus llamadores en este pase — no es un símbolo omitido: ``init``
    #: existe con el nombre de la fuente y es quien lleva el cuerpo.
    seed = init

    # -- Enganches de Django: delegan en los métodos de la referencia --------

    def save(self, *args, **kwargs):
        """Enganche de Django. Corre la guarda de rename de :meth:`write` y
        vacía la familia ``stable``, para que escribir por la vía del ORM de
        Django quede igual de protegido que por :meth:`write`."""
        if self.pk is not None:
            using = kwargs.get('using') or self._state.db or DEFAULT_DB_ALIAS
            previous_key = (type(self).objects.using(using)
                            .filter(pk=self.pk)
                            .values_list('key', flat=True)
                            .first())
            if (previous_key is not None and previous_key != self.key
                    and previous_key in _DEFAULT_PARAMETERS):
                raise ValidationError(
                    'No se pueden renombrar los parámetros de configuración '
                    'con claves %s.' % previous_key)
        registry.clear_cache('stable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Enganche de Django. Corre :meth:`unlink_default_parameters` y vacía
        la familia ``stable``."""
        self.unlink_default_parameters()
        registry.clear_cache('stable')
        return super().delete(*args, **kwargs)
