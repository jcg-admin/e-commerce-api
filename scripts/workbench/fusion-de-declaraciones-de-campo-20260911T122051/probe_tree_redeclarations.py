"""M6 — cuantos modelos CONCRETOS del arbol redeclaran hoy un nombre que una
base declara como ``NonStored``.

Es la tercera medicion previa a escribir la costura de fusion. Decide si el
defecto de M4 —dos objetos para un nombre— ya esta vivo en el arbol (y por
tanto puede estar codificado en migraciones) o si el conteo honesto es
"0 hoy + los que entren con el addon portado".

*Metrica:* por cada modelo de ``apps.get_models()``, los nombres declarados en
el ``__dict__`` de la propia clase que ademas aparecen como ``NonStored`` en
alguna base de su MRO, y viceversa.
*Ciega a:* la redeclaracion stored-sobre-stored (semantica propia de Django,
fuera de este pase) y a los modelos que ningun ``AppConfig`` instalado carga.
"""
import collections
import os
import sys

import django

sys.path.insert(0, 'src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.apps import apps                             # noqa: E402
from django.db import models                             # noqa: E402

from orm.fields_nonstored import NonStored               # noqa: E402


def non_stored_in_bases(cls):
    """Nombre -> clase base que lo declara como ``NonStored`` (sin la propia)."""
    found = {}
    for base in cls.__mro__[1:]:
        for name, held in vars(base).items():
            if isinstance(held, NonStored):
                found.setdefault(name, base)
    return found


def stored_in_bases(cls):
    """Nombre -> base que lo declara como campo con columna (sin la propia)."""
    found = {}
    for base in cls.__mro__[1:]:
        meta = getattr(base, '_meta', None)
        #: La clausula ``and base is cls`` que vivia aqui era INALCANZABLE:
        #: el recorrido es sobre ``__mro__[1:]``, que ya excluye a ``cls``.
        #: Por precedencia la condicion se reducia a ``meta is None``, que es
        #: lo unico que hacia falta. Se escribe lo que mide.
        if meta is None:
            continue
        for field in getattr(meta, 'local_fields', ()):
            found.setdefault(field.name, base)
    return found


def main():
    models_seen = apps.get_models()
    stored_over_nonstored = []
    nonstored_over_stored = []

    for cls in models_seen:
        ns_bases = non_stored_in_bases(cls)
        own_stored = {f.name for f in cls._meta.local_fields}
        own_ns = {n for n, h in vars(cls).items() if isinstance(h, NonStored)}

        for name in sorted(own_stored & set(ns_bases)):
            stored_over_nonstored.append(
                (cls._meta.label, name, ns_bases[name].__name__))

        st_bases = stored_in_bases(cls)
        for name in sorted(own_ns & set(st_bases)):
            nonstored_over_stored.append(
                (cls._meta.label, name, st_bases[name].__name__))

    print(f'modelos medidos: {len(models_seen)}')
    print(f'stored sobre NonStored (el defecto de M4): '
          f'{len(stored_over_nonstored)}')
    for row in stored_over_nonstored:
        print('   ', *row)
    print(f'NonStored sobre stored: {len(nonstored_over_stored)}')
    for row in nonstored_over_stored:
        print('   ', *row)

    by_name = collections.Counter(r[1] for r in stored_over_nonstored)
    if by_name:
        print('por nombre:', dict(by_name))


if __name__ == '__main__':
    main()
