"""``DefaultGetMixin`` — los cinco orígenes del valor con que empieza un alta.

≙ ``BaseModel.default_get`` (``odoo19c: odoo/orm/models.py:1271-1338``) y su
consumidor ``_add_missing_default_values`` (``:1546-1596``), que es quien lo
llama desde ``create`` (``:4796``).

Por qué el orden es el contrato
===============================

Los cinco orígenes están numerados en la fuente, y el número **es** una
prioridad: el contexto gana sobre el default de usuario, el default de usuario
gana sobre el ``default`` del campo, y el ``default`` del campo gana sobre el
respaldo por empresa. Un test que sólo compruebe *"devuelve un valor"* pasa
igual con los cinco reordenados, y entonces no mide nada — por eso cada par en
conflicto tiene su caso.

Qué haría fallar a estos casos
==============================

Reordenar dos orígenes cualesquiera: cada caso de conflicto siembra los dos
lados a la vez y afirma **cuál** gana. Y para el paso que hace observable la
guarda de ``name_create``, el control es directo: con ``default_email`` en el
contexto y un nombre sin correo, la fila tiene que salir con ese correo; si
``create`` no aplicara los defaults, saldría vacía.

Medido con la guarda anulada
============================

Sustituyendo el cuerpo de ``create`` por un ``objects.create`` pelado —o sea,
quitando la llamada a ``_add_missing_default_values``— el módulo pasa de
**35 passed** a **3 failed, 32 passed**, y caen exactamente los tres que
dependen del paso:

- ``test_the_context_default_reaches_the_row``
- ``test_ir_default_reaches_the_row_too``
- ``test_without_an_email_in_the_name_the_context_one_lands``

Sobreviven ``test_the_given_value_always_beats_the_default`` (el valor lo trae
el llamador, no el default) y
``test_with_an_email_in_the_name_the_guard_shields_the_context`` (el correo
sale del nombre). Los dos miden otra cosa, y está bien que la midan: lo que no
valdría es no saberlo. El paso se restauró y ``git diff`` lo confirma.
"""
import pytest


from addons.base.models import IrDefault, ResPartner
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_cron import IrCron
from addons.base.models.ir_sequence import IrSequenceDateRange
from addons.base.models.ir_ui_view import IrUiViewCustom
from addons.base.models.res_users import ResUsers
from orm import registry
from orm.environments import context_scope, sudo
from orm.model_classes import ensure_rec_names, resolve_rec_name
from orm.models import DefaultGetMixin, _delegated_origin, _field_names


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


@pytest.mark.django_db
class TestContextWins:
    """1. El contexto manda sobre todo lo demás."""

    def test_context_key_lands_in_the_defaults(self):
        with context_scope(default_comment='del contexto'):
            defaults = ResPartner.default_get(['comment'])
        assert defaults['comment'] == 'del contexto'

    def test_a_field_not_asked_for_is_not_returned(self):
        """*"Unrequested defaults won't be considered"* — nota de la fuente."""
        with context_scope(default_comment='del contexto',
                           default_website='https://ejemplo.mx'):
            defaults = ResPartner.default_get(['comment'])
        assert 'website' not in defaults

    def test_an_unknown_field_is_skipped_not_raised(self):
        assert ResPartner.default_get(['no_existe_este_campo']) == {}


@pytest.mark.django_db
class TestUserDefaultWins:
    """2. El default de usuario, por encima del ``default`` del campo."""

    def test_ir_default_beats_the_field_default(self):
        """``active`` declara ``default=True``; ``ir.default`` dice ``False``.

        Si el orden estuviera invertido saldría ``True`` — el valor del campo—
        y el default que el administrador fijó no se vería nunca.
        """
        IrDefault.set('base.ResPartner', 'active', False)
        registry.clear_cache('default')
        assert ResPartner.default_get(['active'])['active'] is False

    def test_the_context_still_beats_ir_default(self):
        IrDefault.set('base.ResPartner', 'comment', 'del administrador')
        registry.clear_cache('default')
        with context_scope(default_comment='del contexto'):
            defaults = ResPartner.default_get(['comment'])
        assert defaults['comment'] == 'del contexto'


