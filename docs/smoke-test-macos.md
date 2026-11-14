# Mac mini terminal smoke test

Use Python 3.11+ and a current Ollama release with support for explicit
`:local` model requests. The procedures below were developed with Ollama
0.40.15. Run these commands in a separate checkout so your current branch
and local files stay in place.

```bash
git clone --branch feature/model-agents https://github.com/softnessasastrength/percival.git percival-model-agents
cd percival-model-agents
```

Start Ollama on its default loopback address and install the primary model.
Install the second model to exercise fallback.

```bash
ollama pull qwen3:4b
ollama pull llama3.2:3b
bash scripts/bootstrap-macos.sh
./.local/bin/percival models
./.local/bin/percival chat
```

Pulls and Python dependency installation need network access. With setup
complete, chat runs offline. To also disable cloud features for the entire
Ollama server, start it with `OLLAMA_NO_CLOUD=1 ollama serve` after quitting
any running Ollama app or server.

## Conversation

1. Confirm the banner shows `qwen3:4b`, loopback inference and disabled cloud access.
2. Enter `Good morning, Percival.` Expect a concise reply. Check for draft deliberations, thinking tags or a blank reply.
3. Enter `Remember the code word is teacup for this chat. Confirm in a few words.` Then ask `What code word did I give you? Answer in one word.` Expect `teacup`.
4. Enter `/reset` and repeat the question. Expect Percival to have lost the code word. Enter `/exit` to end the session.
5. Repeat the greeting with `chat --reasoning on`. The terminal should still show just the final reply.

## Fallback and outage

To test a missing primary without removing an installed model, copy
`percival/models.yaml` to `percival/models-smoke.yaml`. Replace every occurrence
of `qwen3:4b` with `qwen3:missing-smoke`. Then run
`./.local/bin/percival chat --config percival/models-smoke.yaml`. Expect the
banner to show `llama3.2:3b` and make sure it answers the greeting. Remove the
temporary config after the test.

With Ollama stopped, run `./.local/bin/percival chat` again. Expect a local
connection error and a nonzero exit. If Ollama stops mid-session, the turn
should fail with a local error and the terminal should accept another prompt.

## Troubleshooting

- Run `ollama list` or `./.local/bin/percival models` to see installed tags.
- Run `curl http://127.0.0.1:11434/api/tags` to verify the local service.
- If the terminal reports an output limit, try the configured fallback or
  adjust `output_tokens` and `context_tokens` in a copy of the registry.
- Use `./.local/bin/percival chat --model llama3.2:3b` to isolate the fallback.
