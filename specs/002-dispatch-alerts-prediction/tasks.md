---

description: "Lista de tareas: despacho, alertas y predicción de efectos en cascada"
---

# Tasks: Despacho, alertas y predicción de efectos en cascada

**Input**: Design documents from `/specs/002-dispatch-alerts-prediction/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluidas. La constitución (principio IX) exige pruebas de lo que toca cada commit y el
[quickstart](quickstart.md) define las pruebas automáticas por historia.

**Organization**: tareas agrupadas por historia de usuario (US1 despacho, US2 alertas, US3
cascada) para implementarlas y probarlas por separado.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1, US2, US3)
- Cada tarea indica rutas exactas; las restricciones de campos se citan como
  `data-model.md Entidad.campo` y no se repiten aquí

## Path Conventions

- Backend: `services/api/app/`, pruebas en `services/api/tests/{unit,integration,contract}/`
- Frontend: `apps/web/{app,components,lib}/`, pruebas en `apps/web/tests/`
- Datos y scripts: `data/seed/`, `scripts/`; documentación: `docs/`
- Commits: uno por tarea (o por grupo inseparable: modelo Pydantic + tipos TS regenerados), en
  formato Conventional Commits (CLAUDE.md §0.1)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: configuración y datos de referencia que usan las tres historias

- [X] T001 Agregar a `Settings` las claves `simulate_tracks`, `track_tick_s`, `track_speedup`, `routing_speed_kmh`, `routing_tortuosity`, `unattended_alert_min` y el submodelo `CascadeSettings` (pesos 35/30/15/20, saturaciones 45°/40 mm/3 reportes, radio 300 m, ventana 6 h, cortes 25/50/75) según la tabla "Configuración nueva" de data-model.md, en `services/api/app/config.py`
- [X] T002 [P] Documentar `SIMULATE_TRACKS`, `TRACK_SPEEDUP` y `UNATTENDED_ALERT_MIN` con sus valores por defecto en `.env.example`
- [X] T003 [P] Crear el catálogo SIMULADO de 10 agencias y 24 recursos (reparto de research R1, bases en coordenadas aproximadas de Manizales, `source: "SIMULADO"`) con los campos data-model.md `Agency.code`, `Agency.name`, `Agency.emre_function`, `Resource.code`, `Resource.type`, `Resource.label`, `Resource.base_geom` en `data/seed/resources.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: esquema, roles y enrutamiento que las tres historias necesitan

**⚠️ CRITICAL**: ninguna historia empieza antes de terminar esta fase

