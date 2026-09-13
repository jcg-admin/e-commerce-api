# census-open-api-tasks

## El encargo

> «vamos a cambiar y revisar todas las TASK viven en thyrox/agent-results/agent_store.sqlite3 ,
> las ultimas las estas registando y estas usando los ID correspondientes? de TODAS las TASK
> que estan en thyrox/agent-results/agent_store.sqlite3 cuales ya estan cerradas? y porque no
> se ejecuta un script que cuando las terminamos de implementar se cierren?»
>
> «para analisizar las TASK de API usa estos directorios,
> THYROX_WORKBENCH_API=/home/user/kaupamex-api/scripts/workbench/
> THYROX_JOBS_API=/home/user/kaupamex-api/scripts/evidence/»

Este banco responde la parte **API**. Su hermano de `docs` vive en
`kaupamex-docs: .claude/eventos/close-open-docs-tasks-20260912T100232/` y está
**congelado**: su `probes/` conserva el instrumento que produjo sus `outputs/`.
Lo reusable se portó al proveedor — `thyrox: src/task/census_open_tasks.py` —
porque la TASK es del proveedor, y porque editar el probe congelado en su sitio
habría repetido la falla de procedencia que su propio README ya registra.

## El universo, declarado antes de medir

| Criterio | filas | abiertas |
|---|---|---|
| `submodule = 'api'` | 473 | **284** (268 `pending` + 16 `in_progress`) |
| `citation_id LIKE 'TASK-API-%'` | 427 | 252 |

**Los dos son válidos y miden poblaciones distintas.** La columna `submodule`
es clasificación y el prefijo de la cita es identidad — `correct_layer` lo
declara: *«el id es identidad, no clasificación»*. Una fila acuñada `GEN` y
luego clasificada `api` entra por el primer criterio y no por el segundo; de
hecho tres del cubo `closed_in_tree` son `TASK-GEN-`.

El censo mide el **primero**: 284. Las 16 `in_progress` no se descartan — una
tarea en curso también puede estar cerrada de hecho.

## Los tres cubos

| cubo | n de 284 | qué significa |
|---|---|---|
| `closed_in_tree` | **35** | un commit de alguno de los seis árboles nombra su cita: el trabajo aterrizó y el store no se enteró |
| `owned_but_open` | **25** | prosa o código las citan, pero ningún commit las nombra |
| `orphan` | **224** | sólo aparecen en el render del tablero: nadie ha trabajado en ellas |

Las **35** del primer cubo son la respuesta operativa a la pregunta del
encargo: son las que un escritor de actualización habría cerrado, y siguen
`pending` o `in_progress`. Su lista completa está en el `.log`.

Contra el hermano de `docs` —412 abiertas, 57/33/322— la forma es la misma: el
cubo dominante es `orphan` (79 % aquí, 78 % allá) y el de trabajo aterrizado no
llega al 15 % en ninguno de los dos.

*Métrica:* filas con `submodule='api'` y `status != 'completed'`, repartidas por
la aparición de su `citation_id` en el mensaje de un commit (`git log --all` de
las seis raíces) y, si no, en el contenido de un archivo que no sea render del
tablero.
*Ciega a:* un commit que cierre la tarea **sin nombrar su cita** —cae en
`owned_but_open` o en `orphan`—; y a si el trabajo del commit **terminó**:
nombrar la cita prueba que aterrizó, no que cerró. `closed_in_tree` es una lista
de triaje, no un veredicto de cierre.

## El alcance son SEIS raíces, no cinco

`reach.reach_roots()` devuelve `('api','db','docs','server','ui')` — **no**
thyrox. Es correcto para lo que ese mecanismo responde: *«hasta dónde alcanza el
trabajo de un consumidor»*. El censo pregunta otra cosa —*«¿qué commit de qué
árbol nombra esta cita?»*— y hay commits de este árbol que la nombran: dos de
las 35 se cierran con `thyrox@a5518ab7` y `thyrox@114f3777`.

