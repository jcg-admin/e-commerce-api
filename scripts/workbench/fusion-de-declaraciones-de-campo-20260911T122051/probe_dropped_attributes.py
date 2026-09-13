#!/usr/bin/env python3
"""Qué atributos del vocabulario de la fuente sobreviven a la declaración.

Mide el ANCHO del hueco 1: ``annotate_related`` sale temprano cuando la
declaración no trae ``compute=`` ni ``related=``, así que todo lo que
``_declared_source_vocabulary`` sacó de ``kwargs`` se pierde. Esta sonda
declara un campo por atributo y lee el valor que quedó en el campo.

Se corre con:

    PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing \
        uv run python scripts/workbench/<...>/probe_dropped_attributes.py
"""
import django

django.setup()

import fields  # noqa: E402


def _inv(records):
    """Invocable de relleno: la sonda mide la declaración, no la llamada."""


CASES = [
    ('readonly=True', dict(readonly=True), 'readonly'),
    ('copy=False', dict(copy=False), 'copy'),
    ('compute_sudo=True', dict(compute_sudo=True), 'compute_sudo'),
    ('store=False', dict(store=False), 'store'),
    ('precompute=True', dict(precompute=True), 'precompute'),
    ('inverse=_inv', dict(inverse='_inv'), 'inverse'),
    ('recursive=True', dict(recursive=True), 'recursive'),
]

print(f'{"declarado":22} {"clase resultante":14} {"valor que quedó"}')
for label, kwargs, attribute in CASES:
    field = fields.Char(**kwargs)
    got = getattr(field, attribute, '<sin atributo>')
    print(f'{label:22} {type(field).__name__:14} {attribute}={got!r}')
