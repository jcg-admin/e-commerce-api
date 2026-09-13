"""El override pierde lo que la base declaró — medido sobre el modelo real.

``TestOrmCategory.display_name`` se porta verbatim de la referencia
(``odoo19c: odoo/addons/test_orm/models/test_orm.py:28-31``)::

    display_name = fields.Char(inverse='_inverse_display_name', recursive=True)

Sin ``compute=`` ni ``store=``. Allá eso NO significa «campo con columna»:
significa «override», y la fusión le trae el ``compute`` de la base
(``BaseModel.display_name``, ``odoo19c: odoo/orm/models.py:473-477``), del que
el bloque ``compute`` deriva ``store=False``.

Aquí no hay fusión, así que la declaración se lee sola y ``store`` cae a su
defecto ``True``: el campo gana columna y pierde el cómputo, el search y el
string de la base.
"""
import importlib
import os
import sys

import django


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()
    apps = importlib.import_module('django.apps').apps
    NonStored = importlib.import_module('orm.fields_nonstored').NonStored

    Category = apps.get_model('test_orm', 'TestOrmCategory')
    mixin = importlib.import_module('orm.models').DisplayNameMixin

    print('== lo que la BASE declara ==')
    base = vars(mixin)['display_name']
    for attribute in ('compute', 'search', 'verbose_name'):
        print(f'   {attribute:14}', repr(getattr(base, attribute, '<ausente>')))
    print('   tipo          ', type(base).__name__)

    print('\n== lo que el OVERRIDE deja en el modelo real ==')
    held = vars(Category).get('display_name', '<ausente en vars>')
    print('   vars(Category) ', type(held).__name__)
    campo = next((f for f in Category._meta.get_fields()
                  if f.name == 'display_name'), None)
    print('   en _meta       ', type(campo).__name__ if campo else '<sin columna>')
    if campo is not None:
        for attribute in ('compute', 'search', 'inverse', 'recursive'):
            print(f'   {attribute:14}', repr(getattr(campo, attribute, '<ausente>')))

    print('\n== el veredicto de conducta ==')
    print('   ¿es NonStored, como manda la fusión de la fuente?',
          isinstance(campo, NonStored) if campo is not None else 'sin campo')
    print('   ¿conserva el compute de la base?',
          getattr(campo, 'compute', None) == getattr(base, 'compute', None)
          if campo is not None else 'sin campo')
    print('   ¿conserva el search de la base? ',
          getattr(campo, 'search', None) == getattr(base, 'search', None)
          if campo is not None else 'sin campo')


if __name__ == '__main__':
    sys.exit(main())
