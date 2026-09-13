# Frontera del porte de `odoo/orm/` — medida, no recordada

Fecha: 2026-09-11T17:44:03
Rama: feature/kaupamex-l5
Referencia: `odoo19c` (`odoo-tools`, sólo lectura)

## Qué falta, con su comando

```bash
python3 scripts/census_orm_reference.py --global
```

**28 de 209** símbolos de nivel superior de `odoo/orm/` no están en `src/orm/`
(modo global: corrige la sobre-cuenta por archivo buscando el nombre en toda la
raíz). El desglose por nombre está en `outputs/ausentes-por-archivo.txt`.

Dos cúmulos concentran **19 de los 28**: `models.py` (12) y
`model_classes.py` (7) — que son las tareas #318 y #319.

## El hallazgo de este pase: la costura de fusión NO está en el campo

Iba a construir un recorrido del MRO dentro de
`_field_contribute_to_class`. **La referencia no tiene eso.** Medido:

| # | Dónde | Qué hace |
|---|---|---|
| 1 | `odoo19c: odoo/orm/fields.py:397` | `owner._field_definitions.append(self)` en `__set_name__`, y **sólo** si `getattr(owner,'pool',None) is None` — o sea sólo sobre clases de definición, no sobre las del registro |
| 2 | `odoo19c: odoo/orm/models.py:229` | `MetaModel.__new__` hace `attrs.setdefault('_field_definitions', [])` — la lista por clase |
| 3 | `odoo19c: odoo/orm/model_classes.py:370-374` | `for cls in reversed(model_cls._model_classes__)`: acumula `definitions[field.name]` en orden de override |
| 4 | `odoo19c: odoo/orm/model_classes.py:411-415` | si hay UNA definición directa del propio modelo, se usa tal cual; si no, `Field = type(fields_[-1])` y `add_field(model_cls, name, Field(_base_fields__=tuple(fields_)))` |

`grep -rn "_base_fields__" $ODOO19C/odoo/orm/` da **un solo** sitio de
población: `model_classes.py:415`. Una sola construcción, en la fase de
registro, con la jerarquía ya resuelta.

### Lo que esto corrige

- El recorrido del MRO desde el campo habría sido **invención**: la fuente
  recoge en la fase de registro, no en la contribución del campo. Es la señal
  (5) de la lección — un problema que aparece al portar y que la fuente no
  tiene.
- `type(fields_[-1])` responde la pregunta que me tenía atascado: **la clase
  del override más derivado decide** la clase del campo resultante. El
  `isinstance(self, type(field))` de `_get_attrs` descarta después lo
  heredado de las ocurrencias incompatibles.

### Consecuencia de alcance

La fusión no se puede cablear con fidelidad hasta que estén `MetaModel`,
`_field_definitions` y `_setup`/`_setup_fields` — tres de los 28 ausentes.
El merge (`_field_get_attrs`, `orm/fields.py:1105-1128`) YA está portado
verbatim, incluida la regla `attrs.clear()`; lo que falta es su **entrada**.

*Métrica:* símbolos de nivel superior por AST (ClassDef, FunctionDef, Assign
simple) de `odoo/orm/*.py` contra todo `src/orm/`.
*Ciega a:* los métodos dentro de una clase (para eso está
`check_porte_completo`), y al símbolo portado con otro nombre, que cuenta
como ausente.
