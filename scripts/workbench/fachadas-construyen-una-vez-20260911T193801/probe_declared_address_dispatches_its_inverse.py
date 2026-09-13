"""Sonda O de TASK-API-0412 — los cuatro caminos de escritura, por CONTENIDO.

Las sondas F..N midieron el campo declarado **en el proceso**. Ésta lo mide
declarado **en el árbol**: ``ResCompany.country`` es ahora un ``Many2one`` con
``compute='_compute_address'`` e ``inverse='_inverse_country'``, la forma que
``odoo19c: addons/base/models/res_company.py:69-79`` fija.

Se mide por contenido y no por presencia (el veredicto se mide por contenido,
no por presencia):

1. ``ResCompany.objects.create(country=mx)`` — el camino del manager.
2. ``company.write({'country': mx})`` — el camino de ``RecordLoaderMixin``.
3. ``company.country = mx; company.save()`` — la asignación directa.
4. leer y volver a guardar — **no** debe despachar nada.

En los tres primeros el criterio no es el contador sino la COLUMNA del partner
releída de la base: un contador a 1 con el partner sin país sería el inverso
corriendo y no llegando, que es el defecto que
``probe_related_write_reaches_the_target`` ya midió con ``related=``. El
contador se publica al lado porque discrimina el otro fallo — el inverso
despachado DOS veces, que es lo que el alcance de protección de ``write``
existe para impedir.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.test.utils import setup_test_environment  # noqa: E402
from django.test.runner import DiscoverRunner  # noqa: E402

setup_test_environment()
runner = DiscoverRunner(verbosity=0, interactive=False, keepdb=True)
old_config = runner.setup_databases()

from addons.base.models.res_company import ResCompany  # noqa: E402
from addons.base.models.res_country import ResCountry  # noqa: E402
from addons.base.models.res_partner import ResPartner  # noqa: E402

dispatches = []
_real_inverse = ResCompany._inverse_country


def _counting_inverse(self):
    dispatches.append(self.pk)
    return _real_inverse(self)


ResCompany._inverse_country = _counting_inverse


def reread_partner_country(company):
    """El país de la COLUMNA del partner, releído de la base."""
    partner = ResPartner.objects.get(pk=company.partner_id)
    return partner.country_id


def report(label, expected_dispatches, company, expected_country):
    got = len(dispatches)
    stored = reread_partner_country(company)
    ok = (got == expected_dispatches
          and stored == (expected_country.pk if expected_country else None))
    print(f'{label}: despachos={got} (esperado {expected_dispatches}) | '
          f'partner.country_id={stored} '
          f'(esperado {expected_country.pk if expected_country else None}) '
          f'-> {"ACIERTA" if ok else "FALLA"}')
    dispatches.clear()
    return ok


try:
    mx, _ = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'Mexico'})
    ar, _ = ResCountry.objects.get_or_create(code='AR', defaults={'name': 'Argentina'})
    veredictos = []

    # 1 — el camino del manager
    dispatches.clear()
    c1 = ResCompany.objects.create(name='Sonda O uno', country=mx)
    veredictos.append(report('create(country=mx)', 1, c1, mx))

    # 2 — el camino de write()
    c2 = ResCompany.objects.create(name='Sonda O dos')
    dispatches.clear()
    c2.write({'country': mx})
    veredictos.append(report("write({'country': mx})", 1, c2, mx))

    # 3 — la asignación directa
    c3 = ResCompany.objects.create(name='Sonda O tres')
    dispatches.clear()
    c3.country = ar
    c3.save()
    veredictos.append(report('country = ar; save()', 1, c3, ar))

    # 4 — leer y guardar: el compute NO es una escritura de negocio
    c4 = ResCompany.objects.get(pk=c2.pk)
    dispatches.clear()
    leido = c4.country
    c4.save()
    veredictos.append(report(f'leer ({leido}) y save()', 0, c4, mx))

    print()
    print(f'veredicto: {sum(veredictos)} de {len(veredictos)} aciertan')
finally:
    runner.teardown_databases(old_config)
