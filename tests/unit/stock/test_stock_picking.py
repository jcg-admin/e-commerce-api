"""Contrato de ``stock.picking`` — segundo y tercer pase de la tarea **#330**
(tercero: **#521**, grupos C/E de :ref:`h-api-685`).

Fiel a ``odoo19c: addons/stock/models/stock_picking.py:538-2149``
(``odoo-tools@622ddc2a``, LGPL-3). Cada caso cita la línea de la referencia
que fija la regla. Cubre el bloque portado en el segundo pase — ciclo de vida
(``create``/``write``/``unlink``), campos estructurales, sus computados de
sólo lectura, y las dos funciones de categorización de fecha — y el bloque
del tercer pase: estado reactivo/UI (``_compute_state``,
``_onchange_picking_type``, ``_onchange_location_id``,
``action_detailed_operations``, ``action_next_transfer``,
``get_empty_list_help``, ``action_toggle_is_locked``) y mensajería
(``_add_reference``, ``_remove_reference``, ``_get_impacted_pickings``,
``_log_activity_get_documents``, ``_log_activity``,
``_log_less_quantities_than_expected``, ``_send_confirmation_email``). El
resto (paquetes, backorder-wizard, la máquina de reservas de
``_action_done``) queda declarado BLOQUEADO — ver :ref:`h-api-685` y
:ref:`h-api-692`.
"""
from decimal import Decimal

import pytest
from orm.environments import sudo
from django.utils import timezone

from addons.base.models import IrSequence, ResCompany, ResPartner, ResUsers
from addons.mail.models import MailActivity, MailMessage, MailTemplate
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockPicking,
    StockPickingType,
    StockReference,
)
from exceptions import UserError

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _elevated():
    """``create`` comprueba ``check_access('create')`` como la fuente
    (:ref:`h-api-1108`); sin usuario en contexto la ACL deniega, así que el
    módulo corre elevado — el mismo ``sudo()`` que
    ``tests/integration/base/test_ir_model_access_check.py`` ya usa."""
    with sudo():
        yield


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex', code='kaupamex_test_685')


@pytest.fixture
def source(db):
    return StockLocation.objects.create(name='Stock', usage='internal')


@pytest.fixture
def destination(db):
    return StockLocation.objects.create(name='Customers', usage='customer')


@pytest.fixture
def inventory_loss(db):
    return StockLocation.objects.create(name='Scrap', usage='inventory')


@pytest.fixture
def variant(db):
    tmpl = ProductTemplate.objects.create(name='Camisa', list_price=Decimal('100.00'))
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='CAM-685')


@pytest.fixture
def picking_type(db, company):
    return StockPickingType.objects.create(
        name='Entrega', code='outgoing', sequence_code='OUT', company=company)


def _move(picking, variant, source, destination, company, **extra):
    values = dict(
        picking=picking, product=variant, location=source,
        location_dest=destination, company=company,
        product_uom=variant.product_tmpl.uom, product_uom_qty=Decimal('5'))
    values.update(extra)
    return StockMove.objects.create(**values)


# -- campos estructurales (note/priority/date_done/owner/backorder/return_of) --

