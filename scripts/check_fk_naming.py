#!/usr/bin/env python3
"""Gate de la convención de nombre de columna en las FK portadas (ADR-029, #141).

La referencia colapsa en un nombre lo que Django separa en tres ejes, así que
una FK portada admite cuatro formas y sólo una es fiel a los dos que importan:

======  =========================================  =========  ==========
Forma   Declaración                                Símbolo    Columna
======  =========================================  =========  ==========
A       ``parent = Many2one(...)``                 divergente fiel
B       ``crud_model_id = Many2one(...)``          fiel       ``..._id_id``
C       ``model_id = Many2one(..., db_column=…)``  fiel       fiel
D       ``page = Many2one(..., db_column='…_id')`` divergente fiel
N       ``Many2one(store=False)``                  fiel       (sin columna)
======  =========================================  =========  ==========

ADR-029 fija **C** como la forma que gobierna. Este gate mide la forma de cada
declaración; NO lleva el conteo del árbol —eso lo publica al correr, y el
registro fechado vive en ``docs: source/gestion/pm/reportes/censo-convencion-fk-sufijo-id.rst``
(``calibration-verified-numbers.md``, corolario de la cifra que vive en código).

El sufijo ``_id`` es el PROXY; el criterio es la referencia
===========================================================

La primera versión decidía «símbolo fiel» con ``field_name.endswith('_id')``.
Eso mide la **forma** del nombre y concluye sobre su **fidelidad**, que es el
sub-patrón C de ``metrica-decide-la-conclusion.md``: el proxy acierta mientras
la referencia use el sufijo, y **la referencia no siempre lo usa**.

Medido sobre ``odoo19c`` (2026-08-28): de **2692** ``Many2one`` declarados,
**128 (4.75 %)** no llevan sufijo — ``recurring_plan`` y ``company_currency``
de ``crm.lead``, ``country_of_birth`` de ``hr.employee``, ``bank_state`` y
``bank_country`` de ``res.partner.bank``, ``product_category`` de
``account.analytic.line``… En esos 128 el porte fiel **es** el símbolo sin
sufijo, y el proxy lo marcaba como incumplidor: el gate pedía apartarse de la
referencia, que es exactamente lo que ADR-029 existe para impedir.

Así que el gate **consulta la contraparte**: si la referencia declara un
``Many2one`` con ese nombre verbatim, el símbolo es fiel. El sufijo queda como
respaldo para lo que no tiene contraparte, que es donde no hay contra qué
comparar. La resolución de la contraparte NO se copia aquí — la da
``reference_roots.addon_root``, el mismo resolutor que usa
``check_porte_completo``.

Qué NO puede ver
================

Un ``db_column`` construido en tiempo de ejecución, un campo declarado por
``contribute_to_class`` fuera de un ``ClassDef``, y el caso en que el símbolo
divergente sea el correcto porque el modelo es propio del L0 y no adapta nada
de la referencia. Ése es el motivo de que la forma A vaya a baseline en vez de
bloquear: la forma sola no distingue un porte con símbolo divergente de un
modelo nuestro que nunca tuvo contraparte.

Y es ciego al **archivo** en que la contraparte declara el campo: consulta el
archivo homónimo del addon, así que un campo que la referencia declare en otro
archivo del mismo addon cae al respaldo del sufijo. Es la misma ceguera
cross-archivo de :ref:`h-api-557`, y aquí sólo puede producir un falso
incumplidor, nunca una absolución falsa.
"""
import argparse
import ast
import functools
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BASELINE = REPO / 'scripts' / 'fk_naming_baseline.txt'

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from reference_roots import addon_root, tree as _tree  # noqa: E402

#: La raíz del árbol que gobierna. Ver
#: ``referencia-odoo-gobierna-las-decisiones.md``: 19 desempata.
REFERENCE_19C = _tree('odoo19c')

#: Los constructores de UN solo valor relacional. ``fields.Many2one`` es
#: nuestro despachador (``src/orm/fields_relational.py``): con ``store=True``
#: devuelve un ``models.ForeignKey``, así que las dos formas de declararlo
#: producen los mismos tres ejes y las dos se miden.
SINGLE_VALUED = ('Many2one', 'ForeignKey', 'OneToOneField')

#: Raíces del monolito modular. ``addons`` son los de comunidad portados;
#: ``src`` es el núcleo espejado.
ROOTS = ('src', 'addons')