- [X] T004 Agregar los enums `EmreFunction`, `ResourceType`, `ResourceStatus`, `DispatchStatus`, `TrackKind`, `TrackOrigin`, `AlertType`, `AlertStatus`, `AlertChannel`, `AlertAction`, `CascadeLevel` y ampliar `ReportAction` (`despachar`, `reforzar`, `despacho_estado`, `cancelar_despacho`, `despacho_doble_bloqueado`, `cerrar_atendido`) según data-model.md §Enumeraciones nuevas, en `services/api/app/domain.py`
- [X] T005 Definir los modelos ORM `Agency`, `Resource`, `Dispatch`, `ResourceTrack`, `Alert`, `AlertEvent`, `AlertDelivery`, `RainReading` con `CommonMixin` en `services/api/app/models.py` — restricciones según data-model.md: `Agency.code` (único), `Agency.emre_function`; `Resource.code` (único), `Resource.type`, `Resource.status`, `Resource.base_geom`, `Resource.last_geom`, `Resource.last_seen_at`; `Dispatch.client_uuid` (único), `Dispatch.agency_id`, `Dispatch.emre_function`, `Dispatch.suggested`, `Dispatch.eta_at`, `Dispatch.resource_id` (índice único parcial), `Dispatch.status`, `Dispatch.justification` (CHECK con `Dispatch.is_reinforcement`), `Dispatch.close_note`, `Dispatch.created_by_role`; `ResourceTrack.kind`, `ResourceTrack.origin`, `ResourceTrack.geom`; `Alert.type`, `Alert.status`, `Alert.area`, `Alert.area_barrios`, `Alert.area_circle`, `Alert.message`, `Alert.channels`, `Alert.misinfo_signals`, `Alert.origin_incident_id`, `Alert.origin_manzana_id`, `Alert.approved_by_role` (CHECK solo `coe`), `Alert.close_reason`; `AlertEvent.action`; `AlertDelivery.recipients_count`; `RainReading.mm_3h`
- [X] T006 Escribir la migración `0003` (tablas, índices GIST, índice único parcial de despachos, CHECK ampliada de `report_action`, upgrade y downgrade) en `services/api/alembic/versions/0003_dispatch_alerts_cascade.py`
- [X] T007 [P] Sembrar de forma idempotente agencias y recursos desde `data/seed/resources.json` al arrancar (con `Resource.last_geom` = `Resource.base_geom` y `Resource.status` = `disponible`), en `services/api/app/seed.py`
- [X] T008 [P] Ampliar el reinicio de la demo para vaciar `dispatches`, `resource_tracks`, `alerts`, `alert_events`, `alert_deliveries`, `rain_readings` y devolver los recursos a su base (research R16), en `services/api/app/routers/demo.py`
- [X] T009 Abrir al rol `coe` las rutas `GET /incidents`, `GET /incidents/{id}`, `PATCH /incidents/{id}` y `GET /map/manzanas`, y `GET /stream` a `coe` y `agencia` (la agencia solo recibe `dispatch.upserted` y `resource.moved`), según contracts/rest-api.md §Cambios a rutas existentes, en `services/api/app/routers/incidents.py`, `services/api/app/routers/review.py`, `services/api/app/routers/map.py` y `services/api/app/routers/stream.py`
- [X] T010 [P] Prueba de integración de la migración 0003 (upgrade y downgrade sobre la base de pruebas) y de los nuevos permisos por rol del T009, en `services/api/tests/integration/test_roles_0003.py`
- [X] T011 [P] Agregar los roles `coe` y `agencia` (tokens de demo, etiquetas y tarjetas de inicio: COE → `/pmu/`, Agencia → `/agencia/`) en `apps/web/lib/session.ts` y `apps/web/app/page.tsx`
- [X] T012 [P] Agregar etiquetas en español de funciones EMRE, estados de recurso y despacho, tipos y estados de alerta, canales y niveles de cascada en `apps/web/lib/labels.ts`
- [X] T013 Hacer que el tablero acepte la sesión `coe` además de `operador_pmu` (token para `useLiveIncidents`) en `apps/web/app/pmu/TableroPmu.tsx`

**Checkpoint**: la API arranca con 0003 aplicada y el catálogo sembrado; el COE entra al tablero.

---

## Phase 3: User Story 1 - Despachar un incidente a la agencia correcta sin duplicar esfuerzos (Priority: P1) 🎯 MVP

**Goal**: sugerir agencia por la tabla EMRE, despachar recursos sin doble despacho, ver el recorrido
tipo RFID y medir el tiempo a despacho.

**Independent Test**: [quickstart.md](quickstart.md) §Escenario 1: sugerencia correcta,
idempotencia, `409 active_dispatch_exists`, refuerzo justificado, recorrido en vivo, cierre por la
agencia y KPI.

### Tests for User Story 1

- [X] T014 [P] [US1] Pruebas unitarias de la tabla `EMRE_ROUTING` para todas las categorías de `Category` (SC-002), del orden de candidatos por distancia, del uso de agencias alternativas (`fallback_used`), de las transiciones de despacho de data-model.md §Despacho y de la regla "posición actual = punto con mayor `at`" (data-model.md `ResourceTrack.at`), en `services/api/tests/unit/test_dispatch.py`
- [X] T015 [P] [US1] Pruebas unitarias de `StraightLineRouting` (distancia × tortuosidad, velocidad, etiqueta SIMULADO) en `services/api/tests/unit/test_routing.py`
- [X] T016 [P] [US1] Pruebas de integración de contracts/rest-api.md §Despachos y §Agencias y recursos: `201`/`200` idempotente por `client_uuid`, `409 active_dispatch_exists` (y su evento `despacho_doble_bloqueado`), `409 resource_unavailable`, `422 justification_required`, `422 incident_closed`, `422 out_of_area` en puntos de paso, `llegada → en_sitio`, filtro obligatorio por `agency_id` con rol `agencia`, `cerrar_atendido`, KPI de despacho y redacción de `Dispatch.justification` y `Dispatch.close_note` (SC-007), en `services/api/tests/integration/test_dispatch_api.py`

### Implementation for User Story 1

