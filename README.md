# Dacora

Datos, alerta y coordinación para la respuesta al sismo del 10 de agosto de 2026 en Manizales.
Prototipo de la Hackathon UNAL Manizales 2026 · Vertical 05 · Datos & Inteligencia Operativa.

> **Todos los datos son SIMULADOS.** Ningún nombre, teléfono o cédula corresponde a personas reales
> (Ley 1581 de 2012). La IA solo sugiere; decide un humano.

## Demo en 1 comando

```bash
docker compose up -d --build
```

Abra **http://localhost:8080** y elija un rol. Para llenar el tablero con el sismo simulado:

```bash
docker compose exec api python scripts/replay_scenario.py --reset            # 12 min (1 h = 1 min)
docker compose exec api python scripts/replay_scenario.py --reset --speed 720  # ~1 min (ensayo)
docker compose exec api python scripts/replay_scenario.py --reset --speed 720 --rain  # + lluvia SIMULADA
```

| Pantalla | URL | Rol / token de demo |
|---|---|---|
| Inicio (elegir rol) | http://localhost:8080 | — |
| Tablero del PMU (triaje, despacho, borradores de alerta, cascada) | http://localhost:8080/pmu/ | Operador PMU · `pmu-demo` |
| Tablero + bandeja del COE (aprobar, rechazar y anular alertas) | http://localhost:8080/pmu/ | COE · `coe-demo` |
| Despachos de una agencia (llegada, finalizado, fuera de servicio) | http://localhost:8080/agencia/ | Agencia · `agencia-demo` |
| Panel de KPI | http://localhost:8080/pmu/kpi/ | Operador PMU o Público · `publico-demo` |
| Mapa público (agregado por manzana, k ≥ 5, y alertas oficiales vigentes) | http://localhost:8080/mapa/ | Público · `publico-demo` |
| Reporte ciudadano (PWA offline) | http://localhost:8080/reportar/ | Ciudadanía · `ciudadano-demo` |
| API (OpenAPI) | http://localhost:8080/docs | — |

Los tokens de demo están en [.env.example](.env.example); sin `.env`, Compose usa esos valores.

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
