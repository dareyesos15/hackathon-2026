# Research: Despacho, alertas y predicción de efectos en cascada

**Feature**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Fecha**: 2026-11-21

Decisiones de la fase 0. Se reutiliza todo lo decidido en
[001/research.md](../001-p0-situational-core/research.md) (stack, bus en memoria, SSE con respaldo,
tokens por rol, exportación estática); aquí solo lo nuevo.

## R1. Catálogo de agencias y recursos

- **Decision**: tablas `agencies` y `resources` sembradas al arrancar la API desde
  `data/seed/resources.json` (SIMULADO), igual que la geografía (`seed.py`, idempotente). 10
  agencias de la tabla EMRE y 24 recursos (Bomberos 6, Defensa Civil 3, Policía 2, Cruz Roja 4,
  Secretaría de Salud 2, Desarrollo Social 2, Infraestructura 2, Aguas de Manizales 1, CHEC 1,
  Efigas 1) con base en coordenadas aproximadas de Manizales.
- **Rationale**: el catálogo es dato de referencia, no estado del escenario; sembrarlo como la
  geografía mantiene un solo comando de arranque y lo hace editable sin código.
- **Alternatives considered**: catálogo en código (difícil de editar por el equipo); endpoint de
  administración de recursos (no lo pide la spec; viola principio VII).

## R2. Sugerencia de agencia (función EMRE)

- **Decision**: tabla estática `EMRE_ROUTING: Category → (función, [agency_code…])` en
  `app/core/dispatch.py`, copiada de CLAUDE.md §7.7 / FR-001. La primera agencia de la lista es la
  sugerida; las demás son alternativas de la misma función. `sismo_sentido`, `rumor_informacion` y
  `sin_clasificar` no tienen sugerencia ("Sin agencia sugerida"). `colapso_estructura` va a la
  función 1.
- **Rationale**: es una regla institucional fija, no un modelo; probarla es trivial y SC-002 pide
  100 % de coincidencia.
- **Alternatives considered**: guardarla en base de datos (sin beneficio para la demo).

## R3. Consistencia del despacho (sin doble despacho, idempotencia)

- **Decision**:
  - `POST /dispatches` lleva `client_uuid` generado por el cliente con restricción única
    (mismo patrón que `reports`): repetir la confirmación devuelve el despacho existente (FR-007).
  - Un recurso solo tiene un despacho activo: índice único parcial
    `dispatches(resource_id) WHERE status IN ('en_camino','en_sitio')` (FR-005).
  - Doble despacho del incidente: dentro de la transacción se bloquea la fila del incidente
    (`SELECT … FOR UPDATE`) y se cuentan sus despachos activos; si hay alguno y no viene
    `is_reinforcement=true` con `justification` no vacía → `409 active_dispatch_exists` con el
    despacho existente en el cuerpo (FR-006). Cada 409 de este tipo suma al KPI
    "despachos dobles evitados" (evento en bitácora `despacho_doble_bloqueado`).
- **Rationale**: la base garantiza las dos invariantes aunque dos operadores actúen a la vez; el
  bloqueo de fila es suficiente con un solo worker y PostgreSQL.
- **Alternatives considered**: solo validación en la interfaz (falla con dos navegadores);
  bloqueo optimista con versión del incidente (más código para el mismo efecto).

## R4. Trazas tipo RFID y avance simulado

- **Decision**:
  - Tabla `resource_tracks` (solo-agregar) con `kind` (`salida`, `control`, `llegada`,
    `regreso`), punto, hora y `origin` (`rfid_simulado`, `manual`).
  - Endpoint `POST /resources/{id}/tracks` (roles `agencia`, `operador_pmu`) para registro manual o
    un lector real futuro.
  - Adaptador `TrackFeed` (principio VI) con implementación `SimulatedRfidFeed`: tarea asyncio
    lanzada en el `lifespan` de la API cuando `SIMULATE_TRACKS=true` (por defecto en modo demo).
    Cada `track_tick_s` (5 s) revisa los despachos `en_camino` y registra puntos de paso sobre la
    línea recta base → incidente: `salida` al crear, `control` en 1/3 y 2/3 del ETA, `llegada` al
    cumplirse el ETA (que pasa el despacho a `en_sitio`). Usa la misma función de dominio que el
    endpoint, así que el resultado es idéntico al de un lector real.
  - Factor de aceleración `track_speedup` (por defecto 20×) para que un recorrido de 6 min reales
    se vea en ~20 s durante la demo (FR-014, SC-004).
- **Rationale**: la demo sigue siendo "un comando" (sin otro proceso que lanzar) y el punto de
  integración RFID (patente 15111163) queda explícito.
- **Alternatives considered**: script externo `simulate_tracks.py` como cliente REST (otro
  proceso que recordar en el pitch); animación solo en el navegador (no deja traza auditable).

