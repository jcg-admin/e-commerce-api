r"""El nombre punteado de la fuente llega a Django sin que derive una clave falsa.

LA FUENTE NO DERIVA NINGUNA CLAVE. ``Field.comodel_name`` es una cadena
(``odoo19c: odoo/orm/fields_relational.py:36``) y la existencia del destinatario
se afirma en una **fase**: ``setup_nonrelated`` hace
``assert self.comodel_name in model.pool`` (``:92-94``), contra un registro
—``Registry(Mapping[str, type[BaseModel]])``, ``odoo/orm/registry.py:84``— cuya
clave **es** el nombre punteado. Late binding por nombre, nunca aritmética sobre
la cadena.

Django hace lo contrario, y la conducta está medida (M18): su
``make_model_tuple`` (``django/db/models/utils.py:5-25``) **parte la cadena por
el punto** y con dos o más puntos levanta ``ValueError`` **en tiempo de
ejecución del cuerpo de la clase** — antes de que exista ninguna entrada
pendiente que un vaciado posterior pudiera arreglar. Medido sobre los 224
``_name`` del árbol: **158 (70.5 %)** llevan dos o más puntos.

De ahí el porte: el nombre punteado **no llega** a ``make_model_tuple``. Se le
entrega a Django un asa opaca y legal —la etiqueta centinela bajo un
``app_label`` que no está instalado, medido: ninguno de los 137 se llama
``orm``— y el nombre de la fuente sobrevive intacto en ``field.comodel_name``,
que es el atributo que la fuente declara.

Son DOS mecanismos porque el orden de declaración tiene dos casos, y cada uno
cae con su propia anulación:

- **destino-primero** — el destino ya está en el registro al construir el campo,
  así que se le entrega su clase a Django y no hay nada que diferir;
- **referente-primero y auto-referencia** — el destino aún no existe, así que se
  entrega el centinela y el vaciado ocurre en ``class_prepared`` del destino.

Qué haría FALLAR este control (sub-patrón D): que el puerto tradujera la cadena
y **no** vaciara —el campo se quedaría con una cadena centinela que ninguna
migración puede resolver—, o que vaciara sólo una dirección. Cada caso de abajo
nombra la pieza de la que depende; la anulación está medida en el banco
``scripts/workbench/resolucion-de-nombre-de-modelo-20260911T104904/``.

*Métrica:* lo que el campo construido lleva en ``remote_field.model`` y en
``related_model`` tras ``django.setup()``, el ``to`` que emite su
``deconstruct()``, y las claves que quedan en ``apps._pending_operations``.
*Ciega a:* ``One2many`` y ``Many2many`` — ``One2many`` resuelve con
``apps.get_model(self.comodel_name)`` (``fields_relational.py:354``), que falla
ante 2+ puntos por OTRO mecanismo y exige otro puerto (sucesor declarado); y al
campo declarado con **etiqueta de Django** (``'base.ResPartner'``), que no toma
ninguno de los tres caminos de M18.
"""
import pytest
from django.apps import apps
from django.db import models
from django.db.models.utils import make_model_tuple

import fields
from addons.base.models.ir_model import IrModelFields
from addons.base.models.res_partner import ResPartner
from orm.registry import sentinel_key, sentinel_label


def _pending_keys():
    """Las claves que Django tiene sin resolver, leidas del registro real."""
    return set(apps._pending_operations)


