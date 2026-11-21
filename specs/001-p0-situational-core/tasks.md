---

description: "Lista de tareas del núcleo situacional P0 de Dacora"
---

# Tasks: Núcleo situacional P0 de Dacora

**Input**: Design documents from `/specs/001-p0-situational-core/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluidas solo las que exige la constitución (principio IX y CLAUDE.md §14) y las de
los módulos críticos del motor (`privacy`, `sms`, `nlp`, `dedup`, `trust`). No es TDD completo.

**Organization**: por historia de usuario; cada fase deja un incremento demostrable.

**Commits**: según CLAUDE.md §0.1, **cada tarea termina en su propio commit** (Conventional
Commits en inglés) en cuanto queda verificada; push al cerrar cada fase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes). El equipo
  trabaja en serie; la marca sirve para reordenar si algo se bloquea.
- **[Story]**: historia de usuario de [spec.md](spec.md) (US1–US4).

## Path Conventions

- Backend: `services/api/app/`, pruebas en `services/api/tests/`
- Frontend: `apps/web/`
- Datos: `data/`; scripts (clientes REST que corren dentro del contenedor `api`): `scripts/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: esqueleto de los dos servicios y de Compose.

- [X] T001 Verificar `docker info` y crear `.gitignore` raíz (Python, Node, `.env`, `node_modules`, `.next`, `out`, `__pycache__`, `.venv`) en `.gitignore`
- [X] T002 Inicializar el proyecto Python con `uv` (Python 3.12; FastAPI, uvicorn, pydantic-settings, SQLAlchemy 2 async, asyncpg, GeoAlchemy2, Alembic, scikit-learn, shapely, httpx; dev: pytest, pytest-asyncio, ruff, black, mypy) en `services/api/pyproject.toml` y `services/api/uv.lock`
- [X] T003 [P] Inicializar Next.js + TypeScript strict + Tailwind + ESLint + Prettier + Vitest con `output: "export"` en `apps/web/package.json`, `apps/web/next.config.ts`, `apps/web/tsconfig.json`
- [X] T004 [P] Configurar ruff, black y mypy (estricto en `app/core`) en `services/api/pyproject.toml`
- [X] T005 Crear `services/api/Dockerfile` (python:3.12-slim + uv, monta `scripts/` y `data/`, healthcheck a `/api/v1/health`)
- [X] T006 [P] Crear `apps/web/Dockerfile` (build estático con Node 22 → nginx) y `apps/web/nginx.conf` (estáticos, fallback a `index.html` por ruta, proxy `/api/` → `api:8000` con `proxy_buffering off` y timeouts largos para SSE)
- [X] T007 Crear `docker-compose.yml` con `db` (`imresamu/postgis:16-3.5`, healthcheck, volumen), `api` (depende de db healthy; volúmenes `./data` y `./scripts` de solo lectura) y `web` (puerto 8080, depende de api), y `.env.example` con `PII_SALT`, `DATABASE_URL`, `SIMILARITY_PROVIDER=tfidf` y `TOKEN_*` por rol (research R9)

**Checkpoint**: `docker compose build` termina y `docker compose up` levanta los tres contenedores.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: configuración, esquema, auth, bus de eventos, geografía y cliente tipado.

**⚠️ CRITICAL**: ninguna historia empieza antes de terminar esta fase.

