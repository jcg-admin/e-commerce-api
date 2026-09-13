#!/usr/bin/env python3
"""Sonda: ``_rec_name`` que nombra el ``attname`` de una FK degrada la etiqueta.

La fuente resuelve ``_rec_name`` en ``self._fields``, que allá tiene UNA clave
por campo: ``self._fields[self._rec_name].convert_to_display_name(
record[self._rec_name], record)`` (``odoo19c: odoo/orm/models.py:1433-1435``).
Aquí Django parte el campo en dos caras —``name`` y ``attname``— y un
``_rec_name`` portado verbatim nombra la segunda.

``resolve_rec_name`` (``src/orm/model_classes.py:222``) ADMITE esa cara a
proposito, y su hermano ``_compute_display_name``
(``src/orm/models.py:2952``) lee con ``getattr(self, rec_name)``, que por el
``attname`` devuelve el entero crudo.

Metrica: el valor de ``display_name`` de un modelo cuyo ``_rec_name`` declarado
es el ``attname`` de una FK, sin tocar la base.
Ciega a: el caso en que la FK esta vacia (``None``), que cae en la guarda de
``_many2one_convert_to_display_name`` y devuelve ``False`` por otra via; y a
todo modelo cuyo ``_rec_name`` nombre la cara ``name``, que ya funciona.
"""
import django

django.setup()

from addons.base.models.ir_ui_view import IrUiViewCustom  # noqa: E402
from django.core.exceptions import FieldDoesNotExist  # noqa: E402


def main():
    modelo = IrUiViewCustom
    rec_name = modelo._rec_name
    print(f'modelo: {modelo.__name__}  _rec_name: {rec_name!r}')

    for clave in ('user_id', 'user'):
        try:
            campo = modelo._meta.get_field(clave)
            print(f'  get_field({clave!r}) -> {type(campo).__name__} '
                  f'name={campo.name} attname={campo.attname}')
        except FieldDoesNotExist:
            print(f'  get_field({clave!r}) -> FieldDoesNotExist')

    registro = modelo(id=1, user_id=7)
    print(f'  getattr(registro, {rec_name!r}) = '
          f'{getattr(registro, rec_name)!r}')
    print(f'  display_name = {registro.display_name!r}')
    print()
    print('esperado por la fuente: la etiqueta del res.users apuntado')
    print('obtenido aqui:          el id crudo como texto')


if __name__ == '__main__':
    main()
