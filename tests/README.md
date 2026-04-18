```shell
export DASHSCOPE_API_KEY=<YOUR_QWEN_API_KEY>

uv run pytest tests/test_ranking.py::test_with_query_and_soft_constraints -q -s
```