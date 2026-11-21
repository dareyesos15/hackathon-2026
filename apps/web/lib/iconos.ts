/**
 * Pictogramas por categoría de incidente (rejilla 24×24, solo trazo).
 * Única fuente: se dibujan como SVG en la interfaz y como imágenes de MapLibre en el mapa,
 * para que el operador reconozca el mismo símbolo en la lista y sobre el terreno.
 */
import type { Category, TriageLevel } from "./labels";
import { TRIAGE_COLOR } from "./labels";

const CIRCLE = (cx: number, cy: number, r: number) =>
  `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;

export const CATEGORY_ICON: Record<Category, string> = {
  // Persona bajo una losa que se parte.
  personas_atrapadas: `M3 8h18M6 4.5 9 8M18 4.5 15 8${CIRCLE(12, 12.5, 1.9)}M7.5 20.5c0-2.6 2-4.3 4.5-4.3s4.5 1.7 4.5 4.3`,
  heridos: "M12 4.5v15M4.5 12h15",
  // Vivienda con la cubierta quebrada.
  colapso_estructura: "M3.5 20.5h17M5 20.5v-8l3.5-4 2.5 3.5 2-4.5 6 5.5v7.5",
  // Vivienda con grieta.
  dano_estructural: "M3.5 11.5 12 4l8.5 7.5M6 9.5v11h12v-11M12.5 10l-2 3 2.2 2-1.4 3.5",
  incendio:
    "M12 3c1 3.2 5.5 5.2 5.5 10.2a5.5 5.5 0 0 1-11 0c0-2.6 1.4-4.2 2.6-5.3.4 2 1.5 3.1 2.6 3.1 0-3.2-1-5.2.3-8Z",
  // Tres vapores que suben.
  fuga_gas:
    "M7 20.5c-1.8-2.7 1.8-4.6 0-7.3s1.8-4.6 0-7.3M12 20.5c-1.8-2.7 1.8-4.6 0-7.3s1.8-4.6 0-7.3M17 20.5c-1.8-2.7 1.8-4.6 0-7.3s1.8-4.6 0-7.3",
  // Ladera con rocas rodando.
  deslizamiento: `M3 19.5V5.5l13 14H3${CIRCLE(17.5, 11, 1.6)}${CIRCLE(20, 16, 1.3)}`,
  // Barrera vial.
  via_bloqueada: "M3 8.5h18v5H3ZM8 8.5l-3 5M13 8.5l-3 5M18 8.5l-3 5M6 13.5v7M18 13.5v7",
  servicios_caidos: "M13.5 3 6 13.5h5.5l-1 7.5L18 10.5h-5.5l1-7.5Z",
  // Carpa.
  necesidad_albergue: "M2.5 20.5h19M4.5 20.5 12 5l7.5 15.5M12 20.5l-2.6-5.5h5.2Z",
  // Caja de ayuda humanitaria.
  necesidad_ayuda: "M4 8l8-4 8 4v9l-8 4-8-4ZM4 8l8 4 8-4M12 12v9",
  persona_desaparecida: "M8.8 9a3.2 3.2 0 1 1 4.8 2.8c-1 .6-1.6 1.2-1.6 2.6M12 18.4v.6",
  // Traza de sismograma.
  sismo_sentido: "M2 12.5h4l2-5 3 10 3-14 2 9 1.6-2.5H22",
  // Globo de conversación: información sin confirmar.
  rumor_informacion: "M4 5h16v11h-9l-4.5 4v-4H4ZM8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01",
  sin_clasificar: CIRCLE(12, 12, 2.5),
};

/** Diámetro lógico del marcador en el mapa (px CSS). */
export const MARKER_SIZE = 40;

export function markerImageId(category: Category, triage: TriageLevel, fake: boolean): string {
  return `inc:${category}:${triage}:${fake ? "falso" : "ok"}`;
}

/**
 * Dibuja el marcador (disco del color de triaje + pictograma blanco) en un canvas y lo devuelve
 * como ImageData listo para `map.addImage(id, data, { pixelRatio })`.
 * Un posible falso conserva su color de triaje (nunca se oculta un riesgo vital),
 * pero con anillo oscuro discontinuo.
 */
export function drawMarker(id: string, pixelRatio: number): ImageData | null {
  const [, category, triage, fake] = id.split(":") as [string, Category, TriageLevel, string];
  const path = CATEGORY_ICON[category];
  const color = TRIAGE_COLOR[triage];
  if (!path || !color) return null;

  const px = Math.round(MARKER_SIZE * pixelRatio);
  const canvas = document.createElement("canvas");
  canvas.width = px;
  canvas.height = px;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(pixelRatio, pixelRatio);

  const c = MARKER_SIZE / 2;
  const r = c - 3;
  ctx.beginPath();
  ctx.arc(c, c, r, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.lineWidth = 2.5;
  if (fake === "falso") {
    ctx.setLineDash([3, 2.5]);
    ctx.strokeStyle = "#231a1c";
  } else {
    ctx.strokeStyle = "#ffffff";
  }
  ctx.stroke();
  ctx.setLineDash([]);

  const glyph = 20;
  const scale = glyph / 24;
  ctx.save();
  ctx.translate(c - glyph / 2, c - glyph / 2);
  ctx.scale(scale, scale);
  ctx.strokeStyle = triage === "medio" ? "#231a1c" : "#ffffff";
  ctx.lineWidth = 2.3;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.stroke(new Path2D(path));
  ctx.restore();

  return ctx.getImageData(0, 0, px, px);
}
