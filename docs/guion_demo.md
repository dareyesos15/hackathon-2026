# Guion de la demo · Dacora (3–4 min)

Para cualquier integrante del equipo. Todos los datos son **SIMULADOS**.

## Antes de la presentación (10 min antes)

1. Docker Desktop abierto. En la carpeta del repositorio:
   ```bash
   docker compose up -d --build
   docker compose exec api python scripts/replay_scenario.py --reset --speed 720 --quiet
   ```
   Al final debe decir **"Todas las metas P0 cumplidas"**.
2. En el navegador del portátil, tres pestañas:
   - **A:** http://localhost:8080 → Operador del PMU → *Entrar* (queda en `/pmu/`).
   - **B:** http://localhost:8080/pmu/kpi/ (abrirla desde la A con "Panel de KPI").
   - **C:** http://localhost:8080/reportar/ → aceptar el aviso de privacidad.
   - **D:** http://localhost:8080/recuperacion/ (desde la A con "Recuperación").
3. Celular (opcional), misma red Wi-Fi: `http://<IP-del-portátil>:8080/reportar/`, aceptar el aviso
   y **dejar la página abierta**. (Sin https no hay service worker; el outbox sí funciona.)
4. Una terminal lista en la carpeta del repositorio.
5. Para mostrar el mapa llenándose en vivo, reinicie justo antes de empezar:
   ```bash
   docker compose exec api python scripts/replay_scenario.py --reset --speed 120
   ```
   (6 min de reproducción; arranque esto al iniciar el paso 2.)

## Guion

