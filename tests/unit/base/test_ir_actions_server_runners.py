"""Los modos no-eval de ``ir.actions.server`` y su motor (#117).

≙ ``odoo19c: addons/base/models/ir_actions.py:980-987`` (``_get_runner``),
``:1019-1023`` (``multi``), ``:1025-1038`` (``object_write``),
``:1084-1095`` (``object_copy``), ``:1097-1109`` (``object_create``),
``:1038-1083`` (``webhook``), ``:1111-1149`` (``_get_eval_context``),
``:1151-1200`` (``run``/``_run``) y ``:1285-1318`` (``_eval_value``).

El bloqueo declarado era *"sus insumos cuelgan de ``ir.model.fields`` como FK
y ``model_name`` sigue siendo ``Char``"*. Medido al abrir la tarea: ``IrModel``
(``ir_model.py:317``) e ``IrModelFields`` (``:468``) existen desde hace pases,
así que la premisa había caducado — la misma forma que #132.

Qué haría fallar a estos casos
==============================

Un motor que no ejecuta devuelve ``False`` sin reventar, así que un caso que
sólo mirase el valor de retorno sería verde con los corredores ausentes. Cada
caso afirma **el efecto en la base** —la fila cambió, la fila nueva existe— y
no la forma del resultado.

El caso del aviso es el control que discrimina el guardián de ``_run``: sin él
una acción mal configurada se ejecutaría igual, y ningún otro caso lo notaría.
"""
import pytest

from addons.base.models.ir_actions import (
    IrActionsServer, ServerActionWithWarningsError)
from addons.base.models.ir_model import IrModel, IrModelFields
from addons.base.models.ir_sequence import IrSequence
from addons.base.models.res_partner import ResPartner
from orm.environments import context_scope, sudo


#: El modelo de prueba es ``ResPartner`` y no cualquiera: los corredores
#: llaman ``write`` y ``copy``, que en la referencia viven en ``BaseModel``
#: —universales— y aquí son mixins que cada modelo adopta
#: (``RecordLoaderMixin`` vía ``TimeStampedModel``, y ``models.CopyMixin``).
#: ``ResPartner`` adopta los dos (``res_partner.py:126``); ``ResCountry`` no
#: adopta ninguno, así que medir con él habría medido esa divergencia del
#: árbol en vez de los corredores.
PARTNER = 'base.ResPartner'


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


def _action(**kwargs):
    kwargs.setdefault('name', 'Accion')
    kwargs.setdefault('state', 'multi')
    return IrActionsServer.objects.create(**kwargs)


def _partner_model():
    #: ``get_or_create``: la reflexión de modelos ya siembra la fila, y
    #: ``ir_model.model`` es único.
    row, _created = IrModel.objects.get_or_create(
        model=PARTNER, defaults={'name': 'Contacto'})
    return row


def _field(model_row, name, ttype='char'):
    #: ``state='base'`` porque la restricción ``ir_model_fields_name_manual_field``
    #: exige el prefijo ``x_`` en los campos manuales, y estos reflejan campos
    #: reales del modelo.
    row, _created = IrModelFields.objects.get_or_create(
        model=PARTNER, name=name,
        defaults={'model_id': model_row, 'ttype': ttype, 'state': 'base'})
    return row


@pytest.mark.django_db
class TestTheRunnerIsResolvedByState:
    """≙ ``_get_runner``: primero ``_multi``, si no el simple."""

    def test_multi_resolves_its_own_runner(self):
        """``multi`` NO es ``_multi``: no existe ``_run_action_multi_multi``.

        Es la trampa del despacho por nombre — el sufijo ``_multi`` de la
        fuente significa *"opera sobre varios registros de una vez"*, no el
        modo llamado ``multi``. Sólo ``code`` tiene corredor ``_multi``.
        """
        runner, multi = _action(state='multi')._get_runner()

        assert multi is False
        assert runner.__name__ == '_run_action_multi'

    def test_object_write_is_not_multi(self):
        runner, multi = _action(state='object_write')._get_runner()

        assert multi is False
        assert runner.__name__ == '_run_action_object_write'

    def test_a_state_without_runner_resolves_to_none(self):
        action = _action(state='multi')
        action.state = 'no_soy_un_modo'

        assert action._get_runner() == (None, False)


@pytest.mark.django_db
class TestMulti:
    """≙ ``_run_action_multi``: encadena a las hijas por su secuencia."""

    def test_children_run_in_sequence_order(self):
        partner = ResPartner.objects.create(name='Zylandia')
        model_row = _partner_model()
        parent = _action(state='multi', model_name=PARTNER)
        _action(name='Segunda', state='object_write', sequence=2,
                model_name=PARTNER, crud_model_id=model_row,
                update_field_id=_field(model_row, 'name'),
                update_path='name', value='Segunda escribio', parent=parent)
        _action(name='Primera', state='object_write', sequence=1,
                model_name=PARTNER, crud_model_id=model_row,
                update_field_id=_field(model_row, 'name'),
                update_path='name', value='Primera escribio', parent=parent)

        with context_scope(active_model=PARTNER, active_id=partner.pk):
            parent.run()

        partner.refresh_from_db()
        assert partner.name == 'Segunda escribio'


