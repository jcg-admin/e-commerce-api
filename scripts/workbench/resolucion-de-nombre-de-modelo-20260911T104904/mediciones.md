# Resolución de `_name` → modelo en una relación — mediciones

Todas de esta sesión, contra Django 6.0.5 instalado y `odoo19c`.

## M1 — el puerto NO introdujo ningún renombre
Los nombres de clase de `test_orm` de la referencia son `TestOrmCategory`,
`TestOrmDiscussion`, … verbatim (155 clases, 146 con `_name`).

## M2 — destinos relacionales en `test_orm.py` de la referencia
143 totales · 116 del mismo addon · 26 `res.*` · 1 `ir.*`.

## M3 — la referencia declara `_name` en los modelos que nuestro árbol no
`ResUsers._name = 'res.users'`, `ResPartner._name = 'res.partner'`;
los nuestros no lo declaran.

## M4 — la semilla: `fields.Many2one` devuelve un `ForeignKey` PELADO
```
tipo devuelto       : (ForeignKey, ForeignObject, RelatedField, FieldCacheMixin)
subclase de proyecto: False
contribute_to_class : django.db.models.fields.related  (no nuestro)
```
No hay `contribute_to_class` propio que interceptar: el único punto que
controlamos hoy es la función `fields.Many2one`, el mismo asiento donde vive
`_apply_ondelete`.

## M5 — dónde revienta un nombre de DOS puntos, y cuándo
`__init__` lo acepta sin tocarlo (`remote_field.model == 'test_orm.multi.line'`).
Revienta **al crear la clase**, por la vía perezosa de Django:

```
base.py:213  __new__
base.py:393  add_to_class
related.py:923 contribute_to_class
related.py:396 contribute_to_class
related.py:86  lazy_related_operation
utils.py:15/22 make_model_tuple  -> ValueError: Invalid model reference
```

`make_model_tuple` hace `app_label, model_name = model.split(".")`: un nombre
de dos puntos no cabe en su espacio de claves. **30 nombres distintos** de los
destinos de `test_orm.py` tienen dos puntos o más.

## M6 — referencias hacia ADELANTE en el mismo archivo
De los 116 destinos del mismo addon: **41 hacia adelante**, 72 hacia atrás,
3 fuera del archivo. Una sustitución en el momento de construir NO puede
resolver esas 41: la clase todavía no existe.

## M7 — el nombre de clase NO es función del `_name`
Medido sobre las **1103** clases con `_name` de `odoo19c/addons`:
**936 coinciden** con el CamelCase de su `_name` y **167 NO** (15 %).
Ejemplos: `l10n_id_efaktur_coretax.document` → `EfakturDocument`;
`l10n_latam.identification.type` → `L10n_LatamIdentificationType`;
`sale.edi.xml.ubl_bis3` → `SaleEdiXmlUbl_Bis3`.

Consecuencia: derivar el nombre de clase del `_name` con una transformación
sería una **invención**, falsa en el 15 % de los casos. La fuente nunca lo
deriva — resuelve por registro (`env[name]`).

## M8 — el espacio de claves de Django
`Apps.register_model` indexa por `model._meta.model_name` = `cls.__name__.lower()`,
bajo `all_models[app_label]`. Nuestro `base` da
`['baseenableprofilingwizard', 'checkoutattempt', …]` — nombres de clase, no
`_name`. Nuestro registro por `_name` ya existe y es `orm.registry.MODELS_BY_NAME`,
poblado por la señal `class_prepared` (`registry.py:387`).

## M9 — la relación muerta EN SILENCIO (2026-09-11T10:54:53)
Un nombre de **un solo punto** que no corresponde a ningún modelo registrado
NO levanta excepción. La clase se crea, `remote_field.model` se queda como
`str`, y `deconstruct()` emite la cadena en minúsculas:

```
clase creada sin excepcion : ProbeOneDot
remote_field.model         : 'base.companysettingXYZ'
tipo                       : str
-> operacion pendiente sobre una clave que NUNCA se registra: relacion muerta EN SILENCIO

resuelta  remote_field.model: <class 'addons.base.models.company_setting.CompanySetting'>
resuelta  deconstruct to=   : base.companysetting
NO resuelta deconstruct to= : base.companysettingxyz
```