- [X] T017 [P] [US1] Implementar `RoutingProvider` y `StraightLineRouting` (research R5) en `services/api/app/adapters/routing.py`
- [X] T018 [US1] Implementar el dominio de despacho: `EMRE_ROUTING` (research R2), `suggest()`, `create_dispatches()` con bloqueo `FOR UPDATE` del incidente, idempotencia por data-model.md `Dispatch.client_uuid`, refuerzo con data-model.md `Dispatch.justification` redactada, `transition()` según data-model.md §Despacho (estados de data-model.md `Dispatch.status` y `Resource.status`; nota redactada en data-model.md `Dispatch.close_note`), `record_track()` con validación de data-model.md `ResourceTrack.geom` y actualización de data-model.md `Resource.last_geom` y `Resource.last_seen_at` solo si `ResourceTrack.at` es más reciente, registro de data-model.md `Dispatch.agency_id`, `Dispatch.emre_function`, `Dispatch.suggested` y `Dispatch.eta_at` (con `RoutingProvider`) al crear, y eventos de bitácora en `report_events` (research R6), en `services/api/app/core/dispatch.py`
- [X] T019 [US1] Implementar `TrackFeed` y `SimulatedRfidFeed` (salida, controles en 1/3 y 2/3 del ETA, llegada; `track_tick_s` y `track_speedup`; research R4) usando `record_track()`, y lanzarlo en el `lifespan` si `simulate_tracks`, en `services/api/app/adapters/tracks.py` y `services/api/app/main.py`
- [X] T020 [US1] Agregar los esquemas `ResourceOut`, `AgencyOut`, `DispatchIn`, `DispatchOut`, `DispatchPatchIn`, `TrackIn`, `TrackOut`, `DispatchSuggestion`, y los campos `dispatch_status`, `assigned_agency`, `unattended` en `IncidentSummary` y `dispatches`, `suggestion` en `IncidentDetail` (contracts/rest-api.md), en `services/api/app/schemas.py`
- [X] T021 [US1] Calcular `dispatch_status`, `assigned_agency` y `unattended` (riesgo vital sin despacho por más de `unattended_alert_min`) en `incidents_out`, en `services/api/app/serializers.py`
- [X] T022 [US1] Implementar `GET /agencies`, `GET /resources`, `GET/POST /resources/{id}/tracks`, `POST/GET /dispatches` y `PATCH /dispatches/{id}`, publicando `dispatch.upserted`, `resource.moved` e `incident.upserted` (contracts/sse-events.md), y registrar el router en `services/api/app/routers/dispatch.py` y `services/api/app/main.py`
- [X] T023 [US1] Incluir `suggestion` y `dispatches` en `GET /incidents/{id}` en `services/api/app/routers/incidents.py`
- [X] T024 [US1] Agregar la acción `cerrar_atendido` (`verificado → atendido`, roles `operador_pmu` y `coe`) en `services/api/app/core/review.py` y `services/api/app/schemas.py`
- [X] T025 [US1] Agregar los KPI en vivo `critical_without_dispatch`, `median_time_to_dispatch_min` (desde `incident.created_at`, research R13) y `double_dispatch_prevented` en `services/api/app/routers/metrics.py`, y sus definiciones en `docs/diccionario_indicadores.md`
- [X] T026 [US1] Exportar el OpenAPI, regenerar los tipos TS y actualizar el snapshot del contrato con `scripts/export_openapi.py` → `apps/web/lib/api/openapi.json`, `apps/web/lib/api/schema.d.ts` y `services/api/tests/contract/test_openapi_snapshot.py`
- [ ] T027 [US1] Manejar `dispatch.upserted` y `resource.moved` en el flujo en vivo, con respaldo por polling a `GET /dispatches?since=` (contracts/sse-events.md), en `apps/web/lib/live.ts`
- [ ] T028 [P] [US1] Crear `PanelDespacho` (función y agencia sugeridas, candidatos con distancia y ETA SIMULADA, confirmar con `client_uuid` del cliente, manejo de `409 active_dispatch_exists` mostrando el despacho activo y pidiendo justificación de refuerzo, cancelar con nota, "Listo para cerrar" → `cerrar_atendido`) en `apps/web/components/PanelDespacho.tsx`
- [ ] T029 [US1] Integrar `PanelDespacho` y la lista de despachos del incidente en `apps/web/components/DetalleIncidente.tsx`
- [ ] T030 [P] [US1] Agregar a `Mapa` las capas de recursos (color por estado) y recorridos (línea de puntos de paso por despacho activo) en `apps/web/components/Mapa.tsx`
- [ ] T031 [P] [US1] Mostrar el estado de despacho y destacar los incidentes `unattended` en la matriz de triaje en `apps/web/components/MatrizTriaje.tsx`
- [ ] T032 [US1] Mostrar la cifra "Críticos sin despacho" (fuente y corte) y pasar recursos y recorridos al mapa en `apps/web/app/pmu/TableroPmu.tsx`
- [ ] T033 [P] [US1] Crear la pantalla de agencia: elegir agencia (`GET /agencies`), ver sus despachos en vivo y marcar llegada, finalizado o fuera de servicio con motivo, en `apps/web/app/agencia/page.tsx` y `apps/web/app/agencia/PanelAgencia.tsx`
- [ ] T034 [P] [US1] Pruebas `vitest` de las etiquetas de estado de despacho y del cálculo de "listo para cerrar" en `apps/web/tests/dispatch.test.ts`

