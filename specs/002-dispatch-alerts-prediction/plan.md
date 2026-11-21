# Implementation Plan: Despacho, alertas y predicción de efectos en cascada

**Branch**: `002-dispatch-alerts-prediction` (spec creada en `fix/remove-some-features`) | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-dispatch-alerts-prediction/spec.md`

## Summary

Bloque 5 de `docs/arquitectura_actual.png` sobre el núcleo P0 ya construido. El servicio `api`
gana tres módulos de dominio:

- **Despacho** (`core/dispatch.py`): sugiere la agencia por la tabla EMRE, ordena recursos por
  distancia con una ETA SIMULADA, crea despachos idempotentes y garantiza en la base de datos "un
  despacho activo por recurso" y "sin doble despacho sin refuerzo justificado". Registra puntos de
  paso tipo RFID, que un feed simulado dentro de la API hace avanzar en vivo.
- **Alertas** (`core/alerts.py`): borrador → aprobación exclusiva del COE con control de versión →
  emisión simulada por tablero, mapa público y SMS a cuadrillas (solo conteos). Redacción de datos
  personales y advertencia de desinformación reutilizando el motor del P0.
- **Cascada** (`core/cascade.py`): nivel de riesgo por manzana, explicable con cuatro factores:
  pendiente SIMULADA, lluvia de un feed SIMULADO, intensidad sísmica neutra y reportes cercanos
  medidos con el reloj del escenario.

El servicio `web` agrega capas y paneles al tablero `/pmu/` (despacho, recorridos, bandeja del COE,
capa de cascada), la pantalla `/agencia/` y las alertas vigentes en `/mapa/`. Todo sigue corriendo
con `docker compose up`, sin internet.

## Technical Context

**Language/Version**: Python 3.12 (`api`); TypeScript 5.x sobre Node 22 LTS (`web`). Sin cambios.

**Primary Dependencies**: las del P0 (FastAPI, Pydantic v2, SQLAlchemy 2 async + GeoAlchemy2,
Alembic, Shapely; Next.js export estático, MapLibre GL, Tailwind, `openapi-fetch`). **Sin
dependencias nuevas**: el círculo de la alerta es un polígono de 32 lados calculado con
Shapely y una conversión local de metros a grados (escala por `cos(lat)`, error < 0,1 % en
Manizales, sin `pyproj`); en el navegador se dibuja como GeoJSON.

**Storage**: PostgreSQL 16 + PostGIS. Migración `0003_dispatch_alerts_cascade.py` con 8 tablas
nuevas y la ampliación de la CHECK de `report_action` ([data-model.md](data-model.md)). Catálogo
sembrado desde `data/seed/resources.json`.

**Testing**: `pytest` (unitarias de `dispatch`, `alerts`, `cascade`; integración HTTP con la base
para invariantes de concurrencia e idempotencia; contrato OpenAPI); `vitest` (formateo de estados,
construcción de áreas, filtros de capas). Prueba de Habeas Data extendida a mensajes de alerta,
justificaciones y notas.

**Target Platform**: igual que P0 (Docker Compose en portátil macOS arm64 / Linux amd64 sin
internet; Chrome y Safari recientes).

**Project Type**: aplicación web, 2 servicios principales (`api` REST + `web` estático/PWA).

**Performance Goals**:
- Sugerencia de despacho < 300 ms.
- Despacho y puntos de paso visibles en el tablero < 5 s (SC-004).
- Alerta emitida visible en el tablero y en el mapa público < 5 s (SC-006).
- Capa de cascada recalculada < 10 s tras un cambio de lluvia (SC-008); el cálculo de 564
  manzanas debe tomar < 100 ms.

**Constraints**:
- Sin internet y un único worker de Uvicorn: el feed RFID simulado es una tarea asyncio del
  `lifespan`, igual que el bus en memoria.
- Sin números de teléfono en ninguna tabla.
- Solo el COE emite alertas, y la base lo refuerza con una CHECK sobre `approved_by_role`.
- El público no ve recursos, despachos ni incidentes.

**Scale/Scope**: 10 agencias, 24 recursos, ~60–120 incidentes, decenas de despachos y alertas por
demo, 564 manzanas, 1 estación de lluvia. Roles activos: + `coe`, `agencia` (5 en total). Una
pantalla nueva (`/agencia/`) y paneles nuevos en `/pmu/` y `/mapa/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo lo cumple el diseño | Estado |
|---|---|---|
| I. Habeas Data | Mensajes, justificaciones y notas pasan por `privacy.redact` antes de guardar. SMS sin números (solo `recipients_count`). `GET /alerts/active` para `publico` sin autor ni detalles. Público sin recursos ni despachos (FR-033). Prueba automática extendida | ✅ |
| II. Offline-first | Sin servicios externos. Ruteo, RFID, lluvia, SMS y pendiente con implementaciones SIMULADAS locales. El tablero mantiene el respaldo por polling para los nuevos eventos | ✅ |
| III. Humano decide | Despacho, cierre del incidente y alertas son acciones humanas con bitácora (`report_events`, `alert_events`). Solo `coe` aprueba, rechaza o anula (403 + CHECK). La cascada nunca despacha ni alerta (FR-031). Finalizar un despacho no cierra el incidente | ✅ |
| IV. Datos sintéticos | Catálogo de recursos, trazas, ETA, lluvia y pendiente etiquetados `SIMULADO` en `source` y en la interfaz. Los KPI de despacho se calculan en vivo | ✅ |
| V. Trazabilidad | Columnas comunes en las tablas nuevas. KPI nuevos con fuente y corte, y en `docs/diccionario_indicadores.md`. Cascada con `model_version`, `cutoff_at` y `scenario_clock`. Recursos con `code` estable | ✅ |
| VI. Adaptadores | `RoutingProvider` (ERIS después), `TrackFeed` (lector RFID real después), `AlertGateway` (SMS real después), `TerrainProvider` (modelo de elevación después), `HazardProvider` (RAMAN después) | ✅ |
| VII. Simplicidad | P0 terminado (salvo el video de respaldo, que no es código). Sin dependencias nuevas, sin plugin de dibujo, sin persistir la cascada, una sola estación de lluvia, círculo en lugar de polígono libre | ✅ |
| VIII. Español de Colombia | Estados, mensajes de error y etiquetas en es-CO; identificadores en inglés | ✅ |
| IX. Calidad | ruff, black y mypy (agrega `dispatch`, `alerts` y `cascade` a los módulos críticos); eslint, prettier y TS strict; pruebas por historia (ver quickstart) | ✅ |
| X. Dos servicios REST | Toda la lógica nueva vive en `api`. `web` solo consume REST + SSE. Tipos regenerados desde `/openapi.json` en el mismo commit del cambio de modelos | ✅ |
| Commits atómicos | Un commit por artefacto, migración, módulo y pantalla (ver `tasks.md`) | ✅ |

