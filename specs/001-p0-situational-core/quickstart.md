# Quickstart: validar el núcleo situacional P0

Guía de validación de punta a punta. Contratos en [contracts/](contracts/), modelo en
[data-model.md](data-model.md). Los comandos exactos se confirman al implementar; la salida
esperada es el criterio de aceptación.

## Prerrequisitos

- Docker Desktop corriendo (`docker info` responde) y Docker Compose v2.
- Imágenes construidas **con internet una vez**: `docker compose build`.
- `cp .env.example .env` (tokens de demo y `PII_SALT`).

## 1. Arranque desde cero (SC-001, FR-001)

```bash
docker compose down -v && docker compose up -d
docker compose ps                      # api, web, db en estado healthy
curl -s localhost:8080/api/v1/health   # {"status":"ok","db":"ok",...}
```

Esperado: todo arriba en < 5 min con las imágenes ya construidas; abrir `http://localhost:8080`
muestra la pantalla de inicio con la etiqueta SIMULADO. Repetir con la red Wi-Fi apagada.

## 2. Motor: SMS crítico y deduplicación (US1)

```bash
docker compose exec api python scripts/simulate_sms.py "DACORA ATR MILAN 3 edificio caido cra 23"
docker compose exec api python scripts/simulate_sms.py --from +573110000002 "DACORA COL MILAN 0 se cayo el edificio de la 23 hay gente adentro"
```

Esperado: el primero crea un incidente `critico`, `is_life_threat=true`, Milán, 3 personas; el
segundo responde `joined_existing_incident: true`, `independent_sources: 2` y trust mayor.
Reenviar el primero desde el mismo número no aumenta `independent_sources`.

## 3. Redacción de datos personales (SC-004)

```bash
docker compose exec api pytest tests/integration/test_pii_scenario.py -q
cd apps/web && npm test -- redact        # mismos casos de data/fixtures/pii_cases.json
```

Esperado: 0 coincidencias de celular, cédula, correo o placa en `reports.text_redacted` y
`location_text` tras reproducir todo el escenario; ambas implementaciones pasan los mismos casos.

## 4. Rumor detectado

```bash
docker compose exec api python scripts/simulate_sms.py "reenvia urgente dicen que habra replica de 9 a las 3 pm"
```

Esperado: `rumor_informacion`, `trust_label = posible_falso`, `misinfo_signals` incluye
`reenvia`, `dicen que`, `replica de 9`.

## 5. Tablero en vivo y decisión humana (US2)

1. Abrir `http://localhost:8080/pmu` con el token de `operador_pmu`.
2. Enviar otro SMS (paso 2): aparece en mapa y lista en < 5 s sin recargar.
3. Filtrar "Crítico", abrir el incidente, ver el desglose de las 7 señales.
4. Pulsar "Descartar" sin nota en un incidente crítico → la UI exige nota.
5. Confirmar otro incidente → la bitácora muestra `confirmar`, rol y hora de Colombia.
6. Detener temporalmente el stream (`docker compose restart api`): el tablero muestra "Modo de
   respaldo" y se recupera solo.

## 6. Reproducción del sismo y KPI (US3, SC-002, SC-003, SC-008)

```bash
docker compose exec api python scripts/replay_scenario.py --speed 60      # 12 min
docker compose exec api python scripts/replay_scenario.py --speed 720 --reset  # ~1 min, ensayo
docker compose exec api python scripts/evaluate_kpis.py
```

Esperado en consola y en `http://localhost:8080/pmu/kpi`:
- Duplicados detectados > 90 %, falsos detectados > 90 %.
- Críticos descartados automáticamente = 0; recall de críticos ≥ 98 %.
- "N reportes → M incidentes" y "mapa consolidado en X min simulados".
- Cada cifra con fuente, versión y fecha/hora de corte (hora de Colombia).

## 7. PWA sin conexión (US4, SC-006)

En el portátil:
1. `http://localhost:8080/reportar`, aceptar aviso de privacidad.
2. DevTools → Network → Offline. Crear reporte con "mi cel 3001234567" en la descripción.
3. Ver "guardado, se enviará cuando haya señal"; en IndexedDB el texto ya dice `[TEL]`.
4. Volver a Online: en < 30 s aparece una sola vez en el tablero.

En el celular (misma red): `http://<ip-del-portátil>:8080/reportar`, página abierta → modo
avión → reportar → quitar modo avión → aparece en el tablero. (Sin service worker por ser HTTP;
ver research R4.)

## 8. Calidad (principio IX)

```bash
docker compose exec api ruff check . && docker compose exec api mypy app/core
docker compose exec api pytest -q
cd apps/web && npm run lint && npm run typecheck && npm test
```

Esperado: todo en verde, incluida la prueba de contrato OpenAPI y la que impide que `app/core`
lea la verdad del escenario.
