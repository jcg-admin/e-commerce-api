"""M7 — que dicionario guarda hoy ``_args__``, y si la rama sin columna lo tiene.

``_get_attrs`` documenta *"Recibe lo declarado en ``_args__``"*. El envoltorio
que lo escribe cuelga de ``models.Field.__init__``, que esta AGUAS ABAJO de dos
traducciones: la firma de la fachada saca ``store``/``related``/``help``/… de
kwargs, y ``_declared_source_vocabulary`` saca ``inverse``/``recursive``. Si lo
que llega es vocabulario de Django, la fusion acumularia el diccionario
equivocado.

*Metrica:* las claves de ``_args__`` de un campo construido por la fachada en
sus dos ramas, y su presencia en la rama sin columna.
*Ciega a:* los campos construidos sin pasar por la fachada.
"""
import os
import sys

import django

sys.path.insert(0, 'src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

import fields                                            # noqa: E402
from orm.fields_nonstored import NonStored               # noqa: E402


_MISSING = object()


def show(label, built):
    args = getattr(built, '_args__', _MISSING)
    if args is _MISSING:
        shown = 'AUSENTE (sin atributo)'
    elif args is None:
        shown = 'None (atributo presente, sin valor)'
    else:
        shown = dict(args)
    print(f'{label}')
    print(f'    tipo      : {type(built).__name__}')
    print(f'    _args__   : {shown}')
    for key in ('inverse', 'recursive', 'store'):
        print(f'    .{key:<9}: {getattr(built, key, "(sin atributo)")!r}')


def main():
    show("Char(inverse='_x', recursive=True)  [rama con columna]",
         fields.Char(inverse='_x', recursive=True))
    print()
    show("Char('Label', store=False, inverse='_x')  [rama sin columna]",
         fields.Char('Label', store=False, inverse='_x'))
    print()
    show("NonStored(default=None, search='_s')  [declaracion directa]",
         NonStored(default=None, search='_s'))


if __name__ == '__main__':
    main()
