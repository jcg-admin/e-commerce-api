"""¿Sobrevive la DECLARACIÓN del autor, o sólo el residuo ya enrutado?

La fuente fusiona ``_args__`` —el diccionario de lo que el autor escribió— y
deriva ``store`` DESPUÉS, dentro de ``_get_attrs`` (``odoo19c:
odoo/orm/fields.py:414-450``). Su ``Field.__init__`` son **tres líneas** y no
enruta nada (``:314-317``)::

    def __init__(self, string=SENTINEL, **kwargs):
        kwargs['string'] = string
        self._sequence = next(_global_seq)
        self._args__ = ReadonlyDict({k: v for k, v in kwargs.items()
                                     if v is not SENTINEL})

Aquí la fachada enruta al construir: con ``compute=`` sale un ``NonStored``,
sin él un ``CharField``. Si la declaración cruda sobreviviera, la fusión podría
operar sobre ella y enrutar UNA vez al final, que es el orden de la fuente.

EL VEREDICTO SE MIDE POR CONTENIDO, NO POR PRESENCIA
=====================================================

La primera versión de esta sonda cerraba con ``hasattr(holder, '_args__')`` y
publicaba tres ``True``. Eso mide el **significante** —que el atributo exista—
y concluye sobre el **significado** —que la declaración esté ahí—. Con los
valores impresos justo encima diciendo ``None`` y ``{}``.

Por eso cada caso declara **qué claves espera** y el veredicto compara claves
presentes contra claves declaradas. Un atributo vacío falla; uno con el residuo
parcial falla nombrando lo que perdió.
"""
import importlib
import os
import sys

import django

#: Cada caso: etiqueta · cómo se construye · las claves que el autor escribió.
#: Son las claves que la fuente guardaría verbatim en ``_args__``.
CASES = [
    ('Char(compute=)', dict(compute='_c'), {'compute'}),
    ('Char(inverse=, recursive=)', dict(inverse='_i', recursive=True),
     {'inverse', 'recursive'}),
    ('Char(max_length=, readonly=)', dict(max_length=9, readonly=True),
     {'max_length', 'readonly'}),
]


def declared_of(holder):
    """Lo que el campo conserva de la declaración, como conjunto de claves."""
    args = getattr(holder, '_args__', None)
    return set(args) if isinstance(args, dict) else set()


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()
    apps = importlib.import_module('django.apps').apps
    fields = importlib.import_module('fields')
    mixin = importlib.import_module('orm.models').DisplayNameMixin

    print('== recién construidos: lo escrito contra lo conservado ==')
    verdicts = []
    for label, kwargs, written in CASES:
        field = fields.Char(**kwargs)
        kept = declared_of(field)
        lost = written - kept
        verdicts.append(not lost)
        print(f'   {label:30} {type(field).__name__:11} '
              f'_args__={getattr(field, "_args__", None)!r:.44}')
        print(f'   {"":30} escrito={sorted(written)} '
              f'perdido={sorted(lost) or "nada"}')

    print('\n== ya instalados en clases reales ==')
    base = vars(mixin)['display_name']
    Category = apps.get_model('test_orm', 'TestOrmCategory')
    override = next(f for f in Category._meta.get_fields()
                    if f.name == 'display_name')
    for label, holder, written in [
            ('base  DisplayNameMixin', base, {'compute', 'search'}),
            ('override TestOrmCategory', override, {'inverse', 'recursive'})]:
        kept = declared_of(holder)
        lost = written - kept
        verdicts.append(not lost)
        print(f'   {label:30} {type(holder).__name__:11} '
              f'_args__={getattr(holder, "_args__", None)!r:.44}')
        print(f'   {"":30} escrito={sorted(written)} '
              f'perdido={sorted(lost) or "nada"}')

    print('\n== el veredicto — por CONTENIDO ==')
    print(f'   casos que conservan su declaración : {sum(verdicts)} de {len(verdicts)}')
    print(f'   se puede fusionar por declaración  : {all(verdicts)}')
    print('\n   Métrica: claves presentes en `_args__` contra las que el autor')
    print('            escribió, por caso.')
    print('   Ciega a: el VALOR de una clave conservada (sólo compara claves),')
    print('            y a una clave que la fachada renombre antes de delegar')
    print('            —`readonly` sale como `editable`, y ahí el conjunto')
    print('            acusa la pérdida aunque el dato viaje con otro nombre.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