def test_priority_defaults_to_normal(picking_type, company):
    """``:592-594`` — ``priority`` reusa ``PROCUREMENT_PRIORITIES``; default '0'."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert picking.priority == '0'


def test_priority_urgent_orders_before_normal(picking_type, company):
    """``_order = "priority desc, ..."`` (``:542``) — ``Meta.ordering`` refleja
    ``-priority`` tras este pase (ver docstring de la clase)."""
    normal = StockPicking.objects.create(
        picking_type=picking_type, company=company, priority='0')
    urgente = StockPicking.objects.create(
        picking_type=picking_type, company=company, priority='1')
    primero = StockPicking.objects.filter(
        pk__in=[normal.pk, urgente.pk]).first()
    assert primero.pk == urgente.pk


def test_backorder_and_return_of_are_self_referencing(picking_type, company):
    """``:560-568`` — ``backorder_id``/``return_id`` apuntan a otro ``stock.picking``.

    D-9: sólo la relación estructural — el reverso ``backorder_ids`` sale de
    ``related_name``, no de un ``One2many`` explícito.
    """
    original = StockPicking.objects.create(picking_type=picking_type, company=company)
    dividido = StockPicking.objects.create(
        picking_type=picking_type, company=company, backorder=original)
    assert dividido.backorder_id == original.pk
    assert list(original.backorder_ids.all()) == [dividido]

    return_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, return_of=original)
    assert list(original.return_ids.all()) == [return_picking]


def test_owner_field_accepts_a_partner(picking_type, company):
    """``:649-651`` — ``owner_id``: al validar, los productos se asignan a él."""
    duena = ResPartner.objects.create(name='Depositante')
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, owner=duena)
    assert picking.owner_id == duena.pk


# -- computados de sólo lectura (D-6) ----------------------------------------

def test_return_count_reflects_the_reverse_relation(picking_type, company):
    """``:569`` — ``return_count`` / ``_compute_return_count`` (``:1007-1009``)."""
    original = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert original.return_count == 0
    StockPicking.objects.create(
        picking_type=picking_type, company=company, return_of=original)
    StockPicking.objects.create(
        picking_type=picking_type, company=company, return_of=original)
    assert original.return_count == 2


def test_has_tracking_true_when_any_move_product_is_tracked(
        picking_type, company, source, destination):
    """``:680`` / ``_compute_has_tracking`` (``:715-717``)."""
    tmpl = ProductTemplate.objects.create(
        name='Serie', list_price=Decimal('10'), tracking='serial')
    serializado = ProductProduct.objects.create(
        product_tmpl=tmpl, default_code='SER-685')
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert picking.has_tracking is False
    _move(picking, serializado, source, destination, company)
    assert picking.has_tracking is True


def test_has_scrap_move_true_when_dest_is_inventory_loss(
        picking_type, company, source, variant, inventory_loss):
    """``:618-619`` / ``_has_scrap_move`` (``:933-940``) — destino ``usage='inventory'``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert picking.has_scrap_move is False
    _move(picking, variant, source, inventory_loss, company)
    assert picking.has_scrap_move is True


def test_date_deadline_direct_takes_the_earliest_open_move(
        picking_type, company, source, destination, variant):
    """``:917-923`` — envío ``direct``: el límite es el más temprano."""
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, move_type='direct')
    temprano = timezone.now() + timezone.timedelta(days=1)
    tardio = timezone.now() + timezone.timedelta(days=5)
    _move(picking, variant, source, destination, company, date_deadline=tardio)
    _move(picking, variant, source, destination, company, date_deadline=temprano)
    assert picking.date_deadline == temprano


def test_date_deadline_one_takes_the_latest_open_move(
        picking_type, company, source, destination, variant):
    """``:917-923`` — envío ``one`` (todo junto): el límite es el más tardío."""
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, move_type='one')
    temprano = timezone.now() + timezone.timedelta(days=1)
    tardio = timezone.now() + timezone.timedelta(days=5)
    _move(picking, variant, source, destination, company, date_deadline=temprano)
    _move(picking, variant, source, destination, company, date_deadline=tardio)
    assert picking.date_deadline == tardio


