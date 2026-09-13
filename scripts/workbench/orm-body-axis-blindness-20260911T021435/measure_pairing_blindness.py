#!/usr/bin/env python3
"""Measure how many symbol pairs ``methods_of`` cannot see.

OE-8 del alcance ``completar-raiz-orm`` declara que el unico medidor de
cuerpo vivo empareja con ``methods_of``, que solo recoge metodos declarados
dentro de una clase. Este guion mide esa ceguera contra ``declarations_of``,
el extractor hermano que el propio motor ya declara y que ``compare`` no
consume.

No emite veredicto: emite el material. Un par visto no dice que los dos
cuerpos hagan lo mismo — solo que el instrumento los puede comparar.
"""
import collections
import os
import pathlib
import sys

#: La raiz del consumidor NO se compone por aritmetica de ruta. El hogar del
#: banco es DECLARABLE (`THYROX_WORKBENCH_DIR`), asi que la profundidad de una
#: pieza dentro de el no es fija: un `parents[3]` resuelve la raiz correcta
#: solo mientras el banco viva donde vivia al escribirlo. Se declara primero
#: (`THYROX_CONSUMER`, la clave que `thyrox: src/paths/reach.py:612` ya fija) y
#: si no, se busca el marcador subiendo — la forma del BOOTSTRAP de ese mismo
#: modulo, que sobrevive a la copia.
MARKER = pathlib.Path('scripts') / 'counterpart_body.py'


def consumer_root():
    """La raiz del repo que aloja el motor: declarada, o por marcador."""
    declared = os.environ.get('THYROX_CONSUMER')
    if declared:
        return pathlib.Path(declared)
    here = pathlib.Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / MARKER).is_file():
            return candidate
    raise SystemExit(
        f'ERROR — no se halla {MARKER} subiendo desde {here}. Declara '
        'THYROX_CONSUMER con la raiz del repo. NO se emite conteo: un 0 '
        'aqui seria un verde falso.')


ROOT = consumer_root()
sys.path.insert(0, str(ROOT / 'scripts'))

import counterpart_body as engine  # noqa: E402


def module_level_pairs(ours, theirs):
    """Pares que ``declarations_of`` ve y ``methods_of`` no: funcion de modulo."""
    mine = {d.name for d in ours if d.owner == '' and d.kind == 'function'}
    yours = {d.name for d in theirs if d.owner == '' and d.kind == 'function'}
    return mine & yours


def sibling_collisions(declarations):
    """Nombres declarados por mas de una clase en el mismo archivo."""
    owners = collections.defaultdict(set)
    for d in declarations:
        if d.kind == 'function' and d.owner:
            owners[d.name].add(d.owner)
    return {name for name, klasses in owners.items() if len(klasses) > 1}


def main():
    files = list(engine.tree_files(['src/orm', 'src/tools']))
    seen = colliding = module_only = with_counterpart = 0
    collision_detail = []
    for path in files:
        reference = engine.counterpart(path)
        if reference is None or not reference.is_file():
            continue
        with_counterpart += 1
        ours_m, theirs_m = engine.methods_of(path), engine.methods_of(reference)
        seen += len(set(ours_m) & set(theirs_m))
        ours_d = engine.declarations_of(path)
        theirs_d = engine.declarations_of(reference)
        extra = module_level_pairs(ours_d, theirs_d)
        module_only += len(extra)
        collisions = sibling_collisions(theirs_d) & set(ours_m)
        colliding += len(collisions)
        if collisions:
            collision_detail.append((str(path), sorted(collisions)))

    total = seen + module_only
    print(f'archivos recorridos           : {len(files)}')
    print(f'archivos con contraparte      : {with_counterpart}')
    print(f'pares que methods_of ve       : {seen}')
    print(f'pares de funcion de modulo    : {module_only}  (ciegos hoy)')
    print(f'universo emparejable          : {total}')
    if total:
        print(f'cobertura de methods_of       : {seen / total:.1%}')
    print(f'nombres con hermanos en fuente: {colliding}  '
          f'(methods_of colapsa por nombre)')
    for path, names in collision_detail:
        print(f'  {path}: {", ".join(names)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