Consecuencia para el control del resolutor (sub-patrón D de
`metrica-decide-la-conclusion.md`): un test que afirme *«no levanta
excepción»* pasaría con la relación muerta. **El control tiene que afirmar
`field.remote_field.model is <la clase>` después de `apps.populate()`**, no
la ausencia de error.

## M10 — el resolutor de Django, las dos líneas que un callback diferido reproduce
`django/db/models/fields/related.py:392-394`:

```python
def resolve_related_class(model, related, field):
    field.remote_field.model = related
    field.do_related_class(related, model)
```

y su registro en `:396-397` con `lazy_related_operation(...)`. El
`split(".")` sobre `remote_field.model` aparece además en `related.py:740` y
`:1816` — o sea que el **string con punto** es vocabulario vivo de Django en
más de un sitio, no sólo en `make_model_tuple`.

## M11 — el discriminador de vocabulario, medido
Sobre los `_name` de `odoo19c`:

```
_name medidos                      : 1472
con MAYUSCULA tras el primer punto : 0
```

Django nombra `app_label.ModelName` — segundo segmento **capitalizado**. La
fuente nombra `modulo.modelo` — segundo segmento **siempre en minúscula**, y
admite ≥2 puntos (`l10n_ar.afip.responsibility.type`). Por tanto
*«segundo segmento en minúscula, o ≥2 puntos»* separa los dos vocabularios
**sin registro**, que es exactamente lo que hace falta para una **referencia
adelantada**: ahí ni `'base.ResPartner'` ni `'test_orm.discussion'` están en
ningún registro todavía.

*Métrica:* la caja de la primera letra del segmento posterior al primer punto.
*Ciega a:* un `_name` de la fuente cuyo segundo segmento empezara con
mayúscula — 0 medidos hoy; si apareciera, el discriminador lo mandaría al
vocabulario de Django.

## M12 — dónde falla hoy un nombre de dos puntos
La traza de `test_orm.discussion.tag` (dos puntos) sube por el camino **de
Django**, no por el nuestro: `base.py:213 __new__` → `base.py:393
add_to_class` → `related.py:923` → `related.py:396 contribute_to_class` →
`related.py:86 lazy_related_operation` → `utils.py:15/22 make_model_tuple`.

Es decir: el fallo ocurre **al crear la clase**, no al construir el campo.
`Many2one.__init__` acepta la cadena intacta. Un resolutor que quiera ver
el nombre antes que `make_model_tuple` tiene que interponerse en
`contribute_to_class`, que es un método de instancia del campo.

## M13 — las tres relaciones NO están al mismo nivel
```
fields.Many2one  -> django.db.models.fields.related.ForeignKey       (desnudo)
fields.One2many  -> orm.fields_relational.One2many                   (clase propia)
fields.Many2many -> django.db.models.fields.related.ManyToManyField  (desnudo)
```

`One2many` ya es clase del proyecto; las otras dos son la clase de Django sin
envolver. Por eso el diferimiento **no puede vivir en la factoría de
`Many2one`**: al siguiente modelo con un `Many2many` hacia otro addon el
porte se vuelve a parar. El hogar tiene que cubrir las tres.

---

## M14 — la relación muerta NO es silenciosa en la creación de la base (2026-09-11T11:05:05)

M9 midió que declarar `Many2one('base.companysettingXYZ')` **no levanta
excepción** al construir la clase. Eso sigue siendo cierto y es sólo la mitad:
al crear la base de pruebas, la misma relación **aborta**.

Comando y salida (cola del traceback):

```
$ uv run pytest tests/unit/scripts/test_check_fk_naming.py -q --reuse-db \
      -k test_the_real_declaration_is_measured_as_faithful
django_db_setup -> setup_databases -> create_test_db -> migrate.handle
  -> sync_apps(connection, executor.loader.unmigrated_apps)
  -> editor.create_model -> table_sql -> column_sql
  -> related.py:1225 db_parameters -> :1115 target_field
  -> :804 foreign_related_fields -> :791 related_fields
  -> :1142/:771 resolve_related_fields
ValueError: Related model 'test_orm.category' cannot be resolved
```

**Dos hechos que esto fija, y ninguno estaba medido:**

1. **`src/addons/test_orm` YA está en `INSTALLED_APPS`.** No se declaró a
   mano: `base.py:115 LOCAL_APPS = _local_apps()` lo **deriva** del grafo de
   addons (`:83` — `('core',) + tuple(f'addons.{node.name}' for node in graph)`),
   así que basta el `__manifest__.py` para que entre. Contesta la incógnita de
   si el addon carga: carga, y sin tocar settings.
