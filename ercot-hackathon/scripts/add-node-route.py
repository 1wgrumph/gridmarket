"""Adds the /api/node route to src/index.js. Safe to run more than once."""
import pathlib, sys

p = pathlib.Path(__file__).resolve().parent.parent / "src" / "index.js"
s = p.read_text()
if "/api/node" in s:
    print("index.js already has /api/node"); sys.exit(0)

s = s.replace('import { buildSnapshot } from "./snapshot.js";',
              'import { buildSnapshot } from "./snapshot.js";\nimport { buildNodes, SP_PATTERN } from "./node.js";', 1)

route = '''      // Live price at one or more settlement points, for the plant drill-down
      if (p === "/api/node") {
        const sps = (url.searchParams.get("sp") || "").split(",").map((x) => x.trim()).filter((x) => SP_PATTERN.test(x)).slice(0, 4);
        if (!sps.length) return json({ error: "Pass ?sp=SETTLEMENT_POINT (comma-separated, up to 4)" }, 400);
        const key = "node:v1:" + sps.join(",");
        const hit = await env.CACHE.get(key);
        if (hit) return json(JSON.parse(hit), 200, { "x-cache": "HIT" });
        const out = await buildNodes((path, params) => ercotJSON(env, path, params), sps);
        await env.CACHE.put(key, JSON.stringify(out), { expirationTtl: 300 });
        return json(out, 200, { "x-cache": "MISS" });
      }

      // One cached call for the 3D grid diagram'''
marker = "      // One cached call for the 3D grid diagram"
if marker not in s or 'import { buildNodes' not in s:
    sys.exit("index.js doesn't look like the expected version; add the route by hand (see README).")
s = s.replace(marker, route, 1)
p.write_text(s)
print("added /api/node to", p)