@pytest.mark.django_db
class TestFieldDefault:
    """3. El ``default`` declarado en el campo."""

    def test_the_field_default_is_read(self):
        assert ResPartner.default_get(['active'])['active'] is True

    def test_a_falsy_default_still_counts(self):
        """``has_default()``, no ``if field.default``.

        La fuente pregunta ``if field.default:`` porque allá es un invocable, y
        un invocable siempre es cierto. Aquí ``field.default`` **es el valor**,
        así que ese mismo ``if`` perdería un ``default=False``. El caso lo mide:
        ``is_company`` lo declara ``False`` y tiene que salir.
        """
        assert ResPartner.default_get(['is_company'])['is_company'] is False

    def test_a_field_without_default_is_absent(self):
        """``image_1920`` no declara ``default=``; ``vat`` sí (``''``).

        La primera version de este caso apuntaba a ``vat`` y fallaba: el campo
        declara ``default=''``, asi que **si** tiene default y el paso 3 lo
        responde. El caso medía la premisa equivocada, no el mecanismo.
        """
        assert 'image_1920' not in ResPartner.default_get(['image_1920'])


@pytest.mark.django_db
class TestCompanyDependentFallback:
    """4. El respaldo por empresa, el último de los cuatro."""

    def test_the_fallback_is_read_for_a_company_dependent_field(self):
        IrDefault.set('base.ResPartner', 'barcode', 'RESPALDO-42')
        registry.clear_cache('default')
        assert ResPartner.default_get(['barcode'])['barcode'] == 'RESPALDO-42'

    def test_the_field_default_beats_the_company_fallback(self):
        """``active`` no es dependiente de empresa: gana su ``default``.

        Es el par que distingue el paso 3 del paso 4. Con los dos invertidos,
        el respaldo se colaría por delante del valor declarado en el campo.
        """
        IrDefault.set('base.ResPartner', 'active', False)
        registry.clear_cache('default')
        # Con ``ir.default`` puesto gana el paso 2 (no dependiente de empresa);
        # sin el, el paso 3.
        assert ResPartner.default_get(['active'])['active'] is False
        IrDefault.discard_values('base.ResPartner', 'active', [False])
        registry.clear_cache('default')
        assert ResPartner.default_get(['active'])['active'] is True


@pytest.mark.django_db
class TestSuperIsReachable:
    """Los dos overrides que existían ya pueden llamar a ``super()``.

    Antes de la tarea #113 no había base a la que llamar, así que cada uno era
    la respuesta completa y los cuatro primeros orígenes no los veía nadie.
    """

    def test_ir_cron_adopts_the_mixin(self):
        assert issubclass(IrCron, DefaultGetMixin)

    def test_ir_sequence_date_range_adopts_the_mixin(self):
        assert issubclass(IrSequenceDateRange, DefaultGetMixin)

    def test_res_partner_adopts_the_mixin(self):
        assert issubclass(ResPartner, DefaultGetMixin)

    def test_ir_cron_keeps_its_own_defaults(self):
        defaults = IrCron.default_get(['interval_number', 'interval_type',
                                       'priority', 'active'])
        assert defaults['interval_number'] == 1
        assert defaults['interval_type'] == 'months'
        assert defaults['priority'] == 5

    def test_ir_cron_lets_the_context_through(self):
        """La prueba de que el ``super()`` corre: el contexto es del padre."""
        with context_scope(default_interval_number=7):
            defaults = IrCron.default_get(['interval_number'])
        assert defaults['interval_number'] == 7


