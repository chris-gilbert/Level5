.PHONY: dev lint format test serve clean

dev:
	uv sync --all-groups

lint:
	uv run ruff format --check . && uv run ruff check .

format:
	uv run ruff format . && uv run ruff check --fix .

test:
	uv run pytest

test-fast:
	uv run pytest -x -q --no-cov

serve:
	uv run uvicorn level5.proxy.main:app --reload --host 0.0.0.0 --port 8000

audit:
	uv run pip-audit

clean:
	rm -rf .ruff_cache/ .pytest_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true
