# Local inference and clanker food budgets (M0)

## Default policy
- Local model is always preferred if it satisfies the task's declared capabilities.
- Cloud fallback is disabled by default and is never automatic in M0.
- Sensitive tasks remain local unless the operator explicitly changes policy.
- No cloud API adapter is implemented in M0.
- The Ollama adapter accepts numeric loopback HTTP origins only. It does not provide remote access to additional Macs.

## Budget accounting
BudgetLedger stores integer micro-USD allocations and atomic reservations in SQLite. An agent cannot reserve above its cap. Reservation IDs cannot be reused. Settlement rejects a charge exceeding its reservation and requires manual reconciliation. The ledger is a local enforcement primitive, **not** a provider-side spending cap. Actual provider charges may arrive later or exceed estimates, so future cloud adapters must also enforce account-level limits and reconcile billing data.

## Known limits
- Per-agent wall-clock and token limits are not yet enforced end-to-end; the Ollama adapter sets request timeout and maximum generated tokens, but this is not a full fleet-wide quota.
- No model discovery, actual model performance benchmarks, cloud integration, OpenClaw plugin, or multi-device inference scheduler is implemented.
- SQLite is intended for one host and local processes, not a shared network filesystem.
- No automatic provider price scraping or model arbitration is implemented.
- A model's advertised capabilities are configuration inputs, not verified benchmark results.

## Running tests
```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Security
Use a dedicated least-privilege service identity. Do not expose Ollama to the public network. Keep all credentials and private mission data out of the repository. Any future OpenClaw tools must enforce these policies outside the prompt layer.
