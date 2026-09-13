#!/usr/bin/env python3
"""Gate: un metodo portado escribe por el mismo CAMINO que su contraparte.

Es el **primer eje** declarado sobre ``counterpart_body.py``, el motor que
compara una propiedad del cuerpo contra la de la fuente. Aqui no vive ningun
recorrido: solo los dos vocabularios y como se nombra cada desacuerdo. El
siguiente eje —si transacciona, si emite senales, por que via lee— se declara
igual, en veinte lineas, sin tocar el motor.

El defecto que mide nacio en H-API-1058 y en la tarea #345.
``_reflect_models`` escribia con ``update_or_create`` —que pasa por ``save()``
y por tanto por la guarda de los cuatro campos inmodificables— mientras la
fuente escribe con ``upsert_en``, SQL con ``ON CONFLICT``, deliberadamente
fuera del alcance de su ``write``. Se descubrio por casualidad: de los 29
gates del repo, ninguno leia el cuerpo de un metodo.

Lo que compara no es la llamada literal —los dos vocabularios no comparten un
solo nombre— sino **si la escritura pasa por el enganche del ORM**, que es
donde viven las guardas, las senales y las validaciones.

Y la direccion no es simetrica:

- **cruza una guarda que la fuente esquiva** — la fuente baja a SQL a
  proposito; nosotros pasamos por ``save()`` y heredamos una guarda que alli
  no existe. Es H-API-1058.
- **se salta un enganche que la fuente usa** — la inversa: perdemos las
  validaciones o efectos que su ``create``/``write`` si aplica.

Ninguna es automaticamente un defecto: hay divergencias de stack legitimas.
Lo que no es legitimo es que la diferencia sea **silenciosa**.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import counterpart_body as engine  # noqa: E402
import reference_roots  # noqa: E402

VIA_ORM = 'por el enganche'
BELOW_ORM = 'por debajo'
MIXED = engine.BOTH
NO_WRITE = engine.ABSENT
Vocabulary = engine.Vocabulary

CROSSES_GUARD = 'cruza una guarda que la fuente esquiva'
SKIPS_HOOK = 'se salta un enganche que la fuente usa'

#: Nuestro lado. Los cuatro primeros entran por ``Model.save()``, donde este
#: arbol instala sus guardas; los seis segundos emiten SQL sin pasar por el.
OURS = Vocabulary(
    'nuestro',
    frozenset({'save', 'create', 'update_or_create', 'get_or_create'}),
    frozenset({'bulk_create', 'bulk_update', 'update', 'raw',
               'execute', 'executemany'}),
)

#: El de la fuente. ``upsert_en`` y ``query_insert`` son sus escritores por
#: debajo del ORM; ``execute_query`` y ``SQL`` bajan al motor directamente.
REFERENCE = Vocabulary(
    'la fuente',
    frozenset({'create', 'write', 'unlink', 'copy'}),
    frozenset({'upsert_en', 'query_insert', 'query_update', 'execute_query',
               'execute_query_dict', 'SQL', 'execute'}),
)

WRITE_PATH = engine.Axis(
    name='camino de escritura',
    ours=OURS,
    reference=REFERENCE,
    first_name=VIA_ORM,
    second_name=BELOW_ORM,
    directions={
        (VIA_ORM, BELOW_ORM): CROSSES_GUARD,
        (MIXED, BELOW_ORM): CROSSES_GUARD,
        (BELOW_ORM, VIA_ORM): SKIPS_HOOK,
        (MIXED, VIA_ORM): SKIPS_HOOK,
    },
)

BASELINE = pathlib.Path(__file__).resolve().parent / 'write_path_baseline.txt'


def classify(node, vocabulary):
    """La categoria del cuerpo en este eje. Envoltorio del motor."""
    return engine.classify(node, vocabulary, WRITE_PATH)


def direction(ours, theirs):
    """El nombre del desacuerdo en este eje, o ``None``."""
    return engine.direction(ours, theirs, WRITE_PATH)


def scan_with_scope(paths):
    return engine.compare(paths, WRITE_PATH)


def scan(paths):
    return scan_with_scope(paths)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', default=None,
                        help='archivos o raices; por defecto src/')
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si hay hallazgos fuera del baseline')
    parser.add_argument('--write-baseline', action='store_true',
                        help='congelar los hallazgos actuales')
    args = parser.parse_args(argv)

    # Precondicion declarada: sin la raiz de la referencia NO se emite conteo.
    # Un 0 contra un arbol ausente seria un verde falso — el sub-patron D de
    # metrica-decide-la-conclusion.md.
    reference_roots.require()

    files = list(engine.tree_files(args.paths or ['src']))
    findings, scope = scan_with_scope(files)

    if args.write_baseline:
        total = engine.write_baseline(
            BASELINE, findings,
            'Deuda heredada del camino de escritura, congelada.')
        print(f'baseline escrito: {total} entrada(s)')
        return 0

    baseline = engine.load_baseline(BASELINE)
    fresh = [f for f in findings if f.key not in baseline]

    for finding in sorted(fresh, key=lambda f: f.key):
        print(f'{finding.key}\n'
              f'    {finding.direction}\n'
              f'    nuestro: {finding.ours} · la fuente: {finding.theirs}')

    print(f'check_write_path: {len(fresh)} hallazgo(s) nuevo(s) '
          f'({len(findings)} en total; {len(baseline)} en baseline) '
          f'(alcance medido: {scope.pairs_compared} par(es) de metodo que '
          f'escriben en ambos lados, sobre {scope.files_with_counterpart} '
          f'archivo(s) con contraparte de {scope.files_scanned} recorrido(s); '
          f'{scope.pairs_indeterminate} indeterminado(s) por granularidad de '
          f'metodo)')
    return 1 if (args.strict and fresh) else 0


if __name__ == '__main__':
    raise SystemExit(main())