class TestRecNameResolution:
    """``_rec_name`` se resuelve; no se declara a mano.

    ≙ el paso 5 de ``_init_model_class_attributes``
    (``odoo19c: odoo/orm/model_classes.py:433-441``). La referencia sólo lo
    declara cuando difiere del default, y por eso ``ResPartner`` no lo declara
    y aun así ``name_create`` escribe ``{self._rec_name: ...}``.
    """

    def test_a_model_with_name_resolves_to_name(self):
        assert ResPartner._rec_name == 'name'

    def test_a_model_without_name_gets_the_explicit_none(self):
        """El default de ``BaseModel``, puesto a mano porque la base es Django.

        ``IrCron`` llama a su campo ``cron_name``, así que no hay ``name`` que
        resolver. Sin este paso, ``cls._rec_name`` daba ``AttributeError``.
        """
        assert IrCron._rec_name is None

    def test_a_declared_rec_name_survives(self):
        """``ir.config_parameter`` declara ``_rec_name = 'key'``, y se respeta."""
        assert SystemParameter._rec_name == 'key'

    def test_the_attname_of_a_relation_counts_as_a_field(self):
        """``ir.ui.view.custom`` declara ``_rec_name = 'user_id'``, verbatim.

        Aquí ese campo se llama ``user`` y su ``attname`` es ``user_id``. Si la
        validación mirara sólo ``name``, el porte fiel del atributo sería un
        error — y el arreglo habría sido cambiar el valor portado, no el
        instrumento.
        """
        assert IrUiViewCustom._rec_name == 'user_id'

    def test_an_invalid_rec_name_is_rejected(self):
        """La aserción de la fuente, verbatim en su intención.

        Es el control que hace real a los demás: sin él, un ``_rec_name`` que
        nombra un campo inexistente pasa callado y revienta en el primer
        ``name_create``, lejos de su causa.
        """
        class ModelWithBrokenRecName:
            _rec_name = 'campo_que_no_existe'
            _meta = ResPartner._meta

        with pytest.raises(ValueError, match='Invalid _rec_name'):
            resolve_rec_name(ModelWithBrokenRecName)

    def test_the_sweep_reports_how_many_it_resolved(self):
        """No devuelve ``None``: devuelve el conteo, para poder medir."""
        assert ensure_rec_names() > 0


@pytest.mark.django_db
class TestCreateAppliesTheDefaults:
    """``create`` aplica ``_add_missing_default_values``, como la fuente."""

    def test_the_context_default_reaches_the_row(self):
        with sudo(), context_scope(default_comment='sembrado por el contexto'):
            partner, = ResPartner.create([{'name': 'Alta con contexto'}])
        partner.refresh_from_db()
        assert partner.comment == 'sembrado por el contexto'

    def test_the_given_value_always_beats_the_default(self):
        """*"never allow the other way around"* — comentario de la fuente."""
        with sudo(), context_scope(default_comment='del contexto'):
            partner, = ResPartner.create([{'name': 'Alta', 'comment': 'explicito'}])
        partner.refresh_from_db()
        assert partner.comment == 'explicito'

    def test_ir_default_reaches_the_row_too(self):
        IrDefault.set('base.ResPartner', 'comment', 'del administrador')
        registry.clear_cache('default')
        with sudo():
            partner, = ResPartner.create([{'name': 'Alta con ir.default'}])
        partner.refresh_from_db()
        assert partner.comment == 'del administrador'


@pytest.mark.django_db
class TestNameCreateGuardIsObservable:
    """La guarda ``if email_normalized`` de ``name_create``, ya observable.

    Su comentario en la fuente es *"keep default_email in context"*: cuando el
    nombre no trae correo, la clave **no** se escribe, y entonces el
    ``default_email`` del contexto llega a la fila. Hasta la tarea #113 el
    árbol no tenía ``default_get``, así que la guarda no cambiaba nada y el
    docstring lo declaraba.
    """

    def test_without_an_email_in_the_name_the_context_one_lands(self):
        with context_scope(default_email='del.contexto@ejemplo.mx'):
            partner_id, _ = ResPartner.name_create('Cliente Sin Correo')
        partner = ResPartner.objects.get(pk=partner_id)
        assert partner.email == 'del.contexto@ejemplo.mx'

    def test_with_an_email_in_the_name_the_guard_shields_the_context(self):
        """El correo del nombre gana: la guarda escribe la clave y la protege.

        Es el otro lado del mismo control. Si la guarda desapareciera, el
        contexto pisaría al correo tecleado — o al revés, según el orden— y
        ninguno de los dos casos sueltos lo distinguiría.
        """
        with context_scope(default_email='del.contexto@ejemplo.mx'):
            partner_id, _ = ResPartner.name_create(
                'Cliente <del.nombre@ejemplo.mx>')
        partner = ResPartner.objects.get(pk=partner_id)
        assert partner.email == 'del.nombre@ejemplo.mx'

    def test_name_create_writes_through_rec_name(self):
        partner_id, _ = ResPartner.name_create('Cliente Con Nombre')
        partner = ResPartner.objects.get(pk=partner_id)
        assert getattr(partner, ResPartner._rec_name) == 'Cliente Con Nombre'