def test_delay_alert_date_is_the_max_among_moves(
        picking_type, company, source, destination, variant):
    """``:607`` / ``_compute_delay_alert_date`` (``:737-742``)."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    temprano = timezone.now() + timezone.timedelta(hours=1)
    tardio = timezone.now() + timezone.timedelta(hours=5)
    _move(picking, variant, source, destination, company, delay_alert_date=temprano)
    _move(picking, variant, source, destination, company, delay_alert_date=tardio)
    assert picking.delay_alert_date == tardio


def test_get_next_transfers_excludes_returns(
        picking_type, company, source, destination, variant):
    """``:1024-1026`` — los que reciben lo que este produce, sin las devoluciones."""
    origen = StockPicking.objects.create(picking_type=picking_type, company=company)
    siguiente = StockPicking.objects.create(picking_type=picking_type, company=company)
    return_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, return_of=origen)

    salida = _move(origen, variant, source, destination, company)
    entrada_siguiente = _move(siguiente, variant, source, destination, company)
    return_move = _move(return_picking, variant, source, destination, company)
    # ``salida`` es el ORIGEN de las dos — se añaden por el lado reverso
    # (``move_dest_ids``) para que ``entrada_siguiente``/``return_move``
    # aparezcan como su destino, no al revés.
    salida.move_dest_ids.add(entrada_siguiente)
    salida.move_dest_ids.add(return_move)

    siguientes = set(origen._get_next_transfers().values_list('pk', flat=True))
    assert siguientes == {siguiente.pk}
    assert origen.show_next_pickings is True


def test_picking_type_passthrough_properties(picking_type, company):
    """``:625-630``/``:678`` — ``related`` de ``picking_type_id``, aquí properties."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert picking.picking_type_code == 'outgoing'
    assert picking.picking_type_entire_packs == picking_type.show_entire_packs
    assert picking.use_create_lots == picking_type.use_create_lots
    assert picking.use_existing_lots == picking_type.use_existing_lots
    assert picking.show_operations == picking_type.show_operations


def test_picking_type_passthrough_properties_without_type(company):
    """Sin ``picking_type`` (nulable, D-6 del primer pase) las properties no revientan."""
    picking = StockPicking.objects.create(company=company)
    assert picking.picking_type_code is None
    assert picking.picking_type_entire_packs is False
    assert picking.warehouse_address is None


def test_product_and_lot_take_the_first_move(
        picking_type, company, source, destination, variant):
    """``:675-676`` — ``related='move_ids.product_id'``; aquí, el primer movimiento."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert picking.product is None
    _move(picking, variant, source, destination, company)
    assert picking.product == variant


def test_picking_warning_text_concatenates_partner_and_parent(
        picking_type, company):
    """``:705-708`` / ``_compute_picking_warning_text`` (``:1002-1011``)."""
    matriz = ResPartner.objects.create(name='Matriz', picking_warn_msg='Cuidado matriz')
    hijo = ResPartner.objects.create(
        name='Hijo', parent=matriz, picking_warn_msg='Cuidado hijo')
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, partner=hijo)
    texto = picking.picking_warning_text
    assert 'Cuidado hijo' in texto
    assert 'Cuidado matriz' in texto


def test_picking_warning_text_empty_without_partner(picking_type, company):
    """Sin contacto, el aviso es cadena vacía — no ``None`` ni excepción."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert picking.picking_warning_text == ''


# -- calculate_date_category / date_category_to_domain (D-7) ----------------

def test_calculate_date_category_empty_string_without_date():
    """``:1799-1836`` — sin fecha, devuelve cadena vacía."""
    assert StockPicking.calculate_date_category(None) == ''


def test_calculate_date_category_today():
    """``:1799-1836`` — ``today`` para el instante actual."""
    assert StockPicking.calculate_date_category(timezone.now()) == 'today'


def test_calculate_date_category_before_and_after():
    """``:1799-1836`` — límites ``before``/``after`` a una semana de distancia."""
    lejos_pasado = timezone.now() - timezone.timedelta(days=10)
    lejos_futuro = timezone.now() + timezone.timedelta(days=10)
    assert StockPicking.calculate_date_category(lejos_pasado) == 'before'
    assert StockPicking.calculate_date_category(lejos_futuro) == 'after'


def test_calculate_date_category_tomorrow_and_day_after(picking_type, company):
    """``:1799-1836`` — ``day_1``/``day_2``, y su consumidor real:
    ``StockPickingType.kanban_dashboard_graph`` (``odoo19c: :370-392``), que
    llamaba a este método cuando aún no existía (H-API-685)."""
    manana = timezone.now() + timezone.timedelta(days=1)
    pasado_manana = timezone.now() + timezone.timedelta(days=2)
    assert StockPicking.calculate_date_category(manana) == 'day_1'
    assert StockPicking.calculate_date_category(pasado_manana) == 'day_2'


