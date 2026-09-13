"""Tests — los endpoints de respaldo (UC-ADM-05).

  GET  /api/v2/admin/backups/                  ``AdminBackupListView`` — historial
  POST /api/v2/admin/backups/                  ``AdminBackupListView`` — disparar ahora
  GET  /api/v2/admin/backups/download/<ruta>/  ``BackupDownloadView`` — descargar

**Un solo mecanismo (DEC-AB-01, :ref:`h-api-768`).** El POST ya no implementa
un respaldo propio: llama a ``DbBackup.action_run_cron()``, que dispara el
mismo ``ir.cron`` que corre el planificador, vía
``IrCron.method_direct_trigger()``. Lo que estos casos verifican es
exactamente eso — que el disparo **entra por el cron** y que la fila que sale
tiene los cuatro campos de la fuente, no una fila huérfana sin archivo.

Los casos que antes probaban ``_run_backup`` —el ``subprocess`` a
``backup_postgres.sh`` en un hilo— desaparecen con él. Su contenido de valor
(la fila de fallo y la alerta por correo) **no** se pierde: se mudó a
``schedule_backup``, donde sirve a los dos caminos, y se prueba en
``test_db_backup.py``.
"""
import os
from unittest import mock

import pytest

from addons.auto_backup.models import DbBackup, DbBackupDetails
from addons.auto_backup.models import db_backup as db_backup_model
from addons.base.models import SystemParameter
from orm.registry import clear_cache
from addons.base.models.ir_cron import IrCron

pytestmark = pytest.mark.integration

LIST_URL = '/api/v2/admin/backups/'
TRIGGER_URL = '/api/v2/admin/backups/'
DOWNLOAD_URL = '/api/v2/admin/backups/download'


def download_url(absolute_path):
    """La URL de descarga de una ruta absoluta del servidor.

    La vista reconstruye la ruta con ``'/' + file_path.lstrip('/')``, así que
    el segmento que viaja es la ruta sin su ``/`` inicial. La barra final la
    exige el ``path()`` de ``admin_urls.py``.
    """
    return '%s/%s/' % (DOWNLOAD_URL, str(absolute_path).lstrip('/'))


@pytest.fixture(autouse=True)
def _clear_param_cache():
    """``backup.alert_email`` vive en SystemParameter (L2, H-API-CFG-01); su
    caché es módulo-nivel (per-proceso), no per-transacción — se limpia entre
    tests para que el rollback de la transacción de pytest-django se refleje
    también en las lecturas cacheadas."""
    clear_cache('stable')
    yield
    clear_cache('stable')


@pytest.fixture
def config(db, tmp_path):
    """Una configuración de respaldo apuntando a un directorio temporal."""
    return DbBackup.objects.create(name='kaupamex_core_qa', folder=str(tmp_path))


class TestBackupEndpoints:

    # --- permisos ---
    def test_list_anon_401(self, api_client, db):
        assert api_client.get(LIST_URL).status_code == 401

    def test_list_buyer_403(self, auth_client, db):
        assert auth_client.get(LIST_URL).status_code == 403

    def test_trigger_anon_401(self, api_client, db):
        assert api_client.post(TRIGGER_URL).status_code == 401

    def test_trigger_buyer_403(self, auth_client, db):
        assert auth_client.post(TRIGGER_URL).status_code == 403

    # --- listado / estado ---
    def test_admin_lists_the_history(self, admin_client, db):
        DbBackupDetails.objects.create(
            type=DbBackupDetails.TYPE_AUTO, status=DbBackupDetails.STATUS_OK,
        )
        r = admin_client.get(LIST_URL)
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        assert len(rows) == 1
        assert rows[0]['status'] == DbBackupDetails.STATUS_OK


