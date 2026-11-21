# Constitución de Dacora

Dacora — prototipo Hackathon UNAL Manizales 2026,
Vertical 05 · Datos & Inteligencia Operativa. Fuente de contexto: `CLAUDE.md` en la raíz.

## Core Principles

### I. Habeas Data desde el diseño (NO NEGOCIABLE)

- Ningún dato personal (cédula, celular, correo, placa, nombre propio) se persiste en claro:
  se redacta **antes de guardar** con marcadores (`[TEL]`, `[CC]`, `[NOMBRE]`, …).
- La redacción ocurre dos veces: en el borde (PWA, `lib/redact.ts`) y en la API
  (`core/privacy.py`), que es la autoridad. Ambas implementaciones comparten casos de prueba.
- Para cruzar duplicados y censo solo se guarda `HMAC-SHA256(sal, dato_normalizado)`; la sal
  vive en configuración, nunca en el repositorio.
- Datos sensibles (salud, niñez, discapacidad) van en tablas separadas con acceso por rol.
- Todo lo público se publica agregado por manzana o barrio con **k ≥ 5**.
- La PWA muestra aviso de privacidad y pide consentimiento explícito antes del primer reporte.
- Nunca se usan, descargan ni publican datos personales reales (Ley 1581 de 2012, Decreto 1377
  de 2013).

*Razón:* es restricción explícita del reto y criterio de viabilidad del jurado; una fuga de datos
reales invalida el prototipo.

### II. Offline-first

- El sistema completo MUST correr en un portátil sin internet (Plan B): `docker compose up`
  sin servicios de nube obligatorios, sin teselas ni modelos descargados en caliente durante
  la demo.
- La PWA guarda en IndexedDB con patrón *outbox*; cada envío lleva `client_uuid` generado en el
  cliente y la API es **idempotente** por ese valor: sincronizar dos veces no duplica.
- Todo componente pesado tiene degradación definida (sin modelo de embeddings → TF-IDF;
  sin PostGIS → SQLite + haversine; sin Ollama → protocolo por reglas) y la degradación no
  rompe el flujo P0.

*Razón:* en el sismo del 10 ago 2026 los cortes de energía y red celular frenaron la
consolidación; un sistema que dependa de la nube falla justo cuando se necesita.

### III. La IA sugiere, decide un humano (NO NEGOCIABLE)

- Clasificación, triaje, deduplicación, trust score y nivel de emergencia son **sugerencias**
  con desglose explicable (`trust_breakdown`) visible en el tablero.
- Un reporte con `is_life_threat = true` (personas atrapadas, heridos, colapso con personas,
  incendio, fuga de gas, deslizamiento sobre viviendas ocupadas) **nunca** se descarta ni se
  marca falso automáticamente: va a la cola de revisión humana, sin importar su puntaje.
- Un duplicado no se elimina: suma corroboración y completa datos del incidente.
- Toda acción humana (confirmar, descartar, marcar duplicado, despachar) queda en la bitácora
  auditable `report_events` con rol y fecha/hora. Los reportes son solo-agregar.
- Solo el rol `coe` aprueba alertas oficiales (EMRE Manizales 2024, tarea 5.5); el resto
  quedan en borrador.

*Razón:* un falso negativo en un reporte crítico cuesta vidas; la autoridad legal de decisión
es del PMU/COE, no del software.

### IV. Datos sintéticos y honestidad de la demo

- Todo escenario, sensor, capa o integración que no sea real MUST mostrarse con la etiqueta
  visible **"SIMULADO"** en la interfaz y en los datos (`source`).
- La verdad de terreno del escenario (`ground_truth`: `unique`, `duplicate_of`, `fake`) vive en
  un archivo separado que el motor **no lee**; solo la usa `evaluate_kpis.py`.
- Los KPI que se muestran al jurado se calculan, no se escriben a mano.

*Razón:* el jurado evalúa conocimiento y viabilidad; presentar simulaciones como reales destruye
la credibilidad del equipo.

