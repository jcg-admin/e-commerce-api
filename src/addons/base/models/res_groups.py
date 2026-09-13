"""``res.groups`` — grupos de acceso con implicación transitiva.

Adaptación de ``odoo/addons/base/models/res_groups.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 397 líneas).

Colisión con ``authz`` — declarada, no resuelta aquí
====================================================

Este árbol autoriza por **capacidad** (DEC-11: ``HasCapability``, fail-closed)
sobre ``authz.Role`` y ``authz.Capability``, no por grupos de Odoo. Portar
``res.groups`` **no** cambia eso: se porta el archivo completo, y el
re-apuntado de los consumidores (``IrUiMenu.group``, que hoy apunta a
``authz.Capability``) es una decisión de producto que va en su propio pase.

Lo que este archivo aporta de inmediato, independientemente de esa decisión, es
el **álgebra de implicación**, que ``authz`` no tiene: un rol que implica a
otro transitivamente, y dos roles declarados mutuamente excluyentes.

El grafo de implicación, portado entero
=======================================

La referencia dibuja el grafo en un comentario ASCII: si Z implica a C,
"todos los gerentes son usuarios". De ahí salen cuatro relaciones, y las
cuatro se portan:

- ``implied_ids`` — los grupos que este implica (arista directa).
- ``implied_by_ids`` — el **reverso de la misma tabla**: en la referencia son
  el mismo ``Many2many`` sobre ``res_groups_implied_rel`` con las columnas
  invertidas (``gid``/``hid`` ↔ ``hid``/``gid``). Aquí es el ``related_name``
  del propio M2M — misma tabla, misma arista leída al revés.
- ``all_implied_ids`` — **clausura transitiva reflexiva**: el grupo *más* todo
  lo que implica, directa o indirectamente. Reflexiva importa: el grupo se
  incluye a sí mismo (``g.ids + …`` en la fuente).
- ``all_implied_by_ids`` — la clausura en el otro sentido.

Las dos clausuras son ``compute`` **sin** ``store`` allá, así que aquí son
propiedades. El recorrido es una BFS con conjunto de visitados: un grafo de
implicación puede tener ciclos y sin el visitado la clausura no termina.

Grupos disjuntos
================

``disjoint_ids`` declara pares mutuamente excluyentes — el ejemplo de la
fuente es que un usuario no puede ser portal e interno a la vez. En la
referencia el conjunto disjunto sale de tres ``xmlid`` fijos
(``base.group_user`` / ``group_portal`` / ``group_public``) resueltos contra
``ir.model.data``. **Actualizado** (porte de ``ir_model.py``):
``grep -rn "^class IrModelData\b" src/`` → **1** clase. [PROVEN] La medición
de **0** que sostenía la decisión de abajo dejó de ser cierta. La decisión
**no** cambia: la tabla existe pero nadie la puebla todavía —falta el cargador
de datos declarativos—, y un conjunto disjunto que depende de tres filas
ausentes no declararía nada.

Por eso la pertenencia al conjunto disjunto se declara **en el propio
registro**, con un campo ``user_type`` que marca al grupo como tipo de usuario:
dos grupos con ``user_type`` no nulo son disjuntos entre sí. Es la misma
semántica sin depender de identificadores XML que este árbol no tiene, y deja
el conjunto extensible sin tocar código.

``check_user_disjoint_groups`` conserva la decisión de escala de la fuente, que
su comentario explica: **no** se recorren todos los usuarios del grupo —no
escala pasados 10 000— sino que se **busca uno** que viole la exclusión. Si
aparece, hay violación; si no, no la hay. Una consulta en vez de N.

Qué NO se porta, con su medición
================================

- ``model_access`` (``ir.model.access``), ``rule_groups`` (``ir.rule``),
  ``view_access`` (``ir.ui.view``): **los tres ya llegaron**, y llegaron como
  este párrafo predijo — *"aparecen solos cuando esos archivos lleguen, sin
  tocar éste"*. Ninguno necesitó una línea nueva aquí:
  ``ir_rule.py`` declara ``related_name='rule_groups'``, ``ir_model.py``
  declara ``related_name='model_access'`` en ``IrModelAccess.group_id``, e
  ``ir_ui_view.py`` declara ``related_name='view_access'``. [PROVEN] Se
  conserva el registro de que estuvieron pendientes —y de que la predicción
  se cumplió literalmente— en vez de borrarlo.
- ``menu_access`` (``ir.ui.menu``): ``IrUiMenu`` **sí** está portado, pero su
  campo ``group`` apunta hoy a ``authz.Capability``. Re-apuntarlo es
  exactamente la decisión de producto que este docstring difiere; añadir aquí
  un segundo M2M crearía dos caminos de autorización al mismo menú, que es
  peor que uno provisional. Sucesor: tarea **#86**, que reintegra ``authz`` a
  ``base`` y hace de ``Role`` un ``ResGroups``; hasta entonces la deuda tiene
  dueño y no es una declinación anónima.
- ``view_group_hierarchy`` / ``_get_view_group_hierarchy`` y
  ``action_show_all_users``: **portados**, y viven abajo en este archivo. Se
  declinaban citando que la capa de vistas seguía ausente; ese cero caducó al
  portarse ``ir_ui_view.py``, que hoy declara ``IrUiView`` e ``IrUiViewCustom``.
  La declinación sobrevivió al porte porque una frase dentro de un docstring no
  aparece en ninguna lista de trabajo — el defecto que el gate
  ``check_stale_zero_claims.py`` existe para atrapar.
- ``_ensure_xml_id`` y ``get_external_id``: **portados** también. Su bloqueo
  —la ausencia de ``ir.model.data``— lo cerró el porte de ``ir_model.py``, que
  declara ``IrModelData``, y ``get_external_id`` lo construyó la tarea #204 en
  :class:`orm.models.AccessQuerySet`. El docstring de ``_ensure_xml_id`` ya lo
  registraba mientras este párrafo seguía diciendo lo contrario: dos referentes
  del mismo archivo en desacuerdo.
- ``api_key_duration``: la duración máxima de una API key. Este árbol autentica
  por sesión de servidor (ADR-018) y las API keys no existen; el campo se
  porta como columna —es dato del grupo— pero sin lógica que lo consuma, y así
  se declara en su ``help_text``.
"""
import logging
from collections import deque

