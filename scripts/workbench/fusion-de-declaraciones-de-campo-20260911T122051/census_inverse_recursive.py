"""Censo AST de ``inverse=`` y ``recursive=`` en llamadas ``fields.X(...)``.

El grep por linea NO sirve: las dos declaraciones de ``display_name`` que
llevan ``inverse=`` lo llevan en la SEGUNDA linea de la llamada. Medir el
significante (la linea de la declaracion) y concluir sobre el significado
(la llamada) es el sub-patron A.
"""
import ast
import collections
import pathlib
import sys

roots = [pathlib.Path(p) for p in sys.argv[1:]]
por_kw = collections.Counter()
por_tipo = collections.Counter()
display_name = []

for root in roots:
    for path in root.rglob('*.py'):
        try:
            tree = ast.parse(path.read_text(errors='ignore'))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == 'fields'):
                continue
            kws = {k.arg for k in node.keywords if k.arg}
            for name in ('inverse', 'recursive'):
                if name in kws:
                    por_kw[name] += 1
                    por_tipo[(name, func.attr)] += 1

        # Y las redeclaraciones de display_name como campo, por AST
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            for stmt in cls.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                if 'display_name' not in targets:
                    continue
                call = stmt.value
                if not (isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == 'fields'):
                    continue
                kws = sorted(k.arg for k in call.keywords if k.arg)
                display_name.append((str(path), stmt.lineno, cls.name,
                                     call.func.attr, kws))

print('=== display_name redeclarado como campo (AST) ===')
for path, line, cls, tipo, kws in sorted(display_name):
    print(f'{path.split("odoo-19.0/")[-1]}:{line} {cls}  fields.{tipo}({", ".join(kws)})')
print(f'total={len(display_name)}')
con = [d for d in display_name if {'inverse', 'recursive'} & set(d[4])]
print(f'de esas, con inverse= o recursive=: {len(con)}')

print()
print('=== universo de los dos parametros, por AST ===')
for name, n in sorted(por_kw.items()):
    print(f'{name}= : {n}')
print()
print('=== reparto por tipo de campo ===')
for (name, tipo), n in sorted(por_tipo.items(), key=lambda x: (-x[1], x[0])):
    print(f'{name:10s} {tipo:14s} {n}')
