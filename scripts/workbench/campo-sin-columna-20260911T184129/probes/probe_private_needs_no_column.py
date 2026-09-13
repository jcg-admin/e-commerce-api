"""¿Basta ``private_only=True`` para un campo sin columna, o hace falta también
``column = None``?

El precedente del stack es ``GenericForeignKey``: declara **las dos cosas**
(``.venv/…/django/contrib/contenttypes/fields.py``)::

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, private_only=True, **kwargs)

    def get_attname_column(self):
        attname, column = super().get_attname_column()
        return attname, None

Y ``Field.set_attributes_from_name`` deriva de ahí la concreción::

    self.attname, self.column = self.get_attname_column()
    self.concrete = self.column is not None          # fields/__init__.py:940

La medición previa de este banco hermano (``recoleccion-de-definiciones``) miró
el estado de migración y ``local_fields``; **no** miró el camino de consulta.
Esta sonda lo mide contra PostgreSQL real, que es donde la diferencia aparece.

Tres brazos sobre la MISMA tabla, que sólo tiene ``id`` y ``plain``:

- **A** — ``CharField`` llano. Control positivo: DEBE ir y volver.
- **B** — contribuido con ``private_only=True`` y su columna intacta.
- **C** — contribuido con ``private_only=True`` y ``column = None``.

El veredicto de cada brazo es ``create()`` + ``first()`` contra la base. Si A
fallara, el instrumento está roto y ningún otro resultado vale.
"""
import django

django.setup()

from django.db import connection, models, transaction  # noqa: E402

TABLE = 'probe_campo_sin_columna'


class SinColumna(models.CharField):
    """Un ``CharField`` que declara no tener columna — la forma de ``GenericForeignKey``."""

    def get_attname_column(self):
        attname, _ = super().get_attname_column()
        return attname, None


def build(label, extra=None):
    """Declara un modelo sobre la tabla de sonda y le añade el campo del brazo."""
    meta = type('Meta', (), {'app_label': 'test_orm', 'db_table': TABLE,
                             'managed': False})
    model = type(label, (models.Model,), {
        '__module__': __name__,
        'Meta': meta,
        'plain': models.CharField(max_length=32),
    })
    if extra is not None:
        name, field = extra
        field.contribute_to_class(model, name, private_only=True)
    return model


def describe(model, name):
    field = model._meta.get_field(name)
    meta = model._meta
    return {
        'column': field.column,
        'concrete': field.concrete,
        'en_concrete_fields': field in meta.concrete_fields,
        'en_local_fields': field in meta.local_fields,
        'en_private_fields': field in meta.private_fields,
    }


def exercise(model):
    """Ida y vuelta real. Devuelve (veredicto, detalle)."""
    try:
        with transaction.atomic():
            model.objects.create(plain='x')
            fila = model.objects.first()
            return ('PASA', f'first() -> plain={fila.plain!r}')
    except Exception as exc:                       # noqa: BLE001 — el fallo ES el dato
        return ('FALLA', f'{type(exc).__name__}: {str(exc).splitlines()[0]}')


def main():
    with connection.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS {TABLE}')
        cur.execute(f'CREATE TABLE {TABLE} '
                    '(id bigserial PRIMARY KEY, plain varchar(32) NOT NULL)')
    try:
        brazos = [
            ('A  CharField llano (control positivo)', build('ProbeA'), None),
            ('B  private_only=True, columna intacta',
             build('ProbeB', ('extra', models.CharField(max_length=32, null=True))),
             'extra'),
            ('C  private_only=True + column=None',
             build('ProbeC', ('extra', SinColumna(max_length=32, null=True))),
             'extra'),
        ]
        for etiqueta, model, name in brazos:
            veredicto, detalle = exercise(model)
            print(f'{etiqueta:40} {veredicto:5} {detalle}')
            if name is not None:
                for clave, valor in describe(model, name).items():
                    print(f'{"":40}   {clave:20} {valor!r}')
            columnas = [f.column for f in model._meta.concrete_fields]
            print(f'{"":40}   {"SELECT pide":20} {columnas!r}')
    finally:
        with connection.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS {TABLE}')


if __name__ == '__main__':
    main()
