# Data Model: Núcleo situacional P0 de Dacora

**Fecha**: 2026-11-20 · **Plan**: [plan.md](plan.md) · **Spec**: [spec.md](spec.md)

Convenciones (constitución, principio V): toda tabla tiene `id UUID` (PK), `created_at
timestamptz`, `source text`, `version int`. Geometrías en EPSG:4326. Horas en UTC en la base y
`America/Bogota` en la UI. Solo el servicio `api` accede a estas tablas.

## Enumeraciones

| Enum | Valores |
|---|---|
| `channel` | `pwa`, `sms`, `whatsapp`, `call_123`, `scraping`, `entity`, `lora` |
| `category` | `personas_atrapadas`, `heridos`, `colapso_estructura`, `dano_estructural`, `incendio`, `fuga_gas`, `deslizamiento`, `via_bloqueada`, `servicios_caidos`, `necesidad_albergue`, `necesidad_ayuda`, `persona_desaparecida`, `sismo_sentido`, `rumor_informacion`, `sin_clasificar` |
| `triage_level` | `critico`, `alto`, `medio`, `bajo` |
| `geo_precision` | `gps`, `address`, `barrio`, `none` |
| `report_status` | `nuevo`, `en_revision`, `verificado`, `descartado`, `duplicado`, `atendido` |
| `incident_status` | `abierto`, `en_revision`, `verificado`, `descartado`, `atendido` |
| `trust_label` | `verificado` (≥ 75), `probable` (50–74), `sin_verificar` (25–49), `posible_falso` (< 25) |
| `role` | `ciudadano`, `operador_pmu`, `publico` (P0); `coe`, `inspector`, `agencia` (reservados P1) |

## Entidades

### Report (`reports`) — solo-agregar

| Campo | Tipo | Reglas |
|---|---|---|
| `client_uuid` | UUID | **UNIQUE**; generado por el cliente; idempotencia (FR-005). Para SMS sin UUID: UUIDv5 de (`reporter_hash`, texto, minuto) |
| `channel` | channel | requerido |
| `received_at` | timestamptz | lo asigna la API |
| `occurred_at` | timestamptz | del cliente o = `received_at`; en el escenario, hora simulada |
| `text_redacted` | text | ≤ 2.000 caracteres; **nunca** texto sin redactar (FR-006) |
| `location_text` | text NULL | redactado también |
| `geom` | POINT NULL | requerido si `geo_precision ≠ none` |
| `geo_precision` | geo_precision | |
| `manzana_id` | FK → manzanas NULL | por punto en polígono |
| `category` | category | |
| `severity` | smallint 1–5 | |
| `triage_level` | triage_level | matriz CLAUDE.md §7.2 |
| `is_life_threat` | bool | `true` ⇔ `triage_level = critico` por categoría de riesgo vital |
| `people_affected` | int NULL | ≥ 0 |
| `has_media` | bool | |
| `media_path` | text NULL | ruta interna; nunca expuesta al rol `publico` |
| `reporter_hash` | char(64) NULL | HMAC-SHA256(`PII_SALT`, dato normalizado) (FR-007) |
| `misinfo_signals` | text[] | palabras/reglas que dispararon señales |
| `incident_id` | FK → incidents | asignado por la agrupación |
| `status` | report_status | ver máquina de estados |
| `processing_ms` | int | para verificar < 1 s (FR-021) |

Índices: `client_uuid` único, GIST(`geom`), (`category`, `occurred_at`), `incident_id`.

### ReportEvent (`report_events`) — bitácora solo-agregar

| Campo | Tipo | Reglas |
|---|---|---|
| `report_id` | FK NULL | uno de `report_id` / `incident_id` requerido |
| `incident_id` | FK NULL | |
| `actor_role` | role o `sistema` | |
| `action` | text | `ingerido`, `agrupado`, `confirmar`, `descartar`, `marcar_duplicado`, `reabrir` |
| `payload` | JSONB | p. ej. `{ "duplicate_of": "<incident_id>", "nota": "…" }` (sin PII) |
| `at` | timestamptz | |

Sin UPDATE ni DELETE (permisos de la aplicación + prueba).

### Incident (`incidents`)

| Campo | Tipo | Reglas |
|---|---|---|
| `centroid` | POINT | promedio ponderado por precisión de sus reportes |
| `category` | category | la del primer reporte de mayor nivel |
| `triage_level` | triage_level | máximo de sus reportes |
| `is_life_threat` | bool | OR de sus reportes |
| `report_count` | int | |
| `independent_sources` | int | `reporter_hash` distintos (+ reportes sin hash por canal distinto) (FR-016) |
| `people_affected` | int NULL | máximo reportado (completa datos, FR-015) |
| `trust_score` | smallint 0–100 | |
| `trust_label` | trust_label | |
| `trust_breakdown` | JSONB | ver abajo |
| `first_seen`, `last_seen` | timestamptz | por `occurred_at` |
| `status` | incident_status | |
| `manzana_id` | FK NULL | |

