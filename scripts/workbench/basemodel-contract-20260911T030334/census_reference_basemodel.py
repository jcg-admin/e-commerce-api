#!/usr/bin/env python3
"""Censo del contrato de ``BaseModel`` en la referencia.

Emite, por metodo declarado en la clase: nombre, firma completa, decoradores,
rango de lineas y la primera linea del docstring. NO emite veredicto — emite el
material contra el que se construye.

El rango de lineas se toma del nodo AST (``lineno``/``end_lineno``), nunca de
una ventana fija: leer con ``sed -n 'A,Bp'`` trunca el cuerpo.
"""
import argparse
import ast
import os

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('target', help='la clase de la referencia a censar')
parser.add_argument('--relative', default='odoo/orm/models.py',
                    help='ruta dentro del arbol de la referencia')
args = parser.parse_args()

root = os.environ.get('ODOO19C')
if not root:
    raise SystemExit(
        'ERROR — falta ODOO19C. Declararla con '
        '`eval "$(python3 scripts/reference_roots.py --env)"`. NO se emite '
        'censo: un censo vacio aqui seria un verde falso.')
SOURCE = os.path.join(root, args.relative)
TARGET = args.target

text = open(SOURCE).read()
tree = ast.parse(text)

klass = next((n for n in tree.body
              if isinstance(n, ast.ClassDef) and n.name == TARGET), None)
if klass is None:
    raise SystemExit(f'ERROR — {TARGET} no esta en {SOURCE}. NO se emite conteo.')

print(f'archivo    : odoo/orm/models.py')
print(f'clase      : {klass.name}  (lineas {klass.lineno}-{klass.end_lineno})')

attrs = [(t.id, n.lineno) for n in klass.body if isinstance(n, ast.Assign)
         for t in n.targets if isinstance(t, ast.Name) and t.id.startswith('_')]
print(f'atributos de clase: {len(attrs)}')
for name, line in attrs:
    print(f'   :{line}  {text.splitlines()[line - 1].strip()}')

methods = [n for n in klass.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
print(f'metodos declarados: {len(methods)}')
print()
for m in methods:
    deco = ','.join(ast.unparse(d) for d in m.decorator_list) or '-'
    doc = (ast.get_docstring(m) or '').strip().splitlines()
    first = doc[0][:90] if doc else ''
    sig = ast.unparse(m.args)
    print(f'{m.name}\t{m.lineno}-{m.end_lineno}\t{deco}\t({sig})\t{first}')