### V. Trazabilidad de cada cifra

- Toda tabla lleva `id UUID`, `created_at`, `source`, `version` y, si aplica, `cutoff_at`.
- Toda cifra del tablero, del panel de KPI y del reporte de situación muestra **fuente, versión
  y fecha/hora de corte**.
- Los indicadores usan un diccionario único (`docs/diccionario_indicadores.md`); no se admiten
  sinónimos sueltos ("afectación total" vs. "pérdida total").
- Los inmuebles se identifican por un `property_id` estable (código catastral o manzana +
  dirección normalizada) para trazar solicitud → visita → clasificación → beneficio.

*Razón:* el problema central observado fue la contradicción de cifras (1.449 → 2.700 → 1.512)
y el conteo de visitas en lugar de predios.

### VI. Integraciones detrás de adaptadores

- Todo servicio externo (SMS, WhatsApp, SGC/ShakeMap, LoRa/Meshtastic, RFID, enrutamiento
  ERIS, LLM) se accede mediante una interfaz (`EventBus`, `HazardProvider`, `RoutingProvider`,
  adaptadores en `app/adapters/`) con implementación **simulada por defecto**.
- Cambiar a la integración real MUST requerir solo configuración o una nueva implementación,
  no cambios en el motor ni en el tablero.
- No se usa Kafka, Kubernetes ni Keycloak en el prototipo; se dejan los puntos de integración.

*Razón:* permite demostrar offline hoy y sostiene el plan 30–90 días (componente 4 de la
rúbrica).

### VII. Simplicidad bajo el reloj

- Prioridad estricta P0 → P1 → P2 (CLAUDE.md §8). Nada de P1/P2 se empieza mientras un criterio
  P0 de §14 esté en rojo.
- Se prefiere algo simple que funcione a algo completo que no arranque: sin abstracciones
  especulativas, sin dependencias nuevas que no resuelvan un requisito P0/P1.
- Si existe código previo del equipo (p. ej. el triaje 0–100 de SIRA), se integra antes que
  reescribir.
- Toda complejidad adicional se justifica en la sección "Complexity Tracking" del plan.

*Razón:* el P0 debe demostrarse antes del sábado 21 nov 2026, 10:00 a. m.

### VIII. Español de Colombia en la interfaz

- Toda la interfaz, mensajes, textos de demo y documentación van en español de Colombia
  (formato numérico `1.449`, decimales con coma, hora de Colombia UTC−5).
- Identificadores de código (variables, tablas, endpoints) van en inglés según el glosario de
  CLAUDE.md §13.
- El léxico de clasificación y desinformación se diseña para el español colombiano.

*Razón:* los usuarios son el PMU, la UGR y la ciudadanía de Manizales.

### IX. Calidad verificable

- Python: tipado con mypy en módulos críticos (`privacy`, `nlp`, `dedup`, `trust`), `ruff` +
  `black`, pruebas con `pytest`. TypeScript: `strict`, `eslint` + `prettier`, pruebas con
  `vitest`.
- Pruebas obligatorias antes de dar por terminado P0:
  - prueba automática de que ningún teléfono, cédula o correo del escenario llega a la base;
  - idempotencia de `/ingest/batch` y `/ingest/report` por `client_uuid`;
  - `evaluate_kpis.py`: detección de duplicados y falsos **> 90 %** y **0** reportes críticos
    descartados automáticamente;
  - el motor procesa un reporte en **< 1 s**.
- Commits pequeños y frecuentes; `README.md` explica cómo correr la demo en un comando.

*Razón:* el KPI oficial del reto es medible y el jurado verá la demo en vivo.

### X. Dos servicios, un contrato REST

- La aplicación tiene **exactamente dos servicios principales**: `api` (Python + FastAPI) y
  `web` (Next.js). Se comunican **solo vía API REST** versionada en `/api/v1`.