class TestTriggerRunsTheCron:
    """El POST entra por el cron — la propiedad que DEC-AB-01 decide."""

    def test_trigger_produces_a_row_with_the_four_source_fields(
            self, admin_client, config):
        """La fila del disparo a mano ya no es huérfana.

        El camino viejo creaba ``DbBackupDetails(type=MANUAL)`` y nada más:
        sin ``name``, sin ``file_path``, sin ``url`` y sin ``db_backup_id``.
        Esa fila era indescargable por ``BackupDownloadView`` (que exige que
        la ruta caiga bajo una ``DbBackup.folder``) e invisible para
        ``_remove_old_local_backups``. Ahora la produce ``schedule_backup``,
        así que trae los cuatro campos de la fuente.

        ``file_path`` se verifica **en la fila**, no en la respuesta: el
        serializer no lo expone a propósito —es una ruta absoluta del
        servidor y el cliente no la necesita— y esa decisión es anterior a
        DEC-AB-01. Lo que el cliente recibe para descargar es ``url``.
        """
        with mock.patch.object(DbBackup, '_take_dump') as dump:
            dump.side_effect = lambda db_name, stream, model, backup_format='zip': (
                stream.write(b'dump'))
            r = admin_client.post(TRIGGER_URL)

        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        row = rows[0]
        assert row['type'] == DbBackupDetails.TYPE_MANUAL
        assert row['status'] == DbBackupDetails.STATUS_OK
        # Tres de los cuatro campos de la fuente, que el camino viejo dejaba
        # vacíos; el cuarto va abajo, contra la fila.
        assert row['name'].endswith('.zip')
        assert row['url'].startswith('/dbbackup/download/')
        assert row['db_backup_id'] == config.pk

        detail = DbBackupDetails.objects.get()
        assert detail.file_path.startswith(config.folder)
        assert os.path.isfile(detail.file_path)

    def test_the_scheduled_run_stamps_auto(self, config):
        """Sin la clave de contexto, la misma corrida sale ``AUTO``.

        Es la mitad que hace útil el discriminador: ``type`` distingue quién
        disparó, y sólo ``action_run_cron`` pone ``CONTEXT_MANUAL``.
        """
        with mock.patch.object(DbBackup, '_take_dump') as dump:
            dump.side_effect = lambda db_name, stream, model, backup_format='zip': (
                stream.write(b'dump'))
            DbBackup.schedule_backup()

        assert DbBackupDetails.objects.get().type == DbBackupDetails.TYPE_AUTO

    def test_trigger_when_the_job_is_taken_409(self, admin_client, config):
        """Un job ya tomado por otro worker sale 409, no 500.

        ``method_direct_trigger`` levanta ``UserError`` cuando
        ``_acquire_one_job`` devuelve ``None`` — que es lo que el
        ``FOR NO KEY UPDATE SKIP LOCKED`` produce cuando otro proceso tiene
        la fila. Se simula devolviendo ``None``: montar dos conexiones que
        compitan por el lock mediría el motor, no la traducción a 409, que
        es lo que este endpoint decide.
        """
        with mock.patch.object(IrCron, '_acquire_one_job', return_value=None):
            r = admin_client.post(TRIGGER_URL)
        assert r.status_code == 409
        assert r.json()['codigo_error'] == 'BACKUP_IN_PROGRESS'

    def test_trigger_without_a_seeded_cron_503(self, admin_client, config):
        """Sin el cron sembrado no hay nada que disparar, y se dice."""
        IrCron.objects.filter(
            ir_actions_server__model_name='auto_backup.DbBackup',
            ir_actions_server__method_name='schedule_backup',
        ).delete()
        r = admin_client.post(TRIGGER_URL)
        assert r.status_code == 503
        assert r.json()['codigo_error'] == 'BACKUP_CRON_NOT_SEEDED'


