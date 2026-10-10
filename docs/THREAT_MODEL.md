# Initial threat model (scope, not implemented controls)

## Assets
Provider credentials, private files and identities, tool capabilities, traces,
outbound network access, and per-run/day budgets.

## Trust boundaries
System/developer/user instructions are privileged. Future retrieved files and
HTTP/tool responses are untrusted data, never authorization. A model's wish
to call a tool is not itself permission.

## Threats to test
Prompt injection (including fake system messages), tool misuse, filesystem
traversal and symlink escapes, SSRF and rebinding, SQL writes, outbound canary
leaks, unapproved side effects, log/fixture secret leakage, and budget races.

## M0 implemented controls
Default offline provider choice, zero USD spend defaults, SQLite transactional
budget accounting, replay-only cassettes with explicit fingerprint failure.

## Residual risk
**Prompt-injection defenses are not implemented.** Even after M4, instruction
hierarchy and prompt-level defenses alone cannot guarantee immunity; successful
attacks and benign false refusals must be measured side by side. Do not attach
real secrets or credentials to unreviewed fixtures.
