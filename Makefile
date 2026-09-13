# Makefile — api targets de mantenimiento / CI.
#
# Targets para ejecucion local y en pipelines de CI futuros.
# Mantiene paridad con ui/package.json scripts equivalentes.
.PHONY: check-symbol-home check-symbol-home-ci help check-names check-names-ci check-layout check-layout-ci check-lazy check-lazy-ci check-cycles check-cycles-ci check-catalog check-catalog-ci check-canon check-canon-ci test test-coverage install-hooks db-up ci-test ci-test-fast pdf check-pdf clean-pdf

help:
	@echo 'Targets:'
	@echo '  make check-names       Nombre de addon contra odoo-tools (H-API-119)'
	@echo '  make check-names-ci    Idem, exit != 0 tambien con deuda heredada'
	@echo '  make check-layout      Capas estructurales en paquete (H-API-238)'
	@echo '  make check-layout-ci   Idem, exit != 0 tambien con deuda heredada'
	@echo '  make check-porte       Simbolos de cada puerto vs odoo19c (surfacing)'
	@echo '  make porte-mapa        Inventario por archivo: COMPLETO/PARCIAL/NO PORTADO'
	@echo '  make check-porte-ci    Idem, exit != 0 si hay porte incompleto'
	@echo '  make check-lazy        Audit AST: 0 lazy imports en apps/** y tests/**'
	@echo '  make check-lazy-ci     Idem, exit code != 0 si hay violaciones'
	@echo '  make check-catalog     Coherencia de los authz_catalog.py (SOL-100)'
	@echo '  make check-catalog-ci  Idem, exit code != 0 si hay incoherencias'
	@echo '  make check-cycles      Direccion de dependencias: 0 inversiones nuevas'
	@echo '  make check-cycles-ci   Idem, exit code != 0 si hay inversiones nuevas'
	@echo '  make check-symbol-home Lado del arbol de cada simbolo vs la referencia'
	@echo '  make check-addon-root  Un addon vive en UNA sola raiz de ADDONS_PATHS'
	@echo '  make check-chain-depends  chain_method declara al dueno del simbolo'
	@echo '  make check-canon       Canon-idioma: 0 identifiers ES en apps/** (soft)'
	@echo '  make check-canon-ci    Idem, exit code != 0 si hay violaciones'
	@echo '  make test              Pytest suite completa'
	@echo '  make test-coverage     Pytest con coverage'
	@echo '  make install-hooks     Activar .githooks/ via core.hooksPath'
	@echo '  make db-up             Arranca PostgreSQL via el script de db (socket)'
	@echo '  make ci-test           db-up + pytest suite completa (--reuse-db)'
	@echo '  make ci-test-fast      db-up + subset de humo sale/ (--reuse-db)'
	@echo '  make serve             Servidor de aplicacion embebido (ADR-027)'
	@echo '  make check-serve       Gate: valida gunicorn.conf.py y que la app importe'
	@echo '  make pdf               Compila los helpers PDF (libharu vendorizada; ADR-017)'
	@echo '  make check-pdf         Gate: los helpers PDF compilan (salida a build/)'
	@echo '  make clean-pdf         Borra binarios y objetos de los helpers PDF'

# Audit local — imprime hallazgos pero no falla (para inspeccion manual).
check-names:
	python3 scripts/check_addon_names.py

check-names-ci:
	python3 scripts/check_addon_names.py --strict

check-layout:
	python3 scripts/check_addon_layout.py

check-layout-ci:
	python3 scripts/check_addon_layout.py --strict

# Cobertura de simbolos del puerto contra la referencia. Surfacing: al dia 1
# hay 181 grupos incompletos en 149 pares de archivo (deuda heredada), asi que
# bloquear el push por eso seria bloquear por deuda ajena — mismo criterio que
# DEC-AM-01. Graduar a -ci en pre-push cuando el conteo baje.
check-porte:
	python3 scripts/check_porte_completo.py || true

# El lado del arbol donde vive cada simbolo (H-API-556). A diferencia de
# check-porte, este SI arranca en 0 fuera de sitio, asi que su variante -ci
# ya esta cableada al pre-commit como gate 9: no hay deuda ajena que
# bloquee a nadie.
check-symbol-home:
	python3 scripts/check_symbol_home.py

check-symbol-home-ci:
	python3 scripts/check_symbol_home.py --strict

check-porte-ci:
	python3 scripts/check_porte_completo.py --strict

porte-mapa:
	python3 scripts/check_porte_completo.py --mapa

check-lazy:
	python3 scripts/check_no_lazy_imports.py || true

