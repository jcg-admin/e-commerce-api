#!/usr/bin/env python3
"""Que SON los 38 cuerpos `stub` de la referencia — clasificados, no supuestos.

Por que existe esta sonda
--------------------------
El manifiesto de este run llego a decir que «la mayoria son metodos abstractos
que la fuente stubea a proposito». Eso **no se habia medido**: era una
explicacion con forma de medicion, que es el defecto que
`evidencia-antes-de-afirmar.md` nombra. Esta sonda lo mide.

Lo que descubre, y no es lo que la frase decia
-----------------------------------------------
El discriminador no es la prosa sino el **decorador**. Un metodo con
``@typing.overload`` no es un `stub` sin implementar: es una **declaracion de firma** para el
verificador de tipos, cuyo cuerpo es `...` por construccion del lenguaje, y su
implementacion real esta en el simbolo siguiente del mismo nombre. Contarlo
como «abstracto» confunde el significante (cuerpo vacio) con el significado
(que hace el simbolo).

Quedan tres `bucket`, y el veredicto de cada uno sale del decorador o del `owner`:

- ``overload`` — firma de tipo; la implementacion existe al lado.
- ``other_decorator`` — el decorador cambia lo que el cuerpo significa
  (``classproperty``, ``api.model``, ``api.private``); se listan aparte porque
  ninguno es «no hace nada».
- ``plain`` — sin decorador. Aqui conviven el metodo de base abstracta que la
  subclase implementa y el hook de extension que la fuente deja vacio a
  proposito, y el discriminador entre los dos **si** es medible: si otra clase
  del mismo paquete declara ese nombre con cuerpo sustantivo, el `stub` es la
  base de una jerarquia; si nadie lo declara, es un `stub` que el consumidor
  implementa o no implementa nunca. Eso es lo que ``overridden_elsewhere`` publica.

*Metrica:* cuerpo `stub` segun ``body_class`` del extractor del censo, repartido
por decorador; y para el `bucket` ``plain``, si el nombre reaparece con cuerpo
sustantivo en otra clase de ``odoo/orm``.
*Ciega a:* la jerarquia real — el cruce es por NOMBRE dentro del paquete, no por
MRO, asi que un homonimo de otra rama cuenta como sobreescritura y una
subclase que viva fuera de ``odoo/orm`` (en un addon) no cuenta como ninguna.
Por eso el `bucket` se publica con su `owner` y su linea: el juicio final se hace con
la cita delante, no con el conteo solo.
"""
import importlib.util
import json
import pathlib
import sys
from collections import Counter

RUN_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_inv = _load('_stub_inventory', RUN_DIR / 'inventory_reference_orm.py')


def _bucket(record):
    """El `bucket` de un `stub`, decidido por su decorador."""
    decorators = record['decorators']
    if any(d in ('overload', 'typing.overload') for d in decorators):
        return 'overload'
    return 'other_decorator' if decorators else 'plain'


def _substantive_names(report):
    """``{nombre: [owner]}`` de los llamables con cuerpo sustantivo.

    Es el otro lado del cruce: contra este indice se pregunta si un `stub`
    ``plain`` es la base de una jerarquia o un `stub` que nadie implementa.
    """
    index = {}
    for entry in report['files']:
        callables = list(entry['functions'])
        for owner in entry['classes']:
            callables.extend(owner['methods'])
        for record in callables:
            if record['body'] == 'substantive':
                index.setdefault(record['name'], []).append(
                    f'{entry["name"]}::{record["owner"] or "<module>"}')
    return index


def classify(alias='odoo19c'):
    """Los cuerpos `stub` del ORM de un arbol, repartidos en sus tres `bucket`."""
    report = _inv.inventory(_inv.orm_root(alias))
    substantive = _substantive_names(report)
    stubs = []
    for entry in report['files']:
        callables = list(entry['functions'])
        for owner in entry['classes']:
            callables.extend(owner['methods'])
        for record in callables:
            if record['body'] != 'stub':
                continue
            bucket = _bucket(record)
            stubs.append({
                'file': entry['name'],
                'owner': record['owner'] or '<module>',
                'name': record['name'],
                'lineno': record['lineno'],
                'decorators': record['decorators'],
                'bucket': bucket,
                'overridden_elsewhere': (
                    substantive.get(record['name'], []) if bucket == 'plain'
                    else None),
            })
    stubs.sort(key=lambda s: (s['file'], s['lineno']))
    plain = [s for s in stubs if s['bucket'] == 'plain']
    return {
        'alias': alias,
        'root': str(_inv.orm_root(alias)),
        'total': len(stubs),
        'by_bucket': dict(Counter(s['bucket'] for s in stubs)),
        'plain_implemented_elsewhere':
            sum(1 for s in plain if s['overridden_elsewhere']),
        'plain_not_implemented_in_package':
            sum(1 for s in plain if not s['overridden_elsewhere']),
        'by_file': dict(Counter(s['file'] for s in stubs)),
        'by_owner': dict(Counter(s['owner'] for s in stubs)),
        'stubs': stubs,
    }


def main(argv=None):
    argv = list(argv or [])
    alias = argv[0] if argv else 'odoo19c'
    report = classify(alias)

    destination = RUN_DIR / 'outputs' / f'stub-bodies-{alias}.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(f'{alias}: {report["total"]} cuerpos stub en {report["root"]}\n')
    for bucket, count in sorted(report['by_bucket'].items(), key=lambda p: -p[1]):
        print(f'  {bucket:<16}{count:>4}')
    print('\npor owner:')
    for owner, count in sorted(report['by_owner'].items(), key=lambda p: (-p[1], p[0])):
        print(f'  {owner:<24}{count:>4}')
    print(f'\nde los plain: '
          f'{report["plain_implemented_elsewhere"]} tienen ese nombre'
          f' implementado en otra clase del paquete, '
          f'{report["plain_not_implemented_in_package"]} no')
    print('\ncada uno:')
    for stub in report['stubs']:
        marca = ','.join(stub['decorators']) or '-'
        if stub['bucket'] == 'plain':
            marca = (f'implementado en {len(stub["overridden_elsewhere"])} clase(s)'
                     if stub['overridden_elsewhere'] else 'sin implementacion aqui')
        print(f'  {stub["file"]}:{stub["lineno"]:<6}'
              f'{stub["owner"]}.{stub["name"]:<34}{stub["bucket"]:<16}{marca}')
    print(f'\nsalida: {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
