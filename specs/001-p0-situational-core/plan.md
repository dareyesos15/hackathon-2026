# Implementation Plan: Núcleo situacional P0 de Dacora

**Branch**: `001-p0-situational-core` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-p0-situational-core/spec.md`

## Summary

Rebanada vertical P0 de Dacora: ingesta multicanal (REST, SMS compacto, lote de la PWA) →
redacción de datos personales → clasificación por reglas/léxico colombiano → triaje →
agrupación espacio-tiempo-texto → trust score explicable, expuesta por una API REST de FastAPI y
consumida por un frontend Next.js puro (exportación estática) con tablero PMU en MapLibre, panel de
KPI y PWA ciudadana con outbox en IndexedDB. Todo corre con `docker compose up` sin internet. Un
escenario sintético determinista del sismo del 10 ago 2026 se reproduce contra la API y un
evaluador externo al motor publica los KPI contra la verdad del escenario.

Contexto del equipo (respuestas del 20 nov 2026): no hay código previo; el trabajo es serial e
iterativo con un solo responsable técnico; Docker Compose es obligatorio en la demo.

## Technical Context

**Language/Version**: Python 3.12 (imagen `python:3.12-slim`); TypeScript 5.x sobre Node 22 LTS.

**Primary Dependencies**:
- `api`: FastAPI, Uvicorn, Pydantic v2 + pydantic-settings, SQLAlchemy 2 (async) + asyncpg +
  GeoAlchemy2, Alembic, scikit-learn (TF-IDF), Shapely. Gestión con `uv`.
- `web`: Next.js (App Router, `output: "export"`), React, MapLibre GL JS, Tailwind CSS, Dexie.js,
  `openapi-typescript` + `openapi-fetch`. Servido por Nginx dentro del contenedor `web`.

**Storage**: PostgreSQL 16 + PostGIS 3.5 (imagen multi-arquitectura `imresamu/postgis:16-3.5`,
ver research R2). IndexedDB (Dexie) en el navegador para el outbox.

**Testing**: `pytest` + `pytest-asyncio` + `httpx` (API, motor, contrato); `vitest` (redacción TS,
outbox, formateadores); casos de redacción compartidos en `data/fixtures/pii_cases.json`;
`scripts/evaluate_kpis.py` como prueba de aceptación del KPI.

**Target Platform**: Docker Compose v2 en portátil macOS arm64 / Linux amd64 sin internet;
navegadores Chrome/Safari recientes (escritorio y móvil).

**Project Type**: Aplicación web: servicio `api` (REST) + servicio `web` (frontend estático/PWA).

**Performance Goals**: < 1 s de procesamiento por reporte (p95); < 5 s desde recepción hasta
verse en el tablero; reproducir 300 reportes en 12 min (por defecto) o en < 1 min (modo rápido)
sin pérdidas.

**Constraints**: offline total en tiempo de demo (imágenes construidas antes); arranque desde cero
< 5 min con imágenes ya construidas; cero datos personales en claro en la base; solo `api` accede
a la base; un único worker de Uvicorn (el bus de eventos es en memoria).

**Scale/Scope**: 1 escenario de 150–300 reportes, ~60–120 incidentes, ~400 manzanas sintéticas,
~40 lugares en el gazetteer, 3 roles activos en P0 (`ciudadano`, `operador_pmu`, `publico`),
3 pantallas principales (`/reportar`, `/pmu`, `/pmu/kpi`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo lo cumple el diseño | Estado |
|---|---|---|
| I. Habeas Data | Redacción en `web/lib/redact.ts` (borde) y `api/app/core/privacy.py` (autoridad) con casos compartidos; `reporter_hash` = HMAC-SHA256 con `PII_SALT` de `.env`; prueba automática sobre todo el escenario; aviso y consentimiento en `/reportar`; endpoint público solo agregado por manzana con k ≥ 5 | ✅ |
| II. Offline-first | Compose sin dependencias de nube; mapa base desde GeoJSON local; TF-IDF local (sin descargas en caliente); outbox Dexie + idempotencia por `client_uuid` (restricción única en BD) | ✅ |
| III. Humano decide | `is_life_threat` impide los estados `descartado`/`falso` automáticos (regla en motor + restricción en la máquina de estados); acciones solo por `PATCH` con rol `operador_pmu`; `report_events` solo-agregar | ✅ |
| IV. Datos sintéticos | Escenario determinista con semilla; `ground_truth.json` fuera del paquete del motor y nunca montado como entrada del motor; KPI de detección publicados por `evaluate_kpis.py` como instantáneas; etiqueta `SIMULADO` en `source` y en la UI | ✅ |
| V. Trazabilidad | Columnas `id`, `created_at`, `source`, `version`, `cutoff_at`; cada cifra de la UI renderizada con componente `<Cifra>` que exige fuente y corte; `docs/diccionario_indicadores.md` | ✅ |
| VI. Adaptadores | Interfaces `SimilarityProvider` (tfidf/minilm), `EventBus` (memoria), `HazardProvider` (neutro en P0), `SmsGateway` (simulado); integraciones reales = nueva implementación | ✅ |
| VII. Simplicidad | Sin Kafka/Redis/Celery; bus en memoria; exportación estática; reglas antes que modelos; un solo worker | ✅ |
| VIII. Español de Colombia | UI en es-CO con `Intl.NumberFormat('es-CO')` y zona `America/Bogota`; identificadores en inglés según glosario | ✅ |
| IX. Calidad | ruff + black + mypy (`privacy`, `nlp`, `dedup`, `trust`); eslint + prettier + TS strict; pruebas obligatorias de §14 mapeadas en quickstart | ✅ |
| X. Dos servicios REST | Servicios principales `api` y `web`; `web` es exportación estática (sin servidor Next.js, imposible tener Route Handlers); Nginx de `web` solo sirve estáticos y hace proxy inverso de `/api/` a `api` (sin lógica); tipos generados desde `/openapi.json`; SSE como única excepción | ✅ |
| Commits atómicos | Un commit por artefacto/tarea (ver tasks) | ✅ |

**Resultado**: pasa sin violaciones. Re-evaluación post-diseño al final de este documento.

## Project Structure

### Documentation (this feature)

```text
specs/001-p0-situational-core/
├── plan.md              # Este archivo
├── research.md          # Fase 0: decisiones técnicas
├── data-model.md        # Fase 1: entidades, validaciones, estados
├── quickstart.md        # Fase 1: guía de validación ejecutable
├── contracts/
│   ├── rest-api.md      # Endpoints REST /api/v1
│   ├── sms-format.md    # Gramática del SMS compacto
│   └── sse-events.md    # Eventos del stream en vivo
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
docker-compose.yml               # api, web (principales) + db (soporte)
.env.example                     # PII_SALT, tokens por rol, DB_URL, SIMILARITY_PROVIDER
README.md                        # demo en 1 comando
docs/
├── arquitectura.jpeg
├── diccionario_indicadores.md
└── guion_demo.md

