"""Conecta un celular Android con SIM como pasarela SMS de Dacora, por cable USB y sin internet.

Requisitos (detalle en docs/pasarela_sms.md):
- En el celular: app "SMS Gateway for Android" en modo servidor local, depuración USB activa y,
  en Ajustes → Webhooks, "Require Internet connection" apagado.
- En el portátil: `adb` (Android platform-tools) y la API de Dacora corriendo (puerto 8000), con
  SMS_GATEWAY_SIGNING_KEY igual a la "Signing Key" de la app.

Qué hace:
1. `adb reverse tcp:9876 tcp:8000`: el celular ve a Dacora en http://127.0.0.1:9876 (la app solo
   admite HTTP hacia 127.0.0.1; así no hace falta certificado ni Wi-Fi).
2. `adb forward tcp:8085 tcp:8080`: el portátil ve el servidor local de la app en
   http://127.0.0.1:8085.
3. Registra el webhook `sms:received` → http://127.0.0.1:9876/api/v1/ingest/sms-gateway.

Uso (en el portátil, desde la raíz del repo):
    python scripts/conectar_pasarela_sms.py --usuario sms --clave <clave del servidor local>
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

import httpx

PHONE_PORT_FOR_DACORA = 9876  # en el celular
PHONE_SERVER_PORT = 8080  # servidor local de la app, en el celular
LOCAL_PORT_FOR_PHONE = 8085  # en el portátil
WEBHOOK_ID = "dacora-sms"


def adb(*args: str) -> str:
    result = subprocess.run(["adb", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"adb {' '.join(args)} falló: {result.stderr.strip() or result.stdout}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usuario", required=True, help="Usuario del servidor local de la app")
    parser.add_argument("--clave", required=True, help="Clave del servidor local de la app")
    parser.add_argument(
        "--puerto-api", type=int, default=8000, help="Puerto de la API en el portátil"
    )
    args = parser.parse_args()

    if shutil.which("adb") is None:
        print(
            "No se encontró adb. Use scripts\preparar_pasarela_sms.ps1, que lo instala, o "
            "instale Android Platform-Tools (ver docs/pasarela_sms.md)."
        )
        return 1
    devices = [line for line in adb("devices").splitlines()[1:] if line.endswith("device")]
    if not devices:
        print("No hay celular conectado: conéctelo por USB y acepte la depuración USB.")
        return 1
    print(f"Celular conectado: {devices[0].split()[0]}")

    adb("reverse", f"tcp:{PHONE_PORT_FOR_DACORA}", f"tcp:{args.puerto_api}")
    adb("forward", f"tcp:{LOCAL_PORT_FOR_PHONE}", f"tcp:{PHONE_SERVER_PORT}")
    print(
        f"Túneles USB listos: celular 127.0.0.1:{PHONE_PORT_FOR_DACORA} → Dacora :{args.puerto_api}"
    )

    url = f"http://127.0.0.1:{PHONE_PORT_FOR_DACORA}/api/v1/ingest/sms-gateway"
    auth = (args.usuario, args.clave)
    base = f"http://127.0.0.1:{LOCAL_PORT_FOR_PHONE}"
    with httpx.Client(timeout=10.0, auth=auth) as client:
        try:
            resp = client.post(
                f"{base}/webhooks",
                json={"id": WEBHOOK_ID, "url": url, "event": "sms:received"},
            )
        except httpx.HTTPError as exc:
            print(
                f"No se pudo hablar con la app en el celular ({exc}). "
                "¿Está activo el servidor local?"
            )
            return 1
        if resp.status_code >= 300:
            print(f"La app rechazó el registro ({resp.status_code}): {resp.text}")
            print("Regístrelo a mano en la app con la URL:", url)
            return 1
        print(f"Webhook registrado: sms:received → {url}")
        listed = client.get(f"{base}/webhooks")
        if listed.status_code < 300:
            print("Webhooks en el celular:", listed.text)
    print("\nListo. Envíe un SMS al número de la SIM y mírelo aparecer en el tablero del PMU.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
