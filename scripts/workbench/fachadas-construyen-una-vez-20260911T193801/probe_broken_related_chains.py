"""Sonda: ¿qué cadenas ``related=`` no resuelven, y qué eslabón les falta?

La costura ``ensure_field_setup()`` aborta con ``KeyError`` en el PRIMER
eslabón ausente, así que su mensaje nombra una cadena y esconde las demás.
Esta sonda recorre TODAS las declaraciones ``related=`` del registro y
publica el censo completo: cuántas resuelven, cuántas no, y qué campo falta
en cada una.

La distinción importa para decidir el alcance: un puñado de cadenas rotas es
una tarea acotada; un reparto ancho sería otro problema.

No toca la base: el recorrido es sobre ``_meta`` y el registro de modelos.
"""
import collections

import django

django.setup()

from django.apps import apps  # noqa: E402


def declared_related_fields():
    """Cada campo del registro que declara ``related=``, con su modelo."""
    for model_cls in apps.get_models():
        for field in model_cls._meta.get_fields():
            related = getattr(field, 'related', None)
            if isinstance(related, str) and related:
                yield model_cls, field, related


def missing_link(model_cls, related):
    """El primer eslabón de la cadena que su modelo no declara, o None."""
    current = model_cls
    for step in related.split('.'):
        field = next((f for f in current._meta.get_fields()
                      if f.name == step), None)
        if field is None:
            return f'{current.__name__}.{step}'
        target = getattr(field, 'related_model', None)
        if target is None:
            return None
        current = target
    return None


def main():
    resolve, broken = 0, []
    for model_cls, field, related in declared_related_fields():
        gap = missing_link(model_cls, related)
        if gap is None:
            resolve += 1
        else:
            broken.append((model_cls.__name__, field.name, related, gap))

    print(f'cadenas related medidas: {resolve + len(broken)} | '
          f'resuelven: {resolve} | rotas: {len(broken)}')
    for model_name, field_name, related, gap in sorted(broken):
        print(f'  ROTA {model_name}.{field_name} = {related}  '
              f'-> falta {gap}')

    by_gap = collections.Counter(gap for *_, gap in broken)
    print(f'eslabones ausentes distintos: {len(by_gap)}')
    for gap, n in by_gap.most_common():
        print(f'  {gap}: {n} cadena(s)')
    print(f'VEREDICTO cadenas_rotas: {"OK" if not broken else "FALLA"}')


if __name__ == '__main__':
    main()
