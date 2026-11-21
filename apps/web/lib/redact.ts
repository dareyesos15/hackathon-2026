/**
 * Redacción de datos personales EN EL BORDE (principio I, FR-008): la app ciudadana la aplica
 * antes de guardar en el dispositivo y de enviar. Espejo de services/api/app/core/privacy.py
 * (la API vuelve a redactar y es la autoridad). Mismos casos: data/fixtures/pii_cases.json.
 * Orden: correo → teléfono → cédula → placa → nombres.
 */

const LETTER = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ";

const EMAIL_RE = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g;
const PHONE_RE = /(?<![\d.])(?:\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?![\d.])/g;
const CC_RE = /(?<![\d.,])(?:\d{1,3}(?:\.\d{3}){2,3}|\d{6,10})(?![\d.,]?\d)/g;
const PLATE_RE = new RegExp(
  `(?<![${LETTER}0-9])[A-Z]{3}[\\s-]?\\d{2}[0-9A-Z](?![${LETTER}0-9])`,
  "g",
);

const FAMILY =
  "mamá|mama|papá|papa|hijo|hija|esposo|esposa|hermano|hermana|abuelo|abuela|" +
  "tío|tio|tía|tia|novio|novia";
const TRIGGER_ANY_RE = new RegExp(`(?<![${LETTER}])(?:me llamo|mi nombre es)\\s+`, "giu");
const TRIGGER_CAP_RE = new RegExp(
  `(?<![${LETTER}])(?:soy|mi (?:${FAMILY})(?: se llama)?)\\s+`,
  "giu",
);
const WORD_RE = new RegExp(`[${LETTER}]+`, "uy");

const STOPWORDS = new Set(
  (
    "y e o u de del la el los las en estoy esta está con que por mi a al soy tengo vivo desde " +
    "para se no"
  ).split(" "),
);

export interface Redaction {
  text: string;
  kinds: string[];
}

function sub(pattern: RegExp, marker: string, text: string, kinds: string[]): string {
  let count = 0;
  const out = text.replace(pattern, () => {
    count += 1;
    return marker;
  });
  if (count) kinds.push(marker.slice(1, -1));
  return out;
}

function isCapitalized(word: string): boolean {
  const first = word[0];
  return first === first.toUpperCase() && first !== first.toLowerCase();
}

function nameSpanEnd(text: string, start: number, requireCapital: boolean): number {
  let end = start;
  let pos = start;
  for (let i = 0; i < 3; i += 1) {
    WORD_RE.lastIndex = pos;
    const match = WORD_RE.exec(text);
    if (!match) break;
    const word = match[0];
    if (STOPWORDS.has(word.toLowerCase())) break;
    if (requireCapital && !isCapitalized(word)) break;
    end = pos + word.length;
    if (text[end] === " ") pos = end + 1;
    else break;
  }
  return end;
}

function redactNames(text: string, kinds: string[]): string {
  const spans: Array<[number, number]> = [];
  for (const [pattern, requireCapital] of [
    [TRIGGER_ANY_RE, false],
    [TRIGGER_CAP_RE, true],
  ] as const) {
    pattern.lastIndex = 0;
    for (const match of text.matchAll(pattern)) {
      const start = (match.index ?? 0) + match[0].length;
      const end = nameSpanEnd(text, start, requireCapital);
      if (end > start) spans.push([start, end]);
    }
  }
  if (!spans.length) return text;
  kinds.push("NOMBRE");
  const unique = Array.from(new Map(spans.map((s) => [`${s[0]}:${s[1]}`, s])).values()).sort(
    (a, b) => a[0] - b[0] || a[1] - b[1],
  );
  let out = "";
  let last = 0;
  for (const [start, end] of unique) {
    if (start < last) continue;
    out += text.slice(last, start) + "[NOMBRE]";
    last = end;
  }
  return out + text.slice(last);
}

/** Reemplaza datos personales por marcadores. Idempotente. */
export function redact(text: string | null | undefined): Redaction {
  if (!text) return { text: "", kinds: [] };
  const kinds: string[] = [];
  let out = sub(EMAIL_RE, "[CORREO]", text, kinds);
  out = sub(PHONE_RE, "[TEL]", out, kinds);
  out = sub(CC_RE, "[CC]", out, kinds);
  out = sub(PLATE_RE, "[PLACA]", out, kinds);
  out = redactNames(out, kinds);
  return { text: out, kinds };
}