Por eso `census_roots()` compone `reach.paths()` con `thyrox_root()` en vez de
reusar `reach()` tal cual.

## El instrumento se leyó a sí mismo, y el control lo destapó

La **segunda** ejecución, con el instrumento sin corregir, publicó esto:

| | 1ª ejecución | 2ª ejecución | 3ª, con el arreglo |
|---|---|---|---|
| `closed_in_tree` | 35 | 35 | 35 |
| `owned_but_open` | 25 | **249** | 25 |
| `orphan` | 224 | **0** | 224 |

De las 249, **las 249** estaban citadas por
`kaupamex-api/scripts/evidence/census_open_api_tasks.json` —la salida de la
primera ejecución— y 25 más por su log. El cubo `orphan` es justo el que el
instrumento existe para poder afirmar, y se vació entero.

La causa no era la lista de descuento: era que **el descuento es parámetro del
corpus y estaba escrito como constante**. `/outputs/`, `/salidas/`,
`/reportes/`, `/preimagen/` describen el árbol de `docs`; el destino de `api` es
`scripts/evidence/`, que no está en ninguna. Corregido en `thyrox@36052983`:
`is_render` acepta `extra_parts` y `own_output_parts` deriva el tramo del
`--out-dir` resuelto contra su raíz.

**Lo que lo destapó no fue releer el guion**: fue que dos ejecuciones idénticas
dieran cifras distintas, y que la tercera —ya corregida— reprodujera **exacto**
el 224 de la primera. Ésa es la medición: 224 = 224, con la contaminada en medio.

## Decisión pendiente del ejecutor — `Refs:` no es `Closes:`

El encargo pregunta *«¿por qué no se ejecuta un script que las cierre?»*. El
hermano de `docs` ya midió que **el propagador existe** —`board_sync.py
reconcile_status`, tres `UPDATE tasks SET status` en el subsistema— y que su
universo son **las tarjetas del board**, no las filas del store. Lo que falta es
un escritor que **cierre desde el commit**.

Construirlo exige una decisión que no es derivable, y por eso se declara aquí en
vez de tomarse:

**¿Qué remolque de commit autoriza a cerrar?** Hoy `Refs:` es el único que el
proyecto usa, y significa *«este commit tiene que ver con esa tarea»* — no
*«la cierra»*. Un cerrador que dispare sobre `Refs:` cerraría las 35 de este
cubo y las 57 del de `docs` **sin que nadie lo haya afirmado**, y varias son
tareas de barrido con trabajo por delante: `TASK-API-0396` («barrer los 1265
identificadores») tiene commit y sigue viva por construcción.

Las dos salidas, con su coste:

1. **Adoptar `Closes:` como remolque distinto.** El cerrador dispara sólo con
   él; `Refs:` sigue significando lo que significa. Coste: prospectivo — nada
   histórico se cierra solo, y las 35 + 57 quedan como lista de triaje manual.
2. **Cerrar con `Refs:` y aceptar el falso positivo.** Coste: cierra tareas
   vivas, y el eje que distingue «aterrizó» de «terminó» se pierde — que es
   exactamente la ceguera que este censo declara y no puede ver.

**La lista de triaje que la decisión necesita** son las 35 de aquí y las 57 del
banco de `docs`, ya identificadas con su `repo@hash`. Sucesor registrado:
**TASK-DOCS-0405**; los dos sucesores del banco hermano —**TASK-THYROX-0020** y
**TASK-THYROX-0021**— cubren el propagador y la deriva de capa.

## Las piezas

| archivo | qué hace |
|---|---|
| `manifest.json` | las cinco claves obligatorias más `corrected_premise` y `control` |
| `scripts/evidence/census-open-api-<ISO>.log` | la salida de la ejecución corregida, con su `EXIT=` |
| `scripts/evidence/census_open_api_tasks.json` | los tres cubos con commits, archivos citantes y `:estado:` del hallazgo |

Reproducible:

```bash
python3 /home/user/thyrox/src/task/census_open_tasks.py --layer api \
    --out-dir /home/user/kaupamex-api/scripts/evidence
```
