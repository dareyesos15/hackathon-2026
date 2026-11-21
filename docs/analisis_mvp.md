# Análisis de brechas y ruta al MVP del pitch

> Estado revisado: `main` en `36e44fe` (21 nov 2026, tras fusionar `feat/006-recovery`).
> Referencias: [arquitectura objetivo](arquitectura.jpeg) y [arquitectura actual](arquitectura_actual.png).
> Leyenda: ✅ verificado en el código · 🟡 parcial o simulado · ❌ no existe en `main` · ❓ suposición, requiere confirmación.

## 1. Decisión sobre el módulo de recuperación

Había **dos implementaciones** del módulo 6:

- `feat/006-recovery` (David Reyes), **ya fusionada en `main`**: inspecciones con semáforo por predio, censo
  único con hash de hogar, ayudas con regla de duplicidad, albergues SIMULADOS, exportación CSV al RUD,
  resumen público con k ≥ 5 y pantalla `/recuperacion` enlazada desde el tablero PMU (`specs/003-recovery`).
- `feat/p1-geo-trust-recovery-ui` (loterini0): otro diseño (`recovery_records` JSONB) que choca con el de
  `main` en `routers/recovery.py` y en la migración `0004`.

**Decisión (21 nov):** se usa el módulo de `main` y **se descarta por completo** la rama de loterini0.
Conviene avisarle para que no siga invirtiendo tiempo en ella.

Verificación local del `main` actual: `ruff` y `mypy` sin errores; `tsc`, `eslint` y `vitest` (28 pruebas) en verde.
`pytest tests/unit`: 133 pasan y 5 fallan en `test_privacy.py::test_redact_matches_shared_fixture`
(ya fallaban antes de la recuperación; parece un problema de codificación en Windows, ❓ confirmar en Linux/Docker).
El módulo de recuperación **no tiene pruebas** (decisión registrada en `specs/003-recovery/plan.md`).

## 2. Estado por bloque de la arquitectura

| Bloque | Componente | Estado | Evidencia |
|---|---|---|---|
| 1. Captación | PWA ciudadana offline (Dexie + outbox) | ✅ | `apps/web/lib/db.ts`, `app/reportar/` |
| | SMS compacto `DACORA …` | 🟡 simulado | `POST /ingest/sms`, `core/sms.py`, `scripts/simulate_sms.py` |
| | Entidades confiables (SGC, SIMAC, Bomberos…) | 🟡 | Solo el canal `entity` en `POST /ingest/report` (rol operador). **No hay adaptador ni feed** |
| | WhatsApp / APIs públicas | 🟡 | Canal `whatsapp` ingresado por operador |
| | LoRa / sensor zonas inseguras | ❌ | Solo el valor de canal `lora` |
| 2. Ingesta y SST | API REST `/api/v1`, idempotencia, OpenAPI | ✅ | `routers/ingest.py` |
| | Habeas Data (redacción + HMAC) | ✅ | `core/privacy.py`, `lib/redact.ts` |
| | PostgreSQL + PostGIS, solo-agregar, bitácora | ✅ | `models.py` |
| | Bus de eventos → SSE | ✅ | `adapters/event_bus.py`, `routers/stream.py` |
| 3. Motor | Clasificación y triaje por reglas | ✅ | `core/nlp.py` |
| | Deduplicación | ✅ | `core/dedup.py`; TF-IDF por defecto, MiniLM opcional |
| | Trust Score explicable | ✅ | `core/trust.py` |
| | Validación cruzada GIS / acelerógrafos | ❌ | `adapters/hazard.py` devuelve siempre 0,5 "sin dato de sensor" |
| | RAG local / LLM (Ollama o Google) | ❌ | Sin ninguna integración |
| 4. Tablero PMU | Mapa, matriz de triaje, revisión humana, KPI con fecha de corte, mapa público k ≥ 5 | ✅ | `app/pmu/`, `components/` |
| | Trazabilidad de recursos | 🟡 simulado | `adapters/tracks.py` |
| 5. Despacho y alertas | Despacho a agencias + pantalla de agencia | ✅ | `routers/dispatch.py`, `app/agencia/` |
| | Alertas con aprobación solo COE | ✅ | `routers/alerts.py` |
| | Efectos en cascada | 🟡 simulado | `routers/cascade.py` |
| | Nivel de emergencia EMRE y `GET /metrics/sitrep` | ❌ | No existen |
| 6. Recuperación | Semáforo por predio, censo único, ayudas, albergues, export RUD | ✅ | `routers/recovery.py`, `core/recovery.py`, `app/recuperacion/` |
| | Infraestructura y servicios (agua, energía, gas) | ❌ | No hay registro de restablecimiento |
| | Reconstrucción transparente, portal "Reconstruir Mejor" | 🟡 | Solo `GET /recovery/summary` agregado |

### Lo que no pude verificar (❓ confirmar con el equipo)
- Que `docker compose up` arranque desde cero con la migración `0004_recovery` (en este portátil **no hay Docker**).
- Las pruebas de integración (necesitan PostgreSQL + PostGIS).
- Si el escenario de demo siembra inspecciones/hogares, o si la pantalla `/recuperacion` arranca vacía (solo se siembran albergues).
- Si el KPI > 90 % se cumple (`scripts/evaluate_kpis.py` no se ejecutó).
- Si "usar la API de Google" está aprobado: rompe offline-first salvo que quede detrás de un adaptador con respaldo local.

## 3. Ruta al MVP, por prioridad

### Indispensable para el pitch
1. **Ensayo completo desde cero** en la máquina de la demo: `docker compose up`, reproducir el escenario y recorrer
   incidente → despacho → `/recuperacion` (semáforo → hogar en el censo → intento de hogar duplicado → ayuda →
   ayuda duplicada bloqueada → albergue). Anotar lo que falle.
2. **Datos de recuperación sembrados para la demo:** algunas inspecciones, hogares y ayudas SIMULADAS para que el
   resumen y el k ≥ 5 se vean con cifras, más uno o dos casos de duplicado preparados para mostrarlos en vivo.
3. **Pruebas mínimas del módulo 6** (hash de hogar, duplicidad de ayudas, regla color↔daño en `core/recovery.py`):
   son funciones puras, rápidas de probar.
4. Actualizar `docs/guion_demo.md` (cierre con recuperación) y `docs/arquitectura_actual.png` (módulo 6 implementado);
   grabar el video de respaldo.

### Resolver de forma sencilla (simulado y etiquetado)
5. **Entidades confiables (módulo 1):** script `scripts/simulate_entities.py` que envíe boletines sintéticos de
   SGC/Bomberos/Cruz Roja por `POST /ingest/report` con `channel=entity`.
6. **Consolidación (módulo 2):** ya existe; basta con que esos reportes corroboren incidentes y suban el Trust Score.
7. **Validación cruzada:** `HazardProvider` con PGA sintético por manzana para que la consistencia física deje de ser neutra.
8. **Nivel de emergencia EMRE sugerido:** regla simple sobre incidentes y barrios afectados.

### Puede esperar (mencionar como "siguiente paso" en el pitch)
9. RAG con LLM: `LlmProvider` con Google en línea y Ollama/reglas como contingencia; nunca bloquear la demo por la red.
10. Ajustes del NLP más allá del léxico.
11. Servicios públicos en recuperación, LoRa/Meshtastic, sensor de zonas inseguras, reconstrucción/financiación, portal completo.

## 4. Riesgos
- Módulo 6 sin pruebas y sin datos sembrados: puede fallar o verse vacío en vivo.
- Depender de internet (API de Google) en el pitch.
- Sin Docker en alguna máquina de la demo.