2. **Sus 153 modelos obtienen tabla por `sync_apps`**, la rama de
   *unmigrated apps* de `migrate`. Es ahí donde la FK se resuelve, y ahí donde
   el nombre punteado de la referencia no tiene destinatario en el espacio de
   claves de Django (M12).

**Consecuencia de orden, no de diseño:** el resolutor diferido deja de ser el
paso siguiente y pasa a ser el **bloqueo**. Con el addon en el árbol, la
creación de la base falla, y con ella **todo test que pida la fixture `db`** —
no sólo los del addon. Medido: los tests preexistentes de
`test_check_fk_naming.py` erroran igual que los nuevos.

*Métrica:* el traceback de `django_db_setup` en un `pytest` con `--reuse-db`
sobre la base QA caliente.
*Ciega a:* el caso en que el addon **no** esté en el árbol — ahí `sync_apps` no
ve sus 153 modelos y la relación muerta no existe; es exactamente la maniobra
de aislamiento que los controles del gate ADR-029 usaron para correr.

> **Corregida la ceguera declarada (2026-09-11T11:13:36).** Decía que el resultado podía dar
> «verde en una máquina y rojo en otra según el estado de su base». Es
> **empíricamente falso**: la corrida que produjo este traceback fue **con
> `--reuse-db` sobre la base QA ya caliente**, y falló igual. La causa es que
> `migrate` corre `sync_apps` sobre las apps sin migraciones en **cada**
> invocación y crea toda tabla ausente de `introspection.table_names()` — la
> base caliente no lo salta. El rojo es determinista en cualquier máquina con
> el addon presente.
>
> Una ceguera mal declarada es peor que ninguna: da por acotado un riesgo que
> no existe y deja sin nombrar el que sí (la ausencia del addon). Es el defecto
> que `metrica-decide-la-conclusion.md` existe para atrapar, cometido en la
> línea que lo declara.

## M15 — Django YA tiene nuestros nombres sin resolver, en su propio mapa

Medido 2026-09-11T11:18:16 con `PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing`
y el addon `test_orm` presente. `django.setup()` **completa sin error**: el
fallo de M14 es de esquema, no de carga.

```
clave real de Django    : ('test_orm', 'testormcategory')
label del AppConfig     : test_orm
tipo del campo          : django.db.models.fields.related.ForeignKey
remote_field.model      : test_orm.category        <- sigue siendo la CADENA
deconstruct ruta        : django.db.models.ForeignKey
pendientes sin resolver : {('test_orm','discussion'): 3,
                           ('test_orm','category'): 4,
                           ('res','users'): 4}
```

**Dos hechos que cambian el diseño:**

1. **El radio de `deconstruct()` es CERO hoy**, y lo seguirá siendo si no se
   introduce una subclase: `Many2one` devuelve un `models.ForeignKey` llano,
   así que la ruta que emite es `django.db.models.ForeignKey`. Una subclase la
   cambiaría y pondría en rojo `makemigrations --check` de toda app migrada.
   El resolutor **no necesita subclase**.
2. **Las once operaciones pendientes ya están ahí**, bajo la tupla mal
   derivada. No hay que construir un mapa: hay que **vaciar el que existe** con
   la clave correcta.

## M16 — Qué guarda cada pendiente, y con qué se vacía

```
--- clave ('test_orm', 'category')  (4 operaciones)
    functools.partial(RelatedField.contribute_to_class.<locals>.resolve_related_class,
                      <class 'addons.test_orm.models.test_orm.TestOrmCategory'>,
                      field=<ForeignKey: parent>)
```

Y el cuerpo que espera, verbatim
(`django/db/models/fields/related.py:392-394`)::

    def resolve_related_class(model, related, field):
        field.remote_field.model = related
        field.do_related_class(related, model)

El vaciador de Django, verbatim (`django/apps/registry.py:428-435`)::

    def do_pending_operations(self, model):
        key = model._meta.app_label, model._meta.model_name
        for function in self._pending_operations.pop(key, []):
            function(model)

**El stack lo trae hecho.** El mapa, los `partial` y el vaciador existen los
tres. Lo único ausente es resolver la clave **alias** — la que sale de
`make_model_tuple('test_orm.category')` — además de la real.

