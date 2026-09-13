#!/usr/bin/env python3
"""Motor: comparar una PROPIEDAD DEL CUERPO contra la contraparte de la fuente.

Los gates de este arbol miden la **presencia** de un simbolo
(``check_porte_completo``), su **cabecera** (``check_model_class_attributes``),
su **sitio** (``check_symbol_home``) o una convencion de nombre. Ninguno leia
el cuerpo para preguntarse **como** hace lo que hace, y por ese hueco entro
H-API-1058: un reflejo escribia por ``update_or_create`` —cruzando la guarda
de ``save()``— donde la fuente escribe por SQL crudo a proposito.

Este modulo es el mecanismo de esa comparacion. **No sabe que propiedad se
mide**: recibe un :class:`Axis` que declara los dos vocabularios y como se
nombra cada desacuerdo. El primer eje es el camino de escritura
(``check_write_path.py``); los siguientes —si transacciona, si emite senales,
por que via lee— se declaran igual, sin escribir otro recorrido.

**Por que un modulo aparte y no dentro de** ``check_porte_completo``. El
precedente del arbol es :ref:`h-api-955`, que partio un ``graph_algorithms.py``
en tres por SRP: *"los tres cambian por razones distintas"*. Aqui pasa lo
mismo — el recorrido cambia cuando cambia como se resuelve un espejo; el eje,
cuando cambia que se mide. Pesado por los siete factores: **claridad** y
**mantenimiento** ganan con la separacion, y el **coste** es una invocacion
mas en el pre-commit, que son milisegundos sobre archivos en staging.
"""
import ast
import collections
import dataclasses
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import reference_roots  # noqa: E402 — la raiz se declara una vez (H-API-335)

#: Las dos categorias transversales, que ningun eje redefine. ``ABSENT`` es lo
#: que el eje NO ve en ese cuerpo; ``BOTH`` es su propia categoria y no se
#: colapsa a ninguna de las dos del eje, porque dice algo distinto.
ABSENT = 'sin senal'
BOTH = 'ambas'

#: El instrumento vio los dos lados y **no puede decidir** con su granularidad.
#: No es un hallazgo —no hay defecto que nombrar— ni un acuerdo. Se cuenta
#: aparte para que el denominador no lo esconda: un par indeterminado contado
#: como acuerdo publica un verde que no discrimina (sub-patron D de
#: ``metrica-decide-la-conclusion.md``).
INDETERMINATE = 'indeterminado por granularidad de metodo'

#: Las tres vias por las que un simbolo halla su contraparte. Se declaran aqui
#: —no en un eje— porque el emparejamiento es del MOTOR: un eje decide que se
#: compara, no quien es la contraparte de quien.
BY_OWNER = 'por clase duena'
MODULE_LEVEL = 'funcion de modulo'
BY_NAME = 'por nombre, duena divergente'


@dataclasses.dataclass(frozen=True)
class Vocabulary:
    """Los nombres de llamada de un lado, en las dos categorias del eje."""

    side: str
    first: frozenset
    second: frozenset


@dataclasses.dataclass(frozen=True)
class Axis:
    """Que propiedad se mide, y como se nombra cada desacuerdo.

    ``first_name``/``second_name`` son las etiquetas legibles de las dos
    categorias. ``directions`` mapea ``(nuestra, la de la fuente)`` al nombre
    del riesgo: sin entrada, el desacuerdo se reporta sin nombrar direccion,
    que es honesto y no inventa una lectura.
    """

    name: str
    ours: Vocabulary
    reference: Vocabulary
    first_name: str
    second_name: str
    directions: dict


