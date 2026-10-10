# Data and dependency provenance

## Data
M0 uses **no training, evaluation, identity, biometric, or personal datasets**.
Unit tests create synthetic in-memory/temp-directory fixtures only.

## Third-party dependencies
Version pins live in `pyproject.toml`; transitive dependencies are **not locked**
until a `uv.lock` is produced and validated on a networked development machine.
Before release, verify every direct/transitive license against its installed wheel
metadata and upstream license text. Current recorded items are preliminary:

| Dependency | Intended use | License review status |
| --- | --- | --- |
| pydantic, pydantic-settings | validation/configuration | Pending detailed release verification |
| httpx | future HTTP provider client | Pending detailed release verification |
| typer, rich | CLI/display | Pending detailed release verification |
| pytest, pytest-cov, pytest-asyncio | tests | Pending detailed release verification |
| hypothesis | property-based tests | MPL-2.0 (verify selected release) |
| ruff, mypy, pre-commit, pip-audit | quality/security tooling | Pending detailed release verification |
| setuptools | build backend | Pending detailed release verification |

No model, dataset, or dependency is claimed to be cleared for commercial use
without checking its exact version and license. Add checksums for future data
download scripts; never commit restricted data or model weights.
