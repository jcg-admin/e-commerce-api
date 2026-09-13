"""``test_orm`` — la suite del ORM de la referencia, portada.

≙ ``odoo19c: odoo/addons/test_orm/__init__.py``, con una divergencia de
mecanismo MEDIDA, no supuesta: allá el ``__init__`` del addon hace
``from . import models`` porque su cargador lo consume; aquí el registro de
aplicaciones es el de Django y descubre los modelos por el paquete ``models``
del app. Medido sobre los 36 ``__init__.py`` de addon de este árbol: sólo **4**
llevan ese import, y el de ``base`` —la raíz del grafo— está **vacío**.

Importarlo aquí adelanta la carga de ``orm.fields_reference``, que importa
``django.contrib.contenttypes``, a un momento en que el registro de apps aún no
está poblado: ``AppRegistryNotReady``. No es una tensión del porte — es el
orden de arranque del stack, y la convención del árbol ya lo resuelve.

Este addon no es producto: es el **control** del porte de ``src/orm``. Un
símbolo presente con la semántica cambiada pasa cualquier censo de nombres y
falla aquí.
"""
