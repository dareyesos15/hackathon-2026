# Feature Specification: Sensor de zonas inseguras (patente NC2025/0015763, SIMULADO)

**Feature Branch**: `feat/zone-sensor-mock`
**Created**: 2026-11-21
**Status**: Draft
**Input**: "Implementa un mock que simule datos de la patente uno" — ficha SIPI "Patentes UNAL del
Reto 5", patente 1: *Dispositivo de monitoreo de zonas inseguras* (modelo de utilidad, UNAL).

## Contexto de la patente
Dispositivo portátil que detecta personas u objetos dentro de un **espacio cónico configurable**.
Unidad principal (100) con **sensores ultrasónicos e infrarrojos**, procesamiento, alarma y antena;
unidad de configuración (200) inalámbrica; **módulo RFID (300)** que reconoce a usuarios
autorizados: si la persona lleva una tarjeta autorizada no salta la alarma. Baterías recargables.
Uso en la Vertical 5: edificios acordonados tras el sismo; avisa al PMU si alguien entra a una
zona con riesgo de colapso; distingue rescatistas (RFID) de civiles.

## Historias
### US1 — Alarma de intrusión en el tablero (P1)
El PMU ve en el mapa los sensores instalados con su cono de vigilancia. Cuando un sensor detecta a
una persona sin tarjeta autorizada dentro del cono, el cono se pone rojo y aparece una alarma en
la pestaña **Zonas** con hora, sensor, detector (ultrasonido, infrarrojo o ambos), distancia y
tarjeta leída. Un operador la marca **Atendida** (queda quién y cuándo).

**Aceptación**: una lectura dentro del cono sin tarjeta → `intrusion`; con tarjeta registrada →
`acceso_autorizado` (sin alarma); fuera del cono → no genera evento; tarjeta desconocida →
`intrusion`.

### US2 — Estado del dispositivo (P2)
Cada sensor muestra batería, última señal y estado (armado, sin señal). Batería < 15 % genera
`bateria_baja`; apertura de la carcasa genera `manipulacion`.

### US3 — Corroboración del puntaje de veracidad (P1)
Una intrusión detectada por **ambos** detectores a ≤ 150 m de un incidente de personas atrapadas,
colapso o daño estructural en las últimas 3 h suma la señal "Confirmación por sensor de campo"
(10 pts, CLAUDE.md §7.4) en el desglose del incidente.

### US4 — Instalar un sensor (P2)
Desde la pestaña Zonas, el PMU instala un sensor (SIMULADO) en el incidente seleccionado o en un
punto, con alcance y apertura del cono.

### US5 — Simulación (P1)
Un simulador en la API genera lecturas sintéticas (rescatistas con RFID, civiles sin tarjeta,
lecturas fuera del cono, batería) cada pocos segundos, por la misma función que usaría un
dispositivo real (`POST /sensors/zones/{id}/readings`). Todo se marca SIMULADO.

## Requisitos
- FR-001 Interfaz `ZoneSensorFeed` con implementación simulada por defecto (`SIMULATE_ZONE_SENSORS`).
- FR-002 Clasificación pura: cono (alcance, semiapertura), detectores, RFID, batería, manipulación.
- FR-003 Eventos solo-agregar; la atención guarda rol y hora.
- FR-004 Sin datos personales: las tarjetas son códigos de credencial institucional.
- FR-005 El reinicio de la demo borra eventos y conserva sensores y credenciales.
