"""Donde EXACTAMENTE se pierde inverse=/recursive= en la rama NonStored."""
import django
django.setup()

import fields
from orm.fields_nonstored import (NonStored, apply_source_defaults,
                                  projection_or_none)

print('=== apply_source_defaults SI los devuelve ===')
for etiqueta, kw in [
        ("store=False, inverse='_x'", dict(store=False, inverse='_x')),
        ("store=False, recursive=True", dict(store=False, recursive=True)),
        ("compute='_c', inverse='_x'", dict(compute='_c', inverse='_x')),
        ("related='a.b', inverse='_x'", dict(related='a.b', inverse='_x')),
]:
    kwargs = dict(kw)
    related = kwargs.pop('related', None)
    attrs = apply_source_defaults(related, kwargs)
    print(f'{etiqueta:32s} attrs.inverse={attrs.get("inverse", "<AUSENTE>")!r} '
          f'attrs.recursive={attrs.get("recursive", "<AUSENTE>")!r} '
          f'store={attrs.get("store")!r}')

print()
print('=== pero el CAMPO construido no los lleva ===')
for etiqueta, kw in [
        ("Char(store=False, inverse='_x')", dict(store=False, inverse='_x')),
        ("Char(store=False, recursive=True)", dict(store=False, recursive=True)),
        ("Char(compute='_c', inverse='_x')", dict(compute='_c', inverse='_x')),
        ("Char(related='a.b', inverse='_x')", dict(related='a.b', inverse='_x')),
]:
    f = fields.Char(**kw)
    tipo = 'NonStored' if isinstance(f, NonStored) else type(f).__name__
    print(f'{etiqueta:36s} -> {tipo:10s} '
          f'inverse={getattr(f, "inverse", "<AUSENTE>")!r} '
          f'recursive={getattr(f, "recursive", "<AUSENTE>")!r}')

print()
print('=== y NonStored.__init__ los traga: no estan en __dict__ ===')
ns = NonStored(inverse='_x', recursive=True)
print('inverse en __dict__:', 'inverse' in ns.__dict__)
print('recursive en __dict__:', 'recursive' in ns.__dict__)
print('vars(ns) =', sorted(ns.__dict__))
