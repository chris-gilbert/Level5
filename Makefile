.PHONY: dev lint format test serve contract-build smoke-setup test-deposit clean

PLATFORM_TOOLS_VERSION ?= v1.53

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
	uv run uvicorn level5.proxy.main:app --reload --host 0.0.0.0 --port 18515

contract-build:
	cd contracts/sovereign-contract && cargo-build-sbf --tools-version $(PLATFORM_TOOLS_VERSION)
	cd contracts/sovereign-contract && anchor idl build -o target/idl/sovereign_contract.json

smoke-setup:
	uv run python scripts/smoke_setup.py

test-deposit:
	cd contracts/sovereign-contract && node ../../scripts/test_deposit.js

audit:
	uv run pip-audit

clean:
	rm -rf .ruff_cache/ .pytest_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true
