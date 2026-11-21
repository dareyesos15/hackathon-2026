"""Genera docs/arquitectura_actual.svg: arquitectura actual de Dacora con el estado de cada pieza.

Uso:
    python scripts/generate_architecture_diagram.py docs/arquitectura_actual.svg
    # PNG (2x) con Chrome sin interfaz:
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
      --hide-scrollbars --force-device-scale-factor=2 --window-size=1600,1040 \
      --screenshot=docs/arquitectura_actual.png "file://$PWD/docs/arquitectura_actual.svg"
"""

import sys
import textwrap
from html import escape

OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/arquitectura_actual.svg"
W, H = 1600, 1040

IMPL, SIM, PLAN = "impl", "sim", "plan"
BADGE = {
    IMPL: ("Implementado", "#22c55e"),
    SIM: ("Simulado", "#f59e0b"),
    PLAN: ("Planeado", "#94a3b8"),
}

COLUMNS = [
    (
        "1. CAPTACIÓN DE DATOS",
        "Entradas",
        "#f59e0b",
        [
            ("PWA ciudadana offline", "IndexedDB (Dexie) + outbox; envía al volver la red", IMPL),
            ("SMS / Línea 123", "Formato compacto DACORA ≤ 160 caracteres", SIM),
            ("WhatsApp y APIs públicas", "Reportes reenviados, ingresados por el operador", SIM),
            (
                "Entidades confiables",
                "SGC, SIMAC, Alcaldía, Bomberos, Cruz Roja, Defensa Civil",
                SIM,
            ),
            ("Hardware de campo", "Nodos LoRa/Meshtastic + sensor de zonas inseguras UNAL", PLAN),
        ],
    ),
    (
        "2. INGESTA Y SST",
        "Single Source of Truth",
        "#10b981",
        [
            (
                "API REST FastAPI /api/v1",
                "Ingesta idempotente por client_uuid; contrato OpenAPI",
                IMPL,
            ),
            (
                "Módulo Habeas Data",
                "Redacción de PII en el borde y en la API + HMAC-SHA256 (Ley 1581)",
                IMPL,
            ),
            (
                "SST PostgreSQL 16 + PostGIS",
                "Reportes solo-agregar y bitácora auditable",
                IMPL,
            ),
            ("Bus de eventos", "En memoria → SSE; interfaz lista para Kafka", IMPL),
        ],
    ),
    (
        "3. MOTOR DE INTELIGENCIA",
        "Y VERIFICACIÓN",
        "#3b82f6",
        [
            (
                "Clasificación y triaje",
                "Reglas/léxico en español colombiano; gravedad y lugar por gazetteer",
                IMPL,
            ),
            (
                "Deduplicación",
                "Espacio ≤ 250 m · tiempo ≤ 3 h · similitud de texto TF-IDF",
                IMPL,
            ),
            ("Trust Score 0–100", "Desglose explicable por señal y etiqueta de veracidad", IMPL),
            (
                "Validación cruzada GIS",
                "Interfaz HazardProvider; acelerógrafos tipo RAMAN en P1",
                PLAN,
            ),
            ("RAG local (Ollama)", "Protocolos EMRE Manizales 2024", PLAN),
        ],
    ),
    (
        "4. TABLERO SITUACIONAL",
        "PMU y público",
        "#22c55e",
        [
            ("Mapa de daños por manzana", "MapLibre offline; SSE con respaldo por polling", IMPL),
            (
                "Matriz de triaje + revisión humana",
                "Confirmar / Descartar / Duplicado; la IA solo sugiere",
                IMPL,
            ),
            ("Panel de KPI", "Cada cifra con fuente, versión y fecha de corte", IMPL),
            ("Mapa público agregado", "Solo conteos por manzana con k ≥ 5", IMPL),
            ("Trazabilidad de recursos", "Recorridos tipo RFID (patente 15111163)", SIM),
        ],
    ),
    (
        "5. DESPACHO, ALERTAS",
        "Y PREDICCIÓN",
        "#8b5cf6",
        [
            (
                "Despacho a agencias",
                "Agencia sugerida por la EMRE, recurso más cercano, sin doble despacho",
                IMPL,
            ),
            (
                "Alertas multicanal",
                "Tablero y mapa público + SMS SIMULADO; solo el COE aprueba",
                IMPL,
            ),
            ("Efectos en cascada", "Pendiente y lluvia SIMULADAS + reportes cercanos", SIM),
            ("Pantalla de agencia", "Llegada, atención finalizada, fuera de servicio", IMPL),
        ],
    ),
    (
        "6. RECUPERACIÓN",
        "Post-sismo (diferencial)",
        "#ec4899",
        [
            ("Semáforo de habitabilidad", "Inspección por predio (verde/amarillo/rojo)", PLAN),
            ("Censo único de damnificados", "Hogar por hash; evita duplicidad", PLAN),
            ("Ayudas y albergues", "Control de subsidios y ayudas humanitarias", PLAN),
            ("Infraestructura y servicios", "Agua, energía, gas, vías, escombros", PLAN),
            ("Reconstrucción transparente", "NSR-10, Findeter/Bancóldex, control de fondos", PLAN),
            ("Portal “Reconstruir Mejor”", "Índice de recuperación por barrio", PLAN),
        ],
    ),
]

