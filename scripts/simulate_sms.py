"""Envía un SMS simulado al gateway de Dacora (contracts/sms-format.md).

Uso (dentro del contenedor api):
    docker compose exec api python scripts/simulate_sms.py "DACORA ATR MILAN 3 edificio caido"
    docker compose exec api python scripts/simulate_sms.py --from +573110000002 "DACORA COL ..."
El número es sintético; la API solo guarda su huella HMAC.

Por defecto el SMS se fecha con el "reloj del escenario" (último reporte recibido + 1 min) para
que pueda unirse a incidentes del sismo reproducido; --tiempo-real usa la hora actual.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta

from _client import api_client


def scenario_clock(client: object) -> datetime | None:
    """Último instante del escenario reproducido + 1 minuto (None si no hay datos)."""
    data = client.get("/incidents", params={"limit": 2000}).json()  # type: ignore[attr-defined]
    seen = [datetime.fromisoformat(i["last_seen"]) for i in data.get("items", [])]
    return max(seen) + timedelta(minutes=1) if seen else None


ADDRESS_RE = re.compile(
    r"((?:calle|carrera|avenida [A-Za-zÁÉÍÓÚáéíóú]+)(?: \d{1,3})? con (?:calle|carrera) \d{1,3})",
    re.IGNORECASE,
)


def sms_about_critical(client: object) -> str | None:
    """SMS de demo sobre el incidente crítico abierto más reciente que tenga un cruce de vías."""
    data = client.get("/incidents", params={"triage": "critico", "limit": 2000}).json()  # type: ignore[attr-defined]
    items = [i for i in data["items"] if i["status"] in ("abierto", "en_revision") and i["barrio"]]
    for inc in sorted(items, key=lambda i: i["last_seen"], reverse=True):
        detail = client.get(f"/incidents/{inc['id']}").json()  # type: ignore[attr-defined]
        for report in detail["reports"]:
            match = ADDRESS_RE.search(report["text_redacted"])
            if match:
                barrio = inc["barrio"].upper().replace(" ", "_")
                return f"DACORA ATR {barrio} 2 gente atrapada en la {match.group(1).lower()} ayuda"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="SMS simulado → POST /ingest/sms")
    parser.add_argument("body", nargs="?", help="Texto del SMS")
    parser.add_argument("--from", dest="sender", default="+573000000001", help="Remitente")
    parser.add_argument("--json", action="store_true", help="Imprime la respuesta completa")
    parser.add_argument("--tiempo-real", action="store_true", help="Usa la hora actual")
    parser.add_argument(
        "--sobre-critico",
        action="store_true",
        help="Demo: arma un SMS sobre el incidente crítico abierto más reciente (mismo cruce)",
    )
    args = parser.parse_args()

    with api_client() as client:
        body = args.body
        if args.sobre_critico:
            body = sms_about_critical(client)
            if not body:
                print("No hay incidentes críticos abiertos con dirección.", file=sys.stderr)
                return 1
            print(f"SMS de demo: {body}")
        if not body:
            parser.error("Indique el texto del SMS o use --sobre-critico")
        payload: dict[str, str] = {"from": args.sender, "body": body}
        if not args.tiempo_real:
            clock = scenario_clock(client)
            if clock:
                payload["received_at"] = clock.isoformat()
        resp = client.post("/ingest/sms", json=payload)
    if resp.status_code >= 400:
        print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
        return 1
    data = resp.json()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    r, i = data["report"], data["incident"]
    estado = "nuevo" if data["created"] else "ya existía"
    union = (
        "se unió a un incidente existente"
        if data["joined_existing_incident"]
        else "incidente nuevo"
    )
    print(
        f"Reporte {estado} · {r['category']} · {r['triage_level']}"
        f"{' · RIESGO VITAL' if r['is_life_threat'] else ''} · {r['barrio'] or 'sin ubicación'}"
    )
    print(f"  texto guardado: {r['text_redacted']}")
    if r["misinfo_signals"]:
        print(f"  señales de desinformación: {', '.join(r['misinfo_signals'])}")
    print(
        f"  {union}: {i['report_count']} reportes, {i['independent_sources']} fuentes, "
        f"trust {i['trust_score']} ({i['trust_label']}) · {data['processing_ms']} ms"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
