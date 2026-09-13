"""``account.financial.year.op`` + ``account.setup.bank.manual.config`` —
los dos asistentes del onboarding contable.

Adaptación de Odoo ``addons/account/wizard/setup_wizards.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

Qué cambió en la tarea #333, y por qué el archivo se reescribió entero
=======================================================================

La versión anterior declaraba los dos asistentes como
``Meta: abstract = True, managed = False`` —clases con ``classmethods``, sin
tabla— y su tabla de módulo declinaba **quince** símbolos con la fórmula
«bloqueado por un campo que no está portado». Medido al abrir la tarea, los
cinco bloqueos citados eran así:

======================================  ===================================
Bloqueo declarado                        Estado real medido
======================================  ===================================
``company.fiscalyear_last_day``          **EXISTE** — ``src/addons/base/
``company.fiscalyear_last_month``        models/res_company.py:391,396``
                                         (lo portó la tarea #207)
``company.account_opening_date``         ausente → **portado en este pase**
``company.account_opening_move_id``      ausente → **portado en este pase**
``journal.bank_account_id``              ausente → **portado en este pase**
``onboarding.onboarding.step``           **EXISTE** — ``addons/onboarding/
                                         models/onboarding_onboarding_
                                         step.py:53``, con su
                                         ``action_validate_step``
======================================  ===================================

Dos habían caducado y tres eran trabajo que se podía hacer. Ninguno era una
divergencia de mecanismo. Es el camino barato que
``porte-completo-no-parcial.md`` prohíbe: *«"este ORM no tiene ese
constructor" describe el punto de partida, no cierra nada»*.

Los tres eslabones de «ausente del registro»
=============================================

El título de #333 —*«verificar la delegación del transitorio, ausente del
registro»*— tenía tres causas encadenadas, no una:

1. **Los asistentes eran abstractos.** Una clase con ``Meta.abstract = True``
   nunca llega a ``apps.get_models()`` ni dispara ``class_prepared``, así que
   nunca entra en ``orm.registry.MODELS_BY_NAME``. Y sin tabla el asistente no
   guarda nada — el mismo defecto que ``ServerActionHistoryWizard`` ya había
   pagado (ver el docstring de ``src/orm/models_transient.py``).
2. **``ResPartnerBank`` no declaraba ``_name``.** Sin él la clave
   ``'res.partner.bank'`` del ``_inherits`` de abajo no resuelve:
   ``orm.inherits.ensure_inherits()`` salta al declarante cuando su comodelo
   es ``None``, y la delegación **no existía**. No fallaba: no estaba.
3. **``AccountJournal`` tampoco**, y es el comodelo de ``linked_journal``.

Los tres se cierran en este pase, junto con los cuatro atributos de clase que
la fuente declara para cada uno (``atributos-de-clase-de-modelo.md``).

Lo que este archivo NO cierra
==============================

- **El valor de retorno de navegación.** ``action_save_onboarding_fiscal_year``
  y ``validate`` devuelven en la fuente un ``ir.actions.client`` con
  ``tag='soft_reload'``: una orden para el cliente web de Odoo, que aquí no
  existe. Los dos métodos **hacen su trabajo** —marcar el paso, servir de
  gancho de extensión— y devuelven ``None`` en vez de esa orden. Es
  divergencia de mecanismo declarada, no un símbolo omitido.
- **``_prepare_rendering_values`` sobre el tablero de onboarding.** La fuente
  lo llama por ``xmlid`` (``self.env.ref('account.onboarding_onboarding_
  account_dashboard')``); aquí el registro por ``xmlid`` de los datos de
  ``account`` es la tarea **#299** (los addons con data-migration sin
  ``seed()``). Queda como DESCONOCIDO con esa condición de cierre.
"""
from datetime import date, timedelta

