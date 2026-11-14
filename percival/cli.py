"""Offline-first terminal conversation."""
from __future__ import annotations

import argparse
from math import isfinite
from pathlib import Path
import re
import sys

from .model_config import DEFAULT_CONFIG, REASONING_MODES, ModelSettings, load_registry, local_tag
from .ollama import LocalOllama

DEFAULT_ORIGIN = "http://127.0.0.1:11434"


def _installed_models(client: LocalOllama, timeout: float) -> set[str]:
    installed = set()
    for name in client.list_models(timeout):
        try:
            installed.add(local_tag(name))
        except ValueError:
            continue
    return installed


def _thinking_mode(reasoning: str, metadata: dict) -> bool | None:
    if reasoning == "default":
        return None
    thinking = metadata.get("thinking")
    values = thinking.get("values") if isinstance(thinking, dict) else None
    requested = reasoning == "on"
    if isinstance(values, list) and requested not in values:
        # Some Qwen3 templates require thinking. Keep Ollama's parser active
        # so the trace stays in message.thinking, outside the final answer.
        return True if values == [True] else None
    capabilities = metadata.get("capabilities")
    if isinstance(capabilities, list) and "thinking" not in capabilities:
        return None
    return requested


def _final_answer(payload: dict) -> str:
    if payload.get("done_reason") == "length":
        raise ValueError("output limit reached before a complete final reply")
    message = payload.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ValueError("Ollama returned no final reply")
    # Older model templates can return an inline trace. Discard through the last
    # closing tag, and discard any remaining answer with an unclosed trace.
    answer = re.split(r"</think\s*>", content, flags=re.IGNORECASE)[-1].strip()
    if not answer or re.search(r"<think\b", answer, flags=re.IGNORECASE):
        raise ValueError("Ollama returned no final reply")
    return answer


def chat(model: str | None, origin: str, timeout: float = 90, *,
         config: Path = DEFAULT_CONFIG, agent: str | None = None,
         reasoning: str | None = None) -> int:
    try:
        registry = load_registry(config)
        profile_name = registry.default_agent if agent is None else agent
        if profile_name not in registry.agents:
            raise ValueError(f"Unknown agent: {profile_name}")
        profile = registry.agents[profile_name]
        candidates = (local_tag(model),) if model is not None else profile.models
        client = LocalOllama(origin)
        installed = _installed_models(client, min(timeout, 5))
        available = [tag for tag in candidates if tag in installed]
        if not available:
            raise ValueError(f"No configured local model installed ({', '.join(candidates)}). Run 'ollama list'.")
    except (OSError, ValueError) as exc:
        print(f"Percival: {exc}", file=sys.stderr)
        return 1

    system = {"role": "system", "content": profile.instructions}
    history = []
    print(f"\nPERCIVAL | LOCAL TERMINAL\nAgent: {profile_name}\nModel: {available[0]}"
          f"\nInference: {client.origin}\nCloud access: DISABLED\n"
          "Type /exit to leave, /reset to clear context.\n")
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0
        if message.lower() in ("/exit", "/quit"):
            print("Goodbye.")
            return 0
        if message.lower() == "/reset":
            history.clear()
            print("Conversation context cleared.\n")
            continue
        if not message:
            continue

        user = {"role": "user", "content": message}
        for tag in available:
            settings = registry.models.get(tag, ModelSettings())
            try:
                metadata = client.show_model(tag, min(timeout, 5))
                if metadata.get("remote_host") or metadata.get("remote_model"):
                    raise ValueError("Ollama identifies this model as remote")
                payload = client.chat(tag, [system, *history, user], {
                    "num_ctx": settings.context_tokens,
                    "num_predict": settings.output_tokens,
                }, think=_thinking_mode(reasoning or profile.reasoning, metadata), timeout=timeout)
                answer = _final_answer(payload)
            except (OSError, ValueError) as exc:
                print(f"Percival: {tag} failed ({exc}).", file=sys.stderr)
                continue
            history = [*history, user, {"role": "assistant", "content": answer}][-20:]
            label = "Percival" if tag == available[0] else f"Percival ({tag})"
            print(f"{label}: {answer}\n")
            break
        else:
            print("Percival: No local model produced a reply.\n", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="percival")
    sub = parser.add_subparsers(dest="command", required=True)
    chat_parser = sub.add_parser("chat", help="Talk to a local Ollama model")
    chat_parser.add_argument("--agent", help="Select an agent profile from the model registry")
    chat_parser.add_argument("--model", help="Use one installed Ollama tag explicitly")
    chat_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    chat_parser.add_argument("--reasoning", choices=REASONING_MODES)
    models_parser = sub.add_parser("models", help="List installed Ollama model tags")
    for command in (chat_parser, models_parser):
        command.add_argument("--origin", default=DEFAULT_ORIGIN)
        command.add_argument("--timeout", type=float, default=90)

    args = parser.parse_args(argv)
    if not isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite positive number")
    if args.command == "chat":
        return chat(args.model, args.origin, args.timeout,
                    config=args.config, agent=args.agent, reasoning=args.reasoning)
    try:
        installed = _installed_models(LocalOllama(args.origin), min(args.timeout, 5))
    except (OSError, ValueError) as exc:
        print(f"Percival: Could not list local models ({exc}).", file=sys.stderr)
        return 1
    print("\n".join(sorted(installed)) if installed else "No installed local model tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
