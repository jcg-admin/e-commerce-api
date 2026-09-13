"""Lo que el autor declara aterriza en el campo — también sin ``compute=``.

Mitad ROJA del hueco 1 de :ref:`h-api-1103`. ``_declared_source_vocabulary``
(``orm/fields_nonstored.py:340-354``) **saca** de ``kwargs`` el vocabulario de
la fuente y ``apply_source_defaults`` lo deja en ``attrs``; pero
``annotate_related:558`` sale temprano cuando la declaración no trae
``related`` ni ``compute``, así que en la rama de campo llano nada de eso llega
nunca al objeto campo. Se pierde **en silencio**: el default de clase
(``orm/fields.py:1915-1945``) devuelve exactamente el valor que el autor quiso
cambiar.

La salida temprana es NUESTRA, no de la fuente
===============================================

``odoo19c: odoo/orm/fields.py:491-500`` — ``_setup_attrs__`` aplica el
diccionario **incondicionalmente**::

    attrs = self._get_attrs(model_class, name)
    ...
    self.__dict__.update(attrs)

No pregunta si el campo es ``related`` ni si es calculado. Y su
``__set_name__`` (``:399-402``) lo invoca para todo campo ``_direct`` o
``_toplevel``, otra vez sin filtrar por vocabulario. Un problema que aparece al
portar y que la fuente no tiene es señal de que el porte inventó algo.

Los cuatro, y su población en la referencia
--------------------------------------------

Declaraciones ``fields.X(...)`` sin ``compute=`` ni ``related=`` que traen el
atributo, medidas por AST sobre los 3328 archivos de modelo de ``odoo19c``:

===============  =====  ==========================================
atributo         nº     ejemplo
===============  =====  ==========================================
``readonly``     645    ``l10n_id_efaktur_coretax/models/efaktur_document.py:15``
``inverse``      35     ``l10n_latam_base/models/res_partner.py:9``
``recursive``    3      ``odoo/addons/test_orm/models/test_orm.py:28``
``compute_sudo`` 1      ``website_hr_recruitment/models/hr_department.py:10``
===============  =====  ==========================================

``precompute`` **no** está en la lista aunque la sonda lo viera en ``False``:
ahí las dos partes normalizan a ``False`` con aviso —``odoo19c: :459-465`` y
``orm/fields_nonstored.py:418-437``—, así que el valor coincide por la razón
correcta. Confundir *«se descartó»* con *«la fuente produce lo mismo»* es medir
el significante; el banco lo registra en M13-bis.

Qué haría fallar a estos casos
-------------------------------

Que la salida temprana de ``annotate_related`` vuelva: con ella, las nueve
aserciones de :class:`TestTheDeclarationLandsOnAPlainField` y
:class:`TestItAlsoLandsAfterContributeToClass` caen, y ninguna de las de
:class:`TestTheClassDefaultIsNotStamped` ni
:class:`TestTheComputedPathStillWorks` se mueve — ése es el control de
anulación, y su asimetría es lo que lo hace discriminar.
"""
import pytest
from django.db import models

import fields
from orm.fields_nonstored import NonStored, apply_source_defaults


#: Los cuatro que la rama llana pierde, con un valor DISTINTO del default de
#: clase: si el caso declarara el default, un «quedó == default» no separaría
#: pérdida de coincidencia.
LOST_ON_A_PLAIN_FIELD = [
    ('readonly', True, False),
    ('compute_sudo', True, False),
    ('inverse', '_inverse_label', None),
    ('recursive', True, False),
]

#: Las claves que ``apply_source_defaults`` deja en ``attrs`` para un campo
#: llano **aunque nadie las declare** — medido, no supuesto::
#:
#:     sin declarar nada    ['compute', 'declared_keys', 'inverse',
#:                           'precompute', 'store']
#:
#: Son las que el filtro de ``declared_keys`` retiene. Sin él aterrizarían las
#: cuatro, y sólo una (``inverse``) está en ``LOST_ON_A_PLAIN_FIELD``: un
#: control parametrizado sólo por esa lista mediría **una** de las cuatro y
#: publicaría verde sobre las otras tres. ``declared_keys`` no entra porque es
#: contabilidad del mecanismo y ``annotate_related`` la salta explícitamente.
UNCONDITIONAL_IN_ATTRS = ['compute', 'inverse', 'precompute', 'store']

#: El universo del control de no-estampado: lo que el arreglo trajo más lo que
#: el filtro retiene. ``inverse`` cae en los dos.
NOT_STAMPED_WITHOUT_DECLARATION = sorted(
    {a for a, _, _ in LOST_ON_A_PLAIN_FIELD} | set(UNCONDITIONAL_IN_ATTRS))


class TestTheDeclarationLandsOnAPlainField:
    """El campo con columna conserva lo que su autor declaró."""

    @pytest.mark.parametrize('attribute,declared,default', LOST_ON_A_PLAIN_FIELD)
    def test_it_keeps_the_declared_value(self, attribute, declared, default):
        field = fields.Char(**{attribute: declared})
        assert getattr(field, attribute) == declared

    @pytest.mark.parametrize('attribute,declared,default', LOST_ON_A_PLAIN_FIELD)
    def test_the_case_discriminates_from_the_class_default(self, attribute,
                                                           declared, default):
        """El control del control: cada caso pide algo que el default NO da."""
        assert declared != default

    def test_a_plain_field_with_an_inverse_still_has_its_column(self):
        """``inverse`` no implica ausencia de columna. La referencia lo declara
        sobre un campo con columna 35 veces —``ir_actions.py:691`` lo hace
        incluso sobre un ``Many2one``—, así que el enrutador no debe reaccionar
        a él."""
        field = fields.Char(inverse='_inverse_label')
        assert not isinstance(field, NonStored), type(field).__name__


