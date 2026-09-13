#!/usr/bin/env python3
"""Mide si el ``Id.__set__`` de la referencia se puede portar verbatim.

``odoo19c: odoo/orm/fields_misc.py:116-117`` declara::

    def __set__(self, record, value):
        raise TypeError("field 'id' cannot be assigned")

Declararlo convierte al descriptor en **descriptor de datos**, y un descriptor
de datos precede al ``__dict__`` de la instancia en la resolucion de atributo
de CPython. Django asigna ``id`` por ``setattr`` al construir una fila
(``django/db/models/base.py:604`` -> ``new = cls(*values)``, y ``Model.__init__``
hace ``_setattr(self, field.attname, val)``).

Esta sonda mide las dos mitades, no las supone: con ``__set__`` y sin el.
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


class GetterOnly:
    """Descriptor NO de datos: el ``__dict__`` de la instancia lo precede."""

    def __init__(self, fallback):
        self.fallback = fallback

    def __get__(self, record, owner=None):
        if record is None:
            return self
        ids = getattr(record, '_ids', None)
        if ids is None:
            return self.fallback.__get__(record, owner)
        return ids[0] if len(ids) == 1 else False


class GetterAndSetter(GetterOnly):
    """El mismo, mas el ``__set__`` verbatim de la referencia."""

    def __set__(self, record, value):
        raise TypeError("field 'id' cannot be assigned")


class Sujeto(dj.Model):
    label = dj.CharField(max_length=32, default='')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_id_setter_probe'


def build_row(descriptor_cls):
    """Instala el descriptor y construye una fila como lo hace Django."""
    original = Sujeto.__dict__['id']
    setattr(Sujeto, 'id', descriptor_cls(original))
    try:
        fila = Sujeto(id=99, label='x')
        return f'.id = {fila.id!r}'
    except Exception as exc:                      # noqa: BLE001
        return f'{type(exc).__name__}: {exc}'
    finally:
        setattr(Sujeto, 'id', original)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(f'descriptor original      : {type(Sujeto.__dict__["id"]).__name__}')
    print(f'solo __get__             : {build_row(GetterOnly)}')
    print(f'__get__ + __set__ (ref)  : {build_row(GetterAndSetter)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
