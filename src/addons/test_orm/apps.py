"""AppConfig del addon ``test_orm``.

≙ ``odoo19c: odoo/addons/test_orm``. La referencia no declara un ``AppConfig``
porque su cargador de addons lee el ``__manifest__.py``; aquí el registro de
aplicaciones es el de Django y ``INSTALLED_APPS`` se deriva del grafo de addons
(``config/settings/base.py``, orden topológico), así que el addon necesita su
``AppConfig`` para entrar en ese grafo.
"""
from django.apps import AppConfig


class TestOrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.test_orm'
    verbose_name       = 'Test ORM (la suite del ORM de la referencia)'
