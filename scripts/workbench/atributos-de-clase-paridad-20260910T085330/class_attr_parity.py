#!/usr/bin/env python3
"""Paridad de atributos de clase entre la referencia y su puerto.

`atributos-de-clase-de-modelo.md` v2.0.0 declara la regla —*«se portan TODOS
los que declare; si no declara ninguno, no se inventa ninguno»*— y dice, en su
seccion de severidad, por que nadie la mide: **«el gate de porte no mira los
atributos de clase»**. `check_porte_completo` compara METODOS dentro de un
archivo dado; un `_order` ausente no aparece en ninguna de sus columnas.

Este instrumento cubre ese eje, y mide en las DOS direcciones:

``missing``
    lo que la fuente declara y el puerto calla — porte parcial silencioso.
``extra``
    lo que el puerto declara y la fuente no — cabecera inventada, que es el
    defecto de la segunda mitad de la regla y el que un instrumento pensado
    solo para «lo que falta» no puede ver.

La clave del join
=================

Tres claves, en este orden de precedencia:

1. el nombre de clase **literal**;
2. el nombre de clase **sin guiones bajos** — la fuente escribe
   ``IrActionsAct_Window`` y este arbol ``IrActionsActWindow``;
3. la **tabla**.

Y la tabla de la referencia **no se deriva de `_name` cuando la clase declara
`_table`**. En la fuente ``model_cls._table = model_cls._name.replace('.','_')``
(``odoo19c: odoo/orm/model_classes.py:266``) es el DEFAULT y se sobreescribe:
nueve de las diez clases de ``ir_actions.py`` lo hacen, y ``ir.actions.act_window``
declara ``ir_act_window``, no ``ir_actions_act_window``. Un join que derive de
``_name`` no empareja ninguna de las nueve — el defecto que este archivo corrige.

El objeto de tabla no es un atributo de ORM
===========================================

``models.Constraint``, ``models.Index`` y ``models.UniqueIndex`` comparten el
prefijo ``_`` con los atributos de ORM y **no son uno**: su hogar aqui es
``Meta.constraints`` / ``Meta.indexes``. Contarlos como ausentes exigiria
declararlos como atributo de clase, que es inventar cabecera — el defecto
inverso al que el instrumento persigue.
"""
import argparse
import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import reference_roots  # noqa: E402

#: Las familias de objeto de tabla, DECLARADAS. Derivarlas de «lo que empieza
#: por mayuscula» aceptaria cualquier llamada y el bucket dejaria de discriminar.
ORM_ATTRS_ARE_TABLE_OBJECTS = ('Constraint', 'Index', 'UniqueIndex')

#: Las raices espejadas: prefijo nuestro -> prefijo de la referencia.
MIRRORED_ROOTS = (
    ('src/orm/', 'odoo/orm/'),
    ('src/tools/', 'odoo/tools/'),
    ('src/addons/base/', 'odoo/addons/base/'),
    ('addons/', 'addons/'),
)

#: Bases cuyo nombre delata que la clase NO es un modelo de datos.
NOT_A_MODEL = ('Serializer', 'Form', 'ViewSet', 'Filter', 'Admin', 'Error',
               'Exception', 'Warning')


def reference_path(ours: pathlib.Path, ref_root: pathlib.Path):
    """La contraparte de un archivo nuestro, o ``None`` si su raiz no se espeja."""
    s = ours.as_posix()
    for nuestro, suyo in MIRRORED_ROOTS:
        if s.startswith(nuestro):
            return ref_root / (suyo + s[len(nuestro):])
    return None


def class_attrs(node: ast.ClassDef) -> dict:
    """Los ``_*`` asignados en el cuerpo de la clase: nombre -> fuente del valor."""
    out = {}
    for n in node.body:
        if not isinstance(n, ast.Assign):
            continue
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id.startswith('_'):
                out[t.id] = ast.unparse(n.value)
    return out


def meta_of(node: ast.ClassDef) -> dict:
    """Las asignaciones de la ``class Meta`` anidada, o ``{}`` si no la hay."""
    for n in node.body:
        if isinstance(n, ast.ClassDef) and n.name == 'Meta':
            return {t.id: ast.unparse(m.value)
                    for m in n.body if isinstance(m, ast.Assign)
                    for t in m.targets if isinstance(t, ast.Name)}
    return {}


def split_table_objects(attrs: dict):
    """Reparte los ``_*`` en (atributos de ORM, objetos de tabla).

    El discriminador es la familia declarada en :data:`ORM_ATTRS_ARE_TABLE_OBJECTS`,
    buscada en la fuente del valor — ``models.UniqueIndex('(a, b)')`` es objeto de
    tabla; ``_order = 'name, id'`` no lo es.
    """
    orm, objetos = {}, {}
    for nombre, valor in attrs.items():
        familia = next((f for f in ORM_ATTRS_ARE_TABLE_OBJECTS
                        if f'{f}(' in valor), None)
        (objetos if familia else orm)[nombre] = valor
    return orm, objetos


def reference_table(attrs: dict):
    """La tabla que la referencia usaria: ``_table`` declarado, o la sustitucion.

    Es el orden de ``model_classes.py:265-266``, donde la sustitucion es el
    default de una asignacion que la clase puede sobreescribir.
    """
    if '_table' in attrs:
        return attrs['_table'].strip('\'"')
    nombre = attrs.get('_name')
    return nombre.strip('\'"').replace('.', '_') if nombre else None


def join_keys(class_name: str, table):
    """Las claves con que una clase se busca, de mas a menos especifica."""
    claves = [class_name.lower()]
    sin_guion = class_name.replace('_', '').lower()
    if sin_guion != claves[0]:
        claves.append(sin_guion)
    if table:
        claves.append(f'tabla:{table}')
    return claves


