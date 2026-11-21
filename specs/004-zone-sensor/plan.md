# Plan: Sensor de zonas inseguras (SIMULADO)

- **Datos** (migración `0005_zone_sensors`): `zone_sensors` (código, etiqueta, punto, rumbo,
  alcance, semiapertura, incidente, estado, batería, última señal), `zone_sensor_events`
  (tipo, detector, distancia, ángulo, tarjeta, autorizada, incidente cercano, atención) y
  `rfid_badges` (credenciales autorizadas por agencia, SIMULADAS).
- **Motor** `app/core/zone_sensor.py` (puro): `in_cone`, `classify(reading, sensor, badges)`.
- **Adaptador** `app/adapters/zone_sensor.py`: `SimulatedZoneSensorFeed` (tarea asyncio en el
  `lifespan`, como el feed RFID de recursos).
- **API** `/api/v1/sensors/zones`: GET sensores, POST instalar, POST `{id}/readings` (punto de
  integración con el dispositivo real), GET `events`, POST `events/{id}/ack`. Evento SSE
  `zone.event`; al confirmar un incidente se recalcula su trust y se publica `incident.upserted`.
- **Trust**: `refresh_trust` consulta si hay intrusión con ambos detectores ≤ 150 m / 3 h.
- **Web**: capa de conos en `Mapa`, pestaña **Zonas** en el tablero PMU (alarmas, sensores,
  instalar en incidente seleccionado). Consulta cada 4 s.
- Verificación: sin pruebas nuevas (plazo); ruff, mypy, tsc, eslint y un recorrido manual.
