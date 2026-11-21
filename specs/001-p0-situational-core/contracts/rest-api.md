# Contrato REST `/api/v1` — P0

Fuente de verdad en ejecución: `GET /openapi.json` (FastAPI). Este documento es el contrato de
diseño; si difieren, se corrige uno de los dos en el mismo commit (principio X).

- Base: `/api/v1` (el Nginx de `web` hace proxy de `/api/` → `api:8000`).
- Autenticación: `Authorization: Bearer <token del rol>`. `401` sin token válido; `403` si el rol
  no tiene permiso.
- Formato: JSON UTF-8; horas ISO 8601 con zona; coordenadas `[lon, lat]` en GeoJSON y
  `lat`/`lon` en cuerpos planos.
- Errores: `{ "detail": "<mensaje en español>", "code": "<clave>" }`.

## Ingesta

### `POST /ingest/report` — roles: `ciudadano`, `operador_pmu`

Request:

```json
{
  "client_uuid": "6f1c…",
  "channel": "pwa",
  "occurred_at": "2026-08-10T12:41:00Z",
  "text": "Edificio caído en la carrera 23 con calle 65, hay gente atrapada",
  "category_hint": "personas_atrapadas",
  "location": { "lat": 5.0561, "lon": -75.4842, "precision": "gps" },
  "barrio": null,
  "people_affected": 3,
  "has_media": false,
  "reporter_contact": "3001234567",
  "consent": true
}
```

- `text` y `reporter_contact` se redactan/hashean antes de persistir; `reporter_contact` nunca se
  guarda ni se devuelve.
- `channel` permitido para `ciudadano`: solo `pwa`. `operador_pmu` puede inyectar `entity`,
  `whatsapp`, `call_123` (canales simulados del escenario).
- `consent` debe ser `true` cuando `channel = pwa` → si no, `422 consent_required`.

Responses:
- `201` `ReportResult` (reporte nuevo procesado).
- `200` `ReportResult` (mismo `client_uuid` ya existía; no se crea otro) — FR-005.
- `422` validación.

`ReportResult`:

```json
{
  "report": { "...Report": "ver abajo" },
  "incident": { "...IncidentSummary": "ver abajo" },
  "joined_existing_incident": true,
  "processing_ms": 37
}
```

### `POST /ingest/sms` — roles: `operador_pmu` (simulador de gateway)

Request: `{ "from": "+573001234567", "body": "DACORA ATR MILAN 3 edificio caido cra 23",
"received_at": "2026-08-10T12:45:00Z" }`. Gramática en [sms-format.md](sms-format.md).
Responses: `201`/`200` `ReportResult` (idempotencia por UUIDv5 de remitente+cuerpo+minuto).
Nunca `4xx` por formato inválido: se ingiere como `sin_clasificar` y va a revisión.

### `POST /ingest/batch` — roles: `ciudadano`

Request: `{ "items": [ <cuerpo de /ingest/report>, … ] }` (máx. 50).
Response `200`: `{ "results": [ { "client_uuid": "…", "status": "created" | "duplicate" |
"error", "report_id": "…", "error": null } ] }`. Un ítem inválido no hace fallar el lote.

## Consulta

### `GET /reports` — roles: `operador_pmu`

Query: `status`, `triage`, `category`, `incident_id`, `since` (ISO), `limit` (≤ 500, defecto
100), `cursor`. Response: `{ "items": [Report], "next_cursor": "…" | null }`.

`Report`:

```json
{
  "id": "…", "client_uuid": "…", "channel": "sms",
  "received_at": "…", "occurred_at": "…",
  "text_redacted": "me llamo [NOMBRE], cel [TEL] …",
  "location_text": "MILAN", "lat": 5.056, "lon": -75.484, "geo_precision": "barrio",
  "manzana_id": "MZ-0123", "category": "personas_atrapadas", "severity": 5,
  "triage_level": "critico", "is_life_threat": true, "people_affected": 3,
  "has_media": false, "misinfo_signals": [], "incident_id": "…", "status": "en_revision",
  "source": "SIMULADO", "version": 1
}
```

