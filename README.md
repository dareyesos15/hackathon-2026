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

| Pantalla | URL | Rol / token de demo |
|---|---|---|
| Inicio público: mapa agregado (k ≥ 5), alertas vigentes y KPI | http://localhost:8080 | — (sin sesión) |
| Iniciar sesión (elegir rol) | http://localhost:8080/ingresar/ | — |
| Tablero de entidades y PMU (triaje, despacho, alertas con aprobación, cascada) | http://localhost:8080/pmu/ | Entidades y PMU · `coe-demo` |
| Despachos por agencia (llegada, finalizado, fuera de servicio) | http://localhost:8080/agencia/ | Entidades y PMU · `coe-demo` |
| Simulaciones: con datos (escenario) o sin datos (tablero vacío) | http://localhost:8080/admin/ | Administrador · `admin-demo` |
| Panel de KPI | http://localhost:8080/pmu/kpi/ | — (cualquiera) |
| Reporte ciudadano (PWA offline) | http://localhost:8080/reportar/ | Ciudadanía · `ciudadano-demo` |

Roles de la interfaz: **Ciudadanía**, **Entidades y PMU** (PMU, COE y agencias en un solo rol;
en la API usa el token `coe`, por eso puede aprobar alertas oficiales) y **Administrador**. Sin
sesión, el inicio público consulta como `publico` (solo agregados).
| API (OpenAPI) | http://localhost:8080/docs | — |

Los tokens de demo están en [.env.example](.env.example); sin `.env`, Compose usa esos valores.

**Marcas "SIMULADO":** con `NEXT_PUBLIC_DEMO_MODE=true` (por defecto) la interfaz marca los datos
sintéticos y muestra la fuente, versión y fecha de corte de cada cifra; con `false`, para un
despliegue con datos reales, no se muestran. Se aplica al
construir la imagen web: `docker compose up -d --build web`.

**Reportar con GPS desde un celular:** los navegadores solo comparten el GPS en conexiones
seguras. Desde el celular (misma red Wi-Fi que el portátil) abra
**https://&lt;IP-del-portátil&gt;:8443/reportar/**, acepte una vez la advertencia del certificado
autofirmado y entre como Ciudadanía. El reporte queda en el punto exacto del GPS en el mapa del
PMU. Por `http://…:8080` el GPS no está disponible y la PWA ofrece el enlace seguro.

Despacho, alertas y cascada (specs/002): los recursos, sus recorridos tipo RFID, la hora estimada
de llegada, el envío de SMS, la lluvia y la pendiente son **SIMULADOS**. El avance de los recursos
despachados va 20 veces acelerado (`TRACK_SPEEDUP`); para que un crítico sin despacho se marque
antes en la demo, baje `UNATTENDED_ALERT_MIN` (por defecto 15 min).

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
  (Habeas Data, clasificación, triaje, deduplicación, trust score), revisión humana, KPI, SSE.
- **`web`** — Next.js como exportación estática servida por Nginx ([apps/web](apps/web)): tablero
  PMU (MapLibre), panel de KPI y PWA ciudadana con outbox en IndexedDB.
- Soporte: **`db`** PostgreSQL 16 + PostGIS.

Diagrama técnico: [docs/arquitectura.jpeg](docs/arquitectura.jpeg). Especificación, plan, contratos
y tareas: [specs/001-p0-situational-core](specs/001-p0-situational-core). Contexto completo:
[CLAUDE.md](CLAUDE.md). Guion de la demo: [docs/guion_demo.md](docs/guion_demo.md).
