#!/usr/bin/env python3
"""Mide si ``.id`` sobre una instancia construida SIN ``Model.__init__`` consulta.

La referencia construye el recordset con ``self.__class__(self.env, ids, ids)``
(``odoo19c: odoo/orm/models.py``, ``BaseModel.browse``). Django ocupa
``__init__`` posicionalmente (``django/db/models/base.py:604`` → ``new =
cls(*values)``), asi que las dos firmas no pueden coexistir y el puerto instala
la tripleta por otra via. Este banco mide QUE PASA con ``.id`` en cada via.

No emite veredicto: emite el material.
"""
import argparse
import os
import pathlib
import sys

MARKER = pathlib.Path('scripts') / 'reference_roots.py'


def consumer_root():
    """La raiz del repo que aloja el ORM: declarada, o por marcador."""
    declared = os.environ.get('THYROX_CONSUMER')
    if declared:
        return pathlib.Path(declared)
    here = pathlib.Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / MARKER).is_file():
            return candidate
    raise SystemExit(
        f'ERROR - no se halla {MARKER} subiendo desde {here}. Declara '
        'THYROX_CONSUMER con la raiz del repo. NO se emite conteo: un 0 '
        'aqui seria un verde falso.')


ROOT = consumer_root()
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')

import django  # noqa: E402

django.setup()

from django.db import connection, models as dj  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402


class IdProbe(dj.Model):
    """Un modelo sin tabla: sólo interesa el descriptor de ``id``."""

    label = dj.CharField(max_length=32, default='')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_id_probe'


def report(title, build):
    print(f'--- {title}')
    try:
        obj = build()
    except Exception as exc:                      # noqa: BLE001
        print(f'    construccion: {type(exc).__name__}: {exc}')
        return
    print(f'    tiene _state : {hasattr(obj, "_state")}')
    print(f'    __dict__     : {sorted(obj.__dict__)}')
    with CaptureQueriesContext(connection) as capturadas:
        try:
            valor = obj.id
            resultado = f'id = {valor!r}'
        except Exception as exc:                  # noqa: BLE001
            resultado = f'{type(exc).__name__}: {exc}'
    print(f'    .id          : {resultado}')
    print(f'    consultas    : {len(capturadas)}')


def blank():
    """``object.__new__`` puro: ni ``__init__`` ni ``_state``."""
    return object.__new__(IdProbe)


def with_state():
    """``object.__new__`` mas el ``_state`` que Django instala en ``__init__``."""
    obj = object.__new__(IdProbe)
    obj._state = dj.base.ModelState()
    return obj


def with_id_in_dict():
    """Igual, con ``id`` ya sembrado en ``__dict__`` (el singleton)."""
    obj = with_state()
    obj.__dict__['id'] = 7
    return obj


def via_init():
    """La via de Django, para tener el control positivo."""
    return IdProbe(id=7)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(f'consumidor    : {ROOT}')
    print(f'descriptor id : {type(IdProbe.__dict__.get("id")).__name__}')
    report('object.__new__ pelado', blank)
    report('object.__new__ + _state', with_state)
    report('object.__new__ + _state + __dict__["id"]', with_id_in_dict)
    report('IdProbe(id=7) — control positivo', via_init)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
