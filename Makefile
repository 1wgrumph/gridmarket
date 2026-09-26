UV := uv run --project backend --frozen
PYTEST := $(UV) pytest -q
LINT_PATHS := $(wildcard backend tools sdk examples bench mcp-server)
SHELL := /bin/bash

.PHONY: setup lint test-contracts test-market test-data test-dash test-providers test-bots test-router test-kit test-mcp test-quant test-jev test-docs test-adversary test-backtest test-parity test-ml test-spec spec-lint test-all red-green coverage mutation bench smoke secrets depscan rules

setup:
	uv sync --project backend --frozen --all-groups --extra ml
	npm ci --prefix dashboard

lint:
	$(UV) ruff check $(LINT_PATHS)
	$(UV) ruff format --check $(LINT_PATHS)

test-contracts:
	$(PYTEST) backend/tests/test_contracts.py

test-market:
	$(PYTEST) backend/tests/test_market.py backend/tests/test_api.py backend/tests/test_sdk.py

test-data:
	$(PYTEST) backend/tests/test_ercot.py backend/tests/test_nws.py backend/tests/test_scoring.py

test-dash:
	npm --prefix dashboard exec -- vitest run
	npm --prefix dashboard run build

test-providers:
	$(PYTEST) backend/tests/test_providers.py backend/tests/test_health.py

test-bots:
	$(PYTEST) backend/tests/test_population.py backend/tests/test_bots.py backend/tests/test_economy.py $(wildcard backend/tests/test_diversity.py)

test-router:
	$(PYTEST) backend/tests/test_router.py

test-kit:
	$(PYTEST) backend/tests/test_kit.py

test-mcp:
	@if [ ! -f mcp-server/pyproject.toml ]; then echo MCP_PROJECT_ABSENT; exit 1; fi
	uv sync --project mcp-server --frozen
	uv run --project mcp-server --frozen pytest -q mcp-server/tests -rs

test-quant:
	uv sync --project backend --frozen --all-groups --extra ml --extra quant
	$(PYTEST) backend/tests/test_quant.py -rs

test-jev:
	$(PYTEST) backend/tests/test_jev.py

test-docs:
	$(PYTEST) backend/tests/test_docs.py

test-adversary:
	$(PYTEST) backend/tests/test_adversarial.py

test-backtest:
	$(PYTEST) backend/tests/test_backtest.py

test-parity:
	GRIDMARKET_REQUIRE_RUST=1 $(PYTEST) backend/tests/test_matching_parity.py -rs

test-ml:
	$(PYTEST) backend/tests/test_ml.py

test-spec:
	$(PYTEST) tools/tests

spec-lint:
	$(UV) python tools/spec_build.py spec/gridmarket/ spec/GridMarket-Specification.md
	git diff --exit-code -- spec/GridMarket-Specification.md
	$(UV) python tools/spec_lint.py spec/gridmarket/
	$(UV) python -m azdiagram lint spec/gridmarket/

test-all:
	$(PYTEST) backend/tests $(if $(wildcard tools/tests),tools/tests,)
	@if [ -f mcp-server/pyproject.toml ]; then $(MAKE) test-mcp; fi
	$(MAKE) test-dash
	@if [ -d ercot-hackathon/test ]; then node --test ercot-hackathon/test/; fi

red-green:
	@test -n "$(TESTS)" && test -n "$(EVIDENCE)"
	@case "$(SUITE)" in \
	  backend|tools) $(UV) pytest $(TESTS) --junitxml=$(EVIDENCE) ;; \
	  backend-quant) uv run --project backend --frozen --extra quant pytest $(TESTS) --junitxml=$(EVIDENCE) ;; \
	  mcp) uv run --project $(if $(filter green,$(PHASE)),mcp-server,backend) --frozen pytest $(TESTS) --junitxml=$(EVIDENCE) ;; \
	  dashboard) npm --prefix dashboard exec -- vitest run $(TESTS) --reporter=junit --outputFile=$(EVIDENCE) ;; \
	  *) echo UNKNOWN_SUITE; exit 2 ;; \
	esac

