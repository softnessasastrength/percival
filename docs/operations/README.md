# Percival Operations & Observability (initial slice)

This first implementation intentionally provides **read-only** health checks. No automatic updates, process restarts, LAN scanning, SSH, arbitrary shell execution, or privilege escalation.

## Run on Mac mini
After installing the terminal smoke-test branch dependencies:

```bash
.venv/bin/python -m percival.operations
.venv/bin/python -m percival.operations --poll 60 --count 5
```

Checks currently cover Ollama `/api/tags` on loopback and free disk space. JSON output includes statuses and timestamps. This is **liveness and inventory**, not proof of model inference readiness. An HTTPS endpoint check function exists but is not wired into automatic polling; it must be called with a specifically approved URL. Its redirect behavior and DNS rebinding risks require hardening before any untrusted configuration or network deployment.

## Future milestones
1. Add an authenticated local control API and persistent audit log.
2. Model inference readiness check with a bounded synthetic prompt.
3. Signed or authenticated model provenance and update advisories, never silent replacement.
4. Validated network endpoint allowlist with DNS/IP enforcement and redirect rejection.
5. macOS launchd packaging with explicit installation approval, least-privilege service identity, and bounded retention.
6. Memory, CPU, thermal, and process metrics; structured alert thresholds.
7. Approved remediation requests requiring human confirmation.

## Security constraints
Never treat model output as authority to add endpoints or run commands. Keep network access constrained at the OS level where possible. Do not expose private addresses or access tokens in the public repository. Polling requires explicit invocation and has a finite count.
