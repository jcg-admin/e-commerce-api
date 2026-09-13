# Fusión de declaraciones de campo — el mecanismo `_base_fields__` de la fuente

<!-- ultima medicion anadida: 2026-09-11T12:45:33 -->

> Última medición registrada: 2026-09-11T12:39:07.

Banco abierto 2026-09-11T12:21:43. Pregunta: qué hace la referencia cuando **dos clases de
definición del mismo modelo declaran el mismo campo**, y qué hace nuestro árbol
ante la misma forma.

El disparador es una declaración REAL del addon que se está portando (#332):

```python
# odoo19c: odoo/addons/test_orm/models/test_orm.py:28 — TestOrmCategory
display_name = fields.Char(
    inverse='_inverse_display_name',
    recursive=True,
)
```

Ni `compute=` ni `store=`. El `compute` sale de `BaseModel.display_name`
(`odoo19c: odoo/orm/models.py:473`), y llega por la fusión.

## M1 — el universo de los dos parámetros, por AST

El grep por línea **no sirve** y por eso se descarta: las dos declaraciones de
`display_name` que llevan `inverse=` lo llevan en la SEGUNDA línea de la
llamada. Medir el significante (la línea de la declaración) y concluir sobre el
significado (la llamada) es el sub-patrón A.

| Instrumento | `inverse=` | `recursive=` |
|---|---|---|
| `grep -n` por línea | 94 | 21 |
| recorrido AST de `ast.Call` | **273** | **42** |

El grep subcuenta **2.9×** y **2.0×**. Reparto por tipo de campo: `inverse`
sale en 18 tipos (Char 68 · Many2one 50 · Boolean 35 · Float 24 · Selection 20 ·
Many2many 15 · One2many 14 · Monetary 12 · …), `recursive` en 9 (Many2one 13 ·
Char 12 · Boolean 4 · Float 4 · …).

**Ninguno de los dos es una necesidad acotada**: son infraestructura del
vocabulario de campo, no un caso del addon que se porta.

Comando: `census_inverse_recursive.py`.

### M1-bis — `display_name` redeclarado como campo

**10** declaraciones en Python (el grep inicial dio 31 porque contaba archivos
`.js` de mock: `hr/static/tests/…`, `web/static/tests/…`,
`spreadsheet/static/tests/…`). De las 10, **4** llevan `inverse=` o
`recursive=`:

| Archivo | Clase | Parámetros declarados |
|---|---|---|
| `addons/project/models/project_task.py:315` | `ProjectTask` | `help`, **`inverse`** |
| `odoo/addons/test_orm/models/test_orm.py:28` | `TestOrmCategory` | **`inverse`**, **`recursive`** |
| `odoo/addons/test_orm/models/test_orm.py:758` | `TestOrmRecursive` | **`recursive`**, `store` |
| `odoo/addons/test_orm/models/test_orm.py:797` | `TestOrmRecursiveTree` | **`recursive`**, `store` |

Las otras 6 declaran `compute` · `help` · `compute_sudo` · `string` ·
`store` ×2.

## M2 — el enrutador nuestro, medido en proceso

```
fields.Char()                                -> CharField    inverse=None recursive=False
fields.Char(store=False)                     -> NonStored    inverse=None recursive=False
fields.Char(inverse='_x')                    -> CharField    inverse=None recursive=False
fields.Char(recursive=True)                  -> CharField    inverse=None recursive=False
fields.Char(inverse='_x', recursive=True)    -> CharField    inverse=None recursive=False
fields.Char(compute='_c')                    -> NonStored    inverse=None recursive=False
fields.Char(recursive=True, store=True)      -> CharField    inverse=None recursive=False
fields.Char(related='a.b')                   -> NonStored    inverse=None recursive=False
```

**`inverse=` solo NO enruta a `NonStored`. Y eso es FIEL**, no un defecto —
medido en la fuente, no supuesto. El bloque `attrs` de
`odoo19c: odoo/orm/fields.py:443-459` sólo escribe `store` bajo
`if attrs.get('compute')` y `if attrs.get('related')`. `inverse` aparece
**una sola vez** en ese bloque, y no para decidir columna sino `readonly`:

```python
attrs['readonly'] = attrs.get('readonly', not attrs.get('inverse'))   # :451
```

Nuestro puerto ya lleva esa línea (`src/orm/fields_nonstored.py:370`).

Comando: `probe_router.py`.

## M3 — dónde se pierde el valor, exactamente

```
apply_source_defaults SI los devuelve:
  store=False, inverse='_x'     attrs.inverse='_x'  store=False
  store=False, recursive=True   attrs.recursive=True store=False
  compute='_c', inverse='_x'    attrs.inverse='_x'  store=False
  related='a.b', inverse='_x'   attrs.inverse='_x'  store=False

pero el CAMPO construido:
  Char(store=False, inverse='_x')    -> NonStored  inverse=None   <-- PERDIDO
  Char(store=False, recursive=True)  -> NonStored  recursive=False <-- PERDIDO
  Char(compute='_c', inverse='_x')   -> NonStored  inverse='_x'   <-- llega
  Char(related='a.b', inverse='_x')  -> NonStored  inverse='_x'   <-- llega

vars(NonStored(inverse='_x', recursive=True)) =
  ['compute','default','help_text','name','related','search','verbose_name']
```

Dos puntos de pérdida, y el vocabulario **ya estaba portado**:

1. `_declared_source_vocabulary` **sí** extrae los dos
   (`fields_nonstored.py:342-343`) y `apply_source_defaults` **sí** los
   devuelve en `attrs` (`:378-380`).
2. La **salida temprana** de `annotate_related` —
   `if not related and not attrs.get('compute'): return field` — los tira
   cuando la declaración es `store=False` a secas.
3. `NonStored.__init__` los traga en `**_ignored`: no quedan en
   `__dict__` por ninguna vía que no sea el `setattr` de
   `annotate_related`.

Comando: `probe_drop_point.py`.

## M4 — el defecto GRANDE: nuestro árbol crea una columna que la fuente no crea

Forma exacta de `TestOrmCategory`: base abstracta con
`Char(compute=…, store=False)`, subclase que redeclara con
`Char(inverse=…, recursive=True)`.

```
el atributo de clase de la subclase : FieldDescriptor
  compute  = <AUSENTE>
  inverse  = <AUSENTE>
  recursive= <AUSENTE>

lo que el registro por MRO devuelve:
  tipo     = NonStored
  compute  = _compute_label
  inverse  = None

¿la subclase creo COLUMNA para label? True
base declara NonStored? True
```

El nombre queda **partido en dos objetos**: una **columna real** en
`_meta.get_fields()` que la fuente nunca crea, y la entrada `NonStored` de
la base que el registro por MRO sigue devolviendo — con el `compute` de la
base y **sin** el `inverse` de la redeclaración.

**Y el gate se queda verde.** `scripts/check_display_name.py::not_a_field`
exige que `display_name` sea `NonStored` en **alguna** clase del MRO; la
base lo es, así que pasa con la columna espuria delante. Sub-patrón D: el verde
no distingue «el puerto es correcto» de «el instrumento mira el tipo, no el
objeto que gana».

Comando: `probe_merge_today.py`.

## M5 — cómo fusiona la fuente, verbatim

`odoo19c: odoo/orm/fields.py:414-432` (`_get_attrs`):

```python
attrs = {}
modules = []
for field in self._args__.get('_base_fields__', ()):
    if not isinstance(self, type(field)):
        # 'self' overrides 'field' and their types are not compatible;
        # so we ignore all the parameters collected so far
        attrs.clear()
        modules.clear()
        continue
    attrs.update(field._args__)
    if field._module:
        modules.append(field._module)
attrs.update(self._args__)
```

Acumular los `_args__` de cada declaración en orden de override, con un
**reinicio por incompatibilidad de tipo**, y superponer al final los propios.

El sitio donde se arma, `odoo19c: odoo/orm/model_classes.py:409-415`:

```python
if len(fields_) == 1 and fields_[0]._direct and fields_[0].model_name == model_cls._name:
    model_cls._fields__[name] = fields_[0]
else:
    Field = type(fields_[-1])
    add_field(model_cls, name, Field(_base_fields__=tuple(fields_)))
```

Una **instancia nueva**, del tipo de la **última** declaración, construida con
toda la cadena. Y el contrato del atributo, `:266`:

```python
_base_fields__: tuple[Self, ...] = ()  # the fields defining self, in override order
```

## La divergencia, en una línea

| | fuente | nuestro árbol hoy |
|---|---|---|
| redeclaración | acumula `_args__` de la cadena y superpone los propios | **último gana**: `non_stored_fields` hace `found[name] = held` recorriendo `reversed(__mro__)` |
| objeto resultante | UNA instancia del tipo de la última | **DOS**: columna de Django en la subclase + `NonStored` de la base en el registro |
| sitio | ensamblado de la clase de registro | no existe — Django arma una clase por modelo desde el MRO |

*Métrica:* el tipo y los atributos del objeto que queda en `vars(cls)`, el que
devuelve `non_stored_fields`, y la presencia del nombre en
`_meta.get_fields()`, sobre modelos desechables construidos bajo
`django.setup()` completo.
*Ciega a:* el reinicio por incompatibilidad de tipo de `:419-423` —no se ha
ejercitado una redeclaración que cambie el tipo de campo—; y a los consumidores
de `recursive` (`fields.py:3508-3511`, `:4157`, `models.py:3361`), que
existen y no se han medido con un campo que lo declare de verdad.

---

## M6 — ¿cuántas redeclaraciones vivas hay en el árbol? (corregida)

`probe_tree_redeclarations.py` sobre `apps.get_models()` bajo `django.setup()`:

```
modelos medidos: 399
stored sobre NonStored (el defecto de M4): 1
    test_orm.TestOrmCategory display_name DisplayNameMixin
NonStored sobre stored: 0
por nombre: {'display_name': 1}
```

**El guion tenía un defecto de precedencia y se corrigió antes de citarlo.**
`stored_in_bases` llevaba `meta is None or getattr(meta,'abstract',False) is
False and base is cls`; `base is cls` es **inalcanzable** en un recorrido sobre
`__mro__[1:]`, así que por precedencia la condición se reducía a `meta is
None`. Corregido a lo que de verdad mide, la cifra **no cambia**: 399 y 1. Se
registra porque un instrumento cuya condición no dice lo que hace no sirve como
evidencia aunque acierte.

Cruzado con las migraciones: `grep -rn "display_name" src/**/migrations/` da
**0**, y `test_orm` no tiene directorio `migrations/`. El defecto **no está
codificado en ninguna parte**: es infraestructura prospectiva más un caso vivo
del addon en vuelo.

*Métrica:* nombres declarados como campo con columna en `cls` que una base del
MRO declara como `NonStored`, y el recíproco, sobre los 399 modelos
registrados.
*Ciega a:* NonStored-sobre-NonStored y stored-sobre-stored (herencia abstracta
de Django, último gana), que no se midieron; y a un descriptor colgado con
`setattr` pelado después del arranque.

## M7 — qué diccionario guarda hoy `_args__`, en las dos ramas

`probe_args_is_post_translation.py`:

```
Char(inverse='_x', recursive=True)  [rama con columna]
    tipo      : CharField
    _args__   : {}
    .inverse  : None
    .recursive: False
    .store    : True

Char('Label', store=False, inverse='_x')  [rama sin columna]
    tipo      : NonStored
    _args__   : None (atributo presente, sin valor)
    .inverse  : None
    .recursive: False
    .store    : False

NonStored(default=None, search='_s')  [declaracion directa]
    tipo      : NonStored
    _args__   : None (atributo presente, sin valor)
```

El docstring de `_field_get_attrs` dice *"Recibe lo declarado en `_args__`"*.
**Hoy es falso en las dos ramas**, y el flujo leído lo explica sin conjetura:

1. `Char()` traduce `required`→`blank`, `help`→`help_text`, `size`→`max_length`;
2. `apply_source_defaults` llama a `_declared_source_vocabulary`, que **saca de
   `kwargs`** `compute`, `inverse`, `recursive`, `precompute`, `compute_sudo`,
   `related_sudo`, `readonly`, `store` (y `copy` condicional);
3. `models.CharField(*args, **kwargs)` — el envoltorio anota `_args__` de lo que
   **queda**, que ya no tiene el vocabulario de la fuente;
4. `annotate_related` **sale temprano** con `not related and not
   attrs.get('compute')`, así que `inverse` y `recursive` no se anotan tampoco.

El `_args__ = None` de `NonStored` no es una ausencia: es el default de clase
que instala el segundo bucle de `_FIELD_CLASS_ATTRIBUTES` (`fields.py:1969`)
sobre esa clase. `NonStored.__init__` nunca lo asigna.

*Métrica:* las claves de `_args__` y los tres atributos del vocabulario de la
fuente sobre un campo construido por la fachada, en sus tres formas.
*Ciega a:* un campo construido sin pasar por la fachada, y a las otras ocho
fachadas (se midió `Char`).

## M8a — el ORDEN de la fuente: fusión ANTES, bloques DESPUÉS

`odoo19c: odoo/orm/fields.py:414-465`, verbatim:

```python
def _get_attrs(self, model_class, name):
    attrs = {}
    for field in self._args__.get('_base_fields__', ()):   # :419
        if not isinstance(self, type(field)):
            attrs.clear(); modules.clear(); continue        # :423
        attrs.update(field._args__)                         # :426
    attrs.update(self._args__)                              # :429
    ...
    if attrs.get('compute'):    ...                          # :443
    if attrs.get('related'):    ...                          # :452
    if attrs.get('precompute'): ...                          # :459
```

**La fusión ocurre en `:419-429` y los bloques `attrs` en `:443-465`.** Nuestro
árbol invierte el orden: los tres bloques corren en la **fachada**
(`apply_source_defaults`), antes de que ninguna fusión sea posible, porque la
fachada sólo ve la declaración de UNA clase.

Consecuencia medible: una subclase que declare `compute=` sobre una base que
declaró `store=True` se resuelve aquí con el diccionario de la subclase sola;
allá, con el acumulado.

*Métrica:* el orden de las sentencias en el cuerpo de `_get_attrs` de la
referencia.
*Ciega a:* si algún consumidor de la referencia depende de ese orden — se leyó
el cuerpo, no se ejercitó.

## M8b — de dónde sale el `_args__` de `NonStored`

`src/orm/fields.py:1948` instala `_FIELD_CLASS_ATTRIBUTES` sobre
`models.Field`; **`:1969` repite el bucle sobre `NonStored`**, con `store` como
única excepción. `_args__: None` es una de sus 66 entradas (`:1901`). Por eso el
atributo existe con valor `None` en un objeto que nunca lo asigna.

## M9 — la fusión NO está muerta: corre y se le da el diccionario equivocado

`probe_merge_is_reached.py` espía `models.Field._get_attrs` durante un cuerpo de
clase:

```
llamadas a _get_attrs durante el cuerpo de clase: 2
  campo 'label'
    _args__ de entrada : {'max_length': 8}
    attrs de salida    : {'max_length': 8, 'model_name': '', 'name': 'label',
                          '_module': None, '_modules': ()}
  campo 'id'
    _args__ de entrada : {'verbose_name': 'ID', 'primary_key': True, ...}

estado final del campo construido:
    .inverse       : None
    .recursive     : False
    .string        : None
    ._extra_keys__ : ()
```

Declarar `_get_attrs` "código muerto" habría sido concluir sobre el significado
leyendo el significante. **Se ejecuta en cada campo de cada clase**; la cadena
`contribute_to_class` → `_setup_attrs__` → `_get_attrs` → `__dict__.update` ya
está cableada entera. Lo que falta no es la costura: es que `_args__` lleve el
vocabulario de la fuente y que **alguien pase `_base_fields__`** —
`grep -rn "_base_fields__=" src/` da **0**.

El campo declarado con `'Label'` sale con `.string = None`: la fuente lo fuerza
en `:317` (`kwargs['string'] = string`) y aquí el posicional va a
`verbose_name` de Django sin que nadie lo espeje.

*Métrica:* número de invocaciones de `_get_attrs`, su `_args__` de entrada y su
`attrs` de salida, durante la ejecución del cuerpo de una clase de modelo.
*Ciega a:* lo que ocurre en `add_to_class` de una extensión `_inherit`, que no
se ejerció aquí.

## M10a — cuántas declaraciones de `NonStored` esquivan la fachada, y qué declara la fuente para ellas

Comando y salida:

```
$ grep -rn "= NonStored(" src/ --include=*.py
src/orm/fields_misc.py:54:              field = NonStored(*args, **kwargs)
src/orm/fields_numeric.py:73:           field = NonStored(*args, **kwargs)
src/orm/fields_textual.py:233:          campo = NonStored(*args, **kwargs)
src/orm/fields_company_dependent.py:482:  field = NonStored(*args, related=related, **kwargs)
src/orm/models.py:2942:                 display_name = NonStored(default=..., search=...)
src/addons/base/models/res_groups.py:177: full_name = NonStored(default=..., search=...)
```

**Seis, y la partición importa: cuatro de las seis son la rama de construcción
DE LA PROPIA FACHADA** —el `else` que elige `NonStored` cuando `store` sale
falso—, no declaraciones de modelo. Las declaraciones **facade-less reales son
DOS**, y la fuente declara las dos **con la fachada**:

| nuestro | fuente | cómo la declara la fuente |
|---|---|---|
| `src/orm/models.py:2942` `display_name` | `odoo19c: odoo/orm/models.py:473` | `display_name = Char(string='Display Name', compute=..., search=...)` |
| `src/addons/base/models/res_groups.py:177` `full_name` | `odoo19c: odoo/addons/base/models/res_groups.py:30` | `full_name = fields.Char(compute='_compute_full_name', string='Group Name', search='_search_full_name')` |

*Métrica:* ocurrencias del literal `= NonStored(` bajo `src/`, cruzadas con la
declaración verbatim de la fuente para cada nombre de campo.
*Ciega a:* una construcción de `NonStored` que no use ese literal —una llamada
indirecta, un `getattr`— y a las declaraciones de `addons/` fuera de `src/`.

**Consecuencia para la premisa que estaba en juego:** la condicional del
encargo —«si `DisplayNameMixin` es la única declaración directa»— es **falsa**:
son dos. La regla inventada «sin fachada ⇒ compatible con cualquiera» se retira
igual, pero el arreglo toca dos sitios, no uno.

## M10b — el control positivo REAL del mecanismo de fusión, en el repo

La fuente redeclara `display_name` en `test_orm` **sin `compute` y sin
`store`** — los hereda por `_base_fields__` de `BaseModel.display_name`:

```
odoo19c: odoo/addons/test_orm/models/test_orm.py:28-31
    display_name = fields.Char(
        inverse='_inverse_display_name',
        recursive=True,
    )
```

Nuestro puerto es **byte a byte igual** (`src/addons/test_orm/models/test_orm.py:36-39`).

Lo que la fuente compone para ese campo, siguiendo `_get_attrs` (`:414-465`):

| paso | resultado |
|---|---|
| `_args__` de la subclase | `{'inverse': ..., 'recursive': True}` |
| merge con `_base_fields__` (`:426`) | `+ {'string': 'Display Name', 'compute': '_compute_display_name', 'search': '_search_display_name'}` |
| bloque `compute` (`:443-451`) | ve el `compute` heredado → deriva el campo **sin columna** |

Lo que nuestro árbol compone, medido en M9: `.store: True`, `.inverse: None`,
`.recursive: False`, `.string: None`. Es decir **un `CharField` con columna**,
y los dos parámetros declarados caen en el `**_ignored` de `NonStored.__init__`
sin aplicarse.

**El defecto no es que `attrs` salga mal: es que el OBJETO ya está elegido.** La
fachada decide `CharField` contra `NonStored` en el sitio de declaración, viendo
sólo `{inverse, recursive}`; ninguna fusión posterior puede des-construir un
`CharField` en un `NonStored`. Por eso el arreglo **no** puede ser recomputar
`attrs` dentro de `_get_attrs`: tiene que **reconstruir el campo** desde el
diccionario fusionado, por la misma fachada que lo construyó.

*Métrica:* la declaración verbatim de los dos árboles, más el estado del campo
construido que M9 midió en proceso.
*Ciega a:* si algún otro de los 399 modelos hereda un `compute` por una vía que
`__mro__` no recorra (una inyección posterior, un `contribute_to_class` de
tercero). Medido sobre `__mro__[1:]`, que es la vía que Django usa.

---

## M10c — un `NonStored` heredado NO llega por `_meta`: llega por `__mro__`

Es la trampa 3, y decide **dónde** puede vivir la costura. Sonda en proceso
bajo `django.setup()` completo: un mixin abstracto que declara
`fields.Char(store=False, …)` y una subclase concreta que lo hereda.

```
display_name en _meta: False
en vars(subclase): False
tipo por atributo:    NonStored
mro:                  ['InheritsTheMixinProbe', 'DisplayNameMixinProbe', 'Model', 'AltersData', 'object']
llega por mro:        True
```

La causa está en Django: la copia desde un padre abstracto recorre
`_meta.local_fields`, que sólo contiene **campos de Django**. Un `NonStored` no
es `models.Field`, así que no está en `local_fields` y no se copia — sobrevive
únicamente como atributo de clase en el `__mro__`.

Consecuencias para la costura, las dos:

1. **La declaración base se busca en `cls.__mro__[1:]` leyendo `vars(base)`**,
   nunca en `_meta`. Un recorrido por `_meta` vería cero y publicaría «no hay
   nada que fusionar» — el sub-patrón D con el instrumento equivocado.
2. **La subclase no tiene el nombre en `vars()`**, así que instalar el campo
   reconstruido con `setattr(cls, name, fresh)` no pisa nada: lo declara donde
   antes sólo había herencia.

*Métrica:* `_meta.get_fields()`, `vars()` por clase del `__mro__` y el tipo del
atributo resuelto, sobre un par mixin-abstracto/concreta construido en proceso.
*Ciega a:* el caso en que la base declare un campo **con columna** (un
`CharField` de verdad) — ése sí lo copia `local_fields` y toma otro camino, que
es el «stored-over-stored» que Django ya resuelve por último-gana y que queda
como sucesor sin portar a ciegas.

---

## M11 (2026-09-11T16:01:28) — `inverse` y `recursive` son parámetros del MOTOR DE CÓMPUTO, no del descriptor

**Pregunta:** el punto 2 del asesor dice que `NonStored` debe aceptar y honrar
`inverse` **en este porte** porque *«tiene un consumidor claro en la fuente
(`Field.__set__` → `determine_inverse`)»*, y deja `recursive` por medir. Las dos
mitades se midieron; la primera resultó **falsa** y la segunda decide el alcance.

### `inverse` — dos consumidores, y ninguno es `__set__`

```
$ grep -rn "determine_inverse" "$ODOO19C/odoo/"
odoo/orm/fields.py:1922:    def determine_inverse(self, records):
odoo/orm/models.py:4416:                determine_inverses[field.inverse].append(field)
odoo/orm/models.py:4501:                    fields[0].determine_inverse(real_recs)
odoo/orm/models.py:4682:                    determine_inverses[field.inverse].add(field)
odoo/orm/models.py:4733:                next(iter(fields)).determine_inverse(inv_records)
```

Resueltos por AST a la función que los contiene:

```
BaseModel.write   def@4334-4518   lineas=[4399, 4416, 4490, 4493, 4501]
BaseModel.create  def@4611-4767   lineas=[4661, 4682, 4717, 4733]
```

Y el recorrido AST de los dos descriptores de `Field`, listando qué atributos de
interés menciona cada cuerpo:

```
--- Field.__get__  :1642-1805  (164 lineas)
    atributos de interes: ['compute', 'recursive', 'related']
--- Field.__set__  :1807-1843  (37 lineas)
    atributos de interes: ['related']
```

**`Field.__set__` no menciona `inverse` ni una vez.** Lo que alcanza es
`related`, y por esa vía `_inverse_related` (`:634` lo cuelga:
`if self.inherited or not (self.readonly or field.readonly): self.inverse =
self._inverse_related`) — que es **exactamente lo que `NonStored.__set__` ya
porta** (`inverse_related`, con la guarda de realidad `:731`).

Consecuencia: asignar `cat.display_name = x` en la fuente **NO corre**
`_inverse_display_name`. Cachea el valor y marca el campo; el método declarado
corre al `write()`/`create()`. Un `__set__` que lo invocara sería inventar algo
que la fuente no tiene.

### `recursive` — cuatro consumidores, los cuatro en el motor de cómputo

```
fields.py:830-832   if field is self and index and not self.recursive:
                        self.recursive = True
                        warnings.warn(f"Field {self} should be declared with recursive=True")
fields.py:1742      recs = record if self.recursive else self._to_prefetch(record)   (dentro de __get__)
fields.py:1875      if self.recursive:  # se computa registro a registro
models.py:6812      if field.recursive:  # descarta ya procesados para evitar ciclos
```

Los cuatro son aguas abajo de `compute`. No hay ninguno fuera de esa máquina.

### El positivo real declara los dos, y verbatim

`odoo19c: addons/test_orm/models/test_orm.py:28-29,41` declara
`display_name = fields.Char(inverse='_inverse_display_name', recursive=True)` y
`@api.depends('name', 'parent.display_name')  # this definition is recursive`.
Nuestro puerto (`src/addons/test_orm/models/test_orm.py:36-39`) los lleva igual.

### Veredicto de alcance

Los dos caen del **mismo lado**: son parámetros del motor de recálculo, y ese
motor **no está portado** — `NonStored.compute` ya se conserva declarado con esa
razón escrita, y su condición de cierre es la tarea **#273**. Honrarlos hoy sería
diseñar política para un caso al que la referencia no llega desde nuestro código.

Así que `inverse` y `recursive` se **conservan declarados** junto a `compute`,
con su consumidor nombrado — no se tragan en `**_ignored`, que es lo que hoy
pasa y lo que sí hay que corregir en este porte. La costura de fusión no depende
de ellos: depende de que el objeto ganador sea el reconstruido.

*Métrica:* `grep -rn` de `determine_inverse` y `\.recursive\b` sobre
`$ODOO19C/odoo/`, resuelto por AST a la función contenedora; y recorrido AST del
cuerpo de `Field.__get__`/`__set__` listando `ast.Attribute` de interés.
*Ciega a:* un consumidor que llegue por `getattr(field, 'inverse')` con el
nombre construido en tiempo de ejecución — medido 0 en `odoo/orm/`, pero el
instrumento es literal; y a los addons fuera de `odoo/addons/base`, que no se
barrieron para esta pregunta.

---

## M11-bis (2026-09-11T16:06:31) — CORRECCIÓN de M11: `inverse` SÍ se alcanza desde la asignación

M11 concluyó que `inverse` y `recursive` caen del **mismo lado** —parámetros del
motor de cómputo, no alcanzables desde nuestro código— y por tanto que los dos se
conservan declarados sin honrarse. **Esa conclusión es falsa para `inverse`.**
La de `recursive` se sostiene y no se toca.

Esta entrada se **añade**; M11 no se reescribe. El banco es evidencia, y la
conclusión equivocada es parte del registro.

### El defecto del instrumento — sub-patrón C, con una sonda recién escrita

M11 recorrió el cuerpo de `Field.__set__` listando **`ast.Attribute`** y midió
que la cadena `inverse` no aparece ni una vez. La cifra es correcta. La
conclusión —*«la asignación no alcanza al inverso»*— no se sigue de ella: el
recorrido **nunca miró `ast.Call`**, y la cadena va por ahí.

Se midió el **significante** (nombres de atributo en un cuerpo de 37 líneas) y se
concluyó sobre el **significado** (si asignar dispara el inverso). Es exactamente
`metrica-decide-la-conclusion.md` sub-patrón C, cometido con el instrumento
escrito ese mismo día para no cometer el D.

### La evidencia — `odoo19c: odoo/orm/fields.py:1807-1843`, leída completa

Las tres ramas de `__set__` reparten `records._ids` en tres cubos. La tercera:

```python
        if other_ids:
            # base case: full business logic
            records = records.__class__(records.env, tuple(other_ids), records._prefetch_ids)
            write_value = self.convert_to_write(value, records)
            records.write({self.name: write_value})
```

`other_ids` es el cubo de los registros **reales y no protegidos** — el que la
propia fuente rotula *«base case: full business logic»*. Y `write()` es el
consumidor que M11 ya había medido:

```
odoo19c: odoo/orm/models.py:4416   determine_inverses[field.inverse].append(field)
odoo19c: odoo/orm/models.py:4462   real_recs = self.filtered('id')
odoo19c: odoo/orm/models.py:4501   fields[0].determine_inverse(real_recs)
```

Así que la cadena completa, síncrona, es:

```
record.campo = valor
  -> Field.__set__            (:1807)
  -> records.write({name: v}) (:1843, rama other_ids)
  -> BaseModel.write          (:4334-4518)
  -> determine_inverse(real_recs)  (:4501, sobre self.filtered('id'))
```

### Por qué esto cambia el alcance, y `recursive` no

| Parámetro | Su consumidor | ¿Está portado su camino? | Veredicto |
|---|---|---|---|
| `recursive` | los 4 consumidores son aguas abajo de `compute` (`:830`, `:1742`, `:1875`, `models.py:6812`) | **no** — el motor de recálculo es la tarea #273 | conservar declarado, no honrar |
| `inverse` | `write()`, que es el **camino de mutación** | **sí** — Django tiene el camino de mutación: la asignación | **honrar, acotado a instancias guardadas** |

La distinción no es de grado: son dos motores distintos. Honrar `recursive` hoy
sería diseñar política para un caso al que la referencia no llega desde nuestro
código; honrar `inverse` es portar un camino que la referencia recorre y que
nosotros ya tenemos.

### El alcance lo fija la referencia, no una decisión nuestra

`real_recs = self.filtered('id')` (`models.py:4462`) es literalmente «sólo los
que tienen id». Y la rama `new_ids` de `__set__` (`:1826-1838`) escribe en caché
bajo `env.protecting(...)` **sin** pasar por `write()` — o sea, sin inverso.

Traducido a nuestro descriptor: la instancia **guardada** (`pk` no nulo) dispara
el inverso; la **no guardada** sólo escribe en `instance.__dict__`. Es la misma
guarda de realidad de `:731` que `NonStored.inverse_related` ya porta verbatim.

*Métrica:* cuerpo completo de `Field.__set__` (`fields.py:1807-1843`) leído sin
filtro, más las cuatro líneas de `write()` que recogen y despachan el inverso.
*Ciega a:* qué hace `convert_to_write` con el valor antes de entregarlo a
`write()` —no se midió—, y a si algún `__set__` de subclase relacional
sobreescribe esta ruta; el recorrido fue sobre el `Field` base.

---

## M12 (2026-09-11T16:09:32) — Dónde se pierden HOY `inverse` y `recursive`: NO era `**_ignored`

M11 y M11-bis discutieron **si** honrar `inverse`. Antes de tocar nada se midió
**dónde** se pierde, y el diagnóstico de M11 —*«hoy se tragan en
`**_ignored`»*— resultó falso también. Se pierden antes, y en un sitio distinto.

### La medición

```
$ PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing uv run python -c "…"
Char(inv, rec)             CharField  inverse=None     recursive=False
Char(compute, inv, rec)    NonStored  inverse='_inv'   recursive=True
Char(related, inv, rec)    NonStored  inverse='_inv'   recursive=True
```

Las dos últimas filas **ya llegan bien**. `_declared_source_vocabulary`
(`orm/fields_nonstored.py:340-349`) hace `kwargs.pop('inverse')` y
`kwargs.pop('recursive')`, `_apply_compute_block` los deja en `attrs`
(`:377-380`), y `annotate_related` los escribe sobre el descriptor. Así que
`**_ignored` **nunca los ve**: no hay nada que rescatar de ahí.

La primera fila es el defecto: `annotate_related:558` sale temprano —

```python
    if not related and not attrs.get('compute'):
        return field
```

— y con `inverse=`/`recursive=` declarados pero **sin** `compute=` ni
`related=`, los dos quedan **populados de `kwargs` y nunca anotados**. El campo
conserva el default de clase (`orm/fields.py:1931,1935`: `recursive: False`,
`inverse: None`). La declaración se pierde en silencio.

### Que esa forma existe NO es hipótesis: la referencia la declara 35 veces

```
declaraciones con inverse= en odoo19c addons: 256
  compute            219   test_testing_utilities/models.py:87 · …
  NINGUNO             35   base/ir_actions.py:689 · base/ir_actions.py:691 · test_orm/test_orm.py:28
  related              1   base_automation/base_automation.py:134
  compute+related      1   website/mixins.py:280
```

Y una de ellas es un campo **con columna**, no una proyección:

```python
odoo19c: base/models/ir_actions.py:691
    selection_value = fields.Many2one('ir.model.fields.selection', string="Custom Value",
                                      ondelete='cascade',
                                      domain='[("field_id", "=", update_field_id)]',
                                      inverse='_set_selection_value')
```

`test_orm/test_orm.py:28` —el `display_name` de la costura— está en ese mismo
cubo, y por la razón que M10b ya nombró: su `compute` **se hereda** de
`BaseModel`, así que la redeclaración del addon sólo añade `inverse` y
`recursive`.

### Los dos huecos, separados — y sólo uno cabe en este tramo

| # | Hueco | Camino de la fuente | ¿Portado aquí? |
|---|---|---|---|
| 1 | la declaración **no aterriza** en el campo sin `compute`/`related` | ninguno: la fuente guarda el vocabulario en `attrs` sin condición | **no** — es porte parcial puro, y se cierra en este tramo |
| 2 | nadie **despacha** el inverso al asignar | `__set__:1843` → `write()` → `determine_inverse` (`models.py:4501`) sobre `real_recs = self.filtered('id')` | **parcial**: tenemos el camino de mutación sólo en `NonStored.__set__`; para un campo **con columna** la asignación es la de Django y el despacho viviría en `save()`, que es `BaseModel.write` — la tarea **#318** |

*Métrica:* tres declaraciones construidas con la fachada real del árbol, leyendo
`getattr(campo, 'inverse'/'recursive')`; y censo AST de `ast.Call` con
`keywords` sobre los `*/models/*.py` de las dos raíces de addon de `odoo19c`.
*Ciega a:* una declaración cuyo `inverse=` llegue por `**kwargs` desplegado en
vez de por palabra clave literal —el censo lee `nodo.keywords`—, y a los
campos declarados fuera de `models/` (mixins en la raíz del addon, p. ej.).

---

## M13 — El hueco 1 son CINCO atributos, no dos; y la salida temprana es NUESTRA

**Medido:** 2026-09-11T16:15:19
**Sonda:** `probe_dropped_attributes.py` (hermana de este banco)
**Comando:**

```bash
PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing \
    uv run python scripts/workbench/fusion-de-declaraciones-de-campo-20260911T122051/probe_dropped_attributes.py
```

### Salida verbatim

```
declarado              clase resultante valor que quedó
readonly=True          CharField      readonly=False
copy=False             CharField      copy=False
compute_sudo=True      CharField      compute_sudo=False
store=False            NonStored      store=False
UserWarning: precompute attribute does not make any sense on non computed field
precompute=True        CharField      precompute=False
inverse=_inv           CharField      inverse=None
recursive=True         CharField      recursive=False
```

### Qué se pierde y qué no

| declarado | default de clase (`orm/fields.py:1915-1945`) | quedó | veredicto |
|---|---|---|---|
| `readonly=True` | `False` | `False` | **PERDIDO** |
| `copy=False` | **`True`** | `False` | sobrevive |
| `compute_sudo=True` | `False` | `False` | **PERDIDO** |
| `store=False` | `True` | `False` | correcto — enruta a `NonStored` |
| `precompute=True` | `False` | `False` | **PERDIDO** (y el `UserWarning` sí dispara) |
| `inverse='_inv'` | `None` | `None` | **PERDIDO** |
| `recursive=True` | `False` | `False` | **PERDIDO** |

**El control discrimina en los siete casos.** Cada declaración pide un valor
**distinto** del default de clase, así que un `quedó == default` es pérdida
medida y no una coincidencia. `copy` es el caso que lo prueba por el lado
contrario: default `True`, declarado `False`, quedó `False` — si la sonda no
discriminara, `copy` saldría igual que los otros cinco.

`copy` sobrevive porque `models.Field.__init__` lo acepta y lo anota:
`orm/fields.py:1061` — `self.copy = declared.get('copy', True)`. Es la
excepción que `_declared_source_vocabulary` ya declara en su docstring, no un
accidente.

**Corrige la cifra de M12**, que hablaba de dos atributos (`inverse` y
`recursive`) porque ésos eran los del caso que la motivó. El hueco 1 son
**cinco**: `readonly`, `compute_sudo`, `precompute`, `inverse`, `recursive`.
La anulación del arreglo tiene que cubrir los cinco, no dos.

### La salida temprana no está en la fuente — es una invención del porte

```bash
sed -n '491,517p' "$ODOO19C/odoo/orm/fields.py"
```

```python
    def _setup_attrs__(self, model_class: type[BaseModel], name: str) -> None:
        """ Initialize the field parameter attributes. """
        attrs = self._get_attrs(model_class, name)

        # determine parameters that must be validated
        extra_keys = tuple(key for key in attrs if not hasattr(self, key))
        if extra_keys:
            attrs['_extra_keys__'] = extra_keys

        self.__dict__.update(attrs)
```

`self.__dict__.update(attrs)` es **incondicional**. La fuente NO pregunta si
el campo es `related` ni si es calculado: aplica todo lo que el autor declaró,
siempre. Y su `__set_name__` (`:399-402`) llama a `_setup_attrs__` para todo
campo `_direct` o `_toplevel` — otra vez sin filtrar por vocabulario.

Nuestro `fields_nonstored.py:558`:

```python
    if not related and not attrs.get('compute'):
        return field
```

es un filtro que **la fuente no tiene**. Cae bajo LA LECCIÓN (5): un problema
que aparece al portar y que la fuente no tiene es señal de que el porte inventó
algo — se retira, no se resuelve. El comentario que lo defiende razona sobre el
coste de anotar atributos de instancia «para repetir lo que la clase ya
declara», y ese razonamiento **es correcto para el campo que no declara nada**
y falso para el que sí: la forma estrecha correcta es *«lo que el autor declaró
aterriza»*, no *«sólo los related y los computed aterrizan»*.

*Métrica:* el valor del atributo en el objeto campo justo después de
construirlo, contra el default de clase declarado en `orm/fields.py:1915-1945`.
*Ciega a:* un atributo cuyo default de clase coincida con el valor declarado en
la sonda — por eso los siete casos declaran un valor distinto del default; y al
momento **posterior** (`contribute_to_class`), donde otro mecanismo podría
reponer el valor. Esa segunda ceguera la cierra el test rojo, que mide el campo
ya contribuido a un modelo.

---

## M13-bis — CORRECCIÓN de M13: son CUATRO, no cinco. `precompute` ya es correcto

**Medido:** 2026-09-11T16:17:01
**Qué corrige:** M13 listó `precompute` entre los perdidos. **Es falso.**

### La fuente NORMALIZA `precompute` a `False` en ese caso, igual que nosotros

```bash
sed -n '459,465p' "$ODOO19C/odoo/orm/fields.py"
```

```python
        if attrs.get('precompute'):
            if not attrs.get('compute') and not attrs.get('related'):
                warnings.warn(f"precompute attribute doesn't make any sense on non computed field {self}", stacklevel=1)
                attrs['precompute'] = False
            elif not attrs.get('store'):
                warnings.warn(f"precompute attribute has no impact on non stored field {self}", stacklevel=1)
                attrs['precompute'] = False
```

Nuestro `fields_nonstored.py:418-437` (`apply_precompute_rules`) ya porta esas
dos ramas **y** añade la tercera de stack, declarada. Así que `precompute=True`
sobre un campo llano da `False` **en las dos partes**, y por la misma razón:
la normalización, no el descarte. El `UserWarning` que la sonda capturó es la
prueba de que la rama correcta se ejecutó.

**El defecto de M13 es el mismo que ya cometió M11**, un nivel más abajo: la
sonda mide `valor == default de clase` y de ahí concluí «perdido». Ese
predicado no separa *«el atributo se descartó»* de *«la fuente también produce
el default aquí»*. Sub-patrón **C** de `metrica-decide-la-conclusion.md`, con
el instrumento recién escrito para evitar el D.

### La población real, por atributo (AST sobre la referencia)

Declaraciones `fields.X(...)` **sin** `compute=` ni `related=` que traen el
atributo, sobre 3328 archivos de modelo de `odoo19c`:

| atributo | declaraciones | ejemplo | veredicto |
|---|---|---|---|
| `readonly` | **645** | `addons/l10n_id_efaktur_coretax/models/efaktur_document.py:15` | **PERDIDO** |
| `inverse` | **35** | `addons/l10n_latam_base/models/res_partner.py:9` | **PERDIDO** |
| `recursive` | **3** | `odoo/addons/test_orm/models/test_orm.py:28` | **PERDIDO** |
| `compute_sudo` | **1** | `addons/website_hr_recruitment/models/hr_department.py:10` | **PERDIDO** |
| `precompute` | 1 | `addons/hr/models/hr_employee.py:218` | correcto — y ese caso declara `precompute=False`, que es el default |

**El hueco 1 son cuatro atributos y 684 declaraciones de la referencia.** No es
un caso de borde: `readonly=` sobre un campo con columna es la forma normal de
declarar un campo que la interfaz no deja editar.

*Métrica:* nodos `ast.Call` con `func` `fields.<X>` cuyo conjunto de
`keywords` no contiene `compute` ni `related` y sí contiene el atributo.
*Ciega a:* la declaración que llega por `_inherit` reabriendo el campo sin
repetir el constructor, y a la que usa un alias distinto de `fields` para el
módulo. Cota inferior, no censo cerrado.

## M14 — El filtro `declared_keys` anulado: caen 4, y con la parametrización vieja habría caído 1

Fecha: 2026-09-11T16:42:51

El arreglo de :ref:`h-api-1103` tiene **dos mitades** y sólo una tenía
anulación. La primera —retirar la salida temprana— ya se midió: 8 caen de 23.
La segunda es el filtro que retiene lo no declarado, y ésta es su medición.

**Primero, el universo real.** `apply_source_defaults` deja en `attrs`, para un
campo llano y **sin que nadie las declare**:

```
sin declarar nada    ['compute', 'declared_keys', 'inverse', 'precompute', 'store']
readonly=True        [... 'readonly' ...]        declared_keys=['readonly']
inverse declarado    [... sin 'readonly' ...]    declared_keys=['inverse']
compute declarado    [... 'compute_sudo', 'copy', 'readonly' ...]
related              [... 'compute_sudo', 'copy', 'readonly' ...]
```

`related_declared` **no** está: `apply_source_defaults` la saca con un
`attrs.pop('related_declared', None)` antes de devolver.

**El control estaba ciego a 3 de 4.** `TestTheClassDefaultIsNotStamped` se
parametrizaba sobre `LOST_ON_A_PLAIN_FIELD` —`readonly`, `compute_sudo`,
`inverse`, `recursive`— y de esas cuatro **sólo `inverse`** viaja
incondicionalmente en `attrs`. Las otras tres no aterrizarían ni sin filtro,
así que su verde no discriminaba: medía un sujeto ausente.

Ensanchado a la unión de las dos listas (7 casos distintos), la anulación del
filtro —`landing = attrs`, con `__pycache__` purgado— da:

```
FAILED ...TestTheClassDefaultIsNotStamped::test_an_undeclared_attribute_stays_on_the_class[compute]
FAILED ...TestTheClassDefaultIsNotStamped::test_an_undeclared_attribute_stays_on_the_class[inverse]
FAILED ...TestTheClassDefaultIsNotStamped::test_an_undeclared_attribute_stays_on_the_class[precompute]
FAILED ...TestTheClassDefaultIsNotStamped::test_an_undeclared_attribute_stays_on_the_class[store]
4 failed, 26 passed, 1 warning in 5.70s
```

**Exactamente las cuatro incondicionales, ni una más**: `readonly`,
`compute_sudo` y `recursive` sobreviven porque no están en el `attrs` de un
campo llano sin declaración. Restaurado el filtro: 30 passed, y
`grep -c ANULACION` da 0.

**Lo que esto prueba, que son dos cosas:** que el filtro hace lo que dice, y
que el control con la parametrización vieja habría publicado verde sobre 3 de
las 4 claves que el filtro retiene. Ese segundo hallazgo es el sub-patrón D de
`metrica-decide-la-conclusion.md` dentro del propio control de anulación.

*Métrica:* claves presentes en `field.__dict__` de un `fields.Char()` sin
argumentos, con y sin el filtro.
*Ciega a:* el **valor** — las cuatro coinciden con su default de clase
(`compute` None, `inverse` None, `precompute` False, `store` True), así que
`test_and_the_class_still_answers_the_default` **no** cae con la anulación y no
sirve como control de esta mitad. Sólo la membresía en `__dict__` discrimina.

## M15 — El eje `readonly` → `editable` NO lo movió el arreglo

Fecha: 2026-09-11T16:42:51

El advisor pidió verificar si el arreglo cambia el contrato del endpoint: 24
declaraciones de `readonly=True` en nuestro árbol pasarían a llevar un
`readonly` que el serializer tendría que honrar. Medido en los dos árboles,
con `__pycache__` purgado entre medición y medición:

```
HEAD (sin el arreglo)   field.readonly = False | field.editable = False
con el arreglo          field.readonly = True  | field.editable = False
```

**`editable=False` es anterior al arreglo.** La inyección de
`apply_source_defaults` lee `attrs.get('readonly')`, y esa clave ya la ponía la
rama `elif not declared['compute']` —`if declared['readonly'] is not _UNSET`—
que el diff no toca. Lo que el arreglo cambia es el **atributo del ORM**, que
antes devolvía el default de clase.

O sea: la preocupación estaba invertida. El contrato del endpoint ya honraba la
declaración; el que mentía era `field.readonly`, que es lo que consume el ORM
—no DRF— para decidir si un campo se recalcula al escribir.

**Residuo medido, y es un hueco real:** un `NonStored` **no tiene** atributo
`editable` (`AttributeError` al pedirlo sobre `fields.Char(compute='_c')`). Hoy
es inocuo porque un `NonStored` no está en `_meta.get_fields()` y DRF nunca lo
alcanza por el mapeo automático; deja de serlo el día que un serializer lo
declare a mano. Sucesor: **TASK-API-0414**.

*Métrica:* `field.readonly` y `field.editable` sobre `fields.Char(readonly=True)`,
con el módulo de HEAD y con el del árbol.
*Ciega a:* lo que un serializer declarado a mano haga con el campo — el eje
medido es el mapeo automático de `ModelSerializer`, no un `Meta.fields` con
override.

## M16 — La etiqueta colisionó viva, y el renumerado es del más nuevo (2026-09-11T16:56:18)

El `pre-push` de docs rechazó la publicación: `.. _h-api-1101:` estaba
declarada **dos veces** sobre 1350 etiquetas del árbol. No es un defecto de
este trabajo — es que el número se eligió sin medir el árbol, y otra
iniciativa ya lo había tomado 39 minutos antes.

| | iniciativa | `:fecha_creacion:` | commit |
|---|---|---|---|
| el otro | `adaptar-familias-odoo-monolito-modular` | 15:48:18 | `docs@ae9f6ef64` |
| el mío | `completar-raiz-orm` | 16:27:13 | `docs@75190294e` |

Renumera el **más nuevo**, así que los dos míos ceden: H-API-1101 →
**H-API-1103** y H-API-1102 → **H-API-1104**. El bloque libre se midió antes
de tomarlo —el máximo del árbol excluyendo los míos era 1101— en vez de
suponerlo.

Lo que esto cuesta y por qué importa: un `:ref:` a una etiqueta duplicada
**resuelve al equivocado en silencio**. Sphinx avisa con `duplicate label` en
el build, que es opcional en este proyecto, así que sin el gate de push la
cita habría apuntado a otro hallazgo sin que nadie lo notara.

*Métrica:* unicidad de la **declaración** `^.. _h-api-NNNN:` sobre los
`.rst` de `source/`, por `check-ids-duplicados.sh --solo-etiquetas`.
*Ciega a:* que una cita apunte al ID equivocado sin que haya duplicado —
eso es semántico y ningún patrón lo ve; y a las citas sin ancla de contexto,
que el propio gate declara (ve 463 de 1639 apariciones de `#NNN`).

Las tres citas del lado api —el comentario de `annotate_related`, la M14 de
este banco y el docstring del archivo de test— se reapuntaron a
`h-api-1103` en el mismo pase. El hallazgo sigue citando `api@a5966121`,
que es el commit que lo resolvió y no cambia.
