#!/usr/bin/env python3
"""Distingue «Django lo declara» de «``object`` lo trae para toda clase».

El cubo TRAE se decidio con ``hasattr(clase, nombre)``. Esa pregunta la
contesta que si CUALQUIER clase de Python para ``__eq__``, ``__ge__``,
``__hash__``, ``__repr__`` e ``__init__``: los hereda de ``object``. El
``hasattr`` mide el SIGNIFICANTE —el nombre resuelve— y se leyo como el
SIGNIFICADO —hay un cuerpo que hace el trabajo—.

Este guion pregunta otra cosa: en que clase del MRO se define el atributo, y si
esa clase es ``object``. ``object.__ge__`` devuelve ``NotImplemented``: no
ordena nada.
"""
import argparse
import json
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


def declaring_class(klass, name):
    """La clase del MRO que declara ``name``, o None si nadie lo declara."""
    for ancestor in klass.__mro__:
        if name in ancestor.__dict__:
            return ancestor
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--names', required=True)
    args = parser.parse_args()
    names = [n for n in args.names.split(',') if n]

    root = consumer_root()
    sys.path.insert(0, str(root / 'src'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    import django
    django.setup()
    from django.db import models as dj
    from django.db.models.query import QuerySet
    from django.db.models.manager import Manager
    from rest_framework import serializers

    carriers = [
        ('django.Model', dj.Model),
        ('django.QuerySet', QuerySet),
        ('django.Manager', Manager),
        ('drf.Serializer', serializers.Serializer),
        ('drf.ModelSerializer', serializers.ModelSerializer),
    ]
    report = {}
    for name in names:
        per_carrier = {}
        for label, klass in carriers:
            owner = declaring_class(klass, name)
            if owner is None:
                per_carrier[label] = 'AUSENTE'
            elif owner is object:
                per_carrier[label] = 'object (default del lenguaje)'
            else:
                per_carrier[label] = f'{owner.__module__}.{owner.__qualname__}'
        report[name] = per_carrier
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
