"""``html.field.history.mixin`` — el historial de revisiones de un campo HTML.

Adaptación de ``odoo19c: addons/html_editor/models/html_field_history_mixin.py``
(167 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**9 símbolos en la fuente, 9 portados, 0 ausentes.** Dos campos, un atributo
de clase y seis métodos.

Qué hace
========

Un modelo que herede este mixin declara en :meth:`_get_versioned_fields` qué
campos HTML suyos llevan historia. A partir de ahí, **cada escritura que
cambie uno de ellos** guarda en ``html_field_history`` un parche que revierte
el valor nuevo al viejo (``models/diff_utils.py``), con su autor y su fecha.
Las revisiones se guardan de la más nueva a la más vieja y se recortan a
:attr:`_html_field_history_size_limit`.

El diseño es **hacia atrás a propósito**: la base guarda el valor *actual* y
la cadena de parches que lleva a cualquier pasado. Guardar cada versión
entera multiplicaría por 300 el tamaño de la columna.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``fields.Json`` (``jsonb``)      **postgresql** — ``fields.Json`` es el
                                 ``JSONField`` de Django sobre ``jsonb``
``write`` del ORM                **django** — ``Model.save()``. Ver
                                 «Las tres divergencias» abajo.
``compute`` sin ``store``        **django** — ``property``, la forma que
                                 ``extend_model(propiedades=…)`` fija
``self.env.cr.now()``            **django** — ``django.utils.timezone``
``self.env.uid`` / ``env.user``  ``orm.environments.get_current_uid`` /
                                 ``get_current_user`` (el ``ContextVar``
                                 que este árbol usa como entorno)
===============================  =====================================

Las tres divergencias de mecanismo, declaradas
==============================================

**1. ``create`` y ``write`` existen con su nombre; ``save`` es su cuerpo.**
Los dos símbolos de la fuente se portan como métodos propios —
:meth:`~HtmlFieldHistoryMixin.create` (``classmethod``, como en
``stock.location`` y ``base_iban``) y :meth:`~HtmlFieldHistoryMixin.write` —
y los dos delegan en :meth:`~HtmlFieldHistoryMixin.save`, que es **el único
punto de escritura de este ORM**. Poner el cuerpo en ``save`` no es
comodidad: por ahí pasan también ``objects.create``,
``objects.update_or_create`` y el cargador de datos, así que dejar la
generación de la revisión en ``write`` la haría saltable desde cualquiera de
esos caminos. Las dos ramas se distinguen por ``self.pk is None``, que es
exactamente la pregunta que separa ``create`` de ``write``:

- rama de creación ≙ ``create`` — descarta el ``html_field_history`` que llegue
  de fuera, para que nadie pueda sembrar un historial falso al crear;
- rama de escritura ≙ ``write`` — lee el contenido en base **antes** de
  guardar, delega en ``super().save()`` y sólo entonces calcula el parche.

El orden importa y la fuente lo dice en un comentario que se conserva
verbatim: el parche se calcula **después** de guardar para diferenciar sobre
el dato ya saneado, no sobre lo que entró.

**2. ``write`` multi-registro → un registro.** La fuente itera ``for rec in
self`` porque su ``self`` es un *recordset*. ``Model.save()`` es de instancia,
así que el bucle desaparece y su cuerpo queda como está. No se pierde
comportamiento: escribir N registros es llamar N veces.

**3. ``field.sanitize`` no existe en este árbol.** La guarda de la fuente
rechaza versionar un campo que no esté declarado ``sanitize=True``, porque un
parche guardado de HTML sin sanear reinyectaría lo que el saneo quitó.
``orm.fields_textual.Html`` de este árbol declara en su propio docstring que
va *"sin saneo (capa UI)"* — el saneo lo hace ``dompurify`` en ``ui``.

La guarda **se porta con el predicado más fuerte que este árbol admite**: el
campo versionado tiene que ser un ``fields.Html``. Eso conserva lo que la
guarda protege de verdad —que no se versione un ``Char`` o un ``Text`` crudo,
donde el editor nunca pasó— y falla igual de ruidoso.

Sucesor nombrado: dotar a ``orm.fields_textual.Html`` del atributo
``sanitize``/``sanitize_tags``/``sanitize_overridable``/``sanitize_form`` que
la referencia declara, y entonces endurecer este predicado. Vive en ``src/orm``
y por tanto **fuera del alcance de este puerto**; se reporta al orquestador
como el sucesor de esta divergencia junto con los tres consumidores que ya lo
esperan (``models.py`` de este addon publica ``sanitize``/``sanitize_tags`` en
los atributos de vista, y ``ir_qweb_fields.IrQwebFieldHtml.attributes`` lee
cuatro de esas banderas).
"""
import fields
import api
import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from orm.environments import get_current_uid, get_current_user

