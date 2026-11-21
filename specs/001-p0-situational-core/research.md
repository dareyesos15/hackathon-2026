# Research: Núcleo situacional P0 de Dacora

**Fecha**: 2026-11-20 · **Plan**: [plan.md](plan.md)

Cada decisión resuelve una incógnita del Technical Context o una restricción de la constitución.

---

## R1. Similitud de texto para la deduplicación sin internet

- **Decision**: interfaz `SimilarityProvider` con implementación por defecto **TF-IDF de
  caracteres** (scikit-learn, `analyzer="char_wb"`, n-gramas 3–5, minúsculas y sin tildes) y
  similitud coseno. Implementación opcional `minilm`
  (`paraphrase-multilingual-MiniLM-L12-v2`) activada con `SIMILARITY_PROVIDER=minilm` y un
  `build-arg` que hornea el modelo en la imagen.
- **Rationale**: sentence-transformers arrastra PyTorch (cientos de MB) y una descarga del modelo;
  eso pone en riesgo el criterio "desde cero en < 5 min" y la operación sin red. Los n-gramas de
  caracteres toleran errores de ortografía y abreviaturas de SMS ("cra", "edif"), y la decisión de
  agrupación ya está acotada por categoría, distancia y tiempo, así que el texto es un desempate.
- **Calibración**: los umbrales 0,75 / 0,6 de CLAUDE.md están pensados para embeddings; con TF-IDF
  los valores iniciales serán 0,35 (ubicación aproximada) y 0,20 (ubicación exacta), en `config` y
  ajustados con `evaluate_kpis.py` hasta superar 90 %.
- **Alternatives considered**: MiniLM por defecto (descartado por tamaño/tiempo de build);
  Jaccard de palabras (frágil con abreviaturas); sin texto, solo espacio-tiempo (fusiona hechos
  distintos de la misma categoría en la misma cuadra).

## R2. Imagen de PostGIS en Mac arm64

- **Decision**: `imresamu/postgis:16-3.5`.
- **Rationale**: verificado con `docker manifest inspect` (20 nov 2026): `postgis/postgis:16-3.5`
  solo publica `amd64` (correría emulado en el Mac del equipo); `imresamu/postgis` publica
  `amd64` y `arm64` y la mantiene uno de los mantenedores del proyecto docker-postgis, con el mismo
  Dockerfile base.
- **Alternatives considered**: `postgis/postgis` con `platform: linux/amd64` (emulación lenta);
  SQLite + haversine (fallback documentado en CLAUDE.md, se mantiene como plan C si Docker falla,
  no se implementa en P0).

## R3. Frontend puro: exportación estática + Nginx

- **Decision**: Next.js con `output: "export"`; la imagen `web` construye los estáticos y los
  sirve con Nginx, que además hace proxy inverso de `/api/` hacia `api:8000`
  (`proxy_buffering off` para SSE). Rutas dinámicas resueltas en el cliente (p. ej.
  `/pmu?incidente=<id>`).
- **Rationale**: la exportación estática hace **imposible** tener Route Handlers o Server Actions
  (principio X garantizado por construcción); un solo origen evita CORS y simplifica que el
  celular en la LAN use una sola URL; el service worker cachea archivos estáticos sin
  complicaciones.
- **Alternatives considered**: `next start` en modo standalone (servidor Node innecesario y
  tentación de lógica en servidor); servir estáticos desde FastAPI (mezcla servicios);
  CORS directo a `:8000` (dos URLs para el celular, más fallas en la demo).

## R4. Offline en la PWA y el problema de HTTPS en la LAN

- **Decision**: el outbox vive en IndexedDB (Dexie) y se vacía al recibir el evento `online`,
  al cargar la página y cada 15 s mientras haya pendientes; **no** depende del service worker.
  El service worker (`public/sw.js`, escrito a mano) cachea el app shell como mejora progresiva.
- **Rationale**: los navegadores solo registran service workers en `https` o `localhost`. En la
  demo el celular entra por `http://<ip-del-portátil>`, donde no habrá SW, pero IndexedDB sí
  funciona: con la página abierta, modo avión → reporte en cola → red → sincroniza. En el
  portátil (`localhost`) el SW funciona y se puede demostrar recarga sin red con DevTools.
  Background Sync no existe en Safari/iOS, por eso el disparo es por eventos de página.
