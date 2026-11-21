"""Reproduce el sismo SIMULADO del 10 ago 2026 contra la API REST, en tiempo acelerado.

--speed 60 (defecto): 1 hora del evento = 1 minuto real (12 min en total).
--speed 720: todo el escenario en ~1 minuto (ensayo).  --speed 0: sin esperas.
Cada 25 reportes y al final ejecuta evaluate_kpis.py, que publica los KPI en el tablero.

Uso (dentro del contenedor api):
    docker compose exec api python scripts/replay_scenario.py --reset
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import evaluate_kpis
from _client import api_client

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
MAP_PATH = evaluate_kpis.MAP_PATH


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
        start = time.monotonic()
        print(
            f"Reproduciendo {len(lines)} reportes del sismo del 10 ago 2026 "
            f"(velocidad ×{args.speed:g}; datos SIMULADOS)…"
        )
        for n, line in enumerate(lines, 1):
            if args.speed > 0:
                due = line["minute"] * 60 / args.speed
                wait = due - (time.monotonic() - start)
                if wait > 0:
                    time.sleep(wait)
            resp = client.post(line["endpoint"], json=line["body"])
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
                hh, mm = divmod(int(line["minute"]) + 7 * 60 + 34, 60)
                print(
                    f"  {hh:02d}:{mm:02d} {line['channel']:9s} {r['category']:22s} "
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
