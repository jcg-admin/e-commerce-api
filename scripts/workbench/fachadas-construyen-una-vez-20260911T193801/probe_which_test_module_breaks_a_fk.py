"""¿Qué módulo de test, al importarse, deja una FK con ``remote_field.model``
en ``None``? Se importan en el orden de colección (alfabético por archivo) y
se toma la foto tras cada uno. Veredicto por contenido: nombra el módulo y
la(s) FK rotas.
"""
import importlib, pathlib, sys, traceback
import django
django.setup()
from django.apps import apps

sys.path.insert(0, str(pathlib.Path('tests').resolve().parent))


def broken():
    out = []
    for m in apps.get_models(include_auto_created=True):
        for f in m._meta.local_fields + m._meta.local_many_to_many:
            rf = getattr(f, 'remote_field', None)
            if rf is not None and getattr(rf, 'model', 'x') is None:
                out.append(f'{m._meta.label}.{f.name}')
    return out


print('base:', broken())
for p in sorted(pathlib.Path('tests/unit/orm').glob('test_*.py')):
    mod = 'tests.unit.orm.' + p.stem
    try:
        importlib.import_module(mod)
    except Exception as exc:  # noqa: BLE001 — la sonda registra, no decide
        print(f'{p.name}: IMPORT-ERROR {type(exc).__name__}: {exc}')
        traceback.print_exc(limit=40)
        continue
    b = broken()
    if b:
        print(f'{p.name}: ROMPE {b}')
        for label in b:
            model_label, fname = label.rsplit('.', 1)
            f = apps.get_model(model_label)._meta.get_field(fname)
            print(f'   tipo={type(f).__name__} to={getattr(f.remote_field, "model", None)!r} '
                  f'related={getattr(f, "related", None)!r} args_keys={sorted(getattr(f, "_args__", {}) )[:12]}')
        break
    print(f'{p.name}: ok')
print('EXIT=0')
