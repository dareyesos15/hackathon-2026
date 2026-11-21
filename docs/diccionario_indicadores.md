# Diccionario de indicadores — Dacora

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
| `time_to_consolidated_map_min` | Hecho en el mapa en (p90) | min | `evaluate_kpis.py` | Percentil 90, sobre los hechos reales recibidos, de los minutos simulados entre el primer reporte de un hecho y el momento en que su incidente queda ubicado en el mapa. Referencia del evento real: las cifras consolidadas tardaron días (1.449 → 2.700 → 1.512 viviendas entre el 13 y el 15 de agosto). | minutos, no días |
| `p95_processing_ms` | Procesamiento por reporte (p95) | ms | `api` | Percentil 95 del tiempo de procesamiento del motor por reporte. | < 1.000 ms |
| `critical_without_dispatch` | Críticos sin despacho | conteo | `api` | Incidentes con riesgo vital (abiertos, en revisión o verificados) sin ningún despacho que no esté cancelado. | **0** |
| `median_time_to_dispatch_min` | Tiempo a despacho de críticos (mediana) | min | `api` | Mediana, sobre los incidentes con riesgo vital despachados, de los minutos entre la consolidación del incidente en Dacora y su primer despacho no cancelado. Se mide en hora real, no en la hora sintética del sismo. | minutos |
| `double_dispatch_prevented` | Despachos dobles evitados | conteo | `api` | Intentos de despachar un incidente que ya tenía un despacho activo, bloqueados por no ser un refuerzo justificado (evento `despacho_doble_bloqueado` en la bitácora). | — |

## Indicadores de recuperación (`GET /api/v1/recovery/summary`)

Fuente: módulo de recuperación de Dacora (SIMULADO), con versión y fecha de corte. Para el rol
público las cifras menores a 5 se suprimen (se muestran como "< 5").

| Clave | Nombre en pantalla | Unidad | Definición |
|---|---|---|---|
| `predios_evaluados` | Predios evaluados | conteo | Predios distintos con al menos una evaluación de habitabilidad. Un predio es el código catastral o, si no hay, la manzana + dirección normalizada. |
| `visitas` | Visitas de inspección | conteo | Evaluaciones registradas (incluye visitas repetidas al mismo predio). `visitas − predios_evaluados` = visitas repetidas. |
| `predios_verde` / `predios_amarillo` / `predios_rojo` | Habitables · Uso restringido · No habitables | conteo | Predios según el color de su **última** evaluación. Verde admite daño menor; amarillo, menor o mediano con uso restringido; rojo, mediano, mayor o colapso (NSR-10). |
| `hogares` | Hogares en el censo único | conteo | Hogares distintos, identificados por HMAC con sal del documento del jefe de hogar. |
| `personas` | Personas damnificadas | conteo | Suma de integrantes de los hogares del censo único. |
| `rud_inscritos` | Hogares inscritos en el RUD | conteo | Hogares del censo con estado `inscrito` en el Registro Único de Damnificados. |
| `ayudas` | Ayudas entregadas | conteo | Entregas registradas (subsidio de arriendo, kit, mercado, cupo en albergue). |
| `ayudas_duplicadas` | Ayudas repetidas con justificación | conteo | Entregas del mismo tipo al mismo hogar dentro de su plazo (30 días; 7 para mercado) que se autorizaron con justificación. Sin justificación, la entrega se bloquea y no se cuenta. |
| `albergue_personas` / `albergue_mascotas` | Personas · Mascotas en albergue | conteo | Ocupación actual sumada de los albergues. |
| `albergue_capacidad` | Capacidad de albergues | conteo | Cupos totales de los albergues registrados. |

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