def test_date_category_to_domain_filters_matching_picking(
        picking_type, company, source, destination, variant):
    """``:1842-1885`` — el dict resultante filtra por el rango de la categoría."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    dominio_hoy = StockPicking.date_category_to_domain('created_at', 'today')
    assert StockPicking.objects.filter(pk=picking.pk, **dominio_hoy).exists()

    dominio_pasado = StockPicking.date_category_to_domain('created_at', 'before')
    assert not StockPicking.objects.filter(pk=picking.pk, **dominio_pasado).exists()


def test_date_category_to_domain_unknown_category_returns_none():
    """``:1842-1885`` — categoría inválida devuelve ``None`` (Odoo: mismo dict.get)."""
    assert StockPicking.date_category_to_domain('created_at', 'nunca') is None


# -- create (D-8) --------------------------------------------------------------

def test_create_assigns_name_from_picking_type_sequence(company):
    """``:1117-1139`` — sin nombre y con secuencia, el nombre sale de ella."""
    sequence = IrSequence.objects.create(
        name='OUT', code='seq_out_685', prefix='OUT/', padding=5, company=company)
    tipo = StockPickingType.objects.create(
        name='Entrega', code='outgoing', sequence_code='OUT',
        company=company, sequence_id=sequence)
    picking, = StockPicking.create([{'picking_type': tipo, 'company': company}])
    assert picking.name == 'OUT/00001'


def test_create_leaves_name_blank_without_sequence(picking_type, company):
    """``:1117-1139`` — sin secuencia en el tipo, el nombre queda vacío (D-8:
    la red de seguridad es ``action_confirm``, no ``create``)."""
    picking, = StockPicking.create([{'picking_type': picking_type, 'company': company}])
    assert picking.name in ('', None)


def test_create_respects_an_explicit_name(company):
    """``:1121`` — con nombre explícito (no ``/``), no se toca."""
    sequence = IrSequence.objects.create(
        name='OUT2', code='seq_out2_685', prefix='OUT2/', padding=5, company=company)
    tipo = StockPickingType.objects.create(
        name='Entrega 2', code='outgoing', sequence_code='OUT2',
        company=company, sequence_id=sequence)
    picking, = StockPicking.create([
        {'picking_type': tipo, 'company': company, 'name': 'MANUAL-001'}])
    assert picking.name == 'MANUAL-001'


# -- write (D-8) ----------------------------------------------------------------

def test_write_forbids_changing_picking_type_once_done(picking_type, company):
    """``:1139-1141`` — cambiar el tipo de un albarán ``done``/``cancel`` revienta."""
    otro_tipo = StockPickingType.objects.create(
        name='Interno', code='internal', sequence_code='INT', company=company)
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, state='done')
    with pytest.raises(UserError):
        picking.write({'picking_type': otro_tipo})


def test_write_renumbers_and_relocates_on_type_change(company):
    """``:1141-1148`` — nuevo tipo: renumera y aplica sus dos ubicaciones."""
    seq_a = IrSequence.objects.create(
        name='A', code='seq_a_685', prefix='A/', padding=3, company=company)
    seq_b = IrSequence.objects.create(
        name='B', code='seq_b_685', prefix='B/', padding=3, company=company)
    origen_a = StockLocation.objects.create(name='OrigenA', usage='internal')
    destino_a = StockLocation.objects.create(name='DestinoA', usage='customer')
    origen_b = StockLocation.objects.create(name='OrigenB', usage='internal')
    destino_b = StockLocation.objects.create(name='DestinoB', usage='customer')
    tipo_a = StockPickingType.objects.create(
        name='TipoA', code='outgoing', sequence_code='A', company=company,
        sequence_id=seq_a, default_location_src=origen_a,
        default_location_dest=destino_a)
    tipo_b = StockPickingType.objects.create(
        name='TipoB', code='outgoing', sequence_code='B', company=company,
        sequence_id=seq_b, default_location_src=origen_b,
        default_location_dest=destino_b)

    picking, = StockPicking.create([{'picking_type': tipo_a, 'company': company}])
    assert picking.name == 'A/001'

    picking.write({'picking_type': tipo_b})
    picking.refresh_from_db()
    assert picking.name == 'B/001'
    assert picking.location_id == origen_b.pk
    assert picking.location_dest_id == destino_b.pk


def test_write_propagates_date_done_to_finished_moves(
        picking_type, company, source, destination, variant):
    """``:1155-1157`` — ``date_done`` se propaga a los movimientos ya hechos."""
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, state='done')
    hecho = _move(picking, variant, source, destination, company, state='done')
    pendiente = _move(picking, variant, source, destination, company, state='confirmed')

    when = timezone.now()
    picking.write({'date_done': when})

    hecho.refresh_from_db()
    pendiente.refresh_from_db()
    assert hecho.date == when
    assert pendiente.date != when


def test_write_propagates_location_change_excluding_inventory_dest(
        picking_type, company, source, destination, inventory_loss, variant):
    """``:1163-1168`` — un cambio de ubicación no toca los movimientos cuyo
    destino ya es una pérdida de inventario (scrap)."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    normal = _move(picking, variant, source, destination, company)
    scrap = _move(picking, variant, source, inventory_loss, company)

    nueva_origen = StockLocation.objects.create(name='NuevoOrigen', usage='internal')
    picking.write({'location': nueva_origen})

    normal.refresh_from_db()
    scrap.refresh_from_db()
    assert normal.location_id == nueva_origen.pk
    assert scrap.location_id == source.pk


