#!/usr/bin/env python3
"""Censo de una clase por AST — un mecanismo con parametros, no N guiones.

La referencia y los binarios del stack se leen con el MISMO instrumento, asi
que sus salidas son comparables sin traducir nada. El rango sale del nodo AST,
nunca de una ventana fija de ``sed``.

El defecto que este guion cierra (TASK-API-0320)
=================================================

El procedimiento que ``atributos-de-clase-de-modelo.md`` publicaba como «el
comando» recorria **solo** ``ast.Assign``. Los 28 atributos que ``BaseModel``
declara —y entre ellos los 24 que la regla legisla: ``_name``,
``_description``, ``_order``, ``_table``, ``_inherit``, ``_rec_name``,
``_check_company_auto``…— son ``ast.AnnAssign``, que es OTRO nodo. Medido
sobre ``odoo19c: odoo/orm/models.py``::

    BaseModel: Assign=3  AnnAssign=28  total=31
      Assign   : __slots__, id, display_name

O sea: corrido contra la clase que DECLARA el contrato, el instrumento viejo
publicaba 3 atributos y ninguno de los que la regla gobierna.

La ceguera no es general. Medido sobre tres modelos de addon
(``stock_picking.py``, ``sale_order.py``, ``res_company.py``): **236
``Assign`` y 0 ``AnnAssign``**. La forma anotada vive en el nucleo
(``odoo/orm/models.py`` 28, ``odoo/orm/fields.py`` 49). El comando servia para
el caso corriente y fallaba justo al ir a leer cual es el contrato.

*Metrica:* sentencias del cuerpo de clase, por tipo de nodo AST.
*Ciega a:* todo atributo instalado fuera del cuerpo de la clase —
``setattr(cls, …)``, un decorador, una metaclase. La referencia usa las tres
(``MetaModel.__init__`` cuelga ``create_uid`` con ``setattr``), asi que un 0
de este instrumento acota lo que se puede afirmar del CUERPO, no de la clase.
"""
import argparse
import ast
import dataclasses
import pathlib
import sys


@dataclasses.dataclass(frozen=True)
class ClassAttribute:
    """Un atributo declarado en el cuerpo de la clase."""

    name: str
    lineno: int
    annotated: bool
    annotation: str | None
    value: str | None


@dataclasses.dataclass(frozen=True)
class ClassMethod:
    """Un metodo declarado en el cuerpo de la clase."""

    name: str
    lineno: int
    end_lineno: int
    decorators: tuple[str, ...]
    signature: str
    summary: str


@dataclasses.dataclass(frozen=True)
class ClassCensus:
    """El censo de una clase: su rango, sus bases, sus atributos, sus metodos."""

    name: str
    lineno: int
    end_lineno: int
    bases: tuple[str, ...]
    attributes: tuple[ClassAttribute, ...]
    methods: tuple[ClassMethod, ...]


def _attribute_of(statement):
    """El atributo que declara la sentencia, o None si no declara ninguno.

    Las DOS formas cuentan: ``x = v`` (``ast.Assign``) y ``x: T = v``
    (``ast.AnnAssign``). Reconocer solo la primera es el defecto que este
    guion cierra.
    """
    if isinstance(statement, ast.Assign):
        if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            return None
        return ClassAttribute(
            name=statement.targets[0].id,
            lineno=statement.lineno,
            annotated=False,
            annotation=None,
            value=ast.unparse(statement.value),
        )
    if isinstance(statement, ast.AnnAssign):
        if not isinstance(statement.target, ast.Name):
            return None
        return ClassAttribute(
            name=statement.target.id,
            lineno=statement.lineno,
            annotated=True,
            annotation=ast.unparse(statement.annotation),
            # Una anotacion SIN valor —``_fields: dict``— declara el atributo
            # y no lo inicializa. Se censa igual: la declaracion existe.
            value=ast.unparse(statement.value) if statement.value is not None else None,
        )
    return None


def _method_of(statement):
    if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    doc = (ast.get_docstring(statement) or '').strip().splitlines()
    return ClassMethod(
        name=statement.name,
        lineno=min([statement.lineno] + [d.lineno for d in statement.decorator_list]),
        end_lineno=statement.end_lineno,
        decorators=tuple(ast.unparse(d) for d in statement.decorator_list),
        signature=ast.unparse(statement.args),
        summary=doc[0] if doc else '',
    )


def census(source, class_names=None):
    """Censa las clases de ``source``; ``class_names`` None censa todas."""
    path = pathlib.Path(source)
    tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
    wanted = None if class_names is None else set(class_names)
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if wanted is not None and node.name not in wanted:
            continue
        attributes = tuple(filter(None, (_attribute_of(s) for s in node.body)))
        methods = tuple(filter(None, (_method_of(s) for s in node.body)))
        out[node.name] = ClassCensus(
            name=node.name,
            lineno=node.lineno,
            end_lineno=node.end_lineno,
            bases=tuple(ast.unparse(b) for b in node.bases),
            attributes=attributes,
            methods=methods,
        )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('source', help='archivo .py que declara las clases')
    parser.add_argument('classes', nargs='*',
                        help='clases a censar; sin ninguna, censa todas')
    parser.add_argument('--prefix', default='',
                        help='solo atributos que empiecen asi (p. ej. "_")')
    args = parser.parse_args()

    found = census(args.source, args.classes or None)
    for name in (args.classes or sorted(found)):
        klass = found.get(name)
        if klass is None:
            print(f'AUSENTE: {name}')
            continue
        attributes = [a for a in klass.attributes if a.name.startswith(args.prefix)]
        anotados = sum(1 for a in attributes if a.annotated)
        print(f'=== {klass.name}({", ".join(klass.bases) or "-"})  '
              f':{klass.lineno}-{klass.end_lineno}  '
              f'atributos={len(attributes)} (anotados={anotados}) '
              f'metodos={len(klass.methods)}')
        for attribute in attributes:
            forma = 'AnnAssign' if attribute.annotated else 'Assign   '
            print(f'  ATTR\t{forma}\t{attribute.name}\t{attribute.lineno}\t'
                  f'{attribute.value if attribute.value is not None else "(sin valor)"}')
        for method in klass.methods:
            print(f'  DEF \t{method.name}\t{method.lineno}-{method.end_lineno}\t'
                  f'{",".join(method.decorators) or "-"}\t({method.signature})\t'
                  f'{method.summary[:80]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