import fields
import api
import models
from addons.account.models.account_journal import AccountJournal
from addons.account.models.account_move import AccountMove
from addons.base.models import ResBank, ResPartnerBank
from addons.onboarding.models.onboarding_onboarding_step import (
    OnboardingOnboardingStep,
)
from exceptions import ValidationError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountFinancialYearOp(models.DefaultGetMixin, models.RecordLoaderMixin,
                             models.CheckCompanyMixin, TransientModel):
    """≙ ``account.financial.year.op`` — fecha de apertura y cierre fiscal
    de la empresa (``odoo19c: setup_wizards.py:10-91``)."""

    _name = 'account.financial.year.op'
    _description = 'Opening Balance of Financial Year'

    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        db_column='company_id', related_name='financial_year_ops',
        help_text='Empresa cuyo ejercicio se abre (Odoo company_id).',
    )
    #: ≙ ``opening_move_posted`` (``:15``) — ``compute`` sin ``store``. Su
    #: cuerpo delega en ``ResCompany.opening_move_posted()``, igual que allá.
    opening_move_posted = fields.Boolean(
        store=False, compute='_compute_opening_move_posted',
        verbose_name='Opening Move Posted',
    )
    #: ≙ ``opening_date`` (``:16``): ``related`` **editable** a la empresa.
    opening_date = fields.Date(
        related='company_id.account_opening_date', readonly=False,
        verbose_name='Opening Date',
        help_text='Fecha desde la que se lleva la contabilidad; es la del '
                  'asiento de apertura (Odoo opening_date).',
    )
    #: ≙ ``fiscalyear_last_day`` / ``fiscalyear_last_month`` (``:17-21``).
    #: Los dos son ``related`` editables, y su ayuda es la de la fuente:
    #: «The last day of the month will be used if the chosen day doesn't
    #: exist.»
    fiscalyear_last_day = fields.Integer(
        related='company_id.fiscalyear_last_day', readonly=False,
        help_text='Si el día elegido no existe en el mes se usa el último '
                  '(Odoo fiscalyear_last_day).',
    )
    fiscalyear_last_month = fields.Selection(
        related='company_id.fiscalyear_last_month', readonly=False,
        help_text='Si el día elegido no existe en el mes se usa el último '
                  '(Odoo fiscalyear_last_month).',
    )

    class Meta:
        # Con tabla real, como todo transitorio de la fuente
        # (``_auto = True``, ``odoo19c: odoo/orm/models_transient.py:18``).
        db_table = 'account_financial_year_op'
        verbose_name = 'Apertura de ejercicio fiscal'
        verbose_name_plural = 'Aperturas de ejercicio fiscal'

    def _compute_opening_move_posted(self):
        """≙ ``_compute_opening_move_posted`` (``:23-26``)."""
        company = self.company_id
        return bool(company) and company.opening_move_posted()

    @classmethod
    def _check_fiscalyear(cls, fiscalyear_last_month, fiscalyear_last_day):
        """≙ ``_check_fiscalyear`` (``:28-39``) — la fecha debe existir; se
        prueba sobre 2020 (bisiesto), igual que la fuente.

        Comentario de la fuente, verbatim: *"We do not define the constrain on
        res.company, since the recomputation of the related fields is done one
        field at a time."*
        """
        try:
            date(2020, int(fiscalyear_last_month), fiscalyear_last_day)
        except ValueError:
            raise ValidationError(_(
                'Incorrect fiscal year date: day is out of range for '
                'month. Month: %(month)s; Day: %(day)s') % {
                    'month': fiscalyear_last_month,
                    'day': fiscalyear_last_day,
                })

    def clean(self):
        """El ``@api.constrains`` de la fuente, en la forma del stack."""
        super().clean()
        if self.fiscalyear_last_month and self.fiscalyear_last_day:
            self._check_fiscalyear(
                self.fiscalyear_last_month, self.fiscalyear_last_day)

    @classmethod
    def _company_fields_to_update(cls):
        """≙ ``_company_fields_to_update`` (``:41-43``) — el contrato,
        verbatim."""
        return {'fiscalyear_last_day', 'fiscalyear_last_month', 'opening_date'}

    @classmethod
    def _update_company(cls, company, vals):
        """≙ ``_update_company`` (``:45-63``).

        Comentario de la fuente, verbatim: *"Amazing workaround: non-stored
        related fields on company are a BAD idea since the 3 fields must
        follow the constraint '_check_fiscalyear_last_day'. The thing is, in
        case of related fields, the inverse write is done one value at a time,
        and thus the constraint is verified one value at a time... so it is
        likely to fail."*

        Por eso los tres viajan en **una** escritura: escribirlos de a uno
        haría que la restricción se validara sobre un estado intermedio.
        """
        company_fields_to_update = {k: k for k in cls._company_fields_to_update()}
        company_fields_to_update['opening_date'] = 'account_opening_date'
        cambiados = []
        for wizard_field, company_field in company_fields_to_update.items():
            if wizard_field in vals:
                setattr(company, company_field, vals[wizard_field])
                cambiados.append(company_field)
        if cambiados:
            company.save(update_fields=cambiados)
        opening_date = vals.get('opening_date', company.account_opening_date)
        opening_move = company.account_opening_move
        if opening_date and opening_move is not None \
                and opening_move.state == 'draft':
            opening_move.date = opening_date - timedelta(days=1)
            opening_move.save(update_fields=['date'])

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``:65-75``): la empresa se actualiza ANTES de guardar
        el asistente, y los campos que ya viajaron a la empresa se sacan de
        ``vals``. El bucle por ``vals`` es el de la referencia; ``super().create``
        es ``DefaultGetMixin.create``, el porte por contenido de
        ``BaseModel.create`` (:ref:`h-api-1108`).

        **La excepción de la fuente no aplica aquí, y decirlo importa.** Allá
        ``opening_date`` se conserva en ``vals`` con este comentario verbatim:
        *"we need to keep opening_date in vals since it's a required field
        otherwise the wizard fails to be created"*. La razón es que en Odoo un
        ``related`` **almacena columna** por defecto y la suya es requerida.
        Aquí los tres son ``related`` sin columna —el defecto de la fuente para
        un ``related`` según ``fields.py:455``, y el que este árbol adopta—,
        así que no hay columna requerida que satisfacer y los tres se sacan por
        igual. El valor sigue siendo legible: se lee de la empresa, que es
        donde ``_update_company`` acaba de escribirlo.
        """
        for vals in vals_list:
            company = vals.get('company_id')
            if company is not None:
                cls._update_company(company, vals)
            for key in cls._company_fields_to_update():
                vals.pop(key, None)
        return super().create(vals_list)

    def write(self, **vals):
        """≙ ``write`` (``:77-84``)."""
        self._update_company(self.company_id, vals)
        for key in self._company_fields_to_update():
            vals.pop(key, None)
        for name, value in vals.items():
            setattr(self, name, value)
        if vals:
            self.save(update_fields=list(vals))
        return True

    def action_save_onboarding_fiscal_year(self):
        """≙ ``action_save_onboarding_fiscal_year`` (``:86-91``).

        Marca el paso del onboarding contable. La fuente además refresca los
        valores de render del tablero por ``xmlid`` y devuelve un
        ``ir.actions.client soft_reload``; aquí el registro por ``xmlid`` de
        los datos de ``account`` es la tarea #299 y la orden de navegación no
        tiene cliente que la ejecute — ver el docstring del módulo.
        """
        return OnboardingOnboardingStep.action_validate_step(
            'account.onboarding_onboarding_step_fiscal_year',
            company=self.company_id,
        )


class AccountSetupBankManualConfig(TransientModel):
    """≙ ``account.setup.bank.manual.config`` — alta manual de una cuenta
    bancaria y su diario (``odoo19c: setup_wizards.py:94-194``)."""

    _name = 'account.setup.bank.manual.config'
    _inherits = {'res.partner.bank': 'res_partner_bank_id'}
    _description = 'Bank setup manual config'
    _check_company_auto = True

    #: ≙ ``res_partner_bank_id`` (``:100``). Es la FK que nombra el
    #: ``_inherits``: por ella el asistente expone como propios ``acc_number``,
    #: ``partner``, ``bank`` y el resto de la cuenta bancaria.
    res_partner_bank_id = fields.Many2one(
        'base.ResPartnerBank', on_delete=models.CASCADE,
        db_column='res_partner_bank_id', related_name='setup_wizards',
        help_text='Cuenta bancaria delegada (Odoo res_partner_bank_id).',
    )
    new_journal_name = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Nombre del diario ligado a esta cuenta '
                  '(Odoo new_journal_name).',
    )
    linked_journal_id = fields.Many2one(
        'account.AccountJournal', on_delete=models.SET_NULL, null=True,
        blank=True, db_column='linked_journal_id',
        related_name='setup_wizards', verbose_name='Journal',
        help_text='Diario ligado (Odoo linked_journal_id).',
    )
    #: ≙ ``num_journals_without_account_bank`` / ``_credit`` (``:108-109``).
    #: Su ``default`` allá es ``lambda self: self._number_unlinked_journal(…)``,
    #: que necesita la empresa activa; aquí el conteo se pide al método y el
    #: campo arranca en 0 — el valor lo escribe quien abre el asistente, que
    #: es el único que sabe de qué empresa habla.
    num_journals_without_account_bank = fields.Integer(default=0)
    num_journals_without_account_credit = fields.Integer(default=0)
    company_id = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        db_column='company_id', related_name='bank_setup_wizards',
        help_text='Empresa (Odoo company_id).',
    )

    class Meta:
        db_table = 'account_setup_bank_manual_config'
        verbose_name = 'Alta manual de cuenta bancaria'
        verbose_name_plural = 'Altas manuales de cuenta bancaria'

    #: ``bank_bic`` NO se declara aquí, y es deliberado. La fuente lo declara
    #: como ``related='bank_id.bic'`` (``:112``) porque su ``_inherits`` le da
    #: ``bank_id``; en este árbol ``ResPartnerBank`` YA declara
    #: ``bank_bic = fields.Char(related='bank.bic')``
    #: (``src/addons/base/models/res_bank.py``), así que la delegación lo
    #: expone con el mismo nombre y el mismo valor. Declararlo otra vez sería
    #: una segunda fuente de verdad sobre la misma columna.

    @classmethod
    def _number_unlinked_journal(cls, journal_type, company):
        """≙ ``_number_unlinked_journal`` (``:114-119``) — cuántos diarios de
        ese tipo NO tienen cuenta bancaria ligada.

        La fuente lee la empresa del entorno; aquí viaja por parámetro, que es
        la forma de este árbol para todo lo que allá sale de ``self.env``.
        """
        queryset = AccountJournal.objects.filter(
            type=journal_type, bank_account_id__isnull=True, company=company)
        excluido = cls.default_linked_journal_id(journal_type, company)
        if excluido is not None:
            queryset = queryset.exclude(pk=excluido)
        return queryset.count()

    @classmethod
    def _onchange_acc_number(cls, acc_number):
        """≙ ``_onchange_acc_number`` (``:121-124``) — el nombre propuesto del
        diario es el número de cuenta."""
        return acc_number

    @classmethod
    def create(cls, company, acc_number, bank=None, bank_bic=None, **vals):
        """≙ ``create`` (``:126-141``).

        Docstring de la fuente, verbatim: *"This wizard is only used to setup
        an account for the current active company, so we always inject the
        corresponding partner when creating the model."*

        Y la segunda mitad: sin banco elegido, un BIC busca o crea el banco.
        """
        bank_account = ResPartnerBank.objects.create(
            acc_number=acc_number, partner=company.partner)
        if bank is None and bank_bic:
            bank = ResBank.objects.filter(bic=bank_bic).first()
            if bank is None:
                bank = ResBank.objects.create(name=bank_bic, bic=bank_bic)
        if bank is not None:
            bank_account.bank = bank
            bank_account.save(update_fields=['bank'])
        return cls.objects.create(
            company_id=company, res_partner_bank_id=bank_account,
            new_journal_name=acc_number, **vals)

    @classmethod
    def _onchange_new_journal_related_data(cls, journal):
        """≙ ``_onchange_new_journal_related_data`` (``:143-146``)."""
        return journal.name if journal is not None else None

    def _compute_linked_journal_id(self, journal_type='bank'):
        """≙ ``_compute_linked_journal_id`` (``:148-152``).

        Comentario de la fuente, verbatim: *"Despite its name, journal_id is
        actually a One2many field"* — de ahí el ``[0]``. Aquí el lado inverso
        de la cuenta bancaria es ``journals``, su ``related_name``.
        """
        propios = self.res_partner_bank_id.journals.all() \
            if self.res_partner_bank_id is not None else []
        primero = next(iter(propios), None)
        if primero is not None:
            return primero
        pk = self.default_linked_journal_id(journal_type, self.company_id)
        return AccountJournal.objects.filter(pk=pk).first() if pk else None

    @classmethod
    def default_linked_journal_id(cls, journal_type, company):
        """≙ ``default_linked_journal_id`` (``:154-171``) — el primer diario
        del tipo sin cuenta ligada Y sin asientos.

        Devuelve la clave primaria, como la fuente (``….id``).
        """
        journals_with_moves = AccountMove.objects.filter(
            journal__isnull=False, journal__type=journal_type,
        ).values_list('journal', flat=True)
        journal = AccountJournal.objects.filter(
            type=journal_type, bank_account_id__isnull=True, company=company,
        ).exclude(pk__in=journals_with_moves).first()
        return journal.pk if journal is not None else None

    def set_linked_journal_id(self, journal_type='bank'):
        """≙ ``set_linked_journal_id`` (``:173-190``) — *"Called when saving
        the wizard."*

        Sin diario elegido crea uno con el código que
        ``AccountJournal._get_next_journal_default_code`` deriva, ligado a la
        cuenta bancaria del asistente y con el origen de extracto en
        ``undefined``. Con diario elegido, le liga la cuenta y le pone el
        nombre nuevo. Las dos ramas son las de la fuente.
        """
        selected_journal = self.linked_journal_id
        if selected_journal is None:
            code = AccountJournal._get_next_journal_default_code(
                journal_type, self.company_id)
            selected_journal = AccountJournal.objects.create(
                name=self.new_journal_name,
                code=code,
                type=journal_type,
                company=self.company_id,
                bank_account_id=self.res_partner_bank_id,
                bank_statements_source='undefined',
            )
            self.linked_journal_id = selected_journal
            self.save(update_fields=['linked_journal_id'])
        else:
            selected_journal.bank_account_id = self.res_partner_bank_id
            selected_journal.name = self.new_journal_name
            selected_journal.save(update_fields=['bank_account_id', 'name'])
        return selected_journal

    @classmethod
    def validate(cls):
        """Called by the validation button of this wizard. Serves as an
        extension hook in account_bank_statement_import.

        (Docstring verbatim de la fuente, ``:192-196``.) Devuelve ``None`` en
        vez del ``ir.actions.client soft_reload`` — ver el docstring del
        módulo.
        """
        return None

    @classmethod
    def _compute_company_id(cls, company=None, active_company=None):
        """≙ ``_compute_company_id`` (``:198-200``) — el fallback a la empresa
        activa."""
        return company or active_company
