#!/usr/bin/env python3
"""Mide las dos piezas que la cabecera del puerto necesita decidir.

1. ``__slots__`` verbatim sobre una base abstracta de Django: ¿lo admite
   ``ModelBase``, y sigue el modelo concreto teniendo ``__dict__``?
2. ``class_prepared`` como via para instalar el ``Id.__get__`` de la
   referencia (``odoo19c: odoo/orm/fields_misc.py:102-114``) DESPUES de que
   ``ModelBase`` haya puesto su ``DeferredAttribute``.
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
from django.db.models.signals import class_prepared  # noqa: E402
from django.dispatch import receiver  # noqa: E402


class IdFromIds:
    """Los tres regimenes de ``Id.__get__``, con relevo al descriptor original."""

    def __init__(self, fallback):
        self.fallback = fallback

    def __get__(self, record, owner=None):
        if record is None:
            return self
        ids = getattr(record, '_ids', None)
        if ids is None:
            return self.fallback.__get__(record, owner)
        size = len(ids)
        if size == 0:
            return False
        if size == 1:
            return ids[0]
        # El mensaje NO interpola el registro con !r: el ``__repr__`` de un
        # modelo de Django lee ``self.pk``, que vuelve a este descriptor y
        # recursa. La referencia no lo sufre porque su ``__repr__`` es
        # ``f'{self._name}{self._ids!r}'`` y no toca ``id``.
        raise ValueError(f'Expected singleton: ids={ids!r}')


@receiver(class_prepared)
def _install(sender, **_ignored):
    if not issubclass(sender, AbstractBase):
        return
    actual = sender.__dict__.get('id')
    if actual is not None and not isinstance(actual, IdFromIds):
        setattr(sender, 'id', IdFromIds(actual))


class AbstractBase(dj.Model):
    __slots__ = ['env', '_ids', '_prefetch_ids']

    class Meta:
        abstract = True


class Sujeto(AbstractBase):
    label = dj.CharField(max_length=32, default='')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_abstract_base_probe'


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(f'AbstractBase.__slots__   : {getattr(AbstractBase, "__slots__", "(ausente)")}')
    print(f'descriptor id en Sujeto  : {type(Sujeto.__dict__.get("id")).__name__}')
    obj = object.__new__(Sujeto)
    obj._state = dj.base.ModelState()
    print(f'instancia tiene __dict__ : {hasattr(obj, "__dict__")}')
    for ids in ((), (7,), (7, 18)):
        obj._ids = ids
        try:
            resultado = repr(obj.id)
        except Exception as exc:                  # noqa: BLE001
            resultado = f'{type(exc).__name__}: {exc}'
        print(f'  _ids={ids!r:12} -> .id = {resultado}')
    fila = Sujeto(id=99, label='x')
    print(f'  fila de Django (sin _ids) -> .id = {fila.id!r}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
