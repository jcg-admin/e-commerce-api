"""La poblacion de claves de dict en español, por raiz de kaupamex-api.

El gate recorre los identificadores DECLARADOS por AST; una clave de dict es un
literal y no se declara, asi que queda fuera de su alcance. Antes de extender el
gate hay que saber a cuantas claves alcanzaria y cuantas de ellas son falso
positivo: una extension global mediria el canon del propio proyecto.

*Metrica:* claves de dict literales de tipo ``str`` bajo cada raiz, filtradas por
``spanish_words_in`` del gate — ocurrencias y claves distintas.
*Ciega a:* la clave compuesta en tiempo de ejecucion (``d[nombre] = x``), la que
llega por ``**kwargs``, y la del JSON, que no es Python; y al criterio de si una
clave es contrato externo, que decide quien lee.
"""
import ast
import collections
import importlib.util
import json
import pathlib
import sys

GATE = pathlib.Path('/home/user/thyrox/src/verify/check_identifier_language.py')
API_ROOT = pathlib.Path('/home/user/kaupamex-api')
ROOTS = ('src', 'tests', 'addons', 'scripts')


def load_gate():
    spec = importlib.util.spec_from_file_location('gate', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def string_keys(tree):
    """Las claves literales de tipo str de todo dict del arbol, con su linea."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    yield key.value, key.lineno


def sweep(gate, root):
    hits = collections.Counter()
    occurrences = 0
    files = 0
    for path in sorted((API_ROOT / root).rglob('*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        files += 1
        families = gate.code_suffix_families(
            [name for name, _ in gate.declared_identifiers(tree)])
        for key, _lineno in string_keys(tree):
            if gate.spanish_words_in(key, families):
                hits[key] += 1
                occurrences += 1
    return {
        'root': root,
        'files_parsed': files,
        'occurrences': occurrences,
        'distinct_keys': len(hits),
        'top_keys': hits.most_common(12),
    }


def main():
    gate = load_gate()
    payload = {
        'corpus_available': gate.corpus_available(),
        'by_root': [sweep(gate, root) for root in ROOTS],
    }
    payload['totals'] = {
        'occurrences': sum(r['occurrences'] for r in payload['by_root']),
        'files_parsed': sum(r['files_parsed'] for r in payload['by_root']),
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
