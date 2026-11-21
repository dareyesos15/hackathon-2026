# Contrato REST `/api/v1` — Despacho, alertas y cascada

Extiende [001/contracts/rest-api.md](../../001-p0-situational-core/contracts/rest-api.md): misma
base `/api/v1`, autenticación `Bearer` por rol, errores `{ "detail", "code" }` en español, horas
ISO 8601 con zona. La fuente de verdad en ejecución es `/openapi.json`; los tipos del frontend se
regeneran en el mismo commit que cambie un modelo (principio X).

## Cambios a rutas existentes

| Ruta | Cambio |
|---|---|
| `GET /incidents`, `GET /incidents/{id}` | roles: `operador_pmu`, **`coe`**. `IncidentSummary` agrega `dispatch_status`, `assigned_agency`, `unattended`. `IncidentDetail` agrega `dispatches[]` y `suggestion` |
| `PATCH /incidents/{id}` | roles: `operador_pmu`, **`coe`**. Nueva acción `cerrar_atendido` (`verificado → atendido`) |
| `GET /map/manzanas` | roles: + `coe` |
| `GET /stream` | roles: `operador_pmu`, **`coe`**, **`agencia`** (la agencia solo recibe eventos de despacho) |
| `GET /metrics/kpi` | + `critical_without_dispatch`, `median_time_to_dispatch_min`, `double_dispatch_prevented` |
| `POST /demo/reset` | también limpia despacho, alertas y lluvia; recursos vuelven a su base |

`suggestion` en `IncidentDetail`:

```json
{
  "emre_function": "salvamento_seguridad",
  "emre_function_label": "1. Salvamento y seguridad",
  "suggested_agency": { "id": "…", "code": "BOMBEROS", "name": "Cuerpo Oficial de Bomberos" },
  "alternative_agencies": [{ "id": "…", "code": "DEFENSA_CIVIL", "name": "Defensa Civil" }],
  "candidates": [
    {
      "resource": { "id": "…", "code": "BOM-M3", "label": "Máquina 3 · Estación Centro", "type": "maquina_extincion", "status": "disponible" },
      "agency_code": "BOMBEROS",
      "distance_m": 1840,
      "eta_min": 6.2,
      "source": "SIMULADO"
    }
  ],
  "fallback_used": false
}
```

- `candidates`: recursos `disponible` de la agencia sugerida ordenados por `distance_m`; si no hay,
  los de las agencias alternativas y `fallback_used = true` (FR-003, escenario US1-6).
- Categorías sin función (`sismo_sentido`, `rumor_informacion`, `sin_clasificar`):
  `emre_function = null` y `candidates` con todos los recursos disponibles.

## Agencias y recursos

### `GET /agencies` — roles: `operador_pmu`, `coe`, `agencia`

`{ "items": [{ "id", "code", "name", "emre_function", "resources_available", "resources_total" }] }`

### `GET /resources?agency_id=&status=` — roles: `operador_pmu`, `coe`, `agencia`

`{ "items": [ResourceOut], "cutoff_at" }` con `ResourceOut = { id, code, label, type, status,
agency_id, agency_code, lat, lon, last_seen_at, active_dispatch_id, source }`.

### `GET /resources/{id}/tracks` — roles: `operador_pmu`, `coe`, `agencia`

`{ "items": [{ "id", "kind", "origin", "lat", "lon", "at", "dispatch_id" }] }` ordenados por `at`.

### `POST /resources/{id}/tracks` — roles: `agencia`, `operador_pmu`

Registro manual o de un lector real.

```json
{ "kind": "control", "lat": 5.0612, "lon": -75.4990, "at": "2026-11-21T15:02:10-05:00" }
```

- `201` → punto de paso; si `kind = llegada` y hay despacho `en_camino`, el despacho pasa a
  `en_sitio`. `422 out_of_area` si el punto no está en Manizales.

## Despachos

### `POST /dispatches` — roles: `operador_pmu`, `coe`

```json
{
  "client_uuid": "0b9e…",
  "incident_id": "…",
  "resource_ids": ["…"],
  "is_reinforcement": false,
  "justification": null
}
```

| Respuesta | Cuándo |
|---|---|
| `201` `{ "items": [DispatchOut] }` | despacho creado (uno por recurso) |
| `200` mismo cuerpo | `client_uuid` repetido (idempotencia, FR-007) |
| `409 active_dispatch_exists` + `{ "active": [DispatchOut] }` | el incidente ya tiene despacho activo y no es refuerzo justificado (FR-006) |
| `409 resource_unavailable` + `{ "resource_ids": [...] }` | algún recurso no está `disponible` (FR-005) |
| `422 justification_required` | `is_reinforcement = true` sin justificación |
| `422 incident_closed` | incidente `descartado` o `atendido` |

`DispatchOut = { id, incident_id, resource: ResourceOut, agency: {id, code, name}, emre_function,
suggested, is_reinforcement, justification, status, eta_at, distance_m, created_by_role,
created_at, arrived_at, closed_at, close_note, source }`.

### `GET /dispatches?incident_id=&agency_id=&status=&since=` — roles: `operador_pmu`, `coe`, `agencia`

`{ "items": [DispatchOut], "cutoff_at" }`. Con rol `agencia`, `agency_id` es obligatorio.

