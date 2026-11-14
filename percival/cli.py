"""Minimal offline-first terminal conversation smoke test."""
from __future__ import annotations
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .ollama import LocalOllama

SYSTEM = ("You are Percival, a composed and discreet British personal steward. "
          "Be concise, natural, and helpful, with occasional dry wit. "
          "Do not claim to have performed actions or accessed tools. "
          "You are running in a local terminal smoke test with no tools.")


def chat(model: str, origin: str, timeout: float = 90) -> int:
    client = LocalOllama(origin)
    history = [{"role": "system", "content": SYSTEM}]
    print(f"\nPERCIVAL | LOCAL TERMINAL\nModel: {model}\nInference: {client.origin}\nCloud access: DISABLED\nType /exit to leave, /reset to clear context.\n")
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
            history = history[:1]
            print("Conversation context cleared.\n")
            continue
        if not message:
            continue
        candidate = history + [{"role": "user", "content": message}]
        # Limit retained context; no transcript is persisted to disk.
        candidate = [candidate[0]] + candidate[1:][-20:]
        request = Request(client.origin + "/api/chat", data=json.dumps({
            "model": model, "messages": candidate, "stream": False, "think": False,
            "options": {"num_predict": 512}
        }).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            answer = payload["message"].get("content", "").strip()
            if not answer:
                print("Percival: Ollama returned no final response. Try another prompt or model.\\n", file=sys.stderr)
                continue
        except (URLError, HTTPError, TimeoutError, KeyError, ValueError) as exc:
            print(f"Percival: Local inference failed ({exc}). Check 'ollama serve' and 'ollama list'.\\n", file=sys.stderr)
            continue
        history = candidate + [{"role": "assistant", "content": answer}]
        print(f"Percival: {answer}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="percival")
    sub = parser.add_subparsers(dest="command", required=True)
    chat_parser = sub.add_parser("chat", help="Talk to a local Ollama model")
    chat_parser.add_argument("--model", default="gpt-oss:20b")
    chat_parser.add_argument("--origin", default="http://127.0.0.1:11434")
    chat_parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args(argv)
    if args.command == "chat":
        return chat(args.model, args.origin, args.timeout)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
