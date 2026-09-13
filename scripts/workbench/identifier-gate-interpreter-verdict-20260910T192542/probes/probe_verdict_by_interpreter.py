"""El veredicto del gate de identificadores contra el interprete que lo corre.

La pregunta la fija ``manifest.json``: si el gate da el mismo veredicto sobre el
mismo arbol cuando lo corre el ``python3`` del sistema y cuando lo corre el
interprete del proyecto. Los dos son ``check_identifier_language.py``; lo que
cambia es si el corpus abierto —``spacy-lookups-data``— esta importable.

*Metrica:* ``corpus_available()``, codigo de salida y linea de veredicto del
gate sobre las mismas raices, por interprete.
*Ciega a:* si el desacuerdo es un defecto del gate o de la declaracion de
dependencias — eso lo decide quien lea, no este instrumento; y al resto de
interpretes del contenedor, que no se enumeran.
"""
import json
import pathlib
import subprocess
import sys

API_ROOT = pathlib.Path('/home/user/kaupamex-api')
#: El MECANISMO, en el proveedor.
GATE = pathlib.Path('/home/user/thyrox/src/verify/check_identifier_language.py')
#: El PUNTO DE ENTRADA del consumidor — el que invoca su `.githooks/pre-commit`,
#: y el unico que declara el baseline de deuda heredada de este arbol. Medir el
#: mecanismo directo da exit 2 en los dos interpretes: rehusa sin baseline, asi
#: que no discriminaria nada.
ENTRY_POINT = API_ROOT / 'scripts' / 'check_identifier_language.py'
LEXICON_PACKAGE = 'spacy_lookups_data'

#: Los dos interpretes que se comparan, con el nombre por el que se les cita.
INTERPRETERS = (
    ('system', ['python3']),
    ('project_toolchain', ['uv', 'run', 'python']),
)


def probe(name, argv):
    """Corre el gate con un interprete y devuelve lo que declara."""
    corpus = subprocess.run(
        argv + ['-c', (
            'import importlib.util,sys;'
            f'spec=importlib.util.spec_from_file_location("gate", {str(GATE)!r});'
            'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);'
            'print(sys.version.split()[0]);print(m.corpus_available())'
        )],
        cwd=API_ROOT, capture_output=True, text=True)
    lines = corpus.stdout.split()
    verdict = subprocess.run(argv + [str(ENTRY_POINT)], cwd=API_ROOT,
                             capture_output=True, text=True)
    head = verdict.stdout.strip().splitlines()
    return {
        'interpreter': name,
        'argv': argv,
        'version': lines[0] if lines else None,
        'corpus_available': lines[1] == 'True' if len(lines) > 1 else None,
        'exit_code': verdict.returncode,
        'verdict_line': head[0] if head else (verdict.stderr.strip()[:200] or None),
    }


def declares_lexicon():
    """Que manifiesto declara el corpus abierto, si alguno."""
    found = []
    for manifest in (API_ROOT / 'pyproject.toml',
                     pathlib.Path('/home/user/thyrox/pyproject.toml')):
        if manifest.is_file() and 'spacy-lookups-data' in manifest.read_text():
            found.append(str(manifest))
    installed = subprocess.run(
        ['python3', '-c',
         f'import {LEXICON_PACKAGE} as m;print(m.__file__)'],
        capture_output=True, text=True)
    return {
        'declared_in': found,
        'importable_by_system_python': installed.returncode == 0,
        'installed_at': installed.stdout.strip() or None,
    }


def main():
    result = {
        'mechanism': str(GATE),
        'entry_point': str(ENTRY_POINT),
        'measured_root': str(API_ROOT),
        'by_interpreter': [probe(name, argv) for name, argv in INTERPRETERS],
        'lexicon': declares_lexicon(),
    }
    result['verdicts_agree'] = len({
        entry['exit_code'] for entry in result['by_interpreter']}) == 1
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