# Audit estricto — para CI. Exit != 0 dispara fallo en pipeline.
check-lazy-ci:
	python3 scripts/check_no_lazy_imports.py

# Silencios de excepción justificados (AC uc-sys-06) — soft / CI.
check-silent:
	python3 scripts/check_silent_oks.py || true

check-silent-ci:
	python3 scripts/check_silent_oks.py

# Reparto de raices: un addon vive en UNA sola raiz de ADDONS_PATHS.
check-addon-root:
	@python3 scripts/check_addon_root.py

check-addon-root-ci:
	@python3 scripts/check_addon_root.py --strict

# chain_method: el dueno del simbolo encadenado esta en el depends (H-API-564).
check-chain-depends:
	@python3 scripts/check_chain_method_depends.py

check-chain-depends-ci:
	@python3 scripts/check_chain_method_depends.py --strict

# Canon-idioma soft — imprime hallazgos pero retorna exit 0.
check-cycles:
	@python3 scripts/check_addon_cycles.py --report

check-cycles-ci:
	@python3 scripts/check_addon_cycles.py

# Declaracion del catalogo L0 (SOL-100) — coherencia estatica de los
# authz_catalog.py: addon instalado, sin duenos duplicados, sin capacidades
# huerfanas, sin aristas depends colgantes.
check-catalog:
	@python3 scripts/check_catalog_declaration.py --report

check-catalog-ci:
	@python3 scripts/check_catalog_declaration.py

check-canon:
	python3 $$(ls -d ../kaupamex-docs ../docs 2>/dev/null | head -1)/scripts/check_canon_language.py --repo-root .. --soft

# Canon-idioma estricto — exit != 0 si hay literales ES fuera del allowlist.
check-canon-ci:
	python3 $$(ls -d ../kaupamex-docs ../docs 2>/dev/null | head -1)/scripts/check_canon_language.py --repo-root ..

test:
	pytest

test-coverage:
	pytest --cov=src --cov-report=term-missing

install-hooks:
	bash scripts/install-hooks.sh

# --- Coordinacion CI/CD: db + api ---------------------------------------

# Arranca PostgreSQL (idempotente) via el script del submodulo db
# (ADR-028 — MariaDB retirado; start_db.sh ya no sirve a ningun entorno).
# DB_DIR permite override; fallback a ../kaupamex-db y luego a la ruta
# absoluta conocida del contenedor.
db-up:
	@DB_DIR="$${DB_DIR:-../kaupamex-db}"; \
	if [ ! -d "$$DB_DIR" ]; then DB_DIR=/home/user/kaupamex-db; fi; \
	echo "db-up: usando DB_DIR=$$DB_DIR"; \
	bash "$$DB_DIR/scripts/start_postgres.sh"

# Suite completa contra PostgreSQL real (--reuse-db: no recrea schema).
ci-test: db-up
	uv run pytest --reuse-db -q

# Subset rapido de humo (sale/) — smoke test de CI. El addon cart se
# retiro; el carrito vive en sale (H-API-310), tests/integration/cart/
# ya no existe.
ci-test-fast: db-up
	uv run pytest tests/integration/sale/ -q --reuse-db

# Servidor de aplicacion embebido (ADR-027). Prefork sincrono, loopback.
# Sobrescribir con GUNICORN_BIND / GUNICORN_WORKERS; ver setup/gunicorn.conf.py.
serve:
	uv run gunicorn -c setup/gunicorn.conf.py

# Gate de configuracion del servidor: valida el archivo y que la app importe.
check-serve:
	DJANGO_SETTINGS_MODULE=config.settings.testing \
	  uv run gunicorn -c setup/gunicorn.conf.py --check-config

# Helpers PDF nativos (ADR-017). libharu va vendorizada en
# src/tools/pdf/vendor/libharu, asi que un clon limpio compila sin buscar nada
# fuera del arbol: no hace falta libhpdf-dev ni CMake, solo gcc/make y las
# cabeceras de zlib/libpng (paquetes de `main`).
#
# Los binarios NO se versionan (son especificos de arquitectura y ABI): un .a
# compilado en otra maquina puede enlazar y comportarse mal, que es peor que
# no estar. Por eso este target existe — el deploy lo ejecuta.
pdf:
	$(MAKE) -C src/tools/pdf build

# Gate de compilacion: exit != 0 si alguno de los dos helpers no compila.
# Deja los binarios de prueba en src/tools/pdf/build/, nunca en /tmp.
check-pdf:
	$(MAKE) -C src/tools/pdf check

clean-pdf:
	$(MAKE) -C src/tools/pdf distclean