from addons.html_editor.models.diff_utils import (
    apply_patch,
    generate_comparison,
    generate_patch,
    generate_unified_diff,
)


class HtmlFieldHistoryMixin(models.DefaultGetMixin, models.Model):
    """≙ ``HtmlFieldHistoryMixin`` (``odoo19c: :9``).

    Los tres atributos de clase que la fuente declara van verbatim; no declara
    ninguno más (medido con el recorrido AST de
    ``atributos-de-clase-de-modelo.md``).
    """

    _name = 'html.field.history.mixin'
    _description = "Field html History"
    _html_field_history_size_limit = 300

    html_field_history = fields.Json(
        null=True, blank=True, editable=False,
        verbose_name="History data",
        help_text='Odoo html_field_history (prefetch=False, readonly).',
    )

    class Meta:
        abstract = True

    @property
    def html_field_history_metadata(self):
        """≙ el campo calculado ``html_field_history_metadata`` (``:16-18``).

        ``compute`` sin ``store`` → ``property``. El valor lo produce
        :meth:`_compute_metadata`, que se conserva con su nombre y su guion
        bajo porque es el símbolo que la fuente declara.
        """
        return self._compute_metadata()

    @classmethod
    def _get_versioned_fields(cls):
        """≙ ``_get_versioned_fields`` (``:20-26``).

        Este método debería sobreescribirse.

        :return: List[string]: la lista de nombres de los campos a versionar
        """
        return []

    def _compute_metadata(self):
        """≙ ``_compute_metadata`` (``:28-40``).

        Las mismas revisiones **sin el parche**: es lo que la vista de
        historial necesita para pintar la lista sin transferir los diffs.
        """
        history_metadata = None
        if self.html_field_history:
            history_metadata = {}
            for field_name in self.html_field_history:
                history_metadata[field_name] = []
                for revision in self.html_field_history[field_name]:
                    metadata = revision.copy()
                    metadata.pop("patch")
                    history_metadata[field_name].append(metadata)
        return history_metadata

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``:42-46``).

        La fuente descarta el ``html_field_history`` que llegue en los valores
        antes de delegar en ``super().create``: nadie puede sembrar un
        historial falso al crear. Aquí ocurre lo mismo, y :meth:`save`, por el
        que la fila pasa, repite el descarte para el llamador que use
        ``objects.create(...)`` directamente.

        La referencia recibe ``vals_list`` y devuelve el recordset; desde
        :ref:`h-api-1108` la firma es la misma aquí — ``@api.model_create_multi``
        convierte un dict suelto en ``[vals]`` — y ``super().create`` es
        ``DefaultGetMixin.create`` (``orm/models.py``), el porte por contenido de
        ``BaseModel.create``.
        """
        for vals in vals_list:
            vals.pop('html_field_history', None)
        return super().create(vals_list)

    def write(self, **vals):
        """≙ ``write`` (``:48-108``).

        Aplica los valores y persiste. El cuerpo que genera la revisión vive
        en :meth:`save`, que es el único punto de escritura de este ORM y por
        el que pasan también ``objects.update_or_create`` y el cargador de
        datos: dejarlo aquí lo haría saltable. Lo que la fuente hace en dos
        ``super().write`` —el de los valores y el del historial nuevo— lo hace
        aquí ese ``save``, en el mismo orden y por la misma razón.

        La fuente itera ``for rec in self`` porque su ``self`` es un
        *recordset*; aquí es un registro, así que el bucle desaparece.
        """
        vals.pop('html_field_history', None)
        for name, value in vals.items():
            setattr(self, name, value)
        self.save()
        return True

    def save(self, *args, **kwargs):
        """El punto de escritura de Django — ``create`` + ``write``.

        Las dos ramas de la fuente se distinguen por ``self.pk is None``, que
        es exactamente la pregunta que separa una de otra. Ver «Las tres
        divergencias» en el docstring del módulo.
        """
        is_new = self.pk is None

        if is_new:
            # ≙ ``create``: el historial no se acepta desde fuera al crear.
            self.html_field_history = None
            return super().save(*args, **kwargs)

        versioned_fields = self._get_versioned_fields()
        rec_db_contents = {}
        changed_versioned_fields = []

        if versioned_fields:
            stored = (type(self).objects.filter(pk=self.pk)
                      .values(*versioned_fields).first())
            if stored is not None:
                rec_db_contents = dict(stored)
                changed_versioned_fields = [
                    name for name in versioned_fields
                    if getattr(self, name) != rec_db_contents.get(name)
                ]

        # ≙ ``if 'html_field_history' in vals: del vals['html_field_history']``
        # — el historial tampoco se acepta desde fuera al escribir: se
        # restaura el valor en base y se recalcula abajo.
        history_revs = (type(self).objects.filter(pk=self.pk)
                        .values_list('html_field_history', flat=True).first())
        self.html_field_history = history_revs

        # Se llama a super().save() ANTES de generar el parche para asegurar
        # que el diff se hace sobre el dato ya saneado.
        write_result = super().save(*args, **kwargs)

        if not changed_versioned_fields:
            return write_result

        new_revisions = False
        model_fields = {f.name: f for f in type(self)._meta.get_fields()
                        if hasattr(f, 'name')}

        if any(name in changed_versioned_fields
               and not isinstance(model_fields.get(name), fields.Html)
               for name in versioned_fields):
            raise ValidationError(
                "Ensure all versioned fields ( %s ) in model %s are declared "
                "as fields.Html" % (str(versioned_fields), self._name)
            )

        history_revs = self.html_field_history or {}

        for field in versioned_fields:
            new_content = getattr(self, field) or ""

            if field not in history_revs:
                history_revs[field] = []

            old_content = rec_db_contents.get(field) or ""
            if new_content != old_content:
                new_revisions = True
                patch = generate_patch(new_content, old_content)
                revision_id = (
                    (history_revs[field][0]["revision_id"] + 1)
                    if history_revs[field]
                    else 1
                )

                user = get_current_user()
                history_revs[field].insert(
                    0,
                    {
                        "patch": patch,
                        "revision_id": revision_id,
                        "create_date": timezone.now().isoformat(),
                        "create_uid": get_current_uid(),
                        "create_user_name": getattr(user, 'name', None),
                    },
                )
                limit = self._html_field_history_size_limit
                history_revs[field] = history_revs[field][:limit]

        # Se vuelve a guardar para incluir la revisión nueva.
        if new_revisions:
            self.html_field_history = history_revs
            type(self).objects.filter(pk=self.pk).update(
                html_field_history=history_revs)

        return write_result

    def html_field_history_get_content_at_revision(self, field_name,
                                                   revision_id):
        """≙ ``html_field_history_get_content_at_revision`` (``:110-128``).

        Devuelve el contenido del campo restaurado a ``revision_id``.

        :param str field_name: el nombre del campo
        :param int revision_id: id de la última revisión a restaurar

        :return: string: el contenido restaurado
        """
        revisions = [
            i
            for i in self.html_field_history[field_name]
            if i["revision_id"] >= revision_id
        ]

        content = getattr(self, field_name) or ""
        for revision in revisions:
            content = apply_patch(content, revision["patch"])

        return content

    def html_field_history_get_comparison_at_revision(self, field_name,
                                                      revision_id):
        """≙ ``html_field_history_get_comparison_at_revision`` (``:130-145``).

        Comparación entre el contenido actual del campo y el restaurado a
        ``revision_id``.

        :param str field_name: el nombre del campo
        :param int revision_id: id de la última revisión a comparar

        :return: string: la comparación
        """
        restored_content = self.html_field_history_get_content_at_revision(
            field_name, revision_id
        )

        return generate_comparison(restored_content,
                                   getattr(self, field_name) or "")

    def html_field_history_get_unified_diff_at_revision(self, field_name,
                                                        revision_id):
        """≙ ``html_field_history_get_unified_diff_at_revision`` (``:147-167``).

        *Unified diff* entre el contenido actual del campo y el restaurado a
        ``revision_id``.

        :param str field_name: el nombre del campo
        :param int revision_id: id de la última revisión a comparar

        :return: string: el *unified diff*
        """
        restored_content = self.html_field_history_get_content_at_revision(
            field_name, revision_id
        )

        return generate_unified_diff(getattr(self, field_name) or "",
                                     restored_content)
