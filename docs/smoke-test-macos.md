# Mac mini terminal smoke test

This test runs local Ollama inference only. It does not require OpenClaw, API keys, or cloud services. It does require network access for the initial Git clone and Python dependency installation if needed.

## Checkout before merge
This smoke-test branch is based on `feature/m0-foundation`. Until both PRs are reviewed and merged, clone the **smoke-test branch**, not `main`:

```bash
git clone --branch feature/m1-terminal-smoke https://github.com/softnessasastrength/percival.git
cd percival
bash scripts/bootstrap-macos.sh
./.local/bin/percival chat
```

The bootstrap script intentionally does not install Ollama or download a model automatically. If missing, install Ollama, start it, and run `ollama pull gpt-oss:20b`. Then rerun bootstrap.

## Manual equivalent
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m percival chat --model gpt-oss:20b
```

## Success criteria
- Startup reports loopback inference and cloud access disabled.
- The assistant responds to a greeting.
- Follow-up references prior turn in the same session.
- `/reset` clears conversational context.
- `/exit` quits cleanly.
- Disconnecting Ollama yields an error without switching to cloud inference.

## Limitations
- Terminal conversation is in memory only; no saved transcripts.
- Ollama endpoint is restricted to numeric loopback addresses.
- No tools, calendar, messaging, autonomous actions, or OpenClaw bridge.
- The request has a timeout and output-token cap but not a comprehensive resource quota.
- Local model quality and Mac mini performance are not yet verified.
- No actual speech input/output: 'talking' means terminal text conversation.

## Troubleshooting
Run `ollama list` to check the model, and `curl http://127.0.0.1:11434/api/tags` to verify Ollama is serving locally.