`trust_breakdown` (cada señal con puntos y explicación legible):

```json
{
  "canal":                 { "puntos": 18.0, "max": 30, "detalle": "SMS (0,5) y entidad oficial (0,9): se toma el mejor" },
  "fuentes_independientes":{ "puntos": 12.5, "max": 25, "detalle": "2 de 4 fuentes" },
  "consistencia_fisica":   { "puntos": 10.0, "max": 20, "detalle": "sin dato de sensor (neutro)" },
  "precision_geografica":  { "puntos": 5.0,  "max": 10, "detalle": "barrio" },
  "desinformacion":        { "puntos": 0.0,  "max": 0,  "min": -15, "detalle": "sin señales" },
  "evidencia":             { "puntos": 0.0,  "max": 5,  "detalle": "sin foto" },
  "sensor_campo":          { "puntos": 0.0,  "max": 10, "detalle": "sin sensor (P1)" },
  "total": 45.5, "etiqueta": "sin_verificar", "version_modelo": "trust-v1"
}
```

### Manzana (`manzanas`)

`id` (text, código sintético `MZ-####`), `geom` POLYGON, `barrio`, `comuna`, `seismic_zone`,
`population`, `buildings_pre_1984_pct`, `source = "SIMULADO"`.

### Place (`places`) — gazetteer

`name`, `aliases text[]` (normalizados sin tildes), `kind` (`barrio`, `comuna`, `via`,
`referencia`), `geom` POINT, `barrio`, `source = "SIMULADO"`. Se carga desde
`data/geo/gazetteer.csv` al arrancar.

### MetricSnapshot (`metrics_snapshots`)

`indicator` (clave del diccionario de indicadores), `value numeric`, `unit` (`%`, `conteo`,
`min`), `source` (p. ej. `evaluate_kpis.py`, `api`), `version`, `cutoff_at`, `details JSONB`.
Solo-agregar; el panel muestra la última por `indicator`.

### Verdad del escenario (fuera de la base)

`data/seed/ground_truth.json`: `{ client_uuid: { "label": "unique" | "duplicate" | "fake",
"duplicate_of": client_uuid | null, "event_id": "...", "is_critical": bool } }`. Nunca se carga
en la base ni la lee `app/core`.

## Relaciones

```text
Incident 1 ── * Report * ── 0..1 Manzana
Report   1 ── * ReportEvent
Incident 1 ── * ReportEvent
Place (independiente, usado por geo.py)
MetricSnapshot (independiente)
```

## Máquinas de estado

### Report

```text
nuevo ──(sistema: agrupado)──▶ en_revision
en_revision ──(operador: confirmar)──▶ verificado
en_revision ──(operador: descartar)──▶ descartado
en_revision ──(operador: marcar_duplicado)──▶ duplicado
verificado | descartado | duplicado ──(operador: reabrir)──▶ en_revision
verificado ──(P1 despacho)──▶ atendido
```

Reglas:
- El actor `sistema` **solo** puede llevar a `en_revision`. Nunca a `descartado` ni `duplicado`
  (FR-013; un reporte agrupado sigue en `en_revision` dentro de su incidente).
- Si `is_life_threat = true`, `descartar` exige rol `operador_pmu` **y** una nota no vacía.
- Cada transición crea un `ReportEvent`.

### Incident

`abierto → en_revision` al llegar el segundo reporte o al abrirlo un operador;
`confirmar/descartar` del operador se propaga a sus reportes en `en_revision` (cada uno con su
evento); al descartar o reabrir un reporte se recalculan `report_count`, `independent_sources`,
`trust_*` (FR-020).

## Reglas de validación (resumen)

| Regla | Origen |
|---|---|
| `text_redacted` no contiene patrones de celular, cédula, correo ni placa | FR-006, SC-004 (prueba sobre todo el escenario) |
| SMS ≤ 160 caracteres; si excede, se procesa y se marca `sin_clasificar` + revisión | FR-004, edge cases |
| `people_affected` entero ≥ 0 | FR-004 |
| Coordenadas dentro del rectángulo de Manizales (lat 4,95–5,15; lon −75,62 – −75,38); fuera → `geo_precision = none` | FR-012 |
| `occurred_at` ≤ `received_at` + 5 min | consistencia |
| Agrupación: misma categoría o compatible, ≤ 250 m (600 m si barrio), ≤ 3 h, similitud ≥ umbral | FR-014 |

Categorías compatibles para agrupar: {`personas_atrapadas`, `colapso_estructura`,
`dano_estructural`, `heridos`}; {`fuga_gas`, `incendio`}; {`deslizamiento`, `via_bloqueada`};
el resto solo consigo misma.