- [X] T008 Implementar configuración tipada (umbrales de agrupación de research R1, pesos del trust score CLAUDE.md §7.4, tokens por rol, `PII_SALT`) en `services/api/app/config.py`
- [X] T009 Implementar engine y sesión async de SQLAlchemy en `services/api/app/db.py`
- [X] T010 Definir enums y modelos ORM de `reports`, `report_events`, `incidents`, `manzanas`, `places`, `metrics_snapshots` con columnas comunes `id/created_at/source/version` en `services/api/app/models.py` — restricciones según data-model.md: `Report.client_uuid` (UNIQUE), `Report.channel`, `Report.category`, `Report.triage_level`, `Report.geo_precision`, `Report.status`, `Report.severity`, `Report.people_affected`, `Report.text_redacted`, `Report.reporter_hash`, `Report.geom`; `ReportEvent.report_id`/`ReportEvent.incident_id` (al menos uno), `ReportEvent.action`, `ReportEvent.actor_role`; `Incident.trust_score`, `Incident.trust_label`, `Incident.status`, `Incident.trust_breakdown`; `Manzana.id`; `Place.kind`, `Place.aliases`; `MetricSnapshot.unit`; índices de data-model.md (Report)
- [X] T011 Configurar Alembic y generar la migración inicial (extensión postgis, tablas, índices GIST) en `services/api/alembic/` y `services/api/alembic/versions/0001_initial.py`
- [X] T012 [P] Implementar autenticación por token fijo y dependencia `require_role(...)` (cabecera Bearer y `?token=` para SSE) en `services/api/app/auth.py`
- [X] T013 [P] Implementar `EventBus` en memoria (colas asyncio por suscriptor, ids incrementales, búfer de 500 eventos) en `services/api/app/adapters/event_bus.py`
- [X] T014 [P] Implementar `HazardProvider` neutro (consistencia física = 0,5, detalle "sin dato de sensor") en `services/api/app/adapters/hazard.py`
- [X] T015 [P] Escribir `scripts/generate_geo.py` y generar `data/geo/gazetteer.csv` (~40 barrios, vías y referencias de CLAUDE.md §7.2 con alias normalizados), `data/geo/barrios.geojson` y `data/geo/manzanas.geojson` (grilla ~150 m) etiquetados SIMULADO (research R7) — campos según data-model.md `Place.kind`, `Place.aliases`, `Manzana.id`
- [X] T016 Implementar la carga idempotente de manzanas y gazetteer al arrancar en `services/api/app/seed.py`
- [X] T017 Crear la app FastAPI con prefijo `/api/v1`, manejador de errores `{detail, code}` en español, `GET /api/v1/health` y startup (migraciones + seed) en `services/api/app/main.py`
- [X] T018 [P] Crear `scripts/export_openapi.py` (escribe `apps/web/lib/api/openapi.json`) y el script `gen:api` con `openapi-typescript` → `apps/web/lib/api/schema.d.ts` + cliente `openapi-fetch` en `apps/web/lib/api/client.ts` (research R11)
- [X] T019 [P] Implementar formateadores es-CO (números `1.449`, decimales con coma, hora `America/Bogota`) en `apps/web/lib/format.ts`
- [X] T020 [P] Crear componentes base `Cifra` (exige valor, fuente, versión y corte — principio V) y `EtiquetaSimulado` en `apps/web/components/Cifra.tsx` y `apps/web/components/EtiquetaSimulado.tsx`
- [X] T021 Crear layout raíz en español, página de inicio con selección de rol y token (guardado en `sessionStorage`) en `apps/web/app/layout.tsx`, `apps/web/app/page.tsx` y `apps/web/lib/session.ts`

**Checkpoint**: `docker compose up` desde cero crea el esquema, carga la geografía, `/api/v1/health` responde y `http://localhost:8080` muestra la pantalla de inicio.

---

## Phase 3: User Story 1 - Reportes verificados y agrupados automáticamente (Priority: P1) 🎯 MVP

**Goal**: redacción → clasificación → triaje → agrupación → trust score en < 1 s, por REST y SMS.

**Independent Test**: enviar los SMS del [quickstart](quickstart.md) §2 y §4 y un lote con datos
personales; verificar categoría, triaje, unión al incidente, desglose y ausencia de PII.

### Tests for User Story 1

