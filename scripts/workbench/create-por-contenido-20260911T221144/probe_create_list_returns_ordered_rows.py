"""Sonda: ``create`` por contenido — lista → filas en orden, dict → singleton.

Mide, por contenido y no por presencia, el porte de ``BaseModel.create``
(``odoo19c: odoo/orm/models.py:4611-4770``) sobre tres adopters de
``DefaultGetMixin``: ``ResPartner`` (sin ``_inherits``), ``ResUsers``
(``_inherits`` → ``res.partner``) e ``IrCron`` (``_inherits`` →
``ir.actions.server``, y hasta hoy sin ``RecordLoaderMixin``).

Claves esperadas (INVENTORY):

- ``django``: ``objects.create`` como INSERT RETURNING (trae hecho).
- ``postgresql``: ids crecientes en el orden de inserción (trae hecho).
- ``cpython``: ``collections.defaultdict`` / ``contextlib.ExitStack`` (trae hecho).
"""
import django
django.setup()

from django.db import transaction

from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from addons.base.models.ir_cron import IrCron
from orm.environments import context_scope, sudo

verdicts = []


def check(label, got, expected):
    ok = got == expected
    verdicts.append(ok)
    print(f"{'OK ' if ok else 'FAIL'} {label}: got={got!r} expected={expected!r}")


with transaction.atomic():
    sid = transaction.savepoint()
    try:
        ResPartner.create([{'name': 'sin usuario'}])
        check('sin usuario ni elevación → denegado', 'sin error', 'PermissionDenied')
    except Exception as exc:  # noqa: BLE001
        check('sin usuario ni elevación → denegado', type(exc).__name__, 'PermissionDenied')
    transaction.savepoint_rollback(sid)
    sid = transaction.savepoint()
    elevated = sudo(); elevated.__enter__()
    rows = ResPartner.create([{'name': 'Sonda A'}, {'name': 'Sonda B'}, {'name': 'Sonda C'}])
    names = [r.name for r in rows]
    check('lista → tres filas en orden', names, ['Sonda A', 'Sonda B', 'Sonda C'])
    pks = [r.pk for r in rows]
    check('ids crecientes', pks == sorted(pks) and len(set(pks)) == 3, True)

    single = ResPartner.create({'name': 'Sonda D'})
    check('dict → singleton (len 1)', len(single), 1)
    d, = single
    check('singleton desempaquetado lee su campo', d.name, 'Sonda D')

    with context_scope(default_comment='del contexto'):
        e, = ResPartner.create([{'name': 'Sonda E'}])
    e.refresh_from_db()
    check('default_* del contexto aterriza', e.comment, 'del contexto')

    try:
        ResPartner.create([{'name': 'X', 'nonexistent_field': 1}])
        check('campo desconocido → ValueError', 'sin error', 'ValueError')
    except ValueError as exc:
        check('campo desconocido → ValueError', str(exc), "Invalid field 'nonexistent_field' in 'res.partner'")

    try:
        ResPartner.create(name='kwargs')
        check('kwargs rechazados', 'sin error', 'TypeError')
    except TypeError as exc:
        check('kwargs rechazados', 'TypeError', 'TypeError')

    empty = ResPartner.create([])
    check('lista vacía → recordset vacío', len(empty), 0)

    # _inherits: el padre se crea primero y su id cae en la FK
    u, = ResUsers.create([{'login': 'sonda-351@ejemplo.mx', 'name': 'Usuario Sonda', 'password': 'x'}])
    check('_inherits: FK al padre puesta', u.partner_id is not None, True)
    check('_inherits: el nombre vive en el padre', u.partner.name, 'Usuario Sonda')

    # IrCron: ahora con RecordLoaderMixin; _inherits → ir.actions.server
    try:
        c, = IrCron.create([{'name': 'Cron sonda', 'model_name': 'res.partner', 'code': 'x',
                             'interval_number': 1, 'interval_type': 'days'}])
        check('IrCron.create por contenido', c.name, 'Cron sonda')
    except Exception as exc:  # noqa: BLE001 — la sonda publica el error, no lo traga
        check('IrCron.create por contenido', f'{type(exc).__name__}: {exc}'[:200], 'sin error')
    elevated.__exit__(None, None, None)
    transaction.savepoint_rollback(sid)

print('VEREDICTO', 'OK' if all(verdicts) else 'FALLA', f'{sum(verdicts)} de {len(verdicts)}')
