"""AppConfig — addons.base (equivalente del addon ``base`` de Odoo).

``addons.base`` es el **addon fundacional** del proyecto, fiel a
``odoo/addons/base`` (Odoo 19/18) y a ``pretix/base``: aloja los modelos de
infraestructura tipo ``ir.*`` que no pertenecen a un dominio concreto. Ni Odoo
ni pretix usan una app "config" para esto — el modelo global key/value vive en
``base`` (``ir.config_parameter`` en Odoo; ``GlobalSettingsObject`` en pretix).
"config" en Odoo es la **L1** (``odoo/conf`` — removido en v19 — y
``odoo.tools.config``), que en nuestro árbol es ``src/config`` (settings), no
una app.

Primer inquilino: ``SystemParameter`` (config runtime **global** L2, key/value,
editable en caliente, sembrada y cacheada; equivalente Django de
``ir.config_parameter``). Diseño: ``analisis-estrategia-configuracion-capas``
(L2); portación fiel: ``implementar-systemparameter-l2``.

``addons.base`` vive en el **plano de control** (base ``default``): son modelos
globales de la instancia, no per-empresa (eso es L3 = ``Company``/
``CompanySetting``, SOL-085). Por eso su app_label ``base`` se registra en
``MULTIDB_CONTROL_PLANE_APPS`` (SOL-091) para que el router lo enrute siempre a
``default`` bajo N>1.
"""
from django.apps import AppConfig, apps

from orm.inherits import ensure_inherits
from orm.model_classes import (ensure_access_managers, ensure_base_urls,
                               ensure_display_names,
                               ensure_model_class_attributes,
                               ensure_rec_names)


class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base'
    label = 'base'
    verbose_name = 'Base (infraestructura fundacional ir.*)'

    def ready(self):
        """Instala la delegación ``_inherits`` de ``res.users`` al partner.

        Equivale a ``_inherits = {'res.partner': 'partner_id'}`` de la
        referencia (``odoo19c: odoo/addons/base/models/res_users.py:165``),
        que es de donde el usuario obtiene ``tz``, ``lang`` y el resto de los
        campos del partner.

        Va en ``ready()`` y no al pie del módulo porque ``res_users`` resuelve
        el modelo de partner de forma perezosa (``_partner_model()``) para
        evitar el ciclo de importación; aquí el registro ya está poblado.
        ``apps.get_model`` es una **llamada**, no un ``import`` — el gate de
        no-lazy-imports da exit 0 (misma resolución que la excepción #4 de
        ``no-lazy-imports.md``).

        **El par delegado→FK sale del atributo, no de aquí** (tarea #385). Antes
        estaba escrito a mano en esta llamada; ahora se lee de
        ``ResUsers._inherits``, que es donde la referencia lo declara. Así el
        cableado no puede divergir de la cabecera: cambiar el atributo cambia
        la delegación.

        Antes de eso corre ``ensure_rec_names()``, el barrido que resuelve el
        ``_rec_name`` de todo modelo ya cargado — el paso 5 de
        ``_init_model_class_attributes`` de la fuente
        (``odoo19c: odoo/orm/model_classes.py:433-441``). La señal
        ``class_prepared`` cubre lo que llega después; este barrido cubre lo
        que ya estaba, que es la misma pareja de vías que ``H-API-577``.

        Y con él ``ensure_access_managers()``, que da las cuatro formas de
        permiso de la fuente a todo modelo nuestro que no declare manager
        propio (tarea #96). Misma pareja de vías, mismo motivo.

        Y ``ensure_display_names()``, que da la etiqueta —``display_name`` y su
        bloque de cuatro métodos— a todo modelo nuestro. En la fuente cuelga de
        ``BaseModel`` (``odoo19c: odoo/orm/models.py:473``), así que **todo**
        modelo la tiene; aquí la base común sólo cubre 285 de los 375 modelos
        concretos nuestros, y los 90 restantes la reciben por esta vía.

        Y ``ensure_base_urls()``, que da ``get_base_url`` por la misma razón y
        con el mismo mecanismo: en la fuente cuelga de ``BaseModel``
        (``odoo19c: odoo/orm/models.py:3985``) y aquí ``TimeStampedModel``
        sólo alcanza a 291 de los 389 modelos. Lo consume
        ``ir.actions.report._get_report_url``.
        """
        # Antes que los demas: valida la especie heredada y rellena los
        # defaults que el resto lee (``_description``, ``_table``, la
        # fusion de ``_inherits`` a lo largo de la MRO). Tarea #332.
        ensure_model_class_attributes()
        ensure_rec_names()
        ensure_access_managers()
        ensure_display_names()
        ensure_base_urls()
        # Y ``ensure_inherits()``, que cablea la delegacion de TODO modelo
        # registrado que declare ``_inherits`` — no solo ``ResUsers``. El
        # bucle escrito a mano que habia aqui dejaba fuera a ``ir.cron``, que
        # declara la suya en este mismo addon.
        ensure_inherits()
        # La fase que completa cada campo (``prepare_setup`` + ``setup``,
        # ``odoo19c: odoo/orm/model_classes.py:318-323``) NO corre aquí: este
        # ``ready()`` va antes que los ``extend_model`` de los addons que
        # cuelgan campos de modelos ajenos (medido: ``crm`` añade
        # ``lead_properties_definition`` a ``crm.team`` en su propio
        # ``ready()``). La dispara el primer consumidor tras ``apps.ready``
        # —``orm.model_classes.ensure_field_setup``—, que es el momento
        # «tras el último módulo» de la fuente (``loading.py:488``).
