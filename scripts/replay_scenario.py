"""Reproduce un escenario de crisis SIMULADO contra la API REST, en tiempo acelerado.

Por defecto las fechas se anclan al presente: la crisis empieza hace 12 h y su último reporte
es de ahora, así el tablero muestra la fecha de hoy. --fecha-original conserva las fechas del
escenario (sismo de referencia del 10 ago 2026).

--speed 60 (defecto): 1 hora del evento = 1 minuto real (12 min en total).
--speed 720: todo el escenario en ~1 minuto (ensayo).  --speed 0: sin esperas.
--rain: publica una curva de lluvia SIMULADA (mm en 3 h) cada hora del escenario para la capa de
efectos en cascada (specs/002 US3).
Cada 25 reportes y al final ejecuta evaluate_kpis.py, que publica los KPI en el tablero.

Uso (dentro del contenedor api):
    docker compose exec api python scripts/replay_scenario.py --reset
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import evaluate_kpis
import seed_recovery
from _client import api_client

# Lluvia acumulada en 3 h por hora del escenario (07:34 → 19:34). SIMULADA.
RAIN_CURVE_MM = [0, 0, 5, 10, 20, 30, 40, 45, 40, 30, 20, 10, 5]

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
MAP_PATH = evaluate_kpis.MAP_PATH
SHIFT_PATH = evaluate_kpis.SHIFT_PATH
WINDOW = timedelta(hours=12)
COLOMBIA = timedelta(hours=-5)
TIME_FIELDS = ("occurred_at", "received_at")


def compute_shift(original_dates: bool, reuse: bool) -> timedelta:
    """Desplazamiento para que la ventana del escenario termine ahora (reutilizable sin --reset)."""
    if original_dates:
        shift = timedelta(0)
    elif reuse and SHIFT_PATH.exists():
        return evaluate_kpis.time_shift()
    else:
        event_start = datetime.fromisoformat(evaluate_kpis.load_truth()["event_start"])
        anchor = (datetime.now(UTC) - WINDOW).replace(second=0, microsecond=0)
        shift = anchor - event_start
    SHIFT_PATH.write_text(json.dumps({"seconds": shift.total_seconds()}), encoding="utf-8")
    return shift


def shifted(body: dict, shift: timedelta) -> dict:
    if not shift:
        return body
    out = copy.deepcopy(body)
    for key in TIME_FIELDS:
        if out.get(key):
            out[key] = (datetime.fromisoformat(out[key]) + shift).isoformat()
    return out


def load_scenario(limit: int | None) -> list[dict]:
    lines = [
        json.loads(line)
        for line in (DATA_DIR / "seed" / "scenario.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return lines[:limit] if limit else lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed", type=float, default=60.0)
    parser.add_argument("--reset", action="store_true", help="Borra los datos antes de empezar")
    parser.add_argument("--eval-every", type=int, default=25)
    parser.add_argument("--no-eval", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--rain", action="store_true", help="Publica la curva de lluvia SIMULADA")
    parser.add_argument(
        "--fecha-original",
        action="store_true",
        help="Conserva las fechas del escenario en vez de anclarlas al presente",
    )
    parser.add_argument(
        "--sin-recuperacion",
        action="store_true",
        help="No siembra los datos SIMULADOS del módulo de recuperación tras --reset",
    )
    args = parser.parse_args()

    lines = load_scenario(args.limit)
    mapping: dict[str, str] = {}
    if MAP_PATH.exists() and not args.reset:
        mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    with api_client() as client:
        if args.reset:
            client.post("/demo/reset").raise_for_status()
            MAP_PATH.unlink(missing_ok=True)
            print("Datos de demo reiniciados.")
            if not args.sin_recuperacion:
                counts = seed_recovery.seed(client)
                print(
                    "Recuperación SIMULADA sembrada: "
                    + ", ".join(f"{v} {k}" for k, v in counts.items())
                    + "."
                )
        shift = compute_shift(args.fecha_original, reuse=not args.reset)
        event_start = datetime.fromisoformat(evaluate_kpis.load_truth()["event_start"]) + shift
        local_start = event_start + COLOMBIA
        start = time.monotonic()
        print(
            f"Reproduciendo {len(lines)} reportes de una crisis simulada que inicia el "
            f"{local_start:%d/%m/%Y %H:%M} (hora de Colombia; velocidad ×{args.speed:g}; "
            "datos SIMULADOS)…"
        )
        last_hour = -1
        for n, line in enumerate(lines, 1):
            if args.speed > 0:
                due = line["minute"] * 60 / args.speed
                wait = due - (time.monotonic() - start)
                if wait > 0:
                    time.sleep(wait)
            hour = int(line["minute"]) // 60
            if args.rain and hour != last_hour and hour < len(RAIN_CURVE_MM):
                last_hour = hour
                client.post(
                    "/sensors/rain",
                    json={"mm_3h": RAIN_CURVE_MM[hour], "station_code": "LLUVIA-URB-01"},
                )
            resp = client.post(line["endpoint"], json=shifted(line["body"], shift))
            if resp.status_code >= 400:
                print(
                    f"  [{line['seq']}] error {resp.status_code}: {resp.text[:200]}",
                    file=sys.stderr,
                )
                continue
            data = resp.json()
            mapping[str(line["seq"])] = data["report"]["id"]
            if not args.quiet:
                r, i = data["report"], data["incident"]
                at = local_start + timedelta(minutes=line["minute"])
                print(
                    f"  {at:%H:%M} {line['channel']:9s} {r['category']:22s} "
                    f"{r['triage_level']:8s} {'+' if data['joined_existing_incident'] else ' '} "
                    f"trust {i['trust_score']:3d} {r['barrio'] or '—'}"
                )
            if n % args.eval_every == 0 or n == len(lines):
                MAP_PATH.write_text(json.dumps(mapping), encoding="utf-8")
                if not args.no_eval:
                    evaluate_kpis.run(publish_snapshot=True, verbose=n == len(lines))

    MAP_PATH.write_text(json.dumps(mapping), encoding="utf-8")
    print(f"Listo: {len(mapping)} reportes en {time.monotonic() - start:.0f} s reales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
