# Atributos de clase de modelo — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/atributos-de-clase-de-modelo.md` (v2.0.0).
Aquí sólo el invariante operativo:

**Si la clase de la referencia declara atributos de clase, se portan TODOS los
que declare. Si no declara ninguno, no se inventa ninguno.**

> **v1 estaba mal** y decía *"todo modelo declara `_name` y `_description`"*.
> Medido sobre 3344 clases de `odoo19c`: sólo el **35 %** declara `_name` (el
> resto son **extensiones**, con `_inherit` y sin nombre propio), y el universo
> es de **al menos 24** atributos, no dos. Coste: el porte de `stock_picking.py`
> declaró **2 de 5** en cada clase y se presentó como completo (:ref:`h-api-580`).

## El procedimiento es un comando, no una lista de memoria

```bash
python3 scripts/census_class.py "$ODOO19C/addons/<x>/models/<y>.py" <Clase> --prefix _
```

> **Corregido 2026-09-11 (TASK-API-0320).** Aquí vivía un `python3 -c` que
> recorría **sólo** `ast.Assign`. Los 28 atributos que `BaseModel` declara —y
> entre ellos los 24 que esta regla legisla— son `ast.AnnAssign`, que es otro
> nodo. Medido sobre `odoo19c: odoo/orm/models.py`: `Assign=3`
> (`__slots__`, `id`, `display_name`) contra `AnnAssign=28`. Corrido contra la
> clase que **declara** el contrato, el comando publicaba 3 atributos y
> **ninguno** de los que la regla gobierna.
>
> La ceguera no era general: medido sobre tres modelos de addon
> (`stock_picking.py`, `sale_order.py`, `res_company.py`) hay **236 `Assign` y
> 0 `AnnAssign`**. La forma anotada vive en el núcleo — `odoo/orm/models.py`
> 28, `odoo/orm/fields.py` 49. El comando servía para el caso corriente y
> fallaba justo al ir a leer **cuál es** el contrato.
>
> La regla nombra ahora **el instrumento**, no una copia de su cuerpo: una
> segunda fuente de verdad en prosa es lo que `calibration-verified-numbers.md`
> prohíbe para una cifra, y vale igual para un recorrido. Su control positivo
> —`BaseModel` da 31, y cegar la rama `AnnAssign` hace caer exactamente 2 de
> los 7 casos— vive en `tests/unit/scripts/test_census_class.py`.

Lo que salga es el contrato. Cada atributo se porta o declara su divergencia;
ninguno se omite en silencio.

## Los más frecuentes (medidos en `odoo19c`)

`_inherit` 2588 · `_name` 1173 · `_description` 1099 · `_order` 379 ·
`_rec_name` 122 · `_check_company_auto` 76 · `_allow_sudo_commands` 41 ·
`_rec_names_search` 36 · `_inherits` 21 · `_auto` 16 · `_table` 15 ·
`_parent_store` 12 · `_log_access` 12. Universo declarado en
`odoo19c: odoo/orm/models.py:370-464`, cada uno con su comentario `#:`.

**Se declaran verbatim y NO sustituyen a su forma Django** — `_description`
convive con `Meta.verbose_name`, `_order` con `Meta.ordering`, `_table` con
`Meta.db_table` (que debe coincidir con `_name.replace('.', '_')`; lo verifica
`orm.registry.check_table_matches_name()`).

**Tres cosas distintas comparten el prefijo `_`:** los atributos de ORM (esta
regla); los **objetos de tabla** de 19 (`_name_uniq = models.Constraint(...)`,
`_x_index = models.Index(...)` — su hogar aquí es `Meta.constraints` /
`Meta.indexes`, con el nombre conservado); y las constantes de módulo
(`_OUTLOOK_SCOPE`), que se portan como constantes normales.

**Prospectivo:** modelo nuevo o portado, lleva los de su fuente; modelo
existente que se toca, se le completan. Sin barrido en bloque.

**Segunda cláusula — el SITIO del archivo** (H-API-578): antes de crear un
archivo en una raíz espejada (`src/orm` ↔ `odoo/orm`, `src/tools` ↔
`odoo/tools`, `addons/<x>` ↔ `addons/<x>`), **listar la raíz de la referencia**:

```bash
ls $ODOO19C/odoo/orm/     # ¿ya existe el hogar de este símbolo?
```

`check_porte_completo` compara símbolos **dentro de un archivo dado**: es
estructuralmente ciego a un archivo que la referencia no tiene, y **no mira los
atributos de clase en absoluto**. Gate de conjunto por raíz: tarea #334.