## R5. Tiempo estimado de llegada

- **Decision**: interfaz `RoutingProvider.eta(origin, destination) -> RouteEstimate` con
  implementación `StraightLineRouting`: distancia haversine × 1,4 (tortuosidad urbana) a 25 km/h,
  etiquetada SIMULADO. El adaptador ERIS-UNAL (rutas con probabilidad de bloqueo) es otra
  implementación futura.
- **Rationale**: suficiente para ordenar recursos por cercanía (FR-003) y mostrar una ETA honesta.
- **Alternatives considered**: grafo vial OSM offline (descarga y peso; fuera de alcance).

## R6. Bitácora de despacho y de alertas

- **Decision**:
  - Acciones de despacho van a `report_events` con `incident_id` (la bitácora del incidente queda
    completa en un solo lugar). Nuevos valores de `ReportAction`: `despachar`, `reforzar`,
    `despacho_estado`, `cancelar_despacho`, `despacho_doble_bloqueado`. La migración amplía la
    restricción CHECK de `report_action`.
  - Las alertas no pertenecen a un incidente: tabla propia `alert_events` (solo-agregar) con
    `alert_id`, `actor_role`, `action`, `alert_version`, `payload`, `at`.
- **Rationale**: principio III (toda acción humana auditable) sin forzar una tabla genérica.
- **Alternatives considered**: tabla de auditoría genérica (refactor del P0 sin necesidad).

## R7. Ciclo de vida y aprobación de alertas

- **Decision**:
  - Estados `borrador → emitida | rechazada`, `emitida → anulada`. El borrador es editable por
    `operador_pmu` y `coe`; cada edición incrementa `version`.
  - `POST /alerts/{id}/approve` exige `version` en el cuerpo; si no coincide con la actual →
    `409 version_conflict` (FR-018). Rechazar exige `reason`; anular exige `reason`.
  - Rol distinto de `coe` en approve/reject/cancel → `403` con el mensaje "Solo el COE puede
    aprobar alertas oficiales" (FR-016).
- **Rationale**: versión explícita = control de concurrencia simple y visible en la bitácora.
- **Alternatives considered**: ETag/If-Match (más difícil de mostrar y probar desde la interfaz).

## R8. Área de la alerta

- **Decision**: el área se define como (a) uno o más barrios (unión de sus polígonos de
  `barrios.geojson`) o (b) un círculo (centro + radio 100–3 000 m) marcado con un clic en el mapa
  o heredado del incidente/manzana de origen. La API la guarda siempre como `MULTIPOLYGON` 4326
  (el círculo se materializa como polígono de 32 lados). Debe intersecar el casco urbano.
- **Rationale**: cubre "barrios o un área dibujada en el mapa" sin agregar un plugin de dibujo a
  MapLibre (principio VII); el polígono almacenado deja abierta la herramienta de dibujo libre.
- **Alternatives considered**: `@mapbox/mapbox-gl-draw` (dependencia nueva, compatibilidad con
  MapLibre 6 sin verificar offline).

## R9. Advertencia de desinformación y redacción en alertas

- **Decision**: al crear o editar un borrador, la API redacta el mensaje con
  `core/privacy.redact` (FR-021) y calcula `core/nlp.misinformation_signals`. Si hay señales y no
  viene `confirm_misinformation=true` → `422 misinformation_confirmation_required` con la lista de
  señales; la interfaz las muestra y permite confirmar o corregir (FR-022). La confirmación queda
  en `alert_events`.
- **Rationale**: reutiliza el léxico calibrado en P0; un solo punto de verdad.
- **Alternatives considered**: advertencia solo en el navegador (la API debe ser la autoridad).

## R10. Envío multicanal simulado

- **Decision**: interfaz `AlertGateway.send(alert, channel) -> Delivery` con `SimulatedGateway`:
  - `tablero` y `mapa_publico`: evento SSE `alert.changed` y visibilidad en
    `GET /alerts/active`.
  - `sms_cuadrillas`: destinatarios = recursos `en_camino`/`en_sitio` cuya última posición cae en
    el área, más las bases de agencias dentro del área; se guarda solo el conteo en
    `alert_deliveries` (FR-020). Mensaje SMS ≤ 160 caracteres validado al crear.
- **Rationale**: sin números de teléfono en ningún lado (principio I) y la integración real es
  otra implementación del adaptador.
- **Alternatives considered**: contar ciudadanos del área (no hay padrón y no es el canal EMRE).

## R11. Predicción de efectos en cascada

