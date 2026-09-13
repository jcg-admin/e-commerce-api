"""El puente que delega en THYROX, medido — no el mecanismo, que ya no vive aquí.

Cierra el hueco que dejó mudar `check_identifier_language.py` a THYROX
(DEC-04, actualizar-agentic-ai-thyrox): retirar `test_check_identifier_language.py`
y `test_identifier_language_corpus.py` sin dejar nada en su lugar habría sido
una PÉRDIDA de cobertura por ausencia, no una declaración — y el mecanismo (AST,
léxico, corpus) es ahora responsabilidad de la suite de thyrox
(`thyrox: tests/gates/test_identifier_language*.py`), no de esta.

Lo que SÍ es responsabilidad de `api`, y lo que este archivo mide: que el
PUENTE resuelva a thyrox, propague el baseline correcto y el código de salida
real. No se reimplementa aquí ninguna prueba del criterio lingüístico —eso
sería la segunda fuente de verdad que `calibration-verified-numbers.md`
prohíbe— sólo el contrato del stub.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / 'scripts'
STUB = SCRIPTS / 'check_identifier_language.py'
sys.path.insert(0, str(SCRIPTS))

import check_identifier_language as stub  # noqa: E402


class TestStubResolvesTheProvider:

    def test_it_finds_thyrox_as_a_sibling(self):
        """Sin THYROX_ROOT declarado, el hermano `<arbol>/thyrox` basta."""
        gate = stub.thyrox_gate()
        assert gate is not None
        assert gate.name == 'check_identifier_language.py'
        # `src/verify/`, no `src/gates/`: el mecanismo se mudo al cerrar
        # TASK-API-0301 y el stub ya lo apunta ahi (`:51`, `:55`).
        assert gate.parent.name == 'verify'

    def test_a_declared_thyrox_root_wins(self, tmp_path, monkeypatch):
        """La variable declarada gana sobre el hermano — mismo criterio que
        el resto del multi-repo (`THYROX_ROOT` en `lint_agents.py`)."""
        fake_gate = tmp_path / 'src' / 'verify' / 'check_identifier_language.py'
        fake_gate.parent.mkdir(parents=True)
        fake_gate.write_text('# stand-in\n')
        monkeypatch.setenv('THYROX_ROOT', str(tmp_path))
        assert stub.thyrox_gate() == fake_gate

    def test_without_thyrox_it_refuses_with_2(self, monkeypatch):
        """Sin proveedor alcanzable, NO se emite veredicto — exit 2, sin cifra."""
        monkeypatch.setattr(stub, 'thyrox_gate', lambda: None)
        assert stub.main(['check_identifier_language.py']) == 2

    def test_a_declared_but_nonexistent_thyrox_root_refuses(self, monkeypatch):
        """Si THYROX_ROOT SE DECLARA y no resuelve, se rehúsa — NO se busca
        por detrás del hermano. La variable existe para que el consumidor
        decida dónde está el proveedor; si la búsqueda cae al hermano de
        todos modos, la variable es decorativa (defecto real, corregido en
        el mismo commit que este test — reportado por el coordinador tras
        medir ``THYROX_ROOT=/no/existe`` y obtener el mismo FAIL que sin
        declarar nada).

        El hermano real (``<arbol>/thyrox``) SIGUE presente en este entorno
        mientras se corre este test — es la condición que hace que el caso
        discrimine: si el fix cae, este test vuelve a pasar por la vía
        equivocada (el hermano), no porque la guarda de rehúse funcione."""
        assert stub.thyrox_gate() is not None, (
            'el hermano tiene que existir para que este test discrimine — '
            'si no hay hermano, un `is None` sería un false-positive del fix')
        monkeypatch.setenv('THYROX_ROOT', '/no/existe/thyrox-root-inexistente')
        assert stub.thyrox_gate() is None


class TestStubPropagatesThisTreesBaseline:
    """El baseline es de API, no de THYROX (DEC-04) — el stub lo declara."""

    def _run(self, *args, env=None):
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run([sys.executable, str(STUB), *args],
                               capture_output=True, text=True, env=e)

    def test_an_english_only_file_passes(self, tmp_path):
        target = tmp_path / 'clean.py'
        target.write_text('def passed():\n    return 1\n')
        done = self._run(str(target))
        assert done.returncode == 0
        assert 'OK' in done.stdout

    def test_a_fresh_spanish_identifier_fails(self, tmp_path):
        target = tmp_path / 'dirty.py'
        target.write_text('def hallazgo_nuevo():\n    return 1\n')
        done = self._run(str(target))
        assert done.returncode == 1
        assert 'hallazgo_nuevo' in done.stdout

    def test_an_explicit_baseline_override_wins_over_the_default(self, tmp_path):
        """`setdefault`: quien invoca puede declarar OTRO baseline — p. ej.
        para medir un archivo aislado sin la deuda heredada real de por medio."""
        target = tmp_path / 'dirty.py'
        target.write_text('def hallazgo_nuevo():\n    return 1\n')
        baseline = tmp_path / 'baseline.txt'
        baseline.write_text(f'{target}::hallazgo_nuevo\n')
        done = self._run(str(target),
                          env={'IDENTIFIER_LANGUAGE_BASELINE': str(baseline)})
        assert done.returncode == 0, done.stdout + done.stderr


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
