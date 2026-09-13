"""Las tres fachadas de azucar publican lo que la referencia publica.

La referencia **declara** el mecanismo en ``odoo/orm/`` y lo **re-exporta** en
tres paquetes, cuyo comentario de cabecera dice lo mismo palabra por palabra
(``odoo19c: odoo/{api,fields,models}/__init__.py``)::

    # Exports features of the ORM to developers.
    # This is a `__init__.py` file to avoid merge conflicts on `odoo/<x>.py`.

Y ``odoo/orm/__init__.py`` declara lo contrario para si mismo — *"developers
should not import directly from here"*—: no re-exporta nada.

Por eso la re-exportacion **es el porte**, no una deuda que se salda aparte. Un
simbolo declarado en ``src/orm`` y no ligado aqui no esta portado a medias:
esta portado **en otro sitio** que el de la fuente, que es la divergencia de
:ref:`h-api-578`. Estos casos son el control de esa mitad — sin ellos, un
``src/orm`` completo y una fachada vacia pasarian iguales.

El censo de :ref:`h-api-1041` es estructuralmente ciego a esta capa: su alcance
de resolucion es el archivo **dentro** de ``odoo/orm/``, y los tres paquetes
viven fuera. Ver :ref:`h-api-1043`.
"""
import ast
import importlib
import pathlib

import pytest

import django.db.models as django_models

import api
import fields
import models
import orm.table_objects as table_objects

#: Lo que cada fachada de la referencia liga y ``src/orm`` YA declara, asi que
#: su re-exportacion no espera a ningun porte. Medido por AST sobre los
#: ``ImportFrom`` de ``odoo19c: odoo/{api,fields,models}/__init__.py`` cruzado
#: con las declaraciones de modulo de ``src/orm/``.
PORTABLE_NOW = {
    'api': ('NewId', 'Environment', 'SUPERUSER_ID',
            'ContextType', 'DomainType', 'IdType', 'ValuesType',
            # Los dos que la tarea #330 porta y liga en el mismo pase.
            'depends_context', 'ondelete'),
    'fields': ('Field', 'NO_ACCESS'),
    'models': ('LOG_ACCESS_COLUMNS', 'MAGIC_COLUMNS',
               'READ_GROUP_NUMBER_GRANULARITY', 'fix_import_export_id_paths',
               'regex_order', 'is_model_class', 'is_model_definition',
               'TransientModel', 'Constraint', 'Index', 'UniqueIndex',
               'check_object_name', 'check_pg_name',
               # Los tres que la tarea #328 porta y liga en el mismo pase.
               'AbstractModel', 'parse_read_group_spec', 'check_method_name',
               # El que la tarea #331 porta y liga en el mismo pase.
               'to_record_ids',
               # El que TASK-API-0397 porta y liga en el mismo pase.
               'BaseModel'),
}

#: Lo que la fachada de la referencia liga y ``src/orm`` todavia NO declara.
#: Ligarlos hoy rompe el import del paquete, asi que cada uno entra con el pase
#: que porta su simbolo — es el mismo pase, no un barrido posterior.
BLOCKED_BY_ITS_SYMBOL = {
    'api': ('deprecated', 'Self'),
    'fields': ('Id',),
    # ``check_company_domain_parent_of`` y su hermano plural salieron de aqui
    # en la tarea #333: ``account.journal`` y ``res.partner.bank`` los declaran
    # como ``_check_company_domain``, y el pase que porto esos dos atributos de
    # clase construyo los dos simbolos, que es lo que esta lista describe.
    # ``READ_GROUP_TIME_GRANULARITY`` salio de aqui al portarse en
    # ``orm/utils.py``, junto a su hermano de numero. La fuente lo
    # re-exporta desde ``odoo.orm.utils`` (``odoo/models/__init__.py:27``),
    # asi que la fachada lo liga por el mismo bloque.
    # ``BaseModel`` salio de aqui en TASK-API-0397, que lo porto como base
    # abstracta de Django y lo ligo en la fachada en el mismo pase.
    'models': ('READ_GROUP_DISPLAY_FORMAT', 'MetaModel'),
}

PACKAGES = {'api': api, 'fields': fields, 'models': models}

