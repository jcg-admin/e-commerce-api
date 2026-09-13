"""``DefaultGetMixin.create`` — el porte por CONTENIDO de ``BaseModel.create``.

≙ ``odoo19c: odoo/orm/models.py:4611-4770``. Hasta :ref:`h-api-1108` el
método recibía ``**values`` y devolvía una instancia; su docstring lo llamaba
*"se porta el paso, no la firma"*. Estos casos fijan la firma de la fuente
—lista de dicts → filas en orden; dict → singleton— y los pasos que la fuente
da y el árbol no daba: ``check_access('create')``, el ``ValueError`` por campo
desconocido, los ``default_*`` del contexto, el lote de padres de
``_inherits`` y el muchos-a-muchos tras la inserción.

Qué haría fallar a estos casos
==============================

- ``test_without_a_user_the_acl_denies`` cae si ``create`` deja de llamar a
  ``check_access`` — es el control que separa «el alta pasa» de «nadie
  preguntó».
- ``test_the_inherits_parent_is_created_first`` cae si el lote de padres se
  omite: ``ResUsers`` no puede insertarse con ``partner_id`` nulo.
- ``test_a_list_returns_the_rows_in_the_given_order`` cae si el retorno deja
  de ser :func:`orm.utils.browse` sobre los ids en orden.

Medido con la guarda anulada
============================

Ver el ``control`` del manifiesto del banco
``scripts/workbench/create-por-contenido-20260911T221144/``: la mutación que
retira el lote de padres de ``_inherits`` hace caer exactamente el caso de
``ResUsers`` y ninguno más.
"""
import pytest
from django.core.exceptions import PermissionDenied

from addons.base.models import ResPartner
from addons.base.models.ir_cron import IrCron
from addons.base.models.res_partner import ResPartnerCategory
from addons.base.models.res_users import ResUsers
from orm.environments import context_scope, sudo

pytestmark = pytest.mark.django_db


class TestTheSignatureIsTheSourcesSignature:
    """Lista de dicts → filas en orden; dict → singleton; kwargs → ``TypeError``."""

    def test_a_list_returns_the_rows_in_the_given_order(self):
        with sudo():
            rows = ResPartner.create([{'name': 'Alta A'}, {'name': 'Alta B'}, {'name': 'Alta C'}])
        assert [row.name for row in rows] == ['Alta A', 'Alta B', 'Alta C']
        pks = [row.pk for row in rows]
        assert pks == sorted(pks) and len(set(pks)) == 3

    def test_a_dict_is_a_singleton_list(self):
        """``@api.model_create_multi``: *"treated as a singleton list [vals]"*."""
        with sudo():
            rows = ResPartner.create({'name': 'Alta suelta'})
        assert len(rows) == 1
        row, = rows
        assert row.name == 'Alta suelta'

    def test_an_empty_list_returns_an_empty_recordset(self):
        with sudo():
            assert len(ResPartner.create([])) == 0

    def test_kwargs_are_no_longer_a_form(self):
        with sudo(), pytest.raises(TypeError):
            ResPartner.create(name='kwargs')

    def test_the_rows_are_persisted(self):
        with sudo():
            row, = ResPartner.create([{'name': 'Persistida'}])
        assert ResPartner.objects.filter(pk=row.pk, name='Persistida').exists()


class TestTheStepsOfTheSource:
    """``check_access``, campo desconocido, ``default_*`` del contexto, M2M."""

    def test_without_a_user_the_acl_denies(self):
        """``self.check_access('create')`` (``:4640``) — sin usuario ni
        elevación la ACL de ``res.partner`` deniega, como
        ``IrModelAccess.check`` ya hace para ``read``."""
        with pytest.raises(PermissionDenied):
            ResPartner.create([{'name': 'sin usuario'}])

    def test_an_unknown_field_raises_the_sources_value_error(self):
        with sudo(), pytest.raises(ValueError, match="Invalid field 'nonexistent_field' in 'res.partner'"):
            ResPartner.create([{'name': 'x', 'nonexistent_field': 1}])

    def test_a_context_default_lands_in_the_row(self):
        """``default_*`` del contexto entra por ``_add_missing_default_values``
        (``:4796``) y su nombre se valida como el de un campo dado (``:4645``)."""
        with sudo(), context_scope(default_comment='del contexto'):
            row, = ResPartner.create([{'name': 'Con contexto'}])
        row.refresh_from_db()
        assert row.comment == 'del contexto'

    def test_a_given_value_beats_the_context_default(self):
        with sudo(), context_scope(default_comment='del contexto'):
            row, = ResPartner.create([{'name': 'Con contexto', 'comment': 'dado'}])
        row.refresh_from_db()
        assert row.comment == 'dado'

    def test_a_many_to_many_is_set_after_the_insert(self):
        """El x2many va en ``other_fields`` de ``_create`` (``:4924``), después
        del ``INSERT``; aquí ``manager.set`` con la fila ya real."""
        category = ResPartnerCategory.objects.create(name='Etiqueta de alta')
        with sudo():
            row, = ResPartner.create([{'name': 'Etiquetado', 'category_ids': [category.pk]}])
        assert list(row.category_ids.values_list('pk', flat=True)) == [category.pk]

    def test_the_magic_columns_are_discarded(self):
        """``bad_names = ['id', 'parent_path']`` (``:4780``) — un ``id`` dado
        no fija la clave."""
        with sudo():
            row, = ResPartner.create([{'name': 'Con id', 'id': 999999}])
        assert row.pk != 999999


class TestInheritsParents:
    """``for model_name, parent_name in self._inherits.items()`` (``:4699-4715``)."""

    def test_the_inherits_parent_is_created_first(self):
        with sudo():
            user, = ResUsers.create([{'login': 'alta-351@ejemplo.mx', 'name': 'Usuaria Alta',
                                      'password': 'x'}])
        assert user.partner_id is not None
        assert user.partner.name == 'Usuaria Alta'
        assert ResPartner.objects.filter(pk=user.partner_id).exists()

    def test_a_given_parent_receives_the_inherited_values_by_write(self):
        """``parent.write(data['inherited'][model_name])`` (``:4707``)."""
        with sudo():
            partner, = ResPartner.create([{'name': 'Antes'}])
            user, = ResUsers.create([{'login': 'alta-352@ejemplo.mx', 'partner': partner,
                                      'name': 'Después', 'password': 'x'}])
        partner.refresh_from_db()
        assert user.partner_id == partner.pk
        assert partner.name == 'Después'

    def test_a_model_without_the_loader_mixin_now_creates(self):
        """``IrCron`` no tenía ``RecordLoaderMixin``: sin ``_check_field_access``
        el paso 3 de la fuente no tenía receptor. Ahora lo adopta."""
        with sudo():
            cron, = IrCron.create([{'name': 'Cron de alta', 'model_name': 'res.partner',
                                    'code': 'x', 'interval_number': 1, 'interval_type': 'days'}])
        assert cron.pk is not None and cron.name == 'Cron de alta'