Es además la forma de la referencia: `Field.comodel_name` es una **cadena**
(`odoo19c: odoo/orm/fields_relational.py:36`), y la existencia del comodelo se
asegura en una **fase**, no al declarar —
`setup_nonrelated` con `assert self.comodel_name in model.pool` (`:92-94`) —
contra un `Registry(Mapping[str, type[BaseModel]])` (`odoo/orm/registry.py:84`,
`__getitem__` `:317`). Enlace tardío por nombre contra un registro.

## M17 — El orden, y por qué NO hay peligro de resolución prematura

```
django/db/models/base.py:387   new_class._prepare()        -> :450 class_prepared.send
django/db/models/base.py:388   register_model(...)         -> do_pending_operations
django/apps/registry.py:421-426
        try:    model_class = self.get_registered_model(*next_model)
        except LookupError: self._pending_operations[next_model].append(...)
        else:   apply_next_model(model_class)
```

Para un nombre de la referencia, `get_registered_model('test_orm','category')`
levanta **siempre** `LookupError` — la clave real es `testormcategory` —, así
que la operación **siempre** se encola, exista ya la clase destino o no. No hay
la variante peligrosa «ya registrado, se aplica de inmediato con la clase
equivocada»: el orden de declaración no puede producirla.

*Métrica:* `apps._pending_operations` tras `django.setup()`, y las tres líneas
de Django que deciden encolar contra aplicar.
*Ciega a:* qué ocurre al **vaciar** — que la clase esté completa cuando se
llame a `do_related_class` no se deduce de aquí; lo decide el momento del
vaciado, que es lo que M18 tiene que medir.

## M18 — El vaciado no es el problema: el 70 % de los nombres NO LLEGA a encolarse

Medido 2026-09-11T11:26:32. M15-M17 midieron el caso `'test_orm.category'` y de ahí salió un
diseño: vaciar `apps._pending_operations` bajo la **clave alias** que
`make_model_tuple` deriva. Esta medición dice que ese diseño cubre una minoría
del árbol, y que el resto falla **antes**, en otro sitio.

### Los tres nombres, tres conductas distintas

```
'category'          -> (sin error)  remote_field.model = 'category'
'test_orm.category' -> (sin error)  encola bajo ('test_orm','category')
'ir.model.fields'   -> ValueError: Invalid model reference 'ir.model.fields'.
                       String model references must be of the form
                       'app_label.ModelName'.
```

El `ValueError` sale de `make_model_tuple`
(`django/db/models/utils.py:5-25`), que hace `model.split(".")` sobre **dos**
partes y convierte cualquier `ValueError` de desempaquetado en ese mensaje. Y
salta al **ejecutar el cuerpo de la clase**, no al resolver: no hay entrada
pendiente, así que ningún vaciado posterior puede alcanzarlo.

El caso de **cero puntos** es peor que un error: `resolve_relation`
(`related.py:61-63`) antepone el `app_label` del modelo declarante —
`'category'` se vuelve `'base.category'` — y resuelve **en silencio** hacia la
app equivocada.

### El reparto del árbol, que es lo que decide

`_name` declarados, únicos, por número de puntos:

| puntos | modelos | ¿`make_model_tuple` deriva clave? |
|---|---|---|
| 0 | 3 | no — resuelve en silencio a la app declarante |
| 1 | 63 | sí |
| 2 | 84 | **no — `ValueError` al declarar** |
| 3 | 65 | **no** |
| 4 | 8 | **no** |
| 5 | 1 | **no** |

**158 de 224 (70.5 %)** llevan dos o más puntos. El diseño de vaciar la clave
alias cubre **63 (28 %)**, y sólo cuando el primer segmento coincide además con
una app instalada.

### Por qué el árbol de hoy no está rojo por esto

Cero campos relacionales **ejecutables** citan un nombre de 2+ puntos. Los siete
hits del grep viven todos en docstrings y comentarios que citan a la fuente:

```
src/orm/fields_relational.py:106          src/orm/model_classes.py:165
src/addons/base/models/ir_default.py:18
addons/base_sparse_field/models/ir_model_fields.py:139
addons/sale_timesheet/models/hr_timesheet.py:16
addons/account_update_tax_tags/models/account_move_line_tax_link.py:15-16
```

