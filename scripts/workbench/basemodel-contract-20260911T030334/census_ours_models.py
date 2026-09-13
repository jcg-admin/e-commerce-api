#!/usr/bin/env python3
"""Censo de lo que nuestro ``src/orm/models.py`` declara hoy.

Por clase: sus bases, sus atributos de clase con guion bajo, y sus metodos con
firma. Es el lado «nuestro» del criterio: lo que el stack ya trae instalado en
este arbol y basta con llamar.
"""
import ast

SOURCE = 'src/orm/models.py'
text = open(SOURCE).read()
tree = ast.parse(text)
lines = text.splitlines()

classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
print(f'archivo : {SOURCE}  ({len(lines)} lineas)')
print(f'clases  : {len(classes)}')
print()
for c in classes:
    bases = ','.join(ast.unparse(b) for b in c.bases) or '-'
    methods = [n for n in c.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    attrs = [t.id for n in c.body if isinstance(n, ast.Assign)
             for t in n.targets if isinstance(t, ast.Name)]
    print(f'=== {c.name}({bases})  :{c.lineno}-{c.end_lineno}  '
          f'metodos={len(methods)} asignaciones={len(attrs)}')
    for m in methods:
        print(f'    {m.name}({ast.unparse(m.args)})')
    if attrs:
        print(f'    asignaciones: {", ".join(attrs)}')

funcs = [n for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
print()
print(f'funciones de modulo: {len(funcs)}')
for f in funcs:
    print(f'    {f.name}({ast.unparse(f.args)})')
