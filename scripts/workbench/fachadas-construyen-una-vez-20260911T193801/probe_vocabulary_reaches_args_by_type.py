"""Sonda F — ¿el vocabulario de la fuente sobrevive al constructor de CADA tipo?

Premisa que TASK-API-0417 necesita medir antes de retirar el enrutado: si las
fachadas dejan de elegir clase y pasan ``store=``/``related=``/``compute=``
directo al constructor de Django, ``_field_init_with_copy`` tiene que
recogerlos en ``_args__`` y retirarlos antes de que los vea el ``__init__``
real. El parche cuelga de ``models.Field.__init__``, y **los tipos
relacionales no lo llaman primero**: ``ForeignKey.__init__`` y
``ManyToManyField.__init__`` tienen cuerpo propio que puede rechazar la clave
antes de llegar al ancestro.

Métrica: por tipo, las claves del vocabulario presentes en ``field._args__``
tras construir, y los atributos derivados tras ``_setup_attrs__``.
Ciega a: el camino de lectura del campo — sólo mide la construcción y la
derivación, no ``__get__``.
"""
import os
import sys

import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.db import models  # noqa: E402

import orm.fields  # noqa: E402,F401  (instala la costura)

VOCABULARY = ('store', 'related', 'compute', 'readonly', 'compute_sudo', 'copy')


class _Target(models.Model):
    """El comodelo de las relacionales — un modelo llano, sin costura propia."""

    label = models.CharField(max_length=32)

    class Meta:
        app_label = 'base'


def _build(name, factory, extra):
    """Construye el campo con el vocabulario dentro y devuelve el veredicto."""
    kwargs = dict(extra)
    kwargs.update({'store': False, 'related': 'owner_id.label'})
    try:
        field = factory(**kwargs)
    except TypeError as error:
        return name, 'RECHAZA-CONSTRUCTOR', {'error': str(error)}, {}
    recorded = {key: field._args__[key]
                for key in VOCABULARY if key in getattr(field, '_args__', {})}
    return name, 'CONSTRUYE', recorded, field


CASES = (
    ('CharField', models.CharField, {'max_length': 32}),
    ('TextField', models.TextField, {}),
    ('JSONField', models.JSONField, {}),
    ('BooleanField', models.BooleanField, {}),
    ('IntegerField', models.IntegerField, {}),
    ('FloatField', models.FloatField, {}),
    ('DecimalField', models.DecimalField, {'max_digits': 8, 'decimal_places': 2}),
    ('BinaryField', models.BinaryField, {}),
    ('ImageField', models.ImageField, {}),
    ('ForeignKey', models.ForeignKey,
     {'to': _Target, 'on_delete': models.CASCADE}),
    ('ManyToManyField', models.ManyToManyField, {'to': _Target}),
)


def main():
    ok = 0
    for name, factory, extra in CASES:
        label, verdict, recorded, field = _build(name, factory, extra)
        missing = [key for key in ('store', 'related') if key not in recorded]
        if verdict == 'CONSTRUYE' and not missing:
            ok += 1
            print(f'  {label:18s} OK          _args__={recorded}')
        elif verdict == 'CONSTRUYE':
            print(f'  {label:18s} PIERDE      ausentes={missing} '
                  f'_args__={recorded}')
        else:
            print(f'  {label:18s} {verdict}  {recorded["error"][:90]}')
    total = len(CASES)
    print(f'VEREDICTO vocabulario_por_tipo: {"OK" if ok == total else "FALLA"} '
          f'({ok} de {total})')
    return 0 if ok == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