def classify(field_name, has_db_column, stored=True, reference_names=None):
    """La letra de la forma en que se declaró este campo.

    ``stored=False`` sale antes que las otras cuatro y no es una quinta forma:
    es la **ausencia del eje**. Un ``Many2one(store=False)`` devuelve un
    ``NonStored`` (``src/orm/fields_nonstored.py``), que no tiene columna, así
    que preguntar si la suya es fiel no significa nada. Meterlo en el cubo B
    —«columna divergente»— rotularía como defecto un campo que no tiene el eje
    donde se mide: el sub-patrón A de ``metrica-decide-la-conclusion.md``.

    ``reference_names`` son los ``Many2one`` que la contraparte declara. Con
    ellos el símbolo se juzga contra la referencia; sin ellos —modelo propio
    del L0, o archivo sin contraparte— cae al respaldo del sufijo, que es el
    proxy correcto para el 95.25 % del árbol medido.
    """
    if not stored:
        return 'N'
    if reference_names and field_name in reference_names:
        # La referencia lo declara con ESTE nombre: el símbolo es fiel, lleve
        # sufijo o no. Por aquí entran los 128 sin sufijo de ``odoo19c``.
        faithful_symbol = True
    else:
        faithful_symbol = field_name.endswith('_id')
    if faithful_symbol:
        return 'C' if has_db_column else 'B'
    return 'D' if has_db_column else 'A'


def _counterpart(relative):
    """La ruta de la contraparte en la referencia, o ``None`` si no hay.

    Dos mapeos, que son los dos que el árbol usa:

    - ``addons/<x>/…`` y ``src/addons/<x>/…`` → el addon ``<x>`` de la
      referencia, resuelto por ``reference_roots.addon_root`` (que conoce sus
      DOS raíces y el mapa de renombre ``authz_* → auth_*``).
    - ``src/<resto>`` → ``odoo/<resto>``, el núcleo espejado.
    """
    partes = relative.parts
    if partes[:1] == ('addons',) and len(partes) > 2:
        raiz, resto = addon_root(partes[1]), partes[2:]
    elif partes[:2] == ('src', 'addons') and len(partes) > 3:
        raiz, resto = addon_root(partes[2]), partes[3:]
    elif partes[:1] == ('src',) and len(partes) > 1:
        raiz, resto = REFERENCE_19C / 'odoo', partes[1:]
    else:
        return None
    return raiz.joinpath(*resto)


@functools.lru_cache(maxsize=None)
def reference_many2one(relative):
    """Los ``Many2one`` que la contraparte declara, por su nombre verbatim.

    Conjunto vacío cuando no hay contraparte — y el vacío es significativo:
    ``classify`` cae entonces al respaldo del sufijo en vez de absolver.
    """
    contraparte = _counterpart(relative)
    if contraparte is None or not contraparte.is_file():
        return frozenset()
    try:
        arbol = ast.parse(contraparte.read_text(encoding='utf-8', errors='ignore'))
    except SyntaxError:
        return frozenset()
    nombres = set()
    for klass in [n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)]:
        for nodo in klass.body:
            if isinstance(nodo, ast.Assign):
                objetivos = nodo.targets
            elif isinstance(nodo, ast.AnnAssign):
                objetivos = [nodo.target]
            else:
                continue
            if not isinstance(nodo.value, ast.Call):
                continue
            f = nodo.value.func
            ctor = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', '')
            if ctor not in SINGLE_VALUED:
                continue
            nombres.update(t.id for t in objetivos if isinstance(t, ast.Name))
    return frozenset(nombres)


