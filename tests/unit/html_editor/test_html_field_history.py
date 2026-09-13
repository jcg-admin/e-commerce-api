"""``models/html_field_history_mixin`` — ``create``, ``write`` y el historial.

Los dos símbolos que la fuente reparte en ``create`` (``odoo19c:
addons/html_editor/models/html_field_history_mixin.py:42-46``) y ``write``
(``:48-108``) existen aquí con su nombre y delegan en ``save``, que es el
único punto de escritura de este ORM. Estos casos miden **la conducta**, no la
presencia del atributo: qué descarta ``create``, qué revisión escribe
``write`` y qué guarda impide versionar un campo que no es HTML.

El mixin es abstracto y ningún modelo del árbol lo hereda todavía, así que los
casos declaran su propio modelo concreto — el mismo recurso que usa la suite
de la fuente (``odoo19c: addons/html_editor/tests/`` declara sus modelos de
prueba en ``models/test_models.py``).
"""
import fields
import models
import pytest
from addons.base.models import TimeStampedModel
from django.core.exceptions import ValidationError
from django.db import connection
from orm.environments import sudo

from addons.html_editor.models.html_field_history_mixin import (
    HtmlFieldHistoryMixin,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class HistoryProbe(HtmlFieldHistoryMixin, TimeStampedModel):
    """Modelo concreto de prueba con un campo HTML versionado."""

    _name = 'html_editor.history.probe'
    _description = 'Html Editor History Probe'

    body = fields.Html(blank=True, default='')
    label = fields.Char(max_length=64, blank=True, default='')

    class Meta:
        app_label = 'html_editor'
        db_table = 'html_editor_history_probe'
        verbose_name = 'Html Editor History Probe'
        # ``managed = False`` deja el modelo FUERA de ``can_migrate``, y con
        # eso fuera de ``serialize_db_to_string``, que pytest-django ejecuta
        # al montar la base: sin esta línea el arranque de la sesión hace un
        # ``SELECT`` sobre una tabla que todavía no existe y **todos** los
        # casos de la sesión mueren en setup. Medido 2026-09-02.
        managed = False

    @classmethod
    def _get_versioned_fields(cls):
        return ['body']


class UnversionableProbe(HtmlFieldHistoryMixin, TimeStampedModel):
    """El campo declarado como versionado **no** es ``fields.Html``."""

    _name = 'html_editor.history.probe.raw'
    _description = 'Html Editor History Probe Raw'

    body = fields.Text(blank=True, default='')

    class Meta:
        app_label = 'html_editor'
        db_table = 'html_editor_history_probe_raw'
        verbose_name = 'Html Editor History Probe Raw'
        managed = False

    @classmethod
    def _get_versioned_fields(cls):
        return ['body']


@pytest.fixture(scope='session')
def tables(django_db_setup, django_db_blocker):
    """Crea las dos tablas de prueba una vez por sesión.

    El mixin es abstracto y no tiene migración, así que las tablas se crean
    con el ``schema_editor``. La creación va **fuera** de la transacción de
    cada caso —de ahí el ámbito de sesión y el ``django_db_blocker``—: dentro,
    el ``rollback`` de pytest-django se llevaría el DDL por delante y el
    segundo caso no encontraría la tabla.
    """
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in (HistoryProbe, UnversionableProbe):
                editor.create_model(model)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in (HistoryProbe, UnversionableProbe):
                editor.delete_model(model)


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


class TestCreateDropsTheIncomingHistory:
    """≙ ``create`` (``:42-46``): nadie siembra un historial al crear."""

    def test_create_is_a_symbol_of_this_model(self, tables):
        assert callable(HistoryProbe.create)

    def test_the_history_that_arrives_from_outside_is_discarded(self, tables):
        record, = HistoryProbe.create([{
            'body': '<p>a</p>',
            'html_field_history': {'body': [{'patch': 'FALSO',
                                             'revision_id': 99}]}}])
        record.refresh_from_db()
        assert record.html_field_history is None

    def test_the_django_path_discards_it_too(self, tables):
        # ``objects.create`` no pasa por :meth:`create`; pasa por ``save``,
        # que repite el descarte. Sin esa repetición el camino de Django
        # dejaría entrar el historial falso.
        record = HistoryProbe.objects.create(
            body='<p>a</p>',
            html_field_history={'body': [{'patch': 'FALSO'}]})
        record.refresh_from_db()
        assert record.html_field_history is None


class TestWriteGeneratesTheRevision:
    """≙ ``write`` (``:48-108``)."""

    def test_write_is_a_symbol_of_this_model(self, tables):
        assert callable(HistoryProbe.write)

    def test_changing_the_versioned_field_inserts_a_revision(self, tables):
        record, = HistoryProbe.create([{'body': '<p>uno</p>'}])
        record.write(body='<p>dos</p>')
        record.refresh_from_db()
        assert record.body == '<p>dos</p>'
        revisions = record.html_field_history['body']
        assert len(revisions) == 1
        assert revisions[0]['revision_id'] == 1
        assert revisions[0]['patch']

    def test_the_revision_id_grows_by_one_on_each_change(self, tables):
        record, = HistoryProbe.create([{'body': '<p>uno</p>'}])
        record.write(body='<p>dos</p>')
        record.write(body='<p>tres</p>')
        record.refresh_from_db()
        # La fuente inserta en la CABEZA: la más nueva es la primera.
        ids = [r['revision_id'] for r in record.html_field_history['body']]
        assert ids == [2, 1]

    def test_writing_the_same_content_adds_no_revision(self, tables):
        record, = HistoryProbe.create([{'body': '<p>uno</p>'}])
        record.write(body='<p>uno</p>')
        record.refresh_from_db()
        assert not (record.html_field_history or {}).get('body')

    def test_writing_a_non_versioned_field_adds_no_revision(self, tables):
        record, = HistoryProbe.create([{'body': '<p>uno</p>'}])
        record.write(label='otra cosa')
        record.refresh_from_db()
        assert record.label == 'otra cosa'
        assert not (record.html_field_history or {}).get('body')

    def test_the_history_cannot_be_written_from_outside(self, tables):
        record, = HistoryProbe.create([{'body': '<p>uno</p>'}])
        record.write(body='<p>dos</p>',
                     html_field_history={'body': [{'patch': 'FALSO'}]})
        record.refresh_from_db()
        assert record.html_field_history['body'][0]['patch'] != 'FALSO'


class TestTheGuardOnTheVersionedFieldType:
    """≙ la guarda de ``field.sanitize`` — divergencia 3 del módulo.

    Está escrita para **poder fallar**: el campo existe y el registro existe,
    así que lo que rechaza es el tipo del campo y no la ausencia del objeto.
    """

    def test_versioning_a_non_html_field_is_refused(self, tables):
        record, = UnversionableProbe.create([{'body': 'uno'}])
        with pytest.raises(ValidationError):
            record.write(body='dos')


class TestTheRestoreRoundTrip:
    def test_the_content_comes_back_at_the_asked_revision(self, tables):
        record, = HistoryProbe.create([{'body': '<p>uno</p>'}])
        record.write(body='<p>dos</p>')
        record.refresh_from_db()
        restored = record.html_field_history_get_content_at_revision('body', 1)
        assert restored == '<p>uno</p>'

    def test_the_metadata_carries_no_patch(self, tables):
        record, = HistoryProbe.create([{'body': '<p>uno</p>'}])
        record.write(body='<p>dos</p>')
        record.refresh_from_db()
        for revision in record.html_field_history_metadata['body']:
            assert 'patch' not in revision
            assert 'revision_id' in revision


class TestTheSizeLimitIsTheOneOfTheSource:
    def test_the_class_attribute_is_verbatim(self, tables):
        assert HistoryProbe._html_field_history_size_limit == 300
