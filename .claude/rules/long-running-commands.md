# Long-running commands — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/long-running-commands.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Comandos >5 min en background (nohup & disown / Monitor con tail -f --pid); nunca foreground >5 min ni sleep largo (dispara SSE timeout).

**El ensamblador ya existe — no se escribe el `nohup` a mano** (2026-09-11,
:ref:`h-docs-1256`). `bg.sh` lanza uno, `run-task-pool.sh` lanza N con la
anchura acotada a `nproc`, `wait-jobs.sh` es la barrera y `marker_wait.py`
distingue «murió» de «timeout». Los cuatro viven en
`"${THYROX_ROOT:-/home/user/thyrox}"/src/session/`:

```bash
T="${THYROX_ROOT:-/home/user/thyrox}"
printf '%s\n' "cmd1" "cmd2" "cmd3" | bash "$T/src/session/run-task-pool.sh" -
```

El criterio de despacho está medido, no es estético: un trabajo en segundo
plano es un **proceso** y cuesta **cero** tokens; un subagente es una
**conversación** que paga en frío el piso siempre-cargado —126 029 tokens—
**por turno**. El agente rinde con trabajo ancho y con juicio; una tanda de
comandos deterministas no lo es. Con thyrox fuera del alcance de la sesión, el
`nohup … & disown` sigue siendo el respaldo.
