# Notebooks

Two notebooks with very different purposes.

| Notebook | Backend | Purpose |
|---|---|---|
| [`prototype.ipynb`](prototype.ipynb) | In-notebook stubs + `PSEUDO_POOL` | Offline scaffold — develop and debug pipeline logic without the harness running. |
| [`demo.ipynb`](demo.ipynb) | Live `POST /listings` via HTTPS | Presentation demo — hits the real API and renders ranked listings on a map. |

---

## `prototype.ipynb` — offline scaffold + debug dashboard

Everything the harness does, re-implemented in one notebook against a 6-listing pseudo pool. Lets teammates iterate on the 4 participant functions without running FastAPI.

### What's inside

1. **Schemas** — dataclasses mirroring the harness's pydantic models (`HardFilters`, `ListingData`, `RankedListingResult`).
2. **Four participant stubs** — `extract_hard_facts`, `extract_soft_facts`, `filter_soft_facts`, `rank_listings`. Signatures match `challenge_harness/app/participant/*.py` exactly; copy function bodies directly into the harness when done.
3. **`search(query)`** — wires the five pipeline stages and records per-stage timings.
4. **Dashboard** — three focused sections:
   - **Extracted filters** — two colour-coded tables (🔴 HARD / 🔵 SOFT). Auto-renders the parser's constraint-schema output if the pipeline attaches it at `soft_facts['parsed']`; otherwise falls back to the legacy HardFilters dict (lifted into the same visual shape).
   - **Candidate funnel** — one-liner: pool → after hard filter → after soft filter.
   - **Ranked results** — compact top-10 table with highlighted #1, tabular-aligned numbers, and per-listing reasons.
5. **Map view** — Airbnb-style price pins at each listing's lat/lon.

### How to run

```bash
cd repo
uv sync
uv run jupyter lab notebooks/prototype.ipynb
```

Run top-to-bottom. `show_results(search("…"))` gives the lean view; `dashboard(search("…"))` gives the debug view. No harness, no tunnel, no data dependencies.

### How teammates plug in their real code

Replace the body of any of the four stub functions with their implementation. The signatures don't change, so nothing downstream (dashboard, map) needs updating. When happy, copy the function body into the matching file under `challenge_harness/app/participant/`.

---

## `demo.ipynb` — live demo against the public API

Thin client. Posts queries to the deployed `POST /listings` endpoint, renders the response exactly the way judges will see it.

### What's inside

- `search(query)` → `requests.post(f'{API_BASE}/listings', …)`.
- Ranked table + folium map with images, prices, and reasons (same visual as `prototype.ipynb`, reading from the live response).
- Three example queries; change the cells or add your own.

### How `API_BASE` resolves

The notebook's first code cell loads `API_BASE` in this order:

1. `ROBINREAL_API_BASE` env var — set before `jupyter lab` to override.
2. `repo/.api_base` file — written automatically by [`scripts/start_tunnel.sh`](../scripts/start_tunnel.sh).
3. `http://localhost:8000` — fallback for local-only testing.

This is why a tunnel restart no longer requires editing the notebook.

### Running the live demo end-to-end

Three terminals:

```bash
# Terminal 1 — FastAPI harness
cd "challenge harness"
uv run uvicorn app.main:app --port 8000
```

```bash
# Terminal 2 — Cloudflare quick tunnel, writes .api_base for the notebook
cd repo
./scripts/start_tunnel.sh              # or ./scripts/start_tunnel.sh 8001
```

Cloudflared prints the public URL and stamps it into `.api_base`. Copy that URL if you're submitting it as the public HTTPS route.

```bash
# Terminal 3 — Jupyter
cd repo
uv run jupyter lab notebooks/demo.ipynb
```

Run the first code cell — it should print `API_BASE = https://<something>.trycloudflare.com`. Run the rest to see live query results.

### Local-only mode (no tunnel)

Skip Terminal 2 entirely. With `.api_base` absent and `ROBINREAL_API_BASE` unset, the notebook falls back to `http://localhost:8000`. Useful for debugging the pipeline without exposing anything publicly.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ConnectionRefusedError` on every query | Harness not running | Start uvicorn in Terminal 1 |
| `API_BASE = http://localhost:8000` but tunnel is up | `.api_base` empty or missing | Restart `scripts/start_tunnel.sh`; wait for the URL line; re-run the first notebook cell |
| Notebook works locally, breaks via tunnel | Cloudflared died, URL now points nowhere | Relaunch `scripts/start_tunnel.sh` (new URL auto-writes) |
| `prototype.ipynb` shows old legacy filter view instead of HARD/SOFT tables | Pipeline isn't attaching parsed output yet | Expected until teammates' parser is wired into `extract_soft_facts`; the legacy view is the fallback |
| `JSONDecodeError` on a query | Harness error — check the uvicorn terminal for a Python traceback | |
