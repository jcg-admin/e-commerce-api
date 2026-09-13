"""Sonda de #351 — ¿nuestro ``model_create_multi`` hace lo que el de la
referencia (``odoo19c: odoo/orm/decorators.py:357-371``): envolver el método,
convertir un ``Mapping`` en ``[vals]``, dejar pasar la lista y marcar
``_api_model``? Control: el stub actual sólo marca, así que debe dar FALLA.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from orm import decorators  # noqa: E402


class Probe:
    @classmethod
    @decorators.model_create_multi
    def create(cls, vals_list, using=None):
        return ('called', vals_list, using)


results = {}
try:
    results['mapping_becomes_list'] = Probe.create({'a': 1}) == ('called', [{'a': 1}], None)
except Exception as exc:  # noqa: BLE001
    results['mapping_becomes_list'] = f'EXC {type(exc).__name__}: {exc}'
try:
    results['list_passes_through'] = Probe.create([{'a': 1}, {'b': 2}]) == ('called', [{'a': 1}, {'b': 2}], None)
except Exception as exc:  # noqa: BLE001
    results['list_passes_through'] = f'EXC {type(exc).__name__}: {exc}'
try:
    results['kwargs_pass_through'] = Probe.create({'a': 1}, using='x') == ('called', [{'a': 1}], 'x')
except Exception as exc:  # noqa: BLE001
    results['kwargs_pass_through'] = f'EXC {type(exc).__name__}: {exc}'
inner = Probe.__dict__['create'].__func__
results['api_model_flag'] = getattr(inner, '_api_model', None) is True
results['wrapped_keeps_name'] = inner.__name__ == 'create'
for key, value in results.items():
    print(f"{key}: {'OK' if value is True else 'FALLA ' + str(value)}")
ok = all(v is True for v in results.values())
print('VEREDICTO model_create_multi:', 'OK' if ok else 'FALLA')
raise SystemExit(0 if ok else 1)