# -- unlink (D: guarda de estado) ------------------------------------------

def test_unlink_cancels_and_deletes_open_moves(
        picking_type, company, source, destination, variant):
    """``:1170-1175`` — cancela antes de borrar; ``StockMove.unlink`` exige
    ``draft``/``cancel``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    move = _move(picking, variant, source, destination, company, state='confirmed')
    move_pk = move.pk
    picking_pk = picking.pk

    picking.delete()

    assert not StockMove.objects.filter(pk=move_pk).exists()
    assert not StockPicking.objects.filter(pk=picking_pk).exists()


def test_unlink_allows_a_done_move_without_a_chain(
        picking_type, company, source, destination, variant):
    """``stock_move.py:1458-1466`` — un movimiento ``done`` **sin cadena**
    sí se borra: la guarda sólo bloquea cuando además está encadenado."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    hecho = _move(picking, variant, source, destination, company, state='done')
    move_pk = hecho.pk

    picking.delete()

    assert not StockMove.objects.filter(pk=move_pk).exists()


def test_unlink_refuses_when_a_done_move_is_chained(
        picking_type, company, source, destination, variant):
    """``stock_move.py:1458-1466`` (≙ ``odoo19c: :2333-2335``) — un
    movimiento ``done`` **encadenado** (``move_orig_ids``/``move_dest_ids``)
    no se borra: borrarlo dejaría la cadena rota."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    anterior = _move(picking, variant, source, destination, company, state='done')
    siguiente = _move(picking, variant, source, destination, company, state='confirmed')
    siguiente.move_orig_ids.add(anterior)

    with pytest.raises(UserError):
        picking.delete()


# -- tarea #521 — Grupo E: estado reactivo / UI ----------------------------

def test_compute_state_draft_when_any_move_is_draft(
        picking_type, company, source, destination, variant):
    """``odoo19c: :843-844`` — cualquier movimiento ``draft`` fuerza el
    albarán entero a ``draft``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    _move(picking, variant, source, destination, company, state='confirmed')
    _move(picking, variant, source, destination, company, state='draft')

    assert picking._compute_state() == StockPicking.STATE_DRAFT
    picking.refresh_from_db()
    assert picking.state == StockPicking.STATE_DRAFT


def test_compute_state_cancel_when_all_moves_cancel(
        picking_type, company, source, destination, variant):
    """``odoo19c: :845-846``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    _move(picking, variant, source, destination, company, state='cancel')
    _move(picking, variant, source, destination, company, state='cancel')

    assert picking._compute_state() == StockPicking.STATE_CANCEL


def test_compute_state_done_when_all_moves_done_and_not_scrapped(
        picking_type, company, source, destination, variant):
    """``odoo19c: :847-853`` — ``done``+``cancel`` con destino que NO es
    merma → ``done``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    _move(picking, variant, source, destination, company, state='done')
    _move(picking, variant, source, destination, company, state='cancel')

    assert picking._compute_state() == StockPicking.STATE_DONE