- [X] T022 [P] [US1] Crear casos compartidos de redacción (celulares con y sin +57, cédulas, correos, placas, "me llamo/soy/mi mamá…", falsos positivos como "carrera 23" o "3 personas") en `data/fixtures/pii_cases.json`
- [X] T023 [P] [US1] Pruebas unitarias de redacción y HMAC contra `data/fixtures/pii_cases.json` en `services/api/tests/unit/test_privacy.py`
- [X] T024 [P] [US1] Pruebas unitarias del parser SMS con la tabla de ejemplos de [contracts/sms-format.md](contracts/sms-format.md) en `services/api/tests/unit/test_sms.py`
- [X] T025 [P] [US1] Pruebas unitarias de clasificación, triaje y señales de desinformación (ejemplos de spec US1 y research R6) en `services/api/tests/unit/test_nlp.py`
- [X] T026 [P] [US1] Pruebas unitarias de agrupación (mismo hecho por dos fuentes, mismo remitente repetido, categorías distintas en la misma cuadra, > 3 h) en `services/api/tests/unit/test_dedup.py`
- [X] T027 [P] [US1] Pruebas unitarias del trust score (etiquetas por rango, desinformación resta, desglose suma el total) en `services/api/tests/unit/test_trust.py`

### Implementation for User Story 1

- [X] T028 [P] [US1] Implementar redacción (`[TEL]`, `[CC]`, `[CORREO]`, `[PLACA]`, `[NOMBRE]`) y `reporter_hash` HMAC-SHA256 en `services/api/app/core/privacy.py` — data-model.md `Report.text_redacted`, `Report.location_text`, `Report.reporter_hash`
- [X] T029 [P] [US1] Implementar el parser del SMS compacto según [contracts/sms-format.md](contracts/sms-format.md) en `services/api/app/core/sms.py` — data-model.md `Report.client_uuid` (UUIDv5 para SMS), `Report.people_affected`, `Report.geo_precision`
- [X] T030 [P] [US1] Implementar normalización, léxico por categoría, matriz de triaje (CLAUDE.md §7.2), `severity` y señales de desinformación en `services/api/app/core/nlp.py` — data-model.md `Report.category`, `Report.severity`, `Report.triage_level`, `Report.is_life_threat`, `Report.misinfo_signals`
- [X] T031 [P] [US1] Implementar búsqueda en gazetteer, punto→manzana, validación del rectángulo de Manizales y haversine en `services/api/app/core/geo.py` — data-model.md `Report.geom`, `Report.geo_precision`, `Report.manzana_id`
- [X] T032 [P] [US1] Implementar `SimilarityProvider` con `tfidf` (char_wb 3–5) y `minilm` opcional perezoso en `services/api/app/core/similarity.py`
- [X] T033 [US1] Implementar agrupación (candidatos SQL con `ST_DWithin` y ventana de 3 h, categorías compatibles, umbral por precisión, bloqueo asesor por celda, completar datos del incidente, fuentes independientes) en `services/api/app/core/dedup.py` — data-model.md `Incident.centroid`, `Incident.independent_sources`, `Incident.people_affected`, `Incident.triage_level`, `Incident.is_life_threat`, `Report.incident_id` (depende de T031, T032)
- [X] T034 [US1] Implementar trust score con las 7 señales y el formato de desglose en `services/api/app/core/trust.py` — data-model.md `Incident.trust_score`, `Incident.trust_label`, `Incident.trust_breakdown` (depende de T014)
- [X] T035 [US1] Implementar el pipeline (redactar → clasificar → ubicar → agrupar → puntuar → registrar `ReportEvent` → publicar en `EventBus`, midiendo `processing_ms`) con la regla de que el sistema solo lleva a `en_revision` en `services/api/app/core/pipeline.py` — data-model.md `Report.status`, `Report.processing_ms`, `ReportEvent.action`
- [X] T036 [US1] Definir esquemas Pydantic `ReportIn`, `SmsIn`, `BatchIn`, `Report`, `IncidentSummary`, `IncidentDetail`, `ReportResult` según [contracts/rest-api.md](contracts/rest-api.md) en `services/api/app/schemas.py`
- [X] T037 [US1] Implementar `POST /ingest/report`, `POST /ingest/sms` y `POST /ingest/batch` con idempotencia (`201`/`200`) y consentimiento obligatorio en `pwa` en `services/api/app/routers/ingest.py` — data-model.md `Report.client_uuid`, `Report.channel`
- [X] T038 [US1] Implementar `GET /reports`, `GET /incidents` y `GET /incidents/{id}` (filtros, orden, cursor, `cutoff_at`) en `services/api/app/routers/reports.py` y `services/api/app/routers/incidents.py`
- [X] T039 [P] [US1] Crear `scripts/simulate_sms.py` (cliente REST de `/ingest/sms`, `--from`)
- [X] T040 [US1] Prueba de integración: idempotencia por `client_uuid` en report y batch, y procesamiento < 1 s p95 sobre 100 reportes en `services/api/tests/integration/test_ingest.py`
- [X] T041 [P] [US1] Prueba de aislamiento: `app/core` no importa `metrics` ni abre `ground_truth` en `services/api/tests/unit/test_core_isolation.py`
- [X] T042 [US1] Exportar OpenAPI y regenerar tipos del frontend (`scripts/export_openapi.py`, `apps/web/lib/api/schema.d.ts`) y añadir prueba de contrato que falla si están desalineados en `services/api/tests/contract/test_openapi_snapshot.py`

