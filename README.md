# Dacora

Datos, alerta y coordinación para la respuesta al sismo del 10 de agosto de 2026 en Manizales.
Prototipo de la Hackathon UNAL Manizales 2026 · Vertical 05 · Datos & Inteligencia Operativa.

> **Todos los datos son SIMULADOS.** Ningún nombre, teléfono o cédula corresponde a personas reales
> (Ley 1581 de 2012). La IA solo sugiere; decide un humano.

## Demo en 1 comando

```bash
docker compose up -d --build
```

Abra **http://localhost:8080**: la página de inicio muestra a cualquiera el mapa agregado y los indicadores. Con **Iniciar sesión** se elige un rol. Para llenar el tablero con el sismo simulado:

```bash
docker compose exec api python scripts/replay_scenario.py --reset            # 12 min (1 h = 1 min)
docker compose exec api python scripts/replay_scenario.py --reset --speed 720  # ~1 min (ensayo)
docker compose exec api python scripts/replay_scenario.py --reset --speed 720 --rain  # + lluvia SIMULADA
```

| Pantalla | URL | Usuario de prueba |
|---|---|---|
| Tablero público: triaje (incidentes sin texto, ubicación aproximada), cascada, zonas inseguras, mapa agregado (k ≥ 5), alertas vigentes y KPI | http://localhost:8080 | — (sin sesión) |
| Reporte de emergencias (PWA offline) | http://localhost:8080/reportar/ | — (sin sesión) |
| Iniciar sesión de entidades | http://localhost:8080/ingresar/ | — |
| Tablero de entidades y PMU (triaje, despacho, alertas con aprobación, cascada, zonas inseguras) | http://localhost:8080/pmu/ | `coe` (aprueba alertas) o `pmu` |
| Avisos y despachos por agencia (incidentes que le llegan según la EMRE, llegada, finalizado, fuera de servicio) | http://localhost:8080/agencia/ | `bomberos`, `cruzroja`, `defensacivil`, `infraestructura` (o `coe`/`pmu`) |
| Recuperación: semáforo de habitabilidad, censo único, ayudas y albergues | http://localhost:8080/recuperacion/ | `coe` o `pmu` |
| Simulaciones: con datos (escenario) o sin datos (tablero vacío) | http://localhost:8080/admin/ | `admin` |
| Panel de KPI | http://localhost:8080/pmu/kpi/ | — (cualquiera) |

**La ciudadanía no inicia sesión:** cualquier visitante ve el tablero público y reporta
emergencias como anónimo (rol `publico` en la API). Las entidades y el administrador entran con
usuario y contraseña de prueba (contraseña de todos: `dacora2026`, variable `DEMO_PASSWORD`);
cada usuario recibe el token de su rol de API: `coe` → `coe` (único que aprueba alertas
oficiales, EMRE tarea 5.5), `pmu` → `operador_pmu`, agencias → `agencia` (con su agencia ya
elegida) y `admin` → `admin`. Todos los usuarios son ficticios.
| API (OpenAPI) | http://localhost:8080/docs | — |

Los tokens de demo están en [.env.example](.env.example); sin `.env`, Compose usa esos valores.

**Marcas "SIMULADO":** con `NEXT_PUBLIC_DEMO_MODE=true` (por defecto) la interfaz marca los datos
sintéticos y muestra la fuente, versión y fecha de corte de cada cifra; con `false`, para un
despliegue con datos reales, no se muestran. Se aplica al
construir la imagen web: `docker compose up -d --build web`.

**Reportar con GPS desde un celular:** los navegadores solo comparten el GPS en conexiones
seguras. Desde el celular (misma red Wi-Fi que el portátil) abra
**https://&lt;IP-del-portátil&gt;:8443/reportar/**, acepte una vez la advertencia del certificado
autofirmado y reporte (sin iniciar sesión). El reporte queda en el punto exacto del GPS en el mapa del
PMU. Por `http://…:8080` el GPS no está disponible y la PWA ofrece el enlace seguro.