@pytest.mark.django_db
class TestObjectWrite:
    """≙ ``_run_action_object_write`` + ``_eval_value``."""

    def _write_action(self, ttype='char', **kwargs):
        model_row = _partner_model()
        kwargs.setdefault('update_path', 'name')
        return _action(
            state='object_write', model_name=PARTNER,
            crud_model_id=model_row,
            update_field_id=_field(model_row, kwargs.pop('field', 'name'), ttype),
            **kwargs)

    def test_a_char_value_lands_in_the_record(self):
        partner = ResPartner.objects.create(name='Zylandia')
        action = self._write_action(value='Nuevo nombre')

        with context_scope(active_model=PARTNER, active_id=partner.pk):
            action.run()

        partner.refresh_from_db()
        assert partner.name == 'Nuevo nombre'

    def test_a_boolean_field_reads_update_boolean_value(self):
        partner = ResPartner.objects.create(name='Zylandia')
        action = self._write_action(
            ttype='boolean', field='is_company',
            update_path='is_company', update_boolean_value='true')

        with context_scope(active_model=PARTNER, active_id=partner.pk):
            action.run()

        partner.refresh_from_db()
        assert partner.is_company is True

    def test_an_integer_field_is_coerced(self):
        model_row = _partner_model()
        action = _action(
            state='object_write', model_name=PARTNER,
            crud_model_id=model_row,
            update_field_id=_field(model_row, 'color', 'integer'),
            update_path='color', value='42')

        assert action._eval_value()[action.pk] == 42

    def test_a_sequence_evaluation_asks_the_sequence(self):
        sequence = IrSequence.objects.create(
            name='Numeración', code='zy.test', prefix='ZY-', padding=3)
        action = self._write_action(
            value='', evaluation_type='sequence', sequence_id=sequence)

        assert action._eval_value()[action.pk].startswith('ZY-')

    def test_the_path_traverses_a_relation(self):
        """``update_path='country_group_ids.name'`` no es el campo local."""
        model_row = _partner_model()
        action = _action(
            state='object_write', model_name=PARTNER,
            crud_model_id=model_row, update_path='name')

        chain, stringified = action._get_relation_chain('update_path')

        assert [field.name for field in chain] == ['name']
        assert stringified


@pytest.mark.django_db
class TestObjectCreate:
    """≙ ``_run_action_object_create``: crea con ``value`` como nombre."""

    def test_the_record_is_created_with_the_value_as_name(self):
        model_row = _partner_model()
        anchor = ResPartner.objects.create(name='Zylandia')
        action = _action(
            state='object_create', model_name=PARTNER,
            crud_model_id=model_row, value='Nuevo contacto')

        with context_scope(active_model=PARTNER, active_id=anchor.pk):
            action.run()

        assert ResPartner.objects.filter(name='Nuevo contacto').exists()


@pytest.mark.django_db
class TestObjectCopy:
    """≙ ``_run_action_object_copy``: duplica el registro referenciado."""

    def test_the_referenced_record_is_duplicated(self):
        partner = ResPartner.objects.create(name='Zylandia')
        model_row = _partner_model()
        action = _action(
            state='object_copy', model_name=PARTNER, crud_model_id=model_row)
        action.resource_ref = partner
        action.save()

        before = ResPartner.objects.count()
        with context_scope(active_model=PARTNER, active_id=partner.pk):
            action.run()

        assert ResPartner.objects.count() == before + 1


@pytest.mark.django_db
class TestTheWarningGuardOfRun:
    """≙ ``_run``: una acción con aviso NO se ejecuta."""

    def test_an_action_with_warnings_refuses_to_run(self):
        parent = _action(state='multi', model_name=PARTNER)
        _action(name='Hija', state='multi', model_name='base.ResCountry',
                parent=parent)

        assert parent.warning
        with pytest.raises(ServerActionWithWarningsError):
            parent.run()


@pytest.mark.django_db
class TestTheEvalContext:
    """≙ ``_get_eval_context``: el registro activo entra por el contexto."""

    def test_the_active_record_is_bound(self):
        partner = ResPartner.objects.create(name='Zylandia')
        action = _action(model_name=PARTNER)

        with context_scope(active_model=PARTNER, active_id=partner.pk):
            context = action._get_eval_context(action)

        assert context['record'] == partner
        assert context['model'] is ResPartner

    def test_without_an_active_model_there_is_no_record(self):
        action = _action(model_name=PARTNER)

        assert action._get_eval_context(action)['record'] is None


@pytest.mark.django_db
class TestTheContextualActionHelpers:
    """≙ ``create_action`` / ``unlink_action``."""

    def test_create_action_binds_the_model(self):
        action = _action(model_name=PARTNER)

        action.create_action()

        action.refresh_from_db()
        assert action.binding_model_name == PARTNER
        assert action.binding_type == 'action'

    def test_unlink_action_clears_the_binding(self):
        action = _action(model_name=PARTNER)
        action.create_action()

        action.unlink_action()

        action.refresh_from_db()
        assert action.binding_model_name == ''