**Checkpoint**: US1 funciona sola: [quickstart.md](quickstart.md) §Escenario 1 pasa completo.

---

## Phase 4: User Story 2 - Alertas oficiales con aprobación del COE (Priority: P2)

**Goal**: borradores de alerta que solo el COE aprueba, emisión simulada por tablero, mapa
público y SMS a cuadrillas, con advertencia de desinformación y bitácora.

**Independent Test**: [quickstart.md](quickstart.md) §Escenario 2: `403 coe_only`,
`409 version_conflict`, `422 misinformation_confirmation_required`, emisión visible en < 5 s en
`/pmu/` y `/mapa/`, anulación y redacción del mensaje.

### Tests for User Story 2

- [ ] T035 [P] [US2] Pruebas unitarias del dominio de alertas: área por barrios (unión) y por círculo (polígono de 32 lados, radio 100–3 000 m, intersección con el casco urbano) para data-model.md `Alert.area`, límite de 160 caracteres para SMS en data-model.md `Alert.message`, transiciones y versión de data-model.md §Alertas, señales de desinformación y conteo de destinatarios sin datos de contacto (data-model.md `AlertDelivery.recipients_count`), en `services/api/tests/unit/test_alerts.py`
- [ ] T036 [P] [US2] Pruebas de integración de contracts/rest-api.md §Alertas: `201` borrador, `422 misinformation_confirmation_required`, `422 sms_too_long`, `422 area_required`/`out_of_area`, `403 coe_only` en approve/reject/cancel, `409 version_conflict` (y evento `aprobacion_conflicto`), `409 not_editable`, `GET /alerts/active` para `publico` sin autor, señales ni entregas (FR-033), mensaje con `[TEL]` (SC-007) y bitácora completa en `GET /alerts/{id}/events`, en `services/api/tests/integration/test_alerts_api.py`

### Implementation for User Story 2

