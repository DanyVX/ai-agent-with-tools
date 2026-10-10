# Security policy

AgentX is a portfolio/runtime research project, not a production security
boundary. Do not use with real customer data, biometrics, sensitive ID documents,
shared hostile sandboxes, or unsupervised side effects.

Report security issues privately to the repository owner; do not place live keys,
detailed exploit paths or private records in public GitHub issues. If a secret
appears in Git history, rotate/revoke it immediately; deletion alone is insufficient.

The default mode is offline, with USD 0 spending caps and default-deny approvals.
Live HTTP fetch is intentionally disabled. See `docs/THREAT_MODEL.md` for
attack classes and known bypass possibilities. Redaction is best-effort.
