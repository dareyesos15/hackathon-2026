# Análisis de brechas y ruta al MVP del pitch

> Estado revisado: `main` en `138b012` (21 nov 2026) y ramas remotas a esa hora.
> Referencias: [arquitectura objetivo](arquitectura.jpeg) y [arquitectura actual](arquitectura_actual.png).
> Leyenda: ✅ verificado en el código · 🟡 parcial o simulado · ❌ no existe en `main` · ❓ suposición, requiere confirmación.

## 1. Hallazgo principal

**El módulo 6 (Recuperación) no está en `main`, pero sí existe en la rama `origin/feat/p1-geo-trust-recovery-ui`** (autor: loterini0, último commit hace ~1 h).
Esa rama tiene 54 commits que `main` no tiene, pero también le faltan 114 commits de `main`. Una fusión de prueba da **12 archivos en conflicto**
(`main.py`, `pipeline.py`, `demo.py`, `seed.py`, `Mapa.tsx`, `DetalleIncidente.tsx`, `MatrizTriaje.tsx`, `ReporteCiudadano.tsx`, `page.tsx`,
`globals.css`, `labels.ts` y el contrato OpenAPI/`schema.d.ts`; además `MapaPublico.tsx` se borró en `main` y se modificó en la rama).

Contenido de esa rama (verificado con `git diff`):
- API: `recovery_models.py`, `routers/recovery.py` (inspecciones, hogares, albergue, restablecimiento de servicios; conteos públicos con umbral), migraciones Alembic 0002–0006.
- Web: `components/Recuperacion.tsx` (formulario dentro del detalle del incidente, mapa de inspecciones).
- GIS: 8 capas municipales offline en `data/gis/`, cruce con deslizamientos.
- Pruebas: `test_recovery.py`, `test_gis.py`, `test_legacy_trust.py`.

**Conclusión:** el camino más corto al MVP centrado en recuperación es **integrar esa rama**, no reescribir el módulo.

## 2. Estado por bloque de la arquitectura

| Bloque | Componente | Estado | Evidencia |
|---|---|---|---|
| 1. Captación | PWA ciudadana offline (Dexie + outbox) | ✅ | `apps/web/lib/db.ts`, `app/reportar/` |
| | SMS compacto `DACORA …` | 🟡 simulado | `POST /ingest/sms`, `core/sms.py`, `scripts/simulate_sms.py` |
| | Entidades confiables (SGC, SIMAC, Bomberos…) | 🟡 | Solo existe el canal `entity` en `POST /ingest/report` (rol operador). **No hay adaptador ni feed** de ninguna entidad |
| | WhatsApp / APIs públicas | 🟡 | Canal `whatsapp` ingresado por operador; rama de recuperación trae `scripts/piloto_x.py` (búsqueda en X, solo lectura) |
| | LoRa / sensor zonas inseguras | ❌ | Solo el valor de canal `lora` |
| 2. Ingesta y SST | API REST `/api/v1`, idempotencia, OpenAPI | ✅ | `routers/ingest.py` |
| | Habeas Data (redacción + HMAC) | ✅ | `core/privacy.py`, `lib/redact.ts` |
| | PostgreSQL + PostGIS, solo-agregar, bitácora | ✅ | `models.py` (`reports`, `report_events`) |
| | Bus de eventos → SSE | ✅ | `adapters/event_bus.py`, `routers/stream.py` |
| 3. Motor | Clasificación y triaje por reglas | ✅ | `core/nlp.py` |
| | Deduplicación | ✅ | `core/dedup.py`; similitud **TF-IDF por defecto**, MiniLM opcional (`SIMILARITY_PROVIDER=minilm`) |
| | Trust Score explicable | ✅ | `core/trust.py` |
| | Validación cruzada GIS / acelerógrafos | ❌ | `adapters/hazard.py` devuelve siempre 0,5 "sin dato de sensor". No hay `sensors`, `sensor_readings` ni `hazard_estimates` |
| | RAG local / LLM (Ollama o Google) | ❌ | No hay ninguna integración con Ollama, Gemini ni otro LLM |
| 4. Tablero PMU | Mapa por manzana, matriz de triaje, revisión humana, KPI con fecha de corte, mapa público k ≥ 5 | ✅ | `app/pmu/`, `components/` |
| | Trazabilidad de recursos | 🟡 simulado | `adapters/tracks.py` |
| 5. Despacho y alertas | Despacho a agencias + pantalla de agencia | ✅ | `routers/dispatch.py`, `app/agencia/` |
| | Alertas con aprobación solo COE | ✅ | `routers/alerts.py` |
| | Efectos en cascada | 🟡 simulado | `routers/cascade.py` (lluvia sintética) |
| | Nivel de emergencia EMRE y `GET /metrics/sitrep` | ❌ | No existen |
| 6. Recuperación | Semáforo, censo único, ayudas/albergues, servicios | ❌ en `main` / 🟡 en rama | Ver sección 1 |
| | Reconstrucción transparente, portal "Reconstruir Mejor" | ❌ | Solo conteos públicos agregados en la rama |

