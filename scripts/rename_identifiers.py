"""Renombra identificadores de Python por TOKEN y por POSICIÓN.

El mecanismo que ``.claude/rules/redaccion-tecnica-es.md`` prescribe en prosa
—*«se renombra por token, no por texto»*— y que no tenía implementación
versionada: se reconstruía a mano en cada pase, en un directorio efímero.

Tres decisiones, y las tres tienen su motivo medido:

1. **Por token, no por texto.** Un ``sed`` sobre palabras reescribe también la
   prosa de los docstrings, donde ``valor``, ``campo`` o ``nombre`` son español
   legítimo. El renombre sólo toca tokens ``NAME``.

2. **Por posición, no con ``untokenize``.** ``untokenize`` reformatea el archivo
   entero: medido, 424 líneas de ruido en el diff por 239 renombres. Aquí se
   reemplaza por offset sobre el texto original, así que el diff sólo muestra
   los identificadores.

3. **Con el intérprete del proyecto (3.12+), y se rehúsa por debajo.** Hasta
   3.11 la f-string entera es un único token ``STRING``, así que su interior es
   invisible para un renombre por posición. Medido (H-API-607): tres f-strings
   sobrevivieron al renombre y quedaron como ``NameError`` en tiempo de
   ejecución, no de import.

   ::

      python 3.11.15  NAME=['def','f','prefijo','return']            ocurrencias=1
      python 3.12.3   NAME=['def','f','prefijo','return','prefijo']  ocurrencias=2

   Por eso el guard sale 2 **sin emitir conteo**: un 0 aquí sería un verde
   falso, el sub-patrón D de ``metrica-decide-la-conclusion.md``.

El mapa NO vive aquí. Es dato de un episodio, no mecanismo — el corolario de
``calibration-verified-numbers.md``: un guion implementa un mecanismo y no
lleva el registro de nada. Se pasa con ``--map``.

Uso
---

::

    # el mapa: una línea por renombre, "viejo<TAB>nuevo" (o espacios)
    uv run python scripts/rename_identifiers.py --map mapa.txt archivo.py ...

    # acotado a las líneas que un commit añadió, para no tocar deuda congelada
    git blame -l --line-porcelain <archivo> | awk '/^<sha>/ {print $3}' > lineas.txt
    uv run python scripts/rename_identifiers.py --map mapa.txt --lines lineas.txt archivo.py

Después del renombre, verificar con un barrido AST: este guion garantiza que
no tocó prosa, no que el árbol siga resolviendo.
"""
import argparse
import ast
import io
import sys
import tokenize
from pathlib import Path

MINIMUM_VERSION = (3, 12)


def require_interpreter():
    """Rehúsa por debajo de 3.12 — y sin emitir conteo (ver el docstring)."""
    if sys.version_info < MINIMUM_VERSION:
        print(
            f'ERROR — este guion exige Python '
            f'{MINIMUM_VERSION[0]}.{MINIMUM_VERSION[1]}+ y corre en '
            f'{sys.version_info.major}.{sys.version_info.minor}. Por debajo, el '
            f'interior de una f-string es un solo token STRING y el renombre lo '
            f'salta EN SILENCIO (H-API-607). Usar el intérprete del proyecto: '
            f'`uv run python`. NO se emite conteo: un 0 aquí sería un verde falso.',
            file=sys.stderr)
        raise SystemExit(2)


def load_map(path):
    """Lee ``viejo nuevo`` por línea. Ignora vacías y comentarios ``#``."""
    mapping = {}
    for number, raw in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) != 2:
            print(f'ERROR — {path}:{number}: se esperaban dos columnas, '
                  f'hay {len(parts)}: {raw!r}', file=sys.stderr)
            raise SystemExit(2)
        old, new = parts
        if old in mapping and mapping[old] != new:
            print(f'ERROR — {path}:{number}: {old!r} ya mapeaba a '
                  f'{mapping[old]!r}', file=sys.stderr)
            raise SystemExit(2)
        mapping[old] = new
    if not mapping:
        print(f'ERROR — {path} no declara ningún renombre.', file=sys.stderr)
        raise SystemExit(2)
    return mapping


def allowed_lines(path):
    return {int(x) for x in Path(path).read_text(encoding='utf-8').split()}


def dict_key_edits(source, mapping, allowed=None):
    """Las claves de diccionario que el mapa nombra, con su posición.

    Una clave es un literal ``STRING``, así que el recorrido por token —que
    sólo mira ``NAME``— es ciego a ella **en silencio**: el guion publicaba
    «0 token(s) renombrado(s)» con el nombre español delante. Es la contraparte,
    en el instrumento de barrido, del defecto que el gate de identificadores
    tenía; `identificadores-en-ingles.md` cuenta la clave como identificador.

    Sólo entra la clave que **puede ser un nombre** (``str.isidentifier``): una
    cabecera MIME o una ruta son datos, no símbolos.

    Se posiciona con ``col_offset``/``end_col_offset`` del nodo, que abarcan las
    comillas — por eso se reescribe el literal ENTERO con su comilla original,
    y no sólo su interior: reemplazar el interior exigiría saber cuántos
    caracteres ocupa el prefijo, y un literal ``r''`` o con comilla triple lo
    desplaza.
    """
    edits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Dict):
            continue
        for key in node.keys:
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            if key.value not in mapping or not key.value.isidentifier():
                continue
            if key.lineno != key.end_lineno:     # literal multilínea: no aplica
                continue
            if allowed is not None and key.lineno not in allowed:
                continue
            edits.append((key.lineno, key.col_offset, key.end_col_offset,
                          f"'{mapping[key.value]}'"))
    return edits


def rename_file(path, mapping, allowed=None, keys=False):
    """Devuelve cuántos tokens renombró. Escribe sólo si hubo alguno."""
    source = Path(path).read_text(encoding='utf-8')
    lines = source.splitlines(keepends=True)
    edits = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.NAME or token.string not in mapping:
            continue
        if token.start[0] != token.end[0]:       # token multilínea: no aplica
            continue
        if allowed is not None and token.start[0] not in allowed:
            continue
        edits.append((token.start[0], token.start[1], token.end[1],
                      mapping[token.string]))
    if keys:
        edits += dict_key_edits(source, mapping, allowed)
    for row, start, end, new in sorted(edits, reverse=True):
        line = lines[row - 1]
        lines[row - 1] = line[:start] + new + line[end:]
    if edits:
        Path(path).write_text(''.join(lines), encoding='utf-8')
    return len(edits)


def main(argv=None):
    require_interpreter()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--map', required=True,
                        help='archivo con "viejo nuevo" por línea')
    parser.add_argument('--lines', default=None,
                        help='acota el renombre a estos números de línea')
    parser.add_argument('--keys', action='store_true',
                        help='renombra tambien la CLAVE de un dict literal '
                             '(opt-in: una clave puede ser un contrato que el '
                             'AST no ve — un acceso por literal en otro '
                             'archivo, un campo de respuesta, una clave de '
                             'configuracion)')
    parser.add_argument('files', nargs='+')
    args = parser.parse_args(argv)

    mapping = load_map(args.map)
    allowed = allowed_lines(args.lines) if args.lines else None

    total = 0
    for path in args.files:
        renamed = rename_file(path, mapping, allowed, args.keys)
        total += renamed
        print(f'{path}: {renamed} token(s) renombrado(s)')
    scope = (f'{len(args.files)} archivo(s); {len(mapping)} renombre(s) '
             f'declarado(s)' + (f'; acotado a {len(allowed)} línea(s)'
                                if allowed is not None else ''))
    print(f'total: {total} token(s) (alcance medido: {scope})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