**Checkpoint**: quickstart §2, §3 (parte API) y §4 pasan solo con la API.

---

## Phase 4: User Story 2 - Tablero situacional del PMU con decisión humana (Priority: P2)

**Goal**: mapa, matriz de triaje, detalle explicable y acciones humanas con bitácora, en vivo.

**Independent Test**: quickstart §5 con incidentes creados por la historia 1.

### Implementation for User Story 2

- [X] T043 [US2] Implementar la máquina de estados (transiciones permitidas, `409 invalid_transition`, nota obligatoria al descartar riesgo vital, recálculo del incidente) en `services/api/app/core/review.py` — data-model.md `Report.status`, `Report.is_life_threat`, `Incident.status`, `ReportEvent.action`, `ReportEvent.actor_role`
- [X] T044 [US2] Implementar `PATCH /reports/{id}` y `PATCH /incidents/{id}` (solo `operador_pmu`, eventos por reporte, evento SSE `incident.status_changed`) en `services/api/app/routers/reports.py` y `services/api/app/routers/incidents.py`
- [X] T045 [P] [US2] Prueba de integración: el sistema nunca descarta un reporte de riesgo vital; descartar sin nota → 422; bitácora solo-agregar en `services/api/tests/integration/test_review.py`
- [X] T046 [US2] Implementar `GET /stream` (SSE, latido 15 s, `Last-Event-ID`) según [contracts/sse-events.md](contracts/sse-events.md) en `services/api/app/routers/stream.py`
- [X] T047 [P] [US2] Implementar `GET /map/manzanas` (agregado por manzana, k ≥ 5 para `publico`) y `GET /geo/barrios` en `services/api/app/routers/map.py`
- [X] T048 [US2] Regenerar OpenAPI y tipos del frontend tras T044–T047 en `apps/web/lib/api/schema.d.ts`
- [X] T049 [P] [US2] Implementar cliente en vivo (EventSource con token, reconexión, fallback a polling cada 3 s tras 2 fallos, estado "Modo de respaldo") en `apps/web/lib/live.ts`
- [X] T050 [P] [US2] Implementar el mapa MapLibre con fondo GeoJSON offline (barrios), capa de manzanas por concentración y círculos de incidentes (color por triaje, radio por `report_count`) en `apps/web/components/Mapa.tsx`
- [X] T051 [P] [US2] Implementar la matriz/lista de triaje con filtros de nivel, estado y categoría en `apps/web/components/MatrizTriaje.tsx`
- [X] T052 [P] [US2] Implementar el detalle de incidente (reportes redactados, desglose de las 7 señales, bitácora, botones Confirmar/Descartar/Marcar duplicado con nota obligatoria si es riesgo vital) en `apps/web/components/DetalleIncidente.tsx`
- [X] T053 [US2] Componer el tablero `/pmu` (mapa + matriz + detalle por `?incidente=`, cabecera con cifras `Cifra` y etiqueta SIMULADO) en `apps/web/app/pmu/page.tsx`

**Checkpoint**: quickstart §5 completo en el navegador.

---

