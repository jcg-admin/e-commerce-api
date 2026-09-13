#!/usr/bin/env python3
"""Measure whether the owner class agrees on both sides of each visible pair.

El guion hermano (``measure_pairing_blindness.py``) mide cuantos pares
``methods_of`` NO ve. Este mide, de los que SI ve, en cuantos la clase duena
coincide con la de la fuente — que es lo que decide si un emparejamiento por
``(owner, name)`` puede sustituirlo sin perder poblacion.

La pregunta no es retorica: nuestro puerto disuelve ``BaseModel`` en mixins
(OE-5 lo declara bloqueado por eso), asi que un emparejamiento estricto por
duena perderia justo los pares del nucleo del ORM.
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


def owners_by_name(declarations):
    """Las clases duenas de cada nombre de metodo declarado en clase."""
    owners = collections.defaultdict(set)
    for declaration in declarations:
        if declaration.kind == 'function' and declaration.owner:
            owners[declaration.name].add(declaration.owner)
    return owners


def main():
    files = list(engine.tree_files(['src/orm', 'src/tools']))
    agree = disagree = both_in_class = 0
    examples = []
    for path in files:
        reference = engine.counterpart(path)
        if reference is None or not reference.is_file():
            continue
        ours, theirs = engine.methods_of(path), engine.methods_of(reference)
        our_owners = owners_by_name(engine.declarations_of(path))
        their_owners = owners_by_name(engine.declarations_of(reference))
        for name in ours:
            if name not in theirs:
                continue
            mine, yours = our_owners.get(name, set()), their_owners.get(name, set())
            if mine & yours:
                agree += 1
                continue
            disagree += 1
            if mine and yours:
                both_in_class += 1
            examples.append((str(path), name, sorted(mine), sorted(yours)))

    print(f'pares con clase duena coincidente : {agree}')
    print(f'pares SIN clase duena coincidente : {disagree}')
    print(f'  de ellos, ambos lados en clase  : {both_in_class}')
    for path, name, mine, yours in examples:
        print(f'    {path}::{name}  nuestro={mine} fuente={yours}')


if __name__ == '__main__':
    main()
