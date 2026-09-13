"""Contrato de ``SystemParameter`` (L2 global) — portación fiel de Odoo
``ir.config_parameter``.

Diseño: ``analisis-estrategia-configuracion-capas`` (L2). Portación + hallazgos:
``implementar-systemparameter-l2`` /
``hallazgos-implementar-systemparameter-l2``. Cada test verifica un
comportamiento del original Odoo
(``ir_config_parameter.py`` v19/v18, arquitectura idéntica): get/set, borrado
por valor None, quirk ``or default``, caché + invalidación, protección de claves
sembradas (dict ``_DEFAULT_PARAMETERS``, NO columna ``is_system``), y ``seed``
idempotente.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from addons.base.models import (
    _DEFAULT_PARAMETERS,
    SystemParameter,
)
from orm import registry

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _seed_defaults(db):
    # Reseed idempotente de las claves de ``_DEFAULT_PARAMETERS``: un test
    # ``transaction=True`` previo (p.ej. el de aislamiento multi-DB SOL-091)
    # hace ``flush`` de ``system_parameter`` sin re-correr la data-migration,
    # dejando las filas sembradas ausentes para los tests que siguen. Restaura
    # el estado que la migración 0002/0003 garantiza en producción, para que
    # estos tests no dependan del orden de ejecución.
    SystemParameter.seed()


@pytest.fixture(autouse=True)
def _clear_param_cache():
    """La memorización es de proceso (``ormcache``, familia ``stable``); se
    vacía entre tests para aislarlos."""
    registry.clear_cache('stable')
    yield
    registry.clear_cache('stable')


class TestGetSetParam:
    def test_get_missing_returns_default(self):
        assert SystemParameter.get_param('no.existe') is None
        assert SystemParameter.get_param('no.existe', 'fallback') == 'fallback'

    def test_set_creates_and_get_returns(self):
        prev = SystemParameter.set_param('web.base.url', 'http://x')
        assert prev is None  # no existía (Odoo devuelve False)
        assert SystemParameter.get_param('web.base.url') == 'http://x'
        assert SystemParameter.objects.filter(key='web.base.url').count() == 1

    def test_set_existing_returns_old_and_updates(self):
        SystemParameter.set_param('k', 'v1')
        old = SystemParameter.set_param('k', 'v2')
        assert old == 'v1'
        assert SystemParameter.get_param('k') == 'v2'

    def test_set_same_value_is_noop_but_returns_old(self):
        SystemParameter.set_param('k', 'v1')
        old = SystemParameter.set_param('k', 'v1')
        assert old == 'v1'
        assert SystemParameter.objects.get(key='k').value == 'v1'

    def test_set_none_deletes_existing(self):
        SystemParameter.set_param('k', 'v1')
        old = SystemParameter.set_param('k', None)
        assert old == 'v1'
        assert not SystemParameter.objects.filter(key='k').exists()

    def test_set_none_on_missing_is_noop(self):
        assert SystemParameter.set_param('nope', None) is None
        assert not SystemParameter.objects.filter(key='nope').exists()

    def test_value_is_coerced_to_str(self):
        # Odoo Text field coacciona; el puerto usa str(value).
        SystemParameter.set_param('n', 900)
        assert SystemParameter.get_param('n') == '900'

    def test_or_default_quirk_empty_value_returns_default(self):
        # Fiel a Odoo (H-CFG-IMPL-03): ``_get_param(key) or default`` -> un
        # valor almacenado falsy (cadena vacía) devuelve el default.
        SystemParameter.objects.create(key='empty', value='')
        assert SystemParameter.get_param('empty', 'D') == 'D'


class TestCache:
    def test_get_param_populates_cache(self):
        SystemParameter.set_param('k', 'v')
        registry.clear_cache('stable')
        key = ('ir.config_parameter',
               SystemParameter._get_param.__func__.__cache__.method,
               'k', 'default')
        assert key not in registry.cache_of('stable').snapshot
        SystemParameter.get_param('k')
        assert registry.cache_of('stable')[key] == 'v'

    def test_cache_hit_avoids_query(self, django_assert_num_queries):
        SystemParameter.set_param('k', 'v')
        SystemParameter.get_param('k')  # llena la caché
        with django_assert_num_queries(0):
            assert SystemParameter.get_param('k') == 'v'

    def test_set_param_invalidates_cache(self):
        SystemParameter.set_param('k', 'v1')
        assert SystemParameter.get_param('k') == 'v1'  # cachea v1
        SystemParameter.set_param('k', 'v2')
        assert SystemParameter.get_param('k') == 'v2'  # caché invalidada

    def test_delete_invalidates_cache(self):
        SystemParameter.set_param('k', 'v1')
        assert SystemParameter.get_param('k') == 'v1'
        SystemParameter.set_param('k', None)  # delete
        assert SystemParameter.get_param('k') is None


class TestProtectedKeys:
    def test_default_parameters_dict_is_source_of_truth(self):
        # H-CFG-IMPL-01: la protección viene del dict, NO de una columna
        # ``is_system`` (Odoo no la tiene).
        assert not hasattr(SystemParameter, 'is_system')
        assert 'database.uuid' in _DEFAULT_PARAMETERS

    def test_cannot_delete_protected_key(self):
        # 'database.uuid' ya existe: lo sembró la migración de datos (Odoo init,
        # defaults al crear la BD). No se re-crea.
        p = SystemParameter.objects.get(key='database.uuid')
        with pytest.raises(ValidationError):
            p.delete()
        assert SystemParameter.objects.filter(key='database.uuid').exists()

    def test_cannot_rename_protected_key(self):
        p = SystemParameter.objects.get(key='database.uuid')
        p.key = 'database.renamed'
        with pytest.raises(ValidationError):
            p.save()

    def test_can_edit_value_of_protected_key(self):
        # El operador L0 puede cambiar el VALOR, no la clave (Odoo write sólo
        # bloquea el rename de 'key').
        p = SystemParameter.objects.get(key='database.uuid')
        p.value = 'edited-value'
        p.save()
        assert SystemParameter.objects.get(key='database.uuid').value == 'edited-value'

    def test_can_delete_non_protected_key(self):
        p = SystemParameter.objects.create(key='free.key', value='v')
        p.delete()
        assert not SystemParameter.objects.filter(key='free.key').exists()


class TestSeed:
    def test_seed_creates_defaults(self):
        SystemParameter.seed()
        for key in _DEFAULT_PARAMETERS:
            assert SystemParameter.objects.filter(key=key).exists()

    def test_seed_is_idempotent(self):
        SystemParameter.seed()
        uuid_before = SystemParameter.get_param('database.uuid')
        registry.clear_cache('stable')
        SystemParameter.seed()  # segunda pasada no sobreescribe
        assert SystemParameter.get_param('database.uuid') == uuid_before

    def test_seed_force_overrides(self):
        SystemParameter.seed()
        before = SystemParameter.get_param('database.uuid')
        registry.clear_cache('stable')
        SystemParameter.seed(force=True)
        assert SystemParameter.get_param('database.uuid') != before


class TestBusinessKeysL2:
    """Claves de negocio migradas de ``config.settings.base`` (slice 2,
    H-API-CFG-01/02, :ref:`hallazgos-estrategia-configuracion-kaupamex`).
    Sembradas por ``addons.base`` migration ``0003_seed_business_keys``
    (idéntico patrón idempotente que ``0002``, ver ``_DEFAULT_PARAMETERS``)."""

    def test_authz_reauth_ttl_seeded_with_previous_default(self):
        # Preserva el valor operativo del viejo AUTHZ_REAUTH_TTL default=900.
        assert SystemParameter.get_param('authz.reauth_ttl') == '900'

    def test_backup_alert_email_seeded_without_stale_domain(self):
        # El viejo default cableaba 'admin@practicayoruba.com' (stale tras el
        # rename L0 a Kaupamex, SOL-087). El nuevo default no debe repetirlo.
        value = SystemParameter.get_param('backup.alert_email')
        assert value is not None
        assert value.endswith('@kaupamex.com')

    def test_business_keys_are_protected_like_the_original_defaults(self):
        # Al estar en _DEFAULT_PARAMETERS, el operador L0 puede editar el
        # VALOR pero no borrar/renombrar la clave (mismo guard que
        # database.uuid, H-CFG-IMPL-01).
        p = SystemParameter.objects.get(key='authz.reauth_ttl')
        with pytest.raises(ValidationError):
            p.delete()
        assert SystemParameter.objects.filter(key='authz.reauth_ttl').exists()

    def test_seed_of_business_keys_is_idempotent(self):
        ttl_before = SystemParameter.get_param('authz.reauth_ttl')
        email_before = SystemParameter.get_param('backup.alert_email')
        registry.clear_cache('stable')
        SystemParameter.seed()  # sin force: no debe sobreescribir lo existente
        assert SystemParameter.get_param('authz.reauth_ttl') == ttl_before
        assert SystemParameter.get_param('backup.alert_email') == email_before


class TestMeta:
    def test_ordering_by_key(self):
        # Filtrado a las claves del test: la BD trae los defaults sembrados por
        # la migración (database.secret/uuid), fuera de este subconjunto.
        SystemParameter.objects.create(key='zzz.b', value='1')
        SystemParameter.objects.create(key='zzz.a', value='2')
        subset = (SystemParameter.objects
                  .filter(key__in=['zzz.a', 'zzz.b'])
                  .values_list('key', flat=True))
        assert list(subset) == ['zzz.a', 'zzz.b']

    def test_key_is_unique(self):
        SystemParameter.objects.create(key='dup', value='1')
        with pytest.raises(IntegrityError):
            SystemParameter.objects.create(key='dup', value='2')

    def test_str_is_key(self):
        assert str(SystemParameter(key='x', value='y')) == 'x'