Despacho, alertas y cascada (specs/002): los recursos, sus recorridos tipo RFID, la hora estimada
de llegada, el envío de SMS y la pendiente son **SIMULADOS**. La lluvia de la cascada es SIMULADA
por defecto; desde **/admin/** (sección "Fuente de lluvia") se puede cambiar en caliente a la
**precipitación real del CDIAC/SIMAC** (UNAL Manizales): la API consulta cada 5 min las estaciones
hidrometeorológicas urbanas y la interpola por manzana. Si CDIAC no responde o sus datos tienen
más de 60 min, la cascada vuelve sola a la lluvia SIMULADA y lo indica (`RAIN_SOURCE`,
`CDIAC_POLL_S`, `CDIAC_MAX_AGE_MIN`). Requiere internet en el servidor; en Plan B, déjela en
SIMULADA. El avance de los recursos
despachados va 20 veces acelerado (`TRACK_SPEEDUP`); para que un crítico sin despacho se marque
antes en la demo, baje `UNATTENDED_ALERT_MIN` (por defecto 15 min).

Recuperación (specs/003): cada predio se identifica por código catastral o por manzana +
dirección normalizada, de modo que las visitas repetidas al mismo inmueble se cuentan una sola vez.
Del documento del jefe de hogar solo se guarda un HMAC con sal (nunca el número); la
vulnerabilidad va en una tabla aparte, visible solo para Entidades y PMU. La misma ayuda al mismo
hogar dentro de su plazo (30 días; 7 para mercado) se bloquea salvo justificación, y el censo se
exporta en CSV con columnas tipo RUD sin datos personales. Los albergues son **SIMULADOS**. El
reinicio de la demo también borra los registros de recuperación.

Sensor de zonas inseguras (specs/004, patente UNAL **NC2025/0015763**): 6 sensores **SIMULADOS**
en edificios acordonados vigilan un cono de 12 m (±30°) con ultrasonido e infrarrojo; el módulo
RFID reconoce 21 credenciales de rescatistas (también simuladas). Una persona sin tarjeta
registrada dentro del cono genera una **intrusión** (alarma en la pestaña *Zonas* del tablero,
con botón *Atender*); con tarjeta, un **acceso autorizado** sin alarma. Una intrusión detectada por
ambos sensores a ≤ 150 m de un incidente de personas atrapadas, colapso o daño estructural en las
últimas 3 h suma los 10 pts de "sensor de campo" a su puntaje de veracidad. Las lecturas sintéticas
llegan cada `ZONE_TICK_S` s (por defecto 6; `SIMULATE_ZONE_SENSORS=false` las apaga) por
`POST /api/v1/sensors/zones/{id}/readings`, el mismo punto de integración que usaría el
dispositivo real.

**Capas del mapa del PMU:** por defecto el mapa muestra solo el módulo de la pestaña activa
(Triaje: incidentes, calor por manzana y recursos; Alertas: áreas; Cascada: riesgo por manzana;
Zonas: sensores y conos). El control *Capas del mapa* (arriba a la izquierda) permite elegir a
mano qué módulos se ven a la vez.

### Requisitos

- Docker Desktop con Docker Compose v2.
- La **primera** construcción descarga imágenes y dependencias (necesita internet una vez).
  Después todo funciona **sin internet**: geografía, mapa base y modelos son locales.

## Comandos útiles

```bash
# SMS simulado (formato DACORA <CÓDIGO> <BARRIO o lat,lon> <N> <texto>)
docker compose exec api python scripts/simulate_sms.py "DACORA ATR MILAN 3 edificio caido cra 23"
docker compose exec api python scripts/simulate_sms.py --sobre-critico   # se une a un incidente crítico

# KPI contra la verdad del escenario (código ≠ 0 si no se cumplen las metas)
docker compose exec api python scripts/evaluate_kpis.py

# Pruebas
docker compose exec api pytest -q                      # API: unitarias, integración, contrato
cd apps/web && npm ci && npm test                      # Web: redacción en el borde, outbox, formato
```

## Resultados medidos (escenario SIMULADO, 254 reportes)

| Indicador | Meta P0 | Resultado |
|---|---|---|
| Duplicados detectados | > 90 % | 100 % |
| Falsos/rumores detectados | > 90 % | 94,7 % |
| Legítimos marcados como falsos | lo más bajo posible | 0 % |
| Críticos identificados | ≥ 98 % | 100 % |
| Críticos descartados por la IA | 0 | 0 |
| Procesamiento por reporte (p95) | < 1 s | < 20 ms |

Definiciones en [docs/diccionario_indicadores.md](docs/diccionario_indicadores.md). Se recalculan
con `scripts/evaluate_kpis.py` y se muestran en el panel con fuente y fecha de corte.

## Arquitectura

Dos servicios principales comunicados por API REST (constitución, principio X):

- **`api`** — Python 3.12 + FastAPI ([services/api](services/api)): ingesta, motor de verificación
  (Habeas Data, clasificación, triaje, deduplicación, trust score), revisión humana, despacho,
  alertas, cascada, sensor de zonas inseguras, recuperación (habitabilidad, censo único,
  ayudas, albergues), KPI, SSE.
- **`web`** — Next.js como exportación estática servida por Nginx ([apps/web](apps/web)): tablero
  PMU (MapLibre), panel de KPI, recuperación y PWA ciudadana con outbox en IndexedDB.
- Soporte: **`db`** PostgreSQL 16 + PostGIS.

Diagrama técnico: [docs/arquitectura.jpeg](docs/arquitectura.jpeg); estado actual (implementado,
simulado, planeado): [docs/arquitectura_actual.png](docs/arquitectura_actual.png). Especificaciones:
[001 núcleo P0](specs/001-p0-situational-core),
[002 despacho, alertas y cascada](specs/002-dispatch-alerts-prediction) y
[003 recuperación](specs/003-recovery) y
[004 sensor de zonas inseguras](specs/004-zone-sensor). Contexto completo:
[CLAUDE.md](CLAUDE.md). Guion de la demo: [docs/guion_demo.md](docs/guion_demo.md).
