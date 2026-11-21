# Data Model: Despacho, alertas y predicción de efectos en cascada

**Feature**: [spec.md](spec.md) · **Research**: [research.md](research.md)

Extiende el modelo del P0 ([001/data-model.md](../001-p0-situational-core/data-model.md)). Todas las
tablas nuevas llevan las columnas comunes `id UUID`, `created_at`, `source` (por defecto
`SIMULADO`) y `version` (principio V). Enumeraciones como `VARCHAR + CHECK`, igual que en P0.
Migración: `services/api/alembic/versions/0003_dispatch_alerts_cascade.py`.

## Enumeraciones nuevas

| Enum | Valores |
|---|---|
| `emre_function` | `salvamento_seguridad` (1), `salud_saneamiento` (2), `asistencia_social` (3), `infraestructura_servicios` (4), `manejo_coordinacion` (5), `logistica` (6) |
| `resource_type` | `cuadrilla_rescate`, `maquina_extincion`, `ambulancia`, `patrulla`, `cuadrilla_tecnica`, `vehiculo_logistico` |
| `resource_status` | `disponible`, `en_camino`, `en_sitio`, `fuera_de_servicio` |
| `dispatch_status` | `en_camino`, `en_sitio`, `finalizado`, `cancelado` |
| `track_kind` | `salida`, `control`, `llegada`, `regreso`, `manual` |
| `track_origin` | `rfid_simulado`, `manual` |
| `alert_type` | `evacuacion`, `deslizamiento`, `sismo_replica`, `servicios_publicos`, `informacion_general` |
| `alert_status` | `borrador`, `emitida`, `rechazada`, `anulada` |
| `alert_channel` | `tablero`, `mapa_publico`, `sms_cuadrillas` |
| `alert_action` | `crear`, `editar`, `confirmar_desinformacion`, `aprobar`, `rechazar`, `anular`, `aprobacion_conflicto` |
| `cascade_level` | `bajo`, `medio`, `alto`, `muy_alto` |

`report_action` (P0) se amplía con: `despachar`, `reforzar`, `despacho_estado`,
`cancelar_despacho`, `despacho_doble_bloqueado`, `cerrar_atendido`.

## Entidades

### `agencies` (Agencia) — catálogo sembrado

| Campo | Tipo | Regla |
|---|---|---|
| `code` | `VARCHAR(32)` único | p. ej. `BOMBEROS`, `CRUZ_ROJA`, `CHEC` |
| `name` | `VARCHAR(120)` | nombre visible en español |
| `emre_function` | `emre_function` | función de respuesta principal |

### `resources` (Recurso) — catálogo sembrado con estado vivo

| Campo | Tipo | Regla |
|---|---|---|
| `code` | `VARCHAR(32)` único | identificador estable (etiqueta RFID simulada), p. ej. `BOM-M3` |
| `agency_id` | FK `agencies` | |
| `type` | `resource_type` | |
| `label` | `VARCHAR(120)` | "Máquina 3 · Estación Centro" |
| `base_geom` | `POINT 4326` | base de la agencia |
| `status` | `resource_status` | por defecto `disponible` |
| `last_geom` | `POINT 4326` | última posición conocida (= base al sembrar) |
| `last_seen_at` | `timestamptz` | hora del último punto de paso |

### `dispatches` (Despacho) — nunca se borra

| Campo | Tipo | Regla |
|---|---|---|
| `client_uuid` | `UUID` único | idempotencia (FR-007) |
| `incident_id` | FK `incidents` | |
| `resource_id` | FK `resources` | índice único parcial `WHERE status IN ('en_camino','en_sitio')` (FR-005) |
| `agency_id` | FK `agencies` | copia al crear (trazabilidad si el recurso cambia de agencia) |
| `emre_function` | `emre_function` | función usada en la decisión |
| `suggested` | `bool` | si la agencia elegida era la sugerida |
| `is_reinforcement` | `bool` | |
| `justification` | `TEXT` ≤ 500, redactado | obligatoria si `is_reinforcement` (CHECK) |
| `status` | `dispatch_status` | |
| `eta_at` | `timestamptz` | ETA (SIMULADA, `RoutingProvider`) |
| `distance_m` | `int` | |
| `created_by_role` | `actor_role` | `operador_pmu` o `coe` |
| `arrived_at`, `closed_at` | `timestamptz` | |
| `close_note` | `TEXT` ≤ 500, redactado | motivo de cancelación o de fuera de servicio |

**Transiciones** (rol permitido):

```text
en_camino ──llegada (feed/agencia/operador)──▶ en_sitio ──agencia/operador──▶ finalizado
    │                                             │
    └──── cancelar (operador/coe, nota) ──────────┴──▶ cancelado
```

- Al crear: recurso `disponible → en_camino`; punto de paso `salida`.
- `en_sitio`: recurso `en_sitio`; `arrived_at`.
- `finalizado` o `cancelado`: recurso `→ disponible` (o `fuera_de_servicio` si así lo marca la
  agencia con motivo); `closed_at`. El incidente **no** cambia de estado automáticamente
  (FR-011); el operador lo marca `atendido` (nueva acción de revisión permitida sobre
  `verificado`).
- Un incidente `descartado` o fusionado con despachos activos: no se cancelan solos; el evento
  `incident.status_changed` hace que la interfaz muestre el aviso del caso límite.

