"""``CopyMixin`` — duplicar un registro con sus hijos.

≙ los tres métodos que ``BaseModel`` declara seguidos: ``copy_data``
(``odoo19c: odoo/orm/models.py:5406``), ``copy_translations`` (``:5465``) y
``copy`` (``:5530``).

Qué decide qué se copia
=======================

El discriminador es ``field.copy``, que este árbol construyó en
``orm/fields.py`` con la ortografía de la fuente (``odoo19c:
odoo/orm/fields.py:281``). Sobre él van las dos listas: la **negra**
—:data:`MAGIC_COLUMNS`, ``parent_path`` y los FK de delegación— y la
**blanca**, que separa los campos propios de los que llegan heredados.

Qué haría fallar a estos casos
==============================

Cada exclusión tiene su caso, y cada caso mide **la exclusión**, no que la
copia exista. Si ``field.copy`` dejara de consultarse, el campo marcado
``copy=False`` viajaría; si :data:`MAGIC_COLUMNS` desapareciera de la lista
negra, la copia intentaría escribir el ``id`` del original y chocaría con la
clave primaria. Los dos son fallos que un caso de *"la copia existe"* no ve:
la fila sale igual.

Medido con la lista negra vaciada
=================================

Sustituyendo el cuerpo de ``_copy_blacklist`` por ``return set()``, el módulo
pasa de **25 passed** a **9 failed, 16 passed**. Caen los dos que la miden
directamente —``test_the_id_does_not_travel`` y
``test_the_audit_columns_do_not_travel``— y **los siete de** :class:`TestCopy`,
porque sin ella el ``id`` del original viaja y el alta revienta contra la clave
primaria.

Que caigan siete de rebote **no es ruido: es el dato**. Dice que la lista negra
no es una comodidad sino una precondición del alta, y que un caso de *"la copia
existe"* no puede distinguir su ausencia de nada: no sale una fila mal, no sale
ninguna. Los dieciséis que sobreviven miden otra cosa —el atributo ``copy`` del
campo, el conteo de columnas mágicas, el bloqueo de las traducciones, la
adopción del mixin— y está bien que la midan.

La cifra que este párrafo trae **no era la esperada**: la primera redacción
decía «3 failed, 18 passed» sobre un módulo de 21, escrita antes de correr la
sonda. Se corrigió con la medición. El cuerpo se restauró y ``git diff`` lo
confirma.
"""
import collections

import pytest
from orm.environments import sudo

import fields
from addons.base.models import ResPartner
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_config import ResConfig
from orm.models import LOG_ACCESS_COLUMNS, MAGIC_COLUMNS, CopyMixin


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


class TestFieldCopyFlag:
    """``Field.copy`` — el atributo que la fuente declara en ``Field``."""

    def test_a_field_copies_by_default(self):
        """``copy: bool = True`` (``odoo19c: odoo/orm/fields.py:281``)."""
        assert ResPartner._meta.get_field('name').copy is True

    def test_a_field_can_opt_out(self):
        assert fields.Char(max_length=10, copy=False).copy is False

    def test_the_flag_does_not_reach_the_migration(self):
        """``copy`` describe el duplicado, no la columna.

        Emitirlo en ``deconstruct`` cambiaría el estado de **todos** los campos
        del árbol sin que ninguna columna hubiera cambiado, y
        ``makemigrations --check`` dejaría de estar limpio.
        """
        _name, _path, _args, kwargs = fields.Char(max_length=10,
                                                  copy=False).deconstruct()
        assert 'copy' not in kwargs


class TestMagicColumns:
    """Las columnas que el ORM pone y una copia no lleva."""

    def test_the_id_is_magic(self):
        assert 'id' in MAGIC_COLUMNS

    def test_the_audit_columns_are_the_log_access_ones(self):
        """≙ ``LOG_ACCESS_COLUMNS`` (``odoo19c: models.py:296``).

        Allá son cuatro y dos son de autoría; aquí ``TimeStampedModel`` declara
        dos y ninguna la guarda. La divergencia es del mixin, no de la copia.
        """
        assert LOG_ACCESS_COLUMNS == ['created_at', 'updated_at']
        assert set(LOG_ACCESS_COLUMNS) <= set(MAGIC_COLUMNS)


@pytest.mark.django_db
class TestCopyData:
    """``copy_data`` — los valores, antes de que exista la fila nueva."""

    def test_a_plain_field_travels(self):
        partner = ResPartner.objects.create(name='Original', comment='texto')
        assert partner.copy_data()['comment'] == 'texto'

    def test_the_id_does_not_travel(self):
        """Si viajara, el alta chocaría con la clave primaria del original."""
        partner = ResPartner.objects.create(name='Original')
        assert 'id' not in partner.copy_data()

    def test_the_audit_columns_do_not_travel(self):
        """La copia es nueva: su fecha de alta es la suya, no la del original."""
        partner = ResPartner.objects.create(name='Original')
        values = partner.copy_data()
        assert 'created_at' not in values
        assert 'updated_at' not in values

    def test_the_given_default_wins(self):
        partner = ResPartner.objects.create(name='Original', comment='texto')
        assert partner.copy_data({'comment': 'otro'})['comment'] == 'otro'

    def test_a_relation_travels_as_its_id(self):
        """El id, no la instancia: es lo que ``objects.create`` toma."""
        padre = ResPartner.objects.create(name='Padre', is_company=True)
        hijo = ResPartner.objects.create(name='Hijo', parent=padre)
        assert hijo.copy_data()['parent_id'] == padre.pk

    def test_a_record_already_seen_returns_none(self):
        """La guarda contra la recursión de una relación circular.

        Allá viaja en el contexto (``__copy_data_seen``); aquí es un
        parámetro, porque el contexto de este árbol es de sólo lectura.
        """
        partner = ResPartner.objects.create(name='Original')
        seen = collections.defaultdict(set)
        assert partner.copy_data(seen=seen) is not None
        assert partner.copy_data(seen=seen) is None