Es la misma forma que destapó `ondelete=`: el vocabulario de la fuente sólo
vive en la prosa, así que el hueco nunca llegó a un intérprete. El primer
modelo portado con `fields.Many2one('ir.model.fields')` lo levanta.

### La consecuencia de diseño

La fuente **nunca deriva una clave**: guarda `comodel_name` como cadena
(`odoo19c: odoo/orm/fields_relational.py:36`) y resuelve por nombre contra el
registro en una fase (`setup_nonrelated`, `:92-94`). Portar eso exige que el
nombre punteado **no llegue** a `make_model_tuple` — no que se le arregle la
clave después.

Nuestro `Many2one` pasa hoy la cadena verbatim a `models.ForeignKey`
(`src/orm/fields_relational.py:719`), que es exactamente lo que la entrega a
`make_model_tuple`.

*Métrica:* construcción de tres modelos desechables con `app_label='base'` y un
`fields.Many2one` de 0, 1 y 3 puntos, bajo `django.setup()` completo; más el
reparto por puntos de los `_name` únicos de `src/` y `addons/`.
*Ciega a:* el campo declarado con **etiqueta de Django** (`'base.ResPartner'`),
que no pasa por ninguno de los tres caminos y hoy es la forma mayoritaria del
árbol; y a `One2many`/`Many2many`, medidos sólo por el literal de su primer
argumento, no construidos.

## M19 — La guarda de `_ensure_seeded` es `apps.ready`, y eso la inhabilita en `ready()`

```python
def _ensure_seeded():
    if _ensure_seeded.hecho or not apps.ready:
        return
```

`src/orm/registry.py:405-406`. `apps.ready` se fija en la **fase 3**, después
de correr todos los `ready()` (`django/apps/registry.py:122` y `:126`), así que
dentro de cualquier `ready()` vale `False` y la función **sale sin hacer nada,
en silencio**. Enrutar un barrido por ahí desde un `AppConfig.ready()` es un
no-op que no se delata.

Las tres fases, verbatim:

```
django/apps/registry.py:86    # Phase 1
django/apps/registry.py:112   self.apps_ready = True
django/apps/registry.py:114   # Phase 2: import models modules.
django/apps/registry.py:120   self.models_ready = True
django/apps/registry.py:122   # Phase 3: run ready() methods
django/apps/registry.py:126   self.ready = True
```

Y la razón de no poner el vaciado en la fase 3 no es sólo esa: `related_model`
es un `cached_property` guardado únicamente por `apps.check_models_ready()`
(`related.py:110-114`), que en fase 3 **pasa**. Un `ready()` de otra app que lo
toque cachea la **cadena**; un vaciado posterior arregla `remote_field.model` y
deja `related_model` mintiendo, con `sync_apps` en verde porque mira
`remote_field.model` (`related.py:771`). En fase 2 `models_ready` es `False`, así
que ese mismo acceso **levanta** en vez de cachear.

*Métrica:* el cuerpo de la guarda y las cuatro líneas de `populate` que fijan
las banderas.
*Ciega a:* si algún `ready()` del árbol toca hoy `related_model` — no se midió;
la conclusión es sobre qué **permite** el mecanismo, no sobre qué ocurre ya.

---

## M20 — El censo por línea midió 14 cadenas y el árbol tiene 580

**2026-09-11T11:46:22**

M18 cerró con un discriminador elegido sobre un censo hecho con
`grep -rhoE "Many2one\(\s*'[^']+'"`. Ese patrón sólo ve la llamada cuyo primer
argumento cabe en la **misma línea**. Medido de nuevo por AST, sobre `src/` y
`addons/`, contando cada llamada y no cada valor distinto:

| Forma del primer posicional | Llamadas | Ejemplos |
|---|---|---|
| etiqueta de Django con mayúscula | **549** | `account.AccountAccount`, `base.ResPartner` |
| `'self'` — el constante recursivo de Django | **27** | — |
| minúscula con un punto | **4** | `res.users`, `test_orm.category`, `base.reportpaperformat` |
| minúscula con dos o más puntos | **0** | — |

El grep publicaba **14** valores distintos; el AST mide **580** llamadas. La
conclusión que se sacó del grep —«0 etiquetas de Django en minúsculas»— era
falsa, y la falsedad tenía consecuencia: `'base.reportpaperformat'` **es** una
etiqueta de Django en minúsculas, y el discriminador de caja la habría mandado
al centinela para siempre.