### `resource_tracks` (Punto de paso) — solo-agregar

| Campo | Tipo | Regla |
|---|---|---|
| `resource_id` | FK `resources` | |
| `dispatch_id` | FK `dispatches` nullable | |
| `kind` | `track_kind` | |
| `origin` | `track_origin` | |
| `geom` | `POINT 4326` | debe caer en Manizales (`in_manizales`) |
| `at` | `timestamptz` | hora del paso (puede llegar fuera de orden) |

La posición actual del recurso es la del punto con mayor `at` (no el último insertado): se
actualiza `resources.last_geom/last_seen_at` solo si `at > last_seen_at`.

### `alerts` (Alerta)

| Campo | Tipo | Regla |
|---|---|---|
| `type` | `alert_type` | |
| `status` | `alert_status` | por defecto `borrador` |
| `version` | `int` | +1 en cada edición del borrador (columna común) |
| `area` | `MULTIPOLYGON 4326` | debe intersecar el casco urbano |
| `area_barrios` | `TEXT[]` | barrios elegidos (vacío si es círculo) |
| `area_circle` | `JSONB` nullable | `{lat, lon, radius_m}` si se definió por círculo |
| `message` | `TEXT` ≤ 500, redactado | ≤ 160 si `sms_cuadrillas ∈ channels` (validación) |
| `channels` | `alert_channel[]` | al menos uno |
| `misinfo_signals` | `TEXT[]` | señales detectadas al guardar |
| `origin_incident_id` | FK `incidents` nullable | si se creó desde un incidente |
| `origin_manzana_id` | FK `manzanas` nullable | si se creó desde la capa de cascada |
| `created_by_role` | `actor_role` | |
| `approved_by_role` | `actor_role` nullable | solo `coe` (CHECK) |
| `emitted_at`, `closed_at` | `timestamptz` | |
| `close_reason` | `TEXT` ≤ 500 | motivo de rechazo o anulación |

**Transiciones**:

```text
borrador ──editar (operador/coe, version+1)──▶ borrador
borrador ──aprobar(version) [solo coe]──▶ emitida ──anular(motivo) [solo coe]──▶ anulada
borrador ──rechazar(motivo) [solo coe]──▶ rechazada
```

`emitida`, `rechazada` y `anulada` no se editan. Aprobar con `version` desactualizada →
`409 version_conflict` y evento `aprobacion_conflicto`.

### `alert_events` (Bitácora de alertas) — solo-agregar

`alert_id`, `actor_role`, `action` (`alert_action`), `alert_version`, `payload JSONB` (motivo,
señales confirmadas, diferencias), `at`.

### `alert_deliveries` (Envío de alerta)

`alert_id`, `channel`, `recipients_count` (int ≥ 0; solo `sms_cuadrillas`, nulo en los demás),
`at`, `source='SIMULADO'`. Nunca guarda números ni identidades.

### `rain_readings` (Lectura de lluvia)

`station_code` (`LLUVIA-URB-01`), `mm_3h` (`NUMERIC(5,1)` 0–300), `at`, `source='SIMULADO'`.

### Estimación de cascada (no persistida)

Valor calculado por `core/cascade.py` y servido como GeoJSON (ver
[contracts/rest-api.md](contracts/rest-api.md#get-mapcascade)):

| Propiedad | Regla |
|---|---|
| `manzana_id`, `barrio` | |
| `level` | `cascade_level` según cortes 25/50/75 |
| `score` | 0–100 |
| `breakdown` | `{pendiente, lluvia, sismo, reportes_cercanos}` cada uno `{puntos, max, detalle}` |
| `slope_deg` | SIMULADO (`TerrainProvider`) |
| `model_version` | `cascade-v1` |
| `cutoff_at` | hora del cálculo; `scenario_clock` = `max(reports.occurred_at)` |

## Cambios a entidades existentes

- **`IncidentSummary`** (respuesta, no tabla): agrega `dispatch_status`
  (`sin_despacho | en_camino | en_sitio | finalizado`) y `assigned_agency` (nombre), derivados del
  despacho más reciente no cancelado; y `unattended` (`bool`: riesgo vital sin despacho por más de
  `unattended_alert_min`).
- **`IncidentDetail`**: agrega `dispatches: DispatchOut[]` y `suggestion: DispatchSuggestion`.
- **Revisión de incidentes**: nueva acción `cerrar_atendido` (`verificado → atendido`), rol
  `operador_pmu`/`coe`.
- **`metrics` KPI**: tres indicadores nuevos (research R13) en `docs/diccionario_indicadores.md`.

## Configuración nueva (`Settings`)

| Clave | Por defecto | Uso |
|---|---|---|
| `simulate_tracks` | `true` | activa `SimulatedRfidFeed` |
| `track_tick_s` / `track_speedup` | `5` / `20` | avance de trazas |
| `routing_speed_kmh` / `routing_tortuosity` | `25` / `1.4` | ETA SIMULADA |
| `unattended_alert_min` | `15` | crítico sin despacho |
| `cascade.*` | pesos 35/30/15/20, saturaciones 45°/40 mm/3 reportes, radio 300 m, ventana 6 h, cortes 25/50/75 | modelo de cascada |
