// Copia el worker de MapLibre a public/vendor para servirlo localmente (offline, principio II).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "maplibre-gl", "dist", "maplibre-gl-worker.mjs");
const dest = join(root, "public", "vendor", "maplibre-gl-worker.mjs");
mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log("worker de MapLibre → public/vendor/maplibre-gl-worker.mjs");