- **Alternatives considered**: `next-pwa` (sin mantenimiento) y Serwist (acoplado al bundler,
  más configuración); certificados con mkcert en la LAN (instalar la CA en el celular consume
  tiempo de demo; queda como opción documentada).

## R5. Tiempo real: SSE con bus en memoria

- **Decision**: `EventBus` en memoria (colas `asyncio` por suscriptor) y `GET /api/v1/stream`
  con `StreamingResponse` (`text/event-stream`), latido cada 15 s, `id` incremental y soporte
  de `Last-Event-ID`. El cliente (`lib/live.ts`) cae a polling de
  `GET /api/v1/incidents?since=` cada 3 s si el stream falla 2 veces seguidas.
- **Rationale**: un solo worker de Uvicorn basta para la demo; sin Redis ni Kafka (principio VII);
  la interfaz `EventBus` permite cambiar a Kafka después (principio VI).
- **Alternatives considered**: WebSockets (bidireccional innecesario); `sse-starlette`
  (dependencia extra para algo que `StreamingResponse` resuelve).

## R6. Clasificación y triaje en español colombiano

- **Decision**: clasificador por reglas: léxico por categoría con lemas y variantes
  (p. ej. `atrapad*`, `bajo los escombros`, `no pueden salir` → personas_atrapadas;
  `huele a gas`, `fuga` → fuga_gas), normalización (minúsculas, sin tildes, abreviaturas de SMS:
  `cra`→`carrera`, `q`→`que`, `edif`→`edificio`), prioridad por nivel de triaje cuando varias
  categorías coinciden y código SMS como señal fuerte. Señales de desinformación por lista
  (`reenvia`, `cadena`, `dicen que`, `me contaron`, `urgente compartir`, `replica de 9`,
  `predicen`, cifras grandes sin lugar).
- **Rationale**: determinista, explicable, < 1 ms por reporte, sin descargas; el desglose del
  trust score puede citar las palabras que dispararon cada señal.
- **Alternatives considered**: modelo transformer ajustado (sin datos etiquetados ni tiempo);
  LLM local (P2, no apto para < 1 s en CPU).

## R7. Geografía de Manizales sin conexión

- **Decision**: `scripts/generate_geo.py` crea (y se versiona en `data/geo/`):
  `gazetteer.csv` con ~40 barrios, vías y referencias con centroides aproximados alrededor de
  `5.0689, -75.5174`; `barrios.geojson` (polígonos de Voronoi recortados al casco urbano
  aproximado) y `manzanas.geojson` (grilla de ~150 m dentro de los barrios, con `seismic_zone`,
  `population` y `buildings_pre_1984_pct` sintéticos). Todo con `source = "SIMULADO"`.
- **Rationale**: no depende de descargas ni licencias en la demo; suficiente para el mapa, la
  agregación por manzana y la ubicación por barrio. Integrar las manzanas del geoportal municipal
  o del DANE es reemplazar archivos (plan 30–90 días).
- **Alternatives considered**: descargar del geoportal ahora (riesgo de formato y tiempo; se puede
  hacer después sin cambiar código); PMTiles de OpenStreetMap (requiere herramientas extra y
  descarga; queda como mejora visual).

## R8. Ground truth fuera del motor y KPI en vivo

- **Decision**: `generate_scenario.py` (semilla fija) produce `data/seed/scenario.jsonl`
  (solo lo que vería el sistema) y `data/seed/ground_truth.json`. `replay_scenario.py` envía los
  reportes y, cada 25 reportes y al final, invoca `evaluate_kpis.py`, que lee el ground truth y
  los resultados de `GET /api/v1/reports` y publica una instantánea en
  `POST /api/v1/metrics/snapshots` con `source="evaluate_kpis.py"`, `version` y `cutoff_at`.
  El paquete `app/core` tiene una prueba que falla si importa o abre algo de `metrics` o
  `ground_truth`.
