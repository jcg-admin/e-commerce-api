#!/usr/bin/env python3
"""El eje de version: donde vive el ORM en cada uno de los cuatro arboles.

Existe porque la poblacion de este inventario es UNA —19c— y esa eleccion hay
que justificarla midiendo, no declarandola. Fusionar dos versiones en un solo
conteo es el defecto que H-API-76 registro; medir 19c sin decir que 18 tiene
otra forma seria su gemelo por omision.

Lo que la sonda establece, y que la tabla del inventario no puede mostrar:

- ``odoo/orm`` **solo existe en 19c**. No es que 18 no tenga ORM: lo tiene
  PLANO, en ``odoo/models.py``, ``odoo/fields.py`` y ``odoo/api.py``.
- Enterprise **no trae directorio ``odoo/``** en ninguna de sus dos versiones.
  Eso es ausencia de DIRECTORIO, no ausencia de ORM: Enterprise es un arbol de
  addons que se monta sobre Community.

El mapeo archivo-a-archivo entre el ORM plano de 18 y el paquete de 19 **no se
afirma aqui** — exigiria emparejar simbolo a simbolo entre las dos formas, que
es otro analisis. Decirlo sin medirlo seria la forma barata del sub-patron C.
"""
import importlib.util
import json
import pathlib
import sys

RUN_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO = RUN_DIR.parents[2]

#: Los archivos donde 18 aloja lo que 19 movio a ``odoo/orm``. Se listan por
#: NOMBRE para poder medir su tamanio, no para afirmar que se corresponden.
FLAT_ORM_18 = ('models.py', 'fields.py', 'api.py')


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


roots = _load('_probe_roots', REPO / 'scripts/reference_roots.py')


def _lines(path):
    try:
        return len(path.read_text(encoding='utf-8').splitlines())
    except OSError:
        return 0


def measure():
    result = {}
    for alias, root in sorted(roots.TREE_ROOTS.items()):
        # El identificador NO lleva el nombre de la referencia (directiva del
        # ejecutor 2026-09-02): lo que nombra es la RAIZ DEL PAQUETE del arbol,
        # que alli se llama ``odoo/``. La clave del JSON si conserva el nombre
        # de la fuente, porque describe el arbol medido, no a este guion.
        package_root = root / 'odoo'
        orm = package_root / 'orm'
        flat = {
            name: _lines(package_root / name)
            for name in FLAT_ORM_18 if (package_root / name).is_file()
        }
        result[alias] = {
            'root': str(root),
            'root_exists': root.is_dir(),
            'odoo_dir': package_root.is_dir(),
            'orm_package': orm.is_dir(),
            'orm_files': len(sorted(orm.glob('*.py'))) if orm.is_dir() else 0,
            'flat_orm_files': flat,
        }
    return result


def main():
    result = measure()
    destination = RUN_DIR / 'outputs' / 'orm-across-trees.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    header = f"{'alias':9} {'odoo/':6} {'odoo/orm/':10} {'.py':>4}  ORM plano"
    print(header)
    print('-' * len(header))
    for alias, data in result.items():
        flat = ' '.join(f'{k}={v}' for k, v in data['flat_orm_files'].items()) or '—'
        print(f"{alias:9} {'si' if data['odoo_dir'] else 'NO':6} "
              f"{'si' if data['orm_package'] else 'NO':10} "
              f"{data['orm_files']:>4}  {flat}")
    print(f'\n{destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
