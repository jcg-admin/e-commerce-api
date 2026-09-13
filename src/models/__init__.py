"""``models`` — fiel a ``odoo/models/__init__.py`` (Odoo 19).

Paquete (no módulo suelto), igual que ``odoo/models/`` es un paquete. Su
comentario de cabecera declara para qué existe, y lo repite palabra por palabra
en las otras dos fachadas del árbol (``odoo/api/``, ``odoo/fields/``)::

    # Exports features of the ORM to developers.
    # This is a `__init__.py` file to avoid merge conflicts on `odoo/models.py`.

Y ``odoo/orm/__init__.py`` declara lo contrario para sí mismo —*"developers
should not import directly from here"*—: no re-exporta nada. Por eso la
re-exportación **es el porte**, no una deuda que se salde aparte: un símbolo
declarado en ``orm/`` y no ligado aquí está portado en otro sitio que el de la
fuente, que es la divergencia de :ref:`h-api-578`.

El ``import *`` es el PUENTE, y es divergencia medida
=====================================================

La fachada de la referencia re-exporta **sólo** el ORM de Odoo, porque allá los
campos viven en ``odoo/fields``. Aquí no: ``models.CharField``,
``models.ForeignKey`` y ``models.CASCADE`` son de ``django.db.models`` y los
escriben así **310 archivos** que hacen ``import models`` (medido por AST
2026-09-02 sobre ``src/``, ``addons/`` y ``tests/``). Retirar el ``*`` los
rompería a los 310.

No es el defecto que :ref:`h-api-604` corrigió en la fachada de campos. Allí el
``*`` congelaba una superficie **nuestra** y escondía su procedencia; aquí
declara una sola cosa, y la declara entera: *la superficie de Django también
entra por esta puerta*. Los símbolos del ORM portado se importan **de cada
módulo que los declara**, debajo, como hace la referencia — así el ``*`` nunca
decide quién gana.

``Index`` sirve a los dos usos, y el reparto está medido
========================================================

Es el único nombre de las tres fachadas que tuvo que decidirse.
``odoo19c: odoo/models/__init__.py`` re-exporta ``Index`` desde
``odoo/orm/table_objects.py``: el **objeto de tabla**, que se declara en el
cuerpo del modelo y recibe su definición SQL posicional —``_active_idx =
models.Index('(active) WHERE active IS TRUE')``—. Aquí ese mismo nombre llega
además por el puente como ``django.db.models.Index``, con **51 usos reales**
que lo pasan en ``Meta.indexes`` con palabras clave.

Lo resuelve ``orm/table_objects.py::Index.__new__``, repartiendo por la
**forma de la llamada**: con argumento posicional es el objeto de tabla; sólo
con palabras clave es el índice nativo. Las dos poblaciones son disjuntas en el
árbol —51 con palabras clave, **0** con posicional (medido por AST)—, así que
el reparto no es ambiguo. Y la rama nativa devuelve el constructo de Django sin
envolver, de modo que su ``deconstruct`` sigue diciendo
``django.db.models.Index`` y las 51 migraciones ya escritas se reconstruyen con
el mismo objeto.

Los cinco pasos medidos y la matriz de criterios que eligió esta salida —frente
a migrar los 51, y frente a declarar divergencia de nombre— viven en
:ref:`analisis-colision-de-nombre-de-index` (#321, #322).

Sus dos hermanos no colisionaban: ``Constraint`` y ``UniqueIndex`` tienen **0**
usos reales del lado de Django. Las 17 menciones de ``models.Constraint`` que
un grep de texto encuentra están todas en prosa que describe la referencia — la
distinción la hace el AST, no el grep.

Los dos que faltan, con su veredicto
====================================

**Bloqueo medido**: ``orm/`` todavía no los declara, y ligar un nombre
inexistente rompe el import del paquete. Cada uno entra con el pase que porta su
símbolo, que es el mismo pase y no un barrido posterior:

- ``MetaModel`` — la metaclase de la fuente
  (``odoo19c: odoo/orm/models.py``). Es #209.
- ``READ_GROUP_DISPLAY_FORMAT`` — la familia de ``read_group``.

``BaseModel`` salió de esta lista en **TASK-API-0397**, que lo portó como base
abstracta de Django y lo ligó abajo en el mismo pase. Su salida la forzó un
control, no la memoria de nadie:
``test_sugar_packages.py::test_src_orm_does_not_declare_it_yet`` se puso rojo el
mismo pase en que la clase aterrizó — que es exactamente para lo que existe.

Esta lista decía **ocho** y su cifra llevaba tres nombres de más. Medido al
portar ``READ_GROUP_TIME_GRANULARITY``: ``AbstractModel``,
``parse_read_group_spec`` y ``check_method_name`` ya se declaran y ya los
re-exporta el bloque de abajo — el propio archivo se contradecía, porque el
tercero aparece nombrado como ausente y como importado con doce líneas de
diferencia. Y el cuarto, ``READ_GROUP_TIME_GRANULARITY``, dejó de faltar en
este pase.

Una lista de pendientes que envejece hacia arriba es peor que ninguna: da por
bloqueado un trabajo que ya está hecho, y el siguiente pase lo re-agenda.

Divergencia de sitio declarada: la referencia saca
``READ_GROUP_NUMBER_GRANULARITY`` de ``odoo/orm/models.py`` y aquí sale de
``orm/utils.py``, junto a su hermano ``READ_GROUP_TIME_GRANULARITY``. El nombre
y el objeto son los de la fuente; lo que difiere es el archivo que lo aloja.
"""
# ruff: noqa: F401,F403
# Exporta las capacidades del ORM a quien escribe un addon.
# Es un `__init__.py` para no pelear merges sobre `orm/models.py`.

# El puente a la superficie de Django (ver el docstring). Va PRIMERO para que
# ningún nombre del ORM portado quede pisado por su homónimo del stack.
from orm.models import *

from orm.models import (
    LOG_ACCESS_COLUMNS,
    MAGIC_COLUMNS,
    AbstractModel,
    BaseModel,
    CopyMixin,
    DefaultGetMixin,
    Model,
    OriginMixin,
    check_companies_domain_parent_of,
    check_company_domain_parent_of,
    fix_import_export_id_paths,
    parse_read_group_spec,
    to_record_ids,
    regex_order,
)
from orm.model_classes import is_model_class, is_model_definition
from orm.models_transient import TransientModel
from orm.table_objects import Constraint, Index, UniqueIndex
from orm.utils import (
    READ_GROUP_NUMBER_GRANULARITY,
    READ_GROUP_TIME_GRANULARITY,
    check_method_name,
    check_object_name,
    check_pg_name,
)
