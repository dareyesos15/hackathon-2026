# Quickstart: validar despacho, alertas y cascada

**Feature**: [spec.md](spec.md) · Contratos: [rest-api.md](contracts/rest-api.md),
[sse-events.md](contracts/sse-events.md) · Modelo: [data-model.md](data-model.md)

## Prerrequisitos

```bash
docker compose up -d --build          # api, web, db; la API migra a 0003 y siembra agencias/recursos
docker compose exec api python scripts/replay_scenario.py --reset --speed 720   # escenario en ~1 min
```

Tokens de demo (`.env.example`): `pmu-demo`, `coe-demo`, `agencia-demo`, `publico-demo`.

```bash
API=http://localhost:8080/api/v1
PMU="Authorization: Bearer pmu-demo"; COE="Authorization: Bearer coe-demo"
AGE="Authorization: Bearer agencia-demo"; PUB="Authorization: Bearer publico-demo"
```

## Pruebas automáticas

```bash
docker compose exec api pytest -q tests/unit/test_dispatch.py tests/unit/test_cascade.py \
  tests/unit/test_alerts.py tests/integration/test_dispatch_api.py tests/integration/test_alerts_api.py
(cd apps/web && npm run typecheck && npm test)
```

Deben cubrir: tabla EMRE completa (SC-002), invariantes de doble despacho e idempotencia
(SC-003, FR-005–007), transiciones de despacho y alertas, `403 coe_only`, `409 version_conflict`,
redacción en mensajes, justificaciones y notas (SC-007), y niveles de cascada con y sin lluvia.

## Escenario 1 — Despacho (US1)

1. Tomar un incidente crítico de personas atrapadas:
   `curl -s -H "$PMU" "$API/incidents?category=personas_atrapadas&limit=1"`.
2. `GET /incidents/{id}` → `suggestion.emre_function = salvamento_seguridad`, agencia sugerida
   `BOMBEROS`, `candidates` ordenados por distancia.
3. `POST /dispatches` con el primer candidato y un `client_uuid` → `201`. Repetir el mismo cuerpo
   → `200` con el mismo despacho (idempotencia).
4. Repetir con otro `client_uuid` y otro recurso, sin refuerzo → `409 active_dispatch_exists`.
   Con `is_reinforcement: true` y justificación → `201`.
5. En el tablero `/pmu/` (rol operador): el incidente muestra "En camino · Cuerpo Oficial de
   Bomberos"; en < 20 s el recurso avanza por los puntos de control y llega (`en_sitio`).
6. En `/agencia/` (rol agencia, agencia Bomberos): marcar "Finalizado" → el recurso vuelve a
   disponible; el operador ve "Listo para cerrar" y aplica `cerrar_atendido`.
7. `GET /metrics/kpi` → `median_time_to_dispatch_min`, `critical_without_dispatch` y
   `double_dispatch_prevented ≥ 1`, cada uno con fuente y corte.

## Escenario 2 — Alertas (US2)

1. Operador crea un borrador para Chipre con canales tablero, mapa público y SMS → `201`,
   `status = borrador`.
2. Crear otro con el mensaje "reenvía: réplica de 9 a las 3 p. m." → `422
   misinformation_confirmation_required` con señales.
3. `POST /alerts/{id}/approve` con `$PMU` → `403 coe_only`.
4. Operador edita el borrador (version 2); el COE intenta aprobar con `version: 1` → `409
   version_conflict`; con `version: 2` → `200`, `status = emitida`, `deliveries` con
   `recipients_count` para SMS.
5. En < 5 s: aviso en `/pmu/` y área sombreada en `/mapa/` (rol público).
   `curl -H "$PUB" $API/alerts/active` no expone autor, señales ni conteos.
6. COE anula con motivo → desaparece del mapa público; `GET /alerts/{id}/events` muestra toda la
   historia.
7. Mensaje con `3001234567` → guardado con `[TEL]`.

## Escenario 3 — Cascada (US3)

1. En `/pmu/`, activar la capa "Efectos en cascada" (etiqueta SIMULADO, leyenda de 4 niveles).
2. Con lluvia 0: las manzanas de ladera con reportes de deslizamiento cercanos están en medio o
   alto; la meseta, en bajo. Tocar una manzana → desglose con 4 factores, `cascade-v1`, corte.
3. Mover el control de lluvia a 40 mm → en < 10 s la capa se recalcula sin recargar y aparecen
   manzanas `muy_alto`.
4. Desde una manzana `muy_alto`, "Crear alerta preventiva" → borrador tipo `deslizamiento` con
   círculo centrado en la manzana; sigue requiriendo aprobación del COE.

## Guion de demo (≤ 2 min, SC-009)

Despachar Bomberos al incidente de Milán → ver el recorrido → subir la lluvia → crear alerta
preventiva desde la manzana en riesgo → cambiar a rol COE y aprobar → mostrar el aviso en el mapa
público. Se agrega a `docs/guion_demo.md` como pasos 6 y 6b.
