# OpenClaw integration architecture

Percival is an installable OpenClaw agent persona and tool suite backed by a portable mission service.

## Distribution
1. Agent workspace instructions define persona and interaction policy.
2. Skills describe bounded procedures (journey planning, morning briefing, fare comparison).
3. A plugin supplies typed, permission-checked tool interfaces.
4. Percival Core persists mission states, decision evidence, and audit events independently of the host.

## Deployment profiles
- Single Mac: Gateway and Percival Core on one machine.
- Mac mini plus MacBook: always-on Gateway and paired MacBook node.
- Multiple Macs: one Gateway and approved nodes, with optional separately managed model workers.

## Security
No remote command execution without host-level approvals and allowlists. Never grant unrestricted shell access to an untrusted node. Use least privilege and explicit consent for spending, messaging, calendar edits, and bookings. Store secrets outside source control.

## Verification
Test against pinned OpenClaw versions; verify skill loading, node pairing, permission enforcement, failure recovery, and offline behavior. Do not claim tested hardware compatibility without testing.

References: https://docs.openclaw.ai/ and https://github.com/openclaw/openclaw
