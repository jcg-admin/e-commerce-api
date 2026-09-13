"""Qué GUARDA cada sitio, y si las dos ocurrencias se pueden recuperar.

La sonda anterior midió que ``vars(Base)`` y ``vars(Child)`` conservan algo
llamado ``label``. Eso es el significante. Lo que decide si la fusión de la
referencia es construible aquí es el significado: **qué objeto** hay en cada
sitio, si las dos ocurrencias sobreviven distinguibles, y en qué orden.

Y mide las DOS formas de herencia que este árbol tiene, que la referencia no
distingue porque allá toda clase de modelo pasa por la misma metaclase:

- **base abstracta de Django** — la hija hereda por ``Meta.abstract``;
- **mixin llano de Python** — la clase base NO es un modelo, así que su campo
  no pasa por ``ModelBase`` en la base, sólo al aterrizar en la hija.
"""
import importlib
import os
import sys

import django


def describe(where, holder, name):
    value = vars(holder).get(name, '<ausente>')
    print(f'   {where:22} {type(value).__name__:24} {value!r:.60}')


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()
    models = importlib.import_module('django.db.models')
    fields = importlib.import_module('fields')

    print('== forma 1: base ABSTRACTA de Django ==')
    Base = type('HoldsBase', (models.Model,), {
        '__module__': __name__,
        'label': models.CharField(max_length=10, verbose_name='de la base'),
        'Meta': type('Meta', (), {'abstract': True, 'app_label': 'base'}),
    })
    Child = type('HoldsChild', (Base,), {
        '__module__': __name__,
        'label': models.CharField(max_length=20, verbose_name='del override'),
        'Meta': type('Meta', (), {'app_label': 'base', 'managed': False}),
    })
    print('qué guarda cada sitio:')
    describe('vars(Base)[label]', Base, 'label')
    describe('vars(Child)[label]', Child, 'label')
    print('   _meta de la base   ', type(Base._meta.get_field('label')).__name__,
          '  max_length =', Base._meta.get_field('label').max_length)
    print('   _meta de la hija   ', type(Child._meta.get_field('label')).__name__,
          '  max_length =', Child._meta.get_field('label').max_length)

    print('\n¿se recuperan LAS DOS ocurrencias, y en orden de override?')
    ocurrencias = []
    for klass in reversed(Child.__mro__):
        meta = getattr(klass, '_meta', None)
        if meta is None or getattr(meta, 'abstract', False) is False and klass is not Child:
            pass
        if meta is not None:
            local = {f.name: f for f in getattr(meta, 'local_fields', ())}
            if 'label' in local:
                ocurrencias.append((klass.__name__, local['label'].max_length))
    print('   por recorrido de __mro__ con _meta.local_fields:', ocurrencias)

    print('\n== forma 2: MIXIN LLANO de Python (el de este árbol) ==')

    class HoldsMixin:
        label = fields.Char(store=False, compute='_compute_label')

    Mixed = type('HoldsMixed', (HoldsMixin, models.Model), {
        '__module__': __name__,
        'label': fields.Char(store=False, compute='_compute_other'),
        'Meta': type('Meta', (), {'app_label': 'base', 'managed': False}),
    })
    print('qué guarda cada sitio:')
    describe('vars(HoldsMixin)', HoldsMixin, 'label')
    describe('vars(HoldsMixed)', Mixed, 'label')
    print('   _meta de la mezclada tiene label:',
          any(f.name == 'label' for f in Mixed._meta.get_fields()))
    print('   el compute que queda           :',
          getattr(vars(Mixed).get('label'), 'compute', '<sin compute>'))
    print('   el compute del mixin sobrevive :',
          getattr(vars(HoldsMixin).get('label'), 'compute', '<sin compute>'))

    print('\n== la pregunta que decide: ¿el objeto de la base es alcanzable? ==')
    print('   forma 1 — base abstracta :',
          Base._meta.get_field('label') is not Child._meta.get_field('label'),
          '(dos objetos distintos, los dos vivos)')
    print('   forma 2 — mixin llano    :',
          vars(HoldsMixin)['label'] is not vars(Mixed)['label'],
          '(dos objetos distintos, los dos vivos)')


if __name__ == '__main__':
    sys.exit(main())
