"""Coste de un descriptor de NO datos frente a uno de DATOS, con el almacén lleno.

La pregunta que decide el porte: el 3.12x de ``scripts/evidence/medicion-211-descriptor.txt``
se atribuye a declarar ``__set__`` —que convierte al descriptor en uno de DATOS y
por tanto gana sobre ``instance.__dict__``—. Si un descriptor de NO datos
(``__get__`` solo) NO cuesta nada con el almacén lleno, entonces la caché del ORM
se puede consultar en el fallo del almacén sin pagar el camino caliente.

Metrica: nanosegundos por ``row.label`` sobre una fila cuyo ``__dict__`` YA
contiene ``label``, que es el camino caliente del ORM.
Ciega a: el coste del fallo del almacén (ahí el cuerpo del descriptor sí corre,
y es el caso que este porte quiere habilitar, no abaratar).
"""
import timeit

REPETITIONS = 300_000


class NonDataDescriptor:
    """``__get__`` solo — el almacén de la instancia gana."""

    def __init__(self, name):
        self.name = name

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        raise AssertionError('unreachable while __dict__ holds the value')


class DataDescriptor:
    """El mismo cuerpo MÁS ``__set__``: pasa a ser descriptor de DATOS."""

    def __init__(self, name):
        self.name = name

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value


def seeded(namespace):
    row = type('Row', (), namespace)()
    row.__dict__['label'] = 'seeded'
    return row


def measure(label, row):
    seconds = timeit.timeit('row.label', globals={'row': row}, number=REPETITIONS)
    per_read = seconds / REPETITIONS * 1e9
    print(f'{label:<34} {per_read:8.1f} ns/lectura')
    return per_read


if __name__ == '__main__':
    print(f'lecturas por caso: {REPETITIONS}')
    bare = measure('atributo llano (sin descriptor)', seeded({}))
    non_data = measure('descriptor de NO datos', seeded({'label': NonDataDescriptor('label')}))
    data = measure('descriptor de DATOS (__set__)', seeded({'label': DataDescriptor('label')}))
    print()
    print(f'NO datos contra llano : {non_data / bare:.2f}x')
    print(f'DATOS   contra llano : {data / bare:.2f}x')
