"""Envía un SMS simulado al gateway de Dacora (contracts/sms-format.md).

Uso (dentro del contenedor api):
    docker compose exec api python scripts/simulate_sms.py "DACORA ATR MILAN 3 edificio caido cra 23"
    docker compose exec api python scripts/simulate_sms.py --from +573110000002 "DACORA COL ..."
El número es sintético; la API solo guarda su huella HMAC.
"""

from __future__ import annotations

import argparse
import json
import sys

from _client import api_client


def main() -> int:
    parser = argparse.ArgumentParser(description="SMS simulado → POST /ingest/sms")
    parser.add_argument("body", help="Texto del SMS")
    parser.add_argument("--from", dest="sender", default="+573000000001", help="Remitente")
    parser.add_argument("--json", action="store_true", help="Imprime la respuesta completa")
    args = parser.parse_args()

    with api_client() as client:
        resp = client.post("/ingest/sms", json={"from": args.sender, "body": args.body})
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
