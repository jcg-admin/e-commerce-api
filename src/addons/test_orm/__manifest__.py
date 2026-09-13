# Adaptado de Odoo Community `odoo/addons/test_orm/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Test ORM',
    'version': '1.0',
    'category': 'Hidden/Tests',
    'summary': 'La suite del ORM de la referencia: el juez del porte de src/orm',
    'description': 'A module to test the ORM.',
    # La referencia declara `['base', 'web', 'web_tour']`. `web_tour` NO existe
    # en este árbol —medido: `find src/addons addons -maxdepth 1 -name web_tour`
    # devuelve nada— y su consumo está acotado: sólo los dos tours JS de
    # `static/tests/tours/` y los dos casos de `tests/test_ui.py`, que llaman
    # `start_tour`. Son 2 de los 604 casos del addon.
    #
    # Es un bloqueo REAL y nombrado, no una divergencia de conveniencia: la
    # dependencia no está en el árbol, así que los dos casos de navegador y sus
    # dos tours quedan fuera con sucesor declarado (TASK-API-0406). Los otros
    # 602 no tocan `web_tour` y no dependen de esta decisión.
    'depends': ['base', 'web'],
    # Licencia de la fuente, tal como su manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
    'author': 'Odoo S.A.',
    'installable': True,
}