class TestBackupFailAlert:
    """La alerta por correo, aislada (``notify_backup_failed``).

    Se mudó de ``controllers/main.py`` al modelo: allá sólo cubría el camino
    bajo demanda, y con un solo mecanismo el aviso tiene que servir a los
    dos. La fuente no alerta en ninguno — su ``except`` sólo escribe dos
    ``_logger.warning`` (``:141-146``).

    ``BACKUP_ALERT_EMAIL`` migró a ``SystemParameter`` L2
    (``backup.alert_email``, H-API-CFG-01): ya no es un setting de Django —
    se sobreescribe con ``set_param``, no con el fixture ``settings``.
    """

    def test_notifies_the_configured_address(self, db, mailoutbox):
        SystemParameter.set_param('backup.alert_email', 'ops@kaupamex.com')
        db_backup_model.notify_backup_failed('kaupamex_core_qa', 'boom')
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ['ops@kaupamex.com']
        assert 'kaupamex_core_qa' in mailoutbox[0].subject

    def test_without_a_recipient_it_neither_sends_nor_breaks(self, db, mailoutbox):
        # 'backup.alert_email' está en _DEFAULT_PARAMETERS -> protegida
        # contra borrado (H-CFG-IMPL-01); no se puede simular "ausente" con
        # delete. Un valor vacío activa el quirk ``or default`` (H-CFG-IMPL-03)
        # y get_param cae al default explícito ('') que pasa el modelo.
        SystemParameter.set_param('backup.alert_email', '')
        db_backup_model.notify_backup_failed('kaupamex_core_qa', 'boom')
        assert len(mailoutbox) == 0

    def test_uses_the_value_seeded_by_the_migration(self, db, mailoutbox):
        # Sin set_param explícito: debe leer el valor sembrado por la
        # migración de datos, no un default local ni el viejo
        # ``settings.BACKUP_ALERT_EMAIL``. Reseed idempotente (== la
        # migración) para no depender de que un test transaction=True previo
        # no haya hecho flush de la fila sembrada.
        SystemParameter.seed()
        db_backup_model.notify_backup_failed('kaupamex_core_qa', 'boom')
        assert len(mailoutbox) == 1
        seeded = SystemParameter.get_param('backup.alert_email')
        assert seeded is not None
        assert mailoutbox[0].to == [seeded]


