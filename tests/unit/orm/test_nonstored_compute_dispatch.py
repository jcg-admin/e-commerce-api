"""El ``compute=`` declarado sobre un campo sin columna se despacha al leerlo.

Mitad ROJA de :ref:`task-api-0415`. ``NonStored.__init__`` guarda
``self.compute`` (``orm/fields_nonstored.py:118``) y su propio docstring
declara el hueco verbatim: *"Hoy nadie lo invoca — el valor sigue saliendo de
``related`` o de ``default``"*. Por eso los dos campos sin columna del árbol
que la referencia declara calculados —``display_name`` (``orm/models.py:2942``)
y ``full_name`` (``addons/base/models/res_groups.py:177``)— pasan su cómputo
por ``default=`` con un envoltorio que lo llama, en vez de por ``compute=``.

La referencia tiene la rama, y es explícita
===========================================

``odoo19c: odoo/orm/fields.py:1736-1737`` abre la rama con su comentario::

    elif self.compute:
        # non-stored field or new record without origin: compute

Su cuerpo llama ``self.compute_value(recs)`` (``:1744``), que termina en
``records._compute_field_value(self)`` (``:1915``), cuyo cuerpo entero es::

    determine(field.compute, self)

    if field.store and any(self._ids):
        ...

(``odoo19c: odoo/orm/models.py:4953-4959``). Para un campo **sin columna** el
``if field.store:`` no se alcanza: el cuerpo efectivo de la rama es
``determine(field.compute, records)``, y ``determine`` ya está portado en
``orm/fields.py:1699``.

El ORDEN es el de la referencia, no una elección
------------------------------------------------

``related`` se comprueba **antes** que ``compute`` porque allá un ``related``
**es** un compute: ``self.compute = self._compute_related``
(``odoo19c: odoo/orm/fields.py:632``) lo sobreescribe al montar la cadena, así
que la rama de related gana siempre. Y el valor escrito gana sobre los dos
porque la referencia lee ``field_cache[record_id]`` (``:1673``) antes de
cualquier rama de cálculo.

Qué haría fallar a estos casos
-------------------------------

Retirar la rama de ``compute`` de ``NonStored.__get__``: caen las cuatro
aserciones de :class:`TestTheDeclaredComputeIsDispatched` y **ninguna** de
:class:`TestTheOtherTwoBranchesStillWin` ni de
:class:`TestWhatTheBranchDoesNotChange`. Esa asimetría es lo que lo hace
discriminar — un control que también moviera las otras estaría midiendo el
descriptor entero, no la rama.
"""
import pytest
from django.db import models

import fields
from orm.fields_nonstored import NonStored


class ComputeDispatchProbe(models.Model):
    """Sujeto de la sonda: declara los cómputos que los casos despachan.

    Declara su propio ``__module__`` —el del archivo de prueba— por la misma
    razón que ``test_declared_source_vocabulary``: un modelo de sonda que dice
    vivir en ``addons.base.models`` engorda las poblaciones que otros casos
    miden por prefijo de módulo.
    """

    #: La forma de la referencia: ``compute=`` y ningún ``store=True``.
    label = fields.Char(compute='_compute_label')
    #: El mismo campo sin cómputo — el control del control.
    plain_label = fields.Char(store=False, default='del default')
    #: El titular de la cadena. **La sonda lo declara desde TASK-API-0412**:
    #: antes la cadena de abajo apuntaba a un campo que este modelo no tenía, y
    #: eso no fallaba sólo porque ``ensure_field_setup()`` abortaba antes de
    #: llegar —en ``company_country_code``, la tarea #353—. Cerrada aquella
    #: costura, el recorrido alcanza esta cadena y la rompe en el import, que
    #: es a la vez el arranque de toda la suite.
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.DO_NOTHING, null=True,
        related_name='+')
    #: La precedencia: con ``related`` la cadena manda aunque haya ``compute``.
    #: El primer eslabón va deletreado como la fuente —``company_id``, que aquí
    #: es el **attname** del campo de arriba—, que es justo lo que
    #: ``model_field_registry`` tuvo que aprender a resolver.
    #:
    #: El segundo eslabón es ``code`` y no ``name``: ``ResCompany.name`` sigue
    #: siendo un ``@property`` —la referencia lo declara
    #: ``related='partner_id.name'`` (``odoo19c: res_company.py:48``)— y un
    #: ``@property`` no vive en ``_meta``, así que ninguna cadena puede
    #: navegarlo. Es el mismo defecto que TASK-API-0412 cerró para la dirección,
    #: una capa más arriba; su sucesor es **TASK-GEN-0634**. La sonda mide la
    #: precedencia, no el inventario de campos de ``ResCompany``.
    company_label = fields.Char(related='company_id.code',
                                compute='_compute_label')

    class Meta:
        app_label = 'base'
        managed = False

    def _compute_label(self):
        return 'calculado'


class TestTheDeclaredComputeIsDispatched:
    """Lo que hoy no ocurre: el cómputo se llama al leer."""

    def test_the_read_returns_what_the_compute_produces(self):
        probe = ComputeDispatchProbe()
        assert probe.label == 'calculado'

    @pytest.mark.parametrize('produced', ['uno', 'otro distinto'])
    def test_the_value_tracks_the_compute_and_not_a_constant(self, produced):
        """El control del control, y su primera forma NO discriminaba.

        Decía ``label != plain_label`` — ``None != 'del default'`` hoy y
        ``'calculado' != 'del default'`` después: verde en los dos estados, o
        sea verde por ausencia de sujeto (sub-patrón D de
        ``metrica-decide-la-conclusion.md``). Dos cómputos que devuelven cosas
        distintas no los puede satisfacer ninguna constante.
        """
        field = fields.Char(compute=lambda record: produced)
        field.name = 'tracked'
        assert field.__get__(ComputeDispatchProbe()) == produced

    def test_the_facade_routes_a_bare_compute_to_the_descriptor(self):
        """``compute=`` sin ``store=`` da ``store=False`` por el bloque de la
        fuente (``odoo19c: fields.py:443-450``), así que el enrutador tiene que
        devolver el descriptor — no un campo con columna."""
        declared = fields.Char(compute='_compute_label')
        assert isinstance(declared, NonStored), type(declared).__name__

    def test_a_callable_compute_is_dispatched_too(self):
        """``determine`` admite cadena **o** invocable (``fields.py:1699``);
        la referencia lo usa en las dos formas."""
        field = fields.Char(compute=lambda record: 'por invocable')
        field.name = 'ad_hoc'
        assert field.__get__(ComputeDispatchProbe()) == 'por invocable'


class TestTheOtherTwoBranchesStillWin:
    """La precedencia de la referencia, que la rama nueva no altera."""

    def test_the_written_value_beats_the_compute(self):
        probe = ComputeDispatchProbe()
        probe.label = 'escrito a mano'
        assert probe.label == 'escrito a mano'

    def test_related_beats_the_compute(self):
        """Con ``related`` la cadena manda: allá ``self.compute`` ya ES
        ``_compute_related`` (``odoo19c: fields.py:632``), así que nunca corre
        el cómputo del autor."""
        probe = ComputeDispatchProbe()
        assert probe.company_label != 'calculado'


class TestWhatTheBranchDoesNotChange:
    """Regresión: el camino de ``default`` sigue siendo el de siempre."""

    def test_a_field_without_compute_still_reads_its_default(self):
        assert ComputeDispatchProbe().plain_label == 'del default'

    def test_a_field_with_neither_reads_none(self):
        field = fields.Char(store=False)
        field.name = 'vacio'
        assert field.__get__(ComputeDispatchProbe()) is None
