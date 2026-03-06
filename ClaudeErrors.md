# Claude Errors Log

Automatically captured by PostToolUseFailure hook. Review with `/learn`.

## 2026-03-06 12:34:51 — Bash error

**Input**: `ssh holdsworth "cd ~/cook && git pull && /home/holdsworth/.local/bin/uv sync --group dev && /home/holdsworth/.local/bin/uv run pytest tests/test_scoring.py tests/test_request_processor.py tests/tes...`
**Error**: Exit code 2
From https://github.com/Holdsworth-Ecosystem/cook
   bc200a8..6bfb9ec  main       -> origin/main
Updating bc200a8..6bfb9ec
Fast-forward
 tests/conftest.py               |  78 +++++++++++
 tests/test_cook_tool.py         | 123 +++++++++++++++++
 tests/test_handlers.py          | 223 ++++++++++++++++++++++++++++++
 tests/test_request_processor.py |  89 ++++++++++++
 tests/test_scoring.py           | 292 ++++++++++++++++++++++++++++++++++++++++
 5 files changed, 805 insertions(+)
 cr...
**Project**: /mnt/c/projects/Holdsworth2/cook

## 2026-03-06 12:34:59 — Bash error

**Input**: `ssh holdsworth "cd ~/cook && /home/holdsworth/.local/bin/uv sync --extra dev && /home/holdsworth/.local/bin/uv run pytest tests/test_scoring.py tests/test_request_processor.py tests/test_handlers.p...`
**Error**: Exit code 1
Resolved 110 packages in 1ms
Installed 5 packages in 4ms
 + iniconfig==2.3.0
 + pluggy==1.6.0
 + pytest==9.0.2
 + pytest-asyncio==1.3.0
 + pytest-mock==3.15.1
============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-9.0.2, pluggy-1.6.0 -- /home/holdsworth/cook/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/holdsworth/cook
configfile: pyproject.toml
plugins: asyncio-1.3.0, mock-3.15.1, anyio-4.12.1
asyncio: ...
**Project**: /mnt/c/projects/Holdsworth2/cook