services/api/
├── Dockerfile
├── pyproject.toml / uv.lock
├── alembic/                     # migraciones
├── app/
│   ├── main.py                  # FastAPI, routers, startup (seed geo)
│   ├── config.py                # pydantic-settings (umbrales, pesos, tokens)
│   ├── db.py                    # engine/sesión async
│   ├── models.py                # SQLAlchemy + GeoAlchemy2
│   ├── schemas.py               # Pydantic (contrato OpenAPI)
│   ├── auth.py                  # token fijo por rol
│   ├── routers/                 # ingest, reports, incidents, map, stream, metrics, geo
│   ├── core/                    # MOTOR (no importa metrics ni ground truth)
│   │   ├── privacy.py           # redacción + HMAC
│   │   ├── sms.py               # parser del formato compacto
│   │   ├── nlp.py               # categoría, gravedad, triaje, señales de desinformación
│   │   ├── geo.py               # gazetteer, manzana por punto, haversine
│   │   ├── similarity.py        # SimilarityProvider (tfidf | minilm)
│   │   ├── dedup.py             # agrupación en incidentes
│   │   ├── trust.py             # trust score + desglose
│   │   └── pipeline.py          # orquesta y mide < 1 s
│   ├── adapters/                # event_bus.py (memoria), hazard.py (neutro), sms_gateway.py
│   └── seed.py                  # carga manzanas + gazetteer al arrancar
└── tests/
    ├── unit/                    # privacy, sms, nlp, dedup, trust
    ├── contract/                # esquemas OpenAPI y códigos de respuesta
    └── integration/             # pipeline completo, idempotencia, PII sobre escenario