#: El modulo de ``orm`` que declara cada nombre — la procedencia que la fachada
#: re-exporta. Medido por AST sobre las declaraciones de modulo de ``src/orm``.
#: Dos difieren de sitio respecto de la fuente y lo declaran: ``IdType`` (alla
#: ``orm/types.py``, aqui ``orm/identifiers.py``, junto a ``NewId``) y
#: ``READ_GROUP_NUMBER_GRANULARITY`` (alla ``orm/models.py``, aqui
#: ``orm/utils.py``, junto a su hermano ``READ_GROUP_TIME_GRANULARITY``).
DECLARANTE = {
    'NewId': 'orm.identifiers', 'IdType': 'orm.identifiers',
    'Environment': 'orm.environments',
    'SUPERUSER_ID': 'orm.utils',
    'ContextType': 'orm.types', 'DomainType': 'orm.types',
    'ValuesType': 'orm.types',
    'Field': 'orm.fields',
    'NO_ACCESS': 'orm.models',
    'LOG_ACCESS_COLUMNS': 'orm.models', 'MAGIC_COLUMNS': 'orm.models',
    'fix_import_export_id_paths': 'orm.models', 'regex_order': 'orm.models',
    'READ_GROUP_NUMBER_GRANULARITY': 'orm.utils',
    'READ_GROUP_TIME_GRANULARITY': 'orm.utils',
    'check_object_name': 'orm.utils', 'check_pg_name': 'orm.utils',
    'depends_context': 'orm.decorators', 'ondelete': 'orm.decorators',
    'check_method_name': 'orm.utils',
    'AbstractModel': 'orm.models', 'parse_read_group_spec': 'orm.models',
    'BaseModel': 'orm.models',
    'to_record_ids': 'orm.models',
    'is_model_class': 'orm.model_classes',
    'is_model_definition': 'orm.model_classes',
    'TransientModel': 'orm.models_transient',
    'Constraint': 'orm.table_objects', 'Index': 'orm.table_objects',
    'UniqueIndex': 'orm.table_objects',
}


def _cases(mapa):
    return [(p, n) for p, names in mapa.items() for n in names]


class TestTheFacadeBindsWhatOrmAlreadyDeclares:
    """La mitad del porte que vive en el paquete, no en el archivo."""

    @pytest.mark.parametrize(('package', 'name'), _cases(PORTABLE_NOW))
    def test_the_symbol_is_reachable_through_its_package(self, package, name):
        assert hasattr(PACKAGES[package], name), (
            f'{package}.{name} no esta ligado: el simbolo existe en src/orm '
            'pero su porte quedo en otro sitio que el de la fuente'
        )

    @pytest.mark.parametrize(('package', 'name'), _cases(PORTABLE_NOW))
    def test_it_is_the_very_object_its_orm_module_declares(self, package,
                                                           name):
        """EL CONTROL que discrimina ligar de re-declarar.

        ``hasattr`` pasaria igual si la fachada definiera un objeto propio con
        el mismo nombre, y entonces habria dos verdades para un simbolo. Lo que
        se exige es **identidad**: el objeto de la fachada ES el del modulo de
        ``orm`` que lo declara.

        No se exige que ``__module__`` empiece por ``orm``, y esa version del
        control estuvo escrita y era el sub-patron C sobre si mismo: media
        DONDE se definio la clase y concluia sobre SI es el objeto correcto.
        ``orm/fields.py:1229`` liga ``Field = models.Field`` — el nombre de la
        fuente sobre la base real de este arbol, con los 66 atributos de clase
        de la referencia instalados encima. Su ``__module__`` dice
        ``django.db.models.fields`` y aun asi es el porte, no un homonimo.
        """
        obj = getattr(PACKAGES[package], name)
        module = importlib.import_module(DECLARANTE[name])
        assert obj is getattr(module, name), (
            f'{package}.{name} no es el objeto de {DECLARANTE[name]}: '
            'la fachada re-exporta, no re-declara'
        )


