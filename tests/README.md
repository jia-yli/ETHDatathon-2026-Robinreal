```shell
uv sync --dev

uv run python scripts/install_cloudflared.py

export DASHSCOPE_API_KEY=<YOUR_QWEN_API_KEY>
export DEEPSEEK_API_KEY=<YOUR_DEEPSEEK_API_KEY>

# serving and test
#uv run uvicorn app.main:app --reload
uv run python scripts/serve.py --export-url 
curl -X POST "$(cat .tunnel_url)/listings" \
  -H "content-type: application/json" \
  -d '{
    "query": "Ich suche etwas Kleineres in Lausanne, möglichst in der Nähe von EPFL, gern möbliert, unter 2100 CHF, mit guter Anbindung, und am besten in einer Ecke, die sich sicher, entspannt und nicht komplett anonym anfühlt.",
    "limit": 25,
    "offset": 0
  }'
curl -X POST http://localhost:8000/listings \
  -H "content-type: application/json" \
  -d '{
    "query": "Ich suche etwas Kleineres in Lausanne, möglichst in der Nähe von EPFL, gern möbliert, unter 2100 CHF, mit guter Anbindung, und am besten in einer Ecke, die sich sicher, entspannt und nicht komplett anonym anfühlt.",
    "limit": 25,
    "offset": 0
  }'

# [for dev] test the pipeline (but please have 'data/listings.db' first)
export DEEPSEEK_API_KEY=<YOUR_DEEPSEEK_API_KEY>
uv run pytest tests/test_ranking.py::test_with_query -q -s
uv run pytest tests/test_ranking.py::test_non_residential_query -q -s
```