- [ ] T037 [P] [US2] Implementar `AlertGateway` y `SimulatedGateway` (tablero y mapa público por evento; `sms_cuadrillas` cuenta recursos en camino o en sitio y bases dentro del área, research R10) en `services/api/app/adapters/alert_gateway.py`
- [ ] T038 [US2] Implementar el dominio de alertas: construcción de data-model.md `Alert.area` desde data-model.md `Alert.area_barrios` o `Alert.area_circle` (research R8), vínculo de origen en data-model.md `Alert.origin_incident_id` y `Alert.origin_manzana_id`, redacción de data-model.md `Alert.message` con `privacy.redact`, `misinformation_signals` guardadas en data-model.md `Alert.misinfo_signals` con confirmación explícita (research R9), validación de data-model.md `Alert.channels`, transiciones con data-model.md `Alert.status` y `Alert.version` (`version_conflict`), solo `coe` en data-model.md `Alert.approved_by_role`, motivo obligatorio en data-model.md `Alert.close_reason`, entregas en `alert_deliveries` y bitácora en `alert_events` con data-model.md `AlertEvent.action`, en `services/api/app/core/alerts.py`
- [ ] T039 [US2] Agregar los esquemas `AlertIn`, `AlertPatchIn`, `AlertDecisionIn`, `AlertOut`, `AlertEventOut` y el GeoJSON público de alertas vigentes (contracts/rest-api.md §Alertas) en `services/api/app/schemas.py`
- [ ] T040 [US2] Implementar `POST/GET /alerts`, `PATCH /alerts/{id}`, `GET /alerts/{id}/events`, `POST /alerts/{id}/approve|reject|cancel` (403 con `code: coe_only`) y `GET /alerts/active`, publicando `alert.changed`, y registrar el router en `services/api/app/routers/alerts.py` y `services/api/app/main.py`
- [ ] T041 [US2] Exportar el OpenAPI, regenerar los tipos TS y actualizar el snapshot del contrato con `scripts/export_openapi.py` → `apps/web/lib/api/openapi.json`, `apps/web/lib/api/schema.d.ts` y `services/api/tests/contract/test_openapi_snapshot.py`
- [ ] T042 [US2] Manejar `alert.changed` en el flujo en vivo, con respaldo por polling a `GET /alerts?status=borrador`, en `apps/web/lib/live.ts`
- [ ] T043 [P] [US2] Crear `EditorAlerta` (tipo, área por barrios o círculo con centro elegido en el mapa y radio, mensaje con contador de 160 caracteres al elegir SMS, canales, confirmación de señales de desinformación, precarga desde incidente o manzana) en `apps/web/components/EditorAlerta.tsx`
- [ ] T044 [P] [US2] Crear `BandejaAlertas` (borradores con versión; solo el COE ve "Aprobar", "Rechazar" con motivo y "Anular"; manejo de `409 version_conflict` recargando la versión nueva) en `apps/web/components/BandejaAlertas.tsx`
- [ ] T045 [P] [US2] Crear `AvisoAlerta` (alerta vigente destacada con tipo, mensaje, hora de emisión y etiqueta SIMULADO en los envíos) en `apps/web/components/AvisoAlerta.tsx`
- [ ] T046 [US2] Agregar a `Mapa` la capa de áreas de alerta vigentes y un modo "elegir centro" por clic para el círculo del editor, en `apps/web/components/Mapa.tsx`
- [ ] T047 [US2] Integrar `EditorAlerta`, `BandejaAlertas` (visible para el COE) y `AvisoAlerta` en el tablero, y el botón "Crear alerta desde este incidente" en el detalle, en `apps/web/app/pmu/TableroPmu.tsx` y `apps/web/components/DetalleIncidente.tsx`
- [ ] T048 [US2] Mostrar las alertas vigentes (área sombreada y `AvisoAlerta`) consultando `GET /alerts/active` cada 4 s en `apps/web/app/mapa/MapaPublico.tsx`
- [ ] T049 [P] [US2] Pruebas `vitest` del contador de caracteres para SMS y de la construcción del cuerpo `area` (barrios o círculo) en `apps/web/tests/alerts.test.ts`

**Checkpoint**: US2 funciona sola: [quickstart.md](quickstart.md) §Escenario 2 pasa completo.

---

## Phase 5: User Story 3 - Predicción de efectos en cascada por manzana (Priority: P3)

**Goal**: capa de riesgo de cascada por manzana, explicable por factores, recalculada al cambiar
la lluvia simulada, con salida a alerta preventiva.

**Independent Test**: [quickstart.md](quickstart.md) §Escenario 3: niveles con lluvia 0 y 40 mm,
desglose de 4 factores, recálculo < 10 s sin recargar, "sin dato de sensor" y alerta preventiva
precargada.

### Tests for User Story 3

- [ ] T050 [P] [US3] Pruebas unitarias del modelo de cascada (research R11): pendiente determinista de `SyntheticTerrain`, saturaciones, cortes de nivel, lluvia ausente → 0 con detalle, factor sísmico neutro "sin dato de sensor" (FR-029), ventana de 6 h medida con el reloj del escenario (`max(reports.occurred_at)`), reportes descartados excluidos y cálculo de 564 manzanas en < 100 ms, en `services/api/tests/unit/test_cascade.py`
- [ ] T051 [P] [US3] Pruebas de integración de contracts/rest-api.md §Lluvia y cascada: `POST /sensors/rain` (rango de data-model.md `RainReading.mm_3h`) publica `cascade.invalidated`, `GET /sensors/rain/latest`, `GET /map/cascade` con `min_level`, propiedades `breakdown`, `model_version`, `cutoff_at`, `scenario_clock`, y permisos por rol, en `services/api/tests/integration/test_cascade_api.py`