def called_names(node):
    """Los nombres invocados en el cuerpo, por atributo o sueltos."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        if isinstance(sub.func, ast.Attribute):
            yield sub.func.attr
        elif isinstance(sub.func, ast.Name):
            yield sub.func.id


def classify(node, vocabulary, axis):
    """La categoria del cuerpo segun el vocabulario de su lado."""
    first = second = False
    for name in called_names(node):
        if name in vocabulary.first:
            first = True
        elif name in vocabulary.second:
            second = True
    if first and second:
        return BOTH
    if first:
        return axis.first_name
    if second:
        return axis.second_name
    return ABSENT


def direction(ours, theirs, axis):
    """El nombre del desacuerdo, ``None`` si coinciden, ``INDETERMINATE`` si el
    instrumento no puede decidir.

    Tres desenlaces, no dos, y el tercero es el que evita un falso positivo:

    - Un lado **sin senal** no se compara: concluir ahi seria hablar de lo que
      el instrumento no ve (``metrica-decide-la-conclusion.md``).
    - Un lado en ``BOTH`` que **contiene** la categoria del otro es
      **indeterminado**, no un desacuerdo. La unidad de esta comparacion es el
      **metodo**, y un metodo puede escribir por dos mecanismos para dos
      operaciones distintas —insertar por debajo, borrar por el enganche—.
      Con esa granularidad, que nosotros usemos uno de los dos que la fuente
      usa no es evidencia de divergencia: es la resolucion del instrumento.
    - Lo demas es desacuerdo, con el nombre que el eje le de.
    """
    if ABSENT in (ours, theirs) or ours == theirs:
        return None
    if BOTH in (ours, theirs):
        return INDETERMINATE
    return axis.directions.get((ours, theirs), 'categoria distinta')


@dataclasses.dataclass(frozen=True)
class Finding:
    path: str
    symbol: str
    ours: str
    theirs: str
    direction: str
    owner: str = ''

    @property
    def key(self):
        """La clave DEL SIMBOLO, no la del nombre.

        Sin la clase duena dos hermanas comparten entrada de baseline: congelar
        ``models.py::__init__`` autorizaria el de cualquiera de las nueve clases
        que lo declaran en ese archivo. La funcion de modulo conserva el nombre
        desnudo porque no tiene duena que la desambigue.
        """
        symbol = f'{self.owner}.{self.symbol}' if self.owner else self.symbol
        return f'{self.path}::{symbol}'


@dataclasses.dataclass(frozen=True)
class Scope:
    """El denominador. Un conteo sin el no es un resultado."""

    files_scanned: int
    files_with_counterpart: int
    pairs_compared: int
    pairs_indeterminate: int = 0
    #: Por que via emparejo cada par comparado. Las tres suman
    #: ``pairs_compared``: un denominador que no dice como se compuso no es
    #: auditable, y la tercera es la que mide cuanto pesa el respaldo.
    pairs_by_owner: int = 0
    pairs_module_level: int = 0
    pairs_by_name: int = 0


#: Las raices espejadas: el prefijo nuestro y su destino en la referencia. Las
#: rutas salen de ``reference_roots``; aqui solo vive el mapa de prefijos.
MIRRORED_ROOTS = (
    (('src', 'orm'), ('odoo', 'orm')),
    (('src', 'tools'), ('odoo', 'tools')),
)


def counterpart(path):
    """El archivo espejo en la referencia, o ``None`` si no lo hay."""
    parts = pathlib.Path(path).parts
    for prefix, destination in MIRRORED_ROOTS:
        if parts[:len(prefix)] == prefix:
            return reference_roots.tree().joinpath(
                *destination, *parts[len(prefix):])
    if parts[:2] == ('src', 'addons') and len(parts) > 3:
        return reference_roots.addon_root(parts[2]).joinpath(*parts[3:])
    return None


@dataclasses.dataclass(frozen=True)
class Declaration:
    """Un simbolo declarado en un archivo, con su duena y su linea.

    ``methods_of`` devuelve el nodo por nombre y pierde dos cosas que un
    analisis de flujo necesita: la **clase duena** —el contrato puede vivir en
    una base, no en la clase que se lee— y la **funcion de modulo**, que en
    ``odoo/tools`` es la forma dominante. Esta estructura las conserva sin
    cambiar el contrato de ``methods_of``, que ``compare`` ya consume.
    """

    name: str
    owner: str            # nombre de la clase, o '' si es de modulo
    lineno: int
    node: object
    bases: tuple = ()     # las bases declaradas: de la clase duena, o suyas
    kind: str = 'function'   # function | class | assign


def parse_file(path):
    """El AST del archivo, o ``None`` si no se puede leer ni parsear."""
    try:
        return ast.parse(pathlib.Path(path).read_text(errors='ignore'))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None


def base_names(klass):
    """Los nombres de las bases declaradas, por atributo o sueltos."""
    names = []
    for base in klass.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return tuple(names)


def declarations_of(path, tree=None):
    """Todo simbolo declarado en el archivo: clase, funcion y asignacion.

    Tres diferencias con ``methods_of``, y las tres las pide un analisis de
    flujo. No **colapsa por nombre** — dos clases del mismo archivo pueden
    declarar el mismo metodo, y esa coincidencia es lo que la unidad
    *hermanos* mide. Recoge la **funcion de modulo**, que en ``odoo/tools`` es
    la forma dominante. Y recoge **clase y asignacion**: un informe que sólo
    viera funciones diria "no se declara" de una clase que si existe, y ese
    cero seria falso — el sub-patron D de ``metrica-decide-la-conclusion.md``.

    La asignacion se recoge sólo al nivel del cuerpo —de modulo o de clase—,
    no dentro de una funcion: una variable local no es una declaracion que
    otro archivo pueda consumir.
    """
    tree = tree if tree is not None else parse_file(path)
    if tree is None:
        return []
    found, nested = [], set()
    for klass in ast.walk(tree):
        if not isinstance(klass, ast.ClassDef):
            continue
        bases = base_names(klass)
        found.append(Declaration(
            klass.name, '', klass.lineno, klass, bases, 'class'))
        for member in klass.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append(Declaration(
                    member.name, klass.name, member.lineno, member, bases))
                nested.add(id(member))
            elif isinstance(member, ast.Assign):
                for target in member.targets:
                    if isinstance(target, ast.Name):
                        found.append(Declaration(
                            target.id, klass.name, member.lineno, member,
                            bases, 'assign'))
        nested.add(id(klass))
    for node in tree.body:
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and id(node) not in nested):
            found.append(Declaration(node.name, '', node.lineno, node))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.append(Declaration(
                        target.id, '', node.lineno, node, (), 'assign'))
    return found


def methods_of(path):
    """Los metodos declarados en clases del archivo, por nombre."""
    try:
        tree = ast.parse(pathlib.Path(path).read_text(errors='ignore'))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return {}
    return {member.name: member
            for klass in ast.walk(tree) if isinstance(klass, ast.ClassDef)
            for member in klass.body
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))}


@dataclasses.dataclass(frozen=True)
class Pair:
    """Un simbolo y su contraparte, con la via por la que se hallaron."""

    name: str
    owner: str
    ours: object
    theirs: object
    route: str

    @property
    def key(self):
        return f'{self.owner}.{self.name}' if self.owner else self.name


def _functions(declarations):
    """Las declaraciones de funcion, separadas en las de clase y las de modulo."""
    in_class, at_module = [], []
    for declaration in declarations:
        if declaration.kind != 'function':
            continue
        (in_class if declaration.owner else at_module).append(declaration)
    return in_class, at_module


def pair_declarations(our_path, their_path):
    """Los pares simbolo-contraparte, por tres vias y en este orden.

    ``methods_of`` devolvia ``{nombre: nodo}``, y eso tiene dos consecuencias.
    La conocida es la **ceguera**: la funcion de modulo —la forma dominante de
    ``odoo/tools``— no entra. La grave es que el dict **colapsa por nombre**,
    asi que con clases hermanas gana la ultima de cada lado y el motor compara
    dos cuerpos que no son contraparte, **sin que nada lo delate**. Medido
    sobre ``src/orm`` + ``src/tools``: 89 nombres con hermanos, y en
    ``fields_properties.py`` nuestro ``PropertiesDefinition.__init__`` se
    comparaba contra ``Property.__init__`` de la fuente teniendo el nuestro.

    Las tres vias, en orden, y **ninguna es prescindible**:

    1. ``BY_OWNER`` — misma clase duena en los dos lados. Es la unica que
       garantiza contraparte, y resuelve 522 de los 585 pares que el
       instrumento viejo veia.
    2. ``MODULE_LEVEL`` — funcion de modulo del mismo nombre en los dos lados.
       Es la ceguera que se cierra: 241 pares mas.
    3. ``BY_NAME`` — el respaldo, y **no es opcional**: nuestro puerto disuelve
       ``BaseModel`` en mixins, asi que ``create`` vive aqui en
       ``DefaultGetMixin`` y alli en ``BaseModel``. Son los 63 pares restantes,
       los 63 en clase de ambos lados, y **todos del nucleo del ORM**. Un
       emparejamiento estricto por duena los perderia justo donde mas importan.
       ``Scope`` publica cuantos resolvio cada via para que ese peso se vea.

    *Metrica:* pares de simbolo del mismo nombre presentes en los dos lados del
    espejo, por AST, sin colapsar por nombre.
    *Ciega a:* el simbolo portado bajo OTRO nombre —no hay tabla de
    equivalencia, asi que un renombre se lee como ausencia—; y, dentro de la
    via 3 con varios candidatos por lado, cual de ellos es la contraparte real:
    se emparejan en orden de linea, que es determinista y no es juicio.
    """
    ours_in_class, ours_at_module = _functions(declarations_of(our_path))
    theirs_in_class, theirs_at_module = _functions(declarations_of(their_path))

    pairs = []
    theirs_by_owner = {(d.owner, d.name): d for d in theirs_in_class}
    taken = set()

    remaining_ours = []
    for mine in ours_in_class:
        yours = theirs_by_owner.get((mine.owner, mine.name))
        if yours is not None and id(yours) not in taken:
            taken.add(id(yours))
            pairs.append(Pair(mine.name, mine.owner, mine.node, yours.node,
                              BY_OWNER))
        else:
            remaining_ours.append(mine)

    theirs_at_module_by_name = {d.name: d for d in theirs_at_module}
    for mine in ours_at_module:
        yours = theirs_at_module_by_name.get(mine.name)
        if yours is not None:
            pairs.append(Pair(mine.name, '', mine.node, yours.node,
                              MODULE_LEVEL))

    leftovers = collections.defaultdict(list)
    for yours in theirs_in_class:
        if id(yours) not in taken:
            leftovers[yours.name].append(yours)
    for candidates in leftovers.values():
        candidates.sort(key=lambda d: d.lineno)
    for mine in sorted(remaining_ours, key=lambda d: d.lineno):
        candidates = leftovers.get(mine.name)
        if candidates:
            yours = candidates.pop(0)
            pairs.append(Pair(mine.name, mine.owner, mine.node, yours.node,
                              BY_NAME))
    return pairs


def compare(paths, axis):
    """Los hallazgos del eje y el alcance sobre el que se midieron."""
    paths = list(paths)
    findings, with_counterpart, compared, indeterminate = [], 0, 0, 0
    by_route = collections.Counter()
    for path in paths:
        reference = counterpart(path)
        if reference is None or not reference.is_file():
            continue
        with_counterpart += 1
        for pair in pair_declarations(path, reference):
            mine = classify(pair.ours, axis.ours, axis)
            yours = classify(pair.theirs, axis.reference, axis)
            if ABSENT in (mine, yours):
                continue
            compared += 1
            by_route[pair.route] += 1
            verdict = direction(mine, yours, axis)
            if verdict == INDETERMINATE:
                indeterminate += 1
            elif verdict is not None:
                findings.append(Finding(str(path), pair.name, mine, yours,
                                        verdict, pair.owner))
    return findings, Scope(
        len(paths), with_counterpart, compared, indeterminate,
        by_route[BY_OWNER], by_route[MODULE_LEVEL], by_route[BY_NAME])


def tree_files(roots):
    """Los ``.py`` de las raices dadas, saltando cache y migraciones."""
    for root in roots:
        base = pathlib.Path(root)
        if base.is_file():
            yield base
            continue
        for path in sorted(base.rglob('*.py')):
            if '__pycache__' in path.parts or 'migrations' in path.parts:
                continue
            yield path


def load_baseline(path):
    """La deuda congelada. Una entrada listada no bloquea; una nueva si."""
    baseline = pathlib.Path(path)
    if not baseline.is_file():
        return set()
    return {line.strip() for line in baseline.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def write_baseline(path, findings, note):
    pathlib.Path(path).write_text(
        f'# {note}\n'
        '# Una entrada listada no bloquea; una nueva si. Se paga al tocar el\n'
        '# archivo, no en un barrido.\n'
        + ''.join(f'{f.key}\n' for f in sorted(findings, key=lambda x: x.key)))
    return len(findings)