apps/web/
├── Dockerfile                   # build estático + nginx
├── nginx.conf                   # estáticos + proxy /api (SSE sin buffering)
├── next.config.ts               # output: "export"
├── app/
│   ├── page.tsx                 # inicio: elegir rol
│   ├── reportar/                # PWA ciudadana
│   └── pmu/                     # tablero + kpi/
├── components/                  # Mapa, MatrizTriaje, DetalleIncidente, Cifra, EtiquetaSimulado
├── lib/
│   ├── api/                     # schema.d.ts generado + cliente openapi-fetch
│   ├── db.ts                    # Dexie + outbox
│   ├── redact.ts                # espejo de privacy.py
│   ├── live.ts                  # SSE con fallback a polling
│   └── format.ts                # es-CO, America/Bogota
├── public/                      # manifest.json, sw.js, íconos
└── tests/                       # vitest

data/
├── geo/                         # manzanas.geojson, barrios.geojson, gazetteer.csv (SIMULADO)
├── seed/                        # scenario.jsonl (entrada), ground_truth.json (solo evaluador)
└── fixtures/pii_cases.json      # casos compartidos py/ts

scripts/                         # clientes de la API REST (se ejecutan dentro del contenedor api)
├── generate_geo.py
├── generate_scenario.py
├── replay_scenario.py
├── simulate_sms.py
└── evaluate_kpis.py
```

**Structure Decision**: aplicación web con dos servicios (`services/api`, `apps/web`) según
CLAUDE.md §5 y principio X. `scripts/` y `data/` se montan en el contenedor `api` para ejecutar
los scripts sin un tercer servicio; los scripts solo hablan con la API por HTTP.

## Complexity Tracking

Sin violaciones que justificar. Dos decisiones vigiladas:

| Decisión | Por qué | Alternativa más simple descartada |
|---|---|---|
| Nginx dentro del contenedor `web` | Servir la exportación estática y dar un solo origen (sin CORS) al celular en la LAN; SSE sin buffering | `next start`: reintroduce servidor Next.js (riesgo de lógica en servidor, contra principio X); servir desde FastAPI: mezcla servicios |
| Alembic | Esquema reproducible en `docker compose up` desde cero | `create_all()`: válido como respaldo, pero sin historial de cambios entre iteraciones |

## Re-evaluación de la Constitution Check (post-diseño)

Revisados [data-model.md](data-model.md) y [contracts/](contracts/):

- I: ningún campo del modelo guarda texto sin redactar; `reporter_hash` es el único derivado del
  remitente; `/api/v1/map/manzanas` agrega con k ≥ 5 para el rol `publico`. ✅
- III: la máquina de estados del data-model impide transiciones automáticas a `descartado` cuando
  `is_life_threat`; `PATCH` exige `operador_pmu`. ✅
- IV: `ground_truth.json` solo lo lee `evaluate_kpis.py`; la API recibe instantáneas por
  `POST /api/v1/metrics/snapshots` con `source = "evaluate_kpis.py"`. ✅
- X: todos los endpoints bajo `/api/v1`; `GET /api/v1/stream` es la única ruta no REST. ✅

**Resultado**: pasa. Listo para `/speckit-tasks`.
