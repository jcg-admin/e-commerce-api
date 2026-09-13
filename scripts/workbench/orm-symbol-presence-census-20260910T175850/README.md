# orm-symbol-presence-census

## El encargo

<!-- verbatim, sin parafrasear -->

> «Yo tenia planeado, mejor crear un nuevo THYROX_WORKBENCH_API/ en el cual,
> revisemos el estado actual de todo lo que tenemos implementado en ORM,
> contando los archivos, las clases, funciones, firmas de funciones actuales,»

> «Por el momento, solo es reportar que es lo que tenemos implementado en
> kaupamex-api con relacion a ORM,»

`THYROX_WORKBENCH_API` ya estaba declarado en `.env:1` — «crear un nuevo» es
un run nuevo bajo `scripts/workbench/`, no un directorio nuevo.

## La premisa, si se corrigio al primer comando

La sospecha que motivo el censo era que el criterio de cierre de los cinco
instrumentos previos —«0 ausentes»— lo pudiera satisfacer un arbol de firmas
vacias, porque ninguno mira el cuerpo.

**No se sostiene.** 42 stubs sobre 1646 simbolos declarados; de los 33 que
casan contra la referencia, **32 son fidelidad** —la fuente tambien los deja
vacios— y **1 es hueco real**: `copy_translations` en `src/orm/models.py:1312`.

Lo que si gobierna es la **ausencia**, que ya se medía, y un tercer eje que
ningun instrumento tenia: **95 firmas divergentes** entre simbolos portados.

## Las piezas

| archivo | que hace |
|---|---|
| `census_symbol_presence.py` | el censo: firma + clase de cuerpo por simbolo, unido a `odoo19c` |
| `tests/test_census_symbol_presence.py` | 8 aserciones, sujetos reales del arbol; dos anulaciones |
| `probes/probe_prefix_blindness.py` | cuanta «ausencia» la produce el emparejador y no el arbol |
| `outputs/census.json` | el detalle por archivo: hueco, fidelidad, divergencia, propios |

## Los resultados

**Solo `src/orm`** — 28 archivos:

| eje | cifra |
|---|---|
| declarado por nosotros | 74 clases + 923 funciones = **997** |
| simbolos de `odoo19c` | 792 |
| resueltos en nuestro arbol | **480 (61 %)** |
| ausentes | **312 (39 %)** |
| stubs nuestros | 16 — de ellos **10 fidelidad**, **1 hueco** |
| firmas divergentes | **68** |
| simbolos solo nuestros | 383 |

Las dos raices juntas (`src/orm` + `src/tools`, 69 archivos): 1646 simbolos
declarados, 1518 de la referencia, 961 resueltos, **557 ausentes**, 42 stubs,
95 firmas divergentes.

*Metrica:* clases y funciones declaradas por AST —modulo y metodo, nunca
anidadas dentro de una funcion— con firma sin receptor y clase de cuerpo;
union por nombre de archivo dentro de `FIXED_MIRRORED_ROOTS` y por nombre de
simbolo via `resolve()`.
*Ciega a:* el prefijo de disolucion que `resolve()` no conoce —medido: 52 de
650 ocurrencias (8 %) casarian por sufijo, 20 de ellas en `fields_temporal.py`—;
al desacuerdo de universo entre el censo (deduplica: 1518) y su sonda (cuenta
ocurrencias: 650); al homologo que vive en otro archivo de la referencia
(H-API-855); y a que un cuerpo sustantivo HAGA lo que el de la fuente hace.