def test_compute_state_cancel_when_done_moves_are_all_scrapped(
        picking_type, company, source, inventory_loss, variant):
    """``odoo19c: :849-853`` — todo lo ``done`` es merma y hay un
    ``cancel`` no-merma → el conjunto se lee como ``cancel``, no ``done``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    other_dest = StockLocation.objects.create(name='Customers2', usage='customer')
    _move(picking, variant, source, inventory_loss, company, state='done')
    _move(picking, variant, source, other_dest, company, state='cancel')

    assert picking._compute_state() == StockPicking.STATE_CANCEL


def test_compute_state_assigned_via_bypass_reservation(
        picking_type, company, destination, variant):
    """``odoo19c: :857-858`` — origen que ``should_bypass_reservation()`` +
    todos los movimientos ``make_to_stock`` → ``assigned`` directo."""
    supplier = StockLocation.objects.create(name='Suppliers', usage='supplier')
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, location=supplier,
        location_dest=destination)
    _move(picking, variant, supplier, destination, company,
          state='confirmed', procure_method='make_to_stock')

    assert picking._compute_state() == StockPicking.STATE_ASSIGNED


def test_compute_state_falls_back_to_relevant_move_state(
        picking_type, company, source, destination, variant):
    """``odoo19c: :859-864`` — sin bypass, delega en
    ``StockMove._get_relevant_state_among_moves``; un único movimiento
    ``assigned`` con cantidad hace que el albarán quede ``assigned``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    _move(picking, variant, source, destination, company, state='assigned')

    assert picking._compute_state() == StockPicking.STATE_ASSIGNED


def test_onchange_picking_type_realigns_draft_moves(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1093-1099`` — sólo en ``draft`` propaga ptype y empresa a
    los movimientos existentes."""
    other_type = StockPickingType.objects.create(
        name='Recepción', code='incoming', sequence_code='IN', company=company)
    picking = StockPicking.objects.create(
        picking_type=other_type, company=company, state=StockPicking.STATE_DRAFT)
    move = _move(picking, variant, source, destination, company, state='draft')

    picking.picking_type = picking_type
    picking._onchange_picking_type()

    move.refresh_from_db()
    assert move.picking_type_id == picking_type.pk


def test_onchange_picking_type_noop_when_not_draft(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1094`` — fuera de ``draft`` no toca los movimientos."""
    other_type = StockPickingType.objects.create(
        name='Recepción 2', code='incoming', sequence_code='IN2', company=company)
    picking = StockPicking.objects.create(
        picking_type=other_type, company=company, state=StockPicking.STATE_ASSIGNED)
    # El tipo se fija a mano a propósito: en la referencia lo pondría
    # ``StockMove._compute_picking_type_id`` (``odoo19c: stock_move.py:299-302``,
    # ``compute=`` con ``store=True``), que aquí NO está portado —
    # ``picking_type`` es una FK plana y nace en ``None``. Sin este valor
    # explícito el test mediría esa ausencia, no la ausencia de propagación
    # que su nombre declara. Sucesor: tarea **#527**.
    move = _move(picking, variant, source, destination, company,
                 state='assigned', picking_type=other_type)

    picking.picking_type = picking_type
    picking._onchange_picking_type()

    move.refresh_from_db()
    assert move.picking_type_id == other_type.pk


def test_onchange_location_id_propagates_to_moves(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1102``."""
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, location=source,
        location_dest=destination)
    move = _move(picking, variant, source, destination, company, state='confirmed')
    new_source = StockLocation.objects.create(name='NuevaOrigen521', usage='internal')

    picking.location = new_source
    result = picking._onchange_location_id()

    move.refresh_from_db()
    assert move.location_id == new_source.pk
    assert result is None


def test_onchange_location_id_warns_when_chained_reservation_breaks(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1104-1113`` — un movimiento encadenado con línea
    reservada fuera del nuevo árbol produce el dict de aviso."""
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, location=source,
        location_dest=destination)
    origin_move = _move(picking, variant, source, destination, company, state='done')
    chained = _move(picking, variant, source, destination, company, state='confirmed')
    chained.move_orig_ids.add(origin_move)
    other_branch = StockLocation.objects.create(name='OtraRama521', usage='internal')
    chained.move_line_ids.create(
        picking=picking, product=variant, location=other_branch,
        location_dest=destination, company=company,
        product_uom=variant.product_tmpl.uom, quantity=Decimal('1'))

    picking.location = StockLocation.objects.create(
        name='DistintaRama521', usage='internal')
    result = picking._onchange_location_id()

    assert result is not None
    assert 'warning' in result


def test_action_detailed_operations_returns_navigation_dict(
        picking_type, company, source, destination):
    """``odoo19c: :1217-1236`` — descriptor de acción con dominio y
    contexto por el albarán."""
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, location=source,
        location_dest=destination)

    action = picking.action_detailed_operations()

    assert action['res_model'] == 'stock.move.line'
    assert action['domain'] == [('picking', '=', picking.pk)]
    assert action['context']['default_picking'] == picking.pk
    assert action['context']['picking_code'] == 'outgoing'