import api
import fields
import models
from orm.domains import NEGATIVE_CONDITION_OPERATORS, Domain
from django.apps import apps
from django.core.exceptions import ValidationError

from exceptions import UserError

from addons.base.models.res_groups_privilege import ResGroupsPrivilege
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm import registry
from orm.utils import SUPERUSER_ID
from tools.cache import ormcache
from tools.set_expression import SetDefinitions

_logger = logging.getLogger(__name__)

#: Traducción del operador de dominio al ``lookup`` de Django, para los que
#: ``_search_full_name`` admite. La fuente compone un ``Domain('name', operator,
#: operand)`` y deja que su motor lo resuelva; aquí el motor es el ORM de
#: Django y el operador viaja como sufijo del campo. Los negativos NO entran:
#: la fuente los rechaza con ``NotImplemented`` (``Domain.NEGATIVE_OPERATORS``).
_OPERATOR_LOOKUPS = {
    '=': 'exact',
    '==': 'exact',
    'like': 'contains',
    'ilike': 'icontains',
    '=like': 'like',
    '=ilike': 'ilike',
    'in': 'in',
}


class ResGroups(models.CopyMixin, TimeStampedModel):
    """Un grupo de acceso (``res.groups``).

    ``full_name`` es ``privilegio / nombre`` cuando hay privilegio, y el
    nombre a secas cuando no — igual que ``_compute_full_name`` de la fuente.
    """

    #: Tipos de usuario mutuamente excluyentes. En la referencia son tres
    #: Los cinco atributos de ORM que la fuente declara (``:10-14``), verbatim.
    #: Se completan al tocar el archivo, por ``atributos-de-clase-de-modelo.md``:
    #: antes eran **0 de 7** y la cabecera no se podía leer contra la de la
    #: fuente. Los dos que faltan son **objetos de tabla**, no atributos de
    #: ORM, y su hogar es ``Meta.constraints`` con el nombre conservado.
    _name = 'res.groups'
    _description = 'Access Groups'
    _rec_name = 'full_name'
    _allow_sudo_commands = False
    _order = 'privilege_id, sequence, name, id'

    #: ``xmlid`` fijos; aquí el grupo declara su tipo y dos tipos distintos
    #: son disjuntos por construcción.
    USER_TYPE_INTERNAL = 'internal'
    USER_TYPE_PORTAL = 'portal'
    USER_TYPE_PUBLIC = 'public'
    USER_TYPE_CHOICES = [
        (USER_TYPE_INTERNAL, 'Interno'),
        (USER_TYPE_PORTAL, 'Portal'),
        (USER_TYPE_PUBLIC, 'Público'),
    ]

    #: ≙ la declaración de la fuente, verbatim salvo el nombre del argumento
    #: de la etiqueta (``odoo19c: odoo/addons/base/models/res_groups.py:30``)::
    #:
    #:     full_name = fields.Char(compute='_compute_full_name',
    #:                             string='Group Name',
    #:                             search='_search_full_name')
    #:
    #: No tiene columna porque el bloque ``compute`` de la fuente deriva
    #: ``store=False`` cuando nadie lo declara (``odoo19c:
    #: odoo/orm/fields.py:443-450``); así ``_rec_name = 'full_name'`` deja de
    #: apuntar a un nombre que no resuelve.
    #:
    #: La etiqueta va en el primer posicional —``verbose_name`` en Django,
    #: ``string`` en la fuente—; antes viajaba en ``help_text=``, que es el
    #: alias de ``help=``. Y el cómputo va en ``compute=``: hasta
    #: ``TASK-API-0415`` se cableaba con un ``default=`` que lo envolvía,
    #: porque el descriptor guardaba ``compute`` y nadie lo despachaba.
    full_name = fields.Char('Group Name',
                            compute='_compute_full_name',
                            search='_search_full_name')

    name = fields.Char(max_length=120, verbose_name='Nombre')
    comment = fields.Text(blank=True, default='', verbose_name='Comentario')
    sequence = fields.Integer(null=True, blank=True, verbose_name='Secuencia')
    share = fields.Boolean(
        default=False, verbose_name='Grupo compartido',
        help_text='Odoo share. Grupo creado para dar acceso al compartir datos '
                  'con algunos usuarios.',
    )
    api_key_duration = fields.Float(
        null=True, blank=True,
        verbose_name='Duración máxima de las API keys (días)',
        help_text='Odoo api_key_duration. Se porta como dato del grupo; este '
                  'árbol autentica por sesión de servidor (ADR-018) y no tiene '
                  'API keys que lo consuman.',
    )
    privilege = fields.Many2one(
        ResGroupsPrivilege, on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, related_name='group_ids', verbose_name='Privilegio',
        help_text='Odoo privilege_id. Agrupa grupos en el formulario.',
    )
    user_type = fields.Selection(
        max_length=16, choices=USER_TYPE_CHOICES, null=True, blank=True,
        db_index=True, verbose_name='Tipo de usuario',
        help_text='Dos grupos con tipo de usuario distinto son disjuntos: un '
                  'usuario no puede pertenecer a ambos.',
    )
    implied_ids = fields.Many2many(
        'self', symmetrical=False, blank=True, related_name='implied_by_ids',
        db_table='res_groups_implied_rel', verbose_name='Grupos implicados',
        help_text='Los usuarios de este grupo pertenecen también, de forma '
                  'implícita, a estos grupos (Odoo implied_ids).',
    )
    # La referencia declara este M2M **del lado de res.groups**
    # (``res_groups_users_rel``, columnas ``gid``/``uid``), así que aquí va
    # igual: no hace falta tocar ``res_users.py``, que recibe el reverso
    # ``group_ids`` por el ``related_name``.
    user_ids = fields.Many2many(
        ResUsers, blank=True, related_name='group_ids',
        db_table='res_groups_users_rel', verbose_name='Usuarios',
        help_text='Usuarios explícitamente en este grupo (Odoo user_ids).',
    )

    class Meta:
        db_table = 'res_groups'
        #: Derivado de ``_order``, verbatim: la fuente ordena **primero por
        #: privilegio**, que es como se agrupa el formulario de ajustes.
        ordering = ['privilege_id', 'sequence', 'name', 'id']
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        constraints = [
            # ``_name_uniq``: ``UNIQUE (privilege_id, name)``.
            models.UniqueConstraint(
                fields=['privilege', 'name'], name='res_groups_name_uniq',
                violation_error_message='El nombre del grupo tiene que ser '
                                        'único dentro de su privilegio.'),
            # ``_check_api_key_duration``: ``CHECK(api_key_duration >= 0)``.
            # Nulo pasa por construcción — en SQL un CHECK sobre NULL es
            # desconocido, no violado —, que es lo que la fuente obtiene con
            # su ``Float`` de default 0.
            models.CheckConstraint(
                condition=models.Q(api_key_duration__gte=0),
                name='res_groups_check_api_key_duration',
                violation_error_message='La duración de la API key no puede '
                                        'ser negativa.'),
        ]

    def __str__(self):
        return self.full_name

    def _compute_full_name(self):
        """``privilegio / nombre``, o el nombre solo — ≙ ``:123-129``."""
        if self.privilege_id and self.privilege:
            return '%s / %s' % (self.privilege.name, self.name)
        return self.name

    # === Búsqueda y orden por nombre completo =============================

    @classmethod
    def _search_full_name(cls, operator, operand):
        """Las filas cuyo nombre completo cumple ``operator`` sobre ``operand``.

        ≙ ``_search_full_name`` (``odoo19c: res_groups.py:131-165``). ``full_name``
        es ``privilegio / nombre`` y no tiene columna, así que buscarlo exige
        descomponer el operando: la fuente prueba el **nombre a secas**, y
        además —si el operando trae ``/``— el privilegio por un lado y el
        nombre por el otro.

        Los tres desenlaces de la fuente, verbatim:

        - operador **negativo** → ``NotImplemented``. La fuente se rehúsa en vez
          de adivinar: la negación de una disyunción de dos columnas no es la
          disyunción de las negaciones, y componerla mal daría filas de más.
        - operando **texto** → cada término recibe el valor tal cual;
        - operando **lista** → cada término recibe ``[valor]``, porque el
          operador que llega (``in``) espera una colección. Es lo que la fuente
          resuelve con su ``make_operand``, y omitirlo produce ``name in 'Alfa'``
          — un ``in`` sobre un escalar.

        El **primer término repite el operando entero**, y eso es de la fuente:
        con un operando de texto queda duplicado con el del bucle, y el punto
        fijo lo colapsa en ``_optimize_same_conditions``. No se recorta aquí —
        recortarlo cambiaría la forma que el optimizador espera recibir.

        El privilegio se compara por ``any!`` sobre la relación, no atravesando
        con punto: es lo que hace el consumidor real de
        ``_optimize_m2o_bypass_comodel_id_lookup``, que reescribe esa subconsulta
        a una comparación directa contra la columna.

        Devuelve un ``Domain``, como la fuente. Hasta ``api@707b3e28`` devolvía
        un ``QuerySet``, con el mismo argumento que ``_search_display_name``
        declaraba y que quedó falso por la misma razón: un dominio se compone
        dentro de un ``any`` y un ``QuerySet`` no (:ref:`h-api-965`).
        """
        if operator in NEGATIVE_CONDITION_OPERATORS:
            return NotImplemented

        if isinstance(operand, str):
            def make_operand(value):
                return value
            operands = [operand]
        else:
            def make_operand(value):
                return [value]
            operands = operand

        where_domains = [Domain('name', operator, operand)]
        for group in operands:
            if not group:
                continue
            where_domains.append(
                Domain('name', operator, make_operand(group)))

            if '/' in group:
                privilege_name, _, group_name = group.partition('/')
                group_name = group_name.strip()
                privilege_name = privilege_name.strip()
            else:
                privilege_name = group
                group_name = None

            if privilege_name:
                domain = Domain(
                    'privilege', 'any!',
                    Domain('name', operator, make_operand(privilege_name)))
                if group_name:
                    domain &= Domain('name', operator,
                                     make_operand(group_name))
                where_domains.append(domain)

        return Domain.OR(where_domains)

    @classmethod
    def _search(cls, queryset=None, order=None):
        """Aplica el orden por ``full_name``, que ninguna columna respalda.

        ≙ ``_search`` (``odoo19c: res_groups.py:167-175``), que intercepta el
        caso *"el orden empieza por full_name"* y ordena **en Python** —
        ``groups.sorted('full_name', ...)``— porque ``full_name`` es un campo
        calculado sin almacenar y ningún ``ORDER BY`` lo alcanza.

        Aquí ocurre lo mismo por la misma razón, así que el método existe con el
        mismo papel: recibe el ``QuerySet`` que se iba a ordenar y devuelve una
        **lista** ordenada cuando el orden es ``full_name``; en cualquier otro
        caso devuelve el ``QuerySet`` intacto, para que el orden lo resuelva
        PostgreSQL.

        La fuente pagina después de ordenar (``groups[offset:offset+limit]``);
        aquí el recorte lo hace el llamador sobre la lista, que es la misma
        operación sobre la misma secuencia ya ordenada.
        """
        if queryset is None:
            queryset = cls.objects.all()
        if not order or not order.startswith('full_name'):
            return queryset
        return sorted(queryset, key=lambda group: group.full_name,
                      reverse=order.endswith('DESC'))

    # === Copia, invariantes y ciclo de vida ===============================

    def copy_data(self, default=None, seen=None):
        """≙ ``copy_data`` (``odoo19c: res_groups.py:177-182``).

        El duplicado lleva ``"<nombre> (copia)"`` salvo que el llamador imponga
        otro nombre. Sin esto un ``UNIQUE (privilege_id, name)`` —la restricción
        que este modelo declara— rechazaría la copia.
        """
        default = dict(default or {})
        values = super().copy_data(default=default, seen=seen)
        if not default.get('name'):
            values['name'] = '%s (copia)' % self.name
        return values

    def _check_disjoint_groups(self):
        """Ningún usuario queda en dos grupos excluyentes tras cambiar el grafo.

        ≙ ``_check_disjoint_groups`` (``odoo19c: res_groups.py:82-86``), su
        ``@api.constrains('implied_ids', 'implied_by_ids')``. Purga el grafo
        —una arista nueva cambia la clausura— y verifica **desde arriba**: los
        grupos que implican a éste son los que pueden haber ganado usuarios.

        DIVERGENCIA DE ENLACE, declarada: allá es un ``@api.constrains`` que el
        ORM dispara al escribir el M2M. Aquí el M2M no pasa por ``save``, así
        que lo llama el receptor de ``m2m_changed`` de ``res_users.py`` — el
        mismo que purga la caché — y también se puede invocar a mano.
        """
        registry.clear_cache('groups')
        for group in self.all_implied_by_ids:
            group.check_user_disjoint_groups()

    def _check_inherited_view_groups(self):
        """Una vista heredada no declara grupos en el registro.

        ≙ ``_check_inherited_view_groups`` (``odoo19c: res_groups.py:88-90``),
        su ``@api.constrains('view_access')``: delega en
        ``IrUiView._check_groups``, que es quien conoce la regla.

        Misma divergencia de enlace que :meth:`_check_disjoint_groups`.
        """
        for view in self.view_access.all():
            view._check_groups()

    def _unlink_except_settings_group(self):
        """No se borra un grupo enlazado a un campo del formulario de ajustes.

        ≙ ``_unlink_except_settings_group``
        (``odoo19c: res_groups.py:114-119``), su ``@api.ondelete``. Un campo
        ``group_...`` de ``res.config.settings`` **es** el interruptor de ese
        grupo: borrarlo dejaría el ajuste apuntando al vacío.

        DIVERGENCIA DE ENLACE: allá es un ``@api.ondelete(at_uninstall=False)``;
        aquí lo llama :meth:`delete`, que es el enganche equivalente de Django.
        El matiz ``at_uninstall=False`` —no correr durante la desinstalación de
        un módulo— no tiene contraparte: aquí el esquema lo gobiernan las
        migraciones, no un desinstalador que borre datos.

        DIVERGENCIA DE FORMA, en dos ejes medidos:

        1. **El modelo de ajustes es uno allá y muchos aquí.** La fuente lee
           ``self.env['res.config.settings']``, el modelo compuesto por todos
           los ``_inherit`` de los addons instalados. Aquí
           :class:`~addons.base.models.res_config.ResConfigSettings` es una
           base **abstracta** (``Meta.abstract = True``) y cada addon declara
           su subclase concreta, así que el equivalente de ese modelo único es
           el **conjunto de sus subclases**; se recorren todas. El
           discriminador es ``hasattr(model, 'classify_fields')`` y no un
           ``issubclass``, por dos razones medidas: la jerarquía entera
           —``ResConfig`` y ``ResConfigSettings``— declara
           ``Meta.abstract = True``, así que ``apps.get_model`` no la
           encuentra (``LookupError: App 'base' doesn't have a 'ResConfig'
           model``); e importar la clase cerraría el ciclo, porque
           ``res_config.py:118`` importa este módulo. ``classify_fields`` sólo
           lo declara esa jerarquía, así que discrimina exactamente igual.
        2. **El grupo implicado se designa por nombre, no por id.** Allá el
           clasificador ya resolvió el xmlid a recordset y el guard compara
           ``implied_group.id``; aquí ``classify_fields`` conserva la cadena y
           el resolvedor del árbol es ``ResGroups.objects.filter(name=...)``
           (``res_config.py:328,372``), así que la comparación equivalente es
           contra ``self.name`` — sin consulta, porque el registro que se está
           borrando ya está en la mano.

        Lo que este método NO cierra: los ``field_attrs`` de los addons
        declaran el implicado en forma de xmlid
        (``'purchase_requisition.group_purchase_alternatives'``) mientras el
        resolvedor busca por ``name``, así que hoy ninguno de los dos casa. Es
        una incoherencia anterior a este porte y su sucesor es la tarea
        **#206**; este guard usa el resolvedor vigente, no uno propio.
        """
        for model in apps.get_models():
            if not hasattr(model, 'classify_fields'):
                continue
            for _name, _groups, implied in model.classify_fields()['group']:
                if implied == self.name:
                    raise ValidationError(
                        'No se puede borrar un grupo enlazado a un campo de '
                        'ajustes.')

    def _ensure_xml_id(self):
        """El identificador externo de cada grupo, creándolo si no lo tiene.

        ≙ ``_ensure_xml_id`` (``odoo19c: res_groups.py:203-221``). Un grupo sin
        identificador externo no se puede nombrar desde un archivo de datos ni
        desde ``parse``, así que la fuente le fabrica uno bajo el módulo
        ``__custom__``, que es su convención para lo creado a mano.

        Estuvo bloqueado por ``get_external_id``, que este árbol no tenía; la
        tarea **#204** lo construyó en :class:`orm.models.AccessQuerySet`.
        """
        data_model = apps.get_model('base', 'IrModelData')
        result = type(self).objects.filter(pk=self.pk).get_external_id()
        missing = {
            group_id: '__custom__.group_%s' % group_id
            for group_id, ext_id in result.items() if not ext_id
        }
        for group_id, xmlid in missing.items():
            data_model.set_xmlid(type(self).objects.get(pk=group_id), xmlid)
        result.update(missing)
        return result

    # === El eje de tipo de usuario ========================================

    @classmethod
    def _get_user_type_groups(cls):
        """Los grupos de tipo de usuario, que son disjuntos entre sí.

        ≙ ``_get_user_type_groups`` (``odoo19c: res_groups.py:280-287``).

        DIVERGENCIA DE MECANISMO, ya declarada en el docstring del módulo: la
        fuente resuelve **tres xmlid fijos** (``base.group_user`` /
        ``group_portal`` / ``group_public``) contra ``ir.model.data``; aquí el
        eje lo declara el propio registro con ``user_type``, así que el
        conjunto es extensible sin tocar código y no depende de tres filas
        sembradas. Es la misma decisión que sostiene :attr:`disjoint_ids`.
        """
        return cls.objects.filter(user_type__isnull=False)

    def _inverse_all_user_ids(self, users):
        """Escribe la pertenencia total, respetando la implicada.

        ≙ ``_inverse_all_user_ids`` (``odoo19c: res_groups.py:228-240``), el
        lado escritor de ``all_user_ids``. La regla que hace falta portar es la
        del error: un usuario que pertenece por **implicación** no se puede
        quitar desde aquí — habría que quitarlo del grupo que implica a éste.

        :param users: el conjunto completo de usuarios que debe quedar.
        :raises UserError: si se pide retirar a alguien que pertenece por
            implicación.
        """
        target = {user.pk for user in users}
        implied = {user.pk for user in self.all_user_ids}
        direct = {pk for pk in self.user_ids.values_list('pk', flat=True)}

        to_add = target - implied
        to_remove = implied - target

        cannot_remove = (implied - direct) & to_remove
        if cannot_remove:
            names = ResUsers.objects.filter(pk__in=sorted(cannot_remove))
            raise UserError(
                'No se puede retirar el grupo implicado %r de los usuarios %s'
                % (self.name, ', '.join(str(user) for user in names)))

        if to_remove:
            self.user_ids.remove(*ResUsers.objects.filter(pk__in=sorted(to_remove)))
        if to_add:
            self.user_ids.add(*ResUsers.objects.filter(pk__in=sorted(to_add)))

    # === Búsquedas sobre las clausuras ====================================

    @classmethod
    def _search_all_user_ids(cls, users):
        """Los grupos a los que ``users`` pertenece, directa o implícitamente.

        ≙ ``_search_all_user_ids`` (``odoo19c: res_groups.py:242-243``), que
        redirige la búsqueda al camino ``all_implied_by_ids.user_ids``.
        """
        pks = [user.pk if hasattr(user, 'pk') else user for user in users]
        directos = cls.objects.filter(user_ids__pk__in=pks).values_list('pk', flat=True)
        definitions = cls._get_group_definitions()
        alcanzados = list(directos)
        return cls.objects.filter(
            pk__in=alcanzados + definitions.get_superset_ids(alcanzados))

    @classmethod
    def _search_all_implied_ids(cls, group_ids, negate=False):
        """Los grupos cuya clausura de implicación toca alguno de ``group_ids``.

        ≙ ``_search_all_implied_ids`` (``odoo19c: res_groups.py:245-251``), que
        se apoya en ``get_subset_ids`` del grafo — el mismo mecanismo que la
        tarea #204 portó.

        La fuente devuelve ``NotImplemented`` para todo operador que no sea
        ``in``/``not in``; aquí eso es el parámetro ``negate``, que son los dos
        únicos casos que admitía.
        """
        definitions = cls._get_group_definitions()
        ids = [*group_ids, *definitions.get_subset_ids(group_ids)]
        if negate:
            return cls.objects.exclude(pk__in=ids)
        return cls.objects.filter(pk__in=ids)

    @classmethod
    def _search_all_implied_by_ids(cls, group_ids, negate=False):
        """Los grupos alcanzados por la clausura inversa de ``group_ids``.

        ≙ ``_search_all_implied_by_ids`` (``odoo19c: res_groups.py:260-266``).
        El espejo del anterior: ahí ``get_subset_ids``, aquí
        ``get_superset_ids``.
        """
        definitions = cls._get_group_definitions()
        ids = [*group_ids, *definitions.get_superset_ids(group_ids)]
        if negate:
            return cls.objects.exclude(pk__in=ids)
        return cls.objects.filter(pk__in=ids)

    # === El árbol que el formulario de ajustes dibuja ======================

    @property
    def view_group_hierarchy(self):
        """Superficie de lectura del campo; el cómputo es el de la fuente.

        ≙ el campo ``view_group_hierarchy = fields.Json(compute=...)``
        (``odoo19c: res_groups.py:37``). Misma forma que
        ``IrModel.inherited_model_ids`` en este árbol: la ``property`` es el
        campo, y su ``compute`` es el método de abajo.
        """
        return self._compute_view_group_hierarchy()

    def _compute_view_group_hierarchy(self):
        """≙ ``_compute_view_group_hierarchy`` (``odoo19c: :321-323``).

        La fuente **asigna** (``self.view_group_hierarchy = ...``); aquí
        devuelve, que es la divergencia de forma que ``DisplayNameMixin`` ya
        declara para todos los cómputos de este árbol.
        """
        return type(self)._get_view_group_hierarchy()

    @classmethod
    @api.model
    @ormcache(cache='groups')
    def _get_view_group_hierarchy(cls):
        """Grupos, privilegios y categorías, tal como los pinta el formulario.

        ≙ ``_get_view_group_hierarchy`` (``odoo19c: res_groups.py:325-360``),
        con sus tres claves y el contenido de cada una. Memorizado en la misma
        familia ``groups`` que el grafo, y por lo mismo: lo invalida cualquier
        cambio del grafo de grupos.

        El orden de ``group_ids`` dentro de un privilegio es el de la fuente y
        **no es alfabético**: primero cuántos grupos del propio privilegio
        implica el grupo —los más generales arriba—, luego ``sequence``, luego
        ``id``. Es lo que hace que el selector del formulario se lea como una
        escala.
        """
        privilege_model = apps.get_model('base', 'ResGroupsPrivilege')
        category_model = apps.get_model('base', 'IrModuleCategory')

        def rank_within_privilege(group, sibling_pks):
            implied = {g.pk for g in group.all_implied_ids} & sibling_pks
            return (len(implied) if group.privilege_id else 0,
                    group.sequence or 0, group.pk)

        privileges = {}
        for privilege in privilege_model.objects.all():
            siblings = list(privilege.group_ids.all())
            pks = {group.pk for group in siblings}
            privileges[privilege.pk] = {
                'id': privilege.pk,
                'name': privilege.name,
                'category_id': privilege.category_id,
                'description': privilege.description,
                'placeholder': privilege.placeholder,
                'group_ids': [
                    group.pk for group in
                    sorted(siblings, key=lambda g: rank_within_privilege(g, pks))
                ],
            }

        return {
            'groups': {
                group.pk: {
                    'id': group.pk,
                    'name': group.name,
                    'comment': group.comment,
                    'privilege_id': group.privilege_id,
                    'disjoint_ids': list(group.disjoint_ids.values_list('pk', flat=True)),
                    'implied_ids': list(group.implied_ids.values_list('pk', flat=True)),
                    'all_implied_ids': [g.pk for g in group.all_implied_ids],
                    'all_implied_by_ids': [g.pk for g in group.all_implied_by_ids],
                }
                for group in cls.objects.all()
            },
            'privileges': privileges,
            'categories': [
                {
                    'id': category.pk,
                    'name': category.name,
                    'privilege_ids': [
                        privilege.pk
                        for privilege in category.privileges.order_by('sequence', 'pk')
                        if privilege.group_ids.exists()
                    ],
                }
                for category in category_model.objects.filter(
                    privileges__group_ids__isnull=False).distinct()
            ],
        }

    def action_show_all_users(self):
        """La acción que abre los usuarios del grupo, implicados incluidos.

        ≙ ``action_show_all_users`` (``odoo19c: res_groups.py:386-397``),
        verbatim en sus siete claves. El dominio usa ``all_group_ids``, no
        ``group_ids``: la acción muestra a quien pertenece por implicación,
        que es lo que su propio nombre promete.
        """
        return {
            'name': 'Usuarios y usuarios implicados de %s' % self.full_name,
            'view_mode': 'list,form',
            'res_model': 'base.ResUsers',
            'type': 'ir.actions.act_window',
            'context': {'create': False, 'delete': False,
                        'form_view_ref': 'base.view_users_form'},
            'domain': [('all_group_ids', 'in', [self.pk])],
            'target': 'current',
        }

    # === Invalidación del grafo memoizado =================================

    def save(self, *args, **kwargs):
        """Enganche de Django — ≙ ``create`` (``odoo19c: res_groups.py:297-301``).

        La fuente vacía la familia ``groups`` al **crear** un grupo, porque el
        grafo memoizado tiene una hoja por grupo y uno nuevo no está en él:
        ``IrModelAccess._get_access_groups`` sobre una ACL de ese grupo revienta
        con ``KeyError`` — medido, es lo que destapó esta invalidación.

        **Aquí también invalida al escribir, y es más ancho que la fuente por
        una razón medida.** Allá el ``write`` sólo purga si cambian
        ``implied_ids``/``implied_by_ids`` (``:197-199``); esos son M2M y en
        Django **no pasan por** ``save`` —van por su descriptor, que emite
        ``m2m_changed``, y ahí los purga su receptor de ``res_users.py``—. Lo
        que sí pasa por ``save`` es ``user_type``, y ése decide
        ``disjoint_ids``: cambiarlo reescribe las aristas de disjunción del
        grafo. La fuente cubre ese mismo caso desde su
        ``@api.constrains('implied_ids', 'implied_by_ids')`` (``:82-86``), que
        también purga. Purgar en todo ``save`` es un superconjunto de los dos,
        y el coste es vaciar un memo de 64 entradas.
        """
        result = super().save(*args, **kwargs)
        registry.clear_cache('groups')
        return result

    def delete(self, *args, **kwargs):
        """Enganche de Django — ≙ ``unlink`` (``odoo19c: res_groups.py:303-306``).

        El receptor ``post_delete`` de ``res_users.py`` cubre además el borrado
        por ``QuerySet.delete()``, que no instancia las filas y por tanto no
        pasa por aquí. Los dos, como en la fuente: un grupo borrado que siga en
        el grafo concede por una hoja que ya no existe.
        """
        self._unlink_except_settings_group()
        result = super().delete(*args, **kwargs)
        registry.clear_cache('groups')
        return result

    # === Clausura transitiva ==============================================

    @staticmethod
    def _closure(seeds, edge):
        """Clausura transitiva **reflexiva** por BFS.

        ``edge(grupo)`` devuelve los vecinos a seguir. El conjunto de visitados
        no es una optimización: el grafo de implicación admite ciclos, y sin él
        el recorrido no termina.
        """
        seen = set()
        queue = deque(seeds)
        while queue:
            group = queue.popleft()
            if group.pk in seen:
                continue
            seen.add(group.pk)
            queue.extend(edge(group))
        return seen

    # === Bandera de funcionalidad =========================================

    @classmethod
    def _is_feature_enabled(cls, group_reference):
        """¿Está activa la funcionalidad que ese grupo representa?

        ≙ ``_is_feature_enabled`` (``odoo19c: base/models/res_groups.py:378-380``),
        que es ``self.env['res.users'].sudo().browse(api.SUPERUSER_ID)._has_group(...)``.

        La pregunta NO es "¿puede el usuario actual?" sino "¿está encendida la
        funcionalidad en esta instalación?". Por eso interroga al superusuario
        y no al que hace la petición: un grupo de configuración —p. ej.
        ``sale.group_discount_per_so_line``— actúa como interruptor, y su
        estado no depende de quién mire. Un usuario sin el grupo vería la
        funcionalidad apagada, que es la lectura contraria.

        ``group_reference`` es el identificador externo totalmente calificado
        (``modulo.ext_id``), igual que en la fuente.

        Devuelve ``False`` cuando el superusuario no existe todavía —una base
        recién migrada antes de la siembra—. Ahí la funcionalidad tampoco
        está encendida, así que el valor es el correcto y no un rodeo: lo que
        se evita es reventar durante el arranque.

        Es ``classmethod`` porque no interroga a ningún grupo concreto: la
        fuente lo declara ``@api.model``, que es su equivalente exacto — un
        método del modelo, no del registro.

        ``ResUsers`` se importa al top de este módulo (``:103``), así que aquí
        no hace falta resolverlo por el registro de apps.
        """
        superuser = ResUsers.objects.filter(pk=SUPERUSER_ID).first()
        if superuser is None:
            return False
        return superuser.has_group(group_reference)

    # === El álgebra de conjuntos ==========================================

    @classmethod
    @api.model
    @ormcache(cache='groups')
    def _get_group_definitions(cls):
        """Todos los grupos como un :class:`tools.set_expression.SetDefinitions`.

        ≙ ``_get_group_definitions``
        (``odoo19c: base/models/res_groups.py:362-376``), verbatim en las tres
        claves que arma por grupo: ``ref`` (su identificador externo, o el id
        en texto si no tiene), ``supersets`` (``implied_ids``) y ``disjoints``
        (``disjoint_ids``).

        Es el **constructor** del objeto que ``IrModelAccess._get_access_groups``
        consume: sin él, esa expresión no se puede construir y el permiso por
        grupo no se puede expresar como "pertenece a A **y** no a B".

        ``ref`` cae a ``str(pk)`` cuando el grupo no tiene identificador
        externo — es el ``or str(group.id)`` de la fuente, no un respaldo
        nuestro. Hoy ese es el caso de **todos** los grupos de este árbol: la
        tabla ``ir.model.data`` existe y tiene su escritor
        (``IrModelData.set_xmlid``), pero el cargador de archivos de datos
        declarativos aún no siembra los grupos. El álgebra funciona igual: el
        ``ref`` sólo se usa para imprimir y para ``parse``, y las relaciones
        —que es lo que decide— salen de los ids.

        La memoria va a la familia ``groups`` (``orm/registry.py:84``), la
        misma que la fuente nombra, y se invalida con
        ``registry.clear_cache('groups')``, que dispara toda escritura sobre
        el M2M de grupos.

        .. warning:: Esa invalidación es **por proceso**, y con
           ``workers = 4`` eso importa.

           Corregido 2026-08-31 (:ref:`h-api-980`). Esta línea decía *«la
           invalidación ya existe»* a secas, y se leía como completa. Lo es
           dentro del proceso que escribe; los otros tres siguen respondiendo
           con el álgebra vieja hasta que reciclen.

           La fuente cierra ese hueco con ``signal_changes`` /
           ``check_signaling`` (``odoo19c: odoo/orm/registry.py:1076-1140``):
           una secuencia por caché en tablas ``orm_signaling_<nombre>``, que
           cada proceso compara al empezar a atender. Medido: **0** en este
           árbol.

           Pesa más aquí que en cualquier otra caché porque lo que memoriza es
           el álgebra sobre la que se deciden los permisos: un grupo retirado
           en un worker sigue concediendo en los otros tres. El mecanismo se
           construye —es PostgreSQL llano, que es justo lo que este stack
           tiene— en la tarea **#256**.

           ``ir_ui_view.py`` llegó a la conclusión **contraria** desde el
           mismo hecho: rehusó adoptar su caché de plantillas citando este
           mismo hueco. Dos archivos del mismo addon, dos desenlaces opuestos,
           y ninguno sabía del otro.

        Divergencia de ENLACE, la misma que ``precision_get`` ya declara: la
        fuente lo marca ``@api.model`` sobre un método de instancia; aquí es un
        ``classmethod``, porque sin conjuntos de registros el receptor natural
        es la clase. ``@api.model`` se conserva encima y ``ormcache`` lee
        ``_name`` igual del ``cls`` — que ahora existe, por la cabecera de
        arriba.
        """
        groups = list(cls.objects.order_by('pk'))
        id_to_ref = cls.objects.filter(
            pk__in=[group.pk for group in groups]).get_external_id()
        return SetDefinitions({
            group.pk: {
                'ref': id_to_ref.get(group.pk) or str(group.pk),
                'supersets': list(group.implied_ids.values_list('pk', flat=True)),
                'disjoints': list(group.disjoint_ids.values_list('pk', flat=True)),
            }
            for group in groups
        })

    @property
    def all_implied_ids(self):
        """El grupo con todos sus implicados, directos e indirectos.

        Reflexiva: incluye al propio grupo, como el ``g.ids + …`` de la fuente.

        ≙ ``_compute_all_implied_ids`` (``odoo19c: base/models/res_groups.py``).
        """
        return type(self).objects.filter(
            pk__in=self._closure([self], lambda g: g.implied_ids.all()))

    @property
    def all_implied_by_ids(self):
        """Todos los grupos que implican a éste, directa o indirectamente.

        ≙ ``_compute_all_implied_by_ids`` (``odoo19c: base/models/res_groups.py``).
        """
        return type(self).objects.filter(
            pk__in=self._closure([self], lambda g: g.implied_by_ids.all()))

    @property
    def disjoint_ids(self):
        """Grupos con los que éste es mutuamente excluyente.

        Vacío si el grupo no declara tipo de usuario — igual que la fuente
        devuelve falso para un grupo que no es de tipo.

        ≙ ``_compute_disjoint_ids`` (``odoo19c: base/models/res_groups.py``).
        """
        model = type(self)
        if not self.user_type:
            return model.objects.none()
        return model.objects.filter(
            user_type__isnull=False).exclude(user_type=self.user_type)

    # === Invariantes ======================================================

    def check_user_disjoint_groups(self):
        """Verifica que ningún usuario esté en dos grupos disjuntos.

        Conserva la decisión de escala de la fuente, que su comentario
        justifica: recorrer todos los usuarios del grupo no escala pasados
        ~10 000, así que se **busca uno** que viole la exclusión. Si la
        búsqueda devuelve algo, hay violación.

        :raises ValidationError: si existe tal usuario.
        """
        disjoint = list(self.disjoint_ids.values_list('pk', flat=True))
        if not disjoint:
            return
        offender = (
            self.user_ids.filter(group_ids__in=disjoint)
            .values_list('pk', flat=True)
            .first()
        )
        if offender is not None:
            raise ValidationError(
                'El usuario %s no puede pertenecer a este grupo y a uno de sus '
                'grupos disjuntos a la vez.' % offender
            )

    # === Usuarios de la clausura ==========================================

    @property
    def all_user_ids(self):
        """Usuarios del grupo y de todos los que lo implican.

        ``all_user_ids`` de la fuente: quien está en un grupo que implica a
        éste, está implícitamente en éste.

        ≙ ``_compute_all_user_ids`` (``odoo19c: base/models/res_groups.py``).
        """
        implying = self.all_implied_by_ids.values_list('pk', flat=True)
        return ResUsers.objects.filter(group_ids__in=list(implying)).distinct()

    @property
    def all_users_count(self):
        """Cuántos usuarios lo tienen, implícita o explícitamente.

        ≙ ``_compute_all_users_count`` (``odoo19c: base/models/res_groups.py``).
        """
        return self.all_user_ids.count()

    # === Mutación del grafo ===============================================

    def apply_group(self, implied_group):
        """Añade ``implied_group`` a los implicados — ``_apply_group``.

        No-op si ya está en la clausura: la fuente filtra por
        ``implied_group not in g.all_implied_ids``, es decir, no vuelve a
        declarar una arista que la transitividad ya da.
        """
        if implied_group.pk in {g.pk for g in self.all_implied_ids}:
            return
        self.implied_ids.add(implied_group)

    def remove_group(self, implied_group):
        """Quita ``implied_group`` de los implicados — ``_remove_group``.

        La fuente lo quita de **todos** los grupos de la clausura que lo
        declaren directamente, no sólo de éste: si un implicado intermedio
        mantiene la arista, el grupo seguiría implicándolo por transitividad.
        """
        for group in self.all_implied_ids:
            if group.implied_ids.filter(pk=implied_group.pk).exists():
                group.implied_ids.remove(implied_group)