**Dónde vive, y por qué es legítima:** en una **migración**
(`0069_ir_actions_report_group_ids_and_paperformat_id.py:96`), cuyo propio
docstring lo declara — *"el estado de una migración rechaza una referencia a la
clase (*«Model fields in ModelState.fields cannot refer to a model class»*),
porque tiene que poder reconstruirse sin importar el modelo real"*. Ahí la
cadena en minúsculas no es un descuido: es el único camino.

De ahí las dos correcciones al diseño de M18, las dos forzadas por una
ejecución real y no por relectura:

1. **La segunda vía del destino-primero.** Antes de mandar al centinela se
   intenta `apps.get_model(comodel, require_ready=False)`: si la cadena ya es
   una etiqueta de Django resoluble, se devuelve **tal cual**. Eso deja las
   migraciones intactas.
2. **Nunca se devuelve la clase, siempre una cadena.** La primera versión
   devolvía la clase cuando el `_name` estaba registrado, y el estado de la
   migración la rechazó con el literal de arriba — sobre
   `base.IrActionsReport.group_ids.to`. Se devuelve `_meta.label_lower`.

*Métrica:* llamadas a `Many2one` con primer argumento constante de cadena,
recorridas por AST sobre todos los `.py` de `src/` y `addons/`, clasificadas
por caja y número de puntos.
*Ciega a:* el primer argumento que no sea una constante literal —una variable o
una clase importada—, que es la forma mayoritaria del árbol y no entra en este
censo; y a `One2many`, que no se midió aquí.

---

## M21 — El vaciado no puede correr en `class_prepared`: la clave aún no existe

**2026-09-11T11:46:22**

El primer puerto colgó el vaciado del receptor de `class_prepared`, con este
razonamiento: `ModelBase.__new__` emite la señal en `base.py:387` y registra el
modelo en `:388`, así que la señal llega antes y el modelo ya tiene `_meta`.
Las dos mitades son ciertas y la conclusión era falsa. Medido:

```
'test_orm.category' registrado: <class ...TestOrmCategory>
claves centinela pendientes: [('orm', 'test_orm_category')]
parent.remote_field.model: orm.test_orm_category
```

El registro se pobló, el vaciado corrió, y la clave **seguía viva**.

**La causa es el encadenamiento de Django, no el orden de la señal.**
`lazy_related_operation` espera a **dos** modelos —el que declara el campo y el
destino (`related.py:80-86`)— y `lazy_model_operation` los toma **de uno en
uno** (`apps/registry.py:400-426`): encola bajo la clave del **primero**, y sólo
cuando ése se registra encola bajo la del segundo. Para un campo
auto-referente el primero es la propia clase, que se registra en `:388` —
**después** de la señal. Al correr el vaciado, la clave centinela todavía no
había nacido.

La corrección usa la misma primitiva en vez de adelantarse a ella:

```python
apps.lazy_model_operation(_flush_sentinels, make_model_tuple(sender))
```

Nuestra función entra en la lista de la clave real del modelo **detrás** de la
de Django, que se encoló en `contribute_to_class` —antes de `_prepare()`—, así
que `do_pending_operations` ejecuta primero la suya (que crea la clave
centinela) y después la nuestra (que la vacía).

*Métrica:* `apps._pending_operations` y `remote_field.model` leídos en proceso
tras `django.setup()` completo, más las líneas citadas del paquete instalado.
*Ciega a:* un campo cuyo destino se encole por una tercera vía que no sea
`lazy_related_operation` — no medida; y al orden **dentro** de la lista de
pendientes, que aquí se infiere del momento de encolado y se comprueba por el
resultado, no leyendo la lista.

---

## M22 — El vaciado apuntaba al registro global y dejó dos referencias colgadas (2026-09-11T11:59:52)