## Phase 5: User Story 3 - Reproducción del sismo y KPI medidos en vivo (Priority: P3)

**Goal**: escenario sintético reproducible y KPI calculados contra la verdad, fuera del motor.

**Independent Test**: quickstart §6.

### Implementation for User Story 3

- [X] T054 [US3] Escribir `scripts/generate_scenario.py` (semilla fija; 150–300 reportes 07:34–19:34 del 10 ago 2026; ~55 % únicos, ~30 % duplicados multicanal, ~15 % falsos/rumores; concentración en Centro, Milán, Av. Santander, Av. Paralela, carrera 23; datos personales sintéticos en el texto para probar la redacción) y generar `data/seed/scenario.jsonl` y `data/seed/ground_truth.json` — formato de verdad según data-model.md (Verdad del escenario)
- [X] T055 [P] [US3] Escribir `docs/diccionario_indicadores.md` con los 9 indicadores P0 y sus definiciones (research R8)
- [X] T056 [US3] Implementar `POST /metrics/snapshots` (emite `kpi.updated`) y `GET /metrics/kpi` (última instantánea por indicador + indicadores operativos calculados por la API) en `services/api/app/routers/metrics.py` — data-model.md `MetricSnapshot.indicator`, `MetricSnapshot.unit`, `MetricSnapshot.cutoff_at`
- [X] T057 [US3] Escribir `scripts/evaluate_kpis.py` (lee `data/seed/ground_truth.json` y `GET /reports`/`GET /incidents`, calcula los KPI de research R8, imprime tabla y publica instantánea; código de salida ≠ 0 si no cumple metas)
- [X] T058 [US3] Escribir `scripts/replay_scenario.py` (`--speed` defecto 60, `--reset`, envía por el canal de cada reporte, llama a `evaluate_kpis` cada 25 reportes y al final)
- [X] T059 [US3] Prueba de integración: reproducir todo el escenario en modo rápido y verificar 0 coincidencias de PII en `reports.text_redacted`/`location_text` en `services/api/tests/integration/test_pii_scenario.py`
- [X] T060 [US3] Calibrar umbrales de similitud y léxico con `evaluate_kpis.py` hasta duplicados > 90 %, falsos > 90 %, recall de críticos ≥ 98 % y 0 críticos descartados; fijar valores en `services/api/app/config.py`
- [X] T061 [US3] Regenerar OpenAPI y tipos del frontend tras T056 en `apps/web/lib/api/schema.d.ts`
- [ ] T062 [US3] Implementar el panel de KPI `/pmu/kpi` (todas las cifras con `Cifra`, actualización por `kpi.updated`, "N reportes → M incidentes", "mapa consolidado en X min") en `apps/web/app/pmu/kpi/page.tsx`

**Checkpoint**: quickstart §6 con metas cumplidas y visibles en el panel.

---

## Phase 6: User Story 4 - Reporte ciudadano sin conexión (Priority: P4)

**Goal**: PWA con consentimiento, redacción en el borde, outbox y sincronización idempotente.

**Independent Test**: quickstart §7.

### Implementation for User Story 4

- [ ] T063 [P] [US4] Implementar `redact` espejo de `privacy.py` en `apps/web/lib/redact.ts` y su prueba con `data/fixtures/pii_cases.json` en `apps/web/tests/redact.test.ts`
- [ ] T064 [P] [US4] Implementar el outbox con Dexie (`client_uuid` con `crypto.randomUUID`, estados pendiente/enviado/error, envío por `/ingest/batch`, disparo en `online`, al cargar y cada 15 s) en `apps/web/lib/db.ts` y su prueba en `apps/web/tests/outbox.test.ts` — data-model.md `Report.client_uuid`
- [ ] T065 [US4] Implementar `/reportar`: aviso de privacidad con consentimiento explícito, formulario (categoría, descripción, GPS o selector de barrio, personas, foto opcional), redacción antes de guardar, lista de reportes con estado, mensaje "guardado, se enviará cuando haya señal" en `apps/web/app/reportar/page.tsx` — data-model.md `Report.people_affected`, `Report.geo_precision`
- [ ] T066 [P] [US4] Crear `apps/web/public/manifest.json`, íconos y `apps/web/public/sw.js` (cache del app shell; registro solo en contextos seguros) (research R4)