def _keyword(call, name):
    """El valor de la palabra clave ``name`` de la llamada, o ``None``."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_stored(call):
    """Si la declaración tiene eje de columna — DERIVADO como la fuente.

    ``store`` no se declara sólo con la palabra clave. La fuente lo deriva de
    ``compute`` y de ``related``, en dos ramas del mismo ``_setup_attrs``
    (``odoo19c: odoo/orm/fields.py``), y sus propios comentarios lo dicen::

        443:        if attrs.get('compute'):
        444:            # by default, computed fields are not stored, ...
        447:            attrs['store'] = store = attrs.get('store', False)
        452:        if attrs.get('related'):
        453:            # by default, related fields are not stored, ...
        455:            attrs['store'] = store = attrs.get('store', False)

    La forma ``attrs.get('store', False)`` es la que hace que un ``store=True``
    explícito sobreviva a la derivación: la fuente fija el **default**, no
    impone el valor. Por eso la palabra clave declarada manda y la derivación
    sólo actúa en su ausencia.

    Nuestro despachador ya espejaba las dos ramas EN EJECUCIÓN
    (``src/orm/fields_relational.py``): con ``compute`` o ``related`` y sin
    ``store``, devuelve un ``NonStored``, que no tiene columna. El lector
    estático de este gate no lo hacía, así que clasificaba con eje de columna
    un campo que en ejecución no la tiene.
    """
    store = _keyword(call, 'store')
    if store is not None:
        return not (isinstance(store, ast.Constant) and store.value is False)
    if _keyword(call, 'compute') is not None or _keyword(call, 'related') is not None:
        return False
    return True


def declarations(path):
    """Cada asignación relacional de un solo valor: ``(clase, campo, forma)``."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError):
        return
    try:
        relativa = path.relative_to(REPO)
    except ValueError:
        # Un archivo fuera del repo —el ``tmp_path`` de un test— no tiene
        # contraparte que consultar. El conjunto vacío NO absuelve: manda a
        # ``classify`` al respaldo del sufijo.
        relativa = None
    fieles = reference_many2one(relativa) if relativa else frozenset()
    for klass in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for node in klass.body:
            # La referencia 19 declara el campo CON anotación de tipo —
            # ``parent_id: ResPartner = fields.Many2one(...)`` es un
            # ``ast.AnnAssign``. Un recorrido que sólo mire ``ast.Assign`` deja
            # de ver la declaración en cuanto el porte adopta esa forma, y
            # publica un 0 que no distingue «no hay deuda» de «no puedo verla»
            # (sub-patrón D de ``metrica-decide-la-conclusion.md``).
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            ctor = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            if ctor not in SINGLE_VALUED:
                continue
            stored = _is_stored(node.value)
            has_column = _keyword(node.value, 'db_column') is not None
            for target in targets:
                if isinstance(target, ast.Name):
                    yield klass.name, target.id, classify(
                        target.id, has_column, stored, fieles)


def python_files():
    """Los ``.py`` del monolito, sin migraciones ni cachés."""
    for root in ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*.py')):
            parts = path.parts
            if 'migrations' in parts or '__pycache__' in parts:
                continue
            yield path


def load_baseline():
    if not BASELINE.is_file():
        return set()
    return {line.strip() for line in BASELINE.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def survey():
    """``(forma, clave)`` de cada declaración medida, con su conteo por forma."""
    rows, counts = [], {letter: 0 for letter in 'ABCDN'}
    for path in python_files():
        relative = path.relative_to(REPO)
        for klass, field, form in declarations(path):
            counts[form] += 1
            rows.append((form, f'{relative}::{klass}.{field}'))
    return rows, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si aparece una declaración no fiel nueva')
    parser.add_argument('--write-baseline', action='store_true',
                        help='congela la deuda heredada (formas A, B y D)')
    args = parser.parse_args()

    rows, counts = survey()
    measured = sum(counts.values())
    offenders = sorted(key for form, key in rows if form in ('A', 'B', 'D'))

    if args.write_baseline:
        BASELINE.write_text(
            '# Deuda heredada de ADR-029 — formas A/B/D congeladas.\n'
            '# Una listada no bloquea; una nueva sí. Se paga al tocar el\n'
            '# archivo (barrido: tarea #143).\n'
            + '\n'.join(offenders) + '\n')
        print(f'baseline escrito: {len(offenders)} declaraciones')
        return 0

    baseline = load_baseline()
    fresh = [key for key in offenders if key not in baseline]

    print(f'formas: ' + ' · '.join(f'{k}={v}' for k, v in sorted(counts.items()))
          + f'  (alcance medido: {measured} declaraciones relacionales '
            f'de un solo valor en {" y ".join(ROOTS)}/)')
    print(f'no fieles: {len(offenders)}  ·  en baseline: {len(offenders) - len(fresh)}'
          f'  ·  nuevas: {len(fresh)}')
    for key in fresh:
        print(f'  NUEVA  {key}')

    if fresh and args.strict:
        print('\nADR-029: la columna lleva el nombre que la referencia declara.\n'
              "Forma C: símbolo fiel + db_column='<mismo nombre>'.", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
