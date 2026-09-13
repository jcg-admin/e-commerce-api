"""Sonda: ¿la escritura por ``related=`` alcanza al partner y PERSISTE?

Decide si los seis campos de dirección de ``ResCompany`` pueden declararse
``related='partner.<f>'`` en vez de resolverse con un par
``@property``/``@setter``, que es la forma que hoy tiene el puerto
(``odoo19c: base/models/res_company.py:69-80`` los declara como campos).

El control de anulación es el propio caso negativo que el docstring de
``_address_set`` registró: escribir, guardar, RELEER de la base. Si el valor
releído no coincide, la conversión regresa la persistencia y se revierte — que
es exactamente lo que midió esta sonda y por qué ``res_company.py`` conserva
las ``@property``.

El orden importa: la escritura se mide ANTES de ``ensure_field_setup()``,
porque con las ``@property`` restauradas la costura levanta ``KeyError`` al
resolver ``company_country_code`` — un eslabón que este puerto todavía no
declara. Medir primero deja la evidencia de persistencia aunque la costura
aborte.

La escritura ocurre dentro de una transacción que se deshace al terminar: la
sonda mide el viaje a la base sin dejar filas en ``kaupamex_core_qa``, que es
la base que ``--reuse-db`` conserva entre corridas.
"""
import django

django.setup()

from django.db import transaction  # noqa: E402

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_partner import ResPartner  # noqa: E402
from orm.fields import ensure_field_setup  # noqa: E402

#: Lo que se escribe. Dos campos bastan: el defecto es del mecanismo de
#: escritura, no de un campo concreto.
STREET = 'Calle de la sonda 42'
CITY = 'Ciudad de la sonda'


def write_reaches_the_target():
    """Escribe por el campo de dirección, guarda, y RELEE de la base.

    Devuelve el veredicto por campo. Un campo cuyo valor releído no coincide
    con el escrito NO puede declararse ``related=``: la proyección mentiría al
    escribir, que es el defecto que ``_address_set`` documentaba.
    """
    verdicts = {}
    with transaction.atomic():
        partner = ResPartner.objects.create(name='Probe partner')
        company = ResCompany.objects.create(name='Probe company',
                                            partner=partner)

        company.street = STREET
        company.city = CITY
        company.save()

        reread = ResCompany.objects.get(pk=company.pk)
        verdicts['street'] = (reread.street == STREET)
        verdicts['city'] = (reread.city == CITY)
        #: El control del hermano: ``partner.street`` es la columna real. Si
        #: la escritura fue a otro sitio, aquí se ve.
        verdicts['partner.street'] = (
            ResPartner.objects.get(pk=partner.pk).street == STREET)

        transaction.set_rollback(True)
    return verdicts


def declaration_report():
    """Lo que la declaración dejó en cada campo, antes de tocar la base."""
    for name in ('street', 'city', 'country', 'country_code'):
        field = next((f for f in ResCompany._meta.get_fields()
                      if f.name == name), None)
        if field is None:
            print(f'{name:13s} NO es campo del modelo (property o ausente)')
            continue
        print(f'{name:13s} related={getattr(field, "related", None)!s:26s} '
              f'store={getattr(field, "store", "?")!s:6s} '
              f'inverse={"SI" if getattr(field, "inverse", None) else "NO"}')


def main():
    verdicts = write_reaches_the_target()
    for name, ok in verdicts.items():
        print(f'write_reaches {name:16s} {"OK" if ok else "FALLA"}')
    print('VEREDICTO escritura_persiste: '
          f'{"OK" if all(verdicts.values()) else "FALLA"}')

    declaration_report()

    #: La costura se mide después y su fallo NO invalida lo de arriba: es el
    #: eslabón ausente que TASK-API-0412 y su sucesor documentan.
    try:
        ensure_field_setup()
        print('ensure_field_setup: OK')
    except KeyError as exc:
        print(f'ensure_field_setup: KeyError {exc}')


if __name__ == '__main__':
    main()
