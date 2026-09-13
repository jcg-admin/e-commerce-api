# Anulación por pieza — el control que discrimina

Fecha: 2026-09-11T11:45:48

Cada pieza del resolutor se retira por separado y se mide **qué aserciones
caen**. Un control que no cambia de veredicto al quitarle la causa no estaba
midiendo la causa (sub-patrón D de `metrica-decide-la-conclusion.md`).

Sujeto: `tests/unit/orm/test_deferred_model_name.py`, **16 casos**, todos en
verde con el árbol intacto.

| Pieza retirada | Qué se sustituyó | Caen | Cuáles |
|---|---|---|---|
| **(a) el vaciado** | `apps.lazy_model_operation(_flush_sentinels, …)` → `pass` | **2** | referente-primero · auto-referencia |
| **(b) la resolución inmediata** | la rama `model_by_name(...)` → `registered = None` | **5** | los tres de M18 · las dos del radio de migración · destino-primero |
| **(c) la traducción entera** | `_translate_comodel` devuelve `args` sin tocar | **8** | los 5 de (b) + los 2 de (a) + el que mide `comodel_name` |

Los conteos se leen de los tres `.txt` de este directorio, que son la salida
verbatim de `pytest` bajo cada mutación.

## Lo que cada caída significa

- **(a)** aísla el vaciado a los dos órdenes que **no** puede servir la
  resolución inmediata: cuando el destino todavía no existe al construir el
  campo. Ni uno más: los otros catorce no dependen de él.
- **(b)** muestra que el positivo de M18 —`fields.Many2one('ir.model.fields')`—
  lo sirve la rama de **destino-primero**: `IrModelFields` ya está cargado
  cuando un cuerpo de clase nuevo lo nombra, así que su `class_prepared` ya
  pasó y ningún vaciado posterior llegaría.
- **(c)** es el superconjunto de las dos, más el caso que afirma que el nombre
  de la fuente sobrevive en `comodel_name`. Los ocho que **sobreviven** son los
  que no dependen de la traducción: las tres formas que ya funcionaban
  (etiqueta de Django, clase, `'self'`) y los cuatro que miden la etiqueta
  centinela como función pura.

## Restauración verificada

```
grep -rc 'ANULADO' src/orm/registry.py src/orm/fields_relational.py
src/orm/registry.py:0 src/orm/fields_relational.py:0
```

---

## (d) — sin la consulta a `apps.get_model` (2026-09-11T12:00:10)

**Pieza retirada.** La rama de `_deferred_comodel` que pregunta a Django si la
cadena en minúsculas ya nombra un modelo suyo:

```python
if comodel.count('.') == 1:          # -> if False:  # ANULADO (d)
    try:
        apps.get_model(comodel, require_ready=False)
```

**Qué cae.** Los **17** casos del archivo, y no como fallo sino como error de
*setup*: el árbol entero deja de levantarse.

```
E   ValueError: The field base.IrActionsReport.group_ids was declared with a
    lazy reference to 'orm.base_resgroups', but app 'orm' isn't installed.
E   The field base.IrActionsReport.paperformat_id was declared with a lazy
    reference to 'orm.base_reportpaperformat', but app 'orm' isn't installed.
```

**Lectura.** La granularidad de este control es el **árbol**, no el caso: la
rama es carga estructural, no una comodidad para un test. Su positivo es real
y está nombrado —dos campos de `base.IrActionsReport` declarados en
`0069_ir_actions_report_group_ids_and_paperformat_id.py`— y el censo de M23 lo
extiende a **41 etiquetas en 31 archivos de migración**.

Que fellen los 17 y no uno **no** hace al control menos discriminante: fella
por una causa nombrada, distinta de la de (a), (b) y (c), y ninguna de ésas
produce este error. Lo que no puede hacer es aislar el caso nuevo
`test_the_django_label_in_lowercase_is_untouched` del resto — para eso haría
falta una anulación que no rompiera `django.setup()`, y la rama que se retira
es justo la que lo sostiene.

**Restauración verificada:** `sha256sum` idéntico al de antes de la anulación y
`grep -c 'ANULADO'` → 0.

### Tabla completa tras (d)

| Pieza retirada | Caen | Cuáles |
|---|---|---|
| (a) el vaciado | 2 | referente-primero · auto-referencia |
| (b) la resolución inmediata | 5 | los tres de M18 · las dos del radio de migración · destino-primero |
| (c) la traducción entera | 8 | los 5 de (b) + los 2 de (a) + el de `comodel_name` |
| **(d) la consulta a `apps.get_model`** | **17 (todos)** | el árbol no levanta: 41 etiquetas `label_lower` van al centinela |
