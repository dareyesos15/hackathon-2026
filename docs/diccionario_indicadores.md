# Diccionario de indicadores — Dacora P0

Cada cifra que muestra Dacora usa **exactamente** esta definición, con su fuente, versión y
fecha/hora de corte (constitución, principio V). No se admiten sinónimos sueltos.

> Todos los valores de la demo provienen del escenario **SIMULADO** del sismo del 10 ago 2026.

| Clave (`indicator`) | Nombre en pantalla | Unidad | Fuente | Definición | Meta P0 |
|---|---|---|---|---|---|
| `reports_received` | Reportes recibidos | conteo | `api` | Reportes registrados (todos los canales), sin contar reenvíos idempotentes del mismo `client_uuid`. | — |
| `incidents_consolidated` | Incidentes consolidados | conteo | `api` | Incidentes con al menos un reporte vigente (no descartado). | — |
| `duplicate_detection_rate` | Duplicados detectados | % | `evaluate_kpis.py` | Reportes que la verdad marca como duplicados y que quedaron en el **mismo incidente** que el reporte original ÷ total de duplicados reales. | > 90 % |
| `fake_detection_rate` | Falsos detectados | % | `evaluate_kpis.py` | Reportes falsos cuyo incidente quedó con etiqueta **Posible falso** (trust < 25) o clasificados como `rumor_informacion` ÷ total de falsos reales. | > 90 % |
| `false_positive_rate` | Legítimos marcados como falsos | % | `evaluate_kpis.py` | Reportes legítimos (únicos o duplicados) cuyo incidente quedó como Posible falso o rumor ÷ total de legítimos. | lo más bajo posible |
| `critical_auto_discarded` | Críticos descartados por la IA | conteo | `evaluate_kpis.py` | Reportes con riesgo vital en estado `descartado` sin una acción humana en la bitácora. | **0** |
| `critical_recall` | Críticos identificados | % | `evaluate_kpis.py` | Reportes críticos reales marcados con riesgo vital ÷ total de críticos reales. | ≥ 98 % |
| `time_to_consolidated_map_min` | Mapa consolidado en | min | `evaluate_kpis.py` | Minutos simulados desde el sismo (07:34) hasta que ≥ 90 % de los hechos reales tienen un incidente en el mapa. | — |
| `p95_processing_ms` | Procesamiento por reporte (p95) | ms | `api` | Percentil 95 del tiempo de procesamiento del motor por reporte. | < 1.000 ms |

## Etiquetas del puntaje de veracidad

| Etiqueta | Rango |
|---|---|
| Verificado | ≥ 75 |
| Probable | 50–74 |
| Sin verificar | 25–49 |
| Posible falso | < 25 |

## Términos

- **Reporte:** mensaje de una persona o entidad. Solo-agregar.
- **Incidente:** agrupación de reportes que describen el mismo hecho.
- **Fuente independiente:** remitente distinto (por huella HMAC); un remitente que repite no suma.
- **Fecha de corte (`cutoff_at`):** momento hasta el cual una cifra incluye datos.
