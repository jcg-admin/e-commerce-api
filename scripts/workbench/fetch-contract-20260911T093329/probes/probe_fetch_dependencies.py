"""Que le pregunta ``fetch()`` a cada campo, y si nuestro arbol sabe responder.

La pregunta NO es «existe un simbolo llamado X». Esa medicion es del
significante y ya produjo una conclusion falsa en este mismo pase: contar
``def column_type`` en ``src/orm/fields.py`` da 0 y de ahi se concluyo que
cinco piezas faltaban. Tres de las cinco estaban — son atributos que el
``__init__`` fija, no ``def``, asi que un recorrido de declaraciones es ciego
a ellas por construccion.

Lo que se mide aqui es CONDUCTA: se toma un campo real de un modelo portado y
se le hace cada una de las preguntas que ``_fetch_query`` y
``_determine_fields_to_fetch`` le hacen en la referencia.

Metrica: el valor que devuelve cada pregunta sobre campos concretos de
``base.ResPartner``, mas una relacion inversa como control negativo.
Ciega a: un campo cuya respuesta sea correcta en ``ResPartner`` y no en otro
modelo — la poblacion es un modelo, no el arbol; y a la SEMANTICA de la
respuesta (que ``db_type`` devuelva ``bigint`` no prueba que la fuente
hubiera devuelto ``('int4','int4')`` para ese mismo campo).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import connection  # noqa: E402

#: Las preguntas, en el orden en que la fuente las hace. La clave es el nombre
#: del simbolo en la referencia; el valor, como se responde aqui.
QUESTIONS = {
    'column_type': lambda f: (f.db_type(connection) if hasattr(f, 'db_type')
                              else '(sin db_type)'),
    'store': lambda f: getattr(f, 'store', '(ausente)'),
    'prefetch': lambda f: getattr(f, 'prefetch', '(ausente)'),
    'translate': lambda f: getattr(f, 'translate', '(ausente)'),
    'read': lambda f: type(getattr(f, 'read', None)).__name__,
    'copy': lambda f: getattr(f, 'copy', '(ausente)'),
    'inherited': lambda f: getattr(f, 'inherited', '(ausente)'),
    '_insert_cache': lambda f: hasattr(f, '_insert_cache'),
    '_cache_missing_ids': lambda f: hasattr(f, '_cache_missing_ids'),
}


def main() -> int:
    model = apps.get_model('base', 'ResPartner')
    subjects = [f.name for f in list(model._meta.concrete_fields)[:4]]
    subjects.append('category_ids')          # control negativo: relacion inversa

    width = max(len(k) for k in QUESTIONS) + 2
    print(f"{'pregunta de la fuente':<{width}}" +
          ''.join(f'{s[:16]:<18}' for s in subjects))
    absent = 0
    for name, ask in QUESTIONS.items():
        row = []
        for subject in subjects:
            field = model._meta.get_field(subject)
            try:
                value = ask(field)
            except Exception as exc:            # noqa: BLE001
                value = f'({type(exc).__name__})'
            row.append(str(value)[:16])
        if all(v.startswith('(ausente') for v in row[:-1]):
            absent += 1
        print(f'{name:<{width}}' + ''.join(f'{v:<18}' for v in row))

    print()
    print(f'preguntas que NINGUN campo concreto sabe responder: {absent} '
          f'de {len(QUESTIONS)} (alcance medido: {len(subjects) - 1} campos '
          f'concretos de base.ResPartner + 1 relacion inversa de control)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