| # | Tiempo | Qué decir | Qué hacer |
|---|---|---|---|
| 1 | 0:00–0:20 | "El 10 de agosto, las viviendas con afectación total pasaron de 1.449 a 2.700 y luego a 1.512 en tres días. Manizales no tuvo cobertura satelital y el 123 se saturó." | Pestaña A con el tablero vacío o recién reiniciado. |
| 2 | 0:20–0:50 | "Reproducimos el sismo: 254 reportes por app, SMS, WhatsApp, 123 y entidades. Dacora quita datos personales, clasifica, agrupa duplicados y calcula un puntaje de veracidad en milisegundos." | Terminal: `replay_scenario.py --reset --speed 120`. Señalar el mapa llenándose y el indicador **En vivo**. |
| 3 | 0:50–1:30 | "Sin señal también se reporta." | Celular en **modo avión** (o pestaña C con DevTools → Network → *Offline*). Escribir: `hay 2 heridos en la calle 30 con carrera 24, me llamo Ana cel 3001234567`, elegir barrio **Centro**, enviar. Mostrar "Guardado en su teléfono" y el aviso de privacidad que ya reemplazó nombre y teléfono. Quitar modo avión → pasa a **Enviado** y aparece en el tablero. |
| 4 | 1:30–2:00 | "Llega un SMS de personas atrapadas: entra como Crítico y se une al incidente que ya existía; no es basura, suma corroboración." | Terminal: `docker compose exec api python scripts/simulate_sms.py --sobre-critico`. Leer "se unió a un incidente existente: N reportes, N fuentes". |
| 5 | 2:00–2:40 | "Este es un rumor de WhatsApp: Posible falso, y el sistema explica por qué." | En la matriz, categoría **Rumor / información** → abrir uno → desglose: canal WhatsApp, señales "reenvía", "dicen que", "réplica de 9". |
| 6 | 2:40–3:10 | "La IA solo sugiere: un reporte con riesgo vital nunca se descarta solo. Para descartarlo, un humano deja una nota que queda en la bitácora." | Abrir un incidente **Crítico** → intentar *Descartar* sin nota (botón deshabilitado) → *Confirmar* → mostrar la bitácora con rol y hora. |
| 6b | +0:30 | "Despachamos Bomberos: el sistema sugiere la agencia según la EMRE, el recurso más cercano y bloquea el doble despacho; se ve el recorrido del vehículo." | Abrir el incidente **Crítico** de Milán → sección *Despacho* → marcar la máquina más cercana → *Despachar*. Ver el recorrido morado en el mapa (llega en ~20 s). Intentar despachar otro recurso: pide justificar un refuerzo. |
| 6c | +0:30 | "Llueve sobre laderas ya golpeadas: Dacora anticipa el siguiente deslizamiento, pero solo el COE emite la alerta." | Pestaña *Cascada* → activar la capa → subir la lluvia a 40 mm → tocar una manzana **Muy alto** → *Crear alerta preventiva* → mensaje corto → *Guardar borrador*. Pestaña *Alertas* → *Aprobar y emitir* (Entidades y PMU incluye la autoridad del COE). Mostrar el aviso rojo en el tablero y en la página de inicio pública (`/`, en una pestaña sin sesión). |
| 6d | +0:30 | "En los edificios acordonados, el dispositivo UNAL de monitoreo de zonas inseguras (patente NC2025/0015763) avisa si alguien entra. Reconoce por RFID a los rescatistas y no da falsas alarmas; si detecta a alguien dentro de un colapso, eso corrobora el reporte." | Pestaña *Zonas*: el contador rojo muestra alarmas abiertas y el mapa solo los sensores. Elegir un incidente de **Colapso** → *Instalar*. En el sensor nuevo: *Simular rescatista con RFID* (acceso autorizado, sin alarma) → *Simular intrusión* (alarma roja + "corrobora 1 incidente: +10 pts"). *Ver incidente* → desglose: **sensor de campo 10/10**. Volver a *Zonas* → *Atender*. |
| 7 | 3:10–3:40 | "Resultados medidos contra la verdad del escenario: más de 90 % de duplicados y falsos detectados, cero críticos descartados por la IA, cada hecho en el mapa en minutos y no en días. Cada cifra con fuente y fecha de corte." | Pestaña B (Panel de KPI). |
| 7b | +0:40 | "Después de la emergencia viene la recuperación. En el sismo hubo hasta 3 visitas al mismo inmueble y ayudas que se entregaban dos veces. Aquí cada predio es uno solo y cada hogar también." | Pestaña D → *Habitabilidad*: registrar un predio **Rojo / Mayor** en una manzana de Milán con `Cra 23 # 45-10`; repetir con `carrera 23 45 10` → aviso "visita n.º 2" unida al mismo predio. *Censo único*: registrar el documento `1053123456`, 4 personas, niñez; repetirlo como `1.053.123.456` → "ya estaba registrado". *Ayudas*: entregar *Mercado* a ese documento y repetir → bloqueada; pide justificación. *Resumen*: predios vs. visitas, hogares, ayudas, con fuente y fecha de corte. |
| 8 | 3:40–4:00 | "Todo corre en un portátil sin internet, con Habeas Data desde el diseño y software abierto: del documento del hogar solo guardamos un código cifrado. Siguiente paso: sensores RAMAN e infraestructura y servicios." | Volver al tablero. |

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| El tablero dice **Modo de respaldo** | Normal: consulta cada 3 s. Seguir con la demo. |
| El mapa no carga | Recargar la pestaña. Si persiste: `docker compose restart web`. |
| El panel de KPI está vacío | `docker compose exec api python scripts/evaluate_kpis.py` |
| El celular no abre la página | Usar la pestaña C del portátil con DevTools *Offline*. |
| El recurso no avanza en el mapa | Esperar ~20 s (`TRACK_SPEEDUP=20`) o, en *Despachos por agencia*, marcar *Llegamos al sitio*. |
| La capa de cascada no cambia | Mover de nuevo el control de lluvia y soltarlo; se recalcula en < 10 s. |
| Hay que repetir la demo desde cero | Entrar como **Administrador** (`/admin/`) → *Iniciar simulación con datos* (o *Empezar sin datos* para reportes en vivo). |
| Nada responde | `docker compose down && docker compose up -d` (los datos se conservan) y repetir la reproducción con `--speed 720`. |
| La recuperación se ve vacía tras reiniciar | Normal: el reinicio también borra inspecciones, censo y ayudas. Registrar de nuevo en la pestaña D. |
| No veo incidentes en el mapa | El mapa muestra solo el módulo de la pestaña activa: volver a *Triaje*, o en *Capas del mapa* desmarcar "solo el módulo de la pestaña activa" y elegir los módulos. |
| La pestaña *Zonas* no tiene eventos | Esperar unos segundos (`ZONE_TICK_S=6`) o usar *Simular intrusión* en un sensor. |
| Último recurso | Video/GIF de respaldo (ver abajo). |

## Video de respaldo

- **GIF (listo):** `dacora_demo_respaldo.gif` en la carpeta *Descargas* del portátil de desarrollo
  (≈ 2,4 MB, 10 cuadros): el tablero llenándose con los 254 reportes y el panel de KPI. Se mantiene
  fuera del repositorio; súbalo a la carpeta de Drive del equipo.
- **Video completo (recomendado):** grabar la demo de punta a punta con el modo avión del celular
  (QuickTime → *Nueva grabación de pantalla*) y anotar aquí su ubicación.