**Pregunta.** La suite completa vuelve con 7 fallos y 10 errores. ¿Cuáles son
del resolutor y cuáles del addon `test_orm` sin rastrear (#332)?

**Instrumento.** `grep -E "^(FAILED|ERROR)"` sobre el log de la corrida, más el
cuerpo de cada traceback.

**Lo que midió.** Sólo **dos** de los 17 nombran un símbolo del resolutor, y no
son ni fallo ni error de test: son dos `models.E022` dentro del resumen de
system checks que `test_checks_irresolvable_fk` imprime.

```
[models.E022] <function _flush_sentinels at 0x...>: contains a lazy reference
  to migrations.migration, but app 'migrations' isn't installed.
[models.E022] <function _flush_sentinels at 0x...>: contains a lazy reference
  to stock.stockmovelineprobe, but app 'stock' doesn't provide model
  'stockmovelineprobe'.
```

**La causa, leída en el paquete instalado — no de memoria.** Django encola y
vacía el pendiente en **el registro del modelo**, nunca en el global:

| Sitio | Línea verbatim |
|---|---|
| `django/db/models/fields/related.py:85` | `apps = model._meta.apps` |
| `django/db/models/base.py:388` | `new_class._meta.apps.register_model(new_class._meta.app_label, new_class)` |
| `django/apps/registry.py:433` | `for function in self._pending_operations.pop(key, []):` |

Mi receptor llamaba al `apps` global. Un modelo bajo `isolate_apps` o
renderizado por el `StateApps` de una migración tiene **otro** `Apps`: registra
allí, vacía allí, y la entrada que yo dejé en el global no la pop-ea nadie.
`_check_lazy_references` la reporta como referencia perezosa colgada.

**El arreglo.** `sender._meta.apps.lazy_model_operation(...)` en el receptor y
`model._meta.apps._pending_operations.pop(...)` en `flush_sentinel`.

**Verificación tras el arreglo** — `collect_system_check_summary()` en proceso:

```
por id: {'fields.E304': 2}
```

Los dos `models.E022` desaparecen. Los `fields.E304` que quedan nombran
`test_orm.TestOrmDiscussion.moderator` y `.participants`, del addon sin
rastrear.

*Métrica:* `errors` de `collect_system_check_summary()`, agrupados por `id`.
*Ciega a:* un pendiente colgado en un `Apps` que los system checks no
recorren — sólo miran el global. Si el defecto reapareciera dentro de un
`StateApps`, este instrumento no lo vería.

### Atribución de los 17

| Familia | N | Dueño |
|---|---|---|
| `models.E022` en el resumen de checks | 2 | **mío** — corregido arriba |
| `fields.E304` `moderator`/`participants` sin `related_name` | 2 | #332 — `test_orm` sin rastrear |
| `test_display_name`: `TestOrmCategory.display_name` es `FieldDescriptor` | 2 | #332 |
| `test_check_fk_naming`: `db_column` de `parent` y `moderator` | 1 | #332 (forma C ya declarada) |
| `test_ir_cron_runner`: el comando corre system checks y aborta con el E304 | 2 | #332, por la vía del E304 |
| `test_modified_engine`: `relation "orm_engine_owner" already exists` | 10 | residuo de una base de worker; ni mío ni de #332 |

`git ls-files src/addons/test_orm | wc -l` → **0**: el addon entero está sin
rastrear, así que ninguno de sus símbolos puede venir de este porte.

---

## M23 — La etiqueta de Django en minúsculas no es una: son 41 (2026-09-11T11:59:52)

**Pregunta.** M20 dijo *«el árbol tiene una»* sobre la forma `label_lower`, y
esa cifra salió del traceback que rompió, no de un censo. ¿Cuántas hay?

**Instrumento.** Recorrido AST de toda constante de cadena bajo `src/` con
exactamente un punto y en minúsculas, cruzada con
`apps.get_model(v, require_ready=False)` bajo `django.setup()` completo.

```
etiquetas: 41
archivos que las llevan: {'migracion': 31, 'otro': 3}
tambien son _name de la fuente: 0 []
```

**Consecuencia.** La rama `apps.get_model` de `_deferred_comodel` no protege un
caso anecdótico: protege 41, casi todas en migraciones, donde el estado
rechaza la referencia a la clase. Y los dos vocabularios **no se solapan hoy**
—0 de las 41 es además un `_name`—, así que el orden de las dos consultas no
desempata nada todavía.

*Métrica:* constantes de cadena por AST bajo `src/`, filtradas por forma y
confirmadas contra el registro de Django.
*Ciega a:* una etiqueta construida en tiempo de ejecución (`f'{app}.{modelo}'`),
que ningún recorrido de constantes ve; y a `addons/`, que este censo no
recorrió.