### Implementation for User Story 3

- [ ] T052 [P] [US3] Implementar `TerrainProvider` y `SyntheticTerrain` (pendiente por zona y hash del id de manzana, SIMULADO) en `services/api/app/adapters/terrain.py`
- [ ] T053 [US3] Implementar el modelo de cascada con caché en memoria invalidada por lluvia o reportes relevantes (factores, pesos y cortes de research R11 desde `Settings.cascade`; versión `cascade-v1`) en `services/api/app/core/cascade.py`
- [ ] T054 [US3] Agregar los esquemas `RainIn`, `RainOut` y las propiedades GeoJSON de la estimación de cascada (data-model.md §Estimación de cascada) en `services/api/app/schemas.py`
- [ ] T055 [US3] Implementar `POST /sensors/rain`, `GET /sensors/rain/latest` y `GET /map/cascade`, y registrar el router en `services/api/app/routers/cascade.py` y `services/api/app/main.py`
- [ ] T056 [US3] Publicar `cascade.invalidated` (como máximo uno cada 3 s) al procesar reportes de `dano_estructural`, `colapso_estructura` o `deslizamiento`, en `services/api/app/routers/ingest.py`
- [ ] T057 [US3] Exportar el OpenAPI, regenerar los tipos TS y actualizar el snapshot del contrato con `scripts/export_openapi.py` → `apps/web/lib/api/openapi.json`, `apps/web/lib/api/schema.d.ts` y `services/api/tests/contract/test_openapi_snapshot.py`
- [ ] T058 [US3] Manejar `cascade.invalidated` en el flujo en vivo (refrescar la capa como máximo una vez cada 3 s) en `apps/web/lib/live.ts`
- [ ] T059 [P] [US3] Crear `CapaCascada` (interruptor, leyenda de 4 niveles con etiqueta SIMULADO, control de lluvia 0–60 mm que publica `POST /sensors/rain`, desglose de la manzana elegida, botón "Crear alerta preventiva" que abre `EditorAlerta` con tipo `deslizamiento` y círculo centrado en la manzana) en `apps/web/components/CapaCascada.tsx`
- [ ] T060 [US3] Agregar a `Mapa` la capa de cascada (color por nivel, clic para elegir manzana) e integrar `CapaCascada` en el tablero, en `apps/web/components/Mapa.tsx` y `apps/web/app/pmu/TableroPmu.tsx`
- [ ] T061 [P] [US3] Agregar la opción `--rain` (curva de lluvia SIMULADA publicada en `POST /sensors/rain` durante la reproducción) en `scripts/replay_scenario.py`

**Checkpoint**: US3 funciona sola: [quickstart.md](quickstart.md) §Escenario 3 pasa completo.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Habeas Data, calidad, documentación y demo