Pendientes de la especificación 002: solo pruebas (T034–T036, T049–T051, T062) y la verificación final T067.

### Lo que no pude verificar (❓ confirmar con el equipo)
- Si la rama de recuperación pasa sus pruebas y si su autor está fusionándola ya.
- Si `docker compose up` arranca hoy desde cero (en este portátil **no hay Docker instalado**).
- Si el KPI > 90 % se cumple con el escenario actual (`scripts/evaluate_kpis.py` no se ejecutó en esta revisión).
- Si "usar la API de Google" está aprobado: rompe la regla offline-first salvo que quede detrás de un adaptador con respaldo local.

## 3. Ruta al MVP, por prioridad

### Indispensable para el pitch (hacer primero)
1. **Fusionar la recuperación en `main`.** Coordinar con el autor de `feat/p1-geo-trust-recovery-ui`: traer `main` a su rama, resolver los 12 conflictos (el contrato OpenAPI se **regenera**, no se edita a mano) y correr `pytest` + `npm test`. Es la tarea con mayor impacto y mayor riesgo; asignarle una sola persona.
2. **Hacer de la recuperación el cierre visible de la demo:** incidente confirmado → despacho → inspección con semáforo → hogar en el censo (con detección de duplicado) → ayuda entregada → conteo público agregado. Verificar que el escenario sintético siembre algunos registros para que la pantalla no arranque vacía.
3. **Ensayo completo desde cero** en la máquina de la demo (`docker compose up`, `replay_scenario.py`, guion) y **grabar el video de respaldo**.
4. Actualizar `docs/guion_demo.md` y `docs/arquitectura_actual.png` para que el módulo 6 aparezca como implementado.

### Resolver de forma sencilla (simulado y etiquetado)
5. **Entidades confiables (módulo 1):** un script `scripts/simulate_entities.py` que envíe por `POST /ingest/report` con `channel=entity` boletines sintéticos de SGC/Bomberos/Cruz Roja. Sin adaptador real.
6. **Consolidación (módulo 2):** ya existe (SST + deduplicación). Basta con que los reportes de entidades corroboren incidentes y suban el Trust Score.
7. **Validación cruzada:** un `HazardProvider` con PGA sintético por manzana (tabla en memoria) para que la señal de "consistencia física" deje de ser neutra.
8. **Nivel de emergencia EMRE sugerido:** regla simple sobre conteos de incidentes y barrios afectados, mostrada en el tablero.

### Puede esperar (mencionar como "siguiente paso" en el pitch)
9. RAG con LLM. Si se hace, `LlmProvider` con implementación Google en línea y Ollama/reglas como contingencia; nunca bloquear la demo por la red.
10. Reentrenar o "corregir" el NLP más allá de ajustes al léxico.
11. LoRa/Meshtastic, sensor de zonas inseguras, reconstrucción/financiación, portal completo.

## 4. Riesgos
- Fusión tardía de la rama de recuperación: cuanto más avance `main`, más conflictos.
- Depender de internet (API de Google) en el pitch.
- Sin Docker en alguna máquina de la demo.
