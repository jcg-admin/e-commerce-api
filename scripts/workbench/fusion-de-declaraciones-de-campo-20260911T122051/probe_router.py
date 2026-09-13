"""Que tipo construye cada declaracion — MEDIDO en proceso, no inferido."""
import django
django.setup()

import fields
from orm.fields_nonstored import NonStored

casos = [
    ("fields.Char()",                            dict()),
    ("fields.Char(store=False)",                 dict(store=False)),
    ("fields.Char(inverse='_x')",                dict(inverse='_x')),
    ("fields.Char(recursive=True)",              dict(recursive=True)),
    ("fields.Char(inverse='_x', recursive=True)", dict(inverse='_x', recursive=True)),
    ("fields.Char(compute='_c')",                dict(compute='_c')),
    ("fields.Char(recursive=True, store=True)",  dict(recursive=True, store=True)),
    ("fields.Char(related='a.b')",               dict(related='a.b')),
]
for etiqueta, kw in casos:
    try:
        f = fields.Char(**kw)
    except Exception as exc:          # noqa: BLE001 — la sonda reporta, no juzga
        print(f'{etiqueta:44s} -> {type(exc).__name__}: {exc}')
        continue
    es = 'NonStored' if isinstance(f, NonStored) else type(f).__name__
    # que conservo de lo declarado
    inv = getattr(f, 'inverse', '<AUSENTE>')
    rec = getattr(f, 'recursive', '<AUSENTE>')
    print(f'{etiqueta:44s} -> {es:22s} inverse={inv!r} recursive={rec!r}')
