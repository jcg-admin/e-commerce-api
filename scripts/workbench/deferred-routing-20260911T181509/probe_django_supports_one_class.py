"""¿Puede UNA sola clase de campo decidir su columna al contribuir?

La fuente no tiene dos clases. ``store`` es un **atributo** de ``Field``
(``odoo19c: odoo/orm/fields.py:278``) y se deriva al FUSIONAR, dentro de
``_get_attrs`` (``:443-450``), a partir de claves que pueden venir de otra
clase de la jerarquía. Su ``Field.__init__`` son tres líneas y no enruta
(``:314-317``).

Aquí la fachada enruta al CONSTRUIR: con ``compute=`` sale un ``NonStored``,
sin él un ``CharField``. Esta sonda mide si el stack admite el orden de la
fuente —capturar · recolectar · fusionar · derivar ``store`` · enrutar— o si
el reparto en dos clases es una restricción del stack.

Se mide por CONDUCTA, no por literal: se construyen modelos reales y se
inspecciona a dónde aterrizó cada campo. Un grep sobre ``django/db/models``
mediría el significante (que la llamada exista) y concluiría sobre el
significado (que sea saltable por instancia), que es el sub-patrón C de
``metrica-decide-la-conclusion.md``.
"""
import os
import sys

import django

APP = 'test_orm'


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()
    from django.db import models
    from django.db.migrations.state import ModelState

    verdicts = []

    # -- A. ¿Es saltable `_meta.add_field` por instancia? --------------------
    #
    # Se declara UNA clase de campo que, al contribuir, se registra como
    # privado. `Options.add_field` mete los privados en `private_fields` y
    # nunca en `local_fields`, así que el motor de migraciones no los ve.

    class ColumnlessChar(models.CharField):
        """Un `CharField` que al contribuir decide NO llevar columna."""

        def contribute_to_class(self, cls, name, private_only=False):
            super().contribute_to_class(cls, name, private_only=True)

    class RoutedAtContribute(models.Model):
        label = ColumnlessChar(max_length=9)

        class Meta:
            app_label = APP

    class RoutedPlain(models.Model):
        label = models.CharField(max_length=9)

        class Meta:
            app_label = APP

    def landing(model):
        local = [f.name for f in model._meta.local_fields]
        private = [f.name for f in model._meta.private_fields]
        state = list(ModelState.from_model(model).fields)
        return local, private, state

    sin_columna = landing(RoutedAtContribute)
    con_columna = landing(RoutedPlain)

    print('== A. la decision de columna, al contribuir ==')
    for etiqueta, (local, private, state) in [
            ('ColumnlessChar', sin_columna), ('CharField (control)', con_columna)]:
        print(f'   {etiqueta:22} local={local} private={private} migracion={state}')

    #: El control positivo es el `CharField` llano: si los dos aterrizaran
    #: igual, la sonda no discriminaria y su verde no diria nada.
    salta = ('label' in sin_columna[1] and 'label' not in sin_columna[2])
    control = ('label' in con_columna[0] and 'label' in con_columna[2])
    verdicts.append(salta and control)
    print(f'   saltable por instancia : {salta}   (control llano lleva columna: {control})')

    # -- B. La herencia de Django PISA; la de la fuente FUSIONA --------------
    #
    # `ModelBase.__new__` copia un campo de la base abstracta solo si el hijo
    # no lo redeclara. Cuando lo redeclara, el objeto del padre NO llega al
    # `_meta` del hijo — pero sigue vivo en el `_meta` de la propia base.

    class LabelBase(models.Model):
        label = models.CharField(max_length=9)

        class Meta:
            app_label = APP
            abstract = True

    class LabelOverride(LabelBase):
        label = models.CharField(max_length=3)

        class Meta:
            app_label = APP

    en_hijo = [f for f in LabelOverride._meta.local_fields if f.name == 'label']
    por_mro = []
    for base in reversed(LabelOverride.__mro__):
        meta = getattr(base, '_meta', None)
        if meta is None or base is LabelOverride:
            continue
        por_mro += [(base.__name__, f.max_length)
                    for f in meta.local_fields if f.name == 'label']

    print('\n== B. redeclarar en el hijo: pisa o fusiona ==')
    print(f'   en el _meta del hijo   : {[f.max_length for f in en_hijo]}')
    print(f'   recuperable por __mro__: {por_mro}')

    #: Uno solo en el hijo (el suyo) y el del padre recuperable aparte: eso es
    #: PISAR. Si Django fusionara, el hijo veria los dos o uno combinado.
    pisa = len(en_hijo) == 1 and en_hijo[0].max_length == 3
    recuperable = por_mro == [('LabelBase', 9)]
    verdicts.append(pisa and recuperable)
    print(f'   Django PISA            : {pisa}   (el del padre sobrevive en su base: {recuperable})')

    print('\n== el veredicto ==')
    print(f'   el stack admite el orden de la fuente : {all(verdicts)}')
    print(f'   mediciones que discriminan            : {sum(verdicts)} de {len(verdicts)}')
    print('\n   Metrica: donde aterriza cada campo (`local_fields`,')
    print('            `private_fields`, estado de migracion) al construir')
    print('            modelos reales, con un control llano en cada caso.')
    print('   Ciega a: si el descriptor resultante COMPUTA lo correcto —solo')
    print('            mide el registro, no la lectura— y al orden en que')
    print('            `contribute_to_class` ve la MRO cuando la base no es')
    print('            abstracta de Django sino un mixin llano de Python.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