- **Definiciones de KPI**:
  - *Detección de duplicados* = reportes con `duplicate_of` en la verdad que quedaron en el mismo
    incidente que su original ÷ total de duplicados reales.
  - *Detección de falsos* = reportes falsos cuyo incidente quedó con trust < 25 (Posible falso) o
    categoría `rumor_informacion` ÷ total de falsos reales. Se publica también la tasa de legítimos
    marcados así (falsos positivos). *Enmienda (implementación):* el umbral inicial era < 50, pero
    casi todo reporte legítimo de una sola fuente queda en "Sin verificar" (25–49), lo que habría
    disparado los falsos positivos.
  - *Críticos descartados automáticamente* = reportes `is_life_threat` con estado `descartado`
    sin evento humano en la bitácora (debe ser 0).
  - *Recall de críticos* = reportes críticos reales marcados `is_life_threat` ÷ críticos reales
    (meta ≥ 98 %).
  - *Tiempo hasta mapa consolidado* = minutos simulados desde 07:34 hasta que ≥ 90 % de los hechos
    reales únicos tienen un incidente en el mapa.
- **Rationale**: cumple literalmente el principio IV (el motor nunca ve la verdad) y el V (cada
  cifra con fuente y corte).
- **Alternatives considered**: que la API cargue el ground truth en un módulo aparte (más simple
  pero viola el texto de la constitución).

## R9. Autenticación por rol para la demo

- **Decision**: tokens fijos por rol en `.env` (`TOKEN_OPERADOR_PMU`, `TOKEN_CIUDADANO`,
  `TOKEN_PUBLICO`, y ya definidos `TOKEN_COE`, `TOKEN_INSPECTOR`, `TOKEN_AGENCIA` para P1),
  cabecera `Authorization: Bearer`. La pantalla de inicio deja elegir el rol y pedir el token;
  los tokens de demo van en `.env.example` y en el guion.
- **Rationale**: sin Keycloak (constitución, principio VI); suficiente para separar quién decide.
- **Alternatives considered**: sin autenticación (rompe "solo el operador decide").

## R10. Rendimiento y concurrencia

- **Decision**: pipeline síncrono dentro de la petición de ingesta (respuesta con el resultado),
  candidatos de agrupación filtrados en SQL con `ST_DWithin` sobre `geography` y ventana de 3 h
  antes de calcular similitud; vectorizador TF-IDF ajustado sobre los textos del incidente
  candidato (decenas, no miles). Bloqueo asesor de Postgres por celda de ~600 m para evitar que
  dos reportes simultáneos creen dos incidentes del mismo hecho.
- **Rationale**: el volumen de la demo (< 1 reporte/s en promedio, ráfagas de decenas) cabe
  holgado en < 1 s; el bloqueo evita la condición de carrera en las ráfagas del modo rápido.
- **Alternatives considered**: cola de trabajos en segundo plano (más piezas, el tablero vería
  reportes "sin procesar").

## R11. Contrato y tipos compartidos

- **Decision**: FastAPI genera `/openapi.json`; `scripts/export_openapi.py` lo escribe en
  `apps/web/lib/api/openapi.json` y `npm run gen:api` produce `schema.d.ts` con
  `openapi-typescript`; el cliente usa `openapi-fetch`. Una prueba de contrato en `api` compara el
  OpenAPI actual con el versionado y falla si no se regeneró.
- **Rationale**: principio X (contrato explícito, tipos generados, regeneración en el mismo
  commit).
- **Alternatives considered**: tipos escritos a mano (descartado por el usuario).

## R12. Versiones y herramientas

- **Decision**: Python 3.12 en contenedor (la máquina local tiene 3.14, pero el ecosistema
  científico y asyncpg tienen ruedas estables para 3.12); Node 22 LTS; `uv` para dependencias de
  Python; `npm` para el frontend (sin espacios de trabajo); versiones exactas fijadas en los
  lockfiles al crear los proyectos.
- **Rationale**: compatibilidad y builds reproducibles sin red una vez construidas las imágenes.
- **Alternatives considered**: Python 3.14 en contenedor (riesgo de ruedas faltantes); pnpm
  (instalado, pero npm reduce sorpresas en el Dockerfile).

## Riesgos abiertos

| Riesgo | Mitigación |
|---|---|
| Docker Desktop no estaba corriendo al planear | Verificar `docker info` antes de la primera tarea de infraestructura |
| TF-IDF no alcanza 90 % de duplicados | Calibrar umbrales con `evaluate_kpis.py`; activar `minilm` como respaldo |
| Celular sin service worker en HTTP | Demostrar la recarga offline en el portátil; en el celular, outbox con página abierta |
| El build inicial necesita internet | Construir imágenes (`docker compose build`) con red antes de la demo y verificar con red apagada |
