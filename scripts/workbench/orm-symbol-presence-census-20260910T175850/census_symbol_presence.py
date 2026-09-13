#!/usr/bin/env python3
"""Censo de PRESENCIA con firma de las raices espejadas, unido a la referencia.

El eje que este instrumento anade
---------------------------------
Los cinco instrumentos que ya existen miden **ausencia**: que simbolo de la
referencia no aparece en nuestro archivo. Su criterio de cierre —«0 ausentes y
0 fuera de sitio»— lo satisface un arbol de firmas vacias, porque ninguno mira
el CUERPO. La columna que discrimina aqui es ``body``.

Por que un extractor nuevo y no ``scripts/compare_reference_symbols.py``
------------------------------------------------------------------------
Su ``inventory()`` ya da los metodos por clase con ``lineno``, y sirve para lo
que fue escrito: comparar conjuntos de nombres. Lo que **no** da es (a) la
FIRMA —nombres de parametro en orden, cuales son opcionales, varargs y
kw-only— ni (b) la CLASE DE CUERPO. Esos dos son exactamente los ejes de este
censo, asi que reusarlo obligaria a re-parsear igualmente cada archivo.

Lo que si se reusa, sin copiar
-------------------------------
- ``scripts/reference_roots.py`` — las cuatro raices de ``odoo-tools``. NO se
  teclea ninguna ruta: el arbol de 19 esta triplicado y un literal a mano cae
  en un directorio que no existe (medido: la segunda raiz de 19c escrita con
  tres segmentos da 0 addons; con cuatro, 24).
- ``scripts/check_mirrored_roots.py`` — ``FIXED_MIRRORED_ROOTS``, el par
  nuestro-referencia por raiz.
- ``scripts/workbench/orm-rename-resolution-20260910T083919/resolve_renames.py``
  — ``resolve``, que reconoce el prefijo de disolucion de este arbol
  (``_field_``, ``_model_``, ``_registry_``). Sin el, los 91 simbolos que este
  arbol disolvio de ``class Field`` se cuentan como ausentes.
"""
import ast
import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
RUN_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, relative_path):
    """Carga un modulo por ruta — la via que este arbol ya usa para sus gates."""
    spec = importlib.util.spec_from_file_location(name, REPO / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_mirrored = _load('_census_mirrored', 'scripts/check_mirrored_roots.py')
_renames = _load(
    '_census_renames',
    'scripts/workbench/orm-rename-resolution-20260910T083919/resolve_renames.py')

MIRRORED_ROOTS = _mirrored.FIXED_MIRRORED_ROOTS
resolve = _renames.resolve

#: Las raices que este censo mide. La iniciativa las declara prioritarias
#: porque de ellas dependen los modelos.
CENSUS_ROOTS = ('src/orm', 'src/tools')


# --- los dos ejes nuevos ---------------------------------------------------

def signature_of(node):
    """El CONTRATO que la firma declara, sin los valores del cuerpo.

    Se descarta el receptor (``self``/``cls``): no es parte del contrato, y
    conservarlo haria que un metodo no casara nunca con su equivalente de
    modulo — que es justo la forma que este arbol usa al disolver una clase.

    Del default se guarda la BANDERA, no el valor: lo que el contrato declara
    es que el parametro es opcional. Guardar el valor haria divergir dos firmas
    identicas porque una constante cambio de nombre.
    """
    args = node.args
    positional = [a.arg for a in (*args.posonlyargs, *args.args)]
    if positional and positional[0] in ('self', 'cls'):
        positional = positional[1:]
    total = len(args.posonlyargs) + len(args.args)
    offset = total - len(positional)
    defaults = [False] * total
    for index in range(len(args.defaults)):
        defaults[total - len(args.defaults) + index] = True
    return {
        'params': positional,
        'has_default': defaults[offset:],
        'vararg': args.vararg.arg if args.vararg else None,
        'kwonly': [a.arg for a in args.kwonlyargs],
        'kwarg': args.kwarg.arg if args.kwarg else None,
    }


def _is_bare_not_implemented(statement):
    """``raise NotImplementedError`` / ``raise NotImplementedError()`` a secas.

    Un ``raise`` con MENSAJE tambien cuenta: el mensaje es documentacion del
    hueco, no cuerpo. Lo que NO cuenta es un ``raise`` dentro de una rama —
    eso lo decide el llamador contando statements, no esta funcion.
    """
    if not isinstance(statement, ast.Raise) or statement.exc is None:
        return False
    target = statement.exc
    if isinstance(target, ast.Call):
        target = target.func
    return isinstance(target, ast.Name) and target.id == 'NotImplementedError'


def body_class(node):
    """``stub`` o ``substantive`` — se computa del NODO, no del texto.

    Un cuerpo es ``stub`` cuando, retirado el docstring inicial, queda
    **exactamente** una de estas formas, o ninguna:

    - nada (solo docstring)   - ``pass``   - ``...``
    - ``raise NotImplementedError`` (con o sin mensaje)
    - ``return`` pelado o ``return None``

    Todo lo demas es ``substantive``, incluido un cuerpo que solo delega en
    ``super()``: delegar no es no hacer nada — el argumento con que delega es
    la decision que ese cuerpo toma.
    """
    body = [s for s in node.body
            if not (isinstance(s, ast.Expr)
                    and isinstance(s.value, ast.Constant)
                    and isinstance(s.value.value, str))]
    if not body:
        return 'stub'
    if len(body) > 1:
        return 'substantive'
    only = body[0]
    if isinstance(only, ast.Pass):
        return 'stub'
    if (isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant)
            and only.value.value is Ellipsis):
        return 'stub'
    if _is_bare_not_implemented(only):
        return 'stub'
    if isinstance(only, ast.Return) and (
            only.value is None
            or (isinstance(only.value, ast.Constant) and only.value.value is None)):
        return 'stub'
    return 'substantive'


