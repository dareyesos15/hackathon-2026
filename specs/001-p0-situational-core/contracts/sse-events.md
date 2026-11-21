# Contrato: eventos en vivo `GET /api/v1/stream`

- `Content-Type: text/event-stream`; autenticación por `?token=` (rol `operador_pmu`).
- Cada evento lleva `id` incremental; el cliente reenvía `Last-Event-ID` al reconectar y el
  servidor reenvía los eventos que tenga en memoria (últimos 500).
- Latido: comentario `: ping` cada 15 s.
- Fallback del cliente: tras 2 fallos seguidos, polling a `GET /api/v1/incidents?since=<último
  updated_at>` cada 3 s y aviso visible "Modo de respaldo".

| `event` | `data` | Cuándo |
|---|---|---|
| `report.created` | `{ "report_id", "incident_id", "triage_level", "is_life_threat" }` | tras procesar un reporte nuevo |
| `incident.upserted` | `IncidentSummary` (ver [rest-api.md](rest-api.md)) | incidente creado o recalculado |
| `incident.status_changed` | `{ "incident_id", "status", "actor_role", "at" }` | acción humana |
| `kpi.updated` | `{ "indicators": ["duplicate_detection_rate", …], "cutoff_at" }` | nueva instantánea de KPI |

Ejemplo:

```text
id: 182
event: incident.upserted
data: {"id":"…","lat":5.056,"lon":-75.484,"triage_level":"critico","report_count":4,"trust_score":68,"trust_label":"probable","status":"en_revision","updated_at":"2026-08-10T12:46:01Z"}

```
