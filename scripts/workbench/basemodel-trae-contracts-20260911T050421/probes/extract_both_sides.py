#!/usr/bin/env python3
"""Extrae, para cada nombre del cubo TRAE, el cuerpo de la referencia y el de
Django, por rango AST (no por ventana fija de ``sed``).

El cubo TRAE dice que el stack declara un simbolo con ese nombre. Eso mide el
SIGNIFICANTE. El veredicto de contrato exige leer los dos cuerpos y compararlos:
que recibe, que devuelve, sobre que opera. Este guion junta el material; el
juicio lo hace quien lo lee.
"""
import argparse
import ast
import json
import os
import pathlib
import sys

MARKER = pathlib.Path('scripts') / 'reference_roots.py'


def consumer_root():
    declared = os.environ.get('THYROX_CONSUMER')
    if declared:
        return pathlib.Path(declared)
    here = pathlib.Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / MARKER).is_file():
            return candidate
    raise SystemExit(f'ERROR - no se halla {MARKER} subiendo desde {here}.')


ROOT = consumer_root()
sys.path.insert(0, str(ROOT / 'scripts'))
import reference_roots as R  # noqa: E402


def bodies(path, class_names=None):
    """Devuelve {clase: {nombre: [(lineno, end_lineno, fuente)]}}.

    ``class_names`` None recorre TODAS las clases del archivo.
    """
    text = pathlib.Path(path).read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    out = {}
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.ClassDef):
            continue
        if class_names is not None and node.name not in class_names:
            continue
        got = out.setdefault(node.name, {})
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([member.lineno] + [d.lineno for d in member.decorator_list])
                got.setdefault(member.name, []).append(
                    (start, member.end_lineno,
                     '\n'.join(lines[start - 1:member.end_lineno])))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--names', required=True,
                        help='Nombres separados por coma.')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    names = [n for n in args.names.split(',') if n]

    reference = pathlib.Path(R.tree('odoo19c')) / 'odoo' / 'orm' / 'models.py'
    django_root = pathlib.Path(__import__('django').__file__).parent
    drf_root = pathlib.Path(__import__('rest_framework').__file__).parent
    sources = {
        'REFERENCIA odoo/orm/models.py': (reference, None),
        'DJANGO db/models/base.py': (django_root / 'db/models/base.py', None),
        'DJANGO db/models/query.py': (django_root / 'db/models/query.py', None),
        'DJANGO db/models/manager.py': (django_root / 'db/models/manager.py', None),
    }
    # DRF es miembro declarado del inventario y su eje es el CONTRATO DEL
    # ENDPOINT. Se recorre entero porque tres nombres del cubo TRAE
    # —``create``, ``update``, ``exists``— existen tambien ahi con otro
    # significado; sin medirlo, el veredicto los daria por el del ORM.
    for module in sorted(drf_root.glob('*.py')):
        sources[f'DRF {module.name}'] = (module, None)
    collected = {label: bodies(path, klasses)
                 for label, (path, klasses) in sources.items()
                 if path.is_file()}

    out = pathlib.Path(args.out)
    with out.open('w', encoding='utf-8') as handle:
        for name in names:
            handle.write(f'{"=" * 78}\nNOMBRE: {name}\n{"=" * 78}\n')
            for label, per_class in collected.items():
                for klass, members in per_class.items():
                    for start, end, source in members.get(name, []):
                        handle.write(f'\n--- {label} :: {klass}.{name} '
                                     f'(lineas {start}-{end}) ---\n{source}\n')
            handle.write('\n')
    resumen = {name: {f'{label}::{klass}': len(members.get(name, []))
                      for label, per_class in collected.items()
                      for klass, members in per_class.items()
                      if members.get(name)}
               for name in names}
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
