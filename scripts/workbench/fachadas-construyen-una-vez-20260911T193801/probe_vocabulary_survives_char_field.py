"""Sonda B de TASK-API-0417 — ¿el vocabulario de la fuente sobrevive a
``models.CharField.__init__`` hasta ``_args__``?

La pregunta que decide el diseño: si la fachada ``fields.Char`` construye
**siempre** ``models.CharField`` y le pasa ``compute``/``related``/``store``/
``search``/``inverse``/… como kwargs, ¿esas claves llegan a ``_args__`` para
que la costura de ``api@67252948`` las recoja y las derive en
``contribute_to_class``? O ``Field.__init__`` de Django las rechaza / las
pierde.

EL VEREDICTO SE MIDE POR CONTENIDO, NO POR PRESENCIA. Cada caso declara qué
claves espera y el veredicto compara claves presentes contra claves declaradas.
Un ``_args__`` vacío falla; uno con residuo parcial falla nombrando lo que
perdió. ``hasattr(field, '_args__')`` NO es un veredicto.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
import django  # noqa: E402

django.setup()

from django.db import models  # noqa: E402

CASES = {
    'compute_sin_store': dict(compute='_compute_x'),
    'compute_con_store': dict(compute='_compute_x', store=True),
    'related': dict(related='partner_id.name'),
    'related_readonly_false': dict(related='partner_id.name', readonly=False),
    'store_false_explicito': dict(store=False),
    'vocabulario_completo': dict(
        compute='_compute_x', inverse='_inverse_x', search='_search_x',
        related=None, store=False, readonly=True, copy=False,
        related_sudo=True, recursive=False, compute_sudo=True,
        precompute=False, depends=('a', 'b'), index='trigram',
        translate=True, size=64, help='ayuda', required=False,
        string='Etiqueta',
    ),
}

exit_code = 0
for name, declared in CASES.items():
    try:
        field = models.CharField(max_length=5, **declared)
    except TypeError as exc:
        print(f'{name}: CONSTRUCCION FALLA -> {exc}')
        exit_code = 1
        continue
    args = getattr(field, '_args__', None)
    if not isinstance(args, dict):
        print(f'{name}: _args__ no es dict -> {args!r}')
        exit_code = 1
        continue
    missing = sorted(set(declared) - set(args))
    changed = sorted(k for k in declared if k in args and args[k] != declared[k])
    verdict = 'OK' if not missing and not changed else 'FALLA'
    if verdict == 'FALLA':
        exit_code = 1
    print(f'{name}: {verdict} declaradas={len(declared)} presentes='
          f'{len(set(declared) & set(args))} perdidas={missing} '
          f'cambiadas={changed}')
    # Y lo que la costura derivó al construir (antes de contribute_to_class):
    print(f'    store={getattr(field, "store", "<sin atributo>")!r} '
          f'compute={getattr(field, "compute", "<sin>")!r} '
          f'related={getattr(field, "related", "<sin>")!r} '
          f'readonly={getattr(field, "readonly", "<sin>")!r}')
print(f'EXIT={exit_code}')
sys.exit(exit_code)