class TestThePositiveThatM18Measured:
    """El caso que hoy levanta ``ValueError`` en el cuerpo de la clase."""

    def test_a_two_dot_name_no_longer_breaks_the_class_body(self):
        class ReferrerAfterTargetProbe(models.Model):
            field_id = fields.Many2one('ir.model.fields', null=True)

            class Meta:
                app_label = 'base'

        field = ReferrerAfterTargetProbe._meta.get_field('field_id')

        assert field.remote_field.model is IrModelFields

    def test_the_source_name_survives_on_the_field(self):
        """``comodel_name`` es el atributo de la fuente, no el asa de Django."""
        class KeepsTheSourceNameProbe(models.Model):
            field_id = fields.Many2one('ir.model.fields', null=True)

            class Meta:
                app_label = 'base'

        field = KeepsTheSourceNameProbe._meta.get_field('field_id')

        assert field.comodel_name == 'ir.model.fields'

    def test_related_model_resolves_to_the_class(self):
        class ReadsRelatedModelProbe(models.Model):
            field_id = fields.Many2one('ir.model.fields', null=True)

            class Meta:
                app_label = 'base'

        field = ReadsRelatedModelProbe._meta.get_field('field_id')

        assert field.related_model is IrModelFields


class TestTheSentinelNeverReachesAMigration:
    """El radio de ``deconstruct()`` — lo que una migracion escribiria."""

    def test_deconstruct_emits_the_real_label(self):
        class WillBeDeconstructedProbe(models.Model):
            field_id = fields.Many2one('ir.model.fields', null=True)

            class Meta:
                app_label = 'base'

        field = WillBeDeconstructedProbe._meta.get_field('field_id')
        _name, path, _args, kwargs = field.deconstruct()

        assert path == 'django.db.models.ForeignKey'
        assert kwargs['to'] == IrModelFields._meta.label_lower

    def test_no_sentinel_key_of_a_registered_name_is_left_pending(self):
        class LeavesNothingPendingProbe(models.Model):
            field_id = fields.Many2one('ir.model.fields', null=True)

            class Meta:
                app_label = 'base'

        LeavesNothingPendingProbe  # el cuerpo ya corrio; lo que se mide es el resto

        assert sentinel_key('ir.model.fields') not in _pending_keys()


class TestTheOrderOfDeclarationHasTwoCases:
    """Cada direccion con su caso, que es lo que la anulacion separa."""

    def test_target_first_resolves_at_construction(self):
        """El destino ya esta registrado: se entrega su clase, sin diferir."""
        class TargetDeclaredFirstProbe(models.Model):
            _name = 'test.deferred.alpha'

            class Meta:
                app_label = 'base'

        class ReferrerDeclaredSecondProbe(models.Model):
            alpha_id = fields.Many2one('test.deferred.alpha', null=True)

            class Meta:
                app_label = 'base'

        field = ReferrerDeclaredSecondProbe._meta.get_field('alpha_id')

        assert field.remote_field.model is TargetDeclaredFirstProbe

    def test_referrer_first_resolves_when_the_target_is_prepared(self):
        """El destino no existe al construir: centinela y vaciado posterior."""
        class ReferrerDeclaredFirstProbe(models.Model):
            beta_id = fields.Many2one('test.deferred.beta', null=True)

            class Meta:
                app_label = 'base'

        field = ReferrerDeclaredFirstProbe._meta.get_field('beta_id')
        assert isinstance(field.remote_field.model, str), (
            'sin el destino declarado, el campo tiene que seguir difiriendo')

        class TargetDeclaredSecondProbe(models.Model):
            _name = 'test.deferred.beta'

            class Meta:
                app_label = 'base'

        assert field.remote_field.model is TargetDeclaredSecondProbe

    def test_self_reference_resolves_on_its_own_class_prepared(self):
        class PointsAtItselfProbe(models.Model):
            _name = 'test.deferred.gamma'
            parent_id = fields.Many2one('test.deferred.gamma', null=True)

            class Meta:
                app_label = 'base'

        field = PointsAtItselfProbe._meta.get_field('parent_id')

        assert field.remote_field.model is PointsAtItselfProbe