def test_action_next_transfer_single_result(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1240-1247`` — un único siguiente → acción de formulario."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    move = _move(picking, variant, source, destination, company, state='confirmed')
    siguiente_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company)
    siguiente_move = _move(
        siguiente_picking, variant, destination, source, company, state='confirmed')
    move.move_dest_ids.add(siguiente_move)

    action = picking.action_next_transfer()

    assert action['views'] == [[False, 'form']]
    assert action['res_id'] == siguiente_picking.pk


def test_action_next_transfer_multiple_results(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1248-1255`` — más de uno → acción de lista."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    move = _move(picking, variant, source, destination, company, state='confirmed')
    for label in ('A521', 'B521'):
        siguiente_picking = StockPicking.objects.create(
            picking_type=picking_type, company=company, name=label)
        siguiente_move = _move(
            siguiente_picking, variant, destination, source, company,
            state='confirmed')
        move.move_dest_ids.add(siguiente_move)

    action = picking.action_next_transfer()

    assert action['views'] == [[False, 'list'], [False, 'form']]
    assert len(action['domain'][0][2]) == 2


@pytest.mark.parametrize('code,snippet', [
    ('incoming', 'recepción'),
    ('outgoing', 'entrega'),
    ('internal', 'movimiento interno'),
])
def test_get_empty_list_help_by_picking_type_code(
        company, code, snippet):
    """``odoo19c: :1079-1084`` — divergencia declarada: texto plano por
    ``picking_type_code``, sin motor QWeb."""
    ptype = StockPickingType.objects.create(
        name='Tipo %s' % code, code=code, sequence_code=code.upper(), company=company)
    picking = StockPicking.objects.create(picking_type=ptype, company=company)

    assert snippet in picking.get_empty_list_help().lower()


def test_get_empty_list_help_respects_explicit_message(picking_type, company):
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    assert picking.get_empty_list_help('message explícito') == 'message explícito'


def test_action_toggle_is_locked_flips_the_flag(picking_type, company):
    """``odoo19c: :1529-1532``."""
    picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, is_locked=True)

    assert picking.action_toggle_is_locked() is True
    picking.refresh_from_db()
    assert picking.is_locked is False


# -- tarea #521 — Grupo C: mensajería (reference_obj + actividades) ----------

def test_add_reference_links_to_all_moves(
        picking_type, company, source, destination, variant):
    """``odoo19c: :2118-2121``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    move_a = _move(picking, variant, source, destination, company, state='confirmed')
    move_b = _move(picking, variant, source, destination, company, state='confirmed')
    reference_obj = StockReference.objects.create(name='SO521')

    picking._add_reference([reference_obj])

    assert reference_obj in list(move_a.reference_ids.all())
    assert reference_obj in list(move_b.reference_ids.all())


def test_remove_reference_unlinks_from_all_moves(
        picking_type, company, source, destination, variant):
    """``odoo19c: :2124-2127``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    move = _move(picking, variant, source, destination, company, state='confirmed')
    reference_obj = StockReference.objects.create(name='SO522')
    move.reference_ids.add(reference_obj)

    picking._remove_reference([reference_obj])

    assert reference_obj not in list(move.reference_ids.all())


