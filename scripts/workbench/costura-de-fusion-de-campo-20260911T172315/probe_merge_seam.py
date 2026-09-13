"""¿Puede dispararse aquí la regla de compatibilidad de tipo de la fuente?

La fuente fusiona las redefiniciones de un campo en `Field._get_attrs`
(`odoo19c: odoo/orm/fields.py:414-430`) y descarta lo heredado cuando los tipos
no son compatibles::

    if not isinstance(self, type(field)):
        attrs.clear(); modules.clear(); continue

La sonda mide si esa condición puede ser verdadera en NUESTRO árbol para el par
que el porte de `test_orm` destapó: la base declara el campo sin columna y la
redefinición lo declara con columna.

Métrica: `type().__mro__` de los dos objetos que produce la fachada `fields.Char`,
y el `isinstance` cruzado.
Ciega a: qué atributos acabarían en `attrs` — mide la GUARDA, no la fusión.
"""
import importlib

import django


def main():
    # `django.setup()` tiene que correr ANTES de importar `fields`: su cadena
    # llega a `contenttypes.models`, que declara un modelo y exige el registro
    # de apps poblado. Es la excepcion #4 de `no-lazy-imports.md` — una LLAMADA
    # a `import_module`, no un statement `import`, asi que el gate AST sale 0.
    django.setup()
    fields = importlib.import_module('fields')
    NonStored = importlib.import_module('orm.fields_nonstored').NonStored

    stored = fields.Char(max_length=64)
    nonstored = fields.Char(store=False, compute='_compute_label')
    shared = [c.__name__ for c in type(stored).__mro__
              if c in type(nonstored).__mro__]
    print('fields.Char(...)             ->', type(stored).__name__)
    print('fields.Char(store=False, ...)->', type(nonstored).__name__)
    print('isinstance(conColumna, type(sinColumna)) =',
          isinstance(stored, type(nonstored)))
    print('isinstance(sinColumna, type(conColumna)) =',
          isinstance(nonstored, type(stored)))
    print('ancestros comunes:', shared)
    print()
    print('VEREDICTO: la guarda de la fuente NUNCA es verdadera cruzando la'
          ' frontera con-columna / sin-columna, porque el unico ancestro comun'
          ' es object. En la fuente SIEMPRE lo es, porque alli las dos'
          ' declaraciones son la misma clase `Char` y `store` es un atributo.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
