#!/usr/bin/env python3
"""Cuantos de los «ausentes» del censo resuelven bajo NUESTRO prefijo de disolucion.

El censo de la raiz compara por **nombre literal** y declara su ceguera:
*«Ciega a: … renombres»*. Este arbol disuelve la clase `Field` de la fuente en
funciones de modulo con prefijo `_field_`, asi que cada metodo disuelto se
cuenta como ausente aunque su cuerpo este portado.

Este instrumento toma la lista de ausentes **del propio censo** —para heredar su
universo y no fabricar uno nuevo— y pregunta, simbolo a simbolo, si resuelve en
nuestro archivo bajo alguno de los prefijos declarados.

Metrica: simbolos que el censo marca ausentes en un archivo de `src/orm/` y que
existen en ese mismo archivo bajo un prefijo de `DISSOLUTION_PREFIXES`.
Ciega a: un metodo portado con OTRO nombre (traduccion, sinonimo) — el prefijo
es una convencion declarada, no un detector de renombres; y al CUERPO, igual que
el censo: que `_field_read` exista no dice que haga lo que `Field.read` hace.
"""
import argparse
import ast
import pathlib
import subprocess
import sys

#: Los prefijos con que este arbol disuelve una clase de la fuente en funciones
#: de modulo. Se DECLARAN: un emparejador que infiriera el prefijo del nombre
#: encontrado aceptaria cualquier sufijo y su verde no mediria nada.
DISSOLUTION_PREFIXES = ('_field_', '_model_', '_registry_')

HERE = pathlib.Path(__file__).resolve().parent
API_ROOT = HERE.parent.parent.parent


def resolve(symbol, declared):
    """El nombre bajo el que `symbol` vive en `declared`, o None.

    El literal gana sobre el prefijo. El guion bajo inicial de la fuente no
    viaja al centro del nombre: `_description_depends` se busca como
    `_field_description_depends`, no como `_field__description_depends`.
    """
    if symbol in declared:
        return symbol
    base = symbol.lstrip('_')
    for prefix in DISSOLUTION_PREFIXES:
        candidate = f'{prefix}{base}'
        if candidate in declared:
            return candidate
    return None


def declared_symbols(path):
    """Todo simbolo que el archivo declara: clase, funcion y asignacion de modulo."""
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.add(target.id)
    return out


def census_absences(census_script):
    """El mapa archivo -> [ausentes] que el CENSO publica, no uno propio.

    Heredar su universo es lo que hace comparables las dos cifras; construir
    uno nuevo produciria un denominador que nadie puede cruzar con el suyo.
    """
    if not census_script.is_file():
        print(f'ERROR — no se puede medir: falta el censo en {census_script}.\n'
              '        NO se emite conteo: un 0 aqui seria un verde falso.',
              file=sys.stderr)
        raise SystemExit(2)
    salida = subprocess.run([sys.executable, str(census_script), '--detalle'],
                            capture_output=True, text=True, cwd=API_ROOT)
    mapa, archivo = {}, None
    for linea in salida.stdout.splitlines():
        if linea and not linea.startswith((' ', '\t')) and linea.split()[0].endswith('.py'):
            archivo = linea.split()[0]
        elif archivo and linea.strip().startswith('ausentes:'):
            crudos = linea.split('ausentes:', 1)[1]
            mapa[archivo] = [s.strip() for s in crudos.split(',') if s.strip()]
    if not mapa:
        print('ERROR — el censo no publico ninguna lista de ausentes. NO se emite conteo.',
              file=sys.stderr)
        raise SystemExit(2)
    return mapa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--census', default=str(
        API_ROOT / 'scripts/workbench/orm-root-census-20260902T203712/census_orm_root.py'))
    args = parser.parse_args()

    absences = census_absences(pathlib.Path(args.census))
    total_absent = total_resolved = total_literal = 0
    print(f'{"archivo":26} {"censo dice":>10} {"resuelven":>10} {"ausentes":>9}')
    for filename, symbols in sorted(absences.items()):
        mine = API_ROOT / 'src' / 'orm' / filename
        if not mine.is_file():
            continue
        declared = declared_symbols(mine)
        resolved = [(s, resolve(s, declared)) for s in symbols]
        # Dos fenomenos distintos, y mezclarlos seria un encabezado unico sobre
        # metricas mezcladas: el PREFIJO es nuestra disolucion; el LITERAL es un
        # desacuerdo de universo entre los dos instrumentos (el censo lo llama
        # ausente y un recorrido AST plano lo ve declarado).
        prefijo = [(s, r) for s, r in resolved if r and r != s]
        literal = [s for s, r in resolved if r == s]
        total_absent += len(symbols)
        total_resolved += len(prefijo)
        total_literal += len(literal)
        restantes = len(symbols) - len(prefijo) - len(literal)
        print(f'{filename:26} {len(symbols):10} {len(prefijo):10} {restantes:9}')
        for s, r in prefijo:
            print(f'      {s} -> {r}')
        for s in literal:
            print(f'      [desacuerdo de universo] {s} — declarado, y el censo lo lista ausente')

    print(f'\nresuelven bajo prefijo declarado: {total_resolved} de {total_absent} '
          f'«ausentes» del censo ({100 * total_resolved / total_absent:.1f} %)')
    print(f'desacuerdo de universo con el censo: {total_literal} '
          f'(declarados aqui y listados ausentes alla)')
    print(f'ausentes tras descontar ambos: {total_absent - total_resolved - total_literal}')
    print(f'(alcance medido: {len(absences)} archivos con lista de ausentes en el censo; '
          f'prefijos: {", ".join(DISSOLUTION_PREFIXES)})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