# --- el recorrido ----------------------------------------------------------

def declared_symbols(path):
    """Los simbolos que un archivo DECLARA, con firma, cuerpo y decoradores.

    Recorre las funciones de modulo, las clases y sus metodos. Un simbolo
    anidado dentro de una funcion NO entra: es detalle de implementacion, no
    superficie, y contarlo inflaria el censo con cierres.
    """
    path = pathlib.Path(path)
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, OSError):
        return []
    records = []

    def function_record(node, owner):
        return {
            'kind': 'method' if owner else 'function',
            'owner': owner,
            'name': node.name,
            'lineno': node.lineno,
            'signature': signature_of(node),
            'body': body_class(node),
            'decorators': [ast.unparse(d) for d in node.decorator_list],
        }

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            records.append(function_record(node, None))
        elif isinstance(node, ast.ClassDef):
            records.append({
                'kind': 'class', 'owner': None, 'name': node.name,
                'lineno': node.lineno, 'signature': None,
                'body': 'substantive',
                'decorators': [ast.unparse(d) for d in node.decorator_list],
            })
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    records.append(function_record(child, node.name))
    return records


def _by_name(records):
    """``{nombre: registro}``. Un homonimo en dos clases se queda con el primero.

    Es una perdida declarada: el emparejamiento de este censo es por NOMBRE,
    igual que el de los cinco instrumentos previos, porque la referencia
    concentra sus metodos en una clase por archivo.
    """
    index = {}
    for record in records:
        index.setdefault(record['name'], record)
    return index


def census(roots=CENSUS_ROOTS):
    """El censo por archivo: presencia, cuerpo y union con la referencia."""
    pairs = {label: (ours, reference)
             for label, ours, reference in MIRRORED_ROOTS}
    report = []
    for label in roots:
        if label not in pairs:
            continue
        our_root, reference_root = pairs[label]
        for our_file in sorted(pathlib.Path(our_root).rglob('*.py')):
            if our_file.name == '__init__.py':
                continue
            ours = declared_symbols(our_file)
            reference_file = pathlib.Path(reference_root) / our_file.name
            reference = declared_symbols(reference_file) if reference_file.is_file() else []
            our_index, reference_index = _by_name(ours), _by_name(reference)
            our_names = set(our_index)

            matched, diverged, hole, fidelity = [], [], [], []
            for name, reference_record in reference_index.items():
                resolved = resolve(name, our_names)
                if resolved is None:
                    continue
                our_record = our_index[resolved]
                if our_record['body'] == 'stub':
                    (fidelity if reference_record['body'] == 'stub' else hole
                     ).append({'reference': name, 'ours': resolved,
                               'line': our_record['lineno']})
                    continue
                matched.append(name)
                if (our_record['signature'] != reference_record['signature']
                        and our_record['kind'] != 'class'):
                    diverged.append({
                        'reference': name, 'ours': resolved,
                        'line': our_record['lineno'],
                        'signature_reference': reference_record['signature'],
                        'signature_ours': our_record['signature'],
                    })
            resolved_names = {resolve(n, our_names) for n in reference_index}
            report.append({
                'file': str(our_file.relative_to(REPO)),
                'reference_file': (str(reference_file) if reference_file.is_file()
                                   else None),
                'classes': sum(1 for r in ours if r['kind'] == 'class'),
                'functions': sum(1 for r in ours if r['kind'] != 'class'),
                'stubs': sum(1 for r in ours if r['body'] == 'stub'),
                'reference_symbols': len(reference_index),
                'matched': len(matched),
                'hole': hole,
                'fidelity': fidelity,
                'diverged': diverged,
                'ours_only': sorted(our_names - {n for n in resolved_names if n}),
            })
    return report


def main(argv=None):
    report = census()
    destination = RUN_DIR / 'outputs' / 'census.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n',
                           encoding='utf-8')

    header = ('archivo', 'cls', 'fn', 'stub', 'ref', 'match', 'hueco', 'fidel',
              'diverg', 'propio')
    print(f'{header[0]:<38}' + ''.join(f'{h:>8}' for h in header[1:]))
    totals = dict.fromkeys(header[1:], 0)
    for row in report:
        values = (row['classes'], row['functions'], row['stubs'],
                  row['reference_symbols'], row['matched'], len(row['hole']),
                  len(row['fidelity']), len(row['diverged']), len(row['ours_only']))
        for key, value in zip(header[1:], values):
            totals[key] += value
        print(f'{row["file"]:<38}' + ''.join(f'{v:>8}' for v in values))
    print(f'{"TOTAL":<38}' + ''.join(f'{totals[h]:>8}' for h in header[1:]))
    print(f'\nalcance medido: {len(report)} archivo(s); '
          f'{sum(1 for r in report if r["reference_file"] is None)} sin '
          f'contraparte de nombre en la referencia')
    print(f'salida: {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
