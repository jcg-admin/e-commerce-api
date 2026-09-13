"""Censo del deletreo de las cadenas ``related=`` DECLARADAS, por AST.

La cifra anterior salió de un grep que también contaba la mención en un
docstring; el denominador era «literales en .py», no «cadenas related».
"""
import ast
import pathlib
import sys

roots = [pathlib.Path('src'), pathlib.Path('addons')]
chains = []
for root in roots:
    if not root.is_dir():
        continue
    for path in root.rglob('*.py'):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg == 'related' and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    chains.append((str(path), node.lineno, kw.value.value))

with_suffix = [c for c in chains if c[2].split('.')[0].endswith('_id')]
print(f'cadenas related= declaradas (AST): {len(chains)}')
print(f'  primer eslabon con sufijo _id (deletreo de la fuente): {len(with_suffix)}')
print(f'  primer eslabon sin sufijo:                             {len(chains) - len(with_suffix)}')
print('--- las que NO llevan el sufijo ---')
for path, lineno, chain in sorted(chains):
    if not chain.split('.')[0].endswith('_id'):
        print(f'  {path}:{lineno}  {chain}')
