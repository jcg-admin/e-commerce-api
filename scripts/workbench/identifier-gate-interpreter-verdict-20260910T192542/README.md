# identifier-gate-interpreter-verdict

## El encargo

Dos tareas del tablero: que el gate de identificadores no ve una clave de dict
(#302) y que ningun gate ve un termino tecnico traducido a una palabra española
atestiguada (#303). La pregunta que las precede la hizo el ejecutor: *«esto
tiene relacion con un diccionario que se supone que instalamos, como thyrox es
el PROVEEDOR, todo ese mecanismo se tiene que instalar en thyrox para que los
demas lo consuman, cierto? como se instala?»*

## La premisa, si se corrigio al primer comando

Se corrigio dos veces.

1. Primera version: *«nadie instala el lexico, esta ahi por accidente del
   contenedor»*. Falsa por el metodo: se midieron dos manifiestos y se concluyo
   sobre tres arboles.
2. Segunda: el lexico lo instalo `kaupamex-docs` cuando era el PRODUCER, de
   forma imperativa y sin declararlo. No aparecia en ningun manifiesto porque
   **THYROX no tenia `pyproject.toml` en absoluto**: su mitad Python no
   declaraba nada. La deuda estaba nombrada desde #183.

## Las piezas

| archivo | que hace |
|---|---|
| `probes/probe_verdict_by_interpreter.py` | corre el punto de entrada del consumidor con dos interpretes y compara veredicto |
| `probes/probe_corpus_exclusion.py` | por palabra, su pertenencia al lexico cerrado, a las particulas y al corpus, por separado |
| `probes/probe_dict_key_population.py` | la poblacion de claves de dict en español, por raiz |

Los tres se lanzaron con el ensamblador del proveedor
(`thyrox: src/session/run-task-pool.sh`), no a mano: tres trabajos, anchura 3,
barrera en primer plano y veredicto por trabajo.

## Los resultados

`verdicts_agree: false`. Mismo arbol, mismo baseline, mismos 2587 archivos:

- `python3` 3.11.15, corpus **True** — exit 1, «FAIL — 2994 fuera del baseline»
- `uv run python` 3.12.3, corpus **False** — exit 0, «OK: identificadores en ingles»

Lo decide **quien puede importar el corpus**, y el gate no lo comprueba:
`corpus_available()` tiene **0 consumidores** en el propio archivo, aunque su
docstring declara que *«el gate REHUSA sin ellos, no publica un cero»*.

Cinco palabras las atrapa **solo** el corpus, ninguna esta en el lexico cerrado
ni en las particulas: `ir`, `vals`, `es`, `q`, `iban`. Es H-DOCS-1139 medido
por conducta.

Claves de dict en español: **859 ocurrencias** sobre 3145 archivos. La mas
frecuente es `codigo_error` ×269 — el canon de error del propio proyecto. Una
extension global del gate la marcaria 269 veces.

*Metrica:* la del `manifest.json`, clave `metric`.
*Ciega a:* la del `manifest.json`, clave `blind_to`.
