"""Genera el escenario SIMULADO del sismo del 10 ago 2026 (07:34, M 7,4) para Manizales.

Salidas (data/seed/):
- scenario.jsonl     → lo único que ve el sistema: una petición REST por línea, con su minuto.
- ground_truth.json  → verdad del escenario (único / duplicado / falso). Solo la lee
                       scripts/evaluate_kpis.py; el motor nunca la ve (principio IV).

Mezcla objetivo (CLAUDE.md §10): ~55 % únicos, ~30 % duplicados, ~15 % falsos o rumores.
Todos los nombres, teléfonos y cédulas son sintéticos (Ley 1581 de 2012).
Uso: python scripts/generate_scenario.py [--seed 20260810] [--events 140]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT_START = datetime(2026, 8, 10, 12, 34, tzinfo=UTC)  # 07:34 hora de Colombia
WINDOW_MIN = 12 * 60
NAMESPACE = uuid.UUID("0f6b2c55-8a7e-4a51-9d0f-2a1d5e0c7b10")

# ------------------------------------------------------------------ catálogo de hechos

CATEGORY_WEIGHTS = {
    "personas_atrapadas": 8,
    "heridos": 9,
    "colapso_estructura": 8,
    "dano_estructural": 22,
    "incendio": 4,
    "fuga_gas": 5,
    "deslizamiento": 6,
    "via_bloqueada": 8,
    "servicios_caidos": 10,
    "necesidad_albergue": 5,
    "necesidad_ayuda": 7,
    "persona_desaparecida": 3,
    "sismo_sentido": 5,
}
SMS_CODE = {
    "personas_atrapadas": "ATR",
    "heridos": "HER",
    "colapso_estructura": "COL",
    "dano_estructural": "DAN",
    "incendio": "INC",
    "fuga_gas": "GAS",
    "deslizamiento": "DES",
    "via_bloqueada": "VIA",
    "servicios_caidos": "SER",
    "necesidad_albergue": "ALB",
    "necesidad_ayuda": "AYU",
    "persona_desaparecida": "DSP",
}
CRITICAL = {"personas_atrapadas", "heridos", "incendio", "fuga_gas"}

OBJECTS = [
    "edificio",
    "casa",
    "bodega",
    "colegio",
    "local",
    "edificio de apartamentos",
    "casa de bahareque",
    "inquilinato",
    "parqueadero",
    "taller",
]
FAMILY = ["mamá", "papá", "abuela", "abuelo", "hermano", "hija", "tío"]
NAMES = [
    "Carolina",
    "Andrés",
    "Luz Marina",
    "Jhon Fredy",
    "Paola",
    "Hernán",
    "Yuliana",
    "Óscar",
    "Martha",
    "Esteban",
    "Natalia",
    "Wilson",
    "Sandra",
    "Mauricio",
]

TEMPLATES: dict[str, list[str]] = {
    "personas_atrapadas": [
        "se cayó el {obj} de la {dir} en {barrio}, hay {n} personas atrapadas",
        "hay gente atrapada en el {obj} de la {dir}, {barrio}, ayuda urgente",
        "ayuda!! {n} personas bajo los escombros en la {dir} ({barrio})",
        "quedaron personas adentro del {obj} en la {dir}, {barrio}, no pueden salir",
        "se escuchan gritos en el {obj} caído de la {dir}, {barrio}, hay atrapados",
    ],
    "heridos": [
        "hay {n} heridos en la {dir}, {barrio}, necesitamos ambulancia",
        "personas heridas por caída de la fachada del {obj} en la {dir}, {barrio}",
        "{n} lesionados frente al {obj} de la {dir} en {barrio}, uno sangrando mucho",
        "necesitamos paramédicos en la {dir} de {barrio}, hay heridos",
    ],
    "colapso_estructura": [
        "colapsó el {obj} de la {dir} en {barrio}",
        "se derrumbó el {obj} de la {dir}, {barrio}, estaba desocupado",
        "se vino abajo el {obj} en la {dir} ({barrio})",
        "el {obj} de la {dir} en {barrio} se desplomó",
    ],
    "dano_estructural": [
        "grietas grandes en las columnas del {obj} de la {dir}, {barrio}",
        "se cayó parte de la fachada del {obj} en la {dir}, {barrio}",
        "muro agrietado y tejas caídas en el {obj} de la {dir}, {barrio}",
        "el {obj} de la {dir} en {barrio} quedó con fisuras en las paredes",
        "daños en el techo y paredes del {obj}, {dir}, {barrio}",
    ],
    "incendio": [
        "incendio en el {obj} de la {dir}, {barrio}, hay mucho humo",
        "fuego en el {obj} de la {dir} en {barrio}, llamen a bomberos",
        "se está quemando el {obj} de la {dir} ({barrio}), salen llamas",
    ],
    "fuga_gas": [
        "huele mucho a gas en el {obj} de la {dir}, {barrio}",
        "fuga de gas en la {dir}, {barrio}, se rompió la tubería",
        "olor a gas fuertísimo en el {obj} de la {dir} en {barrio}",
    ],
    "deslizamiento": [
        "deslizamiento tapó dos viviendas en la {dir}, {barrio}",
        "se vino el talud sobre las casas de la {dir} en {barrio}",
        "derrumbe de tierra en la ladera de la {dir}, {barrio}, afectó viviendas",
    ],
    "via_bloqueada": [
        "vía bloqueada por escombros en la {dir}, {barrio}",
        "no hay paso en la {dir} ({barrio}), cayó un muro sobre la vía",
        "la {dir} en {barrio} está cerrada por escombros, vía bloqueada",
    ],
    "servicios_caidos": [
        "sin luz ni agua en la {dir}, {barrio}, desde el sismo",
        "no hay energía en la {dir} de {barrio}, cayó un poste",
        "en {barrio} estamos sin agua, {dir}, desde el temblor",
    ],
    "necesidad_albergue": [
        "{n} familias sin casa en la {dir}, {barrio}, necesitamos albergue",
        "quedamos en la calle en la {dir}, {barrio}, necesitamos refugio",
        "familias damnificadas en {barrio}, {dir}, no tienen dónde dormir",
    ],
    "necesidad_ayuda": [
        "necesitamos agua y comida para {n} familias en la {dir}, {barrio}",
        "se necesitan medicamentos y cobijas en la {dir}, {barrio}",
        "falta comida y agua potable para {n} familias, {dir}, {barrio}",
    ],
    "persona_desaparecida": [
        "mi {fam} no aparece desde el sismo, vivía en la {dir}, {barrio}",
        "buscamos a una señora de la {dir} en {barrio}, no contesta desde el temblor",
        "desaparecido un vecino de la {dir}, {barrio}, no sabemos nada de él",
    ],
    "sismo_sentido": [
        "se sintió durísimo en {barrio}, en la {dir} todo se movió, qué susto",
        "tembló muy fuerte en la {dir}, {barrio}, se cayeron cosas",
        "fuerte movimiento en {barrio}, {dir}, la gente salió a la calle",
    ],
}

FAKES: list[tuple[str, list[str], int]] = [
    (
        "replica_9",
        [
            "URGENTE reenvía: dicen que a las 3 pm habrá una réplica de 9, salgan de las casas",
            "Reenvíen!! dicen que viene réplica de 9 a las 3 de la tarde en Manizales",
            "me contaron que a las 3 pm hay réplica de 9, urgente compartir con la familia",
            "cadena: réplica de 9 hoy a las 3pm, avisen a todos",
        ],
        9,
    ),
    (
        "nasa",
        [
            "la NASA predice un terremoto de 8,5 esta noche en Manizales, compartan",
            "dicen que la NASA pronosticó otro terremoto para esta noche, difundan",
        ],
        5,
    ),
    (
        "puente_santander",
        [
            "dicen que se cayó el puente de la Avenida Santander, compartan para que nadie pase",
            "URGENTE COMPARTIR: se cayó el puente de la avenida Santander",
            "me dijeron que el puente de la Santander colapsó, reenvíen",
        ],
        6,
    ),
    (
        "hospital",
        [
            "dicen que colapsó el Hospital Santa Sofía, reenvíen",
            "me contaron que se cayó el hospital Santa Sofía, compartan",
        ],
        4,
    ),
    (
        "muertos",
        [
            "cientos de muertos en el centro de Manizales y el gobierno lo oculta, difundan",
            "dicen que hay miles de muertos en Manizales, compartan esto",
        ],
        4,
    ),
    (
        "va_a_temblar",
        [
            "va a temblar otra vez a las 6, salgan todos de los edificios, reenvía",
            "dicen que va a haber otro terremoto más fuerte esta noche, compartan",
        ],
        4,
    ),
    (
        "hospital_atrapados",
        [
            "dicen que hay pacientes atrapados en el Hospital Santa Sofía, reenvíen",
        ],
        2,
    ),
    (
        "cable_sin_senales",
        [
            "se cayó la torre del Cable Aéreo",
            "colapsó la torre del cable aéreo en el Cable",
        ],
        3,
    ),
]


@dataclass
class Place:
    name: str
    kind: str
    lat: float
    lon: float
    barrio: str


@dataclass
class Event:
    id: str
    category: str
    barrio: str
    place_label: str
    direction: str
    lat: float
    lon: float
    offset: float
    people: int
    obj: str
    fam: str
    critical: bool
    reports: list[dict] = field(default_factory=list)


def load_places() -> dict[str, Place]:
    with (ROOT / "data/geo/gazetteer.csv").open(encoding="utf-8") as fh:
        return {
            r["name"]: Place(r["name"], r["kind"], float(r["lat"]), float(r["lon"]), r["barrio"])
            for r in csv.DictReader(fh)
        }


def jitter(rng: random.Random, lat: float, lon: float, meters: float) -> tuple[float, float]:
    d_lat = rng.uniform(-meters, meters) / 111_000
    d_lon = rng.uniform(-meters, meters) / (111_000 * math.cos(math.radians(lat)))
    return round(lat + d_lat, 6), round(lon + d_lon, 6)


class Generator:
    def __init__(self, seed: int, n_events: int) -> None:
        self.rng = random.Random(seed)
        self.n_events = n_events
        self.places = load_places()
        self.barrios = [p for p in self.places.values() if p.kind == "barrio"]
        self.phone_counter = 0
        self.lines: list[dict] = []
        self.truth: dict[str, dict] = {}

    # ---------------------------------------------------------------- utilidades
    def phone(self) -> str:
        self.phone_counter += 1
        return f"+573{self.rng.choice('012')}{self.rng.randint(0, 9)}{self.phone_counter:07d}"

    def offset_for_original(self) -> float:
        r = self.rng.random()
        if r < 0.4:
            return self.rng.uniform(1, 60)
        if r < 0.7:
            return self.rng.uniform(60, 180)
        return self.rng.uniform(180, WINDOW_MIN - 30)

    def hotspot(self) -> tuple[str, str, float, float, str]:
        """(barrio, etiqueta de lugar, lat, lon, dirección)."""
        rng = self.rng
        r = rng.random()
        n = rng.randint(18, 72)
        if r < 0.22:
            b = self.places["Centro"]
            return b.barrio, "Centro", b.lat, b.lon, f"calle {n} con carrera {rng.randint(18, 25)}"
        if r < 0.36:
            b = self.places["Milán"]
            return b.barrio, "Milán", b.lat, b.lon, f"calle {n} con carrera {rng.randint(19, 26)}"
        if r < 0.46:
            v = self.places["Avenida Santander"]
            return v.barrio, "Avenida Santander", v.lat, v.lon, f"avenida Santander con calle {n}"
        if r < 0.56:
            v = self.places["Avenida Paralela"]
            return v.barrio, "Avenida Paralela", v.lat, v.lon, f"avenida Paralela con calle {n}"
        if r < 0.66:
            v = self.places["Carrera 23"]
            return v.barrio, "Carrera 23", v.lat, v.lon, f"carrera 23 con calle {n}"
        b = rng.choice(self.barrios)
        return b.barrio, b.name, b.lat, b.lon, f"calle {n} con carrera {rng.randint(10, 40)}"

    def text_for(self, ev: Event, template: str) -> str:
        return template.format(
            obj=ev.obj, dir=ev.direction, barrio=ev.place_label, n=max(ev.people, 2), fam=ev.fam
        )

    def maybe_pii(self, text: str) -> str:
        r = self.rng.random()
        if r < 0.08:
            return f"{text}. Me llamo {self.rng.choice(NAMES)}, mi cel {self.phone()[3:]}"
        if r < 0.13:
            return f"{text}. Llamar al {self.phone()}"
        if r < 0.16:
            cc = f"{self.rng.randint(10, 99)}.{self.rng.randint(100, 999)}.{self.rng.randint(100, 999)}"
            return f"{text}. Mi cédula es {cc}"
        return text

    # ---------------------------------------------------------------- reportes
    def emit(
        self,
        *,
        ev: Event | None,
        label: str,
        duplicate_of: str | None,
        offset: float,
        channel: str,
        text: str,
        sender: str | None,
        lat: float | None = None,
        lon: float | None = None,
        barrio: str | None = None,
        category: str | None = None,
        people: int | None = None,
        critical: bool = False,
        event_id: str = "",
    ) -> str:
        idx = len(self.lines)
        client_uuid = str(uuid.uuid5(NAMESPACE, f"{idx}|{text}|{offset:.2f}"))
        occurred = EVENT_START + timedelta(minutes=offset)
        if channel == "sms":
            code = SMS_CODE.get(category or "")
            place_token = (barrio or "").upper().replace(" ", "_")
            if code and place_token and self.rng.random() < 0.65:
                body = f"DACORA {code} {place_token} {people or 0} {text}"[:160]
            else:
                body = text[:160]
            request = {
                "endpoint": "/ingest/sms",
                "body": {"from": sender, "body": body, "received_at": occurred.isoformat()},
            }
            client_uuid = f"sms:{idx}"
        else:
            body = {
                "client_uuid": client_uuid,
                "channel": channel,
                "occurred_at": occurred.isoformat(),
                "text": text,
                "consent": True,
            }
            if channel == "pwa" and category and self.rng.random() < 0.7:
                body["category_hint"] = category
            if lat is not None and lon is not None:
                body["location"] = {"lat": lat, "lon": lon, "precision": "gps"}
            elif barrio and channel in ("pwa", "entity"):
                body["barrio"] = barrio
            if people is not None and channel in ("pwa", "entity"):
                body["people_affected"] = people
            if sender:
                body["reporter_contact"] = sender
            if channel == "pwa" and self.rng.random() < 0.3:
                body["has_media"] = True
            request = {"endpoint": "/ingest/report", "body": body}
        self.lines.append({"seq": idx, "minute": round(offset, 2), "channel": channel, **request})
        self.truth[client_uuid] = {
            "seq": idx,
            "label": label,
            "duplicate_of": duplicate_of,
            "event_id": event_id or (ev.id if ev else ""),
            "is_critical": critical,
            "category": category,
        }
        return client_uuid

    def channel_for(self, critical: bool) -> str:
        weights = {"pwa": 30, "sms": 30, "call_123": 15, "entity": 10, "whatsapp": 15}
        if critical:
            weights["entity"] += 5
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def report_for(
        self, ev: Event, *, original: str | None, offset: float, sender: str | None = None
    ) -> str:
        channel = self.channel_for(ev.critical)
        text = self.text_for(ev, self.rng.choice(TEMPLATES[ev.category]))
        if channel != "sms":
            text = self.maybe_pii(text)
        lat = lon = None
        if channel == "entity" or (channel == "pwa" and self.rng.random() < 0.6):
            lat, lon = jitter(self.rng, ev.lat, ev.lon, 60)
        sender = sender or (None if channel == "entity" else self.phone())
        return self.emit(
            ev=ev,
            label="duplicate" if original else "unique",
            duplicate_of=original,
            offset=offset,
            channel=channel,
            text=text,
            sender=sender,
            lat=lat,
            lon=lon,
            barrio=ev.barrio,
            category=ev.category,
            people=ev.people,
            critical=ev.critical,
        )

    def build(self) -> None:
        cats = list(CATEGORY_WEIGHTS)
        events: list[Event] = []
        for i in range(self.n_events):
            category = self.rng.choices(cats, weights=[CATEGORY_WEIGHTS[c] for c in cats])[0]
            barrio, label, lat, lon, direction = self.hotspot()
            lat, lon = jitter(self.rng, lat, lon, 220)
            people = self.rng.randint(1, 6) if category in CRITICAL | {"colapso_estructura"} else 0
            critical = category in CRITICAL
            events.append(
                Event(
                    id=f"EV-{i + 1:03d}",
                    category=category,
                    barrio=barrio,
                    place_label=label,
                    direction=direction,
                    lat=lat,
                    lon=lon,
                    offset=self.offset_for_original(),
                    people=people,
                    obj=self.rng.choice(OBJECTS),
                    fam=self.rng.choice(FAMILY),
                    critical=critical,
                )
            )

        n_duplicates = round(self.n_events * 0.30 / 0.55)
        weights = [
            4 if e.critical else 2 if e.category == "colapso_estructura" else 1 for e in events
        ]
        originals = {e.id: "" for e in events}
        senders: dict[str, str] = {}
        for ev in sorted(events, key=lambda e: e.offset):
            first_sender = None if self.rng.random() < 0.1 else self.phone()
            originals[ev.id] = self.report_for(
                ev, original=None, offset=ev.offset, sender=first_sender
            )
            if first_sender:
                senders[ev.id] = first_sender
        for _ in range(n_duplicates):
            ev = self.rng.choices(events, weights=weights)[0]
            offset = min(ev.offset + self.rng.uniform(2, 120), WINDOW_MIN)
            # Unos pocos son el mismo remitente insistiendo (no suma fuente independiente).
            same = senders.get(ev.id) if self.rng.random() < 0.08 else None
            self.report_for(ev, original=originals[ev.id], offset=offset, sender=same)

        n_fakes = round(self.n_events * 0.15 / 0.55)
        pool = [(key, texts) for key, texts, w in FAKES for _ in range(w)]
        for _ in range(n_fakes):
            key, texts = self.rng.choice(pool)
            channel = self.rng.choices(["whatsapp", "sms", "pwa", "call_123"], [55, 25, 10, 10])[0]
            self.emit(
                ev=None,
                label="fake",
                duplicate_of=None,
                offset=self.rng.uniform(20, WINDOW_MIN - 60),
                channel=channel,
                text=self.rng.choice(texts),
                sender=self.phone(),
                event_id=f"FAKE-{key}",
                critical=False,
            )

        self.lines.sort(key=lambda line: line["minute"])

    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "scenario.jsonl").open("w", encoding="utf-8") as fh:
            for line in self.lines:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        meta = {
            "description": "Verdad del escenario SIMULADO. Solo para scripts/evaluate_kpis.py.",
            "event_start": EVENT_START.isoformat(),
            "window_minutes": WINDOW_MIN,
            "source": "SIMULADO",
            "reports": self.truth,
        }
        (out_dir / "ground_truth.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--events", type=int, default=140)
    parser.add_argument("--out", type=Path, default=ROOT / "data/seed")
    args = parser.parse_args()
    gen = Generator(args.seed, args.events)
    gen.build()
    gen.write(args.out)
    labels = [t["label"] for t in gen.truth.values()]
    total = len(labels)
    print(
        f"{total} reportes → únicos {labels.count('unique')} "
        f"({labels.count('unique') / total:.0%}), duplicados {labels.count('duplicate')} "
        f"({labels.count('duplicate') / total:.0%}), falsos {labels.count('fake')} "
        f"({labels.count('fake') / total:.0%}); críticos "
        f"{sum(t['is_critical'] for t in gen.truth.values())} → {args.out}"
    )


if __name__ == "__main__":
    main()