@pytest.mark.django_db
class TestCopy:
    """``copy`` — los tres pasos de la fuente, en su orden."""

    def test_the_copy_is_a_new_row(self):
        partner = ResPartner.objects.create(name='Original')
        copia = partner.copy()
        assert copia.pk != partner.pk

    def test_res_partner_appends_the_copy_suffix(self):
        """≙ ``copy_data`` de ``res.partner`` (``odoo19c: :564-569``)."""
        partner = ResPartner.objects.create(name='Original')
        assert partner.copy().name == 'Original (copy)'

    def test_a_given_name_is_not_suffixed(self):
        """El ``if default.get('name')`` de la fuente, y no es cosmético.

        Sin la guarda, un duplicado con nombre dado saldría como
        ``'Nombre nuevo (copy)'``.
        """
        partner = ResPartner.objects.create(name='Original')
        assert partner.copy({'name': 'Nombre dado'}).name == 'Nombre dado'

    def test_the_copy_gets_the_defaults_of_a_normal_create(self):
        """El alta va por ``DefaultGetMixin.create``, como allá.

        La fuente llama a ``self.create(vals_list)``, que aplica
        ``_add_missing_default_values``. Un duplicado recibe los defaults que
        recibiría un alta cualquiera.
        """
        partner = ResPartner.objects.create(name='Original')
        assert partner.copy().active is True

    def test_the_children_are_duplicated_under_the_new_parent(self):
        """≙ la rama ``one2many`` de ``copy_data`` (``odoo19c: :5450-5455``).

        Allá el hijo se duplica *"using the wrong (old) parent, but then is
        reassigned to the correct one"*. Aquí el paso corre después del alta,
        porque Django exige la fila del padre antes de colgarle un hijo.
        """
        padre = ResPartner.objects.create(name='Padre', is_company=True)
        ResPartner.objects.create(name='Hijo uno', parent=padre)
        ResPartner.objects.create(name='Hijo dos', parent=padre)
        copia = padre.copy()
        assert copia.children.count() == 2

    def test_the_original_keeps_its_children(self):
        """El otro lado: duplicar no mueve a los hijos, los replica."""
        padre = ResPartner.objects.create(name='Padre', is_company=True)
        ResPartner.objects.create(name='Hijo', parent=padre)
        padre.copy()
        assert padre.children.count() == 1

    def test_a_child_is_not_visited_twice(self):
        """El ``seen`` viaja del padre a los hijos, como el contexto allá."""
        padre = ResPartner.objects.create(name='Padre', is_company=True)
        ResPartner.objects.create(name='Hijo', parent=padre)
        copia = padre.copy()
        assert copia.children.count() == 1


@pytest.mark.django_db
class TestCopyTranslations:
    """BLOQUEADO por ``translate`` — no hay traducciones que copiar.

    El método existe con la firma de la fuente para que :meth:`copy` lo llame
    donde ella lo llama; su cuerpo se escribe cuando #333 construya el
    almacenamiento por idioma.
    """

    def test_it_is_declared_with_the_source_signature(self):
        partner = ResPartner.objects.create(name='Original')
        assert partner.copy_translations(partner, excluded=()) is None

    def test_the_three_symbols_it_would_need_do_not_exist(self):
        """El bloqueo se mide, no se afirma.

        Es la condición de cierre de la tarea #333: cuando estos tres existan,
        el cuerpo se puede escribir.
        """
        partner = ResPartner.objects.create(name='Original')
        for symbol in ('_get_stored_translations', 'update_field_translations',
                       'get_translation_dictionary'):
            assert not hasattr(partner, symbol)


@pytest.mark.django_db
class TestOverridesReachSuper:
    """Los overrides que existían ya pueden llamar a ``super()``."""

    def test_res_partner_adopts_the_mixin(self):
        assert issubclass(ResPartner, CopyMixin)

    def test_ir_model_data_adopts_the_mixin(self):
        assert issubclass(IrModelData, CopyMixin)

    def test_res_config_adopts_the_mixin(self):
        assert issubclass(ResConfig, CopyMixin)

    def test_ir_model_data_gets_a_fresh_name(self):
        """El identificador externo es único por ``(module, name)``.

        Una copia con el mismo nombre chocaría con la restricción.
        """
        entry = IrModelData.objects.create(
            module='base', name='control_de_copia',
            model='base.ResPartner', res_id=1)
        assert entry.copy_data()['name'].startswith('control_de_copia_')
        assert entry.copy_data()['name'] != 'control_de_copia'

    def test_ir_model_data_no_longer_lists_its_fields_by_hand(self):
        """El cuerpo copiaba cuatro campos a mano por no tener base.

        Qué haría fallar al caso: volver a la lista escrita a mano. Un campo
        que no estuviera en ella no viajaría, y nada lo delataría — que es
        justo el modo en que esa lista envejecía sola.
        """
        entry = IrModelData.objects.create(
            module='base', name='control_de_campos',
            model='base.ResPartner', res_id=7, noupdate=True)
        values = entry.copy_data()
        assert values['module'] == 'base'
        assert values['model'] == 'base.ResPartner'
        assert values['res_id'] == 7
        assert values['noupdate'] is True
