# Contributing

Read `CLAUDE.md` and `docs/PROJECT_SPEC.md`. One milestone per branch/PR,
small Conventional Commits, no merge before lint/types/tests/CI pass.

```console
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src/agentx
python -m pytest -m "not slow and not gpu"
python -m pip_audit --local --progress-spinner off
```

Do not commit `.env`, credentials, personal data, real emails, datasets,
model weights or benchmark estimates. Add regression tests for every bug.
Use synthetic fixtures by default. Report real failures and residual security
risks in the docs rather than hiding them behind broad exception catches.
