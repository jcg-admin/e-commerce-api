"""¿Qué trae Django de la fase que la referencia usa para fusionar campos?

La referencia recoge las definiciones de campo por clase y construye UN campo
nuevo con todas (``odoo19c: odoo/orm/model_classes.py:370-415``). Esta sonda
mide, por conducta y no por lectura, qué parte de esa fase el stack ya trae
hecha y cuál habría que construir.

Las cuatro preguntas, una por etapa de la referencia:

1. ¿``ModelBase`` recibe el cuerpo de clase, como ``MetaModel.__new__``?
2. ¿Django conserva la ocurrencia del padre cuando la hija redeclara?
3. ¿Qué pasa con una base ABSTRACTA cuya hija redeclara el mismo nombre?
4. ¿Qué pasa con una base CONCRETA (herencia multi-tabla)?
"""
import importlib
import os
import sys

import django


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()
    models = importlib.import_module('django.db.models')
    ModelBase = importlib.import_module('django.db.models.base').ModelBase

    print('== 1. la metaclase y el cuerpo de clase ==')
    print('metaclase de un modelo :', type(models.Model).__name__)
    print('ModelBase.__new__ firma:',
          importlib.import_module('inspect').signature(ModelBase.__new__))

    seen = []

    class TracingChar(models.CharField):
        """Registra cada contribución: es el ``__set_name__`` de la referencia."""

        def contribute_to_class(self, cls, name, private_only=False):
            seen.append((cls.__name__, name, id(self)))
            super().contribute_to_class(cls, name, private_only=private_only)

    print('\n== 2/3. base ABSTRACTA y la hija que redeclara ==')
    Base = type('CollectionBase', (models.Model,), {
        '__module__': __name__,
        'label': TracingChar(max_length=10, verbose_name='de la base'),
        'Meta': type('Meta', (), {'abstract': True, 'app_label': 'base'}),
    })
    try:
        Child = type('CollectionChild', (Base,), {
            '__module__': __name__,
            'label': TracingChar(max_length=20, verbose_name='del override'),
            'Meta': type('Meta', (), {'app_label': 'base', 'managed': False}),
        })
        field = Child._meta.get_field('label')
        print('la hija se construye  : SI')
        print('max_length que queda  :', field.max_length)
        print('verbose_name que queda:', field.verbose_name)
        print('campos "label" en _meta:',
              len([f for f in Child._meta.get_fields() if f.name == 'label']))
    except Exception as error:
        print('la hija NO se construye:', type(error).__name__, error)

    print('\ncontribuciones registradas (clase, nombre, id):')
    for row in seen:
        print('   ', row)

    print('\n== 4. ¿sobrevive la ocurrencia de la BASE en algún sitio? ==')
    base_field = next((f for f in Base._meta.get_fields() if f.name == 'label'),
                      None)
    print('la base declara label  :', base_field is not None)
    if base_field is not None:
        print('max_length de la base  :', base_field.max_length)
        print('mismo objeto que la hija:',
              base_field is Child._meta.get_field('label'))
    print('\nvars(Base) conserva el campo:', 'label' in vars(Base))
    print('vars(Child) conserva el campo:', 'label' in vars(Child))


if __name__ == '__main__':
    sys.exit(main())