class TestItAlsoLandsAfterContributeToClass:
    """El momento que la sonda de constructor no alcanza.

    ``contribute_to_class`` es donde Django instala el campo en el modelo, y es
    posterior a todo lo que mide el caso anterior. Un arreglo que sólo anotara
    en el constructor y otro que además sobreviviera a la contribución serían
    indistinguibles sin este bloque.
    """

    @pytest.fixture(scope='class')
    def model_class(self):
        return type('DeclaredVocabularyProbe', (models.Model,), {
            #: El modelo de la sonda declara SU módulo, no el del árbol.
            #: ``test_domain_in_required`` fija su población por
            #: ``__module__.startswith('addons.base.models')`` justamente para
            #: que un modelo de pruebas no la engorde; declararlo ahí lo
            #: colaba dentro y su conteo pasaba de 27 a 28.
            '__module__': __name__,
            'label': fields.Char(max_length=64, readonly=True,
                                 compute_sudo=True, inverse='_inverse_label',
                                 recursive=True),
            'Meta': type('Meta', (), {'app_label': 'base', 'managed': False}),
        })

    @pytest.mark.parametrize('attribute,declared,default', LOST_ON_A_PLAIN_FIELD)
    def test_the_contributed_field_keeps_it(self, model_class, attribute,
                                            declared, default):
        field = model_class._meta.get_field('label')
        assert getattr(field, attribute) == declared


class TestTheClassDefaultIsNotStamped:
    """La restricción que el comentario de la salida temprana defendía, y que
    el arreglo conserva: un campo que no declara nada NO gana un atributo de
    instancia por cada clave del vocabulario.

    Es legítima como restricción y no como filtro — la fuente tampoco anota lo
    que nadie declaró, porque su ``attrs`` sale de ``_get_attrs``, que sólo
    recoge lo que el autor pasó.
    """

    @pytest.mark.parametrize('attribute', NOT_STAMPED_WITHOUT_DECLARATION)
    def test_an_undeclared_attribute_stays_on_the_class(self, attribute):
        field = fields.Char()
        assert attribute not in field.__dict__, (
            f'{attribute} se anotó en la instancia sin que nadie lo declarara')

    @pytest.mark.parametrize('attribute,_declared,default',
                             LOST_ON_A_PLAIN_FIELD)
    def test_and_the_class_still_answers_the_default(self, attribute, _declared,
                                                     default):
        assert getattr(fields.Char(), attribute) == default

    @pytest.mark.parametrize('attribute', UNCONDITIONAL_IN_ATTRS)
    def test_the_universe_of_the_control_is_the_measured_one(self, attribute):
        """El control del control: si ``apply_source_defaults`` dejara de poner
        estas cuatro en ``attrs``, el caso de arriba seguiría verde midiendo un
        universo más chico — verde por ausencia de sujeto, que es el
        sub-patrón D de ``metrica-decide-la-conclusion.md``.
        """
        attrs = apply_source_defaults(None, {})
        assert attribute in attrs, (
            f'{attribute} ya no viaja en attrs: el control de no-estampado '
            f'dejó de medirlo')


class TestTheContractOfTheEndpointDoesNotMove:
    """Lo que el arreglo NO cambia, medido en los dos árboles.

    ``editable=False`` para un ``readonly=True`` llano es **anterior** al
    arreglo: la inyección de ``apply_source_defaults`` lee ``attrs['readonly']``,
    y esa clave ya la ponía la rama ``elif not declared['compute']``. Medido
    sobre ``HEAD`` y sobre el árbol con el arreglo::

        HEAD          field.readonly = False | field.editable = False
        con arreglo   field.readonly = True  | field.editable = False

    O sea: el contrato del endpoint ya honraba la declaración —DRF lo lee en
    ``get_field_kwargs`` (``field_mapping.py:124-128``)— y el que mentía era el
    **atributo del ORM**. El caso queda como guarda: si alguien mueve la
    inyección de ``editable`` al retirar la salida temprana, esto cae.
    """

    def test_a_readonly_plain_field_is_not_editable(self):
        assert fields.Char(readonly=True).editable is False

    def test_and_an_undeclared_one_still_is(self):
        """El control del control: el caso de arriba no pasa por vacuidad."""
        assert fields.Char().editable is True


class TestTheComputedPathStillWorks:
    """Regresión: la rama que YA anotaba sigue anotando."""

    def test_a_computed_field_keeps_its_vocabulary(self):
        field = fields.Char(store=False, compute='_compute_label',
                            inverse='_inverse_label', recursive=True)
        assert field.compute == '_compute_label'
        assert field.inverse == '_inverse_label'
        assert field.recursive is True

    def test_a_related_field_keeps_its_path(self):
        field = fields.Char(related='partner_id.name')
        assert field.related == 'partner_id.name'
