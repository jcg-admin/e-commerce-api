#!/usr/bin/env python3
"""Inventario del ORM de la REFERENCIA, medido por si mismo.

Que anade sobre el censo de presencia
--------------------------------------
El censo (``orm-symbol-presence-census-20260910T175850``, ``TASK-API-0391``)
ya alcanzo los 22 archivos no-``__init__`` de ``odoo/orm``: cada uno tiene un
archivo del mismo nombre en ``src/orm``. **Este run NO extiende cobertura.**
Lo que cambia son dos cosas, y sin decirlo las dos cifras se leerian como
contradictorias:

- **La UNIDAD.** El censo empareja por NOMBRE y su indice se queda con el
  primer homonimo (``_by_name``), asi que su universo es de nombres UNICOS.
  Aqui la unidad es la **ocurrencia**, con su clase `owner`. Medido: en
  ``fields_relational.py`` son 86 ocurrencias contra 50 nombres; en
  ``domains.py``, 142 contra 88.
- **El DESGLOSE.** El censo publica una fila por archivo. Aqui cada archivo
  lleva sus clases, cada clase sus metodos, y cada funcion su firma — que es
  literalmente lo que el encargo pide contar.

Lo que se reusa, sin copiar
----------------------------
``declared_symbols``, ``signature_of`` y ``body_class`` se **importan** del run
del censo, donde ya tienen suite propia. Reescribirlos aqui daria dos
extractores del mismo juicio que nadie sincroniza — lo que
``calibration-verified-numbers.md`` prohibe para una cifra y vale igual para un
criterio. Las cuatro raices de ``odoo-tools`` salen de
``scripts/reference_roots.py``: ninguna ruta se teclea.
"""
import argparse
import ast
import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
RUN_DIR = pathlib.Path(__file__).resolve().parent

#: El run hermano del que se importa el extractor ya probado.
CENSUS_RUN = 'scripts/workbench/orm-symbol-presence-census-20260910T175850'

#: El subarbol del ORM dentro de una raiz de la referencia. Existe SOLO en 19c
#: (medido); ver ``probes/probe_orm_across_trees.py``.
ORM_SUBTREE = ('odoo', 'orm')


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_roots = _load('_inv_roots', REPO / 'scripts/reference_roots.py')
_census = _load('_inv_census', REPO / CENSUS_RUN / 'census_symbol_presence.py')

TREE_ROOTS = _roots.TREE_ROOTS
declared_symbols = _census.declared_symbols


def orm_root(alias):
    """La raiz del ORM de un arbol de la referencia. NO comprueba que exista.

    Devolver la ruta de un arbol sin ORM es correcto: quien la consume decide,
    y ``inventory`` distingue «no existe» de «existe y esta vacia».
    """
    return TREE_ROOTS[alias].joinpath(*ORM_SUBTREE)


def file_inventory(path):
    """Un archivo: sus clases con sus metodos, sus funciones de modulo, y el
    conteo CRUDO frente al de nombres unicos.

    ``raw`` es la unidad de este run. ``unique`` viaja al lado para que la
    diferencia con el censo sea legible en la propia fila, en vez de tener que
    reconstruirla.
    """
    path = pathlib.Path(path)
    records = declared_symbols(path)
    try:
        lines = len(path.read_text(encoding='utf-8').splitlines())
    except OSError:
        lines = 0

    classes, functions = [], []
    by_owner = {}
    for record in records:
        if record['kind'] == 'class':
            entry = {'name': record['name'], 'lineno': record['lineno'],
                     'decorators': record['decorators'], 'methods': []}
            classes.append(entry)
            by_owner[record['name']] = entry
        elif record['kind'] == 'function':
            functions.append(record)

    for record in records:
        if record['kind'] != 'method':
            continue
        owner = by_owner.get(record['owner'])
        if owner is not None:
            owner['methods'].append(record)

    names = [r['name'] for r in records]
    return {
        'name': path.name,
        'lines': lines,
        'classes': classes,
        'functions': functions,
        'raw': len(names),
        'unique': len(set(names)),
    }


def _signature_shape(records):
    """Cuantas firmas declaran opcionales, ``*args``, kw-only y ``**kwargs``."""
    shape = {'with_default': 0, 'vararg': 0, 'kwonly': 0, 'kwarg': 0}
    for record in records:
        signature = record.get('signature')
        if not signature:
            continue
        if any(signature['has_default']):
            shape['with_default'] += 1
        if signature['vararg']:
            shape['vararg'] += 1
        if signature['kwonly']:
            shape['kwonly'] += 1
        if signature['kwarg']:
            shape['kwarg'] += 1
    return shape


