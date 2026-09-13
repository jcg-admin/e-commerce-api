"""Tests — crear un contacto desde un texto, promoverlo, y proteger el borrado.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_unlink_except_user`` (``:951-961``), ``create_company`` (``:1004-1012``),
``_create_contact_parent_company`` (``:1014-1021``), ``name_create``
(``:1072-1093``) y ``find_or_create`` (``:1095-1120``), más
``parse_contact_from_email`` (``odoo19c: odoo/tools/mail.py:1031-1056``), que
es de quien los dos últimos cuelgan.

Los tres mecanismos, y por qué no se confunden:

- **crear desde un texto** — quien escribe ``Ana <ana@x.mx>`` en un campo de
  contacto no quiere rellenar un formulario. La fuente parte ese texto en
  nombre y correo, y si sólo hay correo el nombre **es** el correo.
- **promover** — un contacto suelto con razón social escrita a mano no es una
  empresa: ``create_company`` la convierte en un partner padre real y le
  cuelga al contacto y a sus hijos.
- **proteger el borrado** — un partner con cuenta activa no se borra. La
  fuente manda archivar el usuario primero, y su mensaje lo dice.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from django.contrib.auth import get_user_model

from addons.base.models.res_country import ResCountry
from addons.base.models.res_partner import ResPartner
from exceptions import RedirectWarning, ValidationError
from orm.environments import context_scope, sudo
from tools.mail import parse_contact_from_email

User = get_user_model()

pytestmark = pytest.mark.integration

PASSWORD = 'CrearYBorrar123!'


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


class TestParseContactFromEmail:
    """≙ ``parse_contact_from_email`` (``odoo19c: odoo/tools/mail.py:1031``).

    Los tres formatos que su docstring enumera, más el caso por defecto.
    """

    @pytest.mark.parametrize('text, expected', [
        ('Raoul <raoul@grosbedon.fr>', ('Raoul', 'raoul@grosbedon.fr')),
        ('"Raoul le Grand" <raoul@grosbedon.fr>',
         ('Raoul le Grand', 'raoul@grosbedon.fr')),
        ('Raoul raoul@grosbedon.fr', ('Raoul', 'raoul@grosbedon.fr')),
    ])
    def test_the_three_supported_shapes(self, text, expected):
        """El eje — los tres que la fuente enumera en su docstring."""
        assert parse_contact_from_email(text) == expected

    def test_a_text_without_an_email_becomes_the_name(self):
        """CONTROL del caso por defecto: *"text is set as name"*.

        Qué lo haría fallar: devolver ``('', '')`` para lo que no parsea. El
        contacto se crearía sin nombre.
        """
        assert parse_contact_from_email('Solo un nombre') == ('Solo un nombre', '')

    def test_the_empty_text_gives_two_empty_strings(self):
        """CONTROL de la guarda de entrada.

        Qué lo haría fallar: indexar ``split_results[0]`` sin comprobar.
        """
        assert parse_contact_from_email('') == ('', '')
        assert parse_contact_from_email('   ') == ('', '')


class TestNameCreate:
    """≙ ``name_create`` (``:1072-1093``)."""

    def test_it_splits_the_name_and_the_email(self, db):
        """El eje."""
        pk, _display = ResPartner.name_create('Ana Lopez <ana@kaupamex.mx>')
        who = ResPartner.objects.get(pk=pk)
        assert who.name == 'Ana Lopez'
        assert who.email == 'ana@kaupamex.mx'

    def test_with_only_an_email_the_name_is_the_email(self, db):
        """CONTROL de ``name or email_normalized``.

        Su docstring lo dice: *"If only an email address is received and that
        the regex cannot find a name, the name will have the email value."*
        Qué lo haría fallar: dejar el nombre vacío, que es una fila sin nada
        legible en ninguna lista.
        """
        pk, _display = ResPartner.name_create('sola@kaupamex.mx')
        who = ResPartner.objects.get(pk=pk)
        assert who.name == 'sola@kaupamex.mx'
        assert who.email == 'sola@kaupamex.mx'

    def test_without_an_email_the_partner_has_none(self, db):
        """Un texto sin correo no deja basura en el campo.

        **Este caso NO discrimina el ``if email_normalized`` de la fuente, y
        conviene decirlo.** Se midió: sustituir la guarda por escribir la
        clave siempre deja los 23 casos en verde. La razón es que aquí el
        campo es ``blank=True, default=''``, así que *no escribir* y
        *escribir la cadena vacía* dan el mismo valor almacenado — el
        fenómeno que la guarda protege no existe en este árbol.

        Allá sí existe: su comentario dice *"keep default_email in context"*,
        y omitir la clave deja ganar al ``default_email`` que ``default_get``
        pone. La guarda se porta igual, por fidelidad, y se vuelve observable
        cuando ``default_get`` exista. Sucesor: tarea **#113**.
        """
        pk, _display = ResPartner.name_create('Solo un nombre')
        who = ResPartner.objects.get(pk=pk)
        assert who.name == 'Solo un nombre'
        assert not who.email

    def test_force_email_refuses_a_text_without_one(self, db):
        """CONTROL de la clave ``force_email`` del contexto.

        Mensaje de la fuente, verbatim: *"Couldn't create contact without
        email address!"* Qué lo haría fallar: ignorar la clave, y entonces un
        alta que exige correo aceptaría cualquier cosa.
        """
        with context_scope(force_email=True):
            with pytest.raises(ValidationError):
                ResPartner.name_create('Solo un nombre')

    def test_force_email_lets_a_valid_one_through(self, db):
        """CONTROL de la dirección contraria — la clave no cierra el alta.

        Sin este caso, un ``force_email`` que rechazara siempre pasaría el
        anterior.
        """
        with context_scope(force_email=True):
            pk, _display = ResPartner.name_create('con@kaupamex.mx')
        assert ResPartner.objects.get(pk=pk).email == 'con@kaupamex.mx'

    def test_it_returns_the_pair_id_and_display_name(self, db):
        """CONTROL de la forma del retorno — la fuente devuelve una tupla."""
        result = ResPartner.name_create('Ana <ana2@kaupamex.mx>')
        assert isinstance(result, tuple) and len(result) == 2
        assert result[0] == ResPartner.objects.get(email='ana2@kaupamex.mx').pk
        assert result[1]


class TestFindOrCreate:
    """≙ ``find_or_create`` (``:1095-1120``)."""

    def test_it_finds_the_existing_one(self, db):
        """El eje: no duplica."""
        existing = ResPartner.objects.create(name='Ya esta',
                                             email='ya@kaupamex.mx')
        found = ResPartner.find_or_create('Otro nombre <ya@kaupamex.mx>')
        assert found.pk == existing.pk
        assert found.name == 'Ya esta', 'encuentra, no reescribe'

    def test_the_search_ignores_case(self, db):
        """CONTROL del ``=ilike`` de la fuente.

        Qué lo haría fallar: comparar exacto. Un correo escrito en mayúsculas
        crearía un segundo partner para la misma persona, que es el duplicado
        que este método existe para evitar.
        """
        existing = ResPartner.objects.create(name='Mayusculas',
                                             email='MAY@kaupamex.mx')
        found = ResPartner.find_or_create('may@kaupamex.mx')
        assert found.pk == existing.pk

    def test_it_creates_when_there_is_none(self, db):
        """CONTROL de la otra mitad del nombre del método."""
        found = ResPartner.find_or_create('Nueva <nueva@kaupamex.mx>')
        assert found.pk is not None
        assert found.name == 'Nueva'

    def test_an_empty_email_raises(self, db):
        """CONTROL de la guarda de entrada.

        Mensaje de la fuente, verbatim: *"An email is required for
        find_or_create to work"*.
        """
        with pytest.raises(ValueError):
            ResPartner.find_or_create('')

    def test_assert_valid_email_refuses_a_text_without_one(self, db):
        """CONTROL del parámetro ``assert_valid_email``.

        Qué lo haría fallar: ignorarlo. Quien lo pide explícitamente quiere
        que el texto sin correo reviente, no que cree un partner con el texto
        de nombre.
        """
        with pytest.raises(ValueError):
            ResPartner.find_or_create('Solo un nombre', assert_valid_email=True)

    def test_without_the_flag_a_text_without_an_email_creates(self, db):
        """CONTROL de la dirección contraria — por defecto NO revienta.

        Sin este caso, una implementación que rechazara siempre el texto sin
        correo pasaría el anterior.
        """
        found = ResPartner.find_or_create('Solo un nombre sin correo')
        assert found.name == 'Solo un nombre sin correo'


class TestCreateCompany:
    """≙ ``create_company`` (``:1004``) y ``_create_contact_parent_company``
    (``:1014``)."""

    def test_it_promotes_the_company_name_to_a_real_parent(self, db):
        """El eje: la razón social escrita a mano pasa a ser un partner."""
        mx = ResCountry.objects.get_or_create(
            code='MX', defaults={'name': 'Mexico'})[0]
        who = ResPartner.objects.create(
            name='Contacto', company_name='Yoruba SA', vat='XAXX010101000',
            street='Reforma 1', city='CDMX', country=mx)
        assert who.create_company() is True
        who.refresh_from_db()
        assert who.parent is not None
        assert who.parent.name == 'Yoruba SA'
        assert who.parent.is_company is True
        assert who.parent.vat == 'XAXX010101000'
        assert who.parent.street == 'Reforma 1', 'la dirección viaja al padre'

    def test_without_a_company_name_nothing_is_created(self, db):
        """CONTROL de la guarda ``if self.company_name``.

        Qué lo haría fallar: crear un padre sin nombre. Quedaría un partner
        vacío colgando de cada contacto que pulse el botón por error.
        """
        before = ResPartner.objects.count()
        who = ResPartner.objects.create(name='Suelto')
        assert who.create_company() is True
        who.refresh_from_db()
        assert who.parent is None
        assert ResPartner.objects.count() == before + 1, 'sólo el propio contacto'

    def test_the_children_move_to_the_new_company(self, db):
        """CONTROL del ``child_ids`` del ``write`` de la fuente.

        Qué lo haría fallar: mover sólo al contacto. Sus direcciones se
        quedarían colgando de él en vez de de la empresa, y la jerarquía
        quedaría con dos niveles donde la fuente deja uno.
        """
        who = ResPartner.objects.create(name='Contacto',
                                        company_name='Yoruba SA')
        child = ResPartner.objects.create(name='Entrega', parent=who,
                                          type=ResPartner.TYPE_DELIVERY)
        who.create_company()
        child.refresh_from_db()
        who.refresh_from_db()
        assert child.parent_id == who.parent_id
        assert child.parent.name == 'Yoruba SA'


class TestUnlinkExceptUser:
    """≙ ``_unlink_except_user`` (``:951-961``)."""

    def test_a_partner_with_an_active_user_is_not_deleted(self, db):
        """El eje. Qué lo haría fallar: no consultar las cuentas."""
        account = User.objects.create_user(login='borrar@kaupamex.mx',
                                           password=PASSWORD)
        with pytest.raises(RedirectWarning):
            account.partner.delete()

    def test_a_partner_without_users_is_deleted(self, db):
        """CONTROL de la dirección contraria.

        Su propio comentario lo dice: *"no linked user, operation is
        allowed"*. Sin este caso, una guarda que bloqueara todo borrado
        pasaría el anterior.
        """
        who = ResPartner.objects.create(name='Sin cuentas')
        pk = who.pk
        who.delete()
        assert not ResPartner.objects.filter(pk=pk).exists()

    def test_the_message_names_the_linked_users(self, db):
        """CONTROL del ``names=`` del mensaje.

        Qué lo haría fallar: un mensaje genérico. Quien lo lee tiene que
        saber **qué** cuenta archivar, o el consejo de la fuente —*"You should
        rather archive them after archiving their associated user"*— no se
        puede seguir.
        """
        account = User.objects.create_user(login='nombrado@kaupamex.mx',
                                           password=PASSWORD)
        with pytest.raises(RedirectWarning) as exc:
            account.partner.delete()
        assert 'nombrado@kaupamex.mx' in str(exc.value)
