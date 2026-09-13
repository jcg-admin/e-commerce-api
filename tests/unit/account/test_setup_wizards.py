"""Contrato de los dos asistentes del onboarding contable — tarea #333.

``account.financial.year.op`` y ``account.setup.bank.manual.config``, portados
de ``odoo19c: addons/account/wizard/setup_wizards.py``
(``odoo-tools@622ddc2a``, LGPL-3).

Por qué este archivo existe
============================

La premisa de #333 —*«ausente del registro»*— se midió y tiene **tres**
eslabones, no uno:

1. los dos asistentes declaraban ``Meta: abstract = True, managed = False``,
   y una clase abstracta **nunca** llega a ``apps.get_models()`` ni dispara
   ``class_prepared``, asi que nunca entra en ``orm.registry.MODELS_BY_NAME``;
2. ``ResPartnerBank`` no declaraba ``_name``, y sin él la clave
   ``'res.partner.bank'`` del ``_inherits`` del asistente **no resuelve**:
   ``ensure_inherits()`` salta el declarante cuando su comodelo no está en el
   registro;
3. ``AccountJournal`` tampoco, y es el comodelo de ``linked_journal_id``.

Un asistente ausente del registro no falla: **no existe**. Por eso el control
que discrimina no es «el módulo importa» sino «el nombre resuelve y la fila se
guarda» — un ``import`` habría pasado en verde con los tres eslabones rotos.
"""
from datetime import date

import pytest
from orm.environments import sudo
from django.core.exceptions import ValidationError

from addons.account.models import AccountJournal
from addons.account.wizard.setup_wizards import (
    AccountFinancialYearOp,
    AccountSetupBankManualConfig,
)
from addons.base.models import ResBank, ResCompany, ResPartner, ResPartnerBank
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


@pytest.fixture
def company():
    partner = ResPartner.objects.create(name='ACME')
    return ResCompany.objects.create(code='acme', name='ACME', partner=partner)


class TestRegistro:
    """El eslabón 1 y 2: el nombre del modelo resuelve."""

    @pytest.mark.parametrize('model_name, cls', [
        ('account.financial.year.op', AccountFinancialYearOp),
        ('account.setup.bank.manual.config', AccountSetupBankManualConfig),
        ('res.partner.bank', ResPartnerBank),
        ('account.journal', AccountJournal),
    ])
    def test_the_model_name_resolves_in_the_registry(self, model_name, cls):
        assert MODELS_BY_NAME.get(model_name) is cls

    @pytest.mark.parametrize('cls', [
        AccountFinancialYearOp, AccountSetupBankManualConfig])
    def test_the_wizard_has_a_real_table(self, cls):
        """≙ ``_auto = True`` de ``TransientModel`` (``odoo19c:
        odoo/orm/models_transient.py:18``). Sin tabla el asistente no guarda."""
        assert cls._meta.managed is True
        assert cls._meta.abstract is False
        assert cls._meta.db_table == cls._name.replace('.', '_')


class TestFinancialYearOp:
    def test_the_fiscal_year_fields_read_from_the_company(self, company):
        company.fiscalyear_last_day = 31
        company.fiscalyear_last_month = '12'
        company.save(update_fields=['fiscalyear_last_day',
                                    'fiscalyear_last_month'])
        wizard, = AccountFinancialYearOp.create([
            {'company_id': company, 'opening_date': date(2026, 1, 1)}])
        assert wizard.fiscalyear_last_day == 31
        assert wizard.fiscalyear_last_month == '12'

    def test_an_impossible_date_is_rejected(self):
        """≙ ``_check_fiscalyear`` — se prueba sobre 2020, bisiesto."""
        with pytest.raises(ValidationError):
            AccountFinancialYearOp._check_fiscalyear('2', 31)

    def test_a_possible_date_is_accepted(self):
        assert AccountFinancialYearOp._check_fiscalyear('2', 29) is None

    def test_the_company_fields_to_update_is_the_reference_contract(self):
        assert AccountFinancialYearOp._company_fields_to_update() == {
            'fiscalyear_last_day', 'fiscalyear_last_month', 'opening_date'}

    def test_update_company_writes_the_three_fields_back(self, company):
        """≙ ``_update_company`` — el rodeo de la fuente: los tres viajan en
        UNA escritura porque su restricción se valida en conjunto."""
        AccountFinancialYearOp._update_company(company, {
            'fiscalyear_last_day': 30,
            'fiscalyear_last_month': '6',
            'opening_date': date(2026, 7, 1),
        })
        company.refresh_from_db()
        assert company.fiscalyear_last_day == 30
        assert company.fiscalyear_last_month == '6'
        assert company.account_opening_date == date(2026, 7, 1)


