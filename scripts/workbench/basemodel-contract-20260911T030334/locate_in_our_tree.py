#!/usr/bin/env python3
"""Donde declara NUESTRO arbol cada nombre del contrato de la referencia.

Recorre ``src/`` por AST y anota cada declaracion (funcion de modulo o metodo
de clase) cuyo nombre coincida con uno del contrato. Un nombre puede aparecer
en varias duenas: se listan todas, porque el porte disuelve ``BaseModel`` en
mixins y la duena correcta no se deduce del nombre.

Ciega a: un simbolo portado bajo OTRO nombre. Un 0 aqui no prueba ausencia del
mecanismo — prueba ausencia del nombre.
"""
import argparse
import ast
import collections
import os

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('contract', help='TSV del censo de la referencia')
parser.add_argument('--tree', default='src', help='raiz de nuestro arbol')
args = parser.parse_args()

CONTRACT = args.contract
wanted = {line.split('\t')[0] for line in open(CONTRACT)
          if '\t' in line and not line.startswith(' ')}

found = collections.defaultdict(list)
scanned = 0
for base, dirs, files in os.walk(args.tree):
    dirs[:] = [d for d in dirs if d not in {'__pycache__', 'migrations'}]
    for name in files:
        if not name.endswith('.py'):
            continue
        path = os.path.join(base, name)
        scanned += 1
        try:
            tree = ast.parse(open(path).read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if (isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and child.name in wanted):
                        found[child.name].append(
                            f'{path}:{child.lineno} {node.name}')
        for node in tree.body:
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name in wanted):
                found[node.name].append(f'{path}:{node.lineno} <modulo>')

print(f'contrato: {len(wanted)} nombres · archivos recorridos: {scanned}')
print(f'presentes por nombre: {len(found)} · ausentes: {len(wanted) - len(found)}')
print()
for name in sorted(wanted):
    if name in found:
        print(f'PRESENTE\t{name}\t{" | ".join(found[name])}')
print()
for name in sorted(wanted - set(found)):
    print(f'AUSENTE \t{name}')
