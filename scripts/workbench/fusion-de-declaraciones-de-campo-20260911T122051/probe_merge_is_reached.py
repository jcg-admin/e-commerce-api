"""M9 — la fusion, ¿NO se llama, o se llama y es un no-op?

``_get_attrs`` esta portado y ``_field_contribute_to_class`` llama a
``_setup_attrs__``, que lo invoca. Declararlo "codigo muerto" sin medirlo
seria concluir sobre el significado leyendo el significante: un metodo que
corre y no hace nada NO es lo mismo que uno al que nadie llama, y la
correccion es distinta en cada caso.

*Metrica:* si ``_get_attrs`` se ejecuta al construir un modelo, con que
``_args__`` de entrada y que ``attrs`` de salida.
*Ciega a:* un campo instalado con ``setattr`` pelado, que no pasa por
``contribute_to_class``.
"""
import os
import sys

import django

sys.path.insert(0, 'src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import models                             # noqa: E402

import fields                                            # noqa: E402

calls = []
_REAL = models.Field._get_attrs


def spy(self, model_class, name):
    salida = _REAL(self, model_class, name)
    calls.append((name, dict(self._args__ or {}), dict(salida)))
    return salida


models.Field._get_attrs = spy


class MergeReachProbe(models.Model):
    label = fields.Char('Label', max_length=8, inverse='_x', recursive=True)

    class Meta:
        app_label = 'base'


models.Field._get_attrs = _REAL

print(f'llamadas a _get_attrs durante el cuerpo de clase: {len(calls)}')
for name, entrada, salida in calls:
    print(f'  campo {name!r}')
    print(f'    _args__ de entrada : {entrada}')
    print(f'    attrs de salida    : {salida}')

field = MergeReachProbe._meta.get_field('label')
print()
print('estado final del campo construido:')
for key in ('inverse', 'recursive', 'store', 'string', 'model_name',
            '_extra_keys__'):
    print(f'    .{key:<14}: {getattr(field, key, "(sin atributo)")!r}')
