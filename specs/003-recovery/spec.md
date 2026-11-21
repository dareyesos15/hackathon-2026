# Feature Specification: Recuperación inteligente post-sismo (bloque 6)

**Feature Branch**: `feat/006-recovery`
**Created**: 2026-11-21
**Status**: Draft
**Input**: "Punto 6" del diagrama técnico (CLAUDE.md §3 bloque 6 y §8 punto 11): evaluación de
habitabilidad con semáforo por predio, censo único de damnificados sin duplicados, ayudas con
bandera de duplicidad y albergues.

## User Scenarios

### US1 — Semáforo de habitabilidad por predio (P1)
Un inspector registra una evaluación de un predio: identificador (código catastral o manzana +
dirección normalizada), color (verde / amarillo / rojo), nivel de daño (menor, mediano con uso
restringido, mayor, colapso) y observaciones. El sistema une todas las visitas del mismo predio
bajo un único identificador, muestra el último color vigente y el número de visitas, y distingue
**predios evaluados** de **visitas realizadas** (hallazgo 3 del sismo: hasta 3 visitas al mismo
inmueble).

**Aceptación**
1. Dos evaluaciones del mismo predio escrito distinto ("Cra 23 # 45-10" y "carrera 23 45 10")
   quedan en el mismo predio con 2 visitas.
2. El estado vigente es el de la última visita.
3. Un color rojo con daño "menor" es rechazado (consistencia NSR-10 mínima).

### US2 — Censo único de damnificados (P1)
El PMU registra un hogar con el documento del jefe de hogar, número de integrantes, predio y
banderas de vulnerabilidad. El documento **nunca se guarda**: solo `HMAC-SHA256(sal, documento)`.
Si el hogar ya existe, el sistema lo indica y no crea un segundo registro. Las banderas de
vulnerabilidad se guardan en una tabla separada visible solo para PMU/COE.

**Aceptación**
1. Registrar dos veces el mismo documento (con puntos o sin ellos) responde "hogar ya registrado".
2. Ningún documento claro queda en la base.
3. El censo se exporta en CSV con columnas tipo RUD (sin datos personales).

### US3 — Ayudas sin duplicidad (P1)
Al entregar una ayuda (subsidio de arriendo, kit, mercado, albergue) se busca el hogar por su
documento (hasheado). Si el hogar ya recibió el mismo tipo de ayuda en los últimos 30 días, la
entrega queda bloqueada salvo justificación explícita, y en ese caso queda marcada como duplicada.

### US4 — Albergues (P2)
Lista de albergues (SIMULADOS) con capacidad, personas y mascotas alojadas; el PMU actualiza la
ocupación. La ocupación no puede superar la capacidad.

### US5 — Resumen con fecha de corte (P1)
Panel con: predios evaluados por color, visitas vs. predios, hogares censados, personas,
inscritos en RUD, ayudas por tipo y duplicadas bloqueadas, ocupación de albergues. Cada cifra con
fuente y fecha de corte. La vista pública solo recibe agregados con k ≥ 5 (las cifras menores se
suprimen).

## Requisitos funcionales
- FR-001 Identificador único de predio normalizado (catastral o `manzana:dirección`).
- FR-002 Evaluaciones solo-agregar; el estado vigente se calcula.
- FR-003 Hash con sal del documento del hogar; nunca se persiste el dato claro.
- FR-004 Vulnerabilidad en tabla separada con acceso restringido.
- FR-005 Bloqueo de ayuda duplicada (mismo hogar + tipo en 30 días) salvo justificación.
- FR-006 Exportación CSV del censo con columnas RUD configurables.
- FR-007 Resumen con fuente, versión y fecha de corte; k ≥ 5 para el rol público.
- FR-008 El reinicio de la demo borra los registros de recuperación y conserva los albergues.

## Fuera de alcance
Fotos de inspección, integración real con catastro/IGAC o el RUD de la UNGRD, reconstrucción y
financiación (Findeter/Bancóldex), portal "Reconstruir Mejor".
