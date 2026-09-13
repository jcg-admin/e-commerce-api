"""``decimal.precision`` — precisión decimal por dominio (Odoo ``base``).

Portación fiel de ``DecimalPrecision``
(``odoo19c: odoo/addons/base/models/decimal_precision.py``). Config global que
fija cuántos decimales usa un grupo de campos (``Product Price``, ``Product
Unit of Measure``, ``Account``…). Da el control de precisión que tiene la
referencia (``digits='Product Price'``) sobre Django.

Los cinco símbolos de la fuente están aquí: ``precision_get`` con su caché,
``create``, ``write``, ``unlink`` y ``_onchange_digits_warning``.
"""
import api
import fields
import models
from django.db import models as django_models
from orm import registry
from tools.cache import ormcache
from tools.translate import _


class DecimalPrecision(models.OriginMixin, models.Model):
    """``decimal.precision`` — dígitos decimales para un uso nombrado.

    Cabecera — los dos atributos de clase que la referencia declara
    (``odoo19c: decimal_precision.py:10-11``), portados verbatim junto a su
    forma Django derivada (``atributos-de-clase-de-modelo.md``).
    """

    _name = 'decimal.precision'
    _description = 'Decimal Precision'

    name   = fields.Char(
        max_length=128, unique=True,
        help_text='Uso (Odoo name, p. ej. "Product Price"). Único.',
    )
    digits = fields.Integer(
        default=2, help_text='Número de decimales (Odoo digits).',
    )

    class Meta:
        db_table = 'decimal_precision'
        ordering = ['name']
        verbose_name = 'Precisión decimal'
        verbose_name_plural = 'Precisiones decimales'
        constraints = [
            # ≙ ``_name_uniq = models.Constraint('unique (name)', …)``
            # (``odoo19c: decimal_precision.py:16-19``). El nombre de la fuente
            # se conserva, prefijado por la tabla como exige el namespace
            # global de constraints de PostgreSQL.
            django_models.UniqueConstraint(
                fields=['name'], name='decimal_precision_name_uniq',
                violation_error_message=(
                    'Only one value can be defined for each given usage!'
                ),
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name}: {self.digits}'

    @classmethod
    @api.model
    @ormcache('application', cache='stable')
    def precision_get(cls, application: str) -> int:
        """Dígitos declarados para ``application``, o 2. ≙ ``precision_get``
        (``odoo19c: decimal_precision.py:21-27``).

        La referencia baja a SQL crudo (``select digits from decimal_precision
        where name=%s``) precedido de un ``flush_model``, porque su ORM difiere
        las escrituras y el valor recién puesto no estaría en la tabla. Aquí no
        hay cola que vaciar —Django escribe al ejecutar—, así que el
        ``flush_model`` no tiene contraparte y la consulta se hace por el ORM.
        El fallback a **2** se conserva verbatim: es el que hace que un uso no
        sembrado no reviente.

        DIVERGENCIA DE ENLACE, declarada: la fuente lo marca ``@api.model``
        sobre un método de instancia (``self`` es el modelo vacío); aquí es un
        ``classmethod``, porque sin conjuntos de registros el receptor natural
        es la clase — y es la forma que sus seis consumidores de ``addons/`` ya
        usan. ``@api.model`` se conserva encima: la marca que la fuente pone
        sigue estando, y ``ormcache`` lee ``_name`` igual del ``cls``.
        """
        fila = cls.objects.filter(name=application).values_list('digits', flat=True).first()
        return fila if fila is not None else 2

    @classmethod
    @api.model_create_multi
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: decimal_precision.py:29-33``).

        La fuente crea y luego vacía la caché ``stable``, porque un uso nuevo
        cambia lo que ``precision_get`` ya había memorizado —incluido el
        fallback a 2 de un uso que hasta ahora no existía.
        """
        res = [cls.objects.create(**vals) for vals in vals_list]
        registry.clear_cache('stable')
        return res

    def write(self, vals):
        """≙ ``write`` (``odoo19c: decimal_precision.py:35-38``)."""
        for field, value in vals.items():
            setattr(self, field, value)
        res = self.save()
        registry.clear_cache('stable')
        return res

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: decimal_precision.py:40-43``).

        El nombre público del borrado en la referencia. Delega en ``delete()``,
        que es donde Django engancha y donde vive la invalidación — para que un
        borrado directo tampoco deje la caché mintiendo.
        """
        return self.delete()

    def save(self, *args, **kwargs):
        """Vacía la caché ``stable`` en toda escritura.

        Es el punto por el que Django pasa siempre: ``write`` de la referencia
        llega aquí, y también una asignación de atributo seguida de ``save()``,
        que es como escribe el resto del árbol. Poner la invalidación sólo en
        ``write`` la dejaría esquivable.
        """
        res = super().save(*args, **kwargs)
        registry.clear_cache('stable')
        return res

    def delete(self, *args, **kwargs):
        """Vacía la caché ``stable`` en todo borrado — mismo criterio."""
        res = super().delete(*args, **kwargs)
        registry.clear_cache('stable')
        return res

    @api.onchange('digits')
    def _onchange_digits_warning(self):
        """≙ ``_onchange_digits_warning`` (``odoo19c: decimal_precision.py:45-59``).

        Avisa cuando la precisión **baja**: los datos ya escritos no se
        reescriben, así que reducir decimales en una base viva puede descuadrar
        un balance. El texto se porta verbatim de la fuente.
        """
        if self.digits < self._origin.digits:
            return {
                'warning': {
                    'title': _("Warning for %s") % self.name,
                    'message': _(
                        "The precision has been reduced for %s.\n"
                        "Note that existing data WON'T be updated by this change.\n\n"
                        "As decimal precisions impact the whole system, this may cause critical issues.\n"
                        "E.g. reducing the precision could disturb your financial balance.\n\n"
                        "Therefore, changing decimal precisions in a running database is not recommended."
                    ) % self.name,
                }
            }
