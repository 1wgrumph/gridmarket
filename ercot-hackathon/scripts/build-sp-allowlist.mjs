// Run with: node ercot-hackathon/scripts/build-sp-allowlist.mjs
import { readFileSync, writeFileSync } from "node:fs";

const { plants } = JSON.parse(readFileSync(new URL("../public/data/tx_plants.json", import.meta.url)));
const points = [...new Set(plants.flatMap((plant) => plant.nodes).map((sp) => sp.trim().toUpperCase()))].sort();
writeFileSync(new URL("../src/sp-allowlist.js", import.meta.url),
  "// Generated from public/data/tx_plants.json by scripts/build-sp-allowlist.mjs.\n" +
  `export const SP_ALLOWLIST = new Set(${JSON.stringify(points, null, 2)});\n`);