- **Decision**: cálculo determinista por manzana en `app/core/cascade.py`, sin persistir (564
  manzanas: < 50 ms), con caché en memoria invalidada por nueva lluvia o nuevo reporte relevante:

  | Factor | Peso | Fuente |
  |---|---|---|
  | Pendiente | 35 | `TerrainProvider` → `SyntheticTerrain`: `slope_deg` determinista por manzana (ladera 25–60°, meseta 3–15°, hash del id); SIMULADO. Saturación 45° |
  | Lluvia acumulada 3 h | 30 | última lectura de `rain_readings`; saturación 40 mm; sin lecturas → 0 y "sin dato de lluvia" |
  | Intensidad sísmica | 15 | `HazardProvider` existente; hoy neutro (0,5) → "sin dato de sensor" (FR-029) |
  | Reportes cercanos | 20 | reportes `dano_estructural`, `colapso_estructura`, `deslizamiento` no descartados a ≤ 300 m del centroide en las últimas 6 h del **reloj del escenario**; saturación 3 |

  Niveles: `bajo` < 25 ≤ `medio` < 50 ≤ `alto` < 75 ≤ `muy_alto`. Versión `cascade-v1`.
  Pesos, saturaciones y cortes en `Settings.cascade`.
- **Reloj del escenario**: los reportes sintéticos tienen horas del 10 ago 2026; "últimas 6 h" se
  mide contra `max(reports.occurred_at)`, no contra la hora del servidor.
- **Rationale**: explicable factor por factor (FR-026), rápido, sin modelos externos. Los pesos
  hacen que una ladera con lluvia fuerte y reportes cercanos llegue a "muy alto", y que la meseta
  seca quede en "bajo".
- **Alternatives considered**: tabla `hazard_estimates` persistida (útil cuando haya sensores, no
  aún); modelo de susceptibilidad del SAT de Manizales (no disponible offline).

## R12. Feed de lluvia simulado

- **Decision**: tabla `rain_readings` (`station_code`, `mm_3h`, `at`, `source='SIMULADO'`) y
  `POST /sensors/rain` (roles `operador_pmu`, `coe`). Una estación urbana única
  (`LLUVIA-URB-01`, origen declarado: patente NC2022/0005821). El panel de la capa trae un control
  deslizante 0–60 mm que publica la lectura; `replay_scenario.py --rain` puede publicar una curva.
- **Rationale**: una sola estación basta para mostrar el efecto; IDW entre estaciones no aporta a
  la demo.
- **Alternatives considered**: varias estaciones con interpolación (principio VII).

## R13. KPI de despacho

- **Decision**: `GET /metrics/kpi` agrega tres indicadores calculados en vivo (como
  `reports_received`):
  - `critical_without_dispatch`: incidentes `is_life_threat` abiertos/en revisión/verificados sin
    despacho activo ni finalizado.
  - `median_time_to_dispatch_min`: mediana de `primer despacho.created_at − incident.created_at`
    en incidentes críticos (hora real de consolidación, no la hora sintética del evento).
  - `double_dispatch_prevented`: conteo de eventos `despacho_doble_bloqueado`.
  El tablero destaca incidentes críticos sin despacho tras `unattended_alert_min` (15 min,
  configurable; en demo se puede bajar).
- **Rationale**: principio IV (los KPI se calculan) y V (fuente y corte).

## R14. Roles y pantallas

- **Decision**:
  - `web/lib/session.ts` agrega `coe` y `agencia`.
  - `/pmu/` acepta `operador_pmu` y `coe`; el COE ve además la bandeja "Alertas por aprobar".
  - Nueva pantalla `/agencia/`: elegir agencia (lista de `GET /agencies`) y ver/actualizar sus
    despachos. La agencia elegida viaja como query `agency_id`; en la demo un solo token `agencia`
    puede actuar por cualquier agencia (spec, Supuestos).
  - Endpoints de lectura de incidentes, `/stream` y `/map/manzanas` se abren a `coe`; `/stream`
    también a `agencia` (solo eventos de despacho).
- **Rationale**: dos pantallas nuevas como máximo; el COE trabaja sobre el mismo tablero.

## R15. Eventos en vivo y mapa público

- **Decision**: nuevos eventos SSE `dispatch.upserted`, `resource.moved`, `alert.changed`,
  `cascade.invalidated`; `IncidentSummary` gana `dispatch_status` y `assigned_agency` (derivados
  del despacho activo más reciente). El mapa público consulta `GET /alerts/active` cada 4 s (cumple
  < 5 s de SC-006 sin abrir SSE al rol `publico`).
- **Rationale**: reutiliza el bus y el modo de respaldo del P0; el público sigue sin flujo en vivo.

## R16. Reinicio de la demo

- **Decision**: `POST /demo/reset` también vacía `dispatches`, `resource_tracks`, `alerts`,
  `alert_events`, `alert_deliveries`, `rain_readings` y devuelve los recursos a `disponible` en su
  base (el catálogo se conserva).
