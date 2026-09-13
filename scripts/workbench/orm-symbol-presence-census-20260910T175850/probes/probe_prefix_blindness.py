#!/usr/bin/env python3
"""Cuanta de la «ausencia» del censo la produce el emparejador, no el arbol.

``resolve`` conoce tres prefijos de disolucion —``_field_``, ``_model_``,
``_registry_``— derivados al resolver ``fields.py``. Esta sonda mide, sin
tocar el censo, cuantos de sus ausentes casarian bajo el prefijo que CADA
archivo usa de verdad, descubierto por sufijo y no por lista.
"""
import json, pathlib, sys
RUN = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUN))
from census_symbol_presence import declared_symbols, REPO, MIRRORED_ROOTS, resolve  # noqa

report = json.loads((RUN / 'outputs' / 'census.json').read_text())
pairs = {label: (o, r) for label, o, r in MIRRORED_ROOTS}
recovered_total = absent_total = 0
rows = []
for row in report:
    if not row['reference_file']:
        continue
    ours = {s['name'] for s in declared_symbols(REPO / row['file'])}
    reference = [s['name'] for s in declared_symbols(pathlib.Path(row['reference_file']))]
    absent = [n for n in reference if resolve(n, ours) is None]
    # El sufijo manda: `X` casa con `<lo que sea>_X` o `<lo que sea>X`.
    recovered = [n for n in absent
                 if any(o.endswith('_' + n.lstrip('_')) or o.endswith(n) for o in ours)]
    absent_total += len(absent); recovered_total += len(recovered)
    if recovered:
        rows.append((len(recovered), len(absent), row['file'], recovered[:4]))
for count, absent, path, sample in sorted(rows, reverse=True)[:12]:
    print(f'  {count:>4} de {absent:>4}  {path}  {sample}')
print(f'\nausentes del censo: {absent_total}')
print(f'recuperables por SUFIJO: {recovered_total} '
      f'({100*recovered_total/absent_total:.0f} %)')
print(f'ausencia tras descontar: {absent_total - recovered_total}')