**Checkpoint**: quickstart §7 en portátil (offline DevTools) y celular (modo avión con página abierta).

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T067 [P] Escribir `README.md` con "cómo correr la demo en 1 comando", requisitos y tokens de demo
- [ ] T068 [P] Escribir el guion de demo de 3–4 min (CLAUDE.md §10) para cualquier integrante en `docs/guion_demo.md`
- [ ] T069 Dejar ruff, black, mypy (`app/core`), eslint, prettier y typecheck en verde en `services/api/` y `apps/web/`
- [ ] T070 Ejecutar [quickstart.md](quickstart.md) completo desde `docker compose down -v`, primero con red y luego con Wi-Fi apagado, y registrar resultados en `specs/001-p0-situational-core/checklists/demo-run.md`
- [ ] T071 Grabar video/GIF de respaldo de la demo y enlazarlo en `docs/guion_demo.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)** → **Foundational (Fase 2)** → historias.
- **US1 (Fase 3)**: depende de Fase 2. Es el MVP.
- **US2 (Fase 4)**: depende de US1 (necesita incidentes y esquemas).
- **US3 (Fase 5)**: depende de US1 (motor) para el cálculo; el panel (T062) depende de US2 (T049, cliente en vivo).
- **US4 (Fase 6)**: depende de US1 (`/ingest/batch`); independiente de US2 y US3.
- **Polish (Fase 7)**: después de las historias que se vayan a demostrar.

### Within Each User Story

- Pruebas unitarias antes o junto con su módulo (T023–T027 ↔ T028–T034).
- Módulos del motor → pipeline → esquemas → routers → scripts → regenerar tipos.
- Cada vez que cambia un esquema Pydantic: regenerar OpenAPI y tipos en el **mismo commit** (T042, T048, T061).

### Orden serial recomendado (un solo responsable)

T001→T021 · T022→T042 (MVP) · T054→T060 (escenario y KPI del motor, sin UI) · T043→T053 ·
T061→T062 · T063→T066 · T067→T071.

Razón: con el escenario y los KPI listos justo después del MVP se calibra el motor temprano
(el KPI oficial es lo más arriesgado), y el tablero se construye ya con datos realistas.

### Parallel Opportunities

- Fase 1: T003, T004, T006 en paralelo tras T002.
- Fase 2: T012, T013, T014, T015, T018, T019, T020 en paralelo tras T011.
- US1: T022–T027 en paralelo; T028–T032 en paralelo; luego T033→T038 en serie.
- US2: T049–T052 (frontend) en paralelo con T046–T047 (backend).
- US4: T063, T064, T066 en paralelo; T065 al final.

## Parallel Example: User Story 1

```bash
# Módulos independientes del motor (archivos distintos):
Task: "T028 privacy.py"   Task: "T029 sms.py"   Task: "T030 nlp.py"
Task: "T031 geo.py"       Task: "T032 similarity.py"
# Luego, en serie: T033 dedup.py → T034 trust.py → T035 pipeline.py
```

## Implementation Strategy

### MVP First (User Story 1)

1. Fases 1 y 2.
2. Fase 3 (US1). **Parar y validar**: quickstart §2–§4 por API.
3. Inmediatamente T054–T060 para medir y calibrar el KPI.

### Incremental Delivery (meta: P0 demostrable antes del sáb 21 nov, 10:00 a. m.)

1. MVP + KPI calibrado → se puede contar la historia con la consola.
2. + US2 tablero → demo visual (entregable oficial).
3. + panel KPI (T061–T062) → evidencia para el jurado.
4. + US4 PWA → momento "modo avión".
5. Polish → README, guion, ensayo offline, video de respaldo.

Si el tiempo se acaba, se recorta desde el final: US4 se muestra en el portátil únicamente, y el
video de respaldo cubre lo que no esté estable (CLAUDE.md §14).
