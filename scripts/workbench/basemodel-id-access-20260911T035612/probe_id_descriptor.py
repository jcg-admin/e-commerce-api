#!/usr/bin/env python3
"""Mide si un descriptor ``id`` declarado en la BASE sobrevive a ``ModelBase``.

``Id.__get__`` de la referencia (``odoo19c: odoo/orm/fields_misc.py:102-114``)
lee ``record._ids``: 0 -> ``False``, 1 -> ``ids[0]``, >1 -> ``ValueError``.
Django instala un ``DeferredAttribute`` para la clave primaria en CADA clase
concreta. Este banco mide cual de los dos gana.
"""
import argparse
import os
import pathlib
import sys

MARKER = pathlib.Path('scripts') / 'reference_roots.py'


def consumer_root():
    declared = os.environ.get('THYROX_CONSUMER')
    if declared:
        return pathlib.Path(declared)
    here = pathlib.Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / MARKER).is_file():
            return candidate
    raise SystemExit(f'ERROR - no se halla {MARKER} subiendo desde {here}.')


ROOT = consumer_root()
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')

import django  # noqa: E402

django.setup()

from django.db import models as dj  # noqa: E402


class IdFromIds:
    """Las tres regimenes de lectura de ``Id.__get__``, como descriptor."""

    def __get__(self, record, owner=None):
        if record is None:
            return self
        ids = record._ids
        size = len(ids)
        if size == 0:
            return False
        if size == 1:
            return ids[0]
        raise ValueError(f'Expected singleton: {record!r}')


class DescriptorBase:
    """Una base NO-Django que declara ``id``."""

    id = IdFromIds()


class Sujeto(DescriptorBase, dj.Model):
    label = dj.CharField(max_length=32, default='')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_id_descriptor_probe'


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    en_clase = Sujeto.__dict__.get('id')
    heredado = type(getattr(Sujeto, 'id', None)).__name__
    print(f'Sujeto.__dict__["id"] : {type(en_clase).__name__ if en_clase is not None else "(ausente)"}')
    print(f'getattr(Sujeto, "id") : {heredado}')
    print(f'MRO                   : {[c.__name__ for c in Sujeto.__mro__]}')
    obj = object.__new__(Sujeto)
    obj._state = dj.base.ModelState()
    for ids in ((), (7,), (7, 18)):
        obj._ids = ids
        try:
            resultado = repr(obj.id)
        except Exception as exc:                  # noqa: BLE001
            resultado = f'{type(exc).__name__}: {exc}'
        print(f'  _ids={ids!r:12} -> .id = {resultado}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