### `PATCH /dispatches/{id}` — roles: `agencia`, `operador_pmu`, `coe`

```json
{ "action": "llegada" | "finalizar" | "cancelar" | "fuera_de_servicio", "note": "…" }
```

- `llegada`: `en_camino → en_sitio`. `finalizar`: `en_sitio → finalizado`.
- `cancelar` (solo `operador_pmu`/`coe`, `note` obligatoria): `en_camino|en_sitio → cancelado`.
- `fuera_de_servicio` (`note` obligatoria): `→ cancelado` y recurso `fuera_de_servicio`.
- `409 invalid_transition` si el estado no lo permite. `note` se redacta (FR-012, SC-007).

## Alertas

### `POST /alerts` — roles: `operador_pmu`, `coe`

```json
{
  "type": "evacuacion",
  "area": { "barrios": ["Chipre"] },
  "message": "Evacuación preventiva de viviendas de ladera en Chipre. Diríjase al punto de encuentro del parque.",
  "channels": ["tablero", "mapa_publico", "sms_cuadrillas"],
  "origin_incident_id": null,
  "origin_manzana_id": null,
  "confirm_misinformation": false
}
```

`area` es `{ "barrios": [..] }` o `{ "circle": { "lat", "lon", "radius_m" } }` (100–3 000 m).

| Respuesta | Cuándo |
|---|---|
| `201` `AlertOut` (`status = borrador`, `version = 1`) | creado |
| `422 misinformation_confirmation_required` + `{ "signals": [...] }` | señales de desinformación y `confirm_misinformation` falso (FR-022) |
| `422 sms_too_long` | `sms_cuadrillas` en canales y mensaje > 160 caracteres |
| `422 area_required` / `422 out_of_area` | sin área o fuera del casco urbano |

`AlertOut = { id, type, status, version, area (GeoJSON MultiPolygon), area_barrios, area_circle,
message, channels, misinfo_signals, origin_incident_id, origin_manzana_id, created_by_role,
approved_by_role, created_at, emitted_at, closed_at, close_reason, deliveries: [{channel,
recipients_count, at}], source }`. El mensaje devuelto ya está redactado.

### `PATCH /alerts/{id}` — roles: `operador_pmu`, `coe`

Edita un borrador (mismos campos que `POST`, todos opcionales, más `version` obligatorio).
`409 version_conflict` si `version` no es la actual; `409 not_editable` si no es borrador.

### `GET /alerts?status=` — roles: `operador_pmu`, `coe`

`{ "items": [AlertOut], "cutoff_at" }`, más recientes primero.

### `GET /alerts/{id}/events` — roles: `operador_pmu`, `coe`

Bitácora de la alerta: `{ "items": [{ "action", "actor_role", "alert_version", "payload", "at" }] }`.

### `POST /alerts/{id}/approve` — rol: `coe`

`{ "version": 3 }` → `200 AlertOut` (`emitida`, con `deliveries`).
`409 version_conflict` si cambió; `409 not_pending` si no es borrador.
Otro rol → `403` `{ "detail": "Solo el COE puede aprobar alertas oficiales", "code": "coe_only" }`.

### `POST /alerts/{id}/reject` — rol: `coe`

`{ "version": 3, "reason": "…" }` → `200 AlertOut` (`rechazada`). `reason` obligatoria.

### `POST /alerts/{id}/cancel` — rol: `coe`

`{ "reason": "…" }` → `200 AlertOut` (`anulada`). Solo desde `emitida`.

### `GET /alerts/active` — roles: `publico`, `operador_pmu`, `coe`, `agencia`

Alertas `emitida`. Para `publico`, solo las que incluyen `mapa_publico` y solo los campos
`{ id, type, message, area, emitted_at, source }` (FR-033). Respuesta GeoJSON
`FeatureCollection` con `cutoff_at`.

## Lluvia y cascada

### `POST /sensors/rain` — roles: `operador_pmu`, `coe`

`{ "mm_3h": 40.0, "station_code": "LLUVIA-URB-01" }` → `201 { id, station_code, mm_3h, at,
source }`. Publica `cascade.invalidated`.

### `GET /sensors/rain/latest` — roles: `operador_pmu`, `coe`

Última lectura o `null`.

### `GET /map/cascade?min_level=` — roles: `operador_pmu`, `coe`

GeoJSON `FeatureCollection` de manzanas con propiedades: `manzana_id`, `barrio`, `level`,
`score`, `slope_deg`, `breakdown`, `model_version`, `source = "SIMULADO"`; y a nivel de colección
`cutoff_at`, `scenario_clock`, `rain_mm_3h`. `min_level` filtra (`alto` devuelve alto y muy alto).

```json
"breakdown": {
  "pendiente": { "puntos": 31.1, "max": 35, "detalle": "40° (ladera, SIMULADO)" },
  "lluvia": { "puntos": 30.0, "max": 30, "detalle": "40 mm en 3 h (LLUVIA-URB-01, SIMULADO)" },
  "sismo": { "puntos": 7.5, "max": 15, "detalle": "sin dato de sensor (neutro)" },
  "reportes_cercanos": { "puntos": 13.3, "max": 20, "detalle": "2 reportes a ≤ 300 m en 6 h" }
}
```