- [ ] T062 Extender la prueba de Habeas Data del escenario para verificar que no hay teléfonos, cédulas ni correos en data-model.md `Alert.message`, `Dispatch.justification`, `Dispatch.close_note` y `Alert.close_reason` (SC-007), en `services/api/tests/integration/test_pii_scenario.py`
- [ ] T063 [P] Agregar `app.core.dispatch`, `app.core.alerts` y `app.core.cascade` a los módulos con mypy estricto en `services/api/pyproject.toml` y corregir lo que reporte
- [ ] T064 [P] Documentar las pantallas `/agencia/` y la bandeja del COE con sus tokens (`coe-demo`, `agencia-demo`) en `README.md`
- [ ] T065 [P] Agregar al guion los pasos de despacho, recorrido, lluvia, alerta preventiva, aprobación del COE y aviso en el mapa público (≤ 2 min, SC-009) en `docs/guion_demo.md`
- [ ] T066 [P] Mover el generador del diagrama a `scripts/generate_architecture_diagram.py`, marcar el bloque 5 y la trazabilidad de recursos como "Implementado" y regenerar `docs/arquitectura_actual.svg` y `docs/arquitectura_actual.png`
- [ ] T067 Ejecutar [quickstart.md](quickstart.md) completo desde `docker compose up` con la base vacía, más `ruff`, `black --check`, `mypy`, `pytest`, `npm run typecheck`, `npm run lint` y `npm test`, y registrar el resultado en `specs/002-dispatch-alerts-prediction/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sin dependencias.
- **Foundational (Fase 2)**: depende de la Fase 1; bloquea todas las historias. T005 → T006;
  T004 → T005; T009 → T010.
- **US1 (Fase 3)**: depende de la Fase 2.
- **US2 (Fase 4)**: depende de la Fase 2. Es independiente de US1, salvo que el conteo de
  destinatarios SMS es 0 si no hay recursos despachados (correcto y probado así).
- **US3 (Fase 5)**: depende de la Fase 2. El botón "Crear alerta preventiva" (T059) usa
  `EditorAlerta` de US2 (T043); sin US2, la capa funciona y el botón se oculta.
- **Polish (Fase 6)**: depende de las historias que se vayan a demostrar.

### Within Each User Story

- Pruebas primero (deben fallar), luego adaptadores → dominio → esquemas → rutas → regenerar
  tipos → frontend.
- Las tareas de regenerar OpenAPI (T026, T041, T057) van en el mismo commit que el último cambio
  de esquemas de su historia (principio X).
- `Mapa.tsx`, `TableroPmu.tsx`, `live.ts` y `schemas.py` se tocan en varias historias: esas
  tareas no llevan [P] entre sí y se hacen en el orden de las historias.

### Parallel Opportunities

- Fase 1: T002 y T003 en paralelo después de T001.
- Fase 2: T007, T008, T011, T012 en paralelo tras T006; T010 tras T009.
- US1: T014, T015, T016, T017 en paralelo; luego T028, T030, T031, T033, T034 en paralelo
  cuando T026 haya regenerado los tipos.
- US2: T035, T036, T037 en paralelo; T043, T044, T045, T049 en paralelo tras T041.
- US3: T050, T051, T052, T061 en paralelo; T059 tras T057.
- Polish: T063, T064, T065, T066 en paralelo.

---

## Parallel Example: User Story 1

```bash
# Pruebas y adaptador en paralelo:
Task: "T014 Pruebas unitarias de despacho en services/api/tests/unit/test_dispatch.py"
Task: "T015 Pruebas de StraightLineRouting en services/api/tests/unit/test_routing.py"
Task: "T016 Pruebas de integración de despacho en services/api/tests/integration/test_dispatch_api.py"
Task: "T017 RoutingProvider en services/api/app/adapters/routing.py"

# Frontend en paralelo tras regenerar tipos (T026):
Task: "T028 PanelDespacho en apps/web/components/PanelDespacho.tsx"
Task: "T030 Capas de recursos y recorridos en apps/web/components/Mapa.tsx"
Task: "T031 Estado de despacho en apps/web/components/MatrizTriaje.tsx"
Task: "T033 Pantalla de agencia en apps/web/app/agencia/"
```

## Parallel Example: User Story 2

```bash
Task: "T035 Pruebas unitarias de alertas en services/api/tests/unit/test_alerts.py"
Task: "T036 Pruebas de integración de alertas en services/api/tests/integration/test_alerts_api.py"
Task: "T037 AlertGateway en services/api/app/adapters/alert_gateway.py"
# Tras T041:
Task: "T043 EditorAlerta" · "T044 BandejaAlertas" · "T045 AvisoAlerta" · "T049 alerts.test.ts"
```

## Parallel Example: User Story 3

```bash
Task: "T050 Pruebas unitarias de cascada en services/api/tests/unit/test_cascade.py"
Task: "T051 Pruebas de integración de cascada en services/api/tests/integration/test_cascade_api.py"
Task: "T052 SyntheticTerrain en services/api/app/adapters/terrain.py"
Task: "T061 --rain en scripts/replay_scenario.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Fases 1 y 2.
2. Fase 3 (US1). **Parar y validar** con [quickstart.md](quickstart.md) §Escenario 1.
3. Ya cubre el paso 6 del guion de la demo ("Se despacha Bomberos al incidente; se ve la traza del
   recurso").

### Incremental Delivery

1. MVP (US1) → despacho y trazabilidad en la demo.
2. + US2 → control humano del COE y aviso en el mapa público (componente de viabilidad).
3. + US3 → el diferencial predictivo (P2 en CLAUDE.md §8).
4. Polish → guion, README, diagrama actualizado y validación completa.

Si el tiempo se acaba, se recorta desde el final: US3 se presenta como "siguiente paso" del pitch
con el diagrama, y US2 puede mostrarse solo con la bandeja del COE y el aviso en el tablero.
