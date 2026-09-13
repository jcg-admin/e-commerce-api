r"""``ondelete`` de la fuente sobre ``fields.Many2one`` — la mitad ROJA.

El censo de raíz da `Many2one` como **presente**. Lo está como nombre: su
contrato NO. La referencia declara la política de borrado con la palabra clave
``ondelete`` y tres valores —``OnDelete = Literal['cascade', 'set null',
'restrict']`` (``odoo19c: odoo/orm/fields_relational.py:28``)—; nuestro puerto
sólo aceptaba el ``on_delete`` de Django, así que la primera declaración fiel
de la referencia levantaba ``TypeError: ForeignKey.__init__() missing 1
required positional argument: 'on_delete'``.

Por qué nadie lo había destapado, medido: de los tres ``fields.Many2one(...,
ondelete=...)`` del árbol, **dos están dentro de un docstring** que cita a la
fuente y el tercero es el del addon ``test_orm`` que lo destapó. Cero en
código. Todos los modelos portados se escribieron con el vocabulario de Django,
no con el de la fuente, así que el hueco nunca llegó a un intérprete.

LA POLÍTICA SE PORTA, NO SE INVENTA. Está escrita en
``odoo19c: odoo/orm/fields_relational.py:268-295`` y tiene tres casos:

1. sin ``ondelete`` declarado -> ``'restrict' if required else 'set null'``;
2. ``'set null'`` sobre un campo ``required`` -> ``ValueError``;
3. ``'restrict'`` hacia un modelo de ``IR_MODELS`` -> ``ValueError``.

Lo que sí diverge es el MOMENTO, y la divergencia es del stack, no del porte:
la fuente resuelve en ``setup_nonrelated``, una fase que Django no tiene, y su
``ForeignKey.__init__`` exige ``on_delete`` posicional. La resolución ocurre por
tanto al construir. La rama de ``is_transient()`` de la fuente necesita el
modelo, que en ``__init__`` no existe todavía: queda declarada en el puerto,
medida, y no se simula. Su cierre es TASK-API-0405.

Qué haría FALLAR este control (sub-patrón D): que el porte traduzca sólo
``'cascade'`` y deje los otros dos al azar, o que acepte ``ondelete`` y NO
aplique la validación. Las dos clases de error miden exactamente eso, y cada
una se probó por anulación: retirada la rama de ``:289`` cae sólo el caso de
``ir.model``; retirada la de ``:283`` cae sólo el de set-null-requerido;
retirado el default de ``:282`` —en sus DOS ramas— cae sólo el caso por
omisión. Ni una aserción más en ninguna de las tres.

*Métrica:* la política que el campo construido lleva en
``remote_field.on_delete``, o la excepción que levantó al construirse.
*Ciega a:* el caso 3 declarado con la **etiqueta de Django** —
``fields.Many2one('base.IrModel', ondelete='restrict')``—. ``:289`` compara la
cadena declarada contra ``IR_MODELS``, que lleva ``_name`` de la fuente, y
allá no hay segundo vocabulario que comparar. Medido antes de dejarlo así:
**0** declaraciones del árbol combinan etiqueta de Django con ``ondelete=``
(``grep -rnE "Many2one\(\s*['\"][a-z_]+\.[A-Z]" src/ --include=*.py |
grep -c ondelete``), así que el caso es hoy inalcanzable. Sucesor registrado:
TASK-API-0404.
"""
import pytest
from django.db import models as django_models

import fields


def deletion_policy(field):
    """La política que el campo construido lleva en su ``remote_field``."""
    return getattr(field.remote_field, 'on_delete', None)


class TestTheThreeValuesOfTheLiteral:
    """Los tres de ``OnDelete``, cada uno a su política de Django."""

    @pytest.mark.parametrize('declared, expected', [
        ('cascade', django_models.CASCADE),
        ('set null', django_models.SET_NULL),
        ('restrict', django_models.RESTRICT),
    ])
    def test_each_value_maps_to_its_policy(self, declared, expected):
        # `null=True` porque `'set null'` sobre un campo requerido es el
        # ValueError de `:283`: sin el, este caso mediria aquella rama.
        field = fields.Many2one('base.ResPartner', ondelete=declared,
                                null=True)

        assert deletion_policy(field) is expected

    def test_restrict_is_the_sql_clause_not_the_python_guard(self):
        """``RESTRICT`` emite ``ON DELETE RESTRICT``; ``PROTECT`` es una
        guarda del plano de Python que no llega al esquema. La fuente compone
        la clausula SQL (``:306``/``:318``), asi que el puerto toma la que
        tiene contraparte en el motor."""
        field = fields.Many2one('base.ResPartner', ondelete='restrict',
                                null=True)

        assert deletion_policy(field) is not django_models.PROTECT


class TestTheDefaultWhenNothingIsDeclared:
    """``:282`` — ``'restrict' if required else 'set null'``."""

    def test_optional_and_undeclared_gives_set_null(self):
        field = fields.Many2one('base.ResPartner', null=True)

        assert deletion_policy(field) is django_models.SET_NULL


class TestTheTwoProgrammingErrorsOfTheSource:
    """Las dos ramas que la fuente rechaza con ``ValueError``."""

    def test_set_null_on_a_required_field_is_refused(self):
        """``:283`` — un campo requerido no puede quedar en NULL."""
        with pytest.raises(ValueError):
            fields.Many2one('base.ResPartner', ondelete='set null',
                            null=False)

    def test_restrict_towards_a_registry_model_is_refused(self):
        """``:289`` — el comodelo se nombra con el ``_name`` de la fuente, que
        es el unico vocabulario que esa linea compara. Ver la ceguera
        declarada arriba."""
        with pytest.raises(ValueError):
            fields.Many2one('ir.model', ondelete='restrict')


class TestTheDjangoVocabularyStaysAlive:
    """El puerto no puede romper lo que ya estaba declarado."""

    def test_on_delete_of_django_still_works(self):
        field = fields.Many2one('base.ResPartner',
                                on_delete=django_models.CASCADE)

        assert deletion_policy(field) is django_models.CASCADE