class TestBackupDownloadConfinement:
    """El confinamiento de ``BackupDownloadView`` — :ref:`h-api-766`, tarea #639.

    **La fuente sirve cualquier archivo del disco.** Verbatim
    (``odoo18c: app_auto_backup/controllers/main.py:16-22``):

    .. code-block:: python

       @http.route("/dbbackup/download/<path:file_path>", type="http", auth="user")
       def download_backupfile(self, file_path, **kw):
           if not request.env.user.has_group('base.group_system'):
               raise UserError(_('File not found for user.'))
           if os.path.exists(file_path):
               with open(file_path, 'rb') as file:
                   file_content = file.read()

    Un solo ``os.path.exists`` sobre la ruta que el cliente escriba: un usuario
    del sistema puede pedir ``/etc/shadow`` por esa ruta. La divergencia —la
    ruta resuelta debe caer bajo alguna ``DbBackup.folder``— quedó declarada en
    el docstring de la vista y **verificada por lectura**, sin caso propio.
    Estos son esos casos.

    **Cada negativo apunta a un archivo que EXISTE.** Es la condición que hace
    que el 404 mida el confinamiento: contra un archivo ausente, el mismo 404
    lo produciría ``os.path.isfile`` y el caso pasaría por la razón
    equivocada — la ceguera que ``metrica-decide-la-conclusion.md`` describe.
    Por eso cada caso afirma primero ``os.path.isfile(...)``.
    """

    @pytest.fixture
    def tree(self, db, tmp_path):
        """Un árbol con la carpeta configurada y un archivo fuera de ella.

        ``secret.txt`` es hermano de la carpeta, no descendiente: es el
        objetivo legítimo de las tres formas de escape.
        """
        folder = tmp_path / 'backups'
        folder.mkdir()
        dump = folder / '2026_08_20_00_00_00_kaupamex_core_qa.zip'
        dump.write_bytes(b'DUMP')
        secret = tmp_path / 'secret.txt'
        secret.write_text('s3cr3t')
        config = DbBackup.objects.create(
            name='kaupamex_core_qa', folder=str(folder))
        return {'config': config, 'folder': folder,
                'dump': dump, 'secret': secret, 'root': tmp_path}

    # --- permisos: capacidad, no grupo (la primera divergencia) ---
    def test_download_anon_401(self, api_client, tree):
        assert api_client.get(download_url(tree['dump'])).status_code == 401

    def test_download_buyer_403(self, auth_client, tree):
        """Sin ``backups.edit`` no se descarga, aunque el archivo exista.

        La fuente gatea con ``has_group('base.group_system')``; aquí el
        invariante es ``HasCapability`` fail-closed (DEC-11).
        """
        assert os.path.isfile(tree['dump'])
        assert auth_client.get(download_url(tree['dump'])).status_code == 403

    # --- control positivo: lo que SÍ debe servirse ---
    def test_a_file_inside_the_configured_folder_downloads(
            self, admin_client, tree):
        """El caso que las tres negativas necesitan para no ser vacuas.

        Sin él, una vista que devolviera 404 a todo pasaría los tres casos de
        escape y el conjunto no mediría nada.
        """
        r = admin_client.get(download_url(tree['dump']))
        assert r.status_code == 200
        assert b''.join(r.streaming_content) == b'DUMP'
        assert r['Content-Type'] == 'application/octet-stream'
        assert tree['dump'].name in r['Content-Disposition']

    # --- las tres formas de escape que #639 enumera ---
    def test_a_path_outside_every_configured_folder_is_404(
            self, admin_client, tree):
        """Forma 1: ruta absoluta ajena. Es el ``/etc/shadow`` de la fuente."""
        assert os.path.isfile('/etc/passwd')
        r = admin_client.get(download_url('/etc/passwd'))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'BACKUP_FILE_NOT_FOUND'

    def test_dot_dot_escaping_the_configured_folder_is_404(
            self, admin_client, tree):
        """Forma 2: ``..`` que sale de una carpeta que sí está configurada.

        Lo cierra ``os.path.realpath``, y el orden importa: el confinamiento
        se comprueba **sobre la ruta ya resuelta**. Comprobarlo antes dejaría
        pasar la cadena literal, que empieza por la carpeta buena.
        """
        assert os.path.isfile(tree['secret'])
        escape = '%s/../secret.txt' % tree['folder']
        assert os.path.realpath(escape) == str(tree['secret'])
        r = admin_client.get(download_url(escape))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'BACKUP_FILE_NOT_FOUND'

    def test_a_symlink_pointing_outside_is_404(self, admin_client, tree):
        """Forma 3: enlace simbólico **dentro** de la carpeta configurada.

        Es la forma que un confinamiento por prefijo de cadena no ve: el
        archivo pedido está dentro de la carpeta y su destino no. Sólo
        resolver antes de comparar lo detiene.
        """
        link = tree['folder'] / 'inocente.zip'
        os.symlink(str(tree['secret']), str(link))
        assert os.path.isfile(link)          # el enlace resuelve a un archivo real
        r = admin_client.get(download_url(link))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'BACKUP_FILE_NOT_FOUND'

    # --- la frontera que el `+ os.sep` del guard defiende ---
    def test_a_sibling_folder_sharing_the_prefix_is_404(
            self, admin_client, tree):
        """``/…/backups-evil/`` empieza por ``/…/backups`` y no está dentro.

        El guard compara ``resolved == folder or
        resolved.startswith(folder + os.sep)``. Sin el ``os.sep`` el prefijo
        desnudo aceptaría este archivo — medido:
        ``'/tmp/x/backups-evil/f.zip'.startswith('/tmp/x/backups')`` es
        ``True``, y con el separador es ``False``.
        """
        evil = tree['root'] / 'backups-evil'
        evil.mkdir()
        planted = evil / 'f.zip'
        planted.write_bytes(b'NOPE')
        assert os.path.isfile(planted)
        assert str(planted).startswith(str(tree['folder']))
        r = admin_client.get(download_url(planted))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'BACKUP_FILE_NOT_FOUND'

    # --- fail-closed cuando no hay ninguna carpeta configurada ---
    def test_without_any_configured_folder_nothing_downloads(
            self, admin_client, tree):
        """Sin configuraciones, ``folders`` queda vacío y ``any([])`` es False.

        Es la dirección correcta del fallo: un confinamiento que se abriera al
        quedarse sin referencia serviría todo el disco justo cuando nadie ha
        declarado qué se puede servir.
        """
        DbBackup.objects.all().delete()
        assert os.path.isfile(tree['dump'])
        r = admin_client.get(download_url(tree['dump']))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'BACKUP_FILE_NOT_FOUND'

    def test_a_folder_left_empty_does_not_confine_anything(
            self, admin_client, tree):
        """Una ``DbBackup.folder`` vacía se salta, no se lee como ``''``.

        El guard filtra con ``if folder``. Sin ese filtro,
        ``os.path.realpath('')`` devuelve el **directorio de trabajo**, que
        confinaría a un árbol que nadie configuró.
        """
        DbBackup.objects.all().delete()
        DbBackup.objects.create(name='sin-carpeta', folder='')
        r = admin_client.get(download_url(tree['dump']))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'BACKUP_FILE_NOT_FOUND'
