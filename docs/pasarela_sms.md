# Pasarela SMS con un celular Android (Plan B sin internet)

Un celular Android con SIM recibe los SMS de la ciudadanía y los entrega a Dacora **por cable
USB**, sin internet ni Wi-Fi. Cada SMS entra al mismo motor que los demás reportes: se borran los
datos personales, se clasifica, se prioriza, se une a su incidente y aparece en el mapa del PMU.

```
Ciudadano ──SMS──▶ Celular con SIM (app de pasarela) ──USB/adb──▶ Portátil del PMU (Dacora)
```

- **Texto libre o formato compacto:** "Se cayó una casa en Milán, hay 2 atrapados" funciona igual
  que `DACORA ATR MILAN 2 casa caida`.
- **Seguro:** cada SMS llega firmado (HMAC-SHA256); Dacora rechaza firmas falsas y mensajes de
  más de 5 minutos.
- **Sin duplicados:** si la app reintenta, Dacora reconoce el mismo SMS por su identificador.
- **Habeas Data:** el número del remitente solo se guarda como huella cifrada.

## Para quien lo vaya a ejecutar (resumen)

**En el celular** (una vez, ≈ 10 min):

1. Instalar **SMS Gateway for Android** (sms-gate.app o Google Play), aceptar los permisos de
   SMS y quitarle la optimización de batería.
2. En **Home**, activar **Local Server** y anotar el **usuario** y la **clave**.
3. En **Ajustes → Webhooks**: apagar **"Require Internet connection"**. La **Signing Key** se
   llena en el paso de abajo (empieza vacía: es normal).
4. Activar **Opciones de desarrollador → Depuración USB** (tocar 7 veces "Número de
   compilación" en *Acerca del teléfono*).

**En el portátil** (Windows, con Docker Desktop abierto y el repositorio actualizado):

```powershell
git pull
powershell -ExecutionPolicy Bypass -File scripts\preparar_pasarela_sms.ps1
```

El script hace todo lo demás y se puede repetir sin problema:

| Paso del script | Qué hace | Qué tiene que hacer usted |
|---|---|---|
| 1 | Verifica Docker y encuentra la demo en uso | — |
| 2 | Crea la clave de firma en `.env` si no existe y **la muestra** | **Escribirla en el celular** en *Ajustes → Webhooks → Signing Key*, sin espacios |
| 3 | Reconstruye la API y comprueba que la pasarela responde | — |
| 4 | Instala `adb` si falta | — |
| 5 | Espera el celular por USB | Conectar el cable de datos y tocar **Permitir** en "¿Permitir depuración USB?" |
| 6 | Conecta la app con Dacora | Escribir el **usuario** y la **clave** del Local Server |

Al final: enviar un SMS al número de la SIM desde otro celular y mirarlo en
`http://localhost:8080/pmu/`. **Cada vez que se desconecte el cable o se reinicie el portátil**,
volver a correr el script (solo vuelve a crear los túneles).

## Qué se necesita

| En el celular | En el portátil |
|---|---|
| Android con SIM activa | Dacora corriendo (`docker compose up -d`), API en el puerto 8000 |
| App **SMS Gateway for Android** (sms-gate.app, código abierto) | **adb**: [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) |
| Cable USB | Python con `httpx` (o `uv run --project services/api`) |

## Preparación (una vez, ≈ 15 min, mejor antes del día de la demo)

1. **Instalar la app** en el celular desde su página oficial (sms-gate.app) y darle los permisos
   de SMS.
2. En la app, activar **Local Server** y anotar el **usuario y la clave** que muestra.
3. En **Ajustes → Webhooks**:
   - Apagar **"Require Internet connection"** (si no, espera internet para entregar).
   - Copiar la **Signing Key**.
4. En el portátil, poner esa clave en `.env` y reiniciar la API:
   ```bash
   SMS_GATEWAY_SIGNING_KEY=<Signing Key de la app>
   docker compose up -d api
   ```
5. En el celular, activar las **Opciones de desarrollador** y la **Depuración USB**; conectar el
   cable y aceptar la huella del portátil.

## Conectar (cada vez que se enchufa el celular)

```bash
uv run --project services/api python scripts/conectar_pasarela_sms.py --usuario <usuario> --clave <clave>
```

El script crea los túneles por USB (`adb reverse` y `adb forward`) y registra el webhook
`sms:received` → `http://127.0.0.1:9876/api/v1/ingest/sms-gateway`. La app solo permite HTTP sin
cifrar hacia `127.0.0.1`; el túnel USB es lo que hace que esa dirección llegue al portátil.

**Prueba:** envíe un SMS al número de la SIM desde otro celular, por ejemplo *"Se cayó una casa
en Milán, hay 2 personas atrapadas"*. En segundos aparece en el tablero del PMU como **Crítico**,
canal SMS.

## En el pitch (30 s)

1. *"Se cae internet. La ciudadanía todavía tiene SMS."*
2. Pedirle a alguien del jurado que envíe un SMS al número de la SIM.
3. Mostrar el reporte apareciendo en el mapa del PMU, clasificado y priorizado.
4. *"El celular está conectado por cable al portátil del PMU: no hubo internet en ningún paso."*

Respaldo si algo falla: `docker compose exec api python scripts/simulate_sms.py "..."`. Decir que
es el mismo canal, simulado.

## Si no se puede usar cable

| Opción | Cuándo |
|---|---|
| **Wi-Fi con certificado del proyecto** (sms-gate.app ofrece una CA para IP privadas; la app ya confía en ella) | Producción con IP fija en el PMU. Requiere internet una vez para emitir el certificado |
| **Wi-Fi con la APK "insegura"** de la app (permite HTTP en la red local) | Solo demostración: la propia documentación de la app desaconseja usarla en producción |

## Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| El script dice "no hay celular conectado" | Falta aceptar la depuración USB en el celular, o el cable solo carga |
| El SMS no llega y la cola de webhooks de la app muestra error 401 | La Signing Key de la app no coincide con `SMS_GATEWAY_SIGNING_KEY` |
| Error 503 | Falta configurar `SMS_GATEWAY_SIGNING_KEY` en el portátil |
| La app no envía sin internet | "Require Internet connection" sigue encendido |
| Error 401 "fuera de la ventana de 5 minutos" | La hora del celular o del portátil está desfasada |

> Verificado del lado de Dacora con webhooks firmados de prueba (formato documentado por la app).
> Probar con el celular real antes del pitch: la API de registro de webhooks del servidor local
> no tiene un ejemplo oficial; si el script no logra registrarlo, hacerlo a mano en la app.
