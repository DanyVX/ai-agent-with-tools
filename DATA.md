# Data, package and license provenance

## Data
No human imagery, biometric documents, real emails, real customer records or
trained model weights are committed. The sandbox sample database contains
three synthetic products and a synthetic text file. Attack cases contain **planted
fake canary strings** and fake email destinations under `.invalid` domains.

Generated 40 benign and 30 adversarial cases are project-owned synthetic code;
the list is deterministic and reviewed in `eval/tasks/` and `eval/adversarial/`.

## Dependencies

The precise installed version of each package is the one recorded in
`pyproject.toml`; transitive dependency pinning via `uv.lock` is pending.
License terms should be independently verified against the exact installed
distribution and its upstream official license before release.

| Package | Role | Review status |
| --- | --- | --- |
| pydantic / pydantic-settings | Contracts and env | Exact wheel license review pending |
| httpx | Provider HTTP transport | Exact wheel license review pending |
| typer / rich | CLI and terminal traces | Exact wheel license review pending |
| pytest / pytest-asyncio / pytest-cov / hypothesis | Tests | Exact wheel license review pending |
| ruff / mypy / pre-commit / pip-audit | Quality and security | Exact wheel license review pending |
| setuptools | Build | Exact wheel license review pending |

No AGPL or noncommercial component is knowingly distributed, but that is
**not proof of a complete license audit**. New models or datasets require a
new entry with source URL, license, checksum and permission rationale.