def inventory(root):
    """El inventario de una raiz de ORM.

    Una raiz **ausente** devuelve ceros con ``root_exists=False``. Devolver un
    cero mudo no distinguiria «medi y no hay» de «no pude medir», que es el
    sub-patron D de ``metrica-decide-la-conclusion.md``.
    """
    root = pathlib.Path(root)
    if not root.is_dir():
        return {
            'root': str(root), 'root_exists': False, 'files': [],
            'totals': {'files': 0, 'lines': 0, 'classes': 0,
                       'module_functions': 0, 'methods': 0, 'symbols': 0,
                       'unique_names': 0, 'stub': 0,
                       'with_default': 0, 'vararg': 0, 'kwonly': 0, 'kwarg': 0},
        }

    files = [file_inventory(path) for path in sorted(root.glob('*.py'))]

    every_callable = []
    stub = 0
    for entry in files:
        every_callable.extend(entry['functions'])
        for owner in entry['classes']:
            every_callable.extend(owner['methods'])
    stub = sum(1 for r in every_callable if r['body'] == 'stub')

    totals = {
        'files': len(files),
        'lines': sum(e['lines'] for e in files),
        'classes': sum(len(e['classes']) for e in files),
        'module_functions': sum(len(e['functions']) for e in files),
        'methods': sum(len(c['methods']) for e in files for c in e['classes']),
        'unique_names': sum(e['unique'] for e in files),
        'stub': stub,
    }
    totals['symbols'] = (
        totals['classes'] + totals['module_functions'] + totals['methods'])
    totals.update(_signature_shape(every_callable))
    return {'root': str(root), 'root_exists': True, 'files': files,
            'totals': totals}


# --- el reporte ------------------------------------------------------------

#: Las etiquetas de la tabla. Van en INGLES porque nombran las claves del
#: reporte, no prosa: 'default' es el parametro opcional — la forma
#: castellana 'defecto' es un falso amigo que nombra un error.
_HEADER = ('file', 'lines', 'cls', 'fn', 'met', 'raw', 'unique',
           'default', '*args', 'kwonly', '**kw')


def _rows(report):
    for entry in report['files']:
        callables = list(entry['functions'])
        for owner in entry['classes']:
            callables.extend(owner['methods'])
        shape = _signature_shape(callables)
        yield (entry['name'], entry['lines'], len(entry['classes']),
               len(entry['functions']),
               sum(len(c['methods']) for c in entry['classes']),
               entry['raw'], entry['unique'], shape['with_default'],
               shape['vararg'], shape['kwonly'], shape['kwarg'])


def render(report, class_detail_min=10):
    """La tabla por archivo, y el desglose por clase de los archivos grandes."""
    lines = []
    if not report['root_exists']:
        return [f"la raiz no existe: {report['root']}  (0 archivos, 0 simbolos)"]

    widths = [max(len(str(_HEADER[i])),
                  max((len(str(row[i])) for row in _rows(report)), default=0))
              for i in range(len(_HEADER))]
    fmt = '  '.join(
        [f'{{:<{widths[0]}}}'] + [f'{{:>{w}}}' for w in widths[1:]])
    lines.append(fmt.format(*_HEADER))
    lines.append('-' * (sum(widths) + 2 * (len(widths) - 1)))
    for row in _rows(report):
        lines.append(fmt.format(*row))
    total = report['totals']
    lines.append('-' * (sum(widths) + 2 * (len(widths) - 1)))
    lines.append(fmt.format(
        'TOTAL', total['lines'], total['classes'], total['module_functions'],
        total['methods'],
        total['classes'] + total['module_functions'] + total['methods'],
        total['unique_names'], total['with_default'], total['vararg'],
        total['kwonly'], total['kwarg']))

    lines.append('')
    lines.append(f'clases con >= {class_detail_min} metodos, por archivo:')
    for entry in report['files']:
        large = [c for c in entry['classes']
                   if len(c['methods']) >= class_detail_min]
        if not large:
            continue
        lines.append(f"  {entry['name']}")
        for owner in sorted(large, key=lambda c: -len(c['methods'])):
            lines.append(
                f"    {owner['name']:<34} {len(owner['methods']):>4} methods"
                f"   :{owner['lineno']}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Inventaria el ORM de un arbol de la referencia.')
    parser.add_argument('--alias', default='odoo19c', choices=sorted(TREE_ROOTS))
    parser.add_argument('--json', default=None,
                        help='ruta del JSON; por defecto outputs/inventory.json')
    args = parser.parse_args(argv)

    root = orm_root(args.alias)
    report = inventory(root)
    report['alias'] = args.alias

    destination = pathlib.Path(args.json) if args.json else (
        RUN_DIR / 'outputs' / f'inventory-{args.alias}.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')

    print(f'root: {root}')  # nombra la clave del reporte, no es prosa
    print('\n'.join(render(report)))
    print(f'\nJSON con todas las firmas: {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
