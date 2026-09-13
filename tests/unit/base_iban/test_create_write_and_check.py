"""``base_iban`` — los tres símbolos de la referencia que faltaban por portar.

``create`` (``odoo19c: base_iban/models/res_partner_bank.py:110``), ``write``
(``:121``) y ``_check_iban`` (``:130``). Los tres se cuelgan sobre
``base.ResPartnerBank`` desde ``BaseIbanConfig.ready()``; estos casos fijan que
hacen lo que hace la fuente, no sólo que existen con ese nombre.

Qué mide cada bloque:

- ``create``/``write`` normalizan el número **antes** de que llegue a la fila,
  que es el punto que la fuente intercepta — distinto de ``save()``, que ya
  estaba cubierto por ``test_iban.py``.
- ``_check_iban`` conserva el nombre de la fuente (guion bajo incluido) y
  ``clean()`` lo invoca, así que el rechazo llega por las dos puertas.
"""
import pytest

from addons.base.models.res_partner import ResPartner
from addons.base.models.res_bank import ResPartnerBank
from exceptions import ValidationError
from orm.environments import sudo

#: IBAN español de ejemplo, sin separadores y en su forma canónica.
SPANISH_IBAN = 'ES9121000418450200051332'
SPANISH_IBAN_PRETTY = 'ES91 2100 0418 4502 0005 1332'

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


class TestCreate:
    """``create`` — ≙ ``odoo19c: base_iban:110-119``."""

    def test_create_stores_the_iban_in_its_canonical_format(self):
        partner = ResPartner.objects.create(name='Refaccionaria Zapata')
        account, = ResPartnerBank.create([{'partner': partner, 'acc_number': SPANISH_IBAN}])

        account.refresh_from_db()
        assert account.acc_number == SPANISH_IBAN_PRETTY
        assert account.acc_type == 'iban'
        assert account.sanitized_acc_number == SPANISH_IBAN

    def test_create_leaves_a_domestic_number_untouched(self):
        """La fuente traga la ``ValidationError`` y no reformatea."""
        partner = ResPartner.objects.create(name='Abarrotes Don Chuy')
        account, = ResPartnerBank.create([{'partner': partner, 'acc_number': '0012 3456 78'}])

        account.refresh_from_db()
        assert account.acc_number == '0012 3456 78'
        assert account.acc_type == 'bank'

    def test_create_returns_a_persisted_row(self):
        partner = ResPartner.objects.create(name='Ferretería El Martillo')
        account, = ResPartnerBank.create([{'partner': partner, 'acc_number': SPANISH_IBAN}])

        assert account.pk is not None
        assert ResPartnerBank.objects.filter(pk=account.pk).exists()


class TestWrite:
    """``write`` — ≙ ``odoo19c: base_iban:121-128``."""

    def test_write_reformats_a_valid_iban(self):
        partner = ResPartner.objects.create(name='Panadería La Espiga')
        account, = ResPartnerBank.create([{'partner': partner, 'acc_number': '0012 3456 78'}])

        returned = account.write(acc_number=SPANISH_IBAN)

        assert returned is account
        account.refresh_from_db()
        assert account.acc_number == SPANISH_IBAN_PRETTY
        assert account.acc_type == 'iban'

    def test_write_leaves_an_invalid_number_as_written(self):
        partner = ResPartner.objects.create(name='Carnicería El Novillo')
        account, = ResPartnerBank.create([{'partner': partner, 'acc_number': SPANISH_IBAN}])

        account.write(acc_number='0099 8877 66')

        account.refresh_from_db()
        assert account.acc_number == '0099 8877 66'
        assert account.acc_type == 'bank'

    def test_write_carries_other_fields_through(self):
        """No sólo ``acc_number``: ``write`` escribe lo que reciba."""
        partner = ResPartner.objects.create(name='Vinos La Cava')
        account, = ResPartnerBank.create([{'partner': partner, 'acc_number': SPANISH_IBAN}])

        account.write(acc_holder_name='María de la Luz Cárdenas')

        account.refresh_from_db()
        assert account.acc_holder_name == 'María de la Luz Cárdenas'
        # El número no se tocó y sigue en su forma canónica.
        assert account.acc_number == SPANISH_IBAN_PRETTY


class TestCheckIban:
    """``_check_iban`` — ≙ ``odoo19c: base_iban:130-134``."""

    def test_check_iban_rejects_a_row_marked_iban_with_a_broken_number(self):
        account = ResPartnerBank(acc_number='ES9121000418450200051333',
                                 acc_type='iban')
        with pytest.raises(ValidationError):
            account._check_iban()

    def test_check_iban_accepts_a_valid_iban(self):
        account = ResPartnerBank(acc_number=SPANISH_IBAN, acc_type='iban')
        account._check_iban()

    def test_check_iban_ignores_a_row_that_is_not_an_iban(self):
        """La guarda de la fuente: sólo mira las filas marcadas ``iban``."""
        account = ResPartnerBank(acc_number='0001234567', acc_type='bank')
        account._check_iban()

    def test_clean_delegates_to_check_iban(self):
        """``clean`` es el puente del stack, no una segunda implementación."""
        account = ResPartnerBank(acc_number='ES9121000418450200051333',
                                 acc_type='iban')
        with pytest.raises(ValidationError):
            account.clean()
