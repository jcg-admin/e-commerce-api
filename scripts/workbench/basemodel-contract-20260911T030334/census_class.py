#!/usr/bin/env python3
"""Censo de una clase cualquiera por AST — el mismo mecanismo, otro sujeto.

Un mecanismo con N parametros, no N guiones: la referencia y los binarios del
stack se leen con el mismo instrumento, asi que sus salidas son comparables sin
traducir nada.

Uso: census_class.py <archivo.py> <Clase> [<Clase2> ...]

El rango sale del nodo AST, nunca de una ventana fija de ``sed``.
"""
import argparse
import ast

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('source', help='archivo .py que declara las clases')
parser.add_argument('classes', nargs='+', help='clases a censar')
args = parser.parse_args()

path, targets = args.source, args.classes
text = open(path).read()
tree = ast.parse(text)
lines = text.splitlines()

print(f'archivo: {path}  ({len(lines)} lineas)')
for target in targets:
    klass = next((n for n in ast.walk(tree)
                  if isinstance(n, ast.ClassDef) and n.name == target), None)
    if klass is None:
        print(f'AUSENTE: {target}')
        continue
    bases = ','.join(ast.unparse(b) for b in klass.bases) or '-'
    methods = [n for n in klass.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    attrs = [(t.id, n.lineno) for n in klass.body if isinstance(n, ast.Assign)
             for t in n.targets if isinstance(t, ast.Name)]
    print()
    print(f'=== {target}({bases})  :{klass.lineno}-{klass.end_lineno}  '
          f'metodos={len(methods)} atributos={len(attrs)}')
    for name, line in attrs:
        print(f'  ATTR\t{name}\t{line}\t{lines[line - 1].strip()[:100]}')
    for m in methods:
        deco = ','.join(ast.unparse(d) for d in m.decorator_list) or '-'
        doc = (ast.get_docstring(m) or '').strip().splitlines()
        print(f'  DEF \t{m.name}\t{m.lineno}-{m.end_lineno}\t{deco}\t'
              f'({ast.unparse(m.args)})\t{doc[0][:80] if doc else ""}')
