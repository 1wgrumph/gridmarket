"""Adds the /api/help route to src/index.js. Safe to run more than once."""
import pathlib, sys
p = pathlib.Path(__file__).resolve().parent.parent / "src" / "index.js"
s = p.read_text()
if "/api/help" in s:
    print("index.js already has /api/help"); sys.exit(0)
if 'import { buildNodes, SP_PATTERN } from "./node.js";' not in s:
    sys.exit("index.js doesn't have the node.js import; run add-node-route.py first")
s = s.replace('import { buildNodes, SP_PATTERN } from "./node.js";',
              'import { buildNodes, SP_PATTERN } from "./node.js";\nimport { buildHelp } from "./help.js";', 1)
marker = "      // Live price at one or more settlement points, for the plant drill-down"
route = '''      // Help the grid: demand now and upcoming help windows per zone (ERCOT data only)
      if (p === "/api/help") {
        const hit = url.searchParams.has("fresh") ? null : await env.CACHE.get("help:v1");
        if (hit) return json(JSON.parse(hit), 200, { "x-cache": "HIT" });
        const out = await buildHelp((path, params) => ercotJSON(env, path, params));
        await env.CACHE.put("help:v1", JSON.stringify(out), { expirationTtl: 900 });
        return json(out, 200, { "x-cache": "MISS" });
      }

''' + marker
if marker not in s: sys.exit("route marker not found")
s = s.replace(marker, route, 1)
p.write_text(s); print("added /api/help to", p)