class TestBankManualConfig:
    def test_the_inherits_delegation_exposes_the_bank_account_fields(self, company):
        """El eslabón 3: ``_inherits = {'res.partner.bank': …}`` expone
        ``acc_number`` como propio del asistente."""
        bank_account = ResPartnerBank.objects.create(
            acc_number='MX0000001', partner=company.partner)
        wizard = AccountSetupBankManualConfig.objects.create(
            company_id=company, res_partner_bank_id=bank_account,
            new_journal_name='MX0000001')
        assert wizard.acc_number == 'MX0000001'

    def test_create_injects_the_company_partner_and_finds_the_bank_by_bic(
            self, company):
        """≙ el cuerpo del ``create`` de la fuente: el partner es SIEMPRE el
        de la empresa activa, y sin banco elegido el BIC lo busca o lo crea."""
        wizard = AccountSetupBankManualConfig.create(
            company=company, acc_number='MX0000002', bank_bic='BCMRMXMM')
        assert wizard.partner == company.partner
        assert wizard.new_journal_name == 'MX0000002'
        assert wizard.bank.bic == 'BCMRMXMM'
        assert ResBank.objects.filter(bic='BCMRMXMM').count() == 1

    def test_the_bic_of_an_existing_bank_is_reused_not_duplicated(self, company):
        ResBank.objects.create(name='Banco Ya', bic='NAFXMXMM')
        AccountSetupBankManualConfig.create(
            company=company, acc_number='MX0000003', bank_bic='NAFXMXMM')
        assert ResBank.objects.filter(bic='NAFXMXMM').count() == 1

    def test_set_linked_journal_id_links_the_bank_account_to_the_journal(
            self, company):
        """≙ ``set_linked_journal_id`` — el diario nuevo nace ligado a la
        cuenta bancaria del asistente (``bank_account_id`` de la fuente)."""
        bank_account = ResPartnerBank.objects.create(
            acc_number='MX0000004', partner=company.partner)
        wizard = AccountSetupBankManualConfig.objects.create(
            company_id=company, res_partner_bank_id=bank_account,
            new_journal_name='Banco principal')
        journal = wizard.set_linked_journal_id()
        assert journal.bank_account_id == bank_account
        assert journal.name == 'Banco principal'
        assert journal.type == 'bank'

    def test_an_existing_journal_is_relinked_not_recreated(self, company):
        bank_account = ResPartnerBank.objects.create(
            acc_number='MX0000005', partner=company.partner)
        journal = AccountJournal.objects.create(
            name='Viejo', code='BNK9', type='bank', company=company)
        wizard = AccountSetupBankManualConfig.objects.create(
            company_id=company, res_partner_bank_id=bank_account,
            new_journal_name='Nuevo', linked_journal_id=journal)
        wizard.set_linked_journal_id()
        journal.refresh_from_db()
        assert journal.name == 'Nuevo'
        assert journal.bank_account_id == bank_account
        assert AccountJournal.objects.filter(company=company).count() == 1

    def test_the_unlinked_journal_count_ignores_the_ones_with_an_account(
            self, company):
        """≙ ``_number_unlinked_journal`` — cuenta los diarios del tipo SIN
        cuenta bancaria ligada, **menos el que ya seria el propuesto**.

        Esa resta es de la fuente (``:114-119``): el diario que
        ``default_linked_journal_id`` devolveria no cuenta como «pendiente»
        porque el asistente ya lo va a ofrecer. Con tres sin cuenta el
        resultado es dos, no tres — y con uno solo seria cero, que es por que
        el caso usa tres y no uno.
        """
        for n in (1, 2, 3):
            AccountJournal.objects.create(
                name=f'Sin cuenta {n}', code=f'BNK{n}', type='bank',
                company=company)
        ligado = AccountJournal.objects.create(
            name='Con cuenta', code='BNK9', type='bank', company=company)
        ligado.bank_account_id = ResPartnerBank.objects.create(
            acc_number='MX0000006', partner=company.partner)
        ligado.save(update_fields=['bank_account_id'])
        assert AccountSetupBankManualConfig._number_unlinked_journal(
            'bank', company) == 2

    def test_the_company_falls_back_to_the_active_one(self, company):
        assert AccountSetupBankManualConfig._compute_company_id(
            None, company) is company
        assert AccountSetupBankManualConfig._compute_company_id(
            company, None) is company