### `PATCH /reports/{id}` — roles: `operador_pmu`

Request: `{ "action": "confirmar" | "descartar" | "marcar_duplicado" | "reabrir",
"duplicate_of_incident": "…" | null, "note": "…" }`.
- `descartar` con `is_life_threat` sin `note` → `422 note_required_for_life_threat`.
- Transición inválida → `409 invalid_transition`.
Response `200`: `{ "report": Report, "incident": IncidentSummary, "event": ReportEvent }`.

### `GET /incidents` — roles: `operador_pmu`

Query: `triage`, `status`, `category`, `trust_label`, `since` (por `last_seen` o actualización),
`limit`. Orden: nivel de triaje desc, `first_seen` asc.
Response: `{ "items": [IncidentSummary], "cutoff_at": "…" }`.

`IncidentSummary`:

```json
{
  "id": "…", "lat": 5.056, "lon": -75.484, "category": "personas_atrapadas",
  "triage_level": "critico", "is_life_threat": true, "report_count": 4,
  "independent_sources": 3, "people_affected": 3, "trust_score": 68,
  "trust_label": "probable", "status": "en_revision", "first_seen": "…", "last_seen": "…",
  "manzana_id": "MZ-0123", "barrio": "Milán", "updated_at": "…"
}
```

### `PATCH /incidents/{id}` — roles: `operador_pmu`

Mismo cuerpo que `PATCH /reports/{id}`; aplica la acción a todos los reportes del incidente en
`en_revision` (un evento por reporte). Response `200`: `IncidentDetail`.

### `GET /incidents/{id}` — roles: `operador_pmu`

Response: `IncidentDetail` = `IncidentSummary` + `trust_breakdown` (formato en
[data-model.md](../data-model.md)) + `reports: [Report]` + `events: [ReportEvent]`.

## Mapa y geografía

### `GET /map/manzanas` — roles: `operador_pmu`, `publico`

GeoJSON `FeatureCollection`; `properties`: `manzana_id`, `barrio`, `report_count`,
`incident_count`, `max_triage_level`, `source`, `cutoff_at`. Para `publico`, manzanas con
`report_count < 5` devuelven conteos `null` (k ≥ 5, principio I).

### `GET /geo/barrios` — roles: todos

GeoJSON de barrios (mapa base offline) y lista de nombres para el selector de la PWA.

## Tiempo real

### `GET /stream` — roles: `operador_pmu` (token por query `?token=` porque `EventSource` no envía cabeceras)

Ver [sse-events.md](sse-events.md).

## Métricas

### `GET /metrics/kpi` — roles: `operador_pmu`, `publico`

```json
{
  "items": [
    { "indicator": "duplicate_detection_rate", "label": "Duplicados detectados",
      "value": 93.4, "unit": "%", "source": "evaluate_kpis.py", "version": 7,
      "cutoff_at": "2026-08-10T19:34:00Z", "simulated": true },
    { "indicator": "reports_received", "label": "Reportes recibidos", "value": 248,
      "unit": "conteo", "source": "api", "version": 248, "cutoff_at": "…", "simulated": true }
  ]
}
```

Indicadores P0: `reports_received`, `incidents_consolidated`, `duplicate_detection_rate`,
`fake_detection_rate`, `false_positive_rate`, `critical_auto_discarded`, `critical_recall`,
`time_to_consolidated_map_min`, `p95_processing_ms`. Definiciones en
[research.md](../research.md) R8 y en `docs/diccionario_indicadores.md`.

### `POST /metrics/snapshots` — roles: `operador_pmu` (lo usa `evaluate_kpis.py`)

Request: `{ "items": [ { "indicator", "value", "unit", "source", "cutoff_at", "details" } ] }`.
Response `201`. Emite evento SSE `kpi.updated`.

## Salud

### `GET /health` — sin autenticación

`{ "status": "ok", "db": "ok", "similarity_provider": "tfidf", "version": "0.1.0" }`.
