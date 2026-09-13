# Operaciones de archivo van por Bash — cheat-sheet (canónico en thyrox)

Regla completa: `thyrox: .claude/rules/operaciones-de-archivo-con-bash.md`. Aquí
sólo el invariante operativo (THYROX es el proveedor; esta regla vive ahí y
los cinco consumidores la heredan):

Leer, buscar y editar va por Bash — `cat`, `sed -n`, `grep`, `find`, `awk`,
`sort`, `uniq`, `comm`, `cut`, `paste`, `xargs`, heredocs. `Read`, `Edit` y
`Write` quedan para lo que Bash genuinamente no puede — binario, imagen,
notebook. Escribir un archivo entero (`Write`) es la misma operación que
`cat > archivo`: se mira antes con `test -e` si ya existía.

**Gate:** `thyrox: src/hooks/detect_dedicated_tool_usage.py`, sexto detector
de `pretooluse_dispatch.py`. Avisa (no bloquea) vía `additionalContext` sobre
`Write`/`Edit`/`Read` de texto plano, con el equivalente Bash exacto. Sus dos
mitades de juicio (extensión binaria/de medio; colisión de delimitador EOF)
se probaron por anulación — retirar cada una hace caer exactamente 3 de 13
casos, ni uno más.

**Su cableado en ESTE repo es parámetro del consumidor** (DEC-04), y hereda la
precondición de H-DOCS-1010: bajo el harness remoto, con cwd en `/home/user`,
un `settings.json` de directorio adicional aporta `CLAUDE.md` y
`.claude/rules/`, **no hooks**. Mientras eso siga así el detector existe y no
dispara aquí — la regla sigue siendo la que gobierna, y este párrafo es su
declaración de inercia (mismo patrón que el quinto detector en
`trabajo-en-segundo-plano.md`).

Origen: ERR-063 (2026-09-09) midió que la directiva nunca llegaba al prompt
de un subagente; su sucesor citado por ordinal (`#287`) colisionó con otros
dos sujetos en el store. Sucesor con cita durable: **TASK-THYROX-0016**.
