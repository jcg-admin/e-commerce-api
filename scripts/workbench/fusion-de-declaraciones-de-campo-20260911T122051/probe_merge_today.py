"""Que hace HOY nuestro arbol ante una redeclaracion. Sin inferir."""
import django
django.setup()

from django.db import models as dj

import fields
from orm.fields_nonstored import NonStored, non_stored_fields


class BaseProbe(dj.Model):
    label = fields.Char(compute='_compute_label', store=False)

    class Meta:
        abstract = True
        app_label = 'base'


class OverrideProbe(BaseProbe):
    #: la forma EXACTA de TestOrmCategory.display_name en la referencia
    label = fields.Char(inverse='_inverse_label', recursive=True)

    class Meta:
        app_label = 'base'


campo = vars(OverrideProbe).get('label')
print('el atributo de clase de la subclase :', type(campo).__name__)
print('  compute  =', getattr(campo, 'compute', '<AUSENTE>'))
print('  inverse  =', getattr(campo, 'inverse', '<AUSENTE>'))
print('  recursive=', getattr(campo, 'recursive', '<AUSENTE>'))
print()
print('lo que el registro por MRO devuelve:')
mapa = non_stored_fields(OverrideProbe)
elegido = mapa.get('label')
print('  tipo     =', type(elegido).__name__ if elegido else '<NO ESTA>')
if elegido is not None:
    print('  compute  =', getattr(elegido, 'compute', '<AUSENTE>'))
    print('  inverse  =', getattr(elegido, 'inverse', '<AUSENTE>'))
print()
print('¿la subclase creo COLUMNA para label?',
      'label' in {f.name for f in OverrideProbe._meta.get_fields()})
print('base declara NonStored?', isinstance(vars(BaseProbe).get('label'), NonStored))