class TestTheBlockedOnesDeclareTheirCoverage:
    """Lo que no se liga hoy declara por que, y el por que es medible."""

    @pytest.mark.parametrize(('package', 'name'), _cases(BLOCKED_BY_ITS_SYMBOL))
    def test_src_orm_does_not_declare_it_yet(self, package, name):
        """EL CONTROL POSITIVO del bloqueo.

        Sin este caso, ``BLOCKED_BY_ITS_SYMBOL`` seria una lista de excusas que
        nadie vuelve a mirar: un simbolo portado despues se quedaria ahi, no
        ligado, y el bloqueo declarado seguiria pareciendo cierto. El caso
        falla en cuanto ``src/orm`` lo declare — que es cuando hay que ligarlo.
        """
        assert name not in _declarations_of_src_orm(), (
            f'{name} YA lo declara src/orm: su bloqueo caduco y le toca '
            f'entrar en la fachada {package}'
        )


class TestTheFacadeDoesNotHideItsProvenance:
    """La referencia importa de cada modulo que define; el agregador no."""

    @pytest.mark.parametrize('package', ('api', 'fields'))
    def test_it_does_not_import_with_star(self, package):
        """Un ``import *`` congela la superficie en el instante del import.

        Es el defecto que :ref:`h-api-604` corrigio en la fachada de campos: un
        simbolo publicado despues del arranque no llegaba a la puerta publica.
        Y esconde la procedencia, que es lo que la referencia cuida importando
        de doce modulos distintos en vez de uno agregado.
        """
        path = pathlib.Path('src') / package / '__init__.py'
        tree = ast.parse(path.read_text())
        stars = [n.module for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom)
                     and any(a.name == '*' for a in n.names)]
        assert stars == [], (
            f'src/{package}/__init__.py importa con * desde {estrellas}'
        )

    def test_the_models_star_is_a_measured_divergence_not_an_oversight(self):
        """``models`` SI importa con ``*``, y no es descuido: es el puente.

        La fachada de la referencia re-exporta solo el ORM de Odoo, porque alli
        los campos viven en ``odoo/fields``. Aqui ``models.CharField``,
        ``models.ForeignKey`` y ``models.CASCADE`` son de Django y los escriben
        asi **310 archivos** que hacen ``import models``. Retirar el ``*``
        romperia los 310.

        Este caso es el control de la divergencia: fija que el puente exista y
        que siga siendo el de ``django.db.models``, no una copia nuestra.
        """
        tree = ast.parse(pathlib.Path('src/models/__init__.py').read_text())
        stars = [n.module for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom)
                     and any(a.name == '*' for a in n.names)]
        assert stars == ['orm.models'], stars
        assert models.CharField is django_models.CharField
        assert models.ForeignKey is django_models.ForeignKey
        assert models.CASCADE is django_models.CASCADE


def _declarations_of_src_orm():
    """Los nombres que ``src/orm`` declara a nivel de modulo."""
    names = set()
    for py in pathlib.Path('src/orm').rglob('*.py'):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names |= {t.id for t in node.targets
                            if isinstance(t, ast.Name)}
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                                ast.Name):
                names.add(node.target.id)
    return names


class TestTheIndexNameServesBothUses:
    """El unico nombre que tuvo que decidirse — #321 y #322.

    ``odoo19c: odoo/models/__init__.py`` re-exporta ``Index`` desde
    ``odoo/orm/table_objects.py``. Aqui la fachada tambien entrega la
    superficie de Django, donde ``Index`` se escribe con palabras clave en
    ``Meta.indexes`` — 51 sitios reales. El reparto por la forma de la llamada
    (``orm/table_objects.py::Index.__new__``) deja que un solo nombre sirva a
    los dos, y estos casos lo fijan **desde la fachada**, que es por donde un
    addon lo escribe.
    """

    def test_the_facade_hands_the_table_object_on_a_positional_call(self):
        assert isinstance(models.Index('(active) WHERE active IS TRUE'),
                          table_objects.Index)

    def test_the_facade_hands_djangos_index_on_a_keyword_call(self):
        """EL CONTROL de los 51: si esto cae, ``Meta.indexes`` deja de recibir
        lo que Django espera y las migraciones del arbol se rompen."""
        assert type(models.Index(fields=['name'], name='x_idx')) is (
            django_models.Index)
