# Contrato: eventos en vivo `GET /api/v1/stream` — ampliación

Extiende [001/contracts/sse-events.md](../../001-p0-situational-core/contracts/sse-events.md):
mismo mecanismo (ids incrementales, `Last-Event-ID`, latido de 15 s, respaldo por polling).

Roles: `operador_pmu` y `coe` reciben todos los eventos; `agencia` solo `dispatch.upserted` y
`resource.moved` (filtrado en el servidor).

| `event` | `data` | Cuándo |
|---|---|---|
| `dispatch.upserted` | `DispatchOut` ([rest-api.md](rest-api.md#despachos)) | despacho creado o cambio de estado |
| `resource.moved` | `{ "resource_id", "code", "status", "lat", "lon", "kind", "at", "dispatch_id" }` | nuevo punto de paso (feed simulado o manual) |
| `alert.changed` | `{ "alert_id", "status", "version", "type", "actor_role", "at" }` | crear, editar, aprobar, rechazar, anular |
| `cascade.invalidated` | `{ "reason": "lluvia" \| "reportes", "cutoff_at" }` | nueva lectura de lluvia o reporte relevante (máx. uno cada 3 s) |
| `incident.upserted` (P0) | `IncidentSummary` con `dispatch_status`, `assigned_agency`, `unattended` | también tras cada cambio de despacho |

Respaldo por polling (sin SSE): el tablero consulta además `GET /dispatches?since=` y
`GET /alerts?status=borrador` cada 3 s; el mapa público siempre consulta `GET /alerts/active` cada
4 s.