- FastAPI es el **único** dueño de la lógica de negocio, del motor de inteligencia, del acceso a
  la base de datos y de los adaptadores externos.
- Next.js es **frontend puro**: MUST NOT tener Route Handlers (`app/api/`), Server Actions con
  lógica de negocio ni conexión a la base. La redacción en el borde (`lib/redact.ts`) corre en
  el navegador.
- El contrato es el OpenAPI que publica FastAPI; los tipos TS del frontend se **generan** de él
  (`openapi-typescript`) y se regeneran en el mismo commit que cambia un modelo Pydantic.
- Única excepción al REST: `GET /api/v1/stream` (SSE servido por FastAPI) para el tablero en
  vivo, con degradación a polling REST.
- Base de datos y Ollama (opcional, P2) son servicios de soporte: solo `api` habla con ellos.
  Los scripts del escenario son clientes de la misma API REST.

*Razón:* un solo punto de aplicación de Habeas Data y de las reglas de decisión humana, y un
contrato explícito que permite repartir frontend y backend entre integrantes sin desalinearse.

## Restricciones técnicas y legales

- **Stack del prototipo** (CLAUDE.md §4 y §4.1): servicio `web` = Next.js 14+ (App Router, TS)
  como PWA y frontend puro + MapLibre GL + Tailwind + Dexie + cliente generado con
  `openapi-typescript`; servicio `api` = FastAPI + Pydantic v2 + SQLAlchemy 2/GeoAlchemy2;
  soporte: PostgreSQL 16 + PostGIS y Ollama opcional; SSE para el tablero;
  `sentence-transformers` multilingüe + reglas; orquestación con `docker compose`.
- **Marco legal:** Ley 1523 de 2012 (exportar GeoJSON/OGC), Ley 1581 de 2012 (Principio I),
  Ley 1712 de 2014 (solo agregados públicos), NSR-10 (clasificación de daño y semáforo), formato
  RUD exportable en CSV, EMRE Manizales 2024 (niveles, 6 funciones de respuesta, cadencia de
  reportes de situación).
- **Roles de la demo:** `ciudadano`, `operador_pmu`, `coe`, `inspector`, `agencia`, `publico`,
  con token fijo por rol en `.env`; secretos y sales nunca en el repositorio.
- Las patentes NC2022/0005468 y NC2022/0005810 no se presentan como alerta sísmica.

## Flujo de trabajo y puertas de calidad

- Flujo SDD con Spec Kit: `constitution` → `specify` → (`clarify`) → `plan` → `tasks` →
  (`analyze`) → `implement`.
- Cada `plan.md` incluye la "Constitution Check" contra los principios I–X; una violación sin
  justificación en "Complexity Tracking" bloquea el paso a `tasks`.
- Puerta de demo: antes de la Mentoría 2 (sáb 21 nov, 10:30 a. m.) se ejecuta la lista de
  CLAUDE.md §14 y `evaluate_kpis.py`; lo que falle se corta del guion o se etiqueta SIMULADO.
- Cambios a esquema de datos o contratos de API se reflejan en la spec/plan antes del código.

## Governance

- Esta constitución prevalece sobre preferencias individuales; `CLAUDE.md` es la guía de
  contexto y detalle operativo. Si se contradicen, se enmienda uno de los dos explícitamente.
- Enmiendas: propuesta en un commit que modifique este archivo, con el motivo y el impacto;
  aprobación de al menos un integrante distinto del autor (durante la hackathon basta acuerdo
  verbal registrado en el mensaje del commit).
- Versionado semántico: MAJOR = quitar o redefinir un principio; MINOR = principio o sección
  nueva o ampliación material; PATCH = redacción y aclaraciones.
- Toda revisión de código y todo `/speckit-analyze` verifica cumplimiento de los principios I,
  III, IV y X en primer lugar.

**Version**: 1.1.0 | **Ratified**: 2026-11-20 | **Last Amended**: 2026-11-20
