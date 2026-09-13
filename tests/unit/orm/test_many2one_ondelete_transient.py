r"""La rama ``is_transient()`` del default de ``ondelete`` — el tramo que faltaba.

``:274-282`` de ``odoo19c: odoo/orm/fields_relational.py`` NO tiene dos casos,
tiene tres, y el tercero se decide por el ``_transient`` de las DOS clases::

    if not self.ondelete:
        comodel = model.env[self.comodel_name]
        if model.is_transient() and not comodel.is_transient():
            # "Many2one relations from TransientModel Model are annoying
            #  because they can block deletion due to foreign keys."
            self.ondelete = 'cascade' if self.required else 'set null'
        else:
            self.ondelete = 'restrict' if self.required else 'set null'

El puerto anterior declaró esa rama como no simulable —*"necesita el modelo,
que en ``__init__`` no existe todavía"*— y **la premisa era falsa en su
conclusión**. Medido: ``is_transient`` es un ``@classmethod`` que devuelve
``cls._transient``, un atributo de clase (``odoo19c: odoo/orm/models.py:386``
y ``:5738-5744``). No necesita ``env``, ni instancia, ni registro poblado:
sólo la clase. Lo que era cierto es que ``__init__`` es el sitio equivocado —
la fuente tampoco la decide ahí, sino en ``setup_nonrelated``, una fase
POSTERIOR a la construcción de la clase.

Y esa fase el stack la trae hecha: ``lazy_related_operation`` (Django,
``db/models/fields/related.py``) agenda una función *"once `model` and all
`related_models` have been imported and registered with the app registry"* —
que es literalmente lo que ``setup_nonrelated`` garantiza. No se construye
nada: hay símbolo instalado y basta llamarlo.

Qué haría FALLAR este control (sub-patrón D): que el puerto aplicara el
default transitorio a TODO modelo, o que lo dejara sólo en la declaración —
donde el comodelo aún no existe y la condición no se puede evaluar. El caso
que DISCRIMINA es el primero: sin la rama daría ``RESTRICT``, que es el
default no transitorio, y el campo bloquearía el borrado del wizard, que es
exactamente lo que el comentario de la fuente dice evitar.

*Métrica:* la política que el campo construido lleva en
``remote_field.on_delete`` DESPUÉS de ``django.setup()``, y el atributo
``ondelete`` que la fuente declara sobre el propio campo.
*Ciega a:* ``update_db`` (``:296-300``), que prohíbe el sentido contrario
—un ``Many2one`` de Model a TransientModel— y es otra fase (creación de
tabla), con su propio porte; y al modelo transitorio cuyo comodelo nunca se
registra, donde ``lazy_related_operation`` no dispara y el default declarado
se queda.
"""
from django.db import models as django_models

import fields
from orm.model_classes import is_transient
from orm.models import BaseModel
from orm.models_transient import TransientModel


class TestTheThirdCaseOfTheSource:
    """``model.is_transient() and not comodel.is_transient()``."""

    def test_required_towards_a_persistent_model_cascades(self):
        """EL DISCRIMINANTE — sin la rama esto daria RESTRICT."""
        class WizardPointsAtPartnerProbe(TransientModel):
            partner_id = fields.Many2one('base.ResPartner', null=False)

            class Meta:
                app_label = 'base'

        field = WizardPointsAtPartnerProbe._meta.get_field('partner_id')

        assert field.remote_field.on_delete is django_models.CASCADE

    def test_optional_towards_a_persistent_model_sets_null(self):
        class WizardOptionalProbe(TransientModel):
            partner_id = fields.Many2one('base.ResPartner', null=True)

            class Meta:
                app_label = 'base'

        field = WizardOptionalProbe._meta.get_field('partner_id')

        assert field.remote_field.on_delete is django_models.SET_NULL


class TestTheBranchDoesNotSwallowTheOtherTwo:
    """La rama transitoria no puede pisar el default que ya estaba."""

    def test_a_persistent_model_still_restricts(self):
        class PersistentRequiredProbe(django_models.Model):
            partner_id = fields.Many2one('base.ResPartner', null=False)

            class Meta:
                app_label = 'base'

        field = PersistentRequiredProbe._meta.get_field('partner_id')

        assert field.remote_field.on_delete is django_models.RESTRICT

    def test_a_wizard_towards_another_wizard_restricts(self):
        """``comodel.is_transient()`` verdadero cae al ``else`` de ``:282``."""
        class WizardTargetProbe(TransientModel):
            _name = 'test.transient.target'

            class Meta:
                app_label = 'base'

        class WizardTowardsWizardProbe(TransientModel):
            other_id = fields.Many2one('test.transient.target', null=False)

            class Meta:
                app_label = 'base'

        field = WizardTowardsWizardProbe._meta.get_field('other_id')

        assert field.remote_field.on_delete is django_models.RESTRICT


class TestTheReaderAnswersForAnyModelClass:
    """El contrato de ``:5738-5744``, en la forma que esta jerarquia admite.

    La fuente declara ``is_transient`` como ``@classmethod`` de ``BaseModel``,
    y alli **todo** modelo hereda de ``BaseModel``, asi que todo modelo
    responde. Aqui la jerarquia es otra, medida: ``BaseModel(Model)`` y
    ``TransientModel(Model)`` son HERMANOS —``BaseModel.__mro__`` da
    ``[BaseModel, Model, AltersData, object]``— asi que un classmethod en
    ``BaseModel`` no alcanza a un wizard.

    Por eso el arbol ya tenia el lector de modulo
    (``orm/model_classes.py:897``, exportado en su ``__all__``), que si cumple
    el contrato de la fuente: responde por CUALQUIER clase de modelo. El
    classmethod se porta igual sobre ``BaseModel`` —es el simbolo que la
    fuente declara y donde lo declara— pero el consumidor de la fase usa el
    lector, que es el que la jerarquia hace universal.
    """

    def test_a_transient_model_answers_true(self):
        class AnswersTrueProbe(TransientModel):
            class Meta:
                app_label = 'base'

        assert is_transient(AnswersTrueProbe) is True

    def test_a_persistent_model_answers_false(self):
        class AnswersFalseProbe(django_models.Model):
            class Meta:
                app_label = 'base'

        assert is_transient(AnswersFalseProbe) is False

    def test_the_classmethod_of_the_source_is_ported_where_it_declares_it(self):
        """``BaseModel.is_transient`` existe: el simbolo NO se omite."""
        assert BaseModel.is_transient() is False