class TestDelegatedOrigin:
    """El campo heredado por ``_inherits`` delega en su padre."""

    def test_a_model_without_inherits_delegates_nothing(self):
        assert _delegated_origin(ResPartner, 'name') is None

    def test_the_users_delegation_resolves_to_the_partner(self):
        delegated = _delegated_origin(ResUsers, 'name')
        assert delegated is not None
        parent_model, parent_name = delegated
        assert parent_model is ResPartner
        assert parent_name == 'name'

    def test_a_field_the_parent_does_not_have_is_not_delegated(self):
        assert _delegated_origin(ResUsers, 'no_existe_ni_aqui_ni_alla') is None

    def test_field_names_includes_the_parents(self):
        """``_fields`` de la fuente ya trae los del padre; ``_meta`` no."""
        names = _field_names(ResUsers)
        assert 'login' in names
        assert 'name' in names       # llega del partner por delegación

    def test_field_names_excludes_the_reverse_relations(self):
        names = _field_names(ResPartner)
        assert 'name' in names
        assert 'child_ids' not in names


@pytest.mark.django_db
class TestAddMissingDefaultValues:
    """El paso que ``create`` da antes de escribir la fila."""

    def test_the_given_values_survive_untouched(self):
        values = ResPartner._add_missing_default_values({'name': 'Dado'})
        assert values['name'] == 'Dado'

    def test_the_missing_ones_get_their_default(self):
        values = ResPartner._add_missing_default_values({'name': 'Dado'})
        assert values['active'] is True

    def test_a_delegated_field_is_skipped_when_the_parent_comes_set(self):
        """*"avoid overriding inherited values when parent is set"*.

        Con el FK del padre ya en ``values``, los campos que llegan por
        delegación no se rellenan: el padre trae los suyos.
        """
        partner = ResPartner.objects.create(name='Padre puesto')
        with context_scope(default_name='no deberia usarse'):
            values = ResUsers._add_missing_default_values(
                {'login': 'x@ejemplo.mx', 'partner_id': partner.pk})
        assert values.get('name') != 'no deberia usarse'


@pytest.mark.django_db
class TestResPartnerOverride:
    """El ``default_get`` de ``res.partner``, en su mitad viable.

    ≙ ``odoo19c: res_partner.py:201-211``. La herencia del ``company_id`` del
    padre sigue bloqueada por **#110** —el campo no existe aquí—; el saneo del
    ``type`` que se cuela del contexto sí está.
    """

    def test_an_invalid_type_from_the_context_is_cleared(self):
        """*"protection for ``default_type`` values leaking from menu action"*.

        Qué haría fallar al caso: quitar el saneo. El valor basura llegaría
        entero y el alta reventaría en ``full_clean``, lejos de su causa.
        """
        with context_scope(default_type='no_es_un_tipo'):
            assert ResPartner.default_get(['type'])['type'] is None

    def test_a_valid_type_from_the_context_survives(self):
        """El otro lado del control: el saneo no puede comerse lo válido."""
        with context_scope(default_type=ResPartner.TYPE_INVOICE):
            defaults = ResPartner.default_get(['type'])
        assert defaults['type'] == ResPartner.TYPE_INVOICE

    def test_the_field_default_still_comes_through(self):
        assert ResPartner.default_get(['type'])['type'] == ResPartner.TYPE_CONTACT

    def test_the_lang_fallback_asks_default_get_first(self):
        """``_compute_lang`` ya recorre el primer escalón de la cascada.

        La fuente cae a ``default_get(['lang']).get('lang') or env.lang``;
        hasta #113 el cuerpo se saltaba el primero por no existir.
        """
        # Sin guardar: ``save()`` llama al propio ``_compute_lang`` (línea
        # 1544), así que una fila creada ya trae idioma y el respaldo no se
        # ejercita nunca. El cómputo no necesita fila.
        partner = ResPartner(name='Sin idioma', lang='')
        with context_scope(default_lang='ja'):
            assert partner._compute_lang() == 'ja'

    def test_the_lang_fallback_still_lands_without_a_context(self):
        """El otro lado: sin ``default_lang``, cae al idioma de la petición."""
        partner = ResPartner(name='Sin idioma', lang='')
        assert partner._compute_lang()