def test_get_impacted_pickings_follows_move_dest_chain(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1738-1760`` — recorre ``move_dest_ids`` en cascada y
    devuelve los albaranes de cada movimiento visitado, directo e
    indirecto."""
    origin_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company)
    origin_move = _move(
        origin_picking, variant, source, destination, company, state='done')

    mid_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company)
    mid_move = _move(
        mid_picking, variant, destination, source, company, state='confirmed')
    origin_move.move_dest_ids.add(mid_move)

    final_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company)
    final_move = _move(
        final_picking, variant, source, destination, company, state='confirmed')
    mid_move.move_dest_ids.add(final_move)

    impactados = origin_picking._get_impacted_pickings([origin_move])

    ids = set(impactados.values_list('pk', flat=True))
    assert ids == {origin_picking.pk, mid_picking.pk, final_picking.pk}


def test_log_activity_schedules_one_activity_per_document(
        picking_type, company):
    """``odoo19c: :1675-1701``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    partner = ResPartner.objects.create(name='Responsable521')
    responsible = ResUsers.objects.create(
        partner=partner, login='responsable521@test', password='x')
    documents = {(picking, responsible): {'x': 1}}

    picking._log_activity(lambda ctx: 'nota de prueba 521', documents)

    activity = MailActivity.objects.filter(
        res_model='stock.picking', res_id=picking.pk).first()
    assert activity is not None
    assert activity.note == 'nota de prueba 521'
    assert activity.user_id == responsible.pk


def test_log_activity_skips_a_pair_without_a_responsible(picking_type, company):
    """Divergencia declarada: ``mail.activity.user`` es ``NOT NULL`` y este
    stack no cae a un usuario de sesión implícito — el par se omite en vez
    de reventar con ``IntegrityError``."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)
    documents = {(picking, None): {'x': 1}}

    picking._log_activity(lambda ctx: 'nota de prueba 521', documents)

    assert not MailActivity.objects.filter(
        res_model='stock.picking', res_id=picking.pk).exists()


def test_log_less_quantities_than_expected_posts_activity_with_note(
        picking_type, company, source, destination, variant):
    """``odoo19c: :1703-1735`` — divergencia declarada: nota en texto plano,
    sin plantilla QWeb."""
    orig_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company)
    orig_move = _move(
        orig_picking, variant, source, destination, company, state='confirmed',
        product_uom_qty=Decimal('10'))

    partner = ResPartner.objects.create(name='Responsable522')
    responsible = ResUsers.objects.create(
        partner=partner, login='responsable522@test', password='x')
    dest_picking = StockPicking.objects.create(
        picking_type=picking_type, company=company, user=responsible)
    dest_move = _move(
        dest_picking, variant, destination, source, company, state='confirmed')
    orig_move.move_dest_ids.add(dest_move)

    orig_picking._log_less_quantities_than_expected(
        {orig_move: (Decimal('4'), Decimal('10'))})

    activity = MailActivity.objects.filter(
        res_model='stock.picking', res_id=dest_picking.pk).first()
    assert activity is not None
    assert '4' in activity.note and '10' in activity.note


def test_send_confirmation_email_posts_when_enabled_and_outgoing(
        picking_type, company):
    """``odoo19c: :1283-1291``."""
    company.stock_move_email_validation = True
    template = MailTemplate.objects.create(
        name='Confirmación 521', subject='Tu pedido salió',
        body_html='<p>Gracias por tu compra.</p>')
    company.stock_mail_confirmation_template = template
    company.save(update_fields=[
        'stock_move_email_validation', 'stock_mail_confirmation_template',
        'updated_at'])
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)

    picking._send_confirmation_email()

    message = MailMessage.objects.filter(
        model='stock.picking', res_id=picking.pk).first()
    assert message is not None
    assert message.subject == 'Tu pedido salió'


def test_send_confirmation_email_noop_when_disabled(picking_type, company):
    """``odoo19c: :1284`` — sin ``stock_move_email_validation`` no publica."""
    picking = StockPicking.objects.create(picking_type=picking_type, company=company)

    picking._send_confirmation_email()

    assert not MailMessage.objects.filter(
        model='stock.picking', res_id=picking.pk).exists()