RESILIENCE = [
    ("PLAN A · ONLINE TOTAL", "Nube, 4G/fibra, APIs públicas, tableros remotos", PLAN),
    (
        "PLAN B · OFFLINE-FIRST",
        "docker compose en portátil o servidor del PMU, PWA offline, SMS gateway",
        IMPL,
    ),
    ("PLAN C · COLAPSO TOTAL", "Malla LoRaWAN, radio de rescatistas, telemetría UNAL", PLAN),
]

BG, PANEL, TEXT, MUTED = "#0b1220", "#111a2e", "#e2e8f0", "#94a3b8"
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"

out: list[str] = []


def text(x, y, s, size=12, weight="normal", fill=TEXT, anchor="start", opacity=1.0):
    out.append(
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}" opacity="{opacity}">{escape(s)}</text>'
    )


def badge(x, y, kind):
    label, color = BADGE[kind]
    w = 8 + len(label) * 6.2
    out.append(
        f'<rect x="{x}" y="{y}" width="{w:.0f}" height="16" rx="8" fill="{color}" '
        f'fill-opacity="0.18" stroke="{color}" stroke-width="1"/>'
    )
    text(x + w / 2, y + 12, label, size=10, weight="bold", fill=color, anchor="middle")


out.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    f'font-family="{FONT}">'
)
out.append(
    "<defs><marker id='arrow' viewBox='0 0 10 10' refX='8' refY='5' markerWidth='7' "
    "markerHeight='7' orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' "
    "fill='#cbd5e1'/></marker></defs>"
)
out.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

# Encabezado
text(W / 2, 46, "DACORA · ARQUITECTURA ACTUAL DEL PROTOTIPO", 30, "bold", "#f8fafc", "middle")
text(
    W / 2,
    74,
    "Reto 05 · Datos & Inteligencia Operativa · PMU Eje Cafetero (Manizales – UNAL) "
    "· Estado al 21 nov 2026",
    15,
    fill=MUTED,
    anchor="middle",
)
# Leyenda
lx = W / 2 - 205
for i, kind in enumerate((IMPL, SIM, PLAN)):
    badge(lx + i * 140, 90, kind)
text(
    W / 2,
    126,
    "Implementado: en el código y en la demo · Simulado: canal real con datos sintéticos "
    "· Planeado: punto de integración listo",
    11,
    fill=MUTED,
    anchor="middle",
)

