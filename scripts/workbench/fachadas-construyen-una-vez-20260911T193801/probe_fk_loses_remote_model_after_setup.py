"""¿Qué FK pierde ``remote_field.model`` al correr la fase de setup?

Control: se toma la foto de ``remote_field.model`` de toda FK/O2O/M2M antes y
después de ``ensure_field_setup()``. El veredicto es por contenido: nombra
el modelo y el campo cuyo destino pasa a ``None``.
"""
import django
django.setup()
from django.apps import apps
from django.db import models
from orm.model_classes import ensure_field_setup


def snapshot():
    out = {}
    for m in apps.get_models(include_auto_created=True):
        for f in m._meta.local_fields + m._meta.local_many_to_many:
            if getattr(f, 'remote_field', None) is not None:
                out[(m._meta.label, f.name)] = getattr(f.remote_field, 'model', None)
    return out


before = snapshot()
none_before = sorted(k for k, v in before.items() if v is None)
print(f'antes: {len(before)} relacionales; con model=None: {len(none_before)} {none_before[:10]}')
n = ensure_field_setup()
print(f'ensure_field_setup -> {n} campos')
after = snapshot()
lost = sorted(k for k in before if before[k] is not None and after.get(k) is None)
print(f'despues: con model=None: {sum(1 for v in after.values() if v is None)}; perdidos: {len(lost)}')
for k in lost[:20]:
    f = apps.get_model(k[0])._meta.get_field(k[1])
    print(f'  {k[0]}.{k[1]} tipo={type(f).__name__} related={getattr(f, "related", None)!r} setup_done={getattr(f, "_setup_done", None)}')
print(f'EXIT={1 if lost or none_before else 0}')