def pair_classes(ref_classes: dict, our_classes: dict):
    """Empareja por las tres claves. Devuelve (pares, nuestras sin par, ref sin par).

    ``ref_classes`` y ``our_classes`` son ``{nombre: (nombre, tabla)}``.

    Una clase ya emparejada se retira del indice: la clave de tabla **no es
    inyectiva** —``ir.actions.actions`` y ``ir.actions.act_window_close``
    declaran las dos ``ir_actions``— y sin retirarla las dos caerian sobre la
    misma contraparte, dejando una sin medir.
    """
    indice = {}
    for nombre, (cls, tabla) in our_classes.items():
        for clave in join_keys(cls, tabla):
            indice.setdefault(clave, []).append(nombre)

    pares, usadas, ref_sin_par = [], set(), []
    # Dos pasadas: primero las claves de nombre, y solo despues la de tabla. Sin
    # ese orden, una clase de la fuente podria llevarse por tabla la contraparte
    # que otra reclama por nombre, que es el emparejamiento correcto.
    for solo_nombre in (True, False):
        for nombre, (cls, tabla) in ref_classes.items():
            if any(r == nombre for r, _ in pares):
                continue
            for clave in join_keys(cls, tabla):
                if solo_nombre and clave.startswith('tabla:'):
                    continue
                candidatas = [c for c in indice.get(clave, []) if c not in usadas]
                if candidatas:
                    pares.append((nombre, candidatas[0]))
                    usadas.add(candidatas[0])
                    break
    ref_sin_par = [n for n in ref_classes if not any(r == n for r, _ in pares)]
    return pares, [n for n in our_classes if n not in usadas], ref_sin_par


def model_classes(src: str, include_non_models=False) -> dict:
    """``{nombre: (nombre, tabla)}`` de las clases del modulo, con sus atributos.

    Devuelve tambien un mapa paralelo de nodos por nombre para no re-parsear.
    """
    arbol = ast.parse(src)
    salida, nodos = {}, {}
    for c in arbol.body:
        if not isinstance(c, ast.ClassDef):
            continue
        bases = [b.id if isinstance(b, ast.Name) else getattr(b, 'attr', '')
                 for b in c.bases if isinstance(b, (ast.Name, ast.Attribute))]
        if not include_non_models and any(k in b for b in bases for k in NOT_A_MODEL):
            continue
        attrs = class_attrs(c)
        meta = meta_of(c)
        tabla = reference_table(attrs) or (meta.get('db_table') or '').strip('\'"') or None
        salida[c.name] = (c.name, tabla)
        nodos[c.name] = (attrs, meta)
    return salida, nodos


def compare_file(ours: pathlib.Path, ref: pathlib.Path):
    """El veredicto de un par de archivos: una fila por clase emparejada."""
    ref_classes, ref_nodes = model_classes(ref.read_text())
    our_classes, our_nodes = model_classes(ours.read_text())
    pares, nuestras_sin_par, ref_sin_par = pair_classes(ref_classes, our_classes)

    filas = []
    for nombre_ref, nombre_nuestro in pares:
        ref_attrs, _ = ref_nodes[nombre_ref]
        our_attrs, our_meta = our_nodes[nombre_nuestro]
        ref_orm, ref_objetos = split_table_objects(ref_attrs)
        our_orm, _ = split_table_objects(our_attrs)
        filas.append({
            'ref': nombre_ref,
            'ours': nombre_nuestro,
            'missing': sorted(set(ref_orm) - set(our_orm)),
            'extra': sorted(set(our_orm) - set(ref_orm)),
            'table_objects': sorted(ref_objetos),
            'meta_constraints': 'constraints' in our_meta or 'indexes' in our_meta,
        })
    return filas, nuestras_sin_par, ref_sin_par


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('files', nargs='*', help='archivos nuestros; vacio = el tramo')
    args = p.parse_args()

    ref_root = pathlib.Path(reference_roots.tree('odoo19c'))
    objetivos = [pathlib.Path(f) for f in args.files] or \
        [pathlib.Path('src/addons/base/models/ir_actions.py')]

    total_missing = total_extra = 0
    for ours in objetivos:
        ref = reference_path(ours, ref_root)
        if ref is None or not ref.is_file():
            print(f'{ours}: sin contraparte en la referencia — NO se mide')
            continue
        filas, sin_par_nuestras, sin_par_ref = compare_file(ours, ref)
        print(f'\n=== {ours}')
        print(f'    contraparte: odoo19c: {ref.relative_to(ref_root)}')
        for f in filas:
            m, e = len(f['missing']), len(f['extra'])
            total_missing += m
            total_extra += e
            estado = 'OK' if not (m or e) else f'{m} ausentes, {e} inventados'
            flecha = '' if f['ref'] == f['ours'] else f"  (ref {f['ref']})"
            print(f"    {f['ours']:<32}{flecha}")
            print(f"        {estado}")
            if f['missing']:
                print(f"        missing: {', '.join(f['missing'])}")
            if f['extra']:
                print(f"        extra:   {', '.join(f['extra'])}")
            if f['table_objects']:
                hogar = 'Meta declarado' if f['meta_constraints'] else 'SIN Meta'
                print(f"        objetos de tabla (hogar = Meta): "
                      f"{', '.join(f['table_objects'])} — {hogar}")
        if sin_par_nuestras:
            print(f'    nuestras sin contraparte (NO se marcan): '
                  f"{', '.join(sin_par_nuestras)}")
        if sin_par_ref:
            print(f"    de la referencia sin puerto: {', '.join(sin_par_ref)}")

    print(f'\ntotal: {total_missing} atributos ausentes, {total_extra} inventados')
    return 0


if __name__ == '__main__':
    sys.exit(main())
