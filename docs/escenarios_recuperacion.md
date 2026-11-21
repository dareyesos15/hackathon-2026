# Escenarios de acceso a datos: confianza del tablero de recuperación (SIMULADO)

> Generado con `scripts/simulate_recovery_scenarios.py` el 2026-11-21 11:55 UTC · 2000 corridas por escenario y día · semilla fija. **Todas las cifras son SIMULADAS**: miden cuánto se acercaría el tablero a la realidad según cómo le lleguen los datos, no son cifras del evento.

## Método

1. **Una sola verdad simulada** del sismo del 10 ago 2026 en Manizales: ~2.000 predios con daño, ~2.700 familias damnificadas, cobertura de agua, energía, gas, telecomunicaciones y vías, negocios y empleo, pérdida, recursos y pagos, recaudo, turismo y café, evolucionando con una curva de recuperación por días.
2. **Dos procesos de observación** sobre esa misma verdad: qué fuentes entregan dato en cada corte, cuánto se subregistra, cuánto ruido trae cada cifra, cuántos duplicados quedan sin unir y con qué retraso llega frente a la cadencia de la EMRE (6 h los 3 primeros días, 12 h hasta el día 5 y 24 h después). Los primeros días son más caóticos (red y energía inestables) y ese efecto decae con el tiempo.
3. **Monte Carlo**: en cada corrida se compara lo que vería el tablero con la verdad. Se reporta la media y el intervalo del 90 % (percentiles 5 y 95).

**Confianza global (0–100)** = 30 % cobertura + 20 % frescura + 35 % exactitud + 15 % duplicados detectados.

- *Cobertura*: cifras del tablero con dato.
- *Frescura*: cifras con dato dentro de la cadencia EMRE.
- *Exactitud*: cifras dentro de ±10 % de la realidad (±5 puntos en porcentajes); las cifras sin dato cuentan como no exactas.
- *Error del índice*: puntos de diferencia entre el índice de recuperación que ve el tablero y el real.

## Supuestos de cada escenario

### Mejor caso: colaboración institucional y datos constantes

Convenios activos con todas las entidades, identificador único de predio y hogar, red disponible y reportes con la cadencia de la EMRE.

- Cada fuente entrega dato en 90–99 % de los cortes.
- Se registra ~97 % de la realidad (subregistro ~3 %).
- Error de medición ~3 % en conteos y montos; ±2 puntos en porcentajes.
- 12 % de registros repetidos; 97 % se unen por identificador único.
- Edad media del dato: 4 h (cadencia EMRE: 6–24 h).
- Primeros días: hasta 15 % menos de disponibilidad y el doble de ruido (red y energía inestables); el efecto decae con los días.
- Disponibilidad por fuente: dacora 99%, alcaldia 97%, servicios 95%, economia 92%, finanzas 95%, estabilizacion 90%

### Peor caso: datos inconsistentes o ausentes

Sin convenios, cortes de energía y red celular, cifras que cambian entre cortes, sin identificador común entre entidades y reportes atrasados días.

- Solo el registro propio entrega dato con regularidad (70 %); servicios, economía y estabilización casi nunca (5–10 %).
- Se registra ~55 % de la realidad, con mucha variación entre cortes (±20 %).
- Error de medición ~25 %; ±15 puntos en porcentajes.
- 35 % de registros repetidos; solo 55 % se unen (sin identificador común).
- Edad media del dato: 60 h, muy por encima de la cadencia EMRE.
- Primeros días: hasta 50 % menos de disponibilidad y el doble de ruido (cortes de energía y red celular); el efecto decae con los días.
- Disponibilidad por fuente: dacora 70%, alcaldia 45%, servicios 10%, economia 5%, finanzas 20%, estabilizacion 5%

## Resultado hoy (día 102)

| Métrica | Mejor caso: media (IC 90 %) | Peor caso: media (IC 90 %) |
|---|---|---|
| Confianza global del sistema | **95,7 %** (84,4 % a 100,0 %) | **22,8 %** (8,2 % a 37,6 %) |
| Cobertura: cifras con dato | **96,2 %** (83,3 % a 100,0 %) | **35,2 %** (0,0 % a 60,0 %) |
| Frescura: dato dentro de la cadencia EMRE | **95,8 %** (83,3 % a 100,0 %) | **12,2 %** (0,0 % a 43,3 %) |
| Exactitud: cifras dentro de ±10 % de la realidad | **94,8 %** (80,0 % a 100,0 %) | **4,5 %** (0,0 % a 16,7 %) |
| Duplicados detectados | **96,7 %** (92,0 % a 100,0 %) | **54,9 %** (50,1 % a 59,8 %) |
| Error medio de las cifras con dato | **3,0 %** (1,8 % a 4,9 %) | **40,0 %** (14,6 % a 75,6 %) |
| Error del índice de recuperación | **1,1 pts** (0,1 pts a 2,9 pts) | **11,6 pts** (2,1 pts a 21,2 pts) |
| Corridas con confianza ≥ 75 % | **98,2 %** | **0,0 %** |

## Confianza global a lo largo de la recuperación

| Día | Mejor caso: media (IC 90 %) | Peor caso: media (IC 90 %) | Diferencia |
|---|---|---|---|
| 1 | **76,7 %** (47,5 % a 95,0 %) | **15,3 %** (7,8 % a 28,7 %) | 61,4 pts |
| 7 | **87,5 %** (60,9 % a 99,3 %) | **19,1 %** (7,9 % a 34,1 %) | 68,4 pts |
| 15 | **91,7 %** (69,7 % a 99,9 %) | **21,5 %** (8,0 % a 36,3 %) | 70,2 pts |
| 30 | **94,9 %** (83,1 % a 100,0 %) | **22,2 %** (8,1 % a 36,8 %) | 72,7 pts |
| 60 | **95,0 %** (82,3 % a 100,0 %) | **22,8 %** (8,2 % a 37,3 %) | 72,2 pts |
| 90 | **95,4 %** (84,1 % a 100,0 %) | **22,9 %** (8,2 % a 38,1 %) | 72,5 pts |
| 102 | **95,7 %** (84,4 % a 100,0 %) | **22,8 %** (8,2 % a 37,6 %) | 72,9 pts |

## Cómo leerlo

- Con colaboración institucional, el tablero refleja la realidad casi siempre: las decisiones del COE se pueden tomar sobre sus cifras.
- Sin ella, el tablero ve una fracción de la realidad, desactualizada y con duplicados: sirve para alertar, pero cada cifra necesita verificación en terreno. Es lo que pasó en 2026 (1.449 → 2.700 → 1.512 viviendas) y en 1999 (35.000 estimadas frente a 79.500 censadas).
- La brecha entre ambos escenarios es el valor de los convenios del plan de 30–90 días.