**Resultado**: pasa sin violaciones.

## Project Structure

### Documentation (this feature)

```text
specs/002-dispatch-alerts-prediction/
├── plan.md              # Este archivo
├── research.md          # Fase 0: decisiones R1–R16
├── data-model.md        # Fase 1: tablas, enums, transiciones
├── quickstart.md        # Fase 1: validación de punta a punta
├── contracts/
│   ├── rest-api.md      # rutas nuevas y cambios a las del P0
│   └── sse-events.md    # eventos nuevos del stream
├── checklists/requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
services/api/
├── alembic/versions/0003_dispatch_alerts_cascade.py   # nuevo
├── app/
│   ├── domain.py                 # + enums (EmreFunction, ResourceStatus, DispatchStatus, AlertStatus, …)
│   ├── models.py                 # + Agency, Resource, Dispatch, ResourceTrack, Alert, AlertEvent, AlertDelivery, RainReading
│   ├── schemas.py                # + DispatchOut, DispatchSuggestion, ResourceOut, AlertOut, CascadeFeature…
│   ├── config.py                 # + simulate_tracks, routing_*, unattended_alert_min, cascade.*
│   ├── seed.py                   # + siembra de agencias y recursos
│   ├── serializers.py            # IncidentSummary + dispatch_status / assigned_agency / unattended
│   ├── core/
│   │   ├── dispatch.py           # nuevo: tabla EMRE, sugerencia, creación, transiciones, puntos de paso
│   │   ├── alerts.py             # nuevo: ciclo de vida, versión, área, redacción, desinformación
│   │   ├── cascade.py            # nuevo: factores, niveles, caché, reloj del escenario
│   │   └── review.py             # + acción cerrar_atendido
│   ├── adapters/
│   │   ├── routing.py            # nuevo: RoutingProvider + StraightLineRouting
│   │   ├── tracks.py             # nuevo: TrackFeed + SimulatedRfidFeed (tarea del lifespan)
│   │   ├── alert_gateway.py      # nuevo: AlertGateway + SimulatedGateway
│   │   └── terrain.py            # nuevo: TerrainProvider + SyntheticTerrain
│   ├── routers/
│   │   ├── dispatch.py           # nuevo: /agencies, /resources, /resources/{id}/tracks, /dispatches
│   │   ├── alerts.py             # nuevo: /alerts…
│   │   ├── cascade.py            # nuevo: /sensors/rain, /map/cascade
│   │   ├── incidents.py, map.py, stream.py, metrics.py, demo.py, review.py   # roles, campos y KPI
│   └── main.py                   # routers y arranque del feed simulado
└── tests/
    ├── unit/test_dispatch.py, test_alerts.py, test_cascade.py
    └── integration/test_dispatch_api.py, test_alerts_api.py, test_cascade_api.py

apps/web/
├── lib/
│   ├── session.ts                # + roles coe y agencia
│   ├── labels.ts                 # + etiquetas de estados, funciones EMRE, niveles de cascada
│   ├── live.ts                   # + eventos dispatch/resource/alert/cascade y respaldo
│   └── api/openapi.json, schema.d.ts   # regenerados
├── components/
│   ├── Mapa.tsx                  # + capas: recursos, recorridos, áreas de alerta, cascada
│   ├── DetalleIncidente.tsx      # + sección Despacho (sugerencia, candidatos, refuerzo, estados)
│   ├── PanelDespacho.tsx         # nuevo
│   ├── EditorAlerta.tsx          # nuevo: tipo, área (barrios/círculo), mensaje, canales, advertencias
│   ├── BandejaAlertas.tsx        # nuevo: borradores; aprobar/rechazar/anular (COE)
│   ├── AvisoAlerta.tsx           # nuevo: alerta vigente destacada (PMU y público)
│   └── CapaCascada.tsx           # nuevo: interruptor, leyenda, control de lluvia, desglose
├── app/pmu/TableroPmu.tsx        # integra paneles; acepta coe
├── app/agencia/                  # nuevo: page.tsx + PanelAgencia.tsx
├── app/mapa/MapaPublico.tsx      # + alertas vigentes (consulta cada 4 s)
└── app/page.tsx                  # + tarjetas COE y Agencia

data/seed/resources.json          # nuevo: agencias y recursos SIMULADOS
scripts/replay_scenario.py        # + --rain (curva de lluvia opcional)
docs/diccionario_indicadores.md   # + 3 KPI de despacho
docs/guion_demo.md                # + pasos de despacho, alerta y cascada
```

**Structure Decision**: se conserva la estructura del P0 (`services/api` + `apps/web`). Cada
historia agrega un módulo de dominio en `core/`, su router y sus adaptadores, de modo que US1, US2
y US3 se implementan y prueban por separado y en ese orden de prioridad. La única pieza compartida
es la migración `0003`, que se hace primero.

## Post-Design Constitution Re-check

Revisado tras escribir [data-model.md](data-model.md) y los [contratos](contracts/):

- **Principio I**: los contratos no exponen datos de contacto. `alert_deliveries` solo guarda
  conteos. El GeoJSON público de alertas omite autor, señales y entregas.
- **Principio III**: las transiciones que dependen del rol están en el contrato (403 `coe_only`)
  y en la base (CHECK de `approved_by_role`). Ninguna transición automática cierra incidentes ni
  emite alertas: el feed RFID solo mueve el despacho de `en_camino` a `en_sitio`, lo que registra
  un hecho, no una decisión.
- **Principio X**: no hay lógica en `web`. Los paneles nuevos usan solo rutas del contrato.

**Resultado**: sigue sin violaciones; no hace falta la sección Complexity Tracking.
