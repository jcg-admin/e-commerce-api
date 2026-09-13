"""Control de la paridad de atributos de clase — TDD, la mitad ROJA primero.

Lo que discrimina NO es «encuentra atributos ausentes». Son tres cosas que un
emparejador ingenuo daria por buenas:

1. **La clase sin contraparte no se marca.** `atributos-de-clase-de-modelo.md`
   tiene dos mitades y la segunda es la que se pierde: *«Si no declara ninguno,
   no se inventa ninguno»*. Un instrumento que marcara toda clase sin `_name`
   forzaria una cabecera inventada sobre los modelos propios del L0.
2. **`_table` declarado GANA sobre la sustitucion de `_name`.** En la fuente
   `model_cls._table = model_cls._name.replace('.','_')`
   (`odoo19c: odoo/orm/model_classes.py:266`) es el DEFAULT, y nueve de las diez
   clases de `ir_actions.py` lo sobreescriben — `ir.actions.act_window` declara
   `_table = 'ir_act_window'`, no `ir_actions_act_window`. Un join que derive de
   `_name` no empareja NINGUNA de esas nueve.
3. **Un objeto de tabla no es un atributo de ORM.** `models.Constraint`,
   `models.Index` y `models.UniqueIndex` comparten el prefijo `_` y su hogar
   aqui es `Meta.constraints` / `Meta.indexes`. Contarlos como ausentes exigiria
   declararlos como atributo de clase, que es el defecto inverso.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from class_attr_parity import (  # noqa: E402
    ORM_ATTRS_ARE_TABLE_OBJECTS,
    join_keys,
    pair_classes,
    reference_table,
    split_table_objects,
)


# --- 1. la clave de join ---------------------------------------------------

def test_declared_table_wins_over_the_name_substitution():
    # EL QUE CORRIGE LA PREMISA. Sin esto, `ir.actions.act_window` derivaria a
    # `ir_actions_act_window` y no emparejaria con nuestro `ir_act_window`.
    assert reference_table({'_name': 'ir.actions.act_window',
                            '_table': 'ir_act_window'}) == 'ir_act_window'


def test_the_substitution_is_the_default_when_no_table_is_declared():
    assert reference_table({'_name': 'ir.actions.server.history'}) \
        == 'ir_actions_server_history'


def test_class_name_joins_across_the_underscore_of_the_reference():
    # `IrActionsAct_Window` de la fuente es nuestro `IrActionsActWindow`.
    assert 'iractionsactwindow' in join_keys('IrActionsAct_Window', None)


def test_exact_class_name_is_also_a_key():
    assert 'iractionsclient' in join_keys('IrActionsClient', None)


def test_the_table_is_a_key_of_its_own():
    assert 'tabla:ir_act_url' in join_keys('IrActionsAct_Url', 'ir_act_url')


# --- 2. la mitad que NO se marca -------------------------------------------

def test_a_class_with_no_counterpart_is_not_paired():
    # EL QUE DISCRIMINA. `IrActionsBase` es nuestra base abstracta propia; la
    # fuente no la tiene. Emparejarla obligaria a inventarle una cabecera.
    pares, nuestras_sin_par, ref_sin_par = pair_classes(
        {'IrActionsClient': ('IrActionsClient', 'ir_act_client')},
        {'IrActionsBase': ('IrActionsBase', None),
         'IrActionsClient': ('IrActionsClient', 'ir_act_client')},
    )
    assert 'IrActionsBase' in nuestras_sin_par
    assert dict(pares) == {'IrActionsClient': 'IrActionsClient'}


def test_two_classes_sharing_a_table_do_not_collapse():
    # `ir.actions.actions` y `ir.actions.act_window_close` declaran las DOS
    # `_table = 'ir_actions'`. El join por tabla no es inyectivo: si colapsara,
    # una de las dos quedaria sin par y su cabecera sin medir.
    pares, _, ref_sin_par = pair_classes(
        {'IrActionsActions': ('IrActionsActions', 'ir_actions'),
         'IrActionsAct_Window_Close': ('IrActionsAct_Window_Close', 'ir_actions')},
        {'IrActionsActions': ('IrActionsActions', 'ir_actions'),
         'IrActionsActWindowClose': ('IrActionsActWindowClose', 'ir_actions')},
    )
    assert dict(pares) == {'IrActionsActions': 'IrActionsActions',
                           'IrActionsAct_Window_Close': 'IrActionsActWindowClose'}
    assert ref_sin_par == []


def test_the_table_key_alone_does_not_map_two_classes_onto_one():
    # EL CONTROL DEL RETIRO. Aqui la tabla es la UNICA clave que resuelve — los
    # nombres no se parecen ni normalizando —, asi que sin retirar la clase ya
    # emparejada las dos de la fuente caerian sobre la primera candidata y una
    # quedaria sin medir. La fixture de arriba no lo ejercitaba: alli el nombre
    # ya resolvia, y el retiro era codigo muerto que ningun verde delataba.
    pares, _, ref_sin_par = pair_classes(
        {'AlphaAction': ('AlphaAction', 'ir_actions'),
         'BetaAction': ('BetaAction', 'ir_actions')},
        {'PrimeraNuestra': ('PrimeraNuestra', 'ir_actions'),
         'SegundaNuestra': ('SegundaNuestra', 'ir_actions')},
    )
    assert len({n for _, n in pares}) == 2, f'colapsaron: {pares}'
    assert ref_sin_par == []


# --- 3. el objeto de tabla no es un atributo de ORM ------------------------

def test_a_table_object_is_not_counted_as_a_missing_orm_attribute():
    orm, objetos = split_table_objects({
        '_name': 'ir.actions.act_window.view',
        '_unique_mode_per_action': 'models.UniqueIndex(...)',
    })
    assert '_unique_mode_per_action' in objetos
    assert '_unique_mode_per_action' not in orm
    assert '_name' in orm


def test_the_table_object_families_are_declared_not_inferred():
    assert ORM_ATTRS_ARE_TABLE_OBJECTS == ('Constraint', 'Index', 'UniqueIndex')


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_'):
            try:
                fn()
                print(f'  ok    {nombre}')
            except Exception as exc:                       # noqa: BLE001
                fallos += 1
                print(f'  FALLA {nombre} — {type(exc).__name__}: {exc}')
    total = sum(1 for n in globals() if n.startswith('test_'))
    print(f'\naserciones: {total}  ok: {total - fallos}  fallo: {fallos}')
    sys.exit(1 if fallos else 0)
