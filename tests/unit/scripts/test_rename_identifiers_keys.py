"""El renombrador ve simbolos declarados y NO ve una clave de diccionario.

Es la contraparte, en el instrumento de BARRIDO, del defecto que el gate de
identificadores tenia: `identificadores-en-ingles.md` cuenta la clave como
identificador —«claves de manifiesto: una clave es un atributo»— y
`rename_identifiers.py` renombra tokens ``NAME``. Una clave es un literal
``STRING``, asi que el barrido la dejaba atras **en silencio**: el guion
publicaba «0 token(s) renombrado(s)» y el nombre espanol seguia ahi.

El caso NO esta fabricado: es `scripts/audit_ucs.py` de `kaupamex-docs`, cuyas
seis claves `parte_1..6` sobrevivieron al renombre del 2026-09-10 con el mapa
delante. Se reproduce su forma —dict de claves a patrones, consumido por
`.items()`— porque el archivo vive en otro repositorio.

Por que la clave es OPT-IN y el simbolo no
------------------------------------------
Renombrar una clave puede romper un contrato que el AST no ve: un acceso por
literal en otro archivo, un campo de la respuesta de un API, una clave de
configuracion. `codigo_error` es el caso vivo — 270 ocurrencias en `addons/`,
y su propia normativa MANDA escribirlo asi. Por eso `--keys` se pide, no se
asume: el default sigue midiendo solo lo que no puede romper un contrato.
"""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'rename_identifiers.py'

#: La forma real de `audit_ucs.py`: claves a patrones, leidas por `.items()`.
#: La f-string es deliberada — es donde 3.11 se queda ciego (H-API-607), asi
#: que el caso mide de paso que el guard sigue siendo necesario.
SOURCE = '''
import re

REQUIRED_PARTS = {
    'parte_1': re.compile(r'PARTE 1'),
    'parte_2': re.compile(r'PARTE 2'),
    'application/json': 1,
}


def report(parte_1):
    """La `parte_1` de la prosa NO se toca: es espanol legitimo."""
    return f'{parte_1} y {REQUIRED_PARTS}'
'''


@pytest.fixture
def target(tmp_path):
    path = tmp_path / 'audit.py'
    path.write_text(SOURCE, encoding='utf-8')
    return path


@pytest.fixture
def mapping(tmp_path):
    path = tmp_path / 'map.txt'
    path.write_text('parte_1 part_1\nparte_2 part_2\n', encoding='utf-8')
    return path


def run(target, mapping, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), '--map', str(mapping), *extra, str(target)],
        capture_output=True, text=True)


def test_the_default_renames_the_symbol_and_leaves_the_key(target, mapping):
    """Sin `--keys` el default no toca contratos: el simbolo si, la clave no."""
    assert run(target, mapping).returncode == 0
    output = target.read_text(encoding='utf-8')
    assert 'def report(part_1):' in output
    assert "'parte_1': re.compile" in output


def test_keys_renames_the_dict_key(target, mapping):
    """EL QUE DISCRIMINA: con `--keys` la clave del dict entra al renombre."""
    result = run(target, mapping, '--keys')
    assert result.returncode == 0, result.stderr
    output = target.read_text(encoding='utf-8')
    assert "'part_1': re.compile" in output
    assert "'part_2': re.compile" in output
    # Ninguna CLAVE conserva el nombre viejo. La prosa del docstring SI lo
    # conserva, y debe: es espanol legitimo, y `test_keys_leaves_prose_alone`
    # lo afirma. Un `'parte_1' not in output` a secas mediria las dos cosas a
    # la vez y fallaria por la que esta bien.
    assert "'parte_1':" not in output and "'parte_2':" not in output


def test_keys_leaves_a_literal_that_is_not_an_identifier(target, mapping):
    """Una cabecera MIME es dato, no simbolo: sigue intacta."""
    run(target, mapping, '--keys')
    assert "'application/json'" in target.read_text(encoding='utf-8')


def test_keys_leaves_prose_alone(target, mapping):
    """La guarda de prosa sigue en pie: el docstring conserva su espanol."""
    run(target, mapping, '--keys')
    output = target.read_text(encoding='utf-8')
    assert 'de la prosa NO se toca: es espanol legitimo' in output


def test_keys_counts_the_key_it_renamed(target, mapping):
    """El conteo publicado incluye la clave; sin eso el barrido no se audita."""
    default = run(target, mapping).stdout
    target.write_text(SOURCE, encoding='utf-8')
    with_keys = run(target, mapping, '--keys').stdout
    assert 'total: 2 token' in default
    assert 'total: 4 token' in with_keys
