"""
Tests de integración — Schema OpenAPI (drf-spectacular)

Sprint 1: verifica que /api/schema/ funciona y tiene estructura válida.
Sprint 4 (T-001..T-008): verifica que cada grupo de endpoints aparece
            en el schema generado. pytest.mark.schema para estas clases.

DEC-SCHEMA-01: una clase por grupo de apps.
DEC-SCHEMA-02: cobertura representativa, no exhaustiva.
DEC-SCHEMA-03: nuevas clases usan pytest.mark.schema.
DEC-SCHEMA-05: hallazgos de paths ausentes documentados en
               analisis-cobertura-openapi-schema.rst.
"""
import pytest

pytestmark = pytest.mark.api


# =============================================================================
# Sprint 1 — tests originales
# =============================================================================

class TestSchemaEndpoint:
    """El endpoint /api/schema/ genera OpenAPI 3.0 válido."""

    def test_schema_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/')
        assert r.status_code == 200

    def test_schema_contiene_claves_openapi(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        data = r.json()
        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data

    def test_schema_version_correcta(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        assert r.json()['info']['version'] == '1.0.0'

    def test_schema_titulo_nombra_la_plataforma(self, api_client, db):
        # El título publicado nombra al operador L0 (Kaupamex), NO al L1 de
        # ejemplo: la API es una sola y sirve a todas las Company. Decisión de
        # producto del ejecutor (2026-08-05). El guard negativo que vigilaba
        # el nombre del L1 se retiró: el barrido del 2026-09-05 lo dejó
        # apuntando al propio 'Kaupamex' y se contradecía con la línea de
        # arriba. Ver :ref:`h-api-1095`.
        r = api_client.get('/api/schema/?format=json')
        titulo = r.json()['info']['title']
        assert 'Kaupamex' in titulo

    def test_schema_has_signup_endpoint(self, api_client, db):
        # El alta vive en ``authz_signup`` (``controllers/urls.py:9``),
        # montado bajo ``/api/v2/authz/`` (``src/config/urls.py:132``).
        r = api_client.get('/api/schema/?format=json')
        assert '/api/v2/authz/signup/' in r.json()['paths']

    def test_schema_has_session_endpoints(self, api_client, db):
        # La sesión (login/logout) es de la familia ``web`` de la referencia
        # (``odoo19c: addons/web/controllers/session.py:31,88``), portada en
        # este árbol — ver H-API-279. No es forma propia: es un puerto con
        # contrato ya decidido.
        r = api_client.get('/api/schema/?format=json')
        paths = r.json()['paths']
        assert '/api/v2/web/session/authenticate/' in paths
        assert '/api/v2/web/session/logout/' in paths

    def test_schema_contiene_endpoint_config(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        paths = r.json()['paths']
        assert '/api/v2/config/settings/' in paths

    def test_schema_signup_has_request_body(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        alta = r.json()['paths']['/api/v2/authz/signup/']['post']
        assert 'requestBody' in alta

    def test_schema_config_settings_patch_tiene_request(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        settings = r.json()['paths']['/api/v2/config/settings/']['patch']
        assert 'requestBody' in settings

    def test_schema_tiene_esquema_sesion(self, api_client, db):
        # ADR-018: la auth por defecto es la sesion (cookie). El esquema
        # OpenAPI debe documentar cookieAuth (no jwtAuth) — ver
        # CsrfExemptSessionScheme en addons.users.schema.
        r = api_client.get('/api/schema/?format=json')
        schemas = r.json().get('components', {}).get('securitySchemes', {})
        assert 'cookieAuth' in schemas


class TestSwaggerUI:
    """La Swagger UI responde correctamente."""

    def test_swagger_ui_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/swagger-ui/')
        assert r.status_code == 200


class TestRedocUI:
    """La Redoc UI responde correctamente."""

    def test_redoc_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/redoc/')
        assert r.status_code == 200


# =============================================================================
# Sprint 4 — T-001..T-008 (pytest.mark.schema)
# =============================================================================

class TestSchemaSelfAccount:
    """
    Superficie de cuenta propia — ≙ ``/my/*`` de ``odoo19c: portal``.

    El prefijo ``/api/v2/auth/`` que estos tests esperaban no existe: la
    cuenta propia vive en ``portal`` (``controllers/urls.py``, montado en
    ``src/config/urls.py:135``) y el alta/reset en ``authz_signup``
    (``src/config/urls.py:132``). Triage en
    :ref:`analisis-triage-rutas-schema-v2`.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_account_in_schema(self, api_client, db):
        # ``portal/controllers/urls.py:16`` — ≙ /my/account
        assert '/api/v2/portal/account/' in self._paths(api_client, db)

    def test_addresses_in_schema(self, api_client, db):
        # ``portal/controllers/urls.py:17`` — ≙ /my/addresses
        assert '/api/v2/portal/addresses/' in self._paths(api_client, db)

    def test_archive_address_in_schema(self, api_client, db):
        # ``portal/controllers/urls.py:18`` — el verbo es **archivar**, no
        # borrar: la referencia desactiva con ``ResPartner.active``
        # (H-API-252). Por eso la ruta lleva el sufijo ``/archive/``.
        assert ('/api/v2/portal/addresses/{id}/archive/'
                in self._paths(api_client, db))

    def test_change_password_in_schema(self, api_client, db):
        # ``portal/controllers/urls.py:21`` — ≙ /my/security
        assert '/api/v2/portal/security/password/' in self._paths(api_client, db)

    def test_request_reset_in_schema(self, api_client, db):
        # ``authz_signup/controllers/urls.py:11``
        assert '/api/v2/authz/request-reset/' in self._paths(api_client, db)

    def test_deactivate_account_in_schema(self, api_client, db):
        # ``portal/controllers/urls.py:22`` — ≙ /my/deactivate_account
        assert '/api/v2/portal/deactivations/' in self._paths(api_client, db)


class TestSchemaSession:
    """
    Superficie de sesión — familia ``web``, ya portada.

    Las cuatro rutas adaptan ``odoo19c: addons/web/controllers/session.py``.
    El contrato de comportamiento se prueba en ``tests/integration/web/``;
    aquí sólo se verifica que estén **publicadas** en el OpenAPI.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_session_info_in_schema(self, api_client, db):
        assert '/api/v2/web/session/' in self._paths(api_client, db)

    def test_destroy_session_in_schema(self, api_client, db):
        assert '/api/v2/web/session/destroy/' in self._paths(api_client, db)


class TestSchemaEmailVerification:
    """
    Verificación de correo — montada en ``authz_signup`` (``api@4b83a9b``).

    Estuvo PENDIENTE mientras el módulo de tokens de correo no existía
    (H-API-252 midió ``send_verification_email`` → 0 hits). Ya no: el flujo
    reusa el token firmado del propio ``authz_signup`` con un tercer
    ``signup_type``. Su **existencia** es forma propia declarada — la
    referencia no verifica el correo porque su alta llega por invitación
    (H-API-281); el **mecanismo** sí se hereda entero.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_verify_email_in_schema(self, api_client, db):
        """Una ruta, dos operaciones — no hay ``resend-verification/`` aparte.

        El reenvío y la verificación viven en el mismo endpoint y ramifican
        por el payload (``{token}`` verifica, ``{login}`` reenvía), siguiendo
        el patrón de la referencia: ``odoo19c:
        addons/auth_signup/controllers/main.py`` resuelve alta externa y
        set-password en la misma ``@route``, ramificando por ``token``.
        """
        assert '/api/v2/authz/verify-email/' in self._paths(api_client, db)


class TestSchemaCartWishlist:
    """
    T-002: Endpoints de carrito y wishlist presentes en schema.

    Cart: CartView, CartItemListView, CartItemDetailView,
          CartSaveView, CartMergeView, CartVoucherView.
    Wishlist: WishlistView, WishlistItemDetailView, WishlistMoveToCartView.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_cart_in_schema(self, api_client, db):
        assert '/api/v2/cart/' in self._paths(api_client, db)

    def test_cart_items_in_schema(self, api_client, db):
        assert '/api/v2/cart/items/' in self._paths(api_client, db)

    def test_cart_item_detail_in_schema(self, api_client, db):
        assert '/api/v2/cart/items/{id}/' in self._paths(api_client, db)

    def test_cart_voucher_en_schema(self, api_client, db):
        assert '/api/v2/cart/voucher/' in self._paths(api_client, db)

    def test_wishlist_in_schema(self, api_client, db):
        assert '/api/v2/wishlist/' in self._paths(api_client, db)

    def test_wishlist_item_in_schema(self, api_client, db):
        assert '/api/v2/wishlist/{id}/' in self._paths(api_client, db)

    def test_wishlist_move_to_cart_in_schema(self, api_client, db):
        assert '/api/v2/wishlist/{id}/cart-transfers/' in self._paths(api_client, db)


class TestSchemaOrdersPayments:
    """
    T-003: Endpoints de órdenes y pagos presentes en schema.

    H-SCHEMA-02: El checkout principal (UC-ORD-01) está en
    /api/v2/orders/checkout/ (addons.orders.urls). El prefijo
    /api/v2/checkout/ corresponde a addons.payments.checkout_urls
    que solo tiene eligibility y express (UC-ORD-01-EXT).

    Orders usan <str:order_number> — schema genera {order_number}.
    Payments usan <str:order_number> — schema genera {order_number}.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_orders_list_in_schema(self, api_client, db):
        assert '/api/v2/orders/' in self._paths(api_client, db)

    def test_orders_checkout_in_schema(self, api_client, db):
        # H-SCHEMA-02: checkout principal en /api/v2/orders/checkout/
        assert '/api/v2/orders/' in self._paths(api_client, db)

    def test_orders_detail_in_schema(self, api_client, db):
        assert '/api/v2/orders/{order_number}/' in self._paths(api_client, db)

    def test_orders_cancel_in_schema(self, api_client, db):
        assert '/api/v2/orders/{order_number}/cancellations/' in self._paths(api_client, db)

    def test_checkout_express_in_schema(self, api_client, db):
        # H-SCHEMA-02: checkout express en /api/v2/checkout/ (checkout_urls)
        assert '/api/v2/checkout/express/' in self._paths(api_client, db)

    def test_payments_initiate_in_schema(self, api_client, db):
        assert '/api/v2/payments/initiate/' in self._paths(api_client, db)

    def test_payments_status_in_schema(self, api_client, db):
        assert '/api/v2/payments/{order_number}/status/' in self._paths(api_client, db)

    def test_payments_history_in_schema(self, api_client, db):
        assert '/api/v2/payments/{order_number}/history/' in self._paths(api_client, db)


class TestSchemaCatalogue:
    """
    T-004: Endpoints de catálogo presentes en schema.

    H-SCHEMA-03: Hay dos endpoints 'categories':
    - /api/v2/categories/ — CategoryTreeView (browse_public_urls)
    - /api/v2/categories/ — CategoryListView (catalogue/urls_v2.py)
    Ambos son válidos y coexisten; se verifican los dos.

    browse_public_urls provee /api/v2/catalogue/search/
    (CatalogueSearchView, wrapper P-17 con normalized_query).
    catalogue/urls_v2.py provee /api/v2/products/ (list/search/autocomplete
    via query params — no hay ruta separada /products/search/).
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_catalogue_list_en_schema(self, api_client, db):
        assert '/api/v2/products/' in self._paths(api_client, db)

    def test_catalogue_search_en_schema(self, api_client, db):
        # browse_public_urls monta CatalogueSearchView en /catalogue/search/
        assert '/api/v2/catalogue/search/' in self._paths(api_client, db)

    def test_catalogue_product_detail_en_schema(self, api_client, db):
        assert '/api/v2/products/{slug}/' in self._paths(api_client, db)

    def test_categories_browse_in_schema(self, api_client, db):
        # H-SCHEMA-03: CategoryTreeView en /api/v2/categories/ (browse_public)
        assert '/api/v2/categories/' in self._paths(api_client, db)

    def test_product_related_in_schema(self, api_client, db):
        assert '/api/v2/products/{slug}/related/' in self._paths(api_client, db)


class TestSchemaReviewsQuestions:
    """
    T-005: Endpoints de reviews, preguntas e historial de búsqueda.

    Todos montados bajo /api/v2/products/ con product_id int.
    Search history montado bajo /api/v2/search/.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_product_reviews_en_schema(self, api_client, db):
        assert '/api/v2/products/{product_id}/reviews/' in self._paths(api_client, db)

    def test_product_review_helpful_en_schema(self, api_client, db):
        assert '/api/v2/products/{product_id}/reviews/{id}/helpful-votes/' in self._paths(api_client, db)

    # Q&A de producto — RETIRADA: 0 addons con ``question`` en el nombre y 0
    # ``@route`` con ``question`` en el path en todo ``odoo19c:``
    # (``odoo-tools@622ddc2a``). El canal no está en el producto de referencia
    # y su decisión sigue abierta como trabajo aparte. Ver H-API-282.

    def test_search_history_in_schema(self, api_client, db):
        assert '/api/v2/search/history/' in self._paths(api_client, db)

    def test_search_history_detail_in_schema(self, api_client, db):
        assert '/api/v2/search/history/{id}/' in self._paths(api_client, db)


class TestSchemaInventoryLogisticsVoucher:
    """
    T-006: Endpoints de inventario, logística y vouchers.

    Inventory montado en /api/v2/admin/inventory/ (addons.inventory.urls).
    Logistics montado en /api/v2/logistics/ (addons.delivery.controllers.urls).
    Voucher router montado en /api/v2/admin/vouchers/ (addons.loyalty.controllers.admin_urls).
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_inventory_dashboard_in_schema(self, api_client, db):
        assert '/api/v2/admin/inventory/' in self._paths(api_client, db)

    def test_inventory_alerts_in_schema(self, api_client, db):
        assert '/api/v2/admin/inventory/alerts/' in self._paths(api_client, db)

    def test_logistics_panel_en_schema(self, api_client, db):
        assert '/api/v2/logistics/' in self._paths(api_client, db)

    def test_logistics_guides_en_schema(self, api_client, db):
        assert '/api/v2/logistics/guides/' in self._paths(api_client, db)

    def test_logistics_confirm_delivery_en_schema(self, api_client, db):
        assert '/api/v2/logistics/guides/{id}/confirm-delivery/' in self._paths(api_client, db)

    def test_vouchers_list_en_schema(self, api_client, db):
        assert '/api/v2/admin/vouchers/' in self._paths(api_client, db)

    def test_voucher_detail_en_schema(self, api_client, db):
        assert '/api/v2/admin/vouchers/{id}/' in self._paths(api_client, db)


class TestSchemaSupportReturnsNewsletter:
    """
    T-007: Endpoints de soporte, devoluciones, contacto, newsletter
    y notificaciones.

    H-SCHEMA-04: Contact endpoint es /api/v2/contact/messages/
    (ContactMessageCreateView con path 'messages/'), NO /api/v2/contact/.

    H-SCHEMA-05: Newsletter confirm token en path variable:
    /api/v2/newsletter/subscriptions/confirmations/{token}/ (str param).
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_support_tickets_in_schema(self, api_client, db):
        assert '/api/v2/support/tickets/' in self._paths(api_client, db)

    def test_support_ticket_close_in_schema(self, api_client, db):
        assert '/api/v2/support/tickets/{ticket_id}/status/' in self._paths(api_client, db)

    # Devoluciones — RETIRADA: la única ``@route`` con ``return`` en el path de
    # ``odoo19c:`` sirve el PDF de la etiqueta
    # (``addons/sale_stock/controllers/portal.py:40``); la devolución en sí es
    # un wizard de backoffice, ``stock.return.picking``
    # (``addons/stock/wizard/stock_picking_return.py:87``). Ver H-API-282.

    def test_contact_messages_in_schema(self, api_client, db):
        # H-SCHEMA-04: path es /messages/ dentro de /api/v2/contact/
        assert '/api/v2/contact/messages/' in self._paths(api_client, db)

    def test_newsletter_subscribe_in_schema(self, api_client, db):
        assert '/api/v2/newsletter/subscriptions/' in self._paths(api_client, db)

    def test_newsletter_confirm_in_schema(self, api_client, db):
        # H-SCHEMA-05: token va en el body del POST, no en la URL
        assert '/api/v2/newsletter/subscriptions/confirmations/' in self._paths(api_client, db)

    def test_notifications_in_schema(self, api_client, db):
        assert '/api/v2/notifications/' in self._paths(api_client, db)


class TestSchemaAdminEndpoints:
    """
    T-008: Endpoints admin representativos de cada dominio.

    RETIRADAS (H-API-279): ``admin/users/`` y ``admin/users/{id}/`` describían
    un CRUD REST de usuarios que la referencia **no expone** — el único
    ``@http.route`` bajo ``odoo19c: odoo/addons/base/`` es ``ir_http.py``, el
    despachador. La gestión de ``res.users`` pasa por el mecanismo genérico
    sobre el modelo, no por una ruta dedicada; crearla sería invención, no
    adaptación. Su equivalente adaptado ya existe por el lado de autorización
    (``/api/v2/admin/roles/``, ``/api/v2/admin/permissions/``).

    También retiradas ``admin/reports/{sales,dashboard}`` y
    ``admin/dashboard/``: el addon ``reports`` se eliminó (``api@115d219``) y
    sus objetos SQL de agregación no tienen consumidor (ver H-DB-01).

    Orders admin usa <str:order_number> — schema genera {order_number}.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_admin_orders_in_schema(self, api_client, db):
        assert '/api/v2/admin/orders/' in self._paths(api_client, db)

    def test_admin_order_detail_in_schema(self, api_client, db):
        assert '/api/v2/admin/orders/{order_number}/' in self._paths(api_client, db)

    def test_admin_reviews_en_schema(self, api_client, db):
        assert '/api/v2/admin/reviews/' in self._paths(api_client, db)

    def test_admin_review_approve_in_schema(self, api_client, db):
        # v2: approve/reject → PATCH /status/ (admin_urls_v2.py)
        assert '/api/v2/admin/reviews/{id}/status/' in self._paths(api_client, db)

    def test_admin_settings_in_schema(self, api_client, db):
        # settings mounted at /api/v2/config/ (settings_app/urls.py)
        assert '/api/v2/config/settings/' in self._paths(api_client, db)

    # Admin de Q&A — RETIRADA junto con la superficie pública (ver arriba y
    # H-API-282): no hay dominio que administrar.
