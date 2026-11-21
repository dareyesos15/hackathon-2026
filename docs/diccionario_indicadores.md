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

## Tablero de recuperación unificado (`GET /api/v1/recovery/dashboard`)

Solo para PMU/COE. Regla de oro: cada cifra lleva su nombre de este diccionario, fuente, versión y
hora de corte, y se cuentan **predios únicos, no visitas**. Lo que Dacora registra se calcula en
vivo; las fuentes externas (servicios, economía, finanzas, réplicas, solicitudes de visita) son
**SIMULADAS** y vienen de `data/seed/recovery_context.json` (`scripts/generate_recovery_context.py`).

| N.º | Indicador | Claves | Fuente | Definición |
|---|---|---|---|---|
| 1 | Familias damnificadas únicas | `familias_unicas`, `personas_damnificadas`, `rud_inscritos` | Censo de Dacora · RUD (UNGRD) | Hogares distintos por HMAC del documento; exportables en formato RUD. |
| 2 | Predios evaluados únicos contra pendientes | `predios_evaluados`, `predios_pendientes`, `visitas_repetidas_evitadas` | Inspectores en Dacora · solicitudes de la Alcaldía · catastro | Pendientes = por barrio, solicitudes de visita − predios evaluados (nunca negativo). Visitas repetidas = visitas − predios evaluados. |
| 3 | Viviendas por semáforo NSR-10 | `predios_verde`, `predios_amarillo`, `predios_rojo`, `predios_colapso` | EDAN en Dacora | Última evaluación de cada predio; **colapsado** = daño `colapso` (se descuenta de rojo). También por barrio. |
| 4 | Índice de recuperación | `indice_recuperacion`, `barrios_bajo_50` | Calculado por Dacora | Promedio con igual peso de: habitabilidad (verde + ½ amarillo sobre evaluados, ind. 3), servicios (promedio de los 5 servicios, ind. 6), familias en casa (ind. 7) y negocios reabiertos sobre cerrados (ind. 9). Un componente sin datos no cuenta. Curva día 0–90: histórico SIMULADO + valor de hoy en vivo. |
| 5 | Días desde el evento y riesgo activo | `dias_desde_evento`, `replicas_7d`, `replica_max`, `lluvia_3h` | SGC · estaciones UNAL y Corpocaldas | Días completos desde el 10 ago 2026, 07:34. Lluvia: última lectura de `/sensors/rain` o, si no hay, la del contexto; alerta si alcanza el umbral de deslizamiento (25 mm en 3 h, SIMULADO). |
| 6 | Servicios básicos | `servicio_agua`, `servicio_energia`, `servicio_gas`, `servicio_telecom`, `servicio_vias` | Aguas de Manizales, CHEC, Efigas, Obras Públicas | % de usuarios o tramos con servicio, promedio de los barrios; por barrio con fecha estimada de restablecimiento. |
| 7 | Familias por situación y ayudas | `familias_albergue`, `familias_arriendo`, `familias_casa`, `familias_sin_solucion`, `ayudas_entregadas`, `ayudas_repetidas`, `personas_albergue` | UGR, Cruz Roja y Dacora | Situación por la última ayuda de vivienda del hogar (cupo en albergue o subsidio de arriendo). **Sin solución** = predio rojo sin ninguna de las dos. |
| 8 | Calidad de los reportes | `reports_received`, `incidents_consolidated`, `critical_in_human_queue`, `duplicate_detection_rate`, `fake_detection_rate`, `critical_auto_discarded` | Motor de Dacora y `evaluate_kpis.py` | Las tasas son la última instantánea de `evaluate_kpis.py` (metas > 90 %); críticos en cola = reportes con riesgo vital en estado nuevo o en revisión. |
| 9 | Negocios reabiertos y empleos recuperados | `negocios_reabiertos`, `negocios_cerrados`, `empleos_recuperados`, `empleos_perdidos` | Cámara de Comercio, DANE | Por comuna y total de la ciudad. |
| 10 | Recursos y trazabilidad | `perdida_estimada`, `recursos_disponibles`, `brecha`, `comprometido`, `contratado`, `pagado`, `verificado`, `dias_pago` | Hacienda, UNGRD, SECOP, aseguradoras | Brecha = pérdida estimada − recursos por fuente. Embudo en % del comprometido. |

**Necesidades** (lo que se necesita hoy): se derivan de los indicadores y solo aparecen si su
valor es mayor que cero: críticos en cola humana y lluvia sobre el umbral (críticas); familias sin
solución de vivienda (crítica); hogares vulnerables sin ninguna ayuda, predios pendientes y
albergues al 90 % (altas); barrios con un servicio < 80 % y brecha financiera (medias).

**Ciclo económico (parte B):** cinco etapas con su ventana de días. Avance de cada etapa: 1 El
golpe = predios evaluados ÷ solicitudes de visita; 2 La plata disponible = recursos ÷ pérdida;
3 La plata en movimiento = beneficios pagados ÷ aprobados; 4 La reactivación = negocios
reabiertos ÷ cerrados; 5 La estabilización = promedio de ICA, turismo y café frente a antes del
sismo. Semáforo: el avance esperado crece lineal dentro de la ventana y es 100 % al cerrarla;
**verde** (a tiempo) si el avance ≥ 90 % de lo esperado, **amarillo** (con retraso) si ≥ 60 %,
**rojo** (estancada) si es menor; *aún no empieza* antes de la ventana.

## Sensor de zonas inseguras (`/api/v1/sensors/zones`, patente NC2025/0015763)

Fuente: "SIMULADO · patente NC2025/0015763", con hora de cada evento y fecha de corte del listado.

| Término | Definición |
|---|---|
| Cono de vigilancia | Espacio configurado del sensor: alcance (m) y semiapertura (°) alrededor de su rumbo. Por defecto 12 m y ±30°. |
| Intrusión | Persona u objeto dentro del cono detectado por ultrasonido, infrarrojo o ambos, **sin** tarjeta RFID registrada (o con una desconocida). Es alarma hasta que alguien la marca *Atendida*. |
| Acceso autorizado | Detección dentro del cono con una tarjeta RFID registrada (personal de Bomberos, Defensa Civil, Cruz Roja o Infraestructura). No es alarma. |
| Batería baja | Lectura con batería del equipo < 15 %. |
| Manipulación | Apertura de la carcasa del equipo. Es alarma. |
| Alarmas sin atender | Intrusiones y manipulaciones sin atención registrada. |
| Confirmación por sensor de campo | Señal del puntaje de veracidad (10 pts): intrusión detectada por **ambos** detectores a ≤ 150 m del incidente, en las últimas 3 h, para incidentes de personas atrapadas, colapso de estructura o daño estructural. |

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