coverage:
	@test -n "$(BASE)"
	mkdir -p /tmp/gm-evidence
	$(UV) pytest backend/tests $(if $(wildcard tools/tests),tools/tests,) --cov=backend/gridmarket_server --cov=tools --cov-report=xml:/tmp/gm-evidence/coverage.xml
	$(UV) diff-cover /tmp/gm-evidence/coverage.xml --compare-branch=$(BASE) --fail-under=80

mutation:
	cd backend && uv run --frozen mutmut run $(MUTANTS)
	cd backend && uv run --frozen mutmut export-cicd-stats
	cat backend/mutants/mutmut-cicd-stats.json

bench:
	$(UV) python bench/bench_matching.py --orders 100000 --seed 20260926 --out bench/results.md

smoke:
	@test -n "$(SMOKE_PROJECT)" && test -n "$(SMOKE_PORT)" && test -f deploy/compose.yaml
	@f=$$(mktemp); trap 'docker compose -p $(SMOKE_PROJECT) -f deploy/compose.yaml down -v >/dev/null 2>&1; rm -f "$$f"' EXIT; \
	  printf 'GRIDMARKET_NWS=off\nGRIDMARKET_BOT_SECRET=%s\nGRIDMARKET_BOT_MASTER_SEED=20260926\n' "$$(python3 -c 'import secrets;print(secrets.token_hex(16))')" > "$$f"; \
	  GM_ENV_FILE="$$f" GRIDMARKET_PORT=$(SMOKE_PORT) docker compose -p $(SMOKE_PROJECT) -f deploy/compose.yaml up -d --build --wait app bots; \
	  curl --fail --silent http://127.0.0.1:$(SMOKE_PORT)/v1/market/status

secrets:
	gitleaks git --config .gitleaks.toml --redact --exit-code 1 .
	head -1 LICENSE | grep -qx "MIT License"
	! grep -vE '^(#.*|[A-Z_]+=)?$$' .env.example

depscan:
	uv lock --project backend --check --exclude-newer 2026-09-11T22:00:00Z
	set -o pipefail; uv export --project backend --frozen --all-extras --all-groups --no-hashes --no-emit-project | uvx pip-audit --strict --no-deps --disable-pip -r /dev/stdin
	npm --prefix dashboard audit --audit-level=high
	node -e 'const p=require("./dashboard/package-lock.json");const e=require("node:child_process");const c=new Date("2026-09-11T22:00:00Z");const s=[...new Set(Object.entries(p.packages).filter(([k,v])=>k&&v.version).map(([k,v])=>k.split("node_modules/").pop()+"@"+v.version))];let i=0;const bad=[];async function worker(){while(i<s.length){const spec=s[i++];const v=spec.slice(spec.lastIndexOf("@")+1);try{const raw=await new Promise((ok,no)=>e.execFile("npm",["view",spec,"time","--json"],{maxBuffer:4194304},(err,out)=>err?no(err):ok(out)));const times=JSON.parse(raw);const t=times[v]??times.time?.[v];if(!t||new Date(t)>c)bad.push(spec+" "+(t??"unknown"))}catch{bad.push(spec+" lookup failed")}}}Promise.all(Array.from({length:8},worker)).then(()=>{console.log("checked "+s.length+" locked npm package versions");if(bad.length){console.error(bad.join("\n"));process.exitCode=1}else console.log("all meet cutoff")})'
	@if [ "$(RUST)" = 1 ]; then cargo audit --file rust/matching_core/Cargo.lock; fi
	@if [ "$(MCP)" = 1 ]; then uv lock --project mcp-server --check --exclude-newer 2026-09-11T22:00:00Z; fi

rules:
	git grep -qiF "baseline rules" -- ercot-hackathon/public
	! git grep -nIiE "(fetch|urlopen|urllib|httpx|requests\.|https?://)[^\n]*jev" -- ercot-hackathon/src ercot-hackathon/public dashboard/src backend/gridmarket_server sdk mcp-server ':!backend/gridmarket_server/jev.py'
	git log --no-merges --format="%H %aI" 0bfa50a..HEAD | python3 -c 'import datetime,sys; cutoff=datetime.datetime.fromisoformat("2026-09-25T17:00:00-05:00"); assert all(datetime.datetime.fromisoformat(line.split()[1])>=cutoff for line in sys.stdin if line.strip())'