# Columnas
X0, GAP, COLW = 24, 20, (W - 48 - 5 * 20) / 6
Y0, Y1 = 146, 770
HEAD = 62
for ci, (title, subtitle, color, cards) in enumerate(COLUMNS):
    x = X0 + ci * (COLW + GAP)
    out.append(
        f'<rect x="{x}" y="{Y0}" width="{COLW}" height="{Y1 - Y0}" rx="12" fill="{color}" '
        f'fill-opacity="0.07" stroke="{color}" stroke-width="2"/>'
    )
    out.append(
        f'<rect x="{x}" y="{Y0}" width="{COLW}" height="{HEAD}" rx="12" fill="{color}" '
        f'fill-opacity="0.22"/>'
    )
    text(x + COLW / 2, Y0 + 27, title, 14, "bold", "#f8fafc", "middle")
    text(x + COLW / 2, Y0 + 47, subtitle, 12, fill=TEXT, anchor="middle", opacity=0.85)

    # Tarjetas
    inner_x, inner_w = x + 10, COLW - 20
    laid = []
    for ctitle, desc, kind in cards:
        tl = textwrap.wrap(ctitle, 27)
        dl = textwrap.wrap(desc, 34)
        h = 14 + len(tl) * 16 + len(dl) * 14 + 26
        laid.append((tl, dl, kind, h))
    avail = Y1 - Y0 - HEAD - 20
    total = sum(h for *_, h in laid)
    gap = min(22, (avail - total) / max(1, len(laid) - 1)) if len(laid) > 1 else 0
    cy = Y0 + HEAD + 12
    for tl, dl, kind, h in laid:
        dash = ' stroke-dasharray="5 4"' if kind == PLAN else ""
        op = 0.6 if kind == PLAN else 1.0
        out.append(
            f'<rect x="{inner_x}" y="{cy}" width="{inner_w}" height="{h}" rx="8" fill="{PANEL}" '
            f'stroke="{color}" stroke-opacity="{0.45 if kind == PLAN else 0.9}" '
            f'stroke-width="1.3"{dash}/>'
        )
        ty = cy + 20
        for line in tl:
            text(inner_x + 10, ty, line, 13, "bold", "#f8fafc", opacity=op + 0.15 if op < 1 else 1)
            ty += 16
        for line in dl:
            text(inner_x + 10, ty, line, 11, fill="#cbd5e1", opacity=op + 0.15 if op < 1 else 1)
            ty += 14
        badge(inner_x + 10, cy + h - 22, kind)
        cy += h + gap

    if ci < 5:
        ax = x + COLW + 2
        ay = (Y0 + Y1) / 2
        out.append(
            f'<line x1="{ax}" y1="{ay}" x2="{ax + GAP - 4}" y2="{ay}" stroke="#cbd5e1" '
            f'stroke-width="2.5" marker-end="url(#arrow)"/>'
        )

# Servicios
SY = 790
out.append(
    f'<rect x="24" y="{SY}" width="{W - 48}" height="64" rx="10" fill="#0f172a" '
    f'stroke="#334155" stroke-width="1.5"/>'
)
text(W / 2, SY + 24, "SERVICIOS (docker compose up)", 13, "bold", "#f8fafc", "middle")
text(
    W / 2,
    SY + 47,
    "web · Next.js PWA (frontend puro, export estático + Nginx)   ⇄   REST /api/v1 + SSE /stream"
    "   ⇄   api · FastAPI (motor + adaptadores)   ⇄   db · PostgreSQL 16 + PostGIS",
    13,
    fill="#cbd5e1",
    anchor="middle",
)

# Resiliencia
RY = 872
out.append(
    f'<rect x="24" y="{RY}" width="{W - 48}" height="148" rx="12" fill="#0f172a" '
    f'stroke="#38bdf8" stroke-opacity="0.6" stroke-width="1.5"/>'
)
text(
    W / 2, RY + 28, "MATRIZ DE RESILIENCIA (CONTINUIDAD OPERATIVA)", 15, "bold", "#f8fafc", "middle"
)
pw = (W - 48 - 40 - 2 * 20) / 3
for i, (ptitle, pdesc, kind) in enumerate(RESILIENCE):
    px = 44 + i * (pw + 20)
    dash = ' stroke-dasharray="5 4"' if kind == PLAN else ""
    out.append(
        f'<rect x="{px}" y="{RY + 44}" width="{pw}" height="88" rx="8" fill="{PANEL}" '
        f'stroke="#38bdf8" stroke-opacity="{0.4 if kind == PLAN else 0.9}" '
        f'stroke-width="1.3"{dash}/>'
    )
    text(px + pw / 2, RY + 68, ptitle, 14, "bold", "#f8fafc", "middle")
    text(px + pw / 2, RY + 90, pdesc, 12, fill="#cbd5e1", anchor="middle")
    label, _ = BADGE[kind]
    badge(px + pw / 2 - (8 + len(label) * 6.2) / 2, RY + 104, kind)

out.append("</svg>")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
