#!/usr/bin/env python3
"""check_identifier_language.py — delega en el gate de thyrox.

El mecanismo (AST, léxico cerrado, corpus) se mudó a THYROX (DEC-04,
actualizar-agentic-ai-thyrox): ``thyrox: src/verify/check_identifier_language.py``.
Este archivo se conserva porque sus consumidores lo invocan **por su ruta** —
el `.githooks/pre-commit` (gate 4) y `thyrox: src/corpus/migration_report.py`
(fila `check_identifier_language`)— y reapuntarlos es un cambio aparte del
porte del mecanismo.

Lo único que este stub aporta que el mecanismo por sí solo no tiene: EL
BASELINE de deuda heredada de **este** árbol. El baseline es parámetro del
consumidor, no del proveedor (:ref:`h-docs-1072` — un baseline ausente leído
como vacío haría ver como nueva a los 1268 identificadores ya congelados), así
que se declara aquí, donde vive el archivo, y se exporta para ESTA invocación
—el proceso gana sobre el ``.env``, que es como ``env_value`` ya resuelve la
precedencia—.

Sin thyrox alcanzable **NO se emite un veredicto**: se rehúsa con exit 2. Un 0
aquí no distinguiría «ningún identificador incumple» de «no pude medir», que
es el sub-patrón D de ``metrica-decide-la-conclusion.md``.

Y el MECANISMO corre con el intérprete del PROVEEDOR, no con el que este
puente herede. Sus dependencias —el corpus abierto entre ellas— las declara
``thyrox: pyproject.toml``, así que viven en el entorno de thyrox y en ningún
otro. Medido antes de cerrarlo: con ``sys.executable`` el mismo gate, sobre el
mismo árbol y el mismo baseline, daba exit 1 con 2994 incumplidores bajo
``python3`` y exit 0 bajo ``uv run python`` — el veredicto lo decidía quién
invocaba. La regla de reparto y su rehúse viven en
``thyrox: src/lib/toolchain.sh``; aquí se consultan, no se reimplementan.
"""
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def thyrox_gate():
    """La ruta del gate del proveedor — variable declarada, luego hermano.

    Si THYROX_ROOT SE DECLARA, es la ÚNICA fuente: no cae al hermano si no
    resuelve. La variable existe para que el consumidor decida dónde está
    el proveedor — una declarada-e-inexistente que caiga por detrás la
    vuelve decorativa (:ref:`h-docs-1145`, reportado por el coordinador
    tras medir ``THYROX_ROOT=/no/existe`` con un hermano presente y ver el
    mismo resultado que sin declarar nada)."""
    declared = os.environ.get('THYROX_ROOT')
    if declared:
        gate = pathlib.Path(declared) / 'src' / 'verify' / 'check_identifier_language.py'
        return gate if gate.is_file() else None
    # Clon hermano: <arbol>/thyrox junto a <arbol>/kaupamex-api — SOLO
    # cuando THYROX_ROOT no se declaró en absoluto.
    gate = HERE.parents[1] / 'thyrox' / 'src' / 'verify' / 'check_identifier_language.py'
    return gate if gate.is_file() else None


def provider_interpreter(gate):
    """El intérprete del proveedor, preguntado a su propio selector.

    Se consulta ``thyrox: src/lib/toolchain.sh`` en vez de derivar la ruta aquí:
    el reparto —mecanismo al proveedor, sujeto al consumidor— es una decisión
    del proveedor, y una segunda copia de la regla en este puente derivaría en
    silencio. Devuelve ``None`` cuando el selector rehúsa, y su mensaje ya
    nombra el remedio.
    """
    # El gate vive en `<raiz>/src/verify/`; su hermano `lib/` cuelga del mismo
    # `src/`. Se asciende desde el ARCHIVO que ya se resolvió, no desde este
    # puente: el puente no sabe dónde está thyrox, y el gate sí.
    selector = gate.parent.parent / 'lib' / 'toolchain.sh'
    if not selector.is_file():
        print(f'FATAL: no se encontró el selector de toolchain en {selector}.',
              file=sys.stderr)
        return None
    asked = subprocess.run(
        ['bash', '-c',
         f'source {selector} && thyrox_toolchain_provider_python'],
        capture_output=True, text=True)
    if asked.returncode != 0:
        sys.stderr.write(asked.stderr)
        return None
    return asked.stdout.strip()


def main(argv):
    gate = thyrox_gate()
    if gate is None:
        print('FATAL: no se encontró thyrox/src/verify/check_identifier_language.py.',
              file=sys.stderr)
        print('       Declara THYROX_ROOT o clona thyrox como hermano.', file=sys.stderr)
        print('       NO se emite veredicto: un 0 aquí sería un verde falso.', file=sys.stderr)
        return 2

    env = dict(os.environ)
    # El baseline de ESTE árbol. `setdefault`: si quien invoca ya lo declaró
    # (p. ej. para probar contra otro archivo), esa declaración manda.
    env.setdefault('IDENTIFIER_LANGUAGE_BASELINE',
                    str(HERE / 'identifier_language_baseline.txt'))
    interpreter = provider_interpreter(gate)
    if interpreter is None:
        return 2
    return subprocess.call([interpreter, str(gate), *argv[1:]], env=env)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