class TestWhatWasAlreadyWorkingStaysWorking:
    """Las cuatro formas sanas del arbol no cambian de conducta.

    Tres las midio M18; la cuarta —la etiqueta de Django en minusculas—
    la destapo M20 al censar por AST las 580 llamadas con cadena literal,
    y es la que rompio el arbol cuando el discriminador era solo de caja.
    """

    def test_the_django_label_is_untouched(self):
        """Django la resuelve **en el acto**: el modelo ya esta registrado, asi
        que ``lazy_model_operation`` toma su rama ``else`` y aplica la clase sin
        encolar nada (``apps/registry.py:417-426``). Lo que este caso mide es
        que el puerto no se interpone: el discriminador de caja deja pasar la
        etiqueta con mayuscula sin tocarla."""
        class UsesDjangoLabelProbe(models.Model):
            partner_id = fields.Many2one('base.ResPartner', null=True)

            class Meta:
                app_label = 'base'

        field = UsesDjangoLabelProbe._meta.get_field('partner_id')

        assert field.remote_field.model is ResPartner
        # ``comodel_name`` responde igual: es un descriptor NO de datos
        # (``orm/fields.py:2074-2090``) que DERIVA el ``_name`` de la fuente
        # del modelo que Django ya resolvio. Por eso una etiqueta de Django
        # tambien contesta en el vocabulario de la fuente, sin traduccion.
        assert field.comodel_name == 'res.partner'

    def test_a_model_class_is_untouched(self):
        class UsesTheClassProbe(models.Model):
            field_id = fields.Many2one(IrModelFields, null=True)

            class Meta:
                app_label = 'base'

        field = UsesTheClassProbe._meta.get_field('field_id')

        assert field.remote_field.model is IrModelFields

    def test_the_recursive_constant_is_untouched(self):
        class UsesSelfConstantProbe(models.Model):
            parent_id = fields.Many2one('self', null=True)

            class Meta:
                app_label = 'base'

        field = UsesSelfConstantProbe._meta.get_field('parent_id')

        assert field.remote_field.model is UsesSelfConstantProbe

    def test_the_django_label_in_lowercase_is_untouched(self):
        """La cuarta forma, y la unica que el discriminador de caja NO puede
        separar por si solo: una etiqueta de Django escrita en ``label_lower``
        lleva punto y va en minusculas, exactamente igual que un ``_name`` de
        la fuente. Sin la consulta a ``apps.get_model`` del puerto, esta
        declaracion iria al centinela y quedaria colgada.

        **No es hipotetica.** ``base.reportpaperformat`` vive asi en
        ``src/addons/base/migrations/0069_alter_iractionsreport_options_and_more.py``,
        y no por descuido —son 41 asi en el arbol, 31 archivos de migracion y 3
        fuera—: el estado de una migracion rechaza la referencia a
        la clase (*"Model fields in ModelState.fields cannot refer to a model
        class"*), asi que la cadena en minusculas es el unico camino que le
        queda.

        Que haria FALLAR este control: retirar la rama de ``apps.get_model``
        de ``_deferred_comodel``. Medido por anulacion — cae este caso y solo
        este; los otros tres de la clase sobreviven porque ninguno toma esa
        rama.
        """
        class UsesLowercaseDjangoLabelProbe(models.Model):
            partner_id = fields.Many2one('base.respartner', null=True)

            class Meta:
                app_label = 'base'

        field = UsesLowercaseDjangoLabelProbe._meta.get_field('partner_id')

        assert field.remote_field.model is ResPartner


class TestTheSentinelLabelIsLegalAndUnambiguous:
    """La etiqueta que se le entrega a Django, medida, no supuesta."""

    def test_the_sentinel_app_label_is_not_installed(self):
        label, _model = sentinel_key('ir.model.fields')

        assert label not in apps.app_configs

    def test_the_sentinel_is_what_make_model_tuple_would_derive(self):
        assert make_model_tuple(sentinel_label('ir.model.fields')) == \
            sentinel_key('ir.model.fields')

    @pytest.mark.parametrize('name', ['ir.model.fields', 'ir.model',
                                      'account.move.line'])
    def test_every_dotted_name_collapses_to_one_segment(self, name):
        _label, model_name = sentinel_key(name)

        assert '.' not in model_name
