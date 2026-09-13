#!/usr/bin/env python3
"""Los DOS niveles del criterio, mas la tercera categoria que el primer intento
confundio con el primer nivel.

    nivel 1  el stack lo trae hecho -- hay un simbolo instalado y basta llamarlo
    nivel 2  el stack tiene con que construirlo -- no hay simbolo, si primitivas

El primer intento pregunto ``hasattr(Model, name)`` DESPUES de ``django.setup()``
con nuestros settings, que importa ``src/orm`` y cuelga simbolos de
``models.Model``. Publico 35 «instalados en el stack» midiendo stack + nuestros
propios parches: el verde no distinguia «Django lo trae» de «ya lo portamos».
Es el sub-patron D de ``metrica-decide-la-conclusion.md`` cometido con el
instrumento recien escrito.

La correccion NO es leer con mas cuidado: es medir Django PRISTINO en un
proceso sin nuestro arbol en ``sys.path``, y tratar la diferencia contra el
proceso cargado como lo que de verdad es — el inventario de lo que este arbol
YA colgo. Esa diferencia es el tercer cubo, y es evidencia, no ruido.
"""
import argparse
import json
import os
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('contract', help='TSV del censo de la referencia')
args = parser.parse_args()

CONTRACT = args.contract
wanted = [line.split('\t')[0] for line in open(CONTRACT)
          if '\t' in line and not line.startswith(' ')]

PRISTINE = '''
import json, sys
from django.db.models import Model, Manager, QuerySet
from django.db.models.base import ModelBase
names = json.loads(sys.stdin.read())
carriers = [("Model", Model), ("ModelBase", ModelBase),
            ("Manager", Manager), ("QuerySet", QuerySet)]
print(json.dumps({n: [label for label, obj in carriers if hasattr(obj, n)]
                  for n in names}))
'''

env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
env['DJANGO_SETTINGS_MODULE'] = ''
pristine = json.loads(subprocess.run(
    ['uv', 'run', 'python', '-c', PRISTINE],
    input=json.dumps(wanted), capture_output=True, text=True, check=True,
    cwd=os.path.dirname(os.path.abspath(__file__)), env=env).stdout)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
sys.path.insert(0, 'src')
import django  # noqa: E402
django.setup()
from django.db.models import Model, Manager, QuerySet  # noqa: E402
from django.db.models.base import ModelBase  # noqa: E402

LOADED = [('Model', Model), ('ModelBase', ModelBase),
          ('Manager', Manager), ('QuerySet', QuerySet)]

stack, attached, absent = [], [], []
for name in wanted:
    if pristine.get(name):
        stack.append((name, ','.join(pristine[name])))
        continue
    here = [label for label, obj in LOADED if hasattr(obj, name)]
    (attached if here else absent).append((name, ','.join(here) or '-'))

print(f'django {django.get_version()} · contrato {len(wanted)} nombres')
print(f'nivel 1 — el stack lo trae hecho          : {len(stack)}')
print(f'          nuestro arbol YA lo colgo        : {len(attached)}')
print(f'nivel 2 — hay que construirlo              : {len(absent)}')
print()
for name, where in stack:
    print(f'STACK   \t{name}\t{where}')
print()
for name, where in attached:
    print(f'COLGADO \t{name}\t{where}')
print()
for name, _ in absent:
    print(f'CONSTRUIR\t{name}')